"""Visualise convergence radius as a function of s/W^(1/3).

4 plots: det1/det2 × Pressure/Impulse.
Each geometry group (b, s, H) is a line connecting its 3 charge weights.

Run directly:
    python compare_v6/plot_pi_effects.py
"""

import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def _load(csv_path):
    df = pd.read_csv(csv_path)
    df['W13']      = df['ChargeWeight'] ** (1 / 3)
    df['sW13']     = df['StreetWidth'] / df['W13']
    df['rho']      = df['BuildingSize'] ** 2 / (df['BuildingSize'] + df['StreetWidth']) ** 2
    df['Z_P']      = df['RadiusP'] / df['W13']
    df['Z_I']      = df['RadiusI'] / df['W13']
    df['switch_1'] = df['rho'] * (df['sW13'] - 1)          # ρ·(s/W^⅓ − 1)  det=1
    df['switch_2'] = df['rho'] * (df['sW13'] - 2)          # ρ·(s/W^⅓ − 2)  det=2
    df['canyon']   = (np.sqrt(df['rho']) * (df['Height'] / df['StreetWidth'])
                      * (df['W13'] / df['StreetWidth'] - 1))  # √ρ·(H/s)·(W^⅓/s − 1)
    return df


def _color_map(groups):
    cmap = matplotlib.colormaps.get_cmap('tab20').resampled(max(len(groups), 1))
    return {g: cmap(i) for i, g in enumerate(sorted(groups))}


def _plot_vs_sW13(df, out_dir, use_Z):
    """Core plotting logic. use_Z=True → Y axis is Z=R/W^(1/3); False → R [m]."""
    ylabel    = 'Z = R / W^(1/3)  [m / kg^(1/3)]' if use_Z else 'R  [m]'
    suffix    = 'Z' if use_Z else 'R'
    title_qty = 'Z = R/W^(1/3)' if use_Z else 'R'

    titles = {
        (1, 'RadiusP'): f'Det=1 (Street) — Pressure Convergence Radius\n{title_qty} vs s/W^(1/3)',
        (1, 'RadiusI'): f'Det=1 (Street) — Impulse Convergence Radius\n{title_qty} vs s/W^(1/3)',
        (2, 'RadiusP'): f'Det=2 (Intersection) — Pressure Convergence Radius\n{title_qty} vs s/W^(1/3)',
        (2, 'RadiusI'): f'Det=2 (Intersection) — Impulse Convergence Radius\n{title_qty} vs s/W^(1/3)',
    }
    filenames = {
        (1, 'RadiusP'): f'radius_vs_sW13_det1_P_{suffix}.png',
        (1, 'RadiusI'): f'radius_vs_sW13_det1_I_{suffix}.png',
        (2, 'RadiusP'): f'radius_vs_sW13_det2_P_{suffix}.png',
        (2, 'RadiusI'): f'radius_vs_sW13_det2_I_{suffix}.png',
    }
    y_cols = {
        'RadiusP': 'Z_P' if use_Z else 'RadiusP',
        'RadiusI': 'Z_I' if use_Z else 'RadiusI',
    }

    for det in [1, 2]:
        sub_det = df[df['Det'] == det].copy()
        groups = sub_det.groupby(['BuildingSize', 'StreetWidth', 'Height'])
        group_keys = sorted(groups.groups.keys())
        colors = _color_map(group_keys)

        for target in ['RadiusP', 'RadiusI']:
            fig, ax = plt.subplots(figsize=(10, 7))
            fig.patch.set_facecolor('white')
            ax.set_title(titles[(det, target)], fontsize=13, fontweight='bold')
            ax.set_xlabel('s / W^(1/3)  [m / kg^(1/3)]', fontsize=12)
            ax.set_ylabel(ylabel, fontsize=12)
            ax.grid(True, alpha=0.3)

            for (b, s, H), grp in groups:
                grp = grp.sort_values('sW13')
                if len(grp) < 2:
                    continue
                color = colors[(b, s, H)]
                lbl = f'b={int(b)} s={int(s)} H={int(H)}'
                ax.plot(grp['sW13'], grp[y_cols[target]],
                        'o-', color=color, linewidth=1.8, markersize=6,
                        label=lbl)

            ax.legend(fontsize=7, ncol=2, loc='upper left',
                      title='Geometry (b, s, H)', title_fontsize=8)
            plt.tight_layout()

            path = os.path.join(out_dir, filenames[(det, target)])
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            print(f'Saved: {path}')


