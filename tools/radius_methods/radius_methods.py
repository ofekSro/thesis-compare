"""Compare 3 convergence-radius definitions for a single configuration.

For one config, this computes the convergence radius in three different ways
from the per-theta radii produced by find_convergence_radius, and draws ratio
plots (like the pipeline's ratio figures) with the matching convergence circle
for each method:

    1. max        - maximum of the per-theta radii
    2. p95        - 95th percentile of the per-theta radii
    3. eq_area    - equivalent area radius (the method used by the pipeline)

Output (in outputs/figures/radius_methods/):
    <config>_pressure_methods.png  - 3 panels (max / p95 / eq_area), P / P_ref
    <config>_impulse_methods.png   - 3 panels (max / p95 / eq_area), I / I_ref
    pressure_radius_methods.csv    - all configs, all 3 methods
    impulse_radius_methods.csv

Usage:
    python tools\\radius_methods\\radius_methods.py                    # prompts
    python tools\\radius_methods\\radius_methods.py config_01_det1_b15_s5_h4_w50
"""

import argparse
import glob
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.geometry import exclude_radius, concat3
from blastlib.io.npz_store import load_processed_data
from blastlib.processing.convergence import (find_convergence_radius,
                                             equivalent_area_radius)
from blastlib.plotting.common import (bluewhitered, plot_layer,
                                      draw_quarter_circle,
                                      draw_convergence_polyline)
from blastlib.plotting.cuboids import draw_cuboids_gray
from blastlib.plotting.ratio import calculate_scale


# Per-theta angular spacing used by find_convergence_radius (1 degree)
DELTA_THETA = np.radians(1.0)

_PANEL_LABELS  = ['(a)', '(b)', '(c)', '(d)']
_METHOD_NAMES  = {
    'Max':      'Maximum',
    '95th pct': '95th Percentile',
    'Eq. area': 'Equivalent Area',
}


def _summary_radii(radii):
    """Return all three radius definitions for one per-theta radius array.

    The pipeline itself only uses eq_area; max and p95 are computed here so
    this tool can compare them.

    radii : array of per-theta convergence radii (may contain NaN)
    Returns dict {'max', 'p95', 'eq_area'}.
    """
    valid = ~np.isnan(radii)
    if not np.any(valid):
        return {'max': np.nan, 'p95': np.nan, 'eq_area': np.nan}
    return {
        'max': float(np.nanmax(radii)),
        'p95': float(np.nanpercentile(radii[valid], 95)),
        'eq_area': equivalent_area_radius(radii, DELTA_THETA),
    }


def _config_title(cfg):
    """Human-readable geometry string for figure suptitle."""
    det_str = 'Street detonation' if cfg['det'] == 1 else 'Intersection detonation'
    return (f'b = {cfg["bsize"]} m,  s = {cfg["swidth"]} m,  '
            f'H = {cfg["height"]} m,  W = {cfg["weight"]} kg TNT  —  {det_str}')


def _plot_quantity(layers, cfg, config_name, theta_centers, radii_per_theta,
                   methods, cmap, norm, quantity_label, out_path, progress=print):
    """Draw one combined figure (3 method-panels) for a single quantity.

    layers          : list of (X, Z, ratio) triples, far-to-near order
    methods         : list of (name, radius_value) tuples, one per panel
    quantity_label  : 'P / P_ref' or 'I / I_ref'
    """
    radii_vals = [r for _, r in methods if not np.isnan(r)]
    axis_limit = (max(radii_vals) if radii_vals else 10) + 15
    n = len(methods)

    fig, axes = plt.subplots(1, n, figsize=(7 * n, 6), constrained_layout=True)
    if n == 1:
        axes = [axes]

    fig.suptitle(_config_title(cfg), fontsize=13, fontweight='bold')

    for idx, (ax, (name, r)) in enumerate(zip(axes, methods)):
        ax.set_facecolor('white')
        for X, Z, ratio in layers:
            plot_layer(ax, X, Z, ratio, cmap, norm)

        ax.set_xlim(0, axis_limit)
        ax.set_ylim(0, axis_limit)
        ax.set_aspect('equal')
        ax.set_xlabel('X [m]', fontsize=12)
        ax.set_ylabel('Z [m]' if idx == 0 else '', fontsize=12)
        ax.tick_params(labelsize=10)

        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cb = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04)
        cb.set_label(quantity_label, fontsize=11)
        cb.ax.tick_params(labelsize=9)

        draw_cuboids_gray(ax, config_name)

        # Dummy handles for legend (actual lines drawn by the helpers below)
        h_poly = ax.plot([], [], 'k-',  linewidth=1.5, label='Per-θ boundary')[0]
        h_circ = ax.plot([], [], 'k--', linewidth=2, label='Convergence radius')[0]

        draw_convergence_polyline(ax, theta_centers, radii_per_theta)
        draw_quarter_circle(ax, r, color='black', linewidth=2)

        # Panel label + full method name + radius value
        full_name = _METHOD_NAMES.get(name, name)
        r_str = f'{r:.1f} m' if not np.isnan(r) else 'n/a'
        ax.set_title(f'{_PANEL_LABELS[idx]}  {full_name}\nR = {r_str}',
                     fontsize=12, loc='left', pad=8)

        # Legend only on the first panel
        if idx == 0:
            ax.legend(handles=[h_poly, h_circ], fontsize=10,
                      loc='upper right', framealpha=0.85, edgecolor='gray')

    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    progress(f'  Saved: {out_path}')


