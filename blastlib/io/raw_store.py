"""Raw (schema v3) NPZ store — the measurement, with no criterion applied.

WHY THIS EXISTS
---------------
The v1/v2 stores held *processed* arrays: the multi-resolution fill, the
threshold mask, the smart cut, the urban/free-field ratios and the pinning of
converged cells to ratio = 1 were all baked in at preprocessing time. That
made every criterion a property of the stored file rather than of the
analysis, so changing the pressure threshold, the impulse band, the tolerance
or the projection sharpness meant regenerating ~7 GB from the raw VTKs — and
the raw urban impulse was not stored at all, so the impulse criterion could
not be re-derived from a v2 file even in principle.

A v3 file stores only what the solver produced, per resolution level:

    peakP{g}    urban peak overpressure      [kPa]   float32
    impulse{g}  urban peak impulse           [Pa.s]  float32
    refP{g}     free-field peak overpressure [kPa]   float32
    refI{g}     free-field peak impulse      [Pa.s]  float32

plus the grid definition (origin / spacing / dims), the parsed configuration
(det, weight, bsize, swidth, height) and the urban/reference dump times.
Coordinates are NOT stored: they are an exact function of origin/spacing/dims
and are rebuilt through vtk_reader.cell_coords, which is also what the reader
uses — so a rebuilt X/Z is bit-identical to the one read from the VTK.

Everything downstream of the solver — fill, mask, cut, ratio, convergence
pinning, soft weights — is applied by processing.grids.process_grids at
analysis time. ``expand`` below is the bridge: it returns exactly the dict
``process_grids`` expects, so the processed arrays a v3 file yields are
bit-identical to the shipped v2 ones (tests/test_raw_store.py asserts this).

Cost of the move: ~0.3 s per config to rebuild, against roughly a fifth of
the disk (no derived arrays, float32 instead of float64, no coordinates).
"""

import os

import numpy as np

from blastlib.io.vtk_reader import cell_coords

SCHEMA_VERSION = 3

# The four measured fields, per resolution level. Order is not significant.
FIELD_KEYS = ('peakP', 'impulse', 'refP', 'refI')

# Grid definition, per resolution level.
GRID_KEYS = ('origin', 'spacing', 'dims')

# Config scalars parsed from the config name and stored explicitly, so nothing
# downstream has to re-parse a filename to know the charge weight.
META_KEYS = ('det', 'weight', 'bsize', 'swidth', 'height')

LEVELS = ('1', '2', '3')


def raw_keys():
    """Every array key a complete v3 file must contain."""
    return (tuple(f'{f}{g}' for f in FIELD_KEYS for g in LEVELS)
            + tuple(f'{k}{g}' for k in GRID_KEYS for g in LEVELS)
            + ('schema_version',))


def is_raw_file(path):
    """True if *path* is a v3 raw store (cheap — reads the key listing only)."""
    try:
        with np.load(path, allow_pickle=False) as npz:
            if 'schema_version' not in npz.files:
                return False
            return int(npz['schema_version']) >= 3
    except Exception:
        return False


def is_raw_dir(npz_dir):
    """True if *npz_dir* holds v3 raw files (decided by the first one)."""
    from pathlib import Path
    d = Path(npz_dir)
    if not d.is_dir():
        return False
    sample = next(iter(sorted(d.glob('config_*.npz'))), None)
    return sample is not None and is_raw_file(sample)


