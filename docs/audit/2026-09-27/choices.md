# Audit: choices  (2026-09-27, commit 5f19029 + dirty working tree)

Scope: every decision in the path raw fields -> `convergence_table_*` / `max_radius_per_Z_*` -> Phase-2 fits -> `final_production_*` that could reasonably have been made differently. Covered: the pressure criterion (10 kPa band and its low-pressure floor), `thr_I_scaled = 20`, the ±5 % `TOLERANCE`, `K_CONSECUTIVE = 3`, the soft criterion (`softBeta = 3`, `softCap_kPa = 20`) and how beta was selected, the `req` equivalent-area collapse against `p95`/`max`, the MaxR exceedance definition and the new per-direction reference level, the multi-grid merge and the solid-cell mask, the near-blast exclusion radius, the Z_urban fit domain (`z_urban_valid_mask`, `beyond_P/I`, the Z_free floor), fixed model constants and bounds (`a`, B bound), the CV settings (`random_state = 42`, `n_iter`, `test_fraction`, `target_mape`), the safe-domain box, hard-coded copies of production values (`tools/z_surface_3d`, `blast_calculator.html`, docs), the street-model constants (overview only) and `MAX_HEIGHT = 24`.

Documents read: `CLAUDE.md` [U]; `README.md` [M]; `docs/ALGORITHM.md` [U, mtime 2026-08-04, describes the committed soft-beta=3 state but cites HEAD coefficients, see CHO-04]; `docs/THESIS_RESULTS_OUTLINE_HE.md` [U]; `docs/PHYSICS_ANALYSIS_HE.md` and `docs/PARAMETER_STUDY_HE.md` [U] (relevant parts); `blastlib/street/constants.py`; `outputs/check_results/soft_beta_selection_note.md`, `soft_beta_selection.csv`, `soft_criterion_summary.csv`, `logo_summary_*.csv`, `safe_domain_req_soft3.csv`; the version of the selection note at commit cbb2312; the commit messages of 2ed1dfe, d6f33dd, b11863d, e7c04e0, b88ef6e, cbb2312, 430d004. `docs/references/INDEX.md` does not exist, so no standard could be quoted. The thesis chapter, the proposal and compare_v6 were not read (off limits).

Status tags used for every location: **[clean]** = tracked and unchanged since HEAD, **[M]** = modified and not committed, **[U]** = untracked.

## Summary

The mechanics are sound and reproducible where I could test them. The raw store plus the current code reproduces `convergence_table_req.csv` exactly for 16 of 16 sampled configurations. Seed 42 reproduces the recorded CV medians. The beta-scan numbers can be regenerated from the tables. The weak point is the justification behind the criteria, not the code that applies them.

- **beta = 3:** the record says it was the only value meeting both rules "fixed before the numbers were seen". The commit history contradicts this. The pre-registered rule, as coded, selected nothing. beta = 4 was adopted first, with the rule relaxed. beta = 3 was then chosen 13 h later from the "supplementary" set, whose numbers were already known.
- **10 kPa band:** its value has no cited source and no sensitivity study on record. The code defines the low-pressure floor on the *urban* field, while the thesis outline defines it on the *free* field. On a 16-configuration probe the two definitions give pressure radii differing by a median of +58 %.
- **"1.8x looser" claim:** `thr_I_scaled = 20` is calibrated so that every configuration converges, not tied to a load level. The statement that the impulse band is "~1.8x looser" than the pressure band is stale under production: it is 1.26x.
- **`req` collapse:** documents call it "the distance beyond which the urban field is indistinguishable from free field". In the production tables a median of 45 % (P) / 50 % (I) of sectors have their own convergence radius beyond it.
- **Uncommitted rewrite of results of record:** the working tree has uncommitted changes to the MaxR definition and to the Z_urban fit domain. These have rewritten `final_production_z_urban_coefficients_req_soft3.csv`: det-1 pressure B moves from 4.01 to 7.14 and C1 from 1.75 to 2.55. `docs/ALGORITHM.md` and `blast_calculator.html` still carry the HEAD values. Predictions move by at most 4 %, which shows these coefficients are weakly identified.

