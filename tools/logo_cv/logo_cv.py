"""Leave-one-geometry-out (LOGO) cross-validation for the convergence models
and, with --target zurban, for the Z_urban model.

Protocol (docs/PYSR_CONVERGENCE_SEARCH.md): folds are the (Det, b, s, H)
families — 18 per det, 36 total. Per fold, both det groups are refit on the
remaining configs with the real pipeline fitters and the held-out family is
predicted out-of-fold. Error is 100*|pred - actual| / actual on R (identical
to the error on Z = R / W^(1/3)).

Baseline gate (legacy models on the req table): P mean 8.39 / max 43.35,
I mean 8.55 / max 38.48.

--target zurban: per fold the convergence models AND fit_z_urban_all_groups
are refit on the remaining configs, and every MaxR row of the held-out family
is predicted. The rows graded are those evaluate_z_urban grades
(--domain conditional: z_urban_valid_mask, i.e. the MEASURED R_conv and MaxR)
or those evaluate_z_urban_deployable grades (--domain deployable: the domain a
user can identify beforehand, from the PREDICTED R_conv). Predictions carry
the same Z_conv clip. Each fold is gated: the MAPE of the rows written here
must equal what the library evaluator returns for that fold, else the run
stops. Error on Z_urban is identical to the error on Lambda = Z_urban / Z_free.

Figures: predicted vs measured, P and I panels, in the style of
isiems_paper/make_fig4.py (PS_Fig4), under outputs/figures/<tag>/:
R_conv and Z_conv (_R, _Z), or Z_urban and Lambda (_Zu, _Lambda) for
--target zurban. Skip with --no-figure.

Defaults are production: the constants.RADIUS_ESTIMATOR table, relwls P
model, quad I model (as run_analysis.py). The baseline gate above needs
--radius-method req --model-p legacy --model-i legacy.

Usage:
    python tools\\logo_cv\\logo_cv.py
    python tools\\logo_cv\\logo_cv.py --target zurban
    python tools\\logo_cv\\logo_cv.py --target zurban --domain deployable
    python tools\\logo_cv\\logo_cv.py --radius-method req --model-p legacy --model-i legacy
    python tools\\logo_cv\\logo_cv.py --table path\\to\\table.csv --tag mytag
"""

import argparse
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import numpy as np
import pandas as pd

from blastlib import constants, paths
from blastlib.regression.convergence_models import (
    fit_pi_all_groups, fit_impulse_all_groups, predict_pi, predict_impulse)
from blastlib.regression.z_urban import (
    Z_URBAN_FORM, Z_URBAN_ZF_MIN, clip_z_urban_pred, evaluate_z_urban,
    evaluate_z_urban_deployable, fit_z_urban_all_groups, predict_z_urban,
    predicted_Zconv_P, prepare_maxR_data, z_urban_valid_mask)

GROUP_COLS = ['Det', 'BuildingSize', 'StreetWidth', 'Height']

MODEL_P_CHOICES = ('legacy', 'relwls')
MODEL_I_CHOICES = ('legacy', 'quad', 'unified')
# Production models, as the run_analysis.py defaults.
MODEL_P_DEFAULT = 'relwls'
MODEL_I_DEFAULT = 'quad'

TARGET_CHOICES = ('conv', 'zurban')
DOMAIN_CHOICES = ('conditional', 'deployable')
# (load, Z_urban column, z_urban target name, R_conv column, MaxR column)
ZURBAN_LOADS = (('P', 'Z_urban_P', 'Pressure', 'RadiusP', 'MaxR_P'),
                ('I', 'Z_urban_I', 'Impulse', 'RadiusI', 'MaxR_I'))


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
        # 'quad' (production since 2026-09-28) or 'unified' (2026-09-27 only)
        fit_i = lambda df: fit_impulse_all_groups(df, 'RadiusI', model=model_i)
    return fit_p, fit_i


