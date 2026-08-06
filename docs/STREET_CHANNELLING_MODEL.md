# The Street-Channelling Model — E(r) Along the First Street

A closed-form model for **where strong local (channelled) behaviour of the
peak pressure exists, how strong it is, and how far it extends** along the
first street, built from the Pi groups alone. This document records both the
final model and the investigation that produced it, including the dead ends —
several of which changed the direction of the work.

Everything here is pressure-only, measured on the street-axis strip of the
96-configuration dataset. Companion tools: `tools/pressure_profile` (the
measurement) and `tools/e_profile` (the model vs. measurement).

---

## 1. The final model

Inputs: building size `b`, street width `s`, height `H` [m], charge `W` [kg],
detonation type (does **not** enter — tested and rejected, see §6).

Derived groups: `sqrt(rho) = b/(b+s)` (wall continuity), `Pi2 = s/W^(1/3)`,
`H/s`, `H/W^(1/3)`.

```
E(r)   = 1 + (E_peak - 1) * g(r / R_half)          valid to r = 1.6*R_half

E_peak = 1 + 2.69 * sqrt(rho)^1.81 * Pi2^-0.50
           * (1 - exp(-4.56*H/s)) * (1 - exp(-7.07*H/W^(1/3)))

R_half = 1.28 * (b+s) * sqrt(rho)^-1.07 * (H/s)^0.27     [metres]

g(x)   = 59.9 * x^2.48 * exp(-4.75*x)                    unit peak at x = 0.52
```

(Constants updated 2026-08-04, when the decay anchor moved from a crossing
detector to a slope fit — see §2a. The functional forms did not change.)

**Gate.** If `E_peak < 1.5` the street does not channel strongly — no strong
local zone exists and the profile formula is not meaningful (below E ≈ 1.2
the measured "peak" is a noise floor, not channelling). Gate classification
accuracy: 92/96, zero false alarms.

**Design envelope** (bounding curve, for "what not to exceed"):

```
E_env(r) = 1 + 1.20 * (E_peak - 1) * max{ g(x*t) : t in [1/1.35, 1.35] }
```

calibrated so 95.0% of all measured channelling-zone slices lie under it
(in-sample; only 1.5% of slices exceed it by more than 0.15 in E; mean
overprediction 24% — the price of a bound).

### Validation (all leave-one-geometry-out where stated)

| quantity | score |
|---|---|
| `E_peak` | LOGO MAPE **6.7%** (36 geometry families) |
| `R_half` | MAPE **16.5%** against the slope anchor (not comparable to the old 12.6%, which was scored against the noisier crossing anchor) |
| `g` vs the pooled normalized cloud (75 profiles, 11,545 points) | rms 0.206 |
| full profile `E(r)`, channelling zone, 88 configs | mean **9.8%**, median **8.5%**, p90 17.4%, max 31.0% |
| the crossing-anchor pipeline on the same slices | mean 10.4%, median 9.4%, p90 18.0%, max 28.5% |
| attained-peak bias | **−0.4%** (the unit-peak constraint removes a −9% built-in bias) |

### Physical reading

- `sqrt(rho)^1.81 ≈ rho^0.9`: channelling needs **both walls at once** — the
  wave ping-pongs between them; the probability a cross-section has solid
  wall on both sides is `(b/(b+s))^2 = rho`.
- `Pi2^-0.50`: confinement weakens as the square root of the street width in
  charge lengths.
- The two height saturations encode "walls taller than ~s/6 and ~W^(1/3)/6
  act infinite" — the measured H12→H24 saturation and the thesis finding that
  peak pressure is nearly blind to height. They give the correct `E → 1`
  limit as `H → 0`, which a power law cannot.
- `g`: quadratic onset (reflections take two walls to build), peak at
  `0.52*R_half`, `g(1) = 0.48` (the half-decay anchor emerges, it is not
  imposed).

### Rules of thumb

- The strongest local behaviour sits at `R_peak ≈ 0.5*R_half ≈ 1.3*(b+s)` —
  just past the first intersection.
- `R_half ≈ 2–2.5 block periods` (b+s), i.e. after the second or third
  intersection; equivalently `≈ 5*(b*s*H)^(1/3)`. Median 59 m over the
  dataset.
- Beyond `≈ 1.6*R_half` the street is back at free field and then mildly
  **attenuated** (the measured tail settles near `E ≈ 1 − 0.3*(E_peak−1)`
  in the deficit region; deliberately not modelled).

### The two-boundary statement

