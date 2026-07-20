"""Cross-validated regression for convergence radius and Z_urban.

Runs repeated random 80/20 train/test splits on the unified config pool,
fits Buckingham-Pi-consistent formulas (canonical form R = W^(1/3) * Z for
every target), and selects the best coefficients based on test-set MAPE.
R_urban is not fitted separately: R_urban = W^(1/3) * Z_urban identically.
"""

import os
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from config_parser import config_parser


# ============================================================
# Statistical helpers
# ============================================================

def _lstsq(X, y):
    """Solve OLS: X @ coef = y."""
    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    return coef


def _r2_mape(actual, predicted):
    """Return (R², MAPE%) for non-NaN pairs."""
    mask = np.isfinite(actual) & np.isfinite(predicted)
    if mask.sum() < 2:
        return np.nan, np.nan
    a, p = actual[mask], predicted[mask]
    SS_res = np.sum((a - p) ** 2)
    SS_tot = np.sum((a - a.mean()) ** 2)
    R2   = 1 - SS_res / SS_tot if SS_tot > 0 else np.nan
    MAPE = 100 * np.mean(np.abs(a - p) / np.abs(a))
    return R2, MAPE


# ============================================================
# Z_urban model (Buckingham Pi power law)
#
# Canonical form:  MaxR = W^(1/3) * Z_urban   (Hopkinson scaling imposed)
#
#   Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r
#
# Log-linear:  ln(Z_urban) = ln(C) + m*ln(Z_free) + p*ln(rho)
#                            + q*ln(H/s) + r*ln(s/W^(1/3))
# — a 5-coefficient OLS in log space per det group (same family as the
# RadiusI log model). All factors are dimensionless Pi groups (rho,
# Pi_3 = H/s, Pi_2 = s/W^(1/3)); W enters ONLY through W^(1/3).
# R_urban is NOT a separate model: R_urban = W^(1/3) * Z_urban identically.
#
# Validity domain: the impulse mapping is fitted/applied for Z_free >= 2
# only. At Z_free = 1 the point lies within one Hopkinson length of the
# charge (inside the first street), where the discrete near-field geometry
# dominates and per-row errors reach 80-116% — outside any smooth formula.
# Pressure is well-behaved at Z_free = 1 and keeps the full domain.
#
# Physical closure with the convergence radius: by definition the urban
# field equals free-field beyond R_conv, so MaxR can never exceed R_conv
# and never fall below the free-field radius Z_free*W^(1/3). Predictions
# are therefore clipped to  Z_free <= Z_urban <= Z_conv  using the
# convergence-radius formulas (RadiusP additive / RadiusI log) — the two
# formula systems form one consistent chain. For Z_free >= Z_conv the
# mapping is the identity (urban = free-field).
#
# Selected by config-level 5-fold CV over candidate families (additive Pi
# brackets, log brackets, geometry-modulated exponents, slenderness (b/H)
# corrections, L4/minimax fitting): the pure power law matched or beat the
# alternatives; slenderness terms improved CV MAPE by ~0.3-0.7% but were
# dropped for simplicity; tail-targeted norms were strictly worse
# out-of-sample. Remaining error tail: b=10 slender-tower configs and
# isolated W=50 rows (out-of-family geometry).
# ============================================================

Z_URBAN_ZF_MIN = {'Pressure': 1.0, 'Impulse': 2.0}


def _z_urban_design(Z_free, rho, H, s, W13):
    """Log-space design matrix: [1, ln(Zf), ln(rho), ln(H/s), ln(s/W^(1/3))]."""
    Z_free = np.asarray(Z_free, dtype=float)
    rho    = np.asarray(rho,    dtype=float)
    H      = np.asarray(H,      dtype=float)
    s      = np.asarray(s,      dtype=float)
    W13    = np.asarray(W13,    dtype=float)
    return np.column_stack([np.ones(len(rho)), np.log(Z_free), np.log(rho),
                            np.log(H / s), np.log(s / W13)])


def _fit_z_urban_group(Z_free, Z_urban, rho, H, s, W13, target_name):
    """Fit the Z_urban power law for one det group via log-space OLS.

    Returns {'C', 'm', 'p', 'q', 'r', 'zf_min'} or None on failure.
    """
    Z_urban = np.asarray(Z_urban, dtype=float)
    if not np.all(Z_urban > 0):
        return None
    X = _z_urban_design(Z_free, rho, H, s, W13)
    try:
        c0, m, p, q, r = _lstsq(X, np.log(Z_urban))
    except np.linalg.LinAlgError:
        return None
    return {'C': np.exp(c0), 'm': m, 'p': p, 'q': q, 'r': r,
            'zf_min': Z_URBAN_ZF_MIN[target_name]}


def _predict_z_urban(Z_free, rho, H, s, W13, target_name, coef):
    """Predict Z_urban = C * Zf^m * rho^p * (H/s)^q * (s/W^(1/3))^r."""
    X = _z_urban_design(Z_free, rho, H, s, W13)
    lnC = np.log(coef['C'])
    return np.exp(X @ np.array([lnC, coef['m'], coef['p'], coef['q'], coef['r']]))


def _clip_z_urban_pred(pred_Z, sub_valid, det_val, target_name,
                       conv_P_coeffs, conv_I_coeffs):
    """Clip Z_urban predictions to the physical interval [Z_free, Z_conv].

    MaxR cannot exceed the convergence radius (urban = free-field beyond it)
    nor fall below the free-field radius Z_free*W^(1/3). Z_conv comes from
    the fitted convergence-radius formulas, so the prediction chain is
    self-consistent. No-op if the convergence coefficients are missing.
    """
    coeffs = conv_P_coeffs if target_name == 'Pressure' else conv_I_coeffs
    if coeffs is None:
        return pred_Z

    W   = sub_valid['weight'].values.astype(float)
    W13 = W ** (1 / 3)
    det_arr = np.full(len(sub_valid), det_val, dtype=int)
    rho = sub_valid['rho'].values.astype(float)
    H   = sub_valid['height'].values.astype(float)
    s   = sub_valid['swidth'].values.astype(float)
    b   = sub_valid['bsize'].values.astype(float)

    if target_name == 'Pressure':
        Rconv = _predict_pi(W, rho, H, det_arr, s, b, coeffs)
    else:
        Rconv = _predict_impulse(W, rho, H, det_arr, s, b, coeffs)

    Zf = sub_valid['Z_free'].values.astype(float)
    pred_Z = np.where(np.isfinite(Rconv),
                      np.minimum(pred_Z, Rconv / W13), pred_Z)
    return np.maximum(pred_Z, Zf)


