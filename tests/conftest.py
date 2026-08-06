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


def pytest_configure(config):
    config.addinivalue_line(
        'markers', 'slow: full-data sweeps (all 96 configs); skipped '
        'automatically when the data stores are absent')

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


@pytest.fixture
def street_npz_dir():
    """The store the street suite reads (v3-raw preferred), skipping when
    the anchor test config is absent."""
    return _require_config(paths.default_npz_dir(soft=True),
                           'config_93_det2_b10_s5_h15_w250')


@pytest.fixture(scope='session')
def street_full_data():
    """The street store with ALL 96 configs — parity tests only.

    Session-scoped: the slow tests each sweep the full store; one skip
    decision serves them all.
    """
    d = Path(paths.default_npz_dir(soft=True))
    n = len(list(d.glob('config_*.npz'))) if d.is_dir() else 0
    if n < 96:
        pytest.skip(f'street parity needs all 96 configs, found {n} in {d}')
    return d


@pytest.fixture
def street_anchors_csv():
    """The pinned anchors table (tracked since snapshot bf8eefe)."""
    p = paths.CHECK_RESULTS_DIR / 'street_anchors.csv'
    if not p.exists():
        pytest.skip(f'missing pinned table: {p}')
    return p
