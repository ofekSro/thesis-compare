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
    checks  one checkbutton per ``options`` entry; value = ticked subset
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
             'extract_1d_peaks', 'validate_migration', 'config_curve',
             'street'):
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

def _npz_required(npz_dir=None):
    return {'path': npz_dir or paths.default_npz_dir(),
            'kind': 'glob', 'pattern': 'config_*.npz',
            'label': 'NPZ files',
            'hint': 'Build them on the Preprocess tab (writes the raw store '
                    'to data/raw_npz/), or copy an existing processed set '
                    'into data/processed_npz/ (see README).'}


def soft_npz_status(npz_dir=None):
    """(ok, reason) — can the soft criterion run? Import kept lazy so the
    launcher window never waits on numpy just to draw itself."""
    from blastlib.processing.soft_criterion import raw_fields_available
    return raw_fields_available(npz_dir)


def available_radius_methods():
    """Estimator tokens with a convergence table on disk, for the read-side
    dropdowns — hard and soft runs then display side by side, each from its
    own suffixed files. The builtin methods are always offered."""
    tokens = list(VALID_METHODS)
    prefix = 'convergence_table_'
    for csv in sorted(paths.TABLES_DIR.glob(f'{prefix}*.csv')):
        token = csv.stem[len(prefix):]
        if token and not token.startswith('SHIPPED') and token not in tokens:
            tokens.append(token)
    return tokens


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
# An editable combo over the tokens found on disk (req, p95, req_soft4, ...)
# so soft-criterion runs are selectable next to hard ones; Refresh rescans.
_RADIUS_METHOD_PARAM = {
    'key': 'radius_method', 'label': 'Radius estimator', 'kind': 'combo',
    'options_fn': available_radius_methods,
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
    """Analysis inputs depend on the chosen phase (and estimator, for phase 2).

    A soft-criterion estimator moves the NPZ requirement to the v2 superset
    folder (or wherever npz_dir points) and adds a raw-field key probe, so a
    soft run is stopped at preflight rather than dying mid-pipeline on NPZs
    that lack the raw band fields.
    """
    phase = values.get('phase', 'all')
    if phase == '2':
        m = _values_method(values)
        return [_table_required(paths.CONV_CSV.name, method=m),
                _table_required(paths.MAXR_CSV.name, method=m)]

    est = resolve_estimator(values.get('radius_estimator')
                            or values.get('radius_method'))
    if est.get('soft_beta') is None:
        return [_ff_required(), _npz_required(values.get('npz_dir'))]

    npz_dir = values.get('npz_dir') or paths.default_npz_dir(soft=True)
    return [_ff_required(), _npz_required(npz_dir),
            {'kind': 'check', 'label': 'soft criterion inputs',
             'fn': lambda: soft_npz_status(npz_dir)[1],
             'hint': 'Soft runs need the raw band fields: the raw store '
                     '(data/raw_npz, built on the Preprocess tab) produces '
                     'them at load time, and the v2 superset carries them on '
                     'disk. A v1 folder cannot serve them.'}]


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
            {'key': 'make_figures', 'label': 'Figures', 'kind': 'checks',
             'options': ['absolute', 'conv_theta', 'max_radius',
                         'ratio', 'theta_I', 'theta_P'],
             'default': True,
             'help': 'Which per-config figure sets phase 1 redraws — the '
                     'dominant runtime cost. Tables are identical either way.'},
            {'key': 'radius_estimator', 'label': 'Radius estimator',
             'kind': 'estimator', 'default': constants.RADIUS_ESTIMATOR,
             'soft_status_fn': soft_npz_status,
             'help': 'Collapses the 91 per-angle radii to one scalar. Drives '
                     'BOTH the convergence radius and MaxR; outputs are '
                     'suffixed with it (soft runs as e.g. req_soft4). Soft '
                     'reads the v2 NPZ superset.'},
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
        'blurb': 'Convert raw VTK triplets into .npz files. The default "raw" '
                 'store keeps only the solver fields and applies every '
                 'criterion at analysis time, so a threshold change is a '
                 're-run of Analysis rather than a rebuild from VTK '
                 '(and it is ~8x smaller).',
        'target': _call('run_preprocess'),
        'requirements_fn': lambda values: [
            {'path': values.get('vtk_dir') or paths.VTK_DIR,
             'kind': 'glob', 'pattern': 'config_*.vtk', 'label': 'VTK files',
             'hint': 'Point the VTK folder at all_vtks/, or copy '
                     'all_vtks/*.vtk into data/vtk/ (see README).'}],
        'params': [
            {'key': 'vtk_dir', 'label': 'VTK folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/vtk/'},
            {'key': 'store', 'label': 'Store format', 'kind': 'choice',
             'options': ['raw', 'processed'], 'default': 'raw',
             'help': 'raw = solver fields only, criteria applied when '
                     'Analysis runs (recommended); processed = legacy '
                     'layout with the criteria baked in'},
            {'key': 'npz_dir', 'label': 'NPZ output', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/raw_npz/ (or '
                                    'data/processed_npz/ for the legacy store)'},
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
            {'key': 'show_train', 'label': 'Show train configs', 'kind': 'choice',
             'options': ['no', 'yes'], 'default': 'no',
             'cast': lambda s: s == 'yes',
             'help': 'Draw the training (fit) configs in gray behind the '
                     'test points; metrics stay test-only.'},
            {'key': 'error_bands', 'label': 'Error lines %', 'kind': 'text',
             'default': '10',
             'help': "Comma-separated ± lines on the scatters, e.g. "
                     "10,15,20; 'none' removes them."},
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
        # 'kind' switches app.py to the live-preview tab class instead of the
        # standard run-and-log one: this figure is steered, not launched.
        'kind': 'preview',
        'name': 'Config Curve',
        'blurb': 'Peak pressure/impulse vs distance for one config, against '
                 'free field. Redraws as you change anything; nothing is '
                 'written until you press Save figure.',
        'requirements_fn': lambda values: [
            _table_required(paths.MAXR_CSV.name, method=_values_method(values)),
            _table_required(paths.CONV_CSV.name, method=_values_method(values)),
        ],
        'params': [],
    },
    {
        # Reads the NPZs directly and runs the estimator itself, so unlike the
        # other figure tabs it needs no table from phase 1 — only the same
        # inputs phase 1 consumes.
        'kind': 'ratio_preview',
        'name': 'Ratio Map',
        'blurb': 'P/P_ref and I/I_ref over the X–Z plane for one config, the '
                 'same figure phase 1 saves. Toggle the measured convergence '
                 'radius, change the colour scale and extent, and save only '
                 'when you want to.',
        'requirements_fn': lambda values: [_npz_required()],
        'params': [],
    },
    {
        # Pinned to the req table by the tool itself, so unlike the other
        # table-reading tabs its requirement does not follow an estimator
        # widget — there is no estimator control here to follow.
        'kind': 'matched_sets',
        'name': 'Matched Sets',
        'blurb': 'One variable at a time: every group of configs identical in '
                 'the other four factors, plotted as a line. Filter live to '
                 'see where the effect reverses. Reads convergence_table_req '
                 'only; measured data, no fitted models.',
        'requirements_fn': lambda values: [
            _table_required(paths.CONV_CSV.name, method='req')],
        'params': [],
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
        'blurb': 'Compare four radius definitions: max / p95 / equivalent area '
                 '(hard criterion) / equivalent area under the soft criterion '
                 '(beta). All configs go into the CSVs; the 2x2 figures '
                 '(PNG + PDF) are drawn for the chosen one.',
        'target': _positional_call('radius_methods', 'config_name'),
        'requirements': [_npz_required()],
        'params': [
            {'key': 'config_name', 'label': 'Config (for figures)', 'kind': 'combo',
             'options_fn': radius_method_configs, 'default': '',
             'help': 'Refresh re-reads the NPZ folder'},
            {'key': 'soft_beta', 'label': 'Soft beta (panel d)', 'kind': 'float',
             'default': constants.PARAMS['softBeta'],
             'help': 'tanh sharpness of the soft pressure criterion; '
                     '0 = omit the soft panel. Needs the raw store / v2 NPZs.'},
            {'key': 'npz_dir', 'label': 'NPZ folder', 'kind': 'path', 'browse': 'dir',
             'default': '', 'help': 'blank = data/raw_npz/ (falls back to v2/v1)'},
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
    {
        'name': 'Street Model',
        'blurb': 'Street-channelling E(r): measure the strip anchors on all '
                 '96 configs, refit the master curve, validate the '
                 'closed-form model on the 88 channelling configs, and draw '
                 'the figure sets. Stages run alone or as the full chain.',
        'target': _call('street_pipeline'),
        'requirements_fn': lambda values: [
            _npz_required(values.get('npz_dir')
                          or paths.default_npz_dir(soft=True))],
        'params': [
            {'key': 'stage', 'label': 'Stage', 'kind': 'choice',
             'options': ['all', 'anchors', 'fit', 'validate', 'figures'],
             'default': 'all',
             'help': 'anchors -> fit -> validate -> figures; all = the chain'},
            {'key': 'npz_dir', 'label': 'NPZ folder', 'kind': 'path',
             'browse': 'dir', 'default': '',
             'help': 'blank = the default store (raw preferred)'},
            {'key': 'dr', 'label': 'Slice width [m]', 'kind': 'float',
             'default': 0.5, 'advanced': True,
             'help': 'Non-default widths go to suffixed filenames and '
                     'disable the 2.5 m smoothing at dr >= 1 (measured '
                     'kernel quirk) — stability runs only.'},
            {'key': 'hi_frac', 'label': 'Decay window: high', 'kind': 'float',
             'default': 0.85, 'advanced': True,
             'help': 'Fit starts below this fraction of the peak excess.'},
            {'key': 'lo_frac', 'label': 'Decay window: low', 'kind': 'float',
             'default': 0.25, 'advanced': True,
             'help': 'Fit ends below this fraction (or the E=1.2 floor).'},
            {'key': 'anchors_csv', 'label': 'Anchors CSV', 'kind': 'path',
             'browse': 'file', 'default': '', 'advanced': True,
             'help': 'blank = outputs/check_results/street_anchors.csv '
                     '(as written by the anchors stage)'},
            {'key': 'out_dir', 'label': 'Figure folder', 'kind': 'path',
             'browse': 'dir', 'default': '', 'advanced': True,
             'help': 'blank = outputs/figures/e_profile/'},
        ],
    },
    {
        # Live tab (see gui/street_preview.py): draws through the same
        # blastlib.street.figures.draw_profile as the batch PNGs, so the
        # interactive view can never drift from the published figure.
        'kind': 'street_preview',
        'name': 'Street Preview',
        'blurb': 'The street-channelling profile E(r) for one config or free '
                 'geometry, predicted vs measured, redrawn live. Nothing is '
                 'written until you press Save figure.',
        'requirements_fn': lambda values: [
            _npz_required(paths.default_npz_dir(soft=True))],
        'params': [],
    },
]

ADVANCED_WARNING = (
    'These were held fixed during baseline validation. Changing them makes '
    'results non-comparable with the compare_v6 baseline and with each other.'
)