# ============================================================
# Convergence radius models
#
# Both targets share the canonical structure  R = W^(1/3) * Z  with a
# dimensionless Z. They differ in the Z expression (selected by a
# head-to-head comparison: leave-geometry-out CV + W-extrapolation):
#
#   RadiusP — additive Pi (switch) model:
#       Z = C0 + C1*(s/W^(1/3)) + C2*rho*(s/W^(1/3) - a)
#              + C3*sqrt(rho)*(H/s)*(W^(1/3)/s - 1)
#
#   RadiusI — log-space Pi model (2 coefficients per det):
#       Z = A * Pi^( k * ln(W^(1/3)/s) ),   Pi = H/(s*rho)
#     A is the scaled distance where the free-field pressure decays to
#     ~9 kPa — the blast is too weak beyond it for the city to matter.
#     The exponent flips sign at s = W^(1/3): confinement (high Pi)
#     extends R for large charges and shortens it for small ones.
#
# ============================================================
# RadiusP: Buckingham Pi additive model
#
# Target (Hopkinson-scaled convergence radius):
#   Z = R / W^(1/3)
#
# Dimensionless Pi groups used as LINEAR predictors of Z:
#   Pi_1 = rho = b^2/(b+s)^2        (area density)
#   Pi_2 = s / W^(1/3)              (scaled street width)
#   Pi_3 = rho * s / W^(1/3)        (interaction: density effect scaled to charge —
#          = Pi_1 * Pi_2              density matters more for small charges)
# Base Pi groups (from Buckingham: Z = f(rho, Pi_2, Pi_3) per det):
#   rho  = b^2/(b+s)^2     (area density)
#   Pi_2 = s / W^(1/3)     (scaled street width)
#   Pi_3 = H / s           (canyon aspect ratio)
#
# Formula (OLS, linear in the composed terms — not log-space):
#   Z = C0 + C1*Pi_2 + C2*rho*(Pi_2 - a) + C3*sqrt(rho)*Pi_3*(1/Pi_2 - 1)
#
#   a = 1 for det=1 (street), a = 2 for det=2 (intersection) — geometric
#   constant, not fitted (selected by CV from {1, sqrt(2), 2}).
#
# Physical interpretation:
#   C1*Pi_2 — baseline: scaled street width sets the relaxation to free field.
#   C2*rho*(Pi_2 - a) — density switch: rho extends R only when the street is
#     wide relative to the charge (weak blast trapped in the street network);
#     flips slightly negative for big charges (wave overtops the block).
#     At an intersection the threshold doubles (a=2): the cross provides two
#     orthogonal venting canyons, so the "trapped in network" regime where
#     density rules requires a twice-as-wide scaled street.
#   C3*sqrt(rho)*Pi_3*(1/Pi_2 - 1) — canyon law: the H/s effect flips sign at
#     the near-field boundary s = W^(1/3):
#       s < W^(1/3): channeling -> taller canyons push R out (positive)
#       s > W^(1/3): blocking   -> taller buildings strip energy, R shrinks
#     sqrt(rho) = b/(b+s) is the canyon wall continuity (1D line density):
#     cross-street gaps are pressure-relief vents; slender buildings make
#     leaky canyons that channel less.
#
#   For a street (a=1) the formula factors into a single-switch form:
#     Z = C0 + C1*Pi_2 + (Pi_2 - 1)*[C2*rho - C3*sqrt(rho)*Pi_3/Pi_2]
#   — one boundary, s = W^(1/3), separates the two physical regimes.
#
# The formula is fully dimensionally consistent (all terms dimensionless → Z dimensionless).
# ============================================================

def _compute_pi_terms(W, H, s, rho, a):
    """Compute the composed Pi terms from raw geometry arrays.

    All array inputs 1-D float; `a` is the det-dependent density-switch
    threshold (1 = street, 2 = intersection).

    Returns (pi2, switch, canyon):
        pi2    = s / W^(1/3)                          scaled street width
        switch = rho * (pi2 - a)                      density switch term
        canyon = sqrt(rho) * (H/s) * (W^(1/3)/s - 1)  canyon law term
    """
    W13 = W ** (1 / 3)
    pi2 = s / W13
    switch = rho * (pi2 - a)
    canyon = np.sqrt(rho) * (H / s) * (W13 / s - 1.0)
    return pi2, switch, canyon


def _fit_pi_group(W, rho, H, s, R_target, a_thresh):
    """Fit additive Pi model for one det group via OLS.

    Formula: Z = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                    + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1)
    where Z = R / W^(1/3) and a = a_thresh (1 street, 2 intersection).

    Returns dict with keys: C0, C1, C2, C3, a, has_H_term
    Returns None if fewer than 6 samples.
    """
    MIN_SAMPLES = 6
    W        = np.asarray(W,        dtype=float)
    rho      = np.asarray(rho,      dtype=float)
    H        = np.asarray(H,        dtype=float)
    s        = np.asarray(s,        dtype=float)
    R_target = np.asarray(R_target, dtype=float)

    valid = (W > 0) & (s > 0) & (R_target > 0)
    if valid.sum() < MIN_SAMPLES:
        return None

    W, rho, H, s, R_target = W[valid], rho[valid], H[valid], s[valid], R_target[valid]

    has_H = np.any(H > 0)
    Z = R_target / W ** (1 / 3)
    pi2, switch, canyon = _compute_pi_terms(W, H, s, rho, a_thresh)

    if has_H:
        X = np.column_stack([np.ones(len(W)), pi2, switch, canyon])
        coef = _lstsq(X, Z)
        C0, C1, C2, C3 = coef
    else:
        # H=0: canyon=0, so only C0, C1, C2 are identifiable
        X = np.column_stack([np.ones(len(W)), pi2, switch])
        coef = _lstsq(X, Z)
        C0, C1, C2 = coef
        C3 = 0.0

    return {'C0': C0, 'C1': C1, 'C2': C2, 'C3': C3, 'a': a_thresh,
            'has_H_term': has_H}


