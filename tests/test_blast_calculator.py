"""blast_calculator.html runs the production model (reqdir91_soft3, D50).

The page's own <script> is executed in node against a stub DOM, and its
functions are compared with the Python chain built from the
final_production_*_reqdir91_soft3 coefficient CSVs: R_conv, Lambda, the
chain (clip inside, identity beyond R_conv_hat), the Z_urban validity
domain, both tabs, and the pressure jump at R_conv where Lambda_P < 1 (D51).
Skips when node is not installed. Reads only tracked tables.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from blastlib import constants
from blastlib.geometry import area_density
from blastlib.regression.convergence_models import predict_impulse, predict_pi
from blastlib.regression.z_urban import (Z_URBAN_ZF_MIN, clip_z_urban_pred,
                                         predict_z_urban)

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / 'blast_calculator.html'
TOKEN = 'reqdir91_soft3'
NODE = shutil.which('node')
pytestmark = pytest.mark.skipif(NODE is None, reason='node not installed')

# Stub DOM: every element is a plain object; inputs read as '' so the page's
# own calc()/calcQ() return early at load. The harness then sets values.
HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const [html, queryFile] = process.argv.slice(2);
const src = fs.readFileSync(html, 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const els = {};
const el = id => els[id] || (els[id] = {id, value:'', innerHTML:'', textContent:'',
  className:'', classList:{toggle(){}}, addEventListener(){}, appendChild(){}});
const document = {getElementById: el, querySelectorAll: () => [],
                  createElement: () => ({innerHTML:''})};
const ctx = vm.createContext({document, Math, console});
vm.runInContext(src + `
;globalThis.__api = {zConvP, zConvI, lambda, chain, oneRow, calc, calcQ,
  checkDomain, domainBanner, bandPct,
  CONV_P, CONV_I, ZU, ENV, ZF_MIN, Z_URBAN_MIN_PERIODS};`, ctx);
const api = ctx.__api;
const q = JSON.parse(fs.readFileSync(queryFile, 'utf8'));
const out = {coef: {CONV_P: api.CONV_P, CONV_I: api.CONV_I, ZU: api.ZU, ENV: api.ENV,
             ZF_MIN: api.ZF_MIN, Z_URBAN_MIN_PERIODS: api.Z_URBAN_MIN_PERIODS},
             rows: [], dom: []};
for (const r of q.rows) {
  const c = r.cfg;
  const P = api.chain('P', c.det, c.b, c.s, c.H, c.W, r.Zf);
  const I = api.chain('I', c.det, c.b, c.s, c.H, c.W, r.Zf);
  out.rows.push({ZcP: api.zConvP(c.det,c.b,c.s,c.H,c.W), ZcI: api.zConvI(c.det,c.b,c.s,c.H,c.W),
    lamP: api.lambda('P',c.det,c.b,c.s,c.H,c.W,r.Zf).lam,
    lamI: api.lambda('I',c.det,c.b,c.s,c.H,c.W,r.Zf).lam,
    zuP: P.zu, stP: P.state, zuI: I.zu, stI: I.state});
}
// The boundary itself, at the page's own Z_conv (inclusive: identity).
out.boundary = q.boundary.map(c => {
  const ZcP = api.zConvP(c.det,c.b,c.s,c.H,c.W), ZcI = api.zConvI(c.det,c.b,c.s,c.H,c.W);
  const P = api.chain('P',c.det,c.b,c.s,c.H,c.W,ZcP), I = api.chain('I',c.det,c.b,c.s,c.H,c.W,ZcI);
  const Pb = api.chain('P',c.det,c.b,c.s,c.H,c.W,ZcP*(1-1e-12));
  return {ZcP, ZcI, stP:P.state, zuP:P.zu, stI:I.state, zuI:I.zu,
          stPb:Pb.state, zuPb:Pb.zu, lamPb:api.lambda('P',c.det,c.b,c.s,c.H,c.W,ZcP*(1-1e-12)).lam};
});
out.banners = (q.banner || []).map(c => {
  const d = api.checkDomain(c.b, c.s, c.H, c.W);
  return {tier: d.tier, html: api.domainBanner(d)};
});
// Both tabs through the page itself: set the inputs, run calc / calcQ.
for (const r of q.dom) {
  const c = r.cfg;
  for (const [a, v] of [['det',c.det],['b',c.b],['s',c.s],['H',c.H],['W',c.W],['zf',r.Zf]]) {
    el(a).value = String(v); el('q_' + a).value = String(v);
  }
  api.calc(); api.calcQ();
  out.dom.push({rup: el('rup').textContent, rui: el('rui').textContent,
                q_RP: el('q_RP').innerHTML, q_RI: el('q_RI').innerHTML});
}
process.stdout.write(JSON.stringify(out));
"""


