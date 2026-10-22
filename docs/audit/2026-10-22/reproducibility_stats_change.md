# Audit: reproducibility of the uncommitted statistics change (2026-10-22, base commit f8a87b3, tree dirty)

Scope: cross_validation.py (R2 on Z, ceil n_test), z_urban.py (docstring), tools/logo_cv/logo_cv.py (family bootstrap CI, R2 views, coverage), tests/test_logo_bootstrap.py, and the four regenerated tables.
All regenerations went to a scratch dir outside the repo; no committed file was touched.

| # | Check | Result |
|---|-------|--------|
| 1 | Fast tests | PASS: 169 passed, 6 deselected (slow), 0 failed, 0 skipped (`-rs` printed no skip lines, so the data-dependent anchor tests ran). tests/test_logo_bootstrap.py alone: 7 passed. |
| 2 | Regenerated summaries equal working tree | PASS. Phase 2 (n_iter 500) cv_summary_reqdir91_soft3.csv and the three logo_summary CSVs (conv, zurban, zurban deployable) are identical to the working-tree versions (compared modulo CR; the conv summary also compared raw bytes: identical). |
| 3 | HEAD columns unchanged, only appended | PASS. Parsed `git show HEAD:<file>` against the working tree, row by row, field by field on the raw text: 0 differing rows in the HEAD columns, same row counts. cv_summary: 501 rows, 10 -> 12 columns (+conv_P_r2_Z, conv_I_r2_Z). logo_summary conv: 7 rows, 8 -> 16 columns. zurban and zurban_deploy: 9 rows, 8 -> 16 columns. Appended: Mean_CI95_lo, Mean_CI95_hi, two R2 columns (R2_R/R2_Z or R2_Zurban/R2_Lambda), N_families, N_configs, Configs_total, Coverage_configs. |
| 4 | Detail CSVs and other Phase-2 outputs | PASS. logo_cv_* detail CSVs (conv, zurban, zurban_deploy) identical to committed. Phase 2 regenerated best_convergence_coefficients, best_test_configs, best_z_urban_coefficients, final_production_convergence_coefficients, final_production_z_urban_coefficients: all identical to the committed files. The `n_test` change (floor to ceil, 76/20 now logged instead of 77/19) only affects the log line and the new R2-on-Z arithmetic, not the split (StratifiedShuffleSplit already rounds up); the outputs confirm this. |
| 5 | Bootstrap determinism | PASS. Conv, zurban and zurban-deployable logo_cv runs each executed twice; summary and detail CSVs are byte-identical between runs, and equal the committed working-tree files. Seed 42, fresh generator per call (code read: `family_bootstrap_ci`). |

## Notes (non-blocking)

- Phase-2 figures (cv_best_*.png) were regenerated but not compared; figures are not of record (CLAUDE.md §3).
- theta_radius_{P,I}_reqdir91_soft3.csv and the other check_results files are not produced by the commands you allowed, so they were not regenerated; they are untouched by this diff (not in `git status`).
- Not byte-compared on CRLF: the git warning says tools/logo_cv/logo_cv.py will be converted LF to CRLF on the next git touch; this is line-ending noise only, not a content issue.
- The Phase-2 table values in the cv_summary diff (1002 changed lines in `git diff --stat`) are entirely the two appended columns per row (500 rows x 2 lines), consistent with check 3.
- The conv R2 on Z median is 0.118 (P) and 0.753 (I) versus 0.917 / 0.954 on R. This is a result, not a reproducibility matter, but whoever cites R2 in the thesis should know it.
- Tree is dirty by design; the results cannot be tied to a commit until this change is committed together with the regenerated tables.

## Blockers

None found. Commit the code, test and the four tables together so the tables are tied to the code that produces them.
