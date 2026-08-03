"""Reduction tests for the convergence scanners.

The oracle below reimplements the far-to-near K_CONSECUTIVE scan
independently of blastlib; the legacy path must match it exactly. The
soft-scanner tests assert (a) the streak-DP computes the exact expectation
of the hard scan under independent per-cell violation probabilities, and
(b) the beta -> inf limit reproduces the hard path bit-exactly on the real
v2 npz data (cell weights AND per-sector radii AND the shipped anchors).
"""

import itertools

import numpy as np
import pytest

from blastlib import constants
from blastlib.processing.convergence import (
    K_CONSECUTIVE, TOLERANCE, _find_radius_for_slice,
    _find_radius_for_slice_soft, find_convergence_radius)
from blastlib.processing.radius_estimator import (
    reduce_theta_radii, resolve_estimator)
from blastlib.processing.soft_criterion import (
    soft_pressure_fields, soft_pressure_weights, tanh_projection)


def oracle_slice(ratio, peak, dist, exclude_r):
    """Independent reimplementation of the hard far->near K=3 scan."""
    valid = ~np.isnan(ratio) & (dist > exclude_r)
    r, p, d = ratio[valid], peak[valid], dist[valid]
    if len(d) == 0:
        return np.nan, np.nan
    order = np.argsort(d)[::-1]
    r, p, d = r[order], p[order], d[order]
    streak, start = 0, None
    for i in range(len(r)):
        if abs(r[i] - 1.0) > TOLERANCE:
            streak += 1
            if streak == 1:
                start = i
            if streak >= K_CONSECUTIVE:
                j = 0 if start == 0 else start - 1
                return d[j], p[j]
        else:
            streak, start = 0, None
    return d[-1], p[-1]


def _random_slices(n_cases=200, seed=1234):
    rng = np.random.default_rng(seed)
    for _ in range(n_cases):
        n = rng.integers(1, 120)
        dist = rng.uniform(0.5, 120.0, n)
        ratio = 1.0 + rng.normal(0.0, 0.03, n)
        # plant violation streaks of random length at random positions
        for _ in range(rng.integers(0, 4)):
            i = rng.integers(0, n)
            length = rng.integers(1, 6)
            ratio[i:i + length] = 1.0 + rng.choice([-1, 1]) * rng.uniform(0.06, 2.0)
        # sprinkle NaNs
        nan_idx = rng.random(n) < 0.15
        ratio[nan_idx] = np.nan
        peak = rng.uniform(0.1, 500.0, n)
        exclude_r = rng.choice([0.0, 2.5, 10.0])
        yield ratio, peak, dist, exclude_r


def test_slice_scan_matches_oracle():
    for ratio, peak, dist, exclude_r in _random_slices():
        got = _find_radius_for_slice(ratio, peak, dist, exclude_r)
        want = oracle_slice(ratio, peak, dist, exclude_r)
        if np.isnan(want[0]):
            assert np.isnan(got[0]) and np.isnan(got[1])
        else:
            assert got == want  # exact equality, not approx


def _synthetic_field(seed=99):
    """Cells laid out on exact integer-degree rays so each maps to one bin."""
    rng = np.random.default_rng(seed)
    xs, zs, ratio_P, ratio_I, peak_P, peak_I = [], [], [], [], [], []
    per_theta = {}
    for deg in range(0, 91, 3):  # a subset of sectors, some bins left empty
        n = int(rng.integers(5, 60))
        dist = rng.uniform(1.0, 100.0, n)
        rp = 1.0 + rng.normal(0.0, 0.03, n)
        i = rng.integers(0, n)
        rp[i:i + int(rng.integers(0, 5))] = 2.0
        ri = 1.0 + rng.normal(0.0, 0.03, n)
        pp = rng.uniform(1.0, 300.0, n)
        pi_ = rng.uniform(1.0, 300.0, n)
        th = np.radians(deg)
        x, z = dist * np.cos(th), dist * np.sin(th)
        xs.append(x)
        zs.append(z)
        ratio_P.append(rp)
        ratio_I.append(ri)
        peak_P.append(pp)
        peak_I.append(pi_)
        # the pipeline recomputes dist from X/Z — the oracle must see the
        # same rounded values or the comparison differs in the last ulp
        per_theta[deg] = (rp, pp, np.sqrt(x ** 2 + z ** 2))
    cat = lambda a: np.concatenate(a)
    return (cat(ratio_P), cat(ratio_I), cat(peak_P), cat(peak_I),
            cat(xs), cat(zs), per_theta)


