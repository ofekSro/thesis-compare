"""Per-config PRESSURE report: convergence radius and the per-Z urban radius,
measured vs. calculated by the shipped production formulas.

Loops over every configuration in convergence_table_<method>.csv and writes one
Excel workbook, outputs\check_results\pressure_report_<method>.xlsx, with a
sheet per table (plus a Notes sheet).

Sheet "By config" (one row each) — the convergence radius:
       R_conv,P measured   RadiusP from Phase 1
       R_conv,P calculated W^(1/3) * Z, additive Pi model, production coeffs
       relative error      (calculated - measured) / measured

Sheet "By Z" — every free-field level inside the convergence radius:
       P_ff        the pressure that level Z represents [kPa]
       R_free      where the FREE field delivers it, = Z * W^(1/3) [m]
       MaxR_P      where the URBAN field still delivers it, measured from
                   (0,0) [m] — this is the "radius" of the row
       MaxR_P calc W^(1/3) * Z_urban, range_switch model, production coeffs,
                   clipped from above at the predicted Z_conv (the deployed
                   chain — see z_urban.clip_z_urban_pred)
       relative error on that radius

   "Inside the convergence radius" is exactly z_urban.z_urban_valid_mask —
   the domain the Z_urban formula is fitted and used on: MaxR < R_conv,
   R_free < R_conv, R_free > exclude_r, and Z >= 2. Rows failing any of the
   four are dropped, so the per-Z errors are the meaningful ones. The count
   dropped per config is reported in the per-config table (`n_Z_dropped`).

Every relative error is banded by magnitude: |err| in [10, 20]% is YELLOW,
above 20% is RED, below 10% is ok. The workbook paints the graded cells in
those colours; the console prints the same bands in ANSI colour and lists every
flagged config. Each sheet also keeps the band as text in an `*_band` column,
so the grading can be sorted, filtered and read back by other code — a fill
colour cannot.

Both "calculated" columns come from the final_production_* coefficient CSVs,
which are fitted on all 96 configs — so every error here is IN-SAMPLE. For
held-out errors on a CV split use tools\\check_formulas\\check_formulas.py.

Usage:
    python tools\\pressure_report\\pressure_report.py
    python tools\\pressure_report\\pressure_report.py --radius-method req
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root
# The two coefficient-CSV loaders live in check_formulas and are the only
# implementation of that parsing (including the stale-sign-convention guard on
# A_switch). Imported rather than copied so the two tools cannot drift apart.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'check_formulas'))

import numpy as np
import pandas as pd

from blastlib import paths
from blastlib.processing.radius_estimator import resolve_estimator, VALID_METHODS
from blastlib.regression.convergence_models import predict_pi
from blastlib.regression.stats import r2_mape
from blastlib.regression.z_urban import (Z_URBAN_FORM, clip_z_urban_pred,
                                         prepare_maxR_data, predict_z_urban,
                                         z_urban_valid_mask)

from check_formulas import (load_convergence_coefficients,  # noqa: E402
                            load_nonlinear_coefficients)


DETS = (1, 2)
LOCATION = {1: 'Street', 2: 'Intersection'}

# Relative-error banding, applied to |relative error| in percent:
#   < 10        ok      (uncoloured)
#   10 .. 20    yellow
#   > 20        red
# The console prints the bands in colour; both CSVs carry the band name in an
# `*_band` column, because a CSV cannot hold a colour and the band is what a
# spreadsheet's conditional formatting would key on anyway.
ERR_YELLOW_PCT = 10.0
ERR_RED_PCT = 20.0

BAND_ANSI = {'red': '\033[91m', 'yellow': '\033[93m', 'ok': ''}
ANSI_RESET = '\033[0m'


def _band(err_pct):
    """Band name for one relative error in percent; '' when not finite."""
    e = abs(float(err_pct)) if err_pct is not None else np.nan
    if not np.isfinite(e):
        return ''
    if e > ERR_RED_PCT:
        return 'red'
    if e >= ERR_YELLOW_PCT:
        return 'yellow'
    return 'ok'


def _band_series(err_pct):
    """Vectorised _band over a Series/array."""
    return pd.Series(err_pct).map(_band).values


def _enable_ansi():
    """True if the console can render ANSI colour.

    Colour is emitted only for an interactive stdout: piping to a file, or the
    GUI capturing the log through a progress callback, would otherwise collect
    raw escape sequences. On Windows the virtual-terminal mode has to be turned
    on explicitly before the codes mean anything.
    """
    if not (hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()):
        return False
    if sys.platform != 'win32':
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # -11 = STD_OUTPUT_HANDLE, 0x0004 = ENABLE_VIRTUAL_TERMINAL_PROCESSING
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def _paint(text, band, enabled):
    """Wrap *text* in the band's colour when colour is enabled."""
    code = BAND_ANSI.get(band, '') if enabled else ''
    return f'{code}{text}{ANSI_RESET}' if code else text


