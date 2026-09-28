# Change note — the impulse relevance floor is the pressure floor (2026-09-28 evening)

Owner decision, 2026-09-28 evening, adopting the physics-audit verdict
(docs/audit/2026-09-28/physics.md, candidate B, findings physics-1..17).
Commit `959e4a2` carries the code; the tables of record regenerate in the
commit that carries this note. Old = the same-day impulse-floor record
(`3400e26`, documented in `impulse_criterion_change_note.md`); everything
here is old-vs-new on the same raw-mask (v3) store, `req_soft3`,
`--n-iter 500`.

## What changed

**The impulse criterion's irrelevance clause.** A cell now counts as
converged when

    |I_urban - I_ff| / I_ff < 10%      (free field is ACCURATE here)
    or  peakP_urban_raw < 10 kPa       (location is DAMAGE-IRRELEVANT)

replacing the morning rule's floor on the urban scaled impulse
(I_urban/W^(1/3) < 20). The physics audit found that floor ungrounded
(physics-1): every P-I damage curve is bounded from below by a PRESSURE
asymptote, so below the anchored 10 kPa no impulse magnitude can damage
the anchored structural class — an impulse-only irrelevance level does
not exist, and the value 20 was inherited from the rejected band's
calibration. The impulse floor also rode channelling amplification to
Z_conv,I = 32.4, putting 33/96 radii beyond the validated free-field
range Z = 20 (physics-2). Both criteria now share ONE relevance quantum —
`PARAMS['minPressure_kPa']`, deliberately not duplicated — which makes the
two radii commensurable for the safety-distance comparison (aim 4).

**Alternatives measured and rejected** (owner's proposals, taken
seriously): the impulse-only mirror |dI|/W^(1/3) < x OR I/W^(1/3) < y
(physics-11..15: for x = y = 20 it collapses per-config onto the rejected
scaled band — median 7.58, ratio 1.00 — the under-prediction defect and
the implausible Z_I < Z_P ordering both return; no (x, y) satisfies
impulse-only AND bounded guarantee AND sensible radii — a measured
trilemma), and absolute Pa·s clauses (physics-16..17: per-weight
equivalent level varies x3.107 across W = 50..1500, breaking the Z
collapse; absolute P-I currency belongs to the aim-4 per-target products,
not to a convergence criterion). The physics-6 tier-text misattribution
in the IATG anchor comment was corrected (owner confirmed 10 kPa — the
standard's ~10%-to-~20%-repair-cost boundary — is the intended anchor,
not the 16 kPa structural-member tier).

**Wording obligation (physics-4).** R_conv,I is a RELEVANCE-BOUNDED
convergence radius: it is floor-dominated (the accuracy clause trims the
floor-only radius by ~1.5% median), so it must never be presented as the
radius where the impulse field merges with the free field. The merging
radius is larger — channelled canyons carry >10%-excess impulse to
Z ~ 19-32 — and is reportable descriptively as a finding about the reach
of channelling. Carry the PHY-06 caveat (the 10 kPa floor is a CFD-field
value; the KB-equivalent boundary sits ~8-10% further, floor elasticity
~ -0.5) and the damage-scope limit (glazing/light-damage tiers at
2-5 kPa are outside both radii) wherever the radii anchor standards.

## Measured radii, old vs new

| quantity | impulse-floor (morning) | pressure-floor (final) |
|---|---|---|
| median Z_conv,I | 18.64 | **13.85** |
| p90 / max Z_conv,I | — / 32.43 | 15.55 / **17.48** |
| radii beyond validated Z = 20 | 33/96 | **0/96** |
| Z_conv,I > Z_conv,P | 96/96 | 96/96 (median ratio 1.39) |
| RadiusI ratio new/old | — | median x0.72 (p10 0.63, p90 0.89, range 0.47-1.08) |
| median Z_conv,P | 9.88 | 9.88 (RadiusP bit-identical) |
| anchors config_93 / 95 (RadiusI) | 133.19 / 141.36 m | **96.18 / 89.07 m** |

