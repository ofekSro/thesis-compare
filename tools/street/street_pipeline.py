"""The street-channelling batch pipeline: anchors -> fit -> validate -> figures.

One entry point for everything blastlib.street produces in batch:

  anchors    measure the 96-config anchor table -> street_anchors.csv
  fit        refit g(x) + R_half from the anchors, write master_curve_g.csv
             and the collapse figure, and report the constants next to the
             shipped rounding
  validate   score the closed-form model on the 88 -> e_profile_validation_88
             .csv, plus the gate table and true envelope statistics
  figures    the per-config panel sets (top level + all88/ + env/ +
             pressure_check/)
  all        the chain, in that order

Non-default dr / window fractions are stamped into the CSV filenames
(street_anchors_dr2.csv, ...) so exploratory runs can never overwrite the
pinned production tables — the filename-identity rule of this repo.

Usage:
    python tools\\street\\street_pipeline.py
    python tools\\street\\street_pipeline.py --stage anchors --dr 2.0
    python tools\\street\\street_pipeline.py --stage validate
"""

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # project root

# The raw-store expansion divides pre-mask reference fields; the zeros it
# warns about are masked two lines later. 96 loads x 4 warnings is pure
# noise in a batch log.
warnings.filterwarnings('ignore', category=RuntimeWarning,
                        module=r'blastlib\.processing\.grids')

import matplotlib
matplotlib.use('Agg')

import pandas as pd

from blastlib import paths
from blastlib.progress import say as _say
from blastlib.street import figures, fitting, validation
from blastlib.street.anchors import measure_all
from blastlib.street.constants import G, HI_FRAC, LO_FRAC, RHALF

STAGES = ('anchors', 'fit', 'validate', 'figures', 'all')


def _tag(dr, hi_frac, lo_frac):
    """Filename suffix for non-default measurement parameters."""
    parts = []
    if dr != 0.5:
        parts.append(f'dr{dr:g}')
    if (hi_frac, lo_frac) != (HI_FRAC, LO_FRAC):
        parts.append(f'hi{hi_frac:g}_lo{lo_frac:g}')
    return ('_' + '_'.join(parts)) if parts else ''


