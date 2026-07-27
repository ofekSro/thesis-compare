"""Declarative description of every GUI tab.

No tkinter and no pipeline logic here — just data describing which callable a
tab runs, which parameters it exposes, and which inputs must exist first.
Adding or exposing a parameter should only require editing this file.

Parameter kinds understood by widgets.py:
    text    free text entry
    int     integer entry
    float   float entry
    choice  combobox over ``options``
    path    text entry + Browse button (``browse`` = 'dir' | 'file')
    combo   editable combobox filled at runtime by ``options_fn``
    scale     the auto/manual colour-scale group (4 limit fields)
    estimator the radius-estimator radio group + percentile spinbox

``advanced=True`` puts a parameter in the collapsed Advanced section.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Tool modules live in their own folders; make them importable by name.
for _sub in ('check_formulas', 'formulas_printer', 'pi_effects', 'radius_methods',
             'regime_graphs', 'z_surface_3d', 'view_3d', 'migrate_vtks',
             'extract_1d_peaks', 'validate_migration'):
    _p = str(PROJECT_ROOT / 'tools' / _sub)
    if _p not in sys.path:
        sys.path.append(_p)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from blastlib import constants, paths  # noqa: E402
from blastlib.processing.radius_estimator import (  # noqa: E402
    VALID_METHODS, resolve_estimator)


# --------------------------------------------------------------------------
# Requirement helpers
# --------------------------------------------------------------------------

def _npz_required():
    return {'path': paths.PROCESSED_NPZ_DIR, 'kind': 'glob', 'pattern': 'config_*.npz',
            'label': 'processed NPZ files',
            'hint': 'Copy MAT_files/config_*.npz into data/processed_npz/ (see README).'}


def _ff_required():
    return {'path': paths.FF_CSV, 'kind': 'file', 'label': 'free_field_data.csv',
            'hint': 'Copy free_field_data.csv into data/ (see README).'}


def _table_required(name, hint='Run the Analysis tab (phase 1) first.', method=None):
    """Require a table, honouring the radius-estimator filename suffix."""
    fname = paths.suffixed(name, method)
    return {'path': paths.TABLES_DIR / fname, 'kind': 'file', 'label': fname,
            'hint': hint}


def _values_method(values):
    """Radius-estimator token implied by a tab's current widget values."""
    return resolve_estimator(values.get('radius_estimator')
                             or values.get('radius_method'))['method']


_COEF_HINT = 'Run the Analysis tab (phase 2) first.'

# Reusable spec entry for tools that read the estimator-suffixed tables.
_RADIUS_METHOD_PARAM = {
    'key': 'radius_method', 'label': 'Radius estimator', 'kind': 'choice',
    'options': list(VALID_METHODS),
    'default': constants.RADIUS_ESTIMATOR['method'],
    'help': 'Which Analysis run to read (output files are suffixed with it).',
}


def _coef_requirements(values):
    m = _values_method(values)
    return [_table_required('best_convergence_coefficients.csv', _COEF_HINT, m),
            _table_required('best_z_urban_coefficients.csv', _COEF_HINT, m)]


def _conv_table_requirements(values):
    return [_table_required(paths.CONV_CSV.name, method=_values_method(values))]


# --------------------------------------------------------------------------
# Lazy imports — a missing optional dependency must not break the whole GUI
# --------------------------------------------------------------------------

def _call(module_name, attr='main'):
    """Return a callable that imports on first use and forwards its arguments."""
    def invoke(**kwargs):
        module = __import__(module_name)
        return getattr(module, attr)(**kwargs)
    return invoke


def _positional_call(module_name, *positional_names, attr='main'):
    """Like _call, but sends the named parameters positionally."""
    def invoke(**kwargs):
        module = __import__(module_name)
        args = [kwargs.pop(name) for name in positional_names]
        return getattr(module, attr)(*args, **kwargs)
    return invoke


def radius_method_configs():
    """Config names for the radius-methods dropdown (empty if data is absent)."""
    try:
        import radius_methods
        return radius_methods.list_configs()
    except Exception:
        return []


def analysis_requirements(values):
    """Analysis inputs depend on the chosen phase (and estimator, for phase 2)."""
    phase = values.get('phase', 'all')
    if phase == '2':
        m = _values_method(values)
        return [_table_required(paths.CONV_CSV.name, method=m),
                _table_required(paths.MAXR_CSV.name, method=m)]
    return [_ff_required(), _npz_required()]


# --------------------------------------------------------------------------
# Tab definitions
# --------------------------------------------------------------------------

