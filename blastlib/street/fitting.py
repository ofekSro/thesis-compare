"""Fit the model's constants from measured anchors — reproducibly.

Two of the model's three fitted pieces are re-derived here from
street_anchors.csv plus the NPZ stores, and land (before rounding) on
A=59.8843 p=2.4838 q=4.7467 / C=1.2850 p_sq=-1.0700 p_hs=0.2721 — the
shipped G and RHALF exactly (verified 2026-08-06, scipy 1.17.1; curve_fit
is deterministic Levenberg-Marquardt, no seed involved). The third piece,
EPK, is PINNED-HERITAGE: its original fitter was a one-off script that was
never kept. fit_e_peak/logo_e_peak below re-implement the fit as best it
can be reconstructed — they exist to VERIFY the pinned constants are
near-optimal (the parity report prints refit-vs-pinned deltas), and their
output is never adopted into constants.py.

DESIGN CHOICES THAT WERE PAID FOR (each measured end-to-end, i.e. by the
mean/median/p90 profile MAPE on the 88 — collapse-IQR comparisons between
anchor types are UNFAIR, because a crossing anchor self-aligns y(x=1)=0.5
by construction; end-to-end error is the only fair arbiter):

* UNIT-PEAK CONSTRAINT, not a free amplitude: fitting the pointwise MEDIAN
  of the pooled cloud under-attains every measured peak by ~9% (misaligned
  peaks average down). g_unit pins A = (q/p)^p * e^p so max g = 1 exactly
  and the predicted profile ATTAINS E_peak — the safety-critical number.
* FIT WINDOW 0 < x <= X_FIT = 1.65, attenuation tail EXCLUDED: an earlier
  two-term fit with a tail deficit pulled the fitted shape down INSIDE the
  channelling zone.
* (b+s) EXPONENT PINNED AT 1 in R_half: freeing it fits 1.12 and scores
  WORSE (10.1% vs 9.8% mean). The dimensional prior wins.
* NO Pi2 IN R_half: the charge dependence of the decay rate is real
  (within-family d ln L / d ln W median -0.108, matching Pi2^+0.28) but
  adding it is worse (p90 20.3% vs 17.4%) — the anchors' 42% LOGO noise
  enters directly. Composing R_peak_model + ln2*L_model is worst of all
  (10.8%). The oracle ceiling says measured R_half buys only 0.3pp and both
  anchors 0.9pp: the residual error lives in the SHAPE g (the per-crossing
  staircase, positions known from geometry) — the one avenue left open.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.io.npz_store import load_processed_data
from blastlib.progress import say as _say
from blastlib.street import conventions
from blastlib.street.constants import EPK, FLOOR, RMAX, X_FIT, pi2, sqrt_rho, w13
from blastlib.street.strip import street_profile


def g_unit(x, p, q):
    """Unit-peak master curve; A is pinned by (p, q), never fitted."""
    A = (q / p) ** p * np.exp(p)
    return A * x ** p * np.exp(-q * x)


def collect_cloud(anchors, npz_dir=None, rhalf_col='R_half_slope',
                  progress=None):
    """Normalized (x, y) points of every channelling profile, pooled.

    One profile enters iff its rhalf_col anchor is finite AND its measured
    E_peak >= FLOOR — under the slope anchors that is 75 profiles / 11,545
    points. x = r / anchor, y = (E_smoothed - 1) / (E_peak - 1), kept on
    0 < x <= X_FIT. Everything is measured at dr = 0.5 — the production
    slice width the anchors themselves were measured at; mixing widths here
    would divide by an anchor measured on a different profile.

    Returns (x, y, used_names). Point order follows the anchors row order —
    part of the bit-reproducibility of the fit, do not sort.
    """
    say = progress or _say
    npz_dir = paths.resolve(npz_dir, paths.default_npz_dir(soft=True))
    pts_x, pts_y, used = [], [], []
    for _, row in anchors.iterrows():
        if not np.isfinite(row[rhalf_col]) or row.E_peak < FLOOR:
            continue
        proc, ok = load_processed_data(npz_dir, row.cfg)
        if not ok:
            continue
        cfg = config_parser(row.cfg)
        prof = street_profile(proc, cfg, dr=0.5, rmax=RMAX)
        v = conventions.cut_exclusion(prof, cfg)          # Q1: strict
        E = conventions.smooth_physical(v.ratio.values, 0.5)
        x = v.r.values / row[rhalf_col]
        y = (E - 1.0) / (row.E_peak - 1.0)
        keep = (x > 0) & (x <= X_FIT)
        pts_x.append(x[keep])
        pts_y.append(y[keep])
        used.append(row.cfg)
        if len(used) % 16 == 0:
            say(f'  [{len(used)} profiles pooled]')
    say(f'  {len(used)} profiles pooled ({sum(len(p) for p in pts_x)} points)')
    return np.concatenate(pts_x), np.concatenate(pts_y), used


def collapse_iqr(x, y, nbin=40):
    """Median per-bin IQR — how well the profiles collapse onto one curve.

    Bins with fewer than 20 points are skipped. CAVEAT carried from the
    investigation: comparing this number between anchor TYPES is unfair
    (a crossing anchor pins y(x=1)=0.5 by construction, self-aligning the
    cloud); it is only meaningful within one anchor convention.
    """
    bins = np.linspace(0, X_FIT, nbin + 1)
    iqr = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (x >= lo) & (x < hi)
        if m.sum() >= 20:
            iqr.append(np.percentile(y[m], 75) - np.percentile(y[m], 25))
    return float(np.median(iqr))


def fit_master_curve(x, y):
    """Fit g_unit to the pooled cloud. Returns dict(A, p, q, rms).

    Plain unweighted least squares in LINEAR space (not log — the cloud
    crosses zero), scipy curve_fit with p0=(2.8, 5.4); deterministic, no
    seed. Full-precision result on the pinned anchors: A=59.8843 p=2.4838
    q=4.7467, rms 0.2061 — shipped G is this rounded to 1/2/2 dp.
    """
    popt, _ = curve_fit(g_unit, x, y, p0=(2.8, 5.4), maxfev=20000)
    p, q = float(popt[0]), float(popt[1])
    A = float((q / p) ** p * np.exp(p))
    rms = float(np.sqrt(np.mean((g_unit(x, p, q) - y) ** 2)))
    return dict(A=A, p=p, q=q, rms=rms)


def fit_r_half(anchors):
    """Refit the R_half constants to the slope anchors. Returns a dict.

    Closed-form log-space OLS (np.linalg.lstsq — deterministic): regress
    ln(R_half_slope / (b+s)) on [1, ln sqrt(rho), ln(H/s)] over the rows
    with a fitted decay and E_peak >= FLOOR (75). The (b+s) exponent is
    PINNED at 1 by construction of the response — see the module docstring
    for why freeing it was rejected. Full-precision result: C=1.2850
    p_sq=-1.0700 p_hs=0.2721, MAPE 16.51% against its own anchor.
    """
    d = anchors.dropna(subset=['R_half_slope']).copy()
    d = d[d.E_peak >= FLOOR]
    sq = d.b / (d.b + d.s)
    X = np.column_stack([np.ones(len(d)), np.log(sq), np.log(d.H / d.s)])
    yv = np.log(d.R_half_slope / (d.b + d.s))
    co, _, _, _ = np.linalg.lstsq(X, yv, rcond=None)
    C, p_sq, p_hs = float(np.exp(co[0])), float(co[1]), float(co[2])
    pred = (d.b + d.s) * C * sq ** p_sq * (d.H / d.s) ** p_hs
    mape = float(100 * np.mean(np.abs(pred - d.R_half_slope) / d.R_half_slope))
    return dict(C=C, p_sq=p_sq, p_hs=p_hs, mape=mape, n=int(len(d)))


def master_curve_table(x, y):
    """The x-binned median/quartile table — the master_curve_g.csv payload.

    linspace(0, X_FIT, 56) edges (55 bins of 0.03), bins with >= 20 points
    kept — 54 survive on the production cloud.
    """
    bins = np.linspace(0, X_FIT, 56)
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (x >= lo) & (x < hi)
        if m.sum() >= 20:
            rows.append(dict(x=0.5 * (lo + hi), n=int(m.sum()),
                             median=float(np.median(y[m])),
                             p25=float(np.percentile(y[m], 25)),
                             p75=float(np.percentile(y[m], 75))))
    return pd.DataFrame(rows)


# ---- E_peak verification refit (never adopted — see module docstring) ----

def _e_peak_form(pi_groups, C, a, b, k_hs, k_hw):
    """The E_peak functional form on stacked Pi-group columns."""
    sq, p2, hs, hw = pi_groups
    return 1 + C * sq ** a * p2 ** b * (1 - np.exp(-k_hs * hs)) \
        * (1 - np.exp(-k_hw * hw))


def _pi_columns(d):
    return (sqrt_rho(d.b.values, d.s.values), pi2(d.s.values, d.W.values),
            d.H.values / d.s.values, d.H.values / w13(d.W.values))


def fit_e_peak(anchors):
    """VERIFICATION refit of the E_peak constants on the channelling 88.

    The original fitter is lost; its loss function is unknown. This
    reconstruction fits ln(E_peak - 1) by least squares (relative errors on
    the excess — the quantity the model is about), initialized at the
    pinned constants. Output is evidence for the parity report, not a
    replacement: constants.EPK stays canonical regardless.
    """
    d = anchors[anchors.E_peak >= FLOOR]
    pig = _pi_columns(d)

    def _log_excess(_, C, a, b, k_hs, k_hw):
        return np.log(_e_peak_form(pig, C, a, b, k_hs, k_hw) - 1)

    p0 = (EPK['C'], EPK['a'], EPK['b'], EPK['k_hs'], EPK['k_hw'])
    popt, _ = curve_fit(_log_excess, np.zeros(len(d)),
                        np.log(d.E_peak.values - 1), p0=p0, maxfev=40000)
    keys = ('C', 'a', 'b', 'k_hs', 'k_hw')
    out = dict(zip(keys, (float(v) for v in popt)))
    pred = _e_peak_form(pig, *popt)
    out['mape'] = float(100 * np.mean(np.abs(pred - d.E_peak.values)
                                      / d.E_peak.values))
    out['n'] = int(len(d))
    return out


def logo_e_peak(anchors):
    """Leave-one-geometry-out score of the E_peak form on the 88.

    A geometry family is a unique (det, b, s, H) — the same buildings and
    charge position at different charge weights; the published 6.7% was
    scored over 36 such families. Each round refits on the other families
    (from the pinned starting point) and predicts the held-out one; the
    return is the pooled MAPE and the family count.
    """
    d = anchors[anchors.E_peak >= FLOOR].copy()
    fams = list(d.groupby(['det', 'b', 's', 'H']).groups)
    errs = []
    for fam in fams:
        hold = (d.det == fam[0]) & (d.b == fam[1]) & (d.s == fam[2]) \
            & (d.H == fam[3])
        train, test = d[~hold], d[hold]
        pig = _pi_columns(train)

        def _log_excess(_, C, a, b, k_hs, k_hw):
            return np.log(_e_peak_form(pig, C, a, b, k_hs, k_hw) - 1)

        p0 = (EPK['C'], EPK['a'], EPK['b'], EPK['k_hs'], EPK['k_hw'])
        try:
            popt, _ = curve_fit(_log_excess, np.zeros(len(train)),
                                np.log(train.E_peak.values - 1), p0=p0,
                                maxfev=40000)
        except RuntimeError:      # a fold that fails to converge scores as
            popt = p0             # the pinned constants — conservative
        pred = _e_peak_form(_pi_columns(test), *popt)
        errs.extend(np.abs(pred - test.E_peak.values) / test.E_peak.values)
    return dict(mape=float(100 * np.mean(errs)), n_families=len(fams))
