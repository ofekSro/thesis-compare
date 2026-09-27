"""MaxR must be measured on the same terms as R_conv.

Three properties are pinned here, all of them things that were previously true
of the convergence radius but not of the exceedance radius:

* the near-blast exclusion radius applies to both;
* the free-field threshold is sampled per direction, so the mesh anisotropy
  cancels the way it does for R_conv;
* the Z_urban fit domain is the domain the model is actually used on.

The scalar / exclude_r=0 path is asserted to be bit-identical to the historical
behaviour, so a table produced with the defaults cannot silently move.
"""

import numpy as np
import pytest

from blastlib.processing.free_field import (
    find_percentile_radius, reference_level_per_theta, theta_index,
)
from blastlib.processing.radius_estimator import (
    N_THETA, in_theta_bin, reduce_theta_radii, theta_bin_edges,
)


@pytest.fixture(scope='module')
def cloud():
    """A quarter-plane cloud of cells with a reproducible value field."""
    rng = np.random.default_rng(20260803)
    X = rng.uniform(0.05, 120.0, 40000)
    Z = rng.uniform(0.05, 120.0, 40000)
    vals = rng.uniform(0.0, 100.0, 40000)
    return X, Z, vals


@pytest.fixture(scope='module')
def grid():
    """A regular quarter-plane mesh — what the solver actually writes.

    The reference-level tests use this rather than a random cloud: sampling a
    thin ring is only well posed when the ring is populated, and on a 0.25 m
    mesh it is (hundreds of cells per sector at r = 50 m). A sparse cloud
    would exercise the ring-widening fallback instead of the sampling.
    """
    ax = np.arange(0.125, 120.0, 0.25)
    X, Z = np.meshgrid(ax, ax)
    return X.ravel(), Z.ravel()


def _historical(vals, X, Z, ff_val):
    """The pre-change implementation, kept verbatim as the reference."""
    match = ~np.isnan(vals) & (vals >= ff_val)
    if not np.any(match):
        return np.nan
    dist = np.sqrt(X[match] ** 2 + Z[match] ** 2)
    theta = np.arctan2(Z[match], X[match])
    edges = theta_bin_edges()
    r = np.full(N_THETA, np.nan)
    for i in range(N_THETA):
        in_bin = in_theta_bin(theta, edges, i)
        if np.any(in_bin):
            r[i] = float(np.max(dist[in_bin]))
    return reduce_theta_radii(r, 'req')


# ---- binning ------------------------------------------------------------

def test_theta_index_matches_the_shared_binning(cloud):
    """The vectorised index must select exactly what in_theta_bin selects."""
    X, Z, _ = cloud
    idx = theta_index(X, Z)
    theta = np.arctan2(Z, X)
    edges = theta_bin_edges()
    for i in range(N_THETA):
        assert np.array_equal(in_theta_bin(theta, edges, i), idx == i), i
    assert np.all(idx >= 0), 'first-quadrant cells must all be assigned'


# ---- the scalar path must not move --------------------------------------

@pytest.mark.parametrize('ff_val', [5.0, 25.0, 60.0, 95.0])
def test_scalar_path_is_bit_identical_to_the_old_behaviour(cloud, ff_val):
    X, Z, vals = cloud
    got, _ = find_percentile_radius(vals, X, Z, ff_val, estimator='req')
    assert got == _historical(vals, X, Z, ff_val)


def test_uniform_array_level_equals_the_scalar(cloud):
    X, Z, vals = cloud
    a, _ = find_percentile_radius(vals, X, Z, 40.0, estimator='req')
    b, _ = find_percentile_radius(vals, X, Z, np.full(N_THETA, 40.0),
                                  estimator='req')
    assert a == b


def test_array_level_must_have_one_entry_per_sector(cloud):
    X, Z, vals = cloud
    with pytest.raises(ValueError, match='scalar'):
        find_percentile_radius(vals, X, Z, np.zeros(12), estimator='req')


# ---- exclusion radius ---------------------------------------------------

def test_exclusion_radius_drops_inner_cells(cloud):
    """No selected cell may lie at or inside exclude_r."""
    X, Z, vals = cloud
    dist = np.sqrt(X ** 2 + Z ** 2)
    ex = 55.0
    _, r_theta = find_percentile_radius(vals, X, Z, 20.0, estimator='req',
                                        exclude_r=ex)
    finite = r_theta[~np.isnan(r_theta)]
    assert finite.size and np.all(finite > ex)
    assert np.max(finite) <= np.max(dist) + 1e-9


def test_exclusion_radius_can_empty_the_region(cloud):
    """A region entirely inside the first street yields no radius at all."""
    X, Z, vals = cloud
    r, r_theta = find_percentile_radius(vals, X, Z, 20.0, estimator='req',
                                        exclude_r=1e6)
    assert np.isnan(r)
    assert np.all(np.isnan(r_theta))


