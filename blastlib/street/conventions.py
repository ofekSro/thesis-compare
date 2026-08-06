"""The reference-parity quirk ledger: measurement conventions, preserved.

The street suite is a clean-room rewrite of a reference implementation whose
numbers are pinned (outputs/check_results/street_anchors.csv and friends,
snapshot commit bf8eefe). Some of the reference's choices were deliberate
conventions; a few were accidents of code that nevertheless shaped the
pinned numbers. BOTH are preserved here, named, so no later cleanup can
"fix" one silently and shift a published table. Each entry says what the
quirk is, where it came from (retired file:line), and what breaks if it is
changed.

THE LEDGER
----------
Q1  EXCLUSION CUT, STRICT vs INCLUSIVE. Slices inside the exclusion radius
    are dropped from the RAW profile BEFORE smoothing (dropping them after,
    or merely skipping them at read time, let near-blast slices contaminate
    the first outside bins through the running mean). The anchors and
    master-curve stages used strict ``r > Rex`` (measure_anchors.py:106,
    fit_master_curve.py:81); the validation stage used ``r >= Rex``
    (e_profile.py:156). Almost certainly a no-op — slice centres sit at
    0.25 + 0.5k m while Rex is sqrt((b/2)^2+(s/2)^2) (det1, irrational) or
    s/2 in {2.5, 4, 6, 10} (det2, never a centre) — but "almost certainly"
    is not parity: cut_exclusion() keeps both spellings and the parity
    harness asserts the no-op empirically instead of assuming it.

Q2  THREE SMOOTHERS, TWO CONVENTIONS. Anchors and master-curve smooth with
    a kernel adapted to the slice width (smooth_physical: ~2.5 m of street,
    measure_anchors.py:81); validation smoothed with a FIXED k=5 regardless
    of dr (e_profile.py:142). At the production dr = 0.5 they coincide
    (k = 5); at any other dr they do not, and the pinned validation CSV was
    produced by the fixed-k spelling. smooth_fixed() exists so validation
    stays on its own convention.

Q3  BANKER'S ROUNDING DISABLES SMOOTHING AT COARSE dr. smooth_physical
    computes k = int(round(2.5/dr)) then forces it odd DOWNWARD. dr=1.0:
    round(2.5) = 2 under banker's rounding, forced to 1 — no smoothing.
    dr=2.0: round(1.25) = 1 — no smoothing. The documented dr=2 stability
    check (slope anchor moves 1.7% median where the crossing detector moved
    19.6%) therefore compared a SMOOTHED 0.5 m fit against a RAW 2 m fit —
    the stability is a property of fitting the whole fall, not of the
    smoothing. Changing the rounding would change what that published
    comparison means.

Q4  KERNEL EDGES ARE RAW. np.convolve(..., mode='same') tapers the ends
    against implicit zeros, which would drag the first/last k//2 slices of
    E toward 0 (an E of 0.4 instead of 2 at the profile head moves the
    peak). The reference overwrote those samples with the raw input rather
    than renormalizing a shrinking window; so does boxcar_raw_edges. The
    peak search starts well inside the profile, so raw edges are safer than
    wrong ones.

Q5  TWO E_peak MEASUREMENT CONVENTIONS. The anchors table measures E_peak
    as the smoothed maximum on r >= max(detector_start, Rex) capped at
    RMAX (measure_anchors.py:115-121); the validation table measured it as
    the smoothed maximum over r <= r_model[-1] after the Q1-inclusive cut,
    with NO detector_start (e_profile.py:240). On plateau-shaped profiles
    they disagree — config_56: anchors 2.714, validation 3.145 — and the
    pinned validation CSV carries the second. Both are kept, each labelled,
    in their own modules.

Q6  DECAY-FIT WINDOW, TERMINATOR EXCLUSIVE. The fall window opens at the
    FIRST tail index with excess <= HI_FRAC * peak excess (searched over
    the whole tail — a late plateau re-entry does not reopen it) and closes
    EXCLUSIVE at the first subsequent index with excess <=
    max(LO_FRAC * peak excess, FLOOR - 1): the terminating slice is not
    fitted. Non-positive excess is dropped before the log. The OLS is
    np.polyfit(r, ln(excess), 1), unweighted.

Q7  A ROW FOR EVERY CONFIG. measure_profile returns a pre-seeded dict
    (anchors NaN, n_fit=0, span_fit=0.0) and every early exit returns it,
    so street_anchors.csv always holds all 96 rows — 21 with NaN L_decay
    (the 17 s=20 rows that genuinely do not decay inside 100 m, plus the 4
    det1_b10_s12 rows that never channel). Downstream stages FILTER on the
    NaNs; they must never be pre-dropped at write time.
"""

import numpy as np

from blastlib.geometry import exclude_radius
from blastlib.street.constants import SMOOTH_METRES


def boxcar_raw_edges(a, k):
    """Odd-k boxcar mean with the first/last k//2 samples left raw (Q4)."""
    if k <= 1:
        return np.asarray(a, float)
    w = np.ones(k) / k
    s = np.convolve(a, w, mode='same')
    p = k // 2
    s[:p], s[-p:] = a[:p], a[-p:]
    return s


def smooth_physical(a, dr):
    """~2.5 m running mean regardless of slice width (Q2/Q3/Q4).

    The anchors/master-curve convention: k = round(SMOOTH_METRES/dr),
    forced odd downward — which silently disables smoothing at dr >= 1.0
    (Q3). This is the reference's exact arithmetic, banker's rounding
    included; do not "fix" the rounding without re-pinning every anchor.
    """
    k = max(1, int(round(SMOOTH_METRES / dr)))
    if k % 2 == 0:
        k -= 1
    return boxcar_raw_edges(a, k)


def smooth_fixed(a, k=5):
    """Fixed-width boxcar — the validation convention (Q2).

    Equals smooth_physical only at dr = 0.5. The pinned validation table
    was produced with k = 5 regardless of dr, so validation keeps this
    spelling.
    """
    return boxcar_raw_edges(a, k)


def cut_exclusion(prof, cfg, inclusive=False):
    """Drop slices inside the exclusion radius — RAW, before smoothing (Q1).

    inclusive=False is the anchors/master-curve spelling (r > Rex);
    inclusive=True is the validation spelling (r >= Rex). The parity
    harness asserts the two agree on every stored config; the parameter
    exists so that assertion is a measurement, not an assumption.
    """
    ex = exclude_radius(cfg)
    keep = prof.r >= ex if inclusive else prof.r > ex
    return prof[keep].reset_index(drop=True)
