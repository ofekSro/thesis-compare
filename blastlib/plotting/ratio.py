"""Create Figure 2: pressure and impulse ratio plots with convergence circle."""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from blastlib.plotting.common import bluewhitered, plot_layer, draw_quarter_circle
from blastlib.plotting.cuboids import draw_cuboids_gray
from blastlib.processing.radius_estimator import radius_label


def calculate_scale(data, cfg, scale_limits=None):
    """Calculate colour scale limits, excluding the near-blast zone.

    Parameters
    ----------
    scale_limits : None or dict
        None → auto scale (95th percentile of |ratio - 1| outside the
        near-blast zone). Manual → {'P': (lo, hi), 'I': (lo, hi)}.
    """
    if scale_limits is not None:
        return list(scale_limits['P']), list(scale_limits['I'])

    ratioP1 = data['ratioP1'].copy()
    ratioP2 = data['ratioP2'].copy()
    ratioP3 = data['ratioP3'].copy()
    ratioI1 = data['ratioI1'].copy()
    ratioI2 = data['ratioI2'].copy()
    ratioI3 = data['ratioI3'].copy()

    if cfg['det'] == 1:
        ex_x = cfg['bsize'] / 2
        ex_z = cfg['swidth'] / 2
        for rP, rI, X, Z in (
            (ratioP1, ratioI1, data['X1'], data['Z1']),
            (ratioP2, ratioI2, data['X2'], data['Z2']),
            (ratioP3, ratioI3, data['X3'], data['Z3']),
        ):
            mask = (X <= ex_x) & (Z <= ex_z)
            rP[mask] = np.nan
            rI[mask] = np.nan
    else:
        ex_r = cfg['swidth'] / 2
        for rP, rI, X, Z in (
            (ratioP1, ratioI1, data['X1'], data['Z1']),
            (ratioP2, ratioI2, data['X2'], data['Z2']),
            (ratioP3, ratioI3, data['X3'], data['Z3']),
        ):
            dist = np.sqrt(X ** 2 + Z ** 2)
            rP[dist <= ex_r] = np.nan
            rI[dist <= ex_r] = np.nan

    all_rP = np.concatenate([ratioP1.ravel(), ratioP2.ravel(), ratioP3.ravel()])
    all_rI = np.concatenate([ratioI1.ravel(), ratioI2.ravel(), ratioI3.ravel()])

    max_rP = float(np.nanpercentile(np.abs(all_rP - 1), 95))
    max_rI = float(np.nanpercentile(np.abs(all_rI - 1), 95))

    if np.isnan(max_rP) or max_rP < 0.05:
        max_rP = 0.5
    if np.isnan(max_rI) or max_rI < 0.05:
        max_rI = 0.5

    scale_P = [1 - max_rP, 1 + max_rP]
    scale_I = [1 - max_rI, 1 + max_rI]

    return scale_P, scale_I


def plot_ratio(data, cfg, config_name, fig_folder, radius, scale_limits=None,
               method='req'):
    """Save Figure 2 with pressure and impulse ratio plots.

    Parameters
    ----------
    data         : dict returned by process_grids
    cfg          : dict from config_parser
    config_name  : str
    fig_folder   : output directory
    radius       : dict from find_convergence_radius
    scale_limits : None (auto) or {'P': (lo, hi), 'I': (lo, hi)} (manual)
    method       : str — radius-estimator token, used in the panel titles
    """
    label = radius_label(method)
    axis_limit = max(radius['pressure'], radius['impulse']) + 15
    scale_P, scale_I = calculate_scale(data, cfg, scale_limits)

    cmap = bluewhitered()
    norm_P = mcolors.Normalize(vmin=scale_P[0], vmax=scale_P[1])
    norm_I = mcolors.Normalize(vmin=scale_I[0], vmax=scale_I[1])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(config_name, fontsize=14)

    # ---- Pressure ratio ----
    ax1.set_facecolor('white')
    plot_layer(ax1, data['X3'], data['Z3'], data['ratioP3'], cmap, norm_P)
    plot_layer(ax1, data['X2'], data['Z2'], data['ratioP2'], cmap, norm_P)
    plot_layer(ax1, data['X1'], data['Z1'], data['ratioP1'], cmap, norm_P)

    ax1.set_xlim(0, axis_limit)
    ax1.set_ylim(0, axis_limit)
    ax1.set_aspect('equal')
    sm_P = plt.cm.ScalarMappable(cmap=cmap, norm=norm_P)
    sm_P.set_array([])
    fig.colorbar(sm_P, ax=ax1)
    ax1.set_title(f'P / P_ref  ({label} = {radius["pressure"]:.1f} m)')
    ax1.set_xlabel('X [m]')
    ax1.set_ylabel('Z [m]')
    draw_cuboids_gray(ax1, config_name)
    draw_quarter_circle(ax1, radius['pressure'], color='black', linewidth=2)

    # ---- Impulse ratio ----
    ax2.set_facecolor('white')
    plot_layer(ax2, data['X3'], data['Z3'], data['ratioI3'], cmap, norm_I)
    plot_layer(ax2, data['X2'], data['Z2'], data['ratioI2'], cmap, norm_I)
    plot_layer(ax2, data['X1'], data['Z1'], data['ratioI1'], cmap, norm_I)

    ax2.set_xlim(0, axis_limit)
    ax2.set_ylim(0, axis_limit)
    ax2.set_aspect('equal')
    sm_I = plt.cm.ScalarMappable(cmap=cmap, norm=norm_I)
    sm_I.set_array([])
    fig.colorbar(sm_I, ax=ax2)
    ax2.set_title(f'I / I_ref  ({label} = {radius["impulse"]:.1f} m)')
    ax2.set_xlabel('X [m]')
    ax2.set_ylabel('Z [m]')
    draw_cuboids_gray(ax2, config_name)
    draw_quarter_circle(ax2, radius['impulse'], color='black', linewidth=2)

    out_path = os.path.join(str(fig_folder), f'{config_name}_ratio.png')
    fig.savefig(out_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
