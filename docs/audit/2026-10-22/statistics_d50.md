# Audit: statistics  (2026-10-22, commit 54ff394, tree dirty = the D50 change)

Pre-commit review of one uncommitted change (D50): `clip_z_urban_pred`
(`blastlib/regression/z_urban.py`) returns Z_free where R_free >= the
*predicted* R_conv, else min(pred, Z_conv_hat); `return_flags` added; the three
tools aligned to the central function; docs reworded (D49 framing); the three
regenerated results of record (`cv_summary_reqdir91_soft3.csv`, the
conditional LOGO detail and summary); `tests/test_clip_chain.py` (untracked);
`clip_sensitivity.py` pinned to the D49 record; DECISIONS D50 closed and D51
opened. Findings only; no file other than this one was written. Probes ran
read-only from the repo root; `git status` after the audit equals the status
at the start plus this report.

Fast tests: `python -m pytest -q -m "not slow"` → **180 passed, 6 deselected,
0 skipped** (anchor tests ran; includes the new `tests/test_clip_chain.py`).

## Carry-over from 2026-09-27 (and the 2026-10-22 statistics lens for STA-14/15)

Limited, as instructed, to the old findings this change touches. **STA-04
through STA-11 and STA-13 were not re-checked and keep no status here.**
Statuses below are from today's code and tables, not from the register.

| old id | status | evidence (file:line / number) | decision (D#) |
|---|---|---|---|
| STA-01 | open | D5 undecided (`docs/DECISIONS.md:122-133`, "ההכרעה: לא התקבלה"). This change selects nothing new: the best split is invariant (argmin `worst` = iteration 79 in both old and new `cv_summary`, worst 7.0924 identical to the last digit), `best_*` absent from `git status`. The conditional headline 8.45/6.68 remains a post-selection estimate exactly as before. | D5 open |
| STA-02 | superseded-by-decision | D3 (a+b) and D46 in force. The conditional domain is still chosen by the measured target and measured R_conv (`z_urban_valid_mask` untouched by this diff; `evaluate_z_urban` at `z_urban.py:808-809`), reported beside the deployable numbers. D50 operates *inside* that decided domain and reduces the evaluator-vs-chain mismatch the finding's option (d) pointed at. No new evidence against D3. | D3, D46 in force |
| STA-03 | open | D11 undecided. `tools/check_formulas` still rests on the best split; D50 itself quotes a best-split number ("חלוקה 79: 6.57% → 6.50%"), correctly matching `cv_summary` row 79 (z_P 6.5658 → 6.5035) but still subject to the D11/HANDOFF caveat (never quote as accuracy). This change keeps selection mechanics clean: z_*_dep and the new flags stay out of `worst`; `worst == max(conv_P, conv_I, z_P, z_I)` verified on all 500 new rows. | D11 open |
| STA-12 | partially | Unchanged by this change (relwls described as "the same quantity (MAPE)", CV medians without MC error). The changed medians quoted in D50 verified below. | D18 (not documented) |
| STA-14 | open | The `Mean_CI95` columns were recomputed on the re-graded predictions (P conditional now [7.667, 9.271]) and D48 quotes them bare; no document states the CI is conditional on the model selection of STA-01. Nothing in this diff addresses it. | D12 open |
| STA-15 | superseded-by-decision | D47 in force: R² on R [m] is the primary metric with the W^(1/3)-scaling caveat required beside it; R² on Z/Λ diagnostic. The working-tree D48 entry carries both views (R² on Z_urban/Λ updated with old values in parentheses) and repeats the scaling caveat in הסתייגויות — the condition of D47 is met in the register; thesis text pending. | D47, D48 in force |

Counts: 0 resolved, 3 open (STA-01, STA-03, STA-14), 1 partially (STA-12),
2 superseded-by-decision (STA-02, STA-15), 0 regressed. Not re-checked: 8.

## Summary

Answers to the five questions asked for this review:

1. **No leakage.** The identity decision uses only quantities known before the
   answer: `identity = isfinite(Rconv) & (r_free >= Rconv)`
   (`z_urban.py:632-636`), where `Rconv` is the *predicted* radius from the
   fold's own convergence fit (CV: `cross_validation.py:151-154` fits on
   `train_conv`, passes `conv_P_coeffs`/`conv_I_coeffs` into
   `evaluate_z_urban`; LOGO: `logo_cv.py::run_logo_zurban`, `cP = fit_p(train_c)`)
   and `r_free` is the deterministic input Z_free·W^(1/3). The measured R_conv
   and the measured target enter only the (decided, D3) row selection, exactly
   as before this change. The fit is untouched: the clip/identity is
   prediction-time only, `z_urban_valid_mask` is not in the diff, and
   `final_production_*`, `best_*` and all deployable/conv LOGO files are
   absent from `git status` (byte-identical).

