# The Street-Channelling Model — E(r) Along the First Street

A closed-form model for **where strong local (channelled) behaviour of the
peak pressure exists, how strong it is, and how far it extends** along the
first street, built from the Pi groups alone. This document records the
final model, the measurement that defines it, the validation, and the
investigation that produced it — including the dead ends, several of which
changed the direction of the work.

Everything here is pressure-only, measured on the street-axis strip of the
96-configuration dataset. The implementation is `blastlib/street/`
(measurement → anchors → fitting → model → validation → figures, one module
per layer) with thin CLIs in `tools/street/`; every number below is
reproduced by `tools/street/street_parity.py` against the pinned artefacts
(snapshot commit `bf8eefe`). This 2026-08-06 revision is a clean-room
rewrite of the original tools; it also corrects four stale claims the
rewrite's parity work uncovered (§6, corrected-claims table).

---

## 1. The final model

Inputs: building size `b`, street width `s`, height `H` [m], charge `W`
[kg], detonation type (does **not** enter — tested and rejected, §8).

Derived groups: `sqrt(rho) = b/(b+s)` (wall continuity), `Pi2 = s/W^(1/3)`,
`H/s`, `H/W^(1/3)`.

```
E(r)   = 1 + (E_peak - 1) * g(r / R_half)          valid to r = 1.6*R_half

E_peak = 1 + 2.69 * sqrt(rho)^1.81 * Pi2^-0.50
           * (1 - exp(-4.56*H/s)) * (1 - exp(-7.07*H/W^(1/3)))

R_half = 1.28 * (b+s) * sqrt(rho)^-1.07 * (H/s)^0.27     [metres]

g(x)   = 59.9 * x^2.48 * exp(-4.75*x)                    unit peak at x = 0.52
```

Constants (all in `blastlib/street/constants.py`, frozen by test):

