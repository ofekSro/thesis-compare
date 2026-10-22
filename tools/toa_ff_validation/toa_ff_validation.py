"""Free-field arrival-time validation: Viper gauges vs UFC 3-340-02 Fig. 2-15.

Stage 2 of docs/ARRIVAL_TIME_INVERSION_PLAN.md. Reads the Viper free-field
reference runs data/Gauges/ff_<W>kg/<stage>/ and checks
  (a) collapse of the scaled arrival time tau = t_a / W^(1/3) over the five
      weights (Hopkinson-Cranz scaling inside Viper itself);
  (b) agreement with the UFC 3-340-02 Fig. 2-15 (hemispherical) ta curve.

Arrival definition (owner decision D40, docs/DECISIONS.md, revised 2026-10-19):
  t_5   = first crossing of ONSET (5%) of the gauge's global peak, linearly
          interpolated (as Cheinet et al. 2016). Early on a smeared front by
          about half its width, but the bias cancels in g = tau_urban/tau_ff
          (D41): median |dg| 0.35% vs mid-rise (D40 evidence).
  Urban gauges count only if their peak is >= P_MIN_URBAN (5 kPa); in free
  field P depends on Z only, so this is a fixed-Z cut. Not applied here: the
  free-field reference is clean and is kept whole.
Secondary, for sensitivity only:
  t_mid = mid-rise of the first front: crossing of 0.5 * p_first, p_first the
          first local peak after onset (in free field, the global peak);
  t_nz  = first sample with overpressure > 0 (numerical precursor).

Remap time-stamp correction (default on, --no-remap-correction to disable):
the next stage starts with the clock of the remap step (t_load) but with the
field of the last source step that is a multiple of guioutfreq_3d. Arrivals
in that stage are therefore late by t_load - TT(that step), cumulative over
remaps. The offset is read from status_echo.txt and <stage>.vip.bak, and
checked against an independent estimate from the gauge data (t*).

No pass/fail: the collapse was inspected and accepted by the owner; the
observed spread is the reference uncertainty band (docs/DECISIONS.md).
Output (regenerable, not of record): outputs/figures/toa_ff_validation/

Usage:
    python tools\\toa_ff_validation\\toa_ff_validation.py
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import h5py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from blastlib import paths

# Unit factors as in docs/audit/2026-09-27/scripts/kb_crosscheck.py:17-19
LB13 = 0.45359237 ** (1 / 3)
FT2M = 0.3048
Z_F = FT2M / LB13                 # ft/lb^(1/3) -> m/kg^(1/3)

STAGE_EDGES = (100.0, 250.0)      # take-box limits, plan §4
UFC_TA_KEY = 'ta, ms/lb^(1/3)'
SE_3D = re.compile(r'Step=\s*(\d+)\s+TT=\s*(\S+)\s+DT=\s*\S+\s+ET=')  # 3-D column is the one with ET=
OFFSET_CHECK_TOL = 1.5e-3         # s; log offset vs gauge-data estimate, warn above
P_MIN_URBAN = 5e3                 # Pa; urban gauge validity floor (D40), reported only here


def parse_grf(path):
    """Return {curve title: (n,2) array} from a DPlot GRF file.

    Copied from docs/audit/2026-09-27/scripts/kb_crosscheck.py:24-42.
    """
    curves, cur = {}, []
    for ln in open(path, errors='replace'):
        s = ln.strip()
        m = re.match(r'^([-\d.Ee+]+)\s+([-\d.Ee+]+)$', s)
        if m:
            cur.append((float(m.group(1)), float(m.group(2))))
            continue
        if re.match(r'^\d+$', s):
            continue
        if cur:
            a = np.array(cur)
            a = a[(a[:, 0] > 0) & (a[:, 1] > 0)]       # drop format-flag rows
            a = a[np.argsort(a[:, 0])]
            curves[s] = a
            cur = []
        if s.lower() == 'stop':
            break
    return curves


def ufc_tau(grf_path):
    """UFC Fig. 2-15 ta curve in SI: (Z [m/kg^(1/3)], tau [ms/kg^(1/3)])."""
    c = parse_grf(grf_path)[UFC_TA_KEY]
    # t/W_kg^(1/3) = t/(W_lb^(1/3) * LB13)
    return c[:, 0] * Z_F, c[:, 1] / LB13


def read_gauge_list(path):
    """Return DataFrame: id, requested x,y,z [m], actual xa,ya,za [m], label."""
    rows = []
    for ln in open(path, errors='replace'):
        t = ln.split()
        if len(t) < 10 or t[0] != '3d':
            continue
        rows.append({'id': int(t[1]),
                     'x': float(t[2]), 'y': float(t[3]), 'z': float(t[4]),
                     'xa': float(t[5]), 'ya': float(t[6]), 'za': float(t[7]),
                     'label': t[9]})
    return pd.DataFrame(rows)


def take_stage(x, z):
    """Stage that owns a gauge by the take-box rule (plan §4); 0 = on a boundary."""
    for k, edge in enumerate(STAGE_EDGES, start=1):
        if x == edge or z == edge:
            return 0
        if x < edge and z < edge:
            return k
    return 3


def first_crossing(t, p, level):
    """Time [s] of the first crossing of level [Pa], linearly interpolated."""
    i = np.argmax(p >= level)
    if i == 0:
        return t[0]                       # already above level at first sample
    return t[i - 1] + (level - p[i - 1]) * (t[i] - t[i - 1]) / (p[i] - p[i - 1])


def arrival_times(t, p, onset):
    """Arrival times [s] of one gauge: (t_5, t_mid, t_nz). NaN if no signal.

    t_5 is the D40 arrival (onset * global peak); t_mid and t_nz are for
    sensitivity (see module docstring).
    """
    peak = p.max()
    if not peak > 0:
        return np.nan, np.nan, np.nan
    i = np.argmax(p >= onset * peak)
    while i + 1 < len(p) and p[i + 1] >= p[i]:   # climb to the first local peak
        i += 1
    t_mid = first_crossing(t, p, 0.5 * p[i])
    return first_crossing(t, p, onset * peak), t_mid, t[np.argmax(p > 0)]


def read_status_echo(path):
    """3-D column of a Viper status_echo.txt: (step, TT [s]) arrays in file order."""
    steps, tts = [], []
    for ln in open(path, errors='replace'):
        m = SE_3D.search(ln)
        if m:
            steps.append(int(m.group(1)))
            tts.append(float(m.group(2)))
    return np.array(steps), np.array(tts)


def read_guioutfreq(bak_path):
    """guioutfreq_3d [steps] stored in a Viper <stage>.vip.bak (HDF5)."""
    with h5py.File(bak_path, 'r') as f:
        return int(np.ravel(f['vipermodel']['guioutfreq_3d'][()])[0])


def remap_offset_from_logs(src_dir, dst_dir, stage):
    """Clock offset [s] of remap stage -> stage+1, from status_echo and .vip.bak.

    t_load = TT of Step 0 before the last Step 1 in the target log (last attempt).
    The loaded field is that of the last source step that is a multiple of
    guioutfreq_3d at or before the remap step; offset = t_load - TT(that step).
    """
    d_steps, d_tt = read_status_echo(dst_dir / 'status_echo.txt')
    k1 = np.flatnonzero(d_steps == 1)[-1]
    if d_steps[k1 - 1] != 0:
        raise ValueError(f'{dst_dir}: no Step 0 line before last Step 1')
    t_load = d_tt[k1 - 1]

    s_steps, s_tt = read_status_echo(src_dir / 'status_echo.txt')
    hits = np.flatnonzero(np.abs(s_tt - t_load) < 5e-10)   # TT printed to 1e-9
    if hits.size == 0:
        raise ValueError(f'{src_dir}: no step with TT = {t_load:.9f}')
    k = hits[-1]
    step_remap = int(s_steps[k])
    freq = read_guioutfreq(src_dir / f'{stage}.vip.bak')
    step_field = (step_remap // freq) * freq
    back = np.flatnonzero(s_steps[:k + 1] == step_field)
    if back.size == 0:
        raise ValueError(f'{src_dir}: step {step_field} not in log')
    t_field = s_tt[back[-1]]
    return {'transition': f'{stage}->{stage + 1}', 'remap_step': step_remap,
            't_load': t_load, 'guioutfreq_3d': freq, 'field_step': step_field,
            't_field': t_field, 'offset': t_load - t_field}


def remap_offset_from_gauges(src_data, src_gl, dst_first_row, stage):
    """Independent offset estimate [s]: dst first row vs best-matching src row (t*).

    Uses FF gauges strictly inside the source-stage domain. Returns (offset, rel. error).
    """
    edge = STAGE_EDGES[stage - 1]
    ids = src_gl.loc[src_gl['label'].str.startswith('FF_') & (src_gl['x'] < edge)
                     & (src_gl['z'] < edge), 'id'].to_numpy()
    snap = dst_first_row[ids]
    err = np.sqrt(np.mean((src_data[:, ids] - snap) ** 2, axis=1)) / np.sqrt(np.mean(snap ** 2))
    i = int(np.argmin(err))
    return dst_first_row[0] - src_data[i, 0], float(err[i])


def process_weight(ff_dir, W, onset, correct_remap, progress):
    """Rows (one per FF gauge) and remap-offset rows for one free-field run of W [kg]."""
    gls, datas = {}, {}
    for stage in (1, 2, 3):
        sdir = ff_dir / str(stage)
        gls[stage] = read_gauge_list(sdir / 'gauge_list_3d_actual.txt')
        datas[stage] = np.loadtxt(sdir / 'viper3d_th_overpressure.txt')

    # clock shift of each stage relative to the physical field, cumulative
    shift = {1: 0.0, 2: 0.0, 3: 0.0}
    off_rows = []
    for stage in (1, 2):
        o = remap_offset_from_logs(ff_dir / str(stage), ff_dir / str(stage + 1), stage)
        est, err = remap_offset_from_gauges(datas[stage], gls[stage], datas[stage + 1][0], stage)
        o.update({'W': W, 'offset_gauges': est, 'match_err': err})
        off_rows.append(o)
        if abs(o['offset'] - est) > OFFSET_CHECK_TOL:
            progress(f'  WARNING W={W} {o["transition"]}: log offset {1e3 * o["offset"]:.2f} ms '
                     f'vs gauge estimate {1e3 * est:.2f} ms')
        for later in range(stage + 1, 4):
            shift[later] += o['offset']

    rows, dropped = [], []
    for stage in (1, 2, 3):
        gl = gls[stage]
        gl = gl[gl['label'].str.startswith('FF_')]
        gl = gl.assign(stage_own=[take_stage(x, z) for x, z in zip(gl['x'], gl['z'])])
        if stage == 1:
            dropped += list(gl.loc[gl['stage_own'] == 0, 'label'])
        t = datas[stage][:, 0]
        dt_fix = shift[stage] if correct_remap else 0.0
        for _, g in gl[gl['stage_own'] == stage].iterrows():
            p = datas[stage][:, g['id']]          # column 0 is time, gauge ids start at 1
            t_5, t_mid, t_nz = arrival_times(t, p, onset)
            # actual cell-centre position of this stage (clamped copies excluded)
            R = float(np.sqrt(g['xa'] ** 2 + g['ya'] ** 2 + g['za'] ** 2))
            rows.append({'W': W, 'stage': stage, 'label': g['label'],
                         'Z_label': int(re.match(r'FF_Z(\d+)_', g['label']).group(1)),
                         'x': g['xa'], 'y': g['ya'], 'z': g['za'], 'R': R,
                         'Z': R / W ** (1 / 3), 'p_max_kPa': p.max() / 1e3,
                         'remap_offset': shift[stage],
                         't_mid_raw': t_mid, 't_5_raw': t_5, 't_nz_raw': t_nz,
                         't_mid': t_mid - dt_fix, 't_5': t_5 - dt_fix, 't_nz': t_nz - dt_fix})
    if dropped:
        progress(f'  W={W}: boundary gauges dropped: {", ".join(dropped)}')
    return rows, off_rows


def plot(df, z_ufc, tau_ufc, out_png, corrected):
    """Two panels: tau vs Z with UFC curve; Viper/UFC ratio vs Z (raw in grey)."""
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 9), sharex=True,
                                 gridspec_kw={'height_ratios': [2, 1]})
    a1.plot(z_ufc, tau_ufc, 'k-', lw=1.5, label='UFC 3-340-02 Fig. 2-15')
    colors = plt.cm.viridis(np.linspace(0, 0.9, df['W'].nunique()))
    for (W, g), c in zip(df.groupby('W'), colors):
        a1.plot(g['Z'], g['tau_5'], 'o', color=c, ms=5, label=f'Viper W={W} kg (5% of peak)')
        a1.plot(g['Z'], g['tau_mid'], 'o', mfc='none', color=c, ms=7, alpha=0.6)
        if corrected:
            a2.plot(g['Z'], g['ratio_5_raw'], 'o', color='0.8', ms=3, zorder=1)
        a2.plot(g['Z'], g['ratio_5'], 'o-', color=c, ms=4, lw=0.8, zorder=2)
    a1.plot([], [], 'o', mfc='none', color='gray', label='open: mid-rise')
    if corrected:
        a2.plot([], [], 'o', color='0.8', ms=3, label='before remap correction')
        a2.legend(fontsize=8)
    tag = 'remap-corrected' if corrected else 'no remap correction'
    a1.set(xscale='log', yscale='log', ylabel=r'$\tau = t_a/W^{1/3}$ [ms/kg$^{1/3}$]',
           title=f'Free-field arrival time: Viper vs UFC ({tag})')
    a1.grid(True, which='both', alpha=0.3)
    a1.legend(fontsize=8)
    a2.axhline(1.0, color='k', lw=1)
    a2.set(xscale='log', xlabel=r'$Z = R/W^{1/3}$ [m/kg$^{1/3}$]',
           ylabel=r'$\tau_{Viper,5\%}/\tau_{UFC}$')
    a2.grid(True, which='both', alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main(*, gauges_dir=None, grf_path=None, out_dir=None, onset=0.05,
         correct_remap=True, progress=print):
    """Validate free-field tau(Z) of all ff_<W>kg runs; return output CSV path or None."""
    gauges_dir = Path(paths.resolve(gauges_dir, paths.DATA_DIR / 'Gauges'))
    grf_path = paths.resolve(grf_path, paths.PROJECT_ROOT / 'docs' / 'references' / '02_015.GRF')
    out_dir = Path(paths.resolve(out_dir, paths.FIGURES_DIR / 'toa_ff_validation'))
    paths.ensure_dir(out_dir)

    ff_dirs = sorted((d for d in gauges_dir.glob('ff_*kg') if d.is_dir()),
                     key=lambda d: int(re.match(r'ff_(\d+)kg', d.name).group(1)))
    if not ff_dirs:
        progress(f'ERROR: no ff_<W>kg folders in {gauges_dir}')
        return None

    rows, off_rows = [], []
    for d in ff_dirs:
        W = int(re.match(r'ff_(\d+)kg', d.name).group(1))
        progress(f'Reading {d.name} ...')
        r, o = process_weight(d, W, onset, correct_remap, progress)
        rows += r
        off_rows += o
    df = pd.DataFrame(rows).sort_values(['W', 'Z']).reset_index(drop=True)
    offs = pd.DataFrame(off_rows)

    cbrt = df['W'] ** (1 / 3)
    for k in ('mid', '5', 'nz', 'mid_raw', '5_raw', 'nz_raw'):
        df[f'tau_{k}'] = 1e3 * df[f't_{k}'] / cbrt          # ms/kg^(1/3)
    z_ufc, tau_ufc = ufc_tau(grf_path)
    inside = (df['Z'] >= z_ufc[0]) & (df['Z'] <= z_ufc[-1])
    df['tau_UFC'] = np.where(inside, np.exp(np.interp(np.log(df['Z']), np.log(z_ufc),
                                                      np.log(tau_ufc))), np.nan)
    for k in ('5', 'mid', 'nz', '5_raw'):
        df[f'ratio_{k}'] = df[f'tau_{k}'] / df['tau_UFC']

    out_csv = out_dir / 'toa_ff_validation.csv'
    out_png = out_dir / 'toa_ff_validation.png'
    out_off = out_dir / 'toa_ff_remap_offsets.csv'
    df.to_csv(out_csv, index=False)
    offs.to_csv(out_off, index=False)
    plot(df, z_ufc, tau_ufc, out_png, correct_remap)

    # --- summary (no pass/fail; spread is the accepted uncertainty band)
    progress('\nRemap offsets (log = status_echo + guioutfreq_3d; gauges = t* estimate):')
    for _, o in offs.iterrows():
        progress(f'  W={o["W"]:5d} {o["transition"]}: remap step {o["remap_step"]}, '
                 f'guioutfreq {o["guioutfreq_3d"]}, field step {o["field_step"]}, '
                 f'offset log {1e3 * o["offset"]:6.2f} ms, gauges {1e3 * o["offset_gauges"]:6.2f} ms '
                 f'(match err {o["match_err"]:.3f})')
    progress(f'Remap correction applied: {correct_remap}')
    progress(f'\nUFC ta curve: Z = {z_ufc[0]:.3f}..{z_ufc[-1]:.2f} m/kg^(1/3)')
    progress(f'NaN arrivals: t_5 {df["t_5"].isna().sum()}, t_mid {df["t_mid"].isna().sum()}, '
             f't_nz {df["t_nz"].isna().sum()}')
    progress(f'|Z - Z_label| max = {(df["Z"] - df["Z_label"]).abs().max():.3f}')
    low = df[df['p_max_kPa'] < P_MIN_URBAN / 1e3]
    progress(f'Gauges below the urban floor {P_MIN_URBAN / 1e3:.0f} kPa (kept in the reference): '
             f'{len(low)}, from Z = {low["Z"].min():.2f}' if len(low) else 'No gauge below the urban floor')
    progress('\nPer weight (5% definition, vs UFC):')
    for W, g in df.groupby('W'):
        r = (g['ratio_5'] - 1).abs()
        smear = 1e3 * (g['t_mid'] - g['t_5'])
        progress(f'  W={W:5d}: n={len(g):2d}, Z={g["Z"].min():.2f}..{g["Z"].max():.2f}, '
                 f'|ratio-1| median {r.median():.3f} max {r.max():.3f}, '
                 f'front width t_mid-t_5 median {smear.median():.2f} ms max {smear.max():.2f} ms')
    spread = df.groupby('Z_label')['tau_5'].agg(lambda s: s.max() / s.min() - 1)
    progress('\nCollapse spread across weights, max/min(tau_5) - 1, per nominal Z:')
    progress('  ' + ', '.join(f'Z{z}:{v:.3f}' for z, v in spread.items()))
    tail = df[df['Z_label'] >= 20].groupby('W').apply(
        lambda g: np.polyfit(g['Z'], g['tau_5'], 1)[0], include_groups=False)
    progress('\nTail slope dtau/dZ for Z>=20 [ms per m/kg^(1/3)] (1/c0 = 2.94 at 340 m/s):')
    progress('  ' + ', '.join(f'W={W}:{s:.3f}' for W, s in tail.items()))
    progress(f'\nSaved: {out_csv}\nSaved: {out_off}\nSaved: {out_png}')
    return out_csv


def cli(argv=None):
    p = argparse.ArgumentParser(description='Validate free-field arrival time vs UFC.')
    p.add_argument('--gauges-dir', default=None, help='Folder holding ff_<W>kg/.')
    p.add_argument('--grf', default=None, help='UFC Fig. 2-15 GRF file.')
    p.add_argument('--out-dir', default=None, help='Output folder.')
    p.add_argument('--onset', type=float, default=0.05,
                   help='Front detection level as fraction of global peak (default 0.05).')
    p.add_argument('--no-remap-correction', action='store_true',
                   help='Do not subtract the remap clock offset from stage 2-3 arrivals.')
    args = p.parse_args(argv)
    return main(gauges_dir=args.gauges_dir, grf_path=args.grf, out_dir=args.out_dir,
                onset=args.onset, correct_remap=not args.no_remap_correction)


if __name__ == '__main__':
    cli()
