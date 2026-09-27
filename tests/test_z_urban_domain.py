"""The Z_urban fit domain is the domain the model is used on.

z_urban_valid_mask enforces four conditions; each is tested in isolation by
starting from a row that satisfies all four and breaking exactly one. Table
driven, so adding a condition without a test is visible.
"""

import numpy as np
import pandas as pd
import pytest

from blastlib.regression.z_urban import (
    Z_URBAN_ZF_MIN, prepare_maxR_data, z_urban_valid_mask,
)

ARGS = {'Pressure': ('Z_urban_P', 'MaxR_P', 'RadiusP'),
        'Impulse':  ('Z_urban_I', 'MaxR_I', 'RadiusI')}


def _row(target='Pressure', **over):
    """One row satisfying all four conditions; **over breaks one."""
    tgt, maxr, rad = ARGS[target]
    base = {
        'Z_free': 5.0,
        'weight': 250.0,
        'R_free': 5.0 * 250.0 ** (1 / 3),      # 31.5 m
        'exclude_r': 6.0,
        maxr: 28.0,
        rad: 45.0,
        tgt: 28.0 / 250.0 ** (1 / 3),
        'beyond_P': False, 'beyond_I': False,
    }
    base.update(over)
    return pd.DataFrame([base])


@pytest.mark.parametrize('target', ['Pressure', 'Impulse'])
def test_a_fully_valid_row_is_accepted(target):
    assert bool(z_urban_valid_mask(_row(target), *ARGS[target], target).iloc[0])


@pytest.mark.parametrize('target,broken,why', [
    ('Pressure', {'beyond_P': True},  'MaxR at or beyond R_conv'),
    ('Impulse',  {'beyond_I': True},  'MaxR at or beyond R_conv'),
    ('Pressure', {'R_free': 60.0},    'free-field radius beyond R_conv'),
    ('Impulse',  {'R_free': 60.0},    'free-field radius beyond R_conv'),
    ('Pressure', {'exclude_r': 40.0}, 'row sits inside the first street'),
    ('Impulse',  {'exclude_r': 40.0}, 'row sits inside the first street'),
    ('Pressure', {'Z_free': 1.0},     'below the Z_free floor'),
    ('Impulse',  {'Z_free': 1.0},     'below the Z_free floor'),
])
def test_each_condition_rejects_on_its_own(target, broken, why):
    row = _row(target, **broken)
    assert not bool(z_urban_valid_mask(row, *ARGS[target], target).iloc[0]), why


@pytest.mark.parametrize('target', ['Pressure', 'Impulse'])
def test_boundary_is_exclusive_at_R_conv(target):
    """R_free == R_conv is outside: beyond it the urban field IS free field."""
    _, _, rad = ARGS[target]
    row = _row(target, R_free=45.0, **{rad: 45.0})
    assert not bool(z_urban_valid_mask(row, *ARGS[target], target).iloc[0])


@pytest.mark.parametrize('target', ['Pressure', 'Impulse'])
def test_z_free_floor_is_inclusive(target):
    row = _row(target, Z_free=Z_URBAN_ZF_MIN[target])
    assert bool(z_urban_valid_mask(row, *ARGS[target], target).iloc[0])


def test_flagless_table_still_gets_the_range_conditions():
    """Older CSVs carry no R_free/beyond_*; the mask must still bound them.

    R_free is recomputed from Z_free and the weight. exclude_r is unavailable,
    so that one condition is skipped rather than guessed.
    """
    row = _row('Pressure', R_free=60.0).drop(
        columns=['R_free', 'exclude_r', 'beyond_P', 'beyond_I'])
    # Z_free=5, W=250 -> R_free = 31.5 m, inside RadiusP = 45 -> accepted
    assert bool(z_urban_valid_mask(row, *ARGS['Pressure'], 'Pressure').iloc[0])
    far = _row('Pressure', Z_free=12.0).drop(
        columns=['R_free', 'exclude_r', 'beyond_P', 'beyond_I'])
    # Z_free=12, W=250 -> R_free = 75.6 m, outside RadiusP = 45 -> rejected
    assert not bool(z_urban_valid_mask(far, *ARGS['Pressure'], 'Pressure').iloc[0])


def test_no_production_coefficient_sits_on_a_bound():
    """A coefficient pinned to its box face is not a fitted value.

    curve_fit reports the boundary when the objective is flat along a
    direction, so a railed coefficient means the parameter is unidentified on
    that domain — and it would be read off the CSV as physics. This guards the
    shipped tables rather than a synthetic fit, so it also catches a domain
    change that quietly de-identifies a term.
    """
    from pathlib import Path

    from blastlib import paths
    from blastlib.regression.z_urban import (
        CANYON_TRAP_BOUNDS, RANGE_SWITCH_BOUNDS,
    )

    files = sorted(Path(paths.TABLES_DIR).glob(
        'final_production_z_urban_coefficients_*.csv'))
    if not files:
        pytest.skip('no production coefficient tables on this checkout')

    cols = {'range_switch': (['C0', 'C1_amp', 'A_switch', 'B_open'],
                             RANGE_SWITCH_BOUNDS),
            'canyon_trap':  (['C0', 'C1_amp', 'C2_self', 'C3_dilute'],
                             CANYON_TRAP_BOUNDS)}
    railed = []
    for path in files:
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            if row.get('Formula') not in cols:
                continue
            names, (lo, hi) = cols[row['Formula']]
            for name, l, h in zip(names, lo, hi):
                v = row.get(name)
                if v is None or not np.isfinite(v):
                    continue
                if abs(v - l) < 1e-6 or abs(v - h) < 1e-6:
                    railed.append(f'{path.name}: det{int(row["Det"])} '
                                  f'{row["Target"]} {name}={v:g}')
    assert not railed, 'coefficients pinned to a bound: ' + '; '.join(railed)


def test_prepare_maxR_data_supplies_the_geometry():
    """exclude_r and R_free must reach the mask via the shared preparation."""
    name = 'config_93_det2_b10_s5_h15_w250'
    maxR = pd.DataFrame({'Config': [name] * 3, 'Z': [2, 5, 12],
                         'MaxR_P': [10.0, 30.0, 60.0],
                         'MaxR_I': [12.0, 35.0, 70.0],
                         'beyond_P': [False] * 3, 'beyond_I': [False] * 3})
    conv = pd.DataFrame({'ConfigName': [name], 'RadiusP': [50.0],
                         'RadiusI': [60.0]})
    df = prepare_maxR_data(maxR, conv)

    assert {'R_free', 'exclude_r'} <= set(df.columns)
    # det=2 -> exclude_r = s/2 = 2.5 m
    assert np.allclose(df['exclude_r'], 2.5)
    assert np.allclose(df['R_free'], df['Z_free'] * 250.0 ** (1 / 3))

    keep = z_urban_valid_mask(df, *ARGS['Pressure'], 'Pressure')
    # Z=2 (12.6 m) and Z=5 (31.5 m) are inside RadiusP=50; Z=12 (75.6 m) is not
    assert list(keep) == [True, True, False]
