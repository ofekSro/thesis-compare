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
)
from blastlib.regression.output import (
    save_best_convergence_coefficients, save_best_nonlinear_coefficients,
    print_final_formulas, print_z_urban_formulas,
)
from blastlib.regression.plots import plot_best_validation


def run_cross_validation(conv_csv, maxR_csv, output_folder,
                         n_iterations=500, test_fraction=0.2,
                         target_mape=10.0, method=None, progress=print):
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
    progress : callable
        Progress sink (default print). A GUI can pass its own logger.
    """
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
        conv_P_coeffs = fit_pi_all_groups(train_conv, 'RadiusP')
        conv_I_coeffs = fit_impulse_all_groups(train_conv, 'RadiusI')

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
    progress(f'\n{"="*60}')
    progress(f'  CV RESULTS ({n_iterations} iterations)')
    progress(f'{"="*60}')
    progress(f'Target MAPE: < {target_mape:.0f}%')
    progress(f'Iterations meeting target: {n_success}/{n_iterations}')
    progress(f'Best iteration: {best_iteration}')
    progress(f'Best worst-case MAPE: {best_worst_mape:.2f}%')

    if best_mapes:
        progress(f'\nBest iteration MAPEs:')
        for k, v in best_mapes.items():
            progress(f'  {k}: {v:.2f}%')

    # ---- Save CV summary ----
    cv_df = pd.DataFrame(cv_rows)
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
    prod_P_coeffs = fit_pi_all_groups(conv_df, 'RadiusP')
    prod_I_coeffs = fit_impulse_all_groups(conv_df, 'RadiusI')
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
