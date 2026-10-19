"""Z Bands (blastlib.processing.z_bands): the band, the cut and the four colour
classes, on synthetic data, plus one read-only check on a real config."""

import numpy as np
import pandas as pd
import pytest

from blastlib.processing import z_bands as zb


def test_parse_z_list():
    assert zb.parse_z_list('8, 2;4 4') == (2, 4, 8)
    for bad in ('', '0', '21', '2.5', 'a'):
        with pytest.raises(ValueError):
            zb.parse_z_list(bad)


def test_band_is_smallest_z_reached():
    # levels fall with Z (rows ascending Z); two sectors with different levels
    levels = np.array([[100.0, 200.0],      # Z1
                       [50.0, 80.0],        # Z2
                       [10.0, 20.0]])       # Z3
    values = np.array([150.0, 150.0, 60.0, 15.0, 5.0, np.nan])
    th = np.array([0, 1, 0, 1, 0, 0])
    assert list(zb.band_index(values, th, levels)) == [0, 1, 1, -1, -1, -2]


def test_cut_is_last_listed_z_inside_r_conv():
    rows = pd.DataFrame({'Z': [2, 4, 6, 8], 'beyond_P': [False, False, False, True],
                         'beyond_I': ['False', 'True', 'True', 'True']})
    assert zb.z_cut(rows, (2, 4, 8), 'P') == 4          # 6 not listed, 8 beyond
    assert zb.z_cut(rows, (2, 4, 6, 8), 'P') == 6
    assert zb.z_cut(rows, (2, 4), 'I') == 2             # string flags from a CSV
    assert zb.z_cut(rows, (4, 6), 'I') is None


def test_four_colour_classes():
    # bands 0,1 shown (n_shown = 2); band 2 lies past the cut
    band = np.array([0, 1, 2, -1, 2, -1, 0, -2])
    dist = np.array([5, 5, 5, 5, 50, 50, 50, 5.0])
    cat = zb.classify(band, dist, n_shown=2, r_conv=20.0)
    # band kept (also beyond R_conv) / below inside R_conv / white beyond / NaN
    assert list(cat[:7]) == [0, 1, 2, 2, 3, 3, 0]
    assert np.isnan(cat[7])


@pytest.mark.slow
def test_real_config_is_read_only(tmp_path):
    """One real config end to end: cut matches the table, nothing written."""
    from blastlib import paths
    from blastlib.config.parser import config_parser
    from blastlib.io.npz_store import load_processed_data
    from blastlib.processing.free_field import load_ff_lookup
    from conftest import _require_config

    name = 'config_19_det1_b30_s5_h4_w50'
    npz = _require_config(paths.RAW_NPZ_DIR, name)
    before = {p: p.stat().st_mtime for p in paths.TABLES_DIR.glob('*.csv')}
    proc, ok = load_processed_data(npz, name)
    cfg = config_parser(name)
    z = (2, 4, 6, 8, 12)
    for method in ('req_soft3', 'reqdir_soft3'):
        conv, maxr = zb.load_tables(method)
        lv = zb.band_levels(proc, cfg, method, load_ff_lookup(paths.FF_CSV), z_values=z)
        res = zb.compute(proc, cfg, name, z, method, lv, conv, maxr)
        rows = maxr[maxr.Config == name].set_index('Z')
        for t in 'PI':
            inside = [k for k in z if not rows.loc[k, f'beyond_{t}']]
            assert res[t]['z_cut'] == max(inside)
            assert res[t]['maxr_raw'] == (method == 'reqdir_soft3')
            assert res[t]['r_conv'] == pytest.approx(
                conv.set_index('ConfigName').loc[name, f'Radius{t}'])
            # D46: the domain's inner edge; for config_19 (b30 s5, W=50) the
            # binding condition is one urban period, 35 m
            assert res[t]['r_min'] == pytest.approx(35.0)
    after = {p: p.stat().st_mtime for p in paths.TABLES_DIR.glob('*.csv')}
    assert before == after
