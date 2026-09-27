"""Convergence-radius models (RadiusP additive Pi, RadiusI Pi power law)."""

import numpy as np

from blastlib.regression.stats import lstsq


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
#   RadiusI — Pi power law (4 coefficients per det):
#       Z = A * rho^p * (H/s)^q * (s/W^(1/3))^r
#     Each Pi group carries its own exponent, so the geometry effects are
#     separable rather than entangled in a single product Pi = H/(s*rho)
#     with a charge-dependent exponent.
#
# ============================================================
# RadiusP: Buckingham Pi additive model
#
# Target (Hopkinson-scaled convergence radius):
#   Z = R / W^(1/3)
#
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


def _fit_pi_group(W, rho, H, s, R_target, a_thresh, weighting='ols'):
    """Fit additive Pi model for one det group via least squares.

    Formula: Z = C0 + C1*(s/W^1/3) + C2*rho*(s/W^1/3 - a)
                    + C3*sqrt(rho)*(H/s)*(W^1/3/s - 1)
    where Z = R / W^(1/3) and a = a_thresh (1 street, 2 intersection).

    weighting:
      'ols'      — plain OLS on Z (minimizes squared absolute error).
      'relative' — rows weighted 1/Z on both sides, i.e. minimizes squared
                   RELATIVE error. Identical design matrix; MAPE is the
                   selection metric everywhere downstream, so the loss and
                   the metric agree.

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
    else:
        # H=0: canyon=0, so only C0, C1, C2 are identifiable
        X = np.column_stack([np.ones(len(W)), pi2, switch])

    if weighting == 'relative':
        # X/Z * c = 1  <=>  minimize sum(((Xc - Z)/Z)^2)
        coef = lstsq(X / Z[:, None], np.ones_like(Z))
    else:
        coef = lstsq(X, Z)

    if has_H:
        C0, C1, C2, C3 = coef
    else:
        C0, C1, C2 = coef
        C3 = 0.0

    return {'C0': C0, 'C1': C1, 'C2': C2, 'C3': C3, 'a': a_thresh,
            'has_H_term': has_H}


def predict_pi(W, rho, H, det, s, b, pi_coeffs):
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


def fit_pi_all_groups(conv_df, target_col, weighting='ols'):
    """Fit additive Pi model for det=1 and det=2 groups.

    weighting: 'ols' (legacy) or 'relative' — see _fit_pi_group.
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
                             a_thresh=A_THRESH[det_val], weighting=weighting)
        coeffs[det_val] = coef
    return coeffs


# ============================================================
# RadiusI: Pi power law
#
#   Z = R / W^(1/3) = A * rho^p * (H/s)^q * (s/W^(1/3))^r          (legacy)
#   Z = ... * exp(r2 * ln(s/W^(1/3))^2)                            ('quad')
#
# Log-linear:
#   ln(Z) = ln(A) + p*ln(rho) + q*ln(H/s) + r*ln(Pi2) [+ r2*ln(Pi2)^2]
# so each det group is a 4- (or 5-) coefficient OLS in log space with
# Pi2 = s/W^(1/3). Every factor is a dimensionless Pi group and W enters
# only through W^(1/3), so the form is Hopkinson-consistent. The log form
# also cannot predict a negative radius.
# ============================================================

