import numpy as np


def readVTK(filename):
    """Read binary VTK structured points file.

    Returns: peakP, peakImpulse, X, Z  (2D arrays, shape (nz, nx))
    Equivalent to REFERENCES/pi_criterion_check/readVTK.m
    """
    with open(filename, 'rb') as fid:
        dims = None
        origin = None
        spacing = None
        peakP = None
        peakImpulse = None

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

            elif line.startswith('SCALARS'):
                parts = line.split()
                current_field = parts[1]
                fid.readline()  # skip LOOKUP_TABLE line

                nx = dims[0] - 1
                nz = dims[2] - 1
                n_cells = nx * nz

                raw_data = fid.read(n_cells * 4)  # 4 bytes per float32
                # Big-endian float32 — mirrors MATLAB: fread(fid, nCells, 'float', 'b')
                # MATLAB: reshape(data,[nx,nz])' uses column-major order then transpose.
                # Equivalent in NumPy: reshape (nz,nx) with default C (row-major) order.
                data = np.frombuffer(raw_data, dtype='>f4').reshape((nz, nx))

                if current_field == 'Peak_Ovepressure':  # typo preserved from original
                    peakP = data
                elif current_field == 'Peak_Impulse':
                    peakImpulse = data

    # Cell-centred coordinates
    # MATLAB: origin + spacing * (0.5 : (dims-1)-0.5)
    x = origin[0] + spacing[0] * (np.arange(dims[0] - 1) + 0.5)
    z = origin[2] + spacing[2] * (np.arange(dims[2] - 1) + 0.5)
    X, Z = np.meshgrid(x, z)  # shape (nz, nx)

    return peakP, peakImpulse, X, Z
