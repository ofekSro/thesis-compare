"""The smoothing quirks (conventions.py Q2-Q4), asserted, not assumed."""

import numpy as np
import pytest

from blastlib.street import conventions


def _kernel_width(dr):
    """Reproduce the width arithmetic to compare against behaviour."""
    k = max(1, int(round(2.5 / dr)))
    if k % 2 == 0:
        k -= 1
    return k


def test_kernel_width_quirk():
    # Q3: banker's rounding + odd-forcing silently disables smoothing at
    # coarse slice widths. dr=1.0: round(2.5) = 2 (ties-to-even), forced
    # odd -> 1. dr=2.0: round(1.25) = 1. Only dr=0.5 smooths in practice.
    assert _kernel_width(0.5) == 5
    assert _kernel_width(1.0) == 1
    assert _kernel_width(2.0) == 1
    a = np.array([1.0, 5.0, 1.0, 5.0, 1.0, 5.0, 1.0])
    assert np.array_equal(conventions.smooth_physical(a, 1.0), a)
    assert np.array_equal(conventions.smooth_physical(a, 2.0), a)
    assert not np.array_equal(conventions.smooth_physical(a, 0.5), a)


def test_edges_raw_interior_boxcar():
    # Q4: the first/last k//2 outputs are the RAW input (never the
    # zero-padded 'same' taper); interior samples are the exact k-mean.
    a = np.arange(10, dtype=float) ** 2
    s = conventions.boxcar_raw_edges(a, 5)
    assert np.array_equal(s[:2], a[:2])
    assert np.array_equal(s[-2:], a[-2:])
    for i in range(2, 8):
        assert s[i] == pytest.approx(np.mean(a[i - 2:i + 3]), rel=1e-15)


def test_fixed_k5_equals_physical_at_half_metre_only():
    # Q2: the validation smoother (fixed k=5) coincides with the physical
    # 2.5 m smoother at dr=0.5 and ONLY there.
    rng = np.random.default_rng(20260806)
    a = 1 + rng.random(60)
    assert np.array_equal(conventions.smooth_fixed(a),
                          conventions.smooth_physical(a, 0.5))
    assert not np.array_equal(conventions.smooth_fixed(a),
                              conventions.smooth_physical(a, 1.0))


def test_k1_is_identity_copy():
    a = np.array([3.0, 1.0, 4.0])
    out = conventions.boxcar_raw_edges(a, 1)
    assert np.array_equal(out, a)
