"""Free-field reference field, and the impulse convergence criterion.

Two things live here because they are used from two places — the normal
preprocessing path (grids.process_grids, which has the true reference VTK) and
the NPZ rebuild path (which does not, and reconstructs the reference from the
1-D free-field table).

RECONSTRUCTION ACCURACY — read before trusting a number that depends on it.
The reference recovered from free_field_data.csv agrees with the true
reference field to ~0.4% (impulse) and ~2.2% (pressure) for scaled distances
inside the tabulated range Z <= 20. Beyond Z=20 the curve is extrapolated as a
power law and CANNOT be validated at all: every far-field cell in the shipped
NPZs was overwritten to ratio=1 by the old threshold rule, so nothing survives
to check against. Treat any result whose radius exceeds Z=20 as unsupported.
"""

import numpy as np
import pandas as pd

from blastlib import constants

_TABLE_CACHE = {}


def _table(csv_path):
    key = str(csv_path)
    if key not in _TABLE_CACHE:
        _TABLE_CACHE[key] = pd.read_csv(csv_path)
    return _TABLE_CACHE[key]


def reference_curve(csv_path, weight, kind, Z_scaled):
    """Free-field value at scaled distance(s) Z, log-log interpolated.

    kind is 'P' (kPa) or 'I' (Pa.s). Outside the tabulated range the curve is
    continued as a power law — see the module docstring for why that is a
    weak spot rather than a detail.
    """
    ff = _table(csv_path)
    Zs = ff['Z'].values.astype(float)
    y = ff[f'{kind}_{int(weight)}'].values.astype(float)
    lz, ly = np.log(Zs), np.log(y)

    Z = np.asarray(Z_scaled, dtype=float)
    out = np.full(Z.shape, np.nan)
    good = np.isfinite(Z) & (Z > 0)
    if not np.any(good):
        return out

    lq = np.log(Z[good])
    res = np.interp(lq, lz, ly)
    s_hi = (ly[-1] - ly[-6]) / (lz[-1] - lz[-6])
    hi = lq > lz[-1]
    res[hi] = ly[-1] + s_hi * (lq[hi] - lz[-1])
    s_lo = (ly[5] - ly[0]) / (lz[5] - lz[0])
    lo = lq < lz[0]
    res[lo] = ly[0] + s_lo * (lq[lo] - lz[0])
    out[good] = np.exp(res)
    return out


def rebuild_impulse_ratio(processed, weight, ff_csv, thr_I_scaled=None):
    """Recompute ratioI1/2/3 in *processed* under the scaled impulse criterion.

    Needed only because the shipped NPZs were written under the old
    pressure-gated rule and the raw VTKs (which held the true reference field)
    are unavailable, so the ratio cannot be rebuilt at preprocessing time. The
    reference is reconstructed from the 1-D free-field table instead — see the
    module docstring for the accuracy this costs.

    Mutates and returns *processed*.
    """
    W13 = float(weight) ** (1 / 3)
    for g in ('1', '2', '3'):
        I = processed[f'impulse{g}_orig']
        Zsc = np.sqrt(processed[f'X{g}'] ** 2 + processed[f'Z{g}'] ** 2) / W13
        ref = reference_curve(ff_csv, weight, 'I', Zsc)
        with np.errstate(invalid='ignore', divide='ignore'):
            ratio = I / ref
            if thr_I_scaled is not None:      # explicit: historical rule
                conv = impulse_converged_scaled(I, ref, W13, thr_I_scaled)
            else:
                # Production criterion (D35) on the stored filled impulse; the
                # production measurement is grids.process_grids on the v3
                # store. Until 2026-09-30 this branch applied the D24 rule
                # with lowP from peakP*_orig (impulse_converged_pfloor).
                conv = impulse_converged(I, ref, W13)
        # Preserve the existing NaN mask: those cells carry no data at all.
        ratio = np.where(conv & ~np.isnan(ratio), 1.0, ratio)
        processed[f'ratioI{g}'] = np.where(
            np.isnan(processed[f'ratioI{g}']), np.nan, ratio)
    return processed


