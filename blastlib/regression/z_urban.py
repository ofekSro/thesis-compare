"""Z_urban model (Buckingham Pi power law) — fit, predict, clip, evaluate."""

import numpy as np
import pandas as pd

from blastlib.config.parser import config_parser
from blastlib.geometry import area_density
from blastlib.regression.stats import lstsq, r2_mape
from blastlib.regression.convergence_models import predict_pi, predict_impulse


# ============================================================
# Z_urban models
#
# Canonical form:  MaxR = W^(1/3) * Z_urban   (Hopkinson scaling imposed)
# R_urban is NOT a separate model: R_urban = W^(1/3) * Z_urban identically.
#
# Four forms exist, selected per target by Z_URBAN_FORM. All of them model
# the AMPLIFICATION FACTOR Lambda = Z_urban / Z_free in some way, and all are
# built from dimensionless Pi groups (rho, Pi_3 = H/s, Pi_2 = s/W^(1/3));
# W enters ONLY through W^(1/3).
#
# CURRENT DEFAULTS — closed forms found by symbolic regression (PySR) over the
# raw Pi groups and validated under leave-one-geometry-out CV, where they beat
# both the previous models and every polynomial ln(Lambda) expansion tried,
# with 4 fitted parameters per det group each:
#
#   Pressure — 'range_switch':
#       ln Lambda = C0 + C1 * [ (Pi_2 - A)/Z_free - ln(Pi_2) ]
#                            / ( Pi_2/Pi_3 + B )
#     A is stored POSITIVE: it is the switch threshold itself (sign flip at
#     Pi_2 = A), the only convention that survives being read off a CSV.
#     -ln(Pi_2)          baseline street-width power law;
#     (Pi_2 - A)/Z_free  near-field switch DECAYING WITH RANGE: narrow streets
#                        (Pi_2 < A) amplify up close, wide streets attenuate,
#                        both fade as 1/Z_free toward the free field;
#     Pi_2/Pi_3 + B      open-canyon damping — wide, low canyons suppress the
#                        whole urban effect.
#
#   Impulse — 'canyon_trap':
#       ln Lambda = C0 + C1 * rho*(sqrt(Pi_3) - C2*rho)
#                            / ( Pi_3 + C3*sqrt(Pi_2) )
#     rho*sqrt(Pi_3)     trapping: wall continuity x canyon aspect;
#     -C2*rho^2          density self-limiting — over-dense blocks choke the
#                        very streets that carry the reflections;
#     Pi_3 + C3*sqrt(..) canyon saturation plus scaled-street-width dilution.
#     NO Z_free term: impulse amplification is geometry-set and range-flat.
#
# The pair encodes a physics finding, not just a fit: peak pressure
# amplification is RANGE-DRIVEN (wavefront interference decaying toward free
# field) while impulse amplification is GEOMETRY-DRIVEN (the integrated
# positive phase sees only the canyon). Cross-applying either structure to the
# other target degrades LOGO MAPE by 3-4 pp, in both dets — the split is real.
#
# LEGACY FORMS — kept selectable for A/B comparison, do not delete until the
# A/B on a full pipeline run confirms the new defaults:
#
#   Impulse  — 'power': Buckingham Pi power law, both regimes together:
#       Z_urban = C * Z_free^m * rho^p * (H/s)^q * (s/W^(1/3))^r
#     a 5-coefficient OLS in log space per det group.
#
#   Pressure — 'lambda_regime': additive Pi on Lambda, fitted separately per
#     attenuation/amplification regime and multiplied back up. See
#     ATTENUATION_CRITERION for the regime split. The new forms need no
#     regime machinery at all: ln Lambda crosses zero continuously.
#
# Validity domain: Z_free >= 2 (at Z_free = 1 the point lies within one
# Hopkinson length of the charge — inside the first street — where the
# discrete near-field geometry dominates), and inside the convergence radius.
#
# BOTH regimes are fitted. Attenuation (Z_urban < Z_free) is not an edge case:
# it is 51% of in-convergence pressure rows and 15% of impulse rows. It was
# previously excluded as "a different physics the model cannot represent",
# which left the model with no coverage over half its own domain and
# predicting amplification where the data attenuates.
#
# Physical closure with the convergence radius: by definition the urban field
# equals free-field beyond R_conv, so MaxR can never EXCEED R_conv.
# Predictions are therefore clipped from above at Z_conv using the
# convergence-radius formulas (RadiusP additive / RadiusI power law) — the two
# formula systems form one consistent chain. For Z_free >= Z_conv the mapping
# is the identity (urban = free-field).
#
# There is NO lower bound. "MaxR cannot fall below Z_free*W^(1/3)" is a
# tautology only on an amplification-only domain; on the full domain it is
# false for half the data, and imposing it forces Lambda >= 1, making
# attenuation unrepresentable. See clip_z_urban_pred.
# ============================================================