2. **A legitimate evaluation change — but the improvement is mechanical.**
   The old conditional evaluator graded, on x ≥ 1 rows, a value
   (Z_conv_hat) that no deployed caller returns: the calculator's tab 2,
   `config_summary`, `pressure_report` and `check_formulas` all return
   Z_free there. Grading what the chain returns is the correct convention
   (and the same convention the deployable evaluator has used since D3).
   The improvement is guaranteed by construction on this data: on every
   re-graded row Z_conv_hat <= Z_free < Actual (probe: Actual > Z_free on
   25/25 LOGO rows; across all 500 CV splits z_P and z_I decreased or stayed
   equal, never increased), so replacing Z_conv_hat by Z_free can only lower
   the error. The direction was known before the ruling (D50's scope section
   quotes the post-change numbers computed under D49). That makes
   8.773 → 8.454 a re-grading of the same model, not a model improvement —
   see STA-17 for the reading guard. The coefficients, splits and domain are
   unchanged, both old and new numbers are on the record, and the one
   alternative (grading the model's shape inside measured R_conv) was
   explicitly weighed in D50. Not blocking.

3. **Every number in D50 and the updated D48 reproduces** from the
   working-tree files against `git show HEAD:<file>` (full list under
   "Checked and found consistent"): the 25 changed predictions (16 P in 10
   configs, 9 I in 5 configs, all exactly Z_free), 8.773 → 8.454
   [7.667, 9.271], max 41.48 → 28.34, R² 0.925 → 0.934, RMSE 7.32 → 6.89,
   MAE 5.53 → 5.32, I 6.749 → 6.679 [5.718, 7.597], the R²-on-Z_urban/Λ
   pairs, the per-column change counts (450/279/96), the medians and IQRs,
   283 → 290 splits under 10%, best split 79 with worst 7.0924, the
   `pressure_report` triple (15 rows, 8.26 → 7.99, 52 → 37 flags, by
   read-only recomputation), and the D51 boundary counts (LOGO 8/96 min
   0.944; production 10/96 min 0.941).

4. **Best-split selection does not change in any way that matters.** `worst`
   moved in 96 of 500 splits, always downward (max decrease 0.76 pp, zero
   increases), the argmin stays at iteration 79 with an identical worst
   (7.0924 — driven by a column other than z_P there), and since fitting is
   untouched the `best_*` files are byte-identical (not in `git status`).
   The new flags and z_*_dep remain outside `worst`.

5. **The D48/D50 reporting is honest** — old and new side by side, "מאז
   D50 / לפני D50", the deployable invariance stated and true. Two reading
   risks remain: the calculator's first tab still implements the pre-D50
   chain (STA-16, recorded as open in D50 itself), and the conditional delta
   must not be presented as a model improvement (STA-17).

New findings: **0 high, 1 medium, 1 low.** **Nothing here blocks the
commit** — STA-16 is recorded inside D50 as a known open remainder, and
STA-17 is a quoting discipline for the thesis.

## Findings

### STA-16  [medium]  The calculator's first tab still runs the pre-D50 chain, so the quoted conditional accuracy grades a chain one deployed surface does not implement

- Carry: new (follows the STA-02/D3 → D50 line; the gap is recorded in D50's
  "נותר פתוח").
- **Where.** `blast_calculator.html:405-413` (`oneRow`): tab 1 (single point
  and the Z table).
- **What.** `oneRow` returns `min(Λ·Z_free, Z_conv)` with no identity branch:
  for Z_free >= Z_conv_hat it answers Z_conv_hat and marks it `clip`. Tab 2
  (`calcQ`, `:501-516`) and the library implement the D50 identity
  (Z_free). The reworded note in tab 2 and the new ALGORITHM text describe
  the identity convention as *the* chain, and the conditional numbers of
  record (P 8.45, I 6.68) now grade that chain — on exactly the rows where
  tab 1 answers differently. On those rows the tab-1 behaviour carries the
  error the evaluator used to report: 21.61% (P) against 13.19% for the
  identity (LOGO, `docs/audit/2026-10-22/clip_sensitivity/rows.csv`).
- **Evidence.**
  ```
  // blast_calculator.html:405-413 (tab 1 — unchanged by this diff)
  let zuP=P.lam*Zf, clipP=false;
  if(zuP>ZcP){zuP=ZcP;clipP=true;}
  ```
  against `calcQ` (tab 2): `if(Zf>=Zc){ zu=Zf; ident=true; }`. D50:
  "נותר פתוח: ... הפונקציה `oneRow` ... עדיין מחזירה min(Λ·Z_free, Z_conv) גם
  כש־Z_free ≥ Z_conv ... לא תוקן, כי האישור היה לנוסח בלבד."
- **Consequence.** Until fixed, a thesis figure or a reader's check built
  from tab 1's Z table in the Z_free >= Z_conv_hat region will not match the
  quoted conditional accuracy, and the tab's own note (which now claims the
  free-field convention) misdescribes what that tab computes there. The gap
  is bounded: it affects only rows at or beyond the predicted R_conv, and the
  difference per row is Z_free − Z_conv_hat (up to ~26% of Z_free on the 25
  LOGO rows).