The owner has to decide:
- how beta is justified;
- which floor definition the thesis states;
- whether the working-tree tables are adopted.

## Findings

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

### CHO-07  [medium]  `softCap_kPa = 20` is a coupled, unscanned parameter, and the soft radius depends on the mesh, which is fixed in metres for every W

- **Where:**
  - `blastlib/constants.py:25` [clean]
  - `blastlib/processing/soft_criterion.py:134-152` [M]
  - Introduced in e7c04e0. `soft_beta_scan.py` varies beta only.
- **Evidence:**
  - With beta = 3 and cap = 20 kPa, the formula gives weight 0.039 at |ΔP| = 2 kPa, 0.149 at 5, 0.5 at 10, 0.851 at 15, and 1 at 20 kPa and above. The transition width scales with cap/beta, so "beta = 3" has no meaning apart from cap = 20.
  - The mesh is identical for all configurations (grid spacing 0.15 / 0.5 / 1.0 m to 100 / 250 / 500 m, checked on 14 configurations). Cells per scaled length therefore differ 3.1x between W = 50 and W = 1500.
  - ALGORITHM.md:499-503 reports the soft RadiusP moving −9.1 % (2x coarser) and −18.2 % (4x coarser), against +1.9 % / −0.3 % for the hard band. No script or table for that study exists in the repo.
  - Soft-vs-hard inflation by charge weight (median): 12.1 % at W = 50, 22.4 % at 250, 20.3 % at 500, 15.8 % at 1000, 17.0 % at 1500. W = 50, 500 and 1500 share the same 24 geometries.
- **Consequence:** production pressure radii carry a mesh- and weight-dependent part that is not Hopkinson-scaled.
- **Options:**
  - (a) Scan cap jointly with beta.
  - (b) Adopt a mesh-invariant soft scan; ALGORITHM.md says a prototype exists.
  - (c) Document the (beta, cap) pair as one choice, together with the mesh caveat.

### CHO-08  [medium]  `K_CONSECUTIVE = 3` and `TOLERANCE = 0.05` live outside `constants.py`, have no rationale or sensitivity, K is hard-wired twice, and the ±5 % never binds

- **Where:**
  - `blastlib/processing/convergence.py:20-21` [clean]
  - Soft chain `convergence.py:99-110`: states `m0, m1, m2` and `d[i - 3 if i >= 3 else 0]` [clean]
  - Both constants are inherited from compare_v6 (2ed1dfe).
- **Evidence:**
  - **TOLERANCE never binds:**
    - Impulse: a violation needs |ΔI|/W^(1/3) ≥ 20 while I_ff/W^(1/3) ≤ 197, so |ratio − 1| ≥ 10 % > 5 %. TOLERANCE never binds for impulse.
    - Pressure: it binds only where P_ref > 200 kPa (Z ≲ 2). ALGORITHM.md:374-376 says this for pressure only.
  - **K counts cells, not length:** K counts cells sorted by distance inside a 1° sector. The radial step between successive cells is about h²/(r·Δθ):
    - grid 2 at r = 50 m: ≈ 0.29 m per cell, so 3 cells ≈ 0.86 m;
    - grid 2 at r = 150 m: ≈ 0.29 m for 3 cells;
    - grid 1 at r = 20 m: ≈ 0.19 m for 3 cells.

    The filter length varies about 4-5x with r and grid, and in scaled units also with W^(1/3). No study of K = 2, 4 or 5 exists.
  - **K is encoded twice:** changing `K_CONSECUTIVE` alone would not change the soft chain. It would silently break the "β → ∞ reproduces the hard scan bit-exactly" property that ALGORITHM.md:102-103 relies on.
