"""Compare 4 convergence-radius definitions for a single configuration.

For one config, this computes the convergence radius in four different ways
and draws ratio plots (like the pipeline's ratio figures) with the matching
convergence circle for each method:

    1. max      - maximum of the per-theta radii             (hard criterion)
    2. p95      - 95th percentile of the per-theta radii     (hard criterion)
    3. eq_area  - equivalent-area radius                     (hard criterion)
    4. eq_soft  - equivalent-area radius of per-theta radii measured under
                  the SOFT tanh pressure criterion at beta (the production
                  estimator, 'req_soft3'; see processing/soft_criterion.py)

Methods 1-3 share the per-theta radii of the hard +-10 kPa band; method 4
re-scans the PRESSURE sectors with the soft weights exactly as run_analysis
does, then collapses with the same equivalent-area formula as method 3. The
soft criterion leaves the impulse criterion untouched, so for impulse the
radii of (c) and (d) coincide -- the impulse figure still shows all four
panels so the two quantities read the same way.

Output (in outputs/figures/radius_methods/):
    <config>_pressure_methods.png/.pdf - 2x2 panels (a)-(d), P / P_ref
    <config>_impulse_methods.png/.pdf  - 2x2 panels (a)-(d), I / I_ref
    pressure_radius_methods.csv        - all configs, all 4 methods
    impulse_radius_methods.csv

Usage:
    python tools\\radius_methods\\radius_methods.py                    # prompts
    python tools\\radius_methods\\radius_methods.py config_01_det1_b15_s5_h4_w50
    python tools\\radius_methods\\radius_methods.py config_01_... --soft-beta 0
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

from blastlib import constants, paths
from blastlib.config.parser import config_parser
from blastlib.geometry import exclude_radius, concat3
from blastlib.io.npz_store import load_processed_data
from blastlib.processing.convergence import (find_convergence_radius,
                                             equivalent_area_radius)
from blastlib.processing.soft_criterion import (soft_pressure_fields,
                                                soft_pressure_weights)
from blastlib.plotting.common import (bluewhitered, plot_layer,
                                      draw_quarter_circle,
                                      draw_convergence_polyline)
from blastlib.plotting.cuboids import draw_cuboids_gray
from blastlib.plotting.ratio import calculate_scale


# Per-theta angular spacing used by find_convergence_radius (1 degree)
DELTA_THETA = np.radians(1.0)

_PANEL_LABELS = ['(a)', '(b)', '(c)', '(d)']

# Figure typography (thesis figures) -- applied through plt.rc_context so the
# rest of the process keeps matplotlib's defaults.
_RC = {
    'font.size':        11,
    'axes.titlesize':   12,
    'axes.labelsize':   12,
    'xtick.labelsize':  10,
    'ytick.labelsize':  10,
    'legend.fontsize':  10,
    'figure.titlesize': 14,
    'axes.linewidth':   0.8,
}

# Written names of the quantities, in mathtext
_QUANTITY_LABEL = {'P': r'$P\,/\,P_{\mathrm{ref}}$',
                   'I': r'$I\,/\,I_{\mathrm{ref}}$'}


def _summary_radii(radii):
    """Return the three hard-criterion collapses of one per-theta array.

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
    """Human-readable geometry string for the figure suptitle."""
    det_str = 'Street detonation' if cfg['det'] == 1 else 'Intersection detonation'
    return (f'$b$ = {cfg["bsize"]} m,   $s$ = {cfg["swidth"]} m,   '
            f'$H$ = {cfg["height"]} m,   $W$ = {cfg["weight"]} kg TNT'
            f'   —   {det_str}')


