"""Unified analysis: process all configs + cross-validated regression.

Phase 1 (run once):
    Load processed .npz files from data/processed_npz/ (created by
    run_preprocess.py), compute convergence radii and max-radius-per-Z,
    save CSVs to outputs/tables/.

Phase 2 (repeated):
    Random 80/20 train/test splits on the saved CSV data, fit regression
    models, evaluate on test set, track best coefficients.

Usage:
    python run_analysis.py                       # prompts (interactive terminal)
    python run_analysis.py --phase all --n-iter 500
    python run_analysis.py --phase 2 --n-iter 500
    python run_analysis.py --phase 1 --scale-p 0.5 1.5 --scale-i 0.5 1.5

The main()/run_phase1()/run_phase2() functions never prompt — they are the
API a GUI launcher calls. Prompting lives in cli() only.
"""

import argparse
import glob as _glob
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.constants import MAX_HEIGHT
from blastlib.geometry import area_density, volume_density, exclude_radius, concat3
from blastlib.io.npz_store import load_processed_data
from blastlib.processing.convergence import find_convergence_radius
from blastlib.processing.free_field import load_ff_lookup, find_percentile_radius
from blastlib.plotting.absolute import plot_absolute
from blastlib.plotting.ratio import plot_ratio
from blastlib.plotting.max_radius import plot_max_radius
from blastlib.plotting.theta_hist import plot_theta_histogram, plot_theta_histogram_Z
from blastlib.regression.cross_validation import run_cross_validation

# Figure subdirectories written by Phase 1 (name → outputs/figures/<name>)
FIG_SUBDIRS = ('absolute', 'ratio', 'max_radius',
               'theta_P', 'theta_I', 'conv_theta')