- **Options:**
  - (a) Move both constants into `constants.py`, each with a rationale.
  - (b) Tie the soft chain's order to `K_CONSECUTIVE`.
  - (c) Run a K sensitivity study, or express the filter in metres (ALGORITHM.md discusses and rejects a metre window on cliff grounds).

### CHO-09  [medium]  Grids are merged by element-wise maximum, which is undocumented and mislabelled; the comparison operands are asymmetric

- **Where:**
  - `blastlib/processing/grids.py:77-98`: "# Fill missing values: fine grid filled from medium grid" and "np.maximum propagates NaN" [clean]
  - `docs/ALGORITHM.md` does not mention it [U]
  - `blastlib/street/constants.py:101-106` acknowledges "the merged/unmerged asymmetry of peakP\*_orig vs refP\*" [clean]
- **Evidence:** read-only probe on 8 configurations (every 12th raw file), counting valid fine-grid cells (peakP > 1.01 Pa) where the interpolated grid-2 value exceeds the fine value and therefore replaces it:

  | field | cells replaced | median uplift |
  |---|---|---|
  | peakP | 0.4-10.6 % | 1.7-22.2 % |
  | impulse | 6.1-18.9 % | 1.6-20.6 % |
  | refP | 0.2-0.8 % | about 6 % |
  | refI | 5.0-14.5 % | 2.3-7.6 % |

  `np.maximum` never fills a NaN; it only overrides valid values.

  Three operand sets are in play:
  - The convergence band tests raw, pre-merge operands (`grids.py:187-208`).
  - The ratios and MaxR use merged fields.
  - The new MaxR level uses raw, unmerged, uncut references (CHO-04).
- **Consequence:** this affects ratio maps near building edges and MaxR. The size of the effect on the radii is not quantified. Forward to the physics lens: the grid-2 values inside the grid-1 domain look like stage-local peaks.
- **Options:**
  - (a) Document the merge rule and correct the comment.
  - (b) Use a finest-available merge instead.
  - (c) Quantify the effect on R_conv and MaxR.

### CHO-10  [medium]  Z_urban fit-domain rules: assertions, a stale document, and a deployed tool that ignores them

- **Where:**
  - `blastlib/regression/z_urban.py:90` (`Z_URBAN_ZF_MIN = 2`), `:216-271`, `:554-567` [M]
  - `run_analysis.py:339-340` [M]
  - `docs/ALGORITHM.md:258-269` [U]
  - `blast_calculator.html:415-416` [clean]
  - `diag_estimator.py` [U]
- **What:**
  - `beyond_P/I` exists because MaxR and R_conv are measured by different rules. MaxR takes the outermost single cell with urban ≥ level, with no streak and no tolerance. R_conv uses the K = 3 streak and the band. The clip docstring admits "MaxR overshoots R_conv systematically".
  - The Z_free ≥ 2 floor rests on "Z_free = 1 … is not of interest", an assertion, and partly duplicates condition 3.
  - The docstring says condition 3 "is then skipped" for flagless CSVs. In fact `prepare_maxR_data` (`z_urban.py:620-623`) always supplies `exclude_r`, so it is never skipped.
- **Evidence:**
  - Row counts, working tree, `req_soft3`:

    | stage | pressure rows | impulse rows |
    |---|---|---|
    | all rows | 1916 | 1920 |
    | inside R_conv (condition 1) | 750 | 840 |
    | + Z_free ≥ 2 (HEAD mask) | 658 | 744 |
    | + conditions 2 and 3 (working-tree mask) | 591 | 700 |

    For pressure, condition 2 removes 31 rows and condition 3 removes 36.
  - Pressure rows per Z_free = 2…10 under the working-tree mask: 75, 87, 90, 96, 94, 86, 58, 4, 1.
  - ALGORITHM.md:266 says "95, 96, 96, 96, 94, 90, 64 rows at Z_free = 2…8, then 14 and 2". This matches neither the HEAD mask on the current table (96, 96, 96, 96, 94, 90, 66, 19, 5) nor the working-tree mask.
  - The calculator tabulates Zf = 2 … ceil(max(Z_conv,P, Z_conv,I)). It applies neither the Z_free ≈ 8 (P) / ≈ 10 (I) data limit nor R_free > exclude_r.
