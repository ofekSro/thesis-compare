"""D49 pre-measurement inventory: measured impulse rows beyond the predicted R_conv,I.

x = R_free / R_conv,I_hat, with R_conv,I_hat from the convergence fit of the
LOGO fold that holds the row's family out (as tools/logo_cv). Rows pass every
Z_urban domain condition except the R_conv one: Z_free >= 2, R_free >
exclude_r, R_free >= (b+s) (D46), finite MaxR_I. No model is evaluated and no
candidate is compared; this only counts what the data can validate.

Usage (from the repo root):
    python docs/audit/2026-10-22/d49/x_inventory.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools' / 'logo_cv'))
import logo_cv as L                                                   # noqa: E402
from blastlib import constants                                        # noqa: E402
from blastlib.regression.convergence_models import predict_impulse    # noqa: E402
from blastlib.regression.z_urban import Z_URBAN_ZF_MIN, prepare_maxR_data  # noqa: E402

DOMAIN_EDGE_M = 500.0      # outer grid (level 3) spans 0..500 m in X and Z
I_FLOOR = 23.6             # relevance floor of the R_conv,I criterion, Pa.s/kg^(1/3) (D35)
BANDS = [1.0, 1.25, 1.5, 2.0, 3.0, 4.0, np.inf]

conv = pd.read_csv(ROOT / 'outputs/tables/convergence_table_reqdir91_soft3.csv')
maxr = pd.read_csv(ROOT / 'outputs/tables/max_radius_per_Z_reqdir91_soft3.csv')
prep = prepare_maxR_data(maxr, conv)
_, fit_i = L._make_fitters(L.MODEL_P_DEFAULT, L.MODEL_I_DEFAULT)

parts, per_cfg = [], []
for fam, mask in L._families(conv):
    cI = fit_i(conv[~mask])
    sub = prep[prep['Config'].isin(set(conv['ConfigName'].values[mask]))].copy()
    W = sub['weight'].values.astype(float)
    Rc = predict_impulse(W, sub['rho'].values, sub['height'].values,
                         sub['det'].values.astype(int), sub['swidth'].values,
                         sub['bsize'].values, cI)
    sub['Family'] = fam
    sub['Rconv_I_hat'] = Rc
    sub['x'] = sub['R_free'].values / Rc
    parts.append(sub)
d = pd.concat(parts, ignore_index=True)

dom = ((d['Z_free'] >= Z_URBAN_ZF_MIN['Impulse'])
       & (d['R_free'] > d['exclude_r'])
       & (d['R_free'] >= constants.Z_URBAN_MIN_PERIODS * (d['bsize'] + d['swidth']))
       & np.isfinite(d['MaxR_I']))
d = d[dom].copy()
d['lam_meas'] = d['MaxR_I'] / d['R_free']
d['raw_nan'] = ~np.isfinite(d['MaxR_I_raw'])
d['raw_at_edge'] = d['MaxR_I_raw'] >= 0.95 * DOMAIN_EDGE_M
d['below_floor'] = d['I_ff'] / d['weight'] ** (1 / 3) < I_FLOOR
d['band'] = pd.cut(d['x'], [0.0] + BANDS, right=False)

rows = []
for band, s in d.groupby('band', observed=False):
    fam_det = s.groupby('det')['Family'].nunique()
    rows.append({
        'x_band': str(band), 'rows': len(s), 'configs': s['Config'].nunique(),
        'families_det1': int(fam_det.get(1, 0)), 'families_det2': int(fam_det.get(2, 0)),
        'Z_free_range': f"{s['Z_free'].min():.0f}-{s['Z_free'].max():.0f}" if len(s) else '',
        'R_free_max_m': s['R_free'].max(), 'MaxR_I_raw_max_m': s['MaxR_I_raw'].max(),
        'raw_nan': int(s['raw_nan'].sum()), 'raw_at_domain_edge': int(s['raw_at_edge'].sum()),
        'beyond_I_meas': int(s['beyond_I'].sum()),
        'below_I_floor': int(s['below_floor'].sum()),
        'lam_meas_p10': s['lam_meas'].quantile(.1), 'lam_meas_p50': s['lam_meas'].median(),
        'lam_meas_p90': s['lam_meas'].quantile(.9),
    })
inv = pd.DataFrame(rows)

# Furthest x each config's table reaches (Z = 20 is the last tabulated level).
reach = d.groupby(['Config', 'det'])['x'].max().reset_index()
reach_tab = pd.DataFrame([{'x_at_least': t,
                           'configs_det1': int(((reach.det == 1) & (reach.x >= t)).sum()),
                           'configs_det2': int(((reach.det == 2) & (reach.x >= t)).sum())}
                          for t in (1.0, 1.25, 1.5, 2.0, 3.0, 4.0)])

pd.set_option('display.width', 250)
with pd.option_context('display.float_format', '{:7.3f}'.format):
    print('== Impulse rows by x = R_free / R_conv,I_hat (out-of-fold), domain conditions except R_conv')
    print(inv.to_string(index=False))
    print('\n== Configs whose tabulated rows reach x >= t')
    print(reach_tab.to_string(index=False))
    print(f"\nTotal rows {len(d)}; R_free max {d['R_free'].max():.1f} m; "
          f"MaxR_I_raw max {d['MaxR_I_raw'].max():.1f} m; domain edge {DOMAIN_EDGE_M:.0f} m")
inv.to_csv(OUT / 'x_inventory.csv', index=False)
reach_tab.to_csv(OUT / 'x_reach.csv', index=False)