def _plot_term(df, out_dir, xcol_per_det, xlabel_per_det, name, title_term, use_Z,
               zero_line=True):
    """Generic 4-plot helper. xcol_per_det: {det: col_name}."""
    qty   = 'Z = R/W^(1/3)' if use_Z else 'R'
    ylabel = 'Z = R / W^(1/3)  [m / kg^(1/3)]' if use_Z else 'R  [m]'
    suffix = 'Z' if use_Z else 'R'
    y_cols = {'RadiusP': 'Z_P' if use_Z else 'RadiusP',
               'RadiusI': 'Z_I' if use_Z else 'RadiusI'}

    det_labels = {1: 'Det=1 (Street)', 2: 'Det=2 (Intersection)'}
    tgt_labels = {'RadiusP': 'Pressure', 'RadiusI': 'Impulse'}

    for det in [1, 2]:
        sub_det = df[df['Det'] == det].copy()
        groups = sub_det.groupby(['BuildingSize', 'StreetWidth', 'Height'])
        colors = _color_map(sorted(groups.groups.keys()))
        xcol   = xcol_per_det[det]
        xlabel = xlabel_per_det[det]

        for target in ['RadiusP', 'RadiusI']:
            fig, ax = plt.subplots(figsize=(10, 7))
            fig.patch.set_facecolor('white')
            ax.set_title(f'{det_labels[det]} — {tgt_labels[target]} Convergence Radius\n'
                         f'{qty} vs {title_term}', fontsize=13, fontweight='bold')
            ax.set_xlabel(xlabel, fontsize=12)
            ax.set_ylabel(ylabel, fontsize=12)
            if zero_line:
                ax.axvline(0, color='k', linewidth=0.8, linestyle='--', alpha=0.5)
            ax.grid(True, alpha=0.3)

            for (b, s, H), grp in groups:
                grp = grp.sort_values(xcol)
                if len(grp) < 2:
                    continue
                ax.plot(grp[xcol], grp[y_cols[target]],
                        'o-', color=colors[(b, s, H)], linewidth=1.8, markersize=6,
                        label=f'b={int(b)} s={int(s)} H={int(H)}')

            ax.legend(fontsize=7, ncol=2, loc='upper left',
                      title='Geometry (b, s, H)', title_fontsize=8)
            plt.tight_layout()

            tgt_s = 'P' if target == 'RadiusP' else 'I'
            path = os.path.join(out_dir, f'{name}_det{det}_{tgt_s}_{suffix}.png')
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            print(f'Saved: {path}')


def plot_switch(df, out_dir, use_Z):
    _plot_term(df, out_dir,
               xcol_per_det  = {1: 'switch_1', 2: 'switch_2'},
               xlabel_per_det= {1: 'ρ · (s/W^(1/3) − 1)', 2: 'ρ · (s/W^(1/3) − 2)'},
               name='radius_vs_switch', title_term='ρ·(s/W^(1/3) − a)',
               use_Z=use_Z)


def plot_canyon(df, out_dir, use_Z):
    _plot_term(df, out_dir,
               xcol_per_det  = {1: 'canyon', 2: 'canyon'},
               xlabel_per_det= {1: '√ρ · (H/s) · (W^(1/3)/s − 1)',
                                 2: '√ρ · (H/s) · (W^(1/3)/s − 1)'},
               name='radius_vs_canyon', title_term='√ρ·(H/s)·(W^(1/3)/s − 1)',
               use_Z=use_Z)


