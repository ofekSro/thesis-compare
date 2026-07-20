"""One-shot utility: copy all VTK files into compare_v4/all_vtks/.

Training configs (REFERENCES/VTKS/):
    Copied unchanged → all_vtks/

Validation configs (REFERENCES/VALIDATION_VTKS/):
    Renamed: config_{index} → config_{index+72}
    e.g. config_01_... → config_73_...

Run once before running main_ff_compare.py.
Originals in REFERENCES/ are NOT modified.
"""

import os
import re
import shutil

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR  = os.path.dirname(SCRIPT_DIR)

SRC_TRAIN = os.path.join(PARENT_DIR, 'REFERENCES', 'VTKS')
SRC_VAL   = os.path.join(PARENT_DIR, 'REFERENCES', 'VALIDATION_VTKS')
DST       = os.path.join(SCRIPT_DIR, 'all_vtks')

INDEX_OFFSET = 72
PATTERN = re.compile(r'^(config_)(\d+)(_.*)', re.IGNORECASE)


def copy_training():
    files = [f for f in os.listdir(SRC_TRAIN) if f.endswith('.vtk')]
    for fname in sorted(files):
        src = os.path.join(SRC_TRAIN, fname)
        dst = os.path.join(DST, fname)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
    print(f'  Training: copied {len(files)} files from {SRC_TRAIN}')


def copy_validation():
    files = [f for f in os.listdir(SRC_VAL) if f.endswith('.vtk')]
    copied = 0
    for fname in sorted(files):
        m = PATTERN.match(fname)
        if not m:
            print(f'  Warning: unexpected filename pattern, skipping: {fname}')
            continue
        prefix, idx_str, suffix = m.groups()
        new_idx = int(idx_str) + INDEX_OFFSET
        new_name = f'{prefix}{new_idx:02d}{suffix}'
        src = os.path.join(SRC_VAL, fname)
        dst = os.path.join(DST, new_name)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
        copied += 1
    print(f'  Validation: copied {copied} files from {SRC_VAL} (indices +{INDEX_OFFSET})')


def main():
    os.makedirs(DST, exist_ok=True)
    print(f'Destination: {DST}\n')

    if not os.path.isdir(SRC_TRAIN):
        print(f'ERROR: training folder not found: {SRC_TRAIN}')
        return
    copy_training()

    if os.path.isdir(SRC_VAL):
        copy_validation()
    else:
        print(f'  Validation folder not found, skipping: {SRC_VAL}')

    total = len([f for f in os.listdir(DST) if f.endswith('.vtk')])
    print(f'\nDone. {total} .vtk files in {DST}')


if __name__ == '__main__':
    main()
