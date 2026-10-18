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

Sector layouts. The legacy tokens keep 91 sectors centred on whole degrees,
the two end sectors half-width but summed as full width in req (an area of
91 deg instead of 90: Req ~0.45% long, more where the street axes are long).
The 'reqdir' token uses 90 equal sectors [k, k+1) deg, so req integrates
exactly 90 deg (docs/PLAN_LAMBDA_ZURBAN_HE.md, decision H1). The legacy
layout is kept so the req_soft3 record stays reproducible.
"""

import re

import numpy as np

from blastlib import constants

N_THETA = 91                # legacy: 0, 1, 2, ..., 90 degrees
N_THETA_EQUAL = 90          # 'reqdir': [0,1), [1,2), ..., [89,90] degrees
DEFAULT_DTHETA_DEG = 1.0    # angular bin width

# 'reqdir' = req collapse on 90 equal sectors, with MaxR normalised per
# direction by the null city (processing/null_city.py; PLAN H1 + H2).
VALID_METHODS = ('req', 'max', 'p95', 'reqdir')

# A '<base>_soft[<beta>]' token (e.g. 'req_soft', 'req_soft8') selects the
# soft pressure criterion (processing/soft_criterion.py) on top of the same
# <base> collapse. A bare '_soft' takes beta from constants.PARAMS.
_SOFT_RE = re.compile(r'^(?P<base>.+?)_soft(?P<beta>\d+(?:\.\d+)?)?$')

# How each method is written on a figure, so plots stay honest when the
# collapse is not the equivalent-area radius. Percentile tokens ('p95', 'p99')
# are already readable and fall through unchanged.
RADIUS_LABEL = {'req': 'Req', 'max': 'Rmax', 'reqdir': 'Req,dir'}


def radius_label(method):
    """Human-readable name for a radius-estimator token ('req' -> 'Req')."""
    return RADIUS_LABEL.get(method, method)


def theta_bin_edges(n_theta=N_THETA):
    """Return the n_theta+1 bin edges (radians) of the angular sectors.

    n_theta = 91 (legacy): each bin is centred on its integer degree and spans
    +/- 0.5 deg, the first and last clipped to [0, pi/2] (half-width ends).
    n_theta = 90: equal 1-deg sectors [k, k+1) deg, k = 0..89.
    """
    if n_theta == N_THETA_EQUAL:
        return np.radians(np.arange(0.0, 91.0, 1.0))
    if n_theta != N_THETA:
        raise ValueError(f'n_theta must be {N_THETA} or {N_THETA_EQUAL}, got {n_theta}')
    edges = np.radians(np.arange(-0.5, 91.0, 1.0))
    edges[0] = 0.0
    edges[-1] = np.pi / 2
    return edges


def theta_centers_deg(n_theta=N_THETA):
    """Sector centres [deg]: 0..90 (legacy, 91) or 0.5..89.5 (equal, 90)."""
    if n_theta == N_THETA_EQUAL:
        return np.arange(0.5, 90.0, 1.0)
    return np.arange(0, N_THETA, dtype=float)


def in_theta_bin(theta, bin_edges, i):
    """Boolean mask selecting *theta* values falling in angular bin *i*.

    Bins are half-open [lo, hi) except the last, which is closed so that
    theta == pi/2 is not dropped.
    """
    if i == len(bin_edges) - 2:
        return (theta >= bin_edges[i]) & (theta <= bin_edges[i + 1])
    return (theta >= bin_edges[i]) & (theta < bin_edges[i + 1])


def _split_soft(method):
    """Split a method token into (base_token, soft_beta_or_None).

    'req'       -> ('req', None)
    'req_soft'  -> ('req', constants.PARAMS['softBeta'])
    'req_soft8' -> ('req', 8.0)
    A beta of None or 0 (from PARAMS or the suffix) means the hard path.
    """
    m = str(method).strip().lower()
    match = _SOFT_RE.match(m)
    if not match:
        return m, None
    beta = match.group('beta')
    beta = constants.PARAMS.get('softBeta') if beta is None else float(beta)
    if not beta:
        return match.group('base'), None
    return match.group('base'), float(beta)


def _parse_method(method, percentile):
    """Normalise (method, percentile) into ('req'|'max'|'percentile', p).

    Soft tokens ('req_soft6') parse as their base collapse — softness only
    changes how per-sector radii are MEASURED, never how they collapse.
    """
    if method is None:
        method = 'req'
    m, _ = _split_soft(method)

    if m in ('req', 'reqdir'):
        return m, percentile
    if m == 'max':
        return 'max', percentile
    if m == 'percentile':
        return 'percentile', percentile
    if m.startswith('p') and m[1:].replace('.', '', 1).isdigit():
        # 'p95', 'p99', 'p97.5' — the number in the name wins
        return 'percentile', float(m[1:])

    raise ValueError(
        f'Unknown radius estimator method {method!r}; '
        f'expected one of {VALID_METHODS}, pXX, or a <base>_soft[beta] '
        f"soft-criterion token (e.g. 'req_soft', 'req_soft8').")


def reduce_theta_radii(r_per_theta, method='req', percentile=95,
                       dtheta_deg=DEFAULT_DTHETA_DEG):
    """Reduce a per-angle radius array to a scalar radius.

    method:
      'req', 'reqdir'
             -> equivalent-area radius: sqrt(4A/pi), A = sum(0.5*r_i^2*dtheta)
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

    if kind in ('req', 'reqdir'):
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
    """Return a validated {'method', 'percentile', 'base_method',
    'soft_beta'} dict.

    *estimator* may be None (use constants.RADIUS_ESTIMATOR), a dict with
    any of the keys (missing keys fall back to the constant), or a bare
    method string. Unspecified keys always come from the single shared
    default, so callers can override one field without restating the other.

    Soft tokens canonicalise with their beta spelled out ('req_soft' with
    PARAMS softBeta 6.0 -> method 'req_soft6'), so every table/figure
    carries the beta it was measured with. A dict key 'soft_beta' overrides
    the suffix beta (used by --soft-beta); it is ignored for hard tokens.
    'base_method' is the collapse token and 'soft_beta' is None on the hard
    path — existing callers that only read 'method'/'percentile' are
    unaffected. 'n_theta' is the sector layout (91 legacy, 90 for 'reqdir')
    and 'normalise' is 'dir' for 'reqdir' (MaxR per-direction null-city
    normalisation), else None.
    """
    default = dict(constants.RADIUS_ESTIMATOR)

    if estimator is None:
        settings = default
    elif isinstance(estimator, str):
        settings = {**default, 'method': estimator}
    else:
        settings = {**default, **{k: v for k, v in estimator.items()
                                  if v is not None}}

    method = settings.get('method')
    _, soft_beta = _split_soft(method if method is not None else 'req')
    if soft_beta is not None and settings.get('soft_beta') is not None:
        soft_beta = float(settings['soft_beta'])

    kind, p = _parse_method(method, settings.get('percentile', 95))

    if kind == 'percentile':
        p = float(p)
        if not 0 <= p <= 100:
            raise ValueError(f'percentile must be in [0, 100], got {p}')
        base = f'p{p:g}'
        percentile = p
    else:
        base = kind
        percentile = settings.get('percentile', 95)

    token = base if soft_beta is None else f'{base}_soft{soft_beta:g}'
    is_dir = base == 'reqdir'
    return {'method': token, 'percentile': percentile,
            'base_method': base, 'soft_beta': soft_beta,
            'n_theta': N_THETA_EQUAL if is_dir else N_THETA,
            'normalise': 'dir' if is_dir else None}


def method_label(estimator=None):
    """Short token identifying the estimator, for filenames and CSV columns.

    'req' | 'max' | 'p95' (or 'p99', 'p97.5', ... for other percentiles).
    """
    return resolve_estimator(estimator)['method']
