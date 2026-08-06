"""The two street tabs: specs present, targets import, params match main().

Mirrors test_gui_specs_soft.py's approach: gui.specs is data (no tkinter),
so the wiring is testable headless — the target must be importable and
every declared parameter key must be a keyword main() actually accepts.
"""

import inspect
import sys

from conftest import PROJECT_ROOT

from gui import specs


def _tab(name):
    hits = [t for t in specs.TABS if t['name'] == name]
    assert len(hits) == 1, f'{name}: expected exactly one tab'
    return hits[0]


def test_street_model_tab_wiring():
    tab = _tab('Street Model')
    sys.path.append(str(PROJECT_ROOT / 'tools' / 'street'))
    import street_pipeline
    accepted = set(inspect.signature(street_pipeline.main).parameters)
    declared = {p['key'] for p in tab['params']}
    assert declared <= accepted, declared - accepted
    assert callable(tab['target'])
    reqs = tab['requirements_fn']({})
    assert reqs and reqs[0]['pattern'] == 'config_*.npz'


def test_street_preview_tab_wiring():
    tab = _tab('Street Preview')
    assert tab['kind'] == 'street_preview'
    assert tab['params'] == []          # preview tabs own their widgets
    from gui import app
    module_name, class_name = app.PREVIEW_TABS['street_preview']
    assert (module_name, class_name) == ('gui.street_preview',
                                         'StreetPreviewTab')
    # The class must exist without instantiating it (no Tk in headless CI):
    # importing gui.street_preview pulls matplotlib's TkAgg backend, which
    # needs tkinter present but no display until a widget is created.
    import importlib
    mod = importlib.import_module(module_name)
    assert hasattr(mod, class_name)


def test_street_tabs_are_last():
    names = [t['name'] for t in specs.TABS]
    assert names[-2:] == ['Street Model', 'Street Preview']
