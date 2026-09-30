"""Read-only audit of grids.process_grids merge. Writes nothing in the repo."""
import sys, glob, os, json
import numpy as np
REPO = sys.argv[1]
sys.path.insert(0, REPO)
from blastlib.io import raw_store
from blastlib import constants
from blastlib.processing.grids import _interp2_nearest, _interp2_linear

S = np.float32(0.001)
TOL = 0.05
THR = constants.PARAMS['thresholdP_kPa']
MINP = constants.PARAMS['minPressure_kPa']
DETAIL = set(sys.argv[2].split(','))

def cats(a):
    a = np.asarray(a)
    return dict(sent=int((a == S).sum()), zero=int((a == 0).sum()),
                between=int(((a > 0) & (a < S)).sum()), above=int((a > S).sum()),
                neg=int((a < 0).sum()), nan=int(np.isnan(a).sum()))

def readmit(out, data, gf, gc):
    """Coarse grid gc cells inside the box of finer grid gf that stay valid."""
    Xf, Zf = out[f'X{gf}'], out[f'Z{gf}']
    Xc, Zc = out[f'X{gc}'], out[f'Z{gc}']
    inbox = (Xc <= Xf.max()) & (Zc <= Zf.max())
    valid = ~np.isnan(out[f'ratioP{gc}'])
    re = inbox & valid
    # nearest finer-grid raw values at coarse cell centres
    nf_P = _interp2_nearest(Xf, Zf, data[f'peakP{gf}'].astype(float), Xc, Zc, fill_value=np.nan)
    nf_R = _interp2_nearest(Xf, Zf, data[f'refP{gf}'].astype(float), Xc, Zc, fill_value=np.nan)
    kind = np.full(Xc.shape, '', dtype=object)
    kind[re & (nf_P == S)] = 'wall'            # finer cell is building sentinel
    kind[re & (nf_P == 0) & (nf_R > S)] = 'zero_refarrived'   # 62-type: urban empty, ref not
    kind[re & (nf_P == 0) & (nf_R <= S)] = 'zero_both'        # both empty: coarse true for both
    kind[re & (nf_P > 0) & (nf_P < S)] = 'between'
    kind[re & (nf_P > S)] = 'edge_other'       # finer valid (box edge / nearest mismatch)
    kind[re & np.isnan(nf_P)] = 'edge_other'
    r = np.hypot(Xc, Zc)
    res = {}
    for k in ('wall', 'zero_refarrived', 'zero_both', 'between', 'edge_other'):
        m = kind == k
        rp = out[f'ratioP{gc}'][m]; ri = out[f'ratioI{gc}'][m]
        idx = np.argwhere(m)
        # examples: the 3 with largest |ratioP-1|
        ex = []
        if m.any():
            dev = np.abs(np.nan_to_num(rp, nan=1) - 1)
            for j in np.argsort(-dev)[:3]:
                i0, i1 = idx[j]
                ex.append(dict(grid=gc, iz=int(i0), ix=int(i1),
                               X=round(float(Xc[i0, i1]), 3), Z=round(float(Zc[i0, i1]), 3),
                               r=round(float(r[i0, i1]), 2),
                               P_raw=float(data[f'peakP{gc}'][i0, i1]), refP_raw=float(data[f'refP{gc}'][i0, i1]),
                               fine_P_raw=float(nf_P[i0, i1]), fine_refP_raw=float(nf_R[i0, i1]),
                               ratioP_final=float(out[f'ratioP{gc}'][i0, i1]),
                               ratioI_final=float(out[f'ratioI{gc}'][i0, i1])))
        res[k] = dict(n=int(m.sum()),
                      n_viol_P=int((np.abs(rp - 1) > TOL).sum()),
                      n_viol_I=int((np.abs(ri - 1) > TOL).sum()),
                      rmin=float(r[m].min()) if m.any() else None,
                      rmax=float(r[m].max()) if m.any() else None,
                      maxratioP=float(np.nanmax(rp)) if m.any() else None,
                      examples=ex)
    return res

