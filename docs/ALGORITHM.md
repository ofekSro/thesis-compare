# The Analysis Algorithm

> **Revision 2026-09-27.** This document was updated after the audit of the
> same date: the building mask now precedes the cross-grid fill (wall-skin
> sentinel cells no longer drive the scans), the per-direction MaxR level is
> sampled from the grid-filled reference, and the RadiusI production model
> was replaced by the unified five-term form. All quantitative statements
> were refreshed from the regenerated tables; old vs new values are in
> `outputs/check_results/raw_mask_and_unified_model_change_note.md`.
> Sections NOT yet refreshed (their studies were not re-run): the safe
> domain (audit decision D6 pending), the coarsening/mesh-sensitivity
> measurements in Limitations, and the block-period analysis — each is
> marked in place.

## Problem

For an urban configuration — building size *b*, street width *s*, height *H*,
charge weight *W*, detonation type (street / intersection) — predict two things:

1. **Convergence radius R_conv** — the distance beyond which the urban blast
   field is indistinguishable from the free field, to an engineering tolerance.
2. **Z_urban** — inside that radius, the urban scaled distance that carries the
   same load a free-field distance Z_free would.

Both are computed separately for peak **pressure** and for **impulse**.

## The dimensionless framework

Everything is built from Buckingham-Pi groups, so the formulas hold across scale
rather than for one charge size:

| group | meaning |
|---|---|
| ρ = b²/(b+s)² | plan-area density (fraction of ground built on) |
| Π₂ = s/W^⅓ | street width in Hopkinson-scaled units |
| H/s | canyon aspect ratio |

The charge weight enters **only** through the Hopkinson length W^⅓, and the
canonical relation is R = W^⅓ · Z. This is why a fit on 96 configurations
generalizes: W is not a free axis, it is absorbed into the scaling.

### Why the Hopkinson cube root is the right scaling here

Hopkinson–Cranz similarity says two charges of the same explosive and shape
produce geometrically similar blast fields when distances are scaled by W^⅓:
the energy released grows with the mass, the volume it expands into grows with
the cube of a length, so all field structure — arrival times, peak pressures,
the whole waveform — repeats at equal Z = R/W^⅓. Three independent reasons this
applies to the present problem, in increasing order of strength:

1. **Dimensional necessity.** With energy and distance as the only dimensional
   inputs, Buckingham's theorem leaves exactly one length scale, W^⅓. Any
   correlation not expressed in it would carry hidden units and could not be
   transported to another charge size.
2. **The free field very nearly obeys it.** The reference simulations collapse
   onto a single curve in Z across the whole weight range to a coefficient of
   variation of ≈ 4.3% in peak pressure. State the convention, because the
   number depends on it: as (max − min)/mean the same spread is 10–17%, and it
   is **a systematic trend rather than scatter** — free-field peak pressure at
   fixed Z rises about 11% from 50 kg to 1500 kg (57.4 → 63.7 kPa at Z = 4),
   monotonically at every Z ≤ 12. The direction is what a resolution effect
   predicts: at fixed cell size the near field of the smallest charge is the
   least resolved, so its peak is smeared low. The baseline is therefore
   Hopkinson-similar to within about a tenth, by measurement — which is a
   support for the scaling, not a proof of it.
3. **The data recovers the exponent on its own.** Refitting the impulse law
   with the charge exponent left free — ln R = c + α·ln W + p·ln ρ + q·ln(H/s)
   + …, imposing nothing — returns **α = 0.340** (street) and **α = 0.307**
   (intersection) against the cube root's 0.333. The scaling is therefore a
   result read out of the measurements, not a constraint imposed on them.

The practical consequence is what makes the fit possible at all: radii span
20–140 m across the dataset, and most of that span is just W^⅓. Dividing it out
leaves Z varying by only a factor ≈ 2.2, and that residual variation is pure
urban geometry — which is what 96 configurations can actually resolve. Fitting
R directly would force the model to learn the charge law from five weights,
turning every intermediate charge into an interpolation risk for no gain in
accuracy (relative errors in R and in Z are identical, since W^⅓ is exact).

The scaling has a stated limit: it holds for concentrated high-explosive
charges of similar shape and confinement, which is the family simulated here.
It does not cover deflagrations, thermobarics, or charges whose casing or
stand-off changes the near-field energy release.

## Step 1 — Measuring the radii from the simulation

Each configuration is a CFD field on three nested grids. For every cell we form
the ratio urban/free-field, for pressure and for impulse.

Before anything else, cells inside building footprints are removed. The solver
writes a ~1 Pa sentinel into every in-footprint cell, and **the mask is
computed on the raw solver field, before the cross-grid max-fill** (since
2026-09-27). The order matters: filling first let the coarser grid's
interpolation raise one or two wall-skin cells above the mask threshold, and
those sentinel-valued cells then entered both scans — pinned as "converged"
on the pressure side and counted as guaranteed violations on the impulse
side, where they set the radius at the outermost building wall rather than
in the streets. Masking the raw field removes them (RadiusI moved by a
median of −32%, RadiusP by +5%; see the change note in `check_results`).

