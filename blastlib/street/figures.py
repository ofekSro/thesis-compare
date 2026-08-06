"""Every figure of the street suite — rendering only, no science.

The science lives in strip/anchors/fitting/model/validation; this module
draws it. Three of the four figure sets (the validation CSV's per-config
panels, the envelope corners, the pressure checks) previously had NO
in-repo writer — they were produced by one-off scripts that were never
kept; the formats here are reconstructed from the shipped PNGs and the
surviving single-config code of the retired e_profile.py.

Layout contract (what a full run leaves under outputs/figures/e_profile/):
    {config}_E.png              one per validated config (88), top level
    master_curve_collapse.png   the pooled-cloud collapse + fitted g
    all88/                      the same 88 panels + _contact_sheet.png
    env/                        the 4 envelope corner cases + _sheet.png
    pressure_check/             10 two-panel P-and-E checks
The directory is still named e_profile: it is the same artefact set the
docs and thesis reference; renaming it would orphan every existing link.

draw_profile draws into a CALLER-OWNED Figure and is the single source of
the per-config panel — the PNG writer and the GUI preview tab both call
it, so the interactive view can never drift from the published figure.
"""

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.geometry import exclude_radius
from blastlib.progress import say as _say
from blastlib.street import model
from blastlib.street.constants import ENV, FLOOR, GATE, X_MAX
from blastlib.street.fitting import g_unit
from blastlib.street.validation import (measured_profile, model_grid,
                                        score_profile)

# The envelope's four named corner cases: the Pi2 = 0.44 corner
# (config_03), the plateau top that stretches every convention
# (config_56), the largest s = 20 zone (config_68), and the small-block
# far-charge corner (config_96). Kept as a fixed set so the sheet stays
# comparable across reruns.
ENV_CORNERS = (
    'config_03_det1_b15_s5_h4_w1500',
    'config_56_det2_b30_s5_h4_w500',
    'config_68_det2_b30_s20_h12_w500',
    'config_96_det2_b10_s5_h24_w1000',
)

# The pressure-check spread: a cross-section over det, b, s, H and W —
# a spot check that E(r)*P_ff reconstructs the measured pressure, not a
# special population.
PRESSURE_CHECK = (
    'config_08_det1_b15_s5_h24_w500',
    'config_22_det1_b30_s5_h12_w50',
    'config_24_det1_b30_s5_h12_w1500',
    'config_25_det1_b30_s5_h24_w50',
    'config_37_det2_b15_s5_h4_w50',
    'config_49_det2_b15_s20_h12_w50',
    'config_58_det2_b30_s5_h12_w50',
    'config_62_det2_b30_s5_h24_w500',
    'config_91_det1_b10_s5_h24_w250',
    'config_92_det1_b10_s5_h24_w1000',
)


