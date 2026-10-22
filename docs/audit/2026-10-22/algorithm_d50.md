# Audit: algorithm — pre-commit, D50 chain-identity change  (2026-10-22, commit 54ff394, dirty tree = the audited change)

Scope: the uncommitted D50 change only — `blastlib/regression/z_urban.py::clip_z_urban_pred`
(identity at the predicted R_conv, `return_flags`), its callers (`evaluate_z_urban`,
`evaluate_z_urban_deployable`, `cross_validation` via the evaluators, `blastlib/regression/plots.py`,
`tools/logo_cv`, `tools/config_summary`, `tools/pressure_report`, `tools/check_formulas`),
the edited paragraph of `docs/ALGORITHM.md` / `docs/ALGORITHM_HE.md`, the `blast_calculator.html`
wording, the pinned `docs/audit/2026-10-22/clip_sensitivity/clip_sensitivity.py`,
`tests/test_clip_chain.py`, and the moved result files
(`logo_cv/logo_summary_*_zurban.csv`, `cv_summary_reqdir91_soft3.csv`). Everything else: not re-checked.

Documents read: CLAUDE.md; docs/DECISIONS.md D3, D9, D11, D15, D16, D48, D49, D50, D51;
docs/ALGORITHM.md and ALGORITHM_HE.md (edited paragraph + the surrounding validation and
"Why the algorithm is sound" sections); prev_audit docs/audit/2026-09-27/ (algorithm.md,
SUMMARY.md, statistics.md STA-02/STA-03); the full working-tree diff.

Tests: `python -m pytest -q -m "not slow"` — **180 passed, 0 skipped, 6 deselected (slow)**,
including the new `tests/test_clip_chain.py`. Anchor tests ran (no data skips).

## Carry-over from 2026-09-27 (limited to findings this change touches)