Verified against the read-only measurement suite (`pfloor_variant_suite`,
column pf10_b0.10_K3): float64 pipeline vs float32 suite differ <0.1% on
75/96, worst 2.1% — same float32 signature as previous suites. Floor
sensitivity to the neighbouring IATG tiers (9/11 kPa): median 14.61/13.13
(elasticity ~ -0.5). Adding the impulse floor 20 as a third clause is
measured redundant (median 13.72).

## Prediction quality, old vs new

LOGO (leave-one-geometry-family-out, per det), RadiusI quad power law:

| | mean | median | p90 | max |
|---|---|---|---|---|
| impulse-floor record | 9.2 / 8.1% | 5.8 / 5.9% | 20 / 18% | 48 / 48% |
| **pressure-floor record** | **9.0 / 9.0%** | 7.4 / 7.7% | 16 / 18% | 36 / 28% |

On the final radii the forms sit within ~0.4 pp (legacy 8.90/7.58, quad
8.98/7.63, unified 8.56/7.04 mean/median pooled; unified's worst case 44%
vs quad's 36%); the owner's original quad law is retained — no nested
selection. RadiusP LOGO unchanged (9.0/10.2% mean, 7.4% median).

500-split CV (median [p25, p75]); pressure rows identical throughout:

| metric | impulse-floor | pressure-floor |
|---|---|---|
| conv_I | 8.03 [6.71, 9.32] | 8.29 [7.39, 9.07] |
| z_I | 8.63 [7.84, 9.49] | 8.87 [8.07, 9.73] |
| z_I_dep | 10.01 [9.26, 10.82] | 11.25 [10.38, 12.07] |
| conv_P / z_P / z_P_dep | 9.82 / 8.69 / 8.73 | identical |

`check_formulas` on the regenerated tables: conv 6.89 / 7.42%; z_urban
7.32 / 7.31% (impulse fit rows n = 171 — the fit domain tracks R_conv,I).

## Coefficients of record, old vs new

RadiusI (quad power law both; the exponents shrink because the
relevance-bounded radius is, to first order, the urban 10 kPa contour —
its geometry response is the pressure field's, density-dominated):

| det | old (A, p, q, r, r2) | new (A, p, q, r, r2) |
|---|---|---|
| 1 street | 24.773, 0.3519, 0.0834, 0.1076, -0.0419 | 17.410, 0.3031, -0.0558, 0.0344, +0.0072 |
| 2 inters. | 22.031, 0.2111, 0.1325, 0.1514, -0.0081 | 16.327, 0.1646, -0.0123, 0.0701, -0.0133 |

Lambda impulse (canyon_trap; the fit domain tracks R_conv,I; structure and
signs unchanged):

| det | C0 | C1 | C2 | C3 |
|---|---|---|---|---|
| 1 old -> new | -0.0915 -> -0.0929 | 3.0480 -> 3.0191 | 0.9177 -> 0.8957 | 1.2965 -> 1.4234 |
| 2 old -> new | 0.0373 -> 0.0272 | 2.6593 -> 2.6389 | 1.1368 -> 1.1143 | 0.9420 -> 0.8998 |

Lambda pressure and RadiusP: bit-identical throughout.

## Downstream

* `blast_calculator.html`: criterion line, CONV_I and ZU.I coefficients —
  updated 2026-09-28 evening. `tools/z_surface_3d`: RadiusP only,
  unaffected.
* Raw anchors updated; v1/v2 anchors keep guarding the old baked-in rule.
  The morning rule remains reproducible via
  `ff_reference.impulse_converged_ifloor` and commit `3400e26`.
* `docs/ALGORITHM.md` / `_HE.md`, `THESIS_RESULTS_OUTLINE_HE.md`
  (3.2.2, 3.4): rewritten for the final criterion with the mandatory
  relevance-radius wording.
* ISIEMS paper: median 13.85 and ratio 1.4 sit close to the paper's
  original 11.61 / "about 1.3"; Fig. 4 regenerates from
  `logo_cv_req_soft3_relwls_quad.csv`.