def _compute_radius(npz_dir, config_name):
    """Load a config's processed grids and compute its convergence radius.

    Returns (cfg, processed, radius) or None on parse/load failure.
    """
    cfg = config_parser(config_name)
    if cfg is None:
        return None

    processed, success = load_processed_data(npz_dir, config_name)
    if not success:
        return None

    radius = find_convergence_radius(
        concat3(processed, 'ratioP{}'), concat3(processed, 'ratioI{}'),
        processed['peakP_all'], processed['peakI_all'],
        concat3(processed, 'X{}'), concat3(processed, 'Z{}'),
        exclude_radius(cfg)
    )
    return cfg, processed, radius


def _methods(radius):
    """Return (methods_P, methods_I): lists of (name, radius_value) per method.

    Order matches the figure panels and the CSV columns:
        1 = Max, 2 = 95th pct, 3 = Eq. area
    """
    sum_P = _summary_radii(radius['radius_per_theta_P'])
    sum_I = _summary_radii(radius['radius_per_theta_I'])
    methods_P = [
        ('Max',      sum_P['max']),
        ('95th pct', sum_P['p95']),
        ('Eq. area', sum_P['eq_area']),
    ]
    methods_I = [
        ('Max',      sum_I['max']),
        ('95th pct', sum_I['p95']),
        ('Eq. area', sum_I['eq_area']),
    ]
    return methods_P, methods_I


def _plot_config(processed, cfg, config_name, radius, methods_P, methods_I,
                 out_folder, progress=print):
    """Save the two combined method-comparison figures for one config."""
    scale_P, scale_I = calculate_scale(processed, cfg, scale_limits=None)
    cmap = bluewhitered()
    norm_P = mcolors.Normalize(vmin=scale_P[0], vmax=scale_P[1])
    norm_I = mcolors.Normalize(vmin=scale_I[0], vmax=scale_I[1])

    layers_P = [
        (processed['X3'], processed['Z3'], processed['ratioP3']),
        (processed['X2'], processed['Z2'], processed['ratioP2']),
        (processed['X1'], processed['Z1'], processed['ratioP1']),
    ]
    layers_I = [
        (processed['X3'], processed['Z3'], processed['ratioI3']),
        (processed['X2'], processed['Z2'], processed['ratioI2']),
        (processed['X1'], processed['Z1'], processed['ratioI1']),
    ]

    _plot_quantity(
        layers_P, cfg, config_name, radius['theta_centers'],
        radius['radius_per_theta_P'], methods_P, cmap, norm_P, 'P / P_ref',
        os.path.join(str(out_folder), f'{config_name}_pressure_methods.png'),
        progress=progress)
    _plot_quantity(
        layers_I, cfg, config_name, radius['theta_centers'],
        radius['radius_per_theta_I'], methods_I, cmap, norm_I, 'I / I_ref',
        os.path.join(str(out_folder), f'{config_name}_impulse_methods.png'),
        progress=progress)


