"""Output helpers: coefficient CSVs and formula pretty-printers."""

import os
import numpy as np
import pandas as pd

from blastlib.regression.z_urban import Z_URBAN_FORM, ATTENUATION_KEYS


def save_best_convergence_coefficients(conv_P_coeffs, conv_I_coeffs, output_folder,
                                       filename='best_convergence_coefficients.csv'):
    """Save convergence radius coefficients (both formulas) to CSV.

    Superset schema, one row per (det, target) — 4 rows total:
      Det, Location, Target, Formula,
      C0, C1_sW13, C2_switch, C3_canyon, a_thresh, has_H_term,   (additive, P)
      A, p_rho, q_HoverS, r_sW13                                 (power, I)
    Unused cells are left empty.

    RadiusP (Formula='additive'):
      R = W^(1/3) * (C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                        + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1))
    RadiusI (Formula='power'):
      R = W^(1/3) * A * rho^p * (H/s)^q * (s/W^(1/3))^r
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
            'p_rho': np.nan,
            'q_HoverS': np.nan,
            'r_sW13': np.nan,
        })
    for det_val, coef in conv_I_coeffs.items():
        if coef is None:
            continue
        rows.append({
            'Det': det_val,
            'Location': loc_names.get(det_val, str(det_val)),
            'Target': 'RadiusI',
            'Formula': 'power',
            'C0': np.nan,
            'C1_sW13': np.nan,
            'C2_switch': np.nan,
            'C3_canyon': np.nan,
            'a_thresh': np.nan,
            'has_H_term': np.nan,
            'A': coef['A'],
            'p_rho': coef['p'],
            'q_HoverS': coef['q'],
            'r_sW13': coef['r'],
        })

    df = pd.DataFrame(rows)
    path = os.path.join(str(output_folder), filename)
    df.to_csv(path, index=False)
    print(f'Saved: {path}')


def save_best_nonlinear_coefficients(coeffs_dict, filename, output_folder):
    """Save Z_urban coefficients to CSV (superset schema, both formulas).

    Schema (one row per det × target × regime):
      Det, Location, Target, Formula, Regime,
      C, m, p_rho, q_HoverS, r_sW13,                   (power, Impulse)
      C0, C1_sW13, C2_switch, C3_canyon, C4_lnZf, a_thresh,
                                                       (lambda_regime, P)
      Zf_min
    Unused cells are left empty. Zf_min is the lower validity bound on Z_free.

    Impulse (Formula='power', Regime=''):
      Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r
    Pressure (Formula='lambda_regime') — fitted on the amplification factor,
    separately per regime, then multiplied back up:
      Lambda  = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                   + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1) + C4*ln(Z_free)
      Z_urban = Lambda * Z_free
    Three pressure rows per det: Regime='amplification', 'attenuation', and
    'pooled' (the fallback when a regime is too thin to fit). Which one
    applies is decided by z_urban.ATTENUATION_CRITERION, whose xi term needs
    the PREDICTED convergence radius.

    R_urban needs no CSV of its own: R_urban = W^(1/3) * Z_urban.
    """
    loc_names = {1: 'Street', 2: 'Intersection'}
    blank_power = {'C': np.nan, 'm': np.nan, 'p_rho': np.nan,
                   'q_HoverS': np.nan, 'r_sW13': np.nan}
    blank_lambda = {'C0': np.nan, 'C1_sW13': np.nan, 'C2_switch': np.nan,
                    'C3_canyon': np.nan, 'C4_lnZf': np.nan, 'a_thresh': np.nan}
    blank_crit = {f'K_{k}': np.nan for k in ATTENUATION_KEYS}

    rows = []
    for (det_val, target_name), coef in coeffs_dict.items():
        if coef is None:
            continue
        form = Z_URBAN_FORM.get(target_name, 'power')

        def base(regime):
            return {'Det': det_val,
                    'Location': loc_names.get(det_val, str(det_val)),
                    'Target': target_name, 'Formula': form, 'Regime': regime,
                    **blank_power, **blank_lambda, **blank_crit}

        if form == 'lambda_regime':
            # One row per regime; the classifier picks between them at
            # inference (see z_urban.ATTENUATION_CRITERION).
            for key, name in (('amp', 'amplification'),
                              ('att', 'attenuation'), ('pooled', 'pooled')):
                c = coef.get(key)
                if c is None:
                    continue
                row = base(name)
                row.update({'C0': c['C0'], 'C1_sW13': c['C1'],
                            'C2_switch': c['C2'], 'C3_canyon': c['C3'],
                            'C4_lnZf': c['C4'], 'a_thresh': c['a'],
                            'Zf_min': c['zf_min']})
                rows.append(row)
            # The regime classifier is part of the formula: pressure Z_urban
            # cannot be evaluated without it, so it ships with the coefficients.
            crit = coef.get('criterion') or {}
            if crit:
                row = base('criterion')
                row.update({f'K_{k}': crit[k] for k in ATTENUATION_KEYS})
                row['Zf_min'] = coef['pooled']['zf_min']
                rows.append(row)
        else:
            row = base('')
            row.update({'C': coef['C'], 'm': coef['m'], 'p_rho': coef['p'],
                        'q_HoverS': coef['q'], 'r_sW13': coef['r'],
                        'Zf_min': coef['zf_min']})
            rows.append(row)

    df = pd.DataFrame(rows)
    path = os.path.join(str(output_folder), filename)
    df.to_csv(path, index=False)
    print(f'Saved: {path}')


def print_final_formulas(conv_df, conv_P_coeffs, conv_I_coeffs):
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
    print('  RadiusI (Pi power law):')
    print('    Z = A * rho^p * (H/s)^q * (s/W^(1/3))^r')
    print('    one exponent per Pi group, so the geometry effects separate')
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
        print(f'    Z = {coef["A"]:.4f} * rho^({coef["p"]:+.4f})'
              f' * (H/s)^({coef["q"]:+.4f})'
              f' * (s/W^1/3)^({coef["r"]:+.4f})')
        print(f'    R = W^(1/3) * Z')
    print()


def print_z_urban_formulas(z_coeffs):
    """Print the best Z_urban formulas (canonical: MaxR = W^(1/3) * Z_urban)."""
    if z_coeffs is None:
        return
    loc_names = {1: 'Street (det=1)', 2: 'Intersection (det=2)'}

    print(f'{"="*70}')
    print('  BEST Z_URBAN FORMULAS    MaxR = W^(1/3) * Z_urban')
    print(f'{"="*70}')
    print('  Impulse  — power law:')
    print('    Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r')
    print('  Pressure — additive Pi on the amplification factor, per regime:')
    print('    Lambda  = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)')
    print('                 + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1) + C4*ln(Z_free)')
    print('    Z_urban = Lambda * Z_free      (a = 1 street / 2 intersection)')
    print('    regime from ATTENUATION_CRITERION (needs the PREDICTED Z_conv)')
    print('  All factors are Pi groups; W enters only through W^(1/3).')
    print('  R_urban = W^(1/3) * Z_urban  (canonical — not separately fitted)')
    print('  Validity: Z_free >= Zf_min (at Z_free=1 the point is inside the')
    print('  first street; the mapping is invalid there)')
    print('  Physical closure: predictions clipped from ABOVE at Z_conv only')
    print('  (no lower bound — Z_urban < Z_free is the attenuation regime)')
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
            if Z_URBAN_FORM.get(target_name) == 'lambda_regime':
                for key, name in (('amp', 'amplification'),
                                  ('att', 'attenuation'), ('pooled', 'pooled')):
                    c = coef.get(key)
                    if c is None:
                        continue
                    print(f'    [{name}]')
                    print(f'      Lambda = {c["C0"]:+.4f} + {c["C1"]:+.4f}*(s/W^1/3)'
                          f' + {c["C2"]:+.4f}*rho*(s/W^1/3 - {c["a"]:g})')
                    print(f'               + {c["C3"]:+.4f}*sqrt(rho)*(H/s)*(W^1/3/s - 1)'
                          f' + {c["C4"]:+.4f}*ln(Z_free)')
                print(f'    Z_urban = Lambda * Z_free')
                crit = coef.get('criterion')
                if crit:
                    print(f'    regime:  xi = Z_free / Z_conv,P   '
                          f'(Z_conv from the PREDICTED formula)')
                    print(f'             g  = {crit["const"]:+.4f} '
                          f'{crit["invpi2"]:+.4f}*(W^1/3/s) '
                          f'{crit["rho"]:+.4f}*rho')
                    print(f'                  {crit["hs"]:+.4f}*(H/s) '
                          f'{crit["xi"]:+.4f}*xi')
                    print(f'             attenuation if g > 0, else amplification')
                print(f'    MaxR = W^(1/3) * Z_urban    '
                      f'[Z_free >= {coef["pooled"]["zf_min"]:g}]')
                continue
            else:
                print(f'    Z_urban = {coef["C"]:.4f} * Z_free^{coef["m"]:.4f}'
                      f' * rho^{coef["p"]:+.4f} * (H/s)^{coef["q"]:+.4f}'
                      f' * (s/W^1/3)^{coef["r"]:+.4f}')
            print(f'    MaxR = W^(1/3) * Z_urban    [Z_free >= {coef["zf_min"]:g}]')
    print()
