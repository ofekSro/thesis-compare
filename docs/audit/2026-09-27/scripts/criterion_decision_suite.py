"""Decision suite for the NEW impulse convergence criterion (owner
decision, 2026-09-28):

    converged  iff  |i - i_ff| / i_ff < beta   OR   i_urban / W^(1/3) < floor

Variants measured in ONE pass over the 96 configs (each config loaded
once):
  * beta in {0.10, 0.15, 0.20, 0.25, 0.30} at floor = 20, K = 3
  * floor-only (no band) at floor = 20
  * floor sensitivity: 15 and 25 at beta = 0.20
  * K sensitivity: K = 2 and 4 at beta = 0.20, floor = 20

For every variant: per-config radii saved; summary = median/max Z, the
93/95 pair, and LOGO of three forms (legacy power, quad power, unified).
Repo untouched; scratchpad output only.
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

VARIANTS = ([(f'b{b:g}_f20_K3', b, 20.0, 3) for b in
             (0.10, 0.15, 0.20, 0.25, 0.30)]
            + [('flooronly_f20_K3', None, 20.0, 3),
               ('b0.2_f15_K3', 0.20, 15.0, 3),
               ('b0.2_f25_K3', 0.20, 25.0, 3),
               ('b0.2_f20_K2', 0.20, 20.0, 2),
               ('b0.2_f20_K4', 0.20, 20.0, 4)])
est = resolve_estimator('req')

names = sorted(os.path.splitext(os.path.basename(f))[0]
               for f in glob.glob('data/raw_npz/config_*.npz'))

# Resumable: skip configs already in a partial CSV from a previous run.
PART = os.path.join(SCRATCH, 'criterion_decision_partial.csv')
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
    # Slim working set: keep only what the impulse scan needs, in float32.
    p = {}
    for g in ('1', '2', '3'):
        p[f'ratioI{g}_raw'] = p_full[f'ratioI{g}_raw'].astype(np.float32)
        p[f'X{g}'] = p_full[f'X{g}'].astype(np.float32)
        p[f'Z{g}'] = p_full[f'Z{g}'].astype(np.float32)
    p['peakI_all'] = p_full['peakI_all']
    p['peakP_all'] = p_full['peakP_all']
    imp = {g: raw[f'impulse{g}'] for g in ('1', '2', '3')}
    del p_full, raw
    gc.collect()
    X = concat3(p, 'X{}')
    Z = concat3(p, 'Z{}')
    all_ratio_P = np.full(X.shape, np.nan, dtype=np.float32)  # P not needed
    ex = exclude_radius(cfg)

    rec = {'ConfigName': name, 'Det': cfg['det'], 'Height': cfg['height'],
           'BuildingSize': cfg['bsize'], 'StreetWidth': cfg['swidth'],
           'ChargeWeight': cfg['weight'], 'W13': W13}
    for tag, beta, floor, K in VARIANTS:
        parts = []
        for g in ('1', '2', '3'):
            ratio = p[f'ratioI{g}_raw'].copy()
            pin = (imp[g] / W13) < floor
            if beta is None:
                # floor-only: everything above the floor is a violation,
                # i.e. converged iff below the floor
                viol = ~pin
                ratio = np.where(np.isnan(ratio), np.nan,
                                 np.where(viol, 10.0, 1.0))
            else:
                m = pin & ~np.isnan(ratio)
                ratio[m] = 1.0
            parts.append(ratio)
        all_ratio_I = np.concatenate([q.ravel() for q in parts])
        del parts
        convergence.TOLERANCE = beta if beta is not None else 0.05
        convergence.K_CONSECUTIVE = K
        r = convergence.find_convergence_radius(
            all_ratio_P, all_ratio_I, p['peakP_all'], p['peakI_all'],
            X, Z, ex, estimator=est, soft_w_P=None)
        rec[tag] = r['impulse'] / W13
        del all_ratio_I
    convergence.TOLERANCE = 0.05
    convergence.K_CONSECUTIVE = 3
    rows.append(rec)
    del p, imp, all_ratio_P, X, Z
    gc.collect()
    pd.DataFrame(rows).to_csv(PART, index=False)
    if (i + 1) % 12 == 0:
        print(f'  [{i+1}/{len(names)}]', flush=True)

df = pd.DataFrame(rows)
df.to_csv(os.path.join(SCRATCH, 'criterion_decision_suite.csv'), index=False)

df['hs'] = df.Height / df.StreetWidth
df['pi2'] = df.StreetWidth / df.W13
df['rho'] = (df.BuildingSize / (df.BuildingSize + df.StreetWidth)) ** 2
df['family'] = (df.Det.astype(str) + '_b' + df.BuildingSize.astype(str)
                + '_s' + df.StreetWidth.astype(str) + '_h' + df.Height.astype(str))

FORMS = {
    'legacy': ['ln_rho', 'ln_hs', 'ln_pi2'],
    'quad': ['ln_rho', 'ln_hs', 'ln_pi2', 'ln_pi2_sq'],
    'unified': ['rho_sqrt_hs', 'ln_hs_sq', 'x_hs_pi2', 'ln_pi2', 'x_rho_pi2'],
}


def feats(d):
    ln = np.log
    return {'ln_rho': ln(d.rho), 'ln_hs': ln(d.hs), 'ln_pi2': ln(d.pi2),
            'ln_pi2_sq': ln(d.pi2) ** 2, 'ln_hs_sq': ln(d.hs) ** 2,
            'x_hs_pi2': ln(d.hs) * ln(d.pi2),
            'x_rho_pi2': ln(d.rho) * ln(d.pi2),
            'rho_sqrt_hs': d.rho * np.sqrt(d.hs)}


def logo(d, sub, zcol):
    apes = []
    for fam in d.family.unique():
        tr, te = d[d.family != fam], d[d.family == fam]
        F1, F2 = feats(tr), feats(te)
        X1 = np.column_stack([np.ones(len(tr))] + [F1[k] for k in sub])
        X2 = np.column_stack([np.ones(len(te))] + [F2[k] for k in sub])
        c, *_ = np.linalg.lstsq(X1, np.log(tr[zcol].values), rcond=None)
        apes.append(np.abs(np.exp(X2 @ c) / te[zcol].values - 1) * 100)
    return np.concatenate(apes)


print('\nvariant          | med Z | max Z | 93/95 [m] | '
      'LOGO legacy | quad | unified  (mean/med)')
for tag, beta, floor, K in VARIANTS:
    z = df[tag]
    g93 = df[df.ConfigName.str.startswith('config_93')]
    g95 = df[df.ConfigName.str.startswith('config_95')]
    p93 = g93[tag].iloc[0] * g93.W13.iloc[0]
    p95 = g95[tag].iloc[0] * g95.W13.iloc[0]
    parts = []
    for fname, sub in FORMS.items():
        a = np.concatenate([logo(df[df.Det == d_], sub, tag)
                            for d_ in (1, 2)])
        parts.append(f'{a.mean():5.2f}/{np.median(a):4.1f}')
    print(f'{tag:16s} | {z.median():5.2f} | {z.max():5.2f} | '
          f'{p93:5.1f}/{p95:5.1f} | ' + ' | '.join(parts))
