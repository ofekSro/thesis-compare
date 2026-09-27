# Audit: algorithm  (2026-09-27, commit 5f19029, working tree dirty)

Scope: code vs documentation for the whole measured-and-fitted chain: VTK/raw NPZ -> `process_grids` -> convergence radius (hard `req` and soft `req_soft3`) -> MaxR per Z_free (`find_percentile_radius`) -> `z_urban_valid_mask` -> Phase-2 regression (RadiusP relwls, RadiusI quad, `range_switch`, `canyon_trap`, clip, CV, production refit). The street-channelling model was checked against its own document at formula level only. The working tree was audited as it stands. Each finding says whether the code involved is committed or modified-uncommitted.

Documents read: `CLAUDE.md` (untracked), `README.md` (modified), `docs/ALGORITHM.md` and `docs/ALGORITHM_HE.md` (both untracked, never committed, mtime 2026-08-04 07:49), `docs/STREET_CHANNELLING_MODEL.md` (committed), `docs/PYSR_CONVERGENCE_SEARCH.md` (part), the rationale comments in `blastlib/constants.py`, `outputs/check_results/soft_beta_selection_note.md` (working tree and the `cbb2312` version), `soft_beta_selection.csv`, `soft_criterion_summary.csv`, the `logo_*` and `safe_domain_req_soft3.csv` files, and the result tables at HEAD (`git show HEAD:`) and in the working tree.

Code map (data flow, units):
`raw_store.expand` -> `grids.process_grids` (P in kPa, I in Pa.s; merges 3 grids, masks P <= 1.01e-3 kPa, forms ratios, pins converged cells to 1) -> `concat3` -> `convergence.find_convergence_radius` (91 bins, far-to-near K=3 scan, or the soft Markov scan for P; exclusion r > exclude_r) -> `radius_estimator.reduce_theta_radii` (Req = sqrt(4A/pi)) -> `convergence_table_<m>.csv` (m). In parallel, `free_field.reference_level_per_theta` (ring median of raw refP/refI at r_free = Z*W^(1/3)) -> `find_percentile_radius` (outermost cell with value >= level, per sector) -> Req -> `max_radius_per_Z_<m>.csv` (m, plus `beyond_*` flags). Phase 2: `prepare_maxR_data` -> `z_urban_valid_mask` -> `curve_fit` on ln(Lambda) -> clip at the predicted Z_conv -> MAPE; `StratifiedShuffleSplit(500, 0.2, 42)`; production refit on all 96.

Tests: `python -m pytest` could not be run. The only working interpreter (Python 3.12.10) has no pytest, and the `py -3.14` launcher target is missing. In its place I ran read-only probes (scripts in the session temp dir, not in the repo). They reproduce all 96 `RadiusP`/`RadiusI` values of `convergence_table_req.csv` and `convergence_table_req_soft3.csv` exactly from the working-tree code, and they reproduce the MaxR rows checked (config_93, config_58, Z = 2..10).

## Summary

The formulas written in ALGORITHM.md match the code term by term: RadiusP, RadiusI with its quadratic log term, `range_switch`, `canyon_trap`, the tanh projection, the Markov-chain soft scan, the pressure band and the impulse band. The convergence radii are reproducible from the working-tree code.

Three things are doubtful, and each needs a decision by the owner:
1. **ALG-01.** An undocumented order of operations in `process_grids`: the multi-grid max-merge runs before the solid-cell mask. This lets a 0.15-0.3 m skin of cells inside every building wall enter the convergence scans. The measured radii depend on that skin: on all 96 configurations, removing only these cells moves RadiusI by a median of -35% and RadiusP (production) by a median of +5% (up to +66%).
2. **ALG-02.** ALGORITHM.md, in both languages, mixes two states of the repo. Its coefficient table and its CV numbers are those of the committed HEAD tables. Its domain wording and its continuum-limit table are those of the uncommitted working tree. The working-tree results of record differ from the numbers the document prints.
3. **ALG-03.** The claim that R_conv and Z_urban are "comparable by construction" does not hold. The two radii share only the final collapse. The mismatch is absorbed by dropping 13.5% (P) and 28.6% (I) of in-domain rows on an outcome-dependent condition.

