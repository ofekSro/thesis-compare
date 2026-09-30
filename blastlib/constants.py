"""Shared constants for the blast analysis pipeline.

These constants control grid processing thresholds and reference geometry
parameters used across convergence radius and max-radius analyses.
"""

# Reference height for volume density calculation [m]
MAX_HEIGHT = 24

# Grid processing parameters
#
# softBeta / softCap_kPa drive the SOFT pressure convergence criterion
# (processing/soft_criterion.py), used only when a '<method>_soft' radius
# estimator token is requested. The hard 10 kPa band swallows real
# amplification lobes wherever the free field itself is ~10 kPa (Z >~ 10),
# so configs whose lobe peak grazes the threshold get discontinuous radius
# jumps. The soft criterion replaces the band's hard indicator with a
# Wang-Lazarov-Sigmund tanh projection: 0 at |dP|=0, 0.5 exactly at
# |dP| = minPressure_kPa, 1 at |dP| >= softCap_kPa; beta -> inf reproduces
# the hard band exactly. softBeta = None (or 0) disables the soft path.
PARAMS = {
    'thresholdP_kPa':  1.01 / 1000,  # mask threshold [kPa]
    # Convergence band / relevance floor [kPa]. The floor clause tests the
    # URBAN peak (grids.py: lowP = peakP_raw < minPressure) — an owner
    # decision (2026-09-27, audit D7/CHO-03): where the city itself delivers
    # under 10 kPa the location is of no engineering interest even if the
    # free field there is stronger. Hence shielding below the floor counts
    # as converged, and the free-field substitution beyond R_conv is
    # conservative for pressure in shielded zones.
    # Damage-level anchor (audit D8a; tier texts corrected 2026-09-28 per
    # physics-6, owner confirmed 10 kPa is the intended boundary):
    # IATG 02.20:2021[E] 3rd ed., Table 8 ties its quantity-distance tiers
    # to peak side-on overpressure. 10 kPa sits between the 9 kPa tier
    # (PTRD: un-strengthened buildings suffer average damage of the order
    # of 10% of replacement cost) and the 11 kPa tier (Blue Line IBD: the
    # acceptable protection level for low-density areas, damage up to ~20%
    # of replacement cost; personnel in the open unlikely to be injured by
    # blast). I.e. the floor sits at the standard's ~10%-repair to
    # ~20%-repair boundary; the repairable-vs-structural-member boundary
    # is the 16 kPa tier, deliberately NOT the anchor here. The IATG
    # levels are free-field side-on values while this floor tests the
    # urban CFD field — carry the PHY-06 caveat (CFD 10 kPa contour sits
    # ~8-10% closer than KB's) on any standard-anchored statement.
    'minPressure_kPa': 10,
    'softBeta':        3.0,           # tanh projection sharpness
    'softCap_kPa':     20.0,          # |dP| mapping to weight 1 [kPa]
}

