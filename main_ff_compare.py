"""Unified analysis: process all configs + cross-validated regression.

Phase 1 (run once):
    Load processed .npz files from MAT_files/ (created by create_mat_files.py),
    compute convergence radii and max-radius-per-Z, save CSVs.

Phase 2 (repeated):
    Random 80/20 train/test splits on the saved CSV data,
    fit regression models, evaluate on test set, track best coefficients.
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')

import glob as _glob

from config_parser import config_parser

from save_data_file import load_processed_data
from plot_absolute import plot_absolute
from plot_ratio import plot_ratio
from find_convergence_radius import find_convergence_radius
from plot_theta_histogram import plot_theta_histogram_Z, plot_theta_histogram

from constants import MAX_HEIGHT, PARAMS
from ff_lookup import _load_ff_lookup, _find_percentile_radius
from plot_max_radius_fig import plot_max_radius
from regression import run_cross_validation


# ============================================================
# Main
# ============================================================

def main():
    work_folder   = os.path.dirname(os.path.abspath(__file__))
    output_folder   = work_folder

    conv_csv = os.path.join(output_folder, 'convergence_table.csv')
    maxR_csv = os.path.join(output_folder, 'max_radius_per_Z.csv')

    # ---- Check if Phase 1 can be skipped ----
    skip_phase1 = False
    if os.path.exists(conv_csv) and os.path.exists(maxR_csv):
        choice = input('Found existing CSV data. (1) Reprocess from NPZ / (2) Skip to regression: ').strip()
        skip_phase1 = (choice == '2')

    if not skip_phase1:
        _run_phase1(output_folder, conv_csv, maxR_csv)

    # ---- Phase 2: Cross-validated regression ----
    n_iter_str = input('Number of CV iterations [default 500]: ').strip()
    n_iter = int(n_iter_str) if n_iter_str else 500

    print(f'\n{"="*50}')
    print(f'  PHASE 2: CROSS-VALIDATED REGRESSION ({n_iter} iterations)')
    print(f'{"="*50}\n')

    run_cross_validation(conv_csv, maxR_csv, output_folder,
                         n_iterations=n_iter, target_mape=10.0)

    print('\n' + '=' * 40)
    print('  ALL DONE')
    print('=' * 40)


def _run_phase1(output_folder, conv_csv, maxR_csv):
    """Phase 1: Load processed .npz files, compute convergence, save CSVs."""

    print('=' * 50)
    print('  PHASE 1: NPZ PROCESSING')
    print('=' * 50)

    # Create output folders
    mat_folder       = os.path.join(output_folder, 'MAT_files')
    fig_folder       = os.path.join(output_folder, 'Figures')
    fig_folder_ratio = os.path.join(output_folder, 'Figures_Ratio')
    fig_folder_maxR  = os.path.join(output_folder, 'Figures_MaxR')
    fig_folder_theta_P    = os.path.join(output_folder, 'Figures_MaxR_Theta_P')
    fig_folder_theta_I    = os.path.join(output_folder, 'Figures_MaxR_Theta_I')
    fig_folder_conv_theta = os.path.join(output_folder, 'Figures_Conv_Theta')
    for folder in (mat_folder, fig_folder, fig_folder_ratio, fig_folder_maxR,
                   fig_folder_theta_P, fig_folder_theta_I, fig_folder_conv_theta):
        os.makedirs(folder, exist_ok=True)

    # Scale mode (for ratio plots)
    params = dict(PARAMS)
    user_choice = input('Scale mode - (1) Auto / (2) Manual: ').strip()
    if user_choice == '2':
        params['useManualScale'] = True
        lim_p = input('Enter pressure ratio limits [min max]: ').strip().split()
        params['scaleP'] = [float(lim_p[0]), float(lim_p[1])]
        lim_i = input('Enter impulse ratio limits [min max]: ').strip().split()
        params['scaleI'] = [float(lim_i[0]), float(lim_i[1])]
    else:
        params['useManualScale'] = False
        print('Using auto scale')

    # Load free-field lookup table
    ff_csv = os.path.join(output_folder, 'free_field_data.csv')
    ff_lookup = _load_ff_lookup(ff_csv)

    # Discover configs from .npz files in MAT_files/
    npz_files = sorted(_glob.glob(os.path.join(mat_folder, 'config_*.npz')))
    all_configs = [os.path.splitext(os.path.basename(f))[0] for f in npz_files]

    if not all_configs:
        print(f'No .npz files found in {mat_folder}. Run create_mat_files.py first.')
        return

    print(f'Found {len(all_configs)} configs in MAT_files/\n')

    conv_rows   = []
    maxR_rows   = []
    theta_radii_P = {}
    theta_radii_I = {}
    theta_centers_deg = None

    for i, config_name in enumerate(all_configs):
        print(f'Processing [{i+1}/{len(all_configs)}] {config_name}...')

        cfg = config_parser(config_name)
        if cfg is None:
            print('  Warning: could not parse config name')
            continue

        processed, success = load_processed_data(mat_folder, config_name)
        if not success:
            print(f'  Skipping {config_name} (NPZ load failed)')
            continue

        # Plot absolute values
        plot_absolute(processed, config_name, fig_folder)

        # Geometry parameters
        area_density   = cfg['bsize'] ** 2 / (cfg['bsize'] + cfg['swidth']) ** 2
        volume_density = area_density * cfg['height'] / MAX_HEIGHT

        if cfg['det'] == 1:
            exclude_r = np.sqrt((cfg['bsize'] / 2) ** 2 + (cfg['swidth'] / 2) ** 2)
        else:
            exclude_r = cfg['swidth'] / 2

        # Convergence radius (angular, equivalent area)
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

        plot_ratio(processed, cfg, params, config_name, fig_folder_ratio, radius)

        conv_rows.append({
            'ConfigName':    config_name,
            'Det':           cfg['det'],
            'Height':        cfg['height'],
            'BuildingSize':  cfg['bsize'],
            'StreetWidth':   cfg['swidth'],
            'AreaDensity':   area_density,
            'VolumeDensity': volume_density,
            'ChargeWeight':  cfg['weight'],
            'RadiusP':       radius['pressure'],
            'RadiusI':       radius['impulse'],
            'PressureAtR':   radius['pressureAtRadius'],
            'ImpulseAtR':    radius['impulseAtRadius'],
        })

        theta_radii_P[config_name] = radius['radius_per_theta_P']
        theta_radii_I[config_name] = radius['radius_per_theta_I']
        if theta_centers_deg is None:
            theta_centers_deg = np.degrees(radius['theta_centers'])

        print(f'  Req P: {radius["pressure"]:.1f} m  '
              f'Req I: {radius["impulse"]:.1f} m')

        plot_theta_histogram(
            config_name,
            radius['radius_per_theta_P'],
            radius['radius_per_theta_I'],
            radius['pressure'],
            radius['impulse'],
            np.degrees(radius['theta_centers']),
            fig_folder_conv_theta,
        )

        # Max radius per scaled distance Z
        all_P_orig = np.concatenate([processed['peakP1_orig'].ravel(),
                                     processed['peakP2_orig'].ravel(),
                                     processed['peakP3_orig'].ravel()])
        all_I_orig = np.concatenate([processed['impulse1_orig'].ravel(),
                                     processed['impulse2_orig'].ravel(),
                                     processed['impulse3_orig'].ravel()])

        weight = cfg['weight']
        act_R_P = radius['pressure']
        act_R_I = radius['impulse']
        maxR_P_per_Z = {}
        maxR_I_per_Z = {}
        theta_radii_P_per_Z = {}
        theta_radii_I_per_Z = {}

        for z_val in range(1, 21):
            P_ff, I_ff = ff_lookup[weight][z_val]
            maxR_P, r_theta_P = _find_percentile_radius(all_P_orig, all_X, all_Z, P_ff)
            maxR_I, r_theta_I = _find_percentile_radius(all_I_orig, all_X, all_Z, I_ff)

            maxR_P_per_Z[z_val] = maxR_P
            maxR_I_per_Z[z_val] = maxR_I
            theta_radii_P_per_Z[z_val] = r_theta_P
            theta_radii_I_per_Z[z_val] = r_theta_I

            beyond_P = np.isnan(maxR_P) or maxR_P >= act_R_P
            beyond_I = np.isnan(maxR_I) or maxR_I >= act_R_I
            if beyond_P and beyond_I:
                continue

            maxR_rows.append({
                'Config': config_name,
                'Z': z_val,
                'P_ff': P_ff,
                'I_ff': I_ff,
                'MaxR_P': maxR_P if not beyond_P else np.nan,
                'MaxR_I': maxR_I if not beyond_I else np.nan,
            })

        plot_max_radius(processed, config_name, maxR_P_per_Z, maxR_I_per_Z,
                        radius['pressure'], radius['impulse'], fig_folder_maxR)

        plot_theta_histogram_Z(config_name, theta_radii_P_per_Z, maxR_P_per_Z, 'P', fig_folder_theta_P)
        plot_theta_histogram_Z(config_name, theta_radii_I_per_Z, maxR_I_per_Z, 'I', fig_folder_theta_I)

    # ---- Save convergence table ----
    cols = ['ConfigName', 'Det', 'Height', 'BuildingSize', 'StreetWidth',
            'AreaDensity', 'VolumeDensity', 'ChargeWeight',
            'RadiusP', 'RadiusI', 'PressureAtR', 'ImpulseAtR']
    conv_df = pd.DataFrame(conv_rows, columns=cols)
    conv_df.to_csv(conv_csv, index=False)
    print(f'\nSaved: {conv_csv}')
    print(conv_df.to_string())

    # ---- Save theta-radius tables ----
    if theta_centers_deg is not None and theta_radii_P:
        config_names = list(theta_radii_P.keys())

        theta_P_df = pd.DataFrame({'Theta_deg': theta_centers_deg})
        for name in config_names:
            theta_P_df[name] = theta_radii_P[name]
        theta_P_df.to_csv(os.path.join(output_folder, 'theta_radius_P.csv'), index=False)

        theta_I_df = pd.DataFrame({'Theta_deg': theta_centers_deg})
        for name in config_names:
            theta_I_df[name] = theta_radii_I[name]
        theta_I_df.to_csv(os.path.join(output_folder, 'theta_radius_I.csv'), index=False)

    # ---- Save max-radius-per-Z table ----
    maxR_df = pd.DataFrame(maxR_rows, columns=['Config', 'Z', 'P_ff', 'I_ff', 'MaxR_P', 'MaxR_I'])
    maxR_df.to_csv(maxR_csv, index=False)
    print(f'Saved: {maxR_csv}')
    print(f'\nPhase 1 complete: {len(conv_rows)} configs processed')


if __name__ == '__main__':
    main()
