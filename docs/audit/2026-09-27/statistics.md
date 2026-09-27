# Audit: statistics  (2026-09-27, commit 5f19029)

Lens: regression and model selection. The audit covers the working tree as it
stands, not HEAD. Every finding says whether it involves modified-uncommitted
code or tables. It reports findings only. No file other than this one was
written, and no seed, `n_iter`, threshold or coefficient was touched.

Probes were run from the repo root with `PYTHONDONTWRITEBYTECODE=1`. They only
read committed or working-tree CSVs and call the pipeline functions in memory.
The one smoke run
(`python run_analysis.py --phase 2 --n-iter 20 --no-figures --tables-dir <scratch>`)
read copies of `convergence_table_req_soft3.csv` and
`max_radius_per_Z_req_soft3.csv` and wrote to a session scratch folder outside
the repo. `git status` was identical before and after (79 entries).

## Summary

The pipeline is mechanically clean:
- splits are by configuration;
- nothing is fitted on all rows before the split;
- the Z_conv clip inside CV uses the fold's own convergence fits;
- the production refit on all 96 configurations is stated;
- the working-tree production CSVs regenerate byte for byte from the
  working-tree code.

The problems are in what the reported numbers mean:

1. **Selection on the LOGO folds (STA-01).** Leave-one-geometry-out (LOGO) is
   the quoted headline. The same LOGO scores were also used to choose the
   Z_urban forms, the convergence-fit variants, beta and `a`. No nested or
   untouched hold-out exists.
2. **Target-dependent domain (STA-02).** The Z_urban fit and test domain is
   decided with the measured target (`MaxR < R_conv`). On the domain a user can
   identify before predicting, the out-of-fold impulse error is 12.6%, not
   9.8%.
3. **Best-split numbers presented as validation (STA-03).** `check_formulas`,
   `validation_comparison_*.csv`, the `cv_best_*.png` titles and
   `formulas_printer` all rest on the best split, which is the minimum over 500
   draws.
4. **Post-hoc "safe domain" (STA-04).** The box was drawn around the LOGO errors
   and is then quoted, and shipped in the calculator, as an error bound.

In addition:
- no coefficient or prediction carries an uncertainty, and several
  coefficients are weakly identified (STA-05, STA-06);
- the documents and the calculator quote HEAD numbers that the working-tree
  tables no longer match (STA-07);
- the Z_urban LOGO figures have no harness in the repo (STA-08);
- the calculator does not guard rho or Z_free (STA-09).

Counts: **4 high, 5 medium, 3 low, 1 info.**

## Findings

### STA-01  [high]  Structure, variants and beta were chosen on the same LOGO scores that are reported as the generalisation estimate

- **Where.**
  - `docs/ALGORITHM.md:204-242` (Result: "The headline is the leave-one-geometry-out (LOGO) test"), `:396-425` (Provenance), `:111-118` (beta), `:200-202` ("It is validated out-of-sample").
  - `blastlib/regression/z_urban.py:23-27, 103-106`.
  - `blastlib/regression/convergence_models.py:39-40`.
  - `outputs/check_results/soft_beta_selection_note.md:6-19`, `soft_criterion_summary.csv`, `logo_summary_req_soft3_relwls_quad.csv`.
  - `docs/PYSR_CONVERGENCE_SEARCH.md:16-21, 119-120`.
  - Commits 5a1f177, b88ef6e, cbb2312, f34cf2f, 430d004.
- **What.** One LOGO harness decides five choices:
  1. the Z_urban closed forms: PySR candidates were accepted or rejected by LOGO, and `canyon_trap` was re-challenged against 10,484 candidates on LOGO;
  2. `relwls`/`quad` against the legacy fits (gate C5);
  3. beta, chosen from {2, 3, 4, 6, 8, 12} with the acceptance rule stated on the LOGO pressure mean;
  4. the RadiusP switch constant `a`, "selected by CV from {1, sqrt(2), 2}";
  5. the RANGE_SWITCH B bound, raised from 8 to 20 after the all-data det=1 optimum was seen at 8.33 (`z_urban.py:409-420`).

  The same LOGO statistics are then the headline: P 8.4/5.7/18.7/30.1 and I 7.2/5.9/16.4/30.4 (mean/median/p90/max). Constants are refit per fold, but structure, beta, `a` and bounds were chosen with all 96 configurations, including each held-out family.
- **Evidence.**
  - `convergence_models.py:39-40`:
    `#   a = 1 for det=1 (street), a = 2 for det=2 (intersection) — geometric` /
    `#   constant, not fitted (selected by CV from {1, sqrt(2), 2}).`
  - `PYSR_CONVERGENCE_SEARCH.md:119-120` shows that LOGO selection overfits on this very dataset: "The LOGO-best RadiusP form is a LOGO artifact. The 3-parameter model (29.1% LOGO max, smallest gap in the whole study) degrades to 62.95% under leave-one-charge-out."
  - Beta history:
    - b88ef6e: "No required beta meets gap<10m ... user decision on record: adopt beta*=4 with the gap rule relaxed".
    - 430d004 then adopted beta=3 from the "supplementary {2,3}" set.
    - The note (line 6) calls the rules "fixed before the numbers were seen". The rules were fixed in advance, but the candidate set and the choice were revised after the numbers were seen.
  - The improvements quoted for beta ("config_95 40.4% -> 5.7%", "max 43.4 -> 30.1") are measured on the config_93/95 pair that the gap rule was built on.
  - The LOGO pressure means across the beta scan span 8.21-8.80 (`soft_beta_selection.csv`). That is the same order as the differences used to choose.