# When the urban IMPULSE counts as converged to free-field.
#
# PRODUCTION CRITERION (owner decision, 2026-09-28 evening, adopting the
# physics-audit verdict — docs/audit/2026-09-28/physics.md, candidate B):
#
#   |I_urban - I_ff| / I_ff < rel_band     (free field is ACCURATE here)
#   or  peakP_urban_raw < minPressure_kPa  (location is damage-IRRELEVANT)
#
# Meaning: beyond R_conv,I, at every point, either the free-field impulse
# is correct to within rel_band, or the urban peak pressure is below the
# 10 kPa damage floor — below which NO impulse magnitude can produce
# damage in the anchored structural class, because every P-I damage curve
# is bounded from below by a pressure asymptote (UFC 3-340-02 Fig. 1-2 is
# the human-target instance; IATG 02.20 Table 8 states every structural
# tier as a pressure). The floor clause is a PRESSURE statement on
# purpose: an impulse-only irrelevance level does not exist (physics-1;
# D8 said the same for damage criteria), which is also why the impulse-only
# "mirror" criterion (|dI|/W^(1/3) < x OR I/W^(1/3) < y) was rejected —
# measured, it collapses onto the rejected scaled band (physics-12) — and
# why absolute Pa.s clauses are inadmissible (they vary as W^(1/3) across
# charge weights and break the Z collapse; physics-16).
#
# [Corrected 2026-09-29, D24 review] The claim above that "an impulse-only
# irrelevance level does not exist" is wrong: every P-I curve also has an
# impulse asymptote, but it is absolute and target-specific, and none is
# registered for the structural class this floor anchors. The rationale that
# holds is IATG 02.20 §8: the QD tiers are stated as side-on pressures, yet
# "the primary threat to structures is blast impulse energy, which is a
# function of overpressure and event duration"; the tiers were developed for
# very large NEQ (thousands of kg) and scaled down. Each tier sits at a fixed
# scaled distance, so the impulse accompanying 10 kPa grows as W^(1/3): for
# W = 50-1500 kg it is ~0.17-0.53 of a 10 t event's (illustrative mass; IATG
# says only "thousands of kg"). Below the floor the structural threat is
# therefore lower than the tier describes: the floor is conservative over
# this study's charge range.
#
# R_conv,I under this rule is a RELEVANCE-BOUNDED convergence radius: it
# is floor-dominated (the accuracy clause trims the floor-only radius by
# ~1.5% median), so it must never be presented as the radius where the
# impulse field merges with the free field — the merging radius is larger
# and, in channelling configs, beyond the validated Z <= 20 range. Both
# radii now share ONE relevance quantum (minPressure_kPa, D7 + D8a), which
# makes them commensurable for the safety-distance comparison (aim 4).
#
#   * rel_band = 0.10 — twice the impulse mesh-convergence tolerance (5%):
#     the minimal band clearly above numerical noise, so it measures the
#     physics, not the mesh (physics-9; the decision-suite stability sweep
#     in criterion_decision_suite.csv confirms, as a consequence).
#   * The floor value lives in PARAMS['minPressure_kPa'] — deliberately
#     NOT duplicated here: one constant, one relevance quantum, both
#     criteria. Floor sensitivity: 9/11 kPa (the neighbouring IATG tiers)
#     move the median Z_conv,I by only about +-5% (elasticity ~ -0.5).
#   * Measured record (pfloor_variant_suite, 2026-09-28): median Z_conv,I
#     13.82, p90 15.55, max 17.48; 0/96 beyond the validated Z = 20;
#     Z_conv,I > Z_conv,P in 96/96 (median ratio 1.40 vs Z_conv,P 9.88)
#     (a property of the two criteria's forms — floor-only >= floor-or-band —
#     not evidence that geometry affects impulse further; see
#     docs/DECISIONS.md D24).
#
# ---- Historical: the impulse-floor rule (2026-09-28 morning, production
#      for one run; reproduce via impulse_converged_ifloor) ----
#
#   |I_urban - I_ff| / I_ff < 0.10  or  I_urban / W^(1/3) < 20
#
# Same accuracy clause; relevance floor on the urban SCALED IMPULSE. It
# fixed the scaled band's unbounded-error defect, but its floor treated an
# impulse level as a relevance measure, which contradicts the P-I pressure
# asymptote (physics-1: at its far radii the field is at 2-4 kPa, harmless
# at any impulse), inherited the value 20 from the rejected band's
# calibration, and rode channelling amplification to Z_conv,I up to 32.4 —
# 33/96 radii beyond the validated range (physics-2). Its tables are the
# 3400e26 record.
#
# ---- Historical: the 2026-07..2026-09-27 scaled band (kept for
#      reproducing old tables via impulse_converged_scaled) ----
#
#   |I_urban - I_ff| / W^(1/3) < thr_I_scaled     [Pa.s/kg^(1/3)]
#
# The scaling factor is required, not cosmetic. Free-field impulse scales as
# W^(1/3), so a fixed Pa.s band has a relative strictness that varies as
# W^(1/3) too — measured at 3.10x across W=50..1500, exactly (1500/50)^(1/3).
# That makes a fixed Pa.s band pick a DIFFERENT scaled-distance contour for
# every charge weight (Z = 4.98/8.65/10.86/13.77/15.78 at 5% equivalent),
# which is inadmissible under Hopkinson-Cranz. Dividing by W^(1/3) restores a
# single contour (cross-weight spread 1.01-1.04).
#
# The previous rule also OR-ed in a low-PRESSURE floor, so 94.5% of impulse
# convergence decisions were made by a pressure threshold and RadiusI landed
# on the 10 kPa contour. That floor is deliberately absent here.
#
# thr_I_scaled = 20 is a calibration, not a measured boundary. It was
# originally chosen on the pre-2026-09 store as the loosest-but-lowest value
# giving 100% convergence — but that store let building-skin sentinel cells
# drive RadiusI (docs/audit/2026-09-27, ALG-01/PHY-01), so the old "100%
# convergence" and "~1.8x looser than pressure" readings described the
# artefact. On the raw-mask store the value was re-examined and KEPT:
#   * a threshold sweep over 5..40 Pa.s/kg^(1/3)
#     (outputs/check_results/thr_I_sensitivity_scan.csv) shows 20 at the
#     stability/predictability optimum — stricter bands push the radius into
#     the far, noisy field (median Z_conv,I 24.9 at thr=5), looser ones into
#     the discrete near field (3.6 at thr=40), and the LOGO error of the
#     production RadiusI form is minimal at 20;
#   * sensitivity d ln R / d ln thr ~ -0.7 across the sweep;
#   * the K=3 streak rule sits on a stable plateau for BOTH loads
#     (outputs/check_results/k_sensitivity_scan.csv; median |d ln R| <= 1%
#     for K 2->3->4) — which is also why the impulse scan stays HARD while
#     the pressure scan is soft: impulse has no streak-brittleness to soften.
# It is a LOAD-FIDELITY band, not a damage threshold, and deliberately so
# (owner decision 2026-09-27, D8): impulse damage criteria are absolute,
# target-specific P-I curves that cannot collapse to one Hopkinson-
# admissible contour, and human primary injury is bounded by the P-I
# pressure asymptote anyway — UFC 3-340-02 Fig. 1-2 (p. 94) shows no lung
# damage below ~69 kPa at ANY impulse, a contour at Z ~ 3.7-3.8, deep
# inside R_conv,I. An absolute human-impulse floor from the figure's
# vertical asymptote (i_min ~ 3.5 psi.ms/lb^(1/3) x Wh^(1/3) ~ 129 Pa.s
# at 70 kg) was evaluated and REJECTED: it would cut 17 of the 24 W=50
# configurations, break the Z collapse the whole regression framework
# rests on, and hangs on an arbitrary body weight. Human-relevance radii
# belong to a separate product (R_human, from the full P-I curve on the
# urban field — future work, aim 4). At the measured radii the band
# equals a median 55% of the local free-field impulse (p10 36%, p90 92%):
# an engineering-indistinguishability band, with the framework's damage
# anchoring on the pressure side (IATG 02.20 Table 8). [The damage-anchor
# analysis above remains valid under the new criterion: the floor is a
# relevance level, not a damage level, and R_human stays a separate
# product.]
#
# ---- Production since 2026-09-30 (DECISIONS.md D35 (c), owner decision) ----
#
#   |I_urban / I_ff - 1| <= rel_band   or   I_urban / W^(1/3) < floor_scaled
#
# Supersedes the D24 rule above (reproduce via
# ff_reference.impulse_converged_pfloor). Same accuracy clause; the relevance
# floor moves from the urban PRESSURE to the urban SCALED IMPULSE. The value
# 23.6 Pa.s/kg^(1/3) is the scaled free-field impulse of the reference runs
# at the Z where their overpressure is 10 kPa (Z ~ 11.6, data/
# free_field_data.csv): the same contour and the same IATG 02.20 level as the
# pressure floor, stated in impulse. One value for all W (Hopkinson); the
# per-W levels are 21.9-24.4 (D35 alternative (b)). The rule was set after
# measurement, by the owner. Evidence (scratch evaluation, 2026-09-30):
# LOGO I 9.03% (D24 9.46%), safe-box I max 10.3% (23.6%), CV R^2 0.934
# (0.913); the floor sets R_I in 94/96; 8 configs have Z_conv,I > 20.
IMPULSE_CRITERION = {
    'rel_band': 0.10,       # relative accuracy band (-), |I/I_ff - 1| <= rel_band
    'floor_scaled': 23.6,   # Pa.s/kg^(1/3); scaled free-field impulse of the
                            # reference runs at the Z where their overpressure
                            # is 10 kPa (Z ~ 11.6); same contour and IATG level
                            # as the pressure floor. D35.
}