def run_phase1(*, npz_dir=None, ff_csv=None, tables_dir=None, figures_dir=None,
               scale_limits=None, progress=print):
    """Phase 1: load processed .npz files, compute convergence, save CSVs.

    Parameters
    ----------
    npz_dir : path or None
        Folder of config_*.npz files. None → data/processed_npz/.
    ff_csv : path or None
        free_field_data.csv. None → data/free_field_data.csv.
    tables_dir, figures_dir : path or None
        Output roots. None → outputs/tables, outputs/figures.
    scale_limits : None or dict
        None → auto colour scale. Manual → {'P': (lo, hi), 'I': (lo, hi)}.
    progress : callable
        Progress sink (default print).

    Returns dict with conv_csv, maxR_csv, n_configs.
    """
    npz_dir     = paths.resolve(npz_dir, paths.PROCESSED_NPZ_DIR)
    ff_csv      = paths.resolve(ff_csv, paths.FF_CSV)
    tables_dir  = paths.ensure_dir(paths.resolve(tables_dir, paths.TABLES_DIR))
    figures_dir = paths.ensure_dir(paths.resolve(figures_dir, paths.FIGURES_DIR))

    conv_csv = tables_dir / 'convergence_table.csv'
    maxR_csv = tables_dir / 'max_radius_per_Z.csv'

    progress('=' * 50)
    progress('  PHASE 1: NPZ PROCESSING')
    progress('=' * 50)

    fig_dirs = {name: paths.ensure_dir(figures_dir / name) for name in FIG_SUBDIRS}

    if scale_limits is None:
        progress('Using auto scale')
    else:
        progress(f'Using manual scale: P={tuple(scale_limits["P"])} '
                 f'I={tuple(scale_limits["I"])}')

    # Load free-field lookup table
    ff_lookup = load_ff_lookup(ff_csv)

    # Discover configs from .npz files
    npz_files = sorted(_glob.glob(os.path.join(str(npz_dir), 'config_*.npz')))
    all_configs = [os.path.splitext(os.path.basename(f))[0] for f in npz_files]

    if not all_configs:
        progress(f'No .npz files found in {npz_dir}. Run run_preprocess.py first.')
        return {'conv_csv': conv_csv, 'maxR_csv': maxR_csv, 'n_configs': 0}

    progress(f'Found {len(all_configs)} configs in {npz_dir}\n')

    conv_rows   = []
    maxR_rows   = []
    theta_radii_P = {}
    theta_radii_I = {}
    theta_centers_deg = None

    for i, config_name in enumerate(all_configs):
        progress(f'Processing [{i+1}/{len(all_configs)}] {config_name}...')

        cfg = config_parser(config_name)
        if cfg is None:
            progress('  Warning: could not parse config name')
            continue

        processed, success = load_processed_data(npz_dir, config_name)
        if not success:
            progress(f'  Skipping {config_name} (NPZ load failed)')
            continue

        # Plot absolute values
        plot_absolute(processed, config_name, fig_dirs['absolute'])

        # Geometry parameters
        rho = area_density(cfg['bsize'], cfg['swidth'])
        vol_density = volume_density(cfg['bsize'], cfg['swidth'], cfg['height'])
        exclude_r = exclude_radius(cfg)

        # Convergence radius (angular, equivalent area)
        all_ratio_P = concat3(processed, 'ratioP{}')
        all_ratio_I = concat3(processed, 'ratioI{}')
        all_X = concat3(processed, 'X{}')
        all_Z = concat3(processed, 'Z{}')

        radius = find_convergence_radius(
            all_ratio_P, all_ratio_I,
            processed['peakP_all'], processed['peakI_all'],
            all_X, all_Z, exclude_r
        )

        plot_ratio(processed, cfg, config_name, fig_dirs['ratio'], radius,
                   scale_limits=scale_limits)

        conv_rows.append({
            'ConfigName':    config_name,
            'Det':           cfg['det'],
            'Height':        cfg['height'],
            'BuildingSize':  cfg['bsize'],
            'StreetWidth':   cfg['swidth'],
            'AreaDensity':   rho,
            'VolumeDensity': vol_density,
            'ChargeWeight':  cfg['weight'],
            'RadiusP':       radius['pressure'],
            'RadiusI':       radius['impulse'],
            'PressureAtR':   radius['pressureAtRadius'],
            'ImpulseAtR':    radius['impulseAtRadius'],
        })

        theta_radii_P[config_name] = radius['radius_per_theta_P']
        theta_radii_I[config_name] = radius['radius_per_theta_I']
        if theta_centers_deg is None:
            theta_centers_deg = np.degrees(radius['theta_centers'])

        progress(f'  Req P: {radius["pressure"]:.1f} m  '
                 f'Req I: {radius["impulse"]:.1f} m')

        plot_theta_histogram(
            config_name,
            radius['radius_per_theta_P'],
            radius['radius_per_theta_I'],
            radius['pressure'],
            radius['impulse'],
            np.degrees(radius['theta_centers']),
            fig_dirs['conv_theta'],
        )

        # Max radius per scaled distance Z
        all_P_orig = concat3(processed, 'peakP{}_orig')
        all_I_orig = concat3(processed, 'impulse{}_orig')

        weight = cfg['weight']
        act_R_P = radius['pressure']
        act_R_I = radius['impulse']
        maxR_P_per_Z = {}
        maxR_I_per_Z = {}
        theta_radii_P_per_Z = {}
        theta_radii_I_per_Z = {}

        for z_val in range(1, 21):
            P_ff, I_ff = ff_lookup[weight][z_val]
            maxR_P, r_theta_P = find_percentile_radius(all_P_orig, all_X, all_Z, P_ff)
            maxR_I, r_theta_I = find_percentile_radius(all_I_orig, all_X, all_Z, I_ff)

            maxR_P_per_Z[z_val] = maxR_P
            maxR_I_per_Z[z_val] = maxR_I
            theta_radii_P_per_Z[z_val] = r_theta_P
            theta_radii_I_per_Z[z_val] = r_theta_I

            beyond_P = np.isnan(maxR_P) or maxR_P >= act_R_P
            beyond_I = np.isnan(maxR_I) or maxR_I >= act_R_I
            if beyond_P and beyond_I:
                continue

            maxR_rows.append({
                'Config': config_name,
                'Z': z_val,
                'P_ff': P_ff,
                'I_ff': I_ff,
                'MaxR_P': maxR_P if not beyond_P else np.nan,
                'MaxR_I': maxR_I if not beyond_I else np.nan,
            })

        plot_max_radius(processed, config_name, maxR_P_per_Z, maxR_I_per_Z,
                        radius['pressure'], radius['impulse'], fig_dirs['max_radius'])

        plot_theta_histogram_Z(config_name, theta_radii_P_per_Z, maxR_P_per_Z,
                               'P', fig_dirs['theta_P'])
        plot_theta_histogram_Z(config_name, theta_radii_I_per_Z, maxR_I_per_Z,
                               'I', fig_dirs['theta_I'])

    # ---- Save convergence table ----
    cols = ['ConfigName', 'Det', 'Height', 'BuildingSize', 'StreetWidth',
            'AreaDensity', 'VolumeDensity', 'ChargeWeight',
            'RadiusP', 'RadiusI', 'PressureAtR', 'ImpulseAtR']
    conv_df = pd.DataFrame(conv_rows, columns=cols)
    conv_df.to_csv(conv_csv, index=False)
    progress(f'\nSaved: {conv_csv}')
    progress(conv_df.to_string())

    # ---- Save theta-radius tables ----
    if theta_centers_deg is not None and theta_radii_P:
        config_names = list(theta_radii_P.keys())

        theta_P_df = pd.DataFrame({'Theta_deg': theta_centers_deg})
        for name in config_names:
            theta_P_df[name] = theta_radii_P[name]
        theta_P_df.to_csv(tables_dir / 'theta_radius_P.csv', index=False)

        theta_I_df = pd.DataFrame({'Theta_deg': theta_centers_deg})
        for name in config_names:
            theta_I_df[name] = theta_radii_I[name]
        theta_I_df.to_csv(tables_dir / 'theta_radius_I.csv', index=False)

    # ---- Save max-radius-per-Z table ----
    maxR_df = pd.DataFrame(maxR_rows, columns=['Config', 'Z', 'P_ff', 'I_ff',
                                               'MaxR_P', 'MaxR_I'])
    maxR_df.to_csv(maxR_csv, index=False)
    progress(f'Saved: {maxR_csv}')
    progress(f'\nPhase 1 complete: {len(conv_rows)} configs processed')

    return {'conv_csv': conv_csv, 'maxR_csv': maxR_csv, 'n_configs': len(conv_rows)}