def _fit_impulse_group(W, rho, H, s, R_target, model='legacy'):
    """Fit the RadiusI model for one det group via log-space OLS.

    model='unified' (production since 2026-09-27, on the raw-mask store):
        Z = A * Pi2^(C4 + C5*ln(rho) + C3*ln(H/s))
              * exp(C1*rho*sqrt(H/s) + C2*ln(H/s)^2)
    One functional form for both det groups, coefficients per group. The
    separable power law fails structurally on the sentinel-free data: the
    height effect saturates (ln^2 term) and couples to the scaled street
    width (C3), and the trapping factor rho*sqrt(H/s) — the same construct
    as the Z_urban canyon_trap model — carries the density dependence.
    Selected by leave-one-geometry-out comparison under the constraint of
    one shared term set; every coefficient significant in both groups.
    See docs/audit/2026-09-27 (D2 follow-up) and ALGORITHM.md.

    model='quad' / 'legacy' (history): the Pi power law
        Z = A * rho^p * (H/s)^q * Pi2^r * exp(r2*ln(Pi2)^2)
    with r2 fitted ('quad') or fixed to 0 ('legacy'). Kept so historical
    tables and studies can be reproduced; not fitted in production.

    Z = R/W^(1/3), Pi2 = s/W^(1/3).
    Returns a dict predict_impulse dispatches on ('C1'.. keys for unified,
    'p'/'q'/'r' for the power law). None if fewer than 6 samples.
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
    ln_pi2 = np.log(s / W13)
    if model == 'unified':
        ln_hs = np.log(H / s)
        X = np.column_stack([np.ones(len(W)),
                             rho * np.sqrt(H / s),     # C1: canyon trapping
                             ln_hs ** 2,               # C2: height saturation
                             ln_hs * ln_pi2,           # C3: depth-width coupling
                             ln_pi2,                   # C4: street-width base
                             np.log(rho) * ln_pi2])    # C5: density-width coupling
        c0, C1, C2, C3, C4, C5 = lstsq(X, lnZ)
        return {'A': np.exp(c0), 'C1': C1, 'C2': C2, 'C3': C3,
                'C4': C4, 'C5': C5}
    if model == 'quad':
        X = np.column_stack([np.ones(len(W)), np.log(rho), np.log(H / s),
                             ln_pi2, ln_pi2 ** 2])
        c0, p, q, r, r2 = lstsq(X, lnZ)
    else:
        X = np.column_stack([np.ones(len(W)), np.log(rho), np.log(H / s),
                             ln_pi2])
        c0, p, q, r = lstsq(X, lnZ)
        r2 = 0.0
    return {'A': np.exp(c0), 'p': p, 'q': q, 'r': r, 'r2': r2}


def predict_impulse(W, rho, H, det, s, b, imp_coeffs):
    """Predict the impulse convergence radius.

    Dispatches on the coefficient dict:
      unified ('C1'.. keys):
        R = W^(1/3) * A * Pi2^(C4 + C5*ln(rho) + C3*ln(H/s))
              * exp(C1*rho*sqrt(H/s) + C2*ln(H/s)^2)
      power law ('p'/'q'/'r' keys, historical tables):
        R = W^(1/3) * A * rho^p * (H/s)^q * Pi2^r * exp(r2*ln(Pi2)^2)
    Dicts without an 'r2' key (older saved coefficients) predict with
    r2 = 0. Returns prediction array (NaN where group is missing).
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
        if 'C1' in coef:
            hs = H[mask] / s[mask]
            ln_hs = np.log(hs)
            ln_pi2 = np.log(s[mask] / W13m)
            lnZ = (np.log(coef['A'])
                   + coef['C1'] * rho[mask] * np.sqrt(hs)
                   + coef['C2'] * ln_hs ** 2
                   + coef['C3'] * ln_hs * ln_pi2
                   + coef['C4'] * ln_pi2
                   + coef['C5'] * np.log(rho[mask]) * ln_pi2)
            Z = np.exp(lnZ)
        else:
            Z = (coef['A'] * rho[mask] ** coef['p']
                 * (H[mask] / s[mask]) ** coef['q']
                 * (s[mask] / W13m) ** coef['r'])
            r2 = coef.get('r2', 0.0)
            if r2 != 0.0:
                Z = Z * np.exp(r2 * np.log(s[mask] / W13m) ** 2)
        pred[mask] = W13m * Z
    return pred


def fit_impulse_all_groups(conv_df, target_col='RadiusI', model='legacy'):
    """Fit the RadiusI model for det=1 and det=2 groups.

    model: 'unified' (production), 'quad' or 'legacy' (historical power
    laws) — see _fit_impulse_group. Returns dict {det_val: coef_or_None}.
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
                                             S[mask], R[mask], model=model)
    return coeffs