- **Options:**
  - (a) Record the domain as a declared choice with row counts per condition, and refresh ALGORITHM.md.
  - (b) Enforce the same domain in the calculator.
  - (c) Make MaxR and R_conv share one noise filter, so fewer rows are "beyond" by construction.

### CHO-11  [medium]  The near-blast exclusion radius uses different definitions for the two detonation types

- **Where:**
  - `blastlib/geometry.py:18-28` [clean]
  - `docs/ALGORITHM.md:387-390` [U]
- **Evidence:**
  - det 1 excludes out to the nearest building **corner**: sqrt((b/2)² + (s/2)²).
  - det 2 excludes out to the nearest **face**: s/2. The nearest corner of an intersection is at s/√2, so the difference is 0.21 s, i.e. 1.0-4.1 m for s = 5-20 m.
  - No rationale is given for the asymmetry.
  - Since the working-tree change, the radius also gates Z_urban rows (condition 3 drops 36 pressure and 36 impulse rows).
- **Options:**
  - (a) State the rationale for the asymmetry.
  - (b) Use one rule, corner or face, for both detonation types.

### CHO-12  [medium]  Hard-coded copies of production values have drifted, and several choices are set in more than one place

- **Evidence:**
  - `tools/z_surface_3d/z_surface_3d.py:34-37` [clean]: `COEF` has C0 = 7.778 / 10.060, C1 = −0.576 / −1.157. These are HEAD `final_production_convergence_coefficients_req.csv`, i.e. the hard criterion with the legacy OLS fit. Production `req_soft3` has 9.063 / 11.858 and −0.645 / −1.375, so C0 is 14-15 % low. CLAUDE.md §8 names this trap.
  - `blast_calculator.html:235-252` [clean]: the convergence coefficients match production; the Z_urban coefficients are the HEAD values (CHO-04).
  - `docs/ALGORITHM.md:336-353` and `ALGORITHM_HE.md` [U] carry the HEAD values.
  - The density-switch threshold is defined twice: `A_THRESH = {1: 1.0, 2: 2.0}` at `convergence_models.py:186` [clean] and `LAMBDA_A_THRESH` at `z_urban.py:94` [M].
  - beta is set twice: `PARAMS['softBeta'] = 3.0` and the "3" in `RADIUS_ESTIMATOR['method'] = 'req_soft3'`. The GUI soft panel and `radius_methods` read the former, the pipeline the latter.
  - `n_iter = 500` appears in five places: `run_analysis.py:421, 461, 629`, `cross_validation.py:39`, `gui/specs.py:191` [M].
  - `test_fraction = 0.2` appears in four places and `target_mape = 10` in three.
  - The Z_free floor of 2 is set in `z_urban.py:90`, in the calculator loop and in `diag_estimator.py`.
  - The safe-domain box is copied into the calculator (`SAFE` at `:275`).
- **Options:**
  - (a) Read the values from the CSVs and `constants.py` instead of copying them.
  - (b) Add a test that compares each copy with the production CSV.
  - (c) Keep the copies, but list them in one place that is checked after every re-run.

### CHO-13  [medium]  The density-switch threshold `a` was selected on the data but is described as a fixed geometric constant

- **Where:**
  - `blastlib/regression/convergence_models.py:39-40`: "geometric constant, not fitted (selected by CV from {1, sqrt(2), 2})" [clean]
  - `blastlib/regression/z_urban.py:92-93`: "a geometric constant (street / intersection), never fitted" [M]
  - `docs/ALGORITHM.md:135-137` reads s = a·W^(1/3) as a physical crossover [U]
