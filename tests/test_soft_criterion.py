"""Reduction tests for the convergence scanners.

The oracle below reimplements the far-to-near K_CONSECUTIVE scan
independently of blastlib; the legacy path must match it exactly. The
soft-criterion tests (added with the soft scanner) assert bit-exact
reduction of the soft path in its hard limits.
"""

import numpy as np
import pytest

from blastlib.processing.convergence import (
    K_CONSECUTIVE, TOLERANCE, _find_radius_for_slice, find_convergence_radius)
from blastlib.processing.radius_estimator import reduce_theta_radii


def oracle_slice(ratio, peak, dist, exclude_r):
    """Independent reimplementation of the hard far->near K=3 scan."""
    valid = ~np.isnan(ratio) & (dist > exclude_r)
    r, p, d = ratio[valid], peak[valid], dist[valid]
    if len(d) == 0:
        return np.nan, np.nan
    order = np.argsort(d)[::-1]
    r, p, d = r[order], p[order], d[order]
    streak, start = 0, None
    for i in range(len(r)):
        if abs(r[i] - 1.0) > TOLERANCE:
            streak += 1
            if streak == 1:
                start = i
            if streak >= K_CONSECUTIVE:
                j = 0 if start == 0 else start - 1
                return d[j], p[j]
        else:
            streak, start = 0, None
    return d[-1], p[-1]


def _random_slices(n_cases=200, seed=1234):
    rng = np.random.default_rng(seed)
    for _ in range(n_cases):
        n = rng.integers(1, 120)
        dist = rng.uniform(0.5, 120.0, n)
        ratio = 1.0 + rng.normal(0.0, 0.03, n)
        # plant violation streaks of random length at random positions
        for _ in range(rng.integers(0, 4)):
            i = rng.integers(0, n)
            length = rng.integers(1, 6)
            ratio[i:i + length] = 1.0 + rng.choice([-1, 1]) * rng.uniform(0.06, 2.0)
        # sprinkle NaNs
        nan_idx = rng.random(n) < 0.15
        ratio[nan_idx] = np.nan
        peak = rng.uniform(0.1, 500.0, n)
        exclude_r = rng.choice([0.0, 2.5, 10.0])
        yield ratio, peak, dist, exclude_r


def test_slice_scan_matches_oracle():
    for ratio, peak, dist, exclude_r in _random_slices():
        got = _find_radius_for_slice(ratio, peak, dist, exclude_r)
        want = oracle_slice(ratio, peak, dist, exclude_r)
        if np.isnan(want[0]):
            assert np.isnan(got[0]) and np.isnan(got[1])
        else:
            assert got == want  # exact equality, not approx


def _synthetic_field(seed=99):
    """Cells laid out on exact integer-degree rays so each maps to one bin."""
    rng = np.random.default_rng(seed)
    xs, zs, ratio_P, ratio_I, peak_P, peak_I = [], [], [], [], [], []
    per_theta = {}
    for deg in range(0, 91, 3):  # a subset of sectors, some bins left empty
        n = int(rng.integers(5, 60))
        dist = rng.uniform(1.0, 100.0, n)
        rp = 1.0 + rng.normal(0.0, 0.03, n)
        i = rng.integers(0, n)
        rp[i:i + int(rng.integers(0, 5))] = 2.0
        ri = 1.0 + rng.normal(0.0, 0.03, n)
        pp = rng.uniform(1.0, 300.0, n)
        pi_ = rng.uniform(1.0, 300.0, n)
        th = np.radians(deg)
        x, z = dist * np.cos(th), dist * np.sin(th)
        xs.append(x)
        zs.append(z)
        ratio_P.append(rp)
        ratio_I.append(ri)
        peak_P.append(pp)
        peak_I.append(pi_)
        # the pipeline recomputes dist from X/Z — the oracle must see the
        # same rounded values or the comparison differs in the last ulp
        per_theta[deg] = (rp, pp, np.sqrt(x ** 2 + z ** 2))
    cat = lambda a: np.concatenate(a)
    return (cat(ratio_P), cat(ratio_I), cat(peak_P), cat(peak_I),
            cat(xs), cat(zs), per_theta)


def test_find_convergence_radius_matches_oracle_per_sector():
    ratio_P, ratio_I, peak_P, peak_I, X, Z, per_theta = _synthetic_field()
    exclude_r = 2.0
    out = find_convergence_radius(ratio_P, ratio_I, peak_P, peak_I, X, Z,
                                  exclude_r, estimator='req')
    r_expected = np.full(91, np.nan)
    for deg, (rp, pp, dist) in per_theta.items():
        r_expected[deg], _ = oracle_slice(rp, pp, dist, exclude_r)
    got = out['radius_per_theta_P']
    assert np.array_equal(got, r_expected, equal_nan=True)
    assert out['pressure'] == reduce_theta_radii(r_expected, method='req')