def _families(conv_df):
    """Yield (label, held-out mask) per (Det, b, s, H) family."""
    for fam in conv_df[GROUP_COLS].drop_duplicates().itertuples(index=False):
        fam_mask = np.ones(len(conv_df), dtype=bool)
        for col, val in zip(GROUP_COLS, fam):
            fam_mask &= conv_df[col].values == val
        yield 'det{}_b{}_s{}_h{}'.format(*fam), fam_mask


def run_logo(conv_df, model_p=MODEL_P_DEFAULT, model_i=MODEL_I_DEFAULT,
             progress=print):
    """Run LOGO CV over the convergence table. Returns per-config rows df."""
    fit_p, fit_i = _make_fitters(model_p, model_i)

    rows = []
    for fam_label, fam_mask in _families(conv_df):
        train = conv_df[~fam_mask]
        test = conv_df[fam_mask]

        p_coeffs = fit_p(train)
        i_coeffs = fit_i(train)

        args = (test['ChargeWeight'].values, test['AreaDensity'].values,
                test['Height'].values, test['Det'].values,
                test['StreetWidth'].values, test['BuildingSize'].values)
        pred_p = predict_pi(*args, p_coeffs)
        pred_i = predict_impulse(*args, i_coeffs)

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


def _zurban_graded_rows(sub, det_val, target_col, target_name, radius_col,
                        maxR_col, conv_coeffs, domain):
    """Rows of one det/load that the library evaluator grades.

    Mirrors evaluate_z_urban (conditional) and evaluate_z_urban_deployable
    (deployable) in blastlib/regression/z_urban.py; the per-fold gate in
    run_logo_zurban fails if the two ever drift apart.
    """
    if domain == 'conditional':
        sub = sub.dropna(subset=[target_col, radius_col])
        if len(sub) == 0:
            return sub
        return sub[z_urban_valid_mask(sub, target_col, maxR_col, radius_col,
                                      target_name)]

    sub = sub.dropna(subset=[target_col])
    if conv_coeffs is None or len(sub) == 0:
        return sub.iloc[0:0]
    W = sub['weight'].values.astype(float)
    det_arr = np.full(len(sub), det_val, dtype=int)
    rho = sub['rho'].values.astype(float)
    H = sub['height'].values.astype(float)
    s = sub['swidth'].values.astype(float)
    b = sub['bsize'].values.astype(float)
    predict = predict_pi if target_name == 'Pressure' else predict_impulse
    Rconv_pred = predict(W, rho, H, det_arr, s, b, conv_coeffs)
    r_free = sub['R_free'].astype(float).values
    dom = (np.isfinite(Rconv_pred) & (r_free < Rconv_pred)
           & (sub['Z_free'].values >= Z_URBAN_ZF_MIN[target_name]))
    if 'exclude_r' in sub.columns:
        dom &= r_free > sub['exclude_r'].astype(float).values
    dom &= r_free >= constants.Z_URBAN_MIN_PERIODS * (s + b)  # D46
    return sub[dom]