def test_find_convergence_radius_matches_oracle_per_sector():
    ratio_P, ratio_I, peak_P, peak_I, X, Z, per_theta = _synthetic_field()
    exclude_r = 2.0
    out = find_convergence_radius(ratio_P, ratio_I, peak_P, peak_I, X, Z,
                                  exclude_r, estimator='req')
    r_expected = np.full(91, np.nan)
    for deg, (rp, pp, dist) in per_theta.items():
        r_expected[deg], _ = oracle_slice(rp, pp, dist, exclude_r)
    got = out['radius_per_theta_P']
    assert np.array_equal(got, r_expected, equal_nan=True)
    assert out['pressure'] == reduce_theta_radii(r_expected, method='req')


# ---- tanh projection ----

def test_tanh_projection_endpoints():
    for beta in (1.0, 4.0, 6.0, 12.0, 1e6):
        assert tanh_projection(0.0, beta, 0.5) == pytest.approx(0.0, abs=1e-15)
        assert tanh_projection(1.0, beta, 0.5) == pytest.approx(1.0, abs=1e-15)
        assert tanh_projection(0.5, beta, 0.5) == pytest.approx(0.5, abs=1e-15)


# ---- streak-DP scanner ----

def oracle_hard_radius(viol, dist):
    """Radius of the hard scan given a realized violation vector (far->near
    sorted). Mirrors _find_radius_for_slice's bookkeeping."""
    streak, start = 0, None
    for i, v in enumerate(viol):
        if v:
            streak += 1
            if streak == 1:
                start = i
            if streak >= K_CONSECUTIVE:
                return dist[0] if start == 0 else dist[start - 1]
        else:
            streak, start = 0, None
    return dist[-1]


def test_soft_dp_equals_brute_force_expectation():
    """The DP must compute the EXACT expectation of the hard scan under
    independent Bernoulli(w) violations — checked by enumerating all 2^n
    outcomes for small sectors."""
    rng = np.random.default_rng(42)
    for _ in range(20):
        n = int(rng.integers(3, 11))
        dist = np.sort(rng.uniform(1.0, 60.0, n))[::-1].copy()
        w = np.round(rng.uniform(0.0, 1.0, n), 3)
        w[rng.random(n) < 0.3] = 0.0

        expected = 0.0
        for viol in itertools.product([0, 1], repeat=n):
            prob = np.prod([wi if v else 1 - wi for wi, v in zip(w, viol)])
            if prob > 0:
                expected += prob * oracle_hard_radius(viol, dist)

        got, _ = _find_radius_for_slice_soft(
            w, np.ones(n), dist, exclude_r=0.0)
        assert got == pytest.approx(expected, rel=1e-12)


def test_soft_dp_hard_limits():
    dist = np.array([50.0, 40.0, 30.0, 20.0, 10.0, 5.0])
    peak = np.arange(6.0)
    # all converged -> innermost valid cell, the legacy fallback
    r, _ = _find_radius_for_slice_soft(np.zeros(6), peak, dist, 0.0)
    assert r == 5.0
    # streak at the outermost cells -> d[0]
    r, _ = _find_radius_for_slice_soft(
        np.array([1.0, 1, 1, 0, 0, 0]), peak, dist, 0.0)
    assert r == 50.0
    # streak completing at i=4 (start=2) -> cell just outside: d[1]
    w = np.array([0.0, 0, 1, 1, 1, 0])
    r, _ = _find_radius_for_slice_soft(w, peak, dist, 0.0)
    assert r == 40.0
    # matches the hard scan on the same realized pattern
    ratio = np.where(w > 0, 2.0, 1.0)
    r_hard, _ = _find_radius_for_slice(ratio, peak, dist, 0.0)
    assert r == r_hard
    # isolated single violation -> no absorption -> fallback
    r, _ = _find_radius_for_slice_soft(
        np.array([0.0, 0, 1, 0, 0, 0]), peak, dist, 0.0)
    assert r == 5.0