def _plot_quantity(layers, cfg, config_name, methods, cmap, norm, quantity,
                   out_stem, progress=print):
    """Draw one combined figure (one panel per method) for a single quantity.

    layers   : list of (X, Z, ratio) triples, far-to-near order
    methods  : list of method dicts (see _methods), one per panel
    quantity : 'P' or 'I'
    out_stem : output path without extension (.png and .pdf are written)
    """
    radii_vals = [m['radius'] for m in methods if not np.isnan(m['radius'])]
    axis_limit = (max(radii_vals) if radii_vals else 10) + 15
    n = len(methods)
    ncols = 2 if n == 4 else n
    nrows = 2 if n == 4 else 1

    with plt.rc_context(_RC):
        fig, axes = plt.subplots(nrows, ncols,
                                 figsize=(6.0 * ncols + 1.2, 5.6 * nrows + 0.6),
                                 constrained_layout=True)
        axes = np.atleast_1d(axes).ravel()

        fig.suptitle(_config_title(cfg), fontweight='bold')

        h_poly = h_circ = None
        for idx, (ax, m) in enumerate(zip(axes, methods)):
            ax.set_facecolor('white')
            for X, Z, ratio in layers:
                plot_layer(ax, X, Z, ratio, cmap, norm)
            # Rasterise the colour field only (lines/text stay vector), so
            # the PDF is small and quick to write.
            for coll in ax.collections:
                coll.set_rasterized(True)

            ax.set_xlim(0, axis_limit)
            ax.set_ylim(0, axis_limit)
            ax.set_aspect('equal')
            row, col = divmod(idx, ncols)
            if row == nrows - 1:
                ax.set_xlabel('$x$ [m]')
            if col == 0:
                ax.set_ylabel('$z$ [m]')

            draw_cuboids_gray(ax, config_name)

            # Dummy handles for the legend (actual lines drawn by the helpers)
            h_poly = ax.plot([], [], 'k-', linewidth=1.2,
                             label=r'Per-$\theta$ convergence boundary')[0]
            h_circ = ax.plot([], [], 'k--', linewidth=1.8,
                             label='Collapsed radius $R$')[0]

            draw_convergence_polyline(ax, m['theta_centers'], m['per_theta'])
            draw_quarter_circle(ax, m['radius'], color='black', linewidth=1.8)

            r = m['radius']
            r_str = f'{r:.1f} m' if not np.isnan(r) else 'n/a'
            ax.set_title(f'{_PANEL_LABELS[idx]}  {m["name"]}\n'
                         f'{m["symbol"]} = {r_str}', loc='left', pad=8)

        # One legend (first panel) and one shared colour bar for the figure
        axes[0].legend(handles=[h_poly, h_circ], loc='upper right',
                       framealpha=0.9, edgecolor='gray')
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cb = fig.colorbar(sm, ax=list(axes), shrink=0.85, pad=0.02,
                          aspect=30)
        cb.set_label(_QUANTITY_LABEL[quantity])

        if quantity == 'I' and any(m['key'] == 'eq_soft' for m in methods):
            # Below the axes (negative y); bbox_inches='tight' keeps it in.
            fig.text(0.5, -0.012,
                     'Note: the soft criterion applies to the pressure sectors '
                     'only; the impulse radii in (c) and (d) coincide.',
                     fontsize=10, style='italic', ha='center', va='top')

        for ext in ('png', 'pdf'):
            path = f'{out_stem}.{ext}'
            fig.savefig(path, dpi=300, bbox_inches='tight')
            progress(f'  Saved: {path}')
        plt.close(fig)


