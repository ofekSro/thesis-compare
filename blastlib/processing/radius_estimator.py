"""The single place where a per-angle radius array collapses to one scalar.

Both the convergence radius (convergence.py) and the MaxR / Z_urban radius
(free_field.py) reduce the same object — 91 per-angle radii covering 0-90 deg
in 1-degree bins — to a single number. They used to do it differently: Req
(equivalent area, an area *average*) for convergence, p95 (a near-*maximum*)
for MaxR. Comparing a near-maximum against an area average made MaxR >= R_conv
in a large fraction of rows, which is impossible under our own definitions
(the urban field equals free-field beyond R_conv).

One setting — RADIUS_ESTIMATOR in blastlib/constants.py — now drives both, so
the two quantities are always measured the same way. There is deliberately no
way to configure them separately.

The three collapse methods are carried over verbatim from the code they
replace; 'req' and 'p95' reproduce the previous behaviour exactly.
"""

import numpy as np

from blastlib import constants

N_THETA = 91                # 0, 1, 2, ..., 90 degrees
DEFAULT_DTHETA_DEG = 1.0    # angular bin width

VALID_METHODS = ('req', 'max', 'p95')

# How each method is written on a figure, so plots stay honest when the
# collapse is not the equivalent-area radius. Percentile tokens ('p95', 'p99')
# are already readable and fall through unchanged.
RADIUS_LABEL = {'req': 'Req', 'max': 'Rmax'}


def radius_label(method):
    """Human-readable name for a radius-estimator token ('req' -> 'Req')."""
    return RADIUS_LABEL.get(method, method)


def theta_bin_edges():
    """Return the 92 bin edges (radians) for the 91 angular bins.

    Each bin is centred on its integer degree and spans +/- 0.5 deg, with the
    first and last clipped to [0, pi/2] (so bins 0 and 90 are half-width).
    """
    edges = np.radians(np.arange(-0.5, 91.0, 1.0))
    edges[0] = 0.0
    edges[-1] = np.pi / 2
    return edges


def in_theta_bin(theta, bin_edges, i):
    """Boolean mask selecting *theta* values falling in angular bin *i*.

    Bins are half-open [lo, hi) except the last, which is closed so that
    theta == pi/2 is not dropped.
    """
    if i == N_THETA - 1:
        return (theta >= bin_edges[i]) & (theta <= bin_edges[i + 1])
    return (theta >= bin_edges[i]) & (theta < bin_edges[i + 1])


def _parse_method(method, percentile):
    """Normalise (method, percentile) into ('req'|'max'|'percentile', p)."""
    if method is None:
        method = 'req'
    m = str(method).strip().lower()

    if m == 'req':
        return 'req', percentile
    if m == 'max':
        return 'max', percentile
    if m == 'percentile':
        return 'percentile', percentile
    if m.startswith('p') and m[1:].replace('.', '', 1).isdigit():
        # 'p95', 'p99', 'p97.5' — the number in the name wins
        return 'percentile', float(m[1:])

    raise ValueError(
        f'Unknown radius estimator method {method!r}; '
        f'expected one of {VALID_METHODS} (or pXX).')


def reduce_theta_radii(r_per_theta, method='req', percentile=95,
                       dtheta_deg=DEFAULT_DTHETA_DEG):
    """Reduce a per-angle radius array to a scalar radius.

    method:
      'req'  -> equivalent-area radius: sqrt(4A/pi), A = sum(0.5*r_i^2*dtheta)
      'max'  -> np.nanmax(r_per_theta)
      'pXX'  -> np.nanpercentile(r_per_theta, percentile)

    Returns NaN when no bin holds a valid radius.

    Note on 'req': NaN bins are dropped from the sum without renormalising
    dtheta, so missing angular coverage shrinks the area (and thus Req) rather
    than being interpolated. That is the historical behaviour and is preserved
    deliberately — 'max' and 'p95' have no equivalent bias, which is one reason
    the three methods are not interchangeable at the same numeric level.
    """
    radii = np.asarray(r_per_theta, dtype=float)
    kind, p = _parse_method(method, percentile)

    if kind == 'req':
        delta_theta = np.radians(dtheta_deg)
        valid = ~np.isnan(radii)
        if not np.any(valid):
            return np.nan
        A = np.sum(0.5 * radii[valid] ** 2 * delta_theta)
        return float(np.sqrt(4 * A / np.pi))

    valid = radii[~np.isnan(radii)]
    if valid.size == 0:
        return np.nan

    if kind == 'max':
        return float(np.nanmax(valid))

    return float(np.nanpercentile(valid, p))


def resolve_estimator(estimator=None):
    """Return a validated {'method', 'percentile'} dict.

    *estimator* may be None (use constants.RADIUS_ESTIMATOR), a dict with
    either or both keys (missing keys fall back to the constant), or a bare
    method string. Unspecified keys always come from the single shared default,
    so callers can override one field without restating the other.
    """
    default = dict(constants.RADIUS_ESTIMATOR)

    if estimator is None:
        settings = default
    elif isinstance(estimator, str):
        settings = {**default, 'method': estimator}
    else:
        settings = {**default, **{k: v for k, v in estimator.items()
                                  if v is not None}}

    kind, p = _parse_method(settings.get('method'), settings.get('percentile', 95))

    if kind == 'percentile':
        p = float(p)
        if not 0 <= p <= 100:
            raise ValueError(f'percentile must be in [0, 100], got {p}')
        return {'method': f'p{p:g}', 'percentile': p}

    return {'method': kind, 'percentile': settings.get('percentile', 95)}


def method_label(estimator=None):
    """Short token identifying the estimator, for filenames and CSV columns.

    'req' | 'max' | 'p95' (or 'p99', 'p97.5', ... for other percentiles).
    """
    return resolve_estimator(estimator)['method']