Z_URBAN_ZF_MIN = {'Pressure': 2.0, 'Impulse': 2.0}

# Density-switch threshold, shared with the RadiusP additive model: a
# geometric constant (street / intersection), never fitted.
LAMBDA_A_THRESH = {1: 1.0, 2: 2.0}

# Which functional form each target uses — THE A/B SWITCH.
#   'range_switch'  — pressure closed form (PySR), 4 params/det, no classifier
#   'canyon_trap'   — impulse closed form (PySR), 4 params/det, no Z_free term
#   'lambda_regime' — legacy pressure: per-regime additive Lambda + classifier
#   'power'         — legacy impulse: Pi power law
# To A/B against the legacy models, set this back to
#   {'Pressure': 'lambda_regime', 'Impulse': 'power'}
# and re-run; every fit, prediction, CSV row and printed formula follows this
# dict. LOGO CV (18 geometries/det): range_switch 8.4% vs 9.9% legacy,
# canyon_trap 9.9% vs 12.3% legacy.
Z_URBAN_FORM = {'Pressure': 'range_switch', 'Impulse': 'canyon_trap'}

# Pi-expressible criterion for the sign of (Lambda - 1), pressure.
#
#   xi = Z_free / Z_conv,P        (Z_conv from the PREDICTED formula)
#   g  = c_const + c_invpi2*(W^(1/3)/s) + c_rho*rho + c_hs*(H/s) + c_xi*xi
#   attenuation  if  g > 0
#
# xi is the ONLY distance term. An earlier version also carried ln(Z_free),
# but xi = Z_free/Z_conv is nearly the same variable: corr(ln Z_free, xi)
# = 0.94, VIF 11.3 and 12.1. That collinearity produced large opposite-signed
# coefficients on the pair — including an xi sign flip between det groups that
# read like intersection venting and was noise. With ln(Z_free) dropped, xi's
# VIF falls to 1.07.
#
# Whether a point amplifies or attenuates is NOT a property of the
# configuration: 60 of 96 configs flip sign with range, and 65% of rows sit in
# those configs, which caps any purely geometric classifier at 0.815 accuracy.
# The ln(Z_free) and xi terms are what carry the within-config range
# dependence — read physically as interference, the path-length difference
# between the direct shock and its reflections alternating between
# constructive and destructive as distance grows.
#
# THESE ARE PRODUCTION DEFAULTS ONLY — fitted on all 96 configs. They are the
# right thing to ship in a coefficient file and the WRONG thing to use inside
# cross-validation, where they would leak the test rows into the regime
# labels. fit_z_urban_all_groups refits the criterion on its training rows and
# stores the result alongside the Lambda coefficients; these values are used
# only when no fitted criterion is supplied.
ATTENUATION_CRITERION = {
    'const':  1.1019,
    'invpi2': -2.1236,   # W^(1/3)/s
    'rho':     1.9218,
    'hs':      0.3474,   # H/s
    'xi':     -0.5821,   # Z_free / Z_conv  — the only distance term
}

ATTENUATION_KEYS = ('const', 'invpi2', 'rho', 'hs', 'xi')


def _attenuation_design(Z_free, rho, H, s, W13, xi):
    """Columns matching ATTENUATION_KEYS order (const first)."""
    n = len(np.asarray(Z_free, dtype=float))
    return np.column_stack([
        np.ones(n),
        np.asarray(W13, float) / np.asarray(s, float),
        np.asarray(rho, float),
        np.asarray(H, float) / np.asarray(s, float),
        np.asarray(xi, float),
    ])