def _coeffs():
    # round_trip: pandas' default float parser can drop the last digit.
    cv = pd.read_csv(ROOT / f'outputs/tables/final_production_convergence_coefficients_{TOKEN}.csv',
                     float_precision='round_trip')
    zu = pd.read_csv(ROOT / f'outputs/tables/final_production_z_urban_coefficients_{TOKEN}.csv',
                     float_precision='round_trip')
    conv_P, conv_I, z = {}, {}, {}
    for r in cv.itertuples():
        if r.Target == 'RadiusP':
            conv_P[r.Det] = {'C0': r.C0, 'C1': r.C1_sW13, 'C2': r.C2_switch,
                             'C3': r.C3_canyon, 'a': r.a_thresh}
        else:
            conv_I[r.Det] = {'A': r.A, 'p': r.p_rho, 'q': r.q_HoverS,
                             'r': r.r_sW13, 'r2': r.r2_sW13sq}
    for r in zu.itertuples():
        if r.Target == 'Pressure':
            z[(r.Det, 'P')] = {'C0': r.C0, 'C1': r.C1_amp, 'A': r.A_switch, 'B': r.B_open}
        else:
            z[(r.Det, 'I')] = {'C0': r.C0, 'C1': r.C1_amp, 'C2': r.C2_self, 'C3': r.C3_dilute}
    return conv_P, conv_I, z


def _configs():
    c = pd.read_csv(ROOT / f'outputs/tables/convergence_table_{TOKEN}.csv')
    return [{'name': r.ConfigName, 'det': int(r.Det), 'b': float(r.BuildingSize),
             's': float(r.StreetWidth), 'H': float(r.Height), 'W': float(r.ChargeWeight)}
            for r in c.itertuples()]


def _py_chain(cfg, Zf, tg, conv_P, conv_I, z):
    """Production chain + Z_urban domain, one row; returns (Z_urban, state)."""
    W13 = cfg['W'] ** (1 / 3)
    rho = area_density(cfg['b'], cfg['s'])
    sub = pd.DataFrame({'weight': [cfg['W']], 'rho': [rho], 'height': [cfg['H']],
                        'swidth': [cfg['s']], 'bsize': [cfg['b']], 'Z_free': [Zf],
                        'R_free': [Zf * W13]})
    name = 'Pressure' if tg == 'P' else 'Impulse'
    lam = predict_z_urban(np.array([Zf]), np.array([rho]), np.array([cfg['H']]),
                          np.array([cfg['s']]), np.array([W13]), name, z[(cfg['det'], tg)])[0] / Zf
    out, clipped, ident = clip_z_urban_pred(np.array([lam * Zf]), sub, cfg['det'], name,
                                            {cfg['det']: conv_P[cfg['det']]},
                                            {cfg['det']: conv_I[cfg['det']]}, return_flags=True)
    if ident[0]:
        return out[0], 'free'
    if Zf < Z_URBAN_ZF_MIN[name] or Zf * W13 < constants.Z_URBAN_MIN_PERIODS * (cfg['b'] + cfg['s']):
        return np.nan, ('nearZ' if Zf < Z_URBAN_ZF_MIN[name] else 'street')
    return out[0], ('clip' if clipped[0] else 'urban')


