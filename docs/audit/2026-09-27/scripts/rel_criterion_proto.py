"""Prototype of the owner's proposed impulse criterion:

    converged  iff  |i - i_ff| / i_ff < beta   OR   i_urban / W^(1/3) < 20

(relative accuracy band + scaled relevance floor; mirrors the pressure
criterion's difference-clause + floor structure). Measured for
beta in {0.2, 0.3, 0.5} on all 96 configs: radii, the 93/95 stability
pair, and LOGO of the unified form refitted on the resulting radii.
In-memory only; repo untouched.
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
BETAS = [0.2, 0.3, 0.5]
FLOOR = 20.0
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
    W13 = float(cfg['weight']) ** (1 / 3)

    parts = {}
    for g in ('1', '2', '3'):
        ratio = p[f'ratioI{g}_raw'].copy()
        floor_pin = (raw[f'impulse{g}'] / W13) < FLOOR
        m = floor_pin & ~np.isnan(ratio)
        ratio[m] = 1.0
        parts[g] = ratio
    all_ratio_I = np.concatenate([parts[g].ravel() for g in ('1', '2', '3')])
    all_ratio_P = concat3(p, 'ratioP{}')
    X = concat3(p, 'X{}')
    Z = concat3(p, 'Z{}')
    ex = exclude_radius(cfg)

    rec = {'ConfigName': name, 'Det': cfg['det'], 'Height': cfg['height'],
           'BuildingSize': cfg['bsize'], 'StreetWidth': cfg['swidth'],
           'ChargeWeight': cfg['weight'], 'W13': W13}
    for b in BETAS:
        convergence.TOLERANCE = b
        r = convergence.find_convergence_radius(
            all_ratio_P, all_ratio_I, p['peakP_all'], p['peakI_all'],
            X, Z, ex, estimator=est, soft_w_P=None)
        rec[f'ZI_{b}'] = r['impulse'] / W13
    convergence.TOLERANCE = 0.05
    rows.append(rec)
    if (i + 1) % 16 == 0:
        print(f'  [{i+1}/{len(names)}]', flush=True)

df = pd.DataFrame(rows)
df.to_csv(os.path.join(SCRATCH, 'rel_criterion_proto.csv'), index=False)

df['hs'] = df.Height / df.StreetWidth
df['pi2'] = df.StreetWidth / df.W13
df['rho'] = (df.BuildingSize / (df.BuildingSize + df.StreetWidth)) ** 2
df['family'] = (df.Det.astype(str) + '_b' + df.BuildingSize.astype(str)
                + '_s' + df.StreetWidth.astype(str) + '_h' + df.Height.astype(str))

UNIFIED = ['rho_sqrt_hs', 'ln_hs_sq', 'x_hs_pi2', 'ln_pi2', 'x_rho_pi2']


def feats(d):
    ln = np.log
    return {'ln_pi2': ln(d.pi2), 'ln_hs_sq': ln(d.hs) ** 2,
            'x_hs_pi2': ln(d.hs) * ln(d.pi2),
            'x_rho_pi2': ln(d.rho) * ln(d.pi2),
            'rho_sqrt_hs': d.rho * np.sqrt(d.hs)}


def logo(d, zcol):
    apes = []
    for fam in d.family.unique():
        tr, te = d[d.family != fam], d[d.family == fam]
        Ftr, Fte = feats(tr), feats(te)
        Xtr = np.column_stack([np.ones(len(tr))] + [Ftr[k] for k in UNIFIED])
        Xte = np.column_stack([np.ones(len(te))] + [Fte[k] for k in UNIFIED])
        c, *_ = np.linalg.lstsq(Xtr, np.log(tr[zcol].values), rcond=None)
        apes.append(np.abs(np.exp(Xte @ c) / te[zcol].values - 1) * 100)
    return np.concatenate(apes)


print('\nproposed criterion |di|/i_ff < beta OR i/W^(1/3) < 20:')
print('beta | median Z_I | max Z_I | 93/95 pair [m] | LOGO unified '
      '(mean/med/p90/max, pooled)')
for b in BETAS:
    zc = f'ZI_{b}'
    z = df[zc]
    p93 = df[df.ConfigName.str.startswith('config_93')][zc].iloc[0] * \
        df[df.ConfigName.str.startswith('config_93')].W13.iloc[0]
    p95 = df[df.ConfigName.str.startswith('config_95')][zc].iloc[0] * \
        df[df.ConfigName.str.startswith('config_95')].W13.iloc[0]
    a = np.concatenate([logo(df[df.Det == d_], zc) for d_ in (1, 2)])
    print(f'{b:4.1f} | {z.median():8.2f} | {z.max():6.2f} | '
          f'{p93:5.1f} / {p95:5.1f} | {a.mean():5.2f} / {np.median(a):5.2f} / '
          f'{np.percentile(a, 90):5.1f} / {a.max():5.1f}')
print('\nreference (current criterion): median 7.58, max 24.42; '
      'LOGO 11.0 / 9.1 / 23.3 / 54.7')
