"""Every number of the street-channelling model, declared once, justified.

The retired implementation declared FLOOR three times and RMAX/X_FIT twice
across three tool files; a change in one silently diverged the others. Here
each constant appears exactly once, and each carries the measurement that
fixed its value. tests/test_street_model.py freezes the fitted dicts
verbatim — a refactor that nudges any of them fails loudly.

PROVENANCE, in two classes:

* REFIT-REPRODUCIBLE — RHALF and G: blastlib.street.fitting re-derives them
  from street_anchors.csv + the NPZ stores; the full-precision fit gives
  A=59.8843 p=2.4838 q=4.7467 and C=1.2850 p_sq=-1.0700 p_hs=0.2721, which
  round to the shipped values below (verified 2026-08-06, scipy 1.17.1).
* PINNED-HERITAGE — EPK and ENV: the scripts that fitted them were one-off
  and never kept. The constants are carried as published; fitting.fit_e_peak
  exists as a VERIFICATION refit only (its output is reported next to the
  pinned values in the parity report and never adopted). E_peak_pred in the
  pinned validation table matches this formula to 0.0005 — pure 3-dp
  rounding — so formula-level parity is proven even though fit-level
  provenance is lost.
"""

import numpy as np

# ---- E_peak: channelling strength from the Pi groups (PINNED-HERITAGE) ----
# E_peak = 1 + C * sqrt(rho)^a * Pi2^b * (1 - exp(-k_hs*H/s))
#                                      * (1 - exp(-k_hw*H/W^(1/3)))
# with sqrt(rho) = b/(b+s) and Pi2 = s/W^(1/3). Fitted on the 88 channelling
# configurations only (measured E_peak >= FLOOR); LOGO over 36 geometry
# families 6.7%. Fitting on all 96 gave 8.7% and a fake +-8% structured
# residual at s = 8/12 — the b10_s12 family never channels (median E 0.89,
# the street ATTENUATES) and fitting it as data poisoned the regime that
# does. det does not enter: a det constant worsens LOGO 8.7% -> 11.3%.
# The two saturations read as "walls taller than ~s/6 and ~W^(1/3)/6 act
# infinite" and give the correct E -> 1 limit as H -> 0, which no power law
# can.
EPK = dict(C=2.69, a=1.81, b=-0.50, k_hs=4.56, k_hw=7.07)

# ---- R_half: extent scale in metres (REFIT-REPRODUCIBLE) ----
# R_half = C * (b+s) * sqrt(rho)^p_sq * (H/s)^p_hs — geometry only, no
# charge. The (b+s) block-period exponent is PINNED at 1 by the dimensional
# prior: freeing it fits 1.12 and scores WORSE end-to-end (10.1% vs 9.8%
# mean profile MAPE). Adding Pi2 — although the charge dependence of the
# decay RATE is real (within-family d ln L / d ln W median -0.108, matching
# Pi2^+0.28) — is also worse (p90 20.3% vs 17.4%): the anchors' LOGO noise
# outweighs the signal. Fitted to the slope-fit anchors of the 75 profiles
# with a fitted decay; MAPE 16.5% against its own anchor.
RHALF = dict(C=1.28, p_sq=-1.07, p_hs=0.27)

# ---- g: unit-peak master curve of the channelling zone (REFIT-REPRODUCIBLE)
# g(x) = A * x^p * exp(-q*x), x = r/R_half, valid to X_MAX. A is not free:
# A = (q/p)^p * e^p pins max g = 1 exactly at x = p/q = 0.52, so the
# predicted profile ATTAINS E_peak. Fitting the pointwise MEDIAN instead
# under-attains every peak ~9% (misaligned peaks average down) — the pooled
# point cloud with the unit-peak constraint is the fix. Fitted on 75
# slope-anchored profiles, 11,545 points, rms 0.206. NOTE the shipped
# rounding (A to 1 dp) overshoots the exact unit peak by 0.1%
# (max g = 1.00096); g(1) = 0.518.
G = dict(A=59.9, p=2.48, q=4.75)

# ---- Design envelope (PINNED-HERITAGE) ----
# E_env = 1 + f*(E_peak-1)*max{g(x*t) : t in [1/S, S]} — f absorbs amplitude
# scatter, the dilation S absorbs location scatter and extends the domain to
# X_MAX*S = 2.16*R_half. CALIBRATION NOTE (measured 2026-08-06): f and S
# were calibrated against the pre-slope-anchor constants and kept; under the
# shipped constants the true in-sample numbers on the 88 are coverage 96.34%
# of slices (not the once-documented 95.0%), 0.73% of slices exceed by more
# than 0.15 in E, mean overprediction 27.2% (the price of a bound), largest
# single exceedance 0.723 at config_26_det1_b30_s5_h24_w500. The bound is
# slightly MORE conservative than its documentation claimed; it was kept
# rather than recalibrated because loosening a published safety bound to hit
# a cosmetic 95.0% would change a design number for nothing.
ENV = dict(S=1.35, f=1.20)