| block | values | provenance |
|---|---|---|
| `EPK` | 2.69 / 1.81 / −0.50 / 4.56 / 7.07 | **PINNED-heritage** — the original fitter was a one-off script never kept. Formula-level parity is proven (reproduces the pinned validation table's `E_peak_pred` at 3 dp, all 88 rows); a verification refit exists (§5) but is never adopted. |
| `RHALF` | 1.28 / −1.07 / 0.27 | refit-reproducible: `fitting.fit_r_half` re-derives 1.2850 / −1.0700 / 0.2721 from the pinned anchors (log-space OLS, `(b+s)` exponent pinned at 1) |
| `G` | 59.9 / 2.48 / 4.75 | refit-reproducible: `fitting.fit_master_curve` re-derives 59.8843 / 2.4838 / 4.7467 (unit-peak constrained, 75 profiles / 11,545 points, rms 0.206). The 1-dp rounding of A overshoots the exact unit peak by 0.1% (max g = 1.00096) — accepted and frozen. |
| `ENV` | S=1.35, f=1.20 | PINNED-heritage; true calibration stats in §7 (corrected 2026-08-06) |

(Constants updated 2026-08-04, when the decay anchor moved from a crossing
detector to a slope fit — §4. The functional forms did not change.)

### Physical reading

- `sqrt(rho)^1.81 ≈ rho^0.9`: channelling needs **both walls at once** — the
  wave ping-pongs between them; the probability a cross-section has solid
  wall on both sides is `(b/(b+s))^2 = rho`.
- `Pi2^-0.50`: confinement weakens as the square root of the street width in
  charge lengths.
- The two height saturations encode "walls taller than ~s/6 and ~W^(1/3)/6
  act infinite" — the measured H12→H24 saturation and the thesis finding
  that peak pressure is nearly blind to height. They give the correct
  `E → 1` limit as `H → 0`, which a power law cannot.
- `g`: quadratic onset (reflections take two walls to build), peak at
  `0.52*R_half`, `g(1) = 0.518` (the half-decay anchor emerges from the fit,
  it is not imposed).

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

The city has **two boundaries with two different scalings**. The
convergence radius grows with the charge (`R_conv = W^(1/3) * Z_conv(Pi)` —
Hopkinson). The local-zone extent is fixed in the fabric
(`R_half = (b+s) * f(sqrt(rho), H/s)` — metres of geometry, no W). The
charge decides only *whether* the local zone is dangerous (via `Pi2` in the
gate), not *how far* it reaches. Forcing `Pi2` into the extent formula
returns exponent +0.07 and no end-to-end gain. Intuition: channelling lives
between the intersections, and the intersections do not move when the bomb
grows — they only fill harder.

One precision added by the slope-fit anchor (§4): the statement holds for
the *extent* `R_half`, but the decay **rate** per metre does carry a weak,
real charge dependence — within fixed geometry, `d ln L_decay / d ln W` has
median **−0.108** (IQR [−0.22, −0.04], 16/27 (family, det) groups above
0.1 in magnitude), matching the pooled `Pi2^+0.28`. A bigger charge fills
the street harder and its excess dies off slightly faster per metre; over
the full 30× charge range this is a ~30% effect on `L_decay`. It is left
out of the model deliberately: exploiting it was tried and costs more than
it returns (§8, "a better decay model does not exist").

---

## 2. Scope and the gate

**Gate.** If `E_peak < 1.5` the street does not channel strongly — no
strong local zone exists and the profile formula is not meaningful (below
E ≈ 1.2 the measured "peak" is a noise floor, not channelling).

The honest truth table under the shipped constants (measured 2026-08-06;
`validation.gate_table`, truth = measured anchors `E_peak >= 1.5`):

| | count | configs |
|---|---|---|
| correct | **92/96** | |
| misses (predicted weak, measured strong) | 2 | config_67, config_70 (b30_s20 det2 at W=50: predicted 1.43/1.46, measured 1.65) |
| false alarms (predicted strong, measured weak) | 2 | config_78, config_80 (b10_s12 det1 at W=1000: predicted 1.58/1.59, measured 1.18) |

An earlier revision of this document claimed "zero false alarms"; that was
measured against the pre-2026-08-04 constants and is wrong under the
shipped ones. The false alarms are at least the conservative direction
(predicting danger where none was measured), and both sit in the b10_s12
family whose streets attenuate outright (§8).

**Domain**: channelling regime only (gate first); `x = r/R_half <= 1.6`
(envelope: 2.16); the simulated envelope of geometries (b 10–30, s 5–20,
H 4–24, W 50–1500), first street, ground level. The strip is the street
axis — the *extreme* direction; as a gate this is conservative, and it says
nothing about the angular distribution. `E` here is a direct
pressure-ratio profile; related in spirit but **not identical** to the
thesis Λ (defined via equivalent distances from MaxR over 91 sectors) — do
not substitute one for the other.

---

## 3. How the measurement is defined

- **Strip, not rings.** All quantities are measured on the first-street
  strip `0 <= Z <= s/2`, binned into 0.5 m cross-street slices along the
  street axis (`blastlib/street/strip.py`). Every slice holds the same
  ~51–68 cells at every distance. Angular rings were abandoned for a
  measured reason: their sample composition changes with radius — the
  per-ring cell count is set purely by the building layout (identical in
  all 85 bins for two configs 30× apart in charge) and dips to local minima
  exactly where several early "detections" landed. The median jumped
  because the *sample* changed, not the field.
- `E(r) = mean(P_urban) / mean(P_ff)` per slice, the free field taken from
  the charge-only reference simulation **on the same cells** — never from
  `free_field_data.csv` (axis-sampled; the mesh reference is anisotropic by
  9.6% between directions, which the cell-by-cell ratio cancels for free).
- Slices inside the exclusion radius are dropped from the RAW profile
  **before** smoothing (dropping them after, or merely skipping them at
  read time, contaminated the first outside bins through the running
  mean). Smoothing is a ~2.5 m physical running mean — the kernel adapts
  to the slice width.
- Everything is capped at **100 m**: exactly grid 1's extent (0.15 m
  cells), so the whole profile lives on one resolution with no grid
  handoff.
- **The stored 2-D fields hold finite values inside building footprints**
  (an over-roof envelope, ~100% of grid-1 cells valid). Any spatial mask
  must come from geometry, not from data validity — a validity-based
  "crossing detector" and an early strip-orientation check were both
  invalidated by this and redone. The strip needs no mask at all: buildings
  start at `Z = s/2` by construction.
- For det2 the strip represents both streets (θ = 0 ≡ θ = 90, verified
  digit-for-digit).