def raw_vs_filled(out, data):
    """(c): where does the filled/merged path decide differently from raw."""
    res = {}
    for g in '123':
        P = data[f'peakP{g}'].astype(float); R = data[f'refP{g}'].astype(float)
        I = data[f'impulse{g}'].astype(float); RI = data[f'refI{g}'].astype(float)
        valid = ~np.isnan(out[f'ratioP{g}'])
        Pf = out[f'peakP{g}_orig']; Rf = out[f'refP{g}_fill']
        rfinal = out[f'ratioP{g}']; rIfinal = out[f'ratioI{g}']
        with np.errstate(divide='ignore', invalid='ignore'):
            rraw = np.where(np.isnan(rfinal), np.nan, P / R)
            rIraw = I / RI
        pinned = valid & (rfinal == 1.0)
        free = valid & ~pinned
        # hard violation flag with filled ratio (what the scan sees) vs raw/raw
        vf = np.abs(rfinal - 1) > TOL
        vr = np.abs(rraw - 1) > TOL
        # impulse: the pinning uses raw; a non-pinned value uses filled
        freeI = valid & (rIfinal != 1.0)
        vIf = np.abs(rIfinal - 1) > TOL
        vIr = np.abs(rIraw - 1) > TOL
        res[g] = dict(valid=int(valid.sum()),
                      P_filled_ne_raw=int((valid & (Pf != P)).sum()),
                      refP_filled_ne_raw=int((valid & (Rf != R)).sum()),
                      refP_raw_le_sentinel=int((valid & (R <= S)).sum()),
                      nonpinned_P=int(free.sum()),
                      viol_flag_differs_P=int((free & (vf != vr)).sum()),
                      nonpinned_I=int(freeI.sum()),
                      viol_flag_differs_I=int((freeI & (vIf != vIr)).sum()))
    return res

files = sorted(glob.glob(os.path.join(REPO, 'data', 'raw_npz', 'config_*.npz')))
summary, times, detail = [], [], {}
for f in files:
    name = os.path.basename(f)[:-4]
    num = name.split('_')[1]
    raw = dict(np.load(f, allow_pickle=True))
    tu = [float(raw[f't_urban{g}']) for g in '123']
    tr = [float(raw[f't_ref{g}']) for g in '123']
    times.append(dict(cfg=name, t_urban=tu, t_ref=tr,
                      urban_ok=tu[0] < tu[1] < tu[2], ref_ok=tr[0] < tr[1] < tr[2]))
    data = raw_store.grids_from_raw(raw)
    out = raw_store.expand(raw)
    r12 = readmit(out, data, '1', '2')
    r23 = readmit(out, data, '2', '3')
    row = dict(cfg=name)
    for tag, rr in (('2in1', r12), ('3in2', r23)):
        for k, v in rr.items():
            row[f'{tag}_{k}'] = v['n']
            row[f'{tag}_{k}_violP'] = v['n_viol_P']
            row[f'{tag}_{k}_violI'] = v['n_viol_I']
    summary.append(row)
    if num in DETAIL:
        detail[name] = dict(
            counts={g: dict(urban=cats(data[f'peakP{g}']), ref=cats(data[f'refP{g}']))
                    for g in '123'},
            times=dict(t_urban=tu, t_ref=tr),
            readmit_2in1=r12, readmit_3in2=r23,
            raw_vs_filled=raw_vs_filled(out, data),
            empty_fine_masked=int(((data['peakP1'] == 0) & np.isnan(out['ratioP1'])).sum()),
            empty_fine_total=int((data['peakP1'] == 0).sum()))
    print(name, 'done', flush=True)

od = sys.argv[3]
json.dump(dict(summary=summary, times=times, detail=detail, THR=THR),
          open(os.path.join(od, 'merge_audit.json'), 'w'), indent=1, default=str)
