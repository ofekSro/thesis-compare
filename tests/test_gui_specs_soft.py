"""Spec-level soft-criterion wiring (token discovery + soft preflight).

Kept separate from test_gui_soft_wiring.py because gui/specs.py also
carries uncommitted preview-tab work; this file belongs with that commit.
"""

import pytest

from gui import specs


def test_available_radius_methods_lists_builtins_and_disk_tokens():
    tokens = specs.available_radius_methods()
    for builtin in ('req', 'max', 'p95'):
        assert builtin in tokens
    if not (specs.paths.TABLES_DIR / 'convergence_table_req_soft4.csv').exists():
        pytest.skip('soft tables not generated on this checkout')
    assert 'req_soft4' in tokens
    assert not any(t.startswith('SHIPPED') for t in tokens)


def test_analysis_requirements_soft_adds_probe():
    hard = specs.analysis_requirements(
        {'phase': '1', 'radius_estimator': {'method': 'req'}})
    assert all(r.get('kind') != 'check' for r in hard)

    soft = specs.analysis_requirements(
        {'phase': '1',
         'radius_estimator': {'method': 'req_soft', 'soft_beta': 4.0}})
    checks = [r for r in soft if r.get('kind') == 'check']
    assert len(checks) == 1

    # The soft preflight must point at a folder that can actually serve the
    # raw band fields — the v3 raw store when it exists, else the v2
    # superset. Never the v1 folder, which carries neither.
    globs = [r for r in soft if r.get('kind') == 'glob']
    expected = specs.paths.default_npz_dir(soft=True)
    assert any(str(expected) == str(r['path']) for r in globs)
    assert all(str(specs.paths.PROCESSED_NPZ_DIR) != str(r['path'])
               for r in globs)
