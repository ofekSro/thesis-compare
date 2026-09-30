"""Save / load processed grid data as .npz files (data/processed_npz/).

Two on-disk generations are read here, transparently:

* **v1 / v2 (processed)** — the arrays process_grids() returned, written at
  preprocessing time. Loaded verbatim.
* **v3 (raw)** — only the solver's own fields (see io/raw_store.py). The
  criteria are applied on load by calling process_grids(). Costs ~0.3 s per
  config. v1/v2 reproduce the pre-D34 record only; current numbers come from
  raw_npz.

Callers do not need to know which generation they are reading. Pass *params*
/ *weight* only to override the criteria a v3 file is expanded with; both are
ignored for v1/v2 files, where the criteria are already baked in.
"""

import os
import warnings

import numpy as np


# Keys that process_grids() returns (all must be present in the .npz).
# NOTE: legacy NPZ files created by compare_v6 additionally contain 6
# logRatio* keys; those were never consumed anywhere and are no longer
# written or required. Extra keys in a legacy file are loaded and ignored.
EXPECTED_KEYS = {
    'X1', 'Z1', 'X2', 'Z2', 'X3', 'Z3',
    'peakP1_orig', 'peakP2_orig', 'peakP3_orig',
    'impulse1_orig', 'impulse2_orig', 'impulse3_orig',
    'ratioP1', 'ratioP2', 'ratioP3',
    'ratioI1', 'ratioI2', 'ratioI3',
    'peakP_all', 'peakI_all',
    'maxP', 'maxI',
}


def save_processed_data(npz_folder, config_name, processed):
    """Save all processed arrays (output of process_grids) to a .npz file."""
    npz_file = os.path.join(str(npz_folder), f'{config_name}.npz')

    np.savez(npz_file, **{k: v for k, v in processed.items()})
    print(f'  Saved NPZ: {config_name}.npz')


def load_processed_data(npz_folder, config_name, params=None, weight=None):
    """Load .npz file and return (processed_dict, success_bool).

    Returns the same dict format as process_grids(), whether the file on disk
    is a processed (v1/v2) or a raw (v3) store — see the module docstring.
    *params* / *weight* override the criteria applied to a v3 file and are
    ignored for v1/v2 files, whose criteria were fixed at write time.
    """
    npz_file = os.path.join(str(npz_folder), f'{config_name}.npz')
    if not os.path.exists(npz_file):
        print(f'  Warning: NPZ file not found: {npz_file}')
        return {}, False

    from blastlib.io import raw_store
    if raw_store.is_raw_file(npz_file):
        raw, ok = raw_store.load_raw_data(npz_folder, config_name)
        if not ok:
            print(f'  Warning: incomplete raw NPZ: {npz_file} '
                  '-- re-run run_preprocess.py')
            return {}, False
        try:
            return raw_store.expand(raw, params=params, weight=weight), True
        except Exception as e:
            print(f'  Warning: Error expanding raw NPZ - {e}')
            return {}, False

    if params is not None or weight is not None:
        warnings.warn(
            'v1/v2 stores carry the convergence criteria baked in at write '
            'time (pre-D34 merge, pre-D35 impulse); params/weight are ignored. '
            'Use data/raw_npz for the current criteria.', stacklevel=2)

    try:
        npz = np.load(npz_file, allow_pickle=True)
        missing = EXPECTED_KEYS - set(npz.files)
        if missing:
            print(f'  Warning: NPZ missing keys {missing} -- re-run run_preprocess.py')
            return {}, False
        processed = {}
        for key in npz.files:
            val = npz[key]
            # Scalars (maxP, maxI) are stored as 0-d arrays — extract them
            if val.ndim == 0:
                processed[key] = float(val)
            else:
                processed[key] = val
        return processed, True
    except Exception as e:
        print(f'  Warning: Error loading NPZ - {e}')
        return {}, False
