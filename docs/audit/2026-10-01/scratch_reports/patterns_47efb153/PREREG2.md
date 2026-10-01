# Pre-registration, round 2 — mechanism discrimination (written before any test of this round)

Input: the 139 passed pattern keys of round 1 (out/patterns_passed_by_key.csv), record 27211b3.
Fields available: street-level (y = 0.075 m) peak overpressure and impulse, urban and free-field
reference, 3 nested grids (data/raw_npz, expanded with the record code). No time histories exist
(obs_npz = building-surface peaks without reference), so "positive-phase lengthening" can only be
tested through the proxy τ = (I/I_ff)/(P/P_ff) (a duration ratio for a fixed pulse shape).

## Cell strata (from the geometry alone, never from the result)
Layout read from the sentinel mask: det2 charge at the intersection centre, blocks at
[s/2, s/2+b] + k(b+s) on both axes; det1 charge mid-street, street |z| < s/2, blocks at
z ∈ [s/2, s/2+b] + k(b+s), x ∈ [-b/2, b/2] + k(b+s). Checked against the mask (agreement reported).
- C  channel: the street(s) containing the charge (det1: z < s/2; det2: z < s/2 or x < s/2).
- L  line of sight, not channel (2-D ray from the charge reaches the cell without crossing a block).
- S  shadow: no 2-D line of sight.
- wall flag: fluid cell within 1.0 m of a block (independent of C/L/S).
Ratios: UNFORCED P/P_ff and I/I_ff (ratio*_raw); per ring Z ∈ [Z_k−0.5, Z_k+0.5), area-weighted.
m_k(F) = area-weighted mean of ln F in stratum k; f_k = area fraction.
Edge: annulus r ∈ [0.8, 1.2]·R_conv,X; non-converged = record pinned ratio ≠ 1 (hard criterion;
the production pressure radius uses the soft criterion — approximation stated). Excess / deficit by
sign of ln(raw ratio). e_k± = share of non-converged edge area in stratum k with that sign.

## Clusters, mechanisms, discriminating predictions
G1  W / Hopkinson (A1 R_I a<1/3; A2b β_W; B1 W mains; C1 W trends of Λ_P and rings; B1 b:W, s:H:W; B2 W-reversal along b)
 M1a Π-similarity (W acts only through s̃): prediction P1a — B1 b:W and s:H:W lin coefficients computed on the
     B3 Π-model PREDICTIONS of ln Z_P have the observed sign and ≥ 50 % of the observed size; W trends of
     Λ_P and ring targets vanish given Π (β_W CI ∋ 0 in the A2 form).
 M1b numerical non-similarity on the fixed metric mesh: prediction P1b — the FREE-FIELD reference itself
     violates Hopkinson: at fixed Z the ring medians of ln P_ref and ln(I_ref/W^(1/3)) change with ln W
     (slope CI excludes 0 and |slope| > 0.02, i.e. > 2 % per e-fold of W).
G2  det2 > det1 (det main on Z_P, Z_I, Λ_P, Λ_I, Slope_P; paired ring differences)
 M2a channelling (two charge streets vs one): P2a — over matched pairs, the contribution of stratum C to
     Δ(mean ln ratio) is > 0 AND larger than the S contribution (difference CI > 0), at Z = 5 and 10.
 M2b shielding relief: P2b — the S contribution is > 0 and larger than the C contribution.
     Decomposition: Δ = Σ_k [ (f_k2 − f_k1)·m̄_k + f̄_k·(m_k2 − m_k1) ].
G3  density (ρ+ and b+ trends on Z_P, Z_I, Λ_I, R_I, rings)
 M3a channelling: P3a — Spearman(ρ, m_C(P)) > 0 and > Spearman(ρ, m_S(P)) (difference CI > 0), Z = 5, 10.
 M3b reflection superposition at walls: P3b — Spearman(ρ, m_LOS,wall − m_LOS,open) > 0 at Z = 2 and larger at
     Z = 2 than at Z = 10 (decay with range).
G4  street width (s−, s̃− trends; Λ_P, Λ_I s̃ coefficients; det×s)
 M4a channelling: P4a — Spearman(s̃, m_C(P)) < 0 and < Spearman(s̃, m_S(P)).
 M4b reflection superposition: P4b — Spearman(s̃, wall advantage) < 0 at Z = 2 and weaker at Z = 10.
