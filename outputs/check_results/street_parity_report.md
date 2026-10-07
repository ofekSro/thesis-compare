# Street-suite parity report

- date: 2026-10-07 21:21
- reference: pinned artefacts under outputs/check_results/ (first pinned bf8eefe; re-pinned at D36, 92-config record)
- rebuild HEAD: d9b1e58
- environment: Python 3.12.10, numpy 2.4.4, scipy 1.17.1, pandas 3.0.1
- verdict: PASS

## T1 — artefact parity (rtol=1e-12, atol=1e-12)

| artefact | status | detail |
|---|---|---|
| street_anchors.csv | PASS | 96 rows, max|Δ|=0.00e+00, max rel=0.00e+00 |
| master_curve_g.csv | PASS | 54 rows, max|Δ|=0.00e+00, max rel=0.00e+00 |
| e_profile_validation.csv | PASS | 92 rows, max|Δ|=0.00e+00, max rel=0.00e+00 |

## T2 — constants (full precision vs pinned)

| constant | refit | pinned expectation | shipped (pinned) |
|---|---|---|---|
| G.A | 72.00099409429846 | 72.00099409429846 | 59.9 |
| G.p | 2.6401629004429346 | 2.6401629004429346 | 2.48 |
| G.q | 4.907159124527716 | 4.907159124527716 | 4.75 |
| RHALF.C | 1.2842128901999612 | 1.2842128901999612 | 1.28 |
| RHALF.p_sq | -1.020512692535677 | -1.020512692535677 | -1.07 |
| RHALF.p_hs | 0.278019829957591 | 0.278019829957591 | 0.27 |
| EPK (verification only) | C=2.528 a=1.706 b=-0.5424 k_hs=5.826 k_hw=4.477 (mape 6.77%) | pinned 2.69/1.81/-0.50/4.56/7.07 stay canonical | LOGO 7.66% over 36 (det,b,s,H) families; the published 6.7%/36 used the lost fitter and a slightly different family roster |

Since D36 the G and RHALF refits are verification only, like EPK: the shipped values stay pinned at the 88-config fit.

## T3 — headline locks

- profile MAPE (92): mean 9.6109, median 8.45, p90 17.09, max 31.0 [%]
- gate: 94/96 correct; misses ['config_67_det2_b30_s20_h12_w50', 'config_70_det2_b30_s20_h24_w50']; false alarms []
- envelope (in-sample, 92): coverage 96.47%, >0.15 exceedance 0.71%, mean overprediction 26.8%, worst 0.723 at config_26_det1_b30_s5_h24_w500 (10907 slices)
- collapse IQR: slope 0.2452, crossing 0.2053; cloud 79 profiles / 12,185 points

## T4 — figure inventories

- top 92/92, all_figures 93/93, env 5/5, pressure_check 10/10; checks [True, True, True, True, True]
- pixel provenance: three sets had no surviving writer; formats reconstructed from the shipped PNGs (structural parity only, by design)

## Corrected stale claims (doc superseded by measurement)

| claim | was documented | measured now |
|---|---|---|
| envelope coverage | 95.0% | 96.47% |
| slices exceeding by >0.15 | 1.5% | 0.71% |
| mean overprediction | 24% | 26.8% |
| largest exceedance | 0.96 at config_03 | 0.723 at config_26 |
| gate false alarms | zero | none (config_78, config_80 before D36) |
| g(1) | 0.48 | 0.518 |

- Q1 sweep: 0 configs differ (none) — the > vs >= split is empirically a no-op

## Sign-off

- [x] gate B: PASS; 96 rows, max|Δ|=0.00e+00, max rel=0.00e+00; L_decay NaN 17/96 (want 17)
- [x] gate C: PASS; cloud 79/12185 (want 79/12185); A=72.000994 p=2.640163 q=4.907159; C=1.284213 p_sq=-1.020513 p_hs=0.278020; IQR 0.2452/0.2053; checks [True, True, True, True, True, True]
- [x] gate D: 0/92 3-dp mismatches (max |formula-csv| 0.00049)
- [x] gate E: PASS; 92 rows, max|Δ|=0.00e+00, max rel=0.00e+00; membership 92/92
- [x] gate F: chain rebuilt-anchors -> fit -> validate, every link compared against its pinned artefact
- [x] gate G: top 92/92, all_figures 93/93, env 5/5, pressure_check 10/10; checks [True, True, True, True, True]
- [x] gate H: MAPE 9.6109/8.45/17.09/31.0; gate 94/96; envelope 96.47%/0.71%/0.723@config_26_det1_b30_s5_h24_w500; checks [True, True, True, True, True, True, True, True, True, True, True, True]
- [x] gate Q1: 0 configs differ (none) — the > vs >= split is empirically a no-op

(gate A — strip golden rows — lives in tests/test_street_strip.py)
