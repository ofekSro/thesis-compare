"""LOGO summary: family-level bootstrap CI, R² views and coverage.

Synthetic err_df only, no data needed. Guards the statistics review of
2026-10-22: the CI resamples families within det with a fixed seed, and the
R² columns use the same divisor as the figures.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SPEC = importlib.util.spec_from_file_location(
    'logo_cv', Path(__file__).resolve().parents[1] / 'tools' / 'logo_cv' / 'logo_cv.py')
logo_cv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(logo_cv)


def _err_df(seed=0, rows_per_family=(2, 3)):
    """18 families per det, 2-3 configs each, P and I rows, conv layout."""
    rng = np.random.default_rng(seed)
    rows = []
    for det in (1, 2):
        for f in range(18):
            fam = f'det{det}_f{f}'
            for w in (50, 500, 1500)[:rows_per_family[f % 2]]:
                cfg = f'c_d{det}_f{f}_w{w}'
                for t in ('P', 'I'):
                    act = rng.uniform(5, 15) * w ** (1 / 3)
                    pred = act * (1 + rng.normal(0, 0.1))
                    rows.append({'Config': cfg, 'Det': det, 'Family': fam,
                                 'Target': t, 'Actual': act, 'Predicted': pred,
                                 'ErrPct': 100 * abs(pred - act) / act})
    return pd.DataFrame(rows)


def _configs(err_df):
    return (err_df[['Config', 'Det']].drop_duplicates()
            .rename(columns={'Config': 'ConfigName'}))


def test_summary_is_reproducible():
    d = _err_df()
    a = logo_cv.summarize(d, 'conv', _configs(d))
    b = logo_cv.summarize(d, 'conv', _configs(d))
    pd.testing.assert_frame_equal(a, b)


def test_old_columns_unchanged_and_ci_brackets_mean():
    d = _err_df()
    s = logo_cv.summarize(d, 'conv', _configs(d))
    assert list(s.columns[:8]) == ['Target', 'Scope', 'N', 'N_finite',
                                   'Mean', 'Median', 'P90', 'Max']
    for t in ('P', 'I'):
        sub = d[d.Target == t]
        row = s[(s.Target == t) & (s.Scope == 'pooled')].iloc[0]
        assert row.Mean == pytest.approx(sub.ErrPct.mean(), rel=1e-12)
        assert row.Mean_CI95_lo < row.Mean < row.Mean_CI95_hi


def test_ci_collapses_when_families_are_identical():
    d = _err_df()
    d['ErrPct'] = 7.0
    s = logo_cv.summarize(d, 'conv', _configs(d))
    assert np.allclose(s[['Mean_CI95_lo', 'Mean_CI95_hi']].values, 7.0)


def test_seed_controls_ci():
    d = _err_df()
    fin = d[d.Target == 'P']
    assert (logo_cv.family_bootstrap_ci(fin, 2000, 1)
            == logo_cv.family_bootstrap_ci(fin, 2000, 1))
    assert (logo_cv.family_bootstrap_ci(fin, 2000, 1)
            != logo_cv.family_bootstrap_ci(fin, 2000, 2))


def test_r2_on_z_divides_by_w13():
    d = _err_df()
    s = logo_cv.summarize(d, 'conv', _configs(d))
    sub = d[d.Target == 'P']
    w13 = sub.Config.str.extract(r'_w(\d+)$')[0].astype(float) ** (1 / 3)
    a, q = sub.Actual / w13, sub.Predicted / w13
    r2 = 1 - ((a - q) ** 2).sum() / ((a - a.mean()) ** 2).sum()
    row = s[(s.Target == 'P') & (s.Scope == 'pooled')].iloc[0]
    assert row.R2_Z == pytest.approx(r2, rel=1e-12)


def test_coverage_counts_configs_in_scope():
    d = _err_df()
    configs = _configs(d)
    dropped = d.Config.unique()[:3]   # three det-1 configs never graded
    s = logo_cv.summarize(d[~d.Config.isin(dropped)], 'conv', configs)
    row = s[(s.Target == 'P') & (s.Scope == 'det1')].iloc[0]
    n_det1 = int((configs.Det == 1).sum())
    assert row.Configs_total == n_det1
    assert row.N_configs == n_det1 - 3
    assert row.Coverage_configs == pytest.approx((n_det1 - 3) / n_det1)


def test_per_family_ci_resamples_family_means():
    d = _err_df()
    s = logo_cv.summarize_families(d, _configs(d))
    row = s[s.Target == 'I'].iloc[0]
    assert row.N == 36 and row.N_families == 36
    assert row.Mean_CI95_lo < row.Mean < row.Mean_CI95_hi