- **Convergence radius.** The first quadrant is split into 91 one-degree
  sectors. In each sector we scan inward from far to near and mark the point
  where the ratio first leaves a tolerance band and stays out (three consecutive
  cells). Pressure and impulse use physically-appropriate tolerances: pressure a
  10 kPa band (below which load differences are structurally negligible),
  impulse a Hopkinson-scaled band |ΔI|/W^⅓ < 20, which — unlike an absolute
  Pa·s band — picks the *same* scaled contour at every charge weight. The 91
  sector radii are collapsed to one scalar by an equivalent-area rule,
  R = √(4A/π), which is stable because it integrates over all directions rather
  than trusting one.

- **The soft pressure criterion.** A hard 10 kPa indicator has a failure mode:
  beyond Z ≈ 10 the free-field pressure itself sits near 10 kPa, so real ×2
  amplification lobes whose peak ΔP grazes the threshold flip tens of metres of
  radius on a small physical change (measured cliff: two configurations
  differing only in building height jumped 62 m vs 38 m on the pre-mask
  store; 64.6 m vs 39.9 m on the current one — the cliff persists). The production
  measurement therefore replaces the band's indicator with a smoothed Heaviside
  (tanh projection): each cell gets an exceedance weight
  w = gate · τ(|ΔP|/20 kPa), with τ the Wang–Lazarov–Sigmund projection of
  sharpness β, pinned so w = 0 at ΔP = 0, w = ½ exactly at the old 10 kPa edge
  and w = 1 from 20 kPa up. The low-pressure floor (P < 10 kPa) and the ±5%
  ratio gate stay hard. The per-sector radius is then the *expectation of the
  same far-to-near three-consecutive-cell scan* under these per-cell
  probabilities (a three-state Markov chain over the streak length), so an
  isolated noisy cell still cannot fire a radius, and as β → ∞ the soft scan
  reproduces the hard one **bit-exactly** — the hard criterion is its limit,
  not a separate convention. Because the weights are built from the raw
  operands rather than the banded field, softening also restores sensitivity
  that the absolute band had discarded outright: along a channelling street
  where the urban field runs ≈2.3× free-field but ΔP ≈ 7.6 kPa stays under the
  threshold, the sector radius moves 49.9 → 68.5 m as β falls to 2, and back
  to 49.9 m as β → ∞ (config 58, θ = 0). Softness therefore buys
  cliff-robustness by paying in systematically longer radii wherever the field
  is amplified but weak — which is the same trade the band made in the other
  direction. **β = 3 is the production setting**, selected by a
  sensitivity scan over β ∈ {2, 3, 4, 6, 8, 12} as the only value satisfying
  both rules fixed in advance: the threshold-cliff gap between the two
  neighbouring configurations closes below 10 m (8.6 m), and the mean
  out-of-sample error rises by no more than 0.5 pp (+0.24 pp). The impulse
  criterion is untouched by all of this, and the soft tables carry the
  `req_soft3` suffix next to the hard `req` ones.

- **Z_urban.** For each integer Z_free we find the exceedance region — the
  outermost cells still delivering at least the free-field load — and collapse it
  with the *same* estimator. The exceedance level is sampled per direction
  from the reference field **max-filled across the grids, exactly as the
  urban field it is compared with** (since 2026-09-27; the raw fine-grid
  reference is deficient near its outer edge, which inflated a handful of
  large-charge impulse rows). Z_urban = R/W^⅓.

The single estimator collapses both radii from the same 91 sectors, so the
*aggregation* is shared. The per-sector criteria are deliberately not: R_conv
uses a tolerance band and a three-cell streak, MaxR a zero-tolerance single
outermost cell — so MaxR systematically overshoots R_conv, and rows whose
measured MaxR lies at or beyond R_conv are flagged (`beyond_*`) and excluded
from the Z_urban fit, with the deployed chain answering the Z_conv clip
there. The reported error therefore comes in two flavours (see Result).

## Step 2 — The prediction formulas

Fitted per detonation type. All terms are dimensionless.

**Convergence radius — pressure** (additive Pi):

    Z = C₀ + C₁·Π₂ + C₂·ρ·(Π₂ − a) + C₃·√ρ·(H/s)·(W^⅓/s − 1)

Each term is a mechanism, not a curve-fit monomial: the density term switches
sign at s = a·W^⅓; the canyon term flips at s = W^⅓, the physical crossover
between a street that channels the blast and one that blocks it; √ρ = b/(b+s) is
the fraction of the canyon wall that is solid. The coefficients are fitted by
least squares weighted 1/Z — minimizing squared *relative* error — so the loss
being minimized is the same quantity (MAPE) the validation reports.

**Convergence radius — impulse** (unified multiplicative form, one structure
for both detonation types; production since 2026-09-27):

    Z = A · Π₂^(C₄ + C₅·ln ρ + C₃·ln(H/s)) · exp(C₁·ρ√(H/s) + C₂·(ln H/s)²)

