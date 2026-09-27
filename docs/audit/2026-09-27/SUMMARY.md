# Audit summary (2026-09-27)

- **Commit:** `5f19029` (branch `compare-v7`).
- **Tree:** dirty. 30 tracked files modified (19 code, 11 results-of-record tables under `outputs/tables/`), 49 untracked (including `CLAUDE.md`, `docs/ALGORITHM.md`, `docs/ALGORITHM_HE.md`, `blastlib/io/raw_store.py`, 24 result files). Every lens audited the working tree as it stands and tagged each finding committed / modified / untracked. The only file added by the audit is this folder.
- **Lenses run:** algorithm, physics, choices, statistics, reproducibility. All five completed. Traceability (`/verify trace`) was not run.
- **Reports:** [algorithm.md](algorithm.md), [physics.md](physics.md), [choices.md](choices.md), [statistics.md](statistics.md), [reproducibility.md](reproducibility.md).
- **Tests:** `pytest` is not installed in the owner's interpreter (Python 3.12.10). The repro checker installed it into a scratch folder only. Working-tree fast suite: 100 passed, 0 failed, 16 deselected (5 `slow`, 11 that would download cloud-only v1/v2 files). **By CLAUDE.md §5 the anchor tests did not run.** As a substitute, the anchor chain on the local `data/raw_npz` reproduces 62.328853560057645 and 38.15139013777145 bit-exactly. HEAD's own suite on HEAD code: 56 passed, 3 failed, 2 errors (REP-02).
- **Production:** `req_soft3`. Convergence coefficients are identical at HEAD and in the working tree. All 16 production Z_urban coefficients differ (REP-01).

## Counts

| lens | high | medium | low | info | total |
|---|---|---|---|---|---|
| algorithm (ALG) | 3 | 11 | 6 | 0 | 20 |
| physics (PHY) | 4 | 6 | 7 | 0 | 17 |
| choices (CHO) | 6 | 10 | 5 | 2 | 23 |
| statistics (STA) | 4 | 5 | 3 | 1 | 13 |
| reproducibility (REP) | 2 | 4 | 4 | 2 | 12 |
| **total** | **19** | **36** | **25** | **5** | **85** |

Many findings are the same issue seen through different lenses. The clusters:

| cluster | findings |
|---|---|
| A. Which state is of record (HEAD vs uncommitted working tree) | REP-01, ALG-02, CHO-04, ALG-04, STA-07, REP-04, REP-05, REP-06, REP-10 |
| B. Building-rim cells: grid merge runs before the solid mask | ALG-01, PHY-01, CHO-09, PHY-10, CHO-19 |
| C. Z_urban domain decided with the measured target | ALG-03, STA-02, ALG-19, CHO-10 |
| D. beta = 3 selection and the soft scan's mesh dependence | CHO-01, ALG-06, CHO-07, PHY-02, ALG-07 |
| E. Model choices made on the reported LOGO folds | STA-01, CHO-13, CHO-15, STA-08, ALG-13 |
| F. Safe-domain box | STA-04, CHO-14, ALG-11 |
| G. Pressure floor: urban P (code) vs P_ff (outline) | CHO-03, PHY-09 |
| H. Physical anchoring of 10 kPa and thr_I = 20; no KB/UFC check | CHO-02, CHO-06, PHY-06, PHY-08 |
| I. Mesh fixed in metres, not in scaled units | PHY-02, PHY-03, PHY-04, PHY-17, CHO-08 |
| J. "Dimensionless" groups and the constant `a` | ALG-10, PHY-07, CHO-13 |
| K. Hopkinson exponent argument | ALG-09, STA-06, PHY-13 |
| L. Req end-bin bias | ALG-05, CHO-20, PHY-11 |
| M. Hard-coded copies (calculator, `z_surface_3d`) | ALG-14, CHO-12, REP-06 |
| N. `n_iter` wording | STA-11, REP-09 |
| O. `MAX_HEIGHT` unused | ALG-20, CHO-18 |

## All findings

