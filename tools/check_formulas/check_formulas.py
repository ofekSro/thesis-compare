"""Validation check: load best CV coefficients, apply to the best test split,
show per-config errors and overall metrics.

Uses the saved coefficient CSVs from the cross-validation run
(best_convergence_coefficients.csv, best_z_urban_coefficients.csv) and
validates against convergence_table.csv and max_radius_per_Z.csv.
R_urban is validated as the canonical derivation W^(1/3) * Z_urban.

Usage:
    python tools\\check_formulas\\check_formulas.py
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.geometry import area_density
from blastlib.regression.stats import r2_mape


# ============================================================
# Load best coefficients from CSVs
# ============================================================

def load_convergence_coefficients(csv_path):
    """Load convergence radius coefficients (superset CSV, both formulas).

    Returns dict {(det, target): coef_dict}. The 'formula' key selects how
    to apply the row; both formulas share R = W^(1/3) * Z:

    RadiusP ('additive'): keys C0, C1, C2, C3, a, has_H_term
        Z = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
               + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1)
    RadiusI ('log'): keys A, k
        Z = A * Pi^(k*ln(W^1/3/s)),  Pi = H/(s*rho)
    """
    df = pd.read_csv(csv_path)
    coeffs = {}
    for _, row in df.iterrows():
        det = int(row['Det'])
        target = row['Target']
        formula = row['Formula'] if 'Formula' in df.columns else 'additive'
        if formula == 'log':
            coeffs[(det, target)] = {
                'formula': 'log',
                'A': float(row['A']),
                'k': float(row['k']),
            }
        else:
            coeffs[(det, target)] = {
                'formula':    'additive',
                'C0':         float(row['C0']),
                'C1':         float(row['C1_sW13']),
                'C2':         float(row['C2_switch']),
                'C3':         float(row['C3_canyon']),
                'a':          float(row['a_thresh']),
                'has_H_term': bool(int(row['has_H_term'])),
            }
    return coeffs


def load_nonlinear_coefficients(csv_path):
    """Load Z_urban power-law coefficients.

    Returns dict {(det, target): {'C', 'm', 'p', 'q', 'r', 'zf_min'}}.
    Formula: Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r,
    valid for Z_free >= zf_min.
    """
    df = pd.read_csv(csv_path)
    coeffs = {}
    for _, row in df.iterrows():
        det = int(row['Det'])
        target = row['Target']
        coeffs[(det, target)] = {
            'C': float(row['C']), 'm': float(row['m']),
            'p': float(row['p_rho']), 'q': float(row['q_HoverS']),
            'r': float(row['r_sW13']), 'zf_min': float(row['Zf_min']),
        }
    return coeffs


# ============================================================
# Prediction functions
# ============================================================

def predict_convergence_radius(cfg, conv_coeffs):
    """Predict convergence radii for a single config.

    Both targets share R = W^(1/3) * Z:
      RadiusP (additive): Z = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                                 + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1)
      RadiusI (log):      Z = A * Pi^(k*ln(W^1/3/s)),  Pi = H/(s*rho)
    """
    bsize  = cfg['bsize']
    swidth = cfg['swidth']
    height = cfg['height']
    weight = cfg['weight']
    det    = cfg['det']

    rho = area_density(bsize, swidth)
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
        if c['formula'] == 'log':
            if height <= 0:
                continue                          # Pi requires H > 0
            pi_conf = height / (swidth * rho)
            Z = c['A'] * pi_conf ** (c['k'] * np.log(W13 / swidth))
        else:
            switch = rho * (pi2 - c['a'])         # density switch term
            Z = c['C0'] + c['C1'] * pi2 + c['C2'] * switch + c['C3'] * canyon
        val = W13 * Z

        if target == 'RadiusP':
            pred_P = float(val)
        else:
            pred_I = float(val)
    return pred_P, pred_I


def predict_z_urban_per_Z(z_free, weight, rho, height, swidth, det, z_coeffs):
    """Predict MaxR_P and MaxR_I [m] for a single (config, Z) pair.

    Canonical form: MaxR = W^(1/3) * Z_urban,
      Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r
    Returns NaN outside the validity domain (z_free < zf_min).
    R_urban needs no separate predictor — it IS this value in metres.
    """
    W_third = weight ** (1 / 3)
    Hs = height / swidth

    preds = {}
    for target in ['Pressure', 'Impulse']:
        key = (det, target)
        if key not in z_coeffs:
            preds[target] = np.nan
            continue
        c = z_coeffs[key]
        if z_free < c['zf_min']:
            preds[target] = np.nan
            continue
        Z_urban = (c['C'] * z_free ** c['m'] * rho ** c['p']
                   * Hs ** c['q'] * (swidth / W_third) ** c['r'])
        preds[target] = Z_urban * W_third

    return preds['Pressure'], preds['Impulse']


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
            R2, MAPE = r2_mape(act[valid], prd[valid])
        else:
            R2, MAPE = np.nan, np.nan

        ax.scatter(act, prd, s=60, c=cols, edgecolors='k', linewidths=0.5)
        lim_max = max(np.nanmax(act), np.nanmax(prd)) * 1.1 if valid.any() else 1
        lim = [0, lim_max]
        ax.plot(lim, lim, 'k--', linewidth=2)
        ax.plot(lim, [v * 1.1 for v in lim], color='gray', linestyle='--', alpha=0.5)
        ax.plot(lim, [v * 0.9 for v in lim], color='gray', linestyle='--', alpha=0.5)
        ax.set_xlim(lim); ax.set_ylim(lim)
        ax.set_xlabel(f'Actual {xlabel}', fontsize=11)
        ax.set_ylabel(f'Predicted {ylabel}', fontsize=11)
        ax.set_title(f'{panel_title}\nR² = {R2:.3f}, MAPE = {MAPE:.1f}%', fontsize=12)
        ax.set_aspect('equal'); ax.grid(True)
        ax.legend(handles=LEGEND_PATCHES + [
                      plt.Line2D([0], [0], color='gray', linestyle='--',
                                 alpha=0.5, label='+/- 10% Error')],
                  loc='upper left', fontsize=8)

    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def _print_formulas(conv_coeffs, z_coeffs, progress=print):
    """Print all best formulas in readable form."""
    det_names = {1: 'Street (det=1)', 2: 'Intersection (det=2)'}

    progress('=' * 70)
    progress('  BEST CONVERGENCE RADIUS FORMULAS    R = W^(1/3) * Z')
    progress('  RadiusP (Buckingham Pi additive model):')
    progress('    Z = C0 + C1*(s/W^(1/3)) + C2*rho*(s/W^(1/3) - a)')
    progress('           + C3*sqrt(rho)*(H/s)*(W^(1/3)/s - 1)')
    progress('    a = 1 (street) / 2 (intersection): density-switch threshold')
    progress('    Canyon law: H/s effect flips sign at s = W^(1/3) (channeling <-> blocking)')
    progress('    sqrt(rho) = b/(b+s) = canyon wall continuity (cross-street gaps leak)')
    progress('  RadiusI (log-space Pi model):')
    progress('    Z = A * Pi^(k*ln(W^(1/3)/s)),  Pi = H/(s*rho)')
    progress('  where rho = b^2/(b+s)^2,  W^(1/3) is Hopkinson length scale')
    progress('  Groups: by det only (2 formulas per target)')
    progress('=' * 70)

    for target in ['RadiusP', 'RadiusI']:
        progress(f'\n--- {target} ---')
        for (det, tgt), c in sorted((k, v) for k, v in conv_coeffs.items() if k[1] == target):
            loc = det_names.get(det, f'det={det}')
            progress(f'  {loc}:')
            if c['formula'] == 'log':
                progress(f'    Z = {c["A"]:.4f} * Pi^({c["k"]:+.4f}*ln(W^1/3/s))')
            elif c['has_H_term']:
                progress(f'    Z = {c["C0"]:+.4f} + {c["C1"]:+.4f}*(s/W^1/3)'
                         f' + {c["C2"]:+.4f}*rho*(s/W^1/3 - {c["a"]:g})'
                         f' + {c["C3"]:+.4f}*sqrt(rho)*(H/s)*(W^1/3/s - 1)')
            else:
                progress(f'    Z = {c["C0"]:+.4f} + {c["C1"]:+.4f}*(s/W^1/3)'
                         f' + {c["C2"]:+.4f}*rho*(s/W^1/3 - {c["a"]:g})'
                         f'  [H=0, canyon term omitted]')
            progress(f'    R = W^(1/3) * Z')

    progress(f'\n{"="*70}')
    progress('  BEST Z_URBAN FORMULAS    MaxR = W^(1/3) * Z_urban')
    progress('  Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r')
    progress('  All factors are Pi groups; W enters only through W^(1/3).')
    progress('  R_urban = W^(1/3) * Z_urban  (canonical — not separately fitted)')
    progress('  Validity: Z_free >= Zf_min')
    progress('  Physical closure: predictions clipped to Z_free <= Z_urban <= Z_conv')
    progress('  (Z_conv from the convergence formulas); identity beyond Z_conv.')
    progress('  Groups: by det only (2 formulas per target)')
    progress('=' * 70)

    for target in ['Pressure', 'Impulse']:
        for det in [1, 2]:
            c = z_coeffs.get((det, target))
            if c is None:
                continue
            progress(f'\n  {det_names[det]} / {target}:')
            progress(f'    Z_urban = {c["C"]:.4f} * Z_free^{c["m"]:.4f}'
                     f' * rho^{c["p"]:+.4f} * (H/s)^{c["q"]:+.4f}'
                     f' * (s/W^1/3)^{c["r"]:+.4f}')
            progress(f'    MaxR = W^(1/3) * Z_urban    [Z_free >= {c["zf_min"]:g}]')


# ============================================================
# Main
# ============================================================

def main(*, tables_dir=None, out_dir=None, progress=print):
    """Validate the saved coefficients against the best CV test split.

    Returns dict of summary metrics, or None if required inputs are missing.
    """
    tables_dir = paths.resolve(tables_dir, paths.TABLES_DIR)
    out_dir = paths.ensure_dir(paths.resolve(out_dir, paths.CHECK_RESULTS_DIR))

    # ---- Load best coefficients ----
    progress('Loading best coefficients...')
    conv_coeffs = load_convergence_coefficients(
        tables_dir / 'best_convergence_coefficients.csv')
    z_coeffs = load_nonlinear_coefficients(
        tables_dir / 'best_z_urban_coefficients.csv')

    # ---- Load best test split ----
    test_split_path = tables_dir / 'best_test_configs.csv'
    if not test_split_path.exists():
        progress(f'ERROR: {test_split_path} not found.')
        progress('Run run_analysis.py first to generate the best test split.')
        return None
    test_configs = set(pd.read_csv(test_split_path)['ConfigName'].values)
    progress(f'Loaded {len(test_configs)} test configs from best CV split')

    # ---- Load processed data (filter to test only) ----
    conv_df_all = pd.read_csv(tables_dir / 'convergence_table.csv')
    maxR_df_all = pd.read_csv(tables_dir / 'max_radius_per_Z.csv')

    conv_df = conv_df_all[conv_df_all['ConfigName'].isin(test_configs)].copy()
    maxR_df = maxR_df_all[maxR_df_all['Config'].isin(test_configs)].copy()

    progress(f'Validating on {len(conv_df)} test configs, {len(maxR_df)} maxR rows\n')

    # ---- Print best formulas ----
    _print_formulas(conv_coeffs, z_coeffs, progress=progress)

    # ================================================================
    # Validate convergence radius
    # ================================================================
    progress('\n' + '=' * 70)
    progress('  CONVERGENCE RADIUS VALIDATION (TEST CONFIGS)')
    progress('=' * 70)
    progress(f'{"Config":<45s} {"ActP":>7s} {"PrdP":>7s} {"Err%":>6s}  '
             f'{"ActI":>7s} {"PrdI":>7s} {"Err%":>6s}')
    progress('-' * 90)

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

        progress(f'{row["ConfigName"]:<45s} '
                 f'{act_P:>7.1f} {pred_P:>7.1f} {err_P:>5.1f}%  '
                 f'{act_I:>7.1f} {pred_I:>7.1f} {err_I:>5.1f}%')

    act_P_arr = np.array(conv_actual_P)
    prd_P_arr = np.array(conv_pred_P)
    act_I_arr = np.array(conv_actual_I)
    prd_I_arr = np.array(conv_pred_I)

    R2_P, MAPE_P = r2_mape(act_P_arr, prd_P_arr)
    R2_I, MAPE_I = r2_mape(act_I_arr, prd_I_arr)
    progress(f'\nOverall Convergence Radius:')
    progress(f'  Pressure — R2={R2_P:.4f}, MAPE={MAPE_P:.2f}%')
    progress(f'  Impulse  — R2={R2_I:.4f}, MAPE={MAPE_I:.2f}%')

    plot_validation_scatter(
        act_P_arr, prd_P_arr, np.array(conv_colors_P),
        act_I_arr, prd_I_arr, np.array(conv_colors_I),
        'Convergence Radius — Test Configs',
        'Radius [m]', 'Radius [m]',
        out_dir / 'validation_convergence_radius.png')
    progress('Saved: validation_convergence_radius.png')

    # ================================================================
    # Validate Z_urban (and derived R_urban = W^(1/3) * Z_urban)
    # ================================================================
    # Parse geometry for each maxR row; cache the PREDICTED convergence
    # radii per config — Z_urban predictions are clipped to them
    # (physical closure: MaxR cannot exceed R_conv).
    geo_cache = {}
    conv_pred_cache = {}
    for cfg_name in maxR_df['Config'].unique():
        cfg = config_parser(cfg_name)
        if cfg:
            geo_cache[cfg_name] = {
                'det': cfg['det'], 'weight': cfg['weight'],
                'height': cfg['height'], 'swidth': cfg['swidth'],
                'rho': area_density(cfg['bsize'], cfg['swidth']),
            }
            conv_pred_cache[cfg_name] = predict_convergence_radius(cfg, conv_coeffs)

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

        # Z_urban predictions (already in metres: W^(1/3) * Z_urban)
        pred_mR_P, pred_mR_I = predict_z_urban_per_Z(
            z_val, geo['weight'], geo['rho'], geo['height'], geo['swidth'],
            geo['det'], z_coeffs)

        # Physical closure: clip to [Z_free*W^(1/3), R_conv_predicted]
        # (urban = free-field beyond the convergence radius)
        conv_pred_P_val, conv_pred_I_val = conv_pred_cache.get(cfg_name, (np.nan, np.nan))
        R_ff = z_val * W_third
        if np.isfinite(pred_mR_P):
            if np.isfinite(conv_pred_P_val):
                pred_mR_P = min(pred_mR_P, conv_pred_P_val)
            pred_mR_P = max(pred_mR_P, R_ff)
        if np.isfinite(pred_mR_I):
            if np.isfinite(conv_pred_I_val):
                pred_mR_I = min(pred_mR_I, conv_pred_I_val)
            pred_mR_I = max(pred_mR_I, R_ff)

        # R_urban = W^(1/3) * Z_urban — the canonical derivation, same value
        pred_rR_P, pred_rR_I = pred_mR_P, pred_mR_I

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
    progress('\n' + '=' * 60)
    progress('  Z_URBAN VALIDATION (TEST CONFIGS)')
    progress('=' * 60)
    zu_act_P = np.array(zu_actual_P); zu_prd_P = np.array(zu_pred_P)
    zu_act_I = np.array(zu_actual_I); zu_prd_I = np.array(zu_pred_I)
    if len(zu_act_P) > 1:
        R2, MAPE = r2_mape(zu_act_P, zu_prd_P)
        progress(f'  Pressure — n={len(zu_act_P)}, R2={R2:.4f}, MAPE={MAPE:.2f}%')
    if len(zu_act_I) > 1:
        R2, MAPE = r2_mape(zu_act_I, zu_prd_I)
        progress(f'  Impulse  — n={len(zu_act_I)}, R2={R2:.4f}, MAPE={MAPE:.2f}%')

    plot_validation_scatter(
        zu_act_P, zu_prd_P, np.array(zu_colors_P) if zu_colors_P else np.empty((0, 3)),
        zu_act_I, zu_prd_I, np.array(zu_colors_I) if zu_colors_I else np.empty((0, 3)),
        'Z_urban Validation — Test Configs',
        'Z_urban [m/kg^(1/3)]', 'Z_urban [m/kg^(1/3)]',
        out_dir / 'validation_z_urban.png')
    progress('Saved: validation_z_urban.png')

    # ---- R_urban summary (derived: R_urban = W^(1/3) * Z_urban) ----
    progress('\n' + '=' * 60)
    progress('  R_URBAN VALIDATION (TEST CONFIGS)')
    progress('  (derived canonically: R_urban = W^(1/3) * Z_urban)')
    progress('=' * 60)
    ru_act_P = np.array(ru_actual_P); ru_prd_P = np.array(ru_pred_P)
    ru_act_I = np.array(ru_actual_I); ru_prd_I = np.array(ru_pred_I)
    if len(ru_act_P) > 1:
        R2, MAPE = r2_mape(ru_act_P, ru_prd_P)
        progress(f'  Pressure — n={len(ru_act_P)}, R2={R2:.4f}, MAPE={MAPE:.2f}%')
    if len(ru_act_I) > 1:
        R2, MAPE = r2_mape(ru_act_I, ru_prd_I)
        progress(f'  Impulse  — n={len(ru_act_I)}, R2={R2:.4f}, MAPE={MAPE:.2f}%')

    plot_validation_scatter(
        ru_act_P, ru_prd_P, np.array(ru_colors_P) if ru_colors_P else np.empty((0, 3)),
        ru_act_I, ru_prd_I, np.array(ru_colors_I) if ru_colors_I else np.empty((0, 3)),
        'R_urban Validation — Test Configs',
        'R_urban [m]', 'R_urban [m]',
        out_dir / 'validation_r_urban.png')
    progress('Saved: validation_r_urban.png')

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
    comp_out = out_dir / 'validation_comparison.csv'
    comp_df.to_csv(comp_out, index=False)
    progress(f'\nSaved: {comp_out}')

    progress('\n' + '=' * 40)
    progress('  CHECK FORMULAS DONE')
    progress('=' * 40)

    return {
        'conv_R2_P': R2_P, 'conv_MAPE_P': MAPE_P,
        'conv_R2_I': R2_I, 'conv_MAPE_I': MAPE_I,
        'n_test_configs': len(conv_df),
    }


def cli(argv=None):
    p = argparse.ArgumentParser(description='Validate saved formula coefficients.')
    p.add_argument('--tables-dir', default=None, help='Folder with the coefficient/table CSVs.')
    p.add_argument('--out-dir', default=None, help='Output folder for validation results.')
    args = p.parse_args(argv)
    return main(tables_dir=args.tables_dir, out_dir=args.out_dir)


if __name__ == '__main__':
    cli()