Impulse integrates every reflected arrival, so its radius is set by canyon
reverberation, and each factor is a mechanism: C₁·ρ√(H/s) is **trapping** —
wall continuity × canyon aspect, the same construct that drives the Z_urban
impulse model below; C₂ < 0 is **height saturation** — the height effect
peaks near H/s ≈ 1 and fades in both directions, which no pure power (H/s)^q
can represent; C₃ < 0 says **deep canyons mute the street-width effect** —
once the wave is trapped, width stops mattering; C₄ and C₅ are the
street-width baseline and its density coupling. ρ is the dominant variable:
removing its terms triples the held-out error, and it acts through two
channels (trapping and the Π₂ exponent). The previous separable power law
A·ρ^p·(H/s)^q·Π₂^r failed structurally on the sentinel-free data — its
fitted geometry exponents were near zero because the old, artefact radius
followed the I/W^⅓ = 20 contour (a function of W alone) to the nearest
wall; historical tables carrying it stay readable (`Formula='power'`).

**Z_urban** is written as an amplification factor Λ = Z_urban/Z_free, and here
the two loads need genuinely different structures:

- **Pressure** — *range_switch*:

      ln Λ = C₀ + C₁ · [ (Π₂ − A)/Z_free − ln Π₂ ] / ( Π₂·(s/H) + B )

  The 1/Z_free term is the key: pressure amplification **decays with distance**.
  Narrow streets amplify close in, wide streets attenuate, and both fade toward
  the free field — the signature of wavefront interference between the direct and
  reflected shocks. The denominator is open-canyon damping: wide, low canyons
  suppress the whole effect.

- **Impulse** — *canyon_trap*:

      ln Λ = C₀ + C₁ · ρ·(√(H/s) − C₂·ρ) / ( H/s + C₃·√Π₂ )

  There is **no distance term at all**. The canyon sets one amplification factor
  that holds at every range inside R_conv, because the integrated positive phase
  sees the whole reverberant enclosure, not a single arriving front. ρ·√(H/s) is
  trapping (wall continuity × aspect); −C₂ρ² is self-limiting (an over-dense
  block chokes its own streets).

Writing Λ rather than Z_urban directly builds in the correct proportionality to
Z_free and makes attenuation representable continuously: Λ < 1 (ln Λ < 0) is
attenuation, Λ > 1 amplification, with no separate classifier — the sign falls
out of the formula.

Predictions are finally clipped from above at Z_conv (beyond the convergence
radius the urban field *is* the free field, so Z_urban cannot exceed it) and
converted back by R = Z·W^⅓.

## Why the algorithm is sound

- **Dimensional consistency.** Every predictor is a dimensionless Pi group;
  W appears only as W^⅓. The formulas are therefore scale-invariant, not tuned to
  the tested charge sizes — the central requirement for a blast correlation.
- **The measurement is direction-consistent.** One equivalent-area estimator
  collapses both radii over the same 91 sectors, so the scalar is an integral
  rather than a fragile extreme. The per-sector criteria differ by design
  (band + streak for R_conv, zero-tolerance exceedance for MaxR), so MaxR
  overshoots R_conv systematically; the `beyond_*` flags record it and the
  Z_conv clip closes the chain — the closure is imposed, not assumed.
- **The criteria are physically calibrated.** The pressure tolerance sits at the
  load level below which structures are unaffected; the impulse tolerance is
  Hopkinson-scaled so it means the same thing at every charge weight.
- **The forms are mechanistic, not fitted noise.** Each term maps to a physical
  effect (channeling/blocking switch, canyon reflection, trapping, interference
  decay). The pressure-vs-impulse structural split is independently confirmed:
  swapping the two forms costs several points of accuracy, so the difference is
  real physics, not a modelling choice.
- **It is validated out-of-sample.** Accuracy is reported on held-out geometries
  under cross-validation, not on the fitting data, so the numbers reflect
  prediction, not memorization.

## Result

**The headline is the leave-one-geometry-out (LOGO) test** — whole (det,b,s,H)
families held out, constants refit per fold. That is the only test here that
measures what the model is for: predicting a geometry it has not seen.

The 500-split random test is reported below it as a supporting number, not as
the result, for a specific reason: the splits are stratified on detonation type
only, so **92.5% of held-out configurations have a sibling of the same
(det,b,s,H) in the training set** (minimum 60%). Since W divides out exactly
under Hopkinson scaling, predicting such a sibling is close to interpolation in
a variable the scaling already handles — so those splits estimate the charge
law, not the geometry law. Their median is 9.8% (P) / 11.1% (I) for the
convergence radius and 8.7% (P) / 10.4% (I) for Z_urban, with the production
configuration (soft β = 3 pressure criterion, raw-field mask, unified
impulse model).