- **Consequence.**
  - The headline LOGO numbers are post-selection estimates. The bias is probably small for the means, which were chosen among few alternatives about 0.2-0.6 pp apart.
  - The bias can be large for max and p90. Those are the statistics used to motivate beta and the new fits.
  - "Validated out-of-sample" is true for coefficients, not for structure.
- **Touches.** ALGORITHM §Result, §Provenance, §Limitations (worst case 30.1/30.4); `soft_beta_selection_note.md`; `soft_criterion_summary.csv`; `logo_summary_*.csv`; thesis ch. 9 (validation) and ch. 10.
- **Working tree.** The harness and tables are committed. `docs/ALGORITHM.md` is untracked. The B-bound change is modified-uncommitted (`z_urban.py`).
- **Options.**
  - (a) State plainly that LOGO is the error of the selected model and that the structure was chosen on the same folds. Cost: text only.
  - (b) Nested LOGO for the cheap choices: `a`, relwls/OLS, quad/legacy, range_switch/lambda_regime, canyon_trap/power. The inner LOGO on 35 families picks the variant and the outer family scores it. Cost: seconds to minutes; the fitters are fast.
  - (c) Nested beta selection over the six existing beta tables, reporting the config_95 improvement as the tuning target rather than as evidence. Cost: minutes; the tables already exist.
  - (d) Bring the LOCO-W and LOBO-b schemes into the repo and quote them as secondary estimates not used for selection. Cost: small harness, minutes.
  - (e) A truly untouched check needs new CFD configurations. Cost: simulation time.

### STA-02  [high]  The Z_urban fit and test domain is decided with the measured target and the measured R_conv

- **Where.**
  - `blastlib/regression/z_urban.py:216-271`: condition 1 at `:256-260`, condition 2 at `:262-266`, condition 3 at `:268-269`. The mask is applied in the fit (`:682-683`), the evaluation (`:750-751`) and the plots (`plots.py:127-128`).
  - The flags are set in `run_analysis.py:339-340`.
- **What.**
  - Condition 1 keeps a row only if the *measured* `MaxR < R_conv`. MaxR is the target, so this is the same event as Lambda < 1/xi.
  - Condition 2 uses the *measured* `R_conv`, the other model's target.
  - Both conditions are applied to test rows in CV. The reported z_P/z_I error is therefore conditional on the truth lying inside R_conv. That condition cannot be checked at prediction time.
  - The owner's outline already calls the same exclusion "filtering on the dependent variable" (`docs/THESIS_RESULTS_OUTLINE_HE.md:153-158`). The flags replaced deletion in the CSV, but the fit and the evaluation still exclude those rows.
- **Evidence.** Code:

  ```
  # run_analysis.py:339-340
  beyond_P = bool(np.isnan(maxR_P) or maxR_P >= act_R_P)
  beyond_I = bool(np.isnan(maxR_I) or maxR_I >= act_R_I)
  # z_urban.py:257-266
  inside = ~sub[beyond_col].astype(bool)
  ...
  inside = inside & (r_free < sub[radius_col].astype(float))
  ```

  Probe 1: row counts. Rows passing conditions 2-4 (R_conv measured, no condition on the target) and the rows removed by condition 1 (`req_soft3`, working tree):
  - Pressure: 683 rows, of which 92 (13.5%) are removed by condition 1.
  - Impulse: 980 rows, of which 280 (28.6%) are removed by condition 1.

  Probe 2: out-of-fold Z_urban error. Leave-one-family-out, refit per fold with the working-tree functions (`fit_pi_all_groups`, `fit_z_urban_all_groups`, `clip_z_urban_pred`). The "deployable" domain is Z_free >= 2, R_free > exclude_r and R_free < the fold's *predicted* R_conv:

  | target | domain | rows | row-MAPE | median | p90 |
  |---|---|---|---|---|---|
  | P | pipeline mask | 591 | 8.45% | 6.88% | 18.59% |
  | P | deployable | 671 | 8.61% | 7.12% | 18.80% |
  | I | pipeline mask | 700 | 9.84% | 7.80% | 19.45% |
  | I | deployable | 973 | **12.60%** | 9.96% | **27.29%** |

  The in-sample production refit shows the same pattern:
  - impulse: 9.12% on the mask against 12.05% on the deployable domain;
  - impulse rows removed by condition 1 alone: 21.26%.

  Probe 3: refitting with condition 1 dropped (conditions 2-4 kept) moves the coefficients:
  - range_switch det2: C1 0.432 -> 0.851, A 2.170 -> 2.638, B 0.943 -> 2.856;
  - det1: B 7.14 -> 9.00;
  - canyon_trap det2: C3 0.761 -> 0.932.

  Mean ln Lambda_I at Z_free = 9, 10, 11 is 0.129 / 0.079 / 0.070 under the mask against 0.273 / 0.283 / 0.323 without condition 1, which is the truncation signature. The physics conclusions survive:
  - impulse within-config slope d ln Lambda / d ln Z_free: -0.009 (mask) against +0.021 (no condition 1);
  - pressure: +0.122 against +0.114.
