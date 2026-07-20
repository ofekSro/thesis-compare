"""Plot Figure 1: absolute peak pressure and impulse."""

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from blastlib.plotting.common import plot_layer
from blastlib.plotting.cuboids import draw_cuboids_gray


def plot_absolute(data, config_name, fig_folder):
    """Save Figure 1 with absolute pressure and impulse plots.

    Parameters
    ----------
    data        : dict returned by process_grids (contains X1..X3, Z1..Z3,
                  peakP1_orig..peakP3_orig, impulse1_orig..impulse3_orig,
                  maxP, maxI)
    config_name : str
    fig_folder  : output directory
    """
    cmap = 'jet'

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(config_name, fontsize=14)

    # ---- Pressure ----
    ax1.set_facecolor('white')
    norm_P = mcolors.Normalize(vmin=0, vmax=data['maxP'])

    plot_layer(ax1, data['X3'], data['Z3'], data['peakP3_orig'], cmap, norm_P)
    plot_layer(ax1, data['X2'], data['Z2'], data['peakP2_orig'], cmap, norm_P)
    plot_layer(ax1, data['X1'], data['Z1'], data['peakP1_orig'], cmap, norm_P)

    ax1.set_xlim(0, 500)
    ax1.set_ylim(0, 500)
    ax1.set_aspect('equal')
    sm_P = plt.cm.ScalarMappable(cmap=cmap, norm=norm_P)
    sm_P.set_array([])
    fig.colorbar(sm_P, ax=ax1)
    ax1.set_title('Peak Pressure [kPa]')
    ax1.set_xlabel('X [m]')
    ax1.set_ylabel('Z [m]')
    draw_cuboids_gray(ax1, config_name)

    # ---- Impulse ----
    ax2.set_facecolor('white')
    norm_I = mcolors.Normalize(vmin=0, vmax=data['maxI'])

    plot_layer(ax2, data['X3'], data['Z3'], data['impulse3_orig'], cmap, norm_I)
    plot_layer(ax2, data['X2'], data['Z2'], data['impulse2_orig'], cmap, norm_I)
    plot_layer(ax2, data['X1'], data['Z1'], data['impulse1_orig'], cmap, norm_I)

    ax2.set_xlim(0, 500)
    ax2.set_ylim(0, 500)
    ax2.set_aspect('equal')
    sm_I = plt.cm.ScalarMappable(cmap=cmap, norm=norm_I)
    sm_I.set_array([])
    fig.colorbar(sm_I, ax=ax2)
    ax2.set_title('Peak Impulse [kPa·ms]')
    ax2.set_xlabel('X [m]')
    ax2.set_ylabel('Z [m]')
    draw_cuboids_gray(ax2, config_name)

    out_path = os.path.join(str(fig_folder), f'{config_name}.png')
    fig.savefig(out_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
