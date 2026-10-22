# Reproducibility check: R_urban view in logo_cv (2026-10-22, HEAD 7e98844, tree dirty)

Dirty files: tools/logo_cv/logo_cv.py, tests/test_logo_bootstrap.py, the two zurban summary CSVs, docs/DECISIONS.md (ignored).
`git diff HEAD -- run_analysis.py blastlib` is empty, so Phase 2 code is untouched and no Phase 2 or production run was needed.

## Result: PASS on all six checks. Nothing blocks the commit.

1. Fast tests: `pytest -q -m "not slow" -rs` gave 172 passed, 0 failed, 0 skipped, 6 deselected (32 s). The 3 new tests are in that count. No anchor test was skipped.
2. Detail CSVs and conv summary: all three detail CSVs (conv, zurban, zurban_deploy) and the conv summary regenerate byte-identical to HEAD, with CRLF normalised.
3. Zurban summaries:
   - In both, the HEAD column list is an exact prefix of the new one.
   - Every HEAD column is field-for-field identical as strings, so Mean_CI95 did not move in the refactor.
   - Row count is 8 in both, same as HEAD.
   - Nine columns are appended: R2_Rurban, RMSE_Rurban_m and MAE_Rurban_m, each with _CI95_lo and _CI95_hi.
   - The regenerated files are byte-identical to the working-tree versions. Neither differs from HEAD in anything but the appended columns.
4. Determinism: two runs each of conv, zurban and zurban --domain deployable gave byte-identical detail and summary files.
5. Independent recompute: I recomputed R2, RMSE and MAE from the detail CSVs with W from the `_w<kg>` suffix, R = Z * W^(1/3). I did this for P and I, pooled, det1 and det2, in both domains.
   - Max |difference| against the stored point values is 3.6e-15.
   - Every CI brackets its point value (12 of 12 rows per domain).
   - The per_family rows are NaN in the new columns, as intended.
   - Conditional domain, pooled: P has R2 0.9248, RMSE 7.32 m, MAE 5.53 m. I has R2 0.9637, RMSE 7.63 m, MAE 5.54 m.
   - Deployable domain, pooled: P has R2 0.9405, RMSE 7.69 m, MAE 5.85 m. I has R2 0.8697, RMSE 20.81 m, MAE 12.87 m.
6. MAPE on R_urban against ErrPct, row by row: max |difference| is 5.3e-14 in both domains, so they are equal to rounding.

## Notes (non-blocking)
- `_w13` uses the regex `_w(\d+)$`, which accepts integer kg only. This is identical to the previous in-line code and fine for the current 96 configs. A fractional-kg config name would yield NaN and not raise an error.
- The deployable-domain I pooled R2_Rurban of 0.87 and RMSE of 20.8 m are much worse than the conditional-domain values. This is real data, not a reproducibility issue, but it is worth a line in the write-up.
- The old 2026-10-22 audit files were not touched. Scratch outputs are in the session scratchpad only. They were not written into outputs/ or into the repo.