Z_urban carries a second, honest yardstick since 2026-09-27: the fit-domain
error above is *conditional* on the held-out row's own measured MaxR and
R_conv — information a user never has. The `z_P_dep` / `z_I_dep` columns of
`cv_summary` grade the same models on the domain a user can identify
beforehand (predicted R_conv; `beyond` rows judged against the Z_conv clip):
median 8.7% (P) and 13.2% (I). Pressure is unaffected; for impulse the
deployable error is ~3 pp above the conditional one, and both are on record.

A third number appears in the run log and must never be quoted as accuracy:
the *best-split* MAPE is a minimum over 500 draws — a selection statistic. It
is what chooses the coefficients saved in `best_*.csv`, which is why those
files are for inspection only; the deployable coefficients are the
`final_production_*` refit on all 96 configurations.

Under LOGO, for the convergence radii on the raw-mask store:

| | mean | median | p90 | max |
|---|---|---|---|---|
| RadiusP — production (soft β=3, weighted fit) | street 9.0 / inters. 10.2% | 7.4% | ~21% | 35.5% |
| RadiusI — old power law (for reference) | 16.4 / 15.2% | 13.9 / 10.9% | 28 / 32% | 85 / 61% |
| RadiusI — unified form (production) | **12.5 / 9.6%** | 9.2 / 7.2% | 23 / 21% | 49 / 43% |

Two context notes belong beside these numbers. First, the pre-2026-09-27
record quoted conv_I ≈ 7% — that figure was artefact-easy: the old radius
was largely the position of the outermost building wall, a simple function
of the very regressors, and is not a baseline the clean measurement should
be compared against. Second, an in-sample probe with a deliberately rich
12-term pooled fit stops at ~9.5% (street) / 5.8% (intersection), so the
unified form sits close to what 48 configurations per group can support;
the worst held-out families are the singleton intermediate geometries
(b = 10 / s = 8, 12 at W = 250, 1000), where a held-out fold has no
neighbour to interpolate from. The unified form was selected by comparing
candidate forms under this same LOGO harness and is fixed from here on;
the errors quoted are those of the selected form (no nested selection).

## Domain of validity

The formulas interpolate inside the simulated envelope and should not be used
outside it:

| quantity | range covered |
|---|---|
| building size b | 10 – 30 m |
| street width s | 5 – 20 m |
| building height H | 4 – 24 m |
| charge weight W | 50 – 1500 kg |
| ρ | 0.18 – 0.74 |
| Π₂ = s/W^⅓ | 0.44 – 5.4 |
| H/s | 0.20 – 4.8 |
| Z_free | 2 … ≈ 8 (P) / ≈ 10 (I) — see below |

**Both ends of the Z_free range are real limits, and the upper one used to go
unstated.** The lower end is geometric: a row is admitted only when the
free-field radius Z_free·W^⅓ clears the first-street exclusion radius that
R_conv already excludes, and Z_free = 1 lies within one Hopkinson length of the
charge. The upper end is a data limit — the model is only fitted where the row
lies inside R_conv, and on the raw-mask tables the row count falls away beyond
Z_free ≈ 8 for pressure (75, 87, 90, 96, 96, 94, 80 rows at Z_free = 2…8,
then 33, 12, 4, 1; 668 rows in all) and already beyond Z_free ≈ 6 for
impulse (75, 87, 85, 66, 50 at Z_free = 2…6, then 24, 15, 9, 5, 2; 418
rows) — the clean R_conv,I is a third smaller than the artefact one, so the
impulse fit domain shrank with it. Predictions above those values are
extrapolation in the one variable the pressure form is most sensitive to,
since `range_switch` carries a 1/Z_free term.

### The safe domain — where the error is bounded

> **Not yet recomputed (2026-09-27).** The box, its error rates and the
> corner table below were measured on the pre-raw-mask tables and old
> RadiusI model. The audit additionally found the box is drawn around the
> very errors it bounds (decision D6, pending). Treat this subsection as a
> description of the previous record until it is re-derived.

The envelope above says where the formulas *interpolate*; it does not say how
well. Measuring the held-out error of every configuration and asking where it
stays bounded gives a second, tighter statement. Inside the box

| | |
|---|---|
| plan density ρ | 0.31 – 0.56  (equivalently b/(b+s) = 0.56 – 0.75) |
| Π₂ = s/W^⅓ | 0.50 – 5.4  (equivalently (s/5.4)³ ≤ W ≤ 8·s³) |
| canyon aspect H/s | ≤ 3 |

**every** held-out prediction is below 20% error, for pressure and impulse
alike — 38 of the 96 configurations, covering measured radii of 25–110 m (P)
and 35–140 m (I) with all five charge weights represented. Inside it, 89% of
pressure and 95% of impulse predictions fall within ±15%, with worst cases of
18.9% and 19.6%; the mean errors are 7.8% and 6.4%. In engineering terms, that
is an uncertainty of roughly ±15–20 m on a 100 m radius.

All twelve configurations that exceed 20% lie outside this box, and each sits
on a corner of the sampled envelope rather than in its interior:

