# Street-suite parity report

- date: 2026-08-06 12:42
- reference snapshot: bf8eefe (pre-rebuild pinned artefacts)
- rebuild HEAD: 6a44ee8
- environment: Python 3.12.10, numpy 2.4.4, scipy 1.17.1, pandas 3.0.1
- verdict: PASS

## T1 — artefact parity (rtol=1e-12, atol=1e-12)

| artefact | status | detail |
|---|---|---|
| street_anchors.csv | PASS | 96 rows, max|Δ|=0.00e+00, max rel=0.00e+00 |
| master_curve_g.csv | PASS | 54 rows, max|Δ|=0.00e+00, max rel=0.00e+00 |
| e_profile_validation_88.csv | PASS | 88 rows, max|Δ|=0.00e+00, max rel=0.00e+00 |

## T2 — constants (full precision vs pinned)

| constant | refit | pinned expectation | shipped rounding |
|---|---|---|---|
| G.A | 59.88434103668478 | 59.88434103668478 | 59.9 |
| G.p | 2.483758865788831 | 2.483758865788831 | 2.48 |
| G.q | 4.746669040697642 | 4.746669040697642 | 4.75 |
| RHALF.C | 1.2849835992920906 | 1.2849835992920906 | 1.28 |
| RHALF.p_sq | -1.0700379830256466 | -1.0700379830256466 | -1.07 |
| RHALF.p_hs | 0.2721321919965368 | 0.2721321919965368 | 0.27 |
| EPK (verification only) | C=2.517 a=1.674 b=-0.5207 k_hs=4.897 k_hw=4.996 (mape 6.79%) | pinned 2.69/1.81/-0.50/4.56/7.07 stay canonical | LOGO 7.72% over 34 (det,b,s,H) families; the published 6.7%/36 used the lost fitter and a slightly different family roster |

## T3 — headline locks

- profile MAPE (88): mean 9.7364, median 8.50, p90 17.34, max 31.0 [%]
- gate: 92/96 correct; misses ['config_67_det2_b30_s20_h12_w50', 'config_70_det2_b30_s20_h24_w50']; false alarms ['config_78_det1_b10_s12_h10_w1000', 'config_80_det1_b10_s12_h15_w1000']
- envelope (in-sample, 88): coverage 96.34%, >0.15 exceedance 0.73%, mean overprediction 27.2%, worst 0.723 at config_26_det1_b30_s5_h24_w500 (10531 slices)
- collapse IQR: slope 0.2218, crossing 0.1894; cloud 75 profiles / 11,545 points

## T4 — figure inventories

- top 88/88, all88 89/89, env 5/5, pressure_check 10/10; checks [True, True, True, True, True]
- pixel provenance: three sets had no surviving writer; formats reconstructed from the shipped PNGs (structural parity only, by design)

## Corrected stale claims (doc superseded by measurement)

| claim | was documented | measured now |
|---|---|---|
| envelope coverage | 95.0% | 96.34% |
| slices exceeding by >0.15 | 1.5% | 0.73% |
| mean overprediction | 24% | 27.2% |
| largest exceedance | 0.96 at config_03 | 0.723 at config_26 |
| gate false alarms | zero | config_78, config_80 (conservative direction) |
| g(1) | 0.48 | 0.518 |

- Q1 sweep: 0 configs differ (none) — the > vs >= split is empirically a no-op

## Sign-off

- [x] gate B: PASS; 96 rows, max|Δ|=0.00e+00, max rel=0.00e+00; L_decay NaN 21/96 (want 21)
- [x] gate C: PASS; cloud 75/11545 (want 75/11545); A=59.884341 p=2.483759 q=4.746669; C=1.284984 p_sq=-1.070038 p_hs=0.272132; IQR 0.2218/0.1894; checks [True, True, True, True, True, True, True, True]
- [x] gate D: 0/88 3-dp mismatches (max |formula-csv| 0.00049)
- [x] gate E: PASS; 88 rows, max|Δ|=0.00e+00, max rel=0.00e+00; membership 88/88
- [x] gate F: chain rebuilt-anchors -> fit -> validate, every link compared against its pinned artefact
- [x] gate G: top 88/88, all88 89/89, env 5/5, pressure_check 10/10; checks [True, True, True, True, True]
- [x] gate H: MAPE 9.7364/8.50/17.34/31.0; gate 92/96; envelope 96.34%/0.73%/0.723@config_26_det1_b30_s5_h24_w500; checks [True, True, True, True, True, True, True, True, True, True, True, True]
- [x] gate Q1: 0 configs differ (none) — the > vs >= split is empirically a no-op

(gate A — strip golden rows — lives in tests/test_street_strip.py)
