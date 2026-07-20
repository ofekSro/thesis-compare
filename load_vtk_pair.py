"""Load config and free-field VTK file pairs.
Equivalent to REFERENCES/compare/load_vtk_pair.m
"""

import os
import numpy as np

from readVTK import readVTK


def load_vtk_pair(urban_folder, config_name, cfg, ref_folder=None):
    """Load 3 urban VTK files + 3 free-field reference VTK files.

    Parameters
    ----------
    urban_folder : str
        Folder containing the urban config VTK files.
    config_name : str
        Base config name (e.g. ``config_01_det1_b15_s5_h4_w50``).
    cfg : dict
        Parsed config parameters from ``config_parser``.
    ref_folder : str, optional
        Folder containing free-field VTK files. Defaults to ``urban_folder``.

    Returns (data dict, success bool).
    data keys: X1/Z1/X2/Z2/X3/Z3,
               peakP1/peakP2/peakP3  (kPa),
               impulse1/impulse2/impulse3  (Pa·s, unchanged),
               refP1/refP2/refP3  (kPa),
               refI1/refI2/refI3  (Pa·s, unchanged)
    """
    if ref_folder is None:
        ref_folder = urban_folder

    data = {}
    success = False

    files = {
        'fine':      os.path.join(urban_folder, f'{config_name}_1.vtk'),
        'medium':    os.path.join(urban_folder, f'{config_name}_2.vtk'),
        'coarse':    os.path.join(urban_folder, f'{config_name}_3.vtk'),
        'refFine':   os.path.join(ref_folder,
                                  f'free_field_det{cfg["det"]}_w{cfg["weight"]}_1.vtk'),
        'refMedium': os.path.join(ref_folder,
                                  f'free_field_det{cfg["det"]}_w{cfg["weight"]}_2.vtk'),
        'refCoarse': os.path.join(ref_folder,
                                  f'free_field_det{cfg["det"]}_w{cfg["weight"]}_3.vtk'),
    }

    for key in ('fine', 'medium', 'coarse'):
        if not os.path.exists(files[key]):
            print('  Warning: missing config files')
            return data, success

    for key in ('refFine', 'refMedium', 'refCoarse'):
        if not os.path.exists(files[key]):
            print(f'  Warning: missing free field files for det{cfg["det"]}_w{cfg["weight"]}')
            return data, success

    try:
        data['peakP1'], data['impulse1'], data['X1'], data['Z1'] = readVTK(files['fine'])
        data['peakP2'], data['impulse2'], data['X2'], data['Z2'] = readVTK(files['medium'])
        data['peakP3'], data['impulse3'], data['X3'], data['Z3'] = readVTK(files['coarse'])

        data['refP1'], data['refI1'], _, _ = readVTK(files['refFine'])
        data['refP2'], data['refI2'], _, _ = readVTK(files['refMedium'])
        data['refP3'], data['refI3'], _, _ = readVTK(files['refCoarse'])
    except Exception as e:
        print(f'  Warning: Error reading VTK files - {e}')
        return data, success

    # Convert pressure units: Pa → kPa (impulse left in Pa·s)
    data['peakP1'] = data['peakP1'] / 1000
    data['peakP2'] = data['peakP2'] / 1000
    data['peakP3'] = data['peakP3'] / 1000
    data['refP1']  = data['refP1']  / 1000
    data['refP2']  = data['refP2']  / 1000
    data['refP3']  = data['refP3']  / 1000

    success = True
    return data, success
