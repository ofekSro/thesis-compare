"""thr_I_scaled sensitivity scan on the CLEAN (trial) measurement chain.

Hypothesis (owner): the permissive impulse band (thr_I_scaled = 20) parks
R_conv,I where the deviation field is shallow, making the radius unstable
and hard to predict. Test: recompute RadiusI for several thresholds and see
whether stricter bands give (a) less threshold-sensitive and (b) more
predictable radii (LOGO of the same fixed forms).

Implementation: one raw load + one expand per config. Per threshold only the
ratioI pinning is redone from the RAW urban/reference impulse (exactly the
grids.py rule), then the standard 'req' sector scan runs. Validation: the
thr = 20 radii must equal the trial table's RadiusI bit-for-bit.
Read-only w.r.t. the repo; writes only under the scratchpad.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())

from blastlib import constants                                  # noqa: E402
from blastlib.config.parser import config_parser                # noqa: E402
from blastlib.geometry import exclude_radius, concat3           # noqa: E402
from blastlib.io import raw_store                               # noqa: E402
from blastlib.processing.convergence import find_convergence_radius  # noqa: E402
from blastlib.processing.radius_estimator import resolve_estimator   # noqa: E402

SCRATCH = (r'C:\Users\OFEKRO~1\AppData\Local\Temp\claude'
           r'\c--Users-Ofek-Rotem-OneDrive---Technion--------------calculation-backup-compare-v7'
           r'\5e02194a-400f-42fe-9673-51f453008a59\scratchpad')
TRIAL = 'outputs/tables_trial_2026-09-27/convergence_table_req_soft3.csv'
NPZ = 'data/raw_npz'
THRS = [5.0, 10.0, 15.0, 20.0, 30.0, 40.0]

trial = pd.read_csv(TRIAL).set_index('ConfigName')
est = resolve_estimator('req')

import glob                                                     # noqa: E402
names = sorted(os.path.splitext(os.path.basename(f))[0]
               for f in glob.glob(os.path.join(NPZ, 'config_*.npz')))
print(f'{len(names)} configs, thresholds {THRS}', flush=True)

rows = []
n_mismatch = 0
for i, name in enumerate(names):
    cfg = config_parser(name)
    raw, ok = raw_store.load_raw_data(NPZ, name)
    if not ok:
        print(f'  SKIP {name}', flush=True)
        continue
    processed = raw_store.expand(raw)
    data = raw_store.grids_from_raw(raw)
    W13 = float(cfg['weight']) ** (1 / 3)
    exclude_r = exclude_radius(cfg)

    all_ratio_P = concat3(processed, 'ratioP{}')
    all_X = concat3(processed, 'X{}')
    all_Z = concat3(processed, 'Z{}')

    rec = {'ConfigName': name, 'Det': cfg['det'], 'Height': cfg['height'],
           'BuildingSize': cfg['bsize'], 'StreetWidth': cfg['swidth'],
           'ChargeWeight': cfg['weight']}
    for thr in THRS:
        parts = []
        for g in ('1', '2', '3'):
            conv = (np.abs(data[f'impulse{g}'] - data[f'refI{g}']) / W13 < thr)
            ratio = processed[f'ratioI{g}_raw'].copy()
            m = conv & ~np.isnan(ratio)
            ratio[m] = 1.0
            if thr == 20.0:
                same = np.array_equal(ratio, processed[f'ratioI{g}'],
                                      equal_nan=True)
                if not same:
                    n_mismatch += 1
            parts.append(ratio)
        all_ratio_I = np.concatenate([p.ravel() for p in parts])
        radius = find_convergence_radius(
            all_ratio_P, all_ratio_I,
            processed['peakP_all'], processed['peakI_all'],
            all_X, all_Z, exclude_r, estimator=est, soft_w_P=None)
        rec[f'RI_{thr:g}'] = radius['impulse']
    rows.append(rec)
    if (i + 1) % 12 == 0:
        print(f'  [{i+1}/{len(names)}]', flush=True)

df = pd.DataFrame(rows)
df.to_csv(os.path.join(SCRATCH, 'thr_scan.csv'), index=False)
print(f'pinning mismatches at thr=20: {n_mismatch}', flush=True)

# validation vs trial table
v = df.merge(trial[['RadiusI']], left_on='ConfigName', right_index=True)
dmax = np.nanmax(np.abs(v['RI_20'] - v['RadiusI']))
print(f'thr=20 vs trial RadiusI: max |diff| = {dmax:.3e} m', flush=True)

# ---------- analysis ----------
df['W13'] = df.ChargeWeight.astype(float) ** (1 / 3)
df['hs'] = df.Height / df.StreetWidth
df['rho'] = (df.BuildingSize / (df.BuildingSize + df.StreetWidth)) ** 2
df['family'] = (df.Det.astype(str) + '_b' + df.BuildingSize.astype(str)
                + '_s' + df.StreetWidth.astype(str) + '_h' + df.Height.astype(str))

CHAMP = {
    1: ['ln_hs_sq', 'ln_pi2', 'ln_rho', 'rho_sqrt_hs', 'x_hs_pi2'],
    2: ['ln_hs_sq', 'ln_pi2', 'rho_sqrt_hs', 'x_hs_pi2', 'x_rho_pi2'],
}
QUAD = ['ln_rho', 'ln_hs', 'ln_pi2', 'ln_pi2_sq']


def feats(d):
    ln = np.log
    rho, hs = d.rho.values, d.hs.values
    pi2 = (d.StreetWidth / d.W13).values
    return {'ln_rho': ln(rho), 'ln_hs': ln(hs), 'ln_pi2': ln(pi2),
            'ln_pi2_sq': ln(pi2) ** 2, 'ln_hs_sq': ln(hs) ** 2,
            'rho_sqrt_hs': rho * np.sqrt(hs), 'x_hs_pi2': ln(hs) * ln(pi2),
            'x_rho_pi2': ln(rho) * ln(pi2)}


def logo(d, subset, zcol):
    apes = []
    for fam in d.family.unique():
        tr, te = d[d.family != fam], d[d.family == fam]
        Ftr, Fte = feats(tr), feats(te)
        Xtr = np.column_stack([np.ones(len(tr))] + [Ftr[k] for k in subset])
        Xte = np.column_stack([np.ones(len(te))] + [Fte[k] for k in subset])
        c, *_ = np.linalg.lstsq(Xtr, np.log(tr[zcol].values), rcond=None)
        apes.append(np.abs(np.exp(Xte @ c) / te[zcol].values - 1) * 100)
    return np.concatenate(apes)


print('\nthr | med Z_conv,I | elast. dlnR/dlnthr |'
      '  LOGO quad d1/d2  |  LOGO champ d1/d2')
prev = None
for thr in THRS:
    col = f'RI_{thr:g}'
    z = df[col] / df.W13
    df[f'Z_{thr:g}'] = z
    if prev is not None:
        el = (np.log(df[col]) - np.log(df[prev[0]])) / (np.log(thr) - np.log(prev[1]))
        el_txt = f'{np.nanmedian(el):+.3f}'
    else:
        el_txt = '  -  '
    parts_q, parts_c = [], []
    for det in (1, 2):
        d = df[(df.Det == det) & np.isfinite(df[col]) & (df[col] > 0)].copy()
        parts_q.append(f'{logo(d, QUAD, col).mean():5.2f}%')
        parts_c.append(f'{logo(d, CHAMP[det], col).mean():5.2f}%')
    print(f'{thr:4g} |    {z.median():6.2f}    |       {el_txt}       | '
          f'{" / ".join(parts_q)} | {" / ".join(parts_c)}', flush=True)
    prev = (col, thr)

# does per-config threshold sensitivity explain the LOGO error at thr=20?
el_local = np.abs((np.log(df['RI_30']) - np.log(df['RI_15']))
                  / (np.log(30) - np.log(15)))
for det in (1, 2):
    d = df[df.Det == det].copy()
    apes = []
    for fam in d.family.unique():
        tr, te = d[d.family != fam], d[d.family == fam]
        Ftr, Fte = feats(tr), feats(te)
        sub = CHAMP[det]
        Xtr = np.column_stack([np.ones(len(tr))] + [Ftr[k] for k in sub])
        Xte = np.column_stack([np.ones(len(te))] + [Fte[k] for k in sub])
        c, *_ = np.linalg.lstsq(Xtr, np.log(tr['RI_20'].values), rcond=None)
        ape = np.abs(np.exp(Xte @ c) / te['RI_20'].values - 1) * 100
        apes.extend(zip(te.index, ape))
    ape_s = pd.Series(dict(apes))
    r = np.corrcoef(el_local[ape_s.index], ape_s.values)[0, 1]
    print(f'det={det}: corr(|dlnR/dlnthr| at 15-30, champion LOGO APE) '
          f'= {r:+.2f}', flush=True)
print('done', flush=True)
