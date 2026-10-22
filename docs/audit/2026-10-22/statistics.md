# Audit: statistics  (2026-10-22, commit f8a87b3, tree dirty)

Pre-commit review of one uncommitted change: ceil of the printed test size and
two per-split R²-on-Z columns in `blastlib/regression/cross_validation.py`;
family-bootstrap CIs, R² views and coverage columns in `tools/logo_cv/logo_cv.py`;
a docstring fix in `blastlib/regression/z_urban.py`; the regenerated
`cv_summary_reqdir91_soft3.csv` and the three `logo_summary_reqdir91_*` CSVs;
and the untracked `tests/test_logo_bootstrap.py`. Findings only; no file other
than this one was written. Probes ran read-only from the repo root (one stray
placeholder file was briefly created at a mistyped path outside the repo and
deleted; nothing inside the repo was touched). `git status` after the audit is
identical to the status at the start plus one untracked file another session
wrote (`docs/audit/2026-10-22/reproducibility_stats_change.md`, not mine).

Environment: sklearn 1.8.0, Python 3.12. Fast tests: `python -m pytest -q -m
"not slow"` → **169 passed, 6 deselected, 0 skipped** (anchor tests ran, data
present). The new `tests/test_logo_bootstrap.py` is included in the 169.

## Carry-over from 2026-09-27

Limited, as instructed, to the old findings this change touches (CV design,
metrics, uncertainty, domain grading). **STA-04, STA-06, STA-07, STA-09,
STA-10 and STA-13 were not re-checked today** and keep no status here.