The city has **two boundaries with two different scalings**. The convergence
radius grows with the charge (`R_conv = W^(1/3) * Z_conv(Pi)` — Hopkinson).
The local-zone extent is fixed in the fabric (`R_half = (b+s) * f(sqrt(rho),
H/s)` — metres of geometry, no W). The charge decides only *whether* the
local zone is dangerous (via `Pi2` in the gate), not *how far* it reaches.
Forcing `Pi2` into the extent formula returns exponent +0.07 and no
end-to-end gain. Intuition: channelling lives between the intersections,
and the intersections do not move when the bomb grows — they only fill
harder.

One precision added by the slope-fit anchor (§2a): the statement holds for
the *extent* `R_half`, but the decay **rate** per metre does carry a weak,
real charge dependence — within fixed geometry, `d ln L_decay / d ln W` has
median **−0.108** (IQR [−0.22, −0.04], 16/27 (family, det) groups above
0.1 in magnitude), matching the pooled `Pi2^+0.28`. A bigger charge fills
the street harder and its excess dies off slightly faster per metre; over
the full 30× charge range this is a ~30% effect on `L_decay`. It is left
out of the model deliberately: exploiting it was tried and costs more than
it returns (§6, item 6), because the between-family scatter of `L_decay`
(LOGO 42.5% even with `Pi2`) dwarfs it.

---

## 2. How the measurement is defined

- **Strip, not rings.** All quantities are measured on the first-street
  strip `0 <= Z <= s/2`, binned into 0.5 m cross-street slices along the
  street axis. Every slice holds the same ~51–68 cells at every distance.
  Angular rings were abandoned because their sample composition changes with
  radius: the per-ring cell count is set purely by the building layout
  (identical in all 85 bins for two configs 30× apart in charge) and dips to
  local minima exactly where several "detections" landed — the median jumped
  because the *sample* changed, not the field.
- `E(r) = mean(P_urban) / mean(P_ff)` per slice, free field taken from the
  charge-only reference on the same cells; profile lightly smoothed (2.5 m
  running mean, physical — the kernel adapts to the slice width). `E_peak` =
  max over the profile beyond the exclusion radius.

### 2a. The decay anchor — a slope fit, not a crossing (2026-08-04)

`R_half` was originally "the first distance past the peak where the excess
`E−1` halves, 3 consecutive slices". That single-crossing detector had two
measured failure modes: re-measured with 2 m slices instead of 0.5 m it moved
**20% at the median** (one crossing inherits the full staircase noise of the
intersections), and on plateau-topped profiles the halving lands wherever the
plateau happens to end.

The production anchor is now a **slope fit over the whole fall**
(`tools/e_profile/measure_anchors.py`): OLS of `ln(E−1)` against `r` from
where the excess first drops below 85% of its peak value (skipping the
plateau) down to where it drops below max(25% of peak, the E = 1.2 noise
floor), requiring ≥ 6 slices spanning ≥ 4 m and a negative slope. The decay
length `L_decay` (metres per e-fold) gives

    R_half = R_peak + ln(2) * L_decay

— the same semantics, carried by every slice of the fall instead of one
crossing. Measured properties:

| | crossing (old) | slope fit |
|---|---|---|
| stability, 0.5 m vs 2 m slices | 19.6% | **1.7%** |
| fit-window convention (85–25 vs 90–30) | — | 10.4% median |
| configs with a measurable decay | 79 | 75 (+ the 2 m run finds 63) |
| Pi-predictability of the fall scale | R² 0.25 | **R² 0.52** |

The window convention is now the dominant uncertainty of the anchor — an
honest convention, stated, rather than mesh noise. `L_decay` is independent
of `R_peak` noise by construction (a slope does not care where the axis
origin sits). Two findings from the cleaner anchor, left open deliberately:
the strongest single driver of `L_decay` is now `H` (corr +0.52), and the
best 4-Pi fit wants `Pi2^+0.28` — a *hint* of charge dependence in the fall
scale that the crossing noise had buried, which would qualify the
two-boundary statement (§1) if it survives a within-family test.

One number that looks worse and is not: the collapse IQR under the slope
anchor (0.222) reads worse than under the crossing anchor (0.189), because
the crossing anchor pins `y(x=1) = 0.5` for every profile *by construction* —
it is self-aligned at exactly the locus the IQR rewards. The fair comparison
is end-to-end profile error with predicted anchors, where the slope pipeline
wins on mean, median and p90 (§1 table).
- For det2 the strip represents both streets (θ = 0 ≡ θ = 90, verified
  digit-for-digit).
- **The stored 2-D fields hold finite values inside building footprints**
  (an over-roof envelope, ~100% of grid-1 cells valid). Any spatial mask
  must come from geometry, not from data validity — a validity-based
  "crossing detector" and an early strip-orientation check were both
  invalidated by this and redone.

