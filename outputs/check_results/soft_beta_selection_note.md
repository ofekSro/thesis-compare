# Soft-criterion beta selection — justification (Gates C4/C5)

**Adopted: β\* = 3** (production token `req_soft3`, set in
`constants.RADIUS_ESTIMATOR`).

## Correction (2026-09-29, DECISIONS.md D4)

The rules below were not pre-registered for β = 3. The set fixed in advance
was {4, 6, 8, 12}; none of it passed the gap rule, β = 4 was adopted with the
rule relaxed (`cbb2312`), and β = 3 was added afterwards (`430d004`). The text
below is kept as the August record. On 2026-09-29 the same two rules were
re-applied as an ex-post criterion, fixed before measuring, on the record of
`53b280c` (96 configs; β = 3 and hard only):

| | hard | β = 3 | rule |
|---|---|---|---|
| gap 93↔95 [m] | 24.54 | 8.51 | < 10 m ✓ |
| LOGO P mean / median / p90 / max [%] | 12.24 / 8.91 / 26.44 / 47.51 | 9.92 / 8.07 / 21.94 / 38.54 | ≤ hard + 0.5 pp ✓ |

Median RadiusP inflation against hard is +10.05% (p90 +19.34%, max +66.84%,
min −13.25%). β = 3 stays.

## August 2026 justification (historical)

β = 3 is the only tested sharpness that satisfies **both** rules fixed before
the numbers were seen. The C4 selection rule — the largest β whose
config_93↔config_95 Req gap falls under 10 m — is met at 8.6 m (β = 4 leaves
13.1 m, β = 6 leaves 21.4 m, against a hard-criterion cliff of 24.2 m), and the
C5 acceptance bound — mean LOGO error no more than 0.5 pp above the same models
on the hard tables — is met at +0.24 pp (8.43% vs 8.19%), where β = 2 fails it
at +0.61 pp. What that buys is the point of the whole exercise: the worst-case
pressure error falls from 43.4% (hard tables, original models) to 30.1%, the
historical threshold-cliff configuration config_95 drops from 40.4% to 5.7%, and
the median improves as well (6.85% → 5.67%), so the gain is not bought by
sacrificing the bulk of the dataset to rescue one corner. The measurement cost
is a median radius inflation of +17.3% — the softened criterion declares
convergence slightly later, which is the conservative direction for a
protective-design radius. β = 4 was the interim production choice while the gap
rule stood relaxed; its accuracy differences from β = 3 are within noise (mean
8.21 vs 8.43, max 31.6 vs 30.1), so the deciding argument is that β = 3 needs no
relaxation of a pre-registered rule and carries the lower worst case. The
impulse criterion is untouched at every β, and its tables are bit-identical
across all of them.

## Measured beta sensitivity (C4 scan, 96 configs)

| β | gap 93↔95 [m] | median inflation | LOGO P mean | LOGO P max | pre-registered rules |
|---|---|---|---|---|---|
| 2 | 6.3 | +24.4% | 8.80 | 29.97 | gap ✓, acceptance ✗ (+0.61 pp) |
| **3** | **8.6** | **+17.3%** | **8.43** | **30.07** | **both ✓ — adopted** |
| 4 | 13.1 | +12.7% | 8.21 | 31.62 | gap ✗, acceptance ✓ |
| 6 | 21.4 | +6.5% | 8.31 | 32.39 | gap ✗, acceptance ✓ |
| 8 | 25.3 | +4.0% | 8.34 | 33.47 | gap ✗, acceptance ✓ |
| 12 | 26.7 | +2.0% | 8.33 | 39.80 | gap ✗, acceptance ✓ |

Hard-criterion reference: gap 24.2 m, LOGO P mean 8.19 / max 40.38 (same models).

## Final matrix

See `soft_criterion_summary.csv` — {hard, soft β=3, soft β=4} × {legacy, new
models} × {P, I} × {mean, median, p90, max}, with the production row flagged.
The 500-split CV (StratifiedShuffleSplit, n=500, 20% test, seed 42) under the
production combination gives median test MAPE: conv_P 8.79, conv_I 7.15,
z_P 8.49, z_I 9.49.

One honest trade to state alongside the gains: the soft criterion improves the
pressure median and max but worsens the p90 (15.86 → 18.65), because the
inflation cost is spread over the mid-range configurations while the benefit is
concentrated in the threshold-cliff families.