# How a 91-element per-angle radius array collapses to one scalar radius.
# ONE setting drives BOTH the convergence radius and the MaxR / Z_urban radius
# — they measure the same object and must be measured the same way. There is
# deliberately no separate setting for each. See processing/radius_estimator.py.
#
# Production is 'req_soft3': the equivalent-area collapse measured under the
# SOFT pressure criterion at beta = 3 (adopted 2026-08; see
# outputs/check_results/soft_beta_selection_note.md). It was the only tested
# beta to satisfy both pre-registered rules — the config_93/95 threshold gap
# below 10 m and the <=0.5 pp acceptance bound on mean LOGO error — and it
# cuts the worst-case pressure error from 43.4% to 30.1%.
# Correction (2026-09-29, DECISIONS.md D4): the rules above were not
# pre-registered for beta = 3. The registered set was {4, 6, 8, 12}; none
# passed the gap rule, beta = 4 was adopted with the rule relaxed, and
# beta = 3 was added afterwards. The two rules were re-applied on 2026-09-29
# as an ex-post criterion on the record of 53b280c: gap 8.51 m (hard 24.54 m),
# mean LOGO P 9.92% (hard 12.24%). The 43.4% -> 30.1% figures are August's.
#
# The soft path needs the v2 NPZ superset (raw band fields), so a phase-1 run
# under this default reads data/processed_npz_v2. Set 'req' here (or pass
# --radius-method req) for the legacy hard criterion; both output sets live
# side by side under their own filename tokens.
RADIUS_ESTIMATOR = {
    'method': 'req_soft3',  # 'req' | 'max' | 'p95' | '<base>_soft[beta]'
    'percentile': 95,       # used only when method is a percentile
}
