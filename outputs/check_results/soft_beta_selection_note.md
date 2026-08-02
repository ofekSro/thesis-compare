# Soft-criterion beta selection — justification (Gate C4/C5)

**Chosen: β\* = 4** (soft tables token `req_soft4`), by user decision with the
gap rule relaxed.

The pre-registered rule — largest β ∈ {4, 6, 8, 12} with a config_93↔config_95
Req gap under 10 m — selects nothing: the production soft scanner is the exact
streak-DP softening of the hard K=3 scan (chosen for its bit-exact β→∞
reduction), and it tracks the hard scan more tightly than the ring-p95
prototype the 10 m orientation was calibrated on, shifting the whole β⇄gap
curve down (measured gaps: β=4 → 13.1 m, β=6 → 21.4 m vs the hard cliff of
24.2 m; only the supplementary β=2/3 fall below 10 m, at +24%/+17% median
radius inflation). β\*=4 was preferred over β=3 because it delivers what the
gap criterion is a proxy for — robustness of the downstream prediction — at
half the inflation cost: LOGO pressure error with the Task B models is mean
8.21% / max 31.62% (vs 8.19 / 40.38 on the hard tables — the worst case drops
by a quarter while the mean is unchanged within 0.02 pp), the threshold cliff
is halved (24.2 → 13.1 m), and the median radius inflation is +12.7% against
+17.3% at β=3. The acceptance gate (mean degradation ≤ 0.5 pp, material max
drop) passes at β\*=4; the impulse tables are bit-identical to the hard ones
at every β by construction.
