"""The 'reqdir91' estimator: 91 whole-degree sectors, end sectors weighted 1/2.

Pinned (docs/PLAN_LAMBDA_ZURBAN_HE.md, decision H1, layout K1):
* token parsing — 91 sectors, per-direction normalisation, legacy edges;
* the weights integrate exactly 90 deg, and the legacy and 'reqdir' collapses
  are untouched;
* the weighted per-direction rule;
* identity tests on real mesh data — a city that does nothing to the wave
  gives Λ = 1, and a perturbation of known radius gives that R_conv.
"""

import numpy as np
import pytest

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.geometry import concat3, exclude_radius
from blastlib.io import raw_store
from blastlib.processing.convergence import find_convergence_radius
from blastlib.processing.null_city import (null_city_processed, mesh_boxes,
                                           sector_cell_size, per_direction_lambda)
from blastlib.processing.radius_estimator import (
    N_THETA, N_THETA_EQUAL, reduce_theta_radii, resolve_estimator, sector_weights,
    theta_bin_edges, theta_centers_deg)
from blastlib.processing.soft_criterion import soft_pressure_fields, soft_pressure_weights

from conftest import _require_config
from test_reqdir import CONFIG, _free_field_city, _maxr_theta


# ---- token and layout ------------------------------------------------------

def test_token():
    est = resolve_estimator('reqdir91_soft3')
    assert (est['method'], est['base_method'], est['soft_beta']) == ('reqdir91_soft3', 'reqdir91', 3.0)
    assert (est['n_theta'], est['normalise']) == (N_THETA, 'dir')
    # same edges and centres as the legacy layout; only the weights differ
    assert np.array_equal(theta_centers_deg(est['n_theta']), np.arange(0.0, 91.0))
    assert len(theta_bin_edges(est['n_theta'])) == 92


def test_weights():
    w = sector_weights('reqdir91_soft3')
    assert w.shape == (N_THETA,) and w[0] == w[-1] == 0.5 and np.all(w[1:-1] == 1.0)
    assert w.sum() == 90.0
    assert np.all(sector_weights('req_soft3') == 1.0) and sector_weights('req_soft3').size == N_THETA
    assert np.all(sector_weights('reqdir_soft3') == 1.0) and sector_weights('reqdir_soft3').size == N_THETA_EQUAL


def test_uniform_radius_is_returned_exactly():
    R = 37.0
    assert reduce_theta_radii(np.full(N_THETA, R), 'reqdir91') == pytest.approx(R, rel=1e-14)
    assert reduce_theta_radii(np.full(N_THETA, R), 'reqdir91_soft3') == pytest.approx(R, rel=1e-14)


def test_weighted_area_by_hand():
    rng = np.random.default_rng(3)
    r = rng.uniform(10, 80, N_THETA)
    r[[5, 40]] = np.nan                       # dropped sectors shrink the area, as in req
    w = np.r_[0.5, np.ones(89), 0.5]
    ok = ~np.isnan(r)
    A = np.sum(0.5 * r[ok] ** 2 * w[ok] * np.radians(1.0))
    assert reduce_theta_radii(r, 'reqdir91') == pytest.approx(np.sqrt(4 * A / np.pi), rel=1e-14)


def test_legacy_and_reqdir_collapses_unchanged():
    rng = np.random.default_rng(11)
    for n, token in ((N_THETA, 'req_soft3'), (N_THETA_EQUAL, 'reqdir_soft3')):
        r = rng.uniform(10, 80, n)
        r[7] = np.nan
        ok = ~np.isnan(r)
        A = np.sum(0.5 * r[ok] ** 2 * np.radians(1.0))
        assert reduce_theta_radii(r, token) == float(np.sqrt(4 * A / np.pi))   # bit for bit


def test_reqdir91_rejects_wrong_layout():
    with pytest.raises(ValueError):
        reduce_theta_radii(np.full(N_THETA_EQUAL, 10.0), 'reqdir91')


# ---- the weighted per-direction rule ---------------------------------------