Several further medium items concern provenance and selection. The candidate set for beta was widened after the pre-registered set failed. The soft-criterion gains are attributed across a simultaneous model change. Many quantitative claims have no artefact in the repo. The Hopkinson "recovered exponent" argument depends on ALG-01.

## Findings

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

### ALG-04  [medium]  Uncommitted, undocumented changes to the MaxR / Z_urban path; the per-direction reference level uses different operands from R_conv
- Where: `run_analysis.py:286-331`, `free_field.py:59-105` and `:179-189`, `z_urban.py:262-269` and `:408-420`. All modified-uncommitted. None of it is described in ALGORITHM.md; the per-direction level is not mentioned anywhere in the document.
- What: Three changes relative to HEAD:
  - (i) The exceedance level is now the ring median of the reference field per sector (tol 0.6 m, doubling to 4 m), with fallback to the `free_field_data.csv` scalar. Previously it was the scalar.
  - (ii) Two new fit-domain conditions: `R_free < R_conv` and `R_free > exclude_r`.
  - (iii) The B upper bound was raised from 8 to 20.
  The level is taken from the raw, unmerged refP of all three grids, which are not smart-cut. It is compared with the max-merged urban field, while R_conv divides merged urban by merged reference, cell by cell.
- Evidence: MaxR moved in 1920/1920 (P) and 1912/1920 (I) rows between HEAD and the working tree. Over Z = 2-10, P has median -0.76% (p5 -5.0%, max |19.7|%) and I has median +0.31% (p95 +4.4%). The beyond flags changed in 11 rows. Mixing grids in the ring lowers the level by 0.2-2.0% compared with grid 1 only (config_93 and config_58, Z = 2..10). The level also sits 1.4-3.7% above the CSV scalar at the same Z. The working-tree code does reproduce the working-tree MaxR rows checked.
- Consequence: `max_radius_per_Z_*`, the Z_urban coefficients and the CV numbers (see ALG-02).
- Options: (a) document the three changes in ALGORITHM.md (EN and HE) and commit them together with the tables; (b) restrict the ring to the same merged, smart-cut reference that R_conv uses; (c) revert to the committed scalar level and fit domain.

### ALG-05  [medium]  Req weights the two half-width end sectors as full 1-degree sectors
- Where: `radius_estimator.py:46-55` (bins 0 and 90 are 0.5 degrees wide) vs `:134-140` (`A = sum(0.5*r^2*dtheta)` with dtheta = 1 degree for all 91 bins). Committed. The document says "The first quadrant is split into 91 one-degree sectors" (L78-79).
- What: The area sum spans 91 degrees of a 90-degree quadrant, and it double-weights the 0- and 90-degree sectors, which are the street-axis directions.
- Evidence: A uniform r = 100 gives Req = 100.554 (a factor of sqrt(91/90)). On the production theta tables, Req(code)/Req(true widths) has median 1.0046 (P) and 1.0030 (I), with a maximum of 1.0376 (P).
- Consequence: Every radius of record, up to 3.8%. The bias is not uniform, because it grows where the axis radii differ from the mean (axis/mean median 0.92 for P and 0.70 for I).
- Options: (a) keep and document it as a convention; (b) weight each bin by its true width; (c) switch to 90 full-width bins centred on half degrees.

