# Change note — the accurate-or-irrelevant impulse criterion (2026-09-28)

Owner decision, 2026-09-28, closing the 2026-09-27/28 audit's impulse track.
Commit `22c3424` carries the code; the tables of record regenerate in the
commit that carries this note. Everything here is old-vs-new on the same
raw-mask (v3) store, `req_soft3` estimator, `--n-iter 500`.

## What changed

**The impulse convergence criterion.** A cell now counts as converged when

    |I_urban - I_ff| / I_ff < 0.10        (free field is ACCURATE here)
    or  I_urban / W^(1/3) < 20            (urban impulse IRRELEVANT here)

replacing the 2026-07..2026-09 scaled band `|I_urban - I_ff| / W^(1/3) < 20`.
The owner rejected the band because its permitted *relative* deviation grows
with distance: beyond Z ~ 13.7 the band exceeds the local free-field impulse
itself, so a cell at twice the free-field impulse counted as converged and
"use the free field beyond R_conv" could under-predict — the criterion did
not deliver the engineering guarantee it exists for. The new floor is on the
URBAN impulse (the same owner logic as the pressure floor, audit D7) and
keeps 20 Pa·s/kg^(1/3) as a relevance level (Z ~ 13.7 on the free-field
curve). `rel_band = 0.10` is twice the 5% impulse mesh tolerance; the
decision sweep (`criterion_decision_suite.csv`: beta 0.10..0.30 and
floor-only, floor 15/25, K 2/3/4) showed the radius is floor-dominated, so
tighter bands are strictly more stable and more predictable. Full rationale:
`blastlib/constants.py::IMPULSE_CRITERION`.

**The RadiusI production model.** The owner's ORIGINAL quad power law

    Z = A · rho^p · (H/s)^q · Pi2^r · exp(r2·ln²Pi2)

returns as production (`model='quad'`). Under the old criterion on the clean
store it had failed structurally (near-zero geometry exponents — the radius
was tracking the I/W^(1/3) = 20 contour, a function of W alone) and was
replaced by the unified five-term form on 2026-09-27. Under the new
criterion the radius is a smooth transform of the amplification field and
the power law is the best form again — the 09-27 replacement treated a
criterion artefact as physics. `model='unified'` remains available for
reproducing the superseded tables.

**Pressure is untouched.** RadiusP, MaxR_P, Λ_P: bit-identical old-to-new
(verified on the regenerated CSVs). The soft β=3 pressure criterion, the
raw-field mask (D2b) and the grid-filled MaxR reference (PHY-04) all stand.

## Measured radii, old vs new

| quantity | old (scaled band) | new (accurate-or-irrelevant) |
|---|---|---|
| median Z_conv,I | 7.58 | 18.64 |
| median Z_conv,P | 9.88 | 9.88 (unchanged) |
| RadiusI ratio new/old | — | median ×2.29, p10 ×1.76, p90 ×3.19, range ×1.33–×4.26 |
| configs with Z_conv,I > Z_conv,P | 0/96 | 96/96 |
| anchors (config_93 / 95, RadiusI) | 68.16 / 64.22 m | 133.19 / 141.36 m |

The ordering flip is the headline: the old record said impulse converges
*earlier* than pressure, which the owner flagged as physically implausible
(reverberation feeds impulse long after peaks align). Under the new
criterion every configuration has the impulse radius larger — amplified
urban impulse stays *relevant* far beyond the free-field relevance range.
The suite's per-config radii agree with the regenerated tables to <0.1% on
94/96 configs (worst 2%: the suite ran float32 to fit in memory, and a
borderline cell flips one streak; the float64 pipeline is the measurement
of record).

## Prediction quality, old vs new

LOGO (leave-one-geometry-family-out, constants refit per fold), RadiusI:

| model / criterion | mean | median | p90 | max | R² |
|---|---|---|---|---|---|
| power law / old band | 16.4% (det1) / 15.2% (det2) | 13.9 / 10.9% | 28 / 32% | 85 / 61% | — |
| unified / old band | 12.5 / 9.6% | 9.2 / 7.2% | 23 / 21% | 49 / 43% | — |
| **quad power law / new (production)** | **9.2 / 8.1%** | **5.8 / 5.9%** | 20 / 18% | 48 / 48% | 0.935 |

RadiusP LOGO unchanged: mean 9.0 / 10.2%, median 7.4%, max 35.5%, R² 0.924.
Per-row LOGO predictions: `logo_cv_req_soft3_relwls_quad.csv` (the
`_unified` file documents the superseded configuration).

500-split random CV (median [p25, p75] across splits) — pressure rows
identical, impulse rows all improve:

| metric | old | new |
|---|---|---|
| conv_I | 11.10 [9.84, 12.52] | 8.03 [6.71, 9.32] |
| z_I | 10.43 [9.40, 11.45] | 8.63 [7.84, 9.49] |
| z_I_dep (deployable domain) | 13.23 [12.12, 14.44] | 10.01 [9.26, 10.82] |
| conv_P / z_P / z_P_dep | 9.82 / 8.69 / 8.73 | identical |

`check_formulas` on the regenerated tables: conv P 6.89% / I 7.43% MAPE
(production fit, in-sample); Z_urban P 7.32% / I 7.25%.

## Coefficients of record, old vs new

RadiusI (final production; old row = unified form, new row = quad power law):

| det | old (unified: A, C1, C2, C3, C4, C5) | new (quad: A, p_rho, q_HoverS, r_sW13, r2) |
|---|---|---|
| 1 street | 4.182, +1.145, −0.228, −0.276, +0.504, +0.262 | 24.773, 0.3519, 0.0834, 0.1076, −0.0419 |
| 2 inters. | 4.867, +1.065, −0.127, −0.165, +0.705, +0.412 | 22.031, 0.2111, 0.1325, 0.1514, −0.0081 |

Λ impulse (canyon_trap; refit because the larger R_conv,I admits more rows
into the fit domain — structure unchanged):

| det | C0 | C1 | C2 | C3 |
|---|---|---|---|---|
| 1 old → new | −0.1302 → −0.0915 | 3.0325 → 3.0480 | 0.8977 → 0.9177 | 1.1211 → 1.2965 |
| 2 old → new | 0.0044 → 0.0373 | 2.6643 → 2.6593 | 1.0905 → 1.1368 | 0.6908 → 0.9420 |

Λ pressure and RadiusP: bit-identical, see the 2026-09-27 tables.

## Downstream

* `blast_calculator.html`: CONV_I quad form + coefficients, ZU.I refit,
  header criterion line — updated 2026-09-28.
* `tools/z_surface_3d`: carries RadiusP only — unaffected.
* Raw anchors (`tests/test_npz_anchors.py::RAW_ANCHORS`) updated; v1/v2
  anchors keep guarding the old baked-in criterion.
* `docs/ALGORITHM.md` / `_HE.md`: impulse-criterion and RadiusI-model
  sections rewritten for the new record.
* The ISIEMS paper correction list must be recomputed against these
  numbers (Eq. 7 survives as a form; its coefficients and every impulse
  radius/statistic change).
