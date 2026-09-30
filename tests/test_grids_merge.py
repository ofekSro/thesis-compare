"""The grid merge on a synthetic 3-grid case (DECISIONS.md D34).

No data needed. Each grid holds constant fields, so the linear resampling in
the max-fill is exact and every expected value can be written by hand:

    grid 1 (fine)   cells 1 m,   0.5 .. 9.5 m    urban 60, reference 55
    grid 2 (medium) cells 2.5 m, 1.25 .. 48.75 m urban 40, reference 20
    grid 3 (coarse) cells 5 m,   2.5 .. 97.5 m   urban 30, reference 15

Planted in grid 1: one building cell (raw == 0.001 kPa sentinel) and one
empty cell (raw == 0, the fine urban stage ended before the wave arrived,
while the fine reference stage did see it). Planted in grid 2, outside the
fine box: a 2x2 building block. Each planted cell is the nearest finer cell
of some coarser cell, which is where the old cut re-admitted the coarser
grid (docs/audit/2026-09-30/merge.md MRG-01/02).
"""

import numpy as np
import pytest

from blastlib.processing.grids import building_mask, process_grids

PARAMS = {'minPressure_kPa': 10.0, 'thresholdP_kPa': 1.01e-3}
W = 250.0
BUILDING = (3, 3)   # (row = Z index, column = X index) in grid 1: 3.5 m,
EMPTY = (6, 6)      # nearest to medium 3.75 m; 6.5 m, nearest to medium 6.25 m
BUILDING2 = (slice(6, 8), slice(6, 8))   # grid 2, 16.25-18.75 m, under coarse 17.5 m


def _grid(x0, dx, n):
    x = x0 + dx * np.arange(n)
    return np.meshgrid(x, x)


def _data(dtype=np.float32):
    d = {}
    for g, (x0, dx, n, P, R) in {'1': (0.5, 1.0, 10, 60.0, 55.0),
                                 '2': (1.25, 2.5, 20, 40.0, 20.0),
                                 '3': (2.5, 5.0, 20, 30.0, 15.0)}.items():
        X, Z = _grid(x0, dx, n)
        d[f'X{g}'], d[f'Z{g}'] = X, Z
        d[f'peakP{g}'] = np.full(X.shape, P, dtype=dtype)
        d[f'impulse{g}'] = np.full(X.shape, 2 * P, dtype=dtype)
        d[f'refP{g}'] = np.full(X.shape, R, dtype=dtype)
        d[f'refI{g}'] = np.full(X.shape, 2 * R, dtype=dtype)
    d['peakP1'][BUILDING] = np.float32(0.001)
    d['impulse1'][BUILDING] = np.float32(0.001)
    d['peakP1'][EMPTY] = 0.0
    d['impulse1'][EMPTY] = 0.0
    d['peakP2'][BUILDING2] = np.float32(0.001)
    d['impulse2'][BUILDING2] = np.float32(0.001)
    return d


@pytest.fixture
def out():
    return process_grids(_data(), PARAMS, weight=W)


def test_building_cell_is_masked(out):
    for key in ('peakP1_orig', 'impulse1_orig', 'ratioP1', 'ratioI1',
                'ratioP1_raw', 'ratioI1_raw'):
        assert np.isnan(out[key][BUILDING]), key
    # Only that one cell: a fine grid with one building loses one cell.
    assert np.isnan(out['peakP1_orig']).sum() == 1


def test_empty_cell_keeps_the_filled_value(out):
    """raw == 0 is not a building: the medium value (40) is the true peak."""
    assert out['peakP1_orig'][EMPTY] == pytest.approx(40.0)
    assert out['impulse1_orig'][EMPTY] == pytest.approx(80.0)
    # Against the fine reference, which did see the wave (55), not the
    # medium one (20): 40/55, not 40/20.
    assert out['ratioP1_raw'][EMPTY] == pytest.approx(40.0 / 55.0)