def _compute_radius(npz_dir, config_name, soft_beta, progress=print):
    """Load a config's processed grids and compute its convergence radii.

    Returns (cfg, processed, radius_hard, radius_soft) or None on parse/load
    failure. radius_soft is None when soft_beta is falsy or the NPZ lacks the
    raw band fields the soft criterion needs (a warning is printed once).
    """
    cfg = config_parser(config_name)
    if cfg is None:
        return None

    processed, success = load_processed_data(npz_dir, config_name)
    if not success:
        return None

    ratio_P = concat3(processed, 'ratioP{}')
    ratio_I = concat3(processed, 'ratioI{}')
    X = concat3(processed, 'X{}')
    Z = concat3(processed, 'Z{}')
    excl = exclude_radius(cfg)

    radius_hard = find_convergence_radius(
        ratio_P, ratio_I, processed['peakP_all'], processed['peakI_all'],
        X, Z, excl)

    radius_soft = None
    if soft_beta:
        try:
            soft_w_P = soft_pressure_weights(soft_pressure_fields(processed),
                                             soft_beta)
        except KeyError as e:
            if not _compute_radius.warned:
                progress(f'  Soft criterion unavailable -- {e}')
                progress('  Panel (d) will be omitted for every config.')
                _compute_radius.warned = True
        else:
            radius_soft = find_convergence_radius(
                ratio_P, ratio_I, processed['peakP_all'], processed['peakI_all'],
                X, Z, excl, soft_w_P=soft_w_P)
    return cfg, processed, radius_hard, radius_soft


_compute_radius.warned = False


def _methods(radius_hard, radius_soft, soft_beta):
    """Return (methods_P, methods_I): one list of method dicts per quantity.

    Each dict: key, name (panel title), symbol (mathtext), radius,
    per_theta (the per-theta radii the collapse was taken from) and
    theta_centers. Order matches the panels and the CSV columns:
        1 = max, 2 = p95, 3 = eq_area, 4 = eq_soft (only if available)
    """
    def build(per_theta_key):
        r_hard = radius_hard[per_theta_key]
        s = _summary_radii(r_hard)
        th = radius_hard['theta_centers']
        out = [
            dict(key='max', name='Maximum', symbol=r'$R_{\max}$',
                 radius=s['max'], per_theta=r_hard, theta_centers=th),
            dict(key='p95', name='95th percentile', symbol=r'$R_{95}$',
                 radius=s['p95'], per_theta=r_hard, theta_centers=th),
            dict(key='eq_area', name='Equivalent area, hard criterion',
                 symbol=r'$R_{\mathrm{eq}}$',
                 radius=s['eq_area'], per_theta=r_hard, theta_centers=th),
        ]
        if radius_soft is not None:
            r_soft = radius_soft[per_theta_key]
            out.append(dict(
                key='eq_soft',
                name=f'Equivalent area, soft criterion ($\\beta$ = {soft_beta:g})',
                symbol=r'$R_{\mathrm{eq}}^{\mathrm{soft}}$',
                radius=equivalent_area_radius(r_soft, DELTA_THETA),
                per_theta=r_soft, theta_centers=radius_soft['theta_centers']))
        return out

    return build('radius_per_theta_P'), build('radius_per_theta_I')