- **Consequence.**
  - The published z_I (CV median 9.40% in the working tree, 9.49% at HEAD, quoted in ALGORITHM as 9.5%) understates the error on the rows where the calculator will answer by about 3 pp at the mean and about 8 pp at p90.
  - The Z_urban coefficients depend on a rule that uses the target.
  - The physical argument for the domain is legitimate: beyond R_conv the urban field is by definition free-field, and `z_urban.py:554-565` explains the systematic MaxR overshoot. The statistical defect is that a test row's membership is decided by its own answer.
- **Touches.** `cv_summary_req_soft3.csv` (z_P, z_I); `final_production_z_urban_coefficients_req_soft3.csv`; ALGORITHM §Result (8.5%/9.5%) and §Domain of validity (the upper end of Z_free); the LOGO figures in `z_urban.py:103-105` and ALGORITHM §Provenance; thesis §4.6 and ch. 9.
- **Working tree.** Condition 1 is in HEAD. Conditions 2 and 3 are modified-uncommitted (`z_urban.py`). `max_radius_per_Z_req*.csv` are modified-uncommitted: MaxR_P differs from HEAD in 1915/1920 rows (max 26.8 m) and MaxR_I in 1911 (max 54.8 m).
- **Options.**
  - (a) Keep the fit domain and report both numbers: the conditional error and the error on the deployable domain defined with the fold's predicted R_conv. Cost: an evaluation variant; seconds; no refit.
  - (b) Define the *test* domain with predicted R_conv and keep training as is. Cost: phase-2 rerun of about 1-2 min at 500 splits (20 splits took 2.8 s here). This moves z_P/z_I of record.
  - (c) Treat the `beyond` rows as censored at ln(R_conv/R_free) (a censored-likelihood fit on ln Lambda) instead of dropping them. Cost: a new fitter plus a rerun; coefficients move.
  - (d) Give the `beyond` rows the value the deployed chain would output (Z_urban = Z_conv) and include them. Cost: a rerun; coefficients and metrics move.

### STA-03  [high]  Best-split artefacts are labelled and consumed as validation

- **Where.**
  - `tools/check_formulas/check_formulas.py:1-2, 634-648, 673, 724, 762, 819-821`;
  - `outputs/check_results/validation_comparison_req.csv` (tracked) and `validation_comparison_req_soft3.csv` (untracked);
  - `blastlib/regression/plots.py:70-72, 179-183`;
  - `tools/formulas_printer/formulas_printer.py:1, 129-132`;
  - `README.md:212-213`;
  - `tools/pressure_report/pressure_report.py:37-38`;
  - `gui/specs.py:108-109, 266-268`;
  - commit 78352a6.
- **What.** Four artefacts rest on the best split:
  - `check_formulas` takes the best-split coefficients and "validates" them on the best split. Its outputs are headed "CONVERGENCE RADIUS VALIDATION (TEST CONFIGS)".
  - The `cv_best_*.png` titles read "Test MAPE = x%" for the same split.
  - `formulas_printer` (README: "Print the fitted formulas in readable form") prints `best_*` coefficients, which were fitted on 76 configurations. It does not print `final_production_*`.
  - `pressure_report` sends readers to `check_formulas` "for held-out errors".

  That split is the minimum over 500 draws of the worst of four MAPEs, selected on its own test set.
- **Evidence.**
  - `validation_comparison_req_soft3.csv`: mean error 6.02% (RadiusP) and 5.78% (RadiusI) on 20 configurations. These equal iteration 180 of `cv_summary_req_soft3.csv`. For comparison, the split medians are 8.79 / 7.15 and LOGO is 8.43 / 7.21.
  - Probe: the selected split holds out no geometry at all. Its sibling-in-train fraction is 1.00 (20/20), against 0.925 on average (minimum 0.600) over the 500 splits.
  - The best-of-k statistic falls as k grows, as a selection statistic should. From `cv_summary_req_soft3.csv`, min(worst) over the first k splits is 9.11 (k=20), 7.62 (50), 7.62 (100), 7.20 (200) and 7.20 (500).
  - Commit 78352a6 reported "best-split validation: z_P 6.85%, z_I 7.47%, conv_P 6.59%, conv_I 5.31%" as results.
  - Mitigations already present: ALGORITHM:220-224 ("must never be quoted as accuracy"), THESIS_RESULTS_OUTLINE_HE.md:345, and `cross_validation.py:221-233, 249-250`. The last one is uncommitted.
- **Consequence.**
  - The artefacts named "validation" and "Test MAPE" are optimistic by about 2.8 pp (P) and 1.4 pp (I) against the median.
  - The formulas printer hands out non-production coefficients. The GUI exposes both tools.
