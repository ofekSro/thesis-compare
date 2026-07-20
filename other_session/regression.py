"""Cross-validated regression for convergence radius, Z_urban, and R_urban.

Runs repeated random 80/20 train/test splits on the unified config pool,
fits the same formula structures as compare_v2 (Improved convergence model,
Z_urban and R_urban non-linear models), and selects the best coefficients
based on test-set MAPE.
"""

import os
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
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
# Non-linear model functions (same as compare_v2)
# ============================================================

def _z_urban_model_pressure(X, m, a, b, c, d):
    """Z_urban = Z_free^m * (a + b*rho + c*H + d*rho*H)."""
    Z_free, rho, H = X
    return Z_free ** m * (a + b * rho + c * H + d * rho * H)


def _z_urban_model_impulse(X, m, n, a, b, c, d):
    """Z_urban = Z_free^m * W^n * (a + b*rho + c*H + d*rho*H)."""
    Z_free, W, rho, H = X
    return Z_free ** m * W ** n * (a + b * rho + c * H + d * rho * H)


def _r_urban_model(X, m, n, a, b, c, d):
    """R_urban = Z_free^m * W^n * (a + b*rho + c*H + d*rho*H)."""
    Z_free, W, rho, H = X
    return (Z_free ** m) * (W ** n) * (a + b * rho + c * H + d * rho * H)


# ============================================================
# Convergence radius: Buckingham Pi additive model
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


