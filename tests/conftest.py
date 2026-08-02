"""Shared test setup: make the project root importable, expose npz dirs.

The npz data folders are gitignored, so any test that needs them must skip
cleanly on a checkout without data (use the fixtures below).
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from blastlib import paths  # noqa: E402  (needs the sys.path line above)

NPZ_V2_DIR = paths.DATA_DIR / 'processed_npz_v2'


def _require_config(npz_dir, config_name):
    npz_file = Path(npz_dir) / f'{config_name}.npz'
    if not npz_file.exists():
        pytest.skip(f'missing data file: {npz_file}')
    return npz_dir


@pytest.fixture
def npz_v1_dir():
    """data/processed_npz (shipped v1), skipping when absent."""
    return _require_config(paths.PROCESSED_NPZ_DIR, 'config_93_det2_b10_s5_h15_w250')


@pytest.fixture
def npz_v2_dir():
    """data/processed_npz_v2 (raw-field superset), skipping when absent."""
    return _require_config(NPZ_V2_DIR, 'config_93_det2_b10_s5_h15_w250')
