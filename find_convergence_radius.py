"""Find convergence radius using angular binning (theta slices).

Splits the first quadrant into 91 angular samples (0, 1, 2, ..., 90 deg),
finds the convergence radius per sample using far-to-near scanning, then
computes the Equivalent Area Radius as the representative radius.

The 91 per-theta radii are collapsed into one representative radius using the
METHOD switch ('max', 'p95', or 'eq_area' — see below).

Equivalent Area Radius (METHOD = 'eq_area'):
    A   = sum(0.5 * r_i^2 * delta_theta)   — polygon area
    Req = sqrt(4*A / pi)                    — quarter-circle with same area
"""

import numpy as np

N_THETA = 91       # 0, 1, 2, ..., 90 degrees
TOLERANCE = 0.05
K_CONSECUTIVE = 3  # consecutive violations required to declare non-convergence

# How to collapse the 91 per-theta radii into a single representative radius:
#   'max'     - maximum per-theta radius (most conservative)
#   'p95'     - 95th percentile of per-theta radii (robust max)
#   'eq_area' - equivalent area radius (quarter-circle of equal area)
METHOD = 'eq_area'


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


def _equivalent_area_radius(radii, delta_theta):
    """Compute equivalent area radius from per-theta radii.

    A   = sum(0.5 * r_i^2 * delta_theta)  for non-NaN entries
    Req = sqrt(4 * A / pi)
    """
    valid = ~np.isnan(radii)
    if not np.any(valid):
        return np.nan
    A = np.sum(0.5 * radii[valid] ** 2 * delta_theta)
    return float(np.sqrt(4 * A / np.pi))


def _summarize_radius(radii, delta_theta, method):
    """Collapse per-theta radii into one radius using the chosen method.

    method : 'max' | 'p95' | 'eq_area'  (see METHOD at top of module)
    """
    valid = ~np.isnan(radii)
    if not np.any(valid):
        return np.nan
    if method == 'max':
        return float(np.nanmax(radii))
    if method == 'p95':
        return float(np.nanpercentile(radii[valid], 95))
    if method == 'eq_area':
        return _equivalent_area_radius(radii, delta_theta)
    raise ValueError(f"Unknown convergence method: {method!r} "
                     "(expected 'max', 'p95', or 'eq_area')")


def find_convergence_radius(ratio_P, ratio_I, peak_P, peak_I, X, Z, exclude_r,
                            method=METHOD):
    """Find convergence radius using angular binning + equivalent area radius.

    Samples the first quadrant at 91 angles (0-90 deg, 1 deg spacing),
    finds convergence radius per angle, returns equivalent area radius.

    Returns dict with keys:
        pressure, impulse, pressureAtRadius, impulseAtRadius,
        theta_centers, radius_per_theta_P, radius_per_theta_I
    """
    dist = np.sqrt(X ** 2 + Z ** 2)
    theta = np.arctan2(Z, X)  # [0, pi/2] for first quadrant

    # 91 sample angles: 0, 1, 2, ..., 90 degrees
    thetas_deg = np.arange(0, N_THETA, dtype=float)
    thetas_rad = np.radians(thetas_deg)
    delta_theta = np.radians(1.0)  # 1 degree

    # Bin edges: each theta ± 0.5 deg, clipped to [0, pi/2]
    bin_edges = np.radians(np.arange(-0.5, 91.0, 1.0))  # 92 edges
    bin_edges[0] = 0.0
    bin_edges[-1] = np.pi / 2

    r_P = np.full(N_THETA, np.nan)
    r_I = np.full(N_THETA, np.nan)
    val_P = np.full(N_THETA, np.nan)
    val_I = np.full(N_THETA, np.nan)

    for i in range(N_THETA):
        if i == 0:
            in_bin = (theta >= bin_edges[0]) & (theta < bin_edges[1])
        elif i == N_THETA - 1:
            in_bin = (theta >= bin_edges[i]) & (theta <= bin_edges[i + 1])
        else:
            in_bin = (theta >= bin_edges[i]) & (theta < bin_edges[i + 1])

        if not np.any(in_bin):
            continue

        r_P[i], val_P[i] = _find_radius_for_slice(
            ratio_P[in_bin], peak_P[in_bin], dist[in_bin], exclude_r)
        r_I[i], val_I[i] = _find_radius_for_slice(
            ratio_I[in_bin], peak_I[in_bin], dist[in_bin], exclude_r)

    # Collapse per-theta radii into a single radius (method selectable)
    radius_P = _summarize_radius(r_P, delta_theta, method)
    radius_I = _summarize_radius(r_I, delta_theta, method)

    # Peak values at the equivalent area radius (find closest theta-bin)
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
