"""Matched sets over the convergence table: the data layer for the explorer tab.

A *matched set* is a group of configs identical in every factor but one. Vary
W with (det, b, s, H) held fixed and the set's three configs isolate the effect
of W alone — which is the whole point, since the design is factorial and a
one-at-a-time comparison is therefore exact rather than a regression artefact.

No tkinter here and no plotting: this module turns the CSV into sets and
statistics, and the tab renders whatever it returns. That split keeps the
counting testable without a display.

Two grids, never merged
-----------------------
Configs 1-72 are a balanced factorial det(2) x b(2) x s(2) x H(3) x W(3), so
the matched sets come out exact and uniform:

    vary W -> 24 triplets    vary H -> 24 triplets
    vary s -> 36 pairs       vary b -> 36 pairs       vary det -> 36 pairs

Configs 73-96 (b = 10) are a *different* grid — s in {5,8,12}, H in {10,15,24},
W in {250,1000} — and are not part of that factorial. They are grouped
separately and their counts are reported separately, because pooling the two
would produce set counts that describe no experiment anyone ran. That block is
also not fully crossed (s = 5 exists only at H = 15 and H = 24, and H = 24 only
at s = 5), so its sets vary in size and varying b yields nothing at all: b = 10
is its only building size. Callers must not assume a uniform set size.

Everything is measured. Nothing here fits a model or reads a coefficient.
"""

import re

import numpy as np
import pandas as pd

# The five factors of the design. A matched set fixes all but one of these.
FACTORS = {
    'W':   dict(col='ChargeWeight', label='Charge weight W', unit='kg'),
    'H':   dict(col='Height',       label='Building height H', unit='m'),
    's':   dict(col='StreetWidth',  label='Street width s', unit='m'),
    'b':   dict(col='BuildingSize', label='Building size b', unit='m'),
    'det': dict(col='Det',          label='Detonation type', unit=''),
}

# Y-axis targets. 'fn' takes the frame and returns one value per config;
# everything is read from the convergence table, never from a fitted model.
TARGETS = {
    'R_conv,P': dict(label='R$_{conv,P}$  [m]', unit='m',
                     fn=lambda d: d['RadiusP']),
    'R_conv,I': dict(label='R$_{conv,I}$  [m]', unit='m',
                     fn=lambda d: d['RadiusI']),
    'Z_conv,P': dict(label='Z$_{conv,P}$  [m/kg$^{1/3}$]', unit='m/kg^(1/3)',
                     fn=lambda d: d['RadiusP'] / d['W13']),
    'Z_conv,I': dict(label='Z$_{conv,I}$  [m/kg$^{1/3}$]', unit='m/kg^(1/3)',
                     fn=lambda d: d['RadiusI'] / d['W13']),
    'R_I/R_P':  dict(label='R$_{conv,I}$ / R$_{conv,P}$', unit='-',
                     fn=lambda d: d['RadiusI'] / d['RadiusP']),
}

# Derived quantities: range filters, and available to colour by.
DERIVED = {
    'Pi2': dict(label='Π₂ = s/W^(1/3)', col='Pi2'),
    'rho': dict(label='ρ = b²/(b+s)²',  col='AreaDensity'),
    'H/s': dict(label='H/s',            col='Hs'),
}

# What a line may be coloured by: the five factors plus the continuous Pi2.
COLOR_BY = ['det', 'b', 's', 'H', 'W', 'Pi2']

# Which x-axis variables have a scaled form, and how to build it. Only H and s
# do; W is already the scaling quantity and det is categorical.
X_SCALED = {
    'H': dict(label='H / W$^{1/3}$  [m/kg$^{1/3}$]',
              fn=lambda d: d['Height'] / d['W13']),
    's': dict(label='s / W$^{1/3}$  [m/kg$^{1/3}$]',
              fn=lambda d: d['StreetWidth'] / d['W13']),
}

# The two grids, by config number. 'core' is the balanced factorial; 'b10' is
# the later b = 10 block, which has a different level set for s, H and W.
BLOCKS = {
    'core': dict(label='Core 72 (b = 15, 30)', test=lambda n: n <= 72),
    'b10':  dict(label='b = 10 block (73-96)', test=lambda n: n > 72),
}

# Below this relative spread a set counts as flat rather than rising or
# falling: the radii carry a few significant digits, so an exactly equal pair
# is not something the measurement can produce, and calling a 0.1% wobble a
# trend would put nearly every set in one bucket or the other.
FLAT_TOL = 0.01


