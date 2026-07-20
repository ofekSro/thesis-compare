"""Read obstacle (OBS) VTK files and save processed data as .npz files.

Run this once to populate data/obs_npz/. Each config gets one .npz
containing points, cells, and scalar fields for all 3 resolutions.
Used by tools/view_3d.

Usage:
    python run_preprocess_obs.py
    python run_preprocess_obs.py --obs-vtk-dir D:\\vtks\\OBS --obs-npz-dir D:\\out
"""

import argparse
import os

import numpy as np

from blastlib import paths
from blastlib.config.discovery import find_configurations
from blastlib.io.vtk_obs_reader import readVTK_obs


def main(*, obs_vtk_dir=None, obs_npz_dir=None, progress=print):
    """Convert every OBS config's VTK triplet into one .npz file.

    Returns dict with saved / skipped counts.
    """
    obs_vtk_dir = paths.resolve(obs_vtk_dir, paths.OBS_VTK_DIR)
    obs_npz_dir = paths.ensure_dir(paths.resolve(obs_npz_dir, paths.OBS_NPZ_DIR))

    all_names = find_configurations(obs_vtk_dir)
    progress(f'Found {len(all_names)} OBS configs in {obs_vtk_dir}\n')

    success_count = 0
    fail_count = 0

    for i, config_name in enumerate(all_names):
        progress(f'[{i+1}/{len(all_names)}] {config_name}')

        data = {}
        ok = True

        for res in ('1', '2', '3'):
            vtk_path = os.path.join(str(obs_vtk_dir), f'{config_name}_{res}.vtk')
            if not os.path.exists(vtk_path):
                progress(f'  Missing resolution {res}: {vtk_path}')
                ok = False
                break

            points, cells, scalars = readVTK_obs(vtk_path)
            empty = np.array([], dtype=np.float32)

            data[f'points_{res}'] = np.ascontiguousarray(points, dtype=np.float32)
            data[f'cells_{res}'] = np.ascontiguousarray(cells, dtype=np.int32)
            data[f'pressure_{res}'] = np.ascontiguousarray(
                scalars.get('pressure', empty), dtype=np.float32)
            data[f'peakP_{res}'] = np.ascontiguousarray(
                scalars.get('Peak_Ovepressure', empty), dtype=np.float32)
            data[f'impulse_{res}'] = np.ascontiguousarray(
                scalars.get('Peak_Impulse', empty), dtype=np.float32)

            progress(f'  Res {res}: {points.shape[0]} points, {cells.shape[0]} cells')

        if not ok:
            fail_count += 1
            continue

        npz_path = os.path.join(str(obs_npz_dir), f'{config_name}.npz')
        np.savez(npz_path, **data)
        progress(f'  Saved: {config_name}.npz')
        success_count += 1

    progress(f'\nDone: {success_count} saved, {fail_count} skipped')
    return {'saved': success_count, 'skipped': fail_count, 'obs_npz_dir': obs_npz_dir}


def cli(argv=None):
    p = argparse.ArgumentParser(description='OBS VTK → .npz preprocessing.')
    p.add_argument('--obs-vtk-dir', default=None, help='Folder with OBS config_*.vtk files.')
    p.add_argument('--obs-npz-dir', default=None, help='Output folder for OBS .npz files.')
    args = p.parse_args(argv)
    return main(obs_vtk_dir=args.obs_vtk_dir, obs_npz_dir=args.obs_npz_dir)


if __name__ == '__main__':
    cli()
