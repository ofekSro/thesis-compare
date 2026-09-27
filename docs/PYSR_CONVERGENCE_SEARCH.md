# Symbolic regression on the convergence radii (RadiusP, RadiusI)

PySR search over the Pi groups, scored by config-grouped leave-one-geometry-out
with constants refit per fold. Same protocol as the Z_urban search that produced
`range_switch` / `canyon_trap`.

**No pipeline code was changed.** This is a search report.

## Protocol

- **Features**: the three Pi groups only — `rho`, `Pi_3 = H/s`, `Pi_2 = s/W^(1/3)`.
- **Target**: `Z = R / W^(1/3)`, so Hopkinson scaling is imposed by construction
  and `W` enters only through `Pi_2`.
- **Objective inside PySR**: relative error `((p-y)/y)^2`, MAPE-aligned, because
  the quantity of interest is % error, not absolute.
- **Arbiter (outside PySR)**: LOGO over the 18 `(b,s,H)` families per det,
  constants refit per fold, multistart to avoid local minima. PySR proposes;
  this decides.
- **Rejection rule**: a large in-sample/out-of-fold gap kills a candidate
  regardless of how good its in-sample fit is.
- **Extra schemes** (candidates were *not* tuned against these): leave-one-charge-out
  (LOCO-W) and leave-one-building-size-out (LOBO-b).
- Data: `outputs/tables/convergence_table_req.csv`, 96 configs, 48 per det.

Baseline rows are the current shipped forms, refit with the exact pipeline
fitters (`_fit_pi_group`, `_fit_impulse_group`) — reproducing the reported
41.4 / 43.3 figures exactly.

## Headline

**RadiusI: a real structural improvement.** Max error 38.5% → 20.6%, and the
mean improves too. Confirmed by three independent PySR seeds and three CV schemes.

**RadiusP: no candidate survived.** The best LOGO result (29.1%) collapsed to
63% under leave-one-charge-out — it had overfit the LOGO scheme itself. The
shipped form stays.

## RadiusI — results

All values are out-of-fold unless labelled in-sample. Pooled over both dets.

| model | k | in mean | in max | **LOGO mean** | **LOGO max** | gap mean | gap max | LOCO-W max | LOBO-b max |
|---|---|---|---|---|---|---|---|---|---|
| **baseline** `A*rho^p*(H/s)^q*Pi2^r` (shipped) | 4 | 7.64 | 34.44 | 8.55 | 40.4* | 0.91 | 4.05 | 45.63 | 43.27 |
| **(a)** `C0 + C1*rho*(H/s)^q*exp(-k/Pi2)/Pi2` | 4 | 5.76 | 19.45 | **6.37** | 23.42 | 0.61 | 3.97 | 27.75 | 32.16 |
| **(b)** `(rho*(H/s)^q + B)*(A - 1/Pi2)` | 3 | 7.84 | 19.61 | 8.20 | **20.61** | 0.36 | **1.01** | 25.21 | 25.93 |
| **(c)** `C0 + rho*(H/s)*(A - 1/Pi2)` | 2 | 7.80 | 22.12 | 8.34 | 22.98 | 0.54 | **0.86** | 24.66 | 26.04 |

\* pooled LOGO max for the baseline is 38.48 on ZI; 40.4 is the RadiusP figure.
Per-det RadiusI baseline: det1 38.48, det2 35.13.

Per-det max for the candidates: (a) 23.42 / 19.08, (b) 18.76 / 20.61,
(c) 22.98 / 20.01.

### Fitted constants (all 96 configs)

| form | det1 | det2 |
|---|---|---|
| (a) `[C0, C1, k, q]` | `8.875, 24.632, 1.100, 0.069` | `10.186, 18.003, 1.415, 0.573` |
| (b) `[A, B, q]` | `9.914, 0.867, 0.138` | `7.819, 1.285, 0.369` |
| (c) `[C0, A]` | `10.293, 2.838` | `10.658, 3.051` |

### Per-term physical reading

The two spellings encode the *same* mechanism, found independently by three seeds:

- **`(A - 1/Pi2)`** / **`exp(-k/Pi2)/Pi2`** — a **near-field cutoff**. The impulse
  convergence radius stops growing as the street narrows relative to the charge.
  This is the opposite of the shipped power law, whose `Pi2^r` is monotone and
  unbounded, and the opposite of a pole: narrow streets **saturate** rather than
  diverge. In form (b)/(c) the term changes sign at `Pi_2 = 1/A` (≈ 0.35 det1,
  ≈ 0.33 det2) — below that scaled street width the canyon stops adding radius
  and starts removing it. Physically: once the street is much narrower than the
  charge's Hopkinson length, the positive phase is already fully confined; extra
  confinement cannot extend the impulse radius further, and venting losses take over.
- **`rho * (H/s)^q`** — trapping strength: wall continuity times canyon aspect,
  the same product that appears in `canyon_trap` for Z_urban impulse. The fitted
  `q` is small (0.07–0.37), so the aspect dependence is weak — consistent with
  impulse being set mainly by *whether* the canyon closes, not how tall it is.
- **`C0` / the `B` offset** — a free-field floor. Ablating it sends the error to
  100%: without a floor the model must explain the entire radius with geometry,
  and there is a large geometry-independent component.

### Ablations (form (a), LOGO max)