def _rel(path):
    """Path as written for the console: relative to the project root when it
    lives under it. The root itself can contain non-cp1252 characters, which a
    Windows console cannot print — every path this tool reports is inside the
    project, so the relative form is always printable.
    """
    p = Path(path)
    try:
        return str(p.relative_to(paths.PROJECT_ROOT))
    except ValueError:
        return str(p)


def _rel_err_pct(measured, calculated):
    """Signed relative error in percent; NaN where measured is not positive."""
    measured = np.asarray(measured, dtype=float)
    calculated = np.asarray(calculated, dtype=float)
    with np.errstate(invalid='ignore', divide='ignore'):
        out = 100.0 * (calculated - measured) / measured
    return np.where(measured > 0, out, np.nan)


def _by_det(coeffs, target):
    """{det: coef} for one target, dropping dets the CSV has no row for."""
    return {d: coeffs[(d, target)] for d in DETS if (d, target) in coeffs}


def _check_form(z_coeffs, target='Pressure'):
    """Refuse to score a coefficient CSV written for a different functional form.

    predict_z_urban dispatches on the module-level Z_URBAN_FORM, not on the
    CSV's own Formula column, so a mismatch would silently evaluate the wrong
    equation with the right-looking numbers.
    """
    expected = Z_URBAN_FORM.get(target)
    for det in DETS:
        coef = z_coeffs.get((det, target))
        if coef is None:
            continue
        found = coef.get('formula')
        if found != expected:
            raise ValueError(
                f"Z_urban coefficients for det={det} were written for the "
                f"'{found}' form, but z_urban.Z_URBAN_FORM['{target}'] is "
                f"'{expected}'. Re-run run_analysis.py --phase 2 to "
                f"regenerate them, or set Z_URBAN_FORM back to match.")