---

## 3. The investigation: what was tried and what killed it

The path matters because three "clean" intermediate results were later
overturned by specific measurements.

**R_local as a protocol boundary.** The starting question was to split the
domain into local / formulas / free-field. The pipeline already contains an
inner boundary (`max(R_exclusion, 2*W^(1/3))`, never empties the band);
pushing it outward to block-period multiples emptied the middle zone for up
to 26/96 configurations and correlated with nothing.

**Steepest-descent detectors.** Locating "the end of channelling" via
derivatives of the axial profile went through several iterations:

- `dP/dR` finds where the *wave* is strong, not where the street stops
  acting (its magnitude tracks the pressure level).
- `d lnP/d lnR` (local log-log slope by moving regression, bandwidth fixed
  in ln R — an earlier version smoothed in R while differentiating in ln R,
  an 18× effective-bandwidth swing that was fixed) gave a stable marker:
  94/96 configurations reproduce it across bin widths, and within a fixed
  geometry it moves 1% while `W^(1/3)` moves 50%.
- **But the marker is an intersection finder.** Tested against crossing
  positions predicted purely from `(det, b, s)`: **77/78 clean detections
  lie inside a street crossing** (±1 m, vs 42% chance coverage; median 1.2 m
  from the crossing centre). The "steepest fall" is the venting notch at
  whichever intersection vents hardest — real physics (PHYSICS_ANALYSIS §2:
  the channelled excess vents at every crossing), but not a zone boundary.
  Its apparent constancy (~69 m, unexplainable by any Pi fit — a constant
  beat the best power law 23.4% vs 19.5%) was block periods of 20–50 m
  putting everyone's 2nd–3rd crossing at 40–100 m.

