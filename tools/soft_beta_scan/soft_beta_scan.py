"""Beta-sensitivity scan for the soft pressure convergence criterion.

For every config (v2 npz) the beta-independent soft fields are computed
once and the soft radius is measured at each beta; a full convergence
table is written per beta under its own estimator token
(convergence_table_req_soft{b}.csv + theta tables — new filenames only,
the hard tables are never touched). The impulse side is pinned to the
live req table: the npz ratioI is used as-is — the live table was built
from it directly (the shipped npz already bake the scaled criterion with
the true VTK reference; --rebuild-impulse would substitute the weaker
CSV-reconstructed reference and shift RadiusI by meters). RadiusI
equality with convergence_table_req.csv is asserted per config — the
pipeline-level proof that the soft criterion leaves impulse untouched.

Per beta the report gives (a) the config_93 vs config_95 RadiusP gap,
(b) the median RadiusP inflation vs the hard table, and (c) LOGO CV
pressure errors with the Task B models. Selection rule (Task C4): the
LARGEST beta with gap < 10 m.

Betas: required set {4, 6, 8, 12} plus supplementary diagnostics {2, 3}.

Usage:
    python tools\\soft_beta_scan\\soft_beta_scan.py
"""

import importlib.util
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import numpy as np
import pandas as pd

from blastlib import paths
from blastlib.config.parser import config_parser
from blastlib.geometry import (area_density, concat3, exclude_radius,
                               volume_density)
from blastlib.io.npz_store import load_processed_data
from blastlib.processing.convergence import find_convergence_radius
from blastlib.processing.radius_estimator import resolve_estimator
from blastlib.processing.soft_criterion import (soft_pressure_fields,
                                                soft_pressure_weights)

V2_DIR = paths.DATA_DIR / 'processed_npz_v2'
BETAS = (2.0, 3.0, 4.0, 6.0, 8.0, 12.0)
REQUIRED_BETAS = (4.0, 6.0, 8.0, 12.0)
GAP_CONFIGS = ('config_93_det2_b10_s5_h15_w250', 'config_95_det2_b10_s5_h24_w250')
GAP_LIMIT_M = 10.0

CONV_COLS = ['ConfigName', 'Det', 'Height', 'BuildingSize', 'StreetWidth',
             'AreaDensity', 'VolumeDensity', 'ChargeWeight',
             'RadiusP', 'RadiusI', 'PressureAtR', 'ImpulseAtR',
             'RadiusEstimator']