def build_per_z_table(maxR_df, conv_df, conv_coeffs, z_coeffs):
    """Per-(config, Z) pressure rows inside the convergence radius.

    Returns a DataFrame with the measured and calculated urban radius for
    every valid free-field level, ready to write.
    """
    df = prepare_maxR_data(maxR_df, conv_df)
    conv_P = _by_det(conv_coeffs, 'RadiusP')
    conv_I = _by_det(conv_coeffs, 'RadiusI')

    frames = []
    for det in DETS:
        coef = z_coeffs.get((det, 'Pressure'))
        sub = df[df['det'] == det].dropna(subset=['Z_urban_P', 'RadiusP'])
        if coef is None or len(sub) == 0:
            continue

        valid = sub[z_urban_valid_mask(sub, 'Z_urban_P', 'MaxR_P', 'RadiusP',
                                       'Pressure')].copy()
        if len(valid) == 0:
            continue

        W13 = valid['weight'].values.astype(float) ** (1 / 3)
        z_pred = predict_z_urban(valid['Z_free'].values, valid['rho'].values,
                                 valid['height'].values,
                                 valid['swidth'].values, W13, 'Pressure', coef)
        z_clipped = clip_z_urban_pred(z_pred, valid, det, 'Pressure',
                                      conv_P, conv_I)

        valid['Z_urban_P_calc'] = z_clipped
        valid['MaxR_P_calc'] = z_clipped * W13
        valid['clipped_at_Zconv'] = z_clipped < z_pred - 1e-12
        frames.append(valid)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    # Convergence radius of the parent config, for context on every row.
    out['Rconv_P_calc_m'] = predict_pi(
        out['weight'].values, out['rho'].values, out['height'].values,
        out['det'].values, out['swidth'].values, out['bsize'].values, conv_P)

    table = pd.DataFrame({
        'ConfigName':          out['Config'],
        'Det':                 out['det'].astype(int),
        'Location':            out['det'].map(LOCATION),
        'ChargeWeight':        out['weight'],
        'Z_free':              out['Z_free'],
        'P_ff_kPa':            out['P_ff'],
        'R_free_m':            out['R_free'],
        'MaxR_P_measured_m':   out['MaxR_P'],
        'MaxR_P_calculated_m': out['MaxR_P_calc'],
        'MaxR_P_rel_err_pct':  _rel_err_pct(out['MaxR_P'], out['MaxR_P_calc']),
        'Z_urban_measured':    out['Z_urban_P'],
        'Z_urban_calculated':  out['Z_urban_P_calc'],
        'Lambda_measured':     out['Z_urban_P'] / out['Z_free'],
        'Lambda_calculated':   out['Z_urban_P_calc'] / out['Z_free'],
        'clipped_at_Zconv':    out['clipped_at_Zconv'],
        'Rconv_P_measured_m':  out['RadiusP'],
        'Rconv_P_calculated_m': out['Rconv_P_calc_m'],
        'RadiusEstimator':     out.get('RadiusEstimator', ''),
    })
    table.insert(table.columns.get_loc('MaxR_P_rel_err_pct') + 1,
                 'MaxR_P_err_band', _band_series(table['MaxR_P_rel_err_pct']))
    return table.sort_values(['ConfigName', 'Z_free']).reset_index(drop=True)


def build_per_config_table(conv_df, per_z, maxR_df, conv_coeffs):
    """One row per config: the convergence radius plus its per-Z error summary."""
    conv_P = _by_det(conv_coeffs, 'RadiusP')
    calc = predict_pi(conv_df['ChargeWeight'].values, conv_df['AreaDensity'].values,
                      conv_df['Height'].values, conv_df['Det'].values,
                      conv_df['StreetWidth'].values, conv_df['BuildingSize'].values,
                      conv_P)

    table = pd.DataFrame({
        'ConfigName':           conv_df['ConfigName'],
        'Det':                  conv_df['Det'].astype(int),
        'Location':             conv_df['Det'].map(LOCATION),
        'ChargeWeight':         conv_df['ChargeWeight'],
        'Height':               conv_df['Height'],
        'BuildingSize':         conv_df['BuildingSize'],
        'StreetWidth':          conv_df['StreetWidth'],
        'AreaDensity':          conv_df['AreaDensity'],
        'Rconv_P_measured_m':   conv_df['RadiusP'],
        'Rconv_P_calculated_m': calc,
        'Rconv_P_abs_err_m':    np.abs(calc - conv_df['RadiusP'].values),
        'Rconv_P_rel_err_pct':  _rel_err_pct(conv_df['RadiusP'], calc),
    })
    table['Rconv_P_err_band'] = _band_series(table['Rconv_P_rel_err_pct'])

    n_rows = (maxR_df.groupby('Config').size()
              if len(maxR_df) else pd.Series(dtype=int))
    if len(per_z):
        grp = per_z.groupby('ConfigName')['MaxR_P_rel_err_pct']
        n_valid = grp.size()
        mape = grp.apply(lambda s: float(np.mean(np.abs(s))))
        worst = grp.apply(lambda s: float(np.max(np.abs(s))))
        z_lo = per_z.groupby('ConfigName')['Z_free'].min()
        z_hi = per_z.groupby('ConfigName')['Z_free'].max()
        band = per_z.groupby('ConfigName')['MaxR_P_err_band']
        n_yellow = band.apply(lambda s: int((s == 'yellow').sum()))
        n_red = band.apply(lambda s: int((s == 'red').sum()))
    else:
        n_valid = mape = worst = z_lo = z_hi = pd.Series(dtype=float)
        n_yellow = n_red = pd.Series(dtype=int)

    idx = table['ConfigName']
    table['n_Z_valid'] = idx.map(n_valid).fillna(0).astype(int)
    table['n_Z_dropped'] = (idx.map(n_rows).fillna(0).astype(int)
                            - table['n_Z_valid'])
    table['Z_valid_min'] = idx.map(z_lo)
    table['Z_valid_max'] = idx.map(z_hi)
    table['MaxR_P_MAPE_pct'] = idx.map(mape)
    table['MaxR_P_MAPE_band'] = _band_series(table['MaxR_P_MAPE_pct'])
    table['MaxR_P_worst_abs_err_pct'] = idx.map(worst)
    table['n_Z_yellow'] = idx.map(n_yellow).fillna(0).astype(int)
    table['n_Z_red'] = idx.map(n_red).fillna(0).astype(int)
    return table