| old id | status | evidence (file:line / number) | decision (D#) |
|---|---|---|---|
| STA-01 | open | Form/β/`a` selection on the reported LOGO folds unchanged; `tools/logo_cv` is still both the selection harness and the quoted estimate. The new `Mean_CI95` columns do not cover this (see STA-14). | D5 open |
| STA-02 | superseded-by-decision | D3 (a)+(b) in force: domain kept, `z_P_dep`/`z_I_dep` reported beside the conditional numbers (`cross_validation.py:194-200`), and the deployable LOGO record now exists (`logo_summary_..._zurban_deploy.csv`: I pooled mean 9.88% vs conditional 6.75%, max 43.3 vs 31.1 — the gap the finding predicted is now on the record, not hidden). D46 added a target-independent geometric condition 5. No new evidence against D3. | D3, D46 in force |
| STA-03 | open | `tools/check_formulas/check_formulas.py:1-6,637,662-665` and `tools/formulas_printer/formulas_printer.py:141-143` still load `best_*` (best of 500 splits). D11 undecided. This change correctly keeps the new columns out of best-split selection (below). | D11 open |
| STA-05 | partially | New: 95% family-bootstrap CIs on the LOGO **mean errors** (`logo_cv.py::family_bootstrap_ci`), D12 option (a) applied to the error means. Still absent: intervals on any published coefficient or prediction; the weakly identified constants (B, C1, C3) still printed as bare point values; D46 itself recorded coefficient moves up to 239% as "interpretation warning". | D12 open |
| STA-08 | resolved | Z_urban LOGO harness is in the repo at HEAD: `tools/logo_cv/logo_cv.py` `--target zurban --domain conditional|deployable` (`run_logo_zurban`, TARGET_CHOICES line 66), detail + summary CSVs tracked under `outputs/check_results/`. Whether every quoted document number was regenerated from it was not re-checked. | — |
| STA-11 | partially | The printed-size half is fixed **by this change**: `cross_validation.py:105-106` now uses `ceil`, and the probe confirms the real split is 76/20 (10+10 per det) under sklearn 1.8.0. Still wrong: the "prefix" half — `cross_validation.py:54-56` ("changes the ENTIRE sequence of splits") and `CLAUDE.md:175` ("changes the whole split sequence"); probe today (sklearn 1.8.0): splits at `n_splits=20` equal the first 20 of `n_splits=500` → True. | D18 (not documented) |
| STA-12 | partially | New: R² views that separate the W^(1/3) credit (see STA-15), per-family vs row-pooled scopes in the zurban summaries, and CIs on the LOGO means. Still as before: `cv_summary` medians quoted without MC error, relwls loss described as "the same quantity (MAPE)", conv LOGO summary has no per-family scope row (only zurban does: `logo_cv.py::main` calls `summarize_families` only for `target=='zurban'`). | D18 (not documented) |

Counts: 1 resolved, 2 open, 3 partially, 1 superseded-by-decision. Not
re-checked: 6 (listed above).

## Summary

The change is statistically sound and mechanically clean, and it implements
parts of what the 2026-09-27 audit asked for (D3 deployable record, D12
error-mean CIs, the 76/20 print fix, R² without the Hopkinson credit):

- **Old columns are bit-exact against HEAD** in all four regenerated CSVs
  (field-by-field probe below). The new columns are appended strictly after
  the old ones. `best_*` files are untouched (not in `git status`), and the
  new columns do not enter the `worst`/best-split selection.
- **The new numbers are correct.** Every new column of all three LOGO
  summaries reproduces from the tracked detail CSVs through the working-tree
  module to ≤ 4e-15, and splits 0-2 of `cv_summary` (old and new columns)
  reproduce from scratch to the last digit.
- **The bootstrap resamples the right unit** (the (Det,b,s,H) family, within
  det, 18+18), uses a correct ratio-of-sums for the row-pooled mean and a
  correct mean-of-means for the per_family scope, and is deterministic
  (fresh `default_rng(42)` per call). The interval-type choice is immaterial
  here (percentile vs basic vs normal ≤ 0.17 pp; seed ≤ 0.05 pp).
- **No leakage.** The R²-on-Z columns use test-set predictions already
  computed; the CIs and coverage use only the out-of-fold LOGO errors.

Two new findings, both about how the numbers will be read, not about how they
were computed: the CI's scope is stated nowhere a thesis reader will see
(STA-14), and the R²-on-Z columns reveal that the pressure convergence model
explains almost none of the geometry variance (R² on Z ≈ 0.1), which must be
interpreted, not hidden behind R² on R = 0.92 (STA-15).

Counts for this review: **0 high, 0 medium, 2 low** new findings (plus the
carried statuses above). **Nothing here blocks committing the change.**

## Findings

### STA-14  [low]  What the Mean_CI95 covers is stated nowhere, and it covers less than "the uncertainty of the LOGO error"

- Carry: new (relates to STA-01/D5 and D12).
- **Where.** `tools/logo_cv/logo_cv.py:250-258` (the code comment),
  `family_bootstrap_ci`; the `Mean_CI95_lo/hi` columns of the three tracked
  `logo_summary_reqdir91_*.csv`; no document in `docs/` mentions them (only
  the code and the new test do).
- **What.** The CI is a cluster bootstrap of the **fixed** out-of-fold errors:
  families are resampled, but nothing is refit per resample. It therefore
  quantifies family-sampling variability of the mean error of the *already
  selected and already fitted* model chain, and excludes:
  1. model-selection optimism — the Z_urban forms, β, `a` and the fit variants
     were chosen on these same LOGO folds (STA-01, D5 still open), so the CI
     is conditional on choices that used the held-out answers;
  2. refit variability — a new 36-family design would give different
     coefficients, not just different errors (the register's own D46 note:
     weakly identified coefficients moved up to 239% under a domain change);
  3. dependence between folds — every pair of LOGO folds shares 34 of 35
     training families, so the family errors are positively correlated and
     the bootstrap's independence assumption is only approximate (the known
     no-unbiased-variance-estimator problem of CV).
  With 18 clusters per det the percentile interval is first-order only, but
  the probe shows the interval-type choice is immaterial on this data.
- **Evidence.** Probe (percentile vs basic vs normal, 10000 replicates):

  ```
  conv P: mean 9.42  pct [8.03,10.87]  basic [7.98,10.82]  normal [8.01,10.84]
  conv I: mean 7.13  pct [5.63, 8.81]  basic [5.46, 8.64]  normal [5.53, 8.74]
  zurban_deploy P: mean 8.42  pct [7.77,9.08]  basic [7.75,9.07]
  zurban_deploy I: mean 9.88  pct [8.59,11.06] basic [8.70,11.18]
  seeds 42/0/7 (conv P): [8.034,10.871] / [8.032,10.824] / [8.027,10.829]
  ```

  The code comment documents the resampling unit and seed, but says nothing
  about points 1-3, and no `docs/` text exists for the thesis to copy.
