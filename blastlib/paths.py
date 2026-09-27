"""Single source of truth for every directory and well-known file path.

All entry points take optional dir arguments defaulting to None; None resolves
to the constants below, so the whole project can be relocated or redirected
(e.g. by a GUI) without touching any other module. Nothing in blastlib ever
relies on the current working directory.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ---- Inputs ----
DATA_DIR          = PROJECT_ROOT / 'data'
PROCESSED_NPZ_DIR = DATA_DIR / 'processed_npz'   # config_*.npz (was MAT_files/)
# v2 superset: same files plus the raw convergence-band fields the soft
# criterion needs (peakP*_raw, refP*, refI*, ratio*_raw). Regenerated from
# the raw VTKs by run_preprocess.py; the soft pipeline defaults to it.
PROCESSED_NPZ_V2_DIR = DATA_DIR / 'processed_npz_v2'
# v3 raw store: the solver's own fields only, no criterion applied — the
# criteria move to analysis time (see blastlib/io/raw_store.py). This is the
# format run_preprocess.py writes by default; it is what lets a threshold,
# band or projection change be re-run without touching the VTKs.
RAW_NPZ_DIR       = DATA_DIR / 'raw_npz'
OBS_NPZ_DIR       = DATA_DIR / 'obs_npz'         # OBS surface npz (was OBS_MAT_files/)
VTK_DIR           = DATA_DIR / 'vtk'             # raw VTKs (was all_vtks/)
OBS_VTK_DIR       = VTK_DIR / 'OBS'
VIPER1D_DIR       = DATA_DIR / 'viper1d'         # viper1d_th_*.txt (was 1ds/)
FF_CSV            = DATA_DIR / 'free_field_data.csv'

# ---- Outputs ----
OUTPUTS_DIR       = PROJECT_ROOT / 'outputs'
TABLES_DIR        = OUTPUTS_DIR / 'tables'
FIGURES_DIR       = OUTPUTS_DIR / 'figures'
CHECK_RESULTS_DIR = OUTPUTS_DIR / 'check_results'

# Well-known table files (unsuffixed base names — see suffixed() below)
CONV_CSV = TABLES_DIR / 'convergence_table.csv'
MAXR_CSV = TABLES_DIR / 'max_radius_per_Z.csv'


def has_configs(directory):
    """True if *directory* holds at least one config_*.npz."""
    d = Path(directory)
    return d.is_dir() and any(d.glob('config_*.npz'))


def default_npz_dir(soft=False):
    """The NPZ folder a run should read when none was given.

    The v3 raw store is preferred whenever it exists: it serves the hard and
    the soft criterion equally (both are applied at load time), so there is
    no reason to keep steering soft runs at the v2 superset. Falls back to
    the historical split — v2 for soft, v1 for hard — on installations that
    still only have the processed stores.
    """
    if has_configs(RAW_NPZ_DIR):
        return RAW_NPZ_DIR
    return PROCESSED_NPZ_V2_DIR if soft else PROCESSED_NPZ_DIR


def suffixed(name, method):
    """Append a radius-estimator token to a filename's stem.

    ('convergence_table.csv', 'p95') -> 'convergence_table_p95.csv'

    Runs using different radius estimators produce genuinely different numbers,
    so their outputs must not overwrite each other. *method* of None returns
    the name unchanged (for callers that predate the estimator setting).
    """
    if not method:
        return name
    p = Path(name)
    return str(p.with_name(f'{p.stem}_{method}{p.suffix}'))


def table(name, method=None, tables_dir=None):
    """Full path to a suffixed table file inside *tables_dir* (or the default)."""
    return resolve(tables_dir, TABLES_DIR) / suffixed(name, method)


def conv_csv(method=None, tables_dir=None):
    """Path to convergence_table[_<method>].csv."""
    return table(CONV_CSV.name, method, tables_dir)


def maxr_csv(method=None, tables_dir=None):
    """Path to max_radius_per_Z[_<method>].csv."""
    return table(MAXR_CSV.name, method, tables_dir)


def fig_dir(name):
    """Return (and create) a named subdirectory of outputs/figures/."""
    d = FIGURES_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_dir(path):
    """Create *path* (and parents) if missing; return it as a Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve(value, default):
    """Return Path(value) if value is not None, else the default Path."""
    return Path(value) if value is not None else Path(default)