# ============================================================
# Excel output
# ============================================================

# Excel's own "Light Red Fill with Dark Red Text" / "Yellow Fill with Dark
# Yellow Text" pair, so the sheets look like ordinary conditional formatting
# and stay readable when printed.
BAND_FILL = {'red':    ('FFC7CE', '9C0006'),
             'yellow': ('FFEB9C', '9C6500')}

# Which error column grades which columns on each sheet. The error cell is
# always painted; the extra columns are painted with it so a flagged row reads
# as one block rather than a lone coloured number.
SHEET_BANDING = {
    'By config': [
        ('Rconv_P_err_band', ('Rconv_P_measured_m', 'Rconv_P_calculated_m',
                              'Rconv_P_abs_err_m', 'Rconv_P_rel_err_pct')),
        ('MaxR_P_MAPE_band', ('MaxR_P_MAPE_pct', 'MaxR_P_worst_abs_err_pct')),
    ],
    'By Z': [
        ('MaxR_P_err_band', ('MaxR_P_measured_m', 'MaxR_P_calculated_m',
                             'MaxR_P_rel_err_pct')),
    ],
}

# Number format per column-name suffix, most specific first. Only the signed
# relative errors carry an explicit sign — MAPE and worst-|error| are unsigned
# by construction and a leading '+' on them would read as a direction.
NUM_FORMATS = (('rel_err_pct', '+0.00;-0.00'), ('_pct', '0.00'), ('_m', '0.00'),
               ('P_ff_kPa', '0.00'), ('Z_urban_measured', '0.000'),
               ('Z_urban_calculated', '0.000'), ('Lambda_measured', '0.000'),
               ('Lambda_calculated', '0.000'), ('Z_free', '0'),
               ('AreaDensity', '0.0000'))


def _number_format(column):
    for suffix, fmt in NUM_FORMATS:
        if column == suffix or column.endswith(suffix):
            return fmt
    return None