| id | sev | title | results of record / thesis claims touched |
|---|---|---|---|
| ALG-01 | high | Multi-grid max-merge runs before the solid-cell mask; wall-skin cells enter both convergence scans | every `convergence_table_*`, `beyond_*`, Z_urban domain, all coefficients, LOGO; claims on RadiusI accuracy, I-vs-P ordering, Hopkinson argument |
| ALG-02 | high | ALGORITHM.md (EN and HE) mixes HEAD and working-tree numbers | Z_urban coefficients, CV medians, best split, Z_free row counts; any thesis text quoting them |
| ALG-03 | high | "Comparable by construction" does not hold; the gap is absorbed by an outcome-dependent row filter | both Z_urban fits and their CV errors; the "why the algorithm is sound" argument |
| ALG-04 | medium | Uncommitted, undocumented changes to the MaxR / Z_urban path | `max_radius_per_Z_*`, Z_urban coefficients, CV |
| ALG-05 | medium | Req weights the half-width end sectors as full sectors | every radius (median 0.3-0.5 %, up to 3.8 %) |
| ALG-06 | medium | beta = 3 presented as pre-registered; candidate set widened after the pre-registered set failed | thesis wording on pre-registration |
| ALG-07 | medium | Soft-criterion gains attributed across a simultaneous model change | claims about what the soft criterion buys (P p90 +2.8 pp, not +1.5) |
| ALG-08 | medium | Stated loss (MAPE) differs from the fitted loss (L2 relative); Z_urban bounds undocumented | method description |
| ALG-09 | medium | Hopkinson reasons 2 and 3 do not reproduce, or depend on ALG-01 | thesis scaling argument |
| ALG-10 | medium | "Every predictor is a dimensionless Pi group" does not hold | soundness section; physical reading of terms |
| ALG-11 | medium | The printed safe-domain box selects 22 configurations, not 38 | ALGORITHM safe domain; users of the box |
| ALG-12 | medium | README contradicts CLAUDE.md (compare_v6 as reference), wrong default store, v1 no longer readable | README §3-4 |
| ALG-13 | medium | Many quantitative claims have no artefact in the repo | Z_urban LOGO, elasticity -0.6, coarsening table and others |
| ALG-14 | medium | `z_surface_3d` hard-codes non-production coefficients; `a` written twice | `z_surface_3d` figures |
| ALG-15 | low | Special cases of the sector scan and of Req are undocumented | ALGORITHM Step 1 |
| ALG-16 | low | Impulse "floor ≈ 0.93" misstated | ALGORITHM limitations |
| ALG-17 | low | Stale numbers in documents and comments | docs |
| ALG-18 | low | Stale docstrings and printed text | code text only |
| ALG-19 | low | Z_urban test domain uses the held-out configurations' measured R_conv | reported Z_urban MAPE |
| ALG-20 | low | `MAX_HEIGHT` and the `C` column affect no result | none |
| PHY-01 | high | Building-rim cells survive the mask and drive both convergence radii | all RadiusP/RadiusI, coefficients, `beyond_*`, clip, LOGO/CV, safe domain; "impulse 1.5x further", "reverberation Z 12-16", "ignition 50->500 kg"; plausibly the thr_I calibration |
| PHY-02 | high | Soft pressure scan has a W-dependent bias because the mesh is fixed in metres | production RadiusP; C1/C2 Pi_2 terms; beta gap rule |
| PHY-03 | high | The 100 m fine/medium grid seam cuts the pressure radii of large charges only | RadiusP for W >= 1000; "saturation 1.02", "Z non-monotone in W"; ALGORITHM monotonicity claim |
| PHY-04 | high | Per-direction MaxR_I level reads a deficient fine-grid reference near the grid edge (uncommitted) | MaxR_I rows, `beyond_I`, canyon_trap fit rows (W >= 1000, Z_free 9-12) |
| PHY-05 | medium | W = 1000 reference coarse grid is a copy of the medium grid | 12 configurations, at most 0.55 % on radii |
| PHY-06 | medium | No KB/UFC check; CFD free field 10-32 % below the standard curve | physical justification of the absolute thresholds; thesis validation section |
| PHY-07 | medium | Pi_2 and Z are not dimensionless; "crossover at s = W^(1/3)" is a unit artefact | physical reading of the canyon term; "three places, same number" |
| PHY-08 | medium | Both bands loose at the measured radii; impulse band exceeds I_ff beyond Z ≈ 13.7; "1.8x" stale | meaning of R_conv,I; asymmetry statement; "all radii at Z <= 16" |
| PHY-09 | medium | Pressure floor on urban P in code, on P_ff in the outline | thesis §3.2.1 (same as CHO-03) |
| PHY-10 | medium | The three grids are solver stages, max-stitched; undocumented | impulse-field correctness; root of PHY-01 and PHY-04 |
| PHY-11 | low | Req +0.55 % for a round field | common mode (same as ALG-05) |
| PHY-12 | low | Legacy impulse rule compares Pa.s with a kPa number | unreachable branch |
| PHY-13 | low | Free-field Hopkinson statistics quoted inconsistently | ALGORITHM, outline |
| PHY-14 | low | `PressureAtR` / `ImpulseAtR` are single-cell values of unclear meaning | table column; `parametric_study_B` |
| PHY-15 | low | Pressure curves pair MaxR with the axis-sampled CSV level | `config_curve`, `pressure_report` |
| PHY-16 | low | Provenance of `free_field_data.csv` undocumented | CLAUDE.md §4 |
| PHY-17 | low | Some measurement lengths fixed in metres | K window, ring half-width |
| CHO-01 | high | beta = 3 was not selected by a rule fixed in advance | all production pressure radii, `beyond_P`, Z_urban P domain, `final_production_*_req_soft3`, LOGO headline; pre-registration claim |
| CHO-02 | high | 10 kPa band unsourced, no sensitivity on record | every RadiusP, `beyond_P`, clip, RadiusP coefficients; aim 4 |
| CHO-03 | high | Pressure floor on urban P in code, on P_ff in outline; radii differ by a median of 58 % | how the thesis states the criterion |
| CHO-04 | high | Uncommitted MaxR and domain changes rewrote results of record; docs and calculator carry HEAD | `final_production_z_urban_*_req_soft3`, `cv_summary`, `max_radius_per_Z`; ALGORITHM, calculator |
| CHO-05 | high | `req` presented as the "indistinguishable" distance; about half of the directions exceed it | R_conv / MaxR as a safety distance (aim 4); meaning of the clip |
| CHO-06 | high | thr_I = 20 calibrated for 100 % convergence; "1.8x looser" is 1.26x in production | every RadiusI, `beyond_I`, impulse domain; asymmetry statement |
| CHO-07 | medium | softCap = 20 unscanned and coupled to beta; mesh fixed in metres | production pressure radii |
| CHO-08 | medium | K = 3 and ±5 % outside `constants.py`, no rationale; K hard-wired twice; ±5 % never binds | scan; beta -> ∞ property |
| CHO-09 | medium | Grid merge by element-wise max undocumented and mislabelled | ratio maps, MaxR (see cluster B) |
| CHO-10 | medium | Z_urban domain rules are assertions; stale doc; calculator ignores them | ALGORITHM row counts; calculator |
| CHO-11 | medium | Exclusion radius uses corner (det 1) vs face (det 2) | Z_urban rows via condition 3 |
| CHO-12 | medium | Hard-coded copies drifted; several choices set in more than one place | `z_surface_3d`, calculator, docs |
| CHO-13 | medium | `a` CV-selected but described as a geometric constant | RadiusP model description |
| CHO-14 | medium | Safe-domain box drawn from the errors it bounds | safe domain (same as STA-04) |
| CHO-15 | medium | Z_urban forms and bounds cannot be re-validated from the repo | Z_urban LOGO figures |
| CHO-16 | medium | Street-model heritage constants not traceable to a reproducible fit | street model EPK, ENV |
| CHO-17 | low | `random_state = 42`: medians insensitive, `best_*` files not | `best_*` |
| CHO-18 | low | `MAX_HEIGHT = 24` affects nothing used | none |
| CHO-19 | low | 1.01 Pa mask threshold has no rationale and a 1 % margin | solid mask |
| CHO-20 | low | `req` end-sector bias | common mode (same as ALG-05) |
| CHO-21 | low | Stale or incorrect rationale text | comments; `PARAMETER_STUDY_HE` reading of the W variance share |
| CHO-22 | info | Evaluation choices (declared) | none |
| CHO-23 | info | Z_free scan fixed to integers 1-20 | resolution of Λ(Z_free) |
| STA-01 | high | Structure, variants and beta chosen on the same LOGO scores reported as the headline | ALGORITHM Result and Provenance; `logo_summary_*`; thesis ch. 9 validation, ch. 10 |
| STA-02 | high | Z_urban fit and test domain decided with the measured target and R_conv | `cv_summary` z_P/z_I, `final_production_z_urban_*`; ALGORITHM Domain; thesis §4.6, ch. 9 |
| STA-03 | high | Best-split artefacts labelled and consumed as validation | `validation_comparison_*`, `cv_best_*.png`, `best_*`; `formulas_printer`, `check_formulas` |
| STA-04 | high | Safe domain drawn around held-out errors, then shipped as a ±15 % band | ALGORITHM safe domain; calculator; thesis ch. 9-10; aim 5 |
| STA-05 | medium | No uncertainty on coefficients or predictions; several weakly identified | `final_production_*`; thesis ch. 8, appendix A; calculator |
| STA-06 | medium | Hopkinson exponent without interval; det 2 interval excludes 1/3 | ALGORITHM "why the cube root"; thesis ch. 8.1 |
| STA-07 | medium | Docs, calculator and notes quote numbers the WT tables no longer match | ALGORITHM, calculator, beta note, Hebrew docs, `z_surface_3d` |
| STA-08 | medium | Z_urban LOGO figures have no harness in the repo | ALGORITHM Provenance and Limitations; "cross-application costs 3-4 pp" |
| STA-09 | medium | Extrapolation guards incomplete (rho, Z_free) | calculator; `predict_*` API |
| STA-10 | info | Degrees of freedom: 3.6-4.5 families per coefficient | intervals |
| STA-11 | low | `n_iter` gives a prefix of splits, not a new sequence; log prints 77/19 instead of 76/20 | CLAUDE.md wording; log |
| STA-12 | low | Metric definition and aggregation | reporting |
| STA-13 | low | Versions unpinned, split depends on row order, key docs untracked | environment |
| REP-01 | high | Production Z_urban coefficients differ between HEAD and WT; WT values come from uncommitted code | `final_production_z_urban_*_req_soft3`, `best_*`, `cv_summary`, `max_radius_per_Z`; beta-selection material |
| REP-02 | high | HEAD is not self-contained: `paths.default_npz_dir` was never committed | street pinned artefacts; parity report of 06d09ca; HEAD tests fail |
| REP-03 | medium | Anchor and v2/v3 equivalence tests did not run (cloud-only data) | trust in all numbers (CLAUDE.md §5) |
| REP-04 | medium | WT mixes tables from two code states (soft4, p95, soft2 made by HEAD code) | cross-beta comparisons |
| REP-05 | medium | At HEAD, the `req` convergence tables are legacy-model output HEAD's defaults do not reproduce | `*_req` tables at HEAD |
| REP-06 | medium | Hard-coded copies disagree with the tables | calculator, `z_surface_3d` |
| REP-07 | low | Fixtures download placeholders instead of skipping; `raw_npz` not pinned | test hygiene |
| REP-08 | low | pytest missing; no version record; bit-exact only for some tables | environment |
| REP-09 | low | `n_iter` wording | CLAUDE.md, docstring |
| REP-10 | low | `WORKLOG.md`, `TRACEABILITY.md` missing; `CLAUDE.md`, ALGORITHM untracked | provenance |
| REP-11 | info | Line endings (index LF, checkout CRLF) | byte comparisons |
| REP-12 | info | Legacy unsuffixed tables not regenerable by the current CLI | history |

## High findings (copied in full from the lens reports)

### From algorithm.md

### ALG-01  [high]  Multi-grid max-merge runs before the solid-cell mask, so interpolated values inside building walls enter both convergence scans
- Where: `blastlib/processing/grids.py:77-98` (merge), `:109-111` (mask), `:187-215` (band and pinning). Committed, unchanged since HEAD. ALGORITHM.md Step 1 (L75-77) and "Measurement definitions" (L362-395) do not mention the step.
- What: The fine grid is overwritten by the cell-wise maximum with the bilinearly interpolated coarser grid. The threshold mask is then computed on the merged field:
  ```
  peakP1   = np.maximum(peakP1,   peakP2_interp)      # l.84 (same for impulse, refP, refI)
  ...
  mask1 = peakP1 <= threshold_p                       # l.109, on the MERGED field
  ```
  The code comment reads "Fill missing values: fine grid filled from medium grid". Building interiors in the raw store hold a constant floor: peak P <= 1.01 Pa and impulse 0.494 Pa.s. For det2 the "dead" cells coincide exactly with the building footprints (agreement 1.000 for config_93 and config_58). Where the coarse cell straddles a wall, the max-merge gives the first one or two fine cells inside the wall (depth 0.12-0.23 m) an interpolated value. Those cells then pass the mask. The two loads treat them differently:
  - Pressure: `lowP = peakP_raw < 10` pins these cells to ratio 1 (100% of them in config_03). They act as in-band cells that break violation streaks.
  - Impulse: the scaled band tests the raw floor (0.494 Pa.s) against I_ref, so it does not pin them. Their `ratioI_raw` is about 0.04 (median, config_03), which is a guaranteed |ratio-1| > 0.05 violation (99.1% unpinned).
  The merge also raises 1.6-4.8% of live fine cells (median raise 3-26% among the raised cells, configs 93/58/03).
- Evidence: A read-only recomputation of all 96 configurations with the working-tree code reproduced the tables exactly. It was then repeated with only the dead-but-filled cells set to NaN:

  | radius | median change | p10 / p90 | range | configs with change > 10% |
  |---|---|---|---|---|
  | RadiusP, req_soft3 (production) | +5.0% | +1.2 / +23.8 | +0.3 ... +66.0% | 27/96 |
  | RadiusP, hard req | +11.5% | +3.0 / +36.1 | +0.6 ... +91.3% | 53/96 |
  | RadiusI | -35.3% | -56.2 / -3.6 | -65.9 ... +13.7% | 80/96 |

  In-sample MAPE of the production RadiusI form goes from 6.30% to 12.67% without the skin cells; RadiusP goes from 8.04% to 8.70%. MaxR is unaffected (0.0% change at Z = 2..8 in 4 configs), because the outermost exceeding cell lies in the street.
- Consequence: Every `convergence_table_*`, the `beyond_*` flags, the Z_urban fit domain, every convergence coefficient, the LOGO tables and the thesis statements built on them (RadiusI accuracy, the "impulse radius > pressure radius" ordering, the Hopkinson exponent argument in ALG-09). It also bears on the mesh-sensitivity limitation (L487-512), because the skin is one fine cell deep by construction.
- Options: (a) keep the current merge-then-mask order and document it as a convention, with its sensitivity; (b) compute the solid-cell mask on the raw, pre-merge field (or from geometry) so the skin cells stay NaN, and regenerate everything; (c) treat skin cells explicitly, for example with a low-impulse floor analogous to the pressure floor, and report both. Any change moves results of record.

