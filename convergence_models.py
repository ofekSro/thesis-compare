"""Convergence-radius models (RadiusP additive Pi, RadiusI log-space Pi)."""

import numpy as np

from stats_utils import _lstsq


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
