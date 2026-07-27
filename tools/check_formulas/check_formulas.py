"""Validation check: load best CV coefficients, apply to the best test split,
show per-config errors and overall metrics.

Uses the saved coeffi
cient CSVs from the cross-validation run
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
from blastlib.processing.radius_estimator import resolve_estimator, VALID_METHODS
from blastlib.regression.stats import r2_mape
from blastlib.regression.z_urban import (prepare_maxR_data, z_urban_valid_mask,
                                         attenuation_regime, ATTENUATION_KEYS)


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
    RadiusI ('power'): keys A, p, q, r
        Z = A * rho^p * (H/s)^q * (s/W^(1/3))^r
    """
    df = pd.read_csv(csv_path)
    coeffs = {}
    for _, row in df.iterrows():
        det = int(row['Det'])
        target = row['Target']
        formula = row['Formula'] if 'Formula' in df.columns else 'additive'
        if formula == 'power':
            coeffs[(det, target)] = {
                'formula': 'power',
                'A': float(row['A']),
                'p': float(row['p_rho']),
                'q': float(row['q_HoverS']),
                'r': float(row['r_sW13']),
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
    """Load Z_urban coefficients (superset CSV, all four formulas).

    Selected by the Formula column:
      'range_switch'    ln Lambda = C0 + C1*[(Pi2 - A)/Z_free - ln(Pi2)]
                                       / (Pi2/(H/s) + B)       [pressure]
                        A (= A_switch) is stored POSITIVE: the sign-flip
                        threshold itself, sign flip at Pi2 = A.
      'canyon_trap'     ln Lambda = C0 + C1*rho*(sqrt(H/s) - C2*rho)
                                       / (H/s + C3*sqrt(Pi2))  [impulse]
      'power'           Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^1/3)^r
      'lambda_regime'   Lambda  = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                                     + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1)
                                     + C4*ln(Z_free)
                        Z_urban = Lambda * Z_free
                        One coefficient set per regime, keyed 'amp' / 'att' /
                        'pooled'; ATTENUATION_CRITERION selects between them.
    All valid for Z_free >= zf_min; Pi2 = s/W^(1/3).
    """
    df = pd.read_csv(csv_path)
    coeffs = {}
    for _, row in df.iterrows():
        det = int(row['Det'])
        target = row['Target']
        formula = row['Formula'] if 'Formula' in df.columns else 'power'
        if formula == 'range_switch':
            coeffs[(det, target)] = {
                'formula': 'range_switch',
                'C0': float(row['C0']), 'C1': float(row['C1_amp']),
                'A': float(row['A_switch']), 'B': float(row['B_open']),
                'zf_min': float(row['Zf_min']),
            }
        elif formula == 'canyon_trap':
            coeffs[(det, target)] = {
                'formula': 'canyon_trap',
                'C0': float(row['C0']), 'C1': float(row['C1_amp']),
                'C2': float(row['C2_self']), 'C3': float(row['C3_dilute']),
                'zf_min': float(row['Zf_min']),
            }
        elif formula == 'lambda_regime':
            regime = str(row.get('Regime', 'pooled')) or 'pooled'
            entry = coeffs.setdefault((det, target),
                                      {'formula': 'lambda_regime',
                                       'zf_min': float(row['Zf_min'])})
            if regime == 'criterion':
                entry['criterion'] = {k: float(row[f'K_{k}'])
                                      for k in ATTENUATION_KEYS}
                continue
            entry[{'amplification': 'amp', 'attenuation': 'att'}
                  .get(regime, 'pooled')] = {
                'C0': float(row['C0']), 'C1': float(row['C1_sW13']),
                'C2': float(row['C2_switch']), 'C3': float(row['C3_canyon']),
                'C4': float(row['C4_lnZf']), 'a': float(row['a_thresh']),
            }
        else:
            coeffs[(det, target)] = {
                'formula': 'power',
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
      RadiusI (power):    Z = A * rho^p * (H/s)^q * (s/W^(1/3))^r
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
        if c['formula'] == 'power':
            if height <= 0 or rho <= 0:
                continue                          # both are logged in the fit
            Z = (c['A'] * rho ** c['p'] * (height / swidth) ** c['q']
                 * (swidth / W13) ** c['r'])
        else:
            switch = rho * (pi2 - c['a'])         # density switch term
            Z = c['C0'] + c['C1'] * pi2 + c['C2'] * switch + c['C3'] * canyon
        val = W13 * Z

        if target == 'RadiusP':
            pred_P = float(val)
        else:
            pred_I = float(val)
    return pred_P, pred_I


def predict_z_urban_per_Z(z_free, weight, rho, height, swidth, det, z_coeffs,
                          pred_Rconv_P=np.nan):
    """Predict MaxR_P and MaxR_I [m] for a single (config, Z) pair.

    Canonical form: MaxR = W^(1/3) * Z_urban. Pressure uses the Lambda
    (amplification-factor) form, impulse the power law — see
    load_nonlinear_coefficients.
    Returns NaN outside the validity domain (z_free < zf_min).
    R_urban needs no separate predictor — it IS this value in metres.
    """
    W_third = weight ** (1 / 3)
    Hs = height / swidth
    pi2_val = swidth / W_third

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
        if c.get('formula') == 'range_switch':
            ln_lam = (c['C0'] + c['C1']
                      * ((pi2_val - c['A']) / z_free - np.log(pi2_val))
                      / (pi2_val / Hs + c['B']))
            Z_urban = np.exp(ln_lam) * z_free
        elif c.get('formula') == 'canyon_trap':
            ln_lam = (c['C0'] + c['C1'] * rho * (np.sqrt(Hs) - c['C2'] * rho)
                      / (Hs + c['C3'] * np.sqrt(pi2_val)))
            Z_urban = np.exp(ln_lam) * z_free
        elif c.get('formula') == 'lambda_regime':
            # xi uses the PREDICTED convergence radius, never the measured one.
            if not np.isfinite(pred_Rconv_P) or pred_Rconv_P <= 0:
                preds[target] = np.nan
                continue
            xi = z_free / (pred_Rconv_P / W_third)
            att = attenuation_regime(np.array([z_free]), np.array([rho]),
                                     np.array([height]), np.array([swidth]),
                                     np.array([W_third]), np.array([xi]),
                                     c.get('criterion'))[0]
            cc = c.get('att' if att else 'amp') or c.get('pooled')
            if cc is None:
                preds[target] = np.nan
                continue
            pi2 = swidth / W_third
            lam = (cc['C0'] + cc['C1'] * pi2
                   + cc['C2'] * rho * (pi2 - cc['a'])
                   + cc['C3'] * np.sqrt(rho) * Hs * (W_third / swidth - 1.0)
                   + cc['C4'] * np.log(z_free))
            Z_urban = lam * z_free
        else:
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
    progress('  RadiusI (Pi power law):')
    progress('    Z = A * rho^p * (H/s)^q * (s/W^(1/3))^r')
    progress('  where rho = b^2/(b+s)^2,  W^(1/3) is Hopkinson length scale')
    progress('  Groups: by det only (2 formulas per target)')
    progress('=' * 70)

    for target in ['RadiusP', 'RadiusI']:
        progress(f'\n--- {target} ---')
        for (det, tgt), c in sorted((k, v) for k, v in conv_coeffs.items() if k[1] == target):
            loc = det_names.get(det, f'det={det}')
            progress(f'  {loc}:')
            if c['formula'] == 'power':
                progress(f'    Z = {c["A"]:.4f} * rho^({c["p"]:+.4f})'
                         f' * (H/s)^({c["q"]:+.4f})'
                         f' * (s/W^1/3)^({c["r"]:+.4f})')
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
    progress('  Forms are read from the Formula column of the coefficient CSV:')
    progress('    range_switch (P): ln Lambda = C0 + C1*[(Pi2-A)/Zf - ln Pi2]')
    progress('                                     / (Pi2/(H/s) + B)')
    progress('      A stored positive: the sign-flip threshold (Pi2 = A)')
    progress('      -> pressure amplification is RANGE-DRIVEN (decays as 1/Zf)')
    progress('    canyon_trap  (I): ln Lambda = C0 + C1*rho*(sqrt(H/s)-C2*rho)')
    progress('                                     / (H/s + C3*sqrt(Pi2))')
    progress('      -> impulse amplification is GEOMETRY-DRIVEN (no Zf term)')
    progress('    power        (legacy I): Z_urban = C*Zf^m*rho^p*(H/s)^q*Pi2^r')
    progress('    lambda_regime(legacy P): per-regime additive Lambda + classifier')
    progress('  All factors are Pi groups (Pi2 = s/W^(1/3)); W enters only')
    progress('  through W^(1/3).')
    progress('  R_urban = W^(1/3) * Z_urban  (canonical — not separately fitted)')
    progress('  Validity: Z_free >= Zf_min')
    progress('  Physical closure: predictions clipped from ABOVE at Z_conv only')
    progress('  (no lower bound — Z_urban < Z_free is the attenuation regime)')
    progress('  (Z_conv from the convergence formulas); identity beyond Z_conv.')
    progress('  Groups: by det only (2 formulas per target)')
    progress('=' * 70)

    for target in ['Pressure', 'Impulse']:
        for det in [1, 2]:
            c = z_coeffs.get((det, target))
            if c is None:
                continue
            progress(f'\n  {det_names[det]} / {target}:')
            if c.get('formula') == 'range_switch':
                progress(f'    ln Lambda = {c["C0"]:+.4f} + {c["C1"]:.4f}'
                         f'*[ (Pi2 - {c["A"]:.4f})/Z_free - ln(Pi2) ]'
                         f' / ( Pi2/(H/s) + {c["B"]:.4f} )')
                progress(f'      -ln(Pi2):             baseline street-width'
                         f' power law')
                progress(f'      (Pi2 - {c["A"]:.2f})/Z_free:  near-field'
                         f' switch, decays with range')
                progress(f'      /(Pi2/(H/s) + {c["B"]:.2f}): open-canyon'
                         f' damping (wide+low canyons suppress)')
                progress(f'    Z_urban = exp(ln Lambda) * Z_free')
            elif c.get('formula') == 'canyon_trap':
                progress(f'    ln Lambda = {c["C0"]:+.4f} + {c["C1"]:.4f}'
                         f'*rho*(sqrt(H/s) - {c["C2"]:.4f}*rho)'
                         f' / ( H/s + {c["C3"]:.4f}*sqrt(Pi2) )')
                progress(f'      rho*sqrt(H/s):        trapping — wall'
                         f' continuity x canyon aspect')
                progress(f'      -{c["C2"]:.2f}*rho^2:         density'
                         f' self-limiting (dense blocks choke streets)')
                progress(f'      /(H/s + {c["C3"]:.2f}*sqrt(Pi2)): canyon'
                         f' saturation + street-width dilution')
                progress(f'      no Z_free term:       geometry-set,'
                         f' range-flat amplification')
                progress(f'    Z_urban = exp(ln Lambda) * Z_free')
            elif c.get('formula') == 'lambda_regime':
                for key, name in (('amp', 'amplification'),
                                  ('att', 'attenuation'), ('pooled', 'pooled')):
                    cc = c.get(key)
                    if cc is None:
                        continue
                    progress(f'    [{name}]')
                    progress(f'      Lambda = {cc["C0"]:+.4f} + {cc["C1"]:+.4f}*(s/W^1/3)'
                             f' + {cc["C2"]:+.4f}*rho*(s/W^1/3 - {cc["a"]:g})')
                    progress(f'               + {cc["C3"]:+.4f}*sqrt(rho)*(H/s)*(W^1/3/s - 1)'
                             f' + {cc["C4"]:+.4f}*ln(Z_free)')
                progress('    Z_urban = Lambda * Z_free')
                crit = c.get('criterion')
                if crit:
                    progress('    regime:  xi = Z_free / Z_conv,P   '
                             '(Z_conv from the PREDICTED formula)')
                    progress(f'             g  = {crit["const"]:+.4f} '
                             f'{crit["invpi2"]:+.4f}*(W^1/3/s) '
                             f'{crit["rho"]:+.4f}*rho')
                    progress(f'                  {crit["hs"]:+.4f}*(H/s) '
                             f'{crit["xi"]:+.4f}*xi')
                    progress('             attenuation if g > 0, '
                             'else amplification')
            else:
                progress(f'    Z_urban = {c["C"]:.4f} * Z_free^{c["m"]:.4f}'
                         f' * rho^{c["p"]:+.4f} * (H/s)^{c["q"]:+.4f}'
                         f' * (s/W^1/3)^{c["r"]:+.4f}')
            progress(f'    MaxR = W^(1/3) * Z_urban    [Z_free >= {c["zf_min"]:g}]')


# ============================================================
# Main
# ============================================================

def main(*, tables_dir=None, out_dir=None, radius_method=None, progress=print):
    """Validate the saved coefficients against the best CV test split.

    Returns dict of summary metrics, or None if required inputs are missing.
    """
    tables_dir = paths.resolve(tables_dir, paths.TABLES_DIR)
    out_dir = paths.ensure_dir(paths.resolve(out_dir, paths.CHECK_RESULTS_DIR))

    # Every table and figure is suffixed with the radius estimator that
    # produced it, so validate the run that matches.
    method = resolve_estimator(radius_method)['method']

    def tbl(name):
        return tables_dir / paths.suffixed(name, method)

    def fig(name):
        return out_dir / paths.suffixed(name, method)

    progress(f'Radius estimator: {method}')

    # ---- Load best coefficients ----
    progress('Loading best coefficients...')
    conv_coeffs = load_convergence_coefficients(
        tbl('best_convergence_coefficients.csv'))
    z_coeffs = load_nonlinear_coefficients(
        tbl('best_z_urban_coefficients.csv'))

    # ---- Load best test split ----
    test_split_path = tbl('best_test_configs.csv')
    if not test_split_path.exists():
        progress(f'ERROR: {test_split_path} not found.')
        progress('Run run_analysis.py first to generate the best test split.')
        return None
    test_configs = set(pd.read_csv(test_split_path)['ConfigName'].values)
    progress(f'Loaded {len(test_configs)} test configs from best CV split')

    # ---- Load processed data (filter to test only) ----
    conv_df_all = pd.read_csv(tbl(paths.CONV_CSV.name))
    maxR_df_all = pd.read_csv(tbl(paths.MAXR_CSV.name))

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
        fig('validation_convergence_radius.png'))
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

    # Score only the rows the models were actually FITTED on. Using the
    # shared z_urban_valid_mask rather than a local filter is the point: this
    # block used to require only "inside R_conv" and so also scored the
    # attenuation regime (Z_urban <= Z_free), which the fit excludes. That
    # inflated every Z_urban number reported here — for both functional forms
    # — because the models have no coverage there.
    _prep = prepare_maxR_data(maxR_df, conv_df)
    _valid = {}
    for _tgt, _tcol, _mcol, _rcol in (
            ('Pressure', 'Z_urban_P', 'MaxR_P', 'RadiusP'),
            ('Impulse',  'Z_urban_I', 'MaxR_I', 'RadiusI')):
        _sub = _prep.dropna(subset=[_tcol, _rcol])
        _m = z_urban_valid_mask(_sub, _tcol, _mcol, _rcol, _tgt)
        _valid[_tgt] = set(zip(_sub.loc[_m, 'Config'], _sub.loc[_m, 'Z']))

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

        # Inside R_conv, Z_free >= floor, AND amplification — the fit domain.
        use_P = (cfg_name, row['Z']) in _valid['Pressure']
        use_I = (cfg_name, row['Z']) in _valid['Impulse']

        color = _get_group_color(geo['det'])
        W_third = geo['weight'] ** (1/3)

        # Z_urban predictions (already in metres: W^(1/3) * Z_urban)
        conv_pred_P_val, conv_pred_I_val = conv_pred_cache.get(cfg_name, (np.nan, np.nan))
        pred_mR_P, pred_mR_I = predict_z_urban_per_Z(
            z_val, geo['weight'], geo['rho'], geo['height'], geo['swidth'],
            geo['det'], z_coeffs, pred_Rconv_P=conv_pred_P_val)

        # Physical closure: clip from ABOVE at the predicted R_conv only
        # (urban = free-field beyond it). No lower bound — Z_urban < Z_free is
        # the attenuation regime and is real, so clamping at the free-field
        # radius would make it unrepresentable.
        if np.isfinite(pred_mR_P) and np.isfinite(conv_pred_P_val):
            pred_mR_P = min(pred_mR_P, conv_pred_P_val)
        if np.isfinite(pred_mR_I) and np.isfinite(conv_pred_I_val):
            pred_mR_I = min(pred_mR_I, conv_pred_I_val)

        # R_urban = W^(1/3) * Z_urban — the canonical derivation, same value
        pred_rR_P, pred_rR_I = pred_mR_P, pred_mR_I

        if use_P and np.isfinite(maxR_P):
            if np.isfinite(pred_mR_P):
                zu_actual_P.append(maxR_P / W_third)
                zu_pred_P.append(pred_mR_P / W_third)
                zu_colors_P.append(color)
            if np.isfinite(pred_rR_P):
                ru_actual_P.append(maxR_P)
                ru_pred_P.append(pred_rR_P)
                ru_colors_P.append(color)

        if use_I and np.isfinite(maxR_I):
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
        fig('validation_z_urban.png'))
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
        fig('validation_r_urban.png'))
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
    comp_out = fig('validation_comparison.csv')
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
    p.add_argument('--radius-method', choices=list(VALID_METHODS), default=None,
                   dest='radius_method',
                   help='Which radius-estimator run to validate '
                        '(default: constants.RADIUS_ESTIMATOR).')
    args = p.parse_args(argv)
    return main(tables_dir=args.tables_dir, out_dir=args.out_dir,
                radius_method=args.radius_method)


if __name__ == '__main__':
    cli()
