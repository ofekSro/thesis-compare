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
    python run_analysis.py --phase 1 --radius-method p95

The main()/run_phase1()/run_phase2() functions never prompt — they are the
API a GUI launcher calls. Prompting lives in cli() only.

Output files are suffixed with the radius estimator (convergence_table_req.csv,
convergence_table_p95.csv, ...) because different estimators give genuinely
different numbers and must not overwrite each other.
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
from blastlib import constants
from blastlib.geometry import area_density, volume_density, exclude_radius, concat3
from blastlib.io import raw_store
from blastlib.io.npz_store import load_processed_data
from blastlib.processing.convergence import find_convergence_radius
from blastlib.processing.free_field import (load_ff_lookup,
                                            find_percentile_radius,
                                            reference_level_per_theta,
                                            theta_index)
from blastlib.processing.radius_estimator import resolve_estimator, VALID_METHODS
from blastlib.processing.ff_reference import rebuild_impulse_ratio
from blastlib.processing.soft_criterion import (soft_pressure_fields,
                                                soft_pressure_weights)
from blastlib.plotting.absolute import plot_absolute
from blastlib.plotting.ratio import plot_ratio
from blastlib.plotting.max_radius import plot_max_radius
from blastlib.plotting.theta_hist import plot_theta_histogram, plot_theta_histogram_Z
from blastlib.regression.cross_validation import run_cross_validation

# Figure subdirectories written by Phase 1 (name → outputs/figures/<name>)
FIG_SUBDIRS = ('absolute', 'ratio', 'max_radius',
               'theta_P', 'theta_I', 'conv_theta')


def _resolve_figure_set(make_figures):
    """Normalize the make_figures parameter into the set of active categories.

    True -> all of FIG_SUBDIRS; False/None/empty -> none; an iterable of
    category names -> exactly those (unknown names are an error, not a
    silent skip — a typo must not quietly disable a figure).
    """
    if make_figures is True:
        return set(FIG_SUBDIRS)
    if not make_figures:
        return set()
    active = set(make_figures)
    unknown = active - set(FIG_SUBDIRS)
    if unknown:
        raise ValueError(f'unknown figure categories {sorted(unknown)}; '
                         f'expected a subset of {FIG_SUBDIRS}')
    return active