| corner | configurations | driver |
|---|---|---|
| ρ ≈ 0.73 (b=30 m with s=5 m) | 3 | densest fabric sampled, 2-member family |
| Π₂ ≈ 0.44 (s=5 m at W=1500 kg) | 3 | narrowest street at the largest charge |
| H/s = 4.8 at W=50 kg | 2 | tallest canyon at the smallest charge |
| ρ ≈ 0.18–0.21 (b=10/s=12, b=15/s=20) | 4 | sparsest fabric sampled |

The mechanism is sampling density, not model form: in these corners the
leave-one-geometry-out fold has no neighbouring family to interpolate from, so
the test becomes extrapolation. This was checked directly — refitting with a
minimax (worst-case) objective, which is the mathematical optimum for the
maximum error, still cannot bring the in-sample worst case below ≈ 26%, so no
choice of coefficients closes the gap. Filling the corners with additional
simulations is what would extend the safe domain; the machine-readable
per-configuration classification is in
`outputs/check_results/safe_domain_req_soft3.csv`.

Two structural dependencies of the fit itself:

- **The 10 kPa criterion is baked into the coefficients.** The convergence
  threshold is a physical variable (Π₄ = p_thr/p₀) held constant across the
  dataset, so it is absorbed into C₀. The fitted radii are radii *of the 10 kPa
  criterion*; a different tolerance rescales them (measured elasticity
  d log R / d log p_thr ≈ −0.6). The choice is not arbitrary: engineering
  relevance of blast loads ends near Z ≈ 16 and the 10 kPa contour sits near
  Z ≈ 12, so the threshold lies where loads stop being structurally damaging.
  Under the soft criterion the threshold is still centred at 10 kPa (the
  projection crosses ½ exactly there), but the measured radius no longer jumps
  discontinuously when a lobe peak grazes it — the criterion's *location* is
  unchanged, only its knife edge is gone. The softening is conservative:
  measured radii grow by ~17% at the median (β = 3), i.e. convergence is
  declared slightly later, which is the safe direction for a protective radius.
- **Geometry family.** The formulas assume a uniform, effectively infinite
  rectangular grid of identical buildings. Real, heterogeneous urban fabric is
  outside the fitted family.

## The fitted coefficients

Production values (2026-09-27 run: raw-field mask, soft β = 3 pressure
criterion, unified impulse model).

Convergence radius:

| det | target | C₀ | C₁ | C₂ | C₃ | a |
|---|---|---|---|---|---|---|
| 1 street | RadiusP | 10.047 | −0.963 | 3.097 | 0.532 | 1 |
| 2 inters. | RadiusP | 11.766 | −0.863 | 2.298 | 0.700 | 2 |

| det | target | A | C₁ (ρ√(H/s)) | C₂ (ln²H/s) | C₃ (lnH/s·lnΠ₂) | C₄ (lnΠ₂) | C₅ (lnρ·lnΠ₂) |
|---|---|---|---|---|---|---|---|
| 1 street | RadiusI | 4.182 | +1.145 | −0.228 | −0.276 | +0.504 | +0.262 |
| 2 inters. | RadiusI | 4.867 | +1.065 | −0.127 | −0.165 | +0.705 | +0.412 |

Every RadiusI coefficient keeps its sign and order of magnitude across the
two groups — the trapping factor is nearly identical (1.14 vs 1.06) — so the
street/intersection difference is quantitative, not structural, exactly as
with pressure.

Z_urban (Λ forms):

| det | target | C₀ | C₁ | A | B | C₂ | C₃ |
|---|---|---|---|---|---|---|---|
| 1 | Pressure (range_switch) | 0.0974 | 2.6798 | 3.0186 | 7.8188 | — | — |
| 2 | Pressure (range_switch) | 0.1108 | 0.5619 | 2.1074 | 1.4108 | — | — |
| 1 | Impulse (canyon_trap) | −0.1302 | 3.0325 | — | — | 0.8977 | 1.1211 |
| 2 | Impulse (canyon_trap) | 0.0044 | 2.6643 | — | — | 1.0905 | 0.6908 |

(A is the switch threshold, stored positive: the near-field term reads
(Π₂ − A)/Z_free. Both impulse blocks are identical to the hard-criterion fit —
the soft criterion touches only pressure. Machine-precision values live in
`final_production_*_coefficients_req_soft3.csv`; the calculator and
`tools/z_surface_3d` carry hand-synced copies that must be re-checked after
any regression re-run.)

## Measurement definitions, precisely

- **Free field** = a matching charge-only reference simulation on the same grid
  resolutions — not an empirical curve. Ratios are formed cell-against-cell at
  equal resolution. The raw band operands (urban peak, reference field, and the
  unforced ratios) are persisted alongside the processed arrays (the
  `processed_npz_v2` superset), so the soft weights are computed from exactly
  the fields the hard band tested — which is what makes the β → ∞ reduction
  bit-exact rather than approximate.
