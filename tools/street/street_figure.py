"""Predicted-vs-measured E(r) for one configuration or free geometry.

The single-config face of blastlib.street: give a config token (number,
prefix or full name) to overlay its measurement, or free geometry with
--b --s --H --W --det to draw the prediction alone (a geometry matching a
stored config gets its measurement overlaid automatically).

Usage:
    python tools\\street\\street_figure.py 58
    python tools\\street\\street_figure.py --b 30 --s 5 --H 12 --W 50 --det 2
    python tools\\street\\street_figure.py 58 --csv
"""

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # project root

# See street_pipeline.py: the raw-store expansion's divide warnings are
# noise (the offending cells are masked immediately after).
warnings.filterwarnings('ignore', category=RuntimeWarning,
                        module=r'blastlib\.processing\.grids')

import matplotlib
matplotlib.use('Agg')

from blastlib import paths
from blastlib.config.discovery import resolve_config
from blastlib.progress import say as _say
from blastlib.street.figures import profile_figure


def main(config=None, *, b=None, s=None, H=None, W=None, det=None, dr=0.5,
         npz_dir=None, out_dir=None, save=True, write_csv=False,
         progress=None):
    """Delegates to blastlib.street.figures.profile_figure (same contract:
    returns the Figure when save=False, else the PNG path)."""
    return profile_figure(config, b=b, s=s, H=H, W=W, det=det, dr=dr,
                          npz_dir=npz_dir, out_dir=out_dir, save=save,
                          write_csv=write_csv, progress=progress)


def _known_configs(npz_dir):
    return sorted(p.stem for p in Path(npz_dir).glob('config_*.npz'))


def cli(argv=None):
    p = argparse.ArgumentParser(
        description='Predicted vs measured street channelling profile E(r).')
    p.add_argument('config', nargs='?', default=None,
                   help='Config number (58) or full name. Omit to give '
                        'geometry with --b --s --H --W --det instead.')
    p.add_argument('--b', type=float, help='building size [m]')
    p.add_argument('--s', type=float, help='street width [m]')
    p.add_argument('--H', type=float, help='building height [m]')
    p.add_argument('--W', type=float, help='charge weight [kg]')
    p.add_argument('--det', type=int, choices=[1, 2],
                   help='1 = mid-street, 2 = intersection')
    p.add_argument('--dr', type=float, default=0.5)
    p.add_argument('--npz-dir', default=None, dest='npz_dir')
    p.add_argument('--out-dir', default=None, dest='out_dir')
    p.add_argument('--csv', action='store_true', dest='write_csv')
    a = p.parse_args(argv)

    config = a.config
    npz_dir = paths.resolve(a.npz_dir, paths.default_npz_dir(soft=True))
    if config is None and None in (a.b, a.s, a.H, a.W, a.det) \
            and sys.stdin.isatty():
        # isatty alone is not a reliable interactivity signal everywhere,
        # but a wrong guess here only skips the convenience prompt.
        known = _known_configs(npz_dir)
        _say(f'{len(known)} configs available, e.g. {known[0]}')
        try:
            config = input('Config (number or name): ')
        except EOFError:
            config = None
    if config is not None:
        known = _known_configs(npz_dir)
        rc = resolve_config(config, known)
        if rc is None:
            p.error(f'{config!r} matches no config in {npz_dir}')
        config = rc
    elif None in (a.b, a.s, a.H, a.W, a.det):
        p.error('give a config, or all of --b --s --H --W --det')

    main(config, b=a.b, s=a.s, H=a.H, W=a.W, det=a.det, dr=a.dr,
         npz_dir=a.npz_dir, out_dir=a.out_dir, write_csv=a.write_csv)
    return 0


if __name__ == '__main__':
    sys.exit(cli())
