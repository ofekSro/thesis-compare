"""Validation check: load best CV coefficients, apply to ALL configs,
show per-config errors and overall metrics.

Uses the saved coefficient CSVs from the cross-validation run
(best_convergence_coefficients.csv, best_z_urban_coefficients.csv,
best_r_urban_coefficients.csv) and validates against convergence_table.csv
and max_radius_per_Z.csv.
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from config_parser import config_parser

from regression import (
    _r2_mape,
    _z_urban_model_pressure, _z_urban_model_impulse, _r_urban_model,
)


# ============================================================
# Load best coefficients from CSVs
# ============================================================

def load_convergence_coefficients(csv_path):
    """Load additive Pi convergence radius coefficients.

    Returns dict {(det, target): coef_dict} where coef_dict has keys:
        C0, C1, C2, C3, a, has_H_term

    Formula: R = W^(1/3) * (C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                                + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1))
    a = 1 (street) / 2 (intersection): density-switch threshold.
    """
    df = pd.read_csv(csv_path)
    coeffs = {}
    for _, row in df.iterrows():
        det = int(row['Det'])
        target = row['Target']
        coeffs[(det, target)] = {
            'C0':         float(row['C0']),
            'C1':         float(row['C1_sW13']),
            'C2':         float(row['C2_switch']),
            'C3':         float(row['C3_canyon']),
            'a':          float(row['a_thresh']),
            'has_H_term': bool(int(row['has_H_term'])),
        }
    return coeffs


def load_nonlinear_coefficients(csv_path):
    """Load Z_urban or R_urban coefficients.

    Returns dict {(det, target): {m, n, a, b, c, d}}.
    """
    df = pd.read_csv(csv_path)
    coeffs = {}
    for _, row in df.iterrows():
        det = int(row['Det'])
        target = row['Target']
        coeffs[(det, target)] = {
            'm': float(row['m']),
            'n': float(row['n']) if pd.notna(row['n']) else 0.0,
            'a': float(row['a']),
            'b': float(row['b']),
            'c': float(row['c']),
            'd': float(row['d']),
        }
    return coeffs


# ============================================================
# Prediction functions
# ============================================================

def predict_convergence_radius(cfg, conv_coeffs):
    """Predict convergence radii for a single config using the additive Pi model.

    Formula: R = W^(1/3) * (C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                                + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1))
    When has_H_term is False (H=0 group), C3 is zero.
    """
    bsize  = cfg['bsize']
    swidth = cfg['swidth']
    height = cfg['height']
    weight = cfg['weight']
    det    = cfg['det']

    rho = bsize ** 2 / (bsize + swidth) ** 2
    W13 = weight ** (1 / 3)
    pi2 = swidth / W13                            # s/W^(1/3)
    # canyon law scaled by wall continuity sqrt(rho) = b/(b+s)
    canyon = np.sqrt(rho) * (height / swidth) * (W13 / swidth - 1)

    pred_P = pred_I = np.nan
    for target in ['RadiusP', 'RadiusI']:
        key = (det, target)
        if key not in conv_coeffs:
            continue
        c = conv_coeffs[key]
        switch = rho * (pi2 - c['a'])             # density switch term
        Z = c['C0'] + c['C1'] * pi2 + c['C2'] * switch + c['C3'] * canyon
        val = W13 * Z

        if target == 'RadiusP':
            pred_P = float(val)
        else:
            pred_I = float(val)
    return pred_P, pred_I


def predict_z_urban_per_Z(z_free, weight, rho, height, det, z_coeffs):
    """Predict MaxR_P and MaxR_I for a single (config, Z) pair."""
    W_third = weight ** (1 / 3)

    # Pressure
    key_P = (det, 'Pressure')
    if key_P in z_coeffs:
        c = z_coeffs[key_P]
        Z_urban_P = z_free ** c['m'] * (c['a'] + c['b'] * rho +
                                         c['c'] * height + c['d'] * rho * height)
        pred_maxR_P = Z_urban_P * W_third
    else:
        pred_maxR_P = np.nan

    # Impulse
    key_I = (det, 'Impulse')
    if key_I in z_coeffs:
        c = z_coeffs[key_I]
        Z_urban_I = (z_free ** c['m'] * weight ** c['n'] *
                     (c['a'] + c['b'] * rho + c['c'] * height + c['d'] * rho * height))
        pred_maxR_I = Z_urban_I * W_third
    else:
        pred_maxR_I = np.nan

    return pred_maxR_P, pred_maxR_I


def predict_r_urban_per_Z(z_free, weight, rho, height, det, r_coeffs):
    """Predict R_urban (meters) for a single (config, Z) pair."""
    key_P = (det, 'Pressure')
    if key_P in r_coeffs:
        c = r_coeffs[key_P]
        pred_P = (z_free ** c['m'] * weight ** c['n'] *
                  (c['a'] + c['b'] * rho + c['c'] * height + c['d'] * rho * height))
    else:
        pred_P = np.nan

    key_I = (det, 'Impulse')
    if key_I in r_coeffs:
        c = r_coeffs[key_I]
        pred_I = (z_free ** c['m'] * weight ** c['n'] *
                  (c['a'] + c['b'] * rho + c['c'] * height + c['d'] * rho * height))
    else:
        pred_I = np.nan

    return pred_P, pred_I


# ============================================================
# Plotting
# ============================================================

GROUP_COLORS = {
    1: [0.1, 0.3, 0.7],   # Street
    2: [0.8, 0.2, 0.2],   # Intersection
}

LEGEND_PATCHES = [
    Patch(facecolor=[0.1, 0.3, 0.7], label='Street'),
    Patch(facecolor=[0.8, 0.2, 0.2], label='Intersection'),
]


def _get_group_color(det):
    return GROUP_COLORS[det]


def plot_validation_scatter(actual_P, pred_P, colors_P,
                            actual_I, pred_I, colors_I,
                            title, xlabel, ylabel, out_path):
    """1x2 actual-vs-predicted scatter plot."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor('white')
    fig.suptitle(title, fontsize=14, fontweight='bold')

    for ax, act, prd, cols, panel_title in [
        (axes[0], actual_P, pred_P, colors_P, 'Pressure'),
        (axes[1], actual_I, pred_I, colors_I, 'Impulse'),
    ]:
        valid = ~np.isnan(act) & ~np.isnan(prd)
        if valid.any():
            R2, MAPE = _r2_mape(act[valid], prd[valid])
        else:
            R2, MAPE = np.nan, np.nan

        ax.scatter(act, prd, s=60, c=cols, edgecolors='k', linewidths=0.5)
        lim_max = max(np.nanmax(act), np.nanmax(prd)) * 1.1 if valid.any() else 1
        lim = [0, lim_max]
        ax.plot(lim, lim, 'k--', linewidth=2)
        ax.plot(lim, [v * 1.1 for v in lim], color='gray', linestyle='--', alpha=0.5, label='+/- 10% Error')
        ax.plot(lim, [v * 0.9 for v in lim], color='gray', linestyle='--', alpha=0.5)
        ax.set_xlim(lim); ax.set_ylim(lim)
        ax.set_xlabel(f'Actual {xlabel}', fontsize=11)
        ax.set_ylabel(f'Predicted {ylabel}', fontsize=11)
        ax.set_title(f'{panel_title}\nR\u00b2 = {R2:.3f}, MAPE = {MAPE:.1f}%', fontsize=12)
        ax.set_aspect('equal'); ax.grid(True)
        ax.legend(handles=LEGEND_PATCHES + [plt.Line2D([0], [0], color='gray', linestyle='--', alpha=0.5, label='+/- 10% Error')],
                  loc='upper left', fontsize=8)

    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