### ALG-06  [medium]  The beta = 3 selection is presented as pre-registered, but the candidate set was widened after the pre-registered set failed
- Where: ALGORITHM.md L112-117, HE L97-100, `constants.py:58-63`, `soft_beta_selection_note.md`. Committed record: `cbb2312:outputs/check_results/soft_beta_selection_note.md`, and the `soft_beta_selection.csv` column `required_set`.
- What: The document says "selected by a sensitivity scan over beta in {2,3,4,6,8,12} as the only value satisfying both rules fixed in advance". The committed `cbb2312` note says: "The pre-registered rule — largest β ∈ {4, 6, 8, 12} with a config_93↔config_95 Req gap under 10 m — selects nothing ... only the supplementary β=2/3 fall below 10 m". It then chose β* = 4 "by user decision with the gap rule relaxed". `required_set` is False for β = 2 and 3. β = 3 was adopted afterwards (`430d004`).
- Consequence: The thesis wording about pre-registration.
- Options: (a) state the actual sequence (pre-registered set, failure, relaxation to β = 4, extension to {2, 3}, adoption of 3); (b) treat the beta choice as post hoc and report the sensitivity across all six values as the result.

### ALG-07  [medium]  Soft-criterion gains are attributed across a simultaneous model change
- Where: ALGORITHM.md L236-241 and L571-572, HE L204-209 and L491-493, `constants.py:62-63`.
- What: The document says "the soft criterion improves the P median and collapses the max, but its p90 is ~1.5 pp worse than the hard tables'" and "the median improves for both loads". Those figures compare hard + legacy models with soft + new models.
- Evidence (`soft_criterion_summary.csv`, same new models, P): median 6.85 -> 5.67, p90 15.86 -> 18.65 (+2.8 pp, not +1.5), max 40.38 -> 30.07. The impulse improvement (median 7.10 -> 5.89, max 38.48 -> 30.39) comes entirely from the model change; the soft criterion does not touch impulse. The "43.4% -> 30.1%" in `constants.py` likewise mixes the two changes.
- Consequence: Thesis statements about what the soft criterion buys and what it costs.
- Options: (a) report the two effects separately (criterion at fixed models; models at fixed criterion); (b) keep the combined comparison but label it as combined.

### ALG-08  [medium]  Stated loss functions do not match the fitted losses
- Where: ALGORITHM.md L138-140 vs `convergence_models.py:123-125`; `z_urban.py:402-422` and `:441-492` (undocumented bounds, starting points and objective).
- What: The document says "least squares weighted 1/Z — minimizing squared relative error — so the loss being minimized is the same quantity (MAPE) the validation reports". The code minimises sum(((Xc - Z)/Z)^2), the L2 norm of relative error. MAPE is the L1 mean. The Z_urban forms minimise squared error in ln(Lambda) with `curve_fit` inside box bounds (C1 >= 0, A in [0,6], B in [0.2,20], C3 in [0,6]). None of this appears in ALGORITHM.md.
- Consequence: A rationale in the method description; also any comparison that treats the fit loss and the reported metric as the same quantity.
- Options: (a) correct the wording (both are relative-error measures, but not the same measure) and document the bounds; (b) fit an L1 relative loss if identity with MAPE is wanted.

### ALG-09  [medium]  Hopkinson argument: reason 2 does not reproduce from the repo's free-field data; reason 3 depends on the criterion and on ALG-01
- Where: ALGORITHM.md L43-58, HE L41-52; `grids.py:178-179` gives a different figure (4.7%).
- What and evidence:
  - Reason 2 claims a CV of about 4.3%, (max-min)/mean of 10-17%, 57.4 -> 63.7 kPa at Z = 4, and monotone in W at every Z <= 12. `data/free_field_data.csv` gives a CV of 4.77% (mean over Z), (max-min)/mean of 8.1-25.1%, 55.3 -> 62.3 kPa (+12.6%) at Z = 4, and monotonicity only at Z in {1,2,3,4,7,8}. The ring medians of the reference field at Z = 4 are 56.5 kPa (50 kg) and 60.6 kPa (250 kg), which do not match either.
  - Reason 3: α = 0.340 / 0.307 is reproduced from the current RadiusI (legacy linear form with ln s). The text says the refit is "imposing nothing", but the impulse band is itself |ΔI|/W^(1/3) < 20 (`constants.py:30`). The fixed scaled contour I_ff/W^(1/3) = 20 lies at Z of about 13.8 for every weight. Without the ALG-01 skin cells, the same refit gives α = 0.242 (det1) and 0.220 (det2).
