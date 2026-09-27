"""Cross-validated regression for convergence radius and Z_urban.

Runs repeated random 80/20 train/test splits on the unified config pool,
fits Buckingham-Pi-consistent formulas (canonical form R = W^(1/3) * Z for
every target), and selects the best coefficients based on test-set MAPE.
R_urban is not fitted separately: R_urban = W^(1/3) * Z_urban identically.

This module is the orchestrator only. The pieces live in:
    stats.py               — OLS / R² / MAPE helpers
    convergence_models.py  — RadiusP additive Pi model, RadiusI Pi power law
    z_urban.py             — Z_urban power law (fit/predict/clip/evaluate)
    output.py              — coefficient CSVs and formula printers
    plots.py               — best-iteration validation plots
"""

import os
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

from blastlib import paths

from blastlib.regression.convergence_models import (
    fit_pi_all_groups, predict_pi,
    fit_impulse_all_groups, predict_impulse,
)
from blastlib.regression.stats import r2_mape
from blastlib.regression.z_urban import (
    prepare_maxR_data, fit_z_urban_all_groups, evaluate_z_urban,
    evaluate_z_urban_deployable,
)
from blastlib.regression.output import (
    save_best_convergence_coefficients, save_best_nonlinear_coefficients,
    print_final_formulas, print_z_urban_formulas,
)
from blastlib.regression.plots import plot_best_validation


