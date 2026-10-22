"""D49: impulse chain closure — CLIP vs 2a, 2b-min, 2b-4 on identical LOGO rows.

Read-only. Usage (from the repo root):
    python docs/audit/2026-10-22/d49/d49_compare.py

Relevance split: a row is "below the floor" when the free-field scaled
impulse of its level, I_ff(Z_free, W)/W^(1/3) from data/free_field_data.csv,
is under 23.6 Pa.s/kg^(1/3) (D35). That value is known before the answer;
on this table it is exactly Z_free >= 12 for every W (asserted below). It
is the level MaxR carries, not the urban impulse at R_free.

x = R_free / R_conv,I_hat (the fold's convergence fit, as tools/logo_cv).
Lambda = canyon_trap Lambda_I of the fold (range-flat, > 1 in every config).
R_urban predictions [m]:
  C1   x < 1: min(Lambda R_free, R_hat)       x >= 1: R_free
  2a   x <= 1: Lambda R_free                  x > 1: max(R_free, Lambda R_hat)
  2b   x <= 1: Lambda R_free;  1 < x < k: R_free (Lambda + (1-Lambda)(x-1)/(k-1));  x >= k: R_free
       k = 1/(2 - Lambda) per config (2b-min) or k = 4 (2b-4). k is never fitted.
For x < 1 the three 2-variants are one prediction ("no clip").
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent / 'd49_compare'
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools' / 'logo_cv'))
import logo_cv as L                                                    # noqa: E402
from blastlib import constants                                         # noqa: E402
from blastlib.regression.convergence_models import predict_impulse     # noqa: E402
from blastlib.regression.z_urban import (                             # noqa: E402
    Z_URBAN_ZF_MIN, fit_z_urban_all_groups, predict_z_urban, prepare_maxR_data,
    z_urban_valid_mask)

I_FLOOR = 23.6
N_BOOT, SEED = 10000, 42
DATA_X_MAX = 2.0

conv = pd.read_csv(ROOT / 'outputs/tables/convergence_table_reqdir91_soft3.csv')
maxr = pd.read_csv(ROOT / 'outputs/tables/max_radius_per_Z_reqdir91_soft3.csv')
prep = prepare_maxR_data(maxr, conv)
fit_p, fit_i = L._make_fitters(L.MODEL_P_DEFAULT, L.MODEL_I_DEFAULT)

parts = []
for fam, mask in L._families(conv):
    cP, cI = fit_p(conv[~mask]), fit_i(conv[~mask])
    in_test = prep['Config'].isin(set(conv['ConfigName'].values[mask]))
    z = fit_z_urban_all_groups(prep[~in_test], cP)
    for det in (1, 2):
        sub = prep[in_test & (prep['det'] == det)].dropna(subset=['Z_urban_I']).copy()
        popt = z.get((det, 'Impulse'))
        if popt is None or len(sub) == 0:
            continue
        W = sub['weight'].values.astype(float)
        W13 = W ** (1 / 3)
        Rhat = predict_impulse(W, sub['rho'].values, sub['height'].values,
                               np.full(len(sub), det), sub['swidth'].values,
                               sub['bsize'].values, cI)
        lam = predict_z_urban(sub['Z_free'].values, sub['rho'].values,
                              sub['height'].values, sub['swidth'].values, W13,
                              'Impulse', popt) / sub['Z_free'].values
        sub['Family'], sub['Rhat'], sub['lam'] = fam, Rhat, lam
        sub['x'] = sub['R_free'].values / Rhat
        # Conditional membership (measured R_conv, MaxR): the evaluator's rows.
        sub['in_cond'] = z_urban_valid_mask(sub.dropna(subset=['RadiusI']), 'Z_urban_I',
                                            'MaxR_I', 'RadiusI', 'Impulse').reindex(
                                                sub.index, fill_value=False).values
        parts.append(sub)
d = pd.concat(parts, ignore_index=True)

base = ((d['Z_free'] >= Z_URBAN_ZF_MIN['Impulse']) & (d['R_free'] > d['exclude_r'])
        & (d['R_free'] >= constants.Z_URBAN_MIN_PERIODS * (d['bsize'] + d['swidth']))
        & np.isfinite(d['Rhat']))
d = d[base | d['in_cond']].copy()
d['in_dep'] = base.loc[d.index] & (d['x'] < 1)
d['R_act'] = d['MaxR_I'].astype(float)          # measured R_urban [m]
d['below_floor'] = d['I_ff'] / d['weight'] ** (1 / 3) < I_FLOOR
# The split is a-priori: I_ff is the free-field table value at (Z, W).
ff = pd.read_csv(ROOT / 'data/free_field_data.csv').set_index('Z')
assert np.allclose(d['I_ff'], [ff.at[z, f'I_{int(w)}'] for z, w in zip(d['Z_free'], d['weight'])])
assert (d['below_floor'] == (d['Z_free'] >= 12)).all(), 'floor split is not Z_free >= 12'
assert d.groupby('Config')['lam'].std().fillna(0).max() < 1e-9, 'Lambda_I not range-flat'
assert (d['lam'] > 1).all()


def lam_eff(x, lam, cand):
    """Lambda_eff = R_urban / R_free for candidate *cand* (vectorised)."""
    x, lam = np.asarray(x, float), np.asarray(lam, float)
    if cand == 'C1':
        return np.where(x < 1, np.minimum(lam, 1 / x), 1.0)
    if cand == 'no_clip_ref':                       # reference only: never returns to 1
        return lam
    if cand == '2a':
        return np.where(x <= 1, lam, np.maximum(1.0, lam / x))
    k = 1 / (2 - lam) if cand == '2b_min' else np.full_like(lam, 4.0)
    taper = lam + (1 - lam) * (x - 1) / (k - 1)
    return np.where(x <= 1, lam, np.where(x < k, taper, 1.0))


CANDS = ['C1', '2a', '2b_min', '2b_4']
for c in CANDS + ['no_clip_ref']:
    d[f'R_{c}'] = lam_eff(d['x'], d['lam'], c) * d['R_free']

# Gate: on the deployable rows C1 is the production prediction, row for row.
ref = pd.read_csv(ROOT / 'outputs/check_results/logo_cv_reqdir91_soft3_relwls_quad_zurban_deploy.csv')
ref = ref[ref.Target == 'I']
dep = d[d.in_dep]
j = dep.merge(ref, left_on=['Config', 'Z_free'], right_on=['Config', 'Z_free'],
              how='outer', indicator=True)
assert (j['_merge'] == 'both').all() and len(j) == len(ref), 'deployable row set differs'
w13 = j['weight'] ** (1 / 3)
assert np.allclose(j['R_C1'], j['Predicted'] * w13, rtol=1e-12), 'C1 != production'
print(f'gate: C1 on {len(dep)} deployable rows equals production LOGO row for row')

BANDS = {'(i) dep x<1': d.in_dep,
         '(ii) 1<=x<1.25 primary': base.loc[d.index] & (d.x >= 1) & (d.x < 1.25),
         '(ii) 1.25<=x<1.5 secondary': base.loc[d.index] & (d.x >= 1.25) & (d.x < 1.5),
         '(ii) 1.5<=x<2 diagnostic': base.loc[d.index] & (d.x >= 1.5) & (d.x < 2),
         '(ii) 1<=x<2 cumulative': base.loc[d.index] & (d.x >= 1) & (d.x < 2),
         '(iii) conditional': d.in_cond}


def metrics(s, col):
    a, p = s['R_act'].values, s[col].values
    rel = 100 * (p - a) / a
    ae = np.abs(rel)
    return {'MAPE': ae.mean(), 'R2': 1 - ((a - p) ** 2).sum() / ((a - a.mean()) ** 2).sum()
            if len(a) > 2 else np.nan,
            'RMSE_m': np.sqrt(((p - a) ** 2).mean()), 'MAE_m': np.abs(p - a).mean(),
            'bias_pct': rel.mean(), 'p90_abs': np.percentile(ae, 90), 'max_abs': ae.max(),
            'under20_pct': 100 * (rel < -20).mean(), 'over20_pct': 100 * (rel > 20).mean()}


def paired(s, col, ref='R_C1'):
    """Paired family bootstrap of d(MAPE) and d(bias) [pp], col minus ref."""
    t = pd.DataFrame({'Family': s.Family, 'det': s.det,
                      'da': (np.abs(s[col] - s.R_act) - np.abs(s[ref] - s.R_act)) / s.R_act * 100,
                      'ds': (s[col] - s[ref]) / s.R_act * 100, 'n': 1.0})
    f = t.groupby('Family').agg(det=('det', 'first'), da=('da', 'sum'), ds=('ds', 'sum'),
                                n=('n', 'sum'))
    rng = np.random.default_rng(SEED)
    tot = {c: np.zeros(N_BOOT) for c in ('da', 'ds', 'n')}
    for _, g in f.groupby('det'):
        k = rng.integers(0, len(g), size=(N_BOOT, len(g)))
        for c in tot:
            tot[c] += g[c].values[k].sum(axis=1)
    out = {}
    for c, name in (('da', 'dMAPE'), ('ds', 'dbias')):
        bs = tot[c] / tot['n']
        out[name] = f[c].sum() / f['n'].sum()
        out[f'{name}_lo'], out[f'{name}_hi'] = np.percentile(bs, [2.5, 97.5])
    out['fam_better'] = int(((f['da'] / f['n']) < 0).sum())
    out['families'] = len(f)
    return out


res = []
for band, m in BANDS.items():
    for scope, sm in (('all', m), ('det1', m & (d.det == 1)), ('det2', m & (d.det == 2))):
        s = d[sm]
        if len(s) == 0:
            continue
        cands = (['C1', '2a'] if band.startswith('(i)') or band.startswith('(iii)')
                 else CANDS) + ['no_clip_ref']
        for c in cands:
            label = ('no_clip(=2a=2b)' if c == '2a' and (band.startswith('(i)') or band.startswith('(iii)'))
                     else c)
            if label == 'no_clip_ref' and (band.startswith('(i)') or band.startswith('(iii)')):
                continue
            r = {'band': band, 'scope': scope, 'cand': label, 'rows': len(s),
                 'configs': s.Config.nunique(), 'families': s.Family.nunique(),
                 'below_floor': int(s.below_floor.sum()), **metrics(s, f'R_{c}')}
            if c != 'C1':
                r.update(paired(s, f'R_{c}'))
            res.append(r)
res = pd.DataFrame(res)

# Engineering relevance: same comparison split by the relevance floor.
rel = []
for band in ('(i) dep x<1', '(ii) 1<=x<2 cumulative', '(iii) conditional'):
    for flag, name in ((False, 'above_floor'), (True, 'below_floor')):
        s = d[BANDS[band] & (d.below_floor == flag)]
        if len(s) < 3:
            rel.append({'band': band, 'load': name, 'rows': len(s)})
            continue
        for c in (['C1', '2a'] if not band.startswith('(ii)') else CANDS):
            r = {'band': band, 'load': name, 'cand': c, 'rows': len(s),
                 'families': s.Family.nunique(), **metrics(s, f'R_{c}')}
            if c != 'C1':
                r.update(paired(s, f'R_{c}'))
            rel.append(r)
rel = pd.DataFrame(rel)

# Mathematical checks on a grid, every held-out config with its fold's Lambda.
cfg = d.drop_duplicates('Config')[['Config', 'det', 'lam']]
xg = np.round(np.arange(0.01, 4.5 + 1e-12, 1e-3), 6)
math = []
for c in CANDS:
    worst_jump, n_decr, ends = 0.0, 0, []
    for lam in cfg['lam'].values:
        y = xg * lam_eff(xg, np.full_like(xg, lam), c)        # R_urban / R_hat
        dy = np.diff(y)
        n_decr += int((dy < -1e-12).sum())
        # Continuity: no step larger than the steepest slope allows (lam) times dx.
        worst_jump = max(worst_jump, float(np.max(np.abs(dy) / (lam * 1e-3))))
        lam_e = lam_eff(xg, np.full_like(xg, lam), c)
        idx = np.where(np.isclose(lam_e, 1.0) & (xg >= 1))[0]
        ends.append(xg[idx[0]] if len(idx) else np.inf)
    ends = np.array(ends)
    math.append({'cand': c, 'decreasing_steps': n_decr,
                 'max_step_over_max_slope': worst_jump,
                 'identity_at_x_p50': np.median(ends), 'identity_at_x_max': ends.max(),
                 'configs_identity_beyond_data_x>=1.9': int((ends > 1.9).sum()),
                 'configs_identity_beyond_x=3': int((ends > 3).sum())})
math = pd.DataFrame(math)

pd.set_option('display.width', 260)
show = ['band', 'scope', 'cand', 'rows', 'families', 'below_floor', 'MAPE', 'R2', 'RMSE_m',
        'MAE_m', 'bias_pct', 'p90_abs', 'max_abs', 'under20_pct', 'dMAPE', 'dMAPE_lo',
        'dMAPE_hi', 'dbias', 'fam_better']
with pd.option_context('display.float_format', '{:7.2f}'.format):
    print(res[show].to_string(index=False))
    print('\n== split by relevance floor (I_ff/W^1/3 < 23.6)')
    print(rel.reindex(columns=['band', 'load', 'cand', 'rows', 'families', 'MAPE', 'RMSE_m',
                               'bias_pct', 'under20_pct', 'dMAPE', 'dMAPE_lo', 'dMAPE_hi']).to_string(index=False))
with pd.option_context('display.float_format', '{:7.3f}'.format):
    print('\n== mathematical checks, x in [0.01, 4.5], step 1e-3, all 96 held-out configs')
    print(math.to_string(index=False))
print(f"\nLambda_I out-of-fold: min {cfg.lam.min():.3f} median {cfg.lam.median():.3f} max {cfg.lam.max():.3f}")
for name, df in (('rows', d), ('metrics', res), ('relevance', rel), ('math', math)):
    df.to_csv(OUT / f'{name}.csv', index=False)