# ============================================================
# Main
# ============================================================

def main():
    work_folder   = os.path.dirname(os.path.abspath(__file__))
    parent_folder = os.path.dirname(work_folder)
    output_folder = os.path.join(work_folder, 'check_results')
    os.makedirs(output_folder, exist_ok=True)

    # ---- Load best coefficients ----
    print('Loading best coefficients...')
    conv_coeffs = load_convergence_coefficients(
        os.path.join(work_folder, 'best_convergence_coefficients.csv'))
    z_coeffs = load_nonlinear_coefficients(
        os.path.join(work_folder, 'best_z_urban_coefficients.csv'))
    r_coeffs = load_nonlinear_coefficients(
        os.path.join(work_folder, 'best_r_urban_coefficients.csv'))

    # ---- Load best test split ----
    test_split_path = os.path.join(work_folder, 'best_test_configs.csv')
    if not os.path.exists(test_split_path):
        print(f'ERROR: {test_split_path} not found.')
        print('Run main_ff_compare.py first to generate the best test split.')
        return
    test_configs = set(pd.read_csv(test_split_path)['ConfigName'].values)
    print(f'Loaded {len(test_configs)} test configs from best CV split')

    # ---- Load processed data (filter to test only) ----
    conv_df_all = pd.read_csv(os.path.join(work_folder, 'convergence_table.csv'))
    maxR_df_all = pd.read_csv(os.path.join(work_folder, 'max_radius_per_Z.csv'))

    conv_df = conv_df_all[conv_df_all['ConfigName'].isin(test_configs)].copy()
    maxR_df = maxR_df_all[maxR_df_all['Config'].isin(test_configs)].copy()

    print(f'Validating on {len(conv_df)} test configs, {len(maxR_df)} maxR rows\n')

    # ---- Print best formulas ----
    _print_formulas(conv_coeffs, z_coeffs, r_coeffs)

    # ================================================================
    # Validate convergence radius
    # ================================================================
    print('\n' + '=' * 70)
    print('  CONVERGENCE RADIUS VALIDATION (TEST CONFIGS)')
    print('=' * 70)
    print(f'{"Config":<45s} {"ActP":>7s} {"PrdP":>7s} {"Err%":>6s}  '
          f'{"ActI":>7s} {"PrdI":>7s} {"Err%":>6s}')
    print('-' * 90)

    conv_actual_P, conv_pred_P, conv_colors_P = [], [], []
    conv_actual_I, conv_pred_I, conv_colors_I = [], [], []

    for _, row in conv_df.iterrows():
        cfg = config_parser(row['ConfigName'])
        if cfg is None:
            continue

        pred_P, pred_I = predict_convergence_radius(cfg, conv_coeffs)
        act_P = row['RadiusP']
        act_I = row['RadiusI']

        err_P = 100 * abs(act_P - pred_P) / act_P if act_P != 0 else np.nan
        err_I = 100 * abs(act_I - pred_I) / act_I if act_I != 0 else np.nan

        color = _get_group_color(cfg['det'])

        conv_actual_P.append(act_P); conv_pred_P.append(pred_P)
        conv_colors_P.append(color)
        conv_actual_I.append(act_I); conv_pred_I.append(pred_I)
        conv_colors_I.append(color)

        print(f'{row["ConfigName"]:<45s} '
              f'{act_P:>7.1f} {pred_P:>7.1f} {err_P:>5.1f}%  '
              f'{act_I:>7.1f} {pred_I:>7.1f} {err_I:>5.1f}%')

    act_P_arr = np.array(conv_actual_P)
    prd_P_arr = np.array(conv_pred_P)
    act_I_arr = np.array(conv_actual_I)
    prd_I_arr = np.array(conv_pred_I)

    R2_P, MAPE_P = _r2_mape(act_P_arr, prd_P_arr)
    R2_I, MAPE_I = _r2_mape(act_I_arr, prd_I_arr)
    print(f'\nOverall Convergence Radius:')
    print(f'  Pressure — R2={R2_P:.4f}, MAPE={MAPE_P:.2f}%')
    print(f'  Impulse  — R2={R2_I:.4f}, MAPE={MAPE_I:.2f}%')

    plot_validation_scatter(
        act_P_arr, prd_P_arr, np.array(conv_colors_P),
        act_I_arr, prd_I_arr, np.array(conv_colors_I),
        'Convergence Radius — Test Configs',
        'Radius [m]', 'Radius [m]',
        os.path.join(output_folder, 'validation_convergence_radius.png'))
    print('Saved: validation_convergence_radius.png')

    # ================================================================
    # Validate Z_urban and R_urban
    # ================================================================
    # Parse geometry for each maxR row
    geo_cache = {}
    for cfg_name in maxR_df['Config'].unique():
        cfg = config_parser(cfg_name)
        if cfg:
            rho = cfg['bsize'] ** 2 / (cfg['bsize'] + cfg['swidth']) ** 2
            geo_cache[cfg_name] = {
                'det': cfg['det'], 'weight': cfg['weight'],
                'height': cfg['height'], 'rho': rho,
            }

    # Merge convergence radii
    conv_lookup = {}
    for _, row in conv_df.iterrows():
        conv_lookup[row['ConfigName']] = (row['RadiusP'], row['RadiusI'])

    zu_actual_P, zu_pred_P, zu_colors_P = [], [], []
    zu_actual_I, zu_pred_I, zu_colors_I = [], [], []
    ru_actual_P, ru_pred_P, ru_colors_P = [], [], []
    ru_actual_I, ru_pred_I, ru_colors_I = [], [], []

    for _, row in maxR_df.iterrows():
        cfg_name = row['Config']
        if cfg_name not in geo_cache:
            continue
        geo = geo_cache[cfg_name]
        conv_radii = conv_lookup.get(cfg_name, (np.nan, np.nan))

        z_val = float(row['Z'])
        maxR_P = row['MaxR_P']
        maxR_I = row['MaxR_I']

        # Filter urban points only
        beyond_P = np.isnan(maxR_P) or maxR_P >= conv_radii[0]
        beyond_I = np.isnan(maxR_I) or maxR_I >= conv_radii[1]

        color = _get_group_color(geo['det'])
        W_third = geo['weight'] ** (1/3)

        # Z_urban predictions
        pred_mR_P, pred_mR_I = predict_z_urban_per_Z(
            z_val, geo['weight'], geo['rho'], geo['height'], geo['det'], z_coeffs)

        # R_urban predictions
        pred_rR_P, pred_rR_I = predict_r_urban_per_Z(
            z_val, geo['weight'], geo['rho'], geo['height'], geo['det'], r_coeffs)

        if not beyond_P and np.isfinite(maxR_P):
            if np.isfinite(pred_mR_P):
                zu_actual_P.append(maxR_P / W_third)
                zu_pred_P.append(pred_mR_P / W_third)
                zu_colors_P.append(color)
            if np.isfinite(pred_rR_P):
                ru_actual_P.append(maxR_P)
                ru_pred_P.append(pred_rR_P)
                ru_colors_P.append(color)

        if not beyond_I and np.isfinite(maxR_I):
            if np.isfinite(pred_mR_I):
                zu_actual_I.append(maxR_I / W_third)
                zu_pred_I.append(pred_mR_I / W_third)
                zu_colors_I.append(color)
            if np.isfinite(pred_rR_I):
                ru_actual_I.append(maxR_I)
                ru_pred_I.append(pred_rR_I)
                ru_colors_I.append(color)

    # ---- Z_urban summary ----
    print('\n' + '=' * 60)
    print('  Z_URBAN VALIDATION (TEST CONFIGS)')
    print('=' * 60)
    zu_act_P = np.array(zu_actual_P); zu_prd_P = np.array(zu_pred_P)
    zu_act_I = np.array(zu_actual_I); zu_prd_I = np.array(zu_pred_I)
    if len(zu_act_P) > 1:
        R2, MAPE = _r2_mape(zu_act_P, zu_prd_P)
        print(f'  Pressure — n={len(zu_act_P)}, R2={R2:.4f}, MAPE={MAPE:.2f}%')
    if len(zu_act_I) > 1:
        R2, MAPE = _r2_mape(zu_act_I, zu_prd_I)
        print(f'  Impulse  — n={len(zu_act_I)}, R2={R2:.4f}, MAPE={MAPE:.2f}%')

    plot_validation_scatter(
        zu_act_P, zu_prd_P, np.array(zu_colors_P) if zu_colors_P else np.empty((0, 3)),
        zu_act_I, zu_prd_I, np.array(zu_colors_I) if zu_colors_I else np.empty((0, 3)),
        'Z_urban Validation — Test Configs',
        'Z_urban [m/kg^(1/3)]', 'Z_urban [m/kg^(1/3)]',
        os.path.join(output_folder, 'validation_z_urban.png'))
    print('Saved: validation_z_urban.png')

    # ---- R_urban summary ----
    print('\n' + '=' * 60)
    print('  R_URBAN VALIDATION (TEST CONFIGS)')
    print('=' * 60)
    ru_act_P = np.array(ru_actual_P); ru_prd_P = np.array(ru_pred_P)
    ru_act_I = np.array(ru_actual_I); ru_prd_I = np.array(ru_pred_I)
    if len(ru_act_P) > 1:
        R2, MAPE = _r2_mape(ru_act_P, ru_prd_P)
        print(f'  Pressure — n={len(ru_act_P)}, R2={R2:.4f}, MAPE={MAPE:.2f}%')
    if len(ru_act_I) > 1:
        R2, MAPE = _r2_mape(ru_act_I, ru_prd_I)
        print(f'  Impulse  — n={len(ru_act_I)}, R2={R2:.4f}, MAPE={MAPE:.2f}%')

    plot_validation_scatter(
        ru_act_P, ru_prd_P, np.array(ru_colors_P) if ru_colors_P else np.empty((0, 3)),
        ru_act_I, ru_prd_I, np.array(ru_colors_I) if ru_colors_I else np.empty((0, 3)),
        'R_urban Validation — Test Configs',
        'R_urban [m]', 'R_urban [m]',
        os.path.join(output_folder, 'validation_r_urban.png'))
    print('Saved: validation_r_urban.png')

    # ---- Save validation comparison CSV ----
    comp_rows = []
    for _, row in conv_df.iterrows():
        cfg = config_parser(row['ConfigName'])
        if cfg is None:
            continue
        pred_P, pred_I = predict_convergence_radius(cfg, conv_coeffs)
        comp_rows.append({
            'Config': row['ConfigName'],
            'Variable': 'RadiusP',
            'Actual': row['RadiusP'],
            'Predicted': pred_P,
            'Error_pct': 100 * abs(row['RadiusP'] - pred_P) / row['RadiusP'],
        })
        comp_rows.append({
            'Config': row['ConfigName'],
            'Variable': 'RadiusI',
            'Actual': row['RadiusI'],
            'Predicted': pred_I,
            'Error_pct': 100 * abs(row['RadiusI'] - pred_I) / row['RadiusI'],
        })

    comp_df = pd.DataFrame(comp_rows)
    comp_out = os.path.join(output_folder, 'validation_comparison.csv')
    comp_df.to_csv(comp_out, index=False)
    print(f'\nSaved: {comp_out}')

    print('\n' + '=' * 40)
    print('  CHECK FORMULAS DONE')
    print('=' * 40)