def _zconv(cfg, conv_P, conv_I):
    rho = area_density(cfg['b'], cfg['s'])
    args = ([cfg['W']], [rho], [cfg['H']], [cfg['det']], [cfg['s']], [cfg['b']])
    W13 = cfg['W'] ** (1 / 3)
    return (predict_pi(*map(np.array, args), {cfg['det']: conv_P[cfg['det']]})[0] / W13,
            predict_impulse(*map(np.array, args), {cfg['det']: conv_I[cfg['det']]})[0] / W13)


def _run(rows, dom, tmp_path, boundary=(), banner=()):
    qf = tmp_path / 'q.json'
    qf.write_text(json.dumps({'rows': rows, 'dom': dom, 'boundary': list(boundary),
                              'banner': list(banner)}))
    hf = tmp_path / 'harness.js'
    hf.write_text(HARNESS)
    res = subprocess.run([NODE, str(hf), str(HTML), str(qf)], capture_output=True,
                         text=True, encoding='utf-8', check=True)
    return json.loads(res.stdout)


@pytest.fixture(scope='module')
def model():
    return _coeffs(), _configs()


def test_coefficients_and_domain_constants_are_production(model, tmp_path):
    (conv_P, conv_I, z), cfgs = model
    js = _run([], [], tmp_path)['coef']
    for det in (1, 2):
        for k, v in conv_P[det].items():
            assert js['CONV_P'][str(det)][k] == v
        for k, v in conv_I[det].items():
            assert js['CONV_I'][str(det)][k] == v
        for tg in 'PI':
            for k, v in z[(det, tg)].items():
                assert js['ZU'][tg][str(det)][k] == v
    assert js['ZF_MIN'] == Z_URBAN_ZF_MIN['Pressure'] == Z_URBAN_ZF_MIN['Impulse']
    assert js['Z_URBAN_MIN_PERIODS'] == constants.Z_URBAN_MIN_PERIODS
    c = pd.DataFrame(cfgs)
    for k, col in (('b', 'b'), ('s', 's'), ('H', 'H'), ('W', 'W')):
        assert js['ENV'][k] == [c[col].min(), c[col].max()]
    assert constants.RADIUS_ESTIMATOR['method'] == TOKEN


def test_chain_matches_production_for_every_config(model, tmp_path):
    (conv_P, conv_I, z), cfgs = model
    rows, expect = [], []
    for cfg in cfgs:
        ZcP, ZcI = _zconv(cfg, conv_P, conv_I)
        grid = list(np.arange(1.5, 20.01, 0.5))
        for Zc in (ZcP, ZcI):                     # both sides of each boundary
            grid += [Zc * (1 - 1e-9), Zc * (1 + 1e-9)]
        for Zf in grid:
            rows.append({'cfg': cfg, 'Zf': float(Zf)})
            expect.append((cfg, float(Zf), ZcP, ZcI))
    js = _run(rows, [], tmp_path)['rows']
    n_state = {}
    for r, (cfg, Zf, ZcP, ZcI) in zip(js, expect):
        assert r['ZcP'] == pytest.approx(ZcP, rel=1e-12)
        assert r['ZcI'] == pytest.approx(ZcI, rel=1e-12)
        for tg in 'PI':
            zu, st = _py_chain(cfg, Zf, tg, conv_P, conv_I, z)
            assert r[f'st{tg}'] == st, (cfg['name'], Zf, tg)
            if np.isnan(zu):
                assert r[f'zu{tg}'] is None or np.isnan(r[f'zu{tg}'])
            else:
                assert r[f'zu{tg}'] == pytest.approx(zu, rel=1e-12), (cfg['name'], Zf, tg)
            n_state[st] = n_state.get(st, 0) + 1
    assert set(n_state) == {'free', 'street', 'clip', 'urban', 'nearZ'}