**The quirk ledger.** The pinned tables were shaped by a handful of
implementation choices — some deliberate conventions, a few accidents of
the reference code. All are preserved, named Q1–Q7, and documented with
what breaks if each is "fixed", in `blastlib/street/conventions.py`:
Q1 the strict-vs-inclusive exclusion cut (empirically a no-op, asserted by
the parity harness every run); Q2 the two smoothing conventions (physical
2.5 m for anchors/fitting, fixed k=5 for validation — identical at
dr = 0.5); Q3 banker's rounding silently disabling smoothing at dr ≥ 1 m
(so the 2 m stability run measures a *raw* slope fit); Q4 kernel edges
left raw; Q5 the two `E_peak` measurement conventions (anchors vs
validation — config_56 reads 2.714 vs 3.145); Q6 the decay-window
terminator being exclusive; Q7 a CSV row for every config, NaN where
nothing fits.

---

## 4. The decay anchor — a slope fit, not a crossing (2026-08-04)

`R_half` was originally "the first distance past the peak where the excess
`E−1` halves, 3 consecutive slices". That single-crossing detector had two
measured failure modes: re-measured with 2 m slices instead of 0.5 m it
moved **19.6% at the median** (one crossing inherits the full staircase
noise of the intersections), and on plateau-topped profiles the halving
lands wherever the plateau happens to end.

The production anchor is a **slope fit over the whole fall**
(`blastlib/street/anchors.py`): OLS of `ln(E−1)` against `r` from where the
excess first drops below 85% of its peak value (skipping the plateau, which
carries no slope information) down to where it drops below max(25% of peak,
the E = 1.2 noise floor), requiring ≥ 6 slices spanning ≥ 4 m and a
negative slope; otherwise NaN, honestly — the s = 20 family genuinely does
not decay within 100 m. The decay length `L_decay` (metres per e-fold)
gives

    R_half = R_peak + ln(2) * L_decay

— the same semantics, carried by every slice of the fall instead of one
crossing. Measured properties:

| | crossing (old) | slope fit |
|---|---|---|
| stability, 0.5 m vs 2 m slices (median over configs) | 19.6% | **1.7%** |
| fit-window convention (85–25 vs 90–30) | — | 10.4% median |
| configs with a measurable decay | 79 | 75 (+ the 2 m run finds 63) |
| Pi-predictability of the fall scale | R² 0.25 | **R² 0.52** |

The window convention is now the dominant uncertainty of the anchor — an
honest stated convention rather than mesh noise. `L_decay` is independent
of `R_peak` noise by construction (a slope does not care where the axis
origin sits). The legacy crossing detector is still measured into the
`R_half_cross` column of the anchors table for comparison, never for
production.

One number that looks worse and is not: the collapse IQR under the slope
anchor (0.222) reads worse than under the crossing anchor (0.189), because
the crossing anchor pins `y(x=1) = 0.5` for every profile *by
construction* — it is self-aligned at exactly the locus the IQR rewards.
The fair comparison is end-to-end profile error with predicted anchors,
where the slope pipeline wins on mean, median and p90 (§6).

---

## 5. Fitting

All in `blastlib/street/fitting.py`, reproducible from
`street_anchors.csv` + the NPZ stores; the parity harness re-derives every
constant on every run.

- **Master curve `g`** — fitted to the pooled point cloud of the 75
  slope-anchored channelling profiles (11,545 normalized points,
  `0 < x <= 1.65`), NOT to the pointwise median: the median of misaligned
  peaks never reaches 1, so a median-fitted g under-attains every measured
  peak by ~9%. The **unit-peak constraint** (`A = (q/p)^p e^p`, two free
  parameters) removes that bias entirely at a cost of ~1 pp of profile
  MAPE — the peak is the safety-critical number. An attenuation-tail term
  distorted the shape *inside* the zone and was dropped from the fit
  altogether. R_half-scaling gives the best collapse (median IQR 0.16 vs
  0.29 for `r/(b+s)` or `r/R_peak`) — with the §4 caveat that collapse-IQR
  comparisons between anchor *types* are unfair.
- **`R_half` constants** — closed-form log-space OLS with the `(b+s)`
  exponent **pinned at 1** by the dimensional prior (freeing it fits 1.12
  and scores worse end-to-end, §8). MAPE 16.5% against its own anchor (not
  comparable to the crossing era's 12.6%, which was scored against the
  noisier crossing anchor). Configurations whose measured excess never
  halves within 100 m (17, all s = 20) are consistent: their predicted
  `R_half` lies beyond the measured domain.
