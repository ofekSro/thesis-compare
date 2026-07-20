"""Theta-angle histogram plots for per-angle convergence radii.

plot_theta_histogram   : two-panel figure (P left, I right) for a single config.
plot_theta_histogram_Z : 4x5 grid of bar charts (one per Z=1..20) for max_radius_per_Z.
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

THETA_DEG = np.arange(0, 91, dtype=float)  # 0, 1, ..., 90


def plot_theta_histogram(config_name, r_theta_P, r_theta_I, req_P, req_I,
                         theta_centers_deg, fig_folder):
    """Bar charts of per-theta convergence radius — pressure (left) and impulse (right).

    Parameters
    ----------
    config_name       : str
    r_theta_P         : array(91,) — per-theta convergence radius, pressure [m]
    r_theta_I         : array(91,) — per-theta convergence radius, impulse [m]
    req_P             : float — equivalent area radius, pressure [m]
    req_I             : float — equivalent area radius, impulse [m]
    theta_centers_deg : array(91,) — theta bin centres in degrees (0..90)
    fig_folder        : str — output directory (must already exist)
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(config_name, fontsize=13)

    for ax, r_theta, req, color, title_suffix, ylabel in (
        (ax1, r_theta_P, req_P, 'steelblue',  'Pressure', 'Radius [m]'),
        (ax2, r_theta_I, req_I, 'darkorange', 'Impulse',  'Radius [m]'),
    ):
        heights = np.nan_to_num(r_theta, nan=0.0)
        ax.bar(theta_centers_deg, heights, width=0.8, color=color, edgecolor='none')

        if not np.isnan(req):
            ax.axhline(req, color='red', linestyle='--', linewidth=1.5,
                       label=f'Req = {req:.1f} m')
            ax.legend(fontsize=9)

        ax.set_xlabel('θ [deg]')
        ax.set_ylabel(ylabel)
        ax.set_title(f'{config_name} — {title_suffix}', fontsize=11)
        ax.set_xlim(-1, 91)
        ax.set_xticks([0, 15, 30, 45, 60, 75, 90])

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(fig_folder, f'{config_name}_theta.png'),
                dpi=100, bbox_inches='tight')
    plt.close(fig)


def plot_theta_histogram_Z(config_name, theta_radii_per_Z, req_per_Z,
                           quantity_label, fig_folder):
    """4×5 grid of bar charts (one per Z=1..20) showing per-theta radius.

    Parameters
    ----------
    config_name        : str
    theta_radii_per_Z  : dict {z_val (int): array(91,)} — per-theta radii
    req_per_Z          : dict {z_val (int): float} — scalar Req per Z
    quantity_label     : str — 'P' or 'I', used in title and filename
    fig_folder         : str — output directory (must already exist)
    """
    z_values = sorted(theta_radii_per_Z.keys())  # 1..20

    fig, axes = plt.subplots(4, 5, figsize=(22, 16))
    fig.suptitle(f'{config_name} — {"Pressure" if quantity_label == "P" else "Impulse"} '
                 f'theta radii per Z', fontsize=13)

    color = 'steelblue' if quantity_label == 'P' else 'darkorange'

    for idx, z_val in enumerate(z_values):
        row, col = divmod(idx, 5)
        ax = axes[row, col]

        r_theta = theta_radii_per_Z[z_val]
        req     = req_per_Z.get(z_val, np.nan)

        heights = np.nan_to_num(r_theta, nan=0.0)
        ax.bar(THETA_DEG, heights, width=0.8, color=color, edgecolor='none')

        if not np.isnan(req) and req > 0:
            ax.axhline(req, color='red', linestyle='--', linewidth=1.0)

        ax.set_title(f'Z = {z_val}', fontsize=8)
        ax.set_xticks([0, 30, 60, 90])
        ax.tick_params(labelsize=6)
        ax.set_xlabel('θ [deg]', fontsize=6)
        ax.set_ylabel('R [m]', fontsize=6)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(fig_folder, f'{config_name}_theta_Z_{quantity_label}.png'),
                dpi=100, bbox_inches='tight')
    plt.close(fig)