- **Options.** (a) Apply the identity in `oneRow` (same two lines as
  `calcQ`); JavaScript only, no pipeline rerun, no number of record moves.
  (b) Until then, mark tab-1 rows at Z_free >= Z_conv as "free field
  (pre-D50 convention)" in the table. (c) At minimum, keep D50's "נותר פתוח"
  wording in any thesis text that cites the calculator. Cost: text/JS only.

### STA-17  [low]  The conditional improvement is by construction and was known before the ruling; quote it as a re-grading, never as a model improvement

- Carry: new (reading guard on the STA-02/D3 conditional metric).
- **Where.** `docs/DECISIONS.md` D48 (lines 823-827) and D50 ("מה זז");
  any thesis sentence that will cite the conditional MAPE/R² history.
- **What.** On every re-graded row, Z_conv_hat <= Z_free (that is what
  x >= 1 means) and the measured Z_urban exceeds Z_free, so replacing
  Z_conv_hat by Z_free can only shrink the error. Nothing about the model
  got better: the same coefficients, the same splits, the same rows. The
  post-change numbers were computed (under D49) before D50 was decided, so
  the decision was taken knowing the headline improves — acceptable here
  because the stated criterion is consistency with the deployed chain, the
  deployable (a-priori) numbers are untouched, and both old and new values
  are preserved; but the sequence must not be read as validation gain.
- **Evidence.** Probe on the LOGO detail diff: Actual > Z_free on 25/25
  changed rows; old pred < Z_free on 25/25. Probe on `cv_summary`:
  z_P delta in [−1.625, 0.000] with 0 increases over 500 splits; z_I delta
  in [−1.037, 0.000] with 0 increases. Residual bias on the re-graded rows
  after the change: P −13.19%, I −6.90% (under-prediction of R_urban — the
  non-conservative direction for a safety distance), already recorded in
  D50's scope table.
- **Consequence.** A reader comparing "8.77 (older text) vs 8.45 (thesis)"
  without the D50 context would infer progress in the model. And the 8.45
  now *contains* 16 rows where the chain's answer is a known systematic
  under-prediction (−13.2% mean) — the same caveat D49 attached to the
  impulse clip below the relevance floor applies to these pressure rows.
- **Options.** (a) Wherever the conditional numbers appear with a history,
  one sentence: "the 2026-10-22 change re-graded 25 rows against the chain's
  actual output (Z_free); the model is unchanged." Cost: text. (b) Report
  the conditional MAPE with and without the 25 identity rows as a
  sensitivity line (P 8.45 vs 8.27 on the 406 non-identity rows — seconds
  from the detail CSV). (c) Nothing in the code needs to move.

### STA-01  [high]  (carry, open)  Structure, variants and β chosen on the reported LOGO folds