def run_phase2(*, tables_dir=None, n_iterations=500, test_fraction=0.2,
               target_mape=10.0, progress=print):
    """Phase 2: cross-validated regression over the Phase 1 CSVs.

    Returns the summary dict from run_cross_validation.
    """
    tables_dir = paths.ensure_dir(paths.resolve(tables_dir, paths.TABLES_DIR))
    conv_csv = tables_dir / 'convergence_table.csv'
    maxR_csv = tables_dir / 'max_radius_per_Z.csv'

    for path in (conv_csv, maxR_csv):
        if not path.exists():
            raise FileNotFoundError(
                f'{path} not found — run Phase 1 first (--phase 1 or --phase all).')

    progress(f'\n{"="*50}')
    progress(f'  PHASE 2: CROSS-VALIDATED REGRESSION ({n_iterations} iterations)')
    progress(f'{"="*50}\n')

    return run_cross_validation(conv_csv, maxR_csv, tables_dir,
                                n_iterations=n_iterations,
                                test_fraction=test_fraction,
                                target_mape=target_mape,
                                progress=progress)


def main(*, phase='all', n_iterations=500, scale_limits=None,
         npz_dir=None, ff_csv=None, tables_dir=None, figures_dir=None,
         test_fraction=0.2, target_mape=10.0, progress=print):
    """Run the analysis. Never prompts — this is the GUI/API entry point.

    phase : 'all' | '1' | '2'
    """
    result = {}

    if phase in ('all', '1'):
        result['phase1'] = run_phase1(
            npz_dir=npz_dir, ff_csv=ff_csv, tables_dir=tables_dir,
            figures_dir=figures_dir, scale_limits=scale_limits,
            progress=progress)

    if phase in ('all', '2'):
        result['phase2'] = run_phase2(
            tables_dir=tables_dir, n_iterations=n_iterations,
            test_fraction=test_fraction, target_mape=target_mape,
            progress=progress)

    progress('\n' + '=' * 40)
    progress('  ALL DONE')
    progress('=' * 40)
    return result