### ALG-02  [high]  ALGORITHM.md / ALGORITHM_HE.md describe a mixture of the committed and the uncommitted state; the working-tree results of record do not match the printed numbers
- Where: ALGORITHM.md L329-360 (coefficients), L216-222 (500-split medians, best split), L258-269 (row counts), L260-264 (domain wording), L454-461 (block-period table); ALGORITHM_HE.md L287-317, L186-193, L224-233. Tables: `outputs/tables/final_production_z_urban_coefficients_req_soft3.csv`, `cv_summary_req_soft3.csv` and `max_radius_per_Z_req_soft3.csv` are modified-uncommitted. `blast_calculator.html` is committed.
- What and evidence:

  | quantity | ALGORITHM.md | HEAD table | working-tree table |
  |---|---|---|---|
  | Pressure det1 C0 / C1 / A / B | 0.0866 / 1.7457 / 2.7434 / 4.0123 | same | 0.0911 / 2.5468 / 2.9191 / 7.1392 |
  | Pressure det2 C0 / C1 / A / B | 0.1294 / 0.5276 / 2.2219 / 1.1818 | same | 0.1128 / 0.4320 / 2.1697 / 0.9433 |
  | Impulse det1 C0 / C1 / C2 / C3 | -0.0941 / 2.9631 / 0.8344 / 1.6752 | same | -0.1079 / 3.0884 / 0.8573 / 1.5496 |
  | Impulse det2 C0 / C1 / C2 / C3 | -0.0063 / 2.6650 / 1.0991 / 0.7526 | same | +0.0068 / 2.6644 / 1.0985 / 0.7614 |
  | 500-split median z_P / z_I | 8.5% / 9.5% | 8.495 / 9.491 | 8.417 / 9.404 |
  | best-split worst MAPE vs median | 7.42% vs 9.86% | 7.421 / 9.860 | 7.203 / 9.852 |
  | P rows at Z_free = 2..8, 9, 10 | 95,96,96,96,94,90,64, 14, 2 | HEAD table + HEAD mask: identical | WT table + WT mask: 75,87,90,96,94,86,58, 4, 1 |
  | block-period table rows | 198/107/108/137/114/36 | HEAD: 198/109/111/137/116/37 | WT: 198/107/108/137/114/36 |

  The domain paragraph (L261-264) describes the exclusion-radius row condition, which exists only in the uncommitted `z_urban_valid_mask`. The row counts quoted beside it were produced without that condition. The document was last modified after the working-tree tables were written (2026-08-04 07:49 vs 2026-08-03 18:54), but only some of its numbers were updated. `blast_calculator.html` hard-codes the HEAD Z_urban coefficients (0.086646, 1.745664, 4.012298, -0.094070). The English and Hebrew documents agree with each other number for number, so both are stale in the same way.
- Consequence: Any thesis sentence or table quoting the Z_urban coefficients, the Z_urban CV medians, the best-split figure or the Z_free row counts. It also breaks the CLAUDE.md §3 rule that results of record regenerate from the code at the same commit: the working-tree tables come from uncommitted code, and the HEAD tables cannot be regenerated from the working tree.
- Options: (a) declare HEAD (code + tables + doc + calculator) the state of record and set the working-tree changes aside as a proposal; (b) adopt the working-tree state, commit code and tables together, and update the doc, the calculator and any thesis text from the new tables; (c) keep both, with suffixed filenames and a doc section per state.

### ALG-03  [high]  "Comparable by construction" does not hold; the gap is absorbed by an undocumented, outcome-dependent row filter
- Where: ALGORITHM.md L124-125, L189-191, L391-394 (EN); HE L107-108, L165-166, L342-344. Code: `convergence.py:24-62` and `:65-117` (R_conv per sector), `free_field.py:108-203` (MaxR per sector), `run_analysis.py:339-340` (`beyond_*`), `z_urban.py:256-260` (condition 1). The convergence code is committed; `free_field.py`, `run_analysis.py` and `z_urban.py` are modified-uncommitted.
- What: The document says "One equivalent-area estimator sets both radii ... so R_conv and Z_urban cannot drift apart by construction" and "the Z_urban <= Z_conv clip is meaningful only because of this". Only the final collapse is shared. The per-sector measurements differ:

  | | R_conv sector | MaxR sector |
  |---|---|---|
  | quantity scanned | ratio (P or I) | P or I |
  | band | ±5% after the 10 kPa band / scaled I band | none |
  | streak rule | K=3 consecutive cells | outermost single cell |
  | first-street exclusion | cells dropped | none |
  | soft weighting | used for P under `req_soft3` | not used (MaxR is identical under `req` and `req_soft3`) |

  The code's own docstring says the opposite of the document (`z_urban.py:558-564`): "The two radii are measured with different tolerance conventions ... so MaxR overshoots R_conv systematically rather than occasionally".
- Evidence (working-tree `req_soft3` tables): among rows meeting conditions 2-4 (R_free < R_conv, R_free > exclude_r, Z_free >= 2), condition 1 (`MaxR >= R_conv`) drops:
  - Pressure: 92 of 683 rows (13.5%, 52 configs). The dropped rows have median Lambda 1.21, against 1.01 for the kept rows.
  - Impulse: 280 of 980 rows (28.6%, 82 configs). The dropped rows have median Lambda 1.52, against 1.26 for the kept rows.
  The filter selects on the outcome and removes the most amplified rows.
- Consequence: Both Z_urban fits and their CV errors, and the "why the algorithm is sound" argument in the thesis. The fitted Lambda is conditioned on "MaxR < R_conv", which the document does not state.
- Options: (a) restate the claim: the collapse is shared, the criteria are not, and rows beyond R_conv are removed, reporting the shares; (b) make the MaxR sector measurement use the same exclusion and streak rules as R_conv, so that the claim becomes true, and re-measure; (c) keep the rows and model the truncation, for example by fitting with the clip applied, and report the effect on the coefficients.

### From physics.md

### PHY-01  [high]  Building-rim cells survive the mask and drive both convergence radii

- Where: `blastlib/processing/grids.py:77-99` (fill), `:108-124` (mask), `:187-215`
  (criteria). Committed at HEAD, unmodified. Production reaches it through
  `blastlib/io/raw_store.py:169-187`, which is untracked. `constants.PARAMS['thresholdP_kPa']`
  is at `blastlib/constants.py:22`.
- What: the mask that removes building footprints is computed on the filled
  field:

  ```
  peakP1   = np.maximum(peakP1,   peakP2_interp)      # grids.py:84
  ...
  mask1 = peakP1 <= threshold_p                          # grids.py:109
  ```

  The solver writes 0.001 kPa (1 Pa) peak overpressure and about 0.49 Pa.s
  impulse into every in-footprint cell. `thresholdP_kPa = 1.01/1000` kPa is a
  detector for that value. The "mask threshold [kPa]" comment and the outline's
  "removes numerical background" (`THESIS_RESULTS_OUTLINE_HE.md:22`) do not say
  this. Next to a wall, the bilinear interpolation of the medium grid mixes in
  street cells, so the max-filled value exceeds 1.01 Pa and the footprint cell
  is not masked. It then enters the scan with inconsistent operands:
  - Impulse: the criterion uses the raw operands
    (`impulse_converged(data['impulse1'], data['refI1'], ...)`, `grids.py:206`).
    The raw urban value there is 0.49 Pa.s, so |dI|/W^(1/3) >= 20 wherever the
    free-field scaled impulse exceeds 20, i.e. inside Z ~ 13.7. The cell is not
    pinned. Its stored ratio (filled urban / filled reference) is about 0.05-0.46,
    so the scanner counts it as a violation. Since 2026-07-27 (b11863d) the impulse
    rule deliberately has no pressure term, and that term was what used to pin
    these cells.
  - Pressure: raw P = 0.001 kPa < 10 kPa, so the floor pins the ratio to 1 and the
    cell counts as converged inside the building. There it can reset a genuine
    violation streak formed by the street cells in front of the wall. Under the
    soft path the gate (`P_raw >= 10`) sets w = 0, with the same effect.
- Evidence:
  - Rim size. In-footprint fine-grid cells that are valid after the mask:
    16,228 of 250,000 (6.5%) in configs 01/02/03 (b15 s5), and 10,853 (3.3%) in
    config 20 (b30 s5). Of these, unpinned impulse violations number 3,372
    (config 01, W=50), 13,479 (02, W=500), 9,389 (20, W=500) and 16,090
    (03, W=1500). Pressure violations among them: 0.
  - Streak composition, config 02 (W=500, b15 s5 h4). The outermost 3-cell
    violation streak that sets the sector radius lies at 96.7 / 107.4 / 106.9 /
    84.1 m for theta = 10/30/60/80 deg. Every cell in it is an in-building cell:
    raw I = 0.49 Pa.s, I_ref = 161-205 Pa.s, ratio 0.05-0.46. With those cells
    masked, the outermost genuine streaks lie at 15.0 / 45.4 / 49.1 / 22.8 m,
    with ratios 1.58-2.30 and |dI|/W^(1/3) of about 27.
  - Counterfactual: mask every cell whose raw solver peak overpressure is <=
    `thresholdP_kPa`, on each grid, before the scan. Nothing else changes.

    | quantity (96 configs) | current | rim masked |
    |---|---|---|
    | RadiusI change | - | median -35.3%, IQR -49.6..-18.0%, range -65.9..+13.7%; 80/96 beyond +/-10% |
    | RadiusI change by W (median) | - | 50: -20.5%, 250: -46.7%, 500: -35.3%, 1000: -44.5%, 1500: -39.6% |
    | median Z_conv,I | 11.61 | 7.58 |
    | configs with Z_conv,I > 13.8 | 17 | 7 |
    | RadiusP hard change | - | median +11.5%, max +91.3%, 76/96 > 5% (W=50 median +35.2%) |
    | RadiusP soft beta=3 (production) | - | median +5.0%, max +66.0%, 48/96 > 5% (W=50 median +19.8%) |
    | median Z_conv,P hard / soft | 7.54 / 8.99 | 8.58 / 9.88 |

  - HC ratios over the core families (b15/b30 at W = 50/500/1500, median over
    the 24 paired geometries):
    - hard RadiusP: Z500/Z50 goes from 1.200 to 0.989;
    - soft RadiusP: Z500/Z50 goes from 1.213 to 1.045;
    - RadiusI: Z500/Z50 goes from 0.986 to 0.760, and Z1500/Z500 from 0.971 to
      0.864.
  - Symptom in the table of record: `ImpulseAtR` is below 20% of the free-field
    impulse at Z_conv,I in 25 of 96 configurations, e.g. 0.60 Pa.s for config 40
    at 60.5 m, W=50.