- **Touches.** `validation_comparison_*.csv`, `validation_*.png`, `cv_best_*.png`, `best_*.csv`; any thesis figure or formula taken from `check_formulas` or `formulas_printer`.
- **Working tree.** `best_z_urban_coefficients_req_soft3.csv` and `best_test_configs_req.csv` are modified-uncommitted. `validation_comparison_req_soft3.csv` is untracked. The tools are committed.
- **Options.**
  - (a) Relabel ("selected split, optimistic, not an accuracy estimate"). Cost: text.
  - (b) Make `check_formulas` report out-of-fold (LOGO) predictions from the production pipeline. Cost: a tool change; seconds to run.
  - (c) Point `formulas_printer` at `final_production_*`. Cost: trivial.
  - (d) Keep `best_*` for debugging only, or stop writing them. Cost: none numerically.

### STA-04  [high]  The "safe domain" is drawn around the held-out errors and then quoted and shipped as an error bound

- **Where.**
  - `docs/ALGORITHM.md:271-308`;
  - `outputs/check_results/safe_domain_req_soft3.csv`;
  - commit 430d004;
  - `blast_calculator.html:259-276, 302-308, 322-323`;
  - the related post-hoc tiers in `docs/PHYSICS_ANALYSIS_HE.md:470-491, 666` and `docs/THESIS_RESULTS_OUTLINE_HE.md:354-361`.
- **What.** The box (rho 0.31-0.56, Pi2 0.5-5.4, H/s <= 3) was defined by looking at the LOGO errors. The statement "every held-out prediction is below 20%" is then made about the box's own members. The calculator turns it into a "safe" banner and a ±15% band (±30% outside the box).
- **Evidence.**
  - Probe: the rule `rho in [0.308, 0.563] & Pi2 in [0.499, 5.44] & H/s <= 3` reproduces `InSafeDomain` exactly. Each edge sits on a design level next to a failing configuration:
    - the rho levels are {0.184, 0.207, 0.309, 0.360, 0.444, 0.5625, 0.735};
    - the Pi2 levels below 0.6 are {0.437, 0.500}, and the lower bound 0.499 is set just below 0.500;
    - the H/s levels include 3.0 and then 4.8.
  - Inside the box: 38 configurations, max 18.9% / 19.6%, mean 7.8% / 6.4%. Outside: 58 configurations, of which 46 are also below 20% on both targets (mean 8.9% / 7.7%).
  - The errors are convergence-radius LOGO errors only (`LOGO_ErrP_pct`, `LOGO_ErrI_pct` match `logo_cv_req_soft3_relwls_quad.csv`). The calculator still shows the banner above the Z_urban outputs.
  - The calculator's test is a marginal box. It labels unsimulated combinations "safe" with a ±15% band, for example b = 20 m, s = 12 m, H = 12 m, W = 100 kg (rho 0.39, Pi2 2.59, H/s 1.0). No configuration has b = 20 or W = 100, and for b >= 15 only s ∈ {5, 20} were simulated.
  - The 1.5-block-period threshold (ALGORITHM:466-483) was also read off the same errors. The document does say it is not a filter.
- **Consequence.**
  - "Below 20% everywhere in the box" is true by construction and is not an estimate for a new configuration inside the box.
  - The ±15% band is a post-selection descriptive quantity presented to users as an uncertainty envelope (proposal aim 5).
  - Two different post-hoc tier schemes coexist in the documents.
- **Touches.** ALGORITHM §"The safe domain"; the calculator bands; thesis ch. 9 (validity) and ch. 10 (engineering rules).
- **Working tree.** The CSV and the calculator are committed. `docs/ALGORITHM.md` is untracked.
- **Options.**
  - (a) Describe the box as a descriptive partition of the 96 LOGO errors. Cost: text.
  - (b) Nested check: choose the box on 35 families and score the held-out family's configurations that fall inside the chosen box. This gives an honest coverage rate. Cost: seconds; the LOGO errors already exist.
  - (c) Replace the band with a prediction interval computed from out-of-fold residuals, for example split-conformal per det. Cost: a small script; seconds.
  - (d) Simulate interior points (b = 20, s = 8-12, W = 100-250) to test the box. Cost: CFD time.

### STA-05  [medium]  No uncertainty on any published coefficient or prediction; several coefficients are weakly identified

- **Where.**
  - `blastlib/regression/output.py:10-180` writes point estimates only.
  - `docs/ALGORITHM.md:329-360` publishes four decimals with a physical reading for each term.
  - `docs/THESIS_RESULTS_OUTLINE_HE.md:262` uses "A ≈ 2.2–2.6" as independent confirmation of the s ≈ W^(1/3) boundary.