def run_logo_zurban(conv_df, maxr_df, model_p=MODEL_P_DEFAULT,
                    model_i=MODEL_I_DEFAULT, domain='conditional',
                    progress=print):
    """LOGO CV of the Z_urban chain. Returns one row per graded MaxR row.

    conv_df, maxr_df : the convergence and max_radius_per_Z tables of one
                       estimator run.
    domain           : 'conditional' or 'deployable' (see module docstring).
    Columns: Z_free, Actual/Predicted = Z_urban [m/kg^(1/3)], Lambda_actual,
    Lambda_pred [-], ErrPct [%] (the same for Z_urban and Lambda).
    Raises RuntimeError if a fold's MAPE differs from the library evaluator.
    """
    if domain not in DOMAIN_CHOICES:
        raise ValueError(f'domain must be one of {DOMAIN_CHOICES}, got {domain!r}')
    evaluate = (evaluate_z_urban if domain == 'conditional'
                else evaluate_z_urban_deployable)
    fit_p, fit_i = _make_fitters(model_p, model_i)
    prep = prepare_maxR_data(maxr_df, conv_df)

    rows = []
    for fam_label, fam_mask in _families(conv_df):
        test_cfg = set(conv_df['ConfigName'].values[fam_mask])
        train_c = conv_df[~fam_mask]
        in_test = prep['Config'].isin(test_cfg)
        train_m, test_m = prep[~in_test], prep[in_test]

        cP = fit_p(train_c)
        cI = fit_i(train_c)
        z_coeffs = fit_z_urban_all_groups(train_m, cP)

        fam_rows = []
        for det_val in (1, 2):
            sub_det = test_m[test_m['det'] == det_val]
            for load, target_col, target_name, radius_col, maxR_col in ZURBAN_LOADS:
                popt = z_coeffs.get((det_val, target_name))
                if popt is None or len(sub_det) == 0:
                    continue
                conv_coeffs = cP if target_name == 'Pressure' else cI
                sub = _zurban_graded_rows(sub_det, det_val, target_col,
                                          target_name, radius_col, maxR_col,
                                          conv_coeffs, domain)
                if len(sub) == 0:
                    continue
                W13 = sub['weight'].values ** (1 / 3)
                xi = None
                if Z_URBAN_FORM.get(target_name) == 'lambda_regime':
                    xi = (sub['Z_free'].values.astype(float)
                          / predicted_Zconv_P(sub, cP))
                pred = predict_z_urban(
                    sub['Z_free'].values, sub['rho'].values,
                    sub['height'].values, sub['swidth'].values,
                    W13, target_name, popt, xi=xi)
                pred = clip_z_urban_pred(pred, sub, det_val, target_name, cP, cI)
                for cfg, zf, act, prd in zip(sub['Config'].values,
                                             sub['Z_free'].values.astype(float),
                                             sub[target_col].values.astype(float),
                                             pred):
                    ok = np.isfinite(act) and np.isfinite(prd)
                    fam_rows.append({
                        'Config': cfg, 'Det': det_val, 'Family': fam_label,
                        'Target': load, 'Z_free': zf,
                        'Actual': act, 'Predicted': prd,
                        'Lambda_actual': act / zf, 'Lambda_pred': prd / zf,
                        'ErrPct': 100.0 * abs(prd - act) / abs(act) if ok else np.nan})

        # Gate: these rows must reproduce the library's fold MAPE exactly.
        lib = dict(zip(('P', 'I'), evaluate(test_m, z_coeffs, cP, cI)))
        fam_df = pd.DataFrame(fam_rows, columns=['Target', 'ErrPct'])
        for load in ('P', 'I'):
            e = fam_df.loc[fam_df['Target'] == load, 'ErrPct'].values
            e = e[np.isfinite(e)]
            mine = np.mean(e) if len(e) >= 2 else np.nan
            if not (np.isclose(mine, lib[load], rtol=1e-9, atol=0)
                    or (np.isnan(mine) and np.isnan(lib[load]))):
                raise RuntimeError(
                    f'{fam_label} {load}: rows give MAPE {mine!r}, '
                    f'{evaluate.__name__} gives {lib[load]!r}; the row '
                    'selection here no longer mirrors blastlib.')
        rows.extend(fam_rows)
    progress(f'  gate: every fold matches {evaluate.__name__}')
    return pd.DataFrame(rows)


# Family-level bootstrap of the mean error. Rows of one family share a
# geometry and are correlated (a Z_urban family carries 6-49 rows), so the
# resampling unit is the family, not the row; 36 families is the effective
# sample. Resampled within det, so every replicate keeps the design's 18 + 18.
# Fixed seed and a fresh generator per call: the CI of a scope does not depend
# on which scopes were computed before it. Percentile interval.
BOOT_N = 10000
BOOT_SEED = 42

