"""One-shot utility: copy raw VTK files into data/vtk/.

Training configs (<references>/VTKS/):
    Copied unchanged → data/vtk/

Validation configs (<references>/VALIDATION_VTKS/):
    Renamed: config_{index} → config_{index+72}
    e.g. config_01_... → config_73_...

Originals under <references> are NOT modified. Existing destination files
are never overwritten, so re-running is a safe no-op.

NOTE: this migration was already completed for the compare_v6 dataset; the
tool is kept for reprovisioning from scratch. The references folder is no
longer assumed to be a sibling — pass it explicitly.

Usage:
    python tools\\migrate_vtks\\migrate_vtks.py "D:\\path\\to\\REFERENCES"
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

from blastlib import paths

INDEX_OFFSET = 72
PATTERN = re.compile(r'^(config_)(\d+)(_.*)', re.IGNORECASE)


def _copy_training(src_train, dst, progress=print):
    files = [f for f in os.listdir(src_train) if f.endswith('.vtk')]
    for fname in sorted(files):
        src = os.path.join(src_train, fname)
        dst_path = os.path.join(dst, fname)
        if not os.path.exists(dst_path):
            shutil.copy2(src, dst_path)
    progress(f'  Training: copied {len(files)} files from {src_train}')
    return len(files)


def _copy_validation(src_val, dst, progress=print):
    files = [f for f in os.listdir(src_val) if f.endswith('.vtk')]
    copied = 0
    for fname in sorted(files):
        m = PATTERN.match(fname)
        if not m:
            progress(f'  Warning: unexpected filename pattern, skipping: {fname}')
            continue
        prefix, idx_str, suffix = m.groups()
        new_idx = int(idx_str) + INDEX_OFFSET
        new_name = f'{prefix}{new_idx:02d}{suffix}'
        src = os.path.join(src_val, fname)
        dst_path = os.path.join(dst, new_name)
        if not os.path.exists(dst_path):
            shutil.copy2(src, dst_path)
        copied += 1
    progress(f'  Validation: copied {copied} files from {src_val} '
             f'(indices +{INDEX_OFFSET})')
    return copied


def main(references_dir, *, dest_dir=None, progress=print):
    """Copy training + validation VTKs into dest_dir.

    Returns dict with the total .vtk count in the destination, or None if
    the training source is missing.
    """
    references_dir = Path(references_dir)
    dst = paths.ensure_dir(paths.resolve(dest_dir, paths.VTK_DIR))

    src_train = references_dir / 'VTKS'
    src_val = references_dir / 'VALIDATION_VTKS'

    progress(f'Destination: {dst}\n')

    if not src_train.is_dir():
        progress(f'ERROR: training folder not found: {src_train}')
        return None
    _copy_training(str(src_train), str(dst), progress=progress)

    if src_val.is_dir():
        _copy_validation(str(src_val), str(dst), progress=progress)
    else:
        progress(f'  Validation folder not found, skipping: {src_val}')

    total = len([f for f in os.listdir(dst) if f.endswith('.vtk')])
    progress(f'\nDone. {total} .vtk files in {dst}')
    return {'total_vtk': total, 'dest': dst}


def cli(argv=None):
    p = argparse.ArgumentParser(description='Copy raw VTKs into data/vtk/.')
    p.add_argument('references_dir',
                   help='Folder containing VTKS/ and VALIDATION_VTKS/ subfolders.')
    p.add_argument('--dest-dir', default=None, help='Destination VTK folder.')
    args = p.parse_args(argv)
    return main(args.references_dir, dest_dir=args.dest_dir)


if __name__ == '__main__':
    cli()