def plot_weight(df, out_dir, use_Z):
    _plot_term(df, out_dir,
               xcol_per_det  = {1: 'ChargeWeight', 2: 'ChargeWeight'},
               xlabel_per_det= {1: 'Charge Weight  W  [kg]',
                                 2: 'Charge Weight  W  [kg]'},
               name='radius_vs_weight', title_term='Charge Weight W',
               use_Z=use_Z, zero_line=False)


def plot_weight_loglog(df, out_dir):
    """4 figures: det × target. log-log R vs W.

    Slope of each line = effective Hopkinson exponent n (R ~ W^n).
    Dashed reference line shows slope 1/3. Fitted n shown in the legend.
    """
    det_labels = {1: 'Det=1 (Street)', 2: 'Det=2 (Intersection)'}
    tgt_labels = {'RadiusP': 'Pressure', 'RadiusI': 'Impulse'}

    for det in [1, 2]:
        sub_det = df[df['Det'] == det].copy()
        groups = sub_det.groupby(['BuildingSize', 'StreetWidth', 'Height'])
        colors = _color_map(sorted(groups.groups.keys()))

        for target in ['RadiusP', 'RadiusI']:
            fig, ax = plt.subplots(figsize=(10, 7))
            fig.patch.set_facecolor('white')
            ax.set_title(f'{det_labels[det]} — {tgt_labels[target]} Convergence Radius\n'
                         'log-log R vs W   (line slope = effective exponent n)',
                         fontsize=13, fontweight='bold')
            ax.set_xlabel('Charge Weight  W  [kg]', fontsize=12)
            ax.set_ylabel('R  [m]', fontsize=12)
            ax.set_xscale('log')
            ax.set_yscale('log')
            ax.grid(True, alpha=0.3, which='both')

            for (b, s, H), grp in groups:
                grp = grp.sort_values('ChargeWeight')
                if len(grp) < 2:
                    continue
                # fitted exponent: slope of log R vs log W
                n = np.polyfit(np.log(grp['ChargeWeight']), np.log(grp[target]), 1)[0]
                ax.plot(grp['ChargeWeight'], grp[target],
                        'o-', color=colors[(b, s, H)], linewidth=1.8, markersize=6,
                        label=f'b={int(b)} s={int(s)} H={int(H)}  (n={n:.2f})')

            # reference line with slope 1/3, anchored at the data median
            W_ref = np.array([sub_det['ChargeWeight'].min(), sub_det['ChargeWeight'].max()])
            R_mid = sub_det[target].median()
            W_mid = np.sqrt(W_ref[0] * W_ref[1])
            ax.plot(W_ref, R_mid * (W_ref / W_mid) ** (1 / 3),
                    'k--', linewidth=1.5, alpha=0.7, label='slope 1/3 (Hopkinson)')

            ax.legend(fontsize=7, ncol=2, loc='upper left',
                      title='Geometry (b, s, H)', title_fontsize=8)
            plt.tight_layout()

            tgt_s = 'P' if target == 'RadiusP' else 'I'
            path = os.path.join(out_dir, f'radius_vs_weight_loglog_det{det}_{tgt_s}.png')
            fig.savefig(path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            print(f'Saved: {path}')


def main():
    work_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(work_dir, 'convergence_table.csv')
    out_dir  = os.path.join(work_dir, 'Figures_Pi_Effects')
    os.makedirs(out_dir, exist_ok=True)

    print(f'Loading: {csv_path}')
    df = _load(csv_path)
    df = df[~df['ChargeWeight'].isin([250, 1000])].copy()
    print(f'Loaded {len(df)} configs (excluding W=250, 1000)\n')

    _plot_vs_sW13(df, out_dir, use_Z=False)
    _plot_vs_sW13(df, out_dir, use_Z=True)
    plot_switch(df, out_dir, use_Z=False)
    plot_switch(df, out_dir, use_Z=True)
    plot_canyon(df, out_dir, use_Z=False)
    plot_canyon(df, out_dir, use_Z=True)
    plot_weight(df, out_dir, use_Z=False)
    plot_weight(df, out_dir, use_Z=True)
    plot_weight_loglog(df, out_dir)

    print('\nAll plots saved to:', out_dir)


if __name__ == '__main__':
    main()