- Carry: continues STA-01 (open). What/Consequence/Options: the 2026-09-27
  report §STA-01 and D5, unchanged. Today's relevance: the re-graded
  conditional numbers (8.45/6.68) inherit the same post-selection status as
  the numbers they replace; the recomputed CIs remain conditional on that
  selection (STA-14).
- Where today: `tools/logo_cv/logo_cv.py` unchanged in role; D5 "פתוח" in
  `docs/DECISIONS.md:122-133`.

### STA-03  [high]  (carry, open)  Best-split artefacts labelled and consumed as validation

- Carry: continues STA-03 (open); D11 open. What/Consequence/Options: the
  2026-09-27 report §STA-03.
- Where today: `tools/check_formulas/check_formulas.py` still reports on the
  best split; D50 quotes its 6.57% → 6.50% (correct against `cv_summary`
  row 79, z_P 6.565842 → 6.503493) — a best-split figure that keeps the
  "never quote as accuracy" restriction.
- Positive note: this change leaves selection intact — argmin 79 old and
  new, worst 7.0924 identical, `best_*` and `best_test_configs` byte-identical
  (absent from `git status`), new columns and flags outside `worst`.

### STA-12  [low]  (carry, partially)  Metric definition and aggregation

- Carry: continues STA-12 (partially). Unchanged by this change; the D50
  entry quotes the moved medians/IQRs correctly (verified below). Options:
  2026-09-27 report §STA-12.

### STA-14  [low]  (carry, open)  The Mean_CI95 scope is stated nowhere a thesis reader will see

- Carry: continues STA-14 (open). The CIs in the regenerated conditional
  summary are the same construction on the re-graded errors (family
  bootstrap, seed 42); D48 quotes "8.45 [7.67, 9.27]" with no statement that
  the interval is conditional on the selected forms. What/Options: the
  2026-10-22 statistics report §STA-14.

## Checked and found consistent

- **The identity never uses measured quantities.** `z_urban.py:624-636`:
  `Rconv` from `predict_pi`/`predict_impulse` with the fold's coefficients;
  `r_free` from the table's `R_free` (= Z_free·W^(1/3), written by Phase 1)
  or recomputed identically when absent (`tests/test_clip_chain.py::`
  `test_r_free_recomputed_when_column_absent` passes). `clip_sensitivity`
  `rows.csv` carries `Zconv_pred` vs `Zconv_meas` per row — the changed rows
  are exactly those with Z_free >= Zconv_pred, regardless of Zconv_meas.
- **The identity cannot fire in the deployable metric** —
  `evaluate_z_urban_deployable` requires `r_free < Rconv_pred` strictly
  (`z_urban.py:905`), so D48's "מספרי ה־Deployable לא השתנו" is structural,
  not accidental: deploy LOGO files, `z_P_dep`/`z_I_dep` (bit-identical in
  all 500 rows) and the conv LOGO files are unchanged. The accuracy of the
  identity answer itself (x >= 1) is on the record only through D49's group
  (ii) analysis (e.g. impulse MAPE 19.5%, bias −19.1% in 1 <= x < 1.25) —
  the deployable metric by construction never grades it.
- **Fit untouched.** The clip/identity applies at prediction only
  (`fit_z_urban_all_groups` never calls it); `final_production_*` absent from
  `git status`; coverage identical (conditional P 422 rows/82 configs,
  I 732/96; all `*_rows`/`*_cfgs` columns of `cv_summary` bit-identical).
- **LOGO detail diff** (working tree vs `git show HEAD:`): 1154 rows, same
  keys and order, `Actual` identical; exactly 25 `Predicted` changed —
  16 P in 10 configs, 9 I in 5 configs, every new value == `Z_free` exactly;
  old values all below Z_free. Changed-row errors: P 21.61% (bias −21.61%)
  → 13.19% (−13.19%); I 12.60% (−12.60%) → 6.90% (−6.90%) — equal to D50's
  scope table.
- **LOGO summary** (all against the tracked file, old in parentheses):
  P pooled Mean 8.4536 (8.7730), CI [7.6666, 9.2714], Max 28.339 (41.482),
  R2_Rurban 0.9335 (0.9248), RMSE 6.885 (7.321) m, MAE 5.323 (5.534) m,
  R2_Zurban 0.8968 (0.8605), R2_Lambda 0.4454 (0.3745), 82/96 configs,
  422 rows; I pooled 6.6785 (6.7486), CI [5.7178, 7.5968], R2_Rurban 0.9640
  (0.9637), RMSE 7.597 (7.628), MAE 5.500 (5.541), R2_Zurban 0.9246 (0.9230),
  R2_Lambda 0.6873 (0.6840), 96/96, 732. Every value D48/D50 quote rounds
  from these.