# R² columns per target kind: (name, view). 'R'/'Zu' are the stored
# Actual/Predicted; 'Z'/'Lambda' divide by W^(1/3) / Z_free (see plot_logo).
R2_VIEWS = {'conv': (('R2_R', 'R'), ('R2_Z', 'Z')),
            'zurban': (('R2_Zurban', 'Zu'), ('R2_Lambda', 'Lambda'))}


def _view_divisor(err_df, view):
    """Divisor that turns Actual/Predicted into the *view* quantity."""
    if view == 'Z':
        return err_df['Config'].str.extract(r'_w(\d+)$')[0].astype(float) ** (1 / 3.)
    if view == 'Lambda':
        return err_df['Z_free'].astype(float)
    return pd.Series(1.0, index=err_df.index)


def _r2(sub, div):
    """R² of Predicted on Actual, both divided by *div* [-]."""
    a = sub['Actual'] / div[sub.index]
    q = sub['Predicted'] / div[sub.index]
    return 1 - ((a - q) ** 2).sum() / ((a - a.mean()) ** 2).sum()


def family_bootstrap_ci(sub, n_boot=BOOT_N, seed=BOOT_SEED, per_family=False):
    """95% percentile CI [%] of the mean error, resampling whole families.

    sub        : err_df rows with finite ErrPct [%] (columns Family, Det).
    per_family : False -> row-pooled mean (sum of errors / rows, the 'Mean'
                 of the pooled/det scopes); True -> mean of family MAPEs
                 (the 'Mean' of the per_family scope).
    Families are resampled with replacement within each det.
    Returns (lo, hi) [%].
    """
    fam = sub.groupby('Family').agg(det=('Det', 'first'),
                                    s=('ErrPct', 'sum'), n=('ErrPct', 'size'))
    rng = np.random.default_rng(seed)
    num = np.zeros(n_boot)
    den = np.zeros(n_boot)
    for _, g in fam.groupby('det'):
        k = rng.integers(0, len(g), size=(n_boot, len(g)))
        if per_family:
            num += (g['s'] / g['n']).values[k].sum(axis=1)
            den += len(g)
        else:
            num += g['s'].values[k].sum(axis=1)
            den += g['n'].values[k].sum(axis=1)
    lo, hi = np.percentile(num / den, [2.5, 97.5])
    return float(lo), float(hi)


def _coverage(sub, configs, det=None):
    """Families / configs graded in *sub*, out of the configs in scope."""
    if configs is None:
        total = np.nan
    elif det is None:
        total = len(configs)
    else:
        total = int((configs['Det'] == det).sum())
    n_cfg = sub['Config'].nunique()
    return {'N_families': sub['Family'].nunique(), 'N_configs': n_cfg,
            'Configs_total': total, 'Coverage_configs': n_cfg / total}


def summarize(err_df, kind='conv', configs=None, n_boot=BOOT_N, seed=BOOT_SEED):
    """Pooled + per-det mean/median/p90/max rows per target.

    kind    : 'conv' or 'zurban'; selects the R² views (R2_VIEWS).
    configs : DataFrame with ConfigName, Det of every config in the table;
              the denominator of Coverage_configs. None -> coverage NaN.
    Columns after Max: Mean_CI95_lo/hi [%] (family bootstrap), the two R²,
    then coverage.
    """
    out = []
    for target in ('P', 'I'):
        sub_t = err_df[err_df['Target'] == target]
        for scope, det, sub in [('pooled', None, sub_t),
                                ('det1', 1, sub_t[sub_t['Det'] == 1]),
                                ('det2', 2, sub_t[sub_t['Det'] == 2])]:
            errs = sub['ErrPct'].values
            finite = errs[np.isfinite(errs)]
            fin = sub[np.isfinite(sub['ErrPct'])]
            lo, hi = family_bootstrap_ci(fin, n_boot, seed)
            row = {
                'Target': target, 'Scope': scope,
                'N': len(errs), 'N_finite': len(finite),
                'Mean': np.mean(finite), 'Median': np.median(finite),
                'P90': np.percentile(finite, 90), 'Max': np.max(finite),
                'Mean_CI95_lo': lo, 'Mean_CI95_hi': hi,
            }
            for name, view in R2_VIEWS[kind]:
                row[name] = _r2(fin, _view_divisor(fin, view))
            row.update(_coverage(fin, configs, det))
            out.append(row)
    return pd.DataFrame(out)