def main(*, stage='all', npz_dir=None, dr=0.5, hi_frac=HI_FRAC,
         lo_frac=LO_FRAC, anchors_csv=None, out_dir=None, check_dir=None,
         progress=None):
    """Run one stage or the whole chain. Returns a dict of artefact paths.

    anchors_csv overrides which anchor table the fit/validate/figures
    stages read (default: the one this run's parameters would write).
    out_dir overrides the figure root (default outputs/figures/e_profile);
    check_dir the CSV root (default outputs/check_results).
    """
    say = progress or _say
    if stage not in STAGES:
        raise ValueError(f'stage must be one of {STAGES}')
    check_dir = paths.ensure_dir(paths.resolve(check_dir,
                                               paths.CHECK_RESULTS_DIR))
    tag = _tag(dr, hi_frac, lo_frac)
    anchors_out = check_dir / f'street_anchors{tag}.csv'
    out = dict(tag=tag)

    if stage in ('anchors', 'all'):
        say(f'== anchors ==')
        measure_all(npz_dir=npz_dir, dr=dr, hi_frac=hi_frac,
                    lo_frac=lo_frac, out_csv=anchors_out, progress=progress)
        out['anchors_csv'] = anchors_out

    anchors_path = Path(paths.resolve(anchors_csv, anchors_out))
    if stage in ('fit', 'validate', 'figures', 'all') \
            and not anchors_path.exists():
        raise FileNotFoundError(
            f'{anchors_path} — run the anchors stage first (or pass '
            'anchors_csv)')

    if stage in ('fit', 'all'):
        say(f'== fit (anchors: {anchors_path.name}) ==')
        anchors = pd.read_csv(anchors_path)
        say('pooling profiles under the slope-fit R_half:')
        x, y, used = fitting.collect_cloud(anchors, npz_dir,
                                           'R_half_slope', progress)
        iqr_new = fitting.collapse_iqr(x, y)
        say('pooling under the legacy crossing R_half (comparison):')
        xc, yc, _u = fitting.collect_cloud(anchors, npz_dir,
                                           'R_half_cross', progress)
        iqr_old = fitting.collapse_iqr(xc, yc)
        say(f'collapse quality (median per-bin IQR): '
            f'crossing {iqr_old:.3f}  ->  slope {iqr_new:.3f}')
        gfit = fitting.fit_master_curve(x, y)
        say(f"g refit: A={gfit['A']:.1f}  p={gfit['p']:.2f}  "
            f"q={gfit['q']:.2f}   rms {gfit['rms']:.3f}   "
            f"(shipped {G['A']:g}/{G['p']:g}/{G['q']:g})")
        rh = fitting.fit_r_half(anchors)
        say(f"R_half refit (n={rh['n']}): C={rh['C']:.2f}  "
            f"sqrt(rho)^{rh['p_sq']:.2f}  (H/s)^{rh['p_hs']:.2f}   "
            f"MAPE {rh['mape']:.1f}%   (shipped {RHALF['C']:g}/"
            f"{RHALF['p_sq']:g}/{RHALF['p_hs']:g})")
        mc = fitting.master_curve_table(x, y)
        mc_csv = check_dir / f'master_curve_g{tag}.csv'
        mc.to_csv(mc_csv, index=False)
        say(f'wrote {mc_csv}')
        figures.collapse_figure(x, y, gfit, mc, iqr_new, iqr_old,
                                len(used), out_dir=out_dir, progress=progress)
        out.update(master_curve_csv=mc_csv, g_fit=gfit, r_half_fit=rh,
                   iqr_new=iqr_new, iqr_old=iqr_old)

    if stage in ('validate', 'all'):
        say(f'== validate (anchors: {anchors_path.name}) ==')
        val_csv = check_dir / f'e_profile_validation_88{tag}.csv'
        val = validation.validate_all(anchors_path, npz_dir,
                                      out_csv=val_csv, progress=progress)
        hs = validation.headline_stats(val)
        say(f"profile MAPE over {len(val)}: mean {hs['mean']:.1f}  "
            f"median {hs['median']:.1f}  p90 {hs['p90']:.1f}  "
            f"max {hs['max']:.1f}  [%]")
        _gt, summary = validation.gate_table(pd.read_csv(anchors_path))
        say(f"gate E_peak>=1.5: {summary['n_correct']}/{summary['n']} "
            f"correct; misses {len(summary['misses'])}, "
            f"false alarms {len(summary['false_alarms'])}")
        env = validation.envelope_stats(anchors_path, npz_dir,
                                        progress=progress)
        out.update(validation_csv=val_csv, headline=hs, gate=summary,
                   envelope=env)

    if stage in ('figures', 'all'):
        say('== figures ==')
        figures.all88_figures(anchors_path, npz_dir, out_dir,
                              progress=progress)
        figures.envelope_corner_figures(npz_dir, out_dir, progress=progress)
        pc_dir = None if out_dir is None else \
            paths.ensure_dir(Path(out_dir) / 'pressure_check')
        figures.pressure_check_figures(npz_dir=npz_dir, out_dir=pc_dir,
                                       progress=progress)
        out['figures_dir'] = paths.resolve(out_dir,
                                           paths.FIGURES_DIR / 'e_profile')

    return out


def cli(argv=None):
    p = argparse.ArgumentParser(
        description='Street-channelling pipeline: anchors -> fit -> '
                    'validate -> figures.')
    p.add_argument('--stage', default='all', choices=STAGES)
    p.add_argument('--npz-dir', default=None, dest='npz_dir')
    p.add_argument('--dr', type=float, default=0.5, help='slice width [m]')
    p.add_argument('--hi', type=float, default=HI_FRAC, dest='hi_frac',
                   help='decay-fit window start (fraction of peak excess)')
    p.add_argument('--lo', type=float, default=LO_FRAC, dest='lo_frac',
                   help='decay-fit window end (fraction, floored at E=1.2)')
    p.add_argument('--anchors', default=None, dest='anchors_csv',
                   help='anchor table for fit/validate/figures (default: '
                        'the one this run writes)')
    p.add_argument('--out-dir', default=None, dest='out_dir',
                   help='figure root (default outputs/figures/e_profile)')
    p.add_argument('--check-dir', default=None, dest='check_dir',
                   help='CSV root (default outputs/check_results)')
    a = p.parse_args(argv)
    main(stage=a.stage, npz_dir=a.npz_dir, dr=a.dr, hi_frac=a.hi_frac,
         lo_frac=a.lo_frac, anchors_csv=a.anchors_csv, out_dir=a.out_dir,
         check_dir=a.check_dir)
    return 0


if __name__ == '__main__':
    sys.exit(cli())
