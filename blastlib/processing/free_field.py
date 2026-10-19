"""Free-field lookup and exceedance-radius helpers.

Provides functions to load the free-field reference data (pressure and impulse
at scaled distances Z=1-20 for each charge weight) and to find the radius of
the exceedance region — the outermost cells where the urban field still
reaches at least the free-field value — using angular binning over 0-90
degrees (91 legacy sectors, or 90 equal ones for the 'reqdir' token).

The per-bin radii are collapsed to one scalar by the SAME configurable
estimator the convergence radius uses (see processing/radius_estimator.py and
constants.RADIUS_ESTIMATOR), so MaxR and R_conv are always comparable.
"""

import numpy as np
import pandas as pd

from blastlib import constants
from blastlib.processing.radius_estimator import (
    N_THETA, in_theta_bin, reduce_theta_radii, resolve_estimator,
    theta_bin_edges,
)

# free_field_data.csv must contain a Z column plus P_{w}/I_{w} for each weight
FF_WEIGHTS = (50, 250, 500, 1000, 1500)


def load_ff_lookup(csv_path):
    """Load free_field_data.csv into a nested lookup dictionary.

    Parameters
    ----------
    csv_path : str or Path
        Path to the free_field_data.csv file.

    Returns
    -------
    dict
        Nested dict: ``lookup[weight][Z] = (P_ff, I_ff)`` where weight is
        one of FF_WEIGHTS and Z is an integer scaled distance (1-20).
    """
    df = pd.read_csv(csv_path)
    lookup = {}
    for w in FF_WEIGHTS:
        lookup[w] = {}
        for _, row in df.iterrows():
            z_val = int(row['Z'])
            lookup[w][z_val] = (float(row[f'P_{w}']), float(row[f'I_{w}']))
    return lookup


def _percentile_radius(radii, p=95):
    """Compute the p-th percentile of non-NaN per-theta radii.

    Returns NaN if no valid radii exist. Kept as a thin wrapper; the maths
    lives in radius_estimator.reduce_theta_radii.
    """
    return reduce_theta_radii(radii, method='percentile', percentile=p)


def theta_index(all_X, all_Zc, n_theta=N_THETA):
    """Angular-bin index (0..n_theta-1) of every cell; -1 outside the first quadrant.

    Computed once per configuration and reused for all 20 free-field levels —
    the binning does not depend on Z. n_theta: 91 (legacy) or 90 ('reqdir').
    """
    theta = np.arctan2(np.asarray(all_Zc, float), np.asarray(all_X, float))
    edges = theta_bin_edges(n_theta)
    idx = np.digitize(theta, edges) - 1
    # theta == pi/2 lands one past the last bin; the last bin is closed.
    idx = np.where(theta == edges[-1], n_theta - 1, idx)
    return np.where((idx >= 0) & (idx < n_theta), idx, -1)


def reference_level_per_theta(ref_vals, dist, th_idx, r_target, tol=0.6,
                              max_tol=4.0, n_theta=N_THETA, min_cells=None):
    """Free-field level at radius *r_target*, per angular sector.

    The reference field is a simulation on the same Cartesian mesh as the
    urban run, and on that mesh it is anisotropic — measured at 9.6% between
    directions, high on the diagonal and low on the axes. R_conv never sees
    that because it divides cell-by-cell by the reference at the same point;
    MaxR did, because it compared against one scalar. Sampling the reference
    per direction restores the same cancellation for MaxR.

    Median of *ref_vals* in the ring |dist - r_target| < tol, per sector. A
    sector is accepted only with at least *min_cells* cells (default
    constants.MIN_RING_CELLS = 3), so one defective cell cannot set the level
    of a direction; the ring widens (up to *max_tol*) while sectors fall
    short, so a thin ring at small radius or across a grid seam still yields a
    level. Sectors still short are returned NaN for the caller to fall back on.

    Returns (n_theta,) array; n_theta must match the layout of *th_idx*.
    """
    if min_cells is None:
        min_cells = constants.MIN_RING_CELLS
    out = np.full(n_theta, np.nan)
    finite = np.isfinite(ref_vals) & (ref_vals > 0) & (th_idx >= 0)
    if not np.any(finite):
        return out

    while tol <= max_tol:
        ring = finite & (np.abs(dist - r_target) < tol)
        if np.any(ring):
            for i in np.unique(th_idx[ring]):
                if np.isnan(out[i]):
                    vals = ref_vals[ring & (th_idx == i)]
                    if vals.size >= min_cells:
                        out[i] = float(np.median(vals))
        if not np.any(np.isnan(out)):
            break
        tol *= 2.0
    return out


