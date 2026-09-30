"""The strip measurement: E(r) slices down the FIRST street.

This is the single measurement everything else in blastlib.street is built
on: cells with 0 <= Z <= s/2 — the half-width of the street the charge sits
in — binned by X, the distance along the street axis, 0.5 m per slice, and
reduced by the MEAN. E(r) is then mean(P_urban)/mean(P_ff) per slice, the
free field taken from the charge-only reference simulation ON THE SAME
CELLS.

WHY A STRIP AND NOT RINGS
-------------------------
A ring profile changes what it is sampling as it grows: a ring at 37 m may
cross mostly buildings, leaving only the few street cells valid, and its
median then jumps because the sample composition changed, not because the
field did. Measured on config_01 and config_03 — same geometry, charge
weights 30x apart — the per-ring valid-cell count is IDENTICAL in all 85
bins (it is set by the building layout alone) and dips to a local minimum
of 404 cells exactly where the early ring-based "detections" landed. The
strip has no such freedom: every slice holds the same 51 cells (s = 5 m at
0.5 m slices; 51-68 across the geometries), all of them in the open street,
so a change in the profile is a change in the flow. The cross-street strip
would mirror this one only for det=2; for det=1 it runs into the building
row and is 70% empty, which is why only the along-street strip exists. For
det=2 the along-street strip represents both streets of the intersection —
verified digit-for-digit by symmetry.

WHY THE REFERENCE FIELD IS refP ON THE SAME CELLS
-------------------------------------------------
Never data/free_field_data.csv. That table is axis-sampled and 1-D, while
the reference SIMULATION on the Cartesian mesh is anisotropic by 9.6%
between directions (high on the diagonal, low on the axes) and suffers
grid-seam corruption past Z = 100/W^(1/3). Dividing cell-by-cell by refP{g}
cancels the anisotropy for free; any scalar or table reference does not.
refP{g} holds the FILLED reference since D34 (coarse→fine max-fill). RMAX = 100 m is kept as the fine-box limit.

WHY NO BUILDING-FOOTPRINT MASK
------------------------------
None is needed and none must ever come from data validity. The strip
0 <= Z <= s/2 is open street BY CONSTRUCTION (buildings start at
Z = s/2 + j*(b+s)); and the stored 2-D fields hold FINITE values inside
building footprints (the solver's over-roof envelope), so a validity-based
mask would be a silent no-op — two earlier detectors were invalidated by
exactly that assumption. Any spatial mask in this project must come from
geometry.

Relative to the retired pressure_profile.street_profile (:381-437) this
drops: the derivative columns (computed at O(n^2) per profile and discarded
by every downstream caller — a free ~4x speedup, numerically inert), the
impulse target and '--field raw' variants (never used on the street path),
and the dead per-grid radius windows. The slice numerics are identical,
operation for operation.
"""

import numpy as np
import pandas as pd

from blastlib.street.constants import MIN_CELLS_PER_BIN, RMAX

# The three stored resolutions, finest first. Each slice takes its cells
# from the finest grid that still has MIN_CELLS_PER_BIN of them there, so a
# slice never mixes resolutions. Inside RMAX = 100 m (grid 1's extent at
# 0.15 m cells) grid 1 always qualifies.
_GRIDS = (1, 2, 3)

_REDUCERS = {'median': np.median, 'max': np.max, 'mean': np.mean}


def street_profile(processed, cfg, dr=0.5, rmax=RMAX, stat='mean'):
    """Slice the first-street strip of one processed config into E(r).

    processed is the dict from blastlib.io.npz_store.load_processed_data;
    cfg the dict from blastlib.config.parser.config_parser. Returns a
    DataFrame with one row per slice — r (centre), n (cells), urban,
    urban_p10, urban_p90, free_field, ratio — where urban/free_field are
    the *stat* reduction (production: mean) of peakP{g}_orig / refP{g}
    over the SAME masked cells, and ratio = urban/free_field is E(r).

    Slices with fewer than MIN_CELLS_PER_BIN cells on every grid are
    absent, not NaN. The exclusion-radius cut is deliberately NOT applied
    here — callers drop those slices from the raw frame before smoothing
    (conventions.cut_exclusion, quirk Q1), because the cut belongs to the
    anchor/validation conventions, not to the measurement.
    """
    s_half = cfg['swidth'] / 2.0
    reduce_ = _REDUCERS[stat]

    layers = []
    for g in _GRIDS:
        X = np.asarray(processed[f'X{g}']).ravel()
        Z = np.asarray(processed[f'Z{g}']).ravel()
        u = np.asarray(processed[f'peakP{g}_orig']).ravel()
        ref = np.asarray(processed[f'refP{g}']).ravel()
        ok = (np.isfinite(u) & (u > 0) & np.isfinite(ref) & (ref > 0)
              & (Z >= 0) & (Z <= s_half) & (X > 0))
        layers.append((X[ok], u[ok], ref[ok]))

    if rmax is None:
        rmax = max((x.max() for x, _, _ in layers if len(x)), default=0.0)
    edges = np.arange(0.0, rmax + dr, dr)
    rows = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        for x, u, ref in layers:          # finest grid with enough cells wins
            m = (x >= lo) & (x < hi)
            if m.sum() >= MIN_CELLS_PER_BIN:
                rows.append({'r': 0.5 * (lo + hi), 'n': int(m.sum()),
                             'urban': reduce_(u[m]),
                             'urban_p10': np.percentile(u[m], 10),
                             'urban_p90': np.percentile(u[m], 90),
                             'free_field': reduce_(ref[m])})
                break
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out['ratio'] = out.urban / out.free_field
    return out
