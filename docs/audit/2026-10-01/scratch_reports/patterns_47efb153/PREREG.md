# Pre-registration — pattern search on record 27211b3

Written 2026-10-01, before any test below was run. Implementation details that the
owner's brief left open are fixed here. Numbers only, no physical interpretation.

## Data (read-only)
- `convergence_table_req_soft3.csv`, `max_radius_per_Z_req_soft3.csv` taken with
  `git show 27211b3:outputs/tables/...` (production estimator req_soft3).
- Ratio fields: `data/raw_npz` (96 files, mtime 2026-10-01 11:03–11:04, before the
  record commit 11:58), expanded with the RECORD code (`git archive 27211b3 blastlib`)
  through `load_processed_data` with default params, exactly as Phase 1 does.

## Inputs
det ∈ {1,2}; W [kg]; b, s, H [m]; ρ = b²/(b+s)²; s̃ = s/W^(1/3); H/s.
Regression inputs are log-transformed (ln ρ, ln s̃, ln H/s, ln W) and centred; det coded ±0.5.

## Targets (per config)
| id | definition |
|---|---|
| R_P, R_I | RadiusP, RadiusI [m] |
| Z_P, Z_I | R / W^(1/3) |
| Lam_P, Lam_I | median over z_urban_valid_mask rows of Λ = MaxR / R_free (mask re-implemented from record code: not beyond, R_free < R_conv, R_free > ExcludeR, Z_free ≥ 2) |
| Slope_P, Slope_I | OLS slope of ln Λ vs ξ over the same rows, ξ = Z_free / Z_conv (measured, same target); needs ≥ 3 rows |
| ring stats | for field F ∈ {P/P_ff, I/I_ff} (UNFORCED ratios, buildings and cut cells NaN), annulus Z ∈ [Z_k−0.5, Z_k+0.5), cell-AREA-weighted median, P5, P95; Z_k = 1..20 saved; tested at Z_k ∈ {2, 5, 10} → 18 targets `rP_med_Z5` etc. |
All targets analysed as ln(target), except Slope_* (raw).

## Families, clusters, folds
Geometry family g = (b, s, H): 18 families. Every bootstrap resamples families; every
cluster-robust SE clusters on g; LOGO = 18 folds, one family out (pooled tests drop
both dets of that family). Sign stability = share of folds whose estimate has the
full-data sign; computed only where the estimate is defined in the fold.

## Inference, uniform across all tests
- Each test yields estimate, SE (or exact F), p.
  - Regression coefficients: OLS, CR1 cluster-robust SE, t with G−1 df.
  - Spearman: Fisher-z of ρ_s, SE from family-cluster bootstrap (B = 2000), normal p.
  - ANOVA terms: F test vs pooled error; partial η² with noncentral-F CI.
  - Segmented break: SSE-improvement statistic, wild-cluster (Rademacher) bootstrap
    under the linear null, B = 1999.
  - Collapse: paired t over 18 families on LOGO squared-error difference.
  - det difference Δ = est(det2) − est(det1): family-cluster bootstrap SE (B = 2000), normal p.
- ONE Benjamini–Hochberg pass, q = 0.05, over every test in this file (all families,
  pooled + det1 + det2 + Δ). Per-family counts are reported so m is visible.
- Reported CI for each test = FCR-adjusted (Benjamini–Yekutieli 2005) at level
  1 − qR/m, R = number of BH rejections; for Wald-type tests BH rejection ⇔ adjusted
  CI excludes 0. Unadjusted 95% CI also reported.

## Pass rule ("pattern")
(1) BH-rejected; (2) classified pooled/det1/det2 (below); (3) LOGO sign stability ≥ 0.80;
(4) robustness: recompute with configs whose Z_P > 20 or Z_I > 20 removed; report
change (if no config qualifies, check is identical and reported as such).
Classification of a target×input pattern:
- **general**: pooled passes, and both within-det estimates share the pooled sign.
- **det-specific (det k)**: det k passes (1)(3)(4), the other det's adjusted CI includes 0.
- **det interaction**: the Δ test passes (1)(3), or the two within-det estimates pass with opposite signs.
**Undecided** (within one det): fails (1), unadjusted p < 0.10, LOGO ≥ 0.80.

## A. Hopkinson scaling
- A1 per geometry (det,b,s,H): ln R = ln c + a ln W. Core geometries (3 W, df = 1)
  get t-CI and a test of a = 1/3; extension geometries (2 W, df = 0) get a only.
  Pooled: ln R = geometry fixed effects + a ln W, common a; pooled / det1 / det2; test a = 1/3.
