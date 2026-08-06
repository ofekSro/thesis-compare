"""Peak pressure vs distance for ONE configuration, straight from the field.

Unlike tools/config_curve, nothing here is reconstructed from a table: the
curves are read off the simulation grids themselves. For every radial bin the
cells are collected and reduced to one number, giving

    urban       peak pressure in the city, from peakP*_orig (the filled,
                threshold-masked field the pipeline plots) or peakP*_raw
                (the solver's own output, pre-fill, pre-mask) with --field raw
    free field  the matching charge-only reference, refP*

Both are drawn against R in metres (or Z with --x Z). Because the field is
directional, the urban curve carries a shaded p10-p90 band across directions
in the same bin; --theta adds separate curves for named directions:

    --theta 0 90        the two street axes
    --theta 0 45 90     plus the diagonal through the fabric

theta = 0 and theta = 90 are the street axes; for an intersection detonation
(det2) they are equivalent by symmetry, so their two curves land on top of
each other and only the last one drawn is visible — that coincidence is the
symmetry, not a missing curve.

Three stacked panels share the x axis: the load curves, the urban/free-field
ratio, and the derivative of that ratio (--deriv load switches the bottom one
to the load's local decay exponent). The steepest fall is marked.

Each derivative is filtered in the variable it is differentiated by, and
those are not the same variable:

    --deriv ratio   d(ratio)/dR, filtered by a running mean over --smooth
                    bins (uniform in R, like the derivative)
    --deriv load    d ln P / d ln R, from a local linear fit of ln P on ln R
                    with half-bandwidth --log-bw (uniform in ln R, like the
                    derivative)

Either way the result is a filtered estimate, so read the marked radius as a
neighbourhood and not a sharp edge — of order the window width, ~6 m for the
default --smooth 3, ~+-15% of R for the default --log-bw 0.15.

Vertical markers: the near-blast exclusion radius (inside it the pipeline
declines to measure) and, when the convergence table is present, the measured
convergence radius R_conv,P.

Usage:
    python tools\\pressure_profile\\pressure_profile.py                 # prompts
    python tools\\pressure_profile\\pressure_profile.py 2               # by number
    python tools\\pressure_profile\\pressure_profile.py config_02_det1_b15_s5_h4_w500
    python tools\\pressure_profile\\pressure_profile.py 2 --theta 0 45 90
    python tools\\pressure_profile\\pressure_profile.py 2 --target impulse
    python tools\\pressure_profile\\pressure_profile.py 2 --x Z --dr 1
    python tools\\pressure_profile\\pressure_profile.py 2 --csv

main() returns the Figure when save=False, so a GUI can redraw without
touching the filesystem.
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

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.geometry import exclude_radius
from blastlib.io.npz_store import load_processed_data
from blastlib.processing.radius_estimator import resolve_estimator, VALID_METHODS


# Per-target field names. Pressure and impulse differ only by this table.
TARGETS = {
    'pressure': dict(urban='peakP{g}_{f}', ref='refP{g}', conv_col='RadiusP',
                     name='Peak Pressure', symbol='P', unit='kPa'),
    'impulse':  dict(urban='impulse{g}_{f}', ref='refI{g}', conv_col='RadiusI',
                     name='Peak Impulse', symbol='I', unit='kPa·ms'),
}

# Only peakP has a pre-fill '_raw' twin in the store; impulse keeps '_orig'.
_RAW_AVAILABLE = {'pressure': ('orig', 'raw'), 'impulse': ('orig',)}

# What the bottom panel differentiates. 'ratio' is the derivative of the panel
# above it — the rate at which the urban excess itself is changing, which is
# what a search for "where does the city stop helping" wants. 'load' is the
# local decay exponent of the load, negative everywhere because the wave always
# decays; it measures how steeply, not whether the geometry is still acting.
# Labels stay short — the panel is a fifth of the figure height, and a long
# ylabel overruns it into the panel above.
DERIVATIVES = {
    'ratio': dict(col='d_ratio', zero=0.0, label='d(ratio) / dR  [m$^{-1}$]'),
    'load':  dict(col='d_lnP', zero=None, label='d ln {sym} / d ln R'),
}

# Grid 1 is the finest, grid 3 the coarsest, and they overlap. Each radial bin
# takes its cells from the finest grid that still has enough of them there, so
# the curve never mixes resolutions within one bin.
_MIN_CELLS_PER_BIN = 8
_MIN_CELLS_PER_WEDGE = 8

# Default outer radius, as a multiple of the measured convergence radius. The
# grids run out to ~700 m in the corner, where both fields are under 1 kPa and
# only the coarsest resolution survives — plotting that far buries the part of
# the curve the configuration is about.
_RMAX_FACTOR = 1.5

# Hard outer limit, on the plot and on the marker search alike. 100 m is also
# exactly the extent of grid 1, the finest of the three (0.15 m cells), so
# staying inside it keeps the whole profile on one resolution with no grid
# handoff. Beyond it the search had nothing left to lock onto and returned the
# last slice in the configurations whose ratio never settles to RATIO_FLAT.
_RMAX_CAP = 100.0


def resolve_config(token, known):
    """Map a user token to a config name: full name, prefix, or number."""
    token = str(token).strip()
    if not token:
        return None
    if token in known:
        return token
    if token.isdigit():
        n = int(token)
        hits = [c for c in known if _config_number(c) == n]
        return hits[0] if len(hits) == 1 else None
    hits = [c for c in known if c.startswith(token)]
    return hits[0] if len(hits) == 1 else None


def _config_number(name):
    m = re.match(r'config_(\d+)_', name)
    return int(m.group(1)) if m else None


def _grid_layers(processed, target, field):
    """[(r, theta_deg, value)] per grid, finest first, valid cells only."""
    spec = TARGETS[target]
    layers = []
    for g in (1, 2, 3):
        key = spec['urban'].format(g=g, f=field)
        if key not in processed:
            raise KeyError(
                f'{key} is not in this NPZ store. Use --field orig, or point '
                f'--npz-dir at data/processed_npz_v2 (or the raw store).')
        X = np.asarray(processed[f'X{g}']).ravel()
        Y = np.asarray(processed[f'Z{g}']).ravel()
        u = np.asarray(processed[key]).ravel()
        ref = np.asarray(processed[spec['ref'].format(g=g)]).ravel()
        r = np.hypot(X, Y)
        th = np.degrees(np.arctan2(Y, X))
        ok = (np.isfinite(u) & (u > 0) & np.isfinite(ref) & (ref > 0)
              & (r > 0) & (th >= 0) & (th <= 90))
        layers.append((r[ok], th[ok], u[ok], ref[ok]))
    return layers


def radial_profile(processed, target='pressure', field='orig', dr=2.0,
                   rmax=None, theta=None, half_angle=5.0, stat='median',
                   smooth=3, log_bw=0.15, rmin=0.0):
    """Reduce the field to one row per radial bin.

    Returns a DataFrame with, per bin: the urban statistic over all
    directions, its p10/p90 spread, the free-field reference, the cell count,
    one column per requested *theta* wedge, and the two derivatives added by
    _add_derivatives.
    """
    layers = _grid_layers(processed, target, field)
    if rmax is None:
        rmax = max(l[0].max() for l in layers if len(l[0]))
    edges = np.arange(0.0, rmax + dr, dr)
    reduce_ = {'median': np.median, 'max': np.max, 'mean': np.mean}[stat]

    rows = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        # finest grid with enough cells in this bin wins
        chosen = None
        for r, th, u, ref in layers:
            m = (r >= lo) & (r < hi)
            if m.sum() >= _MIN_CELLS_PER_BIN:
                chosen = (th[m], u[m], ref[m])
                break
        if chosen is None:
            continue
        th_b, u_b, ref_b = chosen
        row = {'r': 0.5 * (lo + hi), 'n': len(u_b),
               'urban': reduce_(u_b),
               'urban_p10': np.percentile(u_b, 10),
               'urban_p90': np.percentile(u_b, 90),
               'free_field': np.median(ref_b)}
        for t in (theta or []):
            w = np.abs(th_b - t) <= half_angle
            # A wedge thinned to a handful of cells produces spikes that read
            # as physics; leave the gap visible instead.
            row[f'theta_{t:g}'] = (reduce_(u_b[w])
                                   if w.sum() >= _MIN_CELLS_PER_WEDGE else np.nan)
        rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out['ratio'] = out.urban / out.free_field
    _add_derivatives(out, smooth, log_bw, rmin)
    return out


# --- the search bound: where looking for R_local stops -----------------------
#
# R_local is the steepest relative fall of the urban load; this is only the
# outer end of the window it is looked for in. Two clauses, whichever fires
# first, read outward from detector_rmin:
#
#   ratio <= RATIO_FLAT   the street has stopped amplifying relative to the
#                         free field;
#   urban - free < band   the excess has stopped mattering in absolute terms,
#                         the same 10 kPa the pipeline's convergence band uses.
#
# The second clause is there because the first does not always fire. Along a
# strongly channelled street the ratio levels off above 1.05 and stays: over
# all 96 configurations it never reaches 1.05 inside 100 m in 42 of them, and
# 15 then ran all the way to the hard cap with nothing to lock onto — all of
# them det2, 14 of those s=20. That is the documented behaviour of Lambda,
# which settles near 1.1 rather than returning to 1, because convergence is
# defined on the absolute difference. The band clause tests that difference
# directly, so it fires where the relative one cannot.
RATIO_FLAT = 1.05

# Consecutive slices the condition must hold for. K = 3 matches the sector
# scan's three-in-a-row rule; a single slice is too easy to fire on noise.
RLOCAL_PERSIST = 3


def search_bound(prof, target='pressure', W13=1.0, persist=RLOCAL_PERSIST):
    """Outer end of the R_local search window: first r where the ratio holds
    at or below RATIO_FLAT for *persist* consecutive slices.

    Returns (radius, 'ratio'), or (nan, None) when the ratio never settles
    that low — the caller then falls back to the hard _RMAX_CAP. Only slices
    with a finite derivative count, i.e. at or beyond detector_rmin.

    *target* and *W13* are accepted and ignored; they were needed by the
    absolute-difference clause that used to sit here and are kept so callers
    do not have to change.
    """
    v = prof[np.isfinite(prof.d_ratio)].reset_index(drop=True)
    if len(v) < persist:
        return np.nan, None
    hit = v.ratio.values <= RATIO_FLAT
    for i in range(len(hit) - persist + 1):
        if hit[i:i + persist].all():
            return float(v.r.values[i]), 'ratio'
    return np.nan, None


def detector_rmin(cfg):
    """Inner radius for the derivative panels — THIS TOOL ONLY.

    Deliberately larger than blastlib.geometry.exclude_radius, and not a
    replacement for it: that one is a property of the pipeline's radius
    measurement and changing it would move R_conv and every fitted
    coefficient downstream. This one exists because the derivatives need a
    start point past the first building, where the ratio is still climbing
    steeply out of the charge-emplacement shadow. Measured at 0.5 m bins the
    steepest fall otherwise pins to the first surviving bin in 4 of 10
    configurations.

        det=1 (street):       b + s     one block period out
        det=2 (intersection): s/2 + b   the far face of the first building

    Compare the pipeline's values, which are much smaller — for b=30, s=5
    they are 15.2 m (det1) and 2.5 m (det2) against 35 m and 32.5 m here.
    """
    if cfg['det'] == 1:
        return cfg['bsize'] + cfg['swidth']
    return cfg['swidth'] / 2 + cfg['bsize']


def _loglog_slope(r, y, bw, min_pts=4):
    """d ln y / d ln r by local linear regression, bandwidth *bw* in ln r.

    Not np.gradient on a smoothed copy: this derivative is taken with respect
    to ln r, so its filter has to be defined in ln r too. A running mean over
    a fixed number of uniform-in-R bins is not — a 6 m window spans 1.10 of
    ln R at R = 5 m and 0.06 at R = 100 m, an 18x swing in effective
    bandwidth across one plot, heaviest exactly where the curve bends most.

    Fitting a straight line to ln y against ln r over a fixed +-bw of ln r
    fixes both halves at once: the slope of that line *is* the derivative
    (no differencing step), and the window is constant in the variable being
    differentiated. Tricube weights taper the window's edge so a point
    entering or leaving it does not step the result.

    The window is widened where it would hold fewer than *min_pts* bins —
    near the origin, where uniform-R bins are sparse in ln r. Those radii are
    therefore smoothed more than *bw* asks; the widening is reported by the
    companion _loglog_bandwidth so the figure can say so.
    """
    lr, ly = np.log(r), np.log(y)
    out = np.full(len(r), np.nan)
    for i in range(len(r)):
        d = np.abs(lr - lr[i])
        h = max(bw, np.partition(d, min_pts - 1)[min_pts - 1])
        m = d <= h
        if m.sum() < 3:
            continue
        w = (1.0 - (d[m] / h) ** 3) ** 3
        X = np.column_stack([np.ones(m.sum()), lr[m]])
        sw = np.sqrt(w)
        beta, *_ = np.linalg.lstsq(X * sw[:, None], ly[m] * sw, rcond=None)
        out[i] = beta[1]
    return out


def _loglog_bandwidth(r, bw, min_pts=4):
    """Effective half-bandwidth actually used at each radius by _loglog_slope."""
    lr = np.log(r)
    return np.array([max(bw, np.partition(np.abs(lr - lr[i]), min_pts - 1)[min_pts - 1])
                     for i in range(len(r))])


def _add_derivatives(prof, smooth, log_bw, rmin=0.0):
    """Numerical derivatives of the binned profile, in place.

    Two are written, because they answer different questions — and each is
    filtered in its own variable, which is not the same one:

      d_ratio  = d(urban/free field) / dR      [1/m]
                 How fast the urban excess itself is changing: zero where the
                 excess holds, negative where the city is losing it. Both the
                 quantity and its argument are in metres, so a running mean
                 over *smooth* uniform-in-R bins is matched to it — smoothed
                 in R, differentiated in R.

      d_lnP    = d ln(urban) / d ln R
                 The local decay exponent of the load: if P ~ R^n locally
                 this returns n. Dimensionless, so it compares across charge
                 weights, and it strips the pressure level out — plain dP/dR
                 is largest wherever P is largest, which is always the near
                 field regardless of what the geometry does. Differentiated
                 with respect to ln R, so it is fitted in ln R by
                 _loglog_slope with half-bandwidth *log_bw*, NOT smoothed in
                 bins.
    """
    # Bins inside rmin (the near-blast exclusion radius) are dropped BEFORE
    # differentiating, not merely skipped when the result is read. There the
    # field is dominated by the charge-emplacement geometry and is not a
    # measurement of the urban flow at all; leaving those bins in would let
    # them feed the running mean and the local fit of the first few bins
    # outside, contaminating exactly the radii the detector cares about.
    keep = prof.r.values >= rmin
    r = prof.r.values[keep]
    for col in ('d_ratio', 'd_lnP', 'log_bw_eff'):
        prof[col] = np.nan
    if len(r) < 4:
        return

    k = max(1, int(smooth))
    win = np.ones(k) / k
    pad = k // 2

    def sm(a):
        if k <= 1:
            return a
        s = np.convolve(a, win, mode='same')
        if pad:                       # 'same' tapers the ends against zero
            s[:pad] = a[:pad]
            s[-pad:] = a[-pad:]
        return s

    prof.loc[keep, 'd_ratio'] = np.gradient(sm(prof.ratio.values[keep]), r)
    prof.loc[keep, 'd_lnP'] = _loglog_slope(r, prof.urban.values[keep], log_bw)
    prof.loc[keep, 'log_bw_eff'] = _loglog_bandwidth(r, log_bw)


def street_profile(processed, cfg, target='pressure', field='orig', dr=0.5,
                   rmax=None, stat='mean', smooth=3, log_bw=0.15, rmin=0.0):
    """Profile down the FIRST STREET: a fixed-width strip, not a ring.

    Takes the cells with 0 <= Z <= s/2 — the half-width of the street the
    charge sits in — and bins them by X, the distance along the street axis.

    This exists because the ring profile changes what it is sampling as it
    grows. A ring at 37 m may cross mostly buildings, leaving only the few
    street cells valid, and the median then jumps because the sample
    composition changed, not because the field did. Measured on config_01 and
    config_03 — same geometry, charge weights 30x apart — the per-ring cell
    count is *identical* in all 85 bins and dips to a local minimum of 404
    exactly where both markers land. The strip has no such freedom: every bin
    holds the same 51 cells (s = 5 m at 0.5 m bins), all of them in the open
    street, so a change in the profile is a change in the flow.

    The cross-street strip is the mirror of this one only for det=2; for
    det=1 it runs into the building row and is 70% empty, which is why only
    the along-street strip is offered.
    """
    spec = TARGETS[target]
    s_half = cfg['swidth'] / 2.0
    reduce_ = {'median': np.median, 'max': np.max, 'mean': np.mean}[stat]

    layers = []
    for g, lo_hi in [(1, (0, 100)), (2, (100, 250)), (3, (250, 500))]:
        key = spec['urban'].format(g=g, f=field)
        X = np.asarray(processed[f'X{g}']).ravel()
        Y = np.asarray(processed[f'Z{g}']).ravel()
        u = np.asarray(processed[key]).ravel()
        ref = np.asarray(processed[spec['ref'].format(g=g)]).ravel()
        ok = (np.isfinite(u) & (u > 0) & np.isfinite(ref) & (ref > 0)
              & (Y >= 0) & (Y <= s_half) & (X > 0))
        layers.append((X[ok], u[ok], ref[ok]))

    if rmax is None:
        rmax = max((x.max() for x, _, _ in layers if len(x)), default=0.0)
    edges = np.arange(0.0, rmax + dr, dr)
    rows = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        for x, u, ref in layers:          # finest grid with enough cells wins
            m = (x >= lo) & (x < hi)
            if m.sum() >= _MIN_CELLS_PER_BIN:
                rows.append({'r': 0.5 * (lo + hi), 'n': int(m.sum()),
                             'urban': reduce_(u[m]),
                             'urban_p10': np.percentile(u[m], 10),
                             'urban_p90': np.percentile(u[m], 90),
                             'free_field': reduce_(ref[m])})
                break
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out['ratio'] = out.urban / out.free_field
    _add_derivatives(out, smooth, log_bw, rmin)
    return out


def _read_conv_radius(config, target, conv_csv):
    """Measured convergence radius for this config, or None."""
    try:
        df = pd.read_csv(conv_csv)
    except (OSError, pd.errors.EmptyDataError):
        return None
    hit = df[df.ConfigName == config]
    if hit.empty:
        return None
    return float(hit.iloc[0][TARGETS[target]['conv_col']])


def _draw(prof, config, cfg, target, x_axis, conv_R, theta, field, stat,
          deriv='ratio', smooth=3, log_bw=0.15, mode='ring', show_conv=False):
    spec = TARGETS[target]
    W13 = float(cfg['weight']) ** (1 / 3)
    scale = 1.0 if x_axis == 'R' else 1.0 / W13
    x = prof.r * scale
    xlabel = ('Distance R [m]' if x_axis == 'R'
              else 'Scaled distance Z = R/W$^{1/3}$ [m/kg$^{1/3}$]')

    panels = ['ratio', 'load'] if deriv == 'both' else [deriv]
    fig, axall = plt.subplots(
        2 + len(panels), 1, figsize=(9, 8.0 + 1.5 * len(panels)), sharex=True,
        gridspec_kw={'height_ratios': [3, 1] + [1] * len(panels), 'hspace': 0.08})
    ax, axr, axds = axall[0], axall[1], axall[2:]

    over = 'across the strip' if mode == 'street' else 'across directions'
    ax.fill_between(x, prof.urban_p10, prof.urban_p90, alpha=0.18,
                    color='tab:red', lw=0, label=f'urban, p10–p90 {over}')
    ax.plot(x, prof.urban, color='tab:red', lw=2,
            label=f'urban ({stat} {over})')
    ax.plot(x, prof.free_field, color='tab:blue', lw=2, ls='--',
            label='free field (reference simulation)')
    for t, c in zip(theta or [], ['tab:green', 'tab:purple', 'tab:orange',
                                  'tab:brown', 'tab:olive']):
        col = f'theta_{t:g}'
        if col in prof:
            ax.plot(x, prof[col], color=c, lw=1.4, alpha=0.9,
                    label=f'urban, θ = {t:g}°')

    ax.set_yscale('log')
    ax.set_ylabel(f"{spec['name']} [{spec['unit']}]")
    where = (f"first-street strip, 0 ≤ Z ≤ {cfg['swidth'] / 2:g} m"
             if mode == 'street' else 'angular rings, 0–90°')
    ax.set_title(f'{config}\n'
                 f"b={cfg['bsize']:g} m · s={cfg['swidth']:g} m · "
                 f"H={cfg['height']:g} m · W={cfg['weight']:g} kg · "
                 f"det{cfg['det']}\n{where}   (field: {field})", fontsize=11)
    ax.grid(True, which='both', alpha=0.25)

    axr.axhline(1.0, color='0.4', lw=1)
    axr.axhline(RATIO_FLAT, color='tab:green', lw=1, ls=':')
    axr.plot(x, prof.ratio, color='tab:red', lw=1.6)
    axr.set_ylabel('urban / free field')
    axr.grid(True, alpha=0.25)

    # The 1.05 crossing is the OUTER BOUND OF THE SEARCH, not the answer:
    # R_local is the steepest relative fall inside the window, marked on the
    # d lnP/d lnR panel below. Labelling this line R_local was left over from
    # an earlier version where the crossing itself was the result.
    Rflat, _ = search_bound(prof)
    note = f'bound: ratio ≤ {RATIO_FLAT:g} for {RLOCAL_PERSIST} slices'
    if np.isfinite(Rflat):
        axr.plot(Rflat * scale, RATIO_FLAT, 'o', color='tab:green', ms=7,
                 zorder=5)
        axr.annotate(f'search bound = {Rflat:.0f} m',
                     (Rflat * scale, RATIO_FLAT), xytext=(7, 6),
                     textcoords='offset points', fontsize=8,
                     color='tab:green', va='bottom')
    else:
        note += f' — never reached, bound falls back to {_RMAX_CAP:g} m'
    axr.text(0.995, 0.06, note, transform=axr.transAxes, ha='right',
             fontsize=7, color='0.4')

    # --- derivative panels ---
    Rex = exclude_radius(cfg)
    Rmin = detector_rmin(cfg)
    for axd, name in zip(axds, panels):
        d = DERIVATIVES[name]
        dv = prof[d['col']].values
        if d['zero'] is not None:
            axd.axhline(d['zero'], color='0.4', lw=1)
        axd.plot(x, dv, color='tab:red', lw=1.4)
        if d['zero'] is not None:
            axd.fill_between(x, d['zero'], dv, where=dv < d['zero'],
                             color='tab:red', alpha=0.15, lw=0)
        # Mark the steepest fall rather than leaving it to be eyeballed.
        #
        # The search window is bounded at BOTH ends. Inside, by detector_rmin:
        # the derivatives are NaN there, computed without those slices. Outside,
        # by R_local — once the ratio has come down to RATIO_FLAT the street has
        # stopped amplifying and there is nothing left to find, so anything
        # beyond it is far-field scatter. Without the outer bound the marker
        # ran to the last slice in the wide-street configurations (config_11 at
        # 112 m, config_47 at 100 m) purely because the tail is noisy there.
        hi = min(Rflat, _RMAX_CAP) if np.isfinite(Rflat) else _RMAX_CAP
        ok = np.isfinite(dv) & (prof.r.values <= hi)
        if ok.any():
            i = int(np.flatnonzero(ok)[np.nanargmin(dv[ok])])
            # Only the log-log slope defines R_local; d(ratio)/dR is shown for
            # comparison but is biased toward wherever the ratio is largest.
            is_answer = name == 'load'
            axd.plot(x.iloc[i], dv[i], 'v',
                     color='tab:green' if is_answer else 'k',
                     ms=8 if is_answer else 6, zorder=5)
            label = (f'$R_{{local}}$ = {prof.r.iloc[i]:.0f} m' if is_answer
                     else f'steepest fall\nR = {prof.r.iloc[i]:.0f} m')
            axd.annotate(label, (x.iloc[i], dv[i]), xytext=(6, 4),
                         textcoords='offset points', fontsize=8, va='bottom',
                         color='tab:green' if is_answer else 'k',
                         fontweight='bold' if is_answer else 'normal')
            if is_answer:
                for a in axall:
                    a.axvline(x.iloc[i] / (scale or 1) * scale, color='tab:green',
                              ls='-', lw=1.8, alpha=0.55, zorder=0)
        # str.replace, not str.format — the labels carry mathtext braces.
        axd.set_ylabel(d['label'].replace('{sym}', spec['symbol']), fontsize=9)
        axd.grid(True, alpha=0.25)
        # Name the filter that was actually applied — the two derivatives use
        # different ones, in different variables.
        if name == 'ratio':
            note = (f'running mean over {smooth} bins '
                    f'({smooth * (prof.r.iloc[1] - prof.r.iloc[0]):.0f} m), in R'
                    if smooth > 1 else 'unfiltered')
        else:
            eff = prof.log_bw_eff.values
            widened = np.isfinite(eff) & (eff > log_bw * 1.001)
            note = f'local fit in ln R, half-bandwidth {log_bw:g}'
            if widened.any():
                note += f' (widened below R = {prof.r.values[widened].max():.0f} m)'
        why = '' if np.isfinite(Rflat) and Rflat <= _RMAX_CAP else \
              f' (capped — ratio never ≤ {RATIO_FLAT:g} inside it)'
        note += f' · search window {Rmin:.0f}–{hi:.0f} m{why}'
        # Top of the panel: the steepest-fall label sits at the bottom, on the dip.
        axd.text(0.995, 0.93, note, transform=axd.transAxes, ha='right',
                 va='top', fontsize=7, color='0.4')
    axds[-1].set_xlabel(xlabel)

    for a in axall:
        a.axvline(Rex * scale, color='0.35', ls=':', lw=1.4)
        a.axvline(Rmin * scale, color='tab:orange', ls=':', lw=1.6)
        if np.isfinite(Rflat):
            a.axvline(Rflat * scale, color='tab:green', ls='--', lw=1.4)
        if conv_R and show_conv:
            a.axvline(conv_R * scale, color='k', ls='-.', lw=1.4)
    # Anchored to the bottom of the axes so the labels never fight the legend.
    ax.annotate('exclusion radius', (Rex * scale, 0), xycoords=('data', 'axes fraction'),
                xytext=(3, 6), textcoords='offset points', fontsize=8,
                rotation=90, va='bottom', color='0.35')
    ax.annotate(f'detector start = {Rmin:.0f} m', (Rmin * scale, 0),
                xycoords=('data', 'axes fraction'), xytext=(3, 6),
                textcoords='offset points', fontsize=8, rotation=90,
                va='bottom', color='tab:orange')
    if conv_R and show_conv:
        ax.annotate(f'$R_{{conv}}$ = {conv_R:.0f} m',
                    (conv_R * scale, 0), xycoords=('data', 'axes fraction'),
                    xytext=(3, 6), textcoords='offset points', fontsize=8,
                    rotation=90, va='bottom')

    ax.legend(fontsize=8, loc='upper right')
    return fig


def main(config, *, target='pressure', x_axis='R', field='orig', dr=2.0,
         rmax=None, theta=None, stat=None, deriv='ratio', smooth=3,
         log_bw=0.15, mode='ring', show_conv=False, npz_dir=None,
         conv_csv=None, out_dir=None, radius_method=None, save=True,
         write_csv=False, progress=None):
    """Draw the profile. Returns the Figure (save=False) or its path."""
    say = progress or _say
    if target not in TARGETS:
        raise ValueError(f'target must be one of {sorted(TARGETS)}')
    if deriv not in DERIVATIVES and deriv != 'both':
        raise ValueError(f"deriv must be 'both' or one of {sorted(DERIVATIVES)}")
    if field not in _RAW_AVAILABLE[target]:
        raise ValueError(f'--field {field} is not available for {target} '
                         f'(have: {", ".join(_RAW_AVAILABLE[target])})')

    npz_dir = paths.resolve(npz_dir, paths.default_npz_dir(soft=True))
    method = resolve_estimator(radius_method)['method']
    conv_csv = paths.resolve(conv_csv, paths.conv_csv(method))

    say(f'Loading {config} from {npz_dir} ...')
    processed, ok = load_processed_data(npz_dir, config)
    if not ok:
        raise FileNotFoundError(f'{config}.npz not found or incomplete in {npz_dir}')

    cfg = config_parser(config)
    # Only read when it is going to be drawn — R_local no longer depends on
    # it in any way, so a missing convergence table is not a problem here.
    conv_R = _read_conv_radius(config, target, conv_csv) if show_conv else None
    if show_conv and conv_R is None:
        say(f'  note: {config} not in {conv_csv} — no R_conv line drawn')
    # 100 m flat, not a multiple of R_conv. Scaling the window to R_conv
    # truncated the small-R_conv configurations well inside the marker search
    # bound — config_61 has R_conv = 26.7 m, so 1.5x it ended the profile at
    # 40 m while the search was nominally allowed out to 100.
    rmax = min(rmax, _RMAX_CAP) if rmax else _RMAX_CAP

    # A ring mixes shadowed and open cells, so its centre is the robust
    # median; a street strip is uniform by construction, so plain averaging
    # is right there and keeps every cell's weight equal.
    if stat is None:
        stat = 'median' if mode == 'ring' else 'mean'
    if mode == 'street':
        if theta:
            say('  note: --theta is a ring-profile option, ignored in street mode')
            theta = None
        prof = street_profile(processed, cfg, target=target, field=field, dr=dr,
                              rmax=rmax, stat=stat, smooth=smooth,
                              log_bw=log_bw, rmin=detector_rmin(cfg))
    else:
        prof = radial_profile(processed, target=target, field=field, dr=dr,
                              rmax=rmax, theta=theta, stat=stat, smooth=smooth,
                              log_bw=log_bw, rmin=detector_rmin(cfg))
    if prof.empty:
        raise RuntimeError(f'no radial bin of {dr} m held enough cells — '
                           'try a larger --dr')
    unit = ('cross-street slices along the street axis' if mode == 'street'
            else 'angular rings')
    say(f'  {len(prof)} {unit}, {prof.r.min():.1f}-{prof.r.max():.1f} m')

    fig = _draw(prof, config, cfg, target, x_axis, conv_R, theta, field, stat,
                deriv=deriv, smooth=smooth, log_bw=log_bw, mode=mode,
                show_conv=show_conv)
    if not save:
        return fig

    out_dir = Path(paths.resolve(out_dir, paths.fig_dir('pressure_profile')))
    paths.ensure_dir(out_dir)
    # The field is part of the identity of the curve, so a --field raw run
    # must not overwrite the default one.
    tag = target if field == "orig" else f"{target}_{field}"
    if mode == "street":
        tag = f"{tag}_street"
    png = out_dir / f'{config}_{tag}_profile.png'
    fig.savefig(png, dpi=150, bbox_inches='tight')
    plt.close(fig)
    say(f'  wrote {png}')
    if write_csv:
        csv = out_dir / f'{config}_{tag}_profile.csv'
        prof.to_csv(csv, index=False)
        say(f'  wrote {csv}')
    return png


def _say(msg):
    """print() that survives a console codec narrower than the project path.

    This tree lives under a Hebrew directory name; on a cp1252 console the
    plain print of any resolved path raises UnicodeEncodeError.
    """
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'ascii'
        print(msg.encode(enc, 'replace').decode(enc))


def _known_configs(npz_dir):
    return sorted(p.stem for p in Path(npz_dir).glob('config_*.npz'))


def _ask_config(known):
    print(f'{len(known)} configs available, e.g. {known[0]}')
    try:
        token = input('Config (number or name): ')
    except EOFError:
        return None
    return resolve_config(token, known)


def cli(argv=None):
    p = argparse.ArgumentParser(
        description='Peak pressure (or impulse) vs distance for one config, '
                    'measured directly from the simulation grids.')
    p.add_argument('config', nargs='?', default=None,
                   help='Config number (2) or full name. Omit to be asked.')
    p.add_argument('--target', choices=sorted(TARGETS), default='pressure')
    p.add_argument('--x', choices=['R', 'Z'], default='R', dest='x_axis',
                   type=lambda s: s.strip().upper(),
                   help='X axis: R = metres (default), Z = R/W^(1/3).')
    p.add_argument('--field', choices=['orig', 'raw'], default='orig',
                   help="'orig' = filled, threshold-masked field the pipeline "
                        "plots (default); 'raw' = the solver's own output, "
                        'pre-fill and pre-mask (pressure only).')
    p.add_argument('--dr', type=float, default=2.0,
                   help='Radial bin width in metres (default: 2).')
    p.add_argument('--rmax', type=float, default=None,
                   help=f'Outer radius in metres (default: {_RMAX_FACTOR:g} x '
                        'the measured convergence radius, or the grid extent '
                        'when the convergence table is missing).')
    p.add_argument('--theta', type=float, nargs='*', default=None,
                   metavar='DEG',
                   help='Add a curve per direction, e.g. --theta 0 45 90. '
                        'theta 0 and 90 are the street axes.')
    p.add_argument('--show-conv', action='store_true', dest='show_conv',
                   help='Draw the measured convergence radius as a reference '
                        'line. Off by default: R_local is defined without it, '
                        'and showing it invites reading one off the other.')
    p.add_argument('--mode', choices=['ring', 'street'], default='ring',
                   help="'ring' = angular rings over 0-90 deg (default); "
                        "'street' = a fixed-width strip down the first "
                        'street (0 <= Z <= s/2), binned by distance along it. '
                        'The strip holds the same cells at every distance, so '
                        'a change in the profile cannot come from a change in '
                        'what is being sampled.')
    p.add_argument('--stat', choices=['median', 'max', 'mean'], default=None,
                   help='How to reduce the cells in one bin. Default depends '
                        'on --mode: median for ring (mixes shadowed and open '
                        'cells), mean for street (uniform by construction).')
    p.add_argument('--deriv', choices=sorted(DERIVATIVES) + ['both'],
                   default='ratio',
                   help="Bottom panel(s): 'ratio' = d(urban/free field)/dR "
                        "(default), 'load' = d ln P / d ln R, the local decay "
                        "exponent, 'both' = one panel each. Both are computed "
                        'from bins outside the exclusion radius only.')
    p.add_argument('--smooth', type=int, default=3, metavar='BINS',
                   help='--deriv ratio only: running-mean width in bins, '
                        'applied before differentiating (default: 3; 1 '
                        'disables it). Matched to that derivative, which is '
                        'taken with respect to R.')
    p.add_argument('--log-bw', type=float, default=0.15, metavar='LN_R',
                   dest='log_bw',
                   help='--deriv load only: half-bandwidth of the local '
                        'log-log fit, in units of ln R (default: 0.15, i.e. '
                        'about +-15%% in radius). Widened automatically near '
                        'the origin where the bins are sparse in ln R.')
    p.add_argument('--npz-dir', default=None, dest='npz_dir')
    p.add_argument('--conv-csv', default=None, dest='conv_csv')
    p.add_argument('--out-dir', default=None, dest='out_dir')
    p.add_argument('--radius-method', choices=list(VALID_METHODS), default=None,
                   dest='radius_method',
                   help='Which convergence table to read for the R_conv line.')
    p.add_argument('--csv', action='store_true', dest='write_csv',
                   help='Also write the binned profile as a CSV.')
    args = p.parse_args(argv)

    npz_dir = paths.resolve(args.npz_dir, paths.default_npz_dir(soft=True))
    known = _known_configs(npz_dir)
    if not known:
        p.error(f'no config_*.npz in {npz_dir} — see README section 1.')

    config = args.config
    interactive = sys.stdin is not None and sys.stdin.isatty()
    if config is None:
        config = _ask_config(known) if interactive else None
        if config is None:
            p.error('config is required when running non-interactively.')
    else:
        resolved = resolve_config(config, known)
        if resolved is None:
            p.error(f'{config!r} matches no config in {npz_dir}')
        config = resolved

    return main(config, target=args.target, x_axis=args.x_axis,
                field=args.field, dr=args.dr, rmax=args.rmax, theta=args.theta,
                stat=args.stat, deriv=args.deriv, smooth=args.smooth,
                log_bw=args.log_bw, mode=args.mode, show_conv=args.show_conv,
                npz_dir=args.npz_dir, conv_csv=args.conv_csv,
                out_dir=args.out_dir, radius_method=args.radius_method,
                write_csv=args.write_csv)


if __name__ == '__main__':
    cli()
