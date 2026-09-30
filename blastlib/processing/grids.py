"""Merge multi-resolution grids, apply masks, calculate urban/free-field ratios."""

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from blastlib import constants
from blastlib.processing.ff_reference import impulse_converged

# The solver writes exactly 1 Pa (0.001 kPa, float32) inside building
# footprints. Only that value marks a building; a cell the fine stage left
# empty (raw == 0) is not a building and keeps its filled value. DECISIONS.md
# D34, anchor 3.
BUILDING_SENTINEL_KPA = np.float32(0.001)

_GRIDS = ('1', '2', '3')


def _interp2_linear(X2, Z2, V2, X1, Z1, fill_value=None):
    """Bilinear resampling of grid (X2, Z2, V2) onto points (X1, Z1)."""
    x2_1d = X2[0, :]
    z2_1d = Z2[:, 0]
    rgi = RegularGridInterpolator(
        (z2_1d, x2_1d), V2, method='linear',
        bounds_error=False, fill_value=fill_value
    )
    pts = np.column_stack([Z1.ravel(), X1.ravel()])
    return rgi(pts).reshape(Z1.shape)


def _interp2_nearest(X2, Z2, V2, X1, Z1, fill_value=1.0):
    """Nearest-neighbour resampling of grid (X2, Z2, V2) onto points (X1, Z1)."""
    x2_1d = X2[0, :]
    z2_1d = Z2[:, 0]
    rgi = RegularGridInterpolator(
        (z2_1d, x2_1d), V2, method='nearest',
        bounds_error=False, fill_value=fill_value
    )
    pts = np.column_stack([Z1.ravel(), X1.ravel()])
    return rgi(pts).reshape(Z1.shape)


def building_mask(peakP_raw):
    """True on building-footprint cells: raw urban peak == the 0.001 kPa sentinel.

    peakP_raw : raw solver peak overpressure [kPa], any float dtype.
    Returns a bool array of the same shape. Compared in float32, the dtype
    the solver wrote, so a float64 copy of the field gives the same mask.
    """
    return np.asarray(peakP_raw).astype(np.float32) == BUILDING_SENTINEL_KPA