def fit_attenuation_criterion(sub, xi):
    """Fit the regime classifier on TRAINING rows only.

    Returns a dict in raw (unstandardised) units, keyed by ATTENUATION_KEYS.
    Falls back to the shipped defaults if the fit is degenerate — e.g. a
    training split with only one regime present.
    """
    from sklearn.linear_model import LogisticRegression

    y = (sub['Z_urban_P'].values.astype(float)
         < sub['Z_free'].values.astype(float)).astype(int)
    if len(np.unique(y)) < 2 or len(y) < 20:
        return dict(ATTENUATION_CRITERION)

    X = _attenuation_design(sub['Z_free'].values, sub['rho'].values,
                            sub['height'].values, sub['swidth'].values,
                            sub['weight'].values.astype(float) ** (1 / 3), xi)
    Z = X[:, 1:]
    mu, sd = Z.mean(0), Z.std(0)
    sd[sd == 0] = 1.0
    try:
        m = LogisticRegression(max_iter=3000).fit((Z - mu) / sd, y)
    except Exception:
        return dict(ATTENUATION_CRITERION)
    w = m.coef_[0] / sd
    c0 = float(m.intercept_[0] - (m.coef_[0] * mu / sd).sum())
    return dict(zip(ATTENUATION_KEYS, [c0, *(float(v) for v in w)]))


def predicted_Zconv_P(df, conv_P_coeffs):
    """Z_conv for the classifier, from the PREDICTED convergence radius.

    Must never use the measured RadiusP column: at inference time it does not
    exist, and using it in training would leak the answer into xi.
    """
    W = df['weight'].values.astype(float)
    Rconv = predict_pi(W, df['rho'].values.astype(float),
                       df['height'].values.astype(float),
                       df['det'].values.astype(int),
                       df['swidth'].values.astype(float),
                       df['bsize'].values.astype(float), conv_P_coeffs)
    return Rconv / W ** (1 / 3)


def attenuation_regime(Z_free, rho, H, s, W13, xi, criterion=None):
    """True where the pressure field is predicted to ATTENUATE (Lambda < 1).

    *criterion* must be the fold's fitted criterion whenever this is used
    inside cross-validation; passing None falls back to the shipped production
    defaults, which have seen all 96 configs.
    """
    c = criterion or ATTENUATION_CRITERION
    X = _attenuation_design(Z_free, rho, H, s, W13, xi)
    return X @ np.array([c[k] for k in ATTENUATION_KEYS]) > 0

BEYOND_COL = {'Pressure': 'beyond_P', 'Impulse': 'beyond_I'}


def z_urban_valid_mask(sub, target_col, maxR_col, radius_col, target_name):
    """Rows eligible for the Z_urban fit: the full in-convergence domain.

    Two conditions:
      1. inside the convergence radius — beyond it the urban field IS the
         free field, so the row carries no urban information;
      2. Z_free >= the validity floor (see the module header).

    There used to be a third condition, `Z_urban > Z_free`, restricting the fit
    to the amplification regime. It is gone. Attenuation is not an edge case:
    it is 51% of in-convergence pressure rows and 15% of impulse rows, most of
    them well inside R_conv, so excluding it left the model with no coverage
    over half its own domain and predicting amplification where the data
    attenuates. Pressure handles the two regimes with an explicit split (see
    attenuation_regime); impulse fits both together.

    Condition 1 is what Phase 1 records as beyond_P / beyond_I. The
    `MaxR < R_conv` fallback keeps older, flagless CSVs working — it selects
    the identical set, since beyond == (MaxR is NaN) or (MaxR >= R_conv) and
    NaN rows are dropped by the caller's dropna().

    Defined once and used by the fit, the evaluation and the validation plots
    so those three can never drift apart.
    """
    beyond_col = BEYOND_COL[target_name]
    if beyond_col in sub.columns:
        inside = ~sub[beyond_col].astype(bool)
    else:
        inside = sub[maxR_col] < sub[radius_col]

    return inside & (sub['Z_free'] >= Z_URBAN_ZF_MIN[target_name])