- A2: ln Z = β0 + β_det det + β_ρ ln ρ + β_s̃ ln s̃ + β_Hs ln H/s + β_W ln W; test β_W = 0.
  A2b (form check): add squares and pairwise products of the three ln Π; test β_W = 0.
- A3: exact similar pairs (equal ρ, s̃, H/s, det, different W) are enumerated with
  rel. tol 1e-6; nearest approximate pairs listed descriptively, not tested.

## B. Effects on the 72-config core
- B1: balanced ANOVA on ln Z_P, ln Z_I (and ln R_P, ln R_I); factors det, b, s, H (3), W (3).
  Pooled: 5 main + 10 two-way + 10 three-way terms; error = all 4- and 5-way (df 20).
  Within det: 4 main + 6 two-way + 4 three-way; error = 4-way (df 4).
  ln R differs from ln Z ONLY in the W main effect (ln R = ln Z + ⅓ ln W, additive in W),
  so only that term is counted as a separate test for ln R.
  Direction of a term = sign of its linear(-in-ln-level) × linear contrast coefficient
  (orthogonal polynomial codes); LOGO on that coefficient with the model up to 3-way,
  only where the contrast is estimable in the fold (else "n/a" → cannot pass (3)).
- B2: every 2-way term with partial η² ≥ 0.06: interaction plot; simple effects of each
  factor at each level of the other (cell means, SE from MSE_error); reversal flagged
  when simple effects change sign; "strong" when both opposite-sign simple effects
  have 95% CI excluding 0. Reversal point by linear interpolation in ln level,
  CI by parametric simulation (20000 draws).
- B3: Π-form regression on all 96 (pooled) / 48 (per det): main ln Π + det, plus all
  pairwise products (centred). Targets ln Z_P, ln Z_I, and (extension) ln Lam_P, ln Lam_I.

## C. Other patterns
- C1: Spearman of each target with each of ρ, s̃, H/s, W, b, s, H (pooled, det1, det2);
  det effect: paired det2/det1 ln-ratio over matched (b,s,H,W), cluster bootstrap.
- C2: segmented term (x − ψ)_+ added to the B3 main-effect model, x ∈ {ln s̃, ln ρ};
  targets ln Z_P, ln Z_I, ln Lam_P, ln Lam_I; ψ by grid search over midpoints of
  distinct x values with ≥ 10% of the data each side; break CI = family-bootstrap
  percentile of ψ̂ (reported only if the break test passes).
- C3: collapse ln T = c0 + c1 ζ + c2 ζ² (+ det shift pooled), ζ = α ln ρ + β ln s̃ + γ ln H/s,
  (α,β,γ) by least squares (normalised, β = 1 if possible; else unit norm).
  Baseline = best single ln Π, same quadratic. Statistic = mean over families of
  LOGO squared-error difference (baseline − collapse); positive ⇒ collapse better.
  Reported: in-sample residual SD and LOGO RMSE of both.

## Addendum (written after s01 targets and before any test was run)
- Record fact found while building targets: at 27211b3, 8 configs have Z_I > 20
  (det1: 22, 25, 26; det2: 40, 43, 58, 61, 62); none has Z_P > 20. Check (4) therefore
  removes these 8 configs from every test.
- (4) "survives" = robust estimate has the full-data sign AND robust unadjusted p < 0.05.
  If the model is not estimable after removal (e.g. B1 within det2: 31 obs, 32 params),
  B1 falls back to the model up to 2-way (3-way pooled into error); terms with no
  estimable fallback are "n/a". A pattern with (1)-(3) passed and (4) = n/a is listed
  with that flag, not silently passed.
- Δ (det2 − det1) bootstrap tests are run for A1-pooled a, A2/A2b β_W, every B3 within-det
  coefficient, every C1 Spearman. For B1 the Δ of term X is the pooled ANOVA term det:X
  (exists when X has ≤ 2 factors). C2 and C3 have no Δ test.
- B1 LOGO has 12 folds (the 12 core families); the 6 extension families are not in the core.
- B3 and C2 centring is fixed at the full-data means, so LOGO/robust coefficients keep
  their meaning.
- C3 (3): share of the 18 families whose LOGO squared-error difference has the sign of the mean.
- Bootstrap draws (family resamples) are shared across tests (seed 20261001).
