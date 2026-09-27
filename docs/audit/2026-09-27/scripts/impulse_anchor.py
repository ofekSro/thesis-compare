"""Groundwork for anchoring thr_I (D8, item 2c) from registered data only.

1. Positive-phase durations at the relevant ranges, from the registered
   UFC Fig. 2-15 'to' curve (surface burst) - which response regime do the
   R_conv,I ranges live in?
2. The band as a share of the LOCAL free-field impulse at each config's
   measured R_conv,I (new production tables) - how tight is 20 Pa.s/kg^(1/3)
   where it actually bites?
3. Grep the UFC text for its own impulsive/quasi-static regime definition
   so the regime statement can be cited, not remembered.
"""
import re

import numpy as np
import pandas as pd

LB13 = 0.45359237 ** (1 / 3)
Z_F = 0.3048 / LB13           # ft/lb^(1/3) -> m/kg^(1/3)
T_F = 1.0 / LB13              # ms/lb^(1/3) -> ms/kg^(1/3)


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
            a = a[(a[:, 0] > 0) & (a[:, 1] > 0)]
            curves[s] = a[np.argsort(a[:, 0])]
            cur = []
        if s.lower() == 'stop':
            break
    return curves


f = parse_grf('docs/references/02_015.GRF')
to = f['to, ms/lb^(1/3)']


def to_scaled(z_si):
    x, y = to[:, 0], to[:, 1]
    return np.exp(np.interp(np.log(z_si / Z_F), np.log(x), np.log(y))) * T_F


print('=== 1. positive-phase duration to [ms] (UFC Fig. 2-15) ===')
print(f'{"Z":>5s} {"to/W^1/3":>9s} | ' +
      ' '.join(f'W={w:>4d}' for w in (50, 500, 1500)))
for z in (5.0, 7.6, 10.0, 13.7, 15.7):
    ts = to_scaled(z)
    durs = ' '.join(f'{ts * w ** (1/3):6.0f}' for w in (50, 500, 1500))
    print(f'{z:5.1f} {ts:9.2f} | {durs}')

print('\n=== 2. band share of local free-field impulse at R_conv,I ===')
conv = pd.read_csv('outputs/tables/convergence_table_req_soft3.csv')
ff = pd.read_csv('data/free_field_data.csv')
shares = []
for _, r in conv.iterrows():
    w = int(r.ChargeWeight)
    z = r.RadiusI / w ** (1 / 3)
    isc = np.interp(z, ff.Z.values, ff[f'I_{w}'].values) / w ** (1 / 3)
    shares.append(20.0 / isc)
s = pd.Series(shares)
print(f'band / I_ff at the measured radius: median {100*s.median():.1f}%  '
      f'p10 {100*s.quantile(.1):.1f}%  p90 {100*s.quantile(.9):.1f}%  '
      f'max {100*s.max():.1f}%')

print('\n=== 3. UFC regime definitions (grep) ===')
txt = open('docs/references/ufc_3_340_02.txt', errors='replace').read()
lines = txt.splitlines()
page = 0
hits = 0
for i, ln in enumerate(lines):
    m = re.match(r'=== page (\d+) ===', ln)
    if m:
        page = int(m.group(1))
    low = ln.lower()
    if (('impulsive' in low or 'quasi-static' in low or 'quasi-s' in low)
            and ('t/t' in low.replace(' ', '') or 'ratio' in low
                 or 'regime' in low or 'realm' in low or 'loading' in low)):
        print(f'p.{page} line {i}: {ln.strip()[:110]}')
        hits += 1
        if hits >= 12:
            break