def _z_urban_design(Z_free, rho, H, s, W13):
    """Log-space design matrix: [1, ln(Zf), ln(rho), ln(H/s), ln(s/W^(1/3))]."""
    Z_free = np.asarray(Z_free, dtype=float)
    rho    = np.asarray(rho,    dtype=float)
    H      = np.asarray(H,      dtype=float)
    s      = np.asarray(s,      dtype=float)
    W13    = np.asarray(W13,    dtype=float)
    return np.column_stack([np.ones(len(rho)), np.log(Z_free), np.log(rho),
                            np.log(H / s), np.log(s / W13)])


def _lambda_design(Z_free, rho, H, s, W13, a):
    """Design matrix for the Lambda model (pressure).

    Columns: [1, s/W^(1/3), rho*(s/W^(1/3) - a),
              sqrt(rho)*(H/s)*(W^(1/3)/s - 1), ln(Z_free)]

    The first four are exactly the RadiusP additive Pi terms — same density
    switch and same canyon law, with `a` the same unfitted geometric
    constant — applied here to the amplification factor rather than to a
    radius. The ln(Z_free) column lets the amplification decay with range.
    """
    Z_free = np.asarray(Z_free, dtype=float)
    rho    = np.asarray(rho,    dtype=float)
    H      = np.asarray(H,      dtype=float)
    s      = np.asarray(s,      dtype=float)
    W13    = np.asarray(W13,    dtype=float)
    pi2    = s / W13
    switch = rho * (pi2 - a)
    canyon = np.sqrt(rho) * (H / s) * (W13 / s - 1.0)
    return np.column_stack([np.ones(len(rho)), pi2, switch, canyon,
                            np.log(Z_free)])


def _fit_lambda_group(Z_free, Z_urban, rho, H, s, W13, det_val):
    """Fit the pressure Lambda model for one det group via plain OLS.

    Fits the AMPLIFICATION FACTOR
        Lambda = Z_urban / Z_free
        Lambda = C0 + C1*(s/W^(1/3)) + C2*rho*(s/W^(1/3) - a)
                    + C3*sqrt(rho)*(H/s)*(W^(1/3)/s - 1) + C4*ln(Z_free)
    and recovers Z_urban = Lambda * Z_free.

    Fitting Lambda is not the same model as fitting Z_urban with Z_free as a
    regressor: here Z_free multiplies the whole expression, so the fit
    minimises error in the amplification rather than in the radius, and the
    Z_urban = Z_free identity is exact at Lambda = 1.

    Returns {'C0','C1','C2','C3','C4','a','zf_min'} or None on failure.
    """
    Z_free  = np.asarray(Z_free,  dtype=float)
    Z_urban = np.asarray(Z_urban, dtype=float)
    if not np.all(Z_free > 0):
        return None

    a = LAMBDA_A_THRESH.get(det_val, 1.0)
    X = _lambda_design(Z_free, rho, H, s, W13, a)
    lam = Z_urban / Z_free
    try:
        C0, C1, C2, C3, C4 = lstsq(X, lam)
    except np.linalg.LinAlgError:
        return None
    return {'C0': C0, 'C1': C1, 'C2': C2, 'C3': C3, 'C4': C4, 'a': a,
            'zf_min': Z_URBAN_ZF_MIN['Pressure']}


def _predict_lambda(Z_free, rho, H, s, W13, coef):
    """Z_urban = Lambda * Z_free for the pressure Lambda model."""
    X = _lambda_design(Z_free, rho, H, s, W13, coef['a'])
    beta = np.array([coef['C0'], coef['C1'], coef['C2'], coef['C3'],
                     coef['C4']])
    return (X @ beta) * np.asarray(Z_free, dtype=float)


MIN_REGIME_SAMPLES = 10