def find_percentile_radius(all_vals, all_X, all_Zc, ff_val, estimator=None,
                           exclude_r=0.0, th_idx=None, dist=None):
    """Find the exceedance-region radius for one free-field level.

    Identifies cells whose values are at least the free-field reference value
    (the exceedance region — "how far does the urban field still deliver at
    least this load"), bins them into the estimator's angular sectors (91
    legacy or 90 equal, over 0-90 degrees), finds the maximum distance in each
    bin (the outer exceedance boundary per direction), then collapses those
    per-bin maxima with the configured estimator. The result is the RAW reach;
    the 'reqdir' per-direction normalisation is applied by the caller
    (processing/null_city.py).

    Parameter-free by construction: replaces the earlier tolerance-band
    matching (|val - ff_val| <= tol*ff_val), which inflated MaxR near the
    convergence radius (where urban/free-field is within the band width)
    and left angular bins empty in the steep near field.

    Parameters
    ----------
    all_vals : np.ndarray
        Flattened array of field values (pressure or impulse).
    all_X, all_Zc : np.ndarray
        Flattened coordinates corresponding to all_vals.
    ff_val : float or (n_theta,) array
        Free-field exceedance threshold. A scalar applies one level in every
        direction (the historical behaviour, and the fallback when no
        reference field is available). An array applies ff_val[i] in sector i
        — see reference_level_per_theta. NaN entries fall back to the median
        of the finite ones.
    estimator : dict, str or None
        Collapse method. None uses constants.RADIUS_ESTIMATOR — the same
        setting convergence.py uses, so MaxR and R_conv always match in kind.
    exclude_r : float
        Near-blast exclusion radius; cells at or inside it are dropped.
        **Production passes 0 and excludes the near field per ROW instead**
        (z_urban.z_urban_valid_mask, condition `R_free > exclude_r`). The
        parameter is kept because it is the obvious thing to reach for and
        the reason not to is not obvious:

        Excluding cells here does not remove a *direction* from the estimate,
        it gives that direction a radius of zero. A sector whose exceedance
        lies only inside the first street then contributes zero area to the
        Req sum rather than dropping out of it — 6.7% of sectors, measured,
        and not only in rows the near-field condition would have removed
        anyway. The resulting Req is systematically short at small Z_free,
        which flattens the low-range end of Lambda(Z_free); the pressure
        range_switch fit stops being identified there (its open-canyon
        denominator B runs to whatever bound is offered: 4.0 -> 8.0 at a
        bound of 8, -> 17.5 at a bound of 1000). Applying the same exclusion
        per row leaves B identified at 7.1 on the same 280 rows.

        In short: this is a domain restriction, not a measurement change, and
        it belongs where the domain is defined.
    th_idx, dist : np.ndarray or None
        Precomputed theta_index(...) and cell distances. Supplied by callers
        that loop over many levels for one configuration; computed here when
        omitted. th_idx must use the estimator's sector layout.

    Returns
    -------
    tuple(float, np.ndarray)
        - The collapsed radius (scalar, may be NaN).
        - Array of shape (n_theta,) with the max radius per angular bin.
    """
    est = resolve_estimator(estimator)
    n_theta = est['n_theta']

    if dist is None:
        dist = np.sqrt(np.asarray(all_X, float) ** 2
                       + np.asarray(all_Zc, float) ** 2)
    if th_idx is None:
        th_idx = theta_index(all_X, all_Zc, n_theta)

    level = np.asarray(ff_val, dtype=float)
    if level.ndim == 0:
        threshold = np.full(len(all_vals), float(level))
    else:
        if level.shape != (n_theta,):
            raise ValueError(f'ff_val must be a scalar or a ({n_theta},) '
                             f'array, got shape {level.shape}')
        if np.all(np.isnan(level)):
            return np.nan, np.full(n_theta, np.nan)
        level = np.where(np.isnan(level), np.nanmedian(level), level)
        threshold = np.where(th_idx >= 0, level[th_idx], np.inf)

    with np.errstate(invalid='ignore'):
        match = (~np.isnan(all_vals) & (all_vals >= threshold)
                 & (dist > exclude_r) & (th_idx >= 0))
    if not np.any(match):
        return np.nan, np.full(n_theta, np.nan)

    r_per_theta = np.full(n_theta, np.nan)
    m_idx, m_dist = th_idx[match], dist[match]
    for i in np.unique(m_idx):
        r_per_theta[i] = float(np.max(m_dist[m_idx == i]))

    r_scalar = reduce_theta_radii(r_per_theta, est['method'], est['percentile'])
    return r_scalar, r_per_theta