G5  height (H/s+, H+ on impulse targets; Λ_P H/s− in det1)
 M5a positive-phase lengthening: P5a — Spearman(H/s, mean ln τ) > 0 at Z = 5 and 10 (impulse gains exceed peak gains).
 M5b channelling of the peak: P5b — Spearman(H/s, m(P)) > 0 at Z = 5 and 10 with |ρ_s| ≥ that of mean ln τ.
G6  H effect reversing along s (Z_P, B2) and ρ×s̃, ρ×H/s products
 M6a confinement in narrow streets: P6a — at s = 5, Spearman(H, m_C(P) at Z = 10) > 0.
 M6b shielding in wide streets: P6b — at s = 20, Spearman(H, m_S(P) at Z = 10) < 0.
 M6c channel-mediated ρ×s̃: P6c — regression of m_C(P) at Z = 10 on ln ρ, ln s̃, product (+det): product coef > 0.
 M6d shadow-mediated ρ×s̃: P6d — same regression on m_S(P): product coef > 0.
G7  Λ_P break in s̃ at 1.54
 M7a channel regime change: P7a — channel advantage m_C(P) − m_L(P) at Z = 5, segmented at ψ = 1.54 (fixed):
     slope below < 0 and slope change > 0.
 M7b wall-reflection regime change: P7b — same for wall advantage.
G8  Z_I collapse onto ζ = 2.24 ln ρ + ln s̃ + 0.94 ln H/s
 M8a positive-phase lengthening: P8a — Spearman(ζ, mean ln τ at Z = 10) has the sign of Spearman(ζ, ln Z_I).
 M8b channelling: P8b — Spearman(ζ, m_C(I) at Z = 10) has that sign.
G9  Slope_P (s̃−, s−, det−)
 M9a near-field reflection decaying with range: P9a — Spearman(wall advantage at Z = 2, Slope_P) < 0.
 M9b channel growth with range: P9b — Spearman(m_C(P) at Z10 − at Z2, Slope_P) > 0.

## Inference and verdicts
All CIs: family-cluster bootstrap (18 families, B = 2000), percentile; p from bootstrap SE (normal).
BH (q = 0.05) over all tests of this round. Tests run pooled with det as stratum (Spearman pooled over
both dets; bootstrap resamples families, both dets together) unless stated.
SUPPORTED  = every inequality of the prediction holds with BH-adjusted CI excluding the wrong side.
REJECTED   = the predicted quantity has the opposite sign with CI excluding 0.
UNDECIDED  = otherwise. HYPOTHESIS = mechanism not discriminated (stated only as candidate).
SUPPORTED means "consistent with the prediction and not with the named alternative's", nothing more.

## Addendum (after a 2-config smoke run of the feature script, before any test)
- Smoke-run facts: (i) analytic layout = sentinel mask on grids 1–2 (100 %); grid 3 differs only at x > 480 m
  (the city ends before the domain edge) — outside every ring and edge annulus used. (ii) In the R_conv edge
  annulus, deficit cells are never non-converged: the criterion pins P < 10 kPa and scaled I < floor, so a
  deficit can never set R_conv. The edge composition is therefore reported descriptively only.
  (iii) "S" = no 2-D line of sight; it contains cross streets, not only lee zones. A positive S contribution
  is read as "NLOS cells", and the shielding claim is worded accordingly.
  (iv) Stratum L is often empty in narrow streets.
- Field mapping: pressure-side patterns (Z_P, Λ_P, Slope_P, rP_*) are tested on P fields; impulse-side
  (Z_I, R_I, Λ_I, rI_*) on I fields.
- G3/G4/G5 predictions are also run with the raw inputs b, s, H (same inequalities) for the raw-input patterns.
- G6 extension: P6c'/P6d' — same regressions with the ρ×(H/s) product, for the ρ×H/s patterns.
- G7 fallback: if fewer than 30 configs have both C and L at Z = 5, the channel advantage is m_C − m_(L∪S),
  flagged.
- G2 decomposition: a stratum empty in one member of a pair contributes composition only; empty in both → 0.
- Null-type prediction P1a-ii (β_W CI ∋ 0) is reported with its CI half-width; "SUPPORTED (null)" is weaker
  than a directional support and is labelled so.