def _fit_pi_all_groups(conv_df, target_col, free_W_exp=False):
    """Fit additive Pi model for det=1 and det=2 groups.

    free_W_exp is kept for API compatibility but ignored — the additive
    formulation already handles W scaling through the Pi groups.

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


def _best_curve_fit(model_func, X_data, y_data, p0_list, maxfev=50000):
    """Try multiple initial guesses, return best (lowest MAPE) popt or None."""
    best_popt = None
    best_mape = np.inf

    for p0 in p0_list:
        try:
            popt, _ = curve_fit(model_func, X_data, y_data, p0=p0, maxfev=maxfev)
            y_pred = model_func(X_data, *popt)
            _, mape = _r2_mape(y_data, y_pred)
            if np.isfinite(mape) and mape < best_mape:
                best_mape = mape
                best_popt = popt
        except Exception:
            pass

    return best_popt


def _fit_z_urban_all_groups(train_df):
    """Fit Z_urban models for all 4 groups × 2 targets.

    Returns dict {(det, regime_idx, target_name): popt_array} or None if failed.
    """
    coeffs = {}

    # Multiple initial guesses to avoid local minima
    p0_pressure_list = [
        [1.0, 1.7, -0.3, -0.02, 0.05],
        [0.8, 2.0, -1.0, -0.05, 0.1],
        [1.2, 1.0, 0.5, -0.01, 0.02],
        [0.5, 3.0, -2.0, -0.1, 0.2],
    ]
    p0_impulse_list = [
        [1.0, 0.0, 1.7, -0.3, -0.02, 0.05],
        [0.8, -0.05, 2.0, -1.0, -0.05, 0.1],
        [1.2, 0.05, 1.0, 0.5, -0.01, 0.02],
        [0.5, -0.1, 3.0, -2.0, -0.1, 0.2],
    ]

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

            valid_mask = sub[maxR_col] < sub[radius_col]
            sub_valid = sub[valid_mask]

            if len(sub_valid) < 5:
                coeffs[(det_val, target_name)] = None
                continue

            y_data = sub_valid[target_col].values

            if target_name == 'Pressure':
                X_data = np.array([sub_valid['Z_free'].values,
                                   sub_valid['rho'].values,
                                   sub_valid['height'].values])
                popt = _best_curve_fit(_z_urban_model_pressure, X_data,
                                       y_data, p0_pressure_list)
            else:
                X_data = np.array([sub_valid['Z_free'].values,
                                   sub_valid['weight'].values,
                                   sub_valid['rho'].values,
                                   sub_valid['height'].values])
                popt = _best_curve_fit(_z_urban_model_impulse, X_data,
                                       y_data, p0_impulse_list)

            coeffs[(det_val, target_name)] = popt

    return coeffs


def _evaluate_z_urban(test_df, z_coeffs):
    """Evaluate Z_urban predictions on test data. Returns (mape_P, mape_I)."""
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

            valid_mask = sub[maxR_col] < sub[radius_col]
            sub_valid = sub[valid_mask]
            if len(sub_valid) == 0:
                continue

            y_actual = sub_valid[target_col].values

            if target_name == 'Pressure':
                X_data = np.array([sub_valid['Z_free'].values,
                                   sub_valid['rho'].values,
                                   sub_valid['height'].values])
                y_pred = _z_urban_model_pressure(X_data, *popt)
            else:
                X_data = np.array([sub_valid['Z_free'].values,
                                   sub_valid['weight'].values,
                                   sub_valid['rho'].values,
                                   sub_valid['height'].values])
                y_pred = _z_urban_model_impulse(X_data, *popt)

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
# R_urban model: fit & predict
# ============================================================

def _fit_r_urban_all_groups(train_df):
    """Fit R_urban models for all 4 groups × 2 targets.

    Returns dict {(det, regime_idx, target_name): popt_array} or None.
    """
    p0_list = [
        [1.0, 0.33, 1.7, -0.3, -0.02, 0.05],
        [0.8, 0.40, 2.0, -1.0, -0.05, 0.1],
        [1.2, 0.25, 1.0, 0.5, -0.01, 0.02],
        [0.5, 0.33, 3.0, -2.0, -0.1, 0.2],
    ]

    coeffs = {}

    for det_val in [1, 2]:
        mask = (train_df['det'] == det_val)

        for target_col, target_name, radius_col in [
            ('MaxR_P', 'Pressure', 'RadiusP'),
            ('MaxR_I', 'Impulse', 'RadiusI'),
        ]:
            sub = train_df[mask].dropna(subset=[target_col, radius_col])
            if len(sub) == 0:
                coeffs[(det_val, target_name)] = None
                continue

            valid_mask = sub[target_col] < sub[radius_col]
            sub_valid = sub[valid_mask]

            if len(sub_valid) < 6:
                coeffs[(det_val, target_name)] = None
                continue

            y_data = sub_valid[target_col].values
            X_data = np.array([sub_valid['Z_free'].values,
                               sub_valid['weight'].values,
                               sub_valid['rho'].values,
                               sub_valid['height'].values])

            popt = _best_curve_fit(_r_urban_model, X_data, y_data, p0_list)
            coeffs[(det_val, target_name)] = popt

    return coeffs


def _evaluate_r_urban(test_df, r_coeffs):
    """Evaluate R_urban predictions on test data. Returns (mape_P, mape_I)."""
    all_actual_P, all_pred_P = [], []
    all_actual_I, all_pred_I = [], []

    for det_val in [1, 2]:
        mask = (test_df['det'] == det_val)

        for target_col, target_name, radius_col in [
            ('MaxR_P', 'Pressure', 'RadiusP'),
            ('MaxR_I', 'Impulse', 'RadiusI'),
        ]:
            popt = r_coeffs.get((det_val, target_name))
            if popt is None:
                continue

            sub = test_df[mask].dropna(subset=[target_col, radius_col])
            if len(sub) == 0:
                continue

            valid_mask = sub[target_col] < sub[radius_col]
            sub_valid = sub[valid_mask]
            if len(sub_valid) == 0:
                continue

            y_actual = sub_valid[target_col].values
            X_data = np.array([sub_valid['Z_free'].values,
                               sub_valid['weight'].values,
                               sub_valid['rho'].values,
                               sub_valid['height'].values])
            y_pred = _r_urban_model(X_data, *popt)

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
    H_values     = conv_df['Height'].values.astype(float)
    S_values     = conv_df['StreetWidth'].values.astype(float)
    rho_values   = conv_df['AreaDensity'].values.astype(float)
    C_values     = 3 - (H_values / S_values) - 3 * rho_values
    regime_values = (C_values >= 0).astype(int)

    # Stratify by det × regime
    strata = det_values * 10 + regime_values  # e.g. 10, 11, 20, 21

    n_configs = len(config_names)
    n_test = max(1, int(n_configs * test_fraction))

    print(f'Total configs: {n_configs}')
    print(f'Train/test split: {n_configs - n_test}/{n_test}')
    print(f'Strata distribution:')
    for s_val in np.unique(strata):
        loc_name = 'Street' if s_val < 20 else 'Intersection'
        reg_name = 'Channeling' if s_val % 10 == 1 else 'Blocking'
        print(f'  {loc_name} + {reg_name}: {(strata == s_val).sum()} configs')
    print()

    # ---- Stratified split generator ----
    # Fixed seed: identical splits every run, so formula changes are directly
    # comparable (any difference in the numbers is real, not split luck).
    sss = StratifiedShuffleSplit(n_splits=n_iterations, test_size=test_fraction,
                                 random_state=42)

    # ---- Track results ----
    best_worst_mape = np.inf
    best_iteration = -1
    best_conv_P_coeffs = None      # fixed W^(1/3)
    best_conv_I_coeffs = None
    best_conv_P_free_coeffs = None  # free W exponent
    best_conv_I_free_coeffs = None
    best_z_coeffs = None
    best_r_coeffs = None
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

        # ---- Fit convergence radius — Pi model (fixed W^(1/3)) ----
        conv_P_coeffs = _fit_pi_all_groups(train_conv, 'RadiusP', free_W_exp=False)
        conv_I_coeffs = _fit_pi_all_groups(train_conv, 'RadiusI', free_W_exp=False)

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
        pred_I = _predict_pi(test_W, test_rho, test_H, test_det, test_S, test_B, conv_I_coeffs)

        conv_r2_P, conv_mape_P = _r2_mape(actual_P, pred_P)
        conv_r2_I, conv_mape_I = _r2_mape(actual_I, pred_I)

        # ---- Fit convergence radius — Pi model (free W exponent) ----
        conv_P_free_coeffs = _fit_pi_all_groups(train_conv, 'RadiusP', free_W_exp=True)
        conv_I_free_coeffs = _fit_pi_all_groups(train_conv, 'RadiusI', free_W_exp=True)

        pred_P_free = _predict_pi(test_W, test_rho, test_H, test_det, test_S, test_B, conv_P_free_coeffs)
        pred_I_free = _predict_pi(test_W, test_rho, test_H, test_det, test_S, test_B, conv_I_free_coeffs)

        conv_r2_P_free, conv_mape_P_free = _r2_mape(actual_P, pred_P_free)
        conv_r2_I_free, conv_mape_I_free = _r2_mape(actual_I, pred_I_free)

        # ---- Fit Z_urban ----
        z_coeffs = _fit_z_urban_all_groups(train_maxR)
        z_mape_P, z_mape_I = _evaluate_z_urban(test_maxR, z_coeffs)

        # ---- Fit R_urban ----
        r_coeffs = _fit_r_urban_all_groups(train_maxR)
        r_mape_P, r_mape_I = _evaluate_r_urban(test_maxR, r_coeffs)

        # ---- Collect MAPEs ----
        mapes = {
            'conv_P': conv_mape_P, 'conv_I': conv_mape_I,
            'conv_P_free': conv_mape_P_free, 'conv_I_free': conv_mape_I_free,
            'z_P': z_mape_P, 'z_I': z_mape_I,
            'r_P': r_mape_P, 'r_I': r_mape_I,
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
            'conv_P_free_r2': conv_r2_P_free,
            'conv_I_free_r2': conv_r2_I_free,
        })

        if worst_mape < target_mape:
            n_success += 1

        if worst_mape < best_worst_mape:
            best_worst_mape = worst_mape
            best_iteration = iteration
            best_conv_P_coeffs = conv_P_coeffs
            best_conv_I_coeffs = conv_I_coeffs
            best_conv_P_free_coeffs = conv_P_free_coeffs
            best_conv_I_free_coeffs = conv_I_free_coeffs
            best_z_coeffs = z_coeffs
            best_r_coeffs = r_coeffs
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

    # ---- Fixed W^(1/3) vs Free W exponent comparison (median across iterations) ----
    FIXED_W_THRESHOLD = 2.0  # percentage points
    med_conv_P_fixed = cv_df['conv_P'].median()
    med_conv_I_fixed = cv_df['conv_I'].median()
    med_conv_P_free  = cv_df['conv_P_free'].median()
    med_conv_I_free  = cv_df['conv_I_free'].median()
    med_r2_P_fixed   = cv_df['conv_P_r2'].median()
    med_r2_I_fixed   = cv_df['conv_I_r2'].median()
    med_r2_P_free    = cv_df['conv_P_free_r2'].median()
    med_r2_I_free    = cv_df['conv_I_free_r2'].median()

    print(f'\n{"="*60}')
    print('  CONVERGENCE RADIUS MODEL  (additive Pi groups, Hopkinson scaling)')
    print('  Z = R/W^(1/3) = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)')
    print('                     + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1)')
    print('  a = 1 (street) / 2 (intersection)')
    print(f'{"="*60}')
    print(f'  Median conv_P MAPE: {med_conv_P_fixed:.2f}%  |  R² = {med_r2_P_fixed:.3f}')
    print(f'  Median conv_I MAPE: {med_conv_I_fixed:.2f}%  |  R² = {med_r2_I_fixed:.3f}')

    # Always use the fixed (Hopkinson) model — free W exp is not applicable to additive form
    use_fixed = True
    print('\n  -> Additive Pi model uses W^(1/3) scaling by construction.')

    # ---- Save best test split ----
    if best_test_idx is not None:
        test_config_names = config_names[best_test_idx]
        split_df = pd.DataFrame({'ConfigName': test_config_names})
        split_path = os.path.join(output_folder, 'best_test_configs.csv')
        split_df.to_csv(split_path, index=False)
        print(f'Saved: {split_path}')

    # ---- Save best CV-iteration coefficients ----
    if best_conv_P_coeffs is not None:
        save_P = best_conv_P_coeffs if use_fixed else best_conv_P_free_coeffs
        save_I = best_conv_I_coeffs if use_fixed else best_conv_I_free_coeffs
        _save_best_convergence_coefficients(save_P, save_I, output_folder)

    if best_z_coeffs is not None:
        _save_best_nonlinear_coefficients(
            best_z_coeffs, 'best_z_urban_coefficients.csv', output_folder)

    if best_r_coeffs is not None:
        _save_best_nonlinear_coefficients(
            best_r_coeffs, 'best_r_urban_coefficients.csv', output_folder)

    # ---- Validation plot ----
    if best_conv_P_coeffs is not None:
        _plot_best_validation(conv_df, maxR_prepared,
                              best_conv_P_coeffs if use_fixed else best_conv_P_free_coeffs,
                              best_conv_I_coeffs if use_fixed else best_conv_I_free_coeffs,
                              best_z_coeffs, best_r_coeffs,
                              best_train_idx, best_test_idx,
                              config_names, best_mapes, output_folder)

    # ---- Print formulas for the best CV iteration ----
    if best_conv_P_coeffs is not None:
        show_P = best_conv_P_coeffs if use_fixed else best_conv_P_free_coeffs
        show_I = best_conv_I_coeffs if use_fixed else best_conv_I_free_coeffs
        _print_final_formulas(conv_df, show_P, show_I)

    # ---- Production fit: refit winning model on 100% of data ----
    free_flag = not use_fixed
    prod_P_coeffs = _fit_pi_all_groups(conv_df, 'RadiusP', free_W_exp=free_flag)
    prod_I_coeffs = _fit_pi_all_groups(conv_df, 'RadiusI', free_W_exp=free_flag)
    w_label = 'free W exp' if free_flag else 'fixed W^(1/3)'
    print(f'\n{"="*60}')
    print(f'  PRODUCTION FIT  ({w_label}, 100% of data)')
    print(f'{"="*60}')
    _save_best_convergence_coefficients(
        prod_P_coeffs, prod_I_coeffs, output_folder,
        filename='final_production_convergence_coefficients.csv')
    print('  ^ Use this file for thesis formulas (all configs used for fitting).')


# ============================================================
# Output helpers
# ============================================================

def _save_best_convergence_coefficients(conv_P_coeffs, conv_I_coeffs, output_folder,
                                        filename='best_convergence_coefficients.csv'):
    """Save additive Pi convergence radius coefficients to CSV.

    Columns: Det, Location, Target, C0, C1_sW13, C2_switch, C3_canyon,
             a_thresh, has_H_term
    One row per (det, target) combination (2 groups × 2 targets = 4 rows).

    Formula: R = W^(1/3) * (C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                                + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1))
    """
    loc_names = {1: 'Street', 2: 'Intersection'}

    rows = []
    for target_name, coeffs in [('RadiusP', conv_P_coeffs), ('RadiusI', conv_I_coeffs)]:
        for det_val, coef in coeffs.items():
            if coef is None:
                continue
            rows.append({
                'Det': det_val,
                'Location': loc_names.get(det_val, str(det_val)),
                'Target': target_name,
                'C0': coef['C0'],
                'C1_sW13': coef['C1'],
                'C2_switch': coef['C2'],
                'C3_canyon': coef['C3'],
                'a_thresh': coef['a'],
                'has_H_term': int(coef['has_H_term']),
            })

    df = pd.DataFrame(rows)
    path = os.path.join(output_folder, filename)
    df.to_csv(path, index=False)
    print(f'Saved: {path}')


def _save_best_nonlinear_coefficients(coeffs_dict, filename, output_folder):
    """Save Z_urban or R_urban coefficients to CSV."""
    loc_names = {1: 'Street', 2: 'Intersection'}
    regime_names = {0: 'Blocking', 1: 'Channeling'}

    rows = []
    for key, popt in coeffs_dict.items():
        if popt is None:
            continue
        # Support both (det, target) and (det, regime, target) keys
        if len(key) == 2:
            det_val, target_name = key
            regime_label = 'All'
        else:
            det_val, regime_idx, target_name = key
            regime_label = regime_names[regime_idx]
        row = {
            'Det': det_val,
            'Location': loc_names.get(det_val, str(det_val)),
            'Regime': regime_label,
            'Target': target_name,
        }
        if target_name == 'Pressure' and len(popt) == 5:
            m, a, b, c, d = popt
            row.update({'m': m, 'n': np.nan, 'a': a, 'b': b, 'c': c, 'd': d})
        else:
            m, n, a, b, c, d = popt
            row.update({'m': m, 'n': n, 'a': a, 'b': b, 'c': c, 'd': d})
        rows.append(row)

    df = pd.DataFrame(rows)
    path = os.path.join(output_folder, filename)
    df.to_csv(path, index=False)
    print(f'Saved: {path}')


def _plot_best_validation(conv_df, maxR_df,
                          conv_P_coeffs, conv_I_coeffs,
                          z_coeffs, r_coeffs,
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
    pred_I = _predict_pi(W, rho, H, det, S, B, conv_I_coeffs)

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

    # ---- Z_urban and R_urban plots ----
    if z_coeffs is not None:
        _plot_nonlinear_validation(maxR_df, z_coeffs, r_coeffs,
                                   config_names, train_idx, test_idx,
                                   best_mapes, output_folder)


def _plot_nonlinear_validation(maxR_df, z_coeffs, r_coeffs,
                                config_names, train_idx, test_idx,
                                best_mapes, output_folder):
    """Plot Z_urban and R_urban actual vs predicted."""
    train_configs = set(config_names[train_idx])
    test_configs  = set(config_names[test_idx])

    for model_name, coeffs, target_cols, model_func_p, model_func_i, mape_keys in [
        ('Z_urban', z_coeffs,
         [('Z_urban_P', 'Pressure', 'RadiusP'), ('Z_urban_I', 'Impulse', 'RadiusI')],
         _z_urban_model_pressure, _z_urban_model_impulse,
         ('z_P', 'z_I')),
        ('R_urban', r_coeffs,
         [('MaxR_P', 'Pressure', 'RadiusP'), ('MaxR_I', 'Impulse', 'RadiusI')],
         _r_urban_model, _r_urban_model,
         ('r_P', 'r_I')),
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

                valid_mask = sub[maxR_col] < sub[radius_col]
                sub_valid = sub[valid_mask]
                if len(sub_valid) == 0:
                    continue

                y_actual = sub_valid[target_col].values

                if model_name == 'Z_urban' and target_name == 'Pressure':
                    X_data = np.array([sub_valid['Z_free'].values,
                                       sub_valid['rho'].values,
                                       sub_valid['height'].values])
                    y_pred = model_func_p(X_data, *popt)
                else:
                    X_data = np.array([sub_valid['Z_free'].values,
                                       sub_valid['weight'].values,
                                       sub_valid['rho'].values,
                                       sub_valid['height'].values])
                    y_pred = model_func_i(X_data, *popt)

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
    """Print the best additive Pi convergence radius formulas."""
    loc_names = {1: 'Street (det=1)', 2: 'Intersection (det=2)'}

    print(f'\n{"="*70}')
    print('  BEST CONVERGENCE RADIUS FORMULAS  (Buckingham Pi additive model)')
    print('  Z = R/W^(1/3) = C0 + C1*(s/W^(1/3)) + C2*rho*(s/W^(1/3) - a)')
    print('                     + C3*sqrt(rho)*(H/s)*(W^(1/3)/s - 1)')
    print('  a = 1 (street) / 2 (intersection): density-switch threshold')
    print('  where rho = b^2/(b+s)^2, W^(1/3) is Hopkinson length scale')
    print('  Canyon law: H/s effect flips sign at s = W^(1/3) (channeling <-> blocking)')
    print('  sqrt(rho) = b/(b+s) = canyon wall continuity (cross-street gaps leak)')
    print(f'{"="*70}')

    for target_name, coeffs in [('RadiusP', conv_P_coeffs), ('RadiusI', conv_I_coeffs)]:
        print(f'\n--- {target_name} ---')
        for det_val in sorted(coeffs.keys()):
            coef = coeffs[det_val]
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
                print(f'    R = W^(1/3) * Z')
            else:
                print(f'    Z = {C0:+.4f} + {C1:+.4f}*(s/W^1/3)'
                      f' + {C2:+.4f}*rho*(s/W^1/3 - {a:g})  [H=0, canyon term omitted]')
                print(f'    R = W^(1/3) * Z')
    print()