def summarize_families(err_df, configs=None, n_boot=BOOT_N, seed=BOOT_SEED):
    """Per target, statistics over the per-family MAPEs (Scope 'per_family').

    The mean of these is the LOGO figure of plan_evidence (logo_z_urban),
    which averages families rather than rows. R² is not defined here.
    """
    out = []
    for target in ('P', 'I'):
        sub = err_df[(err_df['Target'] == target) & np.isfinite(err_df['ErrPct'])]
        fam = sub.groupby('Family')['ErrPct'].mean().values
        lo, hi = family_bootstrap_ci(sub, n_boot, seed, per_family=True)
        out.append({'Target': target, 'Scope': 'per_family',
                    'N': len(fam), 'N_finite': len(fam),
                    'Mean': np.mean(fam), 'Median': np.median(fam),
                    'P90': np.percentile(fam, 90), 'Max': np.max(fam),
                    'Mean_CI95_lo': lo, 'Mean_CI95_hi': hi,
                    **_coverage(sub, configs)})
    return pd.DataFrame(out)


# Style copied from isiems_paper/make_fig4.py (ISIEMS paper Fig. 5, PS_Fig4).
BLU, RED = '#2166ac', '#b2182b'
INK, MID, PALE = '#1a1a1a', '#8c8c8c', '#c8c8c8'
FIG_STYLE = {
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial'], 'font.size': 9,
    'mathtext.fontset': 'custom', 'mathtext.rm': 'Arial',
    'mathtext.it': 'Arial:italic', 'mathtext.bf': 'Arial:bold',
    'mathtext.default': 'it',
    'axes.edgecolor': '#5a5a5a', 'axes.linewidth': 0.7,
    'xtick.color': INK, 'ytick.color': INK, 'xtick.direction': 'out',
    'ytick.direction': 'out', 'text.color': INK, 'axes.labelcolor': INK,
    'pdf.fonttype': 42}

# view -> (axis symbol with %s for the load, unit). The divisor per view is
# applied in plot_logo; the % error is the same in every view.
FIG_VIEWS = {
    'R': (r'R_\mathrm{conv,%s}', '[m]'),
    'Z': (r'Z_\mathrm{conv,%s}', r'[m/kg$^{1/3}$]'),
    'Zu': (r'Z_\mathrm{urban,%s}', r'[m/kg$^{1/3}$]'),
    'Lambda': (r'\Lambda_\mathrm{%s}', '[-]'),
}


