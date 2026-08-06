"""The anchor triplet of every street profile: R_peak, E_peak, and decay.

The anchors reduce each measured E(r) to the three numbers the closed-form
model is built from: where the channelling peaks (R_peak), how high
(E_peak), and how fast it falls (L_decay, from which the half-decay anchor
R_half = R_peak + ln(2)*L_decay is DERIVED, not detected).

WHY THE DECAY IS A SLOPE FIT, NOT A CROSSING
--------------------------------------------
The first R_half was "the first distance past the peak where the excess
E - 1 halves, 3 consecutive slices" — a single-crossing detector. Two
measured failure modes killed it:

* instability to the slice width: re-measured at 2 m instead of 0.5 m
  slices, the implied decay length moved 19.6% at the median — one
  crossing point inherits the full staircase noise of the street
  intersections;
* on plateau-topped profiles (config_56 is the exemplar) the "halving"
  lands wherever the plateau happens to end, not where the decay runs.

The replacement fits the WHOLE fall: ordinary least squares of ln(E - 1)
against r over the decay window, giving a decay length L_decay (metres per
e-fold of the excess). Same semantics — the distance where the excess
halves — but carried by every slice of the fall instead of one crossing:
the same 0.5 m -> 2 m re-measurement moves it 1.7% median. L_decay itself
is independent of R_peak noise (a slope does not care where the axis
origin sits). The legacy crossing detector is still measured into the
R_half_cross column for comparison, never for production.

The window convention (HI_FRAC..LO_FRAC of the peak excess, floored at
E = FLOOR) is now the DOMINANT anchor uncertainty: 85-25 vs 90-30 moves
R_half ~10% median. That is an honest stated convention, not mesh noise —
and it is why the model constants are refit whenever the convention moves
(fitting.py), rather than the anchor being tuned to keep old constants.

Conventions carried deliberately (see conventions.py for the full ledger):
slices inside the exclusion radius are dropped BEFORE smoothing (Q1,
strict); smoothing is ~2.5 m physical (Q2-Q4); the peak search starts at
detector_start and is capped at RMAX = 100 m; a row exists for every
config, NaN where nothing fits (Q7).
"""

from pathlib import Path

import numpy as np
import pandas as pd

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.progress import say as _say
from blastlib.geometry import exclude_radius
from blastlib.io.npz_store import load_processed_data
from blastlib.street import conventions
from blastlib.street.constants import (FLOOR, HI_FRAC, LO_FRAC, MIN_PTS,
                                       MIN_SPAN, RMAX)
from blastlib.street.strip import street_profile


def detector_start(cfg):
    """Where the peak search begins — past the first block.

    det1 (mid-street charge): b + s. det2 (intersection charge): s/2 + b.
    A SEARCH bound, not a validity bound (that is geometry.exclude_radius);
    both are geometric lengths on purpose — an absolute-kPa clause in
    either re-imports the charge through the back door (within-family CV
    of the marker 0.010 -> 0.255, measured twice).
    """
    if cfg['det'] == 1:
        return cfg['bsize'] + cfg['swidth']
    return cfg['swidth'] / 2.0 + cfg['bsize']


def measure_profile(prof, cfg, dr, hi_frac=HI_FRAC, lo_frac=LO_FRAC):
    """Anchor triplet from one raw strip profile. Returns a dict.

    R_peak, E_peak : location/height of the smoothed maximum past
                     detector_start (E_peak is the SMOOTHED value; argmax
                     takes the first maximum on ties).
    L_decay        : e-folding length of the excess from the slope fit,
                     NaN when the profile does not decay inside the domain
                     (the s = 20 family, honestly) or never channels.
    R_half_slope   : R_peak + ln(2)*L_decay — the derived half-decay anchor.
    R_half_cross   : the legacy crossing detector, kept for comparison.
    n_fit, span_fit: support of the slope fit, for filtering downstream.

    Every early exit returns the pre-seeded dict — a row per config always
    exists (quirk Q7).
    """
    ex = exclude_radius(cfg)
    v = conventions.cut_exclusion(prof, cfg)              # Q1: strict, BEFORE smoothing
    out = dict(R_peak=np.nan, E_peak=np.nan, L_decay=np.nan,
               R_half_slope=np.nan, R_half_cross=np.nan,
               n_fit=0, span_fit=0.0)
    if len(v) < MIN_PTS:
        return out
    r = v.r.values
    E = conventions.smooth_physical(v.ratio.values, dr)   # Q2-Q4

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

    # ---- legacy crossing detector (comparison only, never production) ----
    half = ep / 2.0
    below = excess[i_pk:] <= half
    run = 0
    for j, b in enumerate(below):
        run = run + 1 if b else 0
        if run >= 3:
            out['R_half_cross'] = float(r[i_pk + j - 2])
            break

    # ---- slope fit over the fall (window semantics: quirk Q6) ----
    lo_cut = max(lo_frac * ep, FLOOR - 1.0)
    hi_cut = hi_frac * ep
    tail_r, tail_e = r[i_pk:], excess[i_pk:]
    inside = np.flatnonzero(tail_e <= hi_cut)             # past the plateau
    if not inside.size:
        return out
    j0 = inside[0]
    ended = np.flatnonzero(tail_e[j0:] <= lo_cut)
    j1 = j0 + ended[0] if ended.size else len(tail_e)     # terminator EXCLUSIVE
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


def measure_all(npz_dir=None, dr=0.5, hi_frac=HI_FRAC, lo_frac=LO_FRAC,
                out_csv=None, progress=None):
    """Anchor table for every stored config — the street_anchors.csv writer.

    Returns the 96-row DataFrame (column order is part of the pinned-file
    contract); writes it to out_csv when given. Calls progress at least
    every 16 configs, which is what makes a GUI cancel land mid-batch.
    """
    say = progress or _say
    npz_dir = paths.resolve(npz_dir, paths.default_npz_dir(soft=True))

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
        prof = street_profile(proc, cfg, dr=dr, rmax=RMAX)
        anchors = measure_profile(prof, cfg, dr, hi_frac, lo_frac)
        rows.append(dict(cfg=name, det=cfg['det'], b=cfg['bsize'],
                         s=cfg['swidth'], H=cfg['height'], W=cfg['weight'],
                         Rex=exclude_radius(cfg), Rmin=detector_start(cfg),
                         dr=dr, hi_frac=hi_frac, lo_frac=lo_frac, **anchors))
        if (i + 1) % 16 == 0:
            say(f'  [{i + 1}/{len(names)}]')
    df = pd.DataFrame(rows)
    if out_csv is not None:
        out_csv = Path(out_csv)
        paths.ensure_dir(out_csv.parent)
        df.to_csv(out_csv, index=False)
        n_dec = int(df.L_decay.notna().sum())
        say(f'wrote {out_csv}  ({len(df)} configs, {n_dec} with a fitted decay)')
    return df
