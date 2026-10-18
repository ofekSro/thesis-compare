"""The 'reqdir' estimator: 90 equal sectors and per-direction null-city MaxR.

Pinned (docs/PLAN_LAMBDA_ZURBAN_HE.md, decisions H1 and H2):
* token parsing — legacy tokens keep 91 sectors and no normalisation;
* the 90-sector layout integrates exactly 90 deg (legacy integrates 91);
* the per-direction rule, case by case;
* identity tests on real mesh data — a city that does nothing to the wave
  gives Λ = 1, and a perturbation of known radius gives that R_conv.
"""

import numpy as np
import pytest

from blastlib import constants, paths
from blastlib.config.parser import config_parser
from blastlib.geometry import concat3, exclude_radius
from blastlib.io import raw_store
from blastlib.processing.convergence import find_convergence_radius
from blastlib.processing.free_field import (find_percentile_radius,
                                            reference_level_per_theta, theta_index)
from blastlib.processing.grids import process_grids
from blastlib.processing.null_city import (null_city_processed, mesh_boxes,
                                           sector_cell_size, per_direction_lambda)
from blastlib.processing.radius_estimator import (
    N_THETA, N_THETA_EQUAL, in_theta_bin, reduce_theta_radii, resolve_estimator,
    theta_bin_edges, theta_centers_deg)
from blastlib.processing.soft_criterion import soft_pressure_fields, soft_pressure_weights

from conftest import _require_config

CONFIG = 'config_01_det1_b15_s5_h4_w50'


# ---- token and layout ------------------------------------------------------

def test_tokens():
    new = resolve_estimator('reqdir_soft3')
    assert (new['method'], new['base_method'], new['soft_beta']) == ('reqdir_soft3', 'reqdir', 3.0)
    assert (new['n_theta'], new['normalise']) == (N_THETA_EQUAL, 'dir')
    old = resolve_estimator('req_soft3')
    assert (old['n_theta'], old['normalise']) == (N_THETA, None)


def test_equal_sectors_cover_exactly_ninety_degrees():
    edges = theta_bin_edges(N_THETA_EQUAL)
    assert len(edges) == 91 and edges[0] == 0 and np.isclose(edges[-1], np.pi / 2)
    assert np.allclose(np.diff(np.degrees(edges)), 1.0)
    assert np.allclose(theta_centers_deg(N_THETA_EQUAL), np.arange(0.5, 90.0))
    R = 37.0
    assert reduce_theta_radii(np.full(N_THETA_EQUAL, R), 'reqdir') == pytest.approx(R, rel=1e-14)
    # The legacy layout sums its two half-width ends as full width (91 deg).
    assert reduce_theta_radii(np.full(N_THETA, R), 'req') == pytest.approx(R * np.sqrt(91 / 90), rel=1e-14)


def test_theta_index_matches_in_theta_bin_for_equal_sectors():
    rng = np.random.default_rng(7)
    X = np.r_[rng.uniform(0.01, 100, 20000), 10.0, 0.0]
    Z = np.r_[rng.uniform(0.01, 100, 20000), 0.0, 10.0]      # theta = 0 and 90 exactly
    idx = theta_index(X, Z, N_THETA_EQUAL)
    theta = np.arctan2(Z, X)
    edges = theta_bin_edges(N_THETA_EQUAL)
    for i in range(N_THETA_EQUAL):
        assert np.array_equal(in_theta_bin(theta, edges, i), idx == i), i
    assert idx[-2] == 0 and idx[-1] == N_THETA_EQUAL - 1


# ---- the per-direction rule -------------------------------------------------

def test_per_direction_cases():
    R_free, h = 50.0, np.full(4, 0.15)
    r_null = np.array([50.1, 40.0, 40.0, np.nan])   # A open, B/C capped at 40, dropped
    r_real = np.array([55.0, 36.0, 52.0, 70.0])    # gain, shielded in front, passed, ignored
    lam, n = per_direction_lambda(r_real, r_null, R_free, h)
    assert n == {'A': 1, 'B': 1, 'C': 1, 'dropped': 1}
    expected = np.sqrt((55.0 ** 2 + 36.0 ** 2 + 52.0 ** 2) / (50.1 ** 2 + 40.0 ** 2 + R_free ** 2))
    assert lam == pytest.approx(expected, rel=1e-14)