def draw_profile(fig, b, s, H, W, det, meas=None, title=None, say=None):
    """The per-config panel: model + envelope, measurement overlaid.

    Draws into the given Figure (cleared first) and returns a dict with
    E_peak, R_half, the gate verdict and — when a measurement was given —
    the channelling-zone MAPE. Everything the panel states numerically
    comes from blastlib.street.model/validation, so this stays a view.
    """
    say = say or (lambda _msg: None)
    Ep, Rh = model.e_peak(b, s, H, W), model.r_half(b, s, H)
    r = model_grid(b, s, H)
    pred = model.predict_profile(r, b, s, H, W)
    env = model.predict_envelope(r, b, s, H, W)

    fig.clear()
    ax = fig.add_subplot(111)
    ax.axhline(1.0, color='0.4', lw=1)
    ax.axhline(GATE, color='0.6', lw=1, ls=':')
    ax.plot(r, env, color='tab:blue', lw=1.6, ls='--',
            label=f"design envelope (in-sample coverage 96.3%, "
                  f"f={ENV['f']:g}, S={ENV['S']:g})")
    ax.fill_between(r, 1.0, env, where=np.isfinite(env), color='tab:blue',
                    alpha=0.06, lw=0)
    ax.plot(r, pred, color='tab:blue', lw=2.2,
            label='best estimate:  1 + (E_peak−1)·g(r/R_half)')
    out = dict(E_peak=float(Ep), R_half=float(Rh),
               strong=model.gate_verdict(Ep), mape=None)
    if meas is not None:
        ax.plot(meas.r, meas.ratio, color='0.75', lw=0.8,
                label='measured (raw slices)')
        ax.plot(meas.r, meas.E_s, color='tab:red', lw=1.8,
                label='measured (smoothed)')
        pk_m = meas[meas.r <= r[-1]].E_s.max()
        say(f'  measured E_peak = {pk_m:.2f}  (predicted {Ep:.2f}, '
            f'{100 * (Ep - pk_m) / pk_m:+.0f}%)')
        mape, n_common = score_profile(meas, r, pred)
        if mape is not None:
            say(f'  profile MAPE, channelling zone (E>={FLOOR:g}, '
                f'r<={r[-1]:.0f} m): {mape:.1f}%')
            ax.text(0.99, 0.02, f'MAPE {mape:.1f}% over the channelling zone',
                    transform=ax.transAxes, ha='right', fontsize=8,
                    color='0.4')
            out['mape'] = mape
        else:
            say(f'  measured profile never reaches E={FLOOR:g} — '
                'nothing to score the channelling model against')
    if r[-1] >= X_MAX * Rh - 1:
        ax.annotate('→ free field\n(mildly attenuated)', (X_MAX * Rh, 1.0),
                    xytext=(6, 6), textcoords='offset points', fontsize=8,
                    color='0.4')
    for xv, lab in [(0.52 * Rh, 'peak'), (Rh, 'R_half'), (1.6 * Rh, 'E→1')]:
        if xv < r[-1]:
            ax.axvline(xv, color='tab:blue', ls=':', lw=1, alpha=0.6)
            ax.annotate(lab, (xv, 1), xycoords=('data', 'axes fraction'),
                        xytext=(2, -11), textcoords='offset points',
                        fontsize=8, color='tab:blue', va='top')
    verdict = 'STRONG local zone' if out['strong'] else 'no strong local zone'
    ax.set_title(f'{title}\nE_peak = {Ep:.2f} ({verdict}) · '
                 f'R_half = {Rh:.0f} m')
    ax.set_xlabel('distance along the street r [m]')
    ax.set_ylabel('E = P_urban / P_ff')
    ax.grid(alpha=0.25)
    ax.legend(fontsize=9)
    return out


def find_matching_config(b, s, H, W, det, npz_dir):
    """The stored config with exactly this geometry, or None — used to
    overlay a measurement when free geometry happens to hit one."""
    for p in sorted(Path(npz_dir).glob('config_*.npz')):
        c = config_parser(p.stem)
        if (c['bsize'], c['swidth'], c['height'], c['weight'], c['det']) == \
                (b, s, H, W, det):
            return p.stem
    return None


def profile_figure(config=None, b=None, s=None, H=None, W=None, det=None,
                   dr=0.5, npz_dir=None, out_dir=None, save=True,
                   write_csv=False, progress=None):
    """Predicted-vs-measured E(r) for one config or free geometry.

    With a config token the measurement is overlaid; with free geometry
    only the prediction is drawn (unless the geometry happens to match a
    stored config, whose measurement is then added). Returns the Figure
    when save=False (the GUI contract), else the PNG path.
    """
    say = progress or _say
    npz_dir = paths.resolve(npz_dir, paths.default_npz_dir(soft=True))
    if config is not None:
        cfg = config_parser(config)
        b, s, H, W, det = (cfg['bsize'], cfg['swidth'], cfg['height'],
                           cfg['weight'], cfg['det'])
    elif None in (b, s, H, W, det):
        raise ValueError('give a config, or all of b, s, H, W, det')
    else:
        config = find_matching_config(b, s, H, W, det, npz_dir)
        if config:
            say(f'  geometry matches {config} — overlaying its measurement')

    say(f'b={b:g} s={s:g} H={H:g} W={W:g} det{det}')
    meas = measured_profile(config, npz_dir, dr) if config else None
    title = config if config else f'b{b:g}_s{s:g}_h{H:g}_w{W:g}_det{det}'
    fig = plt.figure(figsize=(9, 5.5))
    draw_profile(fig, b, s, H, W, det, meas=meas, title=title, say=say)

    if not save:
        return fig
    out_dir = paths.ensure_dir(paths.resolve(out_dir,
                                             paths.fig_dir('e_profile')))
    png = out_dir / f'{title}_E.png'
    fig.savefig(png, dpi=150, bbox_inches='tight')
    plt.close(fig)
    say(f'  wrote {png}')
    if write_csv:
        r = model_grid(b, s, H)
        df = pd.DataFrame({'r': r,
                           'E_pred': model.predict_profile(r, b, s, H, W)})
        if meas is not None:
            df['E_meas'] = np.interp(r, meas.r, meas.E_s,
                                     left=np.nan, right=np.nan)
        csv = out_dir / f'{title}_E.csv'
        df.to_csv(csv, index=False)
        say(f'  wrote {csv}')
    return png


