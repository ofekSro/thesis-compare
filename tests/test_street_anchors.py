"""The anchor triplet: synthetic recovery, guard contracts, pinned goldens."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conftest import PROJECT_ROOT
from blastlib import paths
from blastlib.street.anchors import detector_start, measure_all, \
    measure_profile

sys.path.insert(0, str(PROJECT_ROOT / 'tools' / 'validate_migration'))
from compare_outputs import compare_csv                      # noqa: E402

CFG = dict(det=2, bsize=10, swidth=5, height=15, weight=250)
# det2: exclude_radius = s/2 = 2.5, detector_start = s/2 + b = 12.5


def _profile(E, dr=0.5):
    r = np.arange(dr / 2, 100.0, dr)
    return pd.DataFrame({'r': r, 'ratio': E(r)})


def test_synthetic_exponential_recovery():
    # A pure exponential excess: the boxcar smoother multiplies it by a
    # constant (mean of exp over a symmetric window), so ln(excess) stays
    # exactly linear in r and the OLS must recover L to float precision.
    L = 15.0
    prof = _profile(lambda r: 1 + 2.0 * np.exp(-r / L))
    out = measure_profile(prof, CFG, dr=0.5)
    assert out['L_decay'] == pytest.approx(L, rel=1e-9)
    assert out['R_half_slope'] == pytest.approx(
        out['R_peak'] + np.log(2.0) * L, rel=1e-12)
    assert out['n_fit'] >= 6 and out['span_fit'] >= 4.0


def test_floor_no_decay():
    # Peak excess below FLOOR-1 = 0.2: R_peak/E_peak are reported, every
    # decay field stays NaN — the b10_s12 "never channels" contract.
    prof = _profile(lambda r: 1 + 0.15 * np.exp(-r / 20.0))
    out = measure_profile(prof, CFG, dr=0.5)
    assert np.isfinite(out['R_peak']) and np.isfinite(out['E_peak'])
    assert np.isnan(out['L_decay']) and np.isnan(out['R_half_slope'])
    assert out['n_fit'] == 0 and out['span_fit'] == 0.0


def test_min_span_guard():
    # A fall so steep the 0.85->0.25 window spans under 4 m: NaN, honestly
    # (a slope from two block faces is not a decay measurement).
    prof = _profile(lambda r: 1 + 2.0 * np.exp(-np.maximum(r - 13, 0) / 0.8))
    out = measure_profile(prof, CFG, dr=0.5)
    assert np.isnan(out['L_decay'])


def test_positive_slope_guard():
    # Excess that drops below the window top and then RISES: the fitted
    # slope is positive and the anchor must refuse (slope >= 0 -> NaN).
    def E(r):
        out = np.full_like(r, 1.5)
        out[r < 14] = 2.0                      # peak region past start=12.5
        rise = r >= 14
        out[rise] = 1.5 + 0.004 * (r[rise] - 14)
        return out
    out = measure_profile(_profile(E), CFG, dr=0.5)
    assert np.isnan(out['L_decay'])


# config_93 goldens captured from the reference at both slice widths
# (2026-08-06). NOTE what the pair documents: on THIS config the slope
# anchor moves 6.2% between 0.5 m and 2 m slices while the crossing moves
# 1.8% — an above-median config (the medians over all 96 are 1.7% for the
# slope fit vs 19.6% for the crossing; the full-data test below checks the
# median claim). At dr=2 the kernel quirk (Q3) disables smoothing, so the
# 2 m number is a RAW slope fit by construction.
GOLDEN_93 = {
    0.5: dict(R_peak=14.75, E_peak=2.1382381088898073,
              L_decay=21.69532474629278, R_half_slope=29.78805317922525,
              R_half_cross=42.25, n_fit=36, span_fit=17.5),
    2.0: dict(R_peak=15.0, E_peak=2.1510517261644613,
              L_decay=23.982629069734468, R_half_slope=31.62349172210143,
              R_half_cross=43.0, n_fit=13, span_fit=24.0),
}


def test_slope_anchor_goldens_both_widths(street_npz_dir):
    from blastlib.config.parser import config_parser
    from blastlib.io.npz_store import load_processed_data
    from blastlib.street.strip import street_profile

    name = 'config_93_det2_b10_s5_h15_w250'
    proc, ok = load_processed_data(street_npz_dir, name)
    assert ok
    cfg = config_parser(name)
    for dr, want in GOLDEN_93.items():
        prof = street_profile(proc, cfg, dr=dr)
        out = measure_profile(prof, cfg, dr)
        for k, v in want.items():
            assert out[k] == pytest.approx(v, rel=1e-12), f'dr={dr} {k}'
    ratio = GOLDEN_93[2.0]['R_half_slope'] / GOLDEN_93[0.5]['R_half_slope']
    assert abs(ratio - 1) < 0.08              # the 6.2%, frozen


def test_detector_start():
    assert detector_start(dict(det=1, bsize=15, swidth=5)) == 20
    assert detector_start(dict(det=2, bsize=15, swidth=5)) == 17.5


@pytest.mark.slow
def test_anchor_stability_median_all_configs(street_full_data):
    # THE stability contract that killed the crossing detector: re-measure
    # every config at 2 m slices and compare decay lengths. The slope fit's
    # median move is ~1.7% (crossing: ~19.6%); lock it below 3%.
    a05 = measure_all(npz_dir=street_full_data, dr=0.5,
                      progress=lambda _m: None)
    a20 = measure_all(npz_dir=street_full_data, dr=2.0,
                      progress=lambda _m: None)
    m = pd.merge(a05, a20, on='cfg', suffixes=('_05', '_20'))
    both = m.dropna(subset=['L_decay_05', 'L_decay_20'])
    assert len(both) >= 60                    # most fitted decays survive
    shift = np.abs(both.L_decay_20 / both.L_decay_05 - 1)
    assert float(np.median(shift)) < 0.03


@pytest.mark.slow
def test_anchors_match_pinned(street_full_data, street_anchors_csv,
                              tmp_path):
    out_csv = tmp_path / 'street_anchors.csv'
    df = measure_all(npz_dir=street_full_data, out_csv=out_csv,
                     progress=lambda _m: None)
    status, detail = compare_csv(street_anchors_csv, out_csv,
                                 rtol=1e-12, atol=1e-12)
    assert status == 'PASS', detail
    assert int(df.L_decay.isna().sum()) == 21
