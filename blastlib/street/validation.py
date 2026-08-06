"""Score the closed-form model against the measured 88 — the honest way.

This module is the writer e_profile_validation_88.csv never had: the table
was produced by a one-off script; the scoring block survived inside the
retired e_profile.py (:234-252) and reproduces the pinned file digit for
digit. Here that block is a pure function (score_profile) plus a batch
driver (validate_all), so the convention is testable without data.

THE SCORING CONVENTION, PRECISELY (each clause is load-bearing)
---------------------------------------------------------------
* Membership: a config is validated iff its MEASURED anchors E_peak >=
  FLOOR — computed from street_anchors.csv, never hardcoded. 88 of 96
  qualify; the excluded 8 (4x det1_b10_s12, 4x low det1_b15_s20) never
  channel, and slices with no channelling carry no information about a
  channelling model. Scoring them once produced a fake +-8% structured
  residual — the exclusion is on both sides of the comparison, fit and
  score alike.
* Slice selection: r <= r_model[-1] (the envelope grid's last point, up to
  X_MAX*S*R_half capped at 100 m) AND smoothed E_s >= FLOOR; at least 5
  qualifying slices or no score.
* Effective domain: the model is NaN past x = X_MAX, np.interp propagates
  the NaN, and np.nanmean drops it — so slices in 1.6 < x <= 2.16 are
  SELECTED (they count toward the >= 5) but NOT SCORED. Preserved
  verbatim; changing it re-scores the pinned table.
* The error is MAPE relative to the MEASUREMENT: 100*mean(|pred - E_s| /
  E_s), over the smoothed measured profile — the raw slices carry the
  intersection staircase, which is measurement texture, not model error.
* Validation measures E on its own conventions (quirk ledger Q1/Q2/Q5):
  inclusive exclusion cut, fixed k=5 smoothing, and E_peak_meas = the
  smoothed maximum over r <= r_model[-1] with no detector_start — which is
  why config_56 reads 3.145 here and 2.714 in the anchors table. Both are
  correct under their own convention; the pinned CSV carries this one.

Headline on the pinned table: profile MAPE mean 9.74, median 8.50,
p90 17.34, max 31.0 (%). Worst corner: config_56 (plateau), then the
Pi2 = 0.44 family (config_03/06/57) — the known worst corner of every
formula system in this project.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.io.npz_store import load_processed_data
from blastlib.progress import say as _say
from blastlib.street import conventions, model
from blastlib.street.constants import ENV, FLOOR, GATE, RMAX, X_MAX
from blastlib.street.strip import street_profile


def measured_profile(config, npz_dir=None, dr=0.5):
    """The measured strip profile under the VALIDATION conventions.

    Returns the slice frame with an E_s column (smoothed ratio), cut at
    the exclusion radius inclusively (Q1) and smoothed with fixed k=5
    (Q2) — the spellings the pinned validation table was produced with.
    None when the config's NPZ is absent.
    """
    npz_dir = paths.resolve(npz_dir, paths.default_npz_dir(soft=True))
    proc, ok = load_processed_data(npz_dir, config)
    if not ok:
        return None
    cfg = config_parser(config)
    prof = street_profile(proc, cfg, dr=dr, rmax=RMAX)
    v = conventions.cut_exclusion(prof, cfg, inclusive=True)
    v = v.copy()
    v['E_s'] = conventions.smooth_fixed(v.ratio.values)
    return v


def model_grid(b, s, H):
    """The prediction grid: 0.5 m steps to min(X_MAX*S*R_half, RMAX).

    The grid's last point is the slice-selection cap in score_profile —
    grid and selection are one convention, which is why they live in one
    function.
    """
    Rh = model.r_half(b, s, H)
    return np.arange(0.5, min(X_MAX * ENV['S'] * Rh, RMAX), 0.5)


def score_profile(meas, r_model, pred):
    """The pinned scoring convention as a pure function.

    meas needs columns r and E_s. Returns (mape_percent, n_selected) —
    mape is None when fewer than 5 slices qualify (the measured profile
    never reaches the floor inside the domain). See the module docstring
    for the clause-by-clause meaning; tests lock each clause separately.
    """
    common = meas[(meas.r <= r_model[-1]) & (meas.E_s >= FLOOR)]
    if len(common) < 5:
        return None, int(len(common))
    pr = np.interp(common.r, r_model, pred)
    err = 100 * np.nanmean(np.abs(pr - common.E_s) / common.E_s)
    return float(err), int(len(common))


def validate_all(anchors_csv=None, npz_dir=None, out_csv=None, progress=None):
    """The 88-config validation table — e_profile_validation_88.csv.

    Rounding is part of the pinned-file contract: E_peak_pred 3 dp,
    E_peak_meas 2 dp, R_half_pred and profile_mape 1 dp. Returns the
    DataFrame; writes it when out_csv is given.
    """
    say = progress or _say
    anchors_csv = paths.resolve(anchors_csv,
                                paths.CHECK_RESULTS_DIR / 'street_anchors.csv')
    anchors = pd.read_csv(anchors_csv)
    members = anchors[anchors.E_peak >= FLOOR]
    say(f'{len(members)} channelling configs of {len(anchors)} '
        f'(measured E_peak >= {FLOOR:g})')

    rows = []
    for i, row in enumerate(members.itertuples()):
        meas = measured_profile(row.cfg, npz_dir)
        if meas is None:
            say(f'  {row.cfg}: NPZ load failed, skipped')
            continue
        Ep = model.e_peak(row.b, row.s, row.H, row.W)
        Rh = model.r_half(row.b, row.s, row.H)
        r = model_grid(row.b, row.s, row.H)
        pred = model.predict_profile(r, row.b, row.s, row.H, row.W)
        pk_m = meas[meas.r <= r[-1]].E_s.max()          # Q5: validation E_peak
        mape, n_common = score_profile(meas, r, pred)
        if mape is None:
            say(f'  {row.cfg}: only {n_common} slices reach E={FLOOR:g} — '
                'not scorable')
            continue
        rows.append(dict(cfg=row.cfg, det=row.det, b=row.b, s=row.s,
                         H=row.H, W=row.W,
                         E_peak_pred=round(Ep, 3), E_peak_meas=round(pk_m, 2),
                         R_half_pred=round(Rh, 1),
                         profile_mape=round(mape, 1)))
        if (i + 1) % 16 == 0:
            say(f'  [{i + 1}/{len(members)}]')
    df = pd.DataFrame(rows)
    if out_csv is not None:
        out_csv = Path(out_csv)
        paths.ensure_dir(out_csv.parent)
        df.to_csv(out_csv, index=False)
        say(f'wrote {out_csv}  ({len(df)} configs)')
    return df


def headline_stats(val_df):
    """mean / median / p90 / max of the profile MAPE column.

    Computed from the (rounded) table column, matching how the published
    numbers were derived; p90 is np.percentile's linear interpolation.
    """
    m = val_df.profile_mape.values
    return dict(mean=float(np.mean(m)), median=float(np.median(m)),
                p90=float(np.percentile(m, 90)), max=float(np.max(m)))


def gate_table(anchors):
    """Predicted-vs-measured gate classification over all 96 configs.

    Truth is the MEASURED anchors E_peak >= GATE; prediction is the model
    E_peak >= GATE. Returns (per-config DataFrame, summary dict). The
    honest tally under the shipped constants: 92/96 correct, misses
    config_67/70 (measured 1.65, predicted 1.43/1.46), false alarms
    config_78/80 (measured 1.18, predicted 1.58/1.59) — the once-claimed
    "zero false alarms" was measured on pre-refit constants and is wrong;
    the false alarms are at least the conservative direction.
    """
    rows = []
    for row in anchors.itertuples():
        Ep = model.e_peak(row.b, row.s, row.H, row.W)
        rows.append(dict(cfg=row.cfg, E_peak_meas=row.E_peak, E_peak_pred=Ep,
                         meas_strong=bool(row.E_peak >= GATE),
                         pred_strong=model.gate_verdict(Ep)))
    df = pd.DataFrame(rows)
    agree = df.meas_strong == df.pred_strong
    summary = dict(
        n_correct=int(agree.sum()), n=int(len(df)),
        misses=sorted(df.cfg[df.meas_strong & ~df.pred_strong]),
        false_alarms=sorted(df.cfg[~df.meas_strong & df.pred_strong]))
    return df, summary


def envelope_stats(anchors_csv=None, npz_dir=None, progress=None):
    """True in-sample envelope statistics over the 88 — the stale-claim fix.

    Pooled over the same slices the MAPE scores (r <= r_model[-1], smoothed
    E_s >= FLOOR): coverage = share with envelope >= E_s; exceed_gt_015 =
    share with E_s - envelope > 0.15; mean_overpred = mean of
    (envelope - E_s)/E_s. Measured 2026-08-06 under the shipped constants:
    coverage 96.34%, exceed 0.73%, mean overprediction 27.2%, worst single
    exceedance 0.723 at config_26 — superseding the stale 95.0% / 1.5% /
    24% / 0.96-at-config_03 that had been calibrated on pre-refit
    constants.
    """
    say = progress or _say
    anchors_csv = paths.resolve(anchors_csv,
                                paths.CHECK_RESULTS_DIR / 'street_anchors.csv')
    anchors = pd.read_csv(anchors_csv)
    members = anchors[anchors.E_peak >= FLOOR]
    n = cover = exceed = 0
    overpred = []
    worst, worst_cfg = -np.inf, None
    for row in members.itertuples():
        meas = measured_profile(row.cfg, npz_dir)
        if meas is None:
            continue
        r = model_grid(row.b, row.s, row.H)
        env = model.predict_envelope(r, row.b, row.s, row.H, row.W)
        common = meas[(meas.r <= r[-1]) & (meas.E_s >= FLOOR)]
        ev = np.interp(common.r, r, env)
        es = common.E_s.values
        n += len(common)
        cover += int(np.sum(ev >= es))
        exceed += int(np.sum(es - ev > 0.15))
        overpred.append((ev - es) / es)
        wi = float(np.max(es - ev)) if len(common) else -np.inf
        if wi > worst:
            worst, worst_cfg = wi, row.cfg
    out = dict(n_slices=int(n), coverage=100.0 * cover / n,
               exceed_gt_015=100.0 * exceed / n,
               mean_overpred=100.0 * float(np.mean(np.concatenate(overpred))),
               worst_exceed=worst, worst_cfg=worst_cfg)
    say(f"envelope in-sample: coverage {out['coverage']:.2f}%  "
        f">0.15 exceed {out['exceed_gt_015']:.2f}%  "
        f"mean overpred {out['mean_overpred']:.1f}%  "
        f"worst {out['worst_exceed']:.3f} at {out['worst_cfg']}  "
        f"({n} slices)")
    return out