- Consequence:
  - All RadiusI and RadiusP values in `convergence_table_req*.csv`, and everything
    fitted or selected from them:
    - `final_production_convergence_coefficients_*`;
    - the `beyond_P/I` flags and the `R_free < R_conv` condition of
      `z_urban_valid_mask`, which define the Z_urban fit rows;
    - the Z_conv clip on Z_urban;
    - the LOGO and CV summaries, `safe_domain_req_soft3.csv`, and the ALGORITHM
      coefficient tables.
  - Thesis-level claims that change:
    - "impulse holds 1.5x further, Z 11.6 vs 7.5" (`PHYSICS_ANALYSIS_HE.md:64,71,611`;
      outline §3.4). With the rim masked the order reverses: 7.6 vs 8.6 (hard)
      or 9.9 (soft).
    - "channelling short-range, reverberation through the fabric Z 12-16"
      (`PHYSICS_ANALYSIS_HE.md:89-90`). The through-fabric sectors are the ones
      that cross building walls.
    - "pressure ignition 50->500 kg +20%, impulse clean Hopkinson"
      (`PHYSICS_ANALYSIS_HE.md:257-261,638`).
  - The `thr_I_scaled = 20` calibration is also affected. Its rationale is "100%
    convergence" and "thr ~ 7 only 50-86% converge"
    (`constants.py:44-46`, outline §3.2.2). Phantom rim violations extend to
    wherever I_ff/W^(1/3) exceeds the threshold, so the calibration was plausibly
    shaped by this artefact. That is an inference; it was not tested.
- Options:
  - (a) Build the footprint mask from the raw solver sentinel on each grid, before
    the fill, as in the counterfactual. Then re-run Phase 1 and Phase 2 and
    report old and new values.
  - (b) Keep the fill order, but add a validity gate that pins or drops any cell
    whose raw urban field is the sentinel. This is a data-validity condition, not
    the old pressure gate.
  - (c) Keep the current measurement and state in the thesis that R_conv,I is
    essentially "the outermost building wall inside the I_ff/W^(1/3) = 20
    contour", with the numbers above.

### PHY-02  [high]  The soft pressure scan has a W-dependent bias because the mesh is fixed in metres

- Where: `blastlib/processing/convergence.py:65-117` (committed);
  `constants.RADIUS_ESTIMATOR = 'req_soft3'` (`constants.py:69-72`, committed);
  `docs/ALGORITHM.md:487-512` (untracked).
- What: ALGORITHM states that the soft scanner's radius depends on cell count:
  "the number of independent draws grows with the number of cells". It then
  concludes: "the radii are only comparable across configurations because all 96
  were computed on the same mesh — the bias is largely common-mode here"
  (`ALGORITHM.md:510-512`). The mesh is the same in metres (0.15 / 0.5 / 1.0 m for
  every W, from the `spacing{g}` values in `raw_npz`). It is not the same in
  scaled units, and the model is fitted in Z. The number of cells per unit Z
  along a ray is W^(1/3)/dx:
  - fine grid: 24.6 / 42.0 / 52.9 / 66.7 / 76.3 for W = 50 / 250 / 500 / 1000 / 1500;
  - medium grid: 7.4 / 12.6 / 15.9 / 20.0 / 22.9.
  So the bias is W-dependent by construction. Unlike the thresholds, it is not
  Hopkinson-scaled.
- Evidence:
  - The owner's own coarsening measurement gives soft beta=3 RadiusP -9.1% at 2x
    coarser (`ALGORITHM.md:499-502`), an elasticity of about 0.13 per ln(cells).
    The cells-per-Z ratio between W=500 and W=50 on the fine grid is 2.15, which
    predicts about 10% less soft inflation at W=50.
  - Observed soft/hard RadiusP inflation (`convergence_table_req_soft3` over
    `_req`), median by W: 12.1% (50), 22.4% (250), 20.3% (500), 15.8% (1000),
    17.0% (1500). W=500 minus W=50 is 8.2 pp, the same order as predicted.
  - W=1000/1500 have part of their radius on the 0.5 m grid (see PHY-03), which
    is consistent with their lower inflation.
  - In the core families, soft changes Z1500/Z500 from 1.02 (hard) to 0.958, and
    the share of geometries with Z1500 < Z500 from 46% to 71%.
  - The pattern is confounded with physics. There is no controlled test that
    holds the field fixed and varies only the cells per Z.
- Consequence: production RadiusP (`req_soft3`) and its coefficients. Pi_2 =
  s/W^(1/3) is the only regressor that carries W, so a W-dependent measurement
  bias is absorbed into the C1 and C2 Pi_2 terms. It is then read as street-width
  physics. The beta selection gap rule was tested on one pair only: configs 93
  and 95, both W=250.
- Options:
  - (a) Keep beta=3 and state the W-dependent bias, with these numbers, as a
    limitation of the scaled radii.
  - (b) Make the scan step a fixed scaled length, i.e. cells per unit Z held
    constant. ALGORITHM describes a length-based prototype that restored mesh
    invariance.
  - (c) Run a controlled test: resample one W=500 field to W=50's cells per Z and
    measure the soft radius change, then decide.

### PHY-03  [high]  The 100 m fine/medium grid seam cuts the pressure radii of large charges only

- Where: the grid geometry in `data/raw_npz` (fine grid 0-100 m at 0.15 m,
  medium 0-250 m at 0.5 m); `docs/ALGORITHM.md:43-53` (untracked);
  `blastlib/processing/grids.py:177-181` comment (committed);
  `PHYSICS_ANALYSIS_HE.md` §5 and §5b.
- What: the seam sits at a fixed r = 100 m, i.e. at Z = 100/W^(1/3) = 27.1 /
  15.9 / 12.6 / 10.0 / 8.7 for W = 50 ... 1500. Peak overpressure is
  resolution-sensitive and impulse is not. So the absolute 10 kPa band is applied
  to a field whose fidelity, at fixed Z, depends on W. ALGORITHM describes the
  free-field trend as rising "monotonically at every Z <= 12", and the grids.py
  comment says "a function of scaled distance alone". Neither holds.
- Evidence:
  - Same points recorded on both grids (reference field, 30-60 deg sector).
    Peak P on the medium grid is below the fine grid by:
    - 7.4% (W=1500, r=102 m); 9.8% (W=1500, r=110);
    - 12% (W=500, r=110); 10.8% (W=1000, r=110); 16% (W=50, r=110).
    Impulse at the same points agrees to within 0.6%.
  - The CSV kinks exactly at r of about 100 m. Compared with W=50 over the same Z
    step:
    - W=500, Z 12 -> 13: -20.1% vs -11.0%;
    - W=1000, Z 9 -> 10: -20.7% vs -14.8%;
    - W=1500, Z 8 -> 9: -24.4% vs -16.7%;
    - W=250, Z 15 -> 16: -15.7% vs -8.7%.
  - Monotonicity fails in the CSV at Z = 5, 6, 9, 10, 11, 12. It also fails in the
    per-direction median of the reference field at Z = 10-12, e.g. Z=11:
    10.86 / 11.64 / 11.87 / 10.66 / 10.66 kPa.
  - Share of production RadiusP sector radii that lie beyond the fine-grid box:
    0 / 0 / 2.6 / 7.5 / 28.9% for W = 50 / 250 / 500 / 1000 / 1500 (hard `req`:
    0 / 0 / 1.4 / 3.2 / 14.1%).
  - Size of the effect, estimated from the documented elasticity d log R / d log
    p_thr of about -0.6: roughly -6% on the affected sectors, or about -2% on Req
    at W=1500. This is an estimate, not a measurement.
- Consequence: RadiusP for W >= 1000. The claims "Z not monotone in W 17/36
  (pressure)" and "saturation 1.02 at 1500 kg" (`PHYSICS_ANALYSIS_HE.md:251,257-261,640`)
  are effects of 2-4%, the same order as this bias. The ALGORITHM sentence at
  `:47-49` is false as written. The seam is acknowledged only in
  `blastlib/street/strip.py:32`, as "grid-seam corruption past Z = 100/W^(1/3)",
  and not for R_conv.
- Options:
  - (a) Document the seam and restrict W-trend claims to Z < 100/W^(1/3).
  - (b) Quantify it with a direct test: coarsen fine-grid fields of W=500 to
    0.5 m and re-measure RadiusP.
  - (c) Keep the results and reword the ALGORITHM claim to what the data show:
    monotone up to Z = 9 in the field median, and only along the diagonal up to 12.

### PHY-04  [high]  The per-direction MaxR_I level reads a fine-grid reference that is deficient near the grid edge (uncommitted)

- Where: `run_analysis.py:286-314` and `blastlib/processing/free_field.py:73-105`
  (both **modified, uncommitted**; HEAD used the scalar CSV level);
  `grids.py:166-171` stores `refP{g}/refI{g}` raw, pre-fill (committed). The
  output is `outputs/tables/max_radius_per_Z_req_soft3.csv` (modified,
  uncommitted).
