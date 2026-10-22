# Audit: reproducibility, coverage-column change (2026-10-22, HEAD 224c983, tree dirty)

Scope: uncommitted changes to blastlib/regression/cross_validation.py and blastlib/regression/z_urban.py, and the regenerated outputs/tables/cv_summary_reqdir91_soft3.csv. The tree is dirty by design, so these results are tied to HEAD plus that diff, not to a commit.

## Verdict: PASS, nothing blocks the commit

| # | Check | Result |
|---|---|---|
| 1 | Fast tests (`-m "not slow"`) | 169 passed, 6 deselected (slow), 0 failed, 0 skipped (`-rs` lists none, so the anchor tests ran) |
| 2 | Regenerated cv_summary (Phase 2, n_iter 500, temp dir) vs working-tree file | byte-identical, not only modulo line endings. At HEAD the file has 12 columns and 500 rows. Now it has 21 columns and 500 rows. All 12 HEAD columns are field-for-field equal to the new file (NaN-aware). |
| 3 | Other Phase-2 outputs vs HEAD | best_convergence_coefficients, best_test_configs, best_z_urban_coefficients, final_production_convergence_coefficients and final_production_z_urban_coefficients are byte-identical to HEAD (CR stripped). |
| 3 | logo_cv vs HEAD (outputs/check_results) | The detail and summary CSVs are identical to HEAD for: zurban conditional (`..._relwls_quad_zurban`), zurban deployable (`..._zurban_deploy`), and the default conv target (`..._relwls_quad`). That is 6 files; the conv target was run in addition to the two you listed. |
| 4 | Coverage counts equal what the MAPE uses | See below. |
| 5 | Callers of the two evaluators | See below. |

## Check 4 detail
I ran a 60-iteration Phase 2 into a temp dir with both evaluators wrapped. This was a sample of splits, not the production 500. For each split the wrapper did four things.
- It called the evaluator with `coverage=True` and with the default.
- It spied on `r2_mape` to count the finite (actual, pred) pairs it actually received. That is the true MAPE input.
- It recomputed rows and distinct configs independently. For the conditional evaluator this used `z_urban_valid_mask` per det and target. For the deployable one it re-derived the domain from `predict_pi` / `predict_impulse`, R_free, Z_free, exclude_r and the D46 periods condition.
- It compared everything.

Result: 60 splits, 0 mismatches. The coverage rows equal the `r2_mape` finite-pair count for P and I in both domains. The coverage config counts equal the independent distinct-config counts. The default call still returned the same MAPEs as the `coverage=True` call.

Limit: the independent recompute reuses `z_urban_valid_mask` for the conditional domain. It confirms the counting and plumbing, not the mask definition.

Coverage columns in the 500-split table:

| column | mean | min | max |
|---|---|---|---|
| n_test | 20 | 20 | 20 |
| z_P_cfgs | 17.1 | 13 | 20 |
| z_I_cfgs | 20 | 20 | 20 |
| z_P_dep_cfgs | 16.3 | 11 | 20 |
| z_I_dep_cfgs | 19.8 | 16 | 20 |
| z_P_rows | 88.0 | 57 | 114 |
| z_I_rows | 152.3 | 118 | 178 |
| z_P_dep_rows | 103.1 | 62 | 146 |
| z_I_dep_rows | 229.7 | 177 | 279 |

## Check 5 detail
`grep evaluate_z_urban` over the repo finds these callers.
- `blastlib/regression/cross_validation.py` (lines 191 and 199) is the only caller that passes `coverage=True`, and it unpacks 3 values.
- `tools/logo_cv/logo_cv.py` (lines 181-182) selects the evaluator and calls it with the default flag. Its three outputs are byte-identical to HEAD, which shows it still gets the 2-tuple.
- `outputs/plan_evidence/scripts/b1r_regression.py:105` and its copy under `outputs/backup_2026-10-18/` unpack `mP, mI = evaluate_z_urban(...)`. The default flag still returns a 2-tuple, so they are unaffected. The wrapper also asserted `len(...) == 2` for the default call.

## Notes (not blocking)
- The Phase-2 log gains new lines (Z_urban coverage, the quad r2 term). Anything that parses the console log would see the change. cv_summary readers that select columns by name are unaffected. Readers that index by position would still be fine because the new columns are appended.
- Environment-level drift (scikit-learn, numpy) was not a factor: the regenerated 500-iteration results match HEAD exactly on this machine.
- Not run: the production pipeline, Phase 1, and the slow tests.
- Scratch files were in `%TEMP%\cov_audit`, outside the repo. No repo file other than this report was written. `git status` shows only the five files that were already dirty.