def test_exclusion_radius_is_off_by_default(cloud):
    """Callers that do not pass it keep the historical result."""
    X, Z, vals = cloud
    a, _ = find_percentile_radius(vals, X, Z, 30.0, estimator='req')
    b, _ = find_percentile_radius(vals, X, Z, 30.0, estimator='req',
                                  exclude_r=0.0)
    assert a == b == _historical(vals, X, Z, 30.0)


def test_phase1_does_not_exclude_inside_the_sector_scan():
    """Production must apply the near-field exclusion per row, not per cell.

    Excluding cells here gives a sector radius zero rather than removing the
    sector, and Req integrates that as zero area — which shortens MaxR at
    small Z_free and de-identifies the pressure fit. The reason lives in
    find_percentile_radius's docstring; this pins the call site so the
    "obvious" change cannot be made silently.
    """
    import inspect
    import run_analysis
    src = inspect.getsource(run_analysis.run_phase1)
    calls = [seg for seg in src.split('find_percentile_radius(')[1:]]
    assert calls, 'run_phase1 no longer calls find_percentile_radius'
    for seg in calls:
        head = seg.split(')')[0]
        assert 'exclude_r' not in head, (
            'run_phase1 passes exclude_r into the sector scan; the near-field '
            'exclusion belongs in z_urban_valid_mask')


# ---- per-direction reference level --------------------------------------

def test_constant_reference_field_is_recovered_exactly(grid):
    X, Z = grid
    dist = np.sqrt(X ** 2 + Z ** 2)
    lvl = reference_level_per_theta(np.full(len(X), 7.5), dist,
                                    theta_index(X, Z), 60.0)
    assert not np.isnan(lvl).any()
    assert np.allclose(lvl, 7.5)


def test_radial_reference_field_is_recovered_per_sector(grid):
    """A field that depends only on radius gives the same level everywhere."""
    X, Z = grid
    dist = np.sqrt(X ** 2 + Z ** 2)
    true = 1000.0 / 50.0 ** 1.5
    lvl = reference_level_per_theta(1000.0 / dist ** 1.5, dist,
                                    theta_index(X, Z), 50.0, tol=0.6)
    assert not np.isnan(lvl).any()
    # No angular dependence in the field, so none may appear in the level;
    # what is left is the ring half-width, ~1.8% at r = 50 for tol = 0.6.
    assert np.max(np.abs(lvl / true - 1)) < 0.02


def test_anisotropic_reference_is_seen_per_direction(grid):
    """A level that varies with angle must come back varying with angle.

    This is the whole point of the change: with a scalar threshold the
    direction-dependence of the reference field leaks into MaxR instead.
    """
    X, Z = grid
    dist = np.sqrt(X ** 2 + Z ** 2)
    theta = np.arctan2(Z, X)
    ref = 10.0 * (1.0 + 0.10 * np.sin(2 * theta))     # +10% on the diagonal
    lvl = reference_level_per_theta(ref, dist, theta_index(X, Z), 60.0)
    assert not np.isnan(lvl).any()
    assert lvl[45] > lvl[0] and lvl[45] > lvl[90]
    assert 0.09 < (lvl[45] - lvl[0]) / lvl[0] < 0.11


def test_ring_widens_until_every_sector_is_served(cloud):
    """A ring too thin for the sampling must widen, not return NaN."""
    X, Z, _ = cloud                      # sparse: ~2 cells per sector per 1 m
    dist = np.sqrt(X ** 2 + Z ** 2)
    idx = theta_index(X, Z)
    assert np.any(np.bincount(idx[np.abs(dist - 50.0) < 0.5],
                              minlength=N_THETA) == 0), 'fixture must be sparse'
    lvl = reference_level_per_theta(1000.0 / dist ** 1.5, dist, idx, 50.0,
                                    tol=0.5)
    assert not np.isnan(lvl).any()
    assert np.max(np.abs(lvl / (1000.0 / 50.0 ** 1.5) - 1)) < 0.10


def test_level_is_nan_where_the_reference_has_no_data(grid):
    """Sectors the field cannot serve are reported, not invented."""
    X, Z = grid
    dist = np.sqrt(X ** 2 + Z ** 2)
    lvl = reference_level_per_theta(np.full(len(X), np.nan), dist,
                                    theta_index(X, Z), 60.0)
    assert np.all(np.isnan(lvl)), 'no data must not be filled in silently'


def test_all_nan_level_yields_no_radius(cloud):
    X, Z, vals = cloud
    r, _ = find_percentile_radius(vals, X, Z, np.full(N_THETA, np.nan),
                                  estimator='req')
    assert np.isnan(r)
