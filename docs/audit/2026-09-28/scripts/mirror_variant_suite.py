"""Owner's proposal (E): the exact structural MIRROR of the pressure
criterion, entirely in impulse ("isolation" — no pressure dependence):

    converged  iff  |I_urban - I_ff| / W^(1/3) < x   OR   I_urban / W^(1/3) < y

(absolute Hopkinson-scaled band + absolute Hopkinson-scaled urban floor,
like pressure's |dP| < 10 kPa OR P_urban < 10 kPa where band = floor).

Variants: x = y in {15, 20, 25}, plus x=20/y=25 (floor at the
pressure-floor-equivalent range Z~11).  Same harness as the previous
suites; scratchpad only, repo untouched.
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

SCRATCH = os.path.dirname(os.path.abspath(__file__))

# tag, band x [Pa.s/kg^(1/3)], floor y [Pa.s/kg^(1/3)], K
VARIANTS = [
    ('mir_x15_y15_K3', 15.0, 15.0, 3),
    ('mir_x20_y20_K3', 20.0, 20.0, 3),
    ('mir_x25_y25_K3', 25.0, 25.0, 3),
    ('mir_x20_y25_K3', 20.0, 25.0, 3),
]
est = resolve_estimator('req')

names = sorted(os.path.splitext(os.path.basename(f))[0]
               for f in glob.glob('data/raw_npz/config_*.npz'))

PART = os.path.join(SCRATCH, 'mirror_variant_partial.csv')
done = set()
rows = []
if os.path.exists(PART):
    prev = pd.read_csv(PART)
    rows = prev.to_dict('records')
    done = set(prev.ConfigName)
    print(f'resuming: {len(done)} configs already measured', flush=True)

import gc  # noqa: E402

for i, name in enumerate(names):
    if name in done:
        continue
    cfg = config_parser(name)
    raw, ok = raw_store.load_raw_data('data/raw_npz', name)
    if not ok:
        continue
    p_full = raw_store.expand(raw)
    W13 = float(cfg['weight']) ** (1 / 3)
    p = {}
    for g in ('1', '2', '3'):
        p[f'ratioI{g}_raw'] = p_full[f'ratioI{g}_raw'].astype(np.float32)
        p[f'X{g}'] = p_full[f'X{g}'].astype(np.float32)
        p[f'Z{g}'] = p_full[f'Z{g}'].astype(np.float32)
    p['peakI_all'] = p_full['peakI_all']
    p['peakP_all'] = p_full['peakP_all']
    imp = {g: raw[f'impulse{g}'].astype(np.float32) for g in ('1', '2', '3')}
    ref = {g: raw[f'refI{g}'].astype(np.float32) for g in ('1', '2', '3')}
    del p_full, raw
    gc.collect()
    X = concat3(p, 'X{}')
    Z = concat3(p, 'Z{}')
    all_ratio_P = np.full(X.shape, np.nan, dtype=np.float32)
    ex = exclude_radius(cfg)

    rec = {'ConfigName': name, 'Det': cfg['det'], 'Height': cfg['height'],
           'BuildingSize': cfg['bsize'], 'StreetWidth': cfg['swidth'],
           'ChargeWeight': cfg['weight'], 'W13': W13}
    for tag, x, y, K in VARIANTS:
        parts = []
        for g in ('1', '2', '3'):
            ratio = p[f'ratioI{g}_raw'].copy()
            conv = ((np.abs(imp[g] - ref[g]) / W13) < x) | ((imp[g] / W13) < y)
            viol = ~conv
            # bake the cell rule; scan with a tolerance the pinning drives
            ratio = np.where(np.isnan(ratio), np.nan,
                             np.where(viol, 10.0, 1.0))
            parts.append(ratio)
        all_ratio_I = np.concatenate([q.ravel() for q in parts])
        del parts
        convergence.TOLERANCE = 0.05
        convergence.K_CONSECUTIVE = K
        r = convergence.find_convergence_radius(
            all_ratio_P, all_ratio_I, p['peakP_all'], p['peakI_all'],
            X, Z, ex, estimator=est, soft_w_P=None)
        rec[tag] = r['impulse'] / W13
        del all_ratio_I
    convergence.TOLERANCE = 0.05
    convergence.K_CONSECUTIVE = 3
    rows.append(rec)
    del p, imp, ref, all_ratio_P, X, Z
    gc.collect()
    pd.DataFrame(rows).to_csv(PART, index=False)
    if (i + 1) % 12 == 0:
        print(f'  [{i+1}/{len(names)}]', flush=True)

df = pd.DataFrame(rows)
df.to_csv(os.path.join(SCRATCH, 'mirror_variant_suite.csv'), index=False)

conv_tbl = pd.read_csv('outputs/tables/convergence_table_req_soft3.csv')
conv_tbl['Z_P'] = conv_tbl.RadiusP / conv_tbl.ChargeWeight ** (1 / 3)
df = df.merge(conv_tbl[['ConfigName', 'Z_P']], on='ConfigName')

df['hs'] = df.Height / df.StreetWidth
df['pi2'] = df.StreetWidth / df.W13
df['rho'] = (df.BuildingSize / (df.BuildingSize + df.StreetWidth)) ** 2
df['family'] = (df.Det.astype(str) + '_b' + df.BuildingSize.astype(str)
                + '_s' + df.StreetWidth.astype(str) + '_h' + df.Height.astype(str))


def feats(d):
    ln = np.log
    return {'ln_rho': ln(d.rho), 'ln_hs': ln(d.hs), 'ln_pi2': ln(d.pi2),
            'ln_pi2_sq': ln(d.pi2) ** 2}


SUB = ['ln_rho', 'ln_hs', 'ln_pi2', 'ln_pi2_sq']


def logo(d, zcol):
    apes = []
    for fam in d.family.unique():
        tr, te = d[d.family != fam], d[d.family == fam]
        F1, F2 = feats(tr), feats(te)
        X1 = np.column_stack([np.ones(len(tr))] + [F1[k] for k in SUB])
        X2 = np.column_stack([np.ones(len(te))] + [F2[k] for k in SUB])
        c, *_ = np.linalg.lstsq(X1, np.log(tr[zcol].values), rcond=None)
        apes.append(np.abs(np.exp(X2 @ c) / te[zcol].values - 1) * 100)
    return np.concatenate(apes)


print('\nvariant           | med Z | p90 Z | max Z | Z>20 | Z_I>Z_P | '
      'LOGO quad mean/med')
for tag, *_ in VARIANTS:
    z = df[tag]
    a = np.concatenate([logo(df[df.Det == d_], tag) for d_ in (1, 2)])
    print(f'{tag:17s} | {z.median():5.2f} | {z.quantile(.9):5.2f} | '
          f'{z.max():5.2f} | {int((z > 20).sum()):3d} | '
          f'{int((z > df.Z_P).sum()):3d}/96 | {a.mean():5.2f}/{np.median(a):4.1f}')
print('\n(B pf10_b0.10: med 13.82, max 17.48, 0 beyond Z=20, LOGO 8.97/7.7)')
print('(A production:  med 18.64, max 32.43, 33 beyond Z=20, LOGO 8.64/5.9)')