def config_number(name):
    """Leading number of a config name ('config_41_...' -> 41), or None."""
    m = re.match(r'config_(\d+)_', str(name))
    return int(m.group(1)) if m else None


def load(csv_path):
    """Read the convergence table and add the derived columns.

    Only the req table is ever passed here — see the tab's spec. The estimator
    column is left as read so a caller can assert on it.
    """
    df = pd.read_csv(csv_path)

    df['ConfigNumber'] = df['ConfigName'].map(config_number)
    df['W13'] = df['ChargeWeight'].astype(float) ** (1 / 3)
    df['Pi2'] = df['StreetWidth'].astype(float) / df['W13']
    df['Hs'] = df['Height'].astype(float) / df['StreetWidth'].astype(float)
    # rho is read from AreaDensity rather than recomputed from b and s: the
    # column is exactly b^2/(b+s)^2 (verified), and reading it keeps this
    # consistent with whatever the analysis actually recorded.

    for key, spec in TARGETS.items():
        df[key] = spec['fn'](df)

    return df


def block_of(df):
    """Series naming each row's grid block ('core' or 'b10')."""
    return df['ConfigNumber'].map(
        lambda n: next((k for k, s in BLOCKS.items() if s['test'](n)), 'core'))


def build_sets(df, vary, blocks=('core', 'b10')):
    """Every matched set for *vary*, within each requested block.

    Returns a list of dicts, each with:
        key      the fixed factor values, as a (name, value) tuple
        block    which grid it came from
        rows     the member rows, sorted by the varying factor

    Sets are built per block and never pooled, so a 'set' always describes
    configs from one designed grid. Groups with fewer than two members are
    dropped: a single config shows no effect of varying anything.
    """
    if vary not in FACTORS:
        raise ValueError(f'unknown factor {vary!r}; expected one of '
                         f'{sorted(FACTORS)}')

    vary_col = FACTORS[vary]['col']
    fixed = [(k, FACTORS[k]['col']) for k in FACTORS if k != vary]

    df = df.copy()
    df['_block'] = block_of(df)

    out = []
    for block in blocks:
        part = df[df['_block'] == block]
        if part.empty:
            continue
        for values, group in part.groupby([c for _, c in fixed], sort=True):
            if len(group) < 2:
                continue
            out.append(dict(
                key=tuple(zip((k for k, _ in fixed), values)),
                block=block,
                rows=group.sort_values(vary_col),
            ))
    return out


def _passes(rows, filters):
    """True if every row satisfies every active filter.

    A matched set is shown only when all of its members pass — a partially
    filtered set would draw a line whose shape is an artefact of the filter
    rather than of the physics.
    """
    levels = filters.get('levels', {})
    for key, allowed in levels.items():
        if allowed is None:
            continue
        col = FACTORS[key]['col']
        if not rows[col].isin(list(allowed)).all():
            return False

    for key, (lo, hi) in filters.get('ranges', {}).items():
        col = DERIVED[key]['col']
        values = rows[col].astype(float)
        if lo is not None and not (values >= lo).all():
            return False
        if hi is not None and not (values <= hi).all():
            return False

    return True


def _trend(y):
    """Classify a set's shape as 'rise', 'fall', 'flat' or 'mixed'.

    Compared step by step rather than end to end, so a set that goes up then
    down is reported as non-monotone instead of being flattened into whichever
    endpoint happens to be larger.
    """
    y = np.asarray(y, dtype=float)
    if y.size < 2:
        return 'flat'

    signs = []
    for a, b in zip(y[:-1], y[1:]):
        base = abs(a)
        rel = (b - a) / base if base else (b - a)
        signs.append(0 if abs(rel) < FLAT_TOL else int(np.sign(rel)))

    if all(s > 0 for s in signs):
        return 'rise'
    if all(s < 0 for s in signs):
        return 'fall'
    if all(s == 0 for s in signs):
        return 'flat'
    return 'mixed'


def _pct_steps(y):
    """Per-step percentage changes of one set, skipping zero baselines."""
    y = np.asarray(y, dtype=float)
    return [(b - a) / a * 100.0 for a, b in zip(y[:-1], y[1:]) if a]


