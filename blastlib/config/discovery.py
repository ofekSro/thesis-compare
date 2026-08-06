import os
import re
import glob


def find_configurations(vtks_folder):
    """Find all unique config base names in VTK folder.

    Returns sorted list of base names (without _1/_2/_3.vtk suffix).
    """
    pattern = os.path.join(str(vtks_folder), 'config_*.vtk')
    all_files = sorted(glob.glob(pattern))

    base_names = set()
    for filepath in all_files:
        filename = os.path.basename(filepath)
        m = re.match(r'(.*)_[123]\.vtk$', filename)
        if m:
            base_names.add(m.group(1))

    return sorted(base_names)


def resolve_config(token, known):
    """Map a user token to one name from *known*: exact, number, or prefix.

    'config_58_det2_b30_s5_h12_w50' -> itself; '58' -> the unique config
    whose number is 58; 'config_58' -> the unique prefix match. Returns None
    when the token matches nothing or more than one name — ambiguity is the
    caller's error to report, not this function's to guess through.

    (Moved from the retired tools/pressure_profile/pressure_profile.py; it
    is name resolution, not profiling.)
    """
    token = str(token).strip()
    if not token:
        return None
    if token in known:
        return token
    if token.isdigit():
        n = int(token)
        hits = [c for c in known if _config_number(c) == n]
        return hits[0] if len(hits) == 1 else None
    hits = [c for c in known if c.startswith(token)]
    return hits[0] if len(hits) == 1 else None


def _config_number(name):
    m = re.match(r'config_(\d+)_', name)
    return int(m.group(1)) if m else None