def _load_logo():
    spec = importlib.util.spec_from_file_location(
        'logo_cv', Path(__file__).resolve().parents[1] / 'logo_cv' / 'logo_cv.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(progress=print):
    logo = _load_logo()
    hard_conv = pd.read_csv(paths.conv_csv('req')).set_index('ConfigName')
    names = sorted(p.stem for p in Path(V2_DIR).glob('config_*.npz'))
    assert len(names) == 96, f'expected 96 v2 configs, found {len(names)}'

    tokens = {b: resolve_estimator(f'req_soft{b:g}')['method'] for b in BETAS}
    conv_rows = {b: [] for b in BETAS}
    theta_P = {b: {} for b in BETAS}
    theta_I = {b: {} for b in BETAS}
    theta_deg = None

    t0 = time.time()
    for i, name in enumerate(names):
        cfg = config_parser(name)
        processed, ok = load_processed_data(V2_DIR, name)
        assert ok, f'load failed: {name}'

        fields = soft_pressure_fields(processed)
        args = (concat3(processed, 'ratioP{}'), concat3(processed, 'ratioI{}'),
                processed['peakP_all'], processed['peakI_all'],
                concat3(processed, 'X{}'), concat3(processed, 'Z{}'),
                exclude_radius(cfg))

        rho = area_density(cfg['bsize'], cfg['swidth'])
        vol = volume_density(cfg['bsize'], cfg['swidth'], cfg['height'])
        r_i_expected = hard_conv.loc[name, 'RadiusI']

        for b in BETAS:
            w = soft_pressure_weights(fields, b)
            radius = find_convergence_radius(*args, estimator='req',
                                             soft_w_P=w)
            # Task A.5 invariant: the impulse radius must equal the live
            # req table (same rebuilt ratioI, same hard scan).
            assert radius['impulse'] == pytest_approx(r_i_expected), (
                f'{name} beta={b:g}: RadiusI {radius["impulse"]!r} != '
                f'table {r_i_expected!r}')

            conv_rows[b].append({
                'ConfigName': name, 'Det': cfg['det'],
                'Height': cfg['height'], 'BuildingSize': cfg['bsize'],
                'StreetWidth': cfg['swidth'], 'AreaDensity': rho,
                'VolumeDensity': vol, 'ChargeWeight': cfg['weight'],
                'RadiusP': radius['pressure'], 'RadiusI': radius['impulse'],
                'PressureAtR': radius['pressureAtRadius'],
                'ImpulseAtR': radius['impulseAtRadius'],
                'RadiusEstimator': tokens[b],
            })
            theta_P[b][name] = radius['radius_per_theta_P']
            theta_I[b][name] = radius['radius_per_theta_I']
            if theta_deg is None:
                theta_deg = np.degrees(radius['theta_centers'])

        if (i + 1) % 8 == 0 or i == len(names) - 1:
            progress(f'[{i+1}/96] {name}  ({time.time()-t0:.0f}s elapsed)')

    # ---- write per-beta tables (new filenames only) ----
    tables_dir = Path(paths.TABLES_DIR)
    for b in BETAS:
        token = tokens[b]
        df = pd.DataFrame(conv_rows[b], columns=CONV_COLS)
        df.to_csv(tables_dir / paths.suffixed('convergence_table.csv', token),
                  index=False)
        for tag, store in (('P', theta_P), ('I', theta_I)):
            tdf = pd.DataFrame({'Theta_deg': theta_deg})
            for name in names:
                tdf[name] = store[b][name]
            tdf.to_csv(tables_dir / paths.suffixed(f'theta_radius_{tag}.csv',
                                                   token), index=False)
        progress(f'Saved tables for beta={b:g} (token {token})')

    # ---- per-beta report: gap, inflation, LOGO(P) with Task B models ----
    report_rows = []
    for b in BETAS:
        df = pd.DataFrame(conv_rows[b]).set_index('ConfigName')
        gap = abs(df.loc[GAP_CONFIGS[0], 'RadiusP']
                  - df.loc[GAP_CONFIGS[1], 'RadiusP'])
        infl = (df['RadiusP'] / hard_conv['RadiusP'] - 1.0)
        logo_res = logo.run_logo(df.reset_index(), model_p='relwls',
                                 model_i='quad', progress=lambda *a: None)
        summ = logo.summarize(logo_res)
        p_pool = summ[(summ['Target'] == 'P') & (summ['Scope'] == 'pooled')].iloc[0]
        report_rows.append({
            'beta': b,
            'required_set': b in REQUIRED_BETAS,
            'gap_93_95_m': gap,
            'median_inflation_pct': 100 * infl.median(),
            'p90_inflation_pct': 100 * infl.quantile(0.9),
            'max_inflation_pct': 100 * infl.max(),
            'logo_P_mean': p_pool['Mean'], 'logo_P_p90': p_pool['P90'],
            'logo_P_max': p_pool['Max'],
            'gap_pass': gap < GAP_LIMIT_M,
        })

    hard_gap = abs(hard_conv.loc[GAP_CONFIGS[0], 'RadiusP']
                   - hard_conv.loc[GAP_CONFIGS[1], 'RadiusP'])
    report = pd.DataFrame(report_rows)
    out_csv = Path(paths.ensure_dir(paths.CHECK_RESULTS_DIR)) / 'soft_beta_selection.csv'
    report.to_csv(out_csv, index=False)

    progress(f'\nHard-table gap config_93 vs config_95: {hard_gap:.2f} m')
    with pd.option_context('display.float_format', '{:8.2f}'.format):
        progress(report.to_string(index=False))

    passing = [r['beta'] for r in report_rows
               if r['required_set'] and r['gap_pass']]
    if passing:
        progress(f'\nSelection rule (largest required beta with gap < '
                 f'{GAP_LIMIT_M:g} m): beta* = {max(passing):g}')
    else:
        progress(f'\nNO beta in the required set {REQUIRED_BETAS} achieves '
                 f'gap < {GAP_LIMIT_M:g} m — stopping for review, per plan.')
    progress(f'Wrote {out_csv}')
    return report


def pytest_approx(value, rel=1e-9):
    """Tiny stand-in for pytest.approx (tools must not require pytest)."""
    class _Approx:
        def __eq__(self, other):
            return abs(other - value) <= rel * abs(value)

        def __repr__(self):
            return f'approx({value!r})'
    return _Approx()


if __name__ == '__main__':
    main()