- **The band is applied to the field, not by the scanner.** `process_grids`
  forces the stored ratio to exactly 1 wherever P < 10 kPa *or*
  |P − P_ref| < 10 kPa, and the sector scan then runs on that already-banded
  field. Its ±5% ratio test is therefore not a second, independent tolerance —
  it only ever sees cells the absolute band already passed. Since
  10/P_ref < 0.05 only for P_ref > 200 kPa, the absolute band is the binding
  constraint everywhere outside the immediate near field: at a representative
  long-range sample (config 58, θ = 0, r = 50–72 m, P_ref ≈ 5.6 kPa) it is
  equivalent to a 178% ratio tolerance, and 535 of 535 cells there exceed ±5%
  while 1 exceeds 10 kPa. A consequence worth stating plainly: a stored ratio
  map is not a picture of the flow. For that configuration 95.4% of valid
  cells hold the constant 1 rather than a measured ratio (84.5% from the
  low-pressure floor, 11.0% from the small-difference clause), so a white
  field reports where the criterion declined to look, not agreement. The
  unforced `ratioP/I{g}_raw` arrays are persisted for exactly this reason and
  are what to plot when the question is about the flow rather than the verdict.
- **First-street exclusion.** Cells inside the first street
  (r < √((b/2)² + (s/2)²) for street detonations, s/2 for intersections) are
  excluded from radius measurement: there the discrete near-field geometry
  dominates and no continuum radius is meaningful.
- **Both radii, one estimator — shared collapse, distinct criteria.** R_conv
  and the Z_urban exceedance radius are collapsed from the same 91 sectors by
  the same equivalent-area rule, so the two scalars aggregate directions
  identically. The per-sector measurements deliberately differ (band + K=3
  streak + first-street exclusion for R_conv; zero-tolerance outermost cell
  for MaxR), so MaxR overshoots R_conv systematically rather than
  occasionally; the `beyond_*` flags record those rows, `z_urban_valid_mask`
  excludes them from the fit, and the deployed chain answers the Z_conv clip
  there. The conditional and deployable-domain errors are both reported
  (`z_*` and `z_*_dep` in `cv_summary`).
- **The building mask precedes the fill** (2026-09-27): footprint cells are
  detected on the raw solver field (~1 Pa sentinel) per grid, before the
  cross-grid max-fill, so interpolation can no longer resurrect wall-skin
  cells into the scans. The merged reference (`ref*_fill`) is what the
  per-direction MaxR level samples, like-for-like with the merged urban
  field.

## Provenance of the functional forms

The Pi groups and the additive RadiusP structure are physics-first choices. The
two Λ forms were *discovered* by symbolic regression over the Pi-group space and
then accepted only after surviving leave-one-geometry-out validation with
constants refit per fold; candidate structures that fit well but transferred
poorly (including a spurious density pole) were rejected by that harness. The
pressure/impulse structural split was additionally verified by cross-application:
imposing either form on the other load costs 3–4 percentage points in both
detonation types, so the split reflects the physics, not the search.

The soft criterion went through the same discipline in a stricter order: the
LOGO harness first had to reproduce the documented hard-criterion baselines to
print precision; the streak-DP scanner is proven (by unit test) to equal the
brute-force expectation of the hard scan over all violation outcomes, and to
reproduce the shipped hard radii bit-exactly in its β → ∞ limit on the real
fields; β was then selected from a measured sensitivity table (β ∈ 2…12,
radius inflation vs threshold-gap closure vs LOGO error) rather than assumed.

**The unified RadiusI form (2026-09-27)** went through a five-way search on
the raw-mask tables before adoption: residual diagnostics of the old power
law (which flagged the missing saturation and depth–width interaction), an
exhaustive enumeration of ~21,000 candidate term sets scored by LOGO with a
per-fold refit, an independent genetic-programming search (gplearn; PySR's
Julia backend is blocked on this machine by an OS application-control
policy) whose Pareto front converged on the same saturation-plus-interaction
structure, mechanistic saturation forms with a free scale h\* fitted in
MATLAB (rejected: h\* is not identifiable from 5–6 distinct H/s levels — CI
spans an order of magnitude), and additive pressure-family variants
(rejected: best 15.5/12.0% against 12.5/9.6%, confirming the impulse radius
is multiplicative where the pressure radius is additive). The winning set
was then constrained to ONE shared term set for both detonation groups
(cost: +0.3 pp on the street group). The selection used the same LOGO
metric that is reported, so the quoted errors are those of the selected
form; a nested selection was judged disproportionate and is noted as such.

**`canyon_trap` was re-challenged, and held.** The impulse form was tested
against **10,484** distinct alternative closed forms sampled over the same
feature space (the three Pi groups), under the same budget (≤ 4 constants,
≤ 13 nodes), the same relative-error objective, and the same LOGO arbiter with
constants refit per fold. None beat it — the best alternative scored 10.91%
against its 9.81%, and was worse in-sample too (10.44% vs 9.23%). The shipped
form is therefore not merely "what the search returned once"; it survives a
direct re-search of its own space. (PySR's Julia backend does not run in this
environment, so the search was a direct random-tree sample rather than PySR's
evolutionary one — broad coverage for three variables at this complexity, but
not a guarantee of global optimality.)

