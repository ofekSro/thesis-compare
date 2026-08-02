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


def _radius_p(npz_dir, config_name):
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
    return radius['pressure']


@pytest.mark.parametrize('config_name', sorted(ANCHORS))
def test_shipped_radius_p_v1(npz_v1_dir, config_name):
    assert _radius_p(npz_v1_dir, config_name) == pytest.approx(
        ANCHORS[config_name], rel=1e-9)


@pytest.mark.parametrize('config_name', sorted(ANCHORS))
def test_shipped_radius_p_v2(npz_v2_dir, config_name):
    """The v2 superset npz must reproduce the same hard radii bit-for-bit."""
    assert _radius_p(npz_v2_dir, config_name) == ANCHORS[config_name]
