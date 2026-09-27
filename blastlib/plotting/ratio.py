"""Create Figure 2: pressure and impulse ratio plots with convergence circle."""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from blastlib.plotting.common import (bluewhitered, plot_layer,
                                      draw_quarter_circle,
                                      draw_convergence_polyline)
from blastlib.plotting.cuboids import draw_cuboids_gray
from blastlib.processing.radius_estimator import radius_label


def calculate_scale(data, cfg, scale_limits=None, suffix=''):
    """Calculate colour scale limits, excluding the near-blast zone.

    Parameters
    ----------
    scale_limits : None or dict
        None → auto scale (95th percentile of |ratio - 1| outside the
        near-blast zone). Manual → {'P': (lo, hi), 'I': (lo, hi)}.
    suffix : str
        '' for the stored ratios, '_raw' for the pre-pinning ones. The auto
        scale has to be measured on whichever field is actually drawn: the
        stored field is pinned to exactly 1 over most of the domain, so its
        95th percentile is far tighter than the raw field's and would clip
        the raw view into solid colour.
    """
    if scale_limits is not None:
        return list(scale_limits['P']), list(scale_limits['I'])

    ratioP1 = data['ratioP1' + suffix].copy()
    ratioP2 = data['ratioP2' + suffix].copy()
    ratioP3 = data['ratioP3' + suffix].copy()
    ratioI1 = data['ratioI1' + suffix].copy()
    ratioI2 = data['ratioI2' + suffix].copy()
    ratioI3 = data['ratioI3' + suffix].copy()

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


# Which panels draw_ratio can show, and everything that differs between them.
# Pressure and impulse are the same picture over different arrays, so the panel
# bodies differ only by this table.
PANELS = {
    'P': dict(ratio_fmt='ratioP{}', radius_key='pressure', title='P / P_ref',
              theta_key='radius_per_theta_P', raw_fmt='ratioP{}_raw'),
    'I': dict(ratio_fmt='ratioI{}', radius_key='impulse',  title='I / I_ref',
              theta_key='radius_per_theta_I', raw_fmt='ratioI{}_raw'),
}


