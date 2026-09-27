"""The v3 raw store must be a lossless re-encoding of the processed stores.

The whole point of moving the criteria out of preprocessing is that nothing
downstream changes. These tests pin that: a v3 file expanded through
process_grids() must reproduce the shipped v2 arrays exactly — not
approximately — and the criteria must actually be re-applicable at load time.
"""

import numpy as np
import pytest

from blastlib import constants
from blastlib.config.parser import config_parser
from blastlib.io import raw_store
from blastlib.io.npz_store import load_processed_data
from blastlib.io.vtk_reader import cell_coords

from conftest import NPZ_V2_DIR, _require_config

CONFIG = 'config_93_det2_b10_s5_h15_w250'


@pytest.fixture
def raw_dir():
    """data/raw_npz (v3 store), skipping when absent."""
    from blastlib import paths
    return _require_config(paths.RAW_NPZ_DIR, CONFIG)


@pytest.fixture
def raw(raw_dir):
    payload, ok = raw_store.load_raw_data(raw_dir, CONFIG)
    assert ok, 'raw store present but incomplete'
    return payload


def test_detected_as_raw(raw_dir):
    assert raw_store.is_raw_dir(raw_dir)
    assert not raw_store.is_raw_dir(NPZ_V2_DIR)


def test_expansion_matches_shipped_v2_bit_for_bit(raw_dir):
    """Criterion-independent arrays a v3 file yields equal the v2 file's.

    Until 2026-09-27 this test required FULL bit equality with the shipped
    v2 store. The raw-field building mask adopted then (docs/audit/
    2026-09-27, ALG-01/PHY-01, decision D2b) deliberately changes every
    masked/pinned array relative to v2, whose criteria were baked at write
    time with the old merged-field mask — so full equality is no longer the
    contract. What must still hold, exactly:
      * v3 yields a superset of v2's keys (new ref*_fill keys are additive);
      * every criterion-INDEPENDENT array is bit-identical: coordinates,
        the raw reference fields, and the raw pressure peaks.
    The criterion-dependent arrays are pinned by tests/test_npz_anchors.py
    (raw-store anchors) instead.
    """
    _require_config(NPZ_V2_DIR, CONFIG)
    from_raw, ok_raw = load_processed_data(raw_dir, CONFIG)
    from_v2, ok_v2 = load_processed_data(NPZ_V2_DIR, CONFIG)
    assert ok_raw and ok_v2

    missing = set(from_v2) - set(from_raw)
    assert not missing, f'v3 lost keys the v2 store had: {sorted(missing)}'

    criterion_free = (['X1', 'Z1', 'X2', 'Z2', 'X3', 'Z3']
                      + [f'refP{g}' for g in '123']
                      + [f'refI{g}' for g in '123']
                      + [f'peakP{g}_raw' for g in '123'])
    mismatched = []
    for key in criterion_free:
        a = np.asarray(from_raw[key])
        b = np.asarray(from_v2[key])
        if a.shape != b.shape or not np.array_equal(a, b, equal_nan=True):
            mismatched.append(key)
    assert not mismatched, f'differs from the v2 store: {mismatched}'


def test_coordinates_rebuilt_exactly(raw, raw_dir):
    """X/Z are not stored; rebuilding them must be exact, not close."""
    _require_config(NPZ_V2_DIR, CONFIG)
    from_v2, _ = load_processed_data(NPZ_V2_DIR, CONFIG)
    for g in raw_store.LEVELS:
        X, Z = cell_coords(raw[f'origin{g}'], raw[f'spacing{g}'],
                           [int(v) for v in raw[f'dims{g}']])
        assert np.array_equal(X, from_v2[f'X{g}'])
        assert np.array_equal(Z, from_v2[f'Z{g}'])


def test_config_metadata_matches_the_name(raw):
    """The stored scalars must agree with parsing the filename."""
    parsed = config_parser(CONFIG)
    stored = raw_store.config_from_raw(raw)
    for key in raw_store.META_KEYS:
        assert stored[key] == parsed[key], key


def test_criteria_are_applied_at_load_not_baked_in(raw):
    """A different threshold must actually change the result.

    This is the property the v1/v2 stores did not have. If expansion ignored
    *params* the two calls below would be identical, and the whole point of
    the raw store would be lost.
    """
    base = raw_store.expand(raw)
    params = dict(constants.PARAMS)
    params['minPressure_kPa'] = 2.0 * constants.PARAMS['minPressure_kPa']
    altered = raw_store.expand(raw, params=params)

    a, b = base['ratioP1'], altered['ratioP1']
    differing = np.sum(~np.isclose(a, b, equal_nan=True))
    assert differing > 0, 'changing the pressure band changed nothing'


def test_raw_impulse_is_recoverable(raw):
    """The urban impulse must survive unprocessed — the v2 gap this closes.

    v2 stored only impulse{g}_orig (filled, masked, cut), so the impulse
    convergence criterion could not be re-derived from it at all.
    """
    for g in raw_store.LEVELS:
        arr = np.asarray(raw[f'impulse{g}'])
        assert arr.dtype == np.float32
        assert np.isfinite(arr).any()
        # Nothing has been NaN-masked in the store.
        assert not np.isnan(arr).any()
