"""Task B model-variant tests: exact recovery, legacy no-op, back-compat."""

import numpy as np
import pytest

from blastlib.regression.convergence_models import (
    _compute_pi_terms, _fit_impulse_group, _fit_pi_group,
    fit_impulse_all_groups, fit_pi_all_groups, predict_impulse, predict_pi)
from blastlib.regression.stats import lstsq


def _geometry(seed=7, n=24):
    rng = np.random.default_rng(seed)
    W = rng.choice([50.0, 250.0, 500.0, 1000.0, 1500.0], n)
    b = rng.choice([10.0, 15.0, 30.0], n)
    s = rng.choice([5.0, 8.0, 20.0], n)
    H = rng.choice([4.0, 12.0, 15.0, 24.0], n)
    rho = b ** 2 / (b + s) ** 2
    return W, rho, H, s


# ---- RadiusP additive Pi ----

def test_pi_ols_exact_recovery():
    W, rho, H, s = _geometry()
    a = 1.0
    pi2, switch, canyon = _compute_pi_terms(W, H, s, rho, a)
    true = dict(C0=8.0, C1=-0.6, C2=2.3, C3=0.6)
    Z = true['C0'] + true['C1'] * pi2 + true['C2'] * switch + true['C3'] * canyon
    R = Z * W ** (1 / 3)
    for weighting in ('ols', 'relative'):
        coef = _fit_pi_group(W, rho, H, s, R, a, weighting=weighting)
        for k, v in true.items():
            assert coef[k] == pytest.approx(v, abs=1e-9), (weighting, k)


def test_pi_legacy_matches_frozen_formula():
    """Default fit == plain lstsq on [1, pi2, switch, canyon] to 1e-12."""
    rng = np.random.default_rng(3)
    W, rho, H, s = _geometry(seed=3)
    a = 2.0
    pi2, switch, canyon = _compute_pi_terms(W, H, s, rho, a)
    Z = 9.0 - 1.1 * pi2 + 2.0 * switch + 0.7 * canyon + rng.normal(0, 0.5, len(W))
    R = Z * W ** (1 / 3)

    coef = _fit_pi_group(W, rho, H, s, R, a)
    X = np.column_stack([np.ones(len(W)), pi2, switch, canyon])
    C0, C1, C2, C3 = lstsq(X, R / W ** (1 / 3))
    assert coef['C0'] == pytest.approx(C0, abs=1e-12)
    assert coef['C1'] == pytest.approx(C1, abs=1e-12)
    assert coef['C2'] == pytest.approx(C2, abs=1e-12)
    assert coef['C3'] == pytest.approx(C3, abs=1e-12)


def test_pi_relative_weighting_lowers_relative_error():
    rng = np.random.default_rng(11)
    W, rho, H, s = _geometry(seed=11, n=48)
    a = 1.0
    pi2, switch, canyon = _compute_pi_terms(W, H, s, rho, a)
    Z_true = 8.0 - 0.6 * pi2 + 2.3 * switch + 0.6 * canyon
    # heteroscedastic noise: absolute spread grows with Z
    Z = Z_true * (1 + rng.normal(0, 0.15, len(W))) + rng.normal(0, 0.3, len(W))
    Z = np.abs(Z)
    R = Z * W ** (1 / 3)

    def msre(coef):
        """Mean SQUARED relative error — the loss 'relative' minimizes."""
        pred = predict_pi(W, rho, H, np.ones(len(W)), s, None, {1: coef})
        return np.mean(((pred - R) / R) ** 2)

    m_ols = msre(_fit_pi_group(W, rho, H, s, R, a, weighting='ols'))
    m_rel = msre(_fit_pi_group(W, rho, H, s, R, a, weighting='relative'))
    # relative-WLS is the exact minimizer of MSRE over the same design
    # matrix, so this holds for every draw, not just this seed
    assert m_rel <= m_ols + 1e-12


def test_pi_h0_branch_both_weightings():
    W, rho, _, s = _geometry(seed=5)
    H = np.zeros(len(W))
    pi2, switch, _ = _compute_pi_terms(W, H, s, rho, 1.0)
    Z = 7.0 - 0.5 * pi2 + 1.9 * switch
    R = Z * W ** (1 / 3)
    for weighting in ('ols', 'relative'):
        coef = _fit_pi_group(W, rho, H, s, R, 1.0, weighting=weighting)
        assert coef['C3'] == 0.0 and not coef['has_H_term']
        assert coef['C0'] == pytest.approx(7.0, abs=1e-9)


