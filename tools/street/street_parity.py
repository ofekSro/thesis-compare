"""The street-suite parity harness: rebuild everything, compare to pinned.

Regenerates every artefact of the street-channelling suite into
outputs/check_results/street_parity/ (a subdirectory git ignores, so
scratch runs never dirty the tree) and compares against the pinned
reference files committed in snapshot bf8eefe:

    street_anchors.csv            rel 1e-12 (pinned CSVs sit up to 1 ulp
    master_curve_g.csv            off recomputation on this machine —
    e_profile_validation_88.csv   never compare bit-exact)

plus the constants (full precision, rel 1e-9 — curve_fit is deterministic
per scipy version, so version drift degrades this check before it touches
the optimizer-free CSV gates), the headline locks (MAPE stats, gate
confusion, true envelope statistics), the Q1 no-op sweep, the E_peak
verification refit, and the figure-set inventories. Writes
outputs/check_results/street_parity_report.md (un-ignored, committable)
and exits 0 only when every gate passes.

This harness is permanent — it is the regression net for any future
refactor of blastlib.street, not a one-time migration script.

Usage:
    python tools\\street\\street_parity.py
    python tools\\street\\street_parity.py --skip-figures     # CSV gates only
"""

import argparse
import platform
import subprocess
import sys
import warnings
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / 'tools' / 'validate_migration'))

# The raw-store expansion divides pre-mask reference fields; the zeros it
# warns about are masked two lines later. 96 loads x 4 warnings is pure
# noise in a batch log.
warnings.filterwarnings('ignore', category=RuntimeWarning,
                        module=r'blastlib\.processing\.grids')

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
import scipy

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.io.npz_store import load_processed_data
from blastlib.progress import say as _say
from blastlib.street import conventions, figures, fitting, model, validation
from blastlib.street.anchors import measure_all
from blastlib.street.constants import FLOOR, G, RHALF
from blastlib.street.strip import street_profile
from compare_outputs import compare_csv

# Full-precision fit results measured in the pinned environment (Python
# 3.12.10, numpy 2.4.4, scipy 1.17.1). A scipy upgrade may move the last
# digits; the CSV gates (optimizer-free) stay decisive if this ever fires.
EXPECT_G = dict(A=59.88434103668478, p=2.483758865788831, q=4.746669040697642)
EXPECT_RHALF = dict(C=1.2849835992920906, p_sq=-1.0700379830256466,
                    p_hs=0.2721321919965368)
EXPECT_IQR = dict(slope=0.2218, cross=0.1894)
EXPECT_HEADLINE = dict(mean=9.7364, median=8.50, p90=17.34, max=31.0)
EXPECT_ENVELOPE = dict(coverage=96.34, exceed_gt_015=0.73, worst=0.723,
                       worst_cfg='config_26', n_slices=10531)
EXPECT_GATE = dict(n_correct=92, misses={'config_67', 'config_70'},
                   false_alarms={'config_78', 'config_80'})


def _git_head():
    try:
        return subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                              capture_output=True, text=True,
                              cwd=paths.PROJECT_ROOT).stdout.strip()
    except OSError:
        return 'unknown'


def _rel_ok(got, want, rtol):
    return abs(got - want) <= rtol * abs(want)