def select(df, vary, target, *, blocks=('core', 'b10'), filters=None,
           x_scaled=False):
    """Matched sets to plot, plus the counts describing them.

    Returns (lines, stats). Each line carries the x/y arrays, the member config
    names and the row subset the colour-by control reads from.

    Sets holding a missing or non-finite target value are dropped rather than
    drawn with a gap, and counted in stats['dropped_nan'] so the tab can say so.
    """
    filters = filters or {}
    sets = build_sets(df, vary, blocks=blocks)

    vary_col = FACTORS[vary]['col']
    scaled = x_scaled and vary in X_SCALED

    lines, dropped_filter, dropped_nan = [], 0, 0
    for entry in sets:
        rows = entry['rows']

        if not _passes(rows, filters):
            dropped_filter += 1
            continue

        y = rows[target].to_numpy(dtype=float)
        x = (X_SCALED[vary]['fn'](rows).to_numpy(dtype=float) if scaled
             else rows[vary_col].to_numpy(dtype=float))

        if not (np.isfinite(y).all() and np.isfinite(x).all()):
            dropped_nan += 1
            continue

        lines.append(dict(
            key=entry['key'],
            block=entry['block'],
            x=x,
            y=y,
            configs=list(rows['ConfigName']),
            rows=rows,
            trend=_trend(y),
        ))

    stats = _summarise(lines, sets, dropped_filter, dropped_nan)
    return lines, stats


def _summarise(lines, all_sets, dropped_filter, dropped_nan):
    """Counts for the text panel under the plot."""
    trends = [ln['trend'] for ln in lines]
    steps = [p for ln in lines for p in _pct_steps(ln['y'])]

    return dict(
        shown=len(lines),
        total=len(all_sets),
        dropped_filter=dropped_filter,
        dropped_nan=dropped_nan,
        rise=trends.count('rise'),
        fall=trends.count('fall'),
        flat=trends.count('flat'),
        mixed=trends.count('mixed'),
        median_pct_step=float(np.median(steps)) if steps else float('nan'),
        by_block={b: sum(1 for ln in lines if ln['block'] == b)
                  for b in BLOCKS},
    )


def median_line(lines):
    """Median y at each distinct x across *lines*, as (x, y) arrays.

    Sets in the b = 10 block are not uniformly sized, and a scaled x-axis puts
    every set on its own x values, so the median is taken over whatever sets
    share an x rather than assuming a common grid. x values carrying a single
    set still get a point — that is the median of one.
    """
    if not lines:
        return np.array([]), np.array([])

    buckets = {}
    for ln in lines:
        for xv, yv in zip(ln['x'], ln['y']):
            buckets.setdefault(round(float(xv), 9), []).append(float(yv))

    xs = sorted(buckets)
    return np.array(xs), np.array([float(np.median(buckets[x])) for x in xs])


def describe_line(line, vary):
    """One-line identification of a set, for the hover/click readout."""
    fixed = ',  '.join(f'{k} = {_fmt(v)}' for k, v in line['key'])
    numbers = ', '.join(str(config_number(c)) for c in line['configs'])
    return (f'{BLOCKS[line["block"]]["label"]}   |   {fixed}\n'
            f'configs {numbers}   |   vary {vary}: '
            + ',  '.join(f'{_fmt(xv)} -> {yv:.4g}'
                         for xv, yv in zip(line['x'], line['y'])))


def table(lines, vary, target, x_scaled=False):
    """The plotted data as a tidy frame, for CSV export.

    One row per plotted point, carrying the set it belongs to so the export
    reproduces the figure rather than just listing configs.
    """
    x_name = (f'{vary}_scaled' if x_scaled and vary in X_SCALED else vary)

    records = []
    for i, ln in enumerate(lines):
        fixed = dict(ln['key'])
        for xv, yv, name, (_, row) in zip(ln['x'], ln['y'], ln['configs'],
                                          ln['rows'].iterrows()):
            records.append({
                'set_id': i,
                'block': ln['block'],
                'trend': ln['trend'],
                **{f'fixed_{k}': v for k, v in fixed.items()},
                'ConfigName': name,
                x_name: xv,
                target: yv,
                'Pi2': row['Pi2'],
                'rho': row['AreaDensity'],
                'H_over_s': row['Hs'],
            })
    return pd.DataFrame.from_records(records)


def _fmt(value):
    """Format a factor level without a trailing '.0' (15.0 -> '15')."""
    try:
        return f'{float(value):g}'
    except (TypeError, ValueError):
        return str(value)