- Consequence: A thesis argument for the scaling ("a result read out of the measurements").
- Options: (a) state the source and convention of the reason-2 numbers, or recompute them from a named artefact; (b) qualify reason 3 as conditional on the scaled criterion and on the skin-cell treatment; (c) drop reason 3.

### ALG-10  [medium]  "Every predictor is a dimensionless Pi group" does not hold as stated; the switch constants depend on the unit system
- Where: ALGORITHM.md L129, L133-138, L186-188; `convergence_models.py:39-40` and `:186`; `z_urban.py:94`.
- What: Π₂ = s/W^(1/3) carries m·kg^(-1/3). The density switch at Π₂ = a (a = 1 or 2) and the canyon flip "at s = W^(1/3), the physical crossover" are 1 m/kg^(1/3) statements. In another unit system they would be different numbers. The code comment says a was "selected by CV from {1, sqrt(2), 2}", so it is not a physical constant.
- Consequence: The "scale-invariant" claim in the soundness section and the physical reading of the terms. The fitted numbers themselves are unaffected in SI/kg-TNT use.
- Options: (a) state the unit convention (m, kg TNT) wherever the formulas appear and describe a as a CV-selected constant; (b) re-express with an energy/ambient-pressure length scale if true dimensionlessness is wanted.

### ALG-11  [medium]  The safe-domain box as printed does not reproduce the 38-configuration classification
- Where: ALGORITHM.md L276-288, HE L241-251; `outputs/check_results/safe_domain_req_soft3.csv`.
- Evidence: The printed box (0.31 <= ρ <= 0.56, Π₂ >= 0.50, H/s <= 3) selects 22 configurations. The "equivalent" form b/(b+s) in [0.56, 0.75] selects 30. The file's `InSafeDomain` (38) is reproduced exactly only with ρ in [0.3086, 0.5625], that is, b10/s8 and b15/s5 included. Everything else is confirmed within the 38: max errors 18.94% / 19.64%, means 7.78% / 6.44%, 89.5% / 94.7% within 15%, and all 12 configurations above 20% outside.
- Consequence: A user applying the stated box excludes 16 of the 38 "safe" configurations.
- Options: (a) print the bounds as the sampled lattice values (ρ from 0.309 to 0.5625 inclusive); (b) state the box in terms of (b, s) families.

### ALG-12  [medium]  README contradicts CLAUDE.md and the current code
- Where: README.md L3-7, L103, L165-169, L178-190. README is modified-uncommitted.
- What:
  - README says "Same numerical behaviour" and "compare_v6 ... remains the reference", and §4 says the new code "must reproduce the old numbers exactly". CLAUDE.md §4 says compare_v6 "is history, not a reference", and the impulse criterion, estimator unification, soft default and per-direction level have all changed the numbers.
  - §3 says "Phase 1 reads data/processed_npz"; the default is `data/raw_npz` (`paths.default_npz_dir`).
  - "Both are read transparently" no longer holds for v1: the working-tree Phase 1 calls `concat3(processed, 'refP{}')` (`run_analysis.py:291`), and the v1 files carry no `refP*` keys (checked on `data/processed_npz/config_01...npz`).
- Consequence: Following README §4 would lead to a false FAIL, or to "fixing" code toward compare_v6.
- Options: (a) update README to the CLAUDE.md position and the raw-store default; (b) keep v1 loadable by falling back to the scalar level when `refP*` is absent.