def list_configs(npz_dir=None):
    """Return the sorted config names available in npz_dir (for a GUI dropdown)."""
    npz_dir = paths.resolve(npz_dir, paths.PROCESSED_NPZ_DIR)
    npz_files = sorted(glob.glob(os.path.join(str(npz_dir), 'config_*.npz')))
    return [os.path.splitext(os.path.basename(f))[0] for f in npz_files]


def main(config_name, *, npz_dir=None, out_dir=None, progress=print):
    """Compare radius definitions across all configs; plot the named one.

    Returns dict with the two CSV paths and the row count, or None if no
    NPZ files were found.
    """
    npz_dir = paths.resolve(npz_dir, paths.PROCESSED_NPZ_DIR)
    out_dir = paths.ensure_dir(paths.resolve(out_dir,
                                             paths.FIGURES_DIR / 'radius_methods'))

    all_configs = list_configs(npz_dir)
    if not all_configs:
        progress(f'No .npz files found in {npz_dir}. Run run_preprocess.py first.')
        return None

    progress(f'Computing convergence radii for {len(all_configs)} configs...')

    rows_P = []
    rows_I = []
    plotted = False

    for name in all_configs:
        result = _compute_radius(npz_dir, name)
        if result is None:
            progress(f'  Skipping {name} (parse/load failed)')
            continue
        cfg, processed, radius = result
        methods_P, methods_I = _methods(radius)

        rows_P.append({'ConfigName':     name,
                       'R_convergence1': methods_P[0][1],
                       'R_convergence2': methods_P[1][1],
                       'R_convergence3': methods_P[2][1]})
        rows_I.append({'ConfigName':     name,
                       'R_convergence1': methods_I[0][1],
                       'R_convergence2': methods_I[1][1],
                       'R_convergence3': methods_I[2][1]})

        # Figures only for the requested config
        if name == config_name:
            progress(f'\nConvergence radius for {name}:')
            progress(f'  Pressure  - max={methods_P[0][1]:.2f}  '
                     f'p95={methods_P[1][1]:.2f}  eq_area={methods_P[2][1]:.2f} m')
            progress(f'  Impulse   - max={methods_I[0][1]:.2f}  '
                     f'p95={methods_I[1][1]:.2f}  eq_area={methods_I[2][1]:.2f} m')
            _plot_config(processed, cfg, name, radius, methods_P, methods_I,
                         out_dir, progress=progress)
            plotted = True

    if not plotted:
        progress(f'\nWarning: no figures produced -- "{config_name}" not found '
                 f'in {npz_dir}.')

    # ---- Save comparison CSVs (R_convergence1=Max, 2=95th pct, 3=Eq. area) ----
    cols = ['ConfigName', 'R_convergence1', 'R_convergence2', 'R_convergence3']
    p_csv = out_dir / 'pressure_radius_methods.csv'
    i_csv = out_dir / 'impulse_radius_methods.csv'
    pd.DataFrame(rows_P, columns=cols).to_csv(p_csv, index=False)
    pd.DataFrame(rows_I, columns=cols).to_csv(i_csv, index=False)

    progress(f'\nSaved: {p_csv}')
    progress(f'Saved: {i_csv}')
    progress(f'  {len(rows_P)} configs  |  R_convergence1=Max, '
             f'R_convergence2=95th pct, R_convergence3=Eq. area')

    return {'pressure_csv': p_csv, 'impulse_csv': i_csv, 'n_configs': len(rows_P)}


def cli(argv=None):
    p = argparse.ArgumentParser(description='Compare convergence-radius definitions.')
    p.add_argument('config_name', nargs='?', default=None,
                   help='Config to render figures for (all configs go into the CSVs).')
    p.add_argument('--npz-dir', default=None, help='Folder of config_*.npz files.')
    p.add_argument('--out-dir', default=None, help='Output folder.')
    args = p.parse_args(argv)

    config_name = args.config_name
    if config_name is None:
        # isatty() alone is not reliable — some non-interactive launchers
        # report a tty but deliver EOF on the first read.
        config_name = None
        if sys.stdin is not None and sys.stdin.isatty():
            try:
                config_name = input('Enter config name (for figures): ').strip()
            except (EOFError, KeyboardInterrupt):
                print()
                config_name = None
        if not config_name:
            p.error('config_name is required when running non-interactively.')

    return main(config_name, npz_dir=args.npz_dir, out_dir=args.out_dir)


if __name__ == '__main__':
    cli()