def _predict_pi(W, rho, H, det, s, b, pi_coeffs):
    """Predict convergence radius using additive Pi model for arrays of configs.

    Formula: R = W^(1/3) * (C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                                + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1))

    pi_coeffs: dict {det_val: coef_dict} from _fit_pi_group.
    Returns prediction array (NaN where group is missing).
    """
    W   = np.asarray(W,   dtype=float)
    rho = np.asarray(rho, dtype=float)
    H   = np.asarray(H,   dtype=float)
    det = np.asarray(det, dtype=int)
    s   = np.asarray(s,   dtype=float)

    pred = np.full(len(W), np.nan)
    for det_val, coef in pi_coeffs.items():
        if coef is None:
            continue
        mask = det == det_val
        if not mask.any():
            continue
        Wm, rm, Hm, sm = W[mask], rho[mask], H[mask], s[mask]
        W13m = Wm ** (1 / 3)
        pi2, switch, canyon = _compute_pi_terms(Wm, Hm, sm, rm, coef['a'])

        Z_pred = (coef['C0'] + coef['C1'] * pi2 + coef['C2'] * switch
                  + coef['C3'] * canyon)
        pred[mask] = Z_pred * W13m

    return pred


def _fit_pi_all_groups(conv_df, target_col):
    """Fit additive Pi model for det=1 and det=2 groups.

    Returns dict {det_val: coef_dict_or_None}.
    """
    W   = conv_df['ChargeWeight'].values.astype(float)
    H   = conv_df['Height'].values.astype(float)
    S   = conv_df['StreetWidth'].values.astype(float)
    rho = conv_df['AreaDensity'].values.astype(float)
    det = conv_df['Det'].values.astype(int)
    R   = conv_df[target_col].values.astype(float)

    # Density-switch threshold: 1 for street, 2 for intersection (two venting canyons)
    A_THRESH = {1: 1.0, 2: 2.0}

    coeffs = {}
    for det_val in [1, 2]:
        mask = det == det_val
        if mask.sum() < 5:
            coeffs[det_val] = None
            continue
        coef = _fit_pi_group(W[mask], rho[mask], H[mask], S[mask], R[mask],
                             a_thresh=A_THRESH[det_val])
        coeffs[det_val] = coef
    return coeffs


# ============================================================
# RadiusI: log-space Pi model
#
#   Z = R / W^(1/3) = A * Pi^( k * ln(W^(1/3)/s) ),  Pi = H/(s*rho)
#
# Log-linear:  ln(Z) = ln(A) + k * ln(Pi) * ln(W^(1/3)/s)
# so each det group is a 2-coefficient OLS in log space. The log form
# cannot predict a negative radius and won the impulse head-to-head on
# every out-of-sample test (leave-geometry-out CV, W-extrapolation).
# ============================================================

def _fit_impulse_group(W, rho, H, s, R_target):
    """Fit the log-space Pi model for one det group via OLS.

    Formula: Z = A * Pi^(k*ln(W^(1/3)/s)),  Pi = H/(s*rho), Z = R/W^(1/3)

    Returns dict with keys: A, k.  Returns None if fewer than 6 samples
    (or if H=0 anywhere — Pi requires H > 0).
    """
    MIN_SAMPLES = 6
    W        = np.asarray(W,        dtype=float)
    rho      = np.asarray(rho,      dtype=float)
    H        = np.asarray(H,        dtype=float)
    s        = np.asarray(s,        dtype=float)
    R_target = np.asarray(R_target, dtype=float)

    valid = (W > 0) & (s > 0) & (rho > 0) & (H > 0) & (R_target > 0)
    if valid.sum() < MIN_SAMPLES:
        return None
    W, rho, H, s, R_target = W[valid], rho[valid], H[valid], s[valid], R_target[valid]

    W13 = W ** (1 / 3)
    lnZ = np.log(R_target / W13)
    u = np.log(H / (s * rho)) * np.log(W13 / s)
    X = np.column_stack([np.ones(len(W)), u])
    c0, k = _lstsq(X, lnZ)
    return {'A': np.exp(c0), 'k': k}


def _predict_impulse(W, rho, H, det, s, b, imp_coeffs):
    """Predict convergence radius using the log-space Pi model.

    Formula: R = W^(1/3) * A * Pi^(k*ln(W^(1/3)/s)),  Pi = H/(s*rho)

    imp_coeffs: dict {det_val: coef_dict} from _fit_impulse_group.
    Returns prediction array (NaN where group is missing).
    """
    W   = np.asarray(W,   dtype=float)
    rho = np.asarray(rho, dtype=float)
    H   = np.asarray(H,   dtype=float)
    det = np.asarray(det, dtype=int)
    s   = np.asarray(s,   dtype=float)

    pred = np.full(len(W), np.nan)
    for det_val, coef in imp_coeffs.items():
        if coef is None:
            continue
        mask = (det == det_val) & (H > 0) & (rho > 0) & (s > 0)
        if not mask.any():
            continue
        W13m = W[mask] ** (1 / 3)
        u = np.log(H[mask] / (s[mask] * rho[mask])) * np.log(W13m / s[mask])
        pred[mask] = W13m * coef['A'] * np.exp(coef['k'] * u)
    return pred


def _fit_impulse_all_groups(conv_df, target_col='RadiusI'):
    """Fit the log-space Pi model for det=1 and det=2 groups.

    Returns dict {det_val: coef_dict_or_None}.
    """
    W   = conv_df['ChargeWeight'].values.astype(float)
    H   = conv_df['Height'].values.astype(float)
    S   = conv_df['StreetWidth'].values.astype(float)
    rho = conv_df['AreaDensity'].values.astype(float)
    det = conv_df['Det'].values.astype(int)
    R   = conv_df[target_col].values.astype(float)

    coeffs = {}
    for det_val in [1, 2]:
        mask = det == det_val
        if mask.sum() < 5:
            coeffs[det_val] = None
            continue
        coeffs[det_val] = _fit_impulse_group(W[mask], rho[mask], H[mask],
                                             S[mask], R[mask])
    return coeffs