TABS = [
    {
        'name': 'Analysis',
        'blurb': 'Main pipeline: phase 1 builds the tables from NPZ, '
                 'phase 2 runs the cross-validated regression.',
        'target': _call('run_analysis'),
        'requirements_fn': analysis_requirements,
        'params': [
            {'key': 'phase', 'label': 'Phase', 'kind': 'choice',
             'options': ['all', '1', '2'], 'default': 'all',
             'help': 'all = phase 1 then 2'},
            {'key': 'n_iterations', 'label': 'CV iterations', 'kind': 'int',
             'default': 500,
             'help': 'Passed as n_splits — changing it changes every split, '
                     'so runs are only comparable at equal values.'},
            {'key': 'scale_limits', 'label': 'Ratio colour scale', 'kind': 'scale',
             'default': None},
            {'key': 'radius_estimator', 'label': 'Radius estimator',
             'kind': 'estimator', 'default': constants.RADIUS_ESTIMATOR,
             'help': 'Collapses the 91 per-angle radii to one scalar. Drives '
                     'BOTH the convergence radius and MaxR; outputs are '
                     'suffixed with it.'},
            {'key': 'npz_dir', 'label': 'NPZ folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/processed_npz/'},
            {'key': 'ff_csv', 'label': 'Free-field CSV', 'kind': 'path', 'browse': 'file',
             'default': '', 'help': 'blank = data/free_field_data.csv'},
            {'key': 'tables_dir', 'label': 'Tables output', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = outputs/tables/'},
            {'key': 'figures_dir', 'label': 'Figures output', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = outputs/figures/'},
            {'key': 'test_fraction', 'label': 'Test fraction', 'kind': 'float',
             'default': 0.2, 'advanced': True},
            {'key': 'target_mape', 'label': 'Target MAPE %', 'kind': 'float',
             'default': 10.0, 'advanced': True},
        ],
    },
    {
        'name': 'Preprocess',
        'blurb': 'Convert raw VTK triplets into processed .npz files.',
        'target': _call('run_preprocess'),
        'requirements': [{'path': paths.VTK_DIR, 'kind': 'glob', 'pattern': 'config_*.vtk',
                          'label': 'VTK files',
                          'hint': 'Copy all_vtks/*.vtk into data/vtk/ (see README).'}],
        'params': [
            {'key': 'vtk_dir', 'label': 'VTK folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/vtk/'},
            {'key': 'npz_dir', 'label': 'NPZ output', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/processed_npz/'},
        ],
    },
    {
        'name': 'Preprocess OBS',
        'blurb': 'Convert obstacle-surface VTKs into .npz files (used by the 3D viewer).',
        'target': _call('run_preprocess_obs'),
        'requirements': [{'path': paths.OBS_VTK_DIR, 'kind': 'glob', 'pattern': 'config_*.vtk',
                          'label': 'OBS VTK files',
                          'hint': 'Copy all_vtks/OBS/*.vtk into data/vtk/OBS/ (see README).'}],
        'params': [
            {'key': 'obs_vtk_dir', 'label': 'OBS VTK folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/vtk/OBS/'},
            {'key': 'obs_npz_dir', 'label': 'OBS NPZ output', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/obs_npz/'},
        ],
    },
    {
        'name': 'Check Formulas',
        'blurb': 'Validate the saved coefficients against the best CV test split.',
        'target': _call('check_formulas'),
        'requirements_fn': lambda values: _coef_requirements(values) + [
            _table_required('best_test_configs.csv', _COEF_HINT,
                            _values_method(values)),
            _table_required(paths.CONV_CSV.name, method=_values_method(values)),
            _table_required(paths.MAXR_CSV.name, method=_values_method(values)),
        ],
        'params': [
            dict(_RADIUS_METHOD_PARAM),
            {'key': 'tables_dir', 'label': 'Tables folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = outputs/tables/'},
            {'key': 'out_dir', 'label': 'Output folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = outputs/check_results/'},
        ],
    },
    {
        'name': 'Formulas',
        'blurb': 'Print the fitted convergence and Z_urban formulas.',
        'target': _call('formulas_printer'),
        'requirements_fn': _coef_requirements,
        'params': [
            dict(_RADIUS_METHOD_PARAM),
            {'key': 'tables_dir', 'label': 'Tables folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = outputs/tables/'},
        ],
    },
    {
        'name': 'Pi Effects',
        'blurb': 'Diagnostic plots of R and Z against each Pi group.',
        'target': _call('pi_effects'),
        'requirements_fn': _conv_table_requirements,
        'params': [
            dict(_RADIUS_METHOD_PARAM),
            {'key': 'conv_csv', 'label': 'Convergence CSV', 'kind': 'path', 'browse': 'file',
             'default': '',
             'help': 'blank = the convergence table for the estimator above'},
            {'key': 'out_dir', 'label': 'Output folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = outputs/figures/pi_effects/<method>/'},
        ],
    },
    {
        'name': 'Regime Graphs',
        'blurb': 'The two thesis figures on the height-effect sign flip.',
        'target': _call('regime_graphs'),
        'requirements_fn': _conv_table_requirements,
        'params': [
            dict(_RADIUS_METHOD_PARAM),
            {'key': 'conv_csv', 'label': 'Convergence CSV', 'kind': 'path', 'browse': 'file',
             'default': '',
             'help': 'blank = the convergence table for the estimator above'},
            {'key': 'out_dir', 'label': 'Output folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = outputs/figures/regime_graphs/<method>/'},
        ],
    },
    {
        'name': 'Radius Methods',
        'blurb': 'Compare max / p95 / equivalent-area radius definitions. '
                 'All configs go into the CSVs; figures are drawn for the chosen one.',
        'target': _positional_call('radius_methods', 'config_name'),
        'requirements': [_npz_required()],
        'params': [
            {'key': 'config_name', 'label': 'Config (for figures)', 'kind': 'combo',
             'options_fn': radius_method_configs, 'default': '',
             'help': 'Refresh re-reads the NPZ folder'},
            {'key': 'npz_dir', 'label': 'NPZ folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/processed_npz/'},
            {'key': 'out_dir', 'label': 'Output folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = outputs/figures/radius_methods/'},
        ],
    },
    {
        'name': 'Z Surface 3D',
        'blurb': 'Surface of Z_P over two Pi groups with the third fixed. '
                 'Uses hardcoded production coefficients (see the tool docstring).',
        'target': _positional_call('z_surface_3d', 'fix', 'value', 'det'),
        'main_thread': True,   # matplotlib 3-D rendering
        'params': [
            {'key': 'fix', 'label': 'Fix variable', 'kind': 'choice',
             'options': ['pi2', 'rho', 'hs'], 'default': 'rho'},
            {'key': 'value', 'label': 'Fixed value', 'kind': 'float', 'default': 0.56,
             'help': 'pi2 ~0.4-4.0, rho 0.18-0.74, hs 0.2-4.8'},
            {'key': 'det', 'label': 'Detonation', 'kind': 'choice',
             'options': ['1', '2'], 'default': '1', 'cast': int,
             'help': '1 = street, 2 = intersection'},
            {'key': 'out_dir', 'label': 'Output folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = outputs/figures/z_surface/'},
        ],
    },
    {
        'name': '3D Viewer',
        'blurb': 'Interactive pyvista viewer. Leave the config blank to use the '
                 'picker dialog. Requires the optional pyvista dependency.',
        'target': _positional_call('view_3d', 'config_name'),
        'main_thread': True,   # pyvista owns the main loop
        'optional_import': 'pyvista',
        'requirements': [_npz_required()],
        'params': [
            {'key': 'config_name', 'label': 'Config (blank = picker)', 'kind': 'combo',
             'options_fn': radius_method_configs, 'default': '', 'empty_is_none': True},
            {'key': 'npz_dir', 'label': 'NPZ folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/processed_npz/'},
            {'key': 'obs_npz_dir', 'label': 'OBS NPZ folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/obs_npz/'},
        ],
    },
    {
        'name': 'Extract 1D Peaks',
        'blurb': 'Peak pressure and impulse from the viper1d 1-D runs.',
        'target': _call('extract_1d_peaks'),
        'requirements': [{'path': paths.VIPER1D_DIR, 'kind': 'glob',
                          'pattern': 'viper1d_th_*.txt', 'label': 'viper1d text files',
                          'hint': 'Copy 1ds/viper1d_th_*.txt into data/viper1d/.'}],
        'params': [
            {'key': 'input_dir', 'label': 'viper1d folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/viper1d/'},
            {'key': 'out_csv', 'label': 'Output CSV', 'kind': 'path', 'browse': 'file',
             'default': '', 'help': 'blank = outputs/tables/1d_peaks.csv'},
        ],
    },
    {
        'name': 'Migrate VTKs',
        'blurb': 'One-time import of raw VTKs from a REFERENCES folder '
                 '(expects VTKS/ and VALIDATION_VTKS/ inside it).',
        'target': _positional_call('migrate_vtks', 'references_dir'),
        'params': [
            {'key': 'references_dir', 'label': 'REFERENCES folder', 'kind': 'path',
             'browse': 'dir', 'default': '', 'required': True,
             'help': 'Must contain VTKS/ and optionally VALIDATION_VTKS/'},
            {'key': 'dest_dir', 'label': 'Destination', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/vtk/'},
        ],
    },
    {
        'name': 'Validate',
        'blurb': 'Compare this project\'s outputs against the original compare_v6 '
                 'baseline. Requires a completed analysis run.',
        'target': _positional_call('compare_outputs', 'old_root'),
        'params': [
            {'key': 'old_root', 'label': 'compare_v6 folder', 'kind': 'path',
             'browse': 'dir', 'required': True,
             'default': str(PROJECT_ROOT.parent / 'compare_v6')},
            {'key': 'new_root', 'label': 'New project root', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = this project'},
            {'key': 'rtol', 'label': 'Relative tolerance', 'kind': 'float',
             'default': 1e-9, 'advanced': True},
            {'key': 'atol', 'label': 'Absolute tolerance', 'kind': 'float',
             'default': 1e-12, 'advanced': True},
        ],
    },
]

ADVANCED_WARNING = (
    'These were held fixed during baseline validation. Changing them makes '
    'results non-comparable with the compare_v6 baseline and with each other.'
)
