"""The strip measurement: mask semantics, grid precedence, pinned goldens."""

import numpy as np
import pandas as pd
import pytest

from conftest import _require_config
from blastlib.config.parser import config_parser
from blastlib.io.npz_store import load_processed_data
from blastlib.street.strip import street_profile


def _empty_grids(processed, grids=(2, 3)):
    """Fill the unused resolutions with empty layers."""
    e = np.empty(0)
    for g in grids:
        processed.update({f'X{g}': e, f'Z{g}': e,
                          f'peakP{g}_orig': e, f'refP{g}': e})
    return processed


CFG = dict(det=2, bsize=10, swidth=4, height=15, weight=250)   # s/2 = 2.0


def test_mask_semantics_synthetic():
    # Ten valid cells in one bin, plus one violator of every mask clause.
    # Only the valid ten may be counted, and the slice value is exactly
    # mean(urban)/mean(ref) over them.
    x_ok = np.full(10, 0.7)
    u_ok = np.arange(1.0, 11.0)            # mean 5.5
    r_ok = np.full(10, 2.0)                # mean 2.0
    z_ok = np.linspace(0.0, 2.0, 10)       # Z bounds inclusive both ends
    bad = [                                # (x, z, u, ref) one clause each
        (0.7, 1.0, np.nan, 2.0),           # u not finite
        (0.7, 1.0, 0.0, 2.0),              # u not > 0
        (0.7, 1.0, 5.0, np.nan),           # ref not finite
        (0.7, 1.0, 5.0, 0.0),              # ref not > 0
        (0.7, -0.1, 5.0, 2.0),             # Z < 0
        (0.7, 2.1, 5.0, 2.0),              # Z > s/2
        (0.0, 1.0, 5.0, 2.0),              # X not > 0
    ]
    bx, bz, bu, br = (np.array(v) for v in zip(*bad))
    processed = _empty_grids(dict(
        X1=np.concatenate([x_ok, bx]), Z1=np.concatenate([z_ok, bz]),
        peakP1_orig=np.concatenate([u_ok, bu]),
        refP1=np.concatenate([r_ok, br])))
    prof = street_profile(processed, CFG, dr=0.5, rmax=1.5)
    assert len(prof) == 1
    row = prof.iloc[0]
    assert row.r == 0.75 and row.n == 10
    assert row.urban == 5.5 and row.free_field == 2.0
    assert row.ratio == 5.5 / 2.0          # exact — no tolerance


def test_min_cells_and_grid_precedence():
    # Grid 1 has only 7 cells in the bin (below MIN_CELLS_PER_BIN = 8), so
    # the bin falls through to grid 2; a second bin where grid 1 has 8
    # stays on grid 1 even though grid 2 covers it too.
    g1_x = np.concatenate([np.full(7, 0.25), np.full(8, 0.75)])
    g1 = dict(X1=g1_x, Z1=np.zeros_like(g1_x),
              peakP1_orig=np.full_like(g1_x, 1.0),
              refP1=np.ones_like(g1_x))
    g2_x = np.concatenate([np.full(10, 0.25), np.full(10, 0.75)])
    g1.update(X2=g2_x, Z2=np.zeros_like(g2_x),
              peakP2_orig=np.full_like(g2_x, 2.0),
              refP2=np.ones_like(g2_x))
    processed = _empty_grids(g1, grids=(3,))
    prof = street_profile(processed, CFG, dr=0.5, rmax=1.0)
    assert list(prof.urban) == [2.0, 1.0]   # bin 1 from grid 2, bin 2 grid 1
    assert list(prof.n) == [10, 8]


# Golden rows captured from the reference implementation (retired
# tools/pressure_profile/pressure_profile.py street_profile) on
# config_93_det2_b10_s5_h15_w250 at dr=0.5 — the gate-A contract. The new
# strip reproduced the reference bit-for-bit at capture time (2026-08-06);
# rel 1e-15 leaves room only for a numpy reduction-order change.
# 2026-09-30, D34: refP{g} now holds the FILLED reference, so free_field
# and ratio moved. Rows 0-198 by 1e-8..1e-7 relative (float64 fill in place
# of the float32 raw field); row 199 (r = 99.75 m, the fine-grid edge,
# where the raw fine reference is deficient, PHY-04) by +7.5% in
# free_field: 5.862224102020264 -> 6.304926104475472, ratio
# 1.3598606347465994 -> 1.2643776717289998. Urban columns unchanged.
GOLDEN_93 = {
    0: dict(r=0.25, n=51, urban=377154.05206418503, urban_p10=7078.6845703125,
            urban_p90=2892133.0, free_field=377180.80242800247,
            ratio=0.999929078140655),
    1: dict(r=0.75, n=68, urban=17128.971378102022, urban_p10=6909.70537109375,
            urban_p90=29139.434765625036, free_field=17221.385375976562,
            ratio=0.994633765178761),
    2: dict(r=1.25, n=51, urban=8465.987898284313, urban_p10=5536.59130859375,
            urban_p90=10814.54296875, free_field=8619.279181985294,
            ratio=0.9822153012491617),
    100: dict(r=50.25, n=68, urban=21.503369415507596,
              urban_p10=19.213640213012695, urban_p90=24.529907417297363,
              free_field=18.344323971692255, ratio=1.172208332598692),
    101: dict(r=50.75, n=51, urban=20.970911250394934,
              urban_p10=18.328617095947266, urban_p90=24.081554412841797,
              free_field=18.049666947009516, ratio=1.1618447759707506),
    198: dict(r=99.25, n=51, urban=8.471305304882573,
              urban_p10=8.244070053100586, urban_p90=8.701703071594238,
              free_field=6.654840871399524, ratio=1.2729538494736454),
    199: dict(r=99.75, n=68, urban=7.971807788400089,
              urban_p10=7.697517919540405, urban_p90=8.24845609664917,
              free_field=6.304926104475472, ratio=1.2643776717289998),
}


def test_strip_matches_historical(street_npz_dir):
    name = 'config_93_det2_b10_s5_h15_w250'
    proc, ok = load_processed_data(street_npz_dir, name)
    assert ok
    prof = street_profile(proc, config_parser(name), dr=0.5)
    assert prof.shape == (200, 7)
    for idx, want in GOLDEN_93.items():
        row = prof.iloc[idx]
        assert int(row.n) == want['n']
        for col in ('r', 'urban', 'urban_p10', 'urban_p90', 'free_field',
                    'ratio'):
            assert row[col] == pytest.approx(want[col], rel=1e-15), \
                f'row {idx} col {col}'