# ============================================================
# Z_urban model: fit & predict
# ============================================================

def _prepare_maxR_data(maxR_df, conv_df):
    """Merge geometry and convergence radii into maxR DataFrame."""
    # Parse geometry from config names
    records = []
    for cfg_name in maxR_df['Config'].unique():
        cfg = config_parser(cfg_name)
        if cfg is None:
            continue
        rho = cfg['bsize'] ** 2 / (cfg['bsize'] + cfg['swidth']) ** 2
        C = 3 - (cfg['height'] / cfg['swidth']) - 3 * rho
        records.append({
            'Config': cfg_name,
            'det': cfg['det'],
            'weight': float(cfg['weight']),
            'bsize': float(cfg['bsize']),
            'swidth': float(cfg['swidth']),
            'height': float(cfg['height']),
            'rho': rho,
            'C': C,
        })
    geo_df = pd.DataFrame(records)

    df = maxR_df.merge(geo_df, on='Config', how='left')
    df['Z_free'] = df['Z'].astype(float)
    df['Z_urban_P'] = df['MaxR_P'] / df['weight'] ** (1/3)
    df['Z_urban_I'] = df['MaxR_I'] / df['weight'] ** (1/3)

    # Merge convergence radii
    conv_cols = conv_df[['ConfigName', 'RadiusP', 'RadiusI']].copy()
    conv_cols = conv_cols.rename(columns={'ConfigName': 'Config'})
    df = df.merge(conv_cols, on='Config', how='left')

    return df


def _fit_z_urban_all_groups(train_df):
    """Fit Z_urban Pi-bracket models per det group × 2 targets.

    Returns dict {(det, target_name): {'m': m, 'D': coef_array} or None}.
    """
    coeffs = {}

    for det_val in [1, 2]:
        # Use det-only grouping (no regime split) for more data per fit
        mask = (train_df['det'] == det_val)

        for target_col, target_name, radius_col in [
            ('Z_urban_P', 'Pressure', 'RadiusP'),
            ('Z_urban_I', 'Impulse', 'RadiusI'),
        ]:
            maxR_col = 'MaxR_P' if target_name == 'Pressure' else 'MaxR_I'
            sub = train_df[mask].dropna(subset=[target_col, radius_col])
            if len(sub) == 0:
                coeffs[(det_val, target_name)] = None
                continue

            valid_mask = ((sub[maxR_col] < sub[radius_col]) &
                          (sub['Z_free'] >= Z_URBAN_ZF_MIN[target_name]))
            sub_valid = sub[valid_mask]

            if len(sub_valid) < 5:
                coeffs[(det_val, target_name)] = None
                continue

            W13 = sub_valid['weight'].values ** (1 / 3)
            coeffs[(det_val, target_name)] = _fit_z_urban_group(
                sub_valid['Z_free'].values, sub_valid[target_col].values,
                sub_valid['rho'].values, sub_valid['height'].values,
                sub_valid['swidth'].values, W13, target_name)

    return coeffs


def _evaluate_z_urban(test_df, z_coeffs, conv_P_coeffs=None, conv_I_coeffs=None):
    """Evaluate Z_urban predictions on test data. Returns (mape_P, mape_I).

    Predictions are clipped to [Z_free, Z_conv] when convergence
    coefficients are supplied (the deployed prediction chain).
    """
    all_actual_P, all_pred_P = [], []
    all_actual_I, all_pred_I = [], []

    for det_val in [1, 2]:
        mask = (test_df['det'] == det_val)

        for target_col, target_name, radius_col in [
            ('Z_urban_P', 'Pressure', 'RadiusP'),
            ('Z_urban_I', 'Impulse', 'RadiusI'),
        ]:
            popt = z_coeffs.get((det_val, target_name))
            if popt is None:
                continue

            maxR_col = 'MaxR_P' if target_name == 'Pressure' else 'MaxR_I'
            sub = test_df[mask].dropna(subset=[target_col, radius_col])
            if len(sub) == 0:
                continue

            valid_mask = ((sub[maxR_col] < sub[radius_col]) &
                          (sub['Z_free'] >= Z_URBAN_ZF_MIN[target_name]))
            sub_valid = sub[valid_mask]
            if len(sub_valid) == 0:
                continue

            y_actual = sub_valid[target_col].values

            W13 = sub_valid['weight'].values ** (1 / 3)
            y_pred = _predict_z_urban(
                sub_valid['Z_free'].values, sub_valid['rho'].values,
                sub_valid['height'].values, sub_valid['swidth'].values,
                W13, target_name, popt)
            y_pred = _clip_z_urban_pred(y_pred, sub_valid, det_val,
                                        target_name, conv_P_coeffs,
                                        conv_I_coeffs)

            if target_name == 'Pressure':
                all_actual_P.append(y_actual)
                all_pred_P.append(y_pred)
            else:
                all_actual_I.append(y_actual)
                all_pred_I.append(y_pred)

    mape_P = np.nan
    mape_I = np.nan
    if all_actual_P:
        a = np.concatenate(all_actual_P)
        p = np.concatenate(all_pred_P)
        _, mape_P = _r2_mape(a, p)
    if all_actual_I:
        a = np.concatenate(all_actual_I)
        p = np.concatenate(all_pred_I)
        _, mape_I = _r2_mape(a, p)

    return mape_P, mape_I


# ============================================================
# Cross-validation orchestrator
# ============================================================

