"""The scoring convention, clause by clause, plus the pinned-table locks."""

import sys

import numpy as np
import pandas as pd
import pytest

from conftest import PROJECT_ROOT
from blastlib import paths
from blastlib.street import validation

sys.path.insert(0, str(PROJECT_ROOT / 'tools' / 'validate_migration'))
from compare_outputs import compare_csv                      # noqa: E402


def _meas(r, e_s):
    return pd.DataFrame({'r': np.asarray(r, float),
                         'E_s': np.asarray(e_s, float)})


R_MODEL = np.arange(0.5, 30.0, 0.5)
PRED2 = np.full_like(R_MODEL, 2.0)


def test_scoring_floor_clause():
    # Only slices with smoothed E_s >= FLOOR = 1.2 enter — slices with no
    # channelling carry no information about a channelling model.
    meas = _meas([1, 2, 3, 4, 5, 6, 7],
                 [1.0, 1.19, 1.2, 1.5, 2.0, 2.5, 3.0])
    mape, n = validation.score_profile(meas, R_MODEL, PRED2)
    assert n == 5                              # 1.2 is inclusive
    want = 100 * np.mean([abs(2 - v) / v for v in (1.2, 1.5, 2.0, 2.5, 3.0)])
    assert mape == pytest.approx(want, rel=1e-12)


def test_scoring_range_clause():
    # Slices beyond the model grid's last point (29.5 here) are excluded
    # outright; the last point itself is inclusive.
    meas = _meas([29.5, 30.25, 35.0, 1, 2, 3, 4],
                 [2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0])
    mape, n = validation.score_profile(meas, R_MODEL, PRED2)
    assert n == 5                              # 29.5 in, 30.25/35.0 out
    assert mape == pytest.approx(0.0, abs=1e-12)


def test_scoring_min_slices_clause():
    meas = _meas([1, 2, 3, 4], [2.0, 2.0, 2.0, 2.0])
    mape, n = validation.score_profile(meas, R_MODEL, PRED2)
    assert mape is None and n == 4


def test_scoring_nan_band_selected_not_scored():
    # The model is NaN past x = X_MAX while the grid runs to X_MAX*S: those
    # slices are SELECTED (count toward the >= 5) but dropped by nanmean.
    pred = PRED2.copy()
    pred[R_MODEL > 20.0] = np.nan
    meas = _meas([5, 10, 15, 25, 28], [2.0, 2.0, 1.5, 9.9, 9.9])
    mape, n = validation.score_profile(meas, R_MODEL, pred)
    assert n == 5                              # the two NaN-band slices count
    want = 100 * np.mean([0.0, 0.0, abs(2 - 1.5) / 1.5])
    assert mape == pytest.approx(want, rel=1e-12)   # ...but are not scored


def test_gate_classification(street_anchors_csv):
    # The TRUE confusion under the shipped constants (the doc's old "zero
    # false alarms" was measured on pre-refit constants): 92/96 correct,
    # misses 67/70, false alarms 78/80 — conservative direction.
    anchors = pd.read_csv(street_anchors_csv)
    _df, summary = validation.gate_table(anchors)
    assert (summary['n_correct'], summary['n']) == (92, 96)
    assert {c.split('_det')[0] for c in summary['misses']} \
        == {'config_67', 'config_70'}
    assert {c.split('_det')[0] for c in summary['false_alarms']} \
        == {'config_78', 'config_80'}


def test_membership_is_computed(street_anchors_csv):
    anchors = pd.read_csv(street_anchors_csv)
    members = anchors[anchors.E_peak >= 1.2]
    assert len(members) == 88
    excluded = {c.split('_det')[0] for c in
                set(anchors.cfg) - set(members.cfg)}
    assert excluded == {'config_10', 'config_11', 'config_13', 'config_16',
                        'config_77', 'config_78', 'config_79', 'config_80'}


@pytest.mark.slow
def test_validation_matches_pinned(street_full_data, street_anchors_csv,
                                   tmp_path):
    out_csv = tmp_path / 'e_profile_validation_88.csv'
    val = validation.validate_all(street_anchors_csv, street_full_data,
                                  out_csv=out_csv, progress=lambda _m: None)
    status, detail = compare_csv(
        paths.CHECK_RESULTS_DIR / 'e_profile_validation_88.csv', out_csv,
        rtol=1e-12, atol=1e-12)
    assert status == 'PASS', detail
    hs = validation.headline_stats(val)
    assert hs['mean'] == pytest.approx(9.7364, abs=0.005)
    assert hs['median'] == pytest.approx(8.50, abs=0.005)
    assert hs['p90'] == pytest.approx(17.34, abs=0.01)
    assert hs['max'] == 31.0


@pytest.mark.slow
def test_envelope_true_stats(street_full_data, street_anchors_csv):
    # The corrected-claims lock: code and doc can never drift apart again.
    env = validation.envelope_stats(street_anchors_csv, street_full_data,
                                    progress=lambda _m: None)
    assert env['coverage'] == pytest.approx(96.34, abs=0.05)
    assert env['exceed_gt_015'] == pytest.approx(0.73, abs=0.05)
    assert env['mean_overpred'] == pytest.approx(27.2, abs=0.2)
    assert env['worst_exceed'] == pytest.approx(0.723, abs=0.002)
    assert env['worst_cfg'].startswith('config_26')
    assert env['n_slices'] == 10531
