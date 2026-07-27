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
    """Save Z_urban coefficients to CSV (superset schema, all four formulas).

    Schema (one row per det × target × regime):
      Det, Location, Target, Formula, Regime,
      C0, C1_amp, A_switch, B_open,                    (range_switch, P)
      C0, C1_amp, C2_self, C3_dilute,                  (canyon_trap, I)
      C, m, p_rho, q_HoverS, r_sW13,                   (power, legacy I)
      C0, C1_sW13, C2_switch, C3_canyon, C4_lnZf, a_thresh,
                                                       (lambda_regime, legacy P)
      Zf_min
    Unused cells are left empty. Zf_min is the lower validity bound on Z_free.

    Pressure (Formula='range_switch') — closed form, one row per det:
      ln Lambda = C0 + C1_amp * [ (Pi2 - A_switch)/Z_free - ln(Pi2) ]
                               / ( Pi2/(H/s) + B_open )
      A_switch is stored POSITIVE: it is the sign-flip threshold itself.
    Impulse (Formula='canyon_trap') — closed form, one row per det:
      ln Lambda = C0 + C1_amp * rho*(sqrt(H/s) - C2_self*rho)
                               / ( H/s + C3_dilute*sqrt(Pi2) )
    with Pi2 = s/W^(1/3) and Z_urban = Lambda * Z_free for both.

    Legacy impulse (Formula='power', Regime=''):
      Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r
    Legacy pressure (Formula='lambda_regime') — fitted on the amplification
    factor, separately per regime, then multiplied back up:
      Lambda  = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                   + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1) + C4*ln(Z_free)
      Z_urban = Lambda * Z_free
    Three legacy pressure rows per det plus a 'criterion' row: which regime
    applies is decided by z_urban.ATTENUATION_CRITERION, whose xi term needs
    the PREDICTED convergence radius. The closed forms need none of that.

    R_urban needs no CSV of its own: R_urban = W^(1/3) * Z_urban.
    """
    loc_names = {1: 'Street', 2: 'Intersection'}
    blank_power = {'C': np.nan, 'm': np.nan, 'p_rho': np.nan,
                   'q_HoverS': np.nan, 'r_sW13': np.nan}
    blank_lambda = {'C0': np.nan, 'C1_sW13': np.nan, 'C2_switch': np.nan,
                    'C3_canyon': np.nan, 'C4_lnZf': np.nan, 'a_thresh': np.nan}
    blank_crit = {f'K_{k}': np.nan for k in ATTENUATION_KEYS}
    blank_closed = {'C1_amp': np.nan, 'A_switch': np.nan, 'B_open': np.nan,
                    'C2_self': np.nan, 'C3_dilute': np.nan}

    rows = []
    for (det_val, target_name), coef in coeffs_dict.items():
        if coef is None:
            continue
        form = Z_URBAN_FORM.get(target_name, 'power')

        def base(regime):
            return {'Det': det_val,
                    'Location': loc_names.get(det_val, str(det_val)),
                    'Target': target_name, 'Formula': form, 'Regime': regime,
                    **blank_power, **blank_lambda, **blank_crit,
                    **blank_closed}

        if form == 'range_switch':
            row = base('')
            row.update({'C0': coef['C0'], 'C1_amp': coef['C1'],
                        'A_switch': coef['A'], 'B_open': coef['B'],
                        'Zf_min': coef['zf_min']})
            rows.append(row)
        elif form == 'canyon_trap':
            row = base('')
            row.update({'C0': coef['C0'], 'C1_amp': coef['C1'],
                        'C2_self': coef['C2'], 'C3_dilute': coef['C3'],
                        'Zf_min': coef['zf_min']})
            rows.append(row)
        elif form == 'lambda_regime':
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
    form_P = Z_URBAN_FORM.get('Pressure')
    form_I = Z_URBAN_FORM.get('Impulse')
    if form_P == 'range_switch':
        print('  Pressure — range-switch closed form (Lambda = Z_urban/Z_free):')
        print('    ln Lambda = C0 + C1*[ (Pi2 - A)/Z_free - ln(Pi2) ]')
        print('                     / ( Pi2/(H/s) + B )        Pi2 = s/W^(1/3)')
        print('    amplification is RANGE-DRIVEN: the street-width switch')
        print('    (sign flips at Pi2 = A) decays as 1/Z_free to free field')
    else:
        print('  Pressure — additive Pi on the amplification factor, per regime:')
        print('    Lambda  = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)')
        print('                 + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1) + C4*ln(Z_free)')
        print('    Z_urban = Lambda * Z_free      (a = 1 street / 2 intersection)')
        print('    regime from ATTENUATION_CRITERION (needs the PREDICTED Z_conv)')
    if form_I == 'canyon_trap':
        print('  Impulse  — canyon-trap closed form (Lambda = Z_urban/Z_free):')
        print('    ln Lambda = C0 + C1*rho*(sqrt(H/s) - C2*rho)')
        print('                     / ( H/s + C3*sqrt(Pi2) )')
        print('    amplification is GEOMETRY-DRIVEN: no Z_free term at all —')
        print('    the canyon sets one amplification factor for every range')
    else:
        print('  Impulse  — power law:')
        print('    Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r')
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
            form = Z_URBAN_FORM.get(target_name)
            if form == 'range_switch':
                print(f'    ln Lambda = {coef["C0"]:+.4f} '
                      f'+ {coef["C1"]:.4f}*[ (Pi2 - {coef["A"]:.4f})/Z_free'
                      f' - ln(Pi2) ] / ( Pi2/(H/s) + {coef["B"]:.4f} )')
                print(f'      -ln(Pi2):              baseline street-width power law')
                print(f'      (Pi2 - {coef["A"]:.2f})/Z_free:   near-field switch,'
                      f' decays with range')
                print(f'      /(Pi2/(H/s) + {coef["B"]:.2f}):  open-canyon damping'
                      f' (wide+low canyons suppress)')
                print(f'    Z_urban = exp(ln Lambda) * Z_free')
            elif form == 'canyon_trap':
                print(f'    ln Lambda = {coef["C0"]:+.4f} '
                      f'+ {coef["C1"]:.4f}*rho*(sqrt(H/s) - {coef["C2"]:.4f}*rho)'
                      f' / ( H/s + {coef["C3"]:.4f}*sqrt(Pi2) )')
                print(f'      rho*sqrt(H/s):         trapping — wall continuity'
                      f' x canyon aspect')
                print(f'      -{coef["C2"]:.2f}*rho^2:          density'
                      f' self-limiting (dense blocks choke streets)')
                print(f'      /(H/s + {coef["C3"]:.2f}*sqrt(Pi2)): canyon'
                      f' saturation + street-width dilution')
                print(f'      no Z_free term:        geometry-set, range-flat'
                      f' amplification')
                print(f'    Z_urban = exp(ln Lambda) * Z_free')
            elif form == 'lambda_regime':
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
