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
            conv = impulse_converged(I, ref, W13, thr_I_scaled)
        # Preserve the existing NaN mask: those cells carry no data at all.
        ratio = np.where(conv & ~np.isnan(ratio), 1.0, ratio)
        processed[f'ratioI{g}'] = np.where(
            np.isnan(processed[f'ratioI{g}']), np.nan, ratio)
    return processed


def impulse_converged(I_urban, I_ref, W13, thr_I_scaled=None):
    """Cells where the urban impulse counts as converged to free-field.

        |I_urban - I_ref| / W^(1/3) < thr_I_scaled

    Dividing by W^(1/3) is what makes this admissible under Hopkinson-Cranz;
    see constants.IMPULSE_CRITERION. Deliberately contains no pressure term:
    gating the impulse ratio on a pressure threshold is what pinned RadiusI to
    the 10 kPa contour.
    """
    if thr_I_scaled is None:
        thr_I_scaled = constants.IMPULSE_CRITERION['thr_I_scaled']
    return np.abs(I_urban - I_ref) / W13 < thr_I_scaled