**The reframe** (user's): R_local should mark *where the local behaviour is
strongest*, not where something ends. That turned the object of interest
from a derivative feature into the profile triplet (`R_peak`, `E_peak`,
`R_half`) — all three of which finally correlate with geometry
(`corr(R_peak, b+s) = +0.73` vs +0.09 for the old marker).

**Detector minutiae that mattered.**
- Slices inside the exclusion radius must be dropped *before* any smoothing
  or fitting, not merely skipped when reading the result (they contaminated
  the first outside bins).
- At 0.5 m slices the old marker pinned to the inner boundary in 4/10 test
  configs; the detector start was moved to `b+s` (det1) / `s/2+b` (det2) —
  a tool-local choice, deliberately not touching
  `blastlib.geometry.exclude_radius`, which feeds `R_conv` and every fitted
  coefficient upstream.
- A 10 kPa absolute clause was tried twice as a search bound and removed
  twice: an absolute threshold re-imports the charge through the back door
  (within-family CV of the marker jumped 0.010 → 0.255) — the same failure
  mode as the project's old absolute impulse criterion.
- The eventual search window: `[detector start, min(first ratio<=1.05 for 3
  slices, 100 m)]`. The 100 m cap is also exactly grid 1's extent, keeping
  the whole profile on one resolution.

**Fitting E_peak.** Candidate physical forms were LOGO-validated; height
saturations beat `(H/s)^0.14` and a det split made things worse. An ±8%
structured residual at s = 8/12 refused to yield to any added mechanism
(wall-length b/s saturations, ln² Pi2 curvature) — because it was not
physics: the b10_s12 profiles never exceed E = 1.06 (median 0.89 — the
street *attenuates*), so their "peaks" are noise floors. Fitting on the
channelling regime only (E >= 1.2, 88 configs) collapsed the residual to
<=2.5% and improved LOGO 8.7% → 6.7%. The excluded 8 are self-consistently
flagged weak by the resulting gate.

**The master curve.** The 71 R_half-scaled profiles collapse onto one curve
(median IQR 0.16, vs 0.29 for `r/(b+s)` or `r/R_peak` scaling). Two
corrections after inspection: (1) the pointwise median of misaligned peaks
never reaches 1, so a median-fitted g under-attains every peak by ~9% —
refitted on the pooled point cloud with a unit-peak constraint (costs ~1 pp
of profile MAPE, removes the peak bias entirely; the peak is the
safety-critical number). (2) An attenuation-tail term in g distorted the
shape *inside* the zone of interest — the tail (no channelling) was dropped
from the fit altogether. Configurations whose measured excess never halves
within 100 m (17, all s = 20) are consistent: their predicted `R_half`
lies beyond the measured domain.

---

## 4. Known limits, stated plainly

- **Domain**: channelling regime only (gate first); `x <= 1.6` (envelope:
  2.16); the simulated envelope of geometries (b 10–30, s 5–20, H 4–24,
  W 50–1500). The worst profile errors (26–29%) are the `Pi2 = 0.44`
  corner (narrowest street, largest charge) — the same corner where every
  formula system in this project degrades — and configs where the measured
  decay is faster than predicted (`R_half` over-predicted, e.g. b30_s5 det2
  at large W).
- **g is an envelope shape, not the profile**: real profiles staircase
  around it at the intersections (inter-config scatter ≈ ±0.15 in
  normalized units); a config with double structure (e.g. a second rise at
  the far crossing) is averaged through.
- The strip is the street axis — the *extreme* direction. As a gate this is
  conservative; it says nothing about the angular distribution.
- `E` here is a direct pressure-ratio profile; it is related in spirit but
  **not identical** to the thesis Λ (defined via equivalent distances from
  MaxR over 91 sectors). Do not substitute one for the other.
- The envelope calibration is in-sample (88 configs); expect slightly under
  95% coverage on new geometry.
- The 8 non-channelling configurations (b10_s12 all four, det1_b15_s20 at
  W <= 500) have no meaningful E_peak at all; the four b10_s12 streets
  attenuate over their whole length.

---

## 5. Artefacts

| what | where |
|---|---|
| measurement tool (strip/ring profiles, derivatives) | `tools/pressure_profile/pressure_profile.py` |
| anchor measurement (slope-fit decay; batch, all 96) | `tools/e_profile/measure_anchors.py` |
| master-curve + R_half refitter (reproducible) | `tools/e_profile/fit_master_curve.py` |
| model tool (predicted vs measured E(r), gate, envelope) | `tools/e_profile/e_profile.py` |
| per-config anchors, all 96 (slope-fit, production) | `outputs/check_results/street_anchors.csv` |
| per-config scalars, crossing-era (legacy, kept) | `outputs/check_results/r_peak_all96.csv` |
| master curve (x-binned table) | `outputs/check_results/master_curve_g.csv` |
| full-profile validation, 88 configs | `outputs/check_results/e_profile_validation_88.csv` |
| collapse figure | `outputs/figures/e_profile/master_curve_collapse.png` |
| per-config figures | `outputs/figures/e_profile/all88/` |
| intersection diagnosis of the old marker | `outputs/check_results/rlocal_diagnosis.csv` |

The scripts that originally produced `r_peak_all96.csv` and the first `g`
fit were one-off and never kept; `measure_anchors.py` and
`fit_master_curve.py` are their reproducible replacements.

## 6. Negative results worth keeping

1. **No det split**: one law covers mid-street and intersection charges
   (a det-specific constant worsens LOGO 8.7% → 11.3%).
2. **`H/W^(1/3)` does not drive strength** (exponent −0.09 when offered
   freely); height enters only through the saturations.
3. **Scaled-distance space is a trap for these lengths**: `Z_peak` vs `Pi2`
   correlates at +0.877 purely through the shared `1/W^(1/3)` divisor
   (within-family slope exactly 1.00). Metric lengths must be normalized by
   geometric lengths only.
4. **A field-derived "locality radius" does not exist**: the angular spread
   of urban/free-field never settles below ×2 inside the domain — the field
   never becomes isotropic; only the engineering criteria close.
5. **Fit-splitting, anchors, minimax, added flexibility** (from the wider
   project context) and, here, wall-length saturations and Pi2 curvature:
   all tried, none survived validation.
6. **A better decay model does not exist to be found — measured three ways**
   (2026-08-04, after the slope-fit anchor made the target trustworthy):
   - freeing the block-period exponent of `R_half` (fits +1.12) is *worse*
     end-to-end than pinning it at 1 (mean 10.1% vs 9.8%) — the dimensional
     prior beats the fit;
   - adding `Pi2` (real physics per the within-family test, §1) is worse
     still (10.3%, p90 20.3% vs 17.4%) — its LOGO exponent collapses to
     +0.07 and the extra parameter buys variance;
   - composing `R_half = R_peak_model + ln2 * L_decay_model` from separately
     fitted anchors is worst (10.8%) — `L_decay`'s 42% LOGO noise enters
     directly.
   The **ceiling test** closes the avenue: with the *measured* `R_half`
   (a perfect decay model) the end-to-end error improves only 10.3% → 10.0%,
   and with both anchors measured, 9.4%. The remaining error therefore lives
   in the **shape** — the per-crossing staircase that g averages through —
   not in the anchors. Any future accuracy work belongs there.
