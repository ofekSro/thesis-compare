# CLAIMS — mechanisms behind the round-1 patterns (record 27211b3)

Methods: PREREG2.md (declared before any round-2 test). Tests: out2/r2_tests.csv. Brackets = family-bootstrap CI at the FCR-adjusted level of round 2 (BH over 103 tests, R = 48, level 1 − 0.023); null-type rows use the plain 95 % CI.

Strata: C = charge street(s); L = other 2-D line of sight; S = no 2-D line of sight (includes cross streets, not only lee zones); wall = within 1 m of a block. τ = (I/I_ff)/(P/P_ff) is a duration PROXY (no time histories exist in the record).

SUPPORTED = the declared discriminating inequality held and the named alternative's did not; it is not proof of mechanism.

| id | claim | evidence | status | falsifying test |
|---|---|---|---|---|
| CL-01 | R_P and R_I grow with W by Hopkinson scaling; Z_conv carries no W main effect of comparable size (scaling identity, not an urban mechanism). | Round 1 A1: common a(R_P) = 0.342 [0.291, 0.393], a = 1/3 not rejected; a(R_I) = 0.280 [0.242, 0.318]. | SUPPORTED (R_P) / see CL-02 (R_I) | Per-geometry a with CI excluding 1/3 after BH (0 of 48 in round 1). |
| CL-02 | R_I a < 1/3 and the Z_I W effect are carried by scaled street width s~ (Pi-similarity). | A2 fit: beta_s~ = +0.079 gives a_pred = 0.307 at beta_W = 0, i.e. s~ accounts for 0.026 of the 0.053 deficit; residual beta_W = -0.026 (A2 CI includes 0, A2b CI excludes 0). | HYPOTHESIS | beta_W CI excluding 0 in every Pi form (linear and quadratic) → reject; CI within ±0.01 → support. |
| CL-03 | The impulse-side W effects (R_I a < 1/3, Z_I W-) come from mesh non-similarity of the solver (fixed metric cells). | Free-field reference scaled impulse vs ln W at fixed Z: Z2 -0.005 [-0.005, -0.004] (below 0.02 margin); Z5 -0.001 [-0.002, -0.001] (below 0.02 margin); Z10 -0.002 [-0.003, -0.002] (below 0.02 margin) — all below the 2 % margin. | REJECTED | Reference scaled impulse changing > 2 % per e-fold of W at fixed Z. |
| CL-04a | The free-field reference peak pressure at fixed Z is not W-independent on this mesh. | d ln P_ref / d ln W: Z2 +0.050 [+0.050, +0.050] (holds); Z5 +0.031 [+0.030, +0.031] (holds); Z10 +0.013 [+0.010, +0.017] (below 0.02 margin). W 50→1500 at Z = 2: about +17 %. | SUPPORTED (Z ≤ 5) | Slope within ±0.02 at Z = 2 and 5 on a refined mesh or at equal scaled resolution. |
| CL-04b | The W trends of pressure-side targets (Lambda_P W+, Z_P W main, rP_P95_Z2 W+, rP_med_Z10 W+) are a mesh effect (CL-04a), not urban physics. | CL-04a holds, but the ratio P/P_ff divides by a reference on the same mesh, and the Pi-similarity null (CL-05) also holds → the two are not discriminated. | HYPOTHESIS | W trend of the ratio surviving at equal scaled resolution (rerun subset at Δ/W^(1/3) fixed) → reject. |
| CL-05 | The W trends of Lambda_P, rP_P95_Z2, rP_med_Z10, rP_P5_Z10 act only through the Pi groups (no W effect at fixed Pi). | beta_lnW given Pi: Lambda_P +0.007 [-0.027, +0.062] (holds (null-type)); rP_P95_Z2 +0.070 [-0.007, +0.168] (holds (null-type)); rP_med_Z10 -0.011 [-0.092, +0.103] (holds (null-type)); rP_P5_Z10 -0.014 [-0.137, +0.164] (holds (null-type)). Round 1 A2 Z_P: +0.019 [-0.041, +0.079]. | SUPPORTED (null-type, weak: absence of a W effect, CI half-widths 0.05–0.15) | beta_W CI excluding 0 in any Pi form. |
| CL-06 | The W trend of rI_P95_Z2 acts only through the Pi groups. | beta_lnW given Pi +0.076 [+0.038, +0.129] (fails). | REJECTED | —  (already falsified; candidate left: unexplained residual W effect on near-field impulse P95). |
| CL-07 | The b:W interaction of Z_P and Z_I (and the W-effect reversal along b, B2) is reproduced by the Pi model (rho, s~, H/s with 2-way products). | Lin coefficient on Pi-model predictions / observed: Z_P ratio 0.39 [0.10, 0.74] (undecided); Z_I ratio 0.55 [0.11, 1.02] (undecided). | HYPOTHESIS | Ratio CI entirely below 0.5 → reject; above 0.5 → support. |
| CL-08 | The s:H:W 3-way term of Z_P is a Pi-group effect. | Declared test is structurally empty: a Pi model with 2-way products cannot produce a 3-way W term (ratio = 0 by construction). | HYPOTHESIS (not tested) | Pi model with the rho·s~·H/s product reproducing ≥ 50 % of the term. |
| CL-09 | The Z_I det2 W interactions (s:W, s:H:W) have a Pi-group origin. | No discriminating test declared. | HYPOTHESIS (not tested) | As CL-07 within det2. |
| CL-10 | Pressure, Z = 10: the det2 > det1 difference is carried by non-line-of-sight cells (less NLOS deficit in det2), not by the charge street(s). | Mean ln P-ratio det2-det1 = +0.151; contribution S +0.120 [+0.085, +0.157] (holds), S - C +0.092 [+0.058, +0.127] (holds). NLOS mean ln P-ratio det1 -0.114, det2 +0.023. | SUPPORTED | S - C CI below 0 at Z = 10 on any re-stratification with a different wall/LOS rule. |
| CL-11 | Pressure, Z = 10: channelling (two charge streets in det2) carries the det2 > det1 difference. | Contribution C +0.028 [+0.002, +0.058] (holds), but C - S -0.092 [-0.127, -0.058] (opposite). | REJECTED (as the dominant carrier) | — |
| CL-12 | Pressure, Z = 5: the det difference is carried by channel or by NLOS cells. | Total +0.211; C +0.106 [+0.067, +0.155] (holds), S +0.102 [+0.068, +0.139] (holds), C - S +0.004 [-0.057, +0.064] (undecided). Channel area fraction det1 0.21, det2 0.43; channel mean ln P-ratio det1 0.511, det2 0.475 (C share is composition). | HYPOTHESIS (both carry it equally) | C - S CI excluding 0 in either direction. |
| CL-13 | Impulse, Z = 5: the det2 > det1 difference is carried by the charge street(s) (channelling; composition: channel area doubles). | Total +0.080; C +0.089 [+0.042, +0.150] (holds), C - S +0.099 [+0.035, +0.176] (holds). | SUPPORTED | C - S CI including or below 0 under another stratification. |
| CL-14 | Impulse, Z = 5: NLOS relief carries the det difference. | S -0.010 [-0.040, +0.017] (undecided), S - C -0.099 [-0.176, -0.035] (opposite). | REJECTED | — |
| CL-15 | Impulse, Z = 10: channel or NLOS carries the det difference. | Total +0.036; C +0.033 [+0.002, +0.073] (holds), S +0.011 [-0.011, +0.031] (undecided), C - S +0.022 [-0.016, +0.065] (undecided). | HYPOTHESIS | C - S CI excluding 0. |
| CL-20 | Pressure: the rho (density) trend is channelling (lives in the charge street). | Sp(rho, m_C P Z5) +0.733 [+0.441, +0.902] (holds) but C - NLOS +0.049 [-0.194, +0.355] (undecided); Z10: +0.316 [-0.085, +0.663] (undecided), diff -0.337 [-0.733, +0.117] (undecided). | HYPOTHESIS (trend equally present in channel and NLOS cells) | C - NLOS difference CI excluding 0. |
| CL-21 | Impulse: the rho trend is channelling. | Z5 Sp_C +0.532 [+0.097, +0.855] (holds); Z10 C - NLOS -0.366 [-0.664, -0.076] (opposite) (stronger in NLOS). | REJECTED | — |
| CL-22 | The rho trend is wall-reflection superposition near walls in line of sight. | Sp(rho, wall advantage Z2): P -0.438 [-0.546, -0.217] (opposite), I -0.553 [-0.685, -0.303] (opposite) (wall advantage falls with density). | REJECTED | — |
| CL-23 | The raw block-size b trend (B1 b main, rP/rI Z2–5 b+) is channelling / wall reflection. | P: Sp(b, m_C Z10) +0.378 [+0.039, +0.650] (holds), C - NLOS +0.262 [-0.270, +0.786] (undecided); I wall decay -0.410 [-0.761, -0.040] (opposite). | HYPOTHESIS (channelling); REJECTED (wall reflection, impulse) | C - NLOS difference CI excluding 0. |
| CL-30 | The street-width trend (s, s~ negative) is channelling (lives in the charge street). | P Z5 Sp(s~, m_C) -0.658 [-0.871, -0.268] (holds); P Z10 C - NLOS +0.957 [+0.634, +1.299] (opposite); I Z10 C - NLOS +0.621 [+0.321, +1.036] (opposite); raw s P Z10 +0.562 [+0.140, +0.968] (opposite) — the trend is stronger in NLOS cells. | REJECTED | — |
| CL-31 | The street-width trend is wall-reflection superposition. | Sp(s~, wall advantage Z2): P +0.479 [+0.254, +0.564] (opposite), I +0.505 [+0.143, +0.661] (opposite); raw s P +0.558 [+0.394, +0.620] (opposite) (wall advantage grows with width). | REJECTED | — |
| CL-40 | Raw height H raises impulse more than peak pressure: positive-phase lengthening (τ proxy) carries the H effect on impulse targets. | Sp(H, mean ln τ): Z5 +0.392 [+0.009, +0.602] (holds), Z10 +0.539 [+0.267, +0.735] (holds); mean ln τ at Z10: H4 0.09 → H24 0.33. | SUPPORTED (proxy τ = (I/I_ff)/(P/P_ff), not a measured duration) | Gauge time histories showing equal positive-phase duration across H → reject. |
| CL-41 | Raw height H acts through peak-pressure channelling. | Sp(H, ln P-ratio Z10) -0.120 [-0.529, +0.303] (undecided); minus Sp(H, τ) -0.659 [-1.222, -0.039] (opposite). | REJECTED | — |
| CL-42 | The H/s trends (Lambda_I, Z_I, R_I, rI and rP_P95 rings; Lambda_P det1) are positive-phase lengthening or peak channelling. | Sp(H/s, τ) Z5 +0.192 [-0.185, +0.473] (undecided), Z10 +0.282 [-0.116, +0.577] (undecided); Sp(H/s, P-ratio) Z10 +0.361 [-0.067, +0.620] (undecided). | HYPOTHESIS (neither discriminated with H/s; see CL-40 for raw H) | Either Spearman CI excluding 0 with the other inside 0. |
| CL-50 | The Z_P H-effect reversal along s, wide-street side: taller blocks deepen the NLOS pressure deficit at s = 20. | s = 20: Sp(H, m_S P Z10) -0.741 [-0.840, -0.347] (holds). | SUPPORTED | Sp CI including 0 or positive in an independent wide-street subset. |
| CL-51 | The Z_P H-effect reversal, narrow-street side: taller walls confine the channel at s = 5. | s = 5: Sp(H, m_C P Z10) +0.332 [-0.367, +0.699] (undecided). | HYPOTHESIS | Sp CI excluding 0. |
| CL-52 | Impulse rho×s~ product (Z_I, Lambda_I) is carried by NLOS cells. | NLOS I-ratio product coef +0.179 [+0.020, +0.336] (holds); channel +0.041 [-0.217, +0.392] (undecided). | SUPPORTED (NLOS); HYPOTHESIS (channel) | NLOS coefficient CI including 0 under another stratification. |
| CL-53 | Pressure rho×s~ product (Z_P) is carried by channel or NLOS cells. | Channel +0.122 [-0.212, +0.642] (undecided); NLOS -0.031 [-0.303, +0.211] (undecided). | HYPOTHESIS | Either CI excluding 0. |
| CL-54 | rho×H/s product (Z_P, Lambda_I) is carried by channel or NLOS cells. | P: C +0.293 [-0.073, +1.000] (undecided), S +0.221 [-0.088, +0.415] (undecided); I: C +0.233 [-0.045, +0.720] (undecided), S +0.090 [-0.074, +0.232] (undecided). | HYPOTHESIS | Either CI excluding 0. |
| CL-60 | The Lambda_P break in s~ at 1.54 is a channel regime change or a wall-reflection regime change. | Channel advantage: slope below +0.203 [+0.127, +0.258] (opposite), change -0.444 [-0.660, -0.222] (opposite); wall advantage: slope below +0.054 [+0.020, +0.089] (opposite), change +0.331 [+0.283, +0.388] (holds). | REJECTED (both) | — (break stays unexplained; open). |
| CL-70 | The Z_I collapse onto zeta = 2.24 ln rho + ln s~ + 0.94 ln H/s tracks the channel impulse ratio. | Sp(zeta, ln Z_I) +0.883 [+0.732, +0.950] (holds); Sp(zeta, m_C I Z10) +0.688 [+0.370, +0.868] (holds); Sp(zeta, τ) +0.208 [-0.120, +0.515] (undecided). | SUPPORTED (channel); HYPOTHESIS (positive-phase lengthening) | Channel Spearman CI including 0 on held-out families. |
| CL-80 | Slope_P trends (s~-, s-, det-) are near-field wall reflection decaying with range, or channel growth with range. | Sp(wall adv Z2, Slope_P) -0.260 [-0.496, +0.048] (undecided); Sp(channel growth, Slope_P) -0.294 [-0.583, +0.071] (undecided). | HYPOTHESIS | Either CI excluding 0. |
| CL-90 | det-interaction patterns (det×s on Z_I; Δ of s~, H/s on Lambda; C1 Δ rows; A1 Δa) come from the two-channel layout of det2. | No discriminating test declared for the interaction itself. | HYPOTHESIS (not tested) | Det-split decomposition of the input trend by stratum. |