def _fit_lambda_regimes(sub, det_val, xi, criterion):
    """Fit one Lambda model per regime, split by the CLASSIFIER, not by truth.

    Fitting on the classifier's partition rather than the true one is
    deliberate and worth about 1.4-2.5 pp of MAPE. At inference the regime is
    always a guess, so the Lambda fit should see the same imperfect partition
    it will be applied to; it then absorbs part of the classifier's error.
    Fitting on the true partition instead creates a train/test mismatch that
    costs more than the misclassifications themselves.

    Returns {'amp': coef|None, 'att': coef|None, 'pooled': coef,
             'criterion': criterion}. 'pooled' is fitted on the whole det
    group, ignoring the regime split, and is the fallback used at prediction
    time whenever the regime the classifier picked had fewer than
    MIN_REGIME_SAMPLES training rows to fit on. It is a live prediction path,
    not reference material.
    """
    Z_free = sub['Z_free'].values.astype(float)
    Z_urban = sub['Z_urban_P'].values.astype(float)
    rho = sub['rho'].values.astype(float)
    H = sub['height'].values.astype(float)
    s = sub['swidth'].values.astype(float)
    W13 = sub['weight'].values.astype(float) ** (1 / 3)

    att = attenuation_regime(Z_free, rho, H, s, W13, xi, criterion)
    out = {'pooled': _fit_lambda_group(Z_free, Z_urban, rho, H, s, W13, det_val),
           'criterion': dict(criterion)}
    for key, m in (('att', att), ('amp', ~att)):
        out[key] = (_fit_lambda_group(Z_free[m], Z_urban[m], rho[m], H[m],
                                      s[m], W13[m], det_val)
                    if m.sum() >= MIN_REGIME_SAMPLES else None)
    return out if out['pooled'] is not None else None


def _fit_z_urban_group(Z_free, Z_urban, rho, H, s, W13, target_name):
    """Fit the Z_urban power law for one det group via log-space OLS.

    Returns {'C', 'm', 'p', 'q', 'r', 'zf_min'} or None on failure.
    """
    Z_urban = np.asarray(Z_urban, dtype=float)
    if not np.all(Z_urban > 0):
        return None
    X = _z_urban_design(Z_free, rho, H, s, W13)
    try:
        c0, m, p, q, r = lstsq(X, np.log(Z_urban))
    except np.linalg.LinAlgError:
        return None
    return {'C': np.exp(c0), 'm': m, 'p': p, 'q': q, 'r': r,
            'zf_min': Z_URBAN_ZF_MIN[target_name]}


# Starting points and bounds for the two closed forms, mirroring the LOGO
# validation runs (zero curve_fit failures across all folds there; the
# validation fitted (Pi_2 + A) with A <= 0 — same model, A sign flipped).
# Bounds keep each fit on the physically readable branch: C1 >= 0 preserves
# the sign story of every term, A >= 0 puts the (Pi_2 - A) sign flip at a
# physical street width, and the denominators stay positive over the data.
RANGE_SWITCH_P0     = (0.11, 1.34, 2.4, 1.95)
RANGE_SWITCH_BOUNDS = ((-2.0, 0.0, 0.0, 0.2), (2.0, 6.0, 6.0, 8.0))
CANYON_TRAP_P0      = (0.0, 2.6, 1.0, 1.0)
CANYON_TRAP_BOUNDS  = ((-2.0, 0.0, 0.0, 0.0), (2.0, 12.0, 4.0, 6.0))


def _range_switch_ln_lambda(X, C0, C1, A, B):
    """ln(Lambda) for the pressure closed form. X = (Z_free, H/s, s/W13).

    A is the positive switch threshold: the (Pi_2 - A) term flips sign at
    Pi_2 = A. Stored in the CSV as A_switch with this same sign convention.
    """
    Zf, Hs, pi2 = X
    return C0 + C1 * ((pi2 - A) / Zf - np.log(pi2)) / (pi2 / Hs + B)


def _canyon_trap_ln_lambda(X, C0, C1, C2, C3):
    """ln(Lambda) for the impulse closed form. X = (rho, H/s, s/W13)."""
    rho, Hs, pi2 = X
    return C0 + C1 * rho * (np.sqrt(Hs) - C2 * rho) / (Hs + C3 * np.sqrt(pi2))