- **Evidence.** Probe: a family-cluster bootstrap. The 18 (det, b, s, H) families per det were resampled 300 times, and the production fitters were refit on each resample (working-tree `req_soft3`). Point estimates with 95% percentile ranges:

  | model | det | coefficients |
  |---|---|---|
  | range_switch P | 1 | C0 0.091 [0.042, 0.141] · C1 2.547 [1.103, **6.000**=bound] · A 2.919 [2.477, 3.545] · B 7.139 [2.447, **20.000**=bound] |
  | range_switch P | 2 | C0 0.113 [0.068, 0.198] · C1 0.432 [0.213, 1.737] · A 2.170 [1.857, 3.048] · B 0.943 [0.321, 6.815] |
  | canyon_trap I | 1 | C0 -0.108 [-0.470, -0.013] · C1 3.088 [2.545, 4.583] · C2 0.857 [0.029, 1.043] · C3 1.550 [0.333, **6.000**=bound] |
  | canyon_trap I | 2 | C0 0.007 [-0.155, 0.058] · C1 2.664 [2.296, 3.352] · C2 1.099 [0.849, 1.159] · C3 0.761 [0.263, 1.553] |
  | RadiusP | 1 | C0 9.063 [8.584, 9.771] · C1 -0.645 [-1.124, -0.379] · C2 2.018 [0.953, 3.577] · C3 0.591 [0.338, 0.789] |
  | RadiusP | 2 | C0 11.858 [11.120, 12.582] · C1 -1.375 [-1.626, -1.087] · C2 2.782 [1.583, 3.675] · C3 0.776 [0.285, 1.022] |
  | RadiusI | 1 | A 14.936 [13.988, 15.620] · p 0.203 [0.150, 0.248] · q 0.024 [**-0.004**, 0.055] · r 0.065 [**-0.023**, 0.129] · r2 -0.101 [-0.136, -0.049] |
  | RadiusI | 2 | A 14.602 [13.390, 16.200] · p 0.176 [0.098, 0.283] · q 0.079 [0.037, 0.129] · r 0.125 [0.022, 0.222] · r2 -0.089 [-0.143, -0.035] |

  - corr(C1, B) is 0.97 in both dets, and B sits on its upper bound in 8% of the det-1 resamples.
  - The ratio C1/B is identified: 0.357 [0.266, 0.443] for det 1 and 0.458 [0.256, 0.663] for det 2.
  - HEAD against the working tree illustrates the point. det-1 B moved 4.01 -> 7.14 and C1 1.75 -> 2.55, while C1/B moved only 0.435 -> 0.357.
  - For comparison, only 2 of 500 production CV folds end on a bound, so the bound problem shows under family resampling, not under the 80/20 splits.
- **Consequence.**
  - Physical readings of the individual values of B, C1, C3, q and r are not supported by the data.
  - The "A ≈ 2.2–2.6" coincidence has intervals of roughly ±0.5.
  - There are no uncertainty envelopes for Z_urban at all, and none for R_conv outside the post-hoc box (STA-04).
- **Touches.** `final_production_*_req_soft3.csv`; ALGORITHM "The fitted coefficients"; thesis ch. 8 and appendix A; the calculator.
- **Working tree.** `final_production_z_urban_coefficients_req_soft3.csv` is modified-uncommitted.
- **Options.**
  - (a) Publish family-cluster bootstrap intervals. Cost: under a minute.
  - (b) Report identified combinations (C1/B, A) next to the raw constants.
  - (c) Prediction intervals from out-of-fold residuals, by det. Cost: seconds.
  - (d) Whether to simplify terms whose intervals cover zero is a modelling decision for the owner. It would change coefficients and is only noted here.

### STA-06  [medium]  "The data recovers the Hopkinson exponent" is stated without an interval, and the value depends on the specification

- **Where.** `docs/ALGORITHM.md:54-58`. The contrasting statement is in `docs/THESIS_RESULTS_OUTLINE_HE.md:179-180` ("W explains 20% of Z_conv,P ... a direct measure of its invalidity").
- **Evidence.** Probe: OLS of ln RadiusI on [1, ln W, ln rho, ln(H/s), ln s], 48 configurations per det. The conventional OLS standard errors treat configurations as independent, which they are not within a family:

  | det | alpha | SE | 95% CI | with (ln Pi2)^2 added |
  |---|---|---|---|---|
  | 1 | 0.340 | 0.012 | [0.317, 0.363] | 0.310 [0.289, 0.331] |
  | 2 | 0.307 | 0.012 | [0.282, **0.332**] | 0.282 [0.257, 0.307] |

  The values 0.340 and 0.307 reproduce the document. For det 2 the interval excludes 1/3. Adding the curvature term that the production RadiusI model itself carries moves both estimates down by about 0.03, and then both exclude 1/3.
- **Consequence.** The sentence "the scaling is therefore a result read out of the measurements" is not supported as written for det 2. The two documents make opposite statements about the same question.
- **Touches.** ALGORITHM §"Why the Hopkinson cube root"; thesis ch. 8.1.
- **Working tree.** ALGORITHM is untracked. The tables are committed.
- **Options.** Report alpha with a family-clustered or bootstrap interval, the exact specification, and the pressure counterpart. Cost: seconds.

### STA-07  [medium]  Documents, calculator and notes quote numbers that the working-tree tables of record no longer match