- **What:** `a` is a hyper-parameter chosen by CV over three values. That is one undisclosed degree of freedom per detonation type in the RadiusP model. Its physical reading ("two venting canyons") came after the selection.
- **Options:**
  - (a) State in the docs that `a` was CV-selected.
  - (b) Include the selection inside the LOGO folds.
  - (c) Justify a = 1 / 2 independently of the data.

### CHO-14  [medium]  The safe-domain box was drawn from the same held-out errors it is quoted to bound

- **Where:**
  - `outputs/check_results/safe_domain_req_soft3.csv` [clean]
  - `docs/ALGORITHM.md:271-308` [U]
  - `blast_calculator.html:258-275` [clean]
- **Evidence:**
  - 38 configurations are inside the box. The 12 with worst LOGO error above 20 % are all outside it. 46 configurations with error ≤ 20 % are also outside.
  - Inside the box: P max 18.9 %, I max 19.6 %; means 7.8 % and 6.4 %. These all reproduce from the CSV.
  - The 20 % threshold and the axis-aligned box (ρ, Π2, H/s) were chosen after the errors were known. "Every held-out prediction below 20 %" is therefore true by construction, not a validation result.
- **Options:**
  - (a) Present the box as descriptive, not as a bound.
  - (b) Derive it with a nested procedure (box chosen without the held-out family).
  - (c) Validate it on new simulations.

### CHO-15  [medium]  The Z_urban functional forms and their bounds cannot be re-validated from the repo

- **Where:**
  - `blastlib/regression/z_urban.py:96-106` (LOGO "range_switch 8.4% vs 9.9% legacy, canyon_trap 9.9% vs 12.3%") and `:402-422` (P0, bounds) [M]
  - `docs/ALGORITHM.md:415-425` (the 10,484-candidate re-search) [U]
  - `docs/PYSR_CONVERGENCE_SEARCH.md` [U]
- **Evidence:**
  - `tools/logo_cv` evaluates RadiusP and RadiusI only. No code in the repo runs `range_switch` or `canyon_trap` under LOGO, and no script or table exists for the 10,484-candidate sample.
  - The quoted LOGO figures predate the working-tree domain change (CHO-04).
  - The B upper bound was moved from 8 to 20 after it bound on `req` (8.33).
  - The sign bounds (C1 ≥ 0, A ≥ 0) impose the "sign story" instead of testing it.
- **Options:**
  - (a) Add a Z_urban LOGO harness and commit its tables.
  - (b) Mark the form-selection numbers as historical, not reproducible.
  - (c) Report fits with the sign bounds released, to show whether the sign story is carried by the data.

### CHO-16  [medium]  The street model's heritage constants cannot be traced to a reproducible fit

- **Where:** `blastlib/street/constants.py:9-21, 38, 74` [clean]
- **What:**
  - `EPK` and `ENV` are "PINNED-HERITAGE — the scripts that fitted them were one-off and never kept".
  - `ENV` f and S were "calibrated against the pre-slope-anchor constants and kept". Under the shipped constants, coverage is 96.34 % against the 95.0 % once documented.
  - The other street constants (FLOOR 1.2, GATE 1.5, X_MAX 1.6, HI_FRAC / LO_FRAC 0.85 / 0.25, SMOOTH_METRES 2.5, RMAX 100 m) carry measured rationales. The file itself flags the window convention as the dominant anchor uncertainty (about 10 % on R_half).

  The documentation is honest; the issue is provenance only.
- **Options:**
  - (a) Accept, stating in the thesis that EPK and ENV are carried constants.
  - (b) Refit them with `fitting.fit_e_peak` and adopt the result.

### CHO-17  [low]  `random_state = 42`: CV medians are insensitive to it; the saved best-split files are not