- **`E_peak` — the provenance gap, stated plainly.** The script that fitted
  the shipped constants was one-off and never kept. The constants are
  therefore PINNED: canonical as published, frozen by test, provenance
  documented rather than re-derivable. `fitting.fit_e_peak` +
  `fitting.logo_e_peak` implement the fit as best it can be reconstructed
  (log-space least squares on the excess, 88 channelling configs, LOGO
  over (det, b, s, H) families) as **verification only**: the refit lands
  at C=2.52, a=1.67, b=−0.52, k_hs=4.90, k_hw=5.00 with in-sample MAPE
  6.8% and LOGO 7.7% over 34 families — close to, and never replacing, the
  pinned 2.69/1.81/−0.50/4.56/7.07 (published LOGO 6.7% over "36 geometry
  families", from the lost fitter and a slightly different family roster).
  Fitting on all 96 instead of the channelling 88 was the source of a fake
  ±8% structured residual at s = 8/12 (§8); the 88-membership is computed
  (`anchors E_peak >= 1.2`), never hardcoded.

---

## 6. Validation

Scoring convention (`blastlib/street/validation.py`, locked clause-by-
clause by tests): slices with measured smoothed `E >= 1.2` within the model
domain, at least 5 per config; MAPE relative to the smoothed measurement;
the model draws nothing past `x = 1.6`, so grid slices in `1.6 < x <= 2.16`
are selected but not scored.

| quantity | score |
|---|---|
| `E_peak` | LOGO MAPE **6.7%** (published; verification refit 7.7%, §5) |
| `R_half` | MAPE **16.5%** against the slope anchor |
| `g` vs the pooled normalized cloud (75 profiles, 11,545 points) | rms 0.206 |
| full profile `E(r)`, channelling zone, 88 configs | mean **9.7%**, median **8.5%**, p90 17.3%, max 31.0% |
| the crossing-anchor pipeline on the same slices | mean 10.4%, median 9.4%, p90 18.0%, max 28.5% |
| attained-peak bias | **−0.4%** (the unit-peak constraint removes a −9% built-in bias) |

(The headline row is recomputed from the pinned
`e_profile_validation_88.csv`; earlier text rounded it to 9.8 / 17.4.)

Worst cases: config_56 (31.0% — the plateau top), then the `Pi2 = 0.44`
corner (config_03/06/57, 25–26%) — the same corner where every formula
system in this project degrades.

### Corrected claims (2026-08-06)

The clean-room parity work recomputed every published number; four did not
survive. Tests now lock the measured values so code and document cannot
drift apart again.

| claim | earlier text | measured now |
|---|---|---|
| envelope in-sample coverage | 95.0% | **96.34%** |
| slices exceeding the envelope by > 0.15 | 1.5% | **0.73%** |
| envelope mean overprediction | 24% | **27.2%** |
| largest single exceedance | 0.96 at config_03 | **0.723 at config_26** |
| gate false alarms | zero | **2** (config_78/80, conservative direction) |
| `g(1)` | 0.48 | **0.518** |

Root cause: f and S (and the prose around them) were calibrated against the
pre-2026-08-04 crossing-era constants and never re-measured after the
refit. The envelope turned out slightly *more* conservative than
documented; it was kept rather than recalibrated, because loosening a
published safety bound to restore a cosmetic 95.0% would change a design
number for nothing.

---

## 7. The design envelope

```
E_env(r) = 1 + 1.20 * (E_peak - 1) * max{ g(x*t) : t in [1/1.35, 1.35] }
```

`f = 1.20` absorbs amplitude scatter (E_peak under-predictions), the
dilation `S = 1.35` absorbs location scatter (late peaks, slow tails) and
extends the domain to `1.6*S = 2.16*R_half`. The central curve is a best
estimate — measurements exceed it about half the time by construction; the
envelope is the bounding version. True in-sample calibration on the 88
(§6 table): coverage 96.34% of channelling-zone slices, 0.73% exceed by
more than 0.15 in E, mean overprediction 27.2% (the price of a bound),
worst single exceedance 0.723 at config_26. The calibration is in-sample;
expect somewhat less coverage on new geometry.

---

## 8. The investigation: what was tried and what killed it

The path matters because three "clean" intermediate results were later
overturned by specific measurements.

**R_local as a protocol boundary.** The starting question was to split the
domain into local / formulas / free-field. The pipeline already contains an
inner boundary (`max(R_exclusion, 2*W^(1/3))`, never empties the band);
pushing it outward to block-period multiples emptied the middle zone for up
to 26/96 configurations and correlated with nothing.

**Steepest-descent detectors are intersection finders.** Locating "the end
of channelling" via derivatives of the axial profile went through several
iterations: `dP/dR` finds where the *wave* is strong, not where the street
stops acting; `d lnP/d lnR` (moving log-log regression, bandwidth fixed in
ln R after an 18× effective-bandwidth bug was found and fixed) gave a
stable marker — 94/96 configurations reproduce it across bin widths, and
within a fixed geometry it moves 1% while `W^(1/3)` moves 50%. **But**:
tested against crossing positions predicted purely from `(det, b, s)`,
**77/78 clean detections lie inside a street crossing** (±1 m, vs 42%
chance coverage; median 1.2 m from the crossing centre). The "steepest
fall" is the venting notch at whichever intersection vents hardest — real
physics (the channelled excess vents at every crossing), but not a zone
boundary. Its apparent constancy (~69 m, unexplainable by any Pi fit — a
constant beat the best power law 23.4% vs 19.5%) was block periods of
20–50 m putting everyone's 2nd–3rd crossing at 40–100 m.

**The reframe** (user's): R_local should mark *where the local behaviour
is strongest*, not where something ends. That turned the object of
interest from a derivative feature into the profile triplet (`R_peak`,
`E_peak`, `R_half`) — all three of which finally correlate with geometry
(`corr(R_peak, b+s) = +0.73` vs +0.09 for the old marker).

**Detector minutiae that mattered.**

- Slices inside the exclusion radius must be dropped *before* any
  smoothing or fitting, not merely skipped when reading the result.
- At 0.5 m slices the old marker pinned to the inner boundary in 4/10 test
  configs; the peak-search start was moved to `b+s` (det1) / `s/2+b`
  (det2) — a search bound local to this suite, deliberately not touching
  `blastlib.geometry.exclude_radius`, which feeds `R_conv` and every
  fitted coefficient upstream.
- **A 10 kPa absolute clause was tried twice as a search bound and removed
  twice**: an absolute threshold re-imports the charge through the back
  door (within-family CV of the marker jumped 0.010 → 0.255) — the same
  failure mode as the project's old absolute impulse criterion. Metric
  lengths may be normalized only by geometric lengths.
- The 100 m cap is exactly grid 1's extent, keeping the whole profile on
  one resolution.

**Fitting E_peak.** Candidate physical forms were LOGO-validated; height
saturations beat `(H/s)^0.14` and a det split made things worse. An ±8%
structured residual at s = 8/12 refused to yield to any added mechanism
(wall-length b/s saturations, ln² Pi2 curvature) — because it was not
physics: **the b10_s12 profiles never exceed E = 1.06 (median 0.89 — the
street *attenuates*)**, so their "peaks" are noise floors. Fitting on the
channelling regime only (E ≥ 1.2, 88 configs) collapsed the residual to
≤ 2.5% and improved LOGO 8.7% → 6.7%. (Two of the excluded family are
nonetheless gate false alarms under the shipped constants — §2.)

**Negative results worth keeping.**

1. **No det split**: one law covers mid-street and intersection charges (a
   det-specific constant worsens LOGO 8.7% → 11.3%).
2. **`H/W^(1/3)` does not drive strength** (exponent −0.09 when offered
   freely); height enters only through the saturations.
3. **Scaled-distance space is a trap for these lengths**: `Z_peak` vs
   `Pi2` correlates at +0.877 purely through the shared `1/W^(1/3)`
   divisor (within-family slope exactly 1.00).
4. **A field-derived "locality radius" does not exist**: the angular
   spread of urban/free-field never settles below ×2 inside the domain —
   the field never becomes isotropic; only the engineering criteria close.
5. **Fit-splitting, anchors, minimax, added flexibility** (from the wider
   project context) and, here, wall-length saturations and Pi2 curvature:
   all tried, none survived validation.
6. **A better decay model does not exist to be found — measured three
   ways** (2026-08-04, after the slope-fit anchor made the target
   trustworthy): freeing the block-period exponent of `R_half` (fits
   +1.12) is *worse* end-to-end than pinning it at 1 (mean 10.1% vs 9.8%);
   adding `Pi2` (real physics per the within-family test, §1) is worse
   still (10.3%, p90 20.3% vs 17.4%) — its LOGO exponent collapses to
   +0.07 and the extra parameter buys variance; composing
   `R_half = R_peak_model + ln2 * L_decay_model` from separately fitted
   anchors is worst (10.8%) — `L_decay`'s 42% LOGO noise enters directly.
   The **ceiling test** closes the avenue: with the *measured* `R_half`
   (a perfect decay model) the end-to-end error improves only
   10.3% → 10.0%, and with both anchors measured, 9.4%. The remaining
   error therefore lives in the **shape** — the per-crossing staircase
   that g averages through (inter-config scatter ≈ ±0.15 in normalized
   units; a config with double structure is averaged through) — not in
   the anchors. Any future accuracy work belongs there.

---

## 9. Artefacts and reproduction

| what | where |
|---|---|
| every constant, with its justifying measurement | `blastlib/street/constants.py` |
| quirk ledger Q1–Q7 | `blastlib/street/conventions.py` |
| strip measurement | `blastlib/street/strip.py` |
| anchor measurement (slope-fit decay; batch, all 96) | `blastlib/street/anchors.py` |
| master-curve + R_half refitter; E_peak verification refit | `blastlib/street/fitting.py` |
| the closed-form model, gate, envelope (pure, no I/O) | `blastlib/street/model.py` |
| 88-config scoring, gate table, envelope stats | `blastlib/street/validation.py` |
| every figure writer (shared with the GUI preview) | `blastlib/street/figures.py` |
| batch pipeline (anchors → fit → validate → figures) | `tools/street/street_pipeline.py` |
| single-config / free-geometry figure CLI | `tools/street/street_figure.py` |
| **parity harness** (permanent regression net) | `tools/street/street_parity.py` |
| per-config anchors, all 96 (production) | `outputs/check_results/street_anchors.csv` |
| master curve (x-binned table) | `outputs/check_results/master_curve_g.csv` |
| full-profile validation, 88 configs | `outputs/check_results/e_profile_validation_88.csv` |
| parity report (regenerated by the harness) | `outputs/check_results/street_parity_report.md` |
| collapse figure | `outputs/figures/e_profile/master_curve_collapse.png` |
| per-config figures (+ all88/, env/, pressure_check/) | `outputs/figures/e_profile/` |
| per-config scalars, crossing-era (legacy, kept) | `outputs/check_results/r_peak_all96.csv` |
| intersection diagnosis of the old marker | `outputs/check_results/rlocal_diagnosis.csv` |
| GUI | "Street Model" (batch) and "Street Preview" (live) tabs |
| tests | `tests/test_street_*.py` (fast subset data-free; `@slow` = full-store parity) |

Reproduction: `python tools/street/street_pipeline.py` regenerates the
three production CSVs and all figure sets;
`python tools/street/street_parity.py` regenerates everything into
`outputs/check_results/street_parity/` and compares against the pinned
files at rel 1e-12 (pinned CSVs sit up to 1 ulp off recomputation on this
machine — never compare bit-exact), writing the report. **Pinned-CSV
update policy**: the three production tables change only through a
deliberate, documented model revision — a parity-passing run reproduces
them to the last digit; anything else is a finding, not drift to be
committed. Exploratory runs at non-default dr/window land in suffixed
filenames by construction.

The one-off scripts that originally produced `r_peak_all96.csv`, the first
`g` fit, the validation table and three of the four figure sets were never
kept; `blastlib/street` is their reproducible replacement (figure formats
reconstructed from the shipped PNGs — structural parity, by design).

---

## 10. Provenance and changelog

- **Crossing era** (…→ 2026-08-04): `R_half` from the run-of-3 crossing
  detector; constants of that era survive in `r_peak_all96.csv` and as the
  `R_half_cross` comparison column.
- **Slope era** (2026-08-04): the decay anchor moved to the slope fit
  (§4); `RHALF` and `G` refit; `EPK`/`ENV` carried.
- **Clean-room rebuild** (2026-08-06): implementation rewritten from zero
  as `blastlib/street/` + `tools/street/`; reference implementation and
  pinned artefacts snapshot at commit `bf8eefe`; parity proven (anchors
  and both derived tables reproduce at max|Δ| = 0, constants to full
  precision, headline stats exact) under Python 3.12.10 / numpy 2.4.4 /
  scipy 1.17.1; the retired `tools/pressure_profile` + `tools/e_profile`
  (ring mode, impulse target, raw-field variants, derivative panels
  included) live on in git history at that commit. Four stale claims
  corrected (§6) and locked by tests.
