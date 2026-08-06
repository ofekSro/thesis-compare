"""Predicted vs measured channelling profile E(r) for one configuration.

E(r) = P_urban / P_ff along the first street (strip 0 <= Z <= s/2). The
prediction is the closed-form recipe fitted in this project, built from the
Pi groups alone:

    rho   = b^2/(b+s)^2      sqrt(rho) = b/(b+s)  wall continuity
    Pi2   = s / W^(1/3)                           street width in charge lengths
    H/s, H/W^(1/3)                                height saturations

    E_peak = 1 + 2.69 * sqrt(rho)^1.81 * Pi2^-0.50
                 * (1 - exp(-4.56*H/s)) * (1 - exp(-7.07*H/W^(1/3)))
    R_half = 1.28 * (b+s) * sqrt(rho)^-1.07 * (H/s)^0.27     [m]
    g(x)   = 59.9 * x^2.48 * exp(-4.75*x),  x = r / R_half,  x <= 1.6
             (unit peak at x = 0.52, so E(r) attains E_peak; g(1) = 0.52)
    E(r)   = 1 + (E_peak - 1) * g(r / R_half)

g describes the CHANNELLING ZONE ONLY. It was fitted to the master curve on
x <= 1.65 — the part of the profiles that carries channelling — after the
attenuation tail (E < 1 beyond ~1.6*R_half) was deliberately dropped: an
earlier two-term fit let that tail's deficit term pull the shape down inside
the zone of interest. Beyond 1.6*R_half the model simply says "back to free
field, mildly attenuated" and draws nothing.

Provenance: E_peak fitted on the 88 channelling configurations (E >= 1.2),
LOGO 6.7%. R_half is the slope-fit decay anchor (measure_anchors.py:
R_peak + ln2*L_decay, with L_decay from regressing ln(E-1) on r over the
fall) — mesh-stable to 1.7% where the old crossing detector moved 20% —
and its constants are refit to that anchor (fit_master_curve.py, 75
configs). g is fitted on the 75 slope-anchored profiles, channelling zone,
rms 0.206 against the pooled cloud (11,545 points). End-to-end profile
MAPE on the 88: mean 9.8%, median 8.5%, p90 17.4%, max 31.0% (the crossing
pipeline scored 10.4 / 9.4 / 18.0 / 28.5 on the same slices).

GATE: if E_peak < 1.5 the street does not channel strongly — no strong local
zone, and the profile prediction is not meaningful (below ~1.2 the measured
"peak" is a noise floor). The tool says so instead of drawing nonsense.

Usage:
    python tools\\e_profile\\e_profile.py 58                 # config number/name
    python tools\\e_profile\\e_profile.py --b 30 --s 5 --H 12 --W 50 --det 2
    python tools\\e_profile\\e_profile.py 58 --csv

With a config token the measured strip profile is drawn on top of the
prediction. With free geometry only the prediction is drawn (and if the
geometry happens to match one of the 96 configs, its measurement is added).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pressure_profile'))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.geometry import exclude_radius
from blastlib.io.npz_store import load_processed_data
from pressure_profile import street_profile, resolve_config, _say

# ---- fitted constants (provenance in the module docstring) ----
EPK = dict(C=2.69, a=1.81, b=-0.50, k_hs=4.56, k_hw=7.07)
# R_half is anchored by the SLOPE-FIT decay measurement (measure_anchors.py):
# ln(E-1) regressed on r over the fall, R_half = R_peak + ln2 * L_decay. The
# old single-crossing detector moved 20% when the slice width changed 0.5 -> 2
# m; the slope fit moves 1.7%. Constants refit to that anchor by
# fit_master_curve.py (same functional form; MAPE 16.5% against its own
# anchor — not comparable to the old 12.6%, which was scored against the old,
# noisier anchor).
RHALF = dict(C=1.28, p_sq=-1.07, p_hs=0.27)
# Unit-peak constraint: A = (q/p)^p * e^p, so max g = 1 exactly (at x = p/q)
# and the predicted profile ATTAINS E_peak instead of stopping at 91% of the
# excess. Fitted to the pooled cloud of the 75 slope-anchored profiles
# (11,545 points, rms 0.206) by fit_master_curve.py; peak stays at x = 0.52.
G = dict(A=59.9, p=2.48, q=4.75)
# Design envelope: E_env = 1 + f*(E_peak-1)*max{g(x*t) : t in [1/S, S]}.
# The central curve is a best estimate, so measurements exceed it about half
# the time by construction; the envelope is the bounding version. f absorbs
# amplitude scatter (E_peak under-predictions), the dilation S absorbs
# location scatter (late peaks, slow tails) and extends the domain to
# 1.6*S*R_half. Calibrated on the 88 channelling configurations (IN-SAMPLE —
# expect slightly less on new geometry): pooled slice coverage 95.0%, only
# 1.5% of slices exceed it by more than 0.15 in E, mean overprediction 24%
# (the price of a bound). Largest single exceedance 0.96, config_03 — the
# Pi2 = 0.44 envelope corner.
ENV = dict(S=1.35, f=1.20)
GATE = 1.5          # below this: no strong local zone
FLOOR = 1.2         # below this: E is noise, not channelling — excluded from
                    # the fits and from the measured-vs-predicted score alike
X_MAX = 1.6         # g is the channelling zone only; beyond ~1.6*R_half the
                    # street is back at (or mildly below) free field


def e_peak(b, s, H, W, det=None):
    """Channelling strength from the Pi groups (det does not enter — tested)."""
    sq = b / (b + s)
    Pi2 = s / W ** (1 / 3)
    return 1 + EPK['C'] * sq ** EPK['a'] * Pi2 ** EPK['b'] \
        * (1 - np.exp(-EPK['k_hs'] * H / s)) \
        * (1 - np.exp(-EPK['k_hw'] * H / W ** (1 / 3)))


def r_half(b, s, H):
    """Extent scale in metres — geometry only, no charge (tested: W-free)."""
    sq = b / (b + s)
    return RHALF['C'] * (b + s) * sq ** RHALF['p_sq'] * (H / s) ** RHALF['p_hs']


def g(x):
    """Master curve of the channelling zone: rise, peak at 0.53, decay."""
    x = np.asarray(x, float)
    return G['A'] * x ** G['p'] * np.exp(-G['q'] * x)


def e_profile(r, b, s, H, W):
    """Predicted E(r) [same shape as r]. NaN beyond the fitted range."""
    Rh = r_half(b, s, H)
    x = np.asarray(r, float) / Rh
    out = 1 + (e_peak(b, s, H, W) - 1) * g(x)
    out[x > X_MAX] = np.nan
    return out


def e_envelope(r, b, s, H, W):
    """Design envelope over E(r) — see the ENV constant for calibration."""
    Rh = r_half(b, s, H)
    x = np.asarray(r, float) / Rh
    ts = np.linspace(1.0 / ENV['S'], ENV['S'], 9)
    genv = np.max([g(x * t) for t in ts], axis=0)
    out = 1 + ENV['f'] * (e_peak(b, s, H, W) - 1) * genv
    out[x > X_MAX * ENV['S']] = np.nan
    return out


def _smooth(a, k=5):
    w = np.ones(k) / k
    s = np.convolve(a, w, mode='same')
    p = k // 2
    s[:p], s[-p:] = a[:p], a[-p:]
    return s


def _measured(config, npz_dir, dr):
    proc, ok = load_processed_data(npz_dir, config)
    if not ok:
        return None
    cfg = config_parser(config)
    prof = street_profile(proc, cfg, dr=dr, rmax=100.0, rmin=0.0)
    v = prof[prof.r >= exclude_radius(cfg)].reset_index(drop=True)
    v['E_s'] = _smooth(v.ratio.values)
    return v


def _find_matching_config(b, s, H, W, det, npz_dir):
    for p in sorted(Path(npz_dir).glob('config_*.npz')):
        c = config_parser(p.stem)
        if (c['bsize'], c['swidth'], c['height'], c['weight'], c['det']) == \
                (b, s, H, W, det):
            return p.stem
    return None


def main(config=None, *, b=None, s=None, H=None, W=None, det=None,
         dr=0.5, npz_dir=None, out_dir=None, save=True, write_csv=False,
         progress=None):
    say = progress or _say
    npz_dir = paths.resolve(npz_dir, paths.default_npz_dir(soft=True))

    if config is not None:
        cfg = config_parser(config)
        b, s, H, W, det = (cfg['bsize'], cfg['swidth'], cfg['height'],
                           cfg['weight'], cfg['det'])
    elif None in (b, s, H, W, det):
        raise ValueError('give a config, or all of b, s, H, W, det')
    else:
        config = _find_matching_config(b, s, H, W, det, npz_dir)
        if config:
            say(f'  geometry matches {config} — overlaying its measurement')

    Ep, Rh = e_peak(b, s, H, W), r_half(b, s, H)
    sq, Pi2 = b / (b + s), s / W ** (1 / 3)
    say(f'b={b:g} s={s:g} H={H:g} W={W:g} det{det}   '
        f'sqrt(rho)={sq:.3f}  Pi2={Pi2:.2f}  H/s={H / s:.2f}')
    say(f'  E_peak = {Ep:.2f}   R_half = {Rh:.1f} m   '
        f'(peak at ~{0.52 * Rh:.0f} m, back to free field at ~{1.6 * Rh:.0f} m)')
    if Ep < GATE:
        say(f'  GATE: E_peak < {GATE:g} — no strong local zone; '
            'the profile prediction below the gate is indicative only.')

    meas = _measured(config, npz_dir, dr) if config else None

    r = np.arange(0.5, min(X_MAX * ENV['S'] * Rh, 100.0), 0.5)
    pred = e_profile(r, b, s, H, W)
    env = e_envelope(r, b, s, H, W)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.axhline(1.0, color='0.4', lw=1)
    ax.axhline(GATE, color='0.6', lw=1, ls=':')
    ax.plot(r, env, color='tab:blue', lw=1.6, ls='--',
            label=f"design envelope (covers 95% of slices, f={ENV['f']:g}, "
                  f"S={ENV['S']:g})")
    ax.fill_between(r, 1.0, env, where=np.isfinite(env), color='tab:blue',
                    alpha=0.06, lw=0)
    ax.plot(r, pred, color='tab:blue', lw=2.2,
            label='best estimate:  1 + (E_peak−1)·g(r/R_half)')
    if meas is not None:
        ax.plot(meas.r, meas.ratio, color='0.75', lw=0.8, label='measured (raw slices)')
        ax.plot(meas.r, meas.E_s, color='tab:red', lw=1.8, label='measured (smoothed)')
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
    title = config if config else f'b{b:g}_s{s:g}_h{H:g}_w{W:g}_det{det}'
    verdict = 'STRONG local zone' if Ep >= GATE else 'no strong local zone'
    ax.set_title(f'{title}\nE_peak = {Ep:.2f} ({verdict}) · R_half = {Rh:.0f} m')
    ax.set_xlabel('distance along the street r [m]')
    ax.set_ylabel('E = P_urban / P_ff')
    ax.grid(alpha=0.25)
    ax.legend(fontsize=9)

    if meas is not None:
        # Score only where the MEASUREMENT is channelling (E >= FLOOR) and
        # inside the model's domain — slices with no channelling carry no
        # information about the channelling model and are excluded on both
        # sides of the comparison.
        common = meas[(meas.r <= r[-1]) & (meas.E_s >= FLOOR)]
        pk_m = meas[meas.r <= r[-1]].E_s.max()
        say(f'  measured E_peak = {pk_m:.2f}  (predicted {Ep:.2f}, '
            f'{100 * (Ep - pk_m) / pk_m:+.0f}%)')
        if len(common) >= 5:
            pr = np.interp(common.r, r, pred)
            err = 100 * np.nanmean(np.abs(pr - common.E_s) / common.E_s)
            say(f'  profile MAPE, channelling zone (E>={FLOOR:g}, '
                f'r<={r[-1]:.0f} m): {err:.1f}%')
            ax.text(0.99, 0.02, f'MAPE {err:.1f}% over the channelling zone',
                    transform=ax.transAxes, ha='right', fontsize=8, color='0.4')
        else:
            say(f'  measured profile never reaches E={FLOOR:g} — '
                'nothing to score the channelling model against')

    if not save:
        return fig
    out_dir = Path(paths.resolve(out_dir, paths.fig_dir('e_profile')))
    paths.ensure_dir(out_dir)
    png = out_dir / f'{title}_E.png'
    fig.savefig(png, dpi=150, bbox_inches='tight')
    plt.close(fig)
    say(f'  wrote {png}')
    if write_csv:
        df = pd.DataFrame({'r': r, 'E_pred': pred})
        if meas is not None:
            df['E_meas'] = np.interp(r, meas.r, meas.E_s, left=np.nan, right=np.nan)
        csv = out_dir / f'{title}_E.csv'
        df.to_csv(csv, index=False)
        say(f'  wrote {csv}')
    return png


def cli(argv=None):
    p = argparse.ArgumentParser(
        description='Predicted vs measured street channelling profile E(r).')
    p.add_argument('config', nargs='?', default=None,
                   help='Config number (58) or full name. Omit to give '
                        'geometry with --b --s --H --W --det instead.')
    p.add_argument('--b', type=float, help='building size [m]')
    p.add_argument('--s', type=float, help='street width [m]')
    p.add_argument('--H', type=float, help='building height [m]')
    p.add_argument('--W', type=float, help='charge weight [kg]')
    p.add_argument('--det', type=int, choices=[1, 2],
                   help='1 = mid-street, 2 = intersection')
    p.add_argument('--dr', type=float, default=0.5)
    p.add_argument('--npz-dir', default=None, dest='npz_dir')
    p.add_argument('--out-dir', default=None, dest='out_dir')
    p.add_argument('--csv', action='store_true', dest='write_csv')
    a = p.parse_args(argv)

    config = a.config
    if config is not None:
        npz_dir = paths.resolve(a.npz_dir, paths.default_npz_dir(soft=True))
        known = sorted(q.stem for q in Path(npz_dir).glob('config_*.npz'))
        rc = resolve_config(config, known)
        if rc is None:
            p.error(f'{config!r} matches no config in {npz_dir}')
        config = rc
    elif None in (a.b, a.s, a.H, a.W, a.det):
        p.error('give a config, or all of --b --s --H --W --det')

    return main(config, b=a.b, s=a.s, H=a.H, W=a.W, det=a.det, dr=a.dr,
                npz_dir=a.npz_dir, out_dir=a.out_dir, write_csv=a.write_csv)


if __name__ == '__main__':
    cli()
