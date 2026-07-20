"""Main convergence radius analysis workflow.
Equivalent to REFERENCES/compare/main_compare.m
"""

import os
import sys
import numpy as np
import pandas as pd

# Shared utilities live in pi_criterion_check
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'pi_criterion_check'))
from config_parser import config_parser
from find_configurations import find_configurations

from load_vtk_pair import load_vtk_pair
from process_grids import process_grids
from save_data_file import save_data_file
from plot_absolute import plot_absolute
from plot_ratio import plot_ratio
from find_convergence_radius import find_convergence_radius
from plot_theta_histogram import plot_theta_histogram


def main():
    work_folder   = os.path.dirname(os.path.abspath(__file__))
    parent_folder = os.path.dirname(work_folder)
    vtks_folder   = os.path.join(parent_folder, 'REFERENCES', 'VTKS')
    output_folder = work_folder

    # Create output folders
    mat_folder       = os.path.join(output_folder, 'MAT_files')
    fig_folder       = os.path.join(output_folder, 'Figures')
    fig_folder_ratio = os.path.join(output_folder, 'Figures_Ratio')
    fig_folder_theta = os.path.join(output_folder, 'Figures_Theta')
    for folder in (mat_folder, fig_folder, fig_folder_ratio, fig_folder_theta):
        os.makedirs(folder, exist_ok=True)

    # Parameters (same as MATLAB)
    params = {
        'thresholdP_kPa':  1.01 / 1000,  # mask threshold [kPa]
        'minPressure_kPa': 10,            # convergence threshold [kPa]
    }

    # Ask user for scale mode
    user_choice = input('Scale mode - (1) Auto / (2) Manual: ').strip()
    if user_choice == '2':
        params['useManualScale'] = True
        lim_p = input('Enter pressure ratio limits [min max]: ').strip().split()
        params['scaleP'] = [float(lim_p[0]), float(lim_p[1])]
        lim_i = input('Enter impulse ratio limits [min max]: ').strip().split()
        params['scaleI'] = [float(lim_i[0]), float(lim_i[1])]
        print(f'Using manual scale: P=[{params["scaleP"][0]:.2f} {params["scaleP"][1]:.2f}], '
              f'I=[{params["scaleI"][0]:.2f} {params["scaleI"][1]:.2f}]')
    else:
        params['useManualScale'] = False
        print('Using auto scale')

    # Find all configurations
    base_names = find_configurations(vtks_folder)
    print(f'Found {len(base_names)} configurations')

    max_height = 24  # reference height for volume density [m]

    results_rows = []
    theta_radii_P = {}  # config_name → array(100,)
    theta_radii_I = {}
    theta_centers_deg = None
    row_idx = 0

    for i, config_name in enumerate(base_names):
        print(f'\nProcessing {config_name}...')

        cfg = config_parser(config_name)
        if cfg is None:
            print('  Warning: could not parse config name')
            continue

        data, success = load_vtk_pair(vtks_folder, config_name, cfg)
        if not success:
            continue

        processed = process_grids(data, params)

        save_data_file(mat_folder, config_name, data, processed)

        plot_absolute(processed, config_name, fig_folder)
        print(f'  Saved Figure: {config_name}.png')

        # Densities
        area_density   = cfg['bsize'] ** 2 / (cfg['bsize'] + cfg['swidth']) ** 2
        volume_density = area_density * cfg['height'] / max_height

        # Exclusion radius around blast source
        if cfg['det'] == 1:
            exclude_r = np.sqrt((cfg['bsize'] / 2) ** 2 + (cfg['swidth'] / 2) ** 2)
        else:
            exclude_r = cfg['swidth'] / 2

        # Combine all 3 grids
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
        all_peak_P = processed['peakP_all']
        all_peak_I = processed['peakI_all']

        radius = find_convergence_radius(
            all_ratio_P, all_ratio_I, all_peak_P, all_peak_I,
            all_X, all_Z, exclude_r
        )

        plot_ratio(processed, cfg, params, config_name, fig_folder_ratio, radius)
        print(f'  Saved Figure: {config_name}_ratio.png')

        results_rows.append({
            'Config':        i + 1,
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
        row_idx += 1

        print(f'  Radius P: {radius["pressure"]:.1f} m ({radius["pressureAtRadius"]:.1f} kPa), '
              f'Radius I: {radius["impulse"]:.1f} m ({radius["impulseAtRadius"]:.1f} kPa·ms)')

        # Store per-theta radii for CSV export
        theta_radii_P[config_name] = radius['radius_per_theta_P']
        theta_radii_I[config_name] = radius['radius_per_theta_I']
        if theta_centers_deg is None:
            theta_centers_deg = np.degrees(radius['theta_centers'])

        plot_theta_histogram(
            config_name,
            radius['radius_per_theta_P'],
            radius['radius_per_theta_I'],
            radius['pressure'],
            radius['impulse'],
            np.degrees(radius['theta_centers']),
            fig_folder_theta,
        )

    # ---- Convergence table CSV ----
    cols = ['Config', 'Height', 'BuildingSize', 'StreetWidth',
            'AreaDensity', 'VolumeDensity', 'ChargeWeight',
            'RadiusP', 'RadiusI', 'PressureAtR', 'ImpulseAtR']
    results = pd.DataFrame(results_rows, columns=cols)

    output_file = os.path.join(output_folder, 'convergence_table.csv')
    results.to_csv(output_file, index=False)
    print(f'\nSaved table to: {output_file}')
    print(results.to_string())

    # ---- Theta-radius CSV export ----
    if theta_centers_deg is not None and len(theta_radii_P) > 0:
        config_names = list(theta_radii_P.keys())

        # Pressure theta-radius table
        theta_P_df = pd.DataFrame({'Theta_deg': theta_centers_deg})
        for name in config_names:
            theta_P_df[name] = theta_radii_P[name]
        theta_P_path = os.path.join(output_folder, 'theta_radius_P.csv')
        theta_P_df.to_csv(theta_P_path, index=False)
        print(f'Saved theta-radius (pressure) to: {theta_P_path}')

        # Impulse theta-radius table
        theta_I_df = pd.DataFrame({'Theta_deg': theta_centers_deg})
        for name in config_names:
            theta_I_df[name] = theta_radii_I[name]
        theta_I_path = os.path.join(output_folder, 'theta_radius_I.csv')
        theta_I_df.to_csv(theta_I_path, index=False)
        print(f'Saved theta-radius (impulse) to: {theta_I_path}')

    print('\nDone!')


if __name__ == '__main__':
    main()