def run_cross_validation(conv_csv, maxR_csv, output_folder,
                         n_iterations=500, test_fraction=0.2,
                         target_mape=10.0):
    """Run repeated 80/20 train/test splits and find best formula coefficients.

    Parameters
    ----------
    conv_csv : str
        Path to convergence_table.csv (with ConfigName, Det columns).
    maxR_csv : str
        Path to max_radius_per_Z.csv.
    output_folder : str
        Directory for output files.
    n_iterations : int
        Number of random splits to try.
    test_fraction : float
        Fraction of configs in test set (default 0.2).
    target_mape : float
        Target maximum MAPE (%) across all models.
    """
    # ---- Load data ----
    conv_df = pd.read_csv(conv_csv)
    maxR_df = pd.read_csv(maxR_csv)

    # Prepare maxR data (merge geometry, convergence radii)
    maxR_prepared = _prepare_maxR_data(maxR_df, conv_df)

    # ---- Compute stratification labels ----
    config_names = conv_df['ConfigName'].values
    det_values   = conv_df['Det'].values.astype(int)

    # Stratify by det only (street / intersection)
    strata = det_values

    n_configs = len(config_names)
    n_test = max(1, int(n_configs * test_fraction))

    print(f'Total configs: {n_configs}')
    print(f'Train/test split: {n_configs - n_test}/{n_test}')
    print(f'Strata distribution:')
    for s_val in np.unique(strata):
        loc_name = 'Street' if s_val == 1 else 'Intersection'
        print(f'  {loc_name}: {(strata == s_val).sum()} configs')
    print()

    # ---- Stratified split generator ----
    # Fixed seed: identical splits every run, so formula changes are directly
    # comparable (any difference in the numbers is real, not split luck).
    sss = StratifiedShuffleSplit(n_splits=n_iterations, test_size=test_fraction,
                                 random_state=42)

    # ---- Track results ----
    best_worst_mape = np.inf
    best_iteration = -1
    best_conv_P_coeffs = None      # additive Pi model
    best_conv_I_coeffs = None      # log-space Pi model
    best_z_coeffs = None
    best_mapes = None
    best_test_idx = None

    cv_rows = []
    n_success = 0

    dummy_X = np.arange(n_configs).reshape(-1, 1)

    for iteration, (train_idx, test_idx) in enumerate(sss.split(dummy_X, strata)):
        train_configs = set(config_names[train_idx])
        test_configs  = set(config_names[test_idx])

        # Split convergence data
        train_conv = conv_df[conv_df['ConfigName'].isin(train_configs)].copy()
        test_conv  = conv_df[conv_df['ConfigName'].isin(test_configs)].copy()

        # Split maxR data
        train_maxR = maxR_prepared[maxR_prepared['Config'].isin(train_configs)].copy()
        test_maxR  = maxR_prepared[maxR_prepared['Config'].isin(test_configs)].copy()

        # ---- Fit convergence radius: P additive Pi, I log-space Pi ----
        conv_P_coeffs = _fit_pi_all_groups(train_conv, 'RadiusP')
        conv_I_coeffs = _fit_impulse_all_groups(train_conv, 'RadiusI')

        # Skip iteration if any det group failed to fit
        if any(c is None for c in conv_P_coeffs.values()):
            continue
        if any(c is None for c in conv_I_coeffs.values()):
            continue

        # Evaluate convergence on test
        test_W   = test_conv['ChargeWeight'].values.astype(float)
        test_H   = test_conv['Height'].values.astype(float)
        test_S   = test_conv['StreetWidth'].values.astype(float)
        test_B   = test_conv['BuildingSize'].values.astype(float)
        test_rho = test_conv['AreaDensity'].values.astype(float)
        test_det = test_conv['Det'].values.astype(int)
        actual_P = test_conv['RadiusP'].values
        actual_I = test_conv['RadiusI'].values

        pred_P = _predict_pi(test_W, test_rho, test_H, test_det, test_S, test_B, conv_P_coeffs)
        pred_I = _predict_impulse(test_W, test_rho, test_H, test_det, test_S, test_B, conv_I_coeffs)

        conv_r2_P, conv_mape_P = _r2_mape(actual_P, pred_P)
        conv_r2_I, conv_mape_I = _r2_mape(actual_I, pred_I)

        # ---- Fit Z_urban ----
        # (R_urban = W^(1/3) * Z_urban identically, so no separate fit —
        #  its relative errors equal Z_urban's row-for-row.)
        # Evaluation clips predictions to [Z_free, Z_conv] using the
        # same-iteration convergence fits — the deployed prediction chain.
        z_coeffs = _fit_z_urban_all_groups(train_maxR)
        z_mape_P, z_mape_I = _evaluate_z_urban(test_maxR, z_coeffs,
                                               conv_P_coeffs, conv_I_coeffs)

        # ---- Collect MAPEs ----
        mapes = {
            'conv_P': conv_mape_P, 'conv_I': conv_mape_I,
            'z_P': z_mape_P, 'z_I': z_mape_I,
        }

        # Worst MAPE across all finite targets
        finite_mapes = [v for v in mapes.values() if np.isfinite(v)]
        if not finite_mapes:
            continue
        worst_mape = max(finite_mapes)

        cv_rows.append({
            'iteration': iteration,
            **mapes,
            'worst': worst_mape,
            'conv_P_r2': conv_r2_P,
            'conv_I_r2': conv_r2_I,
        })

        if worst_mape < target_mape:
            n_success += 1

        if worst_mape < best_worst_mape:
            best_worst_mape = worst_mape
            best_iteration = iteration
            best_conv_P_coeffs = conv_P_coeffs
            best_conv_I_coeffs = conv_I_coeffs
            best_z_coeffs = z_coeffs
            best_mapes = mapes
            best_train_idx = train_idx
            best_test_idx = test_idx

        # Progress
        if (iteration + 1) % 50 == 0 or iteration == 0:
            print(f'  Iter {iteration+1}/{n_iterations}  '
                  f'best worst_mape={best_worst_mape:.1f}%  '
                  f'this={worst_mape:.1f}%  successes={n_success}')

    # ---- Summary ----
    print(f'\n{"="*60}')
    print(f'  CV RESULTS ({n_iterations} iterations)')
    print(f'{"="*60}')
    print(f'Target MAPE: < {target_mape:.0f}%')
    print(f'Iterations meeting target: {n_success}/{n_iterations}')
    print(f'Best iteration: {best_iteration}')
    print(f'Best worst-case MAPE: {best_worst_mape:.2f}%')

    if best_mapes:
        print(f'\nBest iteration MAPEs:')
        for k, v in best_mapes.items():
            print(f'  {k}: {v:.2f}%')

    # ---- Save CV summary ----
    cv_df = pd.DataFrame(cv_rows)
    cv_csv = os.path.join(output_folder, 'cv_summary.csv')
    cv_df.to_csv(cv_csv, index=False)
    print(f'\nSaved: {cv_csv}')

    # ---- Median CV performance per target ----
    med_conv_P = cv_df['conv_P'].median()
    med_conv_I = cv_df['conv_I'].median()
    med_r2_P   = cv_df['conv_P_r2'].median()
    med_r2_I   = cv_df['conv_I_r2'].median()

    print(f'\n{"="*60}')
    print('  CONVERGENCE RADIUS MODELS  (R = W^(1/3) * Z, Hopkinson scaling)')
    print('  RadiusP: Z = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)')
    print('                + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1)')
    print('           a = 1 (street) / 2 (intersection)')
    print('  RadiusI: Z = A * Pi^(k*ln(W^1/3/s)),  Pi = H/(s*rho)')
    print(f'{"="*60}')
    print(f'  Median conv_P MAPE: {med_conv_P:.2f}%  |  R² = {med_r2_P:.3f}')
    print(f'  Median conv_I MAPE: {med_conv_I:.2f}%  |  R² = {med_r2_I:.3f}')

    # ---- Save best test split ----
    if best_test_idx is not None:
        test_config_names = config_names[best_test_idx]
        split_df = pd.DataFrame({'ConfigName': test_config_names})
        split_path = os.path.join(output_folder, 'best_test_configs.csv')
        split_df.to_csv(split_path, index=False)
        print(f'Saved: {split_path}')

    # ---- Save best CV-iteration coefficients ----
    if best_conv_P_coeffs is not None:
        _save_best_convergence_coefficients(best_conv_P_coeffs,
                                            best_conv_I_coeffs, output_folder)

    if best_z_coeffs is not None:
        _save_best_nonlinear_coefficients(
            best_z_coeffs, 'best_z_urban_coefficients.csv', output_folder)

    # ---- Validation plot ----
    if best_conv_P_coeffs is not None:
        _plot_best_validation(conv_df, maxR_prepared,
                              best_conv_P_coeffs, best_conv_I_coeffs,
                              best_z_coeffs,
                              best_train_idx, best_test_idx,
                              config_names, best_mapes, output_folder)

    # ---- Print formulas for the best CV iteration ----
    if best_conv_P_coeffs is not None:
        _print_final_formulas(conv_df, best_conv_P_coeffs, best_conv_I_coeffs)
        _print_z_urban_formulas(best_z_coeffs)

    # ---- Production fit: refit on 100% of data ----
    prod_P_coeffs = _fit_pi_all_groups(conv_df, 'RadiusP')
    prod_I_coeffs = _fit_impulse_all_groups(conv_df, 'RadiusI')
    prod_z_coeffs = _fit_z_urban_all_groups(maxR_prepared)
    print(f'\n{"="*60}')
    print(f'  PRODUCTION FIT  (100% of data)')
    print(f'{"="*60}')
    _save_best_convergence_coefficients(
        prod_P_coeffs, prod_I_coeffs, output_folder,
        filename='final_production_convergence_coefficients.csv')
    _save_best_nonlinear_coefficients(
        prod_z_coeffs, 'final_production_z_urban_coefficients.csv',
        output_folder)
    print('  ^ Use these files for thesis formulas (all configs used for fitting).')