def collapse_figure(x, y, gfit, mc, iqr_new, iqr_old, n_profiles,
                    out_dir=None, progress=None):
    """The master-curve collapse: pooled cloud, IQR band, fitted g.

    Pure rendering — the caller (pipeline fit stage) supplies the cloud,
    the fit dict and the binned table so the numbers drawn are exactly the
    numbers written to master_curve_g.csv.
    """
    say = progress or _say
    out_dir = paths.ensure_dir(paths.resolve(out_dir,
                                             paths.fig_dir('e_profile')))
    A, p, q = gfit['A'], gfit['p'], gfit['q']
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(x, y, '.', ms=1.5, color='0.75', alpha=0.35, rasterized=True)
    ax.fill_between(mc.x, mc.p25, mc.p75, color='tab:blue', alpha=0.18,
                    lw=0, label='pooled cloud, interquartile band')
    ax.plot(mc.x, mc['median'], color='tab:blue', lw=1.6,
            label='pooled median')
    xx = np.linspace(0.01, float(mc.x.max()) + 0.015, 300)
    ax.plot(xx, g_unit(xx, p, q), color='tab:red', lw=2.2,
            label=f'g(x) = {A:.0f}·x^{p:.2f}·exp(−{q:.2f}x)  (unit peak)')
    ax.axhline(0, color='0.4', lw=1)
    ax.set_xlabel('x = r / R_half   (slope-fit anchors)')
    ax.set_ylabel('(E − 1) / (E_peak − 1)')
    ax.set_title(f'Master curve, slope-fit anchors: {n_profiles} profiles, '
                 f'median IQR {iqr_new:.2f} (crossing anchors: {iqr_old:.2f})')
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25)
    png = out_dir / 'master_curve_collapse.png'
    fig.savefig(png, dpi=150, bbox_inches='tight')
    plt.close(fig)
    say(f'wrote {png}')
    return png


def _image_sheet(pngs, out_png, ncols, say):
    """Assemble saved panels into one contact sheet (presence > polish)."""
    pngs = [Path(p) for p in pngs]
    nrows = int(np.ceil(len(pngs) / ncols))
    first = plt.imread(pngs[0])
    aspect = first.shape[1] / first.shape[0]
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(ncols * 2.4, nrows * 2.4 / aspect))
    for ax in np.ravel(axes):
        ax.axis('off')
    for ax, png in zip(np.ravel(axes), pngs):
        ax.imshow(plt.imread(png))
        ax.set_title(png.stem.replace('_E', ''), fontsize=4)
    fig.subplots_adjust(wspace=0.02, hspace=0.12)
    fig.savefig(out_png, dpi=110, bbox_inches='tight')
    plt.close(fig)
    say(f'wrote {out_png}')
    return out_png


def all88_figures(anchors_csv=None, npz_dir=None, out_dir=None,
                  contact_sheet=True, progress=None):
    """One panel per validated config (top level) + the all88/ set.

    Membership is computed (anchors E_peak >= FLOOR), never listed. Each
    panel is rendered once at the top level and copied into all88/ — the
    historical layout kept both, and every doc link points at one of them.
    """
    say = progress or _say
    anchors_csv = paths.resolve(anchors_csv,
                                paths.CHECK_RESULTS_DIR / 'street_anchors.csv')
    anchors = pd.read_csv(anchors_csv)
    members = anchors[anchors.E_peak >= FLOOR]
    out_dir = paths.ensure_dir(paths.resolve(out_dir,
                                             paths.fig_dir('e_profile')))
    sub = paths.ensure_dir(out_dir / 'all88')
    pngs = []
    for i, cfg_name in enumerate(members.cfg):
        png = profile_figure(cfg_name, npz_dir=npz_dir, out_dir=out_dir,
                             progress=lambda _m: None)
        shutil.copyfile(png, sub / png.name)
        pngs.append(sub / png.name)
        if (i + 1) % 16 == 0:
            say(f'  [{i + 1}/{len(members)}]')
    say(f'wrote {len(pngs)} panels to {out_dir} (+ copies in {sub})')
    if contact_sheet and pngs:
        _image_sheet(pngs, sub / '_contact_sheet.png', ncols=8, say=say)
    return pngs


