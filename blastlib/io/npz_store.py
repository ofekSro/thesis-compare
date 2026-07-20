"""Save / load processed grid data as .npz files (data/processed_npz/)."""

import os
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


def load_processed_data(npz_folder, config_name):
    """Load .npz file and return (processed_dict, success_bool).

    Returns the same dict format as process_grids().
    """
    npz_file = os.path.join(str(npz_folder), f'{config_name}.npz')
    if not os.path.exists(npz_file):
        print(f'  Warning: NPZ file not found: {npz_file}')
        return {}, False

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
