"""Binary VTK structured-points reader.

``readVTK`` is the historical entry point and returns exactly what it always
did. ``read_vtk_full`` returns the same fields plus the grid definition
(origin / spacing / dimensions) and the dump time, which the raw NPZ store
(io/raw_store.py) persists so the grids can be rebuilt without the VTKs and
so the urban/reference dump times stay auditable.
"""

import struct

import numpy as np


def cell_coords(origin, spacing, dims):
    """Cell-centred (X, Z) meshgrid for a structured-points block.

    The single definition of the grid geometry: both the reader and the raw
    NPZ store go through here, so a rebuilt grid is bit-identical to the one
    read straight from the VTK.
    """
    x = origin[0] + spacing[0] * (np.arange(dims[0] - 1) + 0.5)
    z = origin[2] + spacing[2] * (np.arange(dims[2] - 1) + 0.5)
    return np.meshgrid(x, z)          # shape (nz, nx)


def read_vtk_full(filename):
    """Read a binary VTK structured-points file into a dict.

    Keys: peakP, peakImpulse (2-D, shape (nz, nx), big-endian float32 as
    stored), X, Z, origin, spacing, dims, time.

    *time* is the FieldData TIME entry — the dump time of the run. It is
    metadata only; nothing in the pipeline computes with it, but the urban
    and reference runs do not always share it, which is worth being able to
    see (see docs/ALGORITHM.md on the impulse criterion).
    """
    dims = origin = spacing = None
    peakP = peakImpulse = None
    time_val = np.nan

    with open(filename, 'rb') as fid:
        while True:
            raw_line = fid.readline()
            if not raw_line:
                break
            line = raw_line.decode('ascii', errors='ignore').rstrip()

            if line.startswith('DIMENSIONS'):
                parts = line.split()
                dims = [int(parts[1]), int(parts[2]), int(parts[3])]

            elif line.startswith('ORIGIN'):
                parts = line.split()
                origin = [float(parts[1]), float(parts[2]), float(parts[3])]

            elif line.startswith('SPACING'):
                parts = line.split()
                spacing = [float(parts[1]), float(parts[2]), float(parts[3])]

            elif line.startswith('TIME ') and line.endswith('float'):
                # 'TIME 1 1 float' followed by one big-endian float32.
                # Matched strictly: consuming 4 bytes on a false positive
                # would desync the header scan.
                time_val = float(struct.unpack('>f', fid.read(4))[0])

            elif line.startswith('SCALARS'):
                parts = line.split()
                current_field = parts[1]
                fid.readline()  # skip LOOKUP_TABLE line

                nx = dims[0] - 1
                nz = dims[2] - 1
                n_cells = nx * nz

                raw_data = fid.read(n_cells * 4)  # 4 bytes per float32
                # Big-endian float32; reshape (nz, nx) row-major matches the
                # producer's column-major write + transpose.
                data = np.frombuffer(raw_data, dtype='>f4').reshape((nz, nx))

                # 'Peak_Ovepressure' typo is in the VTK files themselves —
                # the name must match the data, do not "fix" it.
                if current_field == 'Peak_Ovepressure':
                    peakP = data
                elif current_field == 'Peak_Impulse':
                    peakImpulse = data

    X, Z = cell_coords(origin, spacing, dims)
    return {'peakP': peakP, 'peakImpulse': peakImpulse, 'X': X, 'Z': Z,
            'origin': origin, 'spacing': spacing, 'dims': dims,
            'time': time_val}


def readVTK(filename):
    """Read binary VTK structured points file.

    Returns: peakP, peakImpulse, X, Z  (2D arrays, shape (nz, nx))
    """
    v = read_vtk_full(filename)
    return v['peakP'], v['peakImpulse'], v['X'], v['Z']
