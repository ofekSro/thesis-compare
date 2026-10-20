"""Ring average of the reference VTK at r = Z W^(1/3), against the axis gauges.

Grid per (W, Z) = the one chosen for the gauge (ff_gauges_best.csv).
Ring: cells with |r_cell - r| < h (one cell each side). Read-only.
Usage: python ff_ring.py <repo_root> <scratch_dir>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

repo, S = Path(sys.argv[1]), Path(sys.argv[2])
best = pd.read_csv(S / 'ff_gauges_best.csv')
rows = []
for W in sorted(best['W'].unique()):
    ref = np.load(sorted((repo / 'data' / 'raw_npz').glob(f'config_*_w{W}.npz'))[0])
    grids = {}
    for g in '123':
        o, h, n = ref[f'origin{g}'], float(ref[f'spacing{g}'][0]), ref[f'refP{g}'].shape
        x = o[0] + h * (np.arange(n[1]) + 0.5)
        z = o[2] + h * (np.arange(n[0]) + 0.5)
        X, Zc = np.meshgrid(x, z)
        grids[int(g)] = (h, np.hypot(X, Zc), np.degrees(np.arctan2(Zc, X)),
                         ref[f'refP{g}'], ref[f'refI{g}'])
    for _, b in best[best['W'] == W].iterrows():
        h, R, TH, P, I = grids[int(b['grid'])]
        r = b['Z'] * W ** (1 / 3)
        m = (np.abs(R - r) < h) & (P > 0)
        # first-order radial correction of each cell to r, from the local slope
        # of the ring itself, so a band of width 2h does not bias the mean
        p, i, rr, th = P[m], I[m], R[m], TH[m]
        sP = np.polyfit(np.log(rr), np.log(p), 1)[0]
        sI = np.polyfit(np.log(rr), np.log(i), 1)[0]
        p = p * (r / rr) ** sP
        i = i * (r / rr) ** sI
        ax = (th < 5) | (th > 85)
        dg = np.abs(th - 45) < 5
        rows.append(dict(
            W=W, Z=int(b['Z']), grid=int(b['grid']), n=int(m.sum()),
            gauge_P=b['gP'], ring_mean_P=p.mean(), ring_med_P=np.median(p),
            axis_P=p[ax].mean(), diag_P=p[dg].mean(),
            gauge_I=b['gI'], ring_mean_I=i.mean(), ring_med_I=np.median(i),
            axis_I=i[ax].mean(), diag_I=i[dg].mean()))

df = pd.DataFrame(rows)
for q in 'PI':
    df[f'mean/gauge_{q}_%'] = 100 * (df[f'ring_mean_{q}'] / df[f'gauge_{q}'] - 1)
    df[f'diag/axis_{q}_%'] = 100 * (df[f'diag_{q}'] / df[f'axis_{q}'] - 1)
df.to_csv(S / 'ff_ring_vs_gauge.csv', index=False)

tab = pd.DataFrame({'Z': sorted(df['Z'].unique())})
for q, col in (('P', 'ring_mean_P'), ('I', 'ring_mean_I')):
    w = df.pivot(index='Z', columns='W', values=col)
    for W in w.columns:
        tab[f'{q}_{W}'] = w[W].values
tab.to_csv(S / 'free_field_data_ring_mean.csv', index=False)

pd.set_option('display.width', 200)
print('cells per ring: min', df['n'].min(), ' median', int(df['n'].median()))
for col in ['mean/gauge_P_%', 'mean/gauge_I_%', 'diag/axis_P_%', 'diag/axis_I_%']:
    print(f'\n{col}')
    print(df.pivot(index='Z', columns='W', values=col).round(1).to_string())
