"""Merge multi-resolution grids, apply masks, calculate urban/free-field ratios."""

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from blastlib import constants
from blastlib.processing.ff_reference import impulse_converged


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


def process_grids(data, params, weight=None):
    """Merge 3 grids, apply threshold masks, compute urban/free-field ratios.

    params keys:
        thresholdP_kPa  — mask threshold (cells below this → NaN)
        minPressure_kPa — pressure convergence band (kPa, absolute)
        thr_I_scaled    — impulse convergence band (Pa.s/kg^(1/3)), optional;
                          defaults to constants.IMPULSE_CRITERION

    weight : charge weight [kg], required for the impulse criterion. Passing
        None falls back to the legacy pressure-gated impulse rule, which is
        retained only so old callers keep working — it is not admissible under
        Hopkinson-Cranz (see constants.IMPULSE_CRITERION).

    Returns dict (out) with processed grids, ratios, and scale limits.
    """
    threshold_p  = params['thresholdP_kPa']
    min_pressure = params['minPressure_kPa']
    thr_I_scaled = params.get('thr_I_scaled',
                              constants.IMPULSE_CRITERION['thr_I_scaled'])

    out = {}
    for k in ('X1', 'Z1', 'X2', 'Z2', 'X3', 'Z3'):
        out[k] = data[k]

    peakP1   = data['peakP1'].copy()
    peakP2   = data['peakP2'].copy()
    peakP3   = data['peakP3'].copy()
    impulse1 = data['impulse1'].copy()
    impulse2 = data['impulse2'].copy()
    impulse3 = data['impulse3'].copy()
    refP1    = data['refP1'].copy()
    refP2    = data['refP2'].copy()
    refP3    = data['refP3'].copy()
    refI1    = data['refI1'].copy()
    refI2    = data['refI2'].copy()
    refI3    = data['refI3'].copy()

    # Save raw pressure for threshold check (before any modification)
    peakP1_raw = data['peakP1'].copy()
    peakP2_raw = data['peakP2'].copy()
    peakP3_raw = data['peakP3'].copy()

    # Fill missing values: fine grid filled from medium grid
    peakP2_interp   = _interp2_linear(out['X2'], out['Z2'], peakP2,   out['X1'], out['Z1'])
    impulse2_interp = _interp2_linear(out['X2'], out['Z2'], impulse2, out['X1'], out['Z1'])
    refP2_interp    = _interp2_linear(out['X2'], out['Z2'], refP2,    out['X1'], out['Z1'])
    refI2_interp    = _interp2_linear(out['X2'], out['Z2'], refI2,    out['X1'], out['Z1'])

    # np.maximum propagates NaN (if either operand is NaN → NaN)
    peakP1   = np.maximum(peakP1,   peakP2_interp)
    impulse1 = np.maximum(impulse1, impulse2_interp)
    refP1    = np.maximum(refP1,    refP2_interp)
    refI1    = np.maximum(refI1,    refI2_interp)

    # Fill missing values: medium grid filled from coarse grid
    peakP3_interp   = _interp2_linear(out['X3'], out['Z3'], peakP3,   out['X2'], out['Z2'])
    impulse3_interp = _interp2_linear(out['X3'], out['Z3'], impulse3, out['X2'], out['Z2'])
    refP3_interp    = _interp2_linear(out['X3'], out['Z3'], refP3,    out['X2'], out['Z2'])
    refI3_interp    = _interp2_linear(out['X3'], out['Z3'], refI3,    out['X2'], out['Z2'])

    peakP2   = np.maximum(peakP2,   peakP3_interp)
    impulse2 = np.maximum(impulse2, impulse3_interp)
    refP2    = np.maximum(refP2,    refP3_interp)
    refI2    = np.maximum(refI2,    refI3_interp)

    # Save for Figure 1 (absolute values plot, before mask)
    out['peakP1_orig']   = peakP1.copy()
    out['peakP2_orig']   = peakP2.copy()
    out['peakP3_orig']   = peakP3.copy()
    out['impulse1_orig'] = impulse1.copy()
    out['impulse2_orig'] = impulse2.copy()
    out['impulse3_orig'] = impulse3.copy()

    # Create pressure threshold masks
    mask1 = peakP1 <= threshold_p
    mask2 = peakP2 <= threshold_p
    mask3 = peakP3 <= threshold_p

    # Apply masks to orig arrays (for Figure 1)
    out['peakP1_orig'][mask1]   = np.nan
    out['peakP2_orig'][mask2]   = np.nan
    out['peakP3_orig'][mask3]   = np.nan
    out['impulse1_orig'][mask1] = np.nan
    out['impulse2_orig'][mask2] = np.nan
    out['impulse3_orig'][mask3] = np.nan

    # Apply masks for ratio calculation
    peakP1[mask1]   = np.nan;  impulse1[mask1] = np.nan
    peakP2[mask2]   = np.nan;  impulse2[mask2] = np.nan
    peakP3[mask3]   = np.nan;  impulse3[mask3] = np.nan

    # Calculate urban / free-field ratios
    out['ratioP1'] = peakP1   / refP1
    out['ratioP2'] = peakP2   / refP2
    out['ratioP3'] = peakP3   / refP3
    out['ratioI1'] = impulse1 / refI1
    out['ratioI2'] = impulse2 / refI2
    out['ratioI3'] = impulse3 / refI3

    # Smart cut: zero out medium grid where fine grid has valid data
    xMax1 = out['X1'].max();  zMax1 = out['Z1'].max()
    mask1_interp = _interp2_nearest(
        out['X1'], out['Z1'], mask1.astype(float), out['X2'], out['Z2'], fill_value=1.0
    )
    cut_mask2 = (out['X2'] <= xMax1) & (out['Z2'] <= zMax1) & (mask1_interp == 0)

    out['peakP2_orig'][cut_mask2]   = np.nan
    out['impulse2_orig'][cut_mask2] = np.nan
    out['ratioP2'][cut_mask2]       = np.nan
    out['ratioI2'][cut_mask2]       = np.nan

    # Smart cut: zero out coarse grid where medium grid has valid data
    xMax2 = out['X2'].max();  zMax2 = out['Z2'].max()
    mask2_interp = _interp2_nearest(
        out['X2'], out['Z2'], (mask2 | cut_mask2).astype(float),
        out['X3'], out['Z3'], fill_value=1.0
    )
    cut_mask3 = (out['X3'] <= xMax2) & (out['Z3'] <= zMax2) & (mask2_interp == 0)

    out['peakP3_orig'][cut_mask3]   = np.nan
    out['impulse3_orig'][cut_mask3] = np.nan
    out['ratioP3'][cut_mask3]       = np.nan
    out['ratioI3'][cut_mask3]       = np.nan

    # ---- Force ratio = 1 where the field counts as converged ----
    #
    # PRESSURE: unchanged — below minPressure, or within minPressure of the
    # reference. Free-field pressure is a function of scaled distance alone
    # (cross-weight spread 4.7%), so an absolute kPa band picks one contour
    # for every charge weight and is admissible.
    #
    # IMPULSE: |I_urban - I_ref| / W^(1/3) < thr_I_scaled, and NOT gated on
    # pressure. The previous rule OR-ed in the low-pressure floor (which made
    # 94.5% of the decisions and pinned RadiusI to the 10 kPa contour) and
    # used an absolute Pa.s band, whose strictness varies as W^(1/3) — see
    # constants.IMPULSE_CRITERION.
    lowP1 = peakP1_raw < min_pressure
    lowP2 = peakP2_raw < min_pressure
    lowP3 = peakP3_raw < min_pressure

    small_diff_P1 = np.abs(peakP1_raw  - data['refP1']) < min_pressure
    small_diff_P2 = np.abs(peakP2_raw  - data['refP2']) < min_pressure
    small_diff_P3 = np.abs(peakP3_raw  - data['refP3']) < min_pressure

    conv_P1 = lowP1 | small_diff_P1
    conv_P2 = lowP2 | small_diff_P2
    conv_P3 = lowP3 | small_diff_P3

    if weight is None:
        # Legacy pressure-gated rule; kept only for backward compatibility.
        conv_I1 = lowP1 | (np.abs(data['impulse1'] - data['refI1']) < min_pressure)
        conv_I2 = lowP2 | (np.abs(data['impulse2'] - data['refI2']) < min_pressure)
        conv_I3 = lowP3 | (np.abs(data['impulse3'] - data['refI3']) < min_pressure)
    else:
        W13 = float(weight) ** (1 / 3)
        conv_I1 = impulse_converged(data['impulse1'], data['refI1'], W13, thr_I_scaled)
        conv_I2 = impulse_converged(data['impulse2'], data['refI2'], W13, thr_I_scaled)
        conv_I3 = impulse_converged(data['impulse3'], data['refI3'], W13, thr_I_scaled)

    for arr_name, conv_mask in (
        ('ratioP1', conv_P1), ('ratioP2', conv_P2), ('ratioP3', conv_P3),
        ('ratioI1', conv_I1), ('ratioI2', conv_I2), ('ratioI3', conv_I3),
    ):
        mask = conv_mask & ~np.isnan(out[arr_name])
        out[arr_name][mask] = 1.0

    # Scale for Figure 1 (80th percentile of absolute values)
    all_P = np.concatenate([out['peakP1_orig'].ravel(),
                             out['peakP2_orig'].ravel(),
                             out['peakP3_orig'].ravel()])
    all_I = np.concatenate([out['impulse1_orig'].ravel(),
                             out['impulse2_orig'].ravel(),
                             out['impulse3_orig'].ravel()])
    out['maxP'] = float(np.nanpercentile(all_P, 80))
    out['maxI'] = float(np.nanpercentile(all_I, 80))

    # Combined peak arrays for convergence radius calculation
    out['peakP_all'] = np.concatenate([peakP1.ravel(), peakP2.ravel(), peakP3.ravel()])
    out['peakI_all'] = np.concatenate([impulse1.ravel(), impulse2.ravel(), impulse3.ravel()])

    return out
