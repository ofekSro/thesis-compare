"""Measure the E(r) anchor triplet (R_peak, E_peak, decay) for every config.

This is the measurement side of the street-channelling model, made a proper
tool: the script that produced ``r_peak_all96.csv`` was never kept, and its
decay anchor is the reason this rewrite exists.

WHY THE DECAY IS MEASURED BY A SLOPE FIT, NOT A CROSSING
--------------------------------------------------------
The old ``R_half`` was "the first distance past the peak where the excess
E - 1 halves, 3 consecutive slices" — a single-crossing detector. Two
measured failure modes:

* it is unstable to the slice width: re-measured at 2 m instead of 0.5 m
  slices, the implied decay length moved 20% at the median — one crossing
  point inherits the full staircase noise of the intersections;
* on plateau-topped profiles (e.g. config_56) the "halving" lands wherever
  the plateau happens to end, not where the decay actually runs.

The replacement fits the WHOLE fall: ordinary least squares of
``ln(E - 1)`` against ``r`` over the decay window, giving a decay length
``L_decay`` (metres per e-fold of the excess). The half-decay anchor is then
derived, not detected:

    R_half = R_peak + ln(2) * L_decay

Same semantics — the distance where the excess halves — but carried by every
slice of the fall instead of one crossing. ``L_decay`` itself is independent
of R_peak noise (a slope does not care where the axis origin sits), which
matters because the fall scale is the quantity the Pi-predictability question
is about.

The decay window: from where the excess first drops below ``hi_frac`` of the
peak excess (skipping the plateau, which carries no slope information) down
to where it drops below ``max(lo_frac * peak excess, FLOOR - 1)`` (below
E ≈ 1.2 the profile is noise, per the model's own floor). A fit needs at
least MIN_PTS slices spanning MIN_SPAN metres, and a negative slope;
otherwise the config genuinely does not decay inside the domain (the s = 20
family) and NaN is reported, as before.

Conventions carried over from the documented investigation, deliberately:
slices inside the exclusion radius are dropped BEFORE smoothing; the peak
search starts at b+s (det1) / s/2 + b (det2); everything is capped at 100 m
(grid 1's extent, one resolution); smoothing is ~2.5 m physical regardless
of slice width.

Usage:
    python tools\\e_profile\\measure_anchors.py                # all 96 -> CSV
    python tools\\e_profile\\measure_anchors.py --dr 2.0       # stability run
    python tools\\e_profile\\measure_anchors.py --hi 0.90 --lo 0.30
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pressure_profile'))

import numpy as np
import pandas as pd

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.geometry import exclude_radius
from blastlib.io.npz_store import load_processed_data
from pressure_profile import street_profile, _say

FLOOR = 1.2        # below this E is noise, not channelling (model convention)
MIN_PTS = 6        # a slope needs support...
MIN_SPAN = 4.0     # ...and physical extent [m]
RMAX = 100.0       # grid 1's extent — keep the whole profile on one resolution


def detector_start(cfg):
    """Where the peak search begins — past the first block, as documented."""
    if cfg['det'] == 1:
        return cfg['bsize'] + cfg['swidth']
    return cfg['swidth'] / 2.0 + cfg['bsize']


def _smooth(a, dr):
    """~2.5 m running mean regardless of slice width (odd k, k >= 1)."""
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


def measure_profile(prof, cfg, dr, hi_frac=0.85, lo_frac=0.25):
    """Anchor triplet from one street profile. Returns a dict.

    R_peak, E_peak : location/height of the smoothed maximum past the
                     detector start (unchanged from the original convention).
    L_decay        : e-folding length of the excess from the slope fit.
    R_half_slope   : R_peak + ln(2)*L_decay  (derived half-decay anchor).
    R_half_cross   : the legacy crossing detector, kept for comparison.
    n_fit, span_fit: support of the slope fit, for filtering downstream.
    """
    ex = exclude_radius(cfg)
    v = prof[prof.r > ex].reset_index(drop=True)          # BEFORE smoothing
    out = dict(R_peak=np.nan, E_peak=np.nan, L_decay=np.nan,
               R_half_slope=np.nan, R_half_cross=np.nan,
               n_fit=0, span_fit=0.0)
    if len(v) < MIN_PTS:
        return out
    r = v.r.values
    E = _smooth(v.ratio.values, dr)

    start = max(detector_start(cfg), ex)
    search = (r >= start) & (r <= RMAX)
    if not search.any():
        return out
    i_pk = np.flatnonzero(search)[int(np.argmax(E[search]))]
    R_pk, E_pk = float(r[i_pk]), float(E[i_pk])
    out.update(R_peak=R_pk, E_peak=E_pk)

    excess = E - 1.0
    ep = excess[i_pk]
    if ep <= FLOOR - 1.0:          # no channelling — nothing decays
        return out

    # ---- legacy crossing detector (comparison only) ----
    half = ep / 2.0
    below = excess[i_pk:] <= half
    run = 0
    for j, b in enumerate(below):
        run = run + 1 if b else 0
        if run >= 3:
            out['R_half_cross'] = float(r[i_pk + j - 2])
            break

    # ---- slope fit over the fall ----
    lo_cut = max(lo_frac * ep, FLOOR - 1.0)
    hi_cut = hi_frac * ep
    tail_r, tail_e = r[i_pk:], excess[i_pk:]
    inside = np.flatnonzero(tail_e <= hi_cut)             # past the plateau
    if not inside.size:
        return out
    j0 = inside[0]
    ended = np.flatnonzero(tail_e[j0:] <= lo_cut)
    j1 = j0 + ended[0] if ended.size else len(tail_e)
    rr, ee = tail_r[j0:j1], tail_e[j0:j1]
    keep = ee > 0
    rr, ee = rr[keep], ee[keep]
    if len(rr) < MIN_PTS or (rr.max() - rr.min()) < MIN_SPAN:
        return out
    slope, _ = np.polyfit(rr, np.log(ee), 1)
    if slope >= 0:                 # does not decay inside the domain
        return out
    L = -1.0 / slope
    out.update(L_decay=float(L), R_half_slope=float(R_pk + np.log(2.0) * L),
               n_fit=int(len(rr)), span_fit=float(rr.max() - rr.min()))
    return out


def main(*, npz_dir=None, out_csv=None, dr=0.5, hi_frac=0.85, lo_frac=0.25,
         progress=None):
    say = progress or _say
    npz_dir = paths.resolve(npz_dir, paths.default_npz_dir(soft=True))
    out_csv = Path(paths.resolve(
        out_csv, paths.CHECK_RESULTS_DIR / 'street_anchors.csv'))
    paths.ensure_dir(out_csv.parent)

    rows = []
    names = sorted(p.stem for p in Path(npz_dir).glob('config_*.npz'))
    say(f'{len(names)} configs from {npz_dir}   '
        f'(dr={dr:g} m, window {hi_frac:g}-{lo_frac:g} of peak excess)')
    for i, name in enumerate(names):
        proc, ok = load_processed_data(npz_dir, name)
        if not ok:
            say(f'  [{i + 1}/{len(names)}] {name}: NPZ load failed, skipped')
            continue
        cfg = config_parser(name)
        prof = street_profile(proc, cfg, dr=dr, rmax=RMAX, rmin=0.0)
        anchors = measure_profile(prof, cfg, dr, hi_frac, lo_frac)
        rows.append(dict(cfg=name, det=cfg['det'], b=cfg['bsize'],
                         s=cfg['swidth'], H=cfg['height'], W=cfg['weight'],
                         Rex=exclude_radius(cfg), Rmin=detector_start(cfg),
                         dr=dr, hi_frac=hi_frac, lo_frac=lo_frac, **anchors))
        if (i + 1) % 16 == 0:
            say(f'  [{i + 1}/{len(names)}]')
    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False)
    n_dec = int(df.L_decay.notna().sum())
    say(f'wrote {out_csv}  ({len(df)} configs, {n_dec} with a fitted decay)')
    return df


def cli(argv=None):
    p = argparse.ArgumentParser(
        description='Street-profile anchors (R_peak, E_peak, slope-fit decay) '
                    'for every configuration.')
    p.add_argument('--npz-dir', default=None, dest='npz_dir')
    p.add_argument('--out-csv', default=None, dest='out_csv',
                   help='default outputs/check_results/street_anchors.csv')
    p.add_argument('--dr', type=float, default=0.5, help='slice width [m]')
    p.add_argument('--hi', type=float, default=0.85, dest='hi_frac',
                   help='fit starts below this fraction of the peak excess')
    p.add_argument('--lo', type=float, default=0.25, dest='lo_frac',
                   help='fit ends below this fraction (or the E=1.2 floor)')
    a = p.parse_args(argv)
    return main(npz_dir=a.npz_dir, out_csv=a.out_csv, dr=a.dr,
                hi_frac=a.hi_frac, lo_frac=a.lo_frac)


if __name__ == '__main__':
    cli()
