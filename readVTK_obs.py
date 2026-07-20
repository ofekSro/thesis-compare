"""Read binary VTK unstructured-grid files (obstacle / building-surface data).

Returns points, cell connectivity, and per-cell scalar fields
(pressure, Peak_Ovepressure, Peak_Impulse).
"""

import numpy as np


def readVTK_obs(filename):
    """Read a binary VTK UNSTRUCTURED_GRID file from the OBS folder.

    Returns
    -------
    points : ndarray, shape (N, 3)
        Vertex coordinates (X, Y, Z).
    cells : ndarray, shape (M, 4)
        Quad cell connectivity (4 vertex indices per cell).
    scalars : dict
        Per-cell scalar fields, keyed by field name.
        Expected keys: 'pressure', 'Peak_Ovepressure', 'Peak_Impulse'.
    """
    with open(filename, 'rb') as fid:
        # --- Header ---
        fid.readline()  # # vtk DataFile Version ...
        fid.readline()  # title
        fid.readline()  # BINARY
        fid.readline()  # DATASET UNSTRUCTURED_GRID

        # --- POINTS ---
        line = fid.readline().decode('ascii').strip()
        npts = int(line.split()[1])
        points = np.frombuffer(fid.read(npts * 3 * 4), dtype='>f4').reshape(npts, 3)

        # --- CELLS ---
        # Skip blank lines until we find CELLS
        while True:
            line = fid.readline().decode('ascii', errors='replace').strip()
            if line.startswith('CELLS'):
                break
        parts = line.split()
        ncells = int(parts[1])
        total_ints = int(parts[2])
        cell_raw = np.frombuffer(fid.read(total_ints * 4), dtype='>i4')
        # Each cell: [4, i0, i1, i2, i3] → keep only indices
        cells = cell_raw.reshape(ncells, total_ints // ncells)[:, 1:]

        # --- CELL_TYPES (skip) ---
        while True:
            line = fid.readline().decode('ascii', errors='replace').strip()
            if line.startswith('CELL_TYPES'):
                break
        n_types = int(line.split()[1])
        fid.read(n_types * 4)

        # --- FIELD FieldData (skip TIME) ---
        while True:
            line = fid.readline().decode('ascii', errors='replace').strip()
            if line.startswith('FIELD'):
                n_fields = int(line.split()[-1])
                for _ in range(n_fields):
                    field_line = fid.readline().decode('ascii', errors='replace').strip()
                    # e.g. "TIME 1 1 float"
                    field_parts = field_line.split()
                    n_tuples = int(field_parts[2])
                    fid.read(n_tuples * 4)
                break
            if line.startswith('CELL_DATA'):
                # No FIELD section — we already hit CELL_DATA
                break

        # --- CELL_DATA ---
        if not line.startswith('CELL_DATA'):
            while True:
                line = fid.readline().decode('ascii', errors='replace').strip()
                if line.startswith('CELL_DATA'):
                    break

        # --- Read SCALARS blocks ---
        scalars = {}
        while True:
            raw = fid.readline()
            if not raw:
                break
            line = raw.decode('ascii', errors='replace').strip()
            if line.startswith('SCALARS'):
                field_name = line.split()[1]
                fid.readline()  # LOOKUP_TABLE default
                data = np.frombuffer(fid.read(ncells * 4), dtype='>f4')
                scalars[field_name] = data.copy()

    return points, cells, scalars
