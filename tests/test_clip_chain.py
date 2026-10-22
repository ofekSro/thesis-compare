"""clip_z_urban_pred is the user's chain at the predicted R_conv (D49, D50).

Synthetic coefficients give Z_conv_hat = 10 exactly, so rows can sit just
inside, exactly on and just beyond R_conv_hat. No data needed.
"""

import numpy as np
import pandas as pd
import pytest

from blastlib.regression.z_urban import clip_z_urban_pred

Z_CONV = 10.0
W = 500.0
EPS = 1e-6
CONV_P = {1: {'C0': Z_CONV, 'C1': 0.0, 'C2': 0.0, 'C3': 0.0, 'a': 1.0,
              'has_H_term': True}, 2: None}
CONV_I = {1: {'A': Z_CONV, 'p': 0.0, 'q': 0.0, 'r': 0.0, 'r2': 0.0}, 2: None}
Z_FREE = np.array([5.0, Z_CONV * (1 - EPS), Z_CONV, Z_CONV * (1 + EPS), 20.0])


def _rows(with_r_free=True):
    df = pd.DataFrame({'weight': W, 'rho': 0.5, 'height': 12.0, 'swidth': 10.0,
                       'bsize': 20.0, 'Z_free': Z_FREE})
    if with_r_free:
        df['R_free'] = df['Z_free'] * W ** (1 / 3)
    return df


@pytest.mark.parametrize('target', ['Pressure', 'Impulse'])
def test_amplifying_prediction_is_clipped_inside_and_identity_from_the_boundary(target):
    lam = 1.3
    out = clip_z_urban_pred(lam * Z_FREE, _rows(), 1, target, CONV_P, CONV_I)
    assert out[0] == pytest.approx(lam * 5.0)              # inside, below the clip
    assert out[1] == pytest.approx(Z_CONV)                  # inside, clipped at Z_conv
    assert out[2] == pytest.approx(Z_CONV)                  # on R_conv: identity
    assert out[3] == pytest.approx(Z_CONV * (1 + EPS))      # just beyond: identity
    assert out[4] == pytest.approx(20.0)                    # far beyond: identity
    # Continuous and non-decreasing across the boundary.
    assert np.all(np.diff(out) >= 0)
    assert abs(out[3] - out[1]) < 1e-4


@pytest.mark.parametrize('target', ['Pressure', 'Impulse'])
def test_attenuating_prediction_is_kept_inside_and_identity_beyond(target):
    lam = 0.8
    out = clip_z_urban_pred(lam * Z_FREE, _rows(), 1, target, CONV_P, CONV_I)
    assert out[0] == pytest.approx(lam * 5.0)
    assert out[1] == pytest.approx(lam * Z_CONV * (1 - EPS))
    assert out[2:] == pytest.approx(Z_FREE[2:])


@pytest.mark.parametrize('lam, clipped', [
    (1.3, [False, True, False, False, False]),     # only the inside row is a clip
    (0.8, [False, False, False, False, False]),    # nothing is lowered inside
])
def test_flags_mark_a_real_clip_only_and_identity_separately(lam, clipped):
    out, was_clipped, identity = clip_z_urban_pred(
        lam * Z_FREE, _rows(), 1, 'Impulse', CONV_P, CONV_I, return_flags=True)
    assert np.array_equal(out, clip_z_urban_pred(lam * Z_FREE, _rows(), 1, 'Impulse',
                                                 CONV_P, CONV_I))
    assert was_clipped.tolist() == clipped
    assert identity.tolist() == [False, False, True, True, True]
    assert not np.any(was_clipped & identity)


def test_r_free_recomputed_when_column_absent():
    a = clip_z_urban_pred(1.3 * Z_FREE, _rows(True), 1, 'Pressure', CONV_P, CONV_I)
    b = clip_z_urban_pred(1.3 * Z_FREE, _rows(False), 1, 'Pressure', CONV_P, CONV_I)
    assert np.array_equal(a, b)


def test_no_op_without_coefficients_or_finite_r_conv():
    pred = 1.3 * Z_FREE
    assert np.array_equal(clip_z_urban_pred(pred, _rows(), 1, 'Impulse', CONV_P, None), pred)
    # det 2 has no fitted group -> R_conv_hat is NaN -> prediction untouched
    assert np.array_equal(clip_z_urban_pred(pred, _rows(), 2, 'Pressure', CONV_P, CONV_I), pred)