def run_phase1(*, npz_dir=None, ff_csv=None, tables_dir=None, figures_dir=None,
               scale_limits=None, radius_estimator=None,
               rebuild_impulse=False, make_figures=True, progress=print):
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
    radius_estimator : dict, str or None
        How the 91 per-angle radii collapse to one scalar. None →
        constants.RADIUS_ESTIMATOR. The SAME estimator is used for the
        convergence radius and for MaxR — that is the whole point of the
        setting, so it is resolved once here and passed to both.
    rebuild_impulse : bool
        Recompute ratioI from the scaled impulse criterion before analysing,
        reconstructing the free-field reference from ff_csv. Needed only
        because the shipped NPZs were written under the old pressure-gated
        rule and the VTKs are unavailable; once preprocessing can be re-run
        this should be False and the NPZs will already be correct.
    make_figures : bool or iterable of str
        True draws every per-config figure; False skips them all (the
        dominant runtime cost) — tables come out identical either way. An
        iterable of category names (subset of FIG_SUBDIRS: 'absolute',
        'ratio', 'max_radius', 'theta_P', 'theta_I', 'conv_theta') draws
        only those categories.
    progress : callable
        Progress sink (default print).

    A soft radius-estimator token ('req_soft', 'req_soft8', ...) switches
    the PRESSURE sectors to the soft tanh criterion; it needs the raw band
    fields, which the v3 raw store (data/raw_npz, the default) produces at
    load time and the v2 superset carries on disk. A v1 folder cannot serve
    it. The impulse path is identical under hard and soft tokens.

    Returns dict with conv_csv, maxR_csv, method, n_configs.
    """
    est = resolve_estimator(radius_estimator)
    method = est['method']
    active_figs = _resolve_figure_set(make_figures)

    # A blank npz_dir prefers the v3 raw store (it serves both criteria);
    # failing that, soft tokens need the v2 superset's raw band fields.
    npz_dir     = paths.resolve(npz_dir,
                                paths.default_npz_dir(
                                    soft=est['soft_beta'] is not None))
    ff_csv      = paths.resolve(ff_csv, paths.FF_CSV)
    tables_dir  = paths.ensure_dir(paths.resolve(tables_dir, paths.TABLES_DIR))
    figures_dir = paths.ensure_dir(paths.resolve(figures_dir, paths.FIGURES_DIR))

    conv_csv = tables_dir / paths.suffixed(paths.CONV_CSV.name, method)
    maxR_csv = tables_dir / paths.suffixed(paths.MAXR_CSV.name, method)

    progress('=' * 50)
    progress('  PHASE 1: NPZ PROCESSING')
    progress('=' * 50)
    progress(f'Radius estimator: {method}  '
             '(drives both the convergence radius and MaxR)')
    if active_figs != set(FIG_SUBDIRS):
        progress('Figures: ' + (', '.join(f for f in FIG_SUBDIRS
                                          if f in active_figs) or 'none')
                 + '  (tables are unaffected)')

    # Figures depend on the estimator too (they draw the collapsed radius),
    # so each method gets its own tree instead of overwriting the last run.
    fig_root = paths.ensure_dir(figures_dir / method)
    fig_dirs = {name: paths.ensure_dir(fig_root / name) for name in FIG_SUBDIRS}

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
        return {'conv_csv': conv_csv, 'maxR_csv': maxR_csv,
                'method': method, 'n_configs': 0}

    # A raw (v3) store applies the criteria here, at load time, from the
    # solver's own fields — which is exactly what --rebuild-impulse existed to
    # approximate back when only processed NPZs and no VTKs were available.
    # Running it on top would re-derive ratioI from the 1-D free-field table
    # instead of the true reference field, i.e. strictly worse. Refuse rather
    # than silently double-apply.
    raw_store_in_use = raw_store.is_raw_dir(npz_dir)
    progress(f'Found {len(all_configs)} configs in {npz_dir}'
             + ('  [raw store — criteria applied now]' if raw_store_in_use
                else '  [processed store — criteria baked in]'))
    if rebuild_impulse and raw_store_in_use:
        progress('  Ignoring --rebuild-impulse: a raw store already computes '
                 'ratioI from the true reference field.')
    progress('')

    conv_rows   = []
    maxR_rows   = []
    theta_radii_P = {}
    theta_radii_I = {}
    theta_centers_deg = None
    # How often the per-direction reference level was unavailable and the
    # scalar from free_field_data.csv had to stand in. Reported at the end:
    # a large share would mean the reference field is not covering the radii
    # being probed, which the per-direction fix assumes it does.
    n_fallback = 0
    n_levels   = 0

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

        if rebuild_impulse and not raw_store_in_use:
            processed = rebuild_impulse_ratio(processed, cfg['weight'], ff_csv)

        if 'absolute' in active_figs:
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

        soft_w_P = None
        if est['soft_beta'] is not None:
            soft_w_P = soft_pressure_weights(
                soft_pressure_fields(processed), est['soft_beta'])

        radius = find_convergence_radius(
            all_ratio_P, all_ratio_I,
            processed['peakP_all'], processed['peakI_all'],
            all_X, all_Z, exclude_r, estimator=est, soft_w_P=soft_w_P
        )

        if 'ratio' in active_figs:
            plot_ratio(processed, cfg, config_name, fig_dirs['ratio'], radius,
                       scale_limits=scale_limits, method=method)

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
            'RadiusEstimator': method,
        })

        theta_radii_P[config_name] = radius['radius_per_theta_P']
        theta_radii_I[config_name] = radius['radius_per_theta_I']
        if theta_centers_deg is None:
            theta_centers_deg = np.degrees(radius['theta_centers'])

        progress(f'  R_conv({method}) P: {radius["pressure"]:.1f} m  '
                 f'I: {radius["impulse"]:.1f} m')

        if 'conv_theta' in active_figs:
            plot_theta_histogram(
                config_name,
                radius['radius_per_theta_P'],
                radius['radius_per_theta_I'],
                radius['pressure'],
                radius['impulse'],
                np.degrees(radius['theta_centers']),
                fig_dirs['conv_theta'],
                method,
            )

        # Max radius per scaled distance Z
        all_P_orig = concat3(processed, 'peakP{}_orig')
        all_I_orig = concat3(processed, 'impulse{}_orig')

        # The reference FIELD, for a per-direction exceedance level. On the
        # Cartesian mesh the free field is anisotropic (~9.6% between
        # directions); R_conv cancels that by dividing cell-by-cell, and MaxR
        # only cancels it if its threshold is sampled per direction too.
        # ff_lookup stays as the fallback for sectors the field cannot serve.
        # The level is sampled from the MAX-FILLED reference — the same
        # cross-grid merge as the urban field it is compared with — because
        # the raw fine reference is deficient near its outer edge
        # (docs/audit/2026-09-27 PHY-04). Legacy v1/v2 stores carry only the
        # raw reference and keep the old behaviour.
        if 'refP1_fill' in processed:
            all_refP = concat3(processed, 'refP{}_fill')
            all_refI = concat3(processed, 'refI{}_fill')
        else:
            all_refP = concat3(processed, 'refP{}')
            all_refI = concat3(processed, 'refI{}')
        th_idx = theta_index(all_X, all_Z)
        dist_all = np.sqrt(all_X ** 2 + all_Z ** 2)

        weight = cfg['weight']
        W13 = float(weight) ** (1 / 3)
        act_R_P = radius['pressure']
        act_R_I = radius['impulse']
        maxR_P_per_Z = {}
        maxR_I_per_Z = {}
        theta_radii_P_per_Z = {}
        theta_radii_I_per_Z = {}

        for z_val in range(1, 21):
            P_ff, I_ff = ff_lookup[weight][z_val]
            r_free = z_val * W13

            lvl_P = reference_level_per_theta(all_refP, dist_all, th_idx, r_free)
            lvl_I = reference_level_per_theta(all_refI, dist_all, th_idx, r_free)
            n_fallback += int(np.isnan(lvl_P).sum() + np.isnan(lvl_I).sum())
            n_levels += 2 * len(lvl_P)
            lvl_P = np.where(np.isnan(lvl_P), P_ff, lvl_P)
            lvl_I = np.where(np.isnan(lvl_I), I_ff, lvl_I)

            # exclude_r is deliberately NOT applied here — it is applied per
            # ROW in z_urban.z_urban_valid_mask instead. See the note on
            # find_percentile_radius: inside the per-sector maximum it silently
            # converts "this direction is excluded" into "this direction has
            # radius zero", which Req then integrates as zero area.
            maxR_P, r_theta_P = find_percentile_radius(
                all_P_orig, all_X, all_Z, lvl_P, estimator=est,
                th_idx=th_idx, dist=dist_all)
            maxR_I, r_theta_I = find_percentile_radius(
                all_I_orig, all_X, all_Z, lvl_I, estimator=est,
                th_idx=th_idx, dist=dist_all)

            maxR_P_per_Z[z_val] = maxR_P
            maxR_I_per_Z[z_val] = maxR_I
            theta_radii_P_per_Z[z_val] = r_theta_P
            theta_radii_I_per_Z[z_val] = r_theta_I

            # "Beyond" = at or outside the convergence radius, where the urban
            # field is the free field and the row carries no urban information.
            # These rows used to be dropped here (and the beyond side NaN'd),
            # which hid how often it happens. Record the flag and the raw
            # value instead; the exclusion now lives in the fit, in
            # z_urban.z_urban_valid_mask.
            beyond_P = bool(np.isnan(maxR_P) or maxR_P >= act_R_P)
            beyond_I = bool(np.isnan(maxR_I) or maxR_I >= act_R_I)

            maxR_rows.append({
                'Config': config_name,
                'Z': z_val,
                'P_ff': P_ff,
                'I_ff': I_ff,
                'MaxR_P': maxR_P,
                'MaxR_I': maxR_I,
                'beyond_P': beyond_P,
                'beyond_I': beyond_I,
                # Geometry of the row, so z_urban_valid_mask's two range
                # conditions are auditable straight from the table.
                'R_free': r_free,
                'ExcludeR': exclude_r,
                'RadiusEstimator': method,
            })

        if 'max_radius' in active_figs:
            plot_max_radius(processed, config_name, maxR_P_per_Z, maxR_I_per_Z,
                            radius['pressure'], radius['impulse'],
                            fig_dirs['max_radius'])

        if 'theta_P' in active_figs:
            plot_theta_histogram_Z(config_name, theta_radii_P_per_Z, maxR_P_per_Z,
                                   'P', fig_dirs['theta_P'])
        if 'theta_I' in active_figs:
            plot_theta_histogram_Z(config_name, theta_radii_I_per_Z, maxR_I_per_Z,
                                   'I', fig_dirs['theta_I'])

    # ---- Save convergence table ----
    cols = ['ConfigName', 'Det', 'Height', 'BuildingSize', 'StreetWidth',
            'AreaDensity', 'VolumeDensity', 'ChargeWeight',
            'RadiusP', 'RadiusI', 'PressureAtR', 'ImpulseAtR',
            'RadiusEstimator']
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
        theta_P_df.to_csv(
            tables_dir / paths.suffixed('theta_radius_P.csv', method), index=False)

        theta_I_df = pd.DataFrame({'Theta_deg': theta_centers_deg})
        for name in config_names:
            theta_I_df[name] = theta_radii_I[name]
        theta_I_df.to_csv(
            tables_dir / paths.suffixed('theta_radius_I.csv', method), index=False)

    # ---- Save max-radius-per-Z table ----
    maxR_df = pd.DataFrame(maxR_rows, columns=['Config', 'Z', 'P_ff', 'I_ff',
                                               'MaxR_P', 'MaxR_I',
                                               'beyond_P', 'beyond_I',
                                               'R_free', 'ExcludeR',
                                               'RadiusEstimator'])
    maxR_df.to_csv(maxR_csv, index=False)
    progress(f'Saved: {maxR_csv}')

    if len(maxR_df):
        progress(f'  {len(maxR_df)} rows  |  beyond R_conv: '
                 f'P {int(maxR_df["beyond_P"].sum())}, '
                 f'I {int(maxR_df["beyond_I"].sum())} '
                 '(kept in the CSV, excluded at fitting)')
    if n_levels:
        progress(f'  Exceedance level per direction: '
                 f'{100 * (1 - n_fallback / n_levels):.1f}% from the reference '
                 f'field, {100 * n_fallback / n_levels:.1f}% fell back to the '
                 f'free_field_data.csv scalar')
    progress(f'\nPhase 1 complete: {len(conv_rows)} configs processed')

    return {'conv_csv': conv_csv, 'maxR_csv': maxR_csv,
            'method': method, 'n_configs': len(conv_rows)}


def run_phase2(*, tables_dir=None, n_iterations=500, test_fraction=0.2,
               target_mape=10.0, radius_estimator=None,
               model_p='relwls', model_i='unified', progress=print):
    """Phase 2: cross-validated regression over the Phase 1 CSVs.

    *radius_estimator* selects which Phase 1 tables to read and how the
    outputs are named; it does not affect any fitting formula.
    *model_p* ('relwls'|'legacy') and *model_i*
    ('unified'|'quad'|'legacy') select the convergence-model fit variants
    — see run_cross_validation. Defaults are production: 'relwls' since
    the 2026-08 acceptance gate, 'unified' since the 2026-09-27 RadiusI
    model change; pass the older tokens to reproduce historical sets.

    Returns the summary dict from run_cross_validation.
    """
    tables_dir = paths.ensure_dir(paths.resolve(tables_dir, paths.TABLES_DIR))
    method = resolve_estimator(radius_estimator)['method']

    conv_csv = tables_dir / paths.suffixed(paths.CONV_CSV.name, method)
    maxR_csv = tables_dir / paths.suffixed(paths.MAXR_CSV.name, method)

    for path in (conv_csv, maxR_csv):
        if not path.exists():
            raise FileNotFoundError(
                f'{path} not found — run Phase 1 first with the same radius '
                f'estimator ({method}): --phase 1 --radius-method {method}.')

    progress(f'\n{"="*50}')
    progress(f'  PHASE 2: CROSS-VALIDATED REGRESSION ({n_iterations} iterations)')
    progress(f'  Radius estimator: {method}')
    progress(f'{"="*50}\n')

    return run_cross_validation(conv_csv, maxR_csv, tables_dir,
                                n_iterations=n_iterations,
                                test_fraction=test_fraction,
                                target_mape=target_mape,
                                method=method,
                                model_p=model_p, model_i=model_i,
                                progress=progress)


def main(*, phase='all', n_iterations=500, scale_limits=None,
         npz_dir=None, ff_csv=None, tables_dir=None, figures_dir=None,
         test_fraction=0.2, target_mape=10.0, radius_estimator=None,
         rebuild_impulse=False, make_figures=True,
         model_p='relwls', model_i='unified', progress=print):
    """Run the analysis. Never prompts — this is the GUI/API entry point.

    phase : 'all' | '1' | '2'
    radius_estimator : dict, str or None
        {'method': 'req'|'max'|'p95', 'percentile': N}. None →
        constants.RADIUS_ESTIMATOR. Both phases get the same value, so
        Phase 2 always reads the tables Phase 1 just wrote.
    model_p, model_i : str
        Convergence-model fit variants for Phase 2 — see run_phase2.
    """
    result = {}

    if phase in ('all', '1'):
        result['phase1'] = run_phase1(
            npz_dir=npz_dir, ff_csv=ff_csv, tables_dir=tables_dir,
            figures_dir=figures_dir, scale_limits=scale_limits,
            radius_estimator=radius_estimator,
            rebuild_impulse=rebuild_impulse, make_figures=make_figures,
            progress=progress)

    if phase in ('all', '2'):
        result['phase2'] = run_phase2(
            tables_dir=tables_dir, n_iterations=n_iterations,
            test_fraction=test_fraction, target_mape=target_mape,
            radius_estimator=radius_estimator,
            model_p=model_p, model_i=model_i, progress=progress)

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
    p.add_argument('--radius-method', default=None,
                   dest='radius_method',
                   help='How the 91 per-angle radii collapse to one radius: '
                        f'{"|".join(VALID_METHODS)}, pXX, or a soft token '
                        "'<base>_soft[beta]' (e.g. req_soft, req_soft8) that "
                        'measures pressure sectors with the soft tanh '
                        'criterion. Drives BOTH the convergence radius and '
                        f'MaxR (default: {constants.RADIUS_ESTIMATOR["method"]}).')
    p.add_argument('--percentile', type=float, default=None,
                   help='Percentile for --radius-method p95 (default 95).')
    p.add_argument('--soft-beta', type=float, default=None, dest='soft_beta',
                   help='Beta override for a _soft radius method '
                        f'(default: constants.PARAMS softBeta = '
                        f'{constants.PARAMS["softBeta"]}).')
    p.add_argument('--no-figures', action='store_true', dest='no_figures',
                   help='Skip all per-config figures in Phase 1 (tables '
                        'identical, much faster). For parameter sweeps.')
    p.add_argument('--figures', default=None, dest='figures',
                   help='Comma-separated figure categories to draw in Phase 1 '
                        f'({",".join(FIG_SUBDIRS)}), or all|none. '
                        'Default: all.')
    p.add_argument('--rebuild-impulse', action='store_true', dest='rebuild_impulse',
                   help='Recompute ratioI under the scaled impulse criterion, '
                        'reconstructing the free-field reference. Needed while '
                        'the NPZs predate the criterion and the VTKs are absent.')
    p.add_argument('--model-p', choices=['legacy', 'relwls'], default='relwls',
                   dest='model_p',
                   help="RadiusP fit variant for Phase 2: 'relwls' relative-"
                        "error weighted LS (production default) or 'legacy' "
                        "plain OLS.")
    p.add_argument('--model-i', choices=['legacy', 'quad', 'unified'],
                   default='unified', dest='model_i',
                   help="RadiusI fit variant for Phase 2: 'unified' shared "
                        "five-term form (production default since "
                        "2026-09-27), 'quad' power law with the (ln Pi2)^2 "
                        "term, or 'legacy' 4-coefficient power law.")
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

    # ---- Radius estimator ----
    # Only the flags actually given go into the dict; the rest come from
    # constants.RADIUS_ESTIMATOR, the single shared default.
    radius_estimator = {}
    if args.radius_method is not None:
        radius_estimator['method'] = args.radius_method
    if args.percentile is not None:
        method = args.radius_method or constants.RADIUS_ESTIMATOR['method']
        if not str(method).startswith('p'):
            _build_parser().error(
                f'--percentile applies only to a percentile method, '
                f'not --radius-method {method}.')
        radius_estimator['percentile'] = args.percentile
    if args.soft_beta is not None:
        method = args.radius_method or constants.RADIUS_ESTIMATOR['method']
        if '_soft' not in str(method):
            _build_parser().error(
                f'--soft-beta applies only to a _soft radius method, '
                f'not --radius-method {method}.')
        radius_estimator['soft_beta'] = args.soft_beta
    radius_estimator = radius_estimator or None

    method = resolve_estimator(radius_estimator)['method']
    tables_dir = paths.resolve(args.tables_dir, paths.TABLES_DIR)
    conv_csv = tables_dir / paths.suffixed(paths.CONV_CSV.name, method)
    maxR_csv = tables_dir / paths.suffixed(paths.MAXR_CSV.name, method)

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

    # ---- Figure selection ----
    if args.figures is not None:
        s = args.figures.strip().lower()
        if s == 'all':
            make_figures = True
        elif s in ('', 'none'):
            make_figures = False
        else:
            make_figures = tuple(x.strip() for x in s.split(',') if x.strip())
    else:
        make_figures = not args.no_figures

    return main(phase=phase, n_iterations=n_iter, scale_limits=scale_limits,
                npz_dir=args.npz_dir, ff_csv=args.ff_csv,
                tables_dir=args.tables_dir, figures_dir=args.figures_dir,
                radius_estimator=radius_estimator,
                rebuild_impulse=args.rebuild_impulse,
                make_figures=make_figures,
                model_p=args.model_p, model_i=args.model_i)


if __name__ == '__main__':
    cli()
