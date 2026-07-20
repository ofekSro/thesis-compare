"""Free-field lookup and percentile radius helpers.

Provides functions to load the free-field reference data (pressure and impulse
at scaled distances Z=1-20 for each charge weight) and to find the
95th-percentile radius of the exceedance region — the outermost cells where
the urban field still reaches at least the free-field value — using angular
binning (91 bins covering 0-90 degrees).
"""

import numpy as np
import pandas as pd


def _load_ff_lookup(csv_path):
    """Load free_field_data.csv into a nested lookup dictionary.

    Parameters
    ----------
    csv_path : str
        Path to the free_field_data.csv file.

    Returns
    -------
    dict
        Nested dict: ``lookup[weight][Z] = (P_ff, I_ff)`` where weight is
        one of {50, 250, 500, 1000, 1500} and Z is an integer scaled distance (1-20).
    """
    df = pd.read_csv(csv_path)
    lookup = {}
    for w in (50, 250, 500, 1000, 1500):
        lookup[w] = {}
        for _, row in df.iterrows():
            z_val = int(row['Z'])
            lookup[w][z_val] = (float(row[f'P_{w}']), float(row[f'I_{w}']))
    return lookup


def _percentile_radius(radii, p=95):
    """Compute the p-th percentile of non-NaN per-theta radii.

    Parameters
    ----------
    radii : np.ndarray
        Array of per-angle radii (may contain NaN).
    p : float
        Percentile to compute (default 95).

    Returns
    -------
    float
        The p-th percentile value, or NaN if no valid radii exist.
    """
    valid = radii[~np.isnan(radii)]
    if valid.size == 0:
        return np.nan
    return float(np.nanpercentile(valid, p))


def _find_percentile_radius(all_vals, all_X, all_Zc, ff_val, p=95):
    """Find the 95th-percentile radius of the exceedance region for a level.

    Identifies cells whose values are at least the free-field reference value
    (the exceedance region — "how far does the urban field still deliver at
    least this load"), bins them into 91 angular bins (0-90 degrees, 1-degree
    spacing), finds the maximum distance in each bin (the outer exceedance
    boundary per direction), then returns the p-th percentile of those
    per-bin maxima.

    Parameter-free by construction: replaces the earlier tolerance-band
    matching (|val - ff_val| <= tol*ff_val), which inflated MaxR near the
    convergence radius (where urban/free-field is within the band width)
    and left angular bins empty in the steep near field.

    Parameters
    ----------
    all_vals : np.ndarray
        Flattened array of field values (pressure or impulse).
    all_X : np.ndarray
        Flattened array of X coordinates corresponding to all_vals.
    all_Zc : np.ndarray
        Flattened array of Z coordinates corresponding to all_vals.
    ff_val : float
        Free-field reference value (exceedance threshold).
    p : float
        Percentile to compute (default 95).

    Returns
    -------
    tuple(float, np.ndarray)
        - The p-th percentile radius (scalar, may be NaN).
        - Array of shape (91,) with the max radius per angular bin.
    """
    match = ~np.isnan(all_vals) & (all_vals >= ff_val)
    if not np.any(match):
        return np.nan, np.full(91, np.nan)

    vals_X = all_X[match]
    vals_Z = all_Zc[match]
    dist_m = np.sqrt(vals_X ** 2 + vals_Z ** 2)
    theta_m = np.arctan2(vals_Z, vals_X)

    bin_edges = np.radians(np.arange(-0.5, 91.0, 1.0))
    bin_edges[0] = 0.0
    bin_edges[-1] = np.pi / 2

    r_per_theta = np.full(91, np.nan)
    for i in range(91):
        if i == 0:
            in_bin = (theta_m >= bin_edges[0]) & (theta_m < bin_edges[1])
        elif i == 90:
            in_bin = (theta_m >= bin_edges[i]) & (theta_m <= bin_edges[i + 1])
        else:
            in_bin = (theta_m >= bin_edges[i]) & (theta_m < bin_edges[i + 1])

        if np.any(in_bin):
            r_per_theta[i] = float(np.max(dist_m[in_bin]))

    r_pct = _percentile_radius(r_per_theta, p)
    return r_pct, r_per_theta