### ALG-13  [medium]  Many quantitative claims have no artefact or script in the repo
- Where: ALGORITHM.md L302-306 (minimax ≈ 26%), L315-316 (elasticity -0.6), L402-405 (cross-application 3-4 pp), L415-425 (10,484 forms, 9.81% vs 10.91%), L433-445 (16 neighbour pairs), L487-527 (coarsening table, 52 -> 92 -> 99 m, prototype 28%, 14.3%), L539-541 (11.7% / 12.7%), L548-557 (6.70 m, ≈15 m, 12.6% / 16.3%, 6 and 3 configs); `z_urban.py:104-105` (Z_urban LOGO 8.4 vs 9.9, 9.9 vs 12.3).
- What: `tools/logo_cv` covers the convergence radii only. No harness in the repo reproduces any Z_urban LOGO number, and `outputs/check_results` holds no file for the listed checks. The per-Z sector radii that the bimodal diagnostic needs are not saved.
- Consequence: These claims cannot be verified or regenerated (CLAUDE.md §3, §4.4), and some were measured on an earlier fit domain (see ALG-02).
- Options: (a) add the scripts and outputs that produced them; (b) mark them in the document as unreproduced exploratory figures; (c) remove them from thesis-facing text.

### ALG-14  [medium]  Duplicated constants that have drifted or can drift
- Where: `tools/z_surface_3d/z_surface_3d.py:34-37`; `convergence_models.py:186` and `z_urban.py:92-94`.
- What: The `z_surface_3d` `COEF` holds 7.778 / -0.576 / 2.298 / 0.576 and 10.060 / -1.157 / 2.185 / 0.710. These are the HEAD legacy-OLS hard `req` coefficients. The production `req_soft3` values are 9.063 / -0.645 / 2.018 / 0.591 and 11.858 / -1.375 / 2.782 / 0.776, and README calls the tool "hardcoded production coefficients". The switch threshold a = {1: 1, 2: 2} is written twice; the `z_urban.py` comment calls it "shared", but it is a separate literal.
- Consequence: Any figure made with `z_surface_3d` shows a non-production model.
- Options: (a) read the coefficients from `final_production_convergence_coefficients_<method>.csv`; (b) keep the hard-coded values and label the figure with the coefficient set.