- What: the urban exceedance field is max-filled across grids
  (`impulse{g}_orig`), but the level it is compared with is the ring median of
  the raw reference. Near the edges of the fine box, the raw fine-grid reference
  impulse is low:
  - at the edge itself: an outer-boundary effect;
  - in the corner at W=1500: time truncation as well. The reference fine stage was
    dumped at t = 0.319 s against 0.495 s for the urban run.

  `strip.py:34-36` states that the raw/filled asymmetry "is a no-op only within
  grid 1". Near the edges of grid 1 it is not.
- Evidence:
  - Fine/medium reference impulse ratio on the diagonal at r = 130 / 135 / 140 m:
    - W=1500: 0.861 / 0.604 / 0.156;
    - W=1000: 0.951 / 0.930 / 0.918;
    - W=500: 0.963 / 0.949 / 0.938.
  - Config 03, Z_free = 9, theta = 20 deg (3 m from the x = 100 m edge): level
    302.7 Pa.s against 347.4 Pa.s from the grid-filled reference.
  - Config 03, Z_free = 12, theta = 45 deg: level 110.9 against 262.1 Pa.s. The
    sector MaxR is 464.6 m against 174.3 m, and Req 201.8 m against 175.6 m.
  - Counterfactual: take the level from the reference filled exactly as the
    ratios are (`max(refI1, interp(refI2))`), over all 1,440 rows with W >= 250.
    - Pressure: no change; all 481 valid rows are identical.
    - Impulse: valid rows go from 538 to 547 (9 rows now flagged beyond R_conv
      would enter). Among rows valid in both runs, 17 change by more than 1% and
      6 by more than 5%, the largest by -7.4% (config 30, Z=9: 109.1 -> 101.0 m;
      config 78, Z=10: 107.8 -> 99.9 m). All affected rows are W = 1000/1500 at
      Z_free = 9-12.
  - Secondary effect: the impulse criterion itself compares raw urban with raw
    reference over different stage windows. Replacing the fine-grid reference
    moves RadiusI (W=1500) by only -0.67% to +0.61%.
- Consequence: the MaxR_I rows and beyond_I flags of the result of record, and
  therefore the canyon_trap fit rows. The effect is limited to large charges, so
  it is a W-dependent (non-HC) bias.
- Options:
  - (a) Build the level from the grid-filled reference, like-for-like with
    `impulse{g}_orig`.
  - (b) Exclude cells within some margin of each grid's outer boundary from both
    the ring median and the exceedance search.
  - (c) Revert to the committed scalar-CSV level for impulse, which is
    isotropic-biased but free of edges, and document the trade.

### From choices.md

### CHO-01  [high]  beta = 3 was not selected by a rule fixed in advance, as the record states

- **Where:**
  - `blastlib/constants.py:58-63` [clean]
  - `outputs/check_results/soft_beta_selection_note.md:6-12` [clean]
  - `docs/ALGORITHM.md:112-116, 407-413` [U]
  - `tools/soft_beta_scan/soft_beta_scan.py:15-20, 47-50, 170-177` [clean]
  - commits b88ef6e (2026-08-03 00:34), cbb2312 (00:37), 430d004 (13:31)
- **What the record claims:**
  - Note: "β = 3 is the only tested sharpness that satisfies **both** rules fixed before the numbers were seen."
  - ALGORITHM.md: "the only value satisfying both rules fixed in advance".
- **What the rule actually was, as coded:**
  - Scan tool docstring: "Selection rule (Task C4): the LARGEST beta with gap < 10 m. Betas: required set {4, 6, 8, 12} plus supplementary diagnostics {2, 3}."
  - Selection code: `passing = [r['beta'] for r in report_rows if r['required_set'] and r['gap_pass']]`.
- **What the history shows:**
  - b88ef6e: "No required beta meets gap<10m … Stopped per plan; user decision on record: adopt beta*=4 with the gap rule relaxed".
  - The note as committed in cbb2312: "The pre-registered rule — largest β ∈ {4, 6, 8, 12} … — selects nothing … the ring-p95 prototype the 10 m orientation was calibrated on … β\*=4 was preferred over β=3 because it delivers … at half the inflation cost".
  - 430d004, 13 h later: adopts beta = 3 and rewrites the note.
- **Evidence:**
  - `soft_beta_selection.csv` has `required_set = False` for beta = 2 and 3.
  - All six betas' gap, inflation and LOGO numbers are in b88ef6e, before either adoption.
  - The `logo_cv_req_soft2/3_relwls_quad.csv` files are dated 2026-08-03 11:14 and 11:37: after the beta = 4 adoption, before the beta = 3 adoption.
  - I regenerated the scan quantities from `convergence_table_req_soft{β}.csv`. Gap config_93/95: 6.25 / 8.61 / 13.11 / 21.40 / 25.29 / 26.67 m for β = 2/3/4/6/8/12; hard 24.18 m. Median inflation: 24.43 / 17.29 / 12.72 / 6.49 / 3.98 / 2.03 %. All match the note.
- **Further weaknesses of the rationale itself:**
  - (i) The gap rule rests on one pair of configurations: config_93 and config_95, which differ only in H (15 vs 24 m). Hard radii are 62.3 vs 38.2 m. That their radii "should" be within 10 m is an assertion.
  - (ii) Per the cbb2312 note, the 10 m limit was calibrated on a different scanner, the ring-p95 prototype.
  - (iii) The acceptance rule (C5: mean LOGO error at most 0.5 pp worse) compares the error of predicting two *different* targets, soft radii against hard radii. It measures how predictable a definition is, not model accuracy.
  - (iv) β = 3 vs 4 accuracy is "within noise" by the note's own words (mean 8.43 vs 8.21, max 30.1 vs 31.6).
  - (v) ALGORITHM.md:505-509: "part of the documented +17.3% median inflation from softening is cell count rather than physics, so the β selection scan conflates softening with mesh sensitivity" (see CHO-07).
- **Consequence:** every production pressure radius depends on this choice. That covers `convergence_table_req_soft3.csv` (median +17.3 % vs hard), `beyond_P`, the Z_urban pressure fit domain, all `final_production_*_req_soft3.csv`, and the LOGO headline (P max 30.1 %). It also affects any thesis sentence saying beta was pre-registered.
- **Options:**
  - (a) Keep beta = 3 but state the actual order of events: the rule selected nothing, beta = 4 was adopted with the rule relaxed, then beta = 3 was taken from the supplementary set after all numbers were known. Report hard / beta 3 / beta 4 side by side as the sensitivity.
  - (b) Register a new rule now (several cliff pairs, a mesh-invariant soft scan, softCap included) and re-run.
  - (c) Return to beta = 4, the value consistent with the recorded decision, stating the relaxed rule.

### CHO-02  [high]  The 10 kPa pressure band: an unsourced value that controls every pressure radius, with no sensitivity on record

- **Where:**
  - `blastlib/constants.py:23`: `'minPressure_kPa': 10, # convergence threshold [kPa]`, with no rationale [clean]
  - `blastlib/processing/grids.py:177-197` [clean]
  - `docs/ALGORITHM.md:81-82, 192-194, 312-318` [U]
  - `docs/THESIS_RESULTS_OUTLINE_HE.md:71-73` [U]
  - The value is inherited from compare_v6 (first appears in 2ed1dfe).
- **What:** the stated rationales are:
  - "a 10 kPa band (below which load differences are structurally negligible)";
  - "The pressure tolerance sits at the load level below which structures are unaffected";
  - "engineering relevance of blast loads ends near Z ≈ 16 and the 10 kPa contour sits near Z ≈ 12".

  No source is cited anywhere in the repo, and no registered standard exists to check against. From general knowledge, not verified against a registered source here, commonly used damage tables place glazing failure and minor structural damage below 10 kPa. The owner should source this, especially since proposal aim 4 asks for safety distances at several damage levels.
- **Evidence:**
  - As a relative tolerance, 10 / P_ff (P_ff from `data/free_field_data.csv`, mean over W) is: Z = 1: 1 %, Z = 3: 10 %, 5: 25 %, 8: 54 %, 10: 79 %, 12: 105 %, 15: 151 %, 20: 237 %.
  - At the measured production radius (`req_soft3`) the band is a median 67.3 % of P_ff (p10 47.9 %, p90 87.4 %). On the hard `req` table it is 47.9 %.
  - Beyond Z ≈ 12 no shielding can register. Only an excess above +10 kPa, more than 100 % of P_ff, counts as a violation.
  - The ±5 % ratio tolerance never binds wherever P_ref < 200 kPa (Z ≳ 2); see CHO-08.
  - Sensitivity:
    - ALGORITHM.md:315-316 quotes an elasticity d log R / d log p_thr ≈ −0.6.
    - Commit b11863d mentions a sweep of minPressure over {2, 5, 10, 20, 40}.
    - Neither has a script or table in `tools/` or `outputs/check_results/`.
  - The admissibility argument is `grids.py:179`: "cross-weight spread 4.7%". It reproduces as a mean CV of 4.77 % over Z in the CSV.
  - The figures in ALGORITHM.md:44-51 do not match the CSV:
    - The CSV gives 55.3 → 62.3 kPa at Z = 4, where ALGORITHM.md gives "57.4 → 63.7".
    - The CSV is non-monotone in W at Z = 5, 6, 9, 10, 11, 12, where ALGORITHM.md says "monotonically at every Z ≤ 12".
    - ALGORITHM.md gives a CV of "≈ 4.3%".

    These figures probably come from the reference VTK field, but the source is not stated. Forward to the physics lens.
- **Consequence:** the choice feeds, directly:
  - every `RadiusP`, `PressureAtR` and `beyond_P`;
  - the Z_conv clip;
  - all RadiusP coefficients, which ALGORITHM.md:312-315 correctly says are "radii *of the 10 kPa criterion*".
