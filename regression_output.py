"""Output helpers: coefficient CSVs and formula pretty-printers."""

import os
import numpy as np
import pandas as pd


# ============================================================
# Output helpers
# ============================================================

def _save_best_convergence_coefficients(conv_P_coeffs, conv_I_coeffs, output_folder,
                                        filename='best_convergence_coefficients.csv'):
    """Save convergence radius coefficients (both formulas) to CSV.

    Superset schema, one row per (det, target) — 4 rows total:
      Det, Location, Target, Formula,
      C0, C1_sW13, C2_switch, C3_canyon, a_thresh, has_H_term,   (additive, P)
      A, k                                                       (log, I)
    Unused cells are left empty.

    RadiusP (Formula='additive'):
      R = W^(1/3) * (C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                        + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1))
    RadiusI (Formula='log'):
      R = W^(1/3) * A * Pi^(k*ln(W^1/3/s)),  Pi = H/(s*rho)
    """
    loc_names = {1: 'Street', 2: 'Intersection'}

    rows = []
    for det_val, coef in conv_P_coeffs.items():
        if coef is None:
            continue
        rows.append({
            'Det': det_val,
            'Location': loc_names.get(det_val, str(det_val)),
            'Target': 'RadiusP',
            'Formula': 'additive',
            'C0': coef['C0'],
            'C1_sW13': coef['C1'],
            'C2_switch': coef['C2'],
            'C3_canyon': coef['C3'],
            'a_thresh': coef['a'],
            'has_H_term': int(coef['has_H_term']),
            'A': np.nan,
            'k': np.nan,
        })
    for det_val, coef in conv_I_coeffs.items():
        if coef is None:
            continue
        rows.append({
            'Det': det_val,
            'Location': loc_names.get(det_val, str(det_val)),
            'Target': 'RadiusI',
            'Formula': 'log',
            'C0': np.nan,
            'C1_sW13': np.nan,
            'C2_switch': np.nan,
            'C3_canyon': np.nan,
            'a_thresh': np.nan,
            'has_H_term': np.nan,
            'A': coef['A'],
            'k': coef['k'],
        })

    df = pd.DataFrame(rows)
    path = os.path.join(output_folder, filename)
    df.to_csv(path, index=False)
    print(f'Saved: {path}')


def _save_best_nonlinear_coefficients(coeffs_dict, filename, output_folder):
    """Save Z_urban power-law coefficients to CSV.

    Schema (one row per det × target):
      Det, Location, Target, C, m, p_rho, q_HoverS, r_sW13, Zf_min
    Zf_min is the lower validity bound on Z_free (1 pressure, 2 impulse).
    R_urban needs no CSV of its own: R_urban = W^(1/3) * Z_urban.
    """
    loc_names = {1: 'Street', 2: 'Intersection'}

    rows = []
    for (det_val, target_name), coef in coeffs_dict.items():
        if coef is None:
            continue
        rows.append({
            'Det': det_val,
            'Location': loc_names.get(det_val, str(det_val)),
            'Target': target_name,
            'C': coef['C'],
            'm': coef['m'],
            'p_rho': coef['p'],
            'q_HoverS': coef['q'],
            'r_sW13': coef['r'],
            'Zf_min': coef['zf_min'],
        })

    df = pd.DataFrame(rows)
    path = os.path.join(output_folder, filename)
    df.to_csv(path, index=False)
    print(f'Saved: {path}')