- **Consequence.** Quoted bare ("LOGO mean 9.4%, 95% CI [8.0, 10.9]"), the CI
  will read as the uncertainty envelope of proposal aim 5. It is a lower bound
  on that envelope: a CI on the mean error of the selected model, conditional
  on the selection. The same over-reading already happened once with the safe
  domain (STA-04/D6).
- **Options.** (a) One sentence wherever the CI is quoted: "95% CI of the mean
  out-of-fold error under family resampling, conditional on the selected model
  forms; it does not include selection uncertainty." Cost: text. (b) A nested
  variant for the cheap choices (inner LOGO picks the form, outer family
  scores it — D5 option b), whose CI would include the cheap selection steps.
  Cost: minutes, the fitters are fast. (c) Report the basic interval beside
  the percentile as a robustness line (they differ by ≤ 0.17 pp here, which is
  itself worth one sentence). Cost: seconds.

### STA-15  [low]  R² on R vs R² on Z: the new columns show the pressure model's geometry content is near zero, and the thesis must quote the right one

- Carry: new (follows STA-12's metric-definition thread).
- **Where.** `cross_validation.py:176-181` (new columns, with a correct
  rationale comment), `:316-319` (log prints both); `logo_cv.py::R2_VIEWS`,
  `_view_divisor`, `_r2`; columns `R2_R`/`R2_Z` of
  `logo_summary_reqdir91_soft3_relwls_quad.csv` and `R2_Zurban`/`R2_Lambda`
  of the two zurban summaries.
- **What.** The change itself is the fix: R² on R [m] credits the model with
  the W^(1/3) Hopkinson scaling it gets for free (W spans 50-1500 kg, so
  W^(1/3) alone generates most of the variance of R), while R² on
  Z = R/W^(1/3) measures only the geometry dependence the model actually
  fits. The numbers now on the record:
  - LOGO conv P: R2_R 0.924 pooled, but **R2_Z 0.149 pooled and 0.006 for
    det2** (det1 0.203). conv I: R2_R 0.950, R2_Z 0.740.
  - CV (500 splits): median conv_P_r2 0.917 vs median **conv_P_r2_Z 0.118,
    negative in 156/500 splits** (min −2.39); conv_I_r2 0.954 vs
    conv_I_r2_Z 0.753 (min −0.69).
  - zurban deploy: R2_Lambda (the ratio the thesis actually argues about)
    0.44 (P) and 0.23 (I) vs R2_Zurban 0.90/0.80.
- **Evidence.** Independent recomputation (no module helpers) of R2_Z for
  conv P pooled from `logo_cv_reqdir91_soft3_relwls_quad.csv`:
  `r2 = 0.14929209324155024`, equal to the tracked column; the regex-extracted
  W equals the convergence-table `ChargeWeight` for all 96 rows; `Actual`
  equals the table's `RadiusP` row-for-row. Splits 0-2 of `cv_summary`
  recomputed from scratch match all columns to the printed digit
  (e.g. split 1: conv_P_r2 0.921143, conv_P_r2_Z −0.203966).
- **Consequence.** Two misreadings are now possible and both are wrong:
  - quoting R² on R (0.92-0.95) as model quality — that is mostly Hopkinson
    scaling, not the fitted geometry terms;
  - reading R² on Z ≈ 0.1 as "the pressure model is broken". It is not: the
    out-of-fold MAPE is 8-9% while Z_conv,P has a narrow spread across
    configurations, so the test-set Z variance is of the same order as the
    model's squared error. Low R² on Z plus low MAPE means the geometry
    moves Z_conv,P only mildly — a statement about the physics (and about
    which metric is informative), not about a defect. For det2 pressure the
    fitted geometry terms predict essentially none of the between-config
    Z variance out of fold (R² 0.006): on Z, the det2 model is currently
    indistinguishable from a constant.
- **Options.** (a) In the thesis, quote MAPE as the headline and R² on Z (or
  on Λ for Z_urban) as the variance-explained figure; if R² on R appears,
  label it "includes the W^(1/3) scaling". Cost: text. (b) Add the same pair
  of R² views to any figure or table that currently prints a single R².
  Cost: a plotting change; the `plot_logo` figures already use `_r2` with the
  view divisor, so figure and CSV already agree. (c) Report alongside R² a
  spread statement for Z_conv,P (its p5-p95 across configs) so the "narrow
  target" explanation is checkable. Cost: seconds.

### STA-01  [high]  (carry, open)  Structure, variants and β chosen on the reported LOGO folds

- Carry: continues STA-01 (open). What/Consequence/Options: the 2026-09-27
  report (`docs/audit/2026-09-27/statistics.md` §STA-01) and D5, both
  unchanged. Today's relevance: the new CIs are conditional on that
  selection (STA-14 point 1) and must not be presented as resolving it.
- Where today: `tools/logo_cv/logo_cv.py` unchanged in role; D5 status
  "פתוח" in `docs/DECISIONS.md:122-133`.

### STA-03  [high]  (carry, open)  Best-split artefacts labelled and consumed as validation

- Carry: continues STA-03 (open). What/Consequence/Options: the 2026-09-27
  report §STA-03 and D11 (open, `docs/DECISIONS.md:200-206`), unchanged.
- Where today: `tools/check_formulas/check_formulas.py:1-6,637,662-665`;
  `tools/formulas_printer/formulas_printer.py:141-143` still read `best_*`.
- Positive note on the change under review: the new per-split columns are
  deliberately excluded from selection — `mapes` (`cross_validation.py:203-206`)
  and `worst` (`:212`) are built before the R²-on-Z values are stored, and the
  comment at `:194-198` keeps `z_*_dep` out as well. Verified: `best_*` files
  are absent from `git status`, and the bit-exact old columns imply identical
  splits, fits and best iteration.

### STA-11  [low]  (carry, partially)  Printed split size fixed by this change; the "whole sequence" claim remains

- Carry: continues STA-11 (partially).
- Where: fixed — `cross_validation.py:105-106` (`ceil`; log now prints 76/20,
  matching the splitter's actual 20 test configs, 10 per det). Remaining —
  `cross_validation.py:54-56` ("changing it changes the ENTIRE sequence of
  splits") and `CLAUDE.md:175` ("`--n-iter` changes the whole split
  sequence"): probe under today's sklearn 1.8.0 confirms the splits at
  `n_splits=20` equal the first 20 of `n_splits=500` (prefix, not a new
  sequence). The practical rule "compare only at equal n_iter" stays valid
  for the best-split statistic, which is a min over the prefix length.
- Options: unchanged from 2026-09-27 (correct the two sentences; text only).

### STA-05  [medium]  (carry, partially)  Uncertainty: error-mean CIs now exist; coefficient and prediction intervals still absent

- Carry: continues STA-05 (partially); D12 still open.
- Where: new — `Mean_CI95_lo/hi` in the three LOGO summaries (this change).
  Still missing — intervals on `final_production_*` coefficients and on
  predictions (`blastlib/regression/output.py` writes point estimates only);
  the 2026-09-27 bootstrap showed several constants hitting their bounds
  under family resampling, and D46's own note records coefficient moves up
  to 239% under a domain change. Evidence/Options: 2026-09-27 report §STA-05.

### STA-12  [low]  (carry, partially)  Metric definition and aggregation

- Carry: continues STA-12 (partially).
- Improved by this change: per_family vs pooled scopes with CIs (zurban
  summaries), R² views, coverage columns. Remaining: conv LOGO summary has no
  per_family row (`logo_cv.py::main` calls `summarize_families` only for
  zurban); CV medians still quoted without their MC error; the loss-vs-metric
  wording in ALGORITHM (relwls minimises squared relative error, not MAPE;
  log-space losses unstated) not re-checked today. Options: 2026-09-27 §STA-12.

## Checked and found consistent

- **Old columns bit-exact.** Field-by-field probe of working tree vs
  `git show HEAD:<file>`: `cv_summary_reqdir91_soft3.csv` (500 rows, 11 old
  columns, max rel diff 0.0) and the three `logo_summary_reqdir91_*.csv`
  (all old columns bit-exact, old column order preserved as a prefix, new
  columns strictly appended). The 1-ulp drift the memory notes did not
  appear: the regeneration reproduced HEAD exactly.
- **New summary columns reproduce from the tracked detail CSVs.** Running the
  working-tree `summarize`/`summarize_families` on
  `logo_cv_reqdir91_soft3_relwls_quad{,_zurban,_zurban_deploy}.csv` matches
  every numeric column of the three tracked summaries to ≤ 3.6e-15 —
  including the bootstrap CIs (seed 42 is honoured; a fresh generator per
  call makes each scope's CI independent of computation order).
- **cv_summary columns reproduce from scratch.** Splits 0-2 rebuilt with
  `StratifiedShuffleSplit(500, test_size=0.2, random_state=42)` and the
  working-tree fitters match all old and new columns (e.g. split 0:
  conv_P 11.494372 / r2 0.853219 / r2_Z 0.100581, identical to the file).
  Test size observed: 20 (10 per det) — the `ceil` comment is correct.
- **Bootstrap construction.** Unit = family (the correlated cluster; a
  Z_urban family carries up to ~49 rows), resampled within det so every
  replicate keeps the 18+18 design; pooled/det scopes use the ratio-of-sums
  estimator of the row-pooled mean (numerator and denominator both
  resampled — correct for a cluster mean of unequal cluster sizes);
  per_family scope resamples the family MAPEs and divides by the fixed
  family count — exactly the mean-of-family-MAPEs statistic it brackets.
  Family keys embed det (`det1_b15_s5_h4`), so no cross-det collision.
  Degenerate case collapses to a point (unit test), CI brackets the mean
  (unit test), seed controls the draw (unit test).
- **Row alignment and divisors.** `_r2` aligns through the pandas index
  (`div[sub.index]`); `_view_divisor('Z')` regex `_w(\d+)$` matches every
  ConfigName of the production table, and the extracted W equals
  `ChargeWeight` for all 96 configs; `Lambda_actual` = Actual/Z_free checks
  out on the detail rows; the figure (`plot_logo`) now uses the same
  `_view_divisor`/`_r2`, so figure and CSV cannot drift (and the old inline
  divisor it replaced was identical).
- **Coverage denominators.** pooled → 96, det1/det2 → 48 each, per_family →
  96 configs; `N_configs` counts configs with ≥ 1 finite graded row. The
  conditional zurban P coverage 82/96 = 0.854 and deploy P 78/96 = 0.8125,
  I deploy 95/96, are consistent with the D46 domain; the deploy summary now
  shows the conditional-vs-deployable gap on the record (I mean 6.75 → 9.88,
  max 31.1 → 43.3), which is D3 (a) done properly.
- **No leakage, no selection contamination.** New cv columns are computed
  from the same test-fold predictions as the existing MAPEs; they are stored
  after, and excluded from, `worst`/best-split selection; the bootstrap and
  R² consume only out-of-fold LOGO errors; nothing is fitted on pooled data
  anywhere in the change.
- **Docstring change.** `z_urban.py:216-285`: "Five conditions" now matches
  the five conditions actually enforced (condition 5 = D46, in force);
  docstring-only, no behaviour change.
- **Interval-type and seed sensitivity.** Percentile vs basic vs normal moves
  the bounds by ≤ 0.17 pp; seeds 42/0/7 move them by ≤ 0.05 pp at 10000
  replicates. The percentile choice is defensible on this data.
- **Tests.** The new `tests/test_logo_bootstrap.py` is synthetic-data only,
  loads the tool by path, and pins the properties this review checked (old
  column order, CI brackets/collapse/seed, R²-on-Z divisor, coverage
  denominators, per_family resampling). Full fast suite: 169 passed,
  0 skipped, 21.8 s.

## Not checked

- The statuses of STA-04, STA-06, STA-07, STA-09, STA-10 and STA-13 (not
  touched by this change; not re-verified).
- Phase 1 and the `reqdir91_soft3` tables themselves (taken as given; the
  reproducibility lens of 2026-10-22 covers their provenance).
- The production Phase-2 run (not run, as instructed); only splits 0-2 were
  reproduced from scratch, plus the summary-from-detail reproductions.
- Whether `docs/ALGORITHM.md`, the Hebrew documents or the thesis text quote
  any of the new columns yet (no doc changed in this diff; STA-14/STA-15 say
  what the text must state when they do).
- `docs/audit/2026-10-22/reproducibility_stats_change.md` (untracked,
  appeared during this session, written by another session).
- The prior quoted Z_urban LOGO numbers in ALGORITHM against the now-in-repo
  harness (STA-08 marked resolved for the harness's existence only).
