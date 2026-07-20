"""Compare 3 convergence-radius definitions for a single configuration.

For one config (asked at runtime), this computes the convergence radius in
three different ways from the per-theta radii produced by
find_convergence_radius, and draws ratio plots (like Figures_Ratio) with the
matching convergence circle for each method:

    1. max        - maximum of the per-theta radii
    2. p95        - 95th percentile of the per-theta radii
    3. eq_area    - equivalent area radius (the current method)

Output (in Figures_Radius_Methods/):
    <config>_pressure_methods.png  - 3 panels (max / p95 / eq_area), P / P_ref
    <config>_impulse_methods.png   - 3 panels (max / p95 / eq_area), I / I_ref
"""

import os
import glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from config_parser import config_parser
from save_data_file import load_processed_data
from find_convergence_radius import (find_convergence_radius,
                                     _equivalent_area_radius)
from draw_cuboids_gray import draw_cuboids_gray
from constants import PARAMS
from plot_ratio import (_bluewhitered, _plot_layer, _draw_convergence_circle,
                        _draw_convergence_polyline, _calculate_scale)


# Per-theta angular spacing used by find_convergence_radius (1 degree)
DELTA_THETA = np.radians(1.0)


def _summary_radii(radii):
    """Return all three radius definitions for one per-theta radius array.

    Computed independently of find_convergence_radius's METHOD switch, so this
    comparison tool always reports max / p95 / eq_area.

    radii : array of per-theta convergence radii (may contain NaN)
    Returns dict {'max', 'p95', 'eq_area'}.
    """
    valid = ~np.isnan(radii)
    if not np.any(valid):
        return {'max': np.nan, 'p95': np.nan, 'eq_area': np.nan}
    return {
        'max': float(np.nanmax(radii)),
        'p95': float(np.nanpercentile(radii[valid], 95)),
        'eq_area': _equivalent_area_radius(radii, DELTA_THETA),
    }


_PANEL_LABELS  = ['(a)', '(b)', '(c)', '(d)']
_METHOD_NAMES  = {
    'Max':      'Maximum',
    '95th pct': '95th Percentile',
    'Eq. area': 'Equivalent Area',
}


def _config_title(cfg):
    """Human-readable geometry string for figure suptitle."""
    det_str = 'Street detonation' if cfg['det'] == 1 else 'Intersection detonation'
    return (f'b = {cfg["bsize"]} m,  s = {cfg["swidth"]} m,  '
            f'H = {cfg["height"]} m,  W = {cfg["weight"]} kg TNT  —  {det_str}')


def _plot_quantity(layers, cfg, config_name, theta_centers, radii_per_theta,
                   methods, cmap, norm, quantity_label, out_path):
    """Draw one combined figure (3 method-panels) for a single quantity.

    layers          : list of (X, Z, ratio) triples, far-to-near order
    methods         : list of (name, radius_value) tuples, one per panel
    quantity_label  : 'P / P_ref' or 'I / I_ref'
    """
    radii_vals = [r for _, r in methods if not np.isnan(r)]
    axis_limit = (max(radii_vals) if radii_vals else 10) + 15
    n = len(methods)

    fig, axes = plt.subplots(1, n, figsize=(7 * n, 6),
                             constrained_layout=True)
    if n == 1:
        axes = [axes]

    fig.suptitle(_config_title(cfg), fontsize=13, fontweight='bold')

    for idx, (ax, (name, r)) in enumerate(zip(axes, methods)):
        ax.set_facecolor('white')
        for X, Z, ratio in layers:
            _plot_layer(ax, X, Z, ratio, cmap, norm)

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
        h_poly = ax.plot([], [], 'k-',  linewidth=1.5,
                         label='Per-θ boundary')[0]
        h_circ = ax.plot([], [], 'k--', linewidth=2,
                         label='Convergence radius')[0]

        _draw_convergence_polyline(ax, theta_centers, radii_per_theta)
        _draw_convergence_circle(ax, r)

        # Panel label + full method name + radius value
        full_name = _METHOD_NAMES.get(name, name)
        r_str = f'{r:.1f} m' if not np.isnan(r) else 'n/a'
        ax.set_title(f'{_PANEL_LABELS[idx]}  {full_name}\nR = {r_str}',
                     fontsize=12, loc='left', pad=8)

        # Legend only on the first panel
        if idx == 0:
            ax.legend(handles=[h_poly, h_circ], fontsize=10,
                      loc='upper right', framealpha=0.85,
                      edgecolor='gray')

    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved: {out_path}')


