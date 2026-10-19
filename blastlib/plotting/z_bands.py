"""Draw the Z-band map of one configuration (processing/z_bands.compute output).

One panel per load: categorical colours per cell, building footprints, quarter
circles of R_conv and of MaxR for every drawn band, and a legend per panel.
"""

import numpy as np
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from blastlib.plotting.common import plot_layer
from blastlib.plotting.cuboids import draw_cuboids_gray

TITLES = {'P': 'Peak pressure', 'I': 'Impulse'}


def default_band_colors(n):
    """n colours, strongest band (smallest Z) darkest: one hue, dark to light."""
    from matplotlib.colors import LinearSegmentedColormap
    # light end kept dark enough for the dashed MaxR arc to read on white
    cmap = LinearSegmentedColormap.from_list('zb', ['#0d366b', '#2a78d6', '#6da7ec'])
    return [cmap(i / max(n - 1, 1)) for i in range(n)]


def _arc(ax, r, **kw):
    if r is None or not np.isfinite(r) or r <= 0:
        return
    a = np.linspace(0, np.pi / 2, 200)
    ax.plot(r * np.cos(a), r * np.sin(a), **kw)


def draw_z_bands(fig, result, config_name, panels=('P', 'I'), band_colors=None,
                 below_color='#f4b183', building_color='#8f8e89', axis_limit=None,
                 method='', compact=False):
    """Draw *result* (z_bands.compute) into *fig*; returns the axis limit used.

    band_colors : {Z: colour} for the listed Z (missing ones get a default).
    compact     : narrow canvas — one legend column, smaller font.
    """
    keys = [p for p in panels if p in result] or ['P']
    if axis_limit is None:
        r = [result[k]['r_conv'] for k in keys] + [v for k in keys for v in result[k]['maxr'].values()]
        r = [x for x in r if np.isfinite(x)]
        axis_limit = (max(r) + 15) if r else 50.0
    fig.clear()
    axes = fig.subplots(1, len(keys), squeeze=False)[0]
    fig.suptitle(f'{config_name}  —  Z bands ({method})', fontsize=12)
    for ax, k in zip(axes, keys):
        res = result[k]
        zs = res['z_shown']
        defaults = default_band_colors(len(zs))
        cols = [(band_colors or {}).get(z, defaults[i]) for i, z in enumerate(zs)]
        cmap = ListedColormap(cols + [below_color, 'white'])
        norm = BoundaryNorm(np.arange(-0.5, len(zs) + 2.5), cmap.N)
        ax.set_facecolor('white')
        for X, Z, cat in res['layers']:          # coarse to fine
            plot_layer(ax, X, Z, cat, cmap, norm)
        n_before = len(ax.patches)
        draw_cuboids_gray(ax, config_name)
        for p in ax.patches[n_before:]:
            p.set_facecolor(building_color)
        _arc(ax, res['r_conv'], color='black', lw=2.0)
        _arc(ax, res.get('r_min'), color='black', lw=1.2, ls=':')
        for i, z in enumerate(zs):
            _arc(ax, res['maxr'].get(z), color=cols[i], lw=1.4, ls='--')
        ax.set_xlim(0, axis_limit)
        ax.set_ylim(0, axis_limit)
        ax.set_aspect('equal')
        ax.set_xlabel('X [m]')
        ax.set_ylabel('Z [m]')
        cut = res['z_cut']
        ax.set_title(f"{TITLES[k]}: bands cut at Z = {cut}" if cut is not None
                     else f'{TITLES[k]}: no listed Z has MaxR inside R_conv', fontsize=10)

        unit = 'kPa' if k == 'P' else 'Pa·s'
        h = [Patch(facecolor=c, edgecolor='none',
                   label=f'Z = {z}  (L ≈ {res["level"][z]:.3g} {unit})') for z, c in zip(zs, cols)]
        h.append(Patch(facecolor=below_color, edgecolor='none',
                       label=(f'weaker than Z = {cut}, inside R_conv' if cut is not None
                              else 'inside R_conv, no band')))
        h.append(Patch(facecolor='white', edgecolor='#999999', label='no band, beyond R_conv'))
        h.append(Patch(facecolor=building_color, edgecolor='none', label='building'))
        h.append(Line2D([], [], color='black', lw=2.0, label=f'R_conv = {res["r_conv"]:.1f} m'))
        if res.get('r_min') is not None:
            h.append(Line2D([], [], color='black', lw=1.2, ls=':',
                            label=f'Z_urban domain from R = {res["r_min"]:.1f} m'))
        raw = ' (raw reach)' if res['maxr_raw'] else ''
        for i, z in enumerate(zs):
            if z in res['maxr']:
                h.append(Line2D([], [], color=cols[i], lw=1.4, ls='--',
                                label=f'MaxR(Z={z}){raw} = {res["maxr"][z]:.1f} m'))
        # below the map: the panels keep the full width (QA 2026-10-19 F3)
        ax.legend(handles=h, fontsize=5.5 if compact else 7, loc='upper center',
                  bbox_to_anchor=(0.5, -0.12), ncol=1 if compact else 2,
                  borderaxespad=0, framealpha=0.95, edgecolor='gray')
    return axis_limit
