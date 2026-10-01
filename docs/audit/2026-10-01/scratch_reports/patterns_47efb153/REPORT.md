# Pattern search — record 27211b3 (req_soft3) — numbers only

Methods: PREREG.md (written before any test; addendum before any test, after targets).
Full tables: out/patterns_passed_by_key.md, out/C1_compact.md, out/patterns_undecided.md,
out/all_tests.csv (every test, every check).

## Record facts used
- Z_conv,P: median 9.91, range 7.51–14.70; Z_conv,I: median 16.23, range 10.75–29.21.
- 8 configs Z_I > 20 (det1: 22, 25, 26; det2: 40, 43, 58, 61, 62) → removed in check (4).
  (WORKLOG lines 212/231/336 quote Z_conv,I median 13.85, max 17.48, 0/96 > 20 — those are
  NOT the 27211b3 table.)
- Λ_P median-per-config 0.81–1.44; Λ_I 0.93–1.93. Ring stats: 96×20 rings, ≥424 cells each.

## BH
m = 1146 tests, R = 396 rejections, p threshold 0.0171, FCR level for adjusted CIs 1 − 0.0173.
Per-family counts: out/test_counts.csv.
Pass all four: 321 test rows + 6 with (4) not estimable → 139 pattern keys. Undecided: 95.
5 B1 F-terms were BH-rejected but their two-sided adjusted η²p CI reaches 0 → not passed (criterion (1) read literally).

## Deviations / post-hoc, flagged
1. B1 LOGO: with the 3-way model, removing one (b,s,H) family makes every term made only of
   b, s, H non-estimable → pre-registered LOGO = n/a → those terms cannot pass (3).
   POST-HOC 2-way fold model (out/B1_posthoc_logo_2way.csv): b, s, s:H (Z_P pooled) and
   b, s, H, s:H (Z_I pooled) are 12/12 sign-stable and pass (1),(4). Not moved into the passed table.
2. Criterion (1) for F tests enforced as "adjusted η²p CI lower bound > 0" (see above).
3. Display fix: A1 Δ rows are a(det2) − a(det1).

## Limitations (statistical)
- Within-det ANOVA error df = 4; robustness fits within det have 1 df (det1) or are not
  estimable at 3-way (det2: 31 obs < 32 params) → many within-det terms fail (4) or get n/a.
- C2 bootstrap p floor 1/2000; C3 LOGO criterion = share of families improved.
- C1 paired det test is identical for R and Z (same W in each pair) → counted twice in m.
- R_* vs W and vs s̃ trends: s̃ contains W^(−1/3), so these Spearman values are partly fixed by construction.
- A3: no exactly similar pairs exist in the 96 (b/s differs between every pair of geometries).
