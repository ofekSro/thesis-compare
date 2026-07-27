"""Validation plots for the best CV iteration (convergence radius + Z_urban)."""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from blastlib import paths
from blastlib.regression.convergence_models import predict_pi, predict_impulse
from blastlib.regression.z_urban import (
    Z_URBAN_ZF_MIN, Z_URBAN_FORM, z_urban_valid_mask, predicted_Zconv_P,
    predict_z_urban, clip_z_urban_pred,
)


def style_validation_axes(ax, lim, xlabel, ylabel, title):
    """Apply the shared actual-vs-predicted scatter styling.

    Draws the y=x identity line plus the ±10% error guides, squares the
    axes, and labels them. Used by every validation scatter panel.
    """
    ax.plot(lim, lim, 'k--', linewidth=1.5)
    ax.plot(lim, [v * 1.1 for v in lim], color='gray', linestyle='--',
            alpha=0.5, label='+/- 10% Error')
    ax.plot(lim, [v * 0.9 for v in lim], color='gray', linestyle='--', alpha=0.5)
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_aspect('equal'); ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left')


def plot_best_validation(conv_df, maxR_df,
                         conv_P_coeffs, conv_I_coeffs,
                         z_coeffs,
                         train_idx, test_idx,
                         config_names, best_mapes, output_folder, method=None):
    """Plot actual vs predicted for the best CV iteration.

    *method* suffixes the figure names with the radius estimator, matching the
    CSV outputs, so runs with different estimators stay side by side.
    """
    W   = conv_df['ChargeWeight'].values.astype(float)
    H   = conv_df['Height'].values.astype(float)
    S   = conv_df['StreetWidth'].values.astype(float)
    B   = conv_df['BuildingSize'].values.astype(float)
    rho = conv_df['AreaDensity'].values.astype(float)
    det = conv_df['Det'].values.astype(int)

    pred_P = predict_pi(W, rho, H, det, S, B, conv_P_coeffs)
    pred_I = predict_impulse(W, rho, H, det, S, B, conv_I_coeffs)

    actual_P = conv_df['RadiusP'].values
    actual_I = conv_df['RadiusI'].values

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor('white')
    fig.suptitle('Best CV Iteration: Convergence Radius (Train=blue, Test=red)',
                 fontsize=13, fontweight='bold')

    for ax, actual, pred, title, mape_key in [
        (axes[0], actual_P, pred_P, 'Pressure', 'conv_P'),
        (axes[1], actual_I, pred_I, 'Impulse', 'conv_I'),
    ]:
        for idx_set, c, label in [(train_idx, 'C0', 'Train'), (test_idx, 'C3', 'Test')]:
            ax.scatter(actual[idx_set], pred[idx_set], s=50, c=c,
                       edgecolors='k', linewidths=0.5, label=label, alpha=0.7)
        lim = [0, max(actual.max(), np.nanmax(pred)) * 1.1]
        test_mape = best_mapes[mape_key]
        style_validation_axes(ax, lim, 'Actual [m]', 'Predicted [m]',
                              f'{title}\nTest MAPE = {test_mape:.1f}%')

    conv_fname = paths.suffixed('cv_best_convergence.png', method)
    fig.savefig(os.path.join(str(output_folder), conv_fname),
                dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: {conv_fname}')

    # ---- Z_urban plot (R_urban = W^(1/3)*Z_urban — same relative errors) ----
    if z_coeffs is not None:
        _plot_nonlinear_validation(maxR_df, z_coeffs,
                                   conv_P_coeffs, conv_I_coeffs,
                                   config_names, train_idx, test_idx,
                                   best_mapes, output_folder, method)


def _plot_nonlinear_validation(maxR_df, z_coeffs,
                               conv_P_coeffs, conv_I_coeffs,
                               config_names, train_idx, test_idx,
                               best_mapes, output_folder, method=None):
    """Plot Z_urban actual vs predicted (clipped from above at Z_conv)."""
    train_configs = set(config_names[train_idx])
    test_configs  = set(config_names[test_idx])

    for model_name, coeffs, target_cols, mape_keys in [
        ('Z_urban', z_coeffs,
         [('Z_urban_P', 'Pressure', 'RadiusP'), ('Z_urban_I', 'Impulse', 'RadiusI')],
         ('z_P', 'z_I')),
    ]:
        if coeffs is None:
            continue

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.patch.set_facecolor('white')
        fig.suptitle(f'Best CV: {model_name} (Train=blue, Test=red)',
                     fontsize=13, fontweight='bold')

        for ax_idx, (target_col, target_name, radius_col) in enumerate(target_cols):
            ax = axes[ax_idx]
            maxR_col = 'MaxR_P' if target_name == 'Pressure' else 'MaxR_I'

            all_actual_train, all_pred_train = [], []
            all_actual_test, all_pred_test = [], []

            for det_val in [1, 2]:
                popt = coeffs.get((det_val, target_name))
                if popt is None:
                    continue

                mask = (maxR_df['det'] == det_val)

                sub = maxR_df[mask].dropna(subset=[target_col, radius_col])
                if len(sub) == 0:
                    continue

                sub_valid = sub[z_urban_valid_mask(sub, target_col, maxR_col,
                                                   radius_col, target_name)]
                if len(sub_valid) == 0:
                    continue

                y_actual = sub_valid[target_col].values

                W13 = sub_valid['weight'].values ** (1 / 3)
                xi = None
                if Z_URBAN_FORM.get(target_name) == 'lambda_regime':
                    xi = (sub_valid['Z_free'].values.astype(float)
                          / predicted_Zconv_P(sub_valid, conv_P_coeffs))
                y_pred = predict_z_urban(
                    sub_valid['Z_free'].values, sub_valid['rho'].values,
                    sub_valid['height'].values, sub_valid['swidth'].values,
                    W13, target_name, popt, xi=xi)
                y_pred = clip_z_urban_pred(y_pred, sub_valid, det_val,
                                           target_name, conv_P_coeffs,
                                           conv_I_coeffs)

                is_train = sub_valid['Config'].isin(train_configs)
                is_test  = sub_valid['Config'].isin(test_configs)

                if is_train.any():
                    all_actual_train.append(y_actual[is_train.values])
                    all_pred_train.append(y_pred[is_train.values])
                if is_test.any():
                    all_actual_test.append(y_actual[is_test.values])
                    all_pred_test.append(y_pred[is_test.values])

            # Plot
            if all_actual_train:
                at = np.concatenate(all_actual_train)
                pt = np.concatenate(all_pred_train)
                ax.scatter(at, pt, s=30, c='C0', alpha=0.5, edgecolors='k',
                           linewidths=0.3, label='Train')
            if all_actual_test:
                at = np.concatenate(all_actual_test)
                pt = np.concatenate(all_pred_test)
                ax.scatter(at, pt, s=50, c='C3', alpha=0.8, edgecolors='k',
                           linewidths=0.5, label='Test')

            all_vals = []
            for lst in [all_actual_train, all_pred_train, all_actual_test, all_pred_test]:
                if lst:
                    all_vals.append(np.concatenate(lst))
            if all_vals:
                combined = np.concatenate(all_vals)
                lim = [0, np.nanmax(combined) * 1.1]
            else:
                lim = [0, 1]

            mape_key = mape_keys[ax_idx]
            test_mape = best_mapes.get(mape_key, np.nan)
            unit = 'm/kg^(1/3)' if model_name == 'Z_urban' else 'm'
            style_validation_axes(ax, lim, f'Actual [{unit}]', f'Predicted [{unit}]',
                                  f'{target_name}\nTest MAPE = {test_mape:.1f}%')

        fname = paths.suffixed(f'cv_best_{model_name.lower()}.png', method)
        fig.savefig(os.path.join(str(output_folder), fname), dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f'Saved: {fname}')
