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
    # Damage-level anchor (audit D8a): IATG 02.20:2021[E] 3rd ed., Table 8
    # ties its quantity-distance tiers to peak side-on overpressure. 10 kPa
    # sits between the 9 kPa tier (acceptable protection for low-density
    # areas: un-strengthened buildings suffer average damage up to ~20% of
    # replacement cost; personnel in the open unlikely to be injured by
    # blast) and the 11 kPa tier (damage to main structural members,
    # repairs > 20% of replacement cost). I.e. the floor sits at the
    # standard's boundary between repairable and structural damage. The
    # IATG levels are free-field side-on values; the full CFD-vs-KB
    # cross-check is still pending (PHY-06).
    'minPressure_kPa': 10,
    'softBeta':        3.0,           # tanh projection sharpness
    'softCap_kPa':     20.0,          # |dP| mapping to weight 1 [kPa]
}

# When the urban IMPULSE counts as converged to free-field.
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
# anchoring on the pressure side (IATG 02.20 Table 8).
IMPULSE_CRITERION = {
    'thr_I_scaled': 20.0,   # Pa.s/kg^(1/3)
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
#
# The soft path needs the v2 NPZ superset (raw band fields), so a phase-1 run
# under this default reads data/processed_npz_v2. Set 'req' here (or pass
# --radius-method req) for the legacy hard criterion; both output sets live
# side by side under their own filename tokens.
RADIUS_ESTIMATOR = {
    'method': 'req_soft3',  # 'req' | 'max' | 'p95' | '<base>_soft[beta]'
    'percentile': 95,       # used only when method is a percentile
}
