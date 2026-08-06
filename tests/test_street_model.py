"""The closed-form model: frozen constants, spot values, domain contracts."""

import inspect

import numpy as np
import pytest

from blastlib.street import constants, model


def _historical_constants():
    # Verbatim copy of the shipped values (from the retired e_profile.py
    # :69-97 and the 2026-08 refit). The frozen contract: NO refactor may
    # nudge any of these — a deliberate model revision must change BOTH
    # copies and say so in the doc's changelog.
    return dict(
        EPK=dict(C=2.69, a=1.81, b=-0.50, k_hs=4.56, k_hw=7.07),
        RHALF=dict(C=1.28, p_sq=-1.07, p_hs=0.27),
        G=dict(A=59.9, p=2.48, q=4.75),
        ENV=dict(S=1.35, f=1.20),
        GATE=1.5, FLOOR=1.2, X_MAX=1.6, X_FIT=1.65, RMAX=100.0,
        MIN_PTS=6, MIN_SPAN=4.0, HI_FRAC=0.85, LO_FRAC=0.25,
        SMOOTH_METRES=2.5, MIN_CELLS_PER_BIN=8)


def test_shipped_constants_frozen():
    want = _historical_constants()
    for name, value in want.items():
        assert getattr(constants, name) == value, name


def test_e_peak_historical_values():
    # Rows quoted verbatim from the pinned e_profile_validation_88.csv
    # (E_peak_pred, 3 dp). The formula must land on them exactly after
    # rounding — the gate-D contract in miniature.
    for (b, s, H, W), want in [
        ((15, 5, 24, 1500), 3.418),        # config_09
        ((15, 5, 4, 50), 2.335),           # config_37
        ((15, 20, 12, 500), 1.342),        # config_50
    ]:
        assert round(float(model.e_peak(b, s, H, W)), 3) == want


def test_e_peak_ignores_det():
    assert model.e_peak(15, 5, 12, 500, det=1) \
        == model.e_peak(15, 5, 12, 500, det=2)


def test_r_half_is_w_free():
    assert 'W' not in inspect.signature(model.r_half).parameters


def test_e_peak_limits():
    # H -> 0 gives E -> 1 exactly (the saturation form's whole point — a
    # power law cannot do this).
    assert model.e_peak(15, 5, 0, 500) == pytest.approx(1.0, abs=1e-12)


def test_profile_nan_beyond_xmax():
    b, s, H, W = 15, 5, 12, 500
    Rh = model.r_half(b, s, H)
    r = np.array([0.5 * Rh, 1.6 * Rh, 1.6 * Rh + 1e-6, 2.0 * Rh])
    out = model.predict_profile(r, b, s, H, W)
    assert np.isfinite(out[0]) and np.isfinite(out[1])   # x = 1.6 inclusive
    assert np.isnan(out[2]) and np.isnan(out[3])


def test_envelope_domain_and_dominance():
    b, s, H, W = 15, 5, 12, 500
    Rh = model.r_half(b, s, H)
    r = np.arange(0.5, 1.6 * Rh, 0.5)
    prof = model.predict_profile(r, b, s, H, W)
    env = model.predict_envelope(r, b, s, H, W)
    both = np.isfinite(prof) & np.isfinite(env)
    assert both.any()
    assert np.all(env[both] >= prof[both] - 1e-12)
    r2 = np.array([1.6 * 1.35 * Rh + 1e-6])
    assert np.isnan(model.predict_envelope(r2, b, s, H, W)[0])


def test_profile_accepts_scalar():
    # Additive fix over the retired reference (which raised on 0-d input).
    out = model.predict_profile(10.0, 15, 5, 12, 500)
    assert np.isfinite(float(out))


def test_gate_boundary():
    assert model.gate_verdict(1.5) is True
    assert model.gate_verdict(1.4999) is False


def test_g_unit_peak_location():
    xx = np.linspace(0.01, 2.0, 100001)
    x_peak = xx[np.argmax(model.g(xx))]
    assert x_peak == pytest.approx(constants.G['p'] / constants.G['q'],
                                   abs=1e-3)
    assert float(model.g(1.0)) == pytest.approx(0.518, abs=1e-3)