# Gate: predicted E_peak below this means "no strong local zone" — the
# profile prediction below the gate is indicative only. Truth table on the
# 96 (measured E_peak >= 1.5 as truth): 92/96 correct, 2 misses (config_67,
# config_70: predicted 1.43/1.46, measured 1.65) and 2 false alarms
# (config_78, config_80: predicted 1.58/1.59, measured 1.18) — the false
# alarms are the conservative direction.
GATE = 1.5

# Below this the measured "peak" is noise, not channelling: the excluded 8
# configs (4x det1_b10_s12, 4x low det1_b15_s20) top out at E 1.05-1.19 with
# no coherent decay to fit. The floor bounds fits and scoring alike — the
# 88-config membership everywhere in this package is COMPUTED as
# anchors.E_peak >= FLOOR, never hardcoded.
FLOOR = 1.2

# g describes the channelling zone only; beyond ~1.6*R_half the street is
# back at (or mildly below) free field and the model deliberately draws
# nothing. An attenuation-tail term was tried and rejected: its deficit
# pulled the fitted shape down INSIDE the zone of interest.
X_MAX = 1.6

# The master-curve fit window, slightly past X_MAX so the fit sees the
# zone's own edge but none of the attenuation tail.
X_FIT = 1.65

# Everything is capped at 100 m: exactly the extent of grid 1, the finest
# resolution (0.15 m cells). Staying inside keeps the whole profile on one
# resolution with no grid handoff — and the merged/unmerged asymmetry of
# peakP*_orig vs refP* (the urban field is max-filled across grids, the
# reference is not) is a no-op only there.
RMAX = 100.0

# A slope needs support: at least MIN_PTS slices spanning MIN_SPAN metres.
# Below either, the config genuinely does not decay inside the domain (the
# s=20 family) and the anchor is NaN, honestly.
MIN_PTS = 6
MIN_SPAN = 4.0

# The decay-fit window: from where the excess first drops below HI_FRAC of
# the peak excess (skipping the plateau, which carries no slope information)
# down to where it drops below max(LO_FRAC * peak excess, FLOOR - 1). The
# window CONVENTION is the dominant anchor uncertainty — 85-25 vs 90-30
# moves R_half ~10% median — an honest stated convention, not mesh noise
# (the slice width moves it only 1.7%).
HI_FRAC = 0.85
LO_FRAC = 0.25

# The smoothing target is physical — ~2.5 m of street — so the kernel adapts
# to the slice width instead of hardcoding "5 slices".
SMOOTH_METRES = 2.5

# Each radial bin takes its cells from the finest grid that still has at
# least this many of them, so a slice never mixes resolutions. Within
# RMAX = 100 m grid 1 always qualifies (51-68 strip cells per 0.5 m slice at
# s = 5), so the fallback never fires in practice — it exists for stores
# with a truncated grid 1.
MIN_CELLS_PER_BIN = 8

# (The peak-search start — b+s for det1, s/2+b for det2 — is a function of
# the parsed config, not a constant; it lives in anchors.detector_start.
# It is a SEARCH bound, not a validity bound: see geometry.exclude_radius
# for the latter. Any absolute-kPa clause in either bound was tried twice
# and re-imports the charge through the back door — within-family CV of the
# marker 0.010 -> 0.255. Metric lengths may be normalized only by geometric
# lengths here.)


def sqrt_rho(b, s):
    """b/(b+s) — the wall-continuity Pi group. rho^0.9 tracks the
    probability that BOTH walls of the street are present where the wave
    ping-pongs between them, which is the physical reading of EPK's
    sqrt(rho)^1.81."""
    return b / (b + s)


def pi2(s, W):
    """s/W^(1/3) — street width in charge lengths (confinement)."""
    return s / W ** (1.0 / 3.0)


def w13(W):
    """W^(1/3) — the charge length scale [kg^(1/3) -> m via Hopkinson]."""
    return W ** (1.0 / 3.0)


# Guard against accidental redefinition drift: the unit-peak identity that
# fitting.g_unit relies on, evaluated once at import for the shipped G.
assert abs((G['q'] / G['p']) ** G['p'] * np.exp(G['p']) / G['A'] - 1) < 2e-3
