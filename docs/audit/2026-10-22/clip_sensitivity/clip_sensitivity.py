"""Z_urban LOGO: with vs without the Z_conv clip, identical rows. Read-only.

Sensitivity check behind D49 (docs/DECISIONS.md). Reproduces the 36 LOGO
folds of tools/logo_cv with the library fitters, takes the Lambda-formula
prediction before (no_clip) and after (with_clip) clip_z_urban_pred on the
SAME graded rows, gates the clipped one against the tracked LOGO detail
CSVs, and writes the tables next to this script. Changes nothing.

Usage (from the repo root):
    python docs/audit/2026-10-22/clip_sensitivity/clip_sensitivity.py
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
from blastlib.regression.convergence_models import predict_pi, predict_impulse  # noqa: E402
from blastlib.regression.z_urban import (                            # noqa: E402
    BEYOND_COL, Z_URBAN_FORM, clip_z_urban_pred, fit_z_urban_all_groups,
    predict_z_urban, prepare_maxR_data)

conv = pd.read_csv(ROOT / 'outputs/tables/convergence_table_reqdir91_soft3.csv')
maxr = pd.read_csv(ROOT / 'outputs/tables/max_radius_per_Z_reqdir91_soft3.csv')
prep = prepare_maxR_data(maxr, conv)
fit_p, fit_i = L._make_fitters(L.MODEL_P_DEFAULT, L.MODEL_I_DEFAULT)
assert all(v is not None for v in Z_URBAN_FORM.values())


def zconv_pred(sub, det_val, target_name, cP, cI):
    """Predicted Z_conv for *sub* rows [m/kg^(1/3)], the clip level."""
    W = sub['weight'].values.astype(float)
    args = (W, sub['rho'].values.astype(float), sub['height'].values.astype(float),
            np.full(len(sub), det_val), sub['swidth'].values.astype(float),
            sub['bsize'].values.astype(float))
    R = predict_pi(*args, cP) if target_name == 'Pressure' else predict_impulse(*args, cI)
    return R / W ** (1 / 3)


rows, bound = [], []
for fam, fam_mask in L._families(conv):
    test_cfg = set(conv['ConfigName'].values[fam_mask])
    in_test = prep['Config'].isin(test_cfg)
    train_m, test_m = prep[~in_test], prep[in_test]
    cP, cI = fit_p(conv[~fam_mask]), fit_i(conv[~fam_mask])
    z_coeffs = fit_z_urban_all_groups(train_m, cP)
    for det_val in (1, 2):
        sub_det = test_m[test_m['det'] == det_val]
        for load, tcol, tname, rcol, mcol in L.ZURBAN_LOADS:
            popt = z_coeffs.get((det_val, tname))
            if popt is None or len(sub_det) == 0:
                continue
            cc = cP if tname == 'Pressure' else cI
            for domain in L.DOMAIN_CHOICES:
                sub = L._zurban_graded_rows(sub_det, det_val, tcol, tname, rcol,
                                            mcol, cc, domain)
                if len(sub) == 0:
                    continue
                W13 = sub['weight'].values ** (1 / 3)
                raw = predict_z_urban(sub['Z_free'].values, sub['rho'].values,
                                      sub['height'].values, sub['swidth'].values,
                                      W13, tname, popt)
                clip = clip_z_urban_pred(raw, sub, det_val, tname, cP, cI)
                zc = zconv_pred(sub, det_val, tname, cP, cI)
                rows.append(pd.DataFrame({
                    'domain': domain, 'Family': fam, 'Config': sub['Config'].values,
                    'Det': det_val, 'Target': load,
                    'Z_free': sub['Z_free'].values.astype(float), 'W13': W13,
                    'Z_act': sub[tcol].values.astype(float), 'Z_raw': raw,
                    'Z_clip': clip, 'Zconv_pred': zc,
                    'Zconv_meas': sub[rcol].values.astype(float) / W13,
                    'beyond_meas': sub[BEYOND_COL[tname]].values.astype(bool)}))
            # Boundary check: raw prediction AT Z_free = predicted Z_conv, once
            # per held-out config. Beyond R_conv the chain is the identity
            # (Z_urban = Z_free), so raw/Z_conv there is the jump at the boundary.
            cfgs = sub_det.drop_duplicates('Config')
            zc = zconv_pred(cfgs, det_val, tname, cP, cI)
            raw_b = predict_z_urban(zc, cfgs['rho'].values, cfgs['height'].values,
                                    cfgs['swidth'].values,
                                    cfgs['weight'].values ** (1 / 3), tname, popt)
            bound.append(pd.DataFrame({'Config': cfgs['Config'].values, 'Det': det_val,
                                       'Target': load, 'Zconv_pred': zc,
                                       'jump': raw_b / zc}))
d = pd.concat(rows, ignore_index=True)
b = pd.concat(bound, ignore_index=True)

# Gate: clipped predictions equal the tracked LOGO detail files, row for row.
key = ['Config', 'Target', 'Z_free']
for domain, stem in (('conditional', 'zurban'), ('deployable', 'zurban_deploy')):
    ref = pd.read_csv(ROOT / f'outputs/check_results/logo_cv_reqdir91_soft3_relwls_quad_{stem}.csv')
    mine = d[d.domain == domain]
    j = mine.merge(ref[key + ['Predicted', 'Actual']], on=key, how='outer', indicator=True)
    assert (j['_merge'] == 'both').all(), f'{domain}: row sets differ'
    assert np.allclose(j['Z_clip'], j['Predicted'], rtol=1e-12, atol=0), domain
    assert np.allclose(j['Z_act'], j['Actual'], rtol=1e-12, atol=0), domain
print('gate: clipped predictions and rows equal the tracked LOGO detail files')

# Group: shared between domains / deployable only / conditional only.
k = d[key].astype(str).agg('|'.join, axis=1)
d['key'] = k
in_c = set(d.loc[d.domain == 'conditional', 'key'])
in_d = set(d.loc[d.domain == 'deployable', 'key'])
d['group'] = np.where(d.key.isin(in_c) & d.key.isin(in_d), 'shared',
                      np.where(d.key.isin(in_d), 'deploy_only', 'cond_only'))
d['active'] = d.Z_raw > d.Zconv_pred          # clip changes the prediction
assert np.allclose(d.loc[~d.active, 'Z_raw'], d.loc[~d.active, 'Z_clip'])

# R_urban [m]
for c in ('act', 'raw', 'clip'):
    d[f'R_{c}'] = d[f'Z_{c}'] * d['W13']


def metrics(s, which):
    a, p = s['R_act'].values, s[f'R_{which}'].values
    rel = (p - a) / a
    return {'MAPE': 100 * np.mean(np.abs(rel)),
            'R2': 1 - np.sum((a - p) ** 2) / np.sum((a - a.mean()) ** 2) if len(a) > 2 else np.nan,
            'RMSE_m': np.sqrt(np.mean((p - a) ** 2)), 'MAE_m': np.mean(np.abs(p - a)),
            'bias_pct': 100 * np.mean(rel)}


def table(df, by):
    out = []
    for keys, s in df.groupby(by):
        keys = keys if isinstance(keys, tuple) else (keys,)
        base = dict(zip(by, keys), rows=len(s), active=int(s.active.sum()))
        for which in ('clip', 'raw'):
            out.append({**base, 'model': 'with_clip' if which == 'clip' else 'no_clip',
                        **metrics(s, which)})
    return pd.DataFrame(out)


pd.set_option('display.width', 220)
fmt = '{:8.3f}'.format
summ = pd.concat([table(d.assign(Det='all'), ['Target', 'domain', 'Det']),
                  table(d, ['Target', 'domain', 'Det'])], ignore_index=True)
grp = pd.concat([table(d.assign(Det='all'), ['Target', 'domain', 'group', 'Det']),
                 table(d, ['Target', 'domain', 'group', 'Det'])], ignore_index=True)
act = table(d[d.active].assign(Det='all'), ['Target', 'domain', 'group', 'Det'])

# Physical checks on the unclipped predictions.
phys = []
for (t, dom), s in d.groupby(['Target', 'domain']):
    ratio = s.Z_raw / s.Zconv_pred
    phys.append({'Target': t, 'domain': dom, 'rows': len(s),
                 'raw>Zconv_pred': int((ratio > 1).sum()),
                 'raw>Zconv_meas': int((s.Z_raw > s.Zconv_meas).sum()),
                 'meas_MaxR>Rconv_meas(beyond)': int(s.beyond_meas.sum()),
                 'meas>Zconv_pred': int((s.Z_act > s.Zconv_pred).sum()),
                 'ratio_raw/Zc_p50_active': ratio[ratio > 1].median(),
                 'ratio_raw/Zc_p90_active': ratio[ratio > 1].quantile(.9),
                 'ratio_raw/Zc_max': ratio.max(),
                 'ratio_meas/Zc_p50_where_meas>Zc':
                     (s.Z_act / s.Zconv_pred)[s.Z_act > s.Zconv_pred].median(),
                 'ratio_meas/Zc_max': (s.Z_act / s.Zconv_pred).max()})
phys = pd.DataFrame(phys)

# Monotonicity of the predicted map R_urban(R_free) inside one config: a
# farther free-field level must not map to a nearer urban distance.
mono = []
for (t, dom), s in d.groupby(['Target', 'domain']):
    n_pairs = 0
    viol = {'act': 0, 'raw': 0, 'clip': 0}
    for _, g in s.sort_values('Z_free').groupby('Config'):
        if len(g) < 2:
            continue
        n_pairs += len(g) - 1
        for c in viol:
            viol[c] += int((np.diff(g[f'R_{c}'].values) < -1e-9).sum())
    mono.append({'Target': t, 'domain': dom, 'adjacent_pairs': n_pairs,
                 'decreasing_measured': viol['act'], 'decreasing_no_clip': viol['raw'],
                 'decreasing_with_clip': viol['clip']})
mono = pd.DataFrame(mono)

jump = b.drop_duplicates(['Config', 'Target']).groupby(['Target', 'Det'])['jump'].describe(
    percentiles=[.1, .5, .9])[['count', 'min', '10%', '50%', '90%', 'max']]

with pd.option_context('display.float_format', fmt):
    print('\n== All rows, with vs without clip');      print(summ.to_string(index=False))
    print('\n== By group (shared / deploy_only / cond_only)'); print(grp.to_string(index=False))
    print('\n== Only rows where the clip is active');  print(act.to_string(index=False))
    print('\n== Physical checks');                     print(phys.to_string(index=False))
    print('\n== Monotonicity within config');          print(mono.to_string(index=False))
    print('\n== Jump at the R_conv boundary: raw Z_urban(Z_free=Z_conv)/Z_conv');  print(jump)
for name, df in (('rows', d), ('summary', summ), ('groups', grp), ('active', act),
                 ('physical', phys), ('monotonic', mono), ('boundary', b)):
    df.to_csv(OUT / f'{name}.csv', index=False)
