"""Read VTK files and write one .npz per configuration.

Two store formats:

    raw        (default, schema v3) -> data/raw_npz/
        Only the solver's own fields: urban peak pressure and impulse, the
        free-field reference for both, the grid definition and the dump
        times. NO criterion is applied. The threshold mask, the
        multi-resolution fill, the smart cut, the ratios and the pinning of
        converged cells all happen at analysis time instead, so changing a
        threshold, a band or the projection sharpness is a re-run of
        run_analysis.py — not a regeneration from VTK. About a fifth of the
        disk of the processed store.

    processed  (legacy, schema v1/v2) -> data/processed_npz/
        The historical layout: process_grids() is applied here and its output
        is what gets stored, criteria included. Kept so the shipped v1/v2
        folders remain reproducible.

Both are read transparently by run_analysis.py; the tables come out
identical either way (tests/test_raw_store.py asserts this cell-by-cell).

Usage:
    python run_preprocess.py
    python run_preprocess.py --vtk-dir D:\\some\\vtks --npz-dir D:\\out
    python run_preprocess.py --store processed
"""

import argparse

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.config.discovery import find_configurations
from blastlib.constants import PARAMS
from blastlib.io import raw_store
from blastlib.io.vtk_pair import load_vtk_pair, load_vtk_triplets
from blastlib.io.npz_store import save_processed_data
from blastlib.processing.grids import process_grids

STORES = ('raw', 'processed')


def default_npz_dir(store):
    """Where each store format lands when --npz-dir is not given."""
    return paths.RAW_NPZ_DIR if store == 'raw' else paths.PROCESSED_NPZ_DIR


def main(*, vtk_dir=None, npz_dir=None, store='raw', progress=print):
    """Convert every config's VTK triplet into one .npz file.

    store : 'raw' (default, schema v3 — no criterion applied) or 'processed'
        (legacy, criteria baked in). See the module docstring.

    Returns dict with saved / skipped counts.
    """
    if store not in STORES:
        raise ValueError(f'store must be one of {STORES}, got {store!r}')

    vtk_dir = paths.resolve(vtk_dir, paths.VTK_DIR)
    npz_dir = paths.ensure_dir(paths.resolve(npz_dir, default_npz_dir(store)))

    params = dict(PARAMS)

    all_names = find_configurations(vtk_dir)
    progress(f'Found {len(all_names)} configs in {vtk_dir}')
    progress(f'Store format: {store}'
             + ('  (schema v3 — criteria applied at analysis time)'
                if store == 'raw' else
                '  (legacy — criteria baked in at write time)'))
    progress(f'Output: {npz_dir}\n')

    success_count = 0
    fail_count = 0

    for i, config_name in enumerate(all_names):
        progress(f'[{i+1}/{len(all_names)}] {config_name}')

        cfg = config_parser(config_name)
        if cfg is None:
            progress('  Warning: could not parse config name')
            fail_count += 1
            continue

        if store == 'raw':
            urban, ref, ok = load_vtk_triplets(vtk_dir, config_name, cfg,
                                               ref_folder=vtk_dir)
            if not ok:
                progress('  Skipping (VTK load failed)')
                fail_count += 1
                continue
            raw_store.save_raw_data(npz_dir, config_name,
                                    raw_store.build_raw(urban, ref, cfg),
                                    progress=progress)
        else:
            data, ok = load_vtk_pair(vtk_dir, config_name, cfg,
                                     ref_folder=vtk_dir)
            if not ok:
                progress('  Skipping (VTK load failed)')
                fail_count += 1
                continue
            save_processed_data(npz_dir, config_name,
                                process_grids(data, params,
                                              weight=cfg['weight']))
        success_count += 1

    progress(f'\nDone: {success_count} saved, {fail_count} skipped')
    return {'saved': success_count, 'skipped': fail_count,
            'npz_dir': npz_dir, 'store': store}


def cli(argv=None):
    p = argparse.ArgumentParser(description='VTK → .npz preprocessing.')
    p.add_argument('--vtk-dir', default=None,
                   help='Folder containing config_*.vtk files.')
    p.add_argument('--npz-dir', default=None,
                   help='Output folder (blank = data/raw_npz or '
                        'data/processed_npz, per --store).')
    p.add_argument('--store', choices=STORES, default='raw',
                   help="'raw' (default) stores the solver fields only and "
                        "applies the criteria at analysis time; 'processed' "
                        'is the legacy layout with the criteria baked in.')
    args = p.parse_args(argv)
    return main(vtk_dir=args.vtk_dir, npz_dir=args.npz_dir, store=args.store)


if __name__ == '__main__':
    cli()