def build_raw(vtk_full, ref_full, cfg):
    """Assemble the v3 payload from six read_vtk_full() results.

    *vtk_full* / *ref_full* are dicts {level: read_vtk_full(...)} for the
    urban and reference triplets; *cfg* is the parsed config dict.

    Pressure is converted Pa -> kPa here, exactly as load_vtk_pair does, and
    stored float32: the solver wrote float32, the division by 1000 keeps
    float32, so the store is lossless rather than merely close.
    """
    out = {'schema_version': np.int32(SCHEMA_VERSION)}
    for key in META_KEYS:
        out[key] = np.int32(cfg[key])

    for g in LEVELS:
        u, r = vtk_full[g], ref_full[g]
        out[f'peakP{g}']   = np.asarray(u['peakP'] / 1000.0, dtype=np.float32)
        out[f'impulse{g}'] = np.asarray(u['peakImpulse'],    dtype=np.float32)
        out[f'refP{g}']    = np.asarray(r['peakP'] / 1000.0, dtype=np.float32)
        out[f'refI{g}']    = np.asarray(r['peakImpulse'],    dtype=np.float32)
        out[f'origin{g}']  = np.asarray(u['origin'],  dtype=np.float64)
        out[f'spacing{g}'] = np.asarray(u['spacing'], dtype=np.float64)
        out[f'dims{g}']    = np.asarray(u['dims'],    dtype=np.int64)
        out[f't_urban{g}'] = np.float64(u['time'])
        out[f't_ref{g}']   = np.float64(r['time'])

    return out


def save_raw_data(npz_dir, config_name, raw, progress=None):
    """Write one v3 file. Compressed: the fields hold large constant regions."""
    path = os.path.join(str(npz_dir), f'{config_name}.npz')
    np.savez_compressed(path, **raw)
    if progress:
        progress(f'  Saved raw NPZ: {config_name}.npz')
    return path


def load_raw_data(npz_dir, config_name):
    """Load one v3 file into a plain dict. Returns (raw, success)."""
    path = os.path.join(str(npz_dir), f'{config_name}.npz')
    if not os.path.exists(path):
        return {}, False
    try:
        with np.load(path, allow_pickle=False) as npz:
            missing = set(raw_keys()) - set(npz.files)
            if missing:
                return {}, False
            raw = {k: npz[k] for k in npz.files}
    except Exception:
        return {}, False
    return raw, True


def grids_from_raw(raw):
    """Rebuild the dict process_grids() consumes, from a v3 payload.

    Coordinates come from cell_coords(origin, spacing, dims) — the same call
    the VTK reader makes — so they are bit-identical to reading the VTK.
    Fields are handed back in the dtype the historical path produced
    (float32), so the arithmetic downstream is unchanged too.
    """
    data = {}
    for g in LEVELS:
        X, Z = cell_coords(raw[f'origin{g}'], raw[f'spacing{g}'],
                           [int(v) for v in raw[f'dims{g}']])
        data[f'X{g}'] = X
        data[f'Z{g}'] = Z
        for f in FIELD_KEYS:
            data[f'{f}{g}'] = raw[f'{f}{g}']
    return data


def config_from_raw(raw):
    """The parsed configuration the file was built with."""
    cfg = {k: int(raw[k]) for k in META_KEYS}
    # axis_limit is presentation-only and derived, kept for parity with
    # config_parser so callers can use either source interchangeably.
    w = cfg['weight']
    cfg['axis_limit'] = 100 if w == 50 else (150 if w == 500 else 200)
    return cfg


def expand(raw, params=None, weight=None):
    """v3 payload -> the processed dict the analysis expects.

    This is where every criterion is applied, at analysis time: *params*
    carries the pressure threshold / convergence band (default
    constants.PARAMS) and *weight* the charge weight used by the scaled
    impulse criterion (default: the weight stored in the file).

    Imported lazily so blastlib.io stays importable without the processing
    package having been loaded.
    """
    from blastlib import constants
    from blastlib.processing.grids import process_grids

    if params is None:
        params = dict(constants.PARAMS)
    if weight is None:
        weight = float(raw['weight'])
    return process_grids(grids_from_raw(raw), params, weight=weight)


def dump_times(raw):
    """{level: (t_urban, t_ref)} — provenance, not used in any computation."""
    return {g: (float(raw[f't_urban{g}']), float(raw[f't_ref{g}']))
            for g in LEVELS if f't_urban{g}' in raw}