def process_grids(data, params, weight=None):
    """Merge 3 grids, mask buildings, compute urban/free-field ratios.

    DECISIONS.md D34 (adopted 2026-09-30). Each location takes the true peak
    of whichever stage captured the wave there, separately for the urban and
    the reference run, and the ratio compares those two:
      1. max-fill coarse -> fine (2 -> 1, then 3 -> 2), urban and reference
         separately, so a fine cell the wave never reached (raw == 0) takes
         the coarser, true value;
      2. mask building cells only (raw == 0.001 kPa sentinel);
      3. grid 1 inside its box (100 m), grid 2 inside its box (250 m), grid 3
         beyond; a coarser cell inside a finer box is always cut;
      4. ratios and every convergence criterion on the filled urban and
         filled reference fields.

    params keys:
        minPressure_kPa — pressure convergence band AND the pressure
                          damage-relevance floor (kPa, absolute). Since D35
                          the impulse floor is on the scaled impulse
                          (IMPULSE_CRITERION['floor_scaled']), not this.
        rel_band_I      — impulse relative-accuracy band (-), optional;
                          defaults to constants.IMPULSE_CRITERION
        thresholdP_kPa  — accepted, no longer used: the building mask is the
                          solver sentinel itself (D34)

    weight : charge weight [kg]. Any non-None value selects the production
        impulse criterion (D35), whose floor is I / W^(1/3), so W is needed.
        Passing None falls back to the legacy
        pressure-gated |dI| < minPressure rule, retained only so old callers
        keep working — its band is not admissible under Hopkinson-Cranz
        (see constants.IMPULSE_CRITERION).

    Returns dict (out) with processed grids, ratios, and scale limits. The
    keys peakP{g}_raw, refP{g}, refI{g} keep their historical names but hold
    the FILLED fields, the operands the criteria (hard and soft) act on.
    """
    min_pressure = params['minPressure_kPa']
    rel_band_I   = params.get('rel_band_I',
                              constants.IMPULSE_CRITERION['rel_band'])

    out = {k: data[k] for k in ('X1', 'Z1', 'X2', 'Z2', 'X3', 'Z3')}

    P  = {g: data[f'peakP{g}'].copy()   for g in _GRIDS}
    I  = {g: data[f'impulse{g}'].copy() for g in _GRIDS}
    RP = {g: data[f'refP{g}'].copy()    for g in _GRIDS}
    RI = {g: data[f'refI{g}'].copy()    for g in _GRIDS}

    # 1. Max-fill, finer from coarser: medium into fine first, then coarse
    # into medium. np.maximum propagates NaN.
    for gf, gc in (('1', '2'), ('2', '3')):
        src = (out[f'X{gc}'], out[f'Z{gc}'])
        tgt = (out[f'X{gf}'], out[f'Z{gf}'])
        P[gf]  = np.maximum(P[gf],  _interp2_linear(*src, P[gc],  *tgt))
        I[gf]  = np.maximum(I[gf],  _interp2_linear(*src, I[gc],  *tgt))
        RP[gf] = np.maximum(RP[gf], _interp2_linear(*src, RP[gc], *tgt))
        RI[gf] = np.maximum(RI[gf], _interp2_linear(*src, RI[gc], *tgt))

    # 2. Buildings only, from the RAW field. Masking the filled field let
    # wall-skin cells (raised by the coarser grid's interpolation across the
    # wall) into both scans: docs/audit/2026-09-27 ALG-01/PHY-01, D2. The old
    # test raw <= thresholdP_kPa also masked empty and partial fine cells,
    # which then let the coarser cell back in against its residual reference
    # (docs/audit/2026-09-30/merge.md MRG-01, D34).
    building = {g: building_mask(data[f'peakP{g}']) for g in _GRIDS}

    # 3. A coarser grid never re-enters a finer grid's box, whatever the
    # finer grid holds there. Supersedes the D31 cut keyed on the finer
    # mask, which re-admitted the coarser cell wherever the nearest finer
    # cell was masked: empty (MRG-01) or a wall (MRG-02). D34.
    cut = {'1': np.zeros_like(building['1'])}
    for gf, gc in (('1', '2'), ('2', '3')):
        cut[gc] = ((out[f'X{gc}'] <= out[f'X{gf}'].max())
                   & (out[f'Z{gc}'] <= out[f'Z{gf}'].max()))

    for g in _GRIDS:
        drop = building[g] | cut[g]
        Pm = P[g].astype(float)
        Im = I[g].astype(float)
        Pm[drop] = np.nan
        Im[drop] = np.nan
        out[f'peakP{g}_orig']   = Pm.copy()
        out[f'impulse{g}_orig'] = Im.copy()

        # Filled over filled; the reference is 0 only where the reference
        # run never saw the wave, which the ratio reports as inf/NaN.
        with np.errstate(divide='ignore', invalid='ignore'):
            out[f'ratioP{g}'] = Pm / RP[g]
            out[f'ratioI{g}'] = Im / RI[g]

        # 4. Operands of every criterion, hard here and soft downstream
        # (soft_criterion reads peakP{g}_raw, refP{g}, ratioP{g}_raw), are
        # the filled fields; the unforced ratios are kept before pinning.
        out[f'peakP{g}_raw']  = P[g]
        out[f'refP{g}']       = RP[g]
        out[f'refI{g}']       = RI[g]
        out[f'ratioP{g}_raw'] = out[f'ratioP{g}'].copy()
        out[f'ratioI{g}_raw'] = out[f'ratioI{g}'].copy()
        # MaxR level reads the filled reference (PHY-04 option (a)).
        out[f'refP{g}_fill']  = RP[g]
        out[f'refI{g}_fill']  = RI[g]

        # ---- Force ratio = 1 where the field counts as converged ----
        #
        # PRESSURE: below minPressure, or within minPressure of the
        # reference. Free-field pressure is a function of scaled distance
        # alone (cross-weight spread 4.7%), so an absolute kPa band picks one
        # contour for every charge weight and is admissible.
        #
        # IMPULSE (production, 2026-09-28 evening — physics audit verdict):
        # relative-accuracy band OR the SAME urban-pressure relevance floor
        # the pressure criterion uses — |dI|/I_ref < rel_band, or peakP <
        # minPressure. One relevance quantum for both loads.
        # [Corrected 2026-09-29, D24 review: P-I curves also have an impulse
        # asymptote; the rationale that holds is IATG 02.20 §8 — tiers
        # calibrated on NEQ of thousands of kg, so for W <= 1500 kg the
        # impulse accompanying 10 kPa is smaller and the floor is
        # conservative.] See ff_reference.impulse_converged,
        # constants.IMPULSE_CRITERION, and docs/audit/2026-09-28/physics.md
        # for the criterion history.
        # [Superseded 2026-09-30, DECISIONS.md D35 (c): the impulse floor is
        # now the urban SCALED impulse, I / W^(1/3) < 23.6 Pa.s/kg^(1/3) — the
        # reference scaled impulse where the reference overpressure is
        # 10 kPa, the same contour and IATG level as the pressure floor. The
        # D24 rule above is ff_reference.impulse_converged_pfloor.]
        lowP   = P[g] < min_pressure
        conv_P = lowP | (np.abs(P[g] - RP[g]) < min_pressure)
        if weight is None:
            # Legacy pressure-gated rule; kept only for backward compatibility.
            conv_I = lowP | (np.abs(I[g] - RI[g]) < min_pressure)
        else:
            conv_I = impulse_converged(I[g], RI[g], float(weight) ** (1 / 3),
                                       rel_band_I)

        for name, conv in ((f'ratioP{g}', conv_P), (f'ratioI{g}', conv_I)):
            pin = conv & ~np.isnan(out[name])
            out[name][pin] = 1.0

    # Scale for Figure 1 (80th percentile of absolute values)
    all_P = np.concatenate([out[f'peakP{g}_orig'].ravel()   for g in _GRIDS])
    all_I = np.concatenate([out[f'impulse{g}_orig'].ravel() for g in _GRIDS])
    out['maxP'] = float(np.nanpercentile(all_P, 80))
    out['maxI'] = float(np.nanpercentile(all_I, 80))

    # Combined peak arrays for convergence radius calculation (masked and cut)
    out['peakP_all'] = all_P
    out['peakI_all'] = all_I

    return out