# ============================================================
# Output helpers
# ============================================================

def _save_best_convergence_coefficients(conv_P_coeffs, conv_I_coeffs, output_folder,
                                        filename='best_convergence_coefficients.csv'):
    """Save convergence radius coefficients (both formulas) to CSV.

    Superset schema, one row per (det, target) — 4 rows total:
      Det, Location, Target, Formula,
      C0, C1_sW13, C2_switch, C3_canyon, a_thresh, has_H_term,   (additive, P)
      A, k                                                       (log, I)
    Unused cells are left empty.

    RadiusP (Formula='additive'):
      R = W^(1/3) * (C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                        + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1))
    RadiusI (Formula='log'):
      R = W^(1/3) * A * Pi^(k*ln(W^1/3/s)),  Pi = H/(s*rho)
    """
    loc_names = {1: 'Street', 2: 'Intersection'}

    rows = []
    for det_val, coef in conv_P_coeffs.items():
        if coef is None:
            continue
        rows.append({
            'Det': det_val,
            'Location': loc_names.get(det_val, str(det_val)),
            'Target': 'RadiusP',
            'Formula': 'additive',
            'C0': coef['C0'],
            'C1_sW13': coef['C1'],
            'C2_switch': coef['C2'],
            'C3_canyon': coef['C3'],
            'a_thresh': coef['a'],
            'has_H_term': int(coef['has_H_term']),
            'A': np.nan,
            'k': np.nan,
        })
    for det_val, coef in conv_I_coeffs.items():
        if coef is None:
            continue
        rows.append({
            'Det': det_val,
            'Location': loc_names.get(det_val, str(det_val)),
            'Target': 'RadiusI',
            'Formula': 'log',
            'C0': np.nan,
            'C1_sW13': np.nan,
            'C2_switch': np.nan,
            'C3_canyon': np.nan,
            'a_thresh': np.nan,
            'has_H_term': np.nan,
            'A': coef['A'],
            'k': coef['k'],
        })

    df = pd.DataFrame(rows)
    path = os.path.join(output_folder, filename)
    df.to_csv(path, index=False)
    print(f'Saved: {path}')


def _save_best_nonlinear_coefficients(coeffs_dict, filename, output_folder):
    """Save Z_urban power-law coefficients to CSV.

    Schema (one row per det × target):
      Det, Location, Target, C, m, p_rho, q_HoverS, r_sW13, Zf_min
    Zf_min is the lower validity bound on Z_free (1 pressure, 2 impulse).
    R_urban needs no CSV of its own: R_urban = W^(1/3) * Z_urban.
    """
    loc_names = {1: 'Street', 2: 'Intersection'}

    rows = []
    for (det_val, target_name), coef in coeffs_dict.items():
        if coef is None:
            continue
        rows.append({
            'Det': det_val,
            'Location': loc_names.get(det_val, str(det_val)),
            'Target': target_name,
            'C': coef['C'],
            'm': coef['m'],
            'p_rho': coef['p'],
            'q_HoverS': coef['q'],
            'r_sW13': coef['r'],
            'Zf_min': coef['zf_min'],
        })

    df = pd.DataFrame(rows)
    path = os.path.join(output_folder, filename)
    df.to_csv(path, index=False)
    print(f'Saved: {path}')


