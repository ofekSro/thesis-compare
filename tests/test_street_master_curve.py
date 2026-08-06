"""The master curve and R_half fits: unit peak, recovery, pinned constants."""

import sys

import numpy as np
import pandas as pd
import pytest

from conftest import PROJECT_ROOT
from blastlib import paths
from blastlib.street import fitting, model

sys.path.insert(0, str(PROJECT_ROOT / 'tools' / 'validate_migration'))
from compare_outputs import compare_csv                      # noqa: E402


def test_unit_peak_property():
    # The constraint the whole shape argument rests on: for ANY (p, q),
    # g_unit attains exactly 1 at x = p/q. Checked analytically at the
    # maximum and numerically over a dense grid.
    for p in (1.5, 2.48, 3.5):
        for q in (3.0, 4.75, 6.0):
            assert fitting.g_unit(p / q, p, q) == pytest.approx(1.0,
                                                                abs=1e-12)
            xx = np.linspace(1e-6, 3.0, 20001)
            gmax = float(np.max(fitting.g_unit(xx, p, q)))
            assert gmax <= 1.0 + 1e-12     # a unit PEAK: never exceeded...
            assert gmax > 1.0 - 1e-6       # ...and reached, up to grid step


def test_shipped_g_peak_overshoot_is_bounded():
    # The SHIPPED G rounds A to 1 dp, which overshoots the exact unit peak
    # by 0.1% (max g = 1.00096). Documented, frozen: a "fix" of A would
    # shift every predicted profile.
    xx = np.linspace(1e-6, 3.0, 200001)
    peak = float(np.max(model.g(xx)))
    assert 1.0 < peak < 1.002
    assert peak == pytest.approx(1.00096, abs=2e-4)


def test_fit_recovers_synthetic():
    rng = np.random.default_rng(0)
    x = rng.uniform(0.02, 1.65, 6000)
    y = fitting.g_unit(x, 2.5, 4.7) + rng.normal(0, 0.05, x.size)
    got = fitting.fit_master_curve(x, y)
    assert got['p'] == pytest.approx(2.5, rel=1e-2)
    assert got['q'] == pytest.approx(4.7, rel=1e-2)


def test_rhalf_form_and_pinned_exponent():
    # Synthetic anchors built from the exact functional form with the
    # (b+s) exponent at 1: the fit must recover the constants to float
    # precision. This is the structural lock on the pinned exponent — had
    # fit_r_half a free (b+s) power, the recovery of C would break.
    rows = []
    for b in (10, 15, 30):
        for s in (5, 12, 20):
            for H in (4, 12, 24):
                sq = b / (b + s)
                rh = 7.7 * (b + s) * sq ** -0.5 * (H / s) ** 0.3
                rows.append(dict(cfg=f'b{b}s{s}h{H}', b=b, s=s, H=H,
                                 E_peak=2.0, R_half_slope=rh))
    got = fitting.fit_r_half(pd.DataFrame(rows))
    assert got['C'] == pytest.approx(7.7, rel=1e-9)
    assert got['p_sq'] == pytest.approx(-0.5, abs=1e-9)
    assert got['p_hs'] == pytest.approx(0.3, abs=1e-9)
    assert got['mape'] == pytest.approx(0.0, abs=1e-9)


def test_cloud_gate_uses_floor(street_anchors_csv):
    # Membership arithmetic on the pinned table: 75 rows carry a fitted
    # slope anchor above the floor; the crossing column yields 71.
    anchors = pd.read_csv(street_anchors_csv)
    slope = anchors[np.isfinite(anchors.R_half_slope)
                    & (anchors.E_peak >= 1.2)]
    cross = anchors[np.isfinite(anchors.R_half_cross)
                    & (anchors.E_peak >= 1.2)]
    assert len(slope) == 75
    assert len(cross) == 71


@pytest.mark.slow
def test_constants_match_pinned(street_full_data, street_anchors_csv,
                                tmp_path):
    anchors = pd.read_csv(street_anchors_csv)
    x, y, used = fitting.collect_cloud(anchors, street_full_data,
                                       progress=lambda _m: None)
    assert (len(used), len(x)) == (75, 11545)
    g = fitting.fit_master_curve(x, y)
    assert g['A'] == pytest.approx(59.88434103668478, rel=1e-9)
    assert g['p'] == pytest.approx(2.483758865788831, rel=1e-9)
    assert g['q'] == pytest.approx(4.746669040697642, rel=1e-9)
    rh = fitting.fit_r_half(anchors)
    assert rh['C'] == pytest.approx(1.2849835992920906, rel=1e-9)
    assert rh['p_sq'] == pytest.approx(-1.0700379830256466, rel=1e-9)
    assert rh['p_hs'] == pytest.approx(0.2721321919965368, rel=1e-9)
    assert fitting.collapse_iqr(x, y) == pytest.approx(0.2218, abs=5e-4)

    mc = fitting.master_curve_table(x, y)
    out = tmp_path / 'master_curve_g.csv'
    mc.to_csv(out, index=False)
    status, detail = compare_csv(
        paths.CHECK_RESULTS_DIR / 'master_curve_g.csv', out,
        rtol=1e-12, atol=1e-12)
    assert status == 'PASS', detail
