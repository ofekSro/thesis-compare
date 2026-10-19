"""Z bands: each street cell labelled by the smallest free-field Z whose level it reaches.

For one configuration and a list of integer Z_free values, every open cell gets
the smallest listed Z whose free-field level L(Z) it reaches. L(Z) is sampled
per direction exactly as the MaxR loop of run_analysis.run_phase1 does: the
median of the max-filled reference in a ring at R_free = Z * W^(1/3)
(free_field.reference_level_per_theta), with the free_field_data.csv scalar
where a sector has no reference, on the sector layout of the chosen estimator.

Per load the bands are cut at Z_cut, the largest listed Z whose row in the
phase-1 MaxR table lies inside R_conv (beyond_* is False). Categories:
  band k            the cell reaches L(z_k), z_k <= Z_cut (kept beyond R_conv too)
  below             no band, inside R_conv (weaker than L(Z_cut))
  outside           no band, beyond R_conv (drawn white)
  NaN               building, or a coarse cell under a finer grid
Read-only: nothing here writes a file.
"""

import numpy as np
import pandas as pd

from blastlib import constants, paths
from blastlib.geometry import concat3
from blastlib.processing.free_field import reference_level_per_theta, theta_index
from blastlib.processing.radius_estimator import resolve_estimator
from blastlib.regression.z_urban import Z_URBAN_ZF_MIN

Z_ALL = tuple(range(1, 21))
LOADS = {'P': ('peakP{}_orig', 'refP{}'), 'I': ('impulse{}_orig', 'refI{}')}


def parse_z_list(text):
    """'2, 4,6' -> (2, 4, 6): sorted unique integers in 1..20; ValueError otherwise."""
    parts = [p for p in str(text).replace(';', ',').replace(' ', ',').split(',') if p]
    if not parts:
        raise ValueError('Enter at least one Z (integers 1-20, comma separated).')
    try:
        zs = sorted({int(p) for p in parts})
    except ValueError:
        raise ValueError(f'Z list must be integers, got {text!r}.')
    bad = [z for z in zs if z not in Z_ALL]
    if bad:
        raise ValueError(f'Z must be in 1..20, got {bad}.')
    return tuple(zs)


def band_levels(processed, cfg, estimator, ff_lookup, z_values=Z_ALL):
    """Per-direction free-field level for every Z, as the phase-1 MaxR loop builds it.

    Returns {load: {Z: array (n_theta,)}} in the field's units (kPa for P,
    Pa*s for I).
    """
    est = resolve_estimator(estimator)
    n = est['n_theta']
    X, Zc = concat3(processed, 'X{}'), concat3(processed, 'Z{}')
    th = theta_index(X, Zc, n)
    dist = np.hypot(X, Zc)
    filled = 'refP1_fill' in processed
    W = cfg['weight']
    W13 = float(W) ** (1 / 3)
    out = {}
    for t, (_, ref_key) in LOADS.items():
        ref = concat3(processed, ref_key + ('_fill' if filled else ''))
        out[t] = {}
        for z in z_values:
            fallback = ff_lookup[W][z][0 if t == 'P' else 1]
            row = reference_level_per_theta(ref, dist, th, z * W13, n_theta=n)
            out[t][z] = np.where(np.isnan(row), fallback, row)
    return out


def band_index(values, th_idx, levels):
    """Index of the smallest Z (rows of *levels*, ascending Z) the cell reaches.

    values, th_idx : same-shape arrays; levels : (n_z, n_theta).
    Returns int array: k for a band, -1 for no band, -2 for a NaN cell.
    """
    values = np.asarray(values, float)
    out = np.full(values.shape, -1, dtype=int)
    ok = np.isfinite(values) & (th_idx >= 0)
    # descending Z, so the smallest Z the cell reaches is written last
    for k in range(len(levels) - 1, -1, -1):
        thr = np.where(th_idx >= 0, levels[k][np.clip(th_idx, 0, None)], np.inf)
        out[ok & (values >= thr)] = k
    out[~np.isfinite(values)] = -2
    return out