def test_both_tabs_give_the_same_answer(model, tmp_path):
    _, cfgs = model
    dom = [{'cfg': cfg, 'Zf': Zf} for cfg in cfgs[::7] for Zf in (3.0, 6.0, 9.5, 14.0)]
    out = _run([], dom, tmp_path)['dom']
    num = lambda s: re.match(r'[-–\d.]+', s).group(0)
    for d in out:
        assert num(d['rup']) == num(d['q_RP'])
        assert num(d['rui']) == num(d['q_RI'])


def test_boundary_is_inclusive_identity_and_d51_jump(model, tmp_path):
    """At its own Z_conv the page returns Z_free (both loads); just inside,
    pressure gives min(Lambda Z_free, Z_conv), so the step at R_conv is
    1/Lambda where Lambda_P < 1 (D51) and 1 otherwise; impulse never jumps."""
    _, cfgs = model
    b = _run([], [], tmp_path, boundary=cfgs)['boundary']
    jumps, lam_all, no_domain = [], [], 0
    for cfg, r in zip(cfgs, b):
        assert r['stP'] == 'free' and r['zuP'] == r['ZcP']
        assert r['stI'] == 'free' and r['zuI'] == r['ZcI']
        lam_all.append(r['lamPb'])
        if r['stPb'] in ('urban', 'clip'):
            jumps.append((cfg['name'], r['lamPb'], r['zuP'] / r['zuPb']))
        else:
            no_domain += 1                     # R_conv,P_hat < b+s: no Z_urban,P row
    j = pd.DataFrame(jumps, columns=['cfg', 'lam', 'ratio'])
    att = j[j.lam < 1]
    assert np.allclose(att.ratio, 1 / att.lam, rtol=1e-9)
    assert np.allclose(j[j.lam >= 1].ratio, 1.0, rtol=1e-9)        # continuous otherwise
    # D51 record: Lambda_P < 1 at R_conv in 10 of 96 configs (production
    # coefficients), max +6.3%; 2 of them (config_16, config_34) have no
    # Z_urban,P domain below R_conv, so the page shows the jump in 8.
    assert int((np.array(lam_all) < 1).sum()) == 10
    assert len(att) == 8 and no_domain == 17
    assert (1 / np.array(lam_all)).max() == pytest.approx(1.063, abs=1e-3)


def test_chain_is_non_decreasing_in_z_free(model, tmp_path):
    (conv_P, conv_I, z), cfgs = model
    rows, meta = [], []
    for cfg in cfgs:
        for Zf in np.linspace(2.0, 22.0, 801):
            rows.append({'cfg': cfg, 'Zf': float(Zf)})
            meta.append(cfg['name'])
    js = _run(rows, [], tmp_path)['rows']
    df = pd.DataFrame([{'cfg': m, 'zuP': r['zuP'], 'zuI': r['zuI']} for m, r in zip(meta, js)])
    for name, g in df.groupby('cfg', sort=False):
        for col in ('zuP', 'zuI'):
            v = g[col].dropna().values                # 'street' rows carry no value
            assert np.all(np.diff(v) >= -1e-12), (name, col)


def test_no_safety_claim_on_the_core_box_d6(model, tmp_path):
    """D6 open: the box misses its own 20% criterion on 4 of 38 configs, so
    the page must not call it safe (owner, 2026-10-22)."""
    _, cfgs = model
    out = _run([], [], tmp_path, banner=cfgs)['banners']
    core = [o['html'] for o in out if o['tier'] == 'safe']
    assert len(core) == 38
    for html in core:
        assert 'התחום הבטוח' not in html and '✓' not in html
        assert 'אינו</b> תחום בטוח' in html and '34 מתוך 38' in html
    src = HTML.read_text(encoding='utf-8')
    assert 'בתוך התחום הבטוח' not in src