def _fit_range_switch_group(Z_free, Z_urban, H, s, W13, target_name):
    """Fit the pressure range-switch form for one det group (4 parameters).

    Nonlinear least squares on ln(Lambda); rho does not enter this form.
    Returns {'C0','C1','A','B','zf_min'} or None on failure.
    """
    from scipy.optimize import curve_fit

    Z_free  = np.asarray(Z_free,  dtype=float)
    Z_urban = np.asarray(Z_urban, dtype=float)
    if not (np.all(Z_free > 0) and np.all(Z_urban > 0)):
        return None
    X = (Z_free, np.asarray(H, float) / np.asarray(s, float),
         np.asarray(s, float) / np.asarray(W13, float))
    try:
        popt, _ = curve_fit(_range_switch_ln_lambda, X,
                            np.log(Z_urban / Z_free),
                            p0=RANGE_SWITCH_P0, bounds=RANGE_SWITCH_BOUNDS,
                            maxfev=20000)
    except (RuntimeError, ValueError):
        return None
    C0, C1, A, B = popt
    return {'C0': C0, 'C1': C1, 'A': A, 'B': B,
            'zf_min': Z_URBAN_ZF_MIN[target_name]}


def _fit_canyon_trap_group(Z_free, Z_urban, rho, H, s, W13, target_name):
    """Fit the impulse canyon-trap form for one det group (4 parameters).

    Nonlinear least squares on ln(Lambda); Z_free enters only through the
    Lambda target itself — the fitted amplification is range-flat.
    Returns {'C0','C1','C2','C3','zf_min'} or None on failure.
    """
    from scipy.optimize import curve_fit

    Z_free  = np.asarray(Z_free,  dtype=float)
    Z_urban = np.asarray(Z_urban, dtype=float)
    if not (np.all(Z_free > 0) and np.all(Z_urban > 0)):
        return None
    X = (np.asarray(rho, float),
         np.asarray(H, float) / np.asarray(s, float),
         np.asarray(s, float) / np.asarray(W13, float))
    try:
        popt, _ = curve_fit(_canyon_trap_ln_lambda, X,
                            np.log(Z_urban / Z_free),
                            p0=CANYON_TRAP_P0, bounds=CANYON_TRAP_BOUNDS,
                            maxfev=20000)
    except (RuntimeError, ValueError):
        return None
    C0, C1, C2, C3 = popt
    return {'C0': C0, 'C1': C1, 'C2': C2, 'C3': C3,
            'zf_min': Z_URBAN_ZF_MIN[target_name]}


def _predict_range_switch(Z_free, H, s, W13, coef):
    """Z_urban = exp(ln Lambda) * Z_free for the pressure closed form."""
    Z_free = np.asarray(Z_free, dtype=float)
    X = (Z_free, np.asarray(H, float) / np.asarray(s, float),
         np.asarray(s, float) / np.asarray(W13, float))
    return np.exp(_range_switch_ln_lambda(
        X, coef['C0'], coef['C1'], coef['A'], coef['B'])) * Z_free


def _predict_canyon_trap(Z_free, rho, H, s, W13, coef):
    """Z_urban = exp(ln Lambda) * Z_free for the impulse closed form."""
    Z_free = np.asarray(Z_free, dtype=float)
    X = (np.asarray(rho, float),
         np.asarray(H, float) / np.asarray(s, float),
         np.asarray(s, float) / np.asarray(W13, float))
    return np.exp(_canyon_trap_ln_lambda(
        X, coef['C0'], coef['C1'], coef['C2'], coef['C3'])) * Z_free


