"""Pretty-print the best convergence + Z_urban formulas from the saved CSVs.

Usage:
    python tools\\formulas_printer\\formulas_printer.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import pandas as pd

from blastlib import paths
from blastlib.processing.radius_estimator import resolve_estimator, VALID_METHODS


def format_convergence_formulas(csv_path):
    """Return the convergence-radius formulas as text ('' if CSV missing)."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return ''
    df = pd.read_csv(csv_path)

    lines = [
        '=' * 70,
        ' BEST CONVERGENCE RADIUS FORMULAS    R = W^(1/3) * Z',
        ' RadiusP: Z = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)',
        '                + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1)',
        ' RadiusI: Z = A * rho^p * (H/s)^q * (s/W^1/3)^r',
        '=' * 70,
    ]
    for target in ['RadiusP', 'RadiusI']:
        lines.append(f'\n--- {target} ---')
        for _, row in df[df['Target'] == target].iterrows():
            lines.append(f"  {row['Location']}:")
            if row['Formula'] == 'power':
                lines.append(
                    f"    Z = {row['A']:.4f} * rho^({row['p_rho']:+.4f})"
                    f" * (H/s)^({row['q_HoverS']:+.4f})"
                    f" * (s/W^1/3)^({row['r_sW13']:+.4f})")
            else:
                lines.append(
                    f"    Z = {row['C0']:+.4f} {row['C1_sW13']:+.4f}*(s/W^1/3)"
                    f" {row['C2_switch']:+.4f}*rho*(s/W^1/3 - {row['a_thresh']:g})"
                    f" {row['C3_canyon']:+.4f}*sqrt(rho)*(H/s)*(W^1/3/s - 1)")
            lines.append('    R = W^(1/3) * Z')
    return '\n'.join(lines)


def format_z_urban_formulas(csv_path):
    """Return the Z_urban formulas as text ('' if CSV missing)."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return ''
    df = pd.read_csv(csv_path)
    det_map = {1: 'Street (det=1)', 2: 'Intersection (det=2)'}

    lines = [
        '\n' + '=' * 70,
        ' BEST Z_URBAN FORMULAS    MaxR = W^(1/3) * Z_urban',
        ' Pressure (range_switch):  ln Lambda = C0 + C1*[(Pi2-A)/Zf - ln Pi2]'
        ' / (Pi2/(H/s) + B)   [A_switch stored positive]',
        ' Impulse  (canyon_trap):   ln Lambda = C0 + C1*rho*(sqrt(H/s)-C2*rho)'
        ' / (H/s + C3*sqrt(Pi2))',
        ' Legacy impulse (power):   Z_urban = C * Z_free^m * rho^p'
        ' * (H/s)^q * (s/W^(1/3))^r',
        ' Legacy pressure (lambda_regime, one set per regime):'
        ' Lambda = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)',
        '                                      + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1)'
        ' + C4*ln(Z_free)',
        '                             Z_urban = Lambda * Z_free',
        ' R_urban = W^(1/3) * Z_urban  (canonical -- not separately fitted)',
        ' Validity: Z_free >= Zf_min',
        ' Physical closure: clip predictions from ABOVE at Z_conv only'
        ' (no lower bound: Z_urban < Z_free is the attenuation regime),',
        ' (Z_conv from the convergence formulas); identity beyond Z_conv.',
        ' Groups: by det only (2 formulas per target)',
        '=' * 70,
    ]
    for _, row in df.iterrows():
        lines.append(f"\n  {det_map.get(int(row['Det']), str(row['Det']))} / {row['Target']}:")
        formula = row.get('Formula', 'power')
        if formula == 'range_switch':
            lines.append(
                f"    ln Lambda = {row['C0']:+.4f} + {row['C1_amp']:.4f}"
                f"*[ (Pi2 - {row['A_switch']:.4f})/Z_free - ln(Pi2) ]"
                f" / ( Pi2/(H/s) + {row['B_open']:.4f} )")
            lines.append('    (range-driven: street-width switch decaying as'
                         ' 1/Z_free; open canyons damp it)')
            lines.append('    Z_urban = exp(ln Lambda) * Z_free')
        elif formula == 'canyon_trap':
            lines.append(
                f"    ln Lambda = {row['C0']:+.4f} + {row['C1_amp']:.4f}"
                f"*rho*(sqrt(H/s) - {row['C2_self']:.4f}*rho)"
                f" / ( H/s + {row['C3_dilute']:.4f}*sqrt(Pi2) )")
            lines.append('    (geometry-driven: no Z_free term — canyon'
                         ' trapping, density self-limiting)')
            lines.append('    Z_urban = exp(ln Lambda) * Z_free')
        elif formula == 'lambda_regime':
            lines.append(f"    [regime: {row.get('Regime', 'pooled')}]")
            lines.append(
                f"    Lambda = {row['C0']:+.4f} {row['C1_sW13']:+.4f}*(s/W^1/3)"
                f" {row['C2_switch']:+.4f}*rho*(s/W^1/3 - {row['a_thresh']:g})")
            lines.append(
                f"             {row['C3_canyon']:+.4f}*sqrt(rho)*(H/s)*(W^1/3/s - 1)"
                f" {row['C4_lnZf']:+.4f}*ln(Z_free)")
            lines.append('    Z_urban = Lambda * Z_free')
        else:
            lines.append(
                f"    Z_urban = {row['C']:.4f} * Z_free^{row['m']:.4f}"
                f" * rho^{row['p_rho']:+.4f} * (H/s)^{row['q_HoverS']:+.4f}"
                f" * (s/W^1/3)^{row['r_sW13']:+.4f}")
        lines.append(f"    MaxR = W^(1/3) * Z_urban    [Z_free >= {row['Zf_min']:g}]")
    return '\n'.join(lines)


def main(*, tables_dir=None, radius_method=None, progress=print):
    """Print (and return) the formatted formula text.

    *radius_method* selects which estimator's coefficient CSVs to read.
    """
    tables_dir = paths.resolve(tables_dir, paths.TABLES_DIR)
    method = resolve_estimator(radius_method)['method']

    text = format_convergence_formulas(
        tables_dir / paths.suffixed('best_convergence_coefficients.csv', method))
    text += format_z_urban_formulas(
        tables_dir / paths.suffixed('best_z_urban_coefficients.csv', method))

    if not text.strip():
        progress(f'No coefficient CSVs found in {tables_dir}. Run run_analysis.py first.')
    else:
        progress(text)
    return text


def cli(argv=None):
    p = argparse.ArgumentParser(description='Print the best fitted formulas.')
    p.add_argument('--tables-dir', default=None, help='Folder with the coefficient CSVs.')
    p.add_argument('--radius-method', choices=list(VALID_METHODS), default=None,
                   dest='radius_method',
                   help='Which radius-estimator run to print formulas for.')
    args = p.parse_args(argv)
    return main(tables_dir=args.tables_dir, radius_method=args.radius_method)


if __name__ == '__main__':
    cli()