- **Where and evidence.** The working-tree side was re-derived by the smoke run and the probes:

  | source | quoted | working-tree table |
  |---|---|---|
  | ALGORITHM:350-353, ALGORITHM_HE:308; `blast_calculator.html:248-253` | Z_urban P det1 0.0866 / 1.7457 / 2.7434 / 4.0123; det2 0.1294 / 0.5276 / 2.2219 / 1.1818; I det1 -0.0941 / 2.9631 / 0.8344 / 1.6752; I det2 -0.0063 / 2.6650 / 1.0991 / 0.7526 | P det1 0.0911 / 2.5468 / 2.9191 / 7.1392; det2 0.1128 / 0.4320 / 2.1697 / 0.9433; I det1 -0.1079 / 3.0884 / 0.8573 / 1.5496; I det2 0.0068 / 2.6644 / 1.0985 / 0.7614 |
  | ALGORITHM:216-222; `soft_beta_selection_note.md` | z medians 8.5 / 9.5 (8.49 / 9.49); best split 7.42 against a median of 9.86 | 8.42 / 9.40; 7.20 against 9.85 |
  | ALGORITHM:265-267 | pressure rows at Z_free = 2..10: 95, 96, 96, 96, 94, 90, 64, 14, 2 (reproduced with the HEAD mask on the HEAD table) | 75, 87, 90, 96, 94, 86, 58, 4, 1 |
  | PHYSICS_ANALYSIS_HE:647; THESIS_RESULTS_OUTLINE_HE:339-342 | CV means 8.66 / 8.43 / 8.37 / 9.67 | 8.81 / 7.15 / 8.43 / 9.59 |
  | PHYSICS_ANALYSIS_HE:651; outline:348 | LOGO max 43.4 / 38.5 | 30.1 / 30.4 (production) |
  | PHYSICS_ANALYSIS_HE:643; `tools/z_surface_3d/z_surface_3d.py:34-37` | RadiusP C0 7.78 (hard, OLS) | 9.063 (production `req_soft3`) |

  The working-tree tables are internally consistent. The smoke run reproduced `final_production_convergence_coefficients_req_soft3.csv` and `final_production_z_urban_coefficients_req_soft3.csv` byte for byte, and `cv_summary_req_soft3.csv` rows 0-19 to 6e-15.
- **Consequence.** Whichever state the owner adopts, one set of cited numbers is wrong. The calculator currently ships HEAD Z_urban coefficients.
- **Touches.** ALGORITHM (both languages), the calculator, `soft_beta_selection_note.md`, the Hebrew analysis documents, `z_surface_3d`; thesis ch. 8-9.
- **Working tree.** The tables are modified-uncommitted. ALGORITHM is untracked. The calculator and `z_surface_3d` are committed.
- **Options.** The owner decides which state is of record. If it is the working tree, the list above is the update set. If it is HEAD, the working-tree regression changes are what diverge. Cost: text and diff only; no rerun.

### STA-08  [medium]  The Z_urban LOGO figures and several other held-out numbers have no harness in the repo

- **Where.**
  - `tools/logo_cv/logo_cv.py:1-10, 54-87` covers RadiusP and RadiusI only.
  - The Z_urban LOGO numbers appear in `z_urban.py:103-105` ("range_switch 8.4% vs 9.9% legacy, canyon_trap 9.9% vs 12.3%"), `ALGORITHM.md:419-421` (10.91 against 9.81; in-sample 10.44 against 9.23), `:539-542` (11.7 / 12.7 against 9.8), the block-period table at `:454-464`, and commit 5a1f177.
  - `PYSR_CONVERGENCE_SEARCH.md:169` says "Scratch scripts (not part of the pipeline)".
- **What.** These numbers were computed on the hard `req` tables, before the working-tree mask and MaxR changes. They cannot be regenerated from the repo.
- **Evidence.** Probe (STA-02, working-tree code, `req_soft3`, leave-one-family-out):
  - Pressure: 8.45% row-pooled, 8.40% configuration-averaged.
  - Impulse: 9.84% row-pooled, 9.56% configuration-averaged; worst configuration 45.1%.

  These are of the same magnitude as the quoted figures. Definitional choices (row-pooled or configuration-averaged, table, mask) move them by about 0.3 pp, the same size as several of the differences used to choose forms.
- **Touches.** ALGORITHM §Provenance and §Limitations; the thesis claim "cross-application costs 3–4 pp" (outline:256).
- **Working tree.** `z_urban.py` is modified, but the comment lines date from HEAD. ALGORITHM is untracked.
- **Options.** Add a Z_urban mode to `tools/logo_cv` (per-fold convergence fit for the clip, both aggregations) and regenerate the quoted numbers. Cost: a small tool; seconds to run.

### STA-09  [medium]  Extrapolation guards are incomplete

- **Where.**
  - `blastlib/regression/convergence_models.py:139-169, 253-284` and `z_urban.py:514-594` have no domain check. `Zf_min` is stored (`z_urban.py:90`) but never enforced at prediction.
  - `blast_calculator.html:274-300, 351-354, 413-416, 461-464`.
- **Evidence.**
  - The calculator refuses input outside the marginal b, s, H, W, Pi2 and H/s ranges, which is good. However, `ENV.rho` is defined (`:275`) and never referenced (0 uses). For example, b = 10 and s = 20 give rho = 0.111 against a sampled minimum of 0.184; the tool raises only an "edge" warning and still answers.
  - `calc()` has no Z_free check. `calcQ()` accepts any `Zf>0`, so Z_free = 1 is answered even though it is outside the Z_free >= 2 validity and possibly inside the first-street exclusion.
  - The Z table runs to `ceil(max(ZcP, ZcI))` with no mark once pressure passes Z_free ≈ 8. In the working tree the pressure fit has 4 rows at Z_free = 9 and 1 row at 10, and the `range_switch` 1/Z_free term extrapolates there.
  - The block-period condition that ALGORITHM:466-470 calls "checkable before any prediction is made" is not checked.
  - The joint design is sparse (see STA-04 and STA-10).
