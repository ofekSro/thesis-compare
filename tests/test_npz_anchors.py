"""Anchor tests: the hard (legacy) pipeline must reproduce the shipped
RadiusP values for config_93 and config_95 (method='req').

The chain below replicates run_analysis.run_phase1 per-config computation
exactly: config_parser -> load_processed_data -> exclude_radius -> concat3 ->
find_convergence_radius(estimator='req').
"""

import pytest

from blastlib.config.parser import config_parser
from blastlib.geometry import concat3, exclude_radius
from blastlib.io.npz_store import load_processed_data
from blastlib.processing.convergence import find_convergence_radius

ANCHORS = {
    'config_93_det2_b10_s5_h15_w250': 62.328853560057645,
    'config_95_det2_b10_s5_h24_w250': 38.15139013777145,
}

# Raw (v3) store under the RAW-FIELD building mask (2026-09-27, D2b) and
# the production impulse criterion (2026-09-28 evening: accurate to 10%
# OR urban peak P below the 10 kPa relevance floor; see
# constants.IMPULSE_CRITERION and docs/audit/2026-09-28/physics.md). The
# v1/v2 anchors above keep guarding the OLD baked-in criterion (those
# stores load verbatim); these guard the current measurement, pressure
# and impulse. Pressure has been anchor-stable through every impulse
# criterion change. Previous impulse anchors: scaled band
# 68.1610404157357 / 64.22452586218307; impulse-floor rule (one run)
# 133.187531219038 / 141.36036347261955.
# 2026-09-29, D31 (coarse grid no longer re-enters the fine box): previous
# anchors (64.6464183290751, 96.17837472056225) and
# (39.930952732324215, 89.06562858052732).
RAW_ANCHORS = {
    'config_93_det2_b10_s5_h15_w250': (65.03267245093893, 96.78493203719493),
    'config_95_det2_b10_s5_h24_w250': (40.48961749634096, 89.36129957152096),
}


def _radii(npz_dir, config_name):
    cfg = config_parser(config_name)
    processed, ok = load_processed_data(npz_dir, config_name)
    assert ok, f'failed to load {config_name} from {npz_dir}'

    radius = find_convergence_radius(
        concat3(processed, 'ratioP{}'),
        concat3(processed, 'ratioI{}'),
        processed['peakP_all'],
        processed['peakI_all'],
        concat3(processed, 'X{}'),
        concat3(processed, 'Z{}'),
        exclude_radius(cfg),
        estimator='req',
    )
    return radius['pressure'], radius['impulse']


def _radius_p(npz_dir, config_name):
    return _radii(npz_dir, config_name)[0]


@pytest.mark.parametrize('config_name', sorted(ANCHORS))
def test_shipped_radius_p_v1(npz_v1_dir, config_name):
    assert _radius_p(npz_v1_dir, config_name) == pytest.approx(
        ANCHORS[config_name], rel=1e-9)


@pytest.mark.parametrize('config_name', sorted(ANCHORS))
def test_shipped_radius_p_v2(npz_v2_dir, config_name):
    """The v2 superset npz must reproduce the same hard radii bit-for-bit."""
    assert _radius_p(npz_v2_dir, config_name) == ANCHORS[config_name]


@pytest.fixture
def raw_npz_dir():
    from blastlib import paths
    from conftest import _require_config
    return _require_config(paths.RAW_NPZ_DIR, sorted(RAW_ANCHORS)[0])


@pytest.mark.parametrize('config_name', sorted(RAW_ANCHORS))
def test_raw_store_radii(raw_npz_dir, config_name):
    """The raw store under the raw-field mask reproduces both radii exactly."""
    p, i = _radii(raw_npz_dir, config_name)
    anchor_p, anchor_i = RAW_ANCHORS[config_name]
    assert p == pytest.approx(anchor_p, rel=1e-12)
    assert i == pytest.approx(anchor_i, rel=1e-12)
