"""Null city and the per-direction normalisation of MaxR ('reqdir' token).

Why. MaxR takes, per direction, the outermost open cell whose load reaches the
free-field level L. In a direction where R_free falls inside a building, that
cell is the building's front face: the cells behind it are open but weaker than
L. So MaxR is short there even when the city does nothing to the wave. Fed the
free field with the buildings cut out ("null city"), the production scan gives
Λ_P ≈ 0.92 inside the fit domain (0.78 for 30 m blocks on 5 m streets) instead
of 1 (docs/PLAN_LAMBDA_ZURBAN_HE.md A4, decision H2).

The cure compares, per direction, the real city with the null city — the same
holes, the same scan, only the field differs — so the geometric penalty cancels
and what remains is what the city does to the wave:

  null NaN                       -> sector dropped from both sums (no open cell
                                    reaches L even in the free field: the
                                    direction cannot be measured)
  A  r_null >= R_free - tol      -> d = r_null  (R_free lies on open ground)
  B  r_null <  R_free - tol, r_real <= r_null + tol
                                 -> d = r_null  (both stopped by the same front;
                                    shielding in front of it is kept, beyond it
                                    is unknown and counts as no effect)
  C  r_null <  R_free - tol, r_real >  r_null + tol
                                 -> d = R_free  (the real load passed the
                                    building: compare with the free field, not
                                    the front — a whole-row normalisation
                                    over-corrects exactly here, PLAN N1/N2)
  real NaN, null valid           -> r_real = 0  (as in req: zero area)

  Λ_dir = sqrt( sum w r_real^2 / sum w d^2 ),  MaxR_dir = Λ_dir · R_free

tol = TOL_CELLS cells of the local mesh. Case B is an assumption, not a
measurement: in ~29% of pressure sectors the remaining bias is towards a low Λ,
of unknown size (PLAN H2).
"""

import numpy as np

from blastlib import constants
from blastlib.io import raw_store
from blastlib.processing.grids import process_grids, BUILDING_SENTINEL_KPA
from blastlib.processing.radius_estimator import theta_centers_deg

# Two cells: the case boundary sits metres from any building front, so the
# result does not depend on it — 1, 2 and 4 cells gave the same median Λ_P
# (1.126) and Λ_I (1.307) on the in-domain rows (PLAN N2).
TOL_CELLS = 2


def null_city_grids(raw):
    """Grids for process_grids(): the reference field as the urban field, with
    the real buildings kept as buildings (raw sentinel cells).

    raw : v3 raw-store payload (raw_store.load_raw_data). Returns the dict
    process_grids() consumes, float32 fields as the solver wrote them.
    """
    data = raw_store.grids_from_raw(raw)
    for g in raw_store.LEVELS:
        building = raw[f'peakP{g}'].astype(np.float32) == BUILDING_SENTINEL_KPA
        refP = raw[f'refP{g}'].astype(np.float32)
        data[f'peakP{g}'] = np.where(building, BUILDING_SENTINEL_KPA, refP).astype(np.float32)
        data[f'impulse{g}'] = raw[f'refI{g}'].astype(np.float32)
    return data


def null_city_processed(raw, params=None):
    """process_grids() output of the null city, with the production criteria.

    params : criteria dict (default constants.PARAMS). The charge weight is
    read from the payload, as raw_store.expand does.
    """
    params = dict(constants.PARAMS) if params is None else params
    return process_grids(null_city_grids(raw), params, weight=float(raw['weight']))


def mesh_boxes(processed):
    """[(box limit [m], cell size [m]), ...] of the nested grids, finest first.

    A cell at (x, z) belongs to the first box with max(x, z) <= limit — the cut
    process_grids applies (a coarser grid never re-enters a finer box).
    """
    boxes = []
    for g in ('1', '2', '3'):
        X = np.asarray(processed[f'X{g}'], float)
        xs = np.unique(X.ravel())
        h = float(np.min(np.diff(xs))) if xs.size > 1 else np.nan
        limit = float(xs.max() + h / 2) if g != '3' else np.inf
        boxes.append((limit, h))
    return boxes


def sector_cell_size(r, n_theta, boxes):
    """Local cell size [m] at radius r [m] on each sector's centre line."""
    th = np.radians(theta_centers_deg(n_theta))
    m = np.asarray(r, float) * np.maximum(np.abs(np.cos(th)), np.abs(np.sin(th)))
    h = np.full(m.shape, boxes[-1][1])
    for limit, hh in reversed(boxes[:-1]):
        h = np.where(m <= limit, hh, h)
    return h


def per_direction_lambda(r_real, r_null, R_free, h, tol_cells=TOL_CELLS):
    """Per-direction normalised Λ for one row (module docstring for the rule).

    r_real, r_null : per-sector reach [m] of the real and null city (NaN = no
        open cell reaches L). R_free : free-field radius of the level [m].
    h : per-sector local cell size [m]. Sectors are of equal width.
    Returns (Λ_dir [-], counts {'A','B','C','dropped'}); Λ_dir is NaN when no
    sector can be measured.
    """
    r_real = np.asarray(r_real, float)
    r_null = np.asarray(r_null, float)
    keep = ~np.isnan(r_null)
    rR = np.where(np.isnan(r_real), 0.0, r_real)
    tol = tol_cells * np.asarray(h, float)
    capped = keep & (r_null < R_free - tol)
    passed = rR > r_null + tol
    d = np.where(capped & passed, R_free, r_null)
    counts = {'A': int((keep & ~capped).sum()), 'B': int((capped & ~passed).sum()),
              'C': int((capped & passed).sum()), 'dropped': int((~keep).sum())}
    den = float(np.sum(d[keep] ** 2))
    if den <= 0:
        return np.nan, counts
    return float(np.sqrt(np.sum(rR[keep] ** 2) / den)), counts