- **Consequence.** The deployed tool extrapolates silently in rho and Z_free. API users (tools, GUI) get no warning at all.
- **Touches.** ALGORITHM §Domain of validity; the calculator.
- **Working tree.** Committed.
- **Options.**
  - (a) Enforce the rho envelope, Z_free >= 2 and R_free > exclude_r, and flag Z_free above the last well-populated level. Cost: code in the calculator; no numeric change.
  - (b) Check distance to the nearest simulated configuration in Pi space instead of marginal boxes.
  - (c) Add warnings to `predict_*`.

### STA-10  [info]  Degrees of freedom and effective sample size against 96 configurations

- **Design.**
  - A 72-configuration factorial: b ∈ {15, 30} × s ∈ {5, 20} × H ∈ {4, 12, 24} × W ∈ {50, 500, 1500} × det.
  - A 24-configuration b = 10 block: s ∈ {5, 8, 12}, H ∈ {10, 15, 24}, W ∈ {250, 1000}.
  - Intermediate street widths and charge weights therefore exist only at b = 10.
  - The 36 (det, b, s, H) families: 24 have 3 configurations and 12 have 2.
  - There are 7 distinct rho values and 18 distinct (rho, H/s) pairs per det.
- **Parameter counts** (working tree, `req_soft3`):

  | model | coef/det | n per det | configs/coef | families/coef |
  |---|---|---|---|---|
  | RadiusP additive (relwls) | 4 (+ `a` chosen from 3) | 48 configs | 12 | 4.5 |
  | RadiusI power + quad | 5 | 48 configs | 9.6 | 3.6 |
  | Z_urban P range_switch | 4 | 280 / 311 rows (3-9 per config) | 12 | 4.5 |
  | Z_urban I canyon_trap | 4 | 340 / 360 rows (4-10 per config); constant within a config | 12 | 4.5 |

- **Totals.** 34 fitted constants over 96 configurations, plus the structural degrees of freedom of STA-01.
- **Reading.**
  - The rows are not independent. canyon_trap is range-flat, so its effective n is the configuration count.
  - The ratios are adequate for point estimates. With 4.5 or fewer families per coefficient, however, the family, not the row, should be the unit for any interval (STA-05).

### STA-11  [low]  `n_iter`: the split sequence is a prefix, not "changed entirely"; the printed split size is wrong

- **Where.**
  - `CLAUDE.md:168-170, 257-258`;
  - `blastlib/regression/cross_validation.py:52-55, 97, 100`;
  - `run_analysis.py:505-506`.
- **Evidence.**
  - Probe (sklearn 1.9.0): the splits from `StratifiedShuffleSplit(n_splits=20, test_size=0.2, random_state=42)` equal the first 20 splits of `n_splits=500` (True).
  - The smoke run's `cv_summary` equals rows 0-19 of the working-tree `cv_summary_req_soft3.csv` (max |diff| 6.2e-15).
  - `cross_validation.py:97` computes `n_test = max(1, int(n_configs * test_fraction))` = 19, and the log prints "Train/test split: 77/19". The splitter uses ceil(0.2·96) = 20, so the real split is 76/20 (10 per det).
- **Consequence.**
  - Medians at different `n_iter` are comparable up to Monte Carlo error (STA-12).
  - The best-split statistic and the `best_*` files are not comparable, because the minimum falls with `n_iter` (STA-03).
  - The documents misstate the mechanism, and the behaviour depends on the sklearn version.
- **Working tree.** `cross_validation.py` is modified-uncommitted, but the `n_test` line dates from HEAD. CLAUDE.md is untracked.
- **Options.** Correct the text, and take `n_test` from the splitter. Cost: text only.

### STA-12  [low]  How the metrics are defined and aggregated

- **Row weighting.** z MAPE is pooled over rows. A configuration with a large R_conv (up to 9-10 valid rows) weighs up to three times one with 3-4 rows, and the fits weight rows the same way.
- **Pooling.** conv MAPE is pooled over both dets. `worst` is the maximum of four MAPEs, two of which (z_P, z_I) are on a different unit (rows, not configurations).
- **Loss and metric.**
  - relwls minimises the sum of ((y_hat - y)/y)^2, which is not MAPE. `ALGORITHM.md:138-140` says it is "the same quantity (MAPE)".
  - RadiusI and Z_urban minimise squared log error, and ALGORITHM does not say so.
  - MAPE itself is appropriate here: radii are 20-160 m and Z_urban >= ~1, so no denominator nears zero.
- **Uncertainty of the CV medians.**
  - The documents report only the medians. The spread across splits is wide, p5-p95: conv_P 6.37-11.30, conv_I 5.18-9.21, z_P 6.99-9.87, z_I 7.52-12.41.
  - The splits overlap, so that spread is not a confidence interval.
  - The Monte Carlo 95% range of the 500-split median, bootstrapped over splits, is about ±0.15 pp.
  - Probe, seed-to-seed medians at 100 splits (seeds 42 / 0 / 7): conv_P 8.54 / 8.85 / 8.41 and z_I 9.16 / 9.53 / 8.95.
  - The comment at `cross_validation.py:108-109` ("any difference in the numbers is real, not split luck") overstates what a common set of splits guarantees. It is a paired comparison conditional on those 500 splits. Example: cbb2312 compares z_P 8.41 and 8.35.
