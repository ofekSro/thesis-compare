"""Sensitivity of R_conv to re-admitted defect cells (read-only, scratch).

Variant A = as-is (must equal the table of record).
Variant B = defect cells removed (NaN): coarser cells inside a finer box whose
nearest finer cell is sentinel (wall), zero or between. Diagnostic only,
not a proposed fix.
Variant C = only for zero/between cells: coarse ratio recomputed with the
finer grid's raw reference (nearest) instead of the coarse residual ref.
"""
import sys, os, json, csv
import numpy as np
REPO = sys.argv[1]; OD = sys.argv[2]; CFGS = sys.argv[3].split(',')
sys.path.insert(0, REPO)
from blastlib.io import raw_store
from blastlib.config.parser import config_parser
from blastlib.geometry import concat3, exclude_radius
from blastlib.processing.radius_estimator import resolve_estimator
from blastlib.processing.convergence import find_convergence_radius
from blastlib.processing.soft_criterion import soft_pressure_fields, soft_pressure_weights
from blastlib.processing.grids import _interp2_nearest

S = np.float32(0.001)
est = resolve_estimator(None)
rec = {r['ConfigName']: r for r in csv.DictReader(open(
    os.path.join(REPO, 'outputs', 'tables', 'convergence_table_req_soft3.csv')))}

def defect_masks(out, data, gf, gc):
    Xf, Zf, Xc, Zc = out[f'X{gf}'], out[f'Z{gf}'], out[f'X{gc}'], out[f'Z{gc}']
    inbox = (Xc <= Xf.max()) & (Zc <= Zf.max())
    valid = ~np.isnan(out[f'ratioP{gc}'])
    nf = _interp2_nearest(Xf, Zf, data[f'peakP{gf}'].astype(float), Xc, Zc, fill_value=np.nan)
    nR = _interp2_nearest(Xf, Zf, data[f'refP{gf}'].astype(float), Xc, Zc, fill_value=np.nan)
    nRI = _interp2_nearest(Xf, Zf, data[f'refI{gf}'].astype(float), Xc, Zc, fill_value=np.nan)
    wall = inbox & valid & (nf == S)
    empty = inbox & valid & (nf >= 0) & (nf < S)
    return wall, empty, nR, nRI

def radius(p, cfg):
    w = soft_pressure_weights(soft_pressure_fields(p), est['soft_beta']) if est['soft_beta'] is not None else None
    r = find_convergence_radius(concat3(p, 'ratioP{}'), concat3(p, 'ratioI{}'),
                                p['peakP_all'], p['peakI_all'],
                                concat3(p, 'X{}'), concat3(p, 'Z{}'),
                                exclude_radius(cfg), estimator=est, soft_w_P=w)
    return r['pressure'], r['impulse'], r['pressureAtRadius']

res = {}
for c in CFGS:
    f = [x for x in os.listdir(os.path.join(REPO, 'data', 'raw_npz')) if x.startswith(f'config_{c}_')][0]
    name = f[:-4]; cfg = config_parser(name)
    raw = dict(np.load(os.path.join(REPO, 'data', 'raw_npz', f), allow_pickle=True))
    data = raw_store.grids_from_raw(raw)
    A = raw_store.expand(raw)
    rA = radius(A, cfg)
    B = raw_store.expand(raw); C = raw_store.expand(raw)
    nB = 0
    for gf, gc in (('1', '2'), ('2', '3')):
        wall, empty, nR, nRI = defect_masks(A, data, gf, gc)
        m = wall | empty; nB += int(m.sum())
        for k in (f'ratioP{gc}', f'ratioI{gc}', f'ratioP{gc}_raw', f'ratioI{gc}_raw'):
            B[k] = B[k].copy(); B[k][m] = np.nan
        # C: empty cells -> use the finer grid's reference (hard band + ratio)
        P = data[f'peakP{gc}'].astype(float); I = data[f'impulse{gc}'].astype(float)
        with np.errstate(divide='ignore', invalid='ignore'):
            rp = P / nR; ri = I / nRI
        convP = (P < 10) | (np.abs(P - nR) < 10)
        convI = (P < 10) | (np.abs(I - nRI) / nRI < 0.05) if False else None
        for k in (f'ratioP{gc}', f'ratioP{gc}_raw'):
            C[k] = C[k].copy(); C[k][empty] = np.where(convP[empty] & (k == f'ratioP{gc}'), 1.0, rp[empty])
        C[f'refP{gc}'] = C[f'refP{gc}'].copy().astype(float); C[f'refP{gc}'][empty] = nR[empty]
    rB = radius(B, cfg); rC = radius(C, cfg)
    res[name] = dict(record=(float(rec[name]['RadiusP']), float(rec[name]['RadiusI']), float(rec[name]['PressureAtR'])),
                     A_asis=rA, B_removed=rB, C_fine_ref_P=rC, n_removed=nB)
    print(name, json.dumps(res[name]), flush=True)
json.dump(res, open(os.path.join(OD, 'merge_sens.json'), 'w'), indent=1)
