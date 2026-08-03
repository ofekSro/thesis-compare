"""GUI wiring for the soft criterion — headless tests only (no Tk windows).

Covers the pieces that do not depend on the (work-in-progress) tab specs:
the estimator-dict composition the widget delegates to, the v2 probe, the
'check' requirement kind, and the resolve_estimator round-trips for every
dict shape the widget can produce. Spec-level wiring is covered separately
in test_gui_specs_soft.py.
"""

import pytest

from blastlib.processing.radius_estimator import resolve_estimator
from blastlib.processing.soft_criterion import raw_fields_available
from gui import runner
from gui.widgets import estimator_value


# ---- estimator dict composition (the widget's value()) ----

def test_hard_dicts_are_bit_identical_to_legacy():
    assert estimator_value('req', '95', 'hard', '4.0') == {'method': 'req'}
    assert estimator_value('max', '95', 'hard', '4.0') == {'method': 'max'}
    assert estimator_value('p95', '97', 'hard', '4.0') == {
        'method': 'percentile', 'percentile': 97.0}


def test_soft_dicts_carry_suffix_and_beta():
    assert estimator_value('req', '95', 'soft', '4.0') == {
        'method': 'req_soft', 'soft_beta': 4.0}
    assert estimator_value('p95', '97', 'soft', '2.5') == {
        'method': 'percentile_soft', 'percentile': 97.0, 'soft_beta': 2.5}


def test_estimator_value_validation():
    with pytest.raises(ValueError):
        estimator_value('req', '95', 'soft', '0.5')     # below 1
    with pytest.raises(ValueError):
        estimator_value('req', '95', 'soft', '21')      # above 20
    with pytest.raises(ValueError):
        estimator_value('req', '95', 'soft', 'abc')
    with pytest.raises(ValueError):
        estimator_value('p95', 'abc', 'hard', '4.0')


def test_widget_dicts_resolve_to_canonical_tokens():
    """The exact dicts the widget produces, through the shared resolver."""
    assert resolve_estimator(estimator_value('req', '95', 'hard', '4.0')
                             )['method'] == 'req'
    est = resolve_estimator(estimator_value('req', '95', 'soft', '4.0'))
    assert est['method'] == 'req_soft4'
    assert est['base_method'] == 'req' and est['soft_beta'] == 4.0
    est = resolve_estimator(estimator_value('p95', '97', 'soft', '4.5'))
    assert est['method'] == 'p97_soft4.5' and est['soft_beta'] == 4.5


# ---- v2 probe ----

def test_raw_fields_probe_missing_dir(tmp_path):
    ok, reason = raw_fields_available(tmp_path / 'nope')
    assert not ok and 'does not exist' in reason
    empty = tmp_path / 'empty'
    empty.mkdir()
    ok, reason = raw_fields_available(empty)
    assert not ok and 'no config_*.npz' in reason


def test_raw_fields_probe_v1_lacks_keys(npz_v1_dir):
    ok, reason = raw_fields_available(npz_v1_dir)
    assert not ok and 'lacks the raw fields' in reason


def test_raw_fields_probe_v2_ok(npz_v2_dir):
    ok, reason = raw_fields_available(npz_v2_dir)
    assert ok and reason == ''


# ---- the 'check' requirement kind ----

def test_check_requirement_kind():
    reqs = [{'kind': 'check', 'label': 'probe', 'fn': lambda: '',
             'hint': 'unused'}]
    assert runner.check_requirements(reqs) == []

    reqs = [{'kind': 'check', 'label': 'probe', 'fn': lambda: 'broken',
             'hint': 'fix it'}]
    problems = runner.check_requirements(reqs)
    assert len(problems) == 1
    assert 'probe: broken' in problems[0] and 'fix it' in problems[0]

    # a probe that raises is reported, not propagated
    def boom():
        raise RuntimeError('probe exploded')
    problems = runner.check_requirements(
        [{'kind': 'check', 'label': 'probe', 'fn': boom}])
    assert problems and 'probe exploded' in problems[0]
