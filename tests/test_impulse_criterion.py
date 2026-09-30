"""The production impulse criterion (DECISIONS.md D35 (c)) on synthetic values.

    |I / I_ff - 1| <= 0.10   or   I / W^(1/3) < 23.6 Pa.s/kg^(1/3)

No data needed. W = 1000 kg gives W^(1/3) = 10 exactly, so the floor sits at
236 Pa.s; W = 125 kg gives 5, floor 118 Pa.s.
"""

import numpy as np

from blastlib import constants
from blastlib.processing.ff_reference import (impulse_converged,
                                              impulse_converged_pfloor)


def test_constants_hold_the_d35_values():
    assert constants.IMPULSE_CRITERION['rel_band'] == 0.10
    assert constants.IMPULSE_CRITERION['floor_scaled'] == 23.6


def test_band_clause_above_the_floor():
    """I = 500 Pa.s is far above the floor (236 at W13 = 10): only the band decides."""
    ref = np.full(5, 500.0)
    I = np.array([500.0, 549.0, 451.0, 560.0, 440.0])
    assert impulse_converged(I, ref, 10.0).tolist() == [True, True, True, False, False]


def test_band_is_two_sided():
    """Amplification and attenuation just inside 10% pass, just outside fail."""
    ref = np.full(4, 400.0)
    I = np.array([439.6, 360.4, 440.4, 359.6])
    assert impulse_converged(I, ref, 10.0).tolist() == [True, True, False, False]


def test_floor_clause_ignores_the_band():
    """Below 23.6 W^(1/3) a cell converges at any urban/reference ratio."""
    ref = np.array([50.0, 50.0])
    I = np.array([235.0, 237.0])          # ratio 4.7: the band fails
    assert impulse_converged(I, ref, 10.0).tolist() == [True, False]


def test_floor_scales_with_w_cube_root():
    """The same impulse is below the floor for W13 = 10 and above it for W13 = 5."""
    I, ref = np.array([200.0]), np.array([20.0])
    assert impulse_converged(I, ref, 10.0)[0]        # 20.0 < 23.6
    assert not impulse_converged(I, ref, 5.0)[0]     # 40.0 > 23.6
    # Scaled impulse is what matters: I and W13 scaled together, same answer.
    for k in (0.5, 2.0, 7.0):
        assert impulse_converged(I * k, ref * k, 10.0 * k)[0]


def test_non_positive_reference_converges_only_through_the_floor():
    ref = np.array([0.0, 0.0, -1.0])
    I = np.array([100.0, 300.0, 100.0])
    assert impulse_converged(I, ref, 10.0).tolist() == [True, False, True]


def test_nan_never_converges():
    out = impulse_converged(np.array([np.nan, 100.0]), np.array([100.0, np.nan]), 10.0)
    assert out.tolist() == [False, True]      # second: NaN band, but 10 < 23.6


def test_d24_rule_kept_as_historical_function():
    """impulse_converged_pfloor reproduces D24: strict band OR the pressure mask."""
    ref = np.array([100.0, 100.0, 100.0])
    I = np.array([109.0, 150.0, 150.0])
    lowP = np.array([False, False, True])
    assert impulse_converged_pfloor(I, ref, lowP).tolist() == [True, False, True]
