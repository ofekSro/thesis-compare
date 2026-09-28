"""Candidate impulse criterion with a PRESSURE-relevance floor:

    converged  iff  |i - i_ff| / i_ff < beta   OR   P_urban_peak < pfloor

Rationale under test: damage needs pressure AND impulse (P-I curves have a
pressure asymptote), so where the urban peak pressure is below the 10 kPa
structural floor (IATG-anchored, audit D7/D8a), amplified impulse is
irrelevant regardless of magnitude. This bounds R_conv,I by the urban
10 kPa contour instead of letting it ride the amplified-impulse tail to
Z ~ 32.

Variants (one pass, resumable, float32 — same harness as
criterion_decision_suite.py):
  * pf10_b0.10_K3   — the candidate (band = production 10%)
  * pf10_b0.15/0.20 — band sensitivity
  * pf10only        — pressure floor alone (where the floor sits)
  * pf9 / pf11 at b=0.10 — IATG tier sensitivity (9 / 11 kPa tiers)
  * pf10_if20_b0.10 — union with the impulse floor 20 (is it redundant?)

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

SCRATCH = os.path.dirname(os.path.abspath(__file__))

# tag, beta (scan tolerance; None = floor-only), pfloor [kPa], with_ifloor20, K
VARIANTS = [
    ('pf10_b0.10_K3', 0.10, 10.0, False, 3),
    ('pf10_b0.15_K3', 0.15, 10.0, False, 3),
    ('pf10_b0.20_K3', 0.20, 10.0, False, 3),
    ('pf10only_K3',   None, 10.0, False, 3),
    ('pf9_b0.10_K3',  0.10,  9.0, False, 3),
    ('pf11_b0.10_K3', 0.10, 11.0, False, 3),
    ('pf10_if20_b0.10_K3', 0.10, 10.0, True, 3),
]
est = resolve_estimator('req')

names = sorted(os.path.splitext(os.path.basename(f))[0]
               for f in glob.glob('data/raw_npz/config_*.npz'))

PART = os.path.join(SCRATCH, 'pfloor_variant_partial.csv')
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
    pk = {g: raw[f'peakP{g}'].astype(np.float32) for g in ('1', '2', '3')}
    imp = {g: raw[f'impulse{g}'] for g in ('1', '2', '3')}
    del p_full, raw
    gc.collect()
    X = concat3(p, 'X{}')
    Z = concat3(p, 'Z{}')
    all_ratio_P = np.full(X.shape, np.nan, dtype=np.float32)
    ex = exclude_radius(cfg)

    rec = {'ConfigName': name, 'Det': cfg['det'], 'Height': cfg['height'],
           'BuildingSize': cfg['bsize'], 'StreetWidth': cfg['swidth'],
           'ChargeWeight': cfg['weight'], 'W13': W13}
    for tag, beta, pfloor, with_if, K in VARIANTS:
        parts = []
        for g in ('1', '2', '3'):
            ratio = p[f'ratioI{g}_raw'].copy()
            pin = pk[g] < pfloor
            if with_if:
                pin = pin | ((imp[g] / W13) < 20.0)
            if beta is None:
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
    del p, pk, imp, all_ratio_P, X, Z
    gc.collect()
    pd.DataFrame(rows).to_csv(PART, index=False)
    if (i + 1) % 12 == 0:
        print(f'  [{i+1}/{len(names)}]', flush=True)

df = pd.DataFrame(rows)
df.to_csv(os.path.join(SCRATCH, 'pfloor_variant_suite.csv'), index=False)

# ---- summary: medians, max, ordering vs Z_conv,P, LOGO of the quad form ----
conv = pd.read_csv('outputs/tables/convergence_table_req_soft3.csv')
conv['Z_P'] = conv.RadiusP / conv.ChargeWeight ** (1 / 3)
df = df.merge(conv[['ConfigName', 'Z_P']], on='ConfigName')

df['hs'] = df.Height / df.StreetWidth
df['pi2'] = df.StreetWidth / df.W13
df['rho'] = (df.BuildingSize / (df.BuildingSize + df.StreetWidth)) ** 2
df['family'] = (df.Det.astype(str) + '_b' + df.BuildingSize.astype(str)
                + '_s' + df.StreetWidth.astype(str) + '_h' + df.Height.astype(str))


def feats(d):
    ln = np.log
    return {'ln_rho': ln(d.rho), 'ln_hs': ln(d.hs), 'ln_pi2': ln(d.pi2),
            'ln_pi2_sq': ln(d.pi2) ** 2}


SUB = ['ln_rho', 'ln_hs', 'ln_pi2', 'ln_pi2_sq']  # quad power law


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


print('\nvariant              | med Z | p90 Z | max Z | Z_I>Z_P | '
      'LOGO quad mean/med')
for tag, *_ in VARIANTS:
    z = df[tag]
    a = np.concatenate([logo(df[df.Det == d_], tag) for d_ in (1, 2)])
    print(f'{tag:20s} | {z.median():5.2f} | {z.quantile(.9):5.2f} | '
          f'{z.max():5.2f} | {int((z > df.Z_P).sum()):3d}/96 | '
          f'{a.mean():5.2f}/{np.median(a):4.1f}')
print('\n(production b0.1_f20: med 18.64, max 32.43, LOGO 8.64/5.9)')
