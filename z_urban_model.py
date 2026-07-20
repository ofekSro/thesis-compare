"""Z_urban model (Buckingham Pi power law) — fit, predict, clip, evaluate."""

import numpy as np
import pandas as pd

from config_parser import config_parser
from stats_utils import _lstsq, _r2_mape
from convergence_models import _predict_pi, _predict_impulse


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
# Validity domain: fitted/applied for Z_free >= 2 only (at Z_free = 1 the
# point lies within one Hopkinson length of the charge — inside the first
# street — where the discrete near-field geometry dominates), and for the
# AMPLIFICATION regime only (actual Z_urban > Z_free). Rows with
# Z_urban <= Z_free are the attenuation regime — small charges at
# intersections where venting makes the urban impulse WEAKER than
# free-field — a different physics the power law cannot represent
# (12 rows total, all W=50 det2 / W=250 near-field).
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

Z_URBAN_ZF_MIN = {'Pressure': 2.0, 'Impulse': 2.0}


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
                          (sub['Z_free'] >= Z_URBAN_ZF_MIN[target_name]) &
                          (sub[target_col] > sub['Z_free']))
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
                          (sub['Z_free'] >= Z_URBAN_ZF_MIN[target_name]) &
                          (sub[target_col] > sub['Z_free']))
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
