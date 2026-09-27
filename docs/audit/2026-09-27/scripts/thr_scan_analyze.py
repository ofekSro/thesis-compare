"""Corrected analysis of thr_scan.csv: LOGO on Z = R/W^(1/3) (the previous
pass mistakenly fit ln R in metres, leaving the W^(1/3) factor unexplained).
"""
import numpy as np
import pandas as pd

SCRATCH = (r'C:\Users\OFEKRO~1\AppData\Local\Temp\claude'
           r'\c--Users-Ofek-Rotem-OneDrive---Technion--------------calculation-backup-compare-v7'
           r'\5e02194a-400f-42fe-9673-51f453008a59\scratchpad')
df = pd.read_csv(SCRATCH + r'\thr_scan.csv')
THRS = [5, 10, 15, 20, 30, 40]

df['W13'] = df.ChargeWeight.astype(float) ** (1 / 3)
df['hs'] = df.Height / df.StreetWidth
df['rho'] = (df.BuildingSize / (df.BuildingSize + df.StreetWidth)) ** 2
df['pi2'] = df.StreetWidth / df.W13
df['family'] = (df.Det.astype(str) + '_b' + df.BuildingSize.astype(str)
                + '_s' + df.StreetWidth.astype(str) + '_h' + df.Height.astype(str))
for thr in THRS:
    df[f'Z_{thr}'] = df[f'RI_{thr}'] / df.W13

CHAMP = {1: ['ln_hs_sq', 'ln_pi2', 'ln_rho', 'rho_sqrt_hs', 'x_hs_pi2'],
         2: ['ln_hs_sq', 'ln_pi2', 'rho_sqrt_hs', 'x_hs_pi2', 'x_rho_pi2']}
QUAD = ['ln_rho', 'ln_hs', 'ln_pi2', 'ln_pi2_sq']


def feats(d):
    ln = np.log
    rho, hs, pi2 = d.rho.values, d.hs.values, d.pi2.values
    return {'ln_rho': ln(rho), 'ln_hs': ln(hs), 'ln_pi2': ln(pi2),
            'ln_pi2_sq': ln(pi2) ** 2, 'ln_hs_sq': ln(hs) ** 2,
            'rho_sqrt_hs': rho * np.sqrt(hs), 'x_hs_pi2': ln(hs) * ln(pi2),
            'x_rho_pi2': ln(rho) * ln(pi2)}


def logo(d, subset, zcol):
    apes, per = [], {}
    for fam in d.family.unique():
        tr, te = d[d.family != fam], d[d.family == fam]
        Ftr, Fte = feats(tr), feats(te)
        Xtr = np.column_stack([np.ones(len(tr))] + [Ftr[k] for k in subset])
        Xte = np.column_stack([np.ones(len(te))] + [Fte[k] for k in subset])
        c, *_ = np.linalg.lstsq(Xtr, np.log(tr[zcol].values), rcond=None)
        ape = np.abs(np.exp(Xte @ c) / te[zcol].values - 1) * 100
        apes.append(ape)
        for idx, a in zip(te.index, ape):
            per[idx] = a
    return np.concatenate(apes), pd.Series(per)


print('thr | med Z_conv,I | LOGO quad d1/d2 | LOGO champ d1/d2 (mean, [med])')
for thr in THRS:
    zc = f'Z_{thr}'
    q, c = [], []
    for det in (1, 2):
        d = df[(df.Det == det) & np.isfinite(df[zc]) & (df[zc] > 0)].copy()
        aq, _ = logo(d, QUAD, zc)
        ac, _ = logo(d, CHAMP[det], zc)
        q.append(f'{aq.mean():5.2f}')
        c.append(f'{ac.mean():5.2f} [{np.median(ac):4.1f}]')
    print(f'{thr:4d} |    {df[zc].median():6.2f}    | {" / ".join(q)} | '
          f'{" / ".join(c)}')

el = np.abs((np.log(df.RI_30) - np.log(df.RI_15)) / (np.log(30) - np.log(15)))
for det in (1, 2):
    d = df[df.Det == det].copy()
    _, per = logo(d, CHAMP[det], 'Z_20')
    r = np.corrcoef(el[per.index], per.values)[0, 1]
    print(f'det={det}: corr(|dlnR/dlnthr| 15-30, champ LOGO APE at 20) = {r:+.2f}')