def _build_parser():
    p = argparse.ArgumentParser(
        description='Urban blast analysis: Phase 1 (NPZ → tables) + Phase 2 (regression).')
    p.add_argument('--phase', choices=['all', '1', '2'], default=None,
                   help="Which phase to run (default: ask, or 'all' when non-interactive).")
    p.add_argument('--n-iter', type=int, default=None, dest='n_iter',
                   help='Number of CV iterations for Phase 2 (default 500). '
                        'NOTE: changing this changes the whole split sequence.')
    p.add_argument('--scale-p', type=float, nargs=2, metavar=('LO', 'HI'),
                   default=None, help='Manual pressure-ratio colour limits.')
    p.add_argument('--scale-i', type=float, nargs=2, metavar=('LO', 'HI'),
                   default=None, help='Manual impulse-ratio colour limits.')
    p.add_argument('--npz-dir', default=None, help='Folder of config_*.npz files.')
    p.add_argument('--ff-csv', default=None, help='free_field_data.csv path.')
    p.add_argument('--tables-dir', default=None, help='Output folder for CSV tables.')
    p.add_argument('--figures-dir', default=None, help='Output folder for figures.')
    return p


def _prompt(message, default=None):
    """Ask the user for input; return *default* if there is no usable stdin.

    isatty() alone is not reliable — some non-interactive launchers report a
    tty but deliver EOF on the first read — so treat EOFError as "no answer".
    """
    if sys.stdin is None or not sys.stdin.isatty():
        return default
    try:
        return input(message).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def cli(argv=None):
    """Parse args, optionally prompt for anything missing, then run main()."""
    args = _build_parser().parse_args(argv)

    tables_dir = paths.resolve(args.tables_dir, paths.TABLES_DIR)
    conv_csv = tables_dir / 'convergence_table.csv'
    maxR_csv = tables_dir / 'max_radius_per_Z.csv'

    # ---- Phase selection ----
    phase = args.phase
    if phase is None:
        phase = 'all'
        if conv_csv.exists() and maxR_csv.exists():
            choice = _prompt('Found existing CSV data. '
                             '(1) Reprocess from NPZ / (2) Skip to regression: ')
            if choice == '2':
                phase = '2'

    # ---- Scale limits ----
    scale_limits = None
    if args.scale_p and args.scale_i:
        scale_limits = {'P': tuple(args.scale_p), 'I': tuple(args.scale_i)}
    elif args.scale_p or args.scale_i:
        _build_parser().error('--scale-p and --scale-i must be given together.')
    elif phase in ('all', '1'):
        if _prompt('Scale mode - (1) Auto / (2) Manual: ') == '2':
            lim_p = (_prompt('Enter pressure ratio limits [min max]: ') or '').split()
            lim_i = (_prompt('Enter impulse ratio limits [min max]: ') or '').split()
            if len(lim_p) == 2 and len(lim_i) == 2:
                scale_limits = {'P': (float(lim_p[0]), float(lim_p[1])),
                                'I': (float(lim_i[0]), float(lim_i[1]))}
            else:
                _build_parser().error('Manual scale needs two numbers for each of '
                                      'pressure and impulse.')

    # ---- CV iterations ----
    n_iter = args.n_iter
    if n_iter is None:
        n_iter = 500
        if phase in ('all', '2'):
            n_iter_str = _prompt('Number of CV iterations [default 500]: ')
            if n_iter_str:
                n_iter = int(n_iter_str)

    return main(phase=phase, n_iterations=n_iter, scale_limits=scale_limits,
                npz_dir=args.npz_dir, ff_csv=args.ff_csv,
                tables_dir=args.tables_dir, figures_dir=args.figures_dir)


if __name__ == '__main__':
    cli()