def _plot_best_validation(conv_df, maxR_df,
                          conv_P_coeffs, conv_I_coeffs,
                          z_coeffs,
                          train_idx, test_idx,
                          config_names, best_mapes, output_folder):
    """Plot actual vs predicted for the best CV iteration."""
    W   = conv_df['ChargeWeight'].values.astype(float)
    H   = conv_df['Height'].values.astype(float)
    S   = conv_df['StreetWidth'].values.astype(float)
    B   = conv_df['BuildingSize'].values.astype(float)
    rho = conv_df['AreaDensity'].values.astype(float)
    det = conv_df['Det'].values.astype(int)

    pred_P = _predict_pi(W, rho, H, det, S, B, conv_P_coeffs)
    pred_I = _predict_impulse(W, rho, H, det, S, B, conv_I_coeffs)

    actual_P = conv_df['RadiusP'].values
    actual_I = conv_df['RadiusI'].values

    # Color: blue=train, red=test
    colors = np.full(len(conv_df), 'C0')
    colors[test_idx] = 'C3'

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor('white')
    fig.suptitle('Best CV Iteration: Convergence Radius (Train=blue, Test=red)',
                 fontsize=13, fontweight='bold')

    for ax, actual, pred, title, mape_key in [
        (axes[0], actual_P, pred_P, 'Pressure', 'conv_P'),
        (axes[1], actual_I, pred_I, 'Impulse', 'conv_I'),
    ]:
        for idx_set, c, label in [(train_idx, 'C0', 'Train'), (test_idx, 'C3', 'Test')]:
            ax.scatter(actual[idx_set], pred[idx_set], s=50, c=c,
                       edgecolors='k', linewidths=0.5, label=label, alpha=0.7)
        lim = [0, max(actual.max(), np.nanmax(pred)) * 1.1]
        ax.plot(lim, lim, 'k--', linewidth=1.5)
        ax.plot(lim, [v * 1.1 for v in lim], color='gray', linestyle='--', alpha=0.5, label='+/- 10% Error')
        ax.plot(lim, [v * 0.9 for v in lim], color='gray', linestyle='--', alpha=0.5)
        ax.set_xlim(lim); ax.set_ylim(lim)
        ax.set_xlabel('Actual [m]'); ax.set_ylabel('Predicted [m]')
        test_mape = best_mapes[mape_key]
        ax.set_title(f'{title}\nTest MAPE = {test_mape:.1f}%')
        ax.set_aspect('equal'); ax.grid(True, alpha=0.3)
        ax.legend(loc='upper left')

    fig.savefig(os.path.join(output_folder, 'cv_best_convergence.png'),
                dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('Saved: cv_best_convergence.png')

    # ---- Z_urban plot (R_urban = W^(1/3)*Z_urban — same relative errors) ----
    if z_coeffs is not None:
        _plot_nonlinear_validation(maxR_df, z_coeffs,
                                   conv_P_coeffs, conv_I_coeffs,
                                   config_names, train_idx, test_idx,
                                   best_mapes, output_folder)


def _plot_nonlinear_validation(maxR_df, z_coeffs,
                                conv_P_coeffs, conv_I_coeffs,
                                config_names, train_idx, test_idx,
                                best_mapes, output_folder):
    """Plot Z_urban actual vs predicted (clipped to [Z_free, Z_conv])."""
    train_configs = set(config_names[train_idx])
    test_configs  = set(config_names[test_idx])

    for model_name, coeffs, target_cols, mape_keys in [
        ('Z_urban', z_coeffs,
         [('Z_urban_P', 'Pressure', 'RadiusP'), ('Z_urban_I', 'Impulse', 'RadiusI')],
         ('z_P', 'z_I')),
    ]:
        if coeffs is None:
            continue

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.patch.set_facecolor('white')
        fig.suptitle(f'Best CV: {model_name} (Train=blue, Test=red)',
                     fontsize=13, fontweight='bold')

        for ax_idx, (target_col, target_name, radius_col) in enumerate(target_cols):
            ax = axes[ax_idx]
            maxR_col = 'MaxR_P' if target_name == 'Pressure' else 'MaxR_I'

            all_actual_train, all_pred_train = [], []
            all_actual_test, all_pred_test = [], []

            for det_val in [1, 2]:
                popt = coeffs.get((det_val, target_name))
                if popt is None:
                    continue

                mask = (maxR_df['det'] == det_val)

                sub = maxR_df[mask].dropna(subset=[target_col, radius_col])
                if len(sub) == 0:
                    continue

                valid_mask = ((sub[maxR_col] < sub[radius_col]) &
                              (sub['Z_free'] >= Z_URBAN_ZF_MIN[target_name]))
                sub_valid = sub[valid_mask]
                if len(sub_valid) == 0:
                    continue

                y_actual = sub_valid[target_col].values

                W13 = sub_valid['weight'].values ** (1 / 3)
                y_pred = _predict_z_urban(
                    sub_valid['Z_free'].values, sub_valid['rho'].values,
                    sub_valid['height'].values, sub_valid['swidth'].values,
                    W13, target_name, popt)
                y_pred = _clip_z_urban_pred(y_pred, sub_valid, det_val,
                                            target_name, conv_P_coeffs,
                                            conv_I_coeffs)

                is_train = sub_valid['Config'].isin(train_configs)
                is_test  = sub_valid['Config'].isin(test_configs)

                if is_train.any():
                    all_actual_train.append(y_actual[is_train.values])
                    all_pred_train.append(y_pred[is_train.values])
                if is_test.any():
                    all_actual_test.append(y_actual[is_test.values])
                    all_pred_test.append(y_pred[is_test.values])

            # Plot
            if all_actual_train:
                at = np.concatenate(all_actual_train)
                pt = np.concatenate(all_pred_train)
                ax.scatter(at, pt, s=30, c='C0', alpha=0.5, edgecolors='k',
                           linewidths=0.3, label='Train')
            if all_actual_test:
                at = np.concatenate(all_actual_test)
                pt = np.concatenate(all_pred_test)
                ax.scatter(at, pt, s=50, c='C3', alpha=0.8, edgecolors='k',
                           linewidths=0.5, label='Test')

            all_vals = []
            for lst in [all_actual_train, all_pred_train, all_actual_test, all_pred_test]:
                if lst:
                    all_vals.append(np.concatenate(lst))
            if all_vals:
                combined = np.concatenate(all_vals)
                lim = [0, np.nanmax(combined) * 1.1]
            else:
                lim = [0, 1]

            ax.plot(lim, lim, 'k--', linewidth=1.5)
            ax.plot(lim, [v * 1.1 for v in lim], color='gray', linestyle='--', alpha=0.5, label='+/- 10% Error')
            ax.plot(lim, [v * 0.9 for v in lim], color='gray', linestyle='--', alpha=0.5)
            ax.set_xlim(lim); ax.set_ylim(lim)
            mape_key = mape_keys[ax_idx]
            test_mape = best_mapes.get(mape_key, np.nan)
            unit = 'm/kg^(1/3)' if model_name == 'Z_urban' else 'm'
            ax.set_xlabel(f'Actual [{unit}]'); ax.set_ylabel(f'Predicted [{unit}]')
            ax.set_title(f'{target_name}\nTest MAPE = {test_mape:.1f}%')
            ax.set_aspect('equal'); ax.grid(True, alpha=0.3)
            ax.legend(loc='upper left')

        fname = f'cv_best_{model_name.lower()}.png'
        fig.savefig(os.path.join(output_folder, fname), dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f'Saved: {fname}')


def _print_final_formulas(conv_df, conv_P_coeffs, conv_I_coeffs):
    """Print the best convergence radius formulas (both targets).

    Both share the canonical structure R = W^(1/3) * Z; only the Z
    expression differs (additive Pi for pressure, log Pi for impulse).
    """
    loc_names = {1: 'Street (det=1)', 2: 'Intersection (det=2)'}

    print(f'\n{"="*70}')
    print('  BEST CONVERGENCE RADIUS FORMULAS    R = W^(1/3) * Z')
    print(f'{"="*70}')
    print('  RadiusP (Buckingham Pi additive model):')
    print('    Z = C0 + C1*(s/W^(1/3)) + C2*rho*(s/W^(1/3) - a)')
    print('           + C3*sqrt(rho)*(H/s)*(W^(1/3)/s - 1)')
    print('    a = 1 (street) / 2 (intersection): density-switch threshold')
    print('    Canyon law: H/s effect flips sign at s = W^(1/3) (channeling <-> blocking)')
    print('    sqrt(rho) = b/(b+s) = canyon wall continuity (cross-street gaps leak)')
    print('  RadiusI (log-space Pi model):')
    print('    Z = A * Pi^(k*ln(W^(1/3)/s)),  Pi = H/(s*rho)')
    print('    A ~ scaled distance where free-field pressure decays to ~9 kPa;')
    print('    exponent flips sign at s = W^(1/3): confinement extends R for')
    print('    large charges, shortens it for small ones')
    print('  where rho = b^2/(b+s)^2, W^(1/3) is the Hopkinson length scale')
    print(f'{"="*70}')

    print(f'\n--- RadiusP ---')
    for det_val in sorted(conv_P_coeffs.keys()):
        coef = conv_P_coeffs[det_val]
        if coef is None:
            continue
        C0, C1 = coef['C0'], coef['C1']
        C2, C3 = coef['C2'], coef['C3']
        a      = coef['a']
        has_H = coef['has_H_term']
        loc   = loc_names.get(det_val, f'det={det_val}')
        print(f'  {loc}:')
        if has_H:
            print(f'    Z = {C0:+.4f} + {C1:+.4f}*(s/W^1/3)'
                  f' + {C2:+.4f}*rho*(s/W^1/3 - {a:g})'
                  f' + {C3:+.4f}*sqrt(rho)*(H/s)*(W^1/3/s - 1)')
        else:
            print(f'    Z = {C0:+.4f} + {C1:+.4f}*(s/W^1/3)'
                  f' + {C2:+.4f}*rho*(s/W^1/3 - {a:g})  [H=0, canyon term omitted]')
        print(f'    R = W^(1/3) * Z')

    print(f'\n--- RadiusI ---')
    for det_val in sorted(conv_I_coeffs.keys()):
        coef = conv_I_coeffs[det_val]
        if coef is None:
            continue
        loc = loc_names.get(det_val, f'det={det_val}')
        print(f'  {loc}:')
        print(f'    Z = {coef["A"]:.4f} * Pi^({coef["k"]:+.4f}*ln(W^1/3/s))')
        print(f'    R = W^(1/3) * Z')
    print()


def _print_z_urban_formulas(z_coeffs):
    """Print the best Z_urban formulas (canonical: MaxR = W^(1/3) * Z_urban)."""
    if z_coeffs is None:
        return
    loc_names = {1: 'Street (det=1)', 2: 'Intersection (det=2)'}

    print(f'{"="*70}')
    print('  BEST Z_URBAN FORMULAS    MaxR = W^(1/3) * Z_urban')
    print(f'{"="*70}')
    print('  Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r')
    print('  All factors are Pi groups; W enters only through W^(1/3).')
    print('  R_urban = W^(1/3) * Z_urban  (canonical — not separately fitted)')
    print('  Validity: Z_free >= Zf_min (1 pressure, 2 impulse — at Z_free=1')
    print('  the point is inside the first street; impulse mapping invalid)')
    print('  Physical closure: predictions clipped to Z_free <= Z_urban <= Z_conv')
    print('  (Z_conv from the convergence formulas); identity beyond Z_conv.')
    print(f'{"="*70}')

    for target_name in ['Pressure', 'Impulse']:
        print(f'\n--- Z_urban {target_name} ---')
        for det_val in [1, 2]:
            coef = z_coeffs.get((det_val, target_name))
            if coef is None:
                continue
            loc = loc_names.get(det_val, f'det={det_val}')
            print(f'  {loc}:')
            print(f'    Z_urban = {coef["C"]:.4f} * Z_free^{coef["m"]:.4f}'
                  f' * rho^{coef["p"]:+.4f} * (H/s)^{coef["q"]:+.4f}'
                  f' * (s/W^1/3)^{coef["r"]:+.4f}')
            print(f'    MaxR = W^(1/3) * Z_urban    [Z_free >= {coef["zf_min"]:g}]')
    print()
