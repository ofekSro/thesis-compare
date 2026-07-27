"""Verify that compare_v7 reproduces the original compare_v6 outputs exactly.

Compares every result CSV numerically (and figure folders by file count),
mapping the old flat layout onto the new outputs/ tree.

The pipeline is deterministic: the only randomness is
StratifiedShuffleSplit(random_state=42) in the cross-validation, and all
fits are OLS. Given the same inputs and the same n_iterations, results must
match. NOTE n_iterations is passed as n_splits, so the comparison run MUST
use the same value as the original run (500 for the shipped outputs).

Usage:
    python tools\\validate_migration\\compare_outputs.py "<path to compare_v6>"
    python tools\\validate_migration\\compare_outputs.py "<old>" --new-root "<compare_v7>"

Exit code 0 = all comparisons passed, 1 = at least one failed.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import numpy as np
import pandas as pd

from blastlib import paths

# compare_v6 predates the configurable radius estimator: it always used Req for
# the convergence radius and p95 for MaxR, and wrote unsuffixed filenames. Only
# the NEW side carries the estimator suffix, so the baseline files are found
# unchanged. The comparison is meaningful for the estimator that reproduces the
# old behaviour ('req'); other methods will differ by design.
BASELINE_METHOD = 'req'

# old relative name (under compare_v6)  ->  new relative name (under compare_v7)
CSV_MAP = {
    'convergence_table.csv':                          'outputs/tables/convergence_table.csv',
    'max_radius_per_Z.csv':                           'outputs/tables/max_radius_per_Z.csv',
    'theta_radius_P.csv':                             'outputs/tables/theta_radius_P.csv',
    'theta_radius_I.csv':                             'outputs/tables/theta_radius_I.csv',
    'cv_summary.csv':                                 'outputs/tables/cv_summary.csv',
    'best_test_configs.csv':                          'outputs/tables/best_test_configs.csv',
    'best_convergence_coefficients.csv':              'outputs/tables/best_convergence_coefficients.csv',
    'best_z_urban_coefficients.csv':                  'outputs/tables/best_z_urban_coefficients.csv',
    'final_production_convergence_coefficients.csv':  'outputs/tables/final_production_convergence_coefficients.csv',
    'final_production_z_urban_coefficients.csv':      'outputs/tables/final_production_z_urban_coefficients.csv',
    'check_results/validation_comparison.csv':        'outputs/check_results/validation_comparison.csv',
}

# Columns added after the compare_v6 baseline was captured. Dropped from the new
# side before comparing so the numeric comparison stays like-for-like.
NEW_ONLY_COLUMNS = ('RadiusEstimator', 'beyond_P', 'beyond_I')

# old figure folder -> new figure folder (compared by PNG count only).
# Phase-1 figures now live under a per-estimator subfolder.
FIG_MAP = {
    'Figures':                'outputs/figures/{method}/absolute',
    'Figures_Ratio':          'outputs/figures/{method}/ratio',
    'Figures_MaxR':           'outputs/figures/{method}/max_radius',
    'Figures_MaxR_Theta_P':   'outputs/figures/{method}/theta_P',
    'Figures_MaxR_Theta_I':   'outputs/figures/{method}/theta_I',
    'Figures_Conv_Theta':     'outputs/figures/{method}/conv_theta',
}


def compare_csv(old_path, new_path, rtol=1e-9, atol=1e-12):
    """Compare two CSVs. Returns (status, detail).

    status is 'PASS', 'FAIL', or 'SKIP' (when neither file exists).
    Numeric columns must match within tolerance with identical NaN positions;
    non-numeric columns must match exactly.
    """
    old_exists, new_exists = old_path.exists(), new_path.exists()
    if not old_exists and not new_exists:
        return 'SKIP', 'absent on both sides'
    if not old_exists:
        return 'SKIP', f'no baseline ({old_path.name} missing in old tree)'
    if not new_exists:
        return 'FAIL', f'missing in new tree: {new_path}'

    old_df = pd.read_csv(old_path)
    new_df = pd.read_csv(new_path)

    # Columns that did not exist when the baseline was captured are provenance
    # and bookkeeping, not results — drop them rather than fail on shape.
    new_df = new_df.drop(columns=[c for c in NEW_ONLY_COLUMNS
                                  if c in new_df.columns and c not in old_df.columns])

    if old_df.shape != new_df.shape:
        return 'FAIL', f'shape {old_df.shape} vs {new_df.shape}'
    if list(old_df.columns) != list(new_df.columns):
        return 'FAIL', 'column names/order differ'

    worst_abs = 0.0
    worst_rel = 0.0
    for col in old_df.columns:
        o, n = old_df[col], new_df[col]
        if pd.api.types.is_numeric_dtype(o) and pd.api.types.is_numeric_dtype(n):
            o_v, n_v = o.to_numpy(dtype=float), n.to_numpy(dtype=float)
            o_nan, n_nan = np.isnan(o_v), np.isnan(n_v)
            if not np.array_equal(o_nan, n_nan):
                bad = int(np.sum(o_nan != n_nan))
                return 'FAIL', f'column {col!r}: NaN pattern differs in {bad} row(s)'
            valid = ~o_nan
            if valid.any():
                diff = np.abs(o_v[valid] - n_v[valid])
                denom = np.maximum(np.abs(o_v[valid]), 1e-300)
                worst_abs = max(worst_abs, float(diff.max()))
                worst_rel = max(worst_rel, float((diff / denom).max()))
                if not np.allclose(o_v[valid], n_v[valid], rtol=rtol, atol=atol):
                    idx = int(np.argmax(diff))
                    return 'FAIL', (f'column {col!r}: max|Δ|={diff.max():.3e} '
                                    f'(old={o_v[valid][idx]!r}, new={n_v[valid][idx]!r})')
        else:
            if not o.astype(str).equals(n.astype(str)):
                mism = int((o.astype(str) != n.astype(str)).sum())
                return 'FAIL', f'column {col!r}: {mism} string value(s) differ'

    return 'PASS', (f'{old_df.shape[0]} rows, max|Δ|={worst_abs:.2e}, '
                    f'max rel={worst_rel:.2e}')


def compare_figures(old_dir, new_dir):
    """Compare two figure folders by PNG count and non-zero size.

    Pixel comparison is deliberately out of scope: matplotlib output varies
    with version/backend and figure identity is not a correctness criterion.
    """
    if not old_dir.exists() and not new_dir.exists():
        return 'SKIP', 'absent on both sides'
    if not old_dir.exists():
        return 'SKIP', f'no baseline ({old_dir.name} missing in old tree)'
    if not new_dir.exists():
        return 'FAIL', f'missing in new tree: {new_dir}'

    old_pngs = sorted(p.name for p in old_dir.glob('*.png'))
    new_pngs = sorted(p.name for p in new_dir.glob('*.png'))

    if len(old_pngs) != len(new_pngs):
        return 'FAIL', f'{len(old_pngs)} PNGs vs {len(new_pngs)}'

    missing = set(old_pngs) - set(new_pngs)
    if missing:
        sample = ', '.join(sorted(missing)[:3])
        return 'FAIL', f'{len(missing)} filename(s) missing, e.g. {sample}'

    empty = [p.name for p in new_dir.glob('*.png') if p.stat().st_size == 0]
    if empty:
        return 'FAIL', f'{len(empty)} empty PNG(s), e.g. {empty[0]}'

    return 'PASS', f'{len(new_pngs)} PNGs, names match, all non-empty'


def main(old_root, new_root=None, *, rtol=1e-9, atol=1e-12,
         radius_method=BASELINE_METHOD, progress=print):
    """Compare old vs new outputs. Returns True if everything passed.

    *radius_method* selects which estimator's outputs to compare on the new
    side; the baseline side is always unsuffixed. Only BASELINE_METHOD is
    expected to match — other estimators change the numbers by design.
    """
    old_root = Path(old_root)
    new_root = Path(new_root) if new_root is not None else paths.PROJECT_ROOT
    method = radius_method or BASELINE_METHOD

    progress('=' * 78)
    progress('  MIGRATION VALIDATION — compare_v6 (baseline) vs compare_v7 (new)')
    progress('=' * 78)
    progress(f'  old: {old_root}')
    progress(f'  new: {new_root}')
    progress(f'  tolerance: rtol={rtol:g}, atol={atol:g}')
    progress(f'  radius estimator (new side): {method}')
    if method != BASELINE_METHOD:
        progress(f'  NOTE: the baseline used {BASELINE_METHOD}; numeric '
                 'differences below are expected, not regressions.')
    progress('')

    if not old_root.is_dir():
        progress(f'ERROR: baseline folder not found: {old_root}')
        return False

    n_pass = n_fail = n_skip = 0

    progress('-' * 78)
    progress('  CSV TABLES')
    progress('-' * 78)
    for old_rel, new_rel in CSV_MAP.items():
        new_p = Path(new_rel)
        new_p = new_p.with_name(paths.suffixed(new_p.name, method))
        status, detail = compare_csv(old_root / old_rel, new_root / new_p,
                                     rtol=rtol, atol=atol)
        progress(f'  [{status}] {old_rel:<48s} {detail}')
        n_pass += status == 'PASS'
        n_fail += status == 'FAIL'
        n_skip += status == 'SKIP'

    progress('')
    progress('-' * 78)
    progress('  FIGURE FOLDERS (count + names only)')
    progress('-' * 78)
    for old_rel, new_rel in FIG_MAP.items():
        status, detail = compare_figures(old_root / old_rel,
                                         new_root / new_rel.format(method=method))
        progress(f'  [{status}] {old_rel:<48s} {detail}')
        n_pass += status == 'PASS'
        n_fail += status == 'FAIL'
        n_skip += status == 'SKIP'

    progress('')
    progress('=' * 78)
    progress(f'  RESULT: {n_pass} passed, {n_fail} failed, {n_skip} skipped')
    if n_fail == 0:
        progress('  ALL COMPARISONS PASSED — the new pipeline reproduces the original.')
    else:
        progress('  FAILURES PRESENT — inspect the rows marked [FAIL] above.')
        progress('  If only Phase-2 outputs differ, check that the run used the same')
        progress('  --n-iter as the baseline (500) and the same library versions.')
    progress('=' * 78)

    return n_fail == 0


def cli(argv=None):
    p = argparse.ArgumentParser(
        description='Validate that compare_v7 reproduces compare_v6 outputs.')
    p.add_argument('old_root', help='Path to the original compare_v6 folder.')
    p.add_argument('--new-root', default=None,
                   help='Path to the new project root (default: this project).')
    p.add_argument('--rtol', type=float, default=1e-9, help='Relative tolerance.')
    p.add_argument('--atol', type=float, default=1e-12, help='Absolute tolerance.')
    p.add_argument('--radius-method', default=BASELINE_METHOD, dest='radius_method',
                   help=f'Radius estimator to compare on the new side '
                        f'(default {BASELINE_METHOD}, which reproduces the baseline).')
    args = p.parse_args(argv)

    ok = main(args.old_root, args.new_root, rtol=args.rtol, atol=args.atol,
              radius_method=args.radius_method)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(cli())
