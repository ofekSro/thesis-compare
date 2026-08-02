"""Leave-one-geometry-out (LOGO) cross-validation for the convergence models.

Protocol (docs/PYSR_CONVERGENCE_SEARCH.md): folds are the (Det, b, s, H)
families — 18 per det, 36 total. Per fold, both det groups are refit on the
remaining configs with the real pipeline fitters and the held-out family is
predicted out-of-fold. Error is 100*|pred - actual| / actual on R (identical
to the error on Z = R / W^(1/3)).

Baseline gate (legacy models on the req table): P mean 8.39 / max 43.35,
I mean 8.55 / max 38.48.

Usage:
    python tools\\logo_cv\\logo_cv.py --radius-method req
    python tools\\logo_cv\\logo_cv.py --radius-method req --model-p relwls --model-i quad
    python tools\\logo_cv\\logo_cv.py --table path\\to\\table.csv --tag mytag
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import numpy as np
import pandas as pd

from blastlib import paths
from blastlib.regression.convergence_models import (
    fit_pi_all_groups, fit_impulse_all_groups, predict_pi, predict_impulse)

GROUP_COLS = ['Det', 'BuildingSize', 'StreetWidth', 'Height']

MODEL_P_CHOICES = ('legacy', 'relwls')
MODEL_I_CHOICES = ('legacy', 'quad')


def _make_fitters(model_p, model_i):
    """Fit callables for the requested variants.

    'legacy' calls the fitters with no extra kwargs, so this harness runs
    unchanged against a checkout that predates the variant kwargs.
    """
    if model_p == 'legacy':
        fit_p = lambda df: fit_pi_all_groups(df, 'RadiusP')
    else:
        fit_p = lambda df: fit_pi_all_groups(df, 'RadiusP', weighting='relative')
    if model_i == 'legacy':
        fit_i = lambda df: fit_impulse_all_groups(df, 'RadiusI')
    else:
        fit_i = lambda df: fit_impulse_all_groups(df, 'RadiusI', model='quad')
    return fit_p, fit_i


def run_logo(conv_df, model_p='legacy', model_i='legacy', progress=print):
    """Run LOGO CV over the convergence table. Returns per-config rows df."""
    fit_p, fit_i = _make_fitters(model_p, model_i)
    families = conv_df[GROUP_COLS].drop_duplicates().itertuples(index=False)

    rows = []
    for fam in families:
        fam_mask = np.ones(len(conv_df), dtype=bool)
        for col, val in zip(GROUP_COLS, fam):
            fam_mask &= conv_df[col].values == val
        train = conv_df[~fam_mask]
        test = conv_df[fam_mask]

        p_coeffs = fit_p(train)
        i_coeffs = fit_i(train)

        args = (test['ChargeWeight'].values, test['AreaDensity'].values,
                test['Height'].values, test['Det'].values,
                test['StreetWidth'].values, test['BuildingSize'].values)
        pred_p = predict_pi(*args, p_coeffs)
        pred_i = predict_impulse(*args, i_coeffs)

        fam_label = 'det{}_b{}_s{}_h{}'.format(*fam)
        for cfg, det, act, pred, target in zip(
                np.tile(test['ConfigName'].values, 2),
                np.tile(test['Det'].values, 2),
                np.concatenate([test['RadiusP'].values, test['RadiusI'].values]),
                np.concatenate([pred_p, pred_i]),
                ['P'] * len(test) + ['I'] * len(test)):
            err = 100.0 * abs(pred - act) / abs(act) if np.isfinite(pred) else np.nan
            rows.append({'Config': cfg, 'Det': int(det), 'Family': fam_label,
                         'Target': target, 'Actual': act, 'Predicted': pred,
                         'ErrPct': err})
    return pd.DataFrame(rows)


def summarize(err_df):
    """Pooled + per-det mean/median/p90/max rows per target."""
    out = []
    for target in ('P', 'I'):
        sub_t = err_df[err_df['Target'] == target]
        for scope, sub in [('pooled', sub_t),
                           ('det1', sub_t[sub_t['Det'] == 1]),
                           ('det2', sub_t[sub_t['Det'] == 2])]:
            errs = sub['ErrPct'].values
            finite = errs[np.isfinite(errs)]
            out.append({
                'Target': target, 'Scope': scope,
                'N': len(errs), 'N_finite': len(finite),
                'Mean': np.mean(finite), 'Median': np.median(finite),
                'P90': np.percentile(finite, 90), 'Max': np.max(finite),
            })
    return pd.DataFrame(out)


def main(*, table=None, radius_method=None, model_p='legacy', model_i='legacy',
         radius_i_from=None, out_dir=None, tag=None, progress=print):
    if table is None:
        table = paths.conv_csv(radius_method or 'req')
    table = Path(table)
    conv_df = pd.read_csv(table)

    if radius_i_from:
        alt = pd.read_csv(radius_i_from)[['ConfigName', 'RadiusI']]
        conv_df = conv_df.drop(columns=['RadiusI']).merge(alt, on='ConfigName')
        progress(f'RadiusI column overridden from {radius_i_from}')

    if tag is None:
        tag = radius_method or table.stem.replace('convergence_table_', '')
        if radius_i_from:
            tag += '_ialt'

    err_df = run_logo(conv_df, model_p=model_p, model_i=model_i,
                      progress=progress)
    summary = summarize(err_df)

    out_dir = paths.ensure_dir(paths.resolve(out_dir, paths.CHECK_RESULTS_DIR))
    detail_csv = Path(out_dir) / f'logo_cv_{tag}_{model_p}_{model_i}.csv'
    summary_csv = Path(out_dir) / f'logo_summary_{tag}_{model_p}_{model_i}.csv'
    err_df.to_csv(detail_csv, index=False)
    summary.to_csv(summary_csv, index=False)

    progress(f'\nLOGO CV  table={table.name}  model_p={model_p}  model_i={model_i}')
    progress(f'  folds: {err_df["Family"].nunique()}  configs: '
             f'{err_df["Config"].nunique()}')
    with pd.option_context('display.float_format', '{:8.2f}'.format):
        progress(summary.to_string(index=False))
    progress(f'\nWrote {detail_csv}')
    progress(f'Wrote {summary_csv}')
    return {'detail': err_df, 'summary': summary,
            'detail_csv': detail_csv, 'summary_csv': summary_csv}


def cli(argv=None):
    p = argparse.ArgumentParser(description='LOGO CV for convergence models.')
    p.add_argument('--table', default=None,
                   help='Explicit convergence table CSV path.')
    p.add_argument('--radius-method', default=None,
                   help="Estimator token resolving outputs/tables/"
                        "convergence_table_<token>.csv (default 'req').")
    p.add_argument('--model-p', default='legacy', choices=MODEL_P_CHOICES)
    p.add_argument('--model-i', default='legacy', choices=MODEL_I_CHOICES)
    p.add_argument('--radius-i-from', default=None,
                   help='Optional CSV whose RadiusI column replaces the '
                        "table's (e.g. the SHIPPED_ snapshot).")
    p.add_argument('--out-dir', default=None,
                   help='Output folder (default outputs/check_results).')
    p.add_argument('--tag', default=None,
                   help='Filename token override for the output CSVs.')
    a = p.parse_args(argv)
    return main(table=a.table, radius_method=a.radius_method,
                model_p=a.model_p, model_i=a.model_i,
                radius_i_from=a.radius_i_from, out_dir=a.out_dir, tag=a.tag)


if __name__ == '__main__':
    cli()