def _plot_config(processed, cfg, config_name, methods_P, methods_I,
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

    _plot_quantity(layers_P, cfg, config_name, methods_P, cmap, norm_P, 'P',
                   os.path.join(str(out_folder), f'{config_name}_pressure_methods'),
                   progress=progress)
    _plot_quantity(layers_I, cfg, config_name, methods_I, cmap, norm_I, 'I',
                   os.path.join(str(out_folder), f'{config_name}_impulse_methods'),
                   progress=progress)


def list_configs(npz_dir=None):
    """Return the sorted config names available in npz_dir (for a GUI dropdown)."""
    npz_dir = paths.resolve(npz_dir, paths.default_npz_dir())
    npz_files = sorted(glob.glob(os.path.join(str(npz_dir), 'config_*.npz')))
    return [os.path.splitext(os.path.basename(f))[0] for f in npz_files]


_CSV_COLS = ['ConfigName', 'R_convergence1', 'R_convergence2',
             'R_convergence3', 'R_convergence4']


def main(config_name, *, npz_dir=None, out_dir=None, soft_beta=None,
         progress=print):
    """Compare radius definitions across all configs; plot the named one.

    soft_beta : float or None
        tanh sharpness of the soft criterion for method 4. None takes
        constants.PARAMS['softBeta'] (production); 0 omits method 4.

    Returns dict with the two CSV paths and the row count, or None if no
    NPZ files were found.
    """
    npz_dir = paths.resolve(npz_dir, paths.default_npz_dir(soft=True))
    out_dir = paths.ensure_dir(paths.resolve(out_dir,
                                             paths.FIGURES_DIR / 'radius_methods'))
    if soft_beta is None:
        soft_beta = constants.PARAMS.get('softBeta') or 0.0
    soft_beta = float(soft_beta)
    _compute_radius.warned = False

    all_configs = list_configs(npz_dir)
    if not all_configs:
        progress(f'No .npz files found in {npz_dir}. Run run_preprocess.py first.')
        return None

    progress(f'Computing convergence radii for {len(all_configs)} configs'
             + (f' (soft beta = {soft_beta:g})...' if soft_beta else '...'))

    rows_P = []
    rows_I = []
    plotted = False

    def row(name, methods):
        r = {'ConfigName': name}
        for i, col in enumerate(_CSV_COLS[1:]):
            r[col] = methods[i]['radius'] if i < len(methods) else np.nan
        return r

    for name in all_configs:
        result = _compute_radius(npz_dir, name, soft_beta, progress=progress)
        if result is None:
            progress(f'  Skipping {name} (parse/load failed)')
            continue
        cfg, processed, radius_hard, radius_soft = result
        methods_P, methods_I = _methods(radius_hard, radius_soft, soft_beta)

        rows_P.append(row(name, methods_P))
        rows_I.append(row(name, methods_I))

        # Figures only for the requested config
        if name == config_name:
            progress(f'\nConvergence radius for {name}:')
            for label, methods in (('Pressure', methods_P), ('Impulse', methods_I)):
                progress(f'  {label:9s} - ' + '  '.join(
                    f'{m["key"]}={m["radius"]:.2f}' for m in methods) + ' m')
            _plot_config(processed, cfg, name, methods_P, methods_I,
                         out_dir, progress=progress)
            plotted = True

    if not plotted:
        progress(f'\nWarning: no figures produced -- "{config_name}" not found '
                 f'in {npz_dir}.')

    # ---- Save comparison CSVs ----
    p_csv = out_dir / 'pressure_radius_methods.csv'
    i_csv = out_dir / 'impulse_radius_methods.csv'
    pd.DataFrame(rows_P, columns=_CSV_COLS).to_csv(p_csv, index=False)
    pd.DataFrame(rows_I, columns=_CSV_COLS).to_csv(i_csv, index=False)

    progress(f'\nSaved: {p_csv}')
    progress(f'Saved: {i_csv}')
    progress(f'  {len(rows_P)} configs  |  R_convergence1=max, '
             f'R_convergence2=p95, R_convergence3=eq_area (hard), '
             f'R_convergence4=eq_area (soft, beta={soft_beta:g})')

    return {'pressure_csv': p_csv, 'impulse_csv': i_csv, 'n_configs': len(rows_P)}


def cli(argv=None):
    p = argparse.ArgumentParser(description='Compare convergence-radius definitions.')
    p.add_argument('config_name', nargs='?', default=None,
                   help='Config to render figures for (all configs go into the CSVs).')
    p.add_argument('--npz-dir', default=None, help='Folder of config_*.npz files.')
    p.add_argument('--out-dir', default=None, help='Output folder.')
    p.add_argument('--soft-beta', type=float, default=None, dest='soft_beta',
                   help='Soft-criterion beta for method 4 (default: '
                        f'constants.PARAMS softBeta = {constants.PARAMS["softBeta"]}; '
                        '0 omits the soft panel).')
    args = p.parse_args(argv)

    config_name = args.config_name
    if config_name is None:
        # isatty() alone is not reliable -- some non-interactive launchers
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

    return main(config_name, npz_dir=args.npz_dir, out_dir=args.out_dir,
                soft_beta=args.soft_beta)


if __name__ == '__main__':
    cli()