- **Where:** `blastlib/regression/cross_validation.py:110-111` [M]. This is the only place the seed is set.
- **Evidence:** read-only re-run of the convergence-radius CV on `convergence_table_req_soft3.csv` (500 splits, relwls/quad fits), seeds 42, 0, 1, 2, 3, 7 and 2026:
  - Seed 42 reproduces the recorded medians exactly (conv_P 8.786, conv_I 7.153).
  - Across the seven seeds, conv_P medians span 8.54-8.79 (seed 42 is the highest, so the choice does not flatter the result) and conv_I spans 7.07-7.22.
  - The minimum over splits, which selects the `best_*` files, spans 4.32-5.22 for P.
  - The `final_production_*` coefficients do not depend on the seed.
- **Options:**
  - (a) State the seed spread next to the medians.
  - (b) Keep the `best_*` files labelled as inspection-only, as they already are.

### CHO-18  [low]  `MAX_HEIGHT = 24` affects nothing that is used

- **Where:**
  - `blastlib/constants.py:8` [clean]
  - `blastlib/geometry.py:13-15` [clean]
- **Evidence:**
  - It only feeds the `VolumeDensity` column (ρ·H/24 m). No fit, tool, test or document uses that column (grep over `*.py`, `*.md`, `*.html`).
  - ρ·H/24 m is dimensional, not a Pi group.
- **Options:**
  - (a) Drop the column.
  - (b) Keep it and document it as descriptive only.

### CHO-19  [low]  The solid-cell mask threshold of 1.01 Pa has no stated rationale and a 1 % margin

- **Where:** `blastlib/constants.py:22`: `'thresholdP_kPa': 1.01 / 1000` [clean]
- **Evidence:**
  - Masked cells hold exactly the solver's in-solid value of 0.001 kPa on grids 1 and 3.
  - Grid 2 has unmasked cells at 1.02-1.3 Pa (4 of 4 sampled configurations). The mask therefore sits 1 % above the floor.
  - The comment "mask threshold [kPa]" does not say it is a solid-cell detector.
- **Options:**
  - (a) Document it as a solid-cell detector.
  - (b) Use an explicit solid flag instead.

### CHO-20  [low]  `req` counts the two half-width end sectors at full width

- **Where:**
  - `blastlib/processing/radius_estimator.py:46-55` (end bins 0° and 90° are half-width) and `:134-140` (every bin summed with Δθ = 1°) [clean]
- **Evidence:** `reduce_theta_radii(np.full(91, 10.0), 'req')` returns 10.0554, a +0.55 % bias. It is common-mode across all configurations and absorbed mostly into C0.
- **Options:**
  - (a) Weight the end bins by 0.5.
  - (b) Accept and document the bias.

### CHO-21  [low]  Stale or incorrect rationale text

- `constants.py:65-68`: "a phase-1 run under this default reads data/processed_npz_v2". The working-tree default is the v3 raw store (`paths.default_npz_dir`).
- `radius_estimator.py:161-162`: "'req_soft' with PARAMS softBeta 6.0 -> 'req_soft6'". softBeta is now 3.0.
- `soft_criterion.py:22-24`: "Requires the v2 NPZ superset".
- `z_urban.py:241-243`: says condition 3 is skipped (see CHO-10).
- `docs/PHYSICS_ANALYSIS_HE.md:43, 64, 643` quote hard-criterion values as current: Z_conv,P ≈ 7.5 (the production median is 8.99) and C0 = 7.78 (production 9.063).
- `docs/PARAMETER_STUDY_HE.md:90-92` reads W's 20.4 % variance share of Z_conv,P as the non-Hopkinson residual ("if Hopkinson were exact, W would explain 0%"). With s, b and H held in metres, changing W changes Π2 = s/W^(1/3) and H/W^(1/3), so a non-zero W share is expected even under exact Hopkinson scaling. Forward to the physics lens.

### CHO-22  [info]  Evaluation choices

- Z_urban MAPE is pooled over rows (`cross_validation.py` → `z_urban.evaluate_z_urban`), so a configuration contributes between 1 and about 9 rows.
- CV splits are stratified on det only (`cross_validation.py:93-94`); the code and ALGORITHM.md disclose that this is close to in-sample for geometry.
- `target_mape = 10` only counts "successes".
- The `best_*` coefficients come from a minimum over splits and are labelled inspection-only.