def test_criteria_act_on_filled_fields(out):
    """|40 - 55| = 15 kPa > 10 and 40 > 10: not converged, so not pinned.

    On the raw urban value (0 < 10 kPa floor) the same cell would have been
    pinned to 1. The ordinary fine cells, |60 - 55| < 10, are pinned.
    """
    assert out['ratioP1'][EMPTY] == pytest.approx(40.0 / 55.0)
    assert out['peakP1_raw'][EMPTY] == pytest.approx(40.0)
    assert out['refP1'][EMPTY] == pytest.approx(55.0)
    assert out['ratioP1'][0, 0] == 1.0
    # Impulse (D35): |80/110 - 1| = 27% > 10%, but 80 / 250^(1/3) = 12.7 is
    # below the 23.6 Pa.s/kg^(1/3) floor, so the cell is pinned. Under D24
    # (pressure floor, P = 40 > 10) it stayed at 80/110. The unforced ratio
    # is still the filled one.
    assert out['ratioI1'][EMPTY] == 1.0
    assert out['ratioI1_raw'][EMPTY] == pytest.approx(80.0 / 110.0)


@pytest.mark.parametrize('fine, coarse', [('1', '2'), ('2', '3')])
def test_no_coarse_cell_inside_a_finer_box(out, fine, coarse):
    """Every coarser cell inside the finer box is cut, including those over
    finer building and empty cells; outside it every non-building cell stays."""
    inside = ((out[f'X{coarse}'] <= out[f'X{fine}'].max())
              & (out[f'Z{coarse}'] <= out[f'Z{fine}'].max()))
    keep = ~inside & ~building_mask(_data()[f'peakP{coarse}'])
    assert inside.any() and keep.any()
    for key in ('peakP{}_orig', 'impulse{}_orig', 'ratioP{}', 'ratioI{}',
                'ratioP{}_raw', 'ratioI{}_raw'):
        arr = out[key.format(coarse)]
        assert np.isnan(arr[inside]).all(), key
        assert np.isfinite(arr[keep]).all(), key


def test_scan_arrays_hold_each_location_once(out):
    """peakP_all / peakI_all carry the cut too: 99 fine + 380 medium + 300 coarse."""
    n1 = 10 * 10 - 1              # minus the building
    n2 = 20 * 20 - 4 * 4 - 4      # minus the fine box and the building block
    n3 = 20 * 20 - 10 * 10        # minus the medium box
    assert np.isfinite(out['peakP_all']).sum() == n1 + n2 + n3
    assert np.isfinite(out['peakI_all']).sum() == n1 + n2 + n3


def test_max_fill_and_reference_fill_are_separate(out):
    """Urban and reference are filled independently: the medium grid takes
    max(40, 30) and max(20, 15), never a mix of the two runs."""
    outside = ~((out['X2'] <= out['X1'].max()) & (out['Z2'] <= out['Z1'].max()))
    outside &= ~building_mask(_data()['peakP2'])
    assert np.allclose(out['peakP2_orig'][outside], 40.0)
    assert np.allclose(out['refP2_fill'], 20.0)
    assert np.allclose(out['refP1_fill'], 55.0)


def test_building_mask_is_exact_and_dtype_independent():
    raw = np.array([0.0, 0.001, 0.0010001, 4.1e-4, 1.01e-3, 12.0],
                   dtype=np.float32)
    expected = [False, True, False, False, False, False]
    assert building_mask(raw).tolist() == expected
    assert building_mask(raw.astype(np.float64)).tolist() == expected


def test_float64_input_gives_the_same_merge():
    a = process_grids(_data(np.float32), PARAMS, weight=W)
    b = process_grids(_data(np.float64), PARAMS, weight=W)
    for key in ('ratioP1', 'ratioI1', 'ratioP2', 'ratioP3', 'peakP_all'):
        assert np.array_equal(np.isnan(a[key]), np.isnan(b[key])), key
        assert np.allclose(a[key], b[key], equal_nan=True), key