def plot_logo(err_df, out_png, view='R', progress=print):
    """Predicted vs measured, out-of-fold, P and I panels.

    err_df  : run_logo() output (views 'R', 'Z') or run_logo_zurban() output
              (views 'Zu', 'Lambda'); ErrPct in %.
    out_png : output PNG path.
    view    : 'R'  R_conv [m];
              'Z'  Z_conv = R_conv / W^(1/3) [m/kg^(1/3)], W from the
                   '_w<kg>' ConfigName suffix;
              'Zu' Z_urban [m/kg^(1/3)];
              'Lambda' Z_urban / Z_free [-].
    The error statistics do not depend on *view*; only R^2 does, because the
    divisor (W^(1/3) or Z_free) carries part of the axis range.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import MaxNLocator

    sym, unit = FIG_VIEWS[view]
    # Same divisor as the summary's R² columns, so figure and CSV agree.
    div = _view_divisor(err_df, view)
    # Z_urban sets hold ~10x the points of the 96-config sets.
    ms = 4.6 if len(err_df) <= 400 else 2.6

    with plt.rc_context(FIG_STYLE):
        fig, axes = plt.subplots(1, 2, figsize=(16 / 2.54, 8.4 / 2.54))
        fig.subplots_adjust(left=0.080, right=0.988, top=0.845, bottom=0.140,
                            wspace=0.235)
        for ax, load, tag, name in zip(axes, ['P', 'I'], ['(a)', '(b)'],
                                       ['Peak overpressure', 'Positive-phase impulse']):
            sub = err_df[(err_df['Target'] == load)
                         & np.isfinite(err_df['ErrPct'])]
            a = sub['Actual'] / div[sub.index]
            q = sub['Predicted'] / div[sub.index]
            e = sub['ErrPct'].abs().tolist()
            # Axis limit from the data, not make_fig4's fixed 145/240: the tool
            # runs on every estimator token.
            ticks = MaxNLocator(nbins=6, steps=[1, 2, 2.5, 3, 5, 6, 10]).tick_values(
                0, 1.02 * max(a.max(), q.max()))
            hi = ticks[-1]
            r2 = _r2(sub, div)
            n10 = sum(v <= 10 for v in e)
            n20 = sum(v <= 20 for v in e)
            # Inclusive quantiles reproduce the Median/P90 of summarize().
            med = st.median(e)
            p90 = st.quantiles(e, n=10, method='inclusive')[8]

            ax.fill_between([0, hi], [0, hi * 0.80], [0, hi * 1.20],
                            color='#000000', alpha=0.045, lw=0, zorder=1)
            ax.plot([0, hi], [0, hi], color=INK, lw=1.0, zorder=4)
            for f in (1.10, 0.90):
                ax.plot([0, hi], [0, hi * f], color=MID, lw=0.75,
                        ls=(0, (4, 2.6)), zorder=3)
            for f in (1.20, 0.80):
                ax.plot([0, hi], [0, hi * f], color=PALE, lw=0.75,
                        ls=(0, (1.4, 1.8)), zorder=3)
            for det, c in ((1, BLU), (2, RED)):
                m = (sub['Det'] == det).values
                ax.plot(a[m], q[m], ls='none', marker='o', ms=ms, mfc=c,
                        mec='white', mew=0.55 * ms / 4.6, alpha=0.92, zorder=6)

            ax.set_xlim(0, hi)
            ax.set_ylim(0, hi)
            ax.set_aspect('equal', adjustable='box')
            ax.set_xticks(ticks)
            ax.set_yticks(ticks)
            label = sym % load
            ax.set_xlabel(r'measured  $%s$  %s' % (label, unit),
                          labelpad=3, fontsize=8.8)
            ax.set_ylabel(r'predicted  $%s$  %s' % (label, unit),
                          labelpad=3, fontsize=8.8)
            ax.set_title('%s  %s' % (tag, name), fontsize=9.4, loc='left', pad=6)
            ax.grid(color='0.93', lw=0.5, zorder=0)
            ax.set_axisbelow(True)
            ax.tick_params(length=2.6, width=0.7, labelsize=8.2, pad=2)
            # "$R$²" rather than "$R^2$": see make_fig4.py (Arial's own superscript).
            box = ('$R$² = %.3f\nMAPE = %.1f %%\nmedian error = %.1f %%\n'
                   '90th percentile = %.1f %%\n%d of %d within $\\pm$10 %%\n'
                   '%d of %d within $\\pm$20 %%'
                   % (r2, st.mean(e), med, p90, n10, len(e), n20, len(e)))
            ax.text(0.035, 0.955, box, transform=ax.transAxes, fontsize=7.7,
                    color='0.22', ha='left', va='top', linespacing=1.40)
            progress(f'  {view} {load}: R2 {r2:.4f}  within 10% {n10}/{len(e)}  '
                     f'within 20% {n20}/{len(e)}')

        h = [Line2D([], [], color=BLU, lw=0, marker='o', ms=4.6, mfc=BLU,
                    mec='white', mew=0.55, label='street detonation, det1'),
             Line2D([], [], color=RED, lw=0, marker='o', ms=4.6, mfc=RED,
                    mec='white', mew=0.55, label='intersection detonation, det2'),
             Line2D([], [], color=INK, lw=1.0, label='1:1'),
             Line2D([], [], color=MID, lw=0.75, ls=(0, (4, 2.6)),
                    label=r'$\pm$10 %'),
             Line2D([], [], color=PALE, lw=0.75, ls=(0, (1.4, 1.8)),
                    label=r'$\pm$20 %')]
        fig.legend(handles=h, loc='upper center', bbox_to_anchor=(0.534, 1.003),
                   frameon=False, fontsize=8.4, ncol=5, handlelength=1.8,
                   columnspacing=1.35, handletextpad=0.45)
        fig.savefig(out_png, dpi=400)
        plt.close(fig)
    return Path(out_png)


def main(*, table=None, radius_method=None, model_p=MODEL_P_DEFAULT,
         model_i=MODEL_I_DEFAULT, target='conv', domain='conditional',
         maxr_table=None, radius_i_from=None, out_dir=None, tag=None,
         figure=True, n_boot=BOOT_N, boot_seed=BOOT_SEED, progress=print):
    """Run LOGO CV, write the detail and summary CSVs and the figures.

    target     : 'conv' (R_conv models) or 'zurban' (Z_urban chain).
    domain     : 'conditional' | 'deployable'; zurban only.
    maxr_table : max_radius_per_Z CSV for zurban; default = the table of the
                 same estimator token as the convergence table.
    n_boot, boot_seed : family-bootstrap replicates and seed of the
                 Mean_CI95 columns (see family_bootstrap_ci).
    Returns dict with the DataFrames and the written paths.
    """
    if target not in TARGET_CHOICES:
        raise ValueError(f'target must be one of {TARGET_CHOICES}, got {target!r}')
    if table is None:
        radius_method = radius_method or constants.RADIUS_ESTIMATOR['method']
        table = paths.conv_csv(radius_method)
    table = Path(table)
    token = radius_method or table.stem.replace('convergence_table_', '')
    conv_df = pd.read_csv(table)

    if radius_i_from:
        alt = pd.read_csv(radius_i_from)[['ConfigName', 'RadiusI']]
        conv_df = conv_df.drop(columns=['RadiusI']).merge(alt, on='ConfigName')
        progress(f'RadiusI column overridden from {radius_i_from}')

    if tag is None:
        tag = token
        if radius_i_from:
            tag += '_ialt'

    configs = conv_df[['ConfigName', 'Det']]

    if target == 'zurban':
        maxr_table = Path(maxr_table or paths.maxr_csv(token))
        err_df = run_logo_zurban(conv_df, pd.read_csv(maxr_table),
                                 model_p=model_p, model_i=model_i,
                                 domain=domain, progress=progress)
        summary = pd.concat([summarize(err_df, 'zurban', configs, n_boot, boot_seed),
                             summarize_families(err_df, configs, n_boot, boot_seed)],
                            ignore_index=True)
        stem = f'{tag}_{model_p}_{model_i}_zurban'
        if domain == 'deployable':
            stem += '_deploy'
        views = ('Zu', 'Lambda')
        header = (f'LOGO CV  target=zurban  domain={domain}  '
                  f'tables={table.name}, {maxr_table.name}')
    else:
        err_df = run_logo(conv_df, model_p=model_p, model_i=model_i,
                          progress=progress)
        summary = summarize(err_df, 'conv', configs, n_boot, boot_seed)
        stem = f'{tag}_{model_p}_{model_i}'
        views = ('R', 'Z')
        header = f'LOGO CV  table={table.name}'

    out_dir = paths.ensure_dir(paths.resolve(out_dir, paths.CHECK_RESULTS_DIR))
    detail_csv = Path(out_dir) / f'logo_cv_{stem}.csv'
    summary_csv = Path(out_dir) / f'logo_summary_{stem}.csv'
    err_df.to_csv(detail_csv, index=False)
    summary.to_csv(summary_csv, index=False)

    progress(f'\n{header}  model_p={model_p}  model_i={model_i}')
    progress(f'  folds: {err_df["Family"].nunique()}  configs: '
             f'{err_df["Config"].nunique()}  rows: {len(err_df)}')
    with pd.option_context('display.float_format', '{:8.2f}'.format):
        progress(summary.to_string(index=False))
    progress(f'\nWrote {detail_csv}')
    progress(f'Wrote {summary_csv}')

    figures = []
    if figure:
        fig_base = paths.fig_dir(tag) / f'logo_cv_{stem}'
        for view in views:
            figures.append(plot_logo(err_df, f'{fig_base}_{view}.png',
                                     view=view, progress=progress))
            progress(f'Wrote {figures[-1]}')
    return {'detail': err_df, 'summary': summary,
            'detail_csv': detail_csv, 'summary_csv': summary_csv,
            'figures': figures}


def cli(argv=None):
    p = argparse.ArgumentParser(description='LOGO CV for the convergence and '
                                            'Z_urban models.')
    p.add_argument('--table', default=None,
                   help='Explicit convergence table CSV path.')
    p.add_argument('--radius-method', default=None,
                   help="Estimator token resolving outputs/tables/"
                        "convergence_table_<token>.csv (default: production, "
                        f"{constants.RADIUS_ESTIMATOR['method']}).")
    p.add_argument('--model-p', default=MODEL_P_DEFAULT, choices=MODEL_P_CHOICES)
    p.add_argument('--model-i', default=MODEL_I_DEFAULT, choices=MODEL_I_CHOICES)
    p.add_argument('--target', default='conv', choices=TARGET_CHOICES,
                   help='conv = R_conv models; zurban = Z_urban chain.')
    p.add_argument('--domain', default='conditional', choices=DOMAIN_CHOICES,
                   help='zurban only: rows graded as evaluate_z_urban '
                        '(conditional) or evaluate_z_urban_deployable.')
    p.add_argument('--maxr-table', default=None,
                   help='zurban only: max_radius_per_Z CSV (default: the one '
                        'of the same estimator token).')
    p.add_argument('--radius-i-from', default=None,
                   help='Optional CSV whose RadiusI column replaces the '
                        "table's (e.g. the SHIPPED_ snapshot).")
    p.add_argument('--out-dir', default=None,
                   help='Output folder (default outputs/check_results).')
    p.add_argument('--tag', default=None,
                   help='Filename token override for the output CSVs.')
    p.add_argument('--no-figure', dest='figure', action='store_false',
                   help='Skip the predicted-vs-measured figures.')
    p.add_argument('--n-boot', type=int, default=BOOT_N,
                   help=f'Family-bootstrap replicates for Mean_CI95 (default {BOOT_N}).')
    p.add_argument('--boot-seed', type=int, default=BOOT_SEED,
                   help=f'Seed of the family bootstrap (default {BOOT_SEED}).')
    a = p.parse_args(argv)
    return main(table=a.table, radius_method=a.radius_method,
                model_p=a.model_p, model_i=a.model_i, target=a.target,
                domain=a.domain, maxr_table=a.maxr_table,
                radius_i_from=a.radius_i_from, out_dir=a.out_dir, tag=a.tag,
                figure=a.figure, n_boot=a.n_boot, boot_seed=a.boot_seed)


if __name__ == '__main__':
    cli()