## The continuum limit — why some configurations cannot be predicted

The Pi framework describes a *uniform, effectively infinite fabric*. That
description needs room to take hold, and where it does not, no formula over
(ρ, H/s, Π₂) can work — for a reason that is not about the formula.

Configurations that are neighbours in the Pi space were checked directly
against each other: 16 pairs sit within |Δρ| < 0.04, |Δ(H/s)| < 0.25 and
|ΔΠ₂| < 0.25 of one another, which is physically the same point. **Fourteen of
them agree on Λ to a median of 2%.** Two disagree by 46% and 48%:

| det | b, s, H, W | ρ | H/s | Π₂ | Λ measured |
|---|---|---|---|---|---|
| 1 | 10, 12, 15, 250 | 0.21 | 1.25 | 1.90 | **0.74** |
| 1 | 15, 20, 24, 1500 | 0.18 | 1.20 | 1.75 | **1.10** |
| 1 | 10, 12, 10, 250 | 0.21 | 0.83 | 1.90 | **0.80** |
| 1 | 15, 20, 12, 1500 | 0.18 | 0.60 | 1.75 | **1.17** |

Same input, outputs 47% apart. **No function of the three Pi groups can
predict both**, so a form search cannot fix it — which is exactly what the
10,484-candidate search found.

What separates them is where the measurement sits relative to the *block
period* b + s. Both anomalous configurations are measured at **0.98 and 1.00
block periods** — one ring of buildings out, where there is no fabric yet, only
individual obstacles. Across all rows:

| MaxR / (b+s) | rows | mean \|error\| | median Λ |
|---|---|---|---|
| 0 – 1 | 198 | **12.2%** | 1.14 |
| 1 – 1.5 | 107 | 8.8% | 1.21 |
| 1.5 – 2 | 108 | 9.0% | 1.25 |
| 2 – 3 | 137 | 8.1% | 1.26 |
| 3 – 5 | 114 | 6.5% | 1.43 |
| 5 + | 36 | **6.0%** | 1.52 |

Per configuration: below 1.5 block periods, 37 configurations average 11.4%;
above it, 59 average 7.4%.

**Stated as a domain condition:** the target point should lie at least ~1.5
block periods from the charge,

    Z_free · W^⅓ ≳ 1.5 (b + s)

which is checkable before any prediction is made. This is the same idea as the
first-street exclusion radius, one scale up: that one removes the first
*street*, this one says the *fabric* description needs several blocks. It also
subsumes what looked like two separate failure modes — the large-building /
small-charge configurations (b = 30 at W = 50) and the sparse b = 10, s = 12
family both sit at ≈ 1 block period.

Two honest qualifications. The trend is monotone but not a cliff (correlation
of |error| with block periods is −0.21), so 1.5 is a reasonable working
threshold rather than a measured discontinuity. And 37 of 96 configurations sit
below it, so this is a statement about where the formulas are trustworthy — not
a filter that was applied to the fit, which would inflate the reported accuracy
without improving the model.

## Limitations

> The coarsening measurements in this section predate the 2026-09-27 mask
> change and have not been re-run; the construction argument is unaffected.
> On the clean store two complementary stability facts are now on record
> (`outputs/check_results/impulse_criterion_sensitivity_note.md`): the hard
> impulse scan is K-stable (median |Δln R| ≤ 1% for K = 2→3→4, so it is
> deliberately NOT softened), and thr_I = 20 sits at the measured
> stability/predictability optimum of a 5–40 threshold sweep.

- **The soft convergence radius is not mesh-converged.** The measured
  quantity depends on the discretisation, not only on the field, and the
  dependence is a property of the soft scanner's construction: it returns the
  *expectation* of the hard scan under per-**cell** violation probabilities, so
  the number of independent draws grows with the number of cells. On a
  deliberately constant field (w = 0.35 everywhere) the returned radius climbs
  52 → 92 → 99 m as the cell count goes 50 → 400 → 3200, and tends to the outer
  boundary for any w > 0 — there is no mesh-converged limit to converge *to*.
  Measured on the real fields by block-average coarsening (24 configurations,
  the mesh-invariant coarsening operator: the violation *share* per block is
  preserved, unlike subsampling which discards cells):

  | | ×2 coarser | ×4 coarser |
  |---|---|---|
  | RadiusP, hard band | +1.9% | −0.3% |
  | **RadiusP, soft β = 3 (production)** | **−9.1%** | **−18.2%** |
  | RadiusI, hard band | −0.5% | −6.5% |

  The hard band is mesh-stable because a cell is definitely in or out, so
  "three in a row" is a fact about the field. Two consequences follow and both
  should be stated when the radii are used. First, part of the documented
  +17.3% median inflation from softening is cell count rather than physics, so
  the β selection scan conflates softening with mesh sensitivity. Second, the
  radii are only comparable across configurations because all 96 were computed
  on the same mesh — the bias is largely common-mode here, and would not
  transfer to a run at a different resolution.

  The natural repair is to make the scan step a length rather than a cell:
  measure the deviating *share* of a fixed-length window and require it to
  persist over metres. A share converges under refinement where a count
  doubles, and the prototype does restore mesh invariance (+0.5% / +0.6% under
  the same coarsening). It was **not adopted**, because it is measurably worse
  on the trade-off it would have to preserve: at the same threshold-cliff
  closure (~8.6 m) it costs ≈ 28% median radius inflation against the current
  17.3%. Spatial averaging also does not close the cliff on its own — the gap
  stays 23–27 m across a factor of 5 in both window length and threshold —
  because the discontinuity is in *amplitude*, not in space: 14.3% of the
  config_93 field sits within ±2 kPa of the threshold, so a whole region
  crosses together. That is a negative control worth keeping: it is what
  establishes that amplitude softening (β) is the only mechanism that can
  close the cliff, rather than one option among several.

