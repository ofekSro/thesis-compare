"""Extract peak pressure and impulse from 1D simulation output files.

Reads viper1d_th_overpressure_<W>kg.txt and viper1d_th_impulse_<W>kg.txt
files from data/viper1d/. Each file: first column = time, remaining 19
columns = values at R = 1, 1.5, 2, ..., 10 m. Peak = max over time for each R.

Output: outputs/tables/1d_peaks.csv
        columns: ChargeWeight, R, PeakPressure_kPa, PeakImpulse

NOTE: this is an independent 1-D extraction. It is NOT the source of
data/free_field_data.csv (different layout, different weights, R in metres
vs scaled distance Z).

Usage:
    python tools\\extract_1d_peaks\\extract_1d_peaks.py
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # project root

import numpy as np
import pandas as pd

from blastlib import paths

R_VALUES = np.arange(1.0, 10.5, 0.5)   # 1, 1.5, 2, ..., 10  (19 values)


def load_peak(filepath):
    """Return array of peak values (max over time) for each R column."""
    data = np.loadtxt(filepath)
    # data[:, 0] = time; data[:, 1:] = values at each R
    values = data[:, 1:]
    return values.max(axis=0)


def main(*, input_dir=None, out_csv=None, progress=print):
    """Extract peaks for every weight found in input_dir.

    Returns the output path, or None if no data was found.
    """
    input_dir = paths.resolve(input_dir, paths.VIPER1D_DIR)
    out_csv = paths.resolve(out_csv, paths.TABLES_DIR / '1d_peaks.csv')
    paths.ensure_dir(Path(out_csv).parent)

    if not Path(input_dir).is_dir():
        progress(f'ERROR: input folder not found: {input_dir}')
        return None

    rows = []
    for fname in sorted(os.listdir(input_dir)):
        m = re.match(r'viper1d_th_overpressure_(\d+)kg\.txt', fname)
        if not m:
            continue
        weight = int(m.group(1))
        p_path = os.path.join(str(input_dir), fname)
        i_path = os.path.join(str(input_dir), f'viper1d_th_impulse_{weight}kg.txt')

        if not os.path.isfile(i_path):
            progress(f'  Warning: no impulse file for {weight} kg, skipping')
            continue

        peak_P = load_peak(p_path)
        peak_I = load_peak(i_path)

        if len(peak_P) != len(R_VALUES) or len(peak_I) != len(R_VALUES):
            progress(f'  Warning: unexpected column count for {weight} kg '
                     f'(P={len(peak_P)}, I={len(peak_I)}), skipping')
            continue

        for r, p, i in zip(R_VALUES, peak_P, peak_I):
            rows.append({'ChargeWeight': weight, 'R': r,
                         'PeakPressure_kPa': p / 1000.0, 'PeakImpulse': i})
        progress(f'  Processed {weight} kg')

    if not rows:
        progress(f'No data found in {input_dir}.')
        return None

    df = pd.DataFrame(rows).sort_values(['ChargeWeight', 'R'])
    df.to_csv(out_csv, index=False)
    progress(f'\nSaved: {out_csv}')
    progress(df.to_string(index=False))
    return out_csv


def cli(argv=None):
    p = argparse.ArgumentParser(description='Extract 1-D peak pressure/impulse.')
    p.add_argument('--input-dir', default=None, help='Folder with viper1d_th_*.txt files.')
    p.add_argument('--out-csv', default=None, help='Output CSV path.')
    args = p.parse_args(argv)
    return main(input_dir=args.input_dir, out_csv=args.out_csv)


if __name__ == '__main__':
    cli()