def predict_z_urban(Z_free, rho, H, s, W13, target_name, coef, xi=None):
    """Predict Z_urban with whichever form this target uses (Z_URBAN_FORM).

    range_switch:  pressure closed form — no regime machinery, xi unused.
    canyon_trap:   impulse closed form — no regime machinery, xi unused.
    lambda_regime: classify the regime, then Z_urban = Lambda * Z_free with
                   that regime's coefficients. Requires *xi* (from the
                   PREDICTED convergence radius — see predicted_Zconv_P).
    power:         Z_urban = C * Zf^m * rho^p * (H/s)^q * (s/W^(1/3))^r.
    """
    form = Z_URBAN_FORM.get(target_name)
    if form == 'range_switch':
        return _predict_range_switch(Z_free, H, s, W13, coef)
    if form == 'canyon_trap':
        return _predict_canyon_trap(Z_free, rho, H, s, W13, coef)
    if form == 'lambda_regime':
        if xi is None:
            raise ValueError('xi is required for the pressure regime model; '
                             'compute it with predicted_Zconv_P so the '
                             'classifier does not see the measured radius.')
        att = attenuation_regime(Z_free, rho, H, s, W13, xi,
                                 coef.get('criterion'))
        out = np.empty(len(np.asarray(Z_free, dtype=float)))
        for flag, key in ((True, 'att'), (False, 'amp')):
            m = att == flag
            if not np.any(m):
                continue
            c = coef[key] if coef.get(key) is not None else coef['pooled']
            out[m] = _predict_lambda(np.asarray(Z_free, float)[m],
                                     np.asarray(rho, float)[m],
                                     np.asarray(H, float)[m],
                                     np.asarray(s, float)[m],
                                     np.asarray(W13, float)[m], c)
        return out

    X = _z_urban_design(Z_free, rho, H, s, W13)
    lnC = np.log(coef['C'])
    return np.exp(X @ np.array([lnC, coef['m'], coef['p'], coef['q'], coef['r']]))


def clip_z_urban_pred(pred_Z, sub_valid, det_val, target_name,
                      conv_P_coeffs, conv_I_coeffs):
    """Clip Z_urban predictions from ABOVE at Z_conv. No lower bound.

    Upper bound — a deliberate correction, not a patch over a bug. MaxR cannot
    exceed the convergence radius (urban = free-field beyond it). The two radii
    are measured with different tolerance conventions — R_conv from a band
    around the free-field value, MaxR from a zero-tolerance exceedance test,
    the impulse band being materially the looser — so MaxR overshoots R_conv
    systematically rather than occasionally, and the closure has to be imposed
    rather than assumed. Remove it only if the two criteria are first made to
    agree. Z_conv comes from the fitted convergence formulas, so the chain
    stays self-consistent. No-op if those coefficients are missing.

    NO lower bound. There used to be a max(pred, Z_free) here, justified by
    "MaxR cannot fall below the free-field radius". That is a tautology only on
    the amplification-only fit domain. On the full in-convergence domain it is
    false for 51% of pressure rows and 15% of impulse rows, which genuinely
    attenuate — and since it forces Lambda >= 1 it cannot represent them at
    all, clamping every attenuation prediction to exactly the free-field
    radius. Under an oracle regime split it doubled attenuation error
    (6.43% -> 13.57%).
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
        Rconv = predict_pi(W, rho, H, det_arr, s, b, coeffs)
    else:
        Rconv = predict_impulse(W, rho, H, det_arr, s, b, coeffs)

    return np.where(np.isfinite(Rconv), np.minimum(pred_Z, Rconv / W13), pred_Z)


# ============================================================
# Z_urban model: fit & predict
# ============================================================

def prepare_maxR_data(maxR_df, conv_df):
    """Merge geometry and convergence radii into maxR DataFrame."""
    # Parse geometry from config names
    records = []
    for cfg_name in maxR_df['Config'].unique():
        cfg = config_parser(cfg_name)
        if cfg is None:
            continue
        rho = area_density(cfg['bsize'], cfg['swidth'])
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

    # Phase 1 writes these as booleans, but a round-trip through CSV can leave
    # them as 'True'/'False' strings — every non-empty string is truthy, so
    # coerce explicitly or the fit would silently keep every beyond row.
    for col in BEYOND_COL.values():
        if col in df.columns:
            df[col] = df[col].map(
                lambda v: str(v).strip().lower() in ('true', '1', '1.0')
                if not isinstance(v, (bool, np.bool_)) else bool(v))

    df['Z_free'] = df['Z'].astype(float)
    df['Z_urban_P'] = df['MaxR_P'] / df['weight'] ** (1/3)
    df['Z_urban_I'] = df['MaxR_I'] / df['weight'] ** (1/3)

    # Merge convergence radii
    conv_cols = conv_df[['ConfigName', 'RadiusP', 'RadiusI']].copy()
    conv_cols = conv_cols.rename(columns={'ConfigName': 'Config'})
    df = df.merge(conv_cols, on='Config', how='left')

    return df


def fit_z_urban_all_groups(train_df, conv_P_coeffs=None):
    """Fit Z_urban models per det group × 2 targets (forms per Z_URBAN_FORM).

    conv_P_coeffs is required only when pressure uses the legacy
    'lambda_regime' form: its regime classifier needs xi, and xi must be
    built from the PREDICTED convergence radius so nothing leaks from the
    measured one. The closed forms need no xi at fit time (the convergence
    coefficients still supply the Z_conv clip at prediction time).

    Returns dict {(det, target_name): coef_dict or None}.
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

            sub_valid = sub[z_urban_valid_mask(sub, target_col, maxR_col,
                                               radius_col, target_name)]

            if len(sub_valid) < 5:
                coeffs[(det_val, target_name)] = None
                continue

            W13 = sub_valid['weight'].values ** (1 / 3)

            form = Z_URBAN_FORM.get(target_name)
            if form == 'range_switch':
                coef = _fit_range_switch_group(
                    sub_valid['Z_free'].values, sub_valid[target_col].values,
                    sub_valid['height'].values, sub_valid['swidth'].values,
                    W13, target_name)
            elif form == 'canyon_trap':
                coef = _fit_canyon_trap_group(
                    sub_valid['Z_free'].values, sub_valid[target_col].values,
                    sub_valid['rho'].values, sub_valid['height'].values,
                    sub_valid['swidth'].values, W13, target_name)
            elif form == 'lambda_regime':
                if conv_P_coeffs is None:
                    raise ValueError(
                        'conv_P_coeffs is required to fit the pressure '
                        'Z_urban model: xi must come from the predicted '
                        'convergence radius, not the measured one.')
                xi = (sub_valid['Z_free'].values.astype(float)
                      / predicted_Zconv_P(sub_valid, conv_P_coeffs))
                # Refit the regime classifier on THIS fold's training rows.
                # Using the module-level defaults here would leak the test
                # rows into the regime labels.
                crit = fit_attenuation_criterion(sub_valid, xi)
                coef = _fit_lambda_regimes(sub_valid, det_val, xi, crit)
            else:
                coef = _fit_z_urban_group(
                    sub_valid['Z_free'].values, sub_valid[target_col].values,
                    sub_valid['rho'].values, sub_valid['height'].values,
                    sub_valid['swidth'].values, W13, target_name)
            coeffs[(det_val, target_name)] = coef

    return coeffs


