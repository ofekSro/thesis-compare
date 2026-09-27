"""Soft (tanh-projected) pressure convergence criterion — per-cell weights.

The hard criterion pins a cell to "converged" when P_raw < minPressure_kPa
or |P_raw - P_ref| < minPressure_kPa (grids.process_grids). Where the free
field itself sits near 10 kPa (Z >~ 10) that absolute band swallows real
amplification lobes, so a lobe peak grazing the threshold flips tens of
meters of radius. This module replaces ONLY the |dP| band with a smoothed
Heaviside (Wang-Lazarov-Sigmund projection); the low-pressure floor and
the +-5% ratio gate stay hard.

Per-cell weight ("probability that the cell is a real exceedance"):

    x   = clip(|P_raw - P_ref| / softCap_kPa, 0, 1)
    eta = minPressure_kPa / softCap_kPa
    w   = gate * (tanh(b*eta) + tanh(b*(x - eta)))
               / (tanh(b*eta) + tanh(b*(1 - eta)))
    gate = 1[|ratio_raw - 1| > TOLERANCE] * 1[P_raw >= minPressure_kPa]

w(0) = 0 and w(1) = 1 exactly; w = 0.5 exactly at |dP| = minPressure_kPa
for every beta; beta -> inf reproduces the hard band indicator.

Requires the v2 NPZ superset keys (peakP{g}_raw, refP{g}, ratioP{g}_raw)
— the raw band operands the shipped v1 files never stored. The impulse
criterion is untouched by everything here.
"""

from pathlib import Path

import numpy as np

from blastlib import constants, paths
from blastlib.processing.convergence import TOLERANCE

V2_KEYS = tuple(f'{stem}{g}{suffix}'
                for stem, suffix in (('peakP', '_raw'), ('refP', ''),
                                     ('ratioP', '_raw'))
                for g in '123')


def raw_fields_available(npz_dir=None):
    """(ok, reason) — can the soft criterion run against *npz_dir*?

    Two kinds of folder qualify:

    * a **v3 raw store** — the criteria are applied at load time, so the raw
      band fields are produced on the fly and are always available;
    * a **v2 superset** — the raw fields were written at preprocessing time,
      so the first file's key listing has to carry them.

    A v1 folder does not qualify. Reading the npz table of contents is cheap
    (no arrays are loaded). None -> paths.default_npz_dir(soft=True).

    Made for preflight/GUI gating: callers show *reason* instead of
    letting a soft run die on the missing keys mid-pipeline.
    """
    from blastlib.io import raw_store

    npz_dir = Path(paths.default_npz_dir(soft=True) if npz_dir is None
                   else npz_dir)
    if not npz_dir.is_dir():
        return False, (f'{npz_dir} does not exist — regenerate the NPZ set '
                       f'with run_preprocess.py (see README).')
    sample = next(iter(sorted(npz_dir.glob('config_*.npz'))), None)
    if sample is None:
        return False, f'no config_*.npz in {npz_dir}.'
    if raw_store.is_raw_file(sample):
        return True, ''
    try:
        with np.load(sample, allow_pickle=True) as npz:
            missing = [k for k in V2_KEYS if k not in npz.files]
    except Exception as exc:
        return False, f'could not read {sample.name}: {exc}'
    if missing:
        return False, (f'{sample.name} lacks the raw fields {missing} — '
                       f'these NPZs predate the v2 superset; regenerate with '
                       f'run_preprocess.py (which now writes the v3 raw '
                       f'store, and that serves the soft criterion too).')
    return True, ''


def tanh_projection(x, beta, eta):
    """Wang-Lazarov-Sigmund smoothed Heaviside on [0, 1].

    (tanh(b*eta) + tanh(b*(x - eta))) / (tanh(b*eta) + tanh(b*(1 - eta)))
    """
    x = np.asarray(x, dtype=float)
    b = float(beta)
    num = np.tanh(b * eta) + np.tanh(b * (x - eta))
    den = np.tanh(b * eta) + np.tanh(b * (1.0 - eta))
    return num / den


def soft_pressure_fields(processed, *, min_pressure_kPa=None,
                         tolerance=TOLERANCE):
    """Beta-independent per-cell fields, concatenated in concat3 order.

    Returns {'absdiff': |P_raw - P_ref| [kPa], 'gate': bool}, both 1-D over
    grids 1,2,3 raveled — aligned with peakP_all and concat3(...) arrays.
    absdiff is NaN exactly where ratioP{g}_raw is NaN, so the soft scanner
    sees the same valid-cell set as the legacy scanner (same masks; the
    pinning to 1.0 changed values, never NaNs).

    Raises KeyError with a pointed message on v1 NPZs (raw keys absent).
    """
    missing = [k for k in V2_KEYS if k not in processed]
    if missing:
        raise KeyError(
            f'NPZ lacks raw-field keys {missing} — the soft criterion needs '
            f'the v2 superset (data/processed_npz_v2, regenerated from the '
            f'raw VTKs by run_preprocess.py). Point --npz-dir there.')

    if min_pressure_kPa is None:
        min_pressure_kPa = constants.PARAMS['minPressure_kPa']

    absdiff_parts, gate_parts = [], []
    for g in '123':
        p_raw = np.asarray(processed[f'peakP{g}_raw'], dtype=float)
        ref = np.asarray(processed[f'refP{g}'], dtype=float)
        ratio_raw = np.asarray(processed[f'ratioP{g}_raw'], dtype=float)

        absdiff = np.abs(p_raw - ref)
        absdiff = np.where(np.isnan(ratio_raw), np.nan, absdiff)
        with np.errstate(invalid='ignore'):
            gate = ((np.abs(ratio_raw - 1.0) > tolerance)
                    & (p_raw >= min_pressure_kPa))

        absdiff_parts.append(absdiff.ravel())
        gate_parts.append(gate.ravel())

    return {'absdiff': np.concatenate(absdiff_parts),
            'gate': np.concatenate(gate_parts)}


def soft_pressure_weights(fields, beta, *, cap_kPa=None, min_pressure_kPa=None):
    """Per-cell exceedance weights w in [0, 1] (NaN where no data).

    *fields* is the dict from soft_pressure_fields; beta the projection
    sharpness. The gate multiplies the projection, so gated-off cells are
    exactly 0 at every beta.
    """
    if cap_kPa is None:
        cap_kPa = constants.PARAMS['softCap_kPa']
    if min_pressure_kPa is None:
        min_pressure_kPa = constants.PARAMS['minPressure_kPa']

    absdiff, gate = fields['absdiff'], fields['gate']
    eta = float(min_pressure_kPa) / float(cap_kPa)
    with np.errstate(invalid='ignore'):
        x = np.clip(absdiff / float(cap_kPa), 0.0, 1.0)
        w = np.where(gate, tanh_projection(x, beta, eta), 0.0)
    w[np.isnan(absdiff)] = np.nan
    return w