All are declared; they are listed here for completeness.

### CHO-23  [info]  The Z_free scan is fixed to the integers 1-20

- **Where:** `run_analysis.py:305`: `for z_val in range(1, 21)`.
- This is set by `free_field_data.csv`. In practice the fit sees 7-9 levels per configuration (Z_free = 2 to about 10). The resolution of the Λ(Z_free) curve is therefore one unit of Z.

## Checked and found consistent

- The `soft_beta_selection.csv` gaps and median inflations regenerate exactly from `convergence_table_req_soft{2,3,4,6,8,12}.csv` and `convergence_table_req.csv`.
- The LOGO values quoted in the note and ALGORITHM.md (soft3: 8.43 / 5.67 / 18.65 / 30.07; hard: 8.19 / 40.38) match `logo_summary_req*_relwls_quad.csv`.
- The impulse rows and RadiusI coefficients are identical across `req`, `req_soft2`, `req_soft3` and `req_soft4`: the soft criterion leaves impulse untouched.
- The raw store plus current code reproduces `convergence_table_req.csv` `RadiusP` exactly for 16 of 16 sampled configurations.
- The HEAD `final_production_z_urban` pressure coefficients (B 4.012 / 1.182) are reproduced exactly by the HEAD table with the HEAD mask.
- Seed 42 reproduces the `cv_summary_req_soft3.csv` conv_P / conv_I medians (8.786 / 7.153).
- `random_state` and `thr_I_scaled` each have exactly one definition. `process_grids` reads `IMPULSE_CRITERION`, and `PARAMS` holds no copy.
- One estimator is resolved once in `run_phase1` and passed to both radii.
- The Hopkinson spread of free-field scaled impulse is 1.004-1.043 (constants.py says "1.01-1.04"). The free-field pressure mean CV is 4.77 % (grids.py says "4.7%").
- The impulse band at the measured radius is 84.7 % (constants.py says "~83%").
- Impulse units: Pa·s (raw_store) divided by kg^(1/3), consistent with `thr_I_scaled` in Pa·s/kg^(1/3).
- The safe-domain counts and error maxima and means reproduce from the CSV.
- The pressure reference anisotropy is about 9.7 % median, diagonal against axis (claimed 9.6 %).
- The per-direction level falls back to the CSV scalar only rarely (0.03 % on 12 configurations).

## Not checked

- **Thesis chapter, proposal and compare_v6:** off limits.
- **Tests:** not run. `pytest` is not installed in the only working interpreter (Python 3.12, WindowsApps), and the 3.14 launcher entry is broken. Anchor-test status is therefore unknown.
- **Byte-for-byte regeneration:** I did not run the production pipeline, so I could not verify that the working-tree code regenerates the working-tree tables. Only the Z_urban pressure coefficients were reproduced, by refit. The impulse-coefficient change was not attributed.
- **Studies with no artefact in the repo:**
  - the mesh-coarsening study (−9.1 % / −18.2 %);
  - the p_thr elasticity of −0.6;
  - the minPressure sweep;
  - the thr_I ≈ 7 test;
  - the 10,484-candidate Z_urban search;
  - the Z_urban LOGO figures.
- **Physics:** why grid-2 values inside the grid-1 domain look like stage-local peaks (CHO-09). Referred to the physics lens.
- **Street model:** reviewed at the level of stated rationale only; parity suite not re-run.
- **GUI:** reviewed only for duplicated defaults.
- **Standards:** no `docs/references/INDEX.md`, so no standard could be checked.
- **Side effect:** some early read-only probes ran without `PYTHONDONTWRITEBYTECODE` and may have refreshed gitignored `__pycache__` bytecode. No tracked file changed, and no untracked file other than this report was added by this audit. `docs/audit/2026-09-27/statistics.md` and `reproducibility.md` come from other reviewers.