def evaluate_z_urban(test_df, z_coeffs, conv_P_coeffs=None, conv_I_coeffs=None):
    """Evaluate Z_urban predictions on test data. Returns (mape_P, mape_I).

    Predictions are clipped from above at Z_conv when convergence
    coefficients are supplied (the deployed prediction chain). No lower bound.
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

            sub_valid = sub[z_urban_valid_mask(sub, target_col, maxR_col,
                                               radius_col, target_name)]
            if len(sub_valid) == 0:
                continue

            y_actual = sub_valid[target_col].values

            W13 = sub_valid['weight'].values ** (1 / 3)
            xi = None
            if Z_URBAN_FORM.get(target_name) == 'lambda_regime':
                xi = (sub_valid['Z_free'].values.astype(float)
                      / predicted_Zconv_P(sub_valid, conv_P_coeffs))
            y_pred = predict_z_urban(
                sub_valid['Z_free'].values, sub_valid['rho'].values,
                sub_valid['height'].values, sub_valid['swidth'].values,
                W13, target_name, popt, xi=xi)
            y_pred = clip_z_urban_pred(y_pred, sub_valid, det_val,
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
        _, mape_P = r2_mape(a, p)
    if all_actual_I:
        a = np.concatenate(all_actual_I)
        p = np.concatenate(all_pred_I)
        _, mape_I = r2_mape(a, p)

    return mape_P, mape_I
