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
