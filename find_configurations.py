import os
import re
import glob


def find_configurations(vtks_folder):
    """Find all unique config base names in VTK folder.

    Returns sorted list of base names (without _1/_2/_3.vtk suffix).
    Equivalent to REFERENCES/pi_criterion_check/find_configurations.m
    """
    pattern = os.path.join(vtks_folder, 'config_*.vtk')
    all_files = sorted(glob.glob(pattern))

    base_names = set()
    for filepath in all_files:
        filename = os.path.basename(filepath)
        m = re.match(r'(.*)_[123]\.vtk$', filename)
        if m:
            base_names.add(m.group(1))

    return sorted(base_names)
