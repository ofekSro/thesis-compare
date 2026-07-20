"""Plotting helpers for max-radius-per-Z figures.

Creates composite figures showing the merged absolute pressure/impulse fields
(pcolormesh background with per-field colorbar) with colored quarter-circle
overlays indicating the max radius at each scaled distance Z.
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from blastlib.plotting.common import plot_layer, draw_quarter_circle
from blastlib.plotting.cuboids import draw_cuboids_gray


def plot_max_radius(processed, config_name, maxR_P_per_Z, maxR_I_per_Z, req_P, req_I, fig_folder):
    """Save a figure with merged absolute fields and colored quarter-circles per Z.

    Parameters
    ----------
    processed : dict
        Output of ``process_grids`` containing coordinate arrays, peak fields,
        and scale limits (``maxP``, ``maxI``).
    config_name : str
        Configuration name (used for title and filename).
    maxR_P_per_Z : dict
        ``{Z_value: max_radius_pressure}`` mapping.
    maxR_I_per_Z : dict
        ``{Z_value: max_radius_impulse}`` mapping.
    req_P : float
        Convergence radius for pressure.
    req_I : float
        Convergence radius for impulse.
    fig_folder : str
        Directory to save the output PNG.
    """
    cmap_field = 'jet'
    z_values = sorted(maxR_P_per_Z.keys())
    n_z = len(z_values)
    colors = plt.cm.jet(np.linspace(0, 1, n_z))

    # Filter out Z values where maxR exceeds convergence radius
    valid_P = [maxR_P_per_Z[z] for z in z_values
               if not np.isnan(maxR_P_per_Z[z]) and maxR_P_per_Z[z] < req_P]
    valid_I = [maxR_I_per_Z[z] for z in z_values
               if not np.isnan(maxR_I_per_Z[z]) and maxR_I_per_Z[z] < req_I]

    # Dynamic axis limits: 15 m beyond the largest valid quarter-circle radius
    max_r_P = np.nanmax(valid_P) if valid_P else req_P
    max_r_I = np.nanmax(valid_I) if valid_I else req_I
    lim_P = (max_r_P + 15) if not np.isnan(max_r_P) else 500
    lim_I = (max_r_I + 15) if not np.isnan(max_r_I) else 500

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(config_name, fontsize=14)

    # ---- Pressure ----
    _all_P = np.concatenate([processed['peakP1_orig'].ravel(),
                             processed['peakP2_orig'].ravel(),
                             processed['peakP3_orig'].ravel()])
    vmax_P = float(np.nanpercentile(_all_P[np.isfinite(_all_P)], 99))
    ax1.set_facecolor('white')
    norm_P = mcolors.Normalize(vmin=0, vmax=vmax_P)
    plot_layer(ax1, processed['X3'], processed['Z3'],
               processed['peakP3_orig'], cmap_field, norm_P)
    plot_layer(ax1, processed['X2'], processed['Z2'],
               processed['peakP2_orig'], cmap_field, norm_P)
    plot_layer(ax1, processed['X1'], processed['Z1'],
               processed['peakP1_orig'], cmap_field, norm_P)
    draw_cuboids_gray(ax1, config_name)
    sm_P = plt.cm.ScalarMappable(cmap=cmap_field, norm=norm_P)
    sm_P.set_array([])
    fig.colorbar(sm_P, ax=ax1)

    for i, z_val in enumerate(z_values):
        r = maxR_P_per_Z[z_val]
        if not np.isnan(r) and r < req_P:
            draw_quarter_circle(ax1, r, colors[i], label=f'Z={z_val}')
    draw_quarter_circle(ax1, req_P, color='black', linewidth=3)
    ax1.legend(
        [plt.Line2D([0], [0], color='black', linestyle='--', linewidth=3)],
        ['Convergence Radius'],
        loc='upper right', fontsize=8,
    )
    ax1.set_xlim(0, lim_P); ax1.set_ylim(0, lim_P)
    ax1.set_aspect('equal')
    ax1.set_title('Peak Pressure [kPa]')
    ax1.set_xlabel('X [m]'); ax1.set_ylabel('Z [m]')

    # ---- Impulse ----
    _all_I = np.concatenate([processed['impulse1_orig'].ravel(),
                             processed['impulse2_orig'].ravel(),
                             processed['impulse3_orig'].ravel()])
    vmax_I = float(np.nanpercentile(_all_I[np.isfinite(_all_I)], 99))
    ax2.set_facecolor('white')
    norm_I = mcolors.Normalize(vmin=0, vmax=vmax_I)
    plot_layer(ax2, processed['X3'], processed['Z3'],
               processed['impulse3_orig'], cmap_field, norm_I)
    plot_layer(ax2, processed['X2'], processed['Z2'],
               processed['impulse2_orig'], cmap_field, norm_I)
    plot_layer(ax2, processed['X1'], processed['Z1'],
               processed['impulse1_orig'], cmap_field, norm_I)
    draw_cuboids_gray(ax2, config_name)
    sm_I = plt.cm.ScalarMappable(cmap=cmap_field, norm=norm_I)
    sm_I.set_array([])
    fig.colorbar(sm_I, ax=ax2)

    for i, z_val in enumerate(z_values):
        r = maxR_I_per_Z[z_val]
        if not np.isnan(r) and r < req_I:
            draw_quarter_circle(ax2, r, colors[i], label=f'Z={z_val}')
    draw_quarter_circle(ax2, req_I, color='black', linewidth=3)
    ax2.legend(
        [plt.Line2D([0], [0], color='black', linestyle='--', linewidth=3)],
        ['Convergence Radius'],
        loc='upper right', fontsize=8,
    )
    ax2.set_xlim(0, lim_I); ax2.set_ylim(0, lim_I)
    ax2.set_aspect('equal')
    ax2.set_title('Peak Impulse [kPa·ms]')
    ax2.set_xlabel('X [m]'); ax2.set_ylabel('Z [m]')

    fig.savefig(os.path.join(str(fig_folder), f'{config_name}_maxR.png'),
                dpi=100, bbox_inches='tight')
    plt.close(fig)