# ---- RadiusI power law ----

def _impulse_data(r2_true, seed=17, n=30):
    rng = np.random.default_rng(seed)
    W, rho, H, s = _geometry(seed=seed, n=n)
    W13 = W ** (1 / 3)
    ln_pi2 = np.log(s / W13)
    lnZ = (np.log(13.5) + 0.15 * np.log(rho) + 0.05 * np.log(H / s)
           + (-0.03) * ln_pi2 + r2_true * ln_pi2 ** 2)
    R = np.exp(lnZ) * W13
    return W, rho, H, s, R


def test_impulse_quad_exact_recovery():
    W, rho, H, s, R = _impulse_data(r2_true=0.04)
    coef = _fit_impulse_group(W, rho, H, s, R, model='quad')
    assert coef['A'] == pytest.approx(13.5, rel=1e-9)
    assert coef['p'] == pytest.approx(0.15, abs=1e-9)
    assert coef['q'] == pytest.approx(0.05, abs=1e-9)
    assert coef['r'] == pytest.approx(-0.03, abs=1e-9)
    assert coef['r2'] == pytest.approx(0.04, abs=1e-9)


def test_impulse_quad_recovers_zero_r2_on_legacy_data():
    W, rho, H, s, R = _impulse_data(r2_true=0.0)
    coef = _fit_impulse_group(W, rho, H, s, R, model='quad')
    assert coef['r2'] == pytest.approx(0.0, abs=1e-9)


def test_impulse_legacy_matches_frozen_formula():
    rng = np.random.default_rng(23)
    W, rho, H, s, R = _impulse_data(r2_true=0.0, seed=23)
    R = R * np.exp(rng.normal(0, 0.1, len(R)))

    coef = _fit_impulse_group(W, rho, H, s, R)
    assert coef['r2'] == 0.0
    W13 = W ** (1 / 3)
    X = np.column_stack([np.ones(len(W)), np.log(rho), np.log(H / s),
                         np.log(s / W13)])
    c0, p, q, r = lstsq(X, np.log(R / W13))
    assert coef['A'] == pytest.approx(np.exp(c0), rel=1e-12)
    assert coef['p'] == pytest.approx(p, abs=1e-12)
    assert coef['q'] == pytest.approx(q, abs=1e-12)
    assert coef['r'] == pytest.approx(r, abs=1e-12)


def test_predict_impulse_backcompat_without_r2_key():
    """Old 4-key coefficient dicts (no 'r2') must predict the legacy law."""
    W, rho, H, s, _ = _impulse_data(r2_true=0.0)
    det = np.ones(len(W), dtype=int)
    coef4 = {'A': 13.5, 'p': 0.15, 'q': 0.05, 'r': -0.03}
    coef5 = dict(coef4, r2=0.0)
    p4 = predict_impulse(W, rho, H, det, s, None, {1: coef4})
    p5 = predict_impulse(W, rho, H, det, s, None, {1: coef5})
    assert np.array_equal(p4, p5)


def test_all_groups_threading():
    """fit_*_all_groups pass the variant kwargs through per det group."""
    import pandas as pd
    W, rho, H, s, R = _impulse_data(r2_true=0.04, n=40)
    df = pd.DataFrame({
        'ChargeWeight': W, 'Height': H, 'StreetWidth': s,
        'AreaDensity': rho, 'Det': np.r_[np.ones(20), 2 * np.ones(20)],
        'RadiusI': R, 'RadiusP': R,
    })
    quad = fit_impulse_all_groups(df, 'RadiusI', model='quad')
    legacy = fit_impulse_all_groups(df, 'RadiusI')
    for det in (1, 2):
        assert abs(quad[det]['r2']) > 0 or quad[det]['r2'] == pytest.approx(0.04, abs=1e-6)
        assert legacy[det]['r2'] == 0.0
    rel = fit_pi_all_groups(df, 'RadiusP', weighting='relative')
    ols = fit_pi_all_groups(df, 'RadiusP')
    assert rel[1] is not None and ols[1] is not None
