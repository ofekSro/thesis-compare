"""Where would an ABSOLUTE human-impulse floor (UFC Fig. 1-2 vertical
asymptote) bind, and which configs would it move?

Floor: i_min = a * Wh^(1/3), a ~ 3.5 psi-ms/lb^(1/3) (threshold curve's
impulsive asymptote), evaluated for Wh = 20 / 70 / 100 kg. Compare the
free-field impulse per CHARGE weight with the floor to find Z_floor(W),
and count configs whose measured Z_conv,I lies beyond it (their radii
would shrink if the floor pinned cells).
"""
import numpy as np
import pandas as pd

PSI_MS = 6.894757          # psi*ms -> Pa*s
A_US = 3.5                 # psi-ms/lb^(1/3), Fig. 1-2 threshold asymptote

ff = pd.read_csv('data/free_field_data.csv')
conv = pd.read_csv('outputs/tables/convergence_table_req_soft3.csv')
conv['Zc'] = conv.RadiusI / conv.ChargeWeight.astype(float) ** (1 / 3)

print('human-impulse floor i_min = 3.5 * Wh^(1/3) [psi-ms] -> Pa.s:')
floors = {}
for wh_kg in (20, 70, 100):
    wh_lb = wh_kg / 0.45359237
    imin = A_US * wh_lb ** (1 / 3) * PSI_MS
    floors[wh_kg] = imin
    print(f'  Wh = {wh_kg:3d} kg: i_min = {imin:.0f} Pa.s')

print('\nZ_floor(W): scaled distance where I_ff drops to i_min '
      '(- = beyond Z=20):')
hdr = '  W     ' + '  '.join(f'Wh={k}kg' for k in floors)
print(hdr)
for w in (50, 250, 500, 1000, 1500):
    zi = []
    for wh_kg, imin in floors.items():
        col = ff[f'I_{w}'].values
        z = ff.Z.values
        if col.min() > imin:
            zi.append('   -  ')
        else:
            zi.append(f'{np.interp(-imin, -col, z):6.1f}')
    print(f'  {w:5d} ' + '  '.join(zi))

print('\nconfigs whose measured Z_conv,I lies beyond Z_floor '
      '(radius would be cut by the floor), Wh = 70 kg:')
imin70 = floors[70]
n_aff = 0
for w in (50, 250, 500, 1000, 1500):
    col = ff[f'I_{w}'].values
    if col.min() > imin70:
        zf = np.inf
    else:
        zf = np.interp(-imin70, -col, ff.Z.values)
    sub = conv[conv.ChargeWeight == w]
    aff = sub[sub.Zc > zf]
    n_aff += len(aff)
    names = ', '.join(c.split('_det')[0] for c in aff.ConfigName) or '-'
    print(f'  W={w:5d}: Z_floor = {zf if np.isfinite(zf) else -1:6.1f}  '
          f'affected {len(aff)}/{len(sub)}: {names}')
print(f'total affected: {n_aff}/96')