- **Options:**
  - (a) Cite a damage-level source for 10 kPa in `constants.py` and the docs.
  - (b) Commit the threshold sweep (script and table) behind the −0.6 elasticity, so the sensitivity is reproducible.
  - (c) Present R_conv as a function of p_thr for two or three damage levels, which serves aim 4 directly.

### CHO-03  [high]  The low-pressure floor is on the urban pressure in code but on the free-field pressure in the thesis outline; the two give very different radii

- **Where:**
  - `blastlib/processing/grids.py:73, 187-189`: `peakP1_raw = data['peakP1'].copy()` (urban), then `lowP1 = peakP1_raw < min_pressure` [clean]
  - `blastlib/processing/soft_criterion.py:124-125`: `(p_raw >= min_pressure_kPa)` [M, I/O-only changes]
  - `docs/THESIS_RESULTS_OUTLINE_HE.md:70`: "`|P_urban − P_ff| < 10 kPa` **או** `P_ff < 10 kPa` (רצפת רלוונטיות)" [U]
  - `docs/ALGORITHM.md:98, 372`: "P < 10 kPa", which is ambiguous [U]
- **Evidence:** read-only probe on 16 configurations (every 6th raw file, hard criterion, `find_convergence_radius` unchanged).
  - The code's urban floor reproduces `convergence_table_req.csv` `RadiusP` exactly for all 16.
  - Re-pinning with the outline's floor (`refP < 10`) changes the radius by +13 % to +94 %, median +58.5 %. Examples: config_07 22.54 → 43.62 m, config_43 22.15 → 41.70 m, config_61 21.79 → 40.81 m.
  - The mechanism: the urban floor marks shielded cells as converged (urban < 10 kPa behind a building while P_ff ≥ 20 kPa). Under the urban floor, shielding below 10 kPa is invisible to R_conv,P.
- **Consequence:** a chapter written from the outline would describe a criterion that does not produce the tables of record. Separately, "shielding below 10 kPa counts as converged" is a substantive choice that no document states.
- **Options:**
  - (a) Correct the outline and chapter to the urban floor, and state the shielding consequence.
  - (b) Adopt the free-field floor. This would move every pressure radius substantially and needs a full re-run.
  - (c) Report both definitions.

### CHO-04  [high]  Uncommitted changes to the MaxR definition and the Z_urban domain have rewritten results of record; docs and the calculator still carry the HEAD coefficients

- **Where:**
  - Code:
    - `run_analysis.py:286-326` (per-direction exceedance level) [M]
    - `blastlib/processing/free_field.py:73-105` (`reference_level_per_theta`, `tol=0.6`, `max_tol=4.0`) [M]
    - `blastlib/regression/z_urban.py:216-271` (new conditions 2 and 3) [M]
    - `blastlib/regression/z_urban.py:409-420` (B upper bound 8 → 20) [M]
  - Tables, all mtime 2026-08-03 18:54: `outputs/tables/max_radius_per_Z_req_soft3.csv`, `final_production_z_urban_coefficients_req_soft3.csv`, `best_z_urban_coefficients_req_soft3.csv`, `cv_summary_req_soft3.csv` [M]
  - Stale copies: `docs/ALGORITHM.md:346-353` [U] and `blast_calculator.html:248-252` [clean]
  - Tests: `tests/test_maxr_consistency.py`, `tests/test_z_urban_domain.py` [U]
  - No note in `outputs/check_results/` records the change.
- **What:** CLAUDE.md §1.3 says "Results of record never change silently." The working-tree production Z_urban file differs from HEAD:

  | coefficient | HEAD | working tree |
  |---|---|---|
  | det 1 pressure C1 | 1.7457 | 2.5468 |
  | det 1 pressure A | 2.7434 | 2.9191 |
  | det 1 pressure B | 4.0123 | 7.1392 |
  | det 2 pressure B | 1.1818 | 0.9433 |
  | det 1 impulse C0 | −0.0941 | −0.1079 |
  | det 1 impulse C3 | 1.6752 | 1.5496 |

  ALGORITHM.md ("Production values") and the calculator quote the HEAD values.
- **Evidence:**
  - **Row-level change:**
    - MaxR_P changed in 1915 of 1920 rows (median −2.05 %, p5 −7.75 %).
    - MaxR_I changed in 1911 of 1920 rows (median +0.1 %). There is a +336 % jump in six Z = 1 rows, which are outside the fit domain.
    - Inside the fit domain: P median −0.6 % (max |16.4 %|), I +0.3 % (max 12.5 %).
    - `beyond_P` went from 1181 to 1170 rows; `beyond_I` from 1073 to 1080.
  - **Attribution:** I refitted `range_switch` with the module's own fitter, crossing the HEAD and working-tree tables with the HEAD mask (conditions 1 + 4) and the working-tree mask.

    | table | mask | det 1 n | det 1 B | det 1 C1 |
    |---|---|---|---|---|
    | HEAD | HEAD | 328 | 4.012 | 1.746 |
    | HEAD | working tree | 279 | 6.786 | 2.448 |
    | working tree | HEAD | 335 | 3.287 | 1.560 |
    | working tree | working tree | 280 | 7.139 | 2.547 |

    - HEAD table with HEAD mask reproduces the HEAD production values exactly.
    - Working-tree table with working-tree mask reproduces the working-tree production values.
    - The B bound of 8 vs 20 makes no difference for `req_soft3`: the optimum is interior at 7.14. It matters only for `req`, where the working-tree B is 8.33.
  - **Predictions barely move:** on the working-tree domain rows, det 1 median −0.62 % (max |4.2 %|) and det 2 −0.85 % (max |2.4 %|), even though C1 and B move by 40-78 %. So C1 and B for det 1 are weakly identified. ALGORITHM.md:242 ("every coefficient has a physical reading") and the reading of B as "open-canyon damping" are not supported by this.
  - **The new level carries its own undocumented choices:**
    - A ring median of reference cells with |r − R_free| < 0.6 m.
    - The ring doubles up to `max_tol = 4.0`, but the loop runs 0.6 → 1.2 → 2.4 → 4.8 and exits, so the effective maximum half-width is 2.4 m.
    - Reference cells are pooled from all three grids without the smart cut (`grids.py:170` stores the raw `refP{g}`), while the urban values compared against the level are max-merged and cut (CHO-09).
    - Sectors that stay empty fall back to the CSV scalar. The run prints this share but does not store it. On 12 configurations I measured 0.03 %.
  - **Anisotropy rationale:** the 9.6 % anisotropy is confirmed for the pressure reference (median diagonal/axis +9.7 %, 12 configurations). The impulse reference shows none (median 0.0 %). Yet the change is applied to impulse too and moves MaxR_I by up to 12.5 % inside the domain. The exceedance radius is knife-edge sensitive to sub-percent changes in the level.
- **Consequence:**
  - `final_production_z_urban_coefficients_req_soft3.csv` differs between HEAD and the working tree, and the docs and calculator deploy the HEAD set.
  - The CV medians for z_P and z_I change (cv_summary [M]).
  - The ALGORITHM.md row counts are stale (CHO-10).
- **Options:**
  - (a) Adopt: commit with a check_results note giving old and new values and the attribution above, then update ALGORITHM.md, ALGORITHM_HE.md and the calculator.
  - (b) Restore the HEAD tables until the owner has reviewed the change.
  - (c) Give the new MaxR definition its own filename token, so the two definitions are never compared as one run.

### CHO-05  [high]  The `req` collapse is presented as "the distance beyond which the urban field is indistinguishable from free field"; about half of all directions exceed it

- **Where:**
  - `blastlib/constants.py:53-72` [clean]
  - `blastlib/processing/radius_estimator.py:114-140` [clean]
  - `docs/ALGORITHM.md:8-9` ("the distance beyond which the urban blast field is indistinguishable from the free field") and `:85-87, 189-191` [U]
  - `docs/THESIS_RESULTS_OUTLINE_HE.md:62-64` (the distance from which standard free-field curves may be used) [U]
  - `CLAUDE.md` §0
- **What:** the scalar is an area-equivalent mean of 91 sector radii, sqrt(4A/π). The stated rationale for `req` is that one estimator must drive both radii, which is sound. That argument supports using *one* estimator. It does not support *this* one. "Stable because it integrates" is a robustness argument, not a conservatism argument.
- **Evidence** (`theta_radius_{P,I}_req_soft3.csv`, which matches the table `Req` to 3e-14):
  - Share of the 91 sectors whose own convergence radius exceeds Req: median 45.1 % (P) / 50.5 % (I); maximum 62.6 % / 68.1 %.
  - Largest sector / Req: median 1.40 (P) / 1.33 (I); p90 1.84 / 1.59; maximum 2.53 / 1.95.
  - p95 / Req: median 1.30 / 1.27.
  - **No like-for-like estimator comparison exists.** `validation_comparison_p95.csv` and the p95 Phase-2 outputs [U] were fitted on `convergence_table_p95.csv` and `max_radius_per_Z_p95.csv`, dated 2026-07-26 (commit 2582ca4). Their per-theta impulse radii differ from the `req` tables in 8548 of 8736 cells (up to 127.7 m) while the pressure per-theta radii are identical. They were produced under an older impulse criterion. No LOGO result exists for `p95` or `max`.
- **Consequence:** this matters wherever R_conv or MaxR is read as a safety distance (proposal aim 4). It also affects the physical reading of the Z_conv clip.
- **Options:**
  - (a) Keep `req` but define it in the text as the equivalent-area radius of the non-converged region, and report the sector spread (for example the max/Req distribution above).
  - (b) Recompute `p95` or `max` under the current criteria as a conservative companion.
  - (c) Move to directional output, which ALGORITHM.md already names as the natural extension.