def z_cut(rows, z_list, load):
    """Largest listed Z whose MaxR lies inside R_conv (beyond flag False); None if none.

    rows : the max_radius_per_Z rows of this config (columns Z, beyond_P, beyond_I).
    """
    flags = rows.set_index('Z')[f'beyond_{load}'].astype(str).str.lower().isin(['true', '1', '1.0'])
    inside = [z for z in z_list if z in flags.index and not flags[z]]
    return max(inside) if inside else None


def classify(band_idx, dist, n_shown, r_conv):
    """Category per cell: 0..n_shown-1 band, n_shown below, n_shown+1 outside, NaN masked."""
    cat = np.full(band_idx.shape, np.nan)
    shown = (band_idx >= 0) & (band_idx < n_shown)
    cat[shown] = band_idx[shown]
    none = (band_idx == -1) | (band_idx >= n_shown)
    cat[none & (dist < r_conv)] = n_shown
    cat[none & ~(dist < r_conv)] = n_shown + 1
    return cat


def load_tables(method, tables_dir=None):
    """(convergence table, max_radius_per_Z table) of an estimator token; FileNotFoundError if absent."""
    tdir = paths.resolve(tables_dir, paths.TABLES_DIR)
    conv = tdir / paths.suffixed(paths.CONV_CSV.name, method)
    maxr = tdir / paths.suffixed(paths.MAXR_CSV.name, method)
    for p in (conv, maxr):
        if not p.exists():
            raise FileNotFoundError(f'{p.name} not found — run phase 1 with {method} first.')
    return pd.read_csv(conv), pd.read_csv(maxr)


def compute(processed, cfg, config_name, z_list, method, levels, conv, maxr):
    """Everything the figure needs, per load. levels from band_levels, covering z_list.

    Returns {load: dict(z_shown, z_cut, r_conv, maxr {z: r}, maxr_raw (bool),
    layers [(X, Z, category)] coarse to fine, level {z: median level})}.
    """
    est = resolve_estimator(method)
    n = est['n_theta']
    crow = conv.set_index('ConfigName').loc[config_name]
    rows = maxr[maxr.Config == config_name]
    W13 = float(cfg['weight']) ** (1 / 3)
    period = float(cfg['bsize'] + cfg['swidth'])
    out = {}
    for t, (val_key, _) in LOADS.items():
        r_conv = float(crow[f'Radius{t}'])
        # inner edge of the Z_urban prediction domain (z_urban_valid_mask
        # conditions 3-5): the first street, Z_free >= 2, and one urban
        # period (D46)
        target = 'Pressure' if t == 'P' else 'Impulse'
        r_min = max(float(rows['ExcludeR'].iloc[0]),
                    Z_URBAN_ZF_MIN[target] * W13,
                    constants.Z_URBAN_MIN_PERIODS * period)
        zc = z_cut(rows, z_list, t)
        z_shown = tuple(z for z in z_list if zc is not None and z <= zc)
        lv = np.vstack([levels[t][z] for z in z_list])
        # MaxR circles: the measured reach. reqdir tables also carry the
        # normalised equivalent distance in MaxR_*, which is not a map distance.
        raw_col = f'MaxR_{t}_raw'
        use_raw = raw_col in rows.columns
        col = raw_col if use_raw else f'MaxR_{t}'
        r_by_z = rows.set_index('Z')[col]
        layers = []
        for g in ('3', '2', '1'):
            Xg, Zg = processed[f'X{g}'], processed[f'Z{g}']
            th = theta_index(Xg.ravel(), Zg.ravel(), n).reshape(Xg.shape)
            bidx = band_index(processed[val_key.format(g)], th, lv)
            layers.append((Xg, Zg, classify(bidx, np.hypot(Xg, Zg), len(z_shown), r_conv)))
        out[t] = dict(z_shown=z_shown, z_cut=zc, r_conv=r_conv, r_min=r_min, layers=layers,
                      maxr={z: float(r_by_z[z]) for z in z_shown if z in r_by_z.index},
                      maxr_raw=use_raw,
                      level={z: float(np.nanmedian(levels[t][z])) for z in z_shown})
    return out