def _compute_radius(mat_folder, config_name):
    """Load a config's processed grids and compute its convergence radius.

    Returns (cfg, processed, radius) or None on parse/load failure.
    """
    cfg = config_parser(config_name)
    if cfg is None:
        return None

    processed, success = load_processed_data(mat_folder, config_name)
    if not success:
        return None

    # Exclusion radius around blast source (same rule as main_ff_compare.py)
    if cfg['det'] == 1:
        exclude_r = np.sqrt((cfg['bsize'] / 2) ** 2 + (cfg['swidth'] / 2) ** 2)
    else:
        exclude_r = cfg['swidth'] / 2

    all_ratio_P = np.concatenate([processed['ratioP1'].ravel(),
                                  processed['ratioP2'].ravel(),
                                  processed['ratioP3'].ravel()])
    all_ratio_I = np.concatenate([processed['ratioI1'].ravel(),
                                  processed['ratioI2'].ravel(),
                                  processed['ratioI3'].ravel()])
    all_X = np.concatenate([processed['X1'].ravel(),
                            processed['X2'].ravel(),
                            processed['X3'].ravel()])
    all_Z = np.concatenate([processed['Z1'].ravel(),
                            processed['Z2'].ravel(),
                            processed['Z3'].ravel()])

    radius = find_convergence_radius(
        all_ratio_P, all_ratio_I,
        processed['peakP_all'], processed['peakI_all'],
        all_X, all_Z, exclude_r
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
                 params, out_folder):
    """Save the two combined method-comparison figures for one config."""
    scale_P, scale_I = _calculate_scale(processed, cfg, params)
    cmap = _bluewhitered()
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
        os.path.join(out_folder, f'{config_name}_pressure_methods.png'))
    _plot_quantity(
        layers_I, cfg, config_name, radius['theta_centers'],
        radius['radius_per_theta_I'], methods_I, cmap, norm_I, 'I / I_ref',
        os.path.join(out_folder, f'{config_name}_impulse_methods.png'))


def main():
    work_folder = os.path.dirname(os.path.abspath(__file__))
    mat_folder  = os.path.join(work_folder, 'MAT_files')
    out_folder  = os.path.join(work_folder, 'Figures_Radius_Methods')
    os.makedirs(out_folder, exist_ok=True)

    params = dict(PARAMS)
    params['useManualScale'] = False

    config_name = input('Enter config name (for figures): ').strip()
    if not config_name:
        print('No config name given.')
        return

    # Discover all configs in MAT_files for the comparison CSVs
    npz_files = sorted(glob.glob(os.path.join(mat_folder, 'config_*.npz')))
    all_configs = [os.path.splitext(os.path.basename(f))[0] for f in npz_files]
    if not all_configs:
        print(f'No .npz files found in {mat_folder}. Run create_mat_files.py first.')
        return

    print(f'Computing convergence radii for {len(all_configs)} configs...')

    rows_P = []
    rows_I = []
    plotted = False

    for name in all_configs:
        result = _compute_radius(mat_folder, name)
        if result is None:
            print(f'  Skipping {name} (parse/load failed)')
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

        # Figures only for the config entered at the prompt
        if name == config_name:
            print(f'\nConvergence radius for {name}:')
            print(f'  Pressure  - max={methods_P[0][1]:.2f}  '
                  f'p95={methods_P[1][1]:.2f}  eq_area={methods_P[2][1]:.2f} m')
            print(f'  Impulse   - max={methods_I[0][1]:.2f}  '
                  f'p95={methods_I[1][1]:.2f}  eq_area={methods_I[2][1]:.2f} m')
            _plot_config(processed, cfg, name, radius, methods_P, methods_I,
                         params, out_folder)
            plotted = True

    if not plotted:
        print(f'\nWarning: no figures produced -- "{config_name}" not found '
              f'in MAT_files.')

    # ---- Save comparison CSVs (R_convergence1=Max, 2=95th pct, 3=Eq. area) ----
    cols = ['ConfigName', 'R_convergence1', 'R_convergence2', 'R_convergence3']
    p_csv = os.path.join(out_folder, 'pressure_radius_methods.csv')
    i_csv = os.path.join(out_folder, 'impulse_radius_methods.csv')
    pd.DataFrame(rows_P, columns=cols).to_csv(p_csv, index=False)
    pd.DataFrame(rows_I, columns=cols).to_csv(i_csv, index=False)

    print(f'\nSaved: {p_csv}')
    print(f'Saved: {i_csv}')
    print(f'  {len(rows_P)} configs  |  R_convergence1=Max, '
          f'R_convergence2=95th pct, R_convergence3=Eq. area')


if __name__ == '__main__':
    main()