| old id | status | evidence (file:line / number) | decision (D#) |
|---|---|---|---|
| ALG-02 (high) | partially | The edited closure paragraph now quotes current reqdir91_soft3/D49 numbers (all verified below), but the adjacent validation section in BOTH languages still quotes an earlier state: ALGORITHM.md:391-393,400-402 and ALGORITHM_HE.md:323-331 say conv median 9.8/8.3, Z_urban 8.7/8.9, deployable 8.7/11.3 — today's `cv_summary_reqdir91_soft3.csv` medians are conv 9.622/6.855, z 8.372/6.106, dep 8.229/9.226. EN = HE (both stale the same way). | D1 (state of record) resolved earlier; staleness continues |
| ALG-03 (high) | superseded-by-decision | The refuted claim ("comparable by construction ... cannot drift apart") is gone: ALGORITHM.md:352-359 now says the per-sector criteria differ by design, MaxR overshoots systematically, "the closure is imposed, not assumed" — matching z_urban.py:590-598. The outcome-dependent conditional filter itself remains (z_urban.py:227-236), per D3 (a)+(b) in force; D49 closed the clip question under a pre-registered rule; D50 aligned the grading with the user chain. | D3, D49, D50 |
| ALG-14 (medium) | open | blast_calculator.html:230-264 still hard-codes `req_soft3` coefficients ("regenerated 2026-09-28/29"); production is `reqdir91_soft3` since 2026-10-21 (CLAUDE.md §3, D15). The newly reworded tab-2 note therefore wraps numbers from a superseded run. `z_surface_3d` not re-checked today. | D16 (undocumented) |
| ALG-18 (low) | partially | The item this change touches: the stale "AND amplification — the fit domain" comment persists at tools/check_formulas/check_formulas.py:575 (file edited by this change; the amplification condition left the domain long ago). Other ALG-18 items not re-checked. | — |
| ALG-19 (low) | superseded-by-decision | `z_P_dep`/`z_I_dep` on record (cross_validation.py:191-199; cv_summary columns); ALGORITHM.md:396-404 states the conditionality of z_P/z_I. D50 additionally grades conditional rows with R_free ≥ R̂_conv against Z_free — the user chain. | D3, D50 |
| STA-02 (high) | superseded-by-decision | Same evidence as ALG-19; the fit domain still uses the measured target (z_urban_valid_mask conditions 1-2), which D3 (in force) chose to keep with the deployable yardstick alongside. | D3 |
| STA-03 (high) | partially | ALGORITHM.md:405-409 now says the best-split MAPE "must never be quoted as accuracy" and `best_*` are "for inspection only". But `tools/check_formulas` (edited today) still scores the best split and writes `validation_comparison_*` under a validation name (check_formulas.py:1-8); D11 is still open, no decision. | D11 (open) |
| CHO-10 (medium) | partially | Tab 2 of the calculator now matches the documented chain and boundary convention (blast_calculator.html:504-509: identity at Zf >= Zc, clip inside — verified against clip_z_urban_pred). Tab 1 (`oneRow`, :405-413) is still min-only with no identity, and its note (:152-157) keeps the old framing; recorded open in D50. | D50 (open item), D17 (open) |

Counts: resolved 0 · open 1 · partially 4 · superseded-by-decision 3 · regressed 0.
Other 2026-09-27 findings (ALG-01, ALG-04..ALG-17, ALG-20, and the other lenses): **not re-checked** in this pre-commit audit.

## Summary

The change implements exactly what D50 records: `clip_z_urban_pred` returns Z_free where
R_free >= the predicted R_conv (inclusive boundary), keeps min(pred, Z_conv_hat) strictly inside,
and every caller — both evaluators, CV, LOGO (with its per-fold gate), plots, config_summary,
pressure_report, check_formulas — goes through the one central function. The moved result files
match D50's quoted numbers to the digit (25 changed conditional predictions = 16 P + 9 I, all now
equal to Z_free; MAPE 8.773→8.454 / 6.749→6.679; cv_summary 450/279/96 changed splits, medians
8.706→8.372, 6.188→6.106, 9.760→9.701, <10% 283→290, best split 79 unchanged; pressure_report
8.26→7.99 with flags 52→37 over 15 changed rows — all independently recomputed). check_formulas'
`{det: coef}` conversion is correct for every kind the suffixed CSVs carry (additive, power,
unified), and its local R_conv predictor agrees with the library to 0.0 on both production and
best CSVs. What remains doubtful is wording, not arithmetic: one misquoted digit in the register
(RMSE 6.89 vs the table's 6.88, ALG-21), a wording sweep that missed README, run_analysis,
config_curve, output.py and two docstrings which still carry the pre-D49 "beyond R_conv the urban
field IS the free field / no urban information" claim (ALG-22), and the register's statement that
the calculator "is now worded" per D49 when only tab 2 was (ALG-23). **No finding blocks the
commit**; ALG-21 is the one defect inside the diff itself worth correcting at commit time.

## Findings

### ALG-21  [low]  The register (this diff) quotes RMSE 6.89 m; the table of record says 6.88
- Carry: new
- Where: docs/DECISIONS.md:823 (D48, "RMSE 6.89 [6.09, 7.68]") and :927 (D50, "RMSE 7.32 → 6.89 מ'") — both lines are added by this uncommitted change; `outputs/check_results/logo_summary_reqdir91_soft3_relwls_quad_zurban.csv`, row P/pooled.
- What: the post-D50 pressure-conditional RMSE on R_urban is RMSE_Rurban_m = 6.884546, which rounds to **6.88**, not 6.89. Every other number quoted in the D48/D50 entries reproduces exactly (MAPE 8.45 [7.67, 9.27], R² 0.934 [0.918, 0.946], MAE 5.32 [4.69, 6.02], max 41.48→28.34, impulse 6.68 [5.72, 7.60], the pre-D50 values 8.77/0.925/7.32/5.53, and all cv_summary movements).
- Evidence: recomputed the summary row from the working-tree CSV and the old one via `git show HEAD:`; 6.884546 vs the quoted 6.89.
- Consequence: the decision register is the source for thesis text; CLAUDE.md §6 requires numbers copied from actual output.
- Options: (a) correct both lines to 6.88 before committing; (b) quote three decimals (6.885); (c) leave and note the rounding convention.

### ALG-22  [medium]  The D50 wording sweep missed five places that still state the pre-D49 claim ("beyond R_conv the urban field is the free field / the rows carry no urban information")
- Carry: new (consequence of D49/D50; the sentences themselves predate the change)
- Where:
  - README.md:155-157 — "rows at or outside the convergence radius. Those rows carry no urban information";
  - run_analysis.py:381-382 — "'Beyond' = at or outside the convergence radius, where the urban field is the free field and the row carries no urban information";
  - tools/config_curve/config_curve.py:262-266 — "beyond it the urban field IS the free field, so the row carries no urban information";
  - blastlib/regression/output.py:300 — prints "Physical closure: predictions clipped from ABOVE at Z_conv only" (D49 reframed it as an ENGINEERING closure; the next line already says "identity beyond Z_conv");
  - blastlib/regression/z_urban.py:784-787 (evaluate_z_urban docstring) and cross_validation.py:185-186 — describe the chain as clip-only, no identity branch, in the very file/path the change rewrites.
- What: D49 (in force) records that R_conv is NOT where the urban effect vanishes and that the measured reach exceeds R_conv in 385 of 1110 deployable impulse rows — those rows carry measured urban information and were used as data in the D49 comparison. The five texts above still assert the opposite, while z_urban.py's module comment, the clip docstring, ALGORITHM.md/HE and the calculator tab-2 note were all updated.
- Evidence: grep for "is the free field / no urban information / Physical closure" across the repo (hits above); the updated texts quoted in the diff; D49 anchors at docs/DECISIONS.md:844-845.
- Consequence: README is the operating manual and config_curve/README sentences are the kind of text a thesis paragraph gets written from; they restate a claim D49 refuted. Numbers are unaffected.
- Options: (a) extend the wording sweep to these five places in the same commit; (b) record in D50 that the sweep covered only the named files and list the leftovers; (c) leave code comments and fix only README.

### ALG-23  [low]  D50's claim that the calculator "is now worded" per D49 holds only for tab 2; tab 1 still shows the pre-D50 chain beyond R̂_conv
- Carry: new (the tab-1 LOGIC gap itself is recorded open in D50 and is not re-raised)
- Where: docs/DECISIONS.md:922 ("`blast_calculator.html` מנוסחים עכשיו כך...  בדף המחשבון שונה רק הנוסח"); blast_calculator.html:152-157 (tab-1 note, unchanged: "clip = נחתך לרדיוס ההתכנסות", no engineering-approximation framing), :405-413 (`oneRow`, min-only), :428-442 (`buildTable` iterates Zf = 2..ceil(max(ZcP, ZcI)), so tab 1 DISPLAYS rows at and beyond R̂_conv with min(Λ·Zf, Zc) marked "clip").
- What: only tab 2's note (:217-223) and calcQ comments were reworded. At the same inputs, tab 1's Z-table and tab 2's answer disagree wherever Zf >= Zc (tab 1: Zc flagged clip; tab 2: Zf, identity) — exactly the row range tab 1's table always reaches, since it runs to ceil of the larger Zc.
- Evidence: the diff touches only the tab-2 note and calcQ strings; oneRow/buildTable and the tab-1 note are byte-identical to HEAD.
- Consequence: the register entry overstates the sweep; a reader of D50 would believe the calculator text is consistent. The numeric inconsistency between tabs is the open D50 item, for the owner.
- Options: (a) narrow the D50 sentence to "the tab-2 note"; (b) also reword the tab-1 note now (wording only, no logic); (c) decide the tab-1 logic (the open D50 item) and update both together.

### ALG-24  [low]  "385 of 1110" counts the raw reach; the published MaxR_I column gives 394
- Carry: new
- Where: blastlib/regression/z_urban.py:81-82 and :595-596; docs/ALGORITHM.md:341-342; docs/ALGORITHM_HE.md:284; docs/DECISIONS.md D49:837.
- What: all four say "the measured MaxR exceeds R_conv in 385 of 1110 deployable impulse rows". 385 is the count on `MaxR_I_raw` (the raw reach, which defines `beyond_I` — run_analysis.py:360-362, 387-388). On the reported `MaxR_I` column (Λ_dir·R_free — the value the tables publish and the model fits) the count is **394**/1110. None of the texts says "raw".
- Evidence: recomputed from `logo_cv_..._zurban_deploy.csv` ⋈ `max_radius_per_Z_reqdir91_soft3.csv` ⋈ `convergence_table_reqdir91_soft3.csv`: MaxR_I_raw >= RadiusI in 385 rows, MaxR_I >= RadiusI in 394 rows.
- Consequence: a reader reproducing the sentence from the published columns gets 394 and concludes the record is wrong. Nothing numeric depends on it.
- Options: (a) add "(raw reach, the beyond_I flag)" wherever 385 is quoted; (b) quote both numbers once in ALGORITHM; (c) leave, since D49's script defines the count.

### ALG-25  [low]  The rewritten closure paragraph is silent on the known pressure discontinuity at R̂_conv (D51)
- Carry: new; relates to D51 (open, documented-only by the owner) — not a challenge to it
- Where: docs/ALGORITHM.md:336-345 and ALGORITHM_HE.md:279-287 (the paragraph this change rewrote); blastlib/regression/z_urban.py:571-598 (docstring); the behaviour itself is asserted by tests/test_clip_chain.py::test_attenuating_prediction_is_kept_inside_and_identity_beyond (out jumps 0.8·Z_conv → Z_conv across the boundary).
- What: the paragraph presents the chain (clip inside, identity at/beyond) as the final closure but does not mention that for Λ_P(Z_conv) < 1 the pressure chain jumps upward at R̂_conv — up to +6.3% in 10 of 96 production configs (D51). D49's anchors (docs/DECISIONS.md:842) list continuity as mandatory; D51 records the exception and defers the decision.
- Evidence: D51 entry (DECISIONS.md:941-950); the new test demonstrates the jump; the code has no continuity treatment (z_urban.py:633-636).
- Consequence: a chapter paragraph written from this doc section would describe the chain as closed without the one known discontinuity; a referee comparing to the D49 continuity anchor will ask.
- Options: (a) add one sentence + a D51 pointer to the paragraph (both languages together); (b) resolve D51 first and document the outcome; (c) leave it in DECISIONS only, accepting the doc/thesis gap.

## Checked and found consistent

- `clip_z_urban_pred` implements exactly the documented chain: min(pred, R̂_conv/W^⅓) where R_free < R̂_conv, Z_free where R_free >= R̂_conv (inclusive); no-op when coefficients are missing or R̂_conv is not finite; `return_flags` gives (out, real-clip, identity) with clipped ∩ identity = ∅ (z_urban.py:609-640; tests pass).
- Boundary convention is the same everywhere it appears: clip identity `r_free >= Rconv` (:635); calculator tab 2 `Zf >= Zc` (blast_calculator.html:504); the deployable domain uses strict `r_free < Rconv_pred` (z_urban.py:905, logo_cv.py:165) so identity rows never enter it — consistent with D50's "deployable contains no such rows". R_free is written by Phase 1 as exactly Z·W^⅓ (run_analysis.py:337,403).
- Every Z_urban prediction site pairs with the central clip: evaluate_z_urban (:824), evaluate_z_urban_deployable (:926), cross_validation via the evaluators (:191,199), plots.py:143, logo_cv.py:225 (plus its per-fold gate against the evaluators, rtol 1e-9), config_summary.py:138, pressure_report.py:210, check_formulas.py:598/602. No remaining local min() clip outside the pinned audit script.
- check_formulas conversion `{d: c for (d,t),c ...}`: additive dicts carry C0/C1/C2/C3/a for `predict_pi`; power dicts (A,p,q,r,r2) and unified dicts (A,C1..C5) dispatch correctly in `predict_impulse` ('C1' in coef). All suffixed coefficient CSVs on disk carry only additive+power. Local `predict_convergence_radius` ≡ library `predict_pi`/`predict_impulse` to max|Δ| = 0.0 over 96 configs on both production and best reqdir91_soft3 CSVs. A mis-kinded dict fails loudly (KeyError), never silently; the legacy unsuffixed CSVs' 'log' kind crashes at load and is unreachable through the CLI (every method token suffixes the filename).
- `clipped_at_Zconv` in both tools is the real-clip flag only; identity rows are unflagged, and both READMEs/headers say so (config_summary.py:152-161,386-397; pressure_report.py:16-21,215-217). Replicating pressure_report: flags 52→37, MAPE 8.26→7.99, 15 rows changed — equals D50.
- Changed result files match D50 exactly: conditional LOGO detail — 25 predictions changed (16 P, 9 I), all now == Z_free, actuals and row set unchanged (1154 rows); summary — P 8.773→8.454 [7.667, 9.271], max 41.48→28.34, R²(R_urban) 0.925→0.934, I 6.749→6.679; R²(Z_urban)/R²(Λ) P 0.897/0.445, I 0.925/0.687. cv_summary — z_P changed in 450 splits (median 8.706→8.372), z_I in 279 (6.188→6.106), worst in 96 (9.760→9.701), splits <10%: 283→290, best split 79 with worst 7.092 unchanged, split-79 z_P = 6.5035 = the "6.50%" D50 quotes for check_formulas. Deployable LOGO files, final_production_*, best_* identical da83d66→HEAD→working tree at the git-blob level (earlier byte diffs were CRLF checkout artefacts, REP-11).
- D49 numbers quoted in z_urban.py and both ALGORITHM docs reproduce from the pinned `clip_sensitivity/rows.csv`: deployable impulse clip 9.88% vs 7.51% without; above the floor (Z_free ≤ 11, 644 rows) 6.31% vs 6.40%; below (466 rows) 14.82% vs 9.05%; bias −5.46% vs +0.26%; and from today's tables: 1110 rows, 644/466 split, 6.31/14.82 with the clip.
- ALGORITHM.md and ALGORITHM_HE.md: the edited paragraph is sentence-for-sentence and number-for-number equivalent; neither is ahead of the other.
- The pinned `clip_sensitivity.py` carries a verbatim copy of the pre-D50 clip and reads the da83d66 LOGO files via `git show`; its gate inputs at da83d66 are confirmed identical to HEAD for the deployable file it checks.
- `tests/test_clip_chain.py` covers the boundary (just-inside / on / just-beyond), both Λ > 1 and Λ < 1, flag exclusivity, the R_free-recompute fallback and the no-coefficients no-op; the Λ < 1 case pins the D51 jump as current behaviour.
- Nothing in the change moves formulas, coefficients, domains or splits (D50's "לא שונו"): final_production_*, best_*, convergence tables and the deployable records are untouched.

## Not checked

- Running `clip_sensitivity.py` and `d49_compare.py` end-to-end (both write their outputs inside the repo, which this audit must not do); their key numbers were instead reproduced from the pinned `rows.csv` and today's tables.
- A Phase 1 / Phase 2 rerun (production pipeline forbidden for this audit); the updated `cv_summary` is taken as the owner's recorded 500-split run and checked for internal consistency only.
- The 'unified' loader branch numerically (no suffixed CSV on disk currently carries it; verified by reading only).
- `tools/z_surface_3d` (hard-coded coefficients, ALG-14) and all 2026-09-27 findings outside the carry-over table.
- The thesis chapter (no path provided); `compare_v6` and everything outside the repo (CLAUDE.md §1.7).
- blast_calculator tab-1 numerical behaviour beyond confirming it is unchanged (the D50 open item is the owner's).
