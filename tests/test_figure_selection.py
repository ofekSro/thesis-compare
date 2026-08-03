"""Per-category figure selection for Phase 1 (make_figures)."""

import pytest

from run_analysis import FIG_SUBDIRS, _resolve_figure_set


def test_bool_backcompat():
    assert _resolve_figure_set(True) == set(FIG_SUBDIRS)
    assert _resolve_figure_set(False) == set()
    assert _resolve_figure_set(None) == set()
    assert _resolve_figure_set(()) == set()


def test_subset_selection():
    assert _resolve_figure_set(('ratio',)) == {'ratio'}
    assert _resolve_figure_set(['theta_P', 'theta_I']) == {'theta_P', 'theta_I'}
    assert _resolve_figure_set(FIG_SUBDIRS) == set(FIG_SUBDIRS)


def test_unknown_category_is_an_error():
    with pytest.raises(ValueError, match='unknown figure categories'):
        _resolve_figure_set(('ratio', 'nope'))
