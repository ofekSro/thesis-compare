"""K-streak sensitivity of the convergence scan on the CLEAN data.

Monkeypatches convergence.K_CONSECUTIVE in memory (repo untouched) and
recomputes hard-scan radii for K = 2, 3, 4 for BOTH loads. A radius that
rides on smooth physics barely moves with K; one that rides on noisy
single-cell streaks jumps. Pressure (hard) serves as the reference — its
K-brittleness is what motivated the soft criterion.

Read-only w.r.t. the repo; writes only under the scratchpad.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())

from blastlib.config.parser import config_parser        # noqa: E402
from blastlib.geometry import exclude_radius, concat3   # noqa: E402
from blastlib.io import raw_store                       # noqa: E402
from blastlib.processing import convergence             # noqa: E402
from blastlib.processing.radius_estimator import resolve_estimator  # noqa: E402

SCRATCH = (r'C:\Users\OFEKRO~1\AppData\Local\Temp\claude'
           r'\c--Users-Ofek-Rotem-OneDrive---Technion--------------calculation-backup-compare-v7'
           r'\5e02194a-400f-42fe-9673-51f453008a59\scratchpad')
NPZ = 'data/raw_npz'
KS = [2, 3, 4]
est = resolve_estimator('req')

names = sorted(os.path.splitext(os.path.basename(f))[0]
               for f in glob.glob(os.path.join(NPZ, 'config_*.npz')))
print(f'{len(names)} configs, K = {KS}', flush=True)

rows = []
for i, name in enumerate(names):
    cfg = config_parser(name)
    raw, ok = raw_store.load_raw_data(NPZ, name)
    if not ok:
        continue
    processed = raw_store.expand(raw)
    all_ratio_P = concat3(processed, 'ratioP{}')
    all_ratio_I = concat3(processed, 'ratioI{}')
    all_X = concat3(processed, 'X{}')
    all_Z = concat3(processed, 'Z{}')
    exclude_r = exclude_radius(cfg)

    rec = {'ConfigName': name, 'Det': cfg['det']}
    for K in KS:
        convergence.K_CONSECUTIVE = K
        radius = convergence.find_convergence_radius(
            all_ratio_P, all_ratio_I,
            processed['peakP_all'], processed['peakI_all'],
            all_X, all_Z, exclude_r, estimator=est, soft_w_P=None)
        rec[f'P_{K}'] = radius['pressure']
        rec[f'I_{K}'] = radius['impulse']
    convergence.K_CONSECUTIVE = 3
    rows.append(rec)
    if (i + 1) % 16 == 0:
        print(f'  [{i+1}/{len(names)}]', flush=True)

df = pd.DataFrame(rows)
df.to_csv(os.path.join(SCRATCH, 'k_sensitivity.csv'), index=False)

print('\n|d ln R| when K changes (hard scan, both loads):', flush=True)
for lo, hi in ((2, 3), (3, 4)):
    for load in ('P', 'I'):
        d = np.abs(np.log(df[f'{load}_{hi}'] / df[f'{load}_{lo}']))
        big = (d > 0.10).sum()
        print(f'  {load}: K {lo}->{hi}: median {d.median():.4f}  '
              f'p90 {d.quantile(.9):.4f}  max {d.max():.3f}  '
              f'configs>10%: {big}/96')
        w = d.idxmax()
        print(f'      worst: {df.ConfigName[w]}  '
              f'{df[f"{load}_{lo}"][w]:.1f} -> {df[f"{load}_{hi}"][w]:.1f} m')
