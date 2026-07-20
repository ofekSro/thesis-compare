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

from draw_cuboids_gray import draw_cuboids_gray


def _plot_layer_maxR(ax, X, Z, data, norm, cmap):
    """Plot a single merged-grid layer using pcolormesh (same as plot_absolute)."""
    masked = np.ma.masked_invalid(data)
    ax.pcolormesh(X, Z, masked, shading='nearest', cmap=cmap, norm=norm)


def _draw_quarter_circle(ax, r, color, linewidth=1.5, label=None):
    """Draw a dashed quarter-circle arc at radius *r* on the given axes.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes.
    r : float
        Radius of the quarter-circle. Skipped if NaN or non-positive.
    color : array-like
        Line color.
    linewidth : float
        Line width (default 1.5).
    label : str or None
        If provided, place a text label at 45 degrees on the arc.
    """
    if np.isnan(r) or r <= 0:
        return
    theta = np.linspace(0, np.pi / 2, 100)
    ax.plot(r * np.cos(theta), r * np.sin(theta), '--',
            color=color, linewidth=linewidth)
    if label is not None:
        x_txt = r * np.cos(np.pi / 4)
        y_txt = r * np.sin(np.pi / 4)
        ax.text(x_txt, y_txt, label, fontsize=6, fontweight='bold',
                color=color, ha='center', va='bottom',
                bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                          edgecolor='none', alpha=0.7))


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
        Convergence radius for pressure (95th-percentile).
    req_I : float
        Convergence radius for impulse (95th-percentile).
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
    _plot_layer_maxR(ax1, processed['X3'], processed['Z3'],
                     processed['peakP3_orig'], norm_P, cmap_field)
    _plot_layer_maxR(ax1, processed['X2'], processed['Z2'],
                     processed['peakP2_orig'], norm_P, cmap_field)
    _plot_layer_maxR(ax1, processed['X1'], processed['Z1'],
                     processed['peakP1_orig'], norm_P, cmap_field)
    draw_cuboids_gray(ax1, config_name)
    sm_P = plt.cm.ScalarMappable(cmap=cmap_field, norm=norm_P)
    sm_P.set_array([])
    fig.colorbar(sm_P, ax=ax1)

    for i, z_val in enumerate(z_values):
        r = maxR_P_per_Z[z_val]
        if not np.isnan(r) and r < req_P:
            _draw_quarter_circle(ax1, r, colors[i], label=f'Z={z_val}')
    _draw_quarter_circle(ax1, req_P, color='black', linewidth=3)
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
    _plot_layer_maxR(ax2, processed['X3'], processed['Z3'],
                     processed['impulse3_orig'], norm_I, cmap_field)
    _plot_layer_maxR(ax2, processed['X2'], processed['Z2'],
                     processed['impulse2_orig'], norm_I, cmap_field)
    _plot_layer_maxR(ax2, processed['X1'], processed['Z1'],
                     processed['impulse1_orig'], norm_I, cmap_field)
    draw_cuboids_gray(ax2, config_name)
    sm_I = plt.cm.ScalarMappable(cmap=cmap_field, norm=norm_I)
    sm_I.set_array([])
    fig.colorbar(sm_I, ax=ax2)

    for i, z_val in enumerate(z_values):
        r = maxR_I_per_Z[z_val]
        if not np.isnan(r) and r < req_I:
            _draw_quarter_circle(ax2, r, colors[i], label=f'Z={z_val}')
    _draw_quarter_circle(ax2, req_I, color='black', linewidth=3)
    ax2.legend(
        [plt.Line2D([0], [0], color='black', linestyle='--', linewidth=3)],
        ['Convergence Radius'],
        loc='upper right', fontsize=8,
    )
    ax2.set_xlim(0, lim_I); ax2.set_ylim(0, lim_I)
    ax2.set_aspect('equal')
    ax2.set_title('Peak Impulse [kPa\u00b7ms]')
    ax2.set_xlabel('X [m]'); ax2.set_ylabel('Z [m]')

    fig.savefig(os.path.join(fig_folder, f'{config_name}_maxR.png'),
                dpi=100, bbox_inches='tight')
    plt.close(fig)
