# Impulse-criterion sensitivity: thr_I_scaled and the K=3 streak rule

Date: 2026-09-27. Owner-approved study run on the raw-mask store (the
sentinel-free measurement adopted the same day; see ALG-01/PHY-01 in
`docs/audit/2026-09-27/`). Generating scripts:
`docs/audit/2026-09-27/scripts/thr_scan.py`, `k_sensitivity.py`,
`thr_scan_analyze.py`. Data: `data/raw_npz`, all 96 configurations,
hard `req` sector scan (the impulse path is identical under `req_soft3`).

## Why this note exists

The original rationale for `thr_I_scaled = 20` ("loosest-but-lowest value
giving 100% convergence", "~1.8x looser than pressure") was calibrated on
the pre-mask store, where building-skin sentinel cells drove RadiusI. On
the clean store that rationale no longer describes the measurement, so the
value was re-examined — and kept, on the evidence below.

## 1. Threshold sweep (`thr_I_sensitivity_scan.csv`)

RadiusI recomputed for thr_I in {5, 10, 15, 20, 30, 40} Pa.s/kg^(1/3)
(columns `RI_5` .. `RI_40`, metres). Validation: the thr = 20 column
reproduces `convergence_table_req_soft3.csv` RadiusI to 1.4e-14 m.

LOGO mean error of the production unified RadiusI form, fitted per
threshold (street / intersection):

| thr | median Z_conv,I | LOGO street | LOGO intersection |
|----:|----:|----:|----:|
|  5 | 24.9 | 23.6% | 29.6% |
| 10 | 13.8 | 22.6% | 19.0% |
| 15 |  9.4 | 14.2% | 10.1% |
| 20 |  7.6 | 12.2% |  9.6% |
| 30 |  5.3 | 12.5% | 15.1% |
| 40 |  3.6 | 13.0% | 21.4% |

Reading: stricter bands push the radius into the far, low-signal field
(seam- and noise-dominated); looser bands push it into the discrete near
field. thr = 20 sits at the stability/predictability optimum. This is a
post-hoc check of a value fixed beforehand, not a selection on the metric.
Sensitivity of the radius itself: d ln R / d ln thr ~ -0.7 across the
sweep (comparable to the documented -0.6 pressure-threshold elasticity).

## 2. K-streak sweep (`k_sensitivity_scan.csv`)

Hard-scan radii for K_CONSECUTIVE in {2, 3, 4}, both loads (columns
`P_2` .. `I_4`, metres). |d ln R| when K changes:

| step | load | median | p90 | configs > 10% |
|---|---|---:|---:|---:|
| K 2->3 | P | 0.9% | 3.1% | 1/96 |
| K 2->3 | I | 1.0% | 6.4% | 9/96 |
| K 3->4 | P | 0.7% | 2.0% | 0/96 |
| K 3->4 | I | 0.4% | 2.2% | 2/96 |

Reading: both loads sit on a stable plateau at K = 3. In particular the
impulse radius is NOT streak-brittle on the clean store — the large
geometry-to-geometry impulse jumps are physics (multiplicative canyon
trapping), not scanner noise. This is why the impulse scan remains HARD
while the pressure scan is soft (the soft path exists to treat pressure's
mesh-noise cliffs, and would import the cell-count bias documented in
ALGORITHM's mesh-sensitivity note into a measurement that does not need
the cure). The configs that do move >10% at K 2->3 are the singleton
intermediate geometries (e.g. config_87, config_92) — the same families
that dominate the LOGO error tail.

## 3. Damage anchoring: thr_I is a load-fidelity band (owner decision, 2026-09-27)

Why thr_I cannot be a damage threshold, and what anchors it instead:

- **Structural incompatibility.** Impulse damage criteria are absolute,
  target-specific P-I curves; a Hopkinson-admissible band must scale as
  W^(1/3). An absolute damage impulse picks a different scaled contour
  for every charge weight — the exact inadmissibility the criterion was
  rebuilt to remove.
- **Human primary injury is pressure-bounded at these ranges.** UFC
  3-340-02 Fig. 1-2 (p. 94, lung survival curves, i scaled by BODY weight
  Wh — not charge weight): the threshold curve's pressure asymptote is
  ~10 psi ~ 69 kPa — below that overpressure there is no lung damage at
  ANY impulse. The 69 kPa free-field contour sits at Z ~ 3.7-3.8, deep
  inside R_conv,I (median Z 7.6): the human-relevance zone ends well
  before the convergence radius, so R_conv,I is generously conservative
  for primary blast injury.
- **The vertical asymptote was evaluated as a floor and REJECTED.** The
  figure's impulsive asymptote gives an absolute human floor
  i_min ~ 3.5 psi.ms/lb^(1/3) x Wh^(1/3): 85 / 129 / 146 Pa.s for
  Wh = 20 / 70 / 100 kg. Where I_ff drops to 129 Pa.s (70 kg):
  Z = 7.8 (W=50), 13.4 (250), 16.8 (500), beyond 20 for W >= 1000.
  Adding it to the criterion would cut 17 of the 24 W=50 configurations
  (and none of any other weight), i.e. it re-introduces a charge-
  dependent contour, breaks the Z-collapse the regression framework
  rests on, and hangs on an arbitrary body-weight choice (Z_floor at
  W=50 moves 7.8 -> 11.9 between a 70 kg adult and a 20 kg child).
  Human-relevance radii belong to a separate product: R_human, the
  distance where the urban (P, I) point crosses the full Fig. 1-2 curve
  (both asymptotes), per configuration and declared target — future
  work under proposal aim 4.
- **What the band means where it bites.** At the measured production
  radii, 20 Pa.s/kg^(1/3) equals a median 55% of the local free-field
  impulse (p10 36%, p90 92%, max 145%): an engineering-
  indistinguishability band. This replaces the artefact-era "~83% of
  I_ff / 1.8x looser than pressure" description. The framework's damage
  anchoring lives on the pressure side (IATG 02.20 Table 8 bracket).

Generating script: docs/audit/2026-09-27/scripts/impulse_anchor.py and
human_floor_test.py.
