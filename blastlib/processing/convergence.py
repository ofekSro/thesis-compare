"""Find convergence radius using angular binning (theta slices).

Splits the first quadrant into 91 angular samples (0, 1, 2, ..., 90 deg),
finds the convergence radius per sample using far-to-near scanning, then
collapses the per-theta radii into a single scalar radius.

The collapse is configurable — equivalent area (the default), max, or a
percentile — and comes from the SAME setting that drives the MaxR radius in
free_field.py, so the two are always measured the same way. See
processing/radius_estimator.py and constants.RADIUS_ESTIMATOR.
"""

import numpy as np

from blastlib.processing.radius_estimator import (
    N_THETA, DEFAULT_DTHETA_DEG, in_theta_bin, reduce_theta_radii,
    resolve_estimator, theta_bin_edges,
)

TOLERANCE = 0.05
K_CONSECUTIVE = 3  # consecutive violations required to declare non-convergence


def _find_radius_for_slice(ratio_vec, peak_vec, dist_vec, exclude_r):
    """Find convergence radius within a single angular slice.

    Sorts far-to-near and requires K_CONSECUTIVE cells in a row where
    |ratio - 1| > TOLERANCE before declaring non-convergence. Returns the
    distance of the last converged point before the violation streak.
    Only considers cells with valid (non-NaN) ratio values.
    """
    valid = ~np.isnan(ratio_vec) & (dist_vec > exclude_r)
    r_slice = ratio_vec[valid]
    p_slice = peak_vec[valid]
    d_slice = dist_vec[valid]

    if len(d_slice) == 0:
        return np.nan, np.nan

    # Sort from far to near
    order = np.argsort(d_slice)[::-1]
    d_sorted = d_slice[order]
    r_sorted = r_slice[order]
    p_sorted = p_slice[order]

    streak = 0
    streak_start = None

    for i in range(len(r_sorted)):
        if abs(r_sorted[i] - 1.0) > TOLERANCE:
            streak += 1
            if streak == 1:
                streak_start = i
            if streak >= K_CONSECUTIVE:
                if streak_start == 0:
                    return d_sorted[0], p_sorted[0]
                return d_sorted[streak_start - 1], p_sorted[streak_start - 1]
        else:
            streak = 0
            streak_start = None

    return d_sorted[-1], p_sorted[-1]


def _find_radius_for_slice_soft(w_vec, peak_vec, dist_vec, exclude_r):
    """Soft counterpart of _find_radius_for_slice: expected outermost
    exceedance under per-cell violation probabilities *w_vec*.

    The hard scan is replayed as a Markov chain scanning far -> near:
    state = current violation-streak length (0/1/2), absorbing when a
    streak reaches K_CONSECUTIVE=3, where the absorbed outcome's radius is
    the cell just outside the streak (d[i-3], or d[0] when the streak
    starts at the outermost cell) — exactly the hard scan's bookkeeping.
    The returned radius is the expectation over outcomes; mass never
    absorbed contributes the innermost valid cell, matching the hard
    no-violation fallback. With w in {0, 1} the chain is deterministic and
    reproduces _find_radius_for_slice bit-exactly (the beta -> inf limit).

    A lone high-w cell flanked by w ~ 0 contributes ~0 mass (absorption
    needs three consecutive violations), which is what K_CONSECUTIVE was
    for — no separate ring/percentile aggregation needed.
    """
    valid = ~np.isnan(w_vec) & (dist_vec > exclude_r)
    w_slice = w_vec[valid]
    p_slice = peak_vec[valid]
    d_slice = dist_vec[valid]

    if len(d_slice) == 0:
        return np.nan, np.nan

    order = np.argsort(d_slice)[::-1]
    d_sorted = d_slice[order]
    w_sorted = w_slice[order]
    p_sorted = p_slice[order]

    d = d_sorted.tolist()
    w = w_sorted.tolist()

    m0, m1, m2 = 1.0, 0.0, 0.0
    r_exp = 0.0
    for i in range(len(d)):
        wi = w[i]
        absorbed = m2 * wi
        if absorbed > 0.0:
            r_exp += absorbed * d[i - 3 if i >= 3 else 0]
        total = m0 + m1 + m2
        m2 = m1 * wi
        m1 = m0 * wi
        m0 = total * (1.0 - wi)
        if m0 + m1 + m2 == 0.0:
            break
    leftover = m0 + m1 + m2
    if leftover > 0.0:
        r_exp += leftover * d[-1]

    idx = int(np.argmin(np.abs(d_sorted - r_exp)))
    return r_exp, p_sorted[idx]