# ---- estimator token grammar ----

def test_soft_token_grammar():
    est = resolve_estimator('req')
    assert est['method'] == 'req' and est['soft_beta'] is None

    # a bare '_soft' takes its beta from the shared constant, whatever the
    # production value currently is
    default_beta = constants.PARAMS['softBeta']
    est = resolve_estimator('req_soft')
    assert est['method'] == f'req_soft{default_beta:g}'
    assert est['base_method'] == 'req' and est['soft_beta'] == default_beta

    est = resolve_estimator('req_soft8')
    assert est['method'] == 'req_soft8' and est['soft_beta'] == 8.0

    est = resolve_estimator({'method': 'req_soft', 'soft_beta': 12})
    assert est['method'] == 'req_soft12' and est['soft_beta'] == 12.0

    # soft_beta override is ignored on hard tokens
    est = resolve_estimator({'method': 'max', 'soft_beta': 8})
    assert est['method'] == 'max' and est['soft_beta'] is None

    # collapse of a soft token == collapse of its base
    radii = np.array([np.nan, 10.0, 20.0, np.nan, 15.0])
    assert (reduce_theta_radii(radii, 'req_soft3')
            == reduce_theta_radii(radii, 'req'))


# ---- beta -> inf reduction on the real npz data (the required test) ----

@pytest.mark.parametrize('config_name,anchor', [
    ('config_93_det2_b10_s5_h15_w250', 62.328853560057645),
    ('config_95_det2_b10_s5_h24_w250', 38.15139013777145),
])
def test_beta_inf_reduces_to_hard_on_npz(npz_v2_dir, config_name, anchor):
    from blastlib.config.parser import config_parser
    from blastlib.geometry import concat3, exclude_radius
    from blastlib.io.npz_store import load_processed_data
    from blastlib import constants

    cfg = config_parser(config_name)
    processed, ok = load_processed_data(npz_v2_dir, config_name)
    assert ok

    fields = soft_pressure_fields(processed)
    # The tanh transition band around the 10 kPa edge is ~3.8/beta kPa wide;
    # at beta=1e6 four real cells (|dP| within ~3e-4 kPa of the edge) still
    # sit inside it, so the bit-exact check needs a beta whose band (~4e-12
    # kPa at 1e12) provably contains no data.
    w_inf = soft_pressure_weights(fields, beta=1e12)

    # cell level: w at beta -> inf equals the hard violation indicator
    min_p = constants.PARAMS['minPressure_kPa']
    with np.errstate(invalid='ignore'):
        hard = (fields['gate'] & (fields['absdiff'] >= min_p)).astype(float)
    hard[np.isnan(fields['absdiff'])] = np.nan
    assert np.array_equal(w_inf, hard, equal_nan=True)

    args = (concat3(processed, 'ratioP{}'), concat3(processed, 'ratioI{}'),
            processed['peakP_all'], processed['peakI_all'],
            concat3(processed, 'X{}'), concat3(processed, 'Z{}'),
            exclude_radius(cfg))
    hard_out = find_convergence_radius(*args, estimator='req')
    soft_out = find_convergence_radius(*args, estimator='req',
                                       soft_w_P=w_inf)

    # sector level and collapsed radius: bit-exact reduction
    assert np.array_equal(soft_out['radius_per_theta_P'],
                          hard_out['radius_per_theta_P'], equal_nan=True)
    assert soft_out['pressure'] == hard_out['pressure'] == anchor
    # impulse path untouched by the soft criterion (Task A.5)
    assert np.array_equal(soft_out['radius_per_theta_I'],
                          hard_out['radius_per_theta_I'], equal_nan=True)
    assert soft_out['impulse'] == hard_out['impulse']
