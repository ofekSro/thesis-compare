"""Free-field peaks from the FF gauges vs the reference VTK (raw_npz) at the same cell.

Read-only. Usage: python ff_gauges.py <repo_root> <out_dir>
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

repo, out = Path(sys.argv[1]), Path(sys.argv[2])
gdir = repo / 'data' / 'Gauges'
npz_dir = repo / 'data' / 'raw_npz'
ff_csv = pd.read_csv(repo / 'data' / 'free_field_data.csv').set_index('Z')
WEIGHTS = (50, 250, 500, 1000, 1500)

rows = []
for W in WEIGHTS:
    cfgs = sorted(npz_dir.glob(f'config_*_w{W}.npz'))
    ref = np.load(cfgs[0])
    # the reference field must be the same in every config of this W
    other = np.load(cfgs[-1])
    same = all(np.array_equal(ref[f'refP{g}'], other[f'refP{g}']) and
               np.array_equal(ref[f'refI{g}'], other[f'refI{g}']) for g in '123')
    for g in '123':
        d = gdir / f'ff_{W}kg' / g
        act = pd.read_csv(d / 'gauge_list_3d_actual.txt', sep=r'\s+', header=None)
        P = np.loadtxt(d / 'viper3d_th_overpressure.txt')
        I = np.loadtxt(d / 'viper3d_th_impulse.txt')
        t = P[:, 0]
        h = float(ref[f'spacing{g}'][0])
        org = ref[f'origin{g}']
        refP, refI = ref[f'refP{g}'], ref[f'refI{g}']
        for k in range(len(act)):
            name = str(act.iloc[k, 9])
            if not name.startswith('FF_Z'):
                continue
            Z = int(name.split('_')[1][1:])
            # cols: '3d', id, x, y, z (requested), x, y, z (snapped), -1, name
            r_tgt = float(act.iloc[k, 4])
            xa, za = float(act.iloc[k, 5]), float(act.iloc[k, 7])
            pcol, icol = P[:, k + 1], I[:, k + 1]
            ip, ii = int(np.argmax(pcol)), int(np.argmax(icol))
            ix = int(round((xa - org[0]) / h - 0.5))
            iz = int(round((za - org[2]) / h - 0.5))
            inside = 0 <= iz < refP.shape[0] and 0 <= ix < refP.shape[1]
            rows.append(dict(
                W=W, grid=int(g), h=h, Z=Z, r_target=r_tgt, z_actual=za,
                # snapped to the requested radius, and not in the last metre of
                # the box (the seam cell at the box edge is corrupted)
                snapped_ok=(abs(za - r_tgt) <= 0.5 * h + 1e-6 and
                            za <= org[2] + h * (refP.shape[0]) - 1.0),
                gP=pcol[ip], gI=icol[ii],
                peakP_at_end=ip >= len(t) - 2, peakI_at_end=ii >= len(t) - 2,
                t_end=t[-1],
                vP=float(refP[iz, ix]) if inside else np.nan,
                vI=float(refI[iz, ix]) if inside else np.nan,
                ref_same_all_cfgs=same))

df = pd.DataFrame(rows)
# gauge pressure unit: compare to VTK (kPa) to detect Pa
scale = np.nanmedian(df['gP'] / df['vP'])
if scale > 100:
    df['gP'] = df['gP'] / 1000.0
df['dP_%'] = 100 * (df['gP'] / df['vP'] - 1)
df['dI_%'] = 100 * (df['gI'] / df['vI'] - 1)
df.to_csv(out / 'ff_gauges_all_grids.csv', index=False)

# finest grid whose gauge was not clamped / mis-snapped
ok = df[df['snapped_ok']].sort_values('grid')
best = ok.groupby(['W', 'Z'], as_index=False).first()
best['csv_P'] = [ff_csv.loc[z, f'P_{w}'] if z in ff_csv.index else np.nan
                 for w, z in zip(best['W'], best['Z'])]
best['csv_I'] = [ff_csv.loc[z, f'I_{w}'] if z in ff_csv.index else np.nan
                 for w, z in zip(best['W'], best['Z'])]
best['gauge_vs_csv_P_%'] = 100 * (best['gP'] / best['csv_P'] - 1)
best['gauge_vs_csv_I_%'] = 100 * (best['gI'] / best['csv_I'] - 1)
best.to_csv(out / 'ff_gauges_best.csv', index=False)

wide = best.pivot(index='Z', columns='W', values=['gP', 'gI'])
tab = pd.DataFrame({'Z': wide.index})
for w in WEIGHTS:
    tab[f'P_{w}'] = wide[('gP', w)].values
for w in WEIGHTS:
    tab[f'I_{w}'] = wide[('gI', w)].values
tab.to_csv(out / 'free_field_data_from_gauges.csv', index=False)

pd.set_option('display.width', 200)
print('pressure unit scale gauge/VTK (raw):', round(scale, 3))
print('reference identical across configs per W:',
      df.groupby('W')['ref_same_all_cfgs'].first().to_dict())
print('peak at last sample (run cut):', int(best['peakP_at_end'].sum()),
      'P,', int(best['peakI_at_end'].sum()), 'I of', len(best))
print('\nchosen grid per (W, Z):')
print(best.pivot(index='Z', columns='W', values='grid').to_string())
for col in ['dP_%', 'dI_%', 'gauge_vs_csv_P_%', 'gauge_vs_csv_I_%']:
    print(f'\n{col}  (rows = Z, cols = W)')
    print(best.pivot(index='Z', columns='W', values=col).round(2).to_string())