- **Options.** Report configuration-averaged errors next to row-pooled ones, report the IQR, and give paired differences with a bootstrap over splits when variants are compared. Cost: seconds from `cv_summary`.

### STA-13  [low]  Reproducibility of the statistics

- **Versions.** `requirements.txt` uses `>=` only. The running versions are sklearn 1.9.0, scipy 1.17.1, numpy 2.4.6 and pandas 3.0.3, and no lock file records them. The production Z_urban constants depend on scipy `curve_fit` (TRF). `cv_summary` and `best_*` depend on sklearn's splitter.
- **Row order.** Split membership is positional in the convergence table (`run_analysis.py:166`, a sorted glob). `config_01`..`config_96` sort stably, but a `config_100` would sort before `config_11` and reshuffle every split.
- **Untracked documents.** `docs/ALGORITHM.md`, `ALGORITHM_HE.md`, `PYSR_CONVERGENCE_SEARCH.md` and `CLAUDE.md` are untracked.
- **Harnesses outside the repo.** The Z_urban LOGO, PySR, LOCO-W/LOBO-b and safe-domain scripts are not in the repo (STA-08).
- **What does hold.** The production coefficients do not depend on the seed or on `n_iter`; they are refit on all data and reproduced byte for byte at `n_iter` 20.
- **Options.** Pin versions or keep a lock file, and print the versions in the Phase-2 log. Cost: trivial.

## Checked and found consistent

- **Unit of the split.** The split is by configuration: all Z rows of a configuration land on one side (`cross_validation.py:129-138`). Splits are stratified by det (10 + 10 test configurations per split).
- **No global preprocessing.** Nothing is fitted on all rows before the split: there is no scaling or centring, and the free-field reference is a separate simulation table.
- **Legacy regime classifier.** It is refit inside each fold when active. It is not on the production path (`Z_URBAN_FORM`), so `ATTENUATION_CRITERION`, which was fitted on all 96 configurations, is unused.
- **The Z_conv clip in CV** uses the same fold's convergence fits (`cross_validation.py:168-177`). The clip never uses the measured radius.
- **LOGO harness.** Families are (Det, b, s, H) and fits are per det, so a held-out family's other-det twin does not enter its fit.
  - The ALGORITHM LOGO table matches `logo_summary_req_soft3_relwls_quad.csv` (8.43/5.67/18.65/30.07; 7.21/5.89/16.40/30.39) and `logo_summary_req_legacy_legacy.csv`.
  - The LOGO errors in `safe_domain_req_soft3.csv` match `logo_cv_req_soft3_relwls_quad.csv`.
  - The untracked `logo_summary_req_soft2_relwls_quad.csv` is consistent with `soft_beta_selection.csv` (P 8.80 / 29.97).
- **Numbers quoted in ALGORITHM that hold.**
  - The sibling fraction is 92.5% (minimum 60.0%).
  - 272 of 500 splits have worst < 10% ("about half").
  - The mean per-split worst case is 10.03% ("≈ 10%").
- **Size of the sibling optimism.** Probe, 100 splits each: family-level `GroupShuffleSplit` gives medians conv_P 8.56, conv_I 7.64, z_P 8.25, z_I 9.68. Stratified random splits give 8.54, 7.05, 8.36, 9.16. The random splits are optimistic by at most about 0.6 pp at the median. ALGORITHM's caution goes in the right direction and is, if anything, stronger than the effect.
- **Production refit.** It uses 100% of the data and is stated in the code (`cross_validation.py:318-335`) and in ALGORITHM:222-224. The refit is independent of the seed and of `n_iter`.
- **Convergence coefficients.** The RadiusP and RadiusI values in ALGORITHM:336-344 and in the calculator (`CONV_P`, `CONV_I`) match `final_production_convergence_coefficients_req_soft3.csv`. The impulse Z_urban blocks are identical between `req` and `req_soft3`, as stated.
- **No silent failures.** `cv_summary_req_soft3.csv` has 500 rows; no split was skipped. No Z_urban curve fit failed in the 100-split probes (three seeds and grouped). Only 2 of 500 CV folds end on a bound (det-1 pressure B and C1).
- **Boolean flags.** The `beyond_*` string-to-boolean coercion (`z_urban.py:632-636`) prevents the "every string is truthy" trap.

## Not checked

- Phase 1 (radius and MaxR measurement), including the working-tree change to the per-direction exceedance level that moved MaxR in 1915 of 1920 rows. That is another lens, and no data folder was read.
- The test suite. `pytest` is not installed in the available interpreter, so neither the fast tests nor the anchor tests ran. No test result is claimed.
- The production 500-split Phase 2 run (not run, as instructed). Only splits 0-19 and the production refit were reproduced.
- The PySR, LOCO-W/LOBO-b, beta-scan and safe-domain derivation scripts, which are not in the repo.
- `blastlib/street/fitting.py` (the street-channelling regression).
- The GUI wiring beyond the spec lines cited.
- Hebrew/English document parity beyond the numbers listed in STA-07.
- The thesis and the proposal (off limits).