def run_cross_validation(conv_csv, maxR_csv, output_folder,
                         n_iterations=500, test_fraction=0.2,
                         target_mape=10.0, method=None,
                         model_p='relwls', model_i='unified', progress=print):
    """Run repeated 80/20 train/test splits and find best formula coefficients.

    Parameters
    ----------
    conv_csv : str or Path
        Path to convergence_table.csv (with ConfigName, Det columns).
    maxR_csv : str or Path
        Path to max_radius_per_Z.csv.
    output_folder : str or Path
        Directory for output files.
    n_iterations : int
        Number of random splits to try. NOTE: this is passed as n_splits to
        StratifiedShuffleSplit, so changing it changes the ENTIRE sequence of
        splits — results are only comparable across runs with the same value.
    test_fraction : float
        Fraction of configs in test set (default 0.2).
    target_mape : float
        Target maximum MAPE (%) across all models.
    method : str or None
        Radius-estimator token ('req', 'p95', ...) used to suffix every output
        filename so runs with different estimators do not overwrite each other.
        Affects naming only — no fitting formula depends on it.
    model_p : str
        RadiusP fit variant: 'relwls' (rows weighted 1/Z — squared relative
        error, the production default after the 2026-08 acceptance gate) or
        'legacy' (plain OLS). See convergence_models._fit_pi_group.
    model_i : str
        RadiusI fit variant: 'unified' (the shared five-term form,
        production default since 2026-09-27), 'quad' (power law with the
        r2*ln(Pi2)^2 term, previous production) or 'legacy'
        (4-coefficient power law). See _fit_impulse_group.
    progress : callable
        Progress sink (default print). A GUI can pass its own logger.
    """
    pi_weighting = 'relative' if model_p == 'relwls' else 'ols'
    if model_i not in ('unified', 'quad', 'legacy'):
        raise ValueError(f"model_i must be 'unified', 'quad' or 'legacy', "
                         f'got {model_i!r}')
    impulse_model = model_i
    output_folder = str(output_folder)

    def out(name):
        """Output path for *name*, suffixed with the radius estimator."""
        return os.path.join(output_folder, paths.suffixed(name, method))

    # ---- Load data ----
    conv_df = pd.read_csv(conv_csv)
    maxR_df = pd.read_csv(maxR_csv)

    # Prepare maxR data (merge geometry, convergence radii)
    maxR_prepared = prepare_maxR_data(maxR_df, conv_df)

    # ---- Compute stratification labels ----
    config_names = conv_df['ConfigName'].values
    det_values   = conv_df['Det'].values.astype(int)

    # Stratify by det only (street / intersection)
    strata = det_values

    n_configs = len(config_names)
    n_test = max(1, int(n_configs * test_fraction))

    progress(f'Total configs: {n_configs}')
    progress(f'Train/test split: {n_configs - n_test}/{n_test}')
    progress(f'Strata distribution:')
    for s_val in np.unique(strata):
        loc_name = 'Street' if s_val == 1 else 'Intersection'
        progress(f'  {loc_name}: {(strata == s_val).sum()} configs')
    progress('')

    # ---- Stratified split generator ----
    # Fixed seed: identical splits every run, so formula changes are directly
    # comparable (any difference in the numbers is real, not split luck).
    sss = StratifiedShuffleSplit(n_splits=n_iterations, test_size=test_fraction,
                                 random_state=42)

    # ---- Track results ----
    best_worst_mape = np.inf
    best_iteration = -1
    best_conv_P_coeffs = None      # additive Pi model
    best_conv_I_coeffs = None      # Pi power law
    best_z_coeffs = None
    best_mapes = None
    best_train_idx = None
    best_test_idx = None

    cv_rows = []
    n_success = 0

    dummy_X = np.arange(n_configs).reshape(-1, 1)

    for iteration, (train_idx, test_idx) in enumerate(sss.split(dummy_X, strata)):
        train_configs = set(config_names[train_idx])
        test_configs  = set(config_names[test_idx])

        # Split convergence data
        train_conv = conv_df[conv_df['ConfigName'].isin(train_configs)].copy()
        test_conv  = conv_df[conv_df['ConfigName'].isin(test_configs)].copy()

        # Split maxR data
        train_maxR = maxR_prepared[maxR_prepared['Config'].isin(train_configs)].copy()
        test_maxR  = maxR_prepared[maxR_prepared['Config'].isin(test_configs)].copy()

        # ---- Fit convergence radius: P additive Pi, I Pi power law ----
        conv_P_coeffs = fit_pi_all_groups(train_conv, 'RadiusP',
                                          weighting=pi_weighting)
        conv_I_coeffs = fit_impulse_all_groups(train_conv, 'RadiusI',
                                               model=impulse_model)

        # Skip iteration if any det group failed to fit
        if any(c is None for c in conv_P_coeffs.values()):
            continue
        if any(c is None for c in conv_I_coeffs.values()):
            continue

        # Evaluate convergence on test
        test_W   = test_conv['ChargeWeight'].values.astype(float)
        test_H   = test_conv['Height'].values.astype(float)
        test_S   = test_conv['StreetWidth'].values.astype(float)
        test_B   = test_conv['BuildingSize'].values.astype(float)
        test_rho = test_conv['AreaDensity'].values.astype(float)
        test_det = test_conv['Det'].values.astype(int)
        actual_P = test_conv['RadiusP'].values
        actual_I = test_conv['RadiusI'].values

        pred_P = predict_pi(test_W, test_rho, test_H, test_det, test_S, test_B, conv_P_coeffs)
        pred_I = predict_impulse(test_W, test_rho, test_H, test_det, test_S, test_B, conv_I_coeffs)

        conv_r2_P, conv_mape_P = r2_mape(actual_P, pred_P)
        conv_r2_I, conv_mape_I = r2_mape(actual_I, pred_I)

        # ---- Fit Z_urban ----
        # (R_urban = W^(1/3) * Z_urban identically, so no separate fit —
        #  its relative errors equal Z_urban's row-for-row.)
        # Evaluation clips predictions from above at Z_conv using the
        # same-iteration convergence fits — the deployed prediction chain.
        # Those same fits also supply xi to the pressure regime classifier,
        # so nothing leaks from the measured convergence radius.
        z_coeffs = fit_z_urban_all_groups(train_maxR, conv_P_coeffs)
        z_mape_P, z_mape_I = evaluate_z_urban(test_maxR, z_coeffs,
                                              conv_P_coeffs, conv_I_coeffs)

        # Same models, second yardstick: error on the domain a user can
        # identify BEFORE the answer (predicted R_conv; beyond rows graded
        # against the clip). Reported beside z_P/z_I, and deliberately kept
        # OUT of worst/best-split selection so best_* files are unchanged.
        # docs/audit/2026-09-27 STA-02/ALG-03, decision D3 (a)+(b).
        z_mape_P_dep, z_mape_I_dep = evaluate_z_urban_deployable(
            test_maxR, z_coeffs, conv_P_coeffs, conv_I_coeffs)

        # ---- Collect MAPEs ----
        mapes = {
            'conv_P': conv_mape_P, 'conv_I': conv_mape_I,
            'z_P': z_mape_P, 'z_I': z_mape_I,
        }

        # Worst MAPE across all finite targets
        finite_mapes = [v for v in mapes.values() if np.isfinite(v)]
        if not finite_mapes:
            continue
        worst_mape = max(finite_mapes)

        cv_rows.append({
            'iteration': iteration,
            **mapes,
            'worst': worst_mape,
            'conv_P_r2': conv_r2_P,
            'conv_I_r2': conv_r2_I,
            'z_P_dep': z_mape_P_dep,
            'z_I_dep': z_mape_I_dep,
        })

        if worst_mape < target_mape:
            n_success += 1

        if worst_mape < best_worst_mape:
            best_worst_mape = worst_mape
            best_iteration = iteration
            best_conv_P_coeffs = conv_P_coeffs
            best_conv_I_coeffs = conv_I_coeffs
            best_z_coeffs = z_coeffs
            best_mapes = mapes
            best_train_idx = train_idx
            best_test_idx = test_idx

        # Progress
        if (iteration + 1) % 50 == 0 or iteration == 0:
            progress(f'  Iter {iteration+1}/{n_iterations}  '
                     f'best worst_mape={best_worst_mape:.1f}%  '
                     f'this={worst_mape:.1f}%  successes={n_success}')

    # ---- Summary ----
    cv_df = pd.DataFrame(cv_rows)

    # The headline is the DISTRIBUTION over the splits, not its best member.
    # Two separate cautions apply to these numbers and both belong next to
    # them rather than in a document nobody reads beside the log:
    #   * best_worst_mape is a min over n_iterations draws — a selection
    #     statistic. It is what picks the saved best_* coefficients, and it is
    #     optimistically biased by construction (typically ~2 pp below the
    #     median). It is not an accuracy estimate and must never be quoted as
    #     one.
    #   * the splits are stratified on det only, so ~92% of held-out configs
    #     have a same-(det,b,s,H) sibling in train. Since W divides out
    #     exactly under Hopkinson scaling, that is close to an in-sample test
    #     of the geometry dependence. The leave-one-geometry-out harness
    #     (tools/logo_cv) is the estimate to quote for generalisation.
    progress(f'\n{"="*60}')
    progress(f'  CV RESULTS ({n_iterations} random {int(100*(1-test_fraction))}'
             f'/{int(100*test_fraction)} splits)')
    progress(f'{"="*60}')
    progress('  Test MAPE per target — median [p25, p75] over the splits:')
    for key, label in (('conv_P', 'conv_P'), ('conv_I', 'conv_I'),
                       ('z_P', 'z_P   '), ('z_I', 'z_I   '),
                       ('z_P_dep', 'z_P_dep (deployable domain)'),
                       ('z_I_dep', 'z_I_dep (deployable domain)')):
        if key in cv_df:
            v = cv_df[key].dropna()
            if len(v):
                progress(f'    {label}: {v.median():5.2f}%  '
                         f'[{v.quantile(.25):.2f}, {v.quantile(.75):.2f}]')
    progress(f'  Iterations meeting the < {target_mape:.0f}% target: '
             f'{n_success}/{n_iterations}')
    progress('')
    progress('  Split-selection statistics (NOT accuracy estimates — these are')
    progress('  the minimum over the splits, and they choose the best_* files):')
    progress(f'    best iteration       : {best_iteration}')
    progress(f'    its worst-case MAPE  : {best_worst_mape:.2f}%   '
             f'(median across splits: {cv_df["worst"].median():.2f}%)')
    if best_mapes:
        progress('    its per-target MAPEs : '
                 + '  '.join(f'{k} {v:.2f}%' for k, v in best_mapes.items()))
    progress('')
    progress('  Generalisation: quote the leave-one-geometry-out result, not')
    progress('  these splits — they hold out configs, not geometries, and W')
    progress('  divides out exactly, so ~92% of test configs have a sibling')
    progress('  of the same (det, b, s, H) in train.')

    # ---- Save CV summary ----
    cv_csv = out('cv_summary.csv')
    cv_df.to_csv(cv_csv, index=False)
    progress(f'\nSaved: {cv_csv}')

    # ---- Median CV performance per target ----
    med_conv_P = cv_df['conv_P'].median()
    med_conv_I = cv_df['conv_I'].median()
    med_r2_P   = cv_df['conv_P_r2'].median()
    med_r2_I   = cv_df['conv_I_r2'].median()

    progress(f'\n{"="*60}')
    progress('  CONVERGENCE RADIUS MODELS  (R = W^(1/3) * Z, Hopkinson scaling)')
    progress('  RadiusP: Z = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)')
    progress('                + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1)')
    progress('           a = 1 (street) / 2 (intersection)')
    if impulse_model == 'unified':
        progress('  RadiusI: Z = A * Pi2^(C4 + C5*ln(rho) + C3*ln(H/s))')
        progress('               * exp(C1*rho*sqrt(H/s) + C2*ln(H/s)^2)')
    else:
        progress('  RadiusI: Z = A * rho^p * (H/s)^q * (s/W^1/3)^r')
    progress(f'{"="*60}')
    progress(f'  Median conv_P MAPE: {med_conv_P:.2f}%  |  R² = {med_r2_P:.3f}')
    progress(f'  Median conv_I MAPE: {med_conv_I:.2f}%  |  R² = {med_r2_I:.3f}')

    # ---- Save best test split ----
    if best_test_idx is not None:
        test_config_names = config_names[best_test_idx]
        split_df = pd.DataFrame({'ConfigName': test_config_names})
        split_path = out('best_test_configs.csv')
        split_df.to_csv(split_path, index=False)
        progress(f'Saved: {split_path}')

    # ---- Save best CV-iteration coefficients ----
    if best_conv_P_coeffs is not None:
        save_best_convergence_coefficients(
            best_conv_P_coeffs, best_conv_I_coeffs, output_folder,
            filename=paths.suffixed('best_convergence_coefficients.csv', method))

    if best_z_coeffs is not None:
        save_best_nonlinear_coefficients(
            best_z_coeffs,
            paths.suffixed('best_z_urban_coefficients.csv', method),
            output_folder)

    # ---- Validation plot ----
    if best_conv_P_coeffs is not None:
        plot_best_validation(conv_df, maxR_prepared,
                             best_conv_P_coeffs, best_conv_I_coeffs,
                             best_z_coeffs,
                             best_train_idx, best_test_idx,
                             config_names, best_mapes, output_folder,
                             method=method)

    # ---- Print formulas for the best CV iteration ----
    if best_conv_P_coeffs is not None:
        print_final_formulas(conv_df, best_conv_P_coeffs, best_conv_I_coeffs)
        print_z_urban_formulas(best_z_coeffs)

    # ---- Production fit: refit on 100% of data ----
    prod_P_coeffs = fit_pi_all_groups(conv_df, 'RadiusP',
                                      weighting=pi_weighting)
    prod_I_coeffs = fit_impulse_all_groups(conv_df, 'RadiusI',
                                           model=impulse_model)
    prod_z_coeffs = fit_z_urban_all_groups(maxR_prepared, prod_P_coeffs)
    progress(f'\n{"="*60}')
    progress(f'  PRODUCTION FIT  (100% of data)')
    progress(f'{"="*60}')
    save_best_convergence_coefficients(
        prod_P_coeffs, prod_I_coeffs, output_folder,
        filename=paths.suffixed('final_production_convergence_coefficients.csv',
                                method))
    save_best_nonlinear_coefficients(
        prod_z_coeffs,
        paths.suffixed('final_production_z_urban_coefficients.csv', method),
        output_folder)
    progress('  ^ Use these files for thesis formulas (all configs used for fitting).')

    return {
        'best_iteration': best_iteration,
        'best_worst_mape': best_worst_mape,
        'best_mapes': best_mapes,
        'n_success': n_success,
        'n_iterations': n_iterations,
    }
