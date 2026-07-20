"""Standalone script: read VTK files, process grids, and save .npz files.

Run this once (or whenever VTK data changes) to populate MAT_files/.
Then main_ff_compare.py can load the processed data without needing VTK files.
"""

import os

import numpy as np

from config_parser import config_parser
from find_configurations import find_configurations
from load_vtk_pair import load_vtk_pair
from process_grids import process_grids
from save_data_file import save_processed_data
from constants import PARAMS


def main():
    work_folder = os.path.dirname(os.path.abspath(__file__))
    all_vtks_folder = os.path.join(work_folder, 'all_vtks')
    mat_folder = os.path.join(work_folder, 'MAT_files')
    os.makedirs(mat_folder, exist_ok=True)

    params = dict(PARAMS)

    all_names = find_configurations(all_vtks_folder)
    print(f'Found {len(all_names)} configs in {all_vtks_folder}\n')

    success_count = 0
    fail_count = 0

    for i, config_name in enumerate(all_names):
        print(f'[{i+1}/{len(all_names)}] {config_name}')

        cfg = config_parser(config_name)
        if cfg is None:
            print('  Warning: could not parse config name')
            fail_count += 1
            continue

        data, success = load_vtk_pair(
            all_vtks_folder, config_name, cfg, ref_folder=all_vtks_folder
        )
        if not success:
            print(f'  Skipping (VTK load failed)')
            fail_count += 1
            continue

        processed = process_grids(data, params)
        save_processed_data(mat_folder, config_name, processed)
        success_count += 1

    print(f'\nDone: {success_count} saved, {fail_count} skipped')


if __name__ == '__main__':
    main()
