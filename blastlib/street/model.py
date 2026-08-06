"""The closed-form street-channelling model: E(r) from four numbers.

    E(r)   = 1 + (E_peak - 1) * g(r / R_half)         valid to r <= 1.6*R_half
    E_peak = 1 + 2.69*sqrt(rho)^1.81 * Pi2^-0.50
               * (1 - exp(-4.56*H/s)) * (1 - exp(-7.07*H/W^(1/3)))
    R_half = 1.28*(b+s) * sqrt(rho)^-1.07 * (H/s)^0.27          [m]
    g(x)   = 59.9 * x^2.48 * exp(-4.75*x)             unit peak at x = 0.52

with sqrt(rho) = b/(b+s) and Pi2 = s/W^(1/3). Pure functions, zero I/O —
importable by anything (the standalone calculator included) without
touching pandas, matplotlib or the data stores.

PHYSICAL READING (why the formulas look like this)
--------------------------------------------------
* sqrt(rho)^1.81 ~ rho^0.9: very nearly the probability that BOTH walls of
  the street are present where the wave needs them — channelling is the
  wave ping-ponging between facades, and one missing wall breaks the pong.
* Pi2^-0.50: confinement. A street narrow in charge lengths concentrates
  the same energy flux into less cross-section.
* The two height saturations say "walls taller than ~s/6 and ~W^(1/3)/6
  act infinite" — and, unlike any power law, give the correct E -> 1 limit
  as H -> 0: no walls, no channelling.
* The peak sits at 0.52*R_half ~ 1.3*(b+s), just past the FIRST street
  intersection: the crossing bleeds pressure sideways, and the reinforced
  front needs about a block to rebuild past it.
* R_half ~ 2-2.5 block periods; beyond ~1.6*R_half the street is back at
  (or mildly below) free field — the mild attenuation is real and
  DELIBERATELY unmodelled (see constants.X_MAX).
* R_half carries no W: the extent of the zone is set by the geometry, the
  strength by geometry AND charge — the two-boundary statement. The charge
  dependence of the decay RATE is real but too noisy to ship (see
  fitting.py).

WHAT THE MODEL REFUSES TO DO, ON MEASURED GROUNDS
-------------------------------------------------
* No det split: a det constant worsens E_peak LOGO 8.7% -> 11.3%. The
  intersection charge (det=2) sees the same first street twice by symmetry;
  det never earned a coefficient.
* No absolute-pressure clause anywhere: tried twice, removed twice —
  within-family CV of the affected marker went 0.010 -> 0.255 because an
  absolute kPa threshold re-imports the charge weight through the back
  door. Scaled-distance space is the same trap in disguise: Z_peak vs Pi2
  correlate +0.877 purely through the shared 1/W^(1/3).
* No prediction below the gate: b10_s12 NEVER channels (E <= 1.06, median
  0.89 — that street ATTENUATES), and fitting it as data once bought a fake
  +-8% structured residual at s = 8/12. Below measured E ~ 1.2 the "peaks"
  are noise.
* Known worst corner: Pi2 = 0.44 (s=5, W=1500) — profile errors 26-29%,
  the same corner every formula system in this project degrades in.

Validation of this exact parameterization (88 channelling configs, slices
with measured E >= 1.2 inside the domain): profile MAPE mean 9.7%, median
8.5%, p90 17.3%, max 31.0%; E_peak LOGO over 36 geometry families 6.7%.
"""

import numpy as np

from blastlib.street.constants import (ENV, EPK, G, GATE, RHALF, X_MAX,
                                       pi2, sqrt_rho)


def e_peak(b, s, H, W, det=None):
    """Channelling strength from the Pi groups. det is accepted and
    IGNORED — the absence of a det split is a tested result, not an
    oversight (module docstring)."""
    sq = sqrt_rho(b, s)
    P2 = pi2(s, W)
    return 1 + EPK['C'] * sq ** EPK['a'] * P2 ** EPK['b'] \
        * (1 - np.exp(-EPK['k_hs'] * H / s)) \
        * (1 - np.exp(-EPK['k_hw'] * H / W ** (1 / 3)))


def r_half(b, s, H):
    """Extent scale in metres — geometry only, no charge (W-free by
    design; see the two-boundary statement in the module docstring)."""
    sq = sqrt_rho(b, s)
    return RHALF['C'] * (b + s) * sq ** RHALF['p_sq'] \
        * (H / s) ** RHALF['p_hs']


def g(x):
    """Unit-peak master curve of the channelling zone.

    Rise, peak at x = p/q = 0.52, decay; g(1) = 0.518. The shipped
    rounding of A overshoots the exact unit peak by 0.1% (max g =
    1.00096) — accepted, documented, frozen by test.
    """
    x = np.asarray(x, float)
    return G['A'] * x ** G['p'] * np.exp(-G['q'] * x)


def predict_profile(r, b, s, H, W):
    """Best-estimate E(r); NaN beyond the fitted range x > X_MAX.

    Accepts scalars or arrays (the retired reference raised on scalars —
    an additive fix, nothing pinned depends on scalar calls). This is a
    central estimate: measurements exceed it about half the time by
    construction — the bounding version is predict_envelope.
    """
    Rh = r_half(b, s, H)
    x = np.asarray(r, float) / Rh
    out = 1 + (e_peak(b, s, H, W) - 1) * g(x)
    return np.where(x > X_MAX, np.nan, out)


def predict_envelope(r, b, s, H, W):
    """Design envelope over E(r): amplitude factor f on the excess, worst
    case over dilations t in [1/S, S] (9 samples), domain extended to
    X_MAX*S = 2.16*R_half. True in-sample calibration numbers are in
    constants.ENV's comment — including the 2026-08-06 correction of the
    stale 95.0% claim."""
    Rh = r_half(b, s, H)
    x = np.asarray(r, float) / Rh
    ts = np.linspace(1.0 / ENV['S'], ENV['S'], 9)
    genv = np.max([g(x * t) for t in ts], axis=0)
    out = 1 + ENV['f'] * (e_peak(b, s, H, W) - 1) * genv
    return np.where(x > X_MAX * ENV['S'], np.nan, out)


def gate_verdict(ep):
    """True when a strong local zone is predicted (E_peak >= GATE).

    Truth table on the 96 (constants.GATE comment): 92/96 correct, 2
    misses, 2 false alarms — the false alarms are the conservative
    direction. Below the gate the profile prediction is indicative only.
    """
    return bool(ep >= GATE)