### CHO-06  [high]  `thr_I_scaled = 20` is calibrated to make every configuration converge, and the stated "1.8x looser" asymmetry is stale under production

- **Where:**
  - `blastlib/constants.py:44-51` [clean]
  - `blastlib/processing/ff_reference.py:88-100` [clean]
  - commit b11863d
  - `docs/ALGORITHM.md:83-84, 584-588` [U]
  - `docs/THESIS_RESULTS_OUTLINE_HE.md:79-82` [U]
- **What:**
  - constants.py: "thr_I_scaled = 20 is a calibration, not a measured boundary: it is the loosest-but-lowest value giving 100% convergence with no reliance on extrapolated free-field data … ~83% relative band … against ~47% for the pressure rule at ITS radius — the impulse test remains ~1.8x looser."
  - The commit says "the lowest value giving 100% convergence".
  - So the value is set by the slowest-converging configuration in the data, not by an impulse load level.
  - "loosest-but-lowest" contradicts itself.
- **Evidence:**
  - Free-field scaled impulse from the CSV, in Pa·s/kg^(1/3): 197 (Z = 1), 83 (3), 54 (5), 27.5 (10), 18.4 (15), 13.8 (20).
  - The band as a relative tolerance: 10 % (Z = 1), 24 % (3), 37 % (5), 73 % (10), 109 % (15), 145 % (20). Beyond Z ≈ 14 the band exceeds I_ff itself, so any attenuation counts as converged.
  - At the measured radius the band is a median 84.7 % of I_ff (p10 73.6 %, p90 104.7 %), consistent with "~83%".
  - **The pressure side of the comparison is from the hard table.** Under production `req_soft3`, the pressure band at its radius is 67.3 %, not 47 %. The asymmetry is therefore 84.7 / 67.3 = 1.26x, not 1.8x.
  - **"No reliance on extrapolated free-field data" fails for one configuration:** config_61_det2_b30_s5_h24_w50 has Z_conv,I = 21.49 > 20 (RadiusI 79.18 m in `convergence_table_req_soft3.csv` and `_req.csv`). This matters only on the `--rebuild-impulse` path; the raw store uses the true reference field.
  - Sensitivity: outline:82 says "thr_I ≈ 7 was tested and rejected: only 50–86 % convergence". No table or script supports this, and no values above 20 are on record.
- **Consequence:** every RadiusI depends on this value, together with `beyond_I`, the impulse Z_urban domain and the impulse clip. The "looser by 1.8" asymmetry statement in the outline, ALGORITHM.md and constants.py is wrong for the production criterion.
- **Options:**
  - (a) Update the asymmetry statement to the production numbers.
  - (b) Commit the calibration sweep, including values above 20.
  - (c) Anchor thr_I to an impulse damage level instead of to convergence coverage.

### From statistics.md

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


### From reproducibility.md

### REP-01 [high] The production Z_urban coefficients differ between HEAD and the working tree, and the WT values come from uncommitted code

Evidence:
- `final_production_z_urban_coefficients_req_soft3.csv` is modified. All 16 coefficients moved (table above). For det1 Pressure, `B_open` goes 4.012 -> 7.139 (+78%) and `C1_amp` goes 1.746 -> 2.547 (+46%). For det2 Impulse, `C0` changes sign.
- The WT file is regenerated byte for byte only by WT code on WT tables. HEAD code on WT tables gives `B_open` = 3.287, and WT code on HEAD tables gives 6.787.
- The WT code depends on:
  - modified `z_urban.py`: fit domain, and bound 8 -> 20;
  - modified `free_field.py` and `run_analysis.py`: MaxR level;
  - the untracked `blastlib/io/raw_store.py`, which reads `data/raw_npz`.
- The guard test for the new domain, `tests/test_z_urban_domain.py`, is untracked.
- `best_z_urban_coefficients_req_soft3.csv`, `cv_summary_req_soft3.csv` (z columns) and `max_radius_per_Z_req_soft3.csv` moved with it.
- CLAUDE.md §3 requires results of record to be reproducible from the code at the same commit, and §1.3 requires old and new values before a change is made. `WORKLOG.md` does not exist in the repo (REP-10), so no record of this move was found.

Implication (not verified): the LOGO numbers and `soft_beta_selection_note.md`, which justify beta=3, were produced with HEAD's Z_urban code. Their z-target figures may no longer match the WT code.

### REP-02 [high] HEAD is not self-contained: committed street code and tests call a function that was never committed

Evidence:
- `paths.default_npz_dir` is called in HEAD's:
  - `blastlib/street/anchors.py:155`, `fitting.py:73`, `validation.py:62`, `figures.py:160,308`;
  - `gui/street_preview.py:140`;
  - `tools/street/street_figure.py:68`, `street_parity.py:112`;
  - `tests/conftest.py:49,60`.
- `git log -S "def default_npz_dir" -- blastlib/paths.py` is empty: the definition exists only in the uncommitted `paths.py`. The callers arrived in bf8eefe and 6a44ee8.
- HEAD's fast suite on HEAD code gives 3 failed and 2 errors, for the reasons in "Tests" above. The 3 GUI failures happen because the street tabs exist only in the uncommitted `gui/specs.py`.
- Commit 06d09ca ("rebuild reproduces every pinned artefact exactly", "PASS at HEAD 6a44ee8") cannot be re-run from 6a44ee8 or from HEAD. `street_parity.py:112` evaluates `paths.default_npz_dir(soft=True)` as an argument, so it raises even when `--npz-dir` is given.
- The street pinned-artefact parity therefore depends on uncommitted code and is not tied to any commit.

## Decisions the owner must make

Grouped by cluster. The options are the auditors' own; no recommendation is made here. Question D1 comes first because most of the others are answered on top of whichever state is chosen.

**D1. Which state is of record: HEAD or the uncommitted working tree?** (REP-01, ALG-02, CHO-04, ALG-04, STA-07, REP-04, REP-05, REP-06, REP-02)
- (a) HEAD: code, tables, ALGORITHM and calculator are the record. The working-tree changes are set aside as a proposal, and the HEAD tables are restored until reviewed.
- (b) Working tree: commit code and tables together, with a note giving old and new values and the attribution. Then update ALGORITHM (EN and HE), the calculator and any thesis text. This also commits `default_npz_dir` and makes HEAD self-contained (REP-02).
- (c) Keep both, with a separate filename token for the new MaxR definition, so the two are never compared as one run.

**D2. Building-rim cells: the grid merge runs before the solid-cell mask.** (ALG-01, PHY-01, CHO-09, PHY-10, CHO-19)
- (a) Keep the current order. Document it as a convention with its sensitivity, and state that R_conv,I is essentially "the outermost building wall inside the I_ff/W^(1/3) = 20 contour".
- (b) Build the mask from the raw solver sentinel on each grid, before the merge. Re-run Phase 1 and Phase 2, and report old and new values.
- (c) Keep the merge order, but add a validity gate that pins or drops sentinel cells (for example a low-impulse floor like the pressure one), and report both.

**D3. The Z_urban domain is decided with the measured target.** (ALG-03, STA-02, ALG-19, CHO-10)
- (a) Keep the domain and restate the claim. Report both the conditional error and the error on the domain a user can identify beforehand (predicted R_conv), together with the dropped shares.
- (b) Define the test domain by the predicted R_conv. This moves z_P and z_I of record.
- (c) Treat the `beyond` rows as censored in the fit.
- (d) Include the `beyond` rows at the value the deployed chain outputs (Z_conv).
- (e) Align the MaxR sector rules with R_conv (exclusion, streak), so that "comparable by construction" becomes true, and re-measure.

**D4. How is beta = 3 justified?** (CHO-01, ALG-06, CHO-07, PHY-02, ALG-07)
- (a) Keep beta = 3 and state the real order of events. Report hard, beta 3 and beta 4 side by side.
- (b) Register a new rule now (several cliff pairs, a mesh-invariant scan, softCap included) and re-run.
- (c) Return to beta = 4, stating the relaxed rule.
- Sub-questions: whether to report the soft-criterion effect separately from the model change (ALG-07), and whether to scan softCap jointly with beta (CHO-07).

**D5. Model choices made on the same LOGO folds that are reported.** (STA-01, CHO-13, CHO-15, STA-08, ALG-13)
- (a) State plainly that LOGO is the error of the selected model, and that `a` was CV-selected.
- (b) Nested LOGO for the cheap choices (`a`, relwls/OLS, quad/legacy, range_switch, canyon_trap).
- (c) Nested beta selection over the six existing tables.
- (d) Bring the LOCO-W and LOBO-b harnesses, and a Z_urban LOGO harness, into the repo and quote them as secondary estimates.
- (e) New CFD configurations for a truly untouched check.
- For claims with no artefact (ALG-13): add the scripts, mark the figures as unreproduced, or remove them from thesis-facing text.

**D6. The safe-domain box.** (STA-04, CHO-14, ALG-11)
- (a) Describe it as a descriptive partition of the 96 LOGO errors, not a bound.
- (b) Nested box selection, which gives an honest coverage rate.
- (c) Replace the ±15 % band with prediction intervals from out-of-fold residuals.
- (d) Simulate interior points to test the box.
- In every case: print the bounds as the sampled lattice values, since the printed box selects 22 configurations, not 38.

**D7. The pressure floor: urban P (code) or P_ff (outline)?** (CHO-03, PHY-09)
- (a) Correct the outline and chapter to the urban floor, and state that shielding below 10 kPa counts as converged.
- (b) Adopt the P_ff floor. Every pressure radius moves (median +58 % on a 16-configuration probe) and a full re-run is needed.
- (c) Report both.