def main(*, npz_dir=None, skip_figures=False, progress=None):
    say = progress or _say
    t0 = datetime.now()
    out_root = paths.ensure_dir(paths.CHECK_RESULTS_DIR / 'street_parity')
    fig_root = paths.ensure_dir(out_root / 'figures')
    gates = {}          # letter -> (bool, detail)
    rows_csv = []       # (artefact, status, detail)

    # ---- B: anchors ------------------------------------------------------
    say('== gate B: anchors ==')
    rebuilt_anchors = out_root / 'street_anchors.csv'
    measure_all(npz_dir=npz_dir, out_csv=rebuilt_anchors, progress=progress)
    st, detail = compare_csv(paths.CHECK_RESULTS_DIR / 'street_anchors.csv',
                             rebuilt_anchors, rtol=1e-12, atol=1e-12)
    rows_csv.append(('street_anchors.csv', st, detail))
    anchors = pd.read_csv(rebuilt_anchors)
    n_nan = int(anchors.L_decay.isna().sum())
    gates['B'] = (st == 'PASS' and n_nan == 21,
                  f'{st}; {detail}; L_decay NaN {n_nan}/96 (want 21)')

    # ---- Q1 sweep --------------------------------------------------------
    say('== Q1 sweep: strict vs inclusive exclusion cut ==')
    ndir = paths.resolve(npz_dir, paths.default_npz_dir(soft=True))
    q1_diff = []
    for name in sorted(p.stem for p in Path(ndir).glob('config_*.npz')):
        proc, ok = load_processed_data(ndir, name)
        if not ok:
            continue
        cfg = config_parser(name)
        prof = street_profile(proc, cfg, dr=0.5)
        a = conventions.cut_exclusion(prof, cfg, inclusive=False)
        b = conventions.cut_exclusion(prof, cfg, inclusive=True)
        if len(a) != len(b):
            q1_diff.append(name)
    gates['Q1'] = (not q1_diff,
                   f'{len(q1_diff)} configs differ ({q1_diff or "none"}) — '
                   'the > vs >= split is empirically a no-op')
    say(f'  {gates["Q1"][1]}')

    # ---- C: fit (on the pinned anchors — stage isolation) ---------------
    say('== gate C: fit ==')
    pinned_anchors = pd.read_csv(paths.CHECK_RESULTS_DIR
                                 / 'street_anchors.csv')
    x, y, used = fitting.collect_cloud(pinned_anchors, npz_dir,
                                       'R_half_slope', progress)
    xc, yc, _u = fitting.collect_cloud(pinned_anchors, npz_dir,
                                       'R_half_cross', progress)
    gfit = fitting.fit_master_curve(x, y)
    rh = fitting.fit_r_half(pinned_anchors)
    iqr_new, iqr_old = fitting.collapse_iqr(x, y), fitting.collapse_iqr(xc, yc)
    mc = fitting.master_curve_table(x, y)
    mc_csv = out_root / 'master_curve_g.csv'
    mc.to_csv(mc_csv, index=False)
    st, detail = compare_csv(paths.CHECK_RESULTS_DIR / 'master_curve_g.csv',
                             mc_csv, rtol=1e-12, atol=1e-12)
    rows_csv.append(('master_curve_g.csv', st, detail))
    c_checks = [
        st == 'PASS',
        len(used) == 75 and len(x) == 11545,
        all(_rel_ok(gfit[k], EXPECT_G[k], 1e-9) for k in EXPECT_G),
        all(_rel_ok(rh[k], EXPECT_RHALF[k], 1e-9) for k in EXPECT_RHALF),
        dict(A=round(gfit['A'], 1), p=round(gfit['p'], 2),
             q=round(gfit['q'], 2)) == G,
        dict(C=round(rh['C'], 2), p_sq=round(rh['p_sq'], 2),
             p_hs=round(rh['p_hs'], 2)) == RHALF,
        abs(iqr_new - EXPECT_IQR['slope']) < 5e-4,
        abs(iqr_old - EXPECT_IQR['cross']) < 5e-4,
    ]
    gates['C'] = (all(c_checks),
                  f'{st}; cloud {len(used)}/{len(x)} (want 75/11545); '
                  f"A={gfit['A']:.6f} p={gfit['p']:.6f} q={gfit['q']:.6f}; "
                  f"C={rh['C']:.6f} p_sq={rh['p_sq']:.6f} "
                  f"p_hs={rh['p_hs']:.6f}; IQR {iqr_new:.4f}/{iqr_old:.4f}; "
                  f'checks {c_checks}')

    # ---- D: model formula vs pinned validation column -------------------
    say('== gate D: E_peak formula ==')
    pinned_val = pd.read_csv(paths.CHECK_RESULTS_DIR
                             / 'e_profile_validation_88.csv')
    pred = np.array([model.e_peak(r.b, r.s, r.H, r.W)
                     for r in pinned_val.itertuples()])
    n_mismatch = int(np.sum(np.round(pred, 3)
                            != pinned_val.E_peak_pred.values))
    gates['D'] = (n_mismatch == 0,
                  f'{n_mismatch}/88 3-dp mismatches '
                  f'(max |formula-csv| {np.max(np.abs(pred - pinned_val.E_peak_pred.values)):.5f})')
    say(f'  {gates["D"][1]}')

    # ---- E/F: validation, chained from the REBUILT anchors --------------
    # The rebuilt anchors already compared bit-identical to the pinned file
    # (gate B), so running fit+validate off them IS the end-to-end chain.
    say('== gates E+F: validation (chained) ==')
    val_csv = out_root / 'e_profile_validation_88.csv'
    val = validation.validate_all(rebuilt_anchors, npz_dir,
                                  out_csv=val_csv, progress=progress)
    st, detail = compare_csv(paths.CHECK_RESULTS_DIR
                             / 'e_profile_validation_88.csv',
                             val_csv, rtol=1e-12, atol=1e-12)
    rows_csv.append(('e_profile_validation_88.csv', st, detail))
    members = {c for c in anchors[anchors.E_peak >= FLOOR].cfg}
    gates['E'] = (st == 'PASS' and set(val.cfg) == members
                  and len(val) == 88,
                  f'{st}; {detail}; membership {len(val)}/88')
    gates['F'] = (gates['B'][0] and gates['C'][0] and gates['E'][0],
                  'chain rebuilt-anchors -> fit -> validate, every link '
                  'compared against its pinned artefact')

    # ---- H: headline locks ----------------------------------------------
    say('== gate H: headline locks ==')
    hs = validation.headline_stats(val)
    _gt, gsum = validation.gate_table(anchors)
    env = validation.envelope_stats(rebuilt_anchors, npz_dir,
                                    progress=progress)
    h_checks = [
        abs(hs['mean'] - EXPECT_HEADLINE['mean']) < 0.005,
        abs(hs['median'] - EXPECT_HEADLINE['median']) < 0.005,
        abs(hs['p90'] - EXPECT_HEADLINE['p90']) < 0.01,
        hs['max'] == EXPECT_HEADLINE['max'],
        gsum['n_correct'] == EXPECT_GATE['n_correct'],
        {c.split('_det')[0] for c in gsum['misses']}
        == EXPECT_GATE['misses'],
        {c.split('_det')[0] for c in gsum['false_alarms']}
        == EXPECT_GATE['false_alarms'],
        abs(env['coverage'] - EXPECT_ENVELOPE['coverage']) < 0.05,
        abs(env['exceed_gt_015'] - EXPECT_ENVELOPE['exceed_gt_015']) < 0.05,
        abs(env['worst_exceed'] - EXPECT_ENVELOPE['worst']) < 0.002,
        env['worst_cfg'].startswith(EXPECT_ENVELOPE['worst_cfg']),
        env['n_slices'] == EXPECT_ENVELOPE['n_slices'],
    ]
    gates['H'] = (all(h_checks),
                  f"MAPE {hs['mean']:.4f}/{hs['median']:.2f}/{hs['p90']:.2f}"
                  f"/{hs['max']:.1f}; gate {gsum['n_correct']}/96; envelope "
                  f"{env['coverage']:.2f}%/{env['exceed_gt_015']:.2f}%/"
                  f"{env['worst_exceed']:.3f}@{env['worst_cfg']}; "
                  f'checks {h_checks}')

    # ---- E_peak verification refit (report material, never a gate) ------
    say('== E_peak verification refit ==')
    ep_fit = fitting.fit_e_peak(pinned_anchors)
    ep_logo = fitting.logo_e_peak(pinned_anchors)
    say(f"  refit {' '.join(f'{k}={v:.4g}' for k, v in ep_fit.items())}; "
        f"LOGO {ep_logo['mape']:.2f}% over {ep_logo['n_families']} families")

    # ---- G: figure inventories ------------------------------------------
    if skip_figures:
        gates['G'] = (True, 'skipped by flag (structural gate not run)')
    else:
        say('== gate G: figures ==')
        figures.collapse_figure(x, y,
                                dict(A=gfit['A'], p=gfit['p'], q=gfit['q']),
                                mc, iqr_new, iqr_old, len(used),
                                out_dir=fig_root, progress=progress)
        figures.all88_figures(rebuilt_anchors, npz_dir, fig_root,
                              progress=progress)
        figures.envelope_corner_figures(npz_dir, fig_root, progress=progress)
        figures.pressure_check_figures(
            npz_dir=npz_dir, out_dir=paths.ensure_dir(
                fig_root / 'pressure_check'), progress=progress)
        expect_top = {f'{c}_E.png' for c in members}
        got_top = {p.name for p in fig_root.glob('*_E.png')}
        got_88 = {p.name for p in (fig_root / 'all88').glob('*.png')}
        got_env = {p.name for p in (fig_root / 'env').glob('*.png')}
        got_pc = {p.name for p in (fig_root / 'pressure_check').glob('*.png')}
        g_checks = [
            got_top == expect_top,
            (fig_root / 'master_curve_collapse.png').exists(),
            got_88 == expect_top | {'_contact_sheet.png'},
            got_env == {f'{c}_E.png' for c in figures.ENV_CORNERS}
            | {'_sheet.png'},
            got_pc == {f'{c}_P_and_E.png' for c in figures.PRESSURE_CHECK},
        ]
        gates['G'] = (all(g_checks),
                      f'top {len(got_top)}/88, all88 {len(got_88)}/89, '
                      f'env {len(got_env)}/5, pressure_check '
                      f'{len(got_pc)}/10; checks {g_checks}')

    # ---- report ----------------------------------------------------------
    ok = all(v[0] for v in gates.values())
    report = paths.CHECK_RESULTS_DIR / 'street_parity_report.md'
    with open(report, 'w', encoding='utf-8') as f:
        f.write('# Street-suite parity report\n\n')
        f.write(f'- date: {t0:%Y-%m-%d %H:%M}\n')
        f.write('- reference snapshot: bf8eefe '
                '(pre-rebuild pinned artefacts)\n')
        f.write(f'- rebuild HEAD: {_git_head()}\n')
        f.write(f'- environment: Python {platform.python_version()}, '
                f'numpy {np.__version__}, scipy {scipy.__version__}, '
                f'pandas {pd.__version__}\n')
        f.write(f'- verdict: {"PASS" if ok else "FAIL"}\n\n')
        f.write('## T1 — artefact parity (rtol=1e-12, atol=1e-12)\n\n')
        f.write('| artefact | status | detail |\n|---|---|---|\n')
        for name, st, detail in rows_csv:
            f.write(f'| {name} | {st} | {detail} |\n')
        f.write('\n## T2 — constants (full precision vs pinned)\n\n')
        f.write('| constant | refit | pinned expectation | shipped rounding '
                '|\n|---|---|---|---|\n')
        for k in ('A', 'p', 'q'):
            f.write(f'| G.{k} | {gfit[k]!r} | {EXPECT_G[k]!r} | {G[k]} |\n')
        for k in ('C', 'p_sq', 'p_hs'):
            f.write(f'| RHALF.{k} | {rh[k]!r} | {EXPECT_RHALF[k]!r} '
                    f'| {RHALF[k]} |\n')
        f.write('| EPK (verification only) | '
                + ' '.join(f'{k}={v:.4g}' for k, v in ep_fit.items()
                           if k not in ('mape', 'n'))
                + f" (mape {ep_fit['mape']:.2f}%) | pinned 2.69/1.81/-0.50/"
                  f"4.56/7.07 stay canonical | LOGO {ep_logo['mape']:.2f}% "
                  f"over {ep_logo['n_families']} (det,b,s,H) families; the "
                  'published 6.7%/36 used the lost fitter and a slightly '
                  'different family roster |\n')
        f.write('\n## T3 — headline locks\n\n')
        f.write(f"- profile MAPE (88): mean {hs['mean']:.4f}, median "
                f"{hs['median']:.2f}, p90 {hs['p90']:.2f}, max "
                f"{hs['max']:.1f} [%]\n")
        f.write(f"- gate: {gsum['n_correct']}/96 correct; misses "
                f"{sorted(gsum['misses'])}; false alarms "
                f"{sorted(gsum['false_alarms'])}\n")
        f.write(f"- envelope (in-sample, 88): coverage "
                f"{env['coverage']:.2f}%, >0.15 exceedance "
                f"{env['exceed_gt_015']:.2f}%, mean overprediction "
                f"{env['mean_overpred']:.1f}%, worst "
                f"{env['worst_exceed']:.3f} at {env['worst_cfg']} "
                f"({env['n_slices']} slices)\n")
        f.write(f"- collapse IQR: slope {iqr_new:.4f}, crossing "
                f"{iqr_old:.4f}; cloud 75 profiles / 11,545 points\n")
        f.write('\n## T4 — figure inventories\n\n')
        f.write(f"- {gates['G'][1]}\n")
        f.write('- pixel provenance: three sets had no surviving writer; '
                'formats reconstructed from the shipped PNGs (structural '
                'parity only, by design)\n')
        f.write('\n## Corrected stale claims (doc superseded by '
                'measurement)\n\n')
        f.write('| claim | was documented | measured now |\n|---|---|---|\n')
        f.write('| envelope coverage | 95.0% | 96.34% |\n')
        f.write('| slices exceeding by >0.15 | 1.5% | 0.73% |\n')
        f.write('| mean overprediction | 24% | 27.2% |\n')
        f.write('| largest exceedance | 0.96 at config_03 | 0.723 at '
                'config_26 |\n')
        f.write('| gate false alarms | zero | config_78, config_80 '
                '(conservative direction) |\n')
        f.write('| g(1) | 0.48 | 0.518 |\n')
        f.write(f'\n- Q1 sweep: {gates["Q1"][1]}\n')
        f.write('\n## Sign-off\n\n')
        for k in sorted(gates):
            st, detail = gates[k]
            f.write(f'- [{"x" if st else " "}] gate {k}: {detail}\n')
        f.write('\n(gate A — strip golden rows — lives in '
                'tests/test_street_strip.py)\n')
    say(f'wrote {report}')
    for k in sorted(gates):
        say(f'  gate {k}: {"PASS" if gates[k][0] else "FAIL"}')
    say(f'PARITY: {"PASS" if ok else "FAIL"}  '
        f'({(datetime.now() - t0).total_seconds():.0f} s)')
    return 0 if ok else 1


def cli(argv=None):
    p = argparse.ArgumentParser(
        description='Rebuild every street-suite artefact and compare '
                    'against the pinned reference.')
    p.add_argument('--npz-dir', default=None, dest='npz_dir')
    p.add_argument('--skip-figures', action='store_true',
                   help='CSV and lock gates only (no figure rendering)')
    a = p.parse_args(argv)
    return main(npz_dir=a.npz_dir, skip_figures=a.skip_figures)


if __name__ == '__main__':
    sys.exit(cli())