## Context (descriptive, not a claim)
- R_conv edge annulus [0.8, 1.2]·R_conv: median share of non-converged EXCESS area in NLOS cells = 0.932 (P), 0.993 (I); their area share 0.882 / 0.928; channel cells 0.001 / 0.004. Deficit cells are 1.2 % of non-converged edge area (the criterion pins P < 10 kPa and scaled I < floor), so a shielding deficit essentially cannot set R_conv.
- Analytic block layout = sentinel mask on grids 1–2 (≥ 0.99997); grid 3 differs only at x > 480 m (city edge).

## Pattern → claim map (all 139 passed keys + B2/post-hoc)

| fam | target | input | passed in | claims |
|---|---|---|---|---|
| A1 | R_I | a-1/3 (common a, geometry FE) | pooled,det2,delta | CL-02, CL-03 |
| A2b | Z_I | beta_lnW / Pi groups (quad+products) | pooled | CL-02, CL-03 |
| B1 | Z_P | W | pooled | CL-04b, CL-05 |
| B1 | Z_P | b:W | pooled | CL-07 |
| B1 | Z_P | s:H:W | pooled,det2 | CL-08 |
| B1 | Z_I | det | pooled | CL-13, CL-14, CL-15 |
| B1 | Z_I | s | delta | CL-30, CL-31, CL-90 |
| B1 | Z_I | W | pooled,det2 | CL-02, CL-03, CL-90 |
| B1 | Z_I | b:W | pooled,det2 | CL-07 |
| B1 | Z_I | s:W | det2 | CL-09 |
| B1 | Z_I | s:H:W | det2 | CL-09 |
| B1 | R_P | W | pooled,det1,det2 | CL-01 |
| B1 | R_I | W | pooled,det1,det2 | CL-01 |
| B3 | Z_P | det | pooled | CL-10, CL-11, CL-12 |
| B3 | Z_P | l_rhoc | pooled,det1,det2 | CL-20, CL-22 |
| B3 | Z_P | l_rhoc*l_stc | pooled,det1,det2 | CL-53 |
| B3 | Z_P | l_rhoc*l_hsc | pooled | CL-54 |
| B3 | Z_I | det | pooled | CL-13, CL-14, CL-15 |
| B3 | Z_I | l_rhoc | pooled,det1,det2 | CL-21, CL-22 |
| B3 | Z_I | l_stc | pooled,det2,delta,delta_term | CL-30, CL-31, CL-90 |
| B3 | Z_I | l_hsc | pooled,det1,det2 | CL-42 |
| B3 | Z_I | l_rhoc*l_stc | pooled,det2 | CL-52 |
| B3 | Lam_P | det | pooled | CL-10, CL-11, CL-12 |
| B3 | Lam_P | l_stc | pooled,det1,det2 | CL-30, CL-31 |
| B3 | Lam_P | l_hsc | det1,delta,delta_term | CL-42, CL-90 |
| B3 | Lam_I | det | pooled | CL-13, CL-14, CL-15 |
| B3 | Lam_I | l_stc | det1,delta,delta_term | CL-30, CL-31, CL-90 |
| B3 | Lam_I | l_hsc | pooled,det1,det2,delta,delta_term | CL-42, CL-90 |
| B3 | Lam_I | l_rhoc*l_stc | pooled,det1,det2 | CL-52 |
| B3 | Lam_I | l_rhoc*l_hsc | pooled | CL-54 |
| C1 | R_P | s~ | pooled,det1,det2 | CL-30, CL-31 |
| C1 | R_P | W | pooled,det1,det2 | CL-01 |
| C1 | R_P | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12 |
| C1 | R_I | rho | pooled,det1,det2 | CL-21, CL-22 |
| C1 | R_I | s~ | pooled,det1,det2 | CL-30, CL-31, CL-90 |
| C1 | R_I | H/s | pooled,det1,det2 | CL-42 |
| C1 | R_I | W | pooled,det1,det2 | CL-01 |
| C1 | R_I | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | R_I | H | pooled,det2 | CL-40, CL-41 |
| C1 | R_I | det (paired det2-det1) | pooled | CL-13, CL-14, CL-15 |
| C1 | Z_P | rho | pooled,det1,det2 | CL-20, CL-22 |
| C1 | Z_P | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12 |
| C1 | Z_I | rho | pooled,det1,det2,delta | CL-21, CL-22, CL-90 |
| C1 | Z_I | s~ | pooled,det1,delta | CL-30, CL-31, CL-90 |
| C1 | Z_I | H/s | pooled,det1,det2 | CL-42 |
| C1 | Z_I | s | pooled,det1,delta | CL-30, CL-31, CL-90 |
| C1 | Z_I | det (paired det2-det1) | pooled | CL-13, CL-14, CL-15 |
| C1 | Lam_P | rho | pooled,det1 | CL-20, CL-22 |
| C1 | Lam_P | s~ | pooled,det1,det2 | CL-30, CL-31 |
| C1 | Lam_P | W | pooled,det1,det2 | CL-04b, CL-05 |
| C1 | Lam_P | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | Lam_P | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12 |
| C1 | Lam_I | rho | pooled,det1 | CL-21, CL-22 |
| C1 | Lam_I | s~ | pooled,det1,det2,delta | CL-30, CL-31, CL-90 |
| C1 | Lam_I | H/s | pooled,det1,det2 | CL-42 |
| C1 | Lam_I | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | Lam_I | det (paired det2-det1) | pooled | CL-13, CL-14, CL-15 |
| C1 | Slope_P | s~ | pooled,det1 | CL-30, CL-31, CL-80 |
| C1 | Slope_P | s | pooled,det1 | CL-30, CL-31, CL-80 |
| C1 | Slope_P | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12, CL-80 |
| C1 | rP_med_Z2 | rho | pooled,det2,delta | CL-20, CL-22, CL-90 |
| C1 | rP_med_Z2 | s~ | det2,delta | CL-30, CL-31, CL-90 |
| C1 | rP_med_Z2 | H/s | delta | CL-42, CL-90 |
| C1 | rP_med_Z2 | b | pooled,det1 | CL-23 |
| C1 | rP_med_Z2 | s | det2,delta | CL-30, CL-31, CL-90 |
| C1 | rP_med_Z2 | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12 |
| C1 | rP_P5_Z2 | H/s | pooled,det1 | CL-42 |
| C1 | rP_P5_Z2 | b | pooled,det1,det2,delta | CL-23, CL-90 |
| C1 | rP_P5_Z2 | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12 |
| C1 | rP_P95_Z2 | rho | pooled,det1,det2 | CL-20, CL-22 |
| C1 | rP_P95_Z2 | s~ | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rP_P95_Z2 | H/s | pooled,det2 | CL-42 |
| C1 | rP_P95_Z2 | W | pooled,det1,det2 | CL-04b, CL-05 |
| C1 | rP_P95_Z2 | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rI_med_Z2 | rho | pooled,det1,det2 | CL-21, CL-22 |
| C1 | rI_med_Z2 | s~ | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rI_med_Z2 | H/s | pooled,det2 | CL-42 |
| C1 | rI_med_Z2 | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rI_med_Z2 | det (paired det2-det1) | pooled | CL-13, CL-14, CL-15 |
| C1 | rI_P5_Z2 | b | pooled,det2,delta | CL-23, CL-90 |
| C1 | rI_P95_Z2 | rho | pooled,det1,det2 | CL-21, CL-22 |
| C1 | rI_P95_Z2 | s~ | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rI_P95_Z2 | H/s | pooled,det1,det2 | CL-42 |
| C1 | rI_P95_Z2 | W | pooled,det1,det2 | CL-06, CL-90 |
| C1 | rI_P95_Z2 | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rP_med_Z5 | rho | pooled,det1,det2 | CL-20, CL-22 |
| C1 | rP_med_Z5 | s~ | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rP_med_Z5 | b | pooled,det2 | CL-23 |
| C1 | rP_med_Z5 | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rP_med_Z5 | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12 |
| C1 | rP_P5_Z5 | rho | pooled,det2 | CL-20, CL-22 |
| C1 | rP_P5_Z5 | W | delta | CL-04b, CL-05, CL-90 |
| C1 | rP_P5_Z5 | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12 |
| C1 | rP_P95_Z5 | rho | pooled,det1,det2 | CL-20, CL-22 |
| C1 | rP_P95_Z5 | s~ | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rP_P95_Z5 | H/s | pooled,det1 | CL-42 |
| C1 | rP_P95_Z5 | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rP_P95_Z5 | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12 |
| C1 | rI_med_Z5 | rho | pooled,det1,det2 | CL-21, CL-22 |
| C1 | rI_med_Z5 | s~ | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rI_med_Z5 | H/s | pooled,det1,det2 | CL-42 |
| C1 | rI_med_Z5 | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rI_med_Z5 | det (paired det2-det1) | pooled | CL-13, CL-14, CL-15 |
| C1 | rI_P5_Z5 | rho | pooled,det1,det2 | CL-21, CL-22 |
| C1 | rI_P5_Z5 | s~ | pooled,det1,delta | CL-30, CL-31, CL-90 |
| C1 | rI_P5_Z5 | H/s | pooled,det1 | CL-42 |
| C1 | rI_P5_Z5 | s | pooled,det1,delta | CL-30, CL-31, CL-90 |
| C1 | rI_P95_Z5 | rho | pooled,det1,det2 | CL-21, CL-22 |
| C1 | rI_P95_Z5 | s~ | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rI_P95_Z5 | H/s | pooled,det1 | CL-42 |
| C1 | rI_P95_Z5 | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rP_med_Z10 | rho | pooled,det1,det2 | CL-20, CL-22 |
| C1 | rP_med_Z10 | s~ | pooled,det1,det2,delta | CL-30, CL-31, CL-90 |
| C1 | rP_med_Z10 | W | pooled,det1 | CL-04b, CL-05 |
| C1 | rP_med_Z10 | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rP_med_Z10 | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12 |
| C1 | rP_P5_Z10 | rho | det1 | CL-20, CL-22 |
| C1 | rP_P5_Z10 | s~ | det1 | CL-30, CL-31 |
| C1 | rP_P5_Z10 | W | det1 | CL-04b, CL-05 |
| C1 | rP_P5_Z10 | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12 |
| C1 | rP_P95_Z10 | rho | pooled,det1,det2 | CL-20, CL-22 |
| C1 | rP_P95_Z10 | s~ | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rP_P95_Z10 | s | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rP_P95_Z10 | det (paired det2-det1) | pooled | CL-10, CL-11, CL-12 |
| C1 | rI_med_Z10 | rho | pooled,det1,det2,delta | CL-21, CL-22, CL-90 |
| C1 | rI_med_Z10 | s~ | pooled,det1,delta | CL-30, CL-31, CL-90 |
| C1 | rI_med_Z10 | H/s | pooled,det1,det2 | CL-42 |
| C1 | rI_med_Z10 | s | pooled,det1,delta | CL-30, CL-31, CL-90 |
| C1 | rI_P5_Z10 | rho | pooled,det1 | CL-21, CL-22 |
| C1 | rI_P5_Z10 | s~ | pooled,det1 | CL-30, CL-31 |
| C1 | rI_P5_Z10 | H/s | pooled,det1 | CL-42 |
| C1 | rI_P5_Z10 | s | pooled,det1,delta | CL-30, CL-31, CL-90 |
| C1 | rI_P95_Z10 | rho | pooled,det1,det2,delta | CL-21, CL-22, CL-90 |
| C1 | rI_P95_Z10 | s~ | pooled,det1,det2 | CL-30, CL-31 |
| C1 | rI_P95_Z10 | H/s | pooled,det1,det2 | CL-42 |
| C1 | rI_P95_Z10 | b | delta | CL-23, CL-90 |
| C1 | rI_P95_Z10 | s | pooled,det1,det2 | CL-30, CL-31 |
| C2 | Lam_P | break in ln s~ | pooled,det2 | CL-60 |
| C3 | Z_I | collapse vs best single Pi | pooled | CL-70 |
| B2 | Z_P | H effect reverses along s (s≈10.1 m) | – | CL-50, CL-51 |
| B2 | Z_P | W effect reverses along b (b≈22.6 m) | – | CL-07 |
| B1 post-hoc | Z_P/Z_I | s:H (post-hoc LOGO) | – | CL-50, CL-51 |
| B1 post-hoc | Z_P/Z_I | b, s, H mains (post-hoc LOGO) | – | CL-23, CL-30, CL-40/CL-42 |
