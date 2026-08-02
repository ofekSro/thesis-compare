"""Superset validation gate for the v2 (raw-field) NPZ regeneration.

Checks, for all 96 configs:
1. Every legacy key that feeds the pressure path is bit-identical
   (NaN-aware) between data/processed_npz (v1) and data/processed_npz_v2:
   X*, Z*, peakP*_orig, impulse*_orig, ratioP*, peakP_all, peakI_all,
   maxP, maxI. Any mismatch is a HARD failure.
2. ratioI{1,2,3} are compared and reported but ALLOWED to differ (the
   relaxed gate — shipped v1 could predate the scaled impulse criterion).
3. All 15 new raw keys are present (peakP{g}_raw, refP{g}, refI{g},
   ratioP{g}_raw, ratioI{g}_raw).
4. RadiusP recomputed from v2 through the legacy hard chain is bit-equal
   to the SAME computation on v1 for every config, and equal to the
   tracked convergence_table_req.csv within 1e-12 relative (the tracked
   table differs from today's recomputation by 1 ulp on 10/96 configs —
   numpy-version drift at table-write time, verified v1==v2 there).

Writes outputs/check_results/npz_v2_validation.csv and exits non-zero on
any hard failure.

Usage:
    python tools\\validate_npz_v2\\validate_npz_v2.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import numpy as np
import pandas as pd

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.geometry import concat3, exclude_radius
from blastlib.io.npz_store import load_processed_data
from blastlib.processing.convergence import find_convergence_radius

V2_DIR = paths.DATA_DIR / 'processed_npz_v2'

STRICT_KEYS = (
    'X1', 'Z1', 'X2', 'Z2', 'X3', 'Z3',
    'peakP1_orig', 'peakP2_orig', 'peakP3_orig',
    'impulse1_orig', 'impulse2_orig', 'impulse3_orig',
    'ratioP1', 'ratioP2', 'ratioP3',
    'peakP_all', 'peakI_all', 'maxP', 'maxI',
)
RELAXED_KEYS = ('ratioI1', 'ratioI2', 'ratioI3')
NEW_KEYS = tuple(
    f'{stem}{g}{suffix}'
    for stem, suffix in (('peakP', '_raw'), ('refP', ''), ('refI', ''),
                         ('ratioP', '_raw'), ('ratioI', '_raw'))
    for g in '123'
)


def _bit_equal(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if a.shape != b.shape:
        return False
    return bool(np.array_equal(a.astype(np.float64), b.astype(np.float64),
                               equal_nan=True))


def main(progress=print):
    conv = pd.read_csv(paths.conv_csv('req')).set_index('ConfigName')
    names = sorted(p.stem for p in Path(paths.PROCESSED_NPZ_DIR).glob('config_*.npz'))
    assert len(names) == 96, f'expected 96 v1 configs, found {len(names)}'

    rows = []
    hard_failures = 0
    ratio_i_diffs = 0

    for i, name in enumerate(names):
        v1, ok1 = load_processed_data(paths.PROCESSED_NPZ_DIR, name)
        v2, ok2 = load_processed_data(V2_DIR, name)
        row = {'Config': name, 'v1_load': ok1, 'v2_load': ok2}
        if not (ok1 and ok2):
            hard_failures += 1
            rows.append({**row, 'status': 'LOAD_FAIL'})
            progress(f'[{i+1}/96] {name}  LOAD FAIL')
            continue

        bad_strict = [k for k in STRICT_KEYS if not _bit_equal(v1[k], v2[k])]
        bad_relaxed = [k for k in RELAXED_KEYS if not _bit_equal(v1[k], v2[k])]
        missing_new = [k for k in NEW_KEYS if k not in v2]

        cfg = config_parser(name)

        def _radius_p(proc):
            return find_convergence_radius(
                concat3(proc, 'ratioP{}'), concat3(proc, 'ratioI{}'),
                proc['peakP_all'], proc['peakI_all'],
                concat3(proc, 'X{}'), concat3(proc, 'Z{}'),
                exclude_radius(cfg), estimator='req',
            )['pressure']

        r_p_v1 = _radius_p(v1)
        r_p_v2 = _radius_p(v2)
        r_p_table = conv.loc[name, 'RadiusP']
        v1v2_ok = (r_p_v2 == r_p_v1) or (np.isnan(r_p_v2) and np.isnan(r_p_v1))
        table_ok = (r_p_v2 == r_p_table) or (
            abs(r_p_v2 - r_p_table) <= 1e-12 * abs(r_p_table)) or (
            np.isnan(r_p_v2) and np.isnan(r_p_table))
        radius_ok = v1v2_ok and table_ok

        hard_ok = not bad_strict and not missing_new and radius_ok
        if not hard_ok:
            hard_failures += 1
        if bad_relaxed:
            ratio_i_diffs += 1

        row.update({
            'status': 'OK' if hard_ok else 'FAIL',
            'strict_mismatch': ';'.join(bad_strict),
            'ratioI_mismatch': ';'.join(bad_relaxed),
            'missing_new_keys': ';'.join(missing_new),
            'RadiusP_v1': r_p_v1,
            'RadiusP_v2': r_p_v2,
            'RadiusP_table': r_p_table,
            'RadiusP_v1v2_bitexact': v1v2_ok,
            'RadiusP_table_match': table_ok,
        })
        rows.append(row)
        progress(f'[{i+1}/96] {name}  '
                 f'{"OK" if hard_ok else "FAIL"}'
                 f'{"  (ratioI differs)" if bad_relaxed else ""}')

    out_csv = Path(paths.ensure_dir(paths.CHECK_RESULTS_DIR)) / 'npz_v2_validation.csv'
    pd.DataFrame(rows).to_csv(out_csv, index=False)

    progress(f'\nHard failures: {hard_failures}/96')
    progress(f'ratioI divergences (allowed, documented): {ratio_i_diffs}/96')
    progress(f'Wrote {out_csv}')
    if hard_failures:
        progress('GATE FAILED — do not proceed to the soft criterion.')
        return 1
    progress('GATE PASSED — v2 is a validated superset of v1.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
