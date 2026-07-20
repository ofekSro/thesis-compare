"""Shared plotting helpers.

These existed as private near-duplicates in plot_absolute / plot_ratio /
plot_max_radius_fig in compare_v6; consolidated here once.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.colors as mcolors


def bluewhitered():
    """Blue-white-red diverging colormap (MATLAB bluewhitered equivalent)."""
    return mcolors.LinearSegmentedColormap.from_list(
        'bluewhitered', [(0, 'blue'), (0.5, 'white'), (1, 'red')]
    )


def plot_layer(ax, X, Z, data, cmap, norm):
    """Plot one grid layer with pcolormesh; NaN cells are transparent."""
    masked = np.ma.masked_invalid(data)
    ax.pcolormesh(X, Z, masked, shading='nearest', cmap=cmap, norm=norm)


def draw_quarter_circle(ax, r, color='black', linewidth=1.5, label=None):
    """Draw a dashed quarter-circle arc at radius *r* on the given axes.

    Skipped if r is NaN or non-positive. If *label* is given, place a small
    text label at 45 degrees on the arc.
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


def draw_convergence_polyline(ax, theta_centers, radii):
    """Draw solid black polyline connecting per-theta convergence radii."""
    valid = ~np.isnan(radii)
    if not np.any(valid):
        return
    th = theta_centers[valid]
    r = radii[valid]
    x = r * np.cos(th)
    z = r * np.sin(th)
    ax.plot(x, z, 'k-', linewidth=1.5)