def _style_sheet(ws, df, band_specs):
    """Freeze the header, add an autofilter, size the columns, paint the bands."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    cols = list(df.columns)
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions

    for i, name in enumerate(cols, start=1):
        letter = get_column_letter(i)
        header = ws.cell(row=1, column=i)
        header.font = Font(bold=True)
        header.alignment = Alignment(horizontal='center', wrap_text=True)
        # Long config names need the room; everything else fits its header.
        ws.column_dimensions[letter].width = max(11, min(len(name) + 3, 40))
        fmt = _number_format(name)
        if fmt:
            for row in range(2, len(df) + 2):
                ws.cell(row=row, column=i).number_format = fmt
    if 'ConfigName' in cols:
        ws.column_dimensions[
            get_column_letter(cols.index('ConfigName') + 1)].width = 38

    fills = {band: PatternFill('solid', start_color=bg, end_color=bg)
             for band, (bg, _) in BAND_FILL.items()}
    fonts = {band: Font(color=fg) for band, (_, fg) in BAND_FILL.items()}

    for band_col, painted in band_specs:
        if band_col not in cols:
            continue
        targets = [cols.index(c) + 1 for c in painted if c in cols]
        for offset, band in enumerate(df[band_col].values):
            if band not in fills:
                continue
            for col_idx in targets:
                cell = ws.cell(row=offset + 2, column=col_idx)
                cell.fill = fills[band]
                cell.font = fonts[band]


def _notes_frame(method, per_config, per_z):
    """The 'Notes' sheet: what the workbook is and how to read the colours."""
    n_cfg = per_config['Rconv_P_err_band'].value_counts()
    n_row = (per_z['MaxR_P_err_band'].value_counts() if len(per_z)
             else pd.Series(dtype=int))
    return pd.DataFrame([
        ('Radius estimator', method),
        ('Coefficients', 'final_production_* — fitted on ALL configs, so '
                         'every error here is IN-SAMPLE'),
        ('Held-out check', r'tools\check_formulas\check_formulas.py'),
        ('', ''),
        ('Colour — yellow', f'|relative error| between {ERR_YELLOW_PCT:g}% '
                            f'and {ERR_RED_PCT:g}%'),
        ('Colour — red', f'|relative error| above {ERR_RED_PCT:g}%'),
        ('Band columns', 'The *_band columns hold the same grading as text, '
                         'so you can sort and filter on it'),
        ('', ''),
        ('Sheet "By config"', 'One row per configuration: the pressure '
                              'convergence radius, measured vs calculated'),
        ('Sheet "By Z"', 'One row per (config, free-field level Z) inside the '
                         'convergence radius: the pressure that level '
                         'represents and the radius from (0,0) where the '
                         'urban field still delivers it'),
        ('Rows dropped', 'Z levels outside the convergence radius, inside the '
                         'first street, or below Z=2 are excluded '
                         '(z_urban.z_urban_valid_mask)'),
        ('', ''),
        ('Configs ok / yellow / red',
         ' / '.join(str(int(n_cfg.get(b, 0))) for b in ('ok', 'yellow', 'red'))),
        ('Z rows ok / yellow / red',
         ' / '.join(str(int(n_row.get(b, 0))) for b in ('ok', 'yellow', 'red'))),
    ], columns=['Item', 'Value'])


def write_workbook(path, per_config, per_z, method):
    """Write the two tables to one .xlsx, with the error bands as cell colours."""
    try:
        import openpyxl  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            'Writing the .xlsx report needs openpyxl.  pip install openpyxl'
        ) from exc

    sheets = {'By config': per_config, 'By Z': per_z,
              'Notes': _notes_frame(method, per_config, per_z)}
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
        for name, df in sheets.items():
            if name == 'Notes':
                continue
            _style_sheet(writer.sheets[name], df, SHEET_BANDING[name])
        notes = writer.sheets['Notes']
        notes.column_dimensions['A'].width = 26
        notes.column_dimensions['B'].width = 96
        for row in range(1, len(sheets['Notes']) + 2):
            notes.cell(row=row, column=2).alignment = _wrap()
    return path


def _wrap():
    from openpyxl.styles import Alignment
    return Alignment(wrap_text=True, vertical='top')


def _band_counts(progress, bands, color, label):
    """One line of ok / yellow / red counts, each painted in its own colour."""
    n = {b: int((bands == b).sum()) for b in ('ok', 'yellow', 'red')}
    parts = [_paint(f'{b} {n[b]}', b, color) for b in ('ok', 'yellow', 'red')]
    progress(f'  {label}: ' + '   '.join(parts)
             + f'   (yellow >= {ERR_YELLOW_PCT:g}%, red > {ERR_RED_PCT:g}%)')


def _print_summary(progress, per_config, per_z, color=False):
    """Console summary: overall fit quality plus every flagged config.

    Relative errors are painted by band — yellow at 10-20%, red above 20% —
    when *color* is on (see _enable_ansi).
    """
    meas = per_config['Rconv_P_measured_m'].values
    calc = per_config['Rconv_P_calculated_m'].values
    R2, MAPE = r2_mape(meas, calc)

    progress('')
    progress('-' * 66)
    progress(f'CONVERGENCE RADIUS (pressure) — {len(per_config)} configs')
    progress('-' * 66)
    progress(f'  R2 = {R2:.4f}    MAPE = {MAPE:.2f}%')
    for det in DETS:
        m = per_config['Det'] == det
        if not m.any():
            continue
        r2d, mad = r2_mape(meas[m.values], calc[m.values])
        progress(f'    det={det} ({LOCATION[det]:<12}) n={int(m.sum()):>3}  '
                 f'R2 = {r2d:.4f}  MAPE = {mad:.2f}%')
    _band_counts(progress, per_config['Rconv_P_err_band'], color, 'configs')

    flagged = per_config[per_config['Rconv_P_err_band'].isin(('yellow', 'red'))]
    flagged = flagged.reindex(
        flagged['Rconv_P_rel_err_pct'].abs().sort_values(ascending=False).index)
    progress(f'  flagged configs ({len(flagged)}):')
    for _, row in flagged.iterrows():
        line = (f'    {row["ConfigName"]:<38} '
                f'measured {row["Rconv_P_measured_m"]:7.2f} m  '
                f'calc {row["Rconv_P_calculated_m"]:7.2f} m  '
                f'{row["Rconv_P_rel_err_pct"]:+7.2f}%')
        progress(_paint(line, row['Rconv_P_err_band'], color))

    progress('')
    progress('-' * 66)
    progress(f'URBAN RADIUS PER Z (pressure) — {len(per_z)} rows inside R_conv')
    progress('-' * 66)
    if not len(per_z):
        progress('  no valid rows')
        return

    R2z, MAPEz = r2_mape(per_z['MaxR_P_measured_m'].values,
                         per_z['MaxR_P_calculated_m'].values)
    n_clip = int(per_z['clipped_at_Zconv'].sum())
    progress(f'  R2 = {R2z:.4f}    MAPE = {MAPEz:.2f}%'
             f'    clipped at Z_conv: {n_clip} rows')
    for det in DETS:
        m = (per_z['Det'] == det).values
        if not m.any():
            continue
        r2d, mad = r2_mape(per_z['MaxR_P_measured_m'].values[m],
                           per_z['MaxR_P_calculated_m'].values[m])
        progress(f'    det={det} ({LOCATION[det]:<12}) n={int(m.sum()):>4}  '
                 f'R2 = {r2d:.4f}  MAPE = {mad:.2f}%')
    _band_counts(progress, per_z['MaxR_P_err_band'], color, 'rows   ')

    cov = per_config['n_Z_valid']
    progress(f'  Z levels kept per config: min {int(cov.min())}, '
             f'median {cov.median():.0f}, max {int(cov.max())}  '
             f'({int((cov == 0).sum())} configs contribute none)')

    flagged = per_config[per_config['MaxR_P_MAPE_band'].isin(('yellow', 'red'))]
    flagged = flagged.sort_values('MaxR_P_MAPE_pct', ascending=False)
    progress(f'  flagged configs by per-Z MAPE ({len(flagged)}):')
    for _, row in flagged.iterrows():
        line = (f'    {row["ConfigName"]:<38} '
                f'n={int(row["n_Z_valid"]):>2}  '
                f'MAPE {row["MaxR_P_MAPE_pct"]:6.2f}%  '
                f'worst {row["MaxR_P_worst_abs_err_pct"]:6.2f}%  '
                f'[{int(row["n_Z_yellow"])} yellow, {int(row["n_Z_red"])} red]')
        progress(_paint(line, row['MaxR_P_MAPE_band'], color))


def main(*, tables_dir=None, out_dir=None, radius_method=None, color=None,
         progress=print):
    """Build both pressure tables and write them to *out_dir*.

    color : None | bool
        Paint the console's relative errors by band. None auto-detects an
        interactive terminal, which is what a GUI capture or a redirect to a
        file needs — they would otherwise receive the escape codes as text.

    Returns a dict of the headline metrics and the two output paths.
    """
    color = _enable_ansi() if color is None else bool(color)
    est = resolve_estimator(radius_method)
    method = est['method']
    tables = paths.resolve(tables_dir, paths.TABLES_DIR)
    out = paths.ensure_dir(paths.resolve(out_dir, paths.CHECK_RESULTS_DIR))

    conv_csv = paths.conv_csv(method, tables)
    maxr_csv = paths.maxr_csv(method, tables)
    conv_coef_csv = tables / paths.suffixed(
        'final_production_convergence_coefficients.csv', method)
    z_coef_csv = tables / paths.suffixed(
        'final_production_z_urban_coefficients.csv', method)

    for path, what in ((conv_csv, 'convergence table'),
                       (maxr_csv, 'max-radius table'),
                       (conv_coef_csv, 'convergence coefficients'),
                       (z_coef_csv, 'Z_urban coefficients')):
        if not Path(path).is_file():
            raise FileNotFoundError(
                f'Missing the {what} for radius method {method!r}: {path}\n'
                f'Run:  python run_analysis.py --phase all '
                f'--radius-method {method}')

    progress('=' * 66)
    progress(f'  PRESSURE REPORT — radius method {method!r}')
    progress('=' * 66)
    progress(f'  tables      {_rel(conv_csv)}')
    progress(f'              {_rel(maxr_csv)}')
    progress(f'  coeffs      {conv_coef_csv.name}')
    progress(f'              {z_coef_csv.name}')
    progress('  NOTE: production coefficients are fitted on ALL configs, so '
             'every error below is IN-SAMPLE.')

    conv_df = pd.read_csv(conv_csv)
    maxR_df = pd.read_csv(maxr_csv)
    conv_coeffs = load_convergence_coefficients(conv_coef_csv)
    z_coeffs = load_nonlinear_coefficients(z_coef_csv)
    _check_form(z_coeffs, 'Pressure')

    per_z = build_per_z_table(maxR_df, conv_df, conv_coeffs, z_coeffs)
    per_config = build_per_config_table(conv_df, per_z, maxR_df, conv_coeffs)

    xlsx_out = out / paths.suffixed('pressure_report.xlsx', method)
    write_workbook(xlsx_out, per_config, per_z, method)

    _print_summary(progress, per_config, per_z, color=color)

    progress('')
    progress(f'Saved: {_rel(xlsx_out)}')

    R2, MAPE = r2_mape(per_config['Rconv_P_measured_m'].values,
                       per_config['Rconv_P_calculated_m'].values)
    if len(per_z):
        R2z, MAPEz = r2_mape(per_z['MaxR_P_measured_m'].values,
                             per_z['MaxR_P_calculated_m'].values)
    else:
        R2z = MAPEz = np.nan
    return {'method': method, 'n_configs': len(per_config),
            'n_z_rows': len(per_z),
            'conv_R2_P': R2, 'conv_MAPE_P': MAPE,
            'maxR_R2_P': R2z, 'maxR_MAPE_P': MAPEz,
            'xlsx': str(xlsx_out)}


def cli(argv=None):
    p = argparse.ArgumentParser(
        description='Per-config pressure report: measured vs calculated '
                    'convergence radius, and the urban radius at every '
                    'free-field level inside it.')
    p.add_argument('--tables-dir', default=None,
                   help='Folder with the table/coefficient CSVs.')
    p.add_argument('--out-dir', default=None,
                   help='Output folder (default outputs/check_results).')
    p.add_argument('--radius-method', default=None, dest='radius_method',
                   help='Which radius-estimator run to report on: '
                        f'{"|".join(VALID_METHODS)}, pXX, or a soft token '
                        "like 'req_soft3' (default: "
                        'constants.RADIUS_ESTIMATOR).')
    g = p.add_mutually_exclusive_group()
    g.add_argument('--no-color', action='store_false', dest='color',
                   default=None,
                   help='Never colour the console output (default: colour '
                        'when stdout is an interactive terminal).')
    g.add_argument('--color', action='store_true', dest='color',
                   help='Force colour even when stdout is redirected.')
    args = p.parse_args(argv)
    return main(tables_dir=args.tables_dir, out_dir=args.out_dir,
                radius_method=args.radius_method, color=args.color)


if __name__ == '__main__':
    cli()
