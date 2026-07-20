"""Read VTK files, process grids, and save .npz files.

Run this once (or whenever VTK data changes) to populate data/processed_npz/.
Then run_analysis.py can load the processed data without needing VTK files.

Usage:
    python run_preprocess.py
    python run_preprocess.py --vtk-dir D:\\some\\vtks --npz-dir D:\\out
"""

import argparse

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.config.discovery import find_configurations
from blastlib.constants import PARAMS
from blastlib.io.vtk_pair import load_vtk_pair
from blastlib.io.npz_store import save_processed_data
from blastlib.processing.grids import process_grids


def main(*, vtk_dir=None, npz_dir=None, progress=print):
    """Convert every config's VTK triplet into one processed .npz file.

    Returns dict with saved / skipped counts.
    """
    vtk_dir = paths.resolve(vtk_dir, paths.VTK_DIR)
    npz_dir = paths.ensure_dir(paths.resolve(npz_dir, paths.PROCESSED_NPZ_DIR))

    params = dict(PARAMS)

    all_names = find_configurations(vtk_dir)
    progress(f'Found {len(all_names)} configs in {vtk_dir}\n')

    success_count = 0
    fail_count = 0

    for i, config_name in enumerate(all_names):
        progress(f'[{i+1}/{len(all_names)}] {config_name}')

        cfg = config_parser(config_name)
        if cfg is None:
            progress('  Warning: could not parse config name')
            fail_count += 1
            continue

        data, success = load_vtk_pair(vtk_dir, config_name, cfg, ref_folder=vtk_dir)
        if not success:
            progress('  Skipping (VTK load failed)')
            fail_count += 1
            continue

        processed = process_grids(data, params)
        save_processed_data(npz_dir, config_name, processed)
        success_count += 1

    progress(f'\nDone: {success_count} saved, {fail_count} skipped')
    return {'saved': success_count, 'skipped': fail_count, 'npz_dir': npz_dir}


def cli(argv=None):
    p = argparse.ArgumentParser(description='VTK → processed .npz preprocessing.')
    p.add_argument('--vtk-dir', default=None, help='Folder containing config_*.vtk files.')
    p.add_argument('--npz-dir', default=None, help='Output folder for .npz files.')
    args = p.parse_args(argv)
    return main(vtk_dir=args.vtk_dir, npz_dir=args.npz_dir)


if __name__ == '__main__':
    cli()