**D8. Physical anchoring of the thresholds.** (CHO-02, CHO-06, PHY-06, PHY-08)
- 10 kPa: (a) cite a damage-level source; (b) commit the threshold sweep behind the -0.6 elasticity; (c) report R_conv as a function of the threshold for 2-3 damage levels (aim 4).
- thr_I = 20: (a) correct the "1.8x" statement to about 1.26x; (b) commit the calibration sweep, including values above 20; (c) anchor thr_I to an impulse damage level; (d) cap the impulse band relative to I_ff where I_ff/W^(1/3) < 20; (e) describe R_conv,I as a scaled-excess contour.
- KB/UFC: (a) register UFC 3-340-02 and/or Swisdak 1994 in `docs/references/` and add a CFD-vs-KB table; (b) state the thresholds as CFD-field thresholds with their KB-equivalent location; (c) drop the damage-threshold attributions until they are sourced. (The KB coefficients in the physics probe were entered from memory and must be verified before citing.)

**D9. What R_conv means.** (CHO-05)
- (a) Keep `req`, define it in the text as the equivalent-area radius of the non-converged region, and report the sector spread.
- (b) Recompute `p95` or `max` under the current criteria as a conservative companion.
- (c) Move to directional output.

**D10. The mesh is fixed in metres.** (PHY-02, PHY-03, PHY-04, PHY-17)
- Soft-scan bias (PHY-02): (a) document it with the numbers; (b) scan step fixed in scaled length; (c) controlled resampling test on one W = 500 field.
- Grid seam (PHY-03): (a) document it and restrict W-trend claims to Z < 100/W^(1/3); (b) coarsening test on W = 500; (c) reword the ALGORITHM monotonicity claim.
- MaxR_I level (PHY-04): (a) take the level from the grid-filled reference; (b) exclude an edge margin from both the level and the search; (c) revert to the scalar CSV level for impulse.

**D11. Best-split artefacts.** (STA-03) (a) Relabel as "selected split, optimistic"; (b) make `check_formulas` report out-of-fold predictions; (c) point `formulas_printer` at `final_production_*`; (d) keep `best_*` for debugging only.

**D12. Uncertainty.** (STA-05, STA-06) (a) Publish family-cluster bootstrap intervals; (b) report identified combinations (C1/B) next to the raw constants; (c) prediction intervals from out-of-fold residuals; (d) report alpha with an interval and its exact specification. Whether to simplify terms whose intervals cover zero is a separate modelling decision.

**D13. "Dimensionless".** (ALG-10, PHY-07, CHO-13) (a) State the units (m, kg TNT) of Z, Pi_2 and every constant and drop "dimensionless"; (b) rewrite in Sachs-dimensionless form (constants change, fits do not); (c) fit the switch location if its physical reading is to be kept.

**D14. Hopkinson argument.** (ALG-09, STA-06, PHY-13) (a) Recompute reason 2 from one named source; (b) qualify reason 3 as conditional on the scaled criterion and on D2; (c) drop reason 3.

**D15. Req end-bin bias.** (ALG-05, CHO-20, PHY-11) (a) Keep and document; (b) weight bins by their true width; (c) 90 full bins on half degrees.

**D16. Hard-coded copies.** (ALG-14, CHO-12, REP-06) (a) Read values from the CSVs and `constants.py`; (b) a test comparing each copy with the production CSV; (c) keep the copies, listed in one place checked after every re-run.

**D17. Calculator guards.** (STA-09, CHO-10) (a) Enforce the rho envelope, Z_free >= 2 and R_free > exclude_r, and flag Z_free beyond the populated levels; (b) check distance to the nearest simulated configuration; (c) add warnings to `predict_*`.

**D18. Smaller choices, one line each.**
- ALG-08: correct the "same quantity (MAPE)" wording and document the bounds, or fit an L1 relative loss.
- CHO-08: move K and TOLERANCE into `constants.py` with rationale; tie the soft chain to `K_CONSECUTIVE`; run a K sensitivity study.
- CHO-11: state the reason for corner (det 1) vs face (det 2), or use one rule.
- PHY-05: re-export the W = 1000 coarse reference, record the defect with its bound, or add a geometry check to the raw store.
- CHO-16: accept the street constants as carried, or refit them with `fit_e_peak`.
- ALG-12: update README to CLAUDE.md's position and the raw-store default, and optionally keep v1 loadable.
- REP-03 / REP-07: make config_01/93/95 of v1 and v2 local (about 410 MB) so the anchor tests can run; make the fixture skip on placeholders; pin `raw_npz`.
- STA-13 / REP-08: pin versions or keep a lock file; install pytest in the working environment.
- ALG-16, ALG-20 / CHO-18, CHO-17, PHY-12, PHY-14, PHY-15, PHY-16, STA-11 / REP-09, STA-12: wording or documentation choices, options in the reports.

## What was checked and found consistent

- **Units.** Pressure is converted Pa -> kPa once for urban and reference, impulse stays in Pa.s, and the CSV uses the same units. `thr_I_scaled` is in Pa.s/kg^(1/3), with W in kg. (PHY)
- **Hopkinson admissibility of the thresholds.** The scaled free-field impulse collapses across W (median CV 0.29 %), and I/W^(1/3) = 20 sits at Z = 13.6-13.8 for every W. The 10 kPa free-field contour sits at Z = 11.3-12.1 (±4 %). (PHY)
- **Geometry.** rho = b²/(b+s)² equals the solver footprint fraction. The ranges of rho, Pi_2 and H/s are correct. det 1 and det 2 references are byte-identical, so the ratio is not contaminated by det. All Z_urban row conditions are dimensionally consistent. (PHY)
- **Formulas vs document.** RadiusP, RadiusI with its quadratic term, `range_switch`, `canyon_trap`, the tanh projection, the Markov-chain soft scan, the pressure band and the impulse band match ALGORITHM.md term by term. ALGORITHM.md and ALGORITHM_HE.md agree number for number. (ALG)
- **Convergence radii reproduce.** Working-tree code on `data/raw_npz` reproduces all 96 RadiusP and RadiusI in `convergence_table_req.csv` and `_req_soft3.csv` exactly (ALG, PHY), and 16 of 16 sampled configurations (CHO). The RadiusP anchors reproduce bit-exactly (REP).
- **Production files regenerate byte for byte.** HEAD code on HEAD tables gives HEAD's `final_production_*_req_soft3`; WT code on WT tables gives WT's. Two identical runs are byte-identical. `cv_summary` rows 0-19 match to 6e-15. (REP, STA)
- **CV mechanics.** Splits are by configuration and stratified by det. Nothing is fitted on all rows before the split. The Z_conv clip inside CV uses the fold's own convergence fits. The production refit on all 96 is stated and is independent of seed and `n_iter`. No split skipped, no silent fit failure. (STA)
- **LOGO harness.** Families are (det, b, s, H) with fits per det. The ALGORITHM LOGO table matches `logo_summary_req_soft3_relwls_quad.csv` (8.43 / 5.67 / 18.65 / 30.07; 7.21 / 5.89 / 16.40 / 30.39). (STA, ALG, CHO)
- **Sibling optimism is small.** Family-grouped splits give medians within about 0.6 pp of the stratified random splits, so ALGORITHM's caution is, if anything, stronger than the effect. (STA)
- **Seed.** Seed 42 reproduces the recorded medians (8.786 / 7.153). Across seven seeds conv_P spans 8.54-8.79, with 42 the least flattering. (CHO)
- **beta-scan numbers regenerate.** Gaps and median inflations in `soft_beta_selection.csv` regenerate exactly from the tables. Impulse is identical across `req`, `req_soft2/3/4`. (CHO, ALG)
- **Stated statistics that hold.** Sibling fraction 92.5 %, 272 of 500 splits under 10 %, impulse band 84.7 % at the radius (stated ~83 %), pressure anisotropy 9.7 % (stated 9.6 %). (STA, CHO)
- **Street model.** The formulas in its document match `blastlib/street/model.py`, and the inline config_93 goldens pass on the working tree. (ALG, REP)

## Not checked

- **Tests in the owner's environment:** pytest is not installed. The four RadiusP anchor tests, the v2/v3 equivalence tests and the 5 `slow` street pinned-artefact tests did not run.
- **Full Phase 1** (96 configurations) and **Phase 2 at `n_iter = 500`**: not permitted without the owner. Only 2 of 96 configurations were spot-checked in Phase 1 by the repro checker, and splits 0-19 in Phase 2. `best_*` files could not be compared.
- **Downstream effect of PHY-01 to PHY-04 and of ALG-01** on the Phase-2 coefficients, LOGO and the safe domain: needs a production re-run.
- **Tools that write under `outputs/`** (`check_formulas`, `logo_cv`, `street_parity`, the others): not run.
- **Solver semantics:** whether `Peak_Impulse` restarts at each stage remap, the remap times, charge equivalence, height and shape, ambient p0.
- **KB/UFC coefficients** against a primary source: no standard is registered (`docs/references/INDEX.md` does not exist).
- **Studies with no artefact in the repo:** mesh coarsening, the -0.6 elasticity, the minPressure sweep, the thr_I ≈ 7 test, the 10,484-candidate search, the Z_urban LOGO figures, PySR, LOCO-W/LOBO-b.
- **Cloud-only stores** (`processed_npz`, `processed_npz_v2`, `obs_npz`) and the VTKs (absent).
- **The thesis chapters, the proposal and compare_v6:** off limits for this run. `/verify trace` was not run, so no finding has been mapped to a specific thesis equation or table beyond the documents inside the repo.
- **Untracked root files** `diag_estimator.py`, `rchan.csv`, `rchan2.csv`, and the provenance of the untracked `outputs/check_results/*.csv`.
- The street model beyond formula level; the GUI beyond duplicated defaults; `blastlib/street/fitting.py`.