- **The impulse form cannot represent strong attenuation.** In `canyon_trap`,
  Π₂ appears only in the denominator, as `C₃·√Π₂`. A denominator can *dilute*
  the trapping term toward zero but never flip its sign, and the numerator
  `ρ(√(H/s) − C₂ρ)` is non-negative for essentially all the sampled geometry.
  So `ln Λ ≥ C₀`, i.e. **Λ has a floor at ≈ 0.93**: a wide street can cancel the
  amplification but cannot produce attenuation. The measured Λ spans 0.67–2.26
  against a predicted 0.93–1.68. Five of 96 configurations attenuate on the
  median (b = 10/s = 12 and b = 30/s = 20, both street detonations) and the
  model predicts mild amplification for them — errors of 30–56%.

  Removing the floor was tried and is worse: two variants that let the
  numerator change sign scored 11.7% and 12.7% LOGO against the current 9.8%,
  and the fits did not even use the new freedom (their minimum predicted Λ
  stayed at 0.93). Only 11% of rows attenuate, so the extra degree of freedom
  costs the other 89% more than it recovers. The floor is a real structural
  limit, and the configurations it misses are the same ones sitting at ≈ 1
  block period (see the continuum limit above) — which is the more fundamental
  reason they cannot be predicted.

- **Scalar radius on a bimodal field.** The equivalent-area collapse assumes
  the exceedance region is roughly round. Where buildings block most directions
  it is not: in the densest fabric (b = 30, s = 5) the *median* sector radius is
  pinned at 6.70 m — unchanged across Z_free and across charge weight, i.e. set
  by geometry rather than by load — while the open directions reach 36–43 m.
  Req returns ≈ 15 m, a value no direction actually sees, and the model, being
  a smooth function of the Pi groups, predicts ≈ 24 m. The ratio
  `max/median` over the 91 sector radii diagnoses this directly: configurations
  above 3 average 12.6% (P) / 16.3% (I) error against 8.0% / 8.9% overall.
  Six configurations exceed it for pressure, three for impulse.

- **The output is a scalar radius.** The field is directional — the 91-sector
  spread around the equivalent-area radius is real — and the collapse discards
  that structure. Directional Λ(θ) prediction is the natural extension (the
  per-sector data is retained).
- **Worst-case error ~10% per split.** The medians above hide a tail: per-split
  worst-case MAPE averages ≈ 10%, with about half the validation splits fully
  under 10%. Under LOGO the worst single configuration now sits at 30.1% (P) /
  30.4% (I) — down from 43.4% / 38.5% before the soft criterion and the fit
  fixes — and the residual tail is no longer the threshold cliff but genuine
  between-geometry variance at the corners of the domain, i.e. extrapolation
  pressure inside the envelope, not fixable by more terms (see the safe-domain
  section, where the minimax check bounds what any coefficient choice can
  achieve). One honest trade: the soft criterion improves the P median and
  collapses the max, but its p90 is ~1.5 pp worse than the hard tables'.
- **Absolute vs relative error.** Because R = W^⅓·Z with W^⅓ exact, percentage
  errors on R and on Z are identical; in metres they are not comparable across
  the dataset. The largest absolute misses are 18.5 m (P, on a measured 101 m)
  and 29.8 m (I, on 109 m), and they belong to the *large*-charge families —
  not to the percentage-worst cases, whose radii are small. Both should be
  quoted when the result is used for stand-off design.
- **Pressure amplification is only partly predictable in principle.** In 60 of
  96 configurations the sign of the urban effect flips with distance
  (interference), so any geometry-only predictor of amplification vs attenuation
  has a measured ceiling of 81.5% accuracy. The range_switch form models the
  mean of this behaviour; individual near-threshold rows scatter around it.
- **One tolerance convention per load.** The impulse band (~83% relative at its
  own radius) is looser than the pressure band (~47% at its radius). The two
  radii are therefore calibrated engineering thresholds under their own
  criteria — not criterion-free physical boundaries — and should be quoted as
  such.

