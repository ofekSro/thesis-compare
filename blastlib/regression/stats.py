"""Statistical helpers shared by the regression pipeline."""

import numpy as np


def lstsq(X, y):
    """Solve OLS: X @ coef = y."""
    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    return coef


def r2_mape(actual, predicted):
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
