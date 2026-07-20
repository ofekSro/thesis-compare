"""Read obstacle (OBS) VTK files and save processed data as .npz files.

Run this once to populate OBS_MAT_files/.
Each config gets one .npz containing points, cells, and scalar fields
for all 3 resolutions.
"""

import os
import numpy as np

from find_configurations import find_configurations
from readVTK_obs import readVTK_obs


def main():
    work_folder = os.path.dirname(os.path.abspath(__file__))
    obs_vtks_folder = os.path.join(work_folder, 'all_vtks', 'OBS')
    out_folder = os.path.join(work_folder, 'OBS_MAT_files')
    os.makedirs(out_folder, exist_ok=True)

    all_names = find_configurations(obs_vtks_folder)
    print(f'Found {len(all_names)} OBS configs in {obs_vtks_folder}\n')

    success_count = 0
    fail_count = 0

    for i, config_name in enumerate(all_names):
        print(f'[{i+1}/{len(all_names)}] {config_name}')

        data = {}
        ok = True

        for res in ('1', '2', '3'):
            vtk_path = os.path.join(obs_vtks_folder, f'{config_name}_{res}.vtk')
            if not os.path.exists(vtk_path):
                print(f'  Missing resolution {res}: {vtk_path}')
                ok = False
                break

            points, cells, scalars = readVTK_obs(vtk_path)

            data[f'points_{res}'] = np.ascontiguousarray(points, dtype=np.float32)
            data[f'cells_{res}'] = np.ascontiguousarray(cells, dtype=np.int32)
            data[f'pressure_{res}'] = np.ascontiguousarray(scalars.get('pressure', np.array([], dtype=np.float32)), dtype=np.float32)
            data[f'peakP_{res}'] = np.ascontiguousarray(scalars.get('Peak_Ovepressure', np.array([], dtype=np.float32)), dtype=np.float32)
            data[f'impulse_{res}'] = np.ascontiguousarray(scalars.get('Peak_Impulse', np.array([], dtype=np.float32)), dtype=np.float32)

            print(f'  Res {res}: {points.shape[0]} points, {cells.shape[0]} cells')

        if not ok:
            fail_count += 1
            continue

        npz_path = os.path.join(out_folder, f'{config_name}.npz')
        np.savez(npz_path, **data)
        print(f'  Saved: {config_name}.npz')
        success_count += 1

    print(f'\nDone: {success_count} saved, {fail_count} skipped')


if __name__ == '__main__':
    main()
