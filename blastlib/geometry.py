"""Shared geometric helpers (previously copy-pasted across modules)."""

import numpy as np

from blastlib.constants import MAX_HEIGHT


def area_density(bsize, swidth):
    """rho = b^2 / (b + s)^2 — building footprint fraction of one block."""
    return bsize ** 2 / (bsize + swidth) ** 2


def volume_density(bsize, swidth, height):
    """Area density scaled by building height relative to MAX_HEIGHT."""
    return area_density(bsize, swidth) * height / MAX_HEIGHT


def exclude_radius(cfg):
    """Near-blast exclusion radius for convergence scanning.

    det=1 (street): the charge sits mid-street next to a building corner,
    so exclude the half-diagonal of the (b/2, s/2) rectangle.
    det=2 (intersection): the charge sits at the crossing center, so
    exclude half the street width.
    """
    if cfg['det'] == 1:
        return np.sqrt((cfg['bsize'] / 2) ** 2 + (cfg['swidth'] / 2) ** 2)
    return cfg['swidth'] / 2


def concat3(processed, key_fmt):
    """Concatenate the raveled resolution-1/2/3 arrays of one field.

    key_fmt is a format string with one placeholder for the resolution
    index, e.g. 'ratioP{}', 'X{}', 'peakP{}_orig'. Order 1, 2, 3 is part of
    the numerical contract (validation compares against the original).
    """
    return np.concatenate([processed[key_fmt.format(r)].ravel() for r in (1, 2, 3)])
