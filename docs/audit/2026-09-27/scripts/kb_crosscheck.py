"""CFD free field vs UFC 3-340-02 Kingery-Bulmash curves (PHY-06).

Sources: owner-supplied DPlot exports of UFC Fig. 2-15 (hemispherical
surface burst — matches the simulations) and Fig. 2-7 (free air),
docs/references/02_015.GRF / 02_007.GRF, exact curve points, US units.
CFD side: data/free_field_data.csv (P [kPa], I [Pa.s] per W at integer Z).

Units: Z_SI = Z_US * 0.3048 / lb^(1/3), lb = 0.45359237 kg;
P: psi -> kPa (x6.894757); scaled impulse psi*ms/lb^(1/3) ->
Pa.s/kg^(1/3) (x6.894757 / 0.45359237^(1/3)).
"""
import re

import numpy as np
import pandas as pd

LB13 = 0.45359237 ** (1 / 3)
FT2M = 0.3048
Z_F = FT2M / LB13                 # ft/lb^(1/3) -> m/kg^(1/3)
P_F = 6.894757                    # psi -> kPa
I_F = 6.894757 / LB13             # psi*ms/lb^(1/3) -> Pa.s/kg^(1/3)


def parse_grf(path):
    curves, cur = {}, []
    for ln in open(path, errors='replace'):
        s = ln.strip()
        m = re.match(r'^([-\d.Ee+]+)\s+([-\d.Ee+]+)$', s)
        if m:
            cur.append((float(m.group(1)), float(m.group(2))))
            continue
        if re.match(r'^\d+$', s):
            continue
        if cur:
            a = np.array(cur)
            a = a[(a[:, 0] > 0) & (a[:, 1] > 0)]       # drop format-flag rows
            a = a[np.argsort(a[:, 0])]
            curves[s] = a
            cur = []
        if s.lower() == 'stop':
            break
    return curves


f215 = parse_grf('docs/references/02_015.GRF')
print('Fig 2-15 curves:', {k: len(v) for k, v in f215.items()})

Pso = f215['Pso, psi']
Is = f215['Is, psi-ms/lb^(1/3)']


def interp_loglog(curve, z_si):
    z_us = z_si / Z_F
    x, y = curve[:, 0], curve[:, 1]
    return np.exp(np.interp(np.log(z_us), np.log(x), np.log(y)))


ff = pd.read_csv('data/free_field_data.csv')
Ws = [50, 250, 500, 1000, 1500]
rows = []
for _, r in ff.iterrows():
    z = r.Z
    p_cfd = np.array([r[f'P_{w}'] for w in Ws])
    i_cfd_sc = np.array([r[f'I_{w}'] / w ** (1 / 3) for w in Ws])
    p_kb = interp_loglog(Pso, z) * P_F
    i_kb = interp_loglog(Is, z) * I_F
    rows.append({
        'Z': int(z),
        'P_KB_kPa': p_kb,
        'P_CFD_mean_kPa': p_cfd.mean(),
        'P_ratio': p_cfd.mean() / p_kb,
        'P_ratio_min': p_cfd.min() / p_kb,
        'P_ratio_max': p_cfd.max() / p_kb,
        'Isc_KB': i_kb,
        'Isc_CFD_mean': i_cfd_sc.mean(),
        'I_ratio': i_cfd_sc.mean() / i_kb,
    })
out = pd.DataFrame(rows)
pd.set_option('display.width', 160)
print(out.round(3).to_string(index=False))

sub = out[(out.Z >= 2) & (out.Z <= 16)]
print(f"\nZ = 2..16: P_CFD/P_KB median {sub.P_ratio.median():.3f} "
      f"range {sub.P_ratio.min():.3f}-{sub.P_ratio.max():.3f}")
print(f"           I_CFD/I_KB median {sub.I_ratio.median():.3f} "
      f"range {sub.I_ratio.min():.3f}-{sub.I_ratio.max():.3f}")

# threshold locations
zg = np.linspace(1, 25, 2000)
p_curve = interp_loglog(Pso, zg) * P_F
z10_kb = zg[np.argmin(np.abs(p_curve - 10.0))]
i_curve = interp_loglog(Is, zg) * I_F
z20_kb = zg[np.argmin(np.abs(i_curve - 20.0))]
print(f'\nKB (UFC 2-15): 10 kPa contour at Z = {z10_kb:.2f}; '
      f'I/W^(1/3) = 20 Pa.s/kg^(1/3) at Z = {z20_kb:.2f}')

out.round(4).to_csv('outputs/check_results/cfd_vs_kb_ufc215.csv', index=False)
print('saved: outputs/check_results/cfd_vs_kb_ufc215.csv')