def equivalent_area_radius(radii, delta_theta):
    """Compute equivalent area radius from per-theta radii.

    A   = sum(0.5 * r_i^2 * delta_theta)  for non-NaN entries
    Req = sqrt(4 * A / pi)

    Kept as public API (tools/radius_methods imports it); the maths now lives
    in radius_estimator.reduce_theta_radii.
    """
    return reduce_theta_radii(radii, method='req',
                              dtheta_deg=np.degrees(delta_theta))


def find_convergence_radius(ratio_P, ratio_I, peak_P, peak_I, X, Z, exclude_r,
                            estimator=None, soft_w_P=None):
    """Find convergence radius using angular binning + a scalar collapse.

    Samples the first quadrant at 91 angles (0-90 deg, 1 deg spacing) and
    finds the convergence radius per angle, then collapses those per-theta
    radii with the configured estimator.

    estimator : dict, str or None
        None uses constants.RADIUS_ESTIMATOR — the same setting free_field.py
        uses for MaxR, so both radii are always the same kind of average.
    soft_w_P : array or None
        Per-cell soft exceedance weights aligned with ratio_P (from
        soft_criterion.soft_pressure_weights). When given, the PRESSURE
        sectors use the soft expected-radius scan instead of the hard K=3
        scan; the impulse path is never affected. None -> legacy behavior,
        bit-exact.

    Returns dict with keys:
        pressure, impulse, pressureAtRadius, impulseAtRadius,
        theta_centers, radius_per_theta_P, radius_per_theta_I
    """
    est = resolve_estimator(estimator)
    dist = np.sqrt(X ** 2 + Z ** 2)
    theta = np.arctan2(Z, X)  # [0, pi/2] for first quadrant

    # 91 sample angles: 0, 1, 2, ..., 90 degrees
    thetas_deg = np.arange(0, N_THETA, dtype=float)
    thetas_rad = np.radians(thetas_deg)

    # Bin edges: each theta ± 0.5 deg, clipped to [0, pi/2]
    bin_edges = theta_bin_edges()  # 92 edges

    r_P = np.full(N_THETA, np.nan)
    r_I = np.full(N_THETA, np.nan)
    val_P = np.full(N_THETA, np.nan)
    val_I = np.full(N_THETA, np.nan)

    for i in range(N_THETA):
        in_bin = in_theta_bin(theta, bin_edges, i)

        if not np.any(in_bin):
            continue

        if soft_w_P is None:
            r_P[i], val_P[i] = _find_radius_for_slice(
                ratio_P[in_bin], peak_P[in_bin], dist[in_bin], exclude_r)
        else:
            r_P[i], val_P[i] = _find_radius_for_slice_soft(
                soft_w_P[in_bin], peak_P[in_bin], dist[in_bin], exclude_r)
        r_I[i], val_I[i] = _find_radius_for_slice(
            ratio_I[in_bin], peak_I[in_bin], dist[in_bin], exclude_r)

    # Collapse per-theta radii into a single radius
    radius_P = reduce_theta_radii(r_P, est['method'], est['percentile'],
                                  DEFAULT_DTHETA_DEG)
    radius_I = reduce_theta_radii(r_I, est['method'], est['percentile'],
                                  DEFAULT_DTHETA_DEG)

    # Peak values at the collapsed radius (find closest theta-bin)
    def _value_at_radius(radii, values, target_r):
        valid = ~np.isnan(radii)
        if not np.any(valid) or np.isnan(target_r):
            return np.nan
        idx = np.argmin(np.abs(radii[valid] - target_r))
        return float(values[valid][idx])

    p_at_r = _value_at_radius(r_P, val_P, radius_P)
    i_at_r = _value_at_radius(r_I, val_I, radius_I)

    return {
        'pressure':            radius_P,
        'impulse':             radius_I,
        'pressureAtRadius':    p_at_r,
        'impulseAtRadius':     i_at_r,
        'theta_centers':       thetas_rad,
        'radius_per_theta_P':  r_P,
        'radius_per_theta_I':  r_I,
    }
