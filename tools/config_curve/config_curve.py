"""Peak pressure (or impulse) vs scaled distance for ONE configuration.

Two curves on one log-log plot:

  1. Free field   — P_ff vs Z, straight out of max_radius_per_Z_<method>.csv.
  2. Urban        — reconstructed, not stored. MaxR_P is defined as the radius
                    at which the urban peak equals the free-field peak at
                    Z_free, so every row hands us one point of the urban curve:

                        (Z_urban, P_ff)   with  Z_urban = MaxR_P / W^(1/3)

                    Plotted in order of Z_free. Rows with a NaN MaxR_P carry no
                    urban point and are dropped.

The measured convergence distance Z_conv = RadiusP / W^(1/3) (from the
convergence table) is drawn as a vertical line: beyond it the two curves are
meant to coincide, so it marks where the urban curve should rejoin free field.

Usage:
    python tools\\config_curve\\config_curve.py                    # prompts
    python tools\\config_curve\\config_curve.py 41                 # config number
    python tools\\config_curve\\config_curve.py config_41_det2_b15_s5_h12_w500
    python tools\\config_curve\\config_curve.py 41 --target impulse
    python tools\\config_curve\\config_curve.py 41 --x R      # metres, not Z
    python tools\\config_curve\\config_curve.py 5 --radius-method p95

The config may be given as its number (41, or 041/'41') or as the full name.
Omit it — or --x — and the tool asks; both prompts are skipped when the flag
is already on the command line, so scripted calls never block.

--x R rescales the axis to real distance, R = Z * W^(1/3), with W the config's
charge weight (the ChargeWeight column, which matches the _wNNN name suffix).
Only the axis changes — the curves keep their shape.

--context draws other configs' urban curves as thin grey lines behind, for
comparison. Bare --context takes every other config; naming filters restricts
it. A bare name means "same value as this config", NAME=LO:HI means "within
that range", and either end of a range may be left blank:

    --context weight det              same charge weight AND detonation type
    --context weight det hs=0.8:1.5   ...and H/s between 0.8 and 1.5
    --context rho=0.3:0.6             rho in [0.3, 0.6], anything else
    --context sW13=1.0:               s/W^(1/3) at least 1.0

The same plot is available live in the GUI ("Config Curve" tab), which redraws
on every change and writes a file only when asked — main() takes save=False to
return the Figure instead of saving it.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from blastlib import constants, paths
from blastlib.processing.radius_estimator import (resolve_estimator, radius_label,
                                                  VALID_METHODS)
from blastlib.regression.z_urban import Z_URBAN_ZF_MIN

# Per-target column names and labelling. Everything downstream reads from here,
# so pressure and impulse differ only by this table.
TARGETS = {
    'pressure': dict(ff_col='P_ff', maxr_col='MaxR_P', conv_col='RadiusP',
                     symbol='P', name='Peak Pressure', unit='kPa', token='P',
                     beyond_col='beyond_P', fit_name='Pressure'),
    'impulse':  dict(ff_col='I_ff', maxr_col='MaxR_I', conv_col='RadiusI',
                     symbol='I', name='Peak Impulse', unit='kPa·ms', token='I',
                     beyond_col='beyond_I', fit_name='Impulse'),
}


def criterion_band(target, W13):
    """Convergence criterion for one target, in the plot's y-units.

    Returns (half_width, relative, band_label, floor, floor_label). The band
    is ff ± half_width when *relative* is False and ff·(1 ± half_width) when
    it is True. *floor* is the level below which a cell converges
    automatically regardless of the difference, or None when the criterion
    has no such clause.

    Pressure (grids.py: conv_P = lowP | small_diff_P) is a two-clause OR:

        |P_urban - P_free| < 10 kPa   OR   P_urban < 10 kPa

    so the band alone tells half the story — past the floor everything
    converges. NOTE the floor clause tests the URBAN field; free field is used
    here as the drawn proxy, since the urban curve is a reconstruction and has
    no value at a given x to threshold. The two cross within a Z of each other.

    Impulse criterion D35: a cell is free-field in impulse if |I/I_ff − 1| ≤ 0.10 or I/W^(1/3) < 23.6 Pa·s/kg^(1/3).
    The floor is the scaled free-field impulse at the Z where the reference overpressure is 10 kPa (Z ≈ 11.6), i.e. the same
    contour and IATG level as the pressure floor.

    The plot's impulse unit, kPa·ms, equals Pa·s, so the floor is drawn at
    floor_scaled·W^(1/3) directly. As for pressure, the floor clause tests the
    URBAN impulse and the free-field curve is its drawn proxy.
    """
    if target == 'pressure':
        half = float(constants.PARAMS['minPressure_kPa'])
        return (half, False, f'±{half:g} kPa convergence band',
                half, f'{half:g} kPa relevance floor — everything below converges')

    rel = float(constants.IMPULSE_CRITERION['rel_band'])
    thr = float(constants.IMPULSE_CRITERION['floor_scaled'])
    floor = thr * W13
    return (rel, True, f'±{rel * 100:g}% of I$_{{ff}}$ convergence band',
            floor, f'{thr:g}·W$^{{1/3}}$ = {floor:.0f} relevance floor — '
                   'everything below converges')


def resolve_config(token, known):
    """Map a user token to a config name in *known*.

    Accepts the full name, or the config number in any form the user is likely
    to type ('41', '041', '4' for config_04). Returns None if the token matches
    nothing, or if a number somehow matches more than one config.
    """
    token = str(token).strip()
    if not token:
        return None
    if token in known:
        return token

    if token.isdigit():
        n = int(token)
        hits = [c for c in known if _config_number(c) == n]
        return hits[0] if len(hits) == 1 else None

    # tolerate a name given without the trailing geometry, e.g. 'config_41'
    hits = [c for c in known if c.startswith(token)]
    return hits[0] if len(hits) == 1 else None


def _config_number(name):
    """Leading number of a config name ('config_41_...' -> 41), or None."""
    m = re.match(r'config_(\d+)_', name)
    return int(m.group(1)) if m else None


def _describe(known):
    """One-line-per-config listing, for the interactive prompt."""
    lines = []
    for c in sorted(known):
        n = _config_number(c)
        lines.append(f'  {n:>3}  {c}' if n is not None else f'       {c}')
    return '\n'.join(lines)


def _ask_x_axis(progress=print):
    """Ask for the x axis; None if stdin is unusable. Enter accepts Z."""
    while True:
        try:
            ans = input('X axis — Z = scaled distance, R = metres '
                        '[Z/R, Enter for Z]: ').strip().upper()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if ans == '':
            return 'Z'
        if ans in ('Z', 'R'):
            return ans
        progress('  invalid — enter Z or R')


def _ask_config(known, progress=print):
    """Ask for a config until one resolves; None if stdin is unusable."""
    while True:
        try:
            ans = input('Config number or full name (e.g. 41, or "?" to list): ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if ans in ('?', 'list'):
            progress(_describe(known))
            continue
        config = resolve_config(ans, known)
        if config is not None:
            return config
        progress(f'  no config matches {ans!r} — enter a number 1-{len(known)}, '
                 'a full name, or "?" to list them')


# Per-decade tick mantissas: every integer in the first decade (where the
# curves bend), thinning out higher up so labels do not collide once the log
# axis compresses them. Applied to each decade the data spans, so this works
# for Z (~1-30) and for R in metres (~2-250) alike.
TICK_MANTISSAS = [1, 2, 3, 4, 5, 6, 7, 8, 9]
SPARSE_MANTISSAS = [1, 1.5, 2, 3, 4, 5, 7.5]


def _ladder(mantissas, lo, hi):
    """Tick positions from one mantissa ladder, repeated over every decade."""
    ticks = []
    decade = 10.0 ** np.floor(np.log10(lo))
    while decade <= hi:
        ticks += [m * decade for m in mantissas]
        decade *= 10
    return [t for t in ticks if lo * 0.95 <= t <= hi * 1.05]


def _decimal_log_ticks(lo, hi, max_labels=14):
    """Plain-number tick positions covering [lo, hi] on a log axis.

    Prefers the dense 1,2,3,...,9 ladder and falls back to the sparse one only
    when the dense one would produce more labels than fit — a fixed span
    threshold cannot serve both Z (~1-30) and R in metres (~8-230), since the
    dense ladder collides at the top of each decade (...70 80 90 100).
    """
    dense = _ladder(TICK_MANTISSAS, lo, hi)
    if len(dense) <= max_labels:
        return dense
    return _ladder(SPARSE_MANTISSAS, lo, hi)


def _decimal_log_yaxis(ax, lo, hi):
    """Plain-number labels on the log y-axis over the cropped [lo, hi] range.

    After cropping, the range often spans barely one decade, where the default
    log locator labels only the decade itself (a single '10^2') and leaves the
    rest of the axis unreadable.
    """
    ticks = _decimal_log_ticks(lo, hi)
    if len(ticks) < 2:
        return
    ax.set_yticks(ticks)
    ax.set_yticklabels([f'{t:g}' for t in ticks])
    ax.set_yticks([], minor=True)


def _decimal_log_xaxis(ax, values):
    """Label the log x-axis with plain numbers (1, 2, 3, ...) not 10^n.

    Only ticks inside the data range are kept, and matplotlib's minor ticks are
    cleared — otherwise the unlabelled minor ticks sit between our labels and
    read as if they were the decades.
    """
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v) & (v > 0)]
    if v.size == 0:
        return

    ticks = _decimal_log_ticks(v.min(), v.max())
    if len(ticks) < 2:            # very narrow range — let matplotlib decide
        return

    ax.set_xticks(ticks)
    ax.set_xticklabels([f'{t:g}' for t in ticks])
    ax.set_xticks([], minor=True)


def median_lambda(sub, tgt, W13):
    """Median amplification Lambda = Z_urban/Z_free over the valid rows.

    'Valid' is the same domain the Z_urban model is fitted on: inside the
    convergence radius (the beyond_* flag — beyond it the urban field IS the
    free field, so the row carries no urban information) and Z_free above the
    validity floor. Returns (median, zf_lo, zf_hi, n), or None if no row
    qualifies.
    """
    zf_min = Z_URBAN_ZF_MIN[tgt['fit_name']]
    maxr = pd.to_numeric(sub[tgt['maxr_col']], errors='coerce')
    Z_free = sub['Z'].astype(float)

    # Phase 1 writes booleans, but a CSV round-trip can leave 'True'/'False'
    # strings, and every non-empty string is truthy — coerce explicitly.
    beyond = sub[tgt['beyond_col']].map(
        lambda v: str(v).strip().lower() in ('true', '1', '1.0')
        if not isinstance(v, (bool, np.bool_)) else bool(v))

    valid = ~beyond & (Z_free >= zf_min) & np.isfinite(maxr)
    if not valid.any():
        return None

    lam = (maxr[valid] / W13) / Z_free[valid]
    zf = Z_free[valid]
    return float(lam.median()), float(zf.min()), float(zf.max()), int(valid.sum())


def _urban_label(config, row):
    """Readable legend entry for the urban curve.

    'Urban configuration No. 2 - Det.1  b=15m  s=5m  h=4m  w=500 kg-TNT'
    """
    n = _config_number(config)
    number = f'No. {n}' if n is not None else config
    return (f'Urban configuration {number} - Det.{int(row["Det"])}  '
            f'b={_num(row["BuildingSize"])}m  s={_num(row["StreetWidth"])}m  '
            f'h={_num(row["Height"])}m  w={_num(row["ChargeWeight"])} kg-TNT')


def _num(v):
    """Format a numeric field without a trailing '.0' (15.0 -> '15')."""
    return f'{float(v):g}'


def _pi_groups(row):
    """The three geometric Pi groups for one convergence-table row.

    rho is read from the table (AreaDensity) rather than recomputed, so this
    stays consistent with whatever the analysis actually fitted.
    """
    W13 = float(row['ChargeWeight']) ** (1 / 3)
    return {
        'rho':  float(row['AreaDensity']),
        'sW13': float(row['StreetWidth']) / W13,
        'Hs':   float(row['Height']) / float(row['StreetWidth']),
        'W13':  W13,
    }


def _curve(maxr_df, config, tgt):
    """Free-field and reconstructed urban points for one config.

    Returns (sub, Z_free, ff, maxr), all sorted by Z_free. *sub* is the raw row
    subset, kept so the Lambda summary can apply the fit's own validity mask to
    the same rows.
    """
    sub = maxr_df[maxr_df['Config'] == config].sort_values('Z')

    Z_free = sub['Z'].to_numpy(dtype=float)
    ff = sub[tgt['ff_col']].to_numpy(dtype=float)
    maxr = pd.to_numeric(sub[tgt['maxr_col']], errors='coerce').to_numpy(dtype=float)

    return sub, Z_free, ff, maxr


# Which columns the context filters match on. 'exact' compares the raw column;
# 'derived' compares a Pi group computed per row. Values are matched against
# the focus config's own value, so every filter reads "same <thing> as this
# config" — the comparison the plot is for.
CONTEXT_FILTERS = {
    'weight': dict(label='same charge weight', col='ChargeWeight', kind='exact'),
    'det':    dict(label='same detonation type', col='Det', kind='exact'),
    'b':      dict(label='same building size', col='BuildingSize', kind='exact'),
    's':      dict(label='same street width', col='StreetWidth', kind='exact'),
    'h':      dict(label='same height', col='Height', kind='exact'),
    'rho':    dict(label='same ρ', col='AreaDensity', kind='exact'),
    'hs':     dict(label='same H/s', col='Hs', kind='derived'),
    'sW13':   dict(label='same s/W^(1/3)', col='sW13', kind='derived'),
}

# Pi groups are floats built from divisions, so equality needs a tolerance;
# distinct design points differ by far more than this.
_PI_TOL = 1e-6


def _with_derived(conv_df):
    """Add the derived Pi-group columns the context filters can match on."""
    out = conv_df.copy()
    W13 = out['ChargeWeight'].astype(float) ** (1 / 3)
    out['Hs'] = out['Height'].astype(float) / out['StreetWidth'].astype(float)
    out['sW13'] = out['StreetWidth'].astype(float) / W13
    return out


def normalise_filters(filters):
    """Accept the several shapes a caller may express filters in.

    Returns an ordered dict {key: None | (lo, hi)} where None means "same value
    as the focus config" and a pair means "within this inclusive range".

    Understood inputs:
        ['weight', 'det']                       both matched by equality
        {'weight': None, 'hs': (0.8, 1.5)}      mixed equality and range
        [('hs', (0.8, 1.5)), 'det']             pairs and bare keys together

    A range with a None end is open on that side: (0.8, None) means >= 0.8.
    """
    if filters is None:
        return {}

    items = filters.items() if isinstance(filters, dict) else filters

    out = {}
    for item in items:
        if isinstance(item, str):
            key, bounds = item, None
        else:
            key, bounds = item

        if key not in CONTEXT_FILTERS:
            raise ValueError(f'unknown context filter {key!r}; '
                             f'expected from {sorted(CONTEXT_FILTERS)}')

        if bounds is not None:
            lo, hi = bounds
            lo = None if lo is None else float(lo)
            hi = None if hi is None else float(hi)
            if lo is not None and hi is not None and lo > hi:
                raise ValueError(f'{key}: range low {lo} exceeds high {hi}')
            bounds = (lo, hi)

        out[key] = bounds
    return out


def _parse_context_arg(token):
    """Parse one --context token into a key or a (key, (lo, hi)) pair.

    'det'            -> 'det'
    'hs=0.8:1.5'     -> ('hs', (0.8, 1.5))
    'hs=0.8:'        -> ('hs', (0.8, None))
    'rho=:0.5'       -> ('rho', (None, 0.5))

    Raises argparse.ArgumentTypeError so a bad value is reported as a usage
    error rather than a traceback.
    """
    token = token.strip()
    key, sep, spec = token.partition('=')
    key = key.strip()

    if key not in CONTEXT_FILTERS:
        raise argparse.ArgumentTypeError(
            f'unknown filter {key!r}; choose from '
            f'{", ".join(sorted(CONTEXT_FILTERS))}')

    if not sep:
        return key

    if ':' not in spec:
        raise argparse.ArgumentTypeError(
            f'{token!r}: a range needs LO:HI (either end may be blank), '
            f'e.g. {key}=0.8:1.5')

    lo_s, _, hi_s = spec.partition(':')

    def _num(text, which):
        text = text.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f'{token!r}: {which} bound {text!r} is not a number')

    lo, hi = _num(lo_s, 'low'), _num(hi_s, 'high')
    if lo is None and hi is None:
        raise argparse.ArgumentTypeError(
            f'{token!r}: a range needs at least one bound')
    if lo is not None and hi is not None and lo > hi:
        raise argparse.ArgumentTypeError(
            f'{token!r}: low bound {lo:g} exceeds high bound {hi:g}')
    return key, (lo, hi)


def _range_label(key, lo, hi):
    """Legend text for one range filter ('H/s 0.8-1.5')."""
    name = CONTEXT_FILTERS[key]['label'].replace('same ', '')
    if lo is not None and hi is not None:
        return f'{name} {lo:g}–{hi:g}'
    if lo is not None:
        return f'{name} ≥ {lo:g}'
    if hi is not None:
        return f'{name} ≤ {hi:g}'
    return name          # both open — no restriction at all


def select_context(conv_df, config, filters):
    """Config names to draw as background context.

    *filters* is anything normalise_filters accepts. Each entry narrows the set
    either to configs sharing the focus config's value (bare key) or to configs
    whose value falls in a given range. No filters means every other config;
    the focus config itself is always excluded.

    Returns (names, description) where *description* names the restriction in
    the legend.
    """
    spec_map = normalise_filters(filters)

    df = _with_derived(conv_df)
    focus = df[df['ConfigName'] == config]
    if focus.empty:
        return [], ''
    focus = focus.iloc[0]

    mask = df['ConfigName'] != config
    parts = []
    for key, bounds in spec_map.items():
        spec = CONTEXT_FILTERS[key]
        values = df[spec['col']].astype(float)

        if bounds is None:
            target_val = float(focus[spec['col']])
            if spec['kind'] == 'exact':
                mask &= values == target_val
            else:
                # Pi groups are floats built from divisions, so equality needs
                # a tolerance; distinct design points differ by far more.
                mask &= (values - target_val).abs() < _PI_TOL
            parts.append(spec['label'])
        else:
            lo, hi = bounds
            # inclusive on both ends, with the tolerance applied so a bound
            # typed as the exact value of a design point still admits it
            if lo is not None:
                mask &= values >= lo - _PI_TOL
            if hi is not None:
                mask &= values <= hi + _PI_TOL
            parts.append(_range_label(key, lo, hi))

    names = sorted(df.loc[mask, 'ConfigName'])
    desc = ', '.join(parts) if parts else 'all other configs'
    return names, desc


def main(config, *, target='pressure', x_axis='Z', context=None, maxr_csv=None,
         conv_csv=None, out_dir=None, radius_method=None, save=True, fig=None,
         progress=print):
    """Render the two-curve figure for *config*.

    Returns the written PNG path when *save* is true, otherwise the Figure —
    so a GUI can redraw on every widget change and only write a file when the
    user asks. Pass *fig* to draw into an existing Figure (it is cleared
    first), which lets an embedded canvas reuse one object across redraws
    instead of leaking a new one each time.

    *x_axis* is 'Z' for scaled distance or 'R' for real distance in metres
    (R = Z * W^(1/3), W taken from the config's ChargeWeight).

    *context* selects which other configs are drawn as thin grey lines behind
    the focus curves — see normalise_filters for the accepted shapes (bare keys
    mean "same value", pairs give a range). An empty iterable draws every other
    config; None draws no context at all.
    """
    if target not in TARGETS:
        raise ValueError(f'target must be one of {sorted(TARGETS)}, got {target!r}')
    tgt = TARGETS[target]

    x_axis = str(x_axis).strip().upper()
    if x_axis not in ('Z', 'R'):
        raise ValueError(f"x_axis must be 'Z' or 'R', got {x_axis!r}")

    method = resolve_estimator(radius_method)['method']
    maxr_csv = paths.resolve(maxr_csv, paths.maxr_csv(method))
    conv_csv = paths.resolve(conv_csv, paths.conv_csv(method))
    out_dir = paths.ensure_dir(paths.resolve(
        out_dir, paths.FIGURES_DIR / 'config_curve' / method))

    for path in (maxr_csv, conv_csv):
        if not Path(path).exists():
            progress(f'ERROR: {path} not found. Run run_analysis.py first.')
            return None

    maxr_df = pd.read_csv(maxr_csv)
    conv_df = pd.read_csv(conv_csv)

    known = set(maxr_df['Config'])
    resolved = resolve_config(config, known)
    if resolved is None:
        progress(f'ERROR: config {config!r} not found in {maxr_csv}.')
        progress('Known configs, e.g.: '
                 + ', '.join(sorted(known)[:3]) + ', ...')
        return None
    config = resolved

    conv_rows = conv_df[conv_df['ConfigName'] == config]
    if conv_rows.empty:
        progress(f'ERROR: config {config!r} not found in {conv_csv}.')
        return None
    conv_row = conv_rows.iloc[0]
    pi = _pi_groups(conv_row)

    sub, Z_free, ff, maxr = _curve(maxr_df, config, tgt)

    # Reconstruct the urban curve: each row contributes one point at the radius
    # where urban equals the free-field level of that row.
    urban_ok = np.isfinite(maxr)
    Z_urban = maxr[urban_ok] / pi['W13']
    ff_urban = ff[urban_ok]

    n_skipped = int((~urban_ok).sum())
    if n_skipped:
        progress(f'  {n_skipped} row(s) with NaN {tgt["maxr_col"]} skipped '
                 f'on the urban curve.')
    if Z_urban.size == 0:
        progress(f'ERROR: no finite {tgt["maxr_col"]} for {config} — '
                 'nothing to plot for the urban curve.')
        return None

    Z_conv = float(conv_row[tgt['conv_col']]) / pi['W13']

    # R = Z * W^(1/3); on the Z axis the factor is 1, so both axes share a path.
    # The conversion is exact, so the curves keep their shape and only the tick
    # values change.
    scale = pi['W13'] if x_axis == 'R' else 1.0
    x_free, x_urban, x_conv = Z_free * scale, Z_urban * scale, Z_conv * scale
    x_label = ('R  [m]' if x_axis == 'R'
               else 'Z = R / W$^{1/3}$  [m / kg$^{1/3}$]')
    conv_sym = 'R' if x_axis == 'R' else 'Z'
    conv_fmt = f'{x_conv:.1f} m' if x_axis == 'R' else f'{x_conv:.2f}'

    # ---- plot ----
    if fig is None:
        if save:
            fig, ax = plt.subplots(figsize=(9, 7))
        else:
            # An unsaved figure is handed to the caller, so nothing here can
            # close it. Build it off pyplot's global registry — a pyplot figure
            # is retained until explicitly closed, so a loop of save=False
            # calls would pile them up (and warn at 20).
            fig = Figure(figsize=(9, 7))
            ax = fig.add_subplot(111)
    else:
        # reuse the caller's Figure (an embedded canvas) rather than creating a
        # new one per redraw, which would leak figures for the process lifetime
        fig.clear()
        ax = fig.add_subplot(111)
    fig.patch.set_facecolor('white')

    # Convergence band around free field. Anything inside it counts as
    # converged, which is why the two curves can stay visibly apart past
    # Z_conv and still satisfy the criterion.
    half, relative, band_label, floor, floor_label = criterion_band(
        target, pi['W13'])
    band_lo = ff * (1 - half) if relative else ff - half
    band_hi = ff * (1 + half) if relative else ff + half

    # The level below which the criterion stops discriminating, and so the
    # level the plot is cropped to: the floor clause of the OR (10 kPa for
    # pressure, 23.6·W^(1/3) Pa·s for impulse, D35).
    cut = floor if floor is not None else half
    band = ff >= cut

    if floor is not None:
        ax.axhline(floor, color='darkorange', linestyle='-.', linewidth=1.6,
                   alpha=0.9, zorder=4, label=floor_label)

    if band.any():
        # lower edge clipped at the cut: below it there is nothing left to
        # satisfy, so the band would only run away toward zero
        ax.fill_between(x_free[band], np.maximum(band_lo[band], cut),
                        band_hi[band],
                        color='tab:blue', alpha=0.15, linewidth=0, zorder=1,
                        label=band_label)

    # Context: the urban curves of comparable configs, thin and grey, behind
    # everything. Drawn before the focus curves so they never sit on top.
    if context is not None:
        # pass context through untouched — list() on a dict would keep only the
        # keys and silently downgrade every range back to an equality match
        names, desc = select_context(conv_df, config, context)
        drawn = 0
        for name in names:
            crow = conv_df[conv_df['ConfigName'] == name]
            if crow.empty:
                continue
            crow = crow.iloc[0]
            cW13 = float(crow['ChargeWeight']) ** (1 / 3)
            _, _, cff, cmaxr = _curve(maxr_df, name, tgt)
            ok = np.isfinite(cmaxr)
            if not ok.any():
                continue
            # each context config scales by its OWN W^(1/3) — on the R axis the
            # curves are in metres, so a shared factor would misplace them
            cx = (cmaxr[ok] / cW13) * (cW13 if x_axis == 'R' else 1.0)
            ax.plot(cx, cff[ok], '-', color='grey', linewidth=0.8, alpha=0.35,
                    zorder=0, solid_capstyle='round')
            drawn += 1
        if drawn:
            # one proxy entry rather than N identical grey lines in the legend
            ax.plot([], [], '-', color='grey', linewidth=0.8, alpha=0.6,
                    label=f'{drawn} other config{"s" if drawn != 1 else ""} '
                          f'({desc})')
        progress(f'  context: {drawn} curve(s) — {desc}')

    ax.plot(x_free, ff, 'o-', color='tab:blue', linewidth=2.0, markersize=5,
            zorder=3, label=f'Free Field  W={_num(conv_row["ChargeWeight"])} kg')
    ax.plot(x_urban, ff_urban, 's-', color='tab:red', linewidth=2.0,
            markersize=5, zorder=3, label=_urban_label(config, conv_row))

    ax.axvline(x_conv, color='k', linestyle='--', linewidth=1.5, alpha=0.8,
               zorder=4,
               label=f'{conv_sym}$_{{conv}}$ = {conv_fmt}  ({radius_label(method)})')

    # The near field below the validity floor is excluded from the analysis, so
    # the axis simply starts there rather than showing a shaded strip that ate
    # a quarter of the width. The restriction is stated in the caption.
    zf_min = Z_URBAN_ZF_MIN[tgt['fit_name']]
    x_min = zf_min * scale

    # Crop to the region where the criterion is actually doing work: out to
    # where the free-field curve crosses the cut level, and down to the cut
    # itself. Past there every cell converges regardless of the difference, so
    # the extra span is empty plot and a band that only widens.
    x_max = float(x_free[band].max()) if band.any() else float(x_free.max())
    # Keep Z_conv on the plot: for impulse the cut can fall short of it (27 of
    # 96 configs), which would leave the legend advertising a line that is not
    # visible anywhere.
    x_max = max(x_max, x_conv * 1.03)

    # 5% above the largest value still ON the plot. Taking the max over the
    # whole curve would reserve headroom for the cropped-out near field (a 5x
    # difference at Z=1 vs Z=2) and reintroduce the empty space.
    shown = np.concatenate([ff[(x_free >= x_min) & (x_free <= x_max)],
                            ff_urban[(x_urban >= x_min) & (x_urban <= x_max)]])
    y_top = float(shown.max()) * 1.05 if shown.size else float(ff.max()) * 1.05

    ax.set_xscale('log')
    ax.set_yscale('log')
    # ticks are chosen over the visible range only, and the limits come after
    # set_xticks — setting ticks re-expands them, so ordering matters
    visible = np.concatenate([x_free, x_urban, [x_conv]])
    _decimal_log_xaxis(ax, visible[(visible >= x_min) & (visible <= x_max)])
    ax.set_xlim(x_min, x_max)
    # a hair below the cut so the floor line sits just inside the axes rather
    # than being clipped in half by the spine. As on the x-axis, set_yticks
    # re-expands the limits, so the limit is applied after the ticks.
    y_bottom = cut * 0.97
    _decimal_log_yaxis(ax, y_bottom, y_top)
    ax.set_ylim(y_bottom, y_top)
    ax.grid(True, alpha=0.3, which='both')

    # Median amplification over the rows the Z_urban model is actually fitted
    # on — one number summarising how far the urban curve sits from free field.
    lam = median_lambda(sub, tgt, pi['W13'])
    if lam is not None:
        med, zf_lo, zf_hi, n_valid = lam
        ax.text(0.03, 0.04,
                f'Λ = {med:.2f}  (median, Z$_{{free}}$ {_num(zf_lo)}–{_num(zf_hi)}, '
                f'n={n_valid})',
                transform=ax.transAxes, ha='left', va='bottom', fontsize=10,
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor='grey', alpha=0.85), zorder=6)
    ax.set_xlabel(x_label, fontsize=12)
    ax.set_ylabel(f'{tgt["name"]}  {tgt["symbol"]}  [{tgt["unit"]}]', fontsize=12)
    # The config is named in the legend, so the title stays about the physics:
    # the quantity, the axis it runs along, and the Pi groups as a subtitle.
    ax.set_title(
        f'{tgt["name"]} along {x_axis}\n'
        f'ρ = {pi["rho"]:.3f},   s/W$^{{1/3}}$ = {pi["sW13"]:.2f},   '
        f'H/s = {pi["Hs"]:.2f}',
        fontsize=13, fontweight='bold')
    # the urban entry spells out the whole geometry, which is too wide to sit
    # inside the axes without covering the curves — park it under the plot
    ax.legend(fontsize=9, loc='upper center', bbox_to_anchor=(0.5, -0.13),
              frameon=True, borderaxespad=0.0)

    # the hatched strip is gone, so the excluded near field is stated instead
    start = f'{x_min:.1f} m' if x_axis == 'R' else _num(zf_min)
    caption = (f'Axis starts at {conv_sym} = {start}: Z$_{{free}}$ < '
               f'{_num(zf_min)} is outside the model validity domain and '
               'excluded from the analysis.')
    fig.text(0.5, -0.02, caption, ha='center', va='top', fontsize=8.5,
             color='dimgrey')
    # act on THIS figure, not plt's current one — with an embedded canvas the
    # two are different objects
    fig.tight_layout()

    if not save:
        # caller owns the figure (GUI preview); do not close it
        return fig

    out = out_dir / paths.suffixed(
        f'{config}_curve_{tgt["token"]}_{x_axis}.png', method)
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    progress(f'Saved: {out}')
    return out


def cli(argv=None):
    p = argparse.ArgumentParser(
        description='Peak pressure/impulse vs scaled distance for one config '
                    '(free field + reconstructed urban curve).')
    p.add_argument('config', nargs='?', default=None,
                   help='Config number (41) or full name '
                        '(config_41_det2_b15_s5_h12_w500). Omit to be asked.')
    p.add_argument('--target', choices=sorted(TARGETS), default='pressure',
                   help='Which quantity to plot (default: pressure).')
    p.add_argument('--x', choices=['Z', 'R'], default=None, dest='x_axis',
                   type=lambda s: s.strip().upper(),
                   help='X axis: Z = scaled distance, or R = real distance in '
                        'metres (R = Z * W^(1/3)). Omit to be asked; '
                        'defaults to Z when non-interactive.')
    p.add_argument('--context', nargs='*', default=None,
                   metavar='FILTER', type=_parse_context_arg,
                   help='Draw other configs as thin grey lines behind. Give no '
                        'filter for every other config, or any of: '
                        + ', '.join(sorted(CONTEXT_FILTERS)) + '. A bare name '
                        'means "same value as this config"; NAME=LO:HI means '
                        '"within that range" (either end may be blank). '
                        'Filters combine, e.g. '
                        '--context weight det hs=0.8:1.5')
    p.add_argument('--maxr-csv', default=None, help='max_radius_per_Z.csv path.')
    p.add_argument('--conv-csv', default=None, help='convergence_table.csv path.')
    p.add_argument('--out-dir', default=None, help='Output folder for the figure.')
    p.add_argument('--radius-method', choices=list(VALID_METHODS), default=None,
                   dest='radius_method',
                   help='Which radius-estimator tables to read (ignored for a '
                        'table given explicitly).')
    args = p.parse_args(argv)

    # isatty() alone is not reliable — some non-interactive launchers report a
    # tty but deliver EOF on the first read, so the ask helpers return None.
    interactive = sys.stdin is not None and sys.stdin.isatty()

    config, x_axis = args.config, args.x_axis

    if config is None:
        # The config list lives in the MaxR table, so it has to be read before
        # main() to be able to prompt against it.
        method = resolve_estimator(args.radius_method)['method']
        maxr_csv = paths.resolve(args.maxr_csv, paths.maxr_csv(method))
        if not Path(maxr_csv).exists():
            p.error(f'{maxr_csv} not found — run run_analysis.py first.')
        known = set(pd.read_csv(maxr_csv)['Config'])

        if interactive:
            print(f'Peak {args.target} curve — {len(known)} configs available.\n')
            config = _ask_config(known)
        if config is None:
            p.error('config is required when running non-interactively.')

    if x_axis is None:
        # Unlike the config, the axis has a sensible default, so a
        # non-interactive run falls back to Z instead of failing.
        x_axis = (_ask_x_axis() if interactive else None) or 'Z'

    return main(config, target=args.target, x_axis=x_axis,
                context=args.context, maxr_csv=args.maxr_csv,
                conv_csv=args.conv_csv, out_dir=args.out_dir,
                radius_method=args.radius_method)


if __name__ == '__main__':
    cli()