### ALG-15  [low]  Special cases of the sector scan and of Req are not documented
- Where: `convergence.py:55-62`, `radius_estimator.py:125-140`; ALGORITHM.md L79-81.
- What: The hard scan returns the last in-band cell before the first 3-streak, not "the point where the ratio first leaves". If the streak starts at the outermost cell it returns that violating cell. If there is no streak it returns the innermost valid cell (about exclude_r), which Req then integrates as area: 8 of 91 sectors in config_58 (hard P). Req drops NaN sectors without renormalising, so MaxR sectors with no exceedance contribute zero area. The outer domain is never reached (0/91 sectors at the outermost cell; grids extend to 499.5 m).
- Options: (a) document these conventions in Step 1; (b) change them (owner's choice).

### ALG-16  [low]  The impulse "floor at ≈ 0.93" is misstated
- Where: ALGORITHM.md L533-535, HE L460-463.
- What: The document says "ln Λ ≥ C₀, i.e. Λ has a floor at ≈ 0.93". With the printed coefficients, exp(C₀) = 0.910 (det1) and 0.994 (det2). With the working-tree coefficients it is 0.898 and 1.007, so det2 impulse then cannot predict attenuation at all. The value 0.93 is the minimum predicted Λ over the data, not the floor.
- Options: (a) state the per-det floor exp(C₀); (b) keep 0.93 but call it the minimum over the sampled geometry.

### ALG-17  [low]  Stale numbers in the documents and code comments
- Where and what (current values in brackets):
  - `z_urban.py:72,246,571`: attenuating share "51% P / 15% I" [46.0% / 11.3%].
  - ALGORITHM.md L580-582 and `z_urban.py:122-123`: "60 of 96 configs flip, ceiling 81.5%" [62 of 96, 81.7% in the WT state; 64 of 96, 82.7% at HEAD].
  - L60-62: "radii span 20–140 m ... factor ≈ 2.2" [R_I reaches 165.3 m; Z factor 2.16 for P, 2.41 for I].
  - L584-588 and `constants.py:46-48`: "~47% pressure band at its radius" [48% on the hard tables; 67% at the production req_soft3 radii].
  - STREET doc §1: "Median 59 m" for R_half [66.9 m predicted over 96; 54.2 m measured over 75].
  - STREET doc §6: says "four did not survive" but lists six corrected claims.
  - STREET doc §3: "~100% of grid-1 cells valid" [peakP1_orig finite share 58% in config_93 and 26% in config_58; footprints hold a constant floor, not an "over-roof envelope"].
- Options: refresh from the tables, or cite the state each number was measured in.

### ALG-18  [low]  Stale docstrings and printed text in code
- Where and what:
  - `constants.py:65-68` says the soft default reads `processed_npz_v2`; `paths.default_npz_dir` prefers `raw_npz`.
  - `radius_estimator.py:161-163` says softBeta is 6.0; it is 3.0.
  - `soft_criterion.py:22-24` says "Requires the v2 NPZ superset"; v3 serves it.
  - `z_urban.py:241-243`: conditions 2 and 3 use "ExcludeR"/"skipped". The code uses the `exclude_r` column that `prepare_maxR_data` derives from the config name, so condition 3 is never skipped in the pipeline, and the `ExcludeR` CSV column is never read.
  - `tools/check_formulas/check_formulas.py:540` still says "AND amplification".
  - `cross_validation.py:100` prints 77/19; sklearn draws 76/20.
  - `cross_validation.py:279` and `output.py:201` print the RadiusI formula without the quadratic term.
  - `run_analysis.py:4-6` still says "data/processed_npz/".
  - ALGORITHM.md L364-370 describes the `processed_npz_v2` superset as the mechanism; production reads the v3 raw store.
- Options: update the text; no numbers move.

### ALG-19  [low]  The Z_urban test domain uses the measured R_conv of the held-out configurations
- Where: `z_urban.py:750-751` (evaluation) vs `:577-594` (clip uses the predicted R_conv).
- What: Test rows are selected with conditions 1 and 2 on the measured `RadiusP`/`RadiusI`, which a user of the deployed chain does not have. The reported Z_urban MAPE is therefore conditional on the measured domain. ALGORITHM.md does not say this.
- Options: (a) state it; (b) also report MAPE on a predicted-R_conv domain.

### ALG-20  [low]  MAX_HEIGHT and the `C` column have no effect on any result
- Where: `geometry.py:13-15` (`VolumeDensity`), `z_urban.py:610` (`C`).
- What: `MAX_HEIGHT = 24`, which CLAUDE.md lists as a choice to review, feeds only the `VolumeDensity` column. No fit reads that column. `C = 3 - H/s - 3ρ` is computed and never used.
- Options: (a) note in CLAUDE.md that MAX_HEIGHT is informational; (b) remove the unused column (owner's choice).

## Checked and found consistent
- RadiusP additive form, a = 1 / 2, and the relative-weight option: ALGORITHM.md L133 = `convergence_models.py:65-80, 123-127, 165-167`.
- RadiusI power law with the r₂(ln Π₂)² term: L144 = `convergence_models.py:238-250, 277-283`.
- `range_switch` (denominator Π₂·(s/H) + B = `pi2/Hs + B`) and `canyon_trap`: L157 and L167 = `z_urban.py:425-438`; `Z_URBAN_FORM` defaults as documented.
- Soft projection: w(0) = 0, w(10 kPa) = 0.5, w(>= 20 kPa) = 1; hard gate (P >= 10 kPa, |ratio-1| > 5%); raw operands identical to the hard band: `soft_criterion.py:81-152` vs `grids.py:187-215`.
- The Markov-chain bookkeeping (d[i-3], d[0] when the streak starts at the outermost cell, leftover mass to d[-1]) matches the hard scan (`convergence.py:99-117` vs `:46-62`).
- Pressure band applied to the field; the ±5% test only sees unpinned cells; 10/P_ref < 0.05 only above 200 kPa (L371-376).
- Impulse criterion |ΔI|/W^(1/3) < 20 with no pressure floor (`ff_reference.py:88-100`); scaled band width 20·W^(1/3) is about 85% relative at R_I (hard tables).
- First-street exclusion radius formula (`geometry.py:18-28`); upper-only clip at the predicted Z_conv with no lower bound (`z_urban.py:554-594`).
- CV: det-stratified, 500 splits, test 0.2, seed 42; sibling share 92.52% (minimum 60%) recomputed; best-split selection on worst MAPE; production refit on all 96.
- The working-tree code reproduces all 96 R_conv of `convergence_table_req.csv` and `_req_soft3.csv`, and the MaxR rows checked (config_93, config_58, Z = 2..10). `convergence_table_*` are identical at HEAD and in the working tree.
- LOGO convergence figures in L228-233 match `logo_summary_req_legacy_legacy.csv` and `logo_summary_req_soft3_relwls_quad.csv`; config_95 43.35% -> 5.66%; new worst case config_58 at 30.07%.
- config_93 / config_95 cliff: 62.33 vs 38.15 m (hard); gap 8.6 m at β = 3; β table = `soft_beta_selection.csv`; config_58 θ = 0: 49.88 -> 68.53 m (β = 2); median inflation +17.29%; RadiusI identical hard vs soft; MaxR identical hard vs soft; impulse Z_urban blocks identical in `_req` and `_req_soft3` (both at HEAD and in the working tree).
- Envelope table (b, s, H, W, ρ 0.184-0.735, Π₂ 0.437-5.43, H/s 0.2-4.8).
- α = 0.340 / 0.307 reproduced from the current RadiusI (but see ALG-09).
- Largest absolute LOGO misses: 18.5 m on 101.0 m (config_44) and 29.8 m on 109.2 m (config_03).
- Continuum-limit numbers match the working-tree state: Λ 0.74 / 1.10 / 0.80 / 1.17, 11% attenuating impulse rows, Λ range 0.67-2.26.
- The hard-criterion det1 B = 8.33 and the soft3 det1 B = 7.14 on 280 rows match the code comments; no working-tree coefficient sits on a bound.
- ALGORITHM.md and ALGORITHM_HE.md: identical numeric content section by section (differences are wording only).
- Street model: the formulas in the doc = `blastlib/street/model.py` and `constants.py`; g peaks at x = 0.522 with max 1.00096, and g(1) = 0.518.

## Not checked
- The pytest suite: pytest is not installed in the available interpreter. So the bit-exact β -> ∞ test, the raw-store parity test (v3 vs v2) and the anchor tests were not run. The β -> ∞ claim was checked by reading only; a cell with |ΔP| exactly 10 kPa would give 0.5 instead of 1.
- Thesis chapter 9, the proposal and compare_v6 are off limits for this request.
- Every claim listed in ALG-13, for lack of artefacts.
- How often the per-direction level fell back to the CSV scalar; this needs a full Phase-1 run, which was not made.
- The street-suite validation numbers (E_peak LOGO, envelope coverage, gate table) beyond the rule-of-thumb probes.
- Units and physics in depth (physics lens), and leakage and degrees of freedom (choices/statistics lens).
- Other documents seen in passing: `docs/PHYSICS_ANALYSIS_HE.md` and `docs/THESIS_RESULTS_OUTLINE_HE.md` quote the legacy-state figures (43.4%, 38.5%) and were not audited. CLAUDE.md refers to `docs/TRACEABILITY.md` and `WORKLOG.md`, which do not exist in the repo.
- The sensitivity in ALG-01 removes the skin cells with a data-defined mask (raw fine P <= 1.01 Pa). For det2 that mask was confirmed equal to the geometric footprint; for det1 it was not confirmed by geometry. The shares match ρ (e.g. 0.562 for b15/s5).
