"""Free-field lookup and exceedance-radius helpers.

Provides functions to load the free-field reference data (pressure and impulse
at scaled distances Z=1-20 for each charge weight) and to find the radius of
the exceedance region — the outermost cells where the urban field still
reaches at least the free-field value — using angular binning (91 bins
covering 0-90 degrees).

The per-bin radii are collapsed to one scalar by the SAME configurable
estimator the convergence radius uses (see processing/radius_estimator.py and
constants.RADIUS_ESTIMATOR), so MaxR and R_conv are always comparable.
"""

import numpy as np
import pandas as pd

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


def find_percentile_radius(all_vals, all_X, all_Zc, ff_val, estimator=None):
    """Find the exceedance-region radius for one free-field level.

    Identifies cells whose values are at least the free-field reference value
    (the exceedance region — "how far does the urban field still deliver at
    least this load"), bins them into 91 angular bins (0-90 degrees, 1-degree
    spacing), finds the maximum distance in each bin (the outer exceedance
    boundary per direction), then collapses those per-bin maxima with the
    configured estimator.

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
    estimator : dict, str or None
        Collapse method. None uses constants.RADIUS_ESTIMATOR — the same
        setting convergence.py uses, so MaxR and R_conv always match in kind.

    Returns
    -------
    tuple(float, np.ndarray)
        - The collapsed radius (scalar, may be NaN).
        - Array of shape (91,) with the max radius per angular bin.
    """
    est = resolve_estimator(estimator)

    match = ~np.isnan(all_vals) & (all_vals >= ff_val)
    if not np.any(match):
        return np.nan, np.full(N_THETA, np.nan)

    vals_X = all_X[match]
    vals_Z = all_Zc[match]
    dist_m = np.sqrt(vals_X ** 2 + vals_Z ** 2)
    theta_m = np.arctan2(vals_Z, vals_X)

    bin_edges = theta_bin_edges()

    r_per_theta = np.full(N_THETA, np.nan)
    for i in range(N_THETA):
        in_bin = in_theta_bin(theta_m, bin_edges, i)
        if np.any(in_bin):
            r_per_theta[i] = float(np.max(dist_m[in_bin]))

    r_scalar = reduce_theta_radii(r_per_theta, est['method'], est['percentile'])
    return r_scalar, r_per_theta