def impulse_converged(I_urban, I_ref, W13, rel_band=None, floor_scaled=None):
    """Cells where the urban impulse counts as converged to free-field.

    Production criterion since 2026-09-30 (DECISIONS.md D35 (c)):

        |I_urban / I_ref - 1| <= rel_band   or   I_urban / W^(1/3) < floor_scaled

    I_urban, I_ref : filled urban and reference impulse [Pa.s] (D34).
    W13            : cube root of the charge weight [kg^(1/3)].
    rel_band       : relative band (-); default IMPULSE_CRITERION['rel_band'].
    floor_scaled   : scaled floor [Pa.s/kg^(1/3)]; default
                     IMPULSE_CRITERION['floor_scaled'] (23.6, the reference
                     scaled impulse where the reference overpressure is 10 kPa).
    Returns a bool array. Cells with a non-positive reference converge only
    through the floor.
    """
    if rel_band is None:
        rel_band = constants.IMPULSE_CRITERION['rel_band']
    if floor_scaled is None:
        floor_scaled = constants.IMPULSE_CRITERION['floor_scaled']
    with np.errstate(invalid='ignore', divide='ignore'):
        accurate = (I_ref > 0) & (np.abs(I_urban / I_ref - 1.0) <= rel_band)
        floor = I_urban / W13 < floor_scaled
    return accurate | floor


def impulse_converged_pfloor(I_urban, I_ref, low_pressure, rel_band=0.10):
    """The D24 rule (production 2026-09-28 evening .. 2026-09-30), kept to
    reproduce its committed tables. Superseded by D35 (impulse_converged).

    D24 criterion (owner decision, 2026-09-28 evening, on the physics
    audit's verdict — docs/audit/2026-09-28/physics.md; full rationale in
    constants.IMPULSE_CRITERION):

        |I_urban - I_ref| / I_ref < rel_band     (free field is ACCURATE)
        or  low_pressure                         (urban peak P < 10 kPa —
                                                  damage-IRRELEVANT location)

    *low_pressure* is the boolean urban-pressure relevance floor — the SAME
    `peakP_raw < minPressure_kPa` mask the pressure criterion uses (audit
    D7), passed in by the caller so this function stays agnostic to where
    the pressure field comes from. The floor is a pressure statement on
    purpose: every P-I damage curve has a pressure asymptote, so below the
    anchored 10 kPa (IATG 02.20 Table 8) no impulse magnitude can matter —
    an impulse-only irrelevance level does not exist (audit physics-1, and
    D8 before it). The accuracy clause is relative, hence scale-free; cells
    with a non-positive reference converge only through the floor.

    [Corrected 2026-09-29, D24 review] "an impulse-only irrelevance level
    does not exist" is wrong: every P-I curve also has an impulse asymptote,
    but it is absolute and target-specific, and none is registered for the
    anchored structural class. The rationale that holds is IATG 02.20 §8:
    the tiers are stated as pressures although "the primary threat to
    structures is blast impulse energy", because they were developed for
    very large NEQ (thousands of kg) and scaled down. At a fixed scaled
    distance the impulse accompanying 10 kPa grows as W^(1/3) (~0.17-0.53 of
    a 10 t event's for W = 50-1500 kg), so the floor is conservative over
    this study's charge range.
    """
    if rel_band is None:
        rel_band = constants.IMPULSE_CRITERION['rel_band']
    with np.errstate(invalid='ignore', divide='ignore'):
        accurate = (I_ref > 0) & (np.abs(I_urban - I_ref) / I_ref < rel_band)
    return accurate | low_pressure


def impulse_converged_ifloor(I_urban, I_ref, W13, rel_band=0.10,
                             floor_scaled=20.0):
    """The 2026-09-28-morning rule (production for one run), kept to
    reproduce its committed tables: |dI|/I_ref < rel_band OR urban
    I/W^(1/3) < floor_scaled. Superseded the same day: an impulse level is
    not a relevance measure (physics-1), and the floor rode channelling
    amplification to Z ~ 32."""
    with np.errstate(invalid='ignore', divide='ignore'):
        accurate = (I_ref > 0) & (np.abs(I_urban - I_ref) / I_ref < rel_band)
    return accurate | (I_urban / W13 < floor_scaled)


def impulse_converged_scaled(I_urban, I_ref, W13, thr_I_scaled=20.0):
    """The 2026-07..2026-09 scaled-band criterion, kept to reproduce
    historical tables:  |I_urban - I_ref| / W^(1/3) < thr_I_scaled."""
    return np.abs(I_urban - I_ref) / W13 < thr_I_scaled
