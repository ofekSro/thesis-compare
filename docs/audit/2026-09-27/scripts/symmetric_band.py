"""Symmetric-relative-band diagnostic: measure BOTH convergence radii with
the same pure relative criterion |ratio - 1| > alpha (no floors, no
scaled band), alpha in {0.2, 0.3, 0.5}. If the urban impulse influence
truly persists farther than the pressure influence, Z_conv,I > Z_conv,P
under this symmetric yardstick.

Implementation: unpinned ratio fields (ratioP/I_raw, post raw-mask),
hard K=3 scan via find_convergence_radius with TOLERANCE monkeypatched
in memory. Repo untouched; scratchpad output only.
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
ALPHAS = [0.2, 0.3, 0.5]
est = resolve_estimator('req')

names = sorted(os.path.splitext(os.path.basename(f))[0]
               for f in glob.glob('data/raw_npz/config_*.npz'))
rows = []
for i, name in enumerate(names):
    cfg = config_parser(name)
    raw, ok = raw_store.load_raw_data('data/raw_npz', name)
    if not ok:
        continue
    p = raw_store.expand(raw)
    rp = concat3(p, 'ratioP{}_raw')
    ri = concat3(p, 'ratioI{}_raw')
    X = concat3(p, 'X{}')
    Z = concat3(p, 'Z{}')
    ex = exclude_radius(cfg)
    W13 = float(cfg['weight']) ** (1 / 3)
    rec = {'ConfigName': name, 'W13': W13}
    for a in ALPHAS:
        convergence.TOLERANCE = a
        r = convergence.find_convergence_radius(
            rp, ri, p['peakP_all'], p['peakI_all'], X, Z, ex,
            estimator=est, soft_w_P=None)
        rec[f'ZP_{a}'] = r['pressure'] / W13
        rec[f'ZI_{a}'] = r['impulse'] / W13
    convergence.TOLERANCE = 0.05
    rows.append(rec)
    if (i + 1) % 16 == 0:
        print(f'  [{i+1}/{len(names)}]', flush=True)

df = pd.DataFrame(rows)
df.to_csv(os.path.join(SCRATCH, 'symmetric_band.csv'), index=False)
print('\nsymmetric relative band |ratio-1| > alpha, both loads:')
for a in ALPHAS:
    zp, zi = df[f'ZP_{a}'], df[f'ZI_{a}']
    frac = (zi > zp).mean() * 100
    print(f'  alpha={a:.1f}: median Z_conv P = {zp.median():5.2f}  '
          f'I = {zi.median():5.2f}   I > P in {frac:.0f}% of configs')