def test_equal_weights_are_bit_exact():
    rng = np.random.default_rng(5)
    r_null = rng.uniform(20, 60, 90)
    r_real = r_null * rng.uniform(0.8, 1.3, 90)
    r_null[3] = np.nan
    h = np.full(90, 0.15)
    a, na = per_direction_lambda(r_real, r_null, 50.0, h)
    b, nb = per_direction_lambda(r_real, r_null, 50.0, h, w=np.ones(90))
    assert a == b and na == nb


def test_end_weights_by_hand():
    R_free, h = 50.0, np.full(N_THETA, 0.15)
    r_null = np.full(N_THETA, 60.0)            # every sector case A: d = r_null
    r_real = np.full(N_THETA, 60.0)
    r_real[0] = r_real[-1] = 90.0              # gain only on the two axes
    w = sector_weights('reqdir91')
    lam, n = per_direction_lambda(r_real, r_null, R_free, h, w=w)
    assert n == {'A': N_THETA, 'B': 0, 'C': 0, 'dropped': 0}
    expected = np.sqrt((89 * 60.0 ** 2 + 2 * 0.5 * 90.0 ** 2) / (90 * 60.0 ** 2))
    assert lam == pytest.approx(expected, rel=1e-14)
    # unweighted (the K0 error) would count the axes twice as heavily
    lam0, _ = per_direction_lambda(r_real, r_null, R_free, h)
    assert lam0 > lam


# ---- identity on real mesh data ---------------------------------------------

@pytest.fixture(scope='module')
def raw():
    d = _require_config(paths.RAW_NPZ_DIR, CONFIG)
    payload, ok = raw_store.load_raw_data(d, CONFIG)
    assert ok
    return payload


def test_free_field_gives_lambda_one(raw):
    est = resolve_estimator('reqdir91_soft3')
    proc = _free_field_city(raw)
    lam = []
    for z in (2, 5, 10, 15):
        (r_scalar, r_theta), r_free, *_ = _maxr_theta(proc, est, z)
        assert r_theta.shape == (N_THETA,)
        lam.append(r_scalar / r_free)
    # 1.1%, not the 1% of test_reqdir (owner, 2026-10-21): at Z = 2 (R_free
    # 7.4 m) the half-degree end sectors are narrower than a cell and reach
    # 1.23 R_free, Λ = 1.0106 (K2: 1.0069, legacy K0: 1.0189). The production
    # Λ_dir cancels this against the null city (next test).
    assert np.all(np.abs(np.array(lam) - 1) < 0.011), lam


def test_null_city_as_the_city_gives_lambda_dir_one(raw):
    est = resolve_estimator('reqdir91_soft3')
    w = sector_weights(est)
    null = null_city_processed(raw)
    boxes = mesh_boxes(null)
    for z in (2, 5, 10):
        (_, r_theta), r_free, *_ = _maxr_theta(null, est, z)
        lam, _ = per_direction_lambda(r_theta, r_theta.copy(), r_free,
                                      sector_cell_size(r_theta, est['n_theta'], boxes), w=w)
        assert lam == 1.0


def test_known_perturbation_radius_is_recovered(raw):
    est = resolve_estimator('reqdir91_soft3')
    cfg = config_parser(CONFIG)
    R0 = 6.0 * float(cfg['weight']) ** (1 / 3)
    proc = _free_field_city(raw, perturb_r=R0)
    soft_w = soft_pressure_weights(soft_pressure_fields(proc), est['soft_beta'])
    rad = find_convergence_radius(
        concat3(proc, 'ratioP{}'), concat3(proc, 'ratioI{}'), proc['peakP_all'], proc['peakI_all'],
        concat3(proc, 'X{}'), concat3(proc, 'Z{}'), exclude_radius(cfg), estimator=est, soft_w_P=soft_w)
    assert len(rad['radius_per_theta_P']) == N_THETA
    for key in ('pressure', 'impulse'):
        assert abs(rad[key] - R0) <= 0.15, (key, rad[key], R0)   # one fine cell