def envelope_corner_figures(npz_dir=None, out_dir=None, progress=None):
    """The four named envelope corner cases + their 2x2 sheet."""
    say = progress or _say
    out_dir = paths.ensure_dir(paths.resolve(out_dir,
                                             paths.fig_dir('e_profile')))
    sub = paths.ensure_dir(out_dir / 'env')
    pngs = [profile_figure(c, npz_dir=npz_dir, out_dir=sub, progress=say)
            for c in ENV_CORNERS]
    _image_sheet(pngs, sub / '_sheet.png', ncols=2, say=say)
    return pngs


def pressure_check_figure(config, npz_dir=None, out_dir=None, dr=0.5,
                          progress=None):
    """Two stacked panels: measured P vs P_calc = E(r)*P_ff, and E itself.

    The top panel is the point of the whole model: the measured street
    pressure (red), the free field on the same slices (grey dashed), and
    their model-reconstructed product (blue) on a log axis. The bottom
    panel shows the same comparison in E. The exclusion radius is shaded
    on both. MAPEs are quoted over the channelling zone only (the same
    slice selection as the validation table).
    """
    say = progress or _say
    npz_dir = paths.resolve(npz_dir, paths.default_npz_dir(soft=True))
    out_dir = paths.ensure_dir(paths.resolve(
        out_dir, paths.fig_dir('e_profile') / 'pressure_check'))
    cfg = config_parser(config)
    b, s, H, W, det = (cfg['bsize'], cfg['swidth'], cfg['height'],
                       cfg['weight'], cfg['det'])
    meas = measured_profile(config, npz_dir, dr)
    if meas is None:
        say(f'  {config}: NPZ load failed, skipped')
        return None
    Ep, Rh = model.e_peak(b, s, H, W), model.r_half(b, s, H)
    r = model_grid(b, s, H)
    pred = model.predict_profile(r, b, s, H, W)
    pred_at = np.interp(meas.r, r, pred)          # NaN past the domain
    p_calc = pred_at * meas.free_field

    e_mape, _ = score_profile(meas, r, pred)
    common = meas[(meas.r <= r[-1]) & (meas.E_s >= FLOOR)]
    pc = np.interp(common.r, r, pred) * common.free_field
    p_mape = float(100 * np.nanmean(np.abs(pc - common.urban) / common.urban))

    fig, (ax_p, ax_e) = plt.subplots(
        2, 1, sharex=True, figsize=(9, 8),
        gridspec_kw=dict(height_ratios=[1.4, 1], hspace=0.08))
    ax_p.semilogy(meas.r, meas.urban, color='tab:red', lw=1.5,
                  label='P measured (street strip)')
    ax_p.semilogy(meas.r, meas.free_field, color='0.55', lw=1.2, ls='--',
                  label='P free field (same slices)')
    ax_p.semilogy(meas.r, p_calc, color='tab:blue', lw=2.0,
                  label='P calculated = E(r)·P_ff')
    ax_p.set_ylabel('peak overpressure [kPa]')
    ax_p.legend(fontsize=9)
    ax_p.grid(alpha=0.25)

    ax_e.plot(meas.r, meas.ratio, color='0.75', lw=0.8,
              label='E measured (raw slices)')
    ax_e.plot(meas.r, meas.E_s, color='tab:red', lw=1.6,
              label='E measured (smoothed)')
    ax_e.plot(r, pred, color='tab:blue', lw=2.0, label='E calculated (model)')
    ax_e.axhline(1.0, color='0.4', lw=1)
    ax_e.axhline(GATE, color='0.6', lw=1, ls=':')
    ax_e.set_xlabel('distance along the street r [m]')
    ax_e.set_ylabel('E = P_urban / P_ff')
    ax_e.legend(fontsize=9)
    ax_e.grid(alpha=0.25)
    for ax in (ax_p, ax_e):
        ax.axvspan(0, exclude_radius(cfg), color='0.85', alpha=0.6, lw=0)
    fig.suptitle(f'{config}\nE_peak = {Ep:.2f}, R_half = {Rh:.0f} m · '
                 f'channelling-zone MAPE: E {e_mape:.1f}%, P {p_mape:.1f}%',
                 y=0.98)
    png = out_dir / f'{config}_P_and_E.png'
    fig.savefig(png, dpi=150, bbox_inches='tight')
    plt.close(fig)
    say(f'  wrote {png}')
    return png


def pressure_check_figures(configs=None, npz_dir=None, out_dir=None,
                           progress=None):
    """The pressure-check spread (default: the 10 shipped configs)."""
    say = progress or _say
    pngs = [pressure_check_figure(c, npz_dir=npz_dir, out_dir=out_dir,
                                  progress=say)
            for c in (configs or PRESSURE_CHECK)]
    return [p for p in pngs if p is not None]