def draw_ratio(fig, data, cfg, config_name, radius, scale_limits=None,
               method='req', panels=('P', 'I'), show_radius=True,
               axis_limit=None, show_buildings=True, center_white=False,
               show_polyline=False, use_raw=False):
    """Draw the ratio map(s) into *fig* and return the axis limit used.

    Split out of plot_ratio so the batch run and the GUI preview share one
    drawing path: the batch caller saves the result, the GUI hands in the
    Figure behind an embedded canvas and redraws on every widget change.
    *fig* is cleared first, so one Figure can be reused across redraws.

    Parameters beyond plot_ratio's:

    panels        : which of PANELS to draw, in order. One entry gives a single
                    full-width panel rather than a half-empty row.
    show_radius   : draw the measured convergence radius as a quarter circle.
                    Off shows the raw ratio field with nothing overlaid on it,
                    which is the point of the toggle — the circle is an
                    *estimate* and hiding it lets you judge the field first.
    axis_limit    : half-width of the square axes in metres. None keeps the
                    batch rule (the larger radius + 15 m). Given explicitly it
                    is used as-is, so zooming does not depend on the radius
                    that may itself be switched off.
    show_buildings: draw the grey building footprints.
    center_white  : pin ratio 1 to the white midpoint of the colormap by
                    stretching the two sides of the scale independently.
                    Off (the batch default) the white lands on the midpoint of
                    the limits, which only coincides with 1 when they are
                    symmetric about it — as the auto scale always is. So this
                    changes nothing for auto limits and matters only for
                    manual ones, where the GUI turns it on and enforces the
                    limits straddle 1. The batch keeps it off so a saved
                    figure stays byte-comparable with the ones already on disk.
    show_polyline : draw the per-theta convergence boundary — the 91 per-angle
                    radii joined into a polyline, which is the raw frontier the
                    single radius collapses. Same overlay tools/radius_methods
                    draws, so the two read alike. Independent of show_radius:
                    together they show how much shape the collapse discards,
                    and the legend appears only once this is on so the batch
                    figures keep their current look.
    use_raw       : draw ratioP/I{g}_raw — the field as measured, before
                    process_grids forces it to exactly 1 wherever P is under
                    minPressure_kPa or within minPressure_kPa of the
                    reference. The stored field is pinned over most of the
                    domain, so the drawn map says far more about that rule
                    than about the flow; this shows what was actually there.
                    The radius and the per-theta boundary are NOT recomputed —
                    they still come from the pinned field, because that is
                    what the criterion runs on. That mismatch is the point:
                    it shows what the criterion discarded. Raises ValueError
                    on a v1 NPZ, which has no raw keys.
    """
    label = radius_label(method)
    if axis_limit is None:
        # NaN radii would poison max(); fall back to a fixed frame rather than
        # producing empty axes for a config whose radius did not resolve.
        finite = [radius[k] for k in ('pressure', 'impulse')
                  if not np.isnan(radius[k])]
        axis_limit = (max(finite) + 15) if finite else 50.0
    if use_raw and 'ratioP1_raw' not in data:
        raise ValueError(
            'this NPZ has no raw ratio fields (v1 store) — rebuild it with '
            'run_preprocess.py so ratioP/I{g}_raw are present, or turn the '
            'raw view off')

    suffix = '_raw' if use_raw else ''
    scale_P, scale_I = calculate_scale(data, cfg, scale_limits, suffix=suffix)
    scales = {'P': scale_P, 'I': scale_I}

    cmap = bluewhitered()

    keys = [p for p in panels if p in PANELS] or ['P']
    fig.clear()
    axes = fig.subplots(1, len(keys), squeeze=False)[0]
    # spell the raw view out on the figure itself: it is easy to mistake for
    # the normal one, and it means something quite different
    fig.suptitle(f'{config_name}  —  RAW (pre-pinning)'
                 if use_raw else config_name, fontsize=14)

    for ax, key in zip(axes, keys):
        spec = PANELS[key]
        lo, hi = scales[key]
        # TwoSlopeNorm would raise on limits that do not straddle 1; callers
        # asking for it are expected to have rejected those already.
        norm = (mcolors.TwoSlopeNorm(vmin=lo, vcenter=1.0, vmax=hi)
                if center_white else mcolors.Normalize(vmin=lo, vmax=hi))
        r = radius[spec['radius_key']]

        fmt = spec['raw_fmt'] if use_raw else spec['ratio_fmt']

        ax.set_facecolor('white')
        # coarse to fine, so the finer grids land on top where they overlap
        for res in (3, 2, 1):
            plot_layer(ax, data[f'X{res}'], data[f'Z{res}'],
                       data[fmt.format(res)], cmap, norm)

        ax.set_xlim(0, axis_limit)
        ax.set_ylim(0, axis_limit)
        ax.set_aspect('equal')
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        fig.colorbar(sm, ax=ax)
        panel_title = spec['title'] + ('  (raw)' if use_raw else '')
        ax.set_title(f'{panel_title}  ({label} = {r:.1f} m)'
                     if show_radius else panel_title)
        ax.set_xlabel('X [m]')
        ax.set_ylabel('Z [m]')
        if show_buildings:
            draw_cuboids_gray(ax, config_name)

        # Legend handles first, so the entries exist even when a line draws
        # nothing (an all-NaN theta row, or a radius that did not resolve).
        handles = []
        if show_polyline and spec['theta_key'] in radius:
            handles.append(ax.plot([], [], 'k-', linewidth=1.5,
                                   label='Per-θ boundary')[0])
            draw_convergence_polyline(ax, radius['theta_centers'],
                                      radius[spec['theta_key']])
        if show_radius:
            if handles:
                handles.append(ax.plot([], [], 'k--', linewidth=2,
                                       label=f'{label} (collapsed)')[0])
            draw_quarter_circle(ax, r, color='black', linewidth=2)
        if handles:
            ax.legend(handles=handles, fontsize=8, loc='upper right',
                      framealpha=0.85, edgecolor='gray')

    return axis_limit


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
    fig = plt.figure(figsize=(12, 5))
    draw_ratio(fig, data, cfg, config_name, radius,
               scale_limits=scale_limits, method=method)

    out_path = os.path.join(str(fig_folder), f'{config_name}_ratio.png')
    fig.savefig(out_path, dpi=100, bbox_inches='tight')
    plt.close(fig)
