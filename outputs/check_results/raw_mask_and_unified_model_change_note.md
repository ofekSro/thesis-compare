# Results-of-record change note: raw-field mask, merged MaxR level, unified RadiusI model

Date: 2026-09-27. Branch `audit-fixes-2026-09-27` (owner-approved execution
of the consolidated proposal; merge decision pending). Every number below
regenerates from the code at the same commit with
`python run_analysis.py --phase all --n-iter 500`.

## What changed, in one paragraph

Three measurement fixes from the 2026-09-27 audit were adopted: the
building-footprint mask is computed on the RAW solver field before the
cross-grid max-fill (wall-skin sentinel cells no longer enter the scans;
ALG-01/PHY-01, decision D2b); the per-direction MaxR level is sampled from
the reference field max-filled across grids, like the urban field it is
compared with (PHY-04a); and cv_summary gains deployable-domain columns
z_P_dep / z_I_dep (STA-02/ALG-03, D3 a+b). On the sentinel-free data the
separable RadiusI power law fails structurally, so the production RadiusI
model was replaced by one shared five-term form (coefficients per det).
The impulse criterion (thr_I_scaled = 20) and the K = 3 streak rule were
re-examined on the clean store and KEPT — see
`impulse_criterion_sensitivity_note.md`.

## Convergence radii (96 configurations)

| quantity | old record | new record |
|---|---|---|
| RadiusP, median change | — | +5.0% (p10 +1.2, p90 +26.4, max +66.0; 28/96 beyond 10%) |
| RadiusI, median change | — | -31.7% (p10 -56.2, p90 -3.6, max -65.9; 80/96 beyond 10%) |
| median Z_conv,P | 8.99 | 9.88 |
| median Z_conv,I | 11.61 | 7.58 |
| beyond_P rows (of 1920) | 1170 | 1086 |
| beyond_I rows (of 1920) | 1080 | 1361 |

The old RadiusI was largely an artefact: its outermost violation streaks
lay INSIDE building walls (sentinel cells), i.e. it measured the position
of the outermost wall inside the I_ff/W^(1/3) = 20 contour. Thesis-facing
statements that flip with the fix:

* "impulse converges ~1.5x further than pressure (Z 11.6 vs 7.5)" —
  REVERSES: 7.6 (I) vs 9.9 (P, soft) on the clean store.
* the "clean Hopkinson scaling" of RadiusI was inherited from the
  artefact contour (Z500/Z50 0.986 -> 0.760 after the fix).
* MaxR / Z_urban measurements are essentially unchanged (only the
  fit/validity masks move through R_conv and the PHY-04 level fix).

## Anchors (method='req', raw store)

| config | old P | new P | new I |
|---|---|---|---|
| config_93_det2_b10_s5_h15_w250 | 62.328853560057645 | 64.6464183290751 | 68.1610404157357 |
| config_95_det2_b10_s5_h24_w250 | 38.15139013777145 | 39.930952732324215 | 64.22452586218307 |

Pinned in `tests/test_npz_anchors.py::RAW_ANCHORS`. The v1/v2 anchors keep
guarding the old baked-in criterion (those stores load verbatim).

## Production coefficients

RadiusP (additive form, unchanged structure):

| det | C0 | C1 | C2 | C3 | a | old C0/C1/C2/C3 |
|---|---|---|---|---|---|---|
| 1 | 10.0472 | -0.9627 | 3.0965 | 0.5319 | 1 | 9.0631 / -0.6451 / 2.0181 / 0.5908 |
| 2 | 11.7661 | -0.8632 | 2.2975 | 0.6999 | 2 | 11.8576 / -1.3754 / 2.7820 / 0.7758 |

RadiusI — model REPLACED. Old (power law):
det1 A=14.9363 p=0.2031 q=0.0238 r=0.0653 r2=-0.1005;
det2 A=14.6024 p=0.1759 q=0.0790 r=0.1251 r2=-0.0889.
(The near-zero geometry exponents are the artefact's signature: the old
target was ~A*W^(1/3) with wall-position corrections.)

New (unified form, one structure for both dets):

    Z = A * Pi2^(C4 + C5*ln(rho) + C3*ln(H/s))
          * exp(C1*rho*sqrt(H/s) + C2*ln(H/s)^2)

| det | A | C1 trap | C2 sat | C3 hs·pi2 | C4 pi2 | C5 rho·pi2 |
|---|---|---|---|---|---|---|
| 1 | 4.1822 | +1.1445 | -0.2277 | -0.2755 | +0.5039 | +0.2623 |
| 2 | 4.8674 | +1.0645 | -0.1272 | -0.1653 | +0.7051 | +0.4118 |

Every coefficient is significant in both groups (worst p = 5e-4, OLS in
ln space, n = 48 per det); robust (bisquare) refit moves coefficients by
at most ~10%, so the config_91 outlier does not drive the fit.

## Z_urban coefficients (form unchanged; rows move via the masks and the PHY-04 level)

| det/target | old | new |
|---|---|---|
| 1 P (C0, C1, A, B) | 0.0911, 2.5468, 2.9191, 7.1392 | 0.0974, 2.6798, 3.0186, 7.8188 |
| 2 P (C0, C1, A, B) | 0.1128, 0.4320, 2.1697, 0.9433 | 0.1108, 0.5619, 2.1074, 1.4108 |
| 1 I (C0, C1, C2, C3) | -0.1079, 3.0884, 0.8573, 1.5496 | -0.1302, 3.0325, 0.8977, 1.1211 |
| 2 I (C0, C1, C2, C3) | +0.0068, 2.6644, 1.0985, 0.7614 | +0.0044, 2.6643, 1.0905, 0.6908 |

## Error metrics

cv_summary medians (500 splits, stratified by det — sibling-optimistic;
quote LOGO for geometry generalisation):

| metric | old | new |
|---|---|---|
| conv_P | 8.79% | 9.82% |
| conv_I | 7.15% | 11.10% |
| z_P | 8.42% | 8.69% |
| z_I | 9.40% | 10.43% |
| z_P_dep (deployable domain) | — | 8.73% |
| z_I_dep (deployable domain) | — | 13.23% |

LOGO (leave-one-(det,b,s,H)-family-out), convergence radii, clean store:

| model | street | intersection |
|---|---|---|
| RadiusP (production additive) | 9.0% mean / 7.4% median | 10.2% / 7.3% |
| RadiusI old power law | 16.4% | 15.2% |
| RadiusI unified (production) | 12.5% mean / 9.2% median | 9.6% / 7.2% |

Honest caveats, to be carried into any thesis text:

* the old conv_I figures (7.15% CV, ~6.3% in-sample) were artefact-easy —
  the model was predicting wall geometry; they are not a baseline the
  clean measurement should be compared against;
* the unified form was SELECTED by LOGO comparison over candidate forms
  on these 96 configurations, and is fixed from now on; the reported
  errors are those of the selected form (no nested selection);
* z_I_dep > z_I by ~3 pp: the conditional error understates the error on
  the domain a user can identify beforehand; both are now on record;
* an in-sample noise-floor probe (rich 12-term pooled fit) stops at
  ~9.5% (street) / 5.8% (intersection), so the unified form sits close
  to what this dataset can support.