def _print_formulas(conv_coeffs, z_coeffs, r_coeffs):
    """Print all best formulas in readable form."""
    det_names = {1: 'Street (det=1)', 2: 'Intersection (det=2)'}

    print('=' * 70)
    print('  BEST CONVERGENCE RADIUS FORMULAS  (Buckingham Pi additive model)')
    print('  Z = R/W^(1/3) = C0 + C1*(s/W^(1/3)) + C2*rho*(s/W^(1/3) - a)')
    print('                     + C3*sqrt(rho)*(H/s)*(W^(1/3)/s - 1)')
    print('  a = 1 (street) / 2 (intersection): density-switch threshold')
    print('  where rho = b^2/(b+s)^2,  W^(1/3) is Hopkinson length scale')
    print('  Canyon law: H/s effect flips sign at s = W^(1/3) (channeling <-> blocking)')
    print('  sqrt(rho) = b/(b+s) = canyon wall continuity (cross-street gaps leak)')
    print('  Groups: by det only (2 formulas per target)')
    print('=' * 70)

    for target in ['RadiusP', 'RadiusI']:
        print(f'\n--- {target} ---')
        for (det, tgt), c in sorted((k, v) for k, v in conv_coeffs.items() if k[1] == target):
            loc = det_names.get(det, f'det={det}')
            print(f'  {loc}:')
            if c['has_H_term']:
                print(f'    Z = {c["C0"]:+.4f} + {c["C1"]:+.4f}*(s/W^1/3)'
                      f' + {c["C2"]:+.4f}*rho*(s/W^1/3 - {c["a"]:g})'
                      f' + {c["C3"]:+.4f}*sqrt(rho)*(H/s)*(W^1/3/s - 1)')
            else:
                print(f'    Z = {c["C0"]:+.4f} + {c["C1"]:+.4f}*(s/W^1/3)'
                      f' + {c["C2"]:+.4f}*rho*(s/W^1/3 - {c["a"]:g})  [H=0, canyon term omitted]')
            print(f'    R = W^(1/3) * Z')

    print(f'\n{"="*70}')
    print('  BEST Z_URBAN FORMULAS')
    print('  Pressure: Z_urban = Z_free^m * (a + b*rho + c*H + d*rho*H)')
    print('  Impulse:  Z_urban = Z_free^m * W^n * (a + b*rho + c*H + d*rho*H)')
    print('  MaxR = Z_urban * W^(1/3)')
    print('  Groups: by det only (2 formulas per target)')
    print('=' * 70)

    for (det, target), c in sorted(z_coeffs.items()):
        if target == 'Pressure':
            print(f'\n  {det_names[det]} / {target}:')
            print(f'    Z_urban = Z_free^{c["m"]:.4f} * '
                  f'({c["a"]:.4f} {c["b"]:+.4f}*rho {c["c"]:+.6f}*H {c["d"]:+.6f}*rho*H)')
        else:
            print(f'  {det_names[det]} / {target}:')
            print(f'    Z_urban = Z_free^{c["m"]:.4f} * W^{c["n"]:.4f} * '
                  f'({c["a"]:.4f} {c["b"]:+.4f}*rho {c["c"]:+.6f}*H {c["d"]:+.6f}*rho*H)')

    print(f'\n{"="*70}')
    print('  BEST R_URBAN FORMULAS')
    print('  R_urban = Z_free^m * W^n * (a + b*rho + c*H + d*rho*H)')
    print('  Groups: by det only (2 formulas per target)')
    print('=' * 70)

    for (det, target), c in sorted(r_coeffs.items()):
        print(f'\n  {det_names[det]} / {target}:')
        print(f'    R_urban = Z_free^{c["m"]:.4f} * W^{c["n"]:.4f} * '
              f'({c["a"]:.4f} {c["b"]:+.4f}*rho {c["c"]:+.6f}*H {c["d"]:+.6f}*rho*H)')


if __name__ == '__main__':
    main()