- **cv_summary diff**: z_P changed in 450 splits (median 8.706 → 8.372, IQR
  [8.083, 9.282] → [7.820, 8.857]), z_I in 279 (6.188 → 6.106), worst in 96
  (9.760 → 9.701); splits with worst < 10%: 283 → 290; conv_P/conv_I and both
  R² column pairs bit-identical; `worst == max` of the four MAPEs on all 500
  rows; all deltas <= 0 (no split got worse).
- **From-scratch reproduction.** Splits 0 and 79 rebuilt with
  `StratifiedShuffleSplit(500, test_size=0.2, random_state=42)` and the
  working-tree fitters (`relwls`→weighting='relative', impulse 'quad'):
  z_P/z_I match the regenerated file to < 1e-12 rel (split 0: 8.855771351 /
  7.242553832; split 79: 6.503493414 / 5.033335317). The regenerated
  `cv_summary` is what the working-tree code produces.
- **pressure_report numbers** (read-only recomputation via
  `build_per_z_table` with the production coefficient CSVs): 422 rows,
  MAPE 8.2614 → 7.9882, flags 52 → 37, 15 rows changed — D50's "15 שורות.
  MAPE 8.26% → 7.99% ... 52 → 37" exactly. The flag semantics change
  (identity rows no longer flagged `clipped_at_Zconv`) matches the new
  README text in `config_summary`. Note: the new `was_clipped` is strict
  (`pred_Z > Rconv/W13`) where the old flag used a 1e-12 tolerance —
  immaterial on this data (the 15-row difference is entirely the identity
  rows).
- **Docs quotes.** ALGORITHM.md and ALGORITHM_HE.md updated in parallel with
  the same content (neither ahead). The "385 of 1110" claim reproduces from
  the `beyond_I` flags of the graded deployable rows (385 exactly; a naive
  recount of MaxR_I >= the convergence table's RadiusI gives 394 — the flag
  is the Phase-1 definition and is the one the sentence means; definitional,
  not an error). The "6.31% with the clip, 6.40% without" above-floor pair
  matches D49's record verbatim.
- **D51 numbers** (new entry, documented-only): LOGO boundary Λ_P < 1 in
  8/96 configs — exactly the eight configs listed (16, 17, 32, 34, 35, 36,
  77, 79, all det1), min 0.944 (`boundary.csv`); production coefficients
  give 10/96, min 0.941 (probe); impulse min 1.024, no discontinuity — all
  as the entry states. The new test pins non-decreasing behaviour and
  documents the Λ < 1 jump case.
- **clip_sensitivity.py pinning.** The D49 probe now carries a verbatim copy
  of the pre-D50 clip and gates against the `da83d66` CSVs via `git show` —
  the D49 evidence stays reproducible after this commit lands (correct way
  to freeze a superseded behaviour for an audit script).
- **Tests.** 180 passed, 0 skipped, data present; `test_clip_chain.py`
  covers both sides of the boundary, Λ > 1 and Λ < 1, the flags, the
  R_free fallback and the no-op paths.

## Not checked

- `check_formulas`, `config_summary` and `pressure_report` were not executed
  end-to-end (they write under `outputs/`); `pressure_report` was verified by
  read-only recomputation of its table builder, `check_formulas`' 6.57 → 6.50
  against `cv_summary` row 79, and `validation_comparison_reqdir91_soft3.csv`
  byte-identity from its absence in `git status` (tracked, unmodified).
- The production Phase-2 run was not rerun (as instructed); splits 0 and 79
  were reproduced from scratch and the summaries re-derived from the tracked
  detail CSVs.
- STA-04 through STA-11 and STA-13 (not touched by this change).
- The LOGO bootstrap internals (verified in the 2026-10-22 statistics review;
  construction unchanged by this diff).
- `blast_calculator.html` beyond the two chain sites cited (STA-16); the
  thesis and proposal (off limits).
- D49's own decision process (closed, "ביקורת: טרם נבדק") — only the numbers
  this change quotes from it were cross-checked.
