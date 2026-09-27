"""Load config and free-field VTK file pairs."""

import os

from blastlib.io.vtk_reader import read_vtk_full, readVTK


def vtk_paths(urban_folder, config_name, cfg, ref_folder=None):
    """The six file paths one configuration is built from.

    Defined once so the processed loader and the raw-store loader can never
    disagree about which reference file pairs with which config.
    """
    if ref_folder is None:
        ref_folder = urban_folder
    urban_folder, ref_folder = str(urban_folder), str(ref_folder)
    ff = f'free_field_det{cfg["det"]}_w{cfg["weight"]}'
    return {
        'fine':      os.path.join(urban_folder, f'{config_name}_1.vtk'),
        'medium':    os.path.join(urban_folder, f'{config_name}_2.vtk'),
        'coarse':    os.path.join(urban_folder, f'{config_name}_3.vtk'),
        'refFine':   os.path.join(ref_folder, f'{ff}_1.vtk'),
        'refMedium': os.path.join(ref_folder, f'{ff}_2.vtk'),
        'refCoarse': os.path.join(ref_folder, f'{ff}_3.vtk'),
    }


def _check_present(files, cfg):
    """(ok, message) — are all six VTKs on disk?"""
    for key in ('fine', 'medium', 'coarse'):
        if not os.path.exists(files[key]):
            return False, '  Warning: missing config files'
    for key in ('refFine', 'refMedium', 'refCoarse'):
        if not os.path.exists(files[key]):
            return False, ('  Warning: missing free field files for '
                           f'det{cfg["det"]}_w{cfg["weight"]}')
    return True, ''


def load_vtk_triplets(urban_folder, config_name, cfg, ref_folder=None):
    """Read all six VTKs in full (geometry + dump time retained).

    Returns (urban, reference, success) where *urban* and *reference* are
    {'1': read_vtk_full(...), '2': ..., '3': ...}. This is the raw-store
    path; load_vtk_pair below is the historical, field-only view of the same
    files.
    """
    files = vtk_paths(urban_folder, config_name, cfg, ref_folder)
    ok, msg = _check_present(files, cfg)
    if not ok:
        print(msg)
        return {}, {}, False

    try:
        urban = {g: read_vtk_full(files[k]) for g, k in
                 (('1', 'fine'), ('2', 'medium'), ('3', 'coarse'))}
        ref = {g: read_vtk_full(files[k]) for g, k in
               (('1', 'refFine'), ('2', 'refMedium'), ('3', 'refCoarse'))}
    except Exception as e:
        print(f'  Warning: Error reading VTK files - {e}')
        return {}, {}, False

    return urban, ref, True


def load_vtk_pair(urban_folder, config_name, cfg, ref_folder=None):
    """Load 3 urban VTK files + 3 free-field reference VTK files.

    Parameters
    ----------
    urban_folder : str or Path
        Folder containing the urban config VTK files.
    config_name : str
        Base config name (e.g. ``config_01_det1_b15_s5_h4_w50``).
    cfg : dict
        Parsed config parameters from ``config_parser``.
    ref_folder : str or Path, optional
        Folder containing free-field VTK files. Defaults to ``urban_folder``.

    Returns (data dict, success bool).
    data keys: X1/Z1/X2/Z2/X3/Z3,
               peakP1/peakP2/peakP3  (kPa),
               impulse1/impulse2/impulse3  (Pa·s, unchanged),
               refP1/refP2/refP3  (kPa),
               refI1/refI2/refI3  (Pa·s, unchanged)
    """
    data = {}
    success = False

    files = vtk_paths(urban_folder, config_name, cfg, ref_folder)
    ok, msg = _check_present(files, cfg)
    if not ok:
        print(msg)
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
