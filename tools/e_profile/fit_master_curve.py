"""Refit the master curve g(x) and the R_half model from measured anchors.

Reads the anchor table written by measure_anchors.py, rescales every
channelling profile by its measured slope-fit R_half, pools the normalized
points, and refits:

  g(x)   = A * x^p * exp(-q*x),  A = (q/p)^p * e^p   (unit peak, 2 free
           parameters — the constraint keeps the predicted profile attaining
           E_peak exactly; provenance in STREET_CHANNELLING_MODEL.md)
  R_half = C * (b+s) * sqrt(rho)^p_sq * (H/s)^p_hs   (same form as shipped;
           constants refit because the anchor they were fitted to changed)

Outputs: master_curve_g.csv (x-binned median/quartiles of the pooled cloud),
the collapse figure, and the fitted constants printed for e_profile.py.
The old-anchor collapse is measured side by side so the change is a number,
not an impression.

The script that originally fitted g was never kept; this one is the
reproducible replacement.

Usage:
    python tools\\e_profile\\fit_master_curve.py
    python tools\\e_profile\\fit_master_curve.py --anchors path\\to\\anchors.csv
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pressure_profile'))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.geometry import exclude_radius
from blastlib.io.npz_store import load_processed_data
from pressure_profile import street_profile, _say

FLOOR = 1.2
X_FIT = 1.65        # channelling zone only; the attenuation tail is excluded
RMAX = 100.0


def _smooth(a, dr=0.5):
    k = max(1, int(round(2.5 / dr)))
    if k % 2 == 0:
        k -= 1
    if k <= 1:
        return np.asarray(a, float)
    w = np.ones(k) / k
    s = np.convolve(a, w, mode='same')
    p = k // 2
    s[:p], s[-p:] = a[:p], a[-p:]
    return s


def g_unit(x, p, q):
    """Unit-peak master curve; A is pinned by (p, q)."""
    A = (q / p) ** p * np.exp(p)
    return A * x ** p * np.exp(-q * x)


def collect_cloud(anchors, npz_dir, rhalf_col, say):
    """Normalized (x, y) points of every channelling profile, pooled."""
    pts_x, pts_y, used = [], [], []
    for _, row in anchors.iterrows():
        if not np.isfinite(row[rhalf_col]) or row.E_peak < FLOOR:
            continue
        proc, ok = load_processed_data(npz_dir, row.cfg)
        if not ok:
            continue
        cfg = config_parser(row.cfg)
        prof = street_profile(proc, cfg, dr=0.5, rmax=RMAX, rmin=0.0)
        v = prof[prof.r > exclude_radius(cfg)].reset_index(drop=True)
        E = _smooth(v.ratio.values)
        x = v.r.values / row[rhalf_col]
        y = (E - 1.0) / (row.E_peak - 1.0)
        keep = (x > 0) & (x <= X_FIT)
        pts_x.append(x[keep])
        pts_y.append(y[keep])
        used.append(row.cfg)
    say(f'  {len(used)} profiles pooled ({sum(len(p) for p in pts_x)} points)')
    return np.concatenate(pts_x), np.concatenate(pts_y), used


def collapse_iqr(x, y, nbin=40):
    """Median per-bin IQR — the number that says how well profiles collapse."""
    bins = np.linspace(0, X_FIT, nbin + 1)
    iqr = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (x >= lo) & (x < hi)
        if m.sum() >= 20:
            iqr.append(np.percentile(y[m], 75) - np.percentile(y[m], 25))
    return float(np.median(iqr))


def main(*, anchors_csv=None, npz_dir=None, out_dir=None, progress=None):
    say = progress or _say
    npz_dir = paths.resolve(npz_dir, paths.default_npz_dir(soft=True))
    anchors_csv = Path(paths.resolve(
        anchors_csv, paths.CHECK_RESULTS_DIR / 'street_anchors.csv'))
    out_dir = Path(paths.resolve(out_dir, paths.fig_dir('e_profile')))

    anchors = pd.read_csv(anchors_csv)
    say(f'anchors: {anchors_csv}')

    # ---- pooled cloud under the NEW (slope) anchors ----
    say('pooling profiles under the slope-fit R_half:')
    x, y, used = collect_cloud(anchors, npz_dir, 'R_half_slope', say)
    iqr_new = collapse_iqr(x, y)

    # ---- the same under the OLD (crossing) anchors, for the comparison ----
    say('pooling under the legacy crossing R_half (comparison):')
    xc, yc, _ = collect_cloud(anchors.rename(
        columns={'R_half_cross': '_rc'}).assign(R_half_cross=lambda d: d._rc),
        npz_dir, 'R_half_cross', say)
    iqr_old = collapse_iqr(xc, yc)

    say(f'collapse quality (median per-bin IQR): '
        f'crossing {iqr_old:.3f}  ->  slope {iqr_new:.3f}')

    # ---- refit g on the new cloud ----
    popt, _ = curve_fit(g_unit, x, y, p0=(2.8, 5.4), maxfev=20000)
    p, q = popt
    A = (q / p) ** p * np.exp(p)
    rms = float(np.sqrt(np.mean((g_unit(x, p, q) - y) ** 2)))
    say(f'g refit: A={A:.1f}  p={p:.2f}  q={q:.2f}   peak at x={p / q:.2f}   '
        f'g(1)={g_unit(np.array([1.0]), p, q)[0]:.2f}   rms {rms:.3f}')

    # ---- refit the R_half model constants (same form) ----
    d = anchors.dropna(subset=['R_half_slope']).copy()
    d = d[d.E_peak >= FLOOR]
    sq = d.b / (d.b + d.s)
    X = np.column_stack([np.ones(len(d)), np.log(sq), np.log(d.H / d.s)])
    yv = np.log(d.R_half_slope / (d.b + d.s))
    co, _, _, _ = np.linalg.lstsq(X, yv, rcond=None)
    C, p_sq, p_hs = float(np.exp(co[0])), float(co[1]), float(co[2])
    pred = (d.b + d.s) * C * sq ** p_sq * (d.H / d.s) ** p_hs
    mape = float(100 * np.mean(np.abs(pred - d.R_half_slope) / d.R_half_slope))
    say(f'R_half refit (n={len(d)}): C={C:.2f}  sqrt(rho)^{p_sq:.2f}  '
        f'(H/s)^{p_hs:.2f}   MAPE {mape:.1f}%')

    # ---- master curve table ----
    bins = np.linspace(0, X_FIT, 56)
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (x >= lo) & (x < hi)
        if m.sum() >= 20:
            rows.append(dict(x=0.5 * (lo + hi), n=int(m.sum()),
                             median=float(np.median(y[m])),
                             p25=float(np.percentile(y[m], 25)),
                             p75=float(np.percentile(y[m], 75))))
    mc = pd.DataFrame(rows)
    mc_csv = paths.CHECK_RESULTS_DIR / 'master_curve_g.csv'
    mc.to_csv(mc_csv, index=False)
    say(f'wrote {mc_csv}')

    # ---- collapse figure ----
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(x, y, '.', ms=1.5, color='0.75', alpha=0.35, rasterized=True)
    ax.fill_between(mc.x, mc.p25, mc.p75, color='tab:blue', alpha=0.18,
                    lw=0, label='pooled cloud, interquartile band')
    ax.plot(mc.x, mc['median'], color='tab:blue', lw=1.6,
            label='pooled median')
    xx = np.linspace(0.01, X_FIT, 300)
    ax.plot(xx, g_unit(xx, p, q), color='tab:red', lw=2.2,
            label=f'g(x) = {A:.0f}·x^{p:.2f}·exp(−{q:.2f}x)  (unit peak)')
    ax.axhline(0, color='0.4', lw=1)
    ax.set_xlabel('x = r / R_half   (slope-fit anchors)')
    ax.set_ylabel('(E − 1) / (E_peak − 1)')
    ax.set_title(f'Master curve, slope-fit anchors: {len(used)} profiles, '
                 f'median IQR {iqr_new:.2f} (crossing anchors: {iqr_old:.2f})')
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25)
    png = out_dir / 'master_curve_collapse.png'
    fig.savefig(png, dpi=150, bbox_inches='tight')
    plt.close(fig)
    say(f'wrote {png}')

    return dict(G=dict(A=round(A, 1), p=round(p, 2), q=round(q, 2)),
                RHALF=dict(C=round(C, 2), p_sq=round(p_sq, 2),
                           p_hs=round(p_hs, 2)),
                rms=rms, iqr_new=iqr_new, iqr_old=iqr_old,
                rhalf_mape=mape, n_profiles=len(used))


def cli(argv=None):
    p = argparse.ArgumentParser(
        description='Refit the master curve g and the R_half model from '
                    'measured street anchors.')
    p.add_argument('--anchors', default=None, dest='anchors_csv',
                   help='default outputs/check_results/street_anchors.csv')
    p.add_argument('--npz-dir', default=None, dest='npz_dir')
    p.add_argument('--out-dir', default=None, dest='out_dir')
    a = p.parse_args(argv)
    return main(anchors_csv=a.anchors_csv, npz_dir=a.npz_dir,
                out_dir=a.out_dir)


if __name__ == '__main__':
    cli()