def test_per_direction_real_nan_counts_as_zero():
    lam, _ = per_direction_lambda(np.array([np.nan, 50.0]), np.array([50.0, 50.0]), 50.0,
                                  np.full(2, 0.15))
    assert lam == pytest.approx(np.sqrt(0.5), rel=1e-14)


def test_per_direction_identity():
    r = np.array([12.0, 30.0, 49.9, 20.0])
    lam, _ = per_direction_lambda(r, r.copy(), 50.0, np.full(4, 0.15))
    assert lam == 1.0


# ---- identity on real mesh data ---------------------------------------------

@pytest.fixture(scope='module')
def raw():
    d = _require_config(paths.RAW_NPZ_DIR, CONFIG)
    payload, ok = raw_store.load_raw_data(d, CONFIG)
    assert ok
    return payload


def _free_field_city(raw, perturb_r=None):
    """Reference field as the urban field, no buildings; optionally x1.5 (+30 kPa)
    inside r < perturb_r, which passes every convergence gate."""
    data = raw_store.grids_from_raw(raw)
    for g in raw_store.LEVELS:
        RP, RI = raw[f'refP{g}'].astype(np.float32), raw[f'refI{g}'].astype(np.float32)
        P, I = RP.copy(), RI.copy()
        if perturb_r is not None:
            zone = np.hypot(data[f'X{g}'], data[f'Z{g}']) < perturb_r
            P = np.where(zone, 1.5 * RP + 30.0, RP).astype(np.float32)
            I = np.where(zone, 1.5 * RI, RI).astype(np.float32)
        data[f'peakP{g}'], data[f'impulse{g}'] = P, I
    return process_grids(data, dict(constants.PARAMS), weight=float(raw['weight']))


def _maxr_theta(proc, est, z):
    """Per-sector raw reach of level Z for P, on the estimator's layout."""
    X, Zc = concat3(proc, 'X{}'), concat3(proc, 'Z{}')
    th = theta_index(X, Zc, est['n_theta'])
    dist = np.hypot(X, Zc)
    r_free = z * float(config_parser(CONFIG)['weight']) ** (1 / 3)
    lvl = reference_level_per_theta(concat3(proc, 'refP{}_fill'), dist, th, r_free,
                                    n_theta=est['n_theta'])
    return find_percentile_radius(concat3(proc, 'peakP{}_orig'), X, Zc, lvl, estimator=est,
                                  th_idx=th, dist=dist), r_free, lvl, th, dist


def test_free_field_gives_lambda_one(raw):
    est = resolve_estimator('reqdir_soft3')
    proc = _free_field_city(raw)
    lam = [_maxr_theta(proc, est, z)[0][0] / _maxr_theta(proc, est, z)[1] for z in (2, 5, 10, 15)]
    assert np.all(np.abs(np.array(lam) - 1) < 0.01), lam


def test_null_city_as_the_city_gives_lambda_dir_one(raw):
    est = resolve_estimator('reqdir_soft3')
    null = null_city_processed(raw)
    boxes = mesh_boxes(null)
    for z in (2, 5, 10):
        (_, r_theta), r_free, *_ = _maxr_theta(null, est, z)
        lam, _ = per_direction_lambda(r_theta, r_theta.copy(), r_free,
                                      sector_cell_size(r_theta, est['n_theta'], boxes))
        assert lam == 1.0


def test_known_perturbation_radius_is_recovered(raw):
    est = resolve_estimator('reqdir_soft3')
    cfg = config_parser(CONFIG)
    R0 = 6.0 * float(cfg['weight']) ** (1 / 3)
    proc = _free_field_city(raw, perturb_r=R0)
    soft_w = soft_pressure_weights(soft_pressure_fields(proc), est['soft_beta'])
    rad = find_convergence_radius(
        concat3(proc, 'ratioP{}'), concat3(proc, 'ratioI{}'), proc['peakP_all'], proc['peakI_all'],
        concat3(proc, 'X{}'), concat3(proc, 'Z{}'), exclude_radius(cfg), estimator=est, soft_w_P=soft_w)
    assert len(rad['radius_per_theta_P']) == N_THETA_EQUAL
    for key in ('pressure', 'impulse'):
        assert abs(rad[key] - R0) <= 0.15, (key, rad[key], R0)   # one fine cell