def _print_final_formulas(conv_df, conv_P_coeffs, conv_I_coeffs):
    """Print the best convergence radius formulas (both targets).

    Both share the canonical structure R = W^(1/3) * Z; only the Z
    expression differs (additive Pi for pressure, log Pi for impulse).
    """
    loc_names = {1: 'Street (det=1)', 2: 'Intersection (det=2)'}

    print(f'\n{"="*70}')
    print('  BEST CONVERGENCE RADIUS FORMULAS    R = W^(1/3) * Z')
    print(f'{"="*70}')
    print('  RadiusP (Buckingham Pi additive model):')
    print('    Z = C0 + C1*(s/W^(1/3)) + C2*rho*(s/W^(1/3) - a)')
    print('           + C3*sqrt(rho)*(H/s)*(W^(1/3)/s - 1)')
    print('    a = 1 (street) / 2 (intersection): density-switch threshold')
    print('    Canyon law: H/s effect flips sign at s = W^(1/3) (channeling <-> blocking)')
    print('    sqrt(rho) = b/(b+s) = canyon wall continuity (cross-street gaps leak)')
    print('  RadiusI (log-space Pi model):')
    print('    Z = A * Pi^(k*ln(W^(1/3)/s)),  Pi = H/(s*rho)')
    print('    A ~ scaled distance where free-field pressure decays to ~9 kPa;')
    print('    exponent flips sign at s = W^(1/3): confinement extends R for')
    print('    large charges, shortens it for small ones')
    print('  where rho = b^2/(b+s)^2, W^(1/3) is the Hopkinson length scale')
    print(f'{"="*70}')

    print(f'\n--- RadiusP ---')
    for det_val in sorted(conv_P_coeffs.keys()):
        coef = conv_P_coeffs[det_val]
        if coef is None:
            continue
        C0, C1 = coef['C0'], coef['C1']
        C2, C3 = coef['C2'], coef['C3']
        a      = coef['a']
        has_H = coef['has_H_term']
        loc   = loc_names.get(det_val, f'det={det_val}')
        print(f'  {loc}:')
        if has_H:
            print(f'    Z = {C0:+.4f} + {C1:+.4f}*(s/W^1/3)'
                  f' + {C2:+.4f}*rho*(s/W^1/3 - {a:g})'
                  f' + {C3:+.4f}*sqrt(rho)*(H/s)*(W^1/3/s - 1)')
        else:
            print(f'    Z = {C0:+.4f} + {C1:+.4f}*(s/W^1/3)'
                  f' + {C2:+.4f}*rho*(s/W^1/3 - {a:g})  [H=0, canyon term omitted]')
        print(f'    R = W^(1/3) * Z')

    print(f'\n--- RadiusI ---')
    for det_val in sorted(conv_I_coeffs.keys()):
        coef = conv_I_coeffs[det_val]
        if coef is None:
            continue
        loc = loc_names.get(det_val, f'det={det_val}')
        print(f'  {loc}:')
        print(f'    Z = {coef["A"]:.4f} * Pi^({coef["k"]:+.4f}*ln(W^1/3/s))')
        print(f'    R = W^(1/3) * Z')
    print()


def _print_z_urban_formulas(z_coeffs):
    """Print the best Z_urban formulas (canonical: MaxR = W^(1/3) * Z_urban)."""
    if z_coeffs is None:
        return
    loc_names = {1: 'Street (det=1)', 2: 'Intersection (det=2)'}

    print(f'{"="*70}')
    print('  BEST Z_URBAN FORMULAS    MaxR = W^(1/3) * Z_urban')
    print(f'{"="*70}')
    print('  Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r')
    print('  All factors are Pi groups; W enters only through W^(1/3).')
    print('  R_urban = W^(1/3) * Z_urban  (canonical — not separately fitted)')
    print('  Validity: Z_free >= Zf_min (1 pressure, 2 impulse — at Z_free=1')
    print('  the point is inside the first street; impulse mapping invalid)')
    print('  Physical closure: predictions clipped to Z_free <= Z_urban <= Z_conv')
    print('  (Z_conv from the convergence formulas); identity beyond Z_conv.')
    print(f'{"="*70}')

    for target_name in ['Pressure', 'Impulse']:
        print(f'\n--- Z_urban {target_name} ---')
        for det_val in [1, 2]:
            coef = z_coeffs.get((det_val, target_name))
            if coef is None:
                continue
            loc = loc_names.get(det_val, f'det={det_val}')
            print(f'  {loc}:')
            print(f'    Z_urban = {coef["C"]:.4f} * Z_free^{coef["m"]:.4f}'
                  f' * rho^{coef["p"]:+.4f} * (H/s)^{coef["q"]:+.4f}'
                  f' * (s/W^1/3)^{coef["r"]:+.4f}')
            print(f'    MaxR = W^(1/3) * Z_urban    [Z_free >= {coef["zf_min"]:g}]')
    print()