| change | max | verdict |
|---|---|---|
| full form | 23.42 | — |
| remove `exp(-k/Pi2)` cutoff | 43.47 | **the cutoff is the finding** |
| remove `1/Pi2` prefactor | 26.51 | contributes |
| remove `(H/s)^q` | 40.22 | contributes |
| remove `C0` floor | 100.28 | essential |
| add 5th parameter (`rho^p`) | 23.44 | **no gain — form is complete** |
| add `Pi2` baseline | 24.12 | no gain |
| add density switch | 24.56 | no gain |

Adding capacity does nothing, which is the signature of a form that is
structurally right rather than merely flexible.

### Cross-application

The cutoff form applied to **RadiusP** gives 48.71% LOGO max — worse than the
RadiusP baseline. This mirrors the pressure/impulse structural split already
documented for Z_urban: the mechanism is genuinely impulse-specific.

## RadiusP — nothing shippable

| model | k | in mean | in max | LOGO mean | LOGO max | gap max | LOCO-W max | LOBO-b max |
|---|---|---|---|---|---|---|---|---|
| **baseline (shipped)** | 4 | 7.93 | 41.36 | 8.39 | 43.35 | 2.87 | 43.83 | 44.19 |
| `rho^1` canyon + soft switch `/(1+Pi2)` | 4 | 8.08 | 33.74 | 8.49 | 35.73 | 1.99 | 36.16 | **48.64** |
| drop `Pi2` baseline, `rho^1` soft | 3 | 10.73 | 28.01 | 11.36 | **29.14** | 1.13 | **62.95** | 36.00 |

Two things were learned even though nothing is adoptable:

1. **The hard hinge is part of the problem.** Replacing `(1/Pi2 - 1)` with
   `(1/Pi2 - 1)/(1+Pi2)` and `sqrt(rho)` with `rho` buys ~4.7 pp of LOGO max at
   equal parameter count. But it *loses* under LOBO-b, so it is not a clean win.
2. **The LOGO-best RadiusP form is a LOGO artifact.** The 3-parameter model
   (29.1% LOGO max, smallest gap in the whole study) degrades to 62.95% under
   leave-one-charge-out. Had we scored on LOGO alone — as the brief specified —
   this would have looked like the headline result. It is the strongest argument
   in this report for keeping the second CV scheme.

### The PySR pole trap

PySR's det1/RadiusP runs converge, at every complexity ≥ 13, on

```
Z = C0 + C1*(H/s - T) / (Pi_2 - D)
```

In-sample this is excellent — 24.0% max vs the baseline's 37.5%. Out-of-fold it
reaches **51–136%**, with gaps of 27–94 pp. The pole at `Pi_2 = D` lands inside
the data range (`Pi_2 ∈ [0.437, 5.429]`); refit per fold, `D` wanders into the
span and predictions diverge. This is the same failure mode as the "spurious
density pole" the Z_urban search rejected, and the harness caught it the same way.

Note the contrast: the RadiusI pole spelling (seed 1, `-1/(Pi_2 - 0.288)`) sits
just *outside* the data range and is benign — it scores 26.5% and is essentially
a re-spelling of the cutoff. Pole placement relative to the domain is what
separates the two, not the presence of a pole.

## What limits RadiusP

Your reading — that a 41% in-sample max means functional form, not
generalization — is confirmed: in-sample max stays at 28–37% even when the model
has seen every config. Two additions:

1. **The error is concentrated in a thin corner of the design.** The six `b=10`
   families have only **2 configs each**, spanning `Pi_2` of 0.29, versus 3 configs
   and a span of 3.68 for the `s=20` families. OOF error in those 24 configs is
   40.4% max / 10.6% mean, versus 26.6% / 7.4% elsewhere. Every model tested —
   baseline and candidates alike — has its single worst error on the same config,
   `config_95_det2_b10_s5_h24_w250`.

2. **The ~7.5% noise floor is partly an artifact.** A 2-parameter fit through a
   2-point family is exactly determined, so all six `b=10` families report 0.0%
   residual and contribute nothing to the estimate. Recomputed per det, the floor
   is ~3.0–4.1% mean but **11.7–12.6% max**. The headroom on max error is
   therefore smaller than the ~30 pp the original estimate implied — roughly
   43% → ~12%, not → ~7.5%.

This does not contradict the "missing term" conclusion; it bounds the prize and
says where new data would help most (more charge weights in the `b=10` families).

## Reproducing

Scratch scripts (not part of the pipeline):
`harness.py` (LOGO + baselines), `search.py` (PySR driver), `score.py` (arbiter),
`seeds*.py` (candidate structures per wave).

PySR needed a local Julia; `pyjuliapkg`'s auto-install stalls, and its
`OpenSSL_jll = "~3.0"` pin is unsatisfiable against the Julia 1.12 registry
(relaxing it to `"3"` resolves).

## Recommendation

Adopt nothing yet — the brief asked for candidates, not a pipeline change.

For RadiusI the evidence is strong enough to justify a real A/B: form **(b)**
is the best max-error/robustness trade (3 params, 20.6% LOGO max, tightest gap,
holds under all three schemes), and form **(c)** does nearly as well on **two**
parameters, half the shipped count. Form (a) is the choice if mean error matters
more than max (6.37% mean, at the noise floor).

For RadiusP, the shipped form stands.
