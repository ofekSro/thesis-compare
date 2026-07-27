"""Shared constants for the blast analysis pipeline.

These constants control grid processing thresholds and reference geometry
parameters used across convergence radius and max-radius analyses.
"""

# Reference height for volume density calculation [m]
MAX_HEIGHT = 24

# Grid processing parameters
PARAMS = {
    'thresholdP_kPa':  1.01 / 1000,  # mask threshold [kPa]
    'minPressure_kPa': 10,            # convergence threshold [kPa]
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
# thr_I_scaled = 20 is a calibration, not a measured boundary: it is the
# loosest-but-lowest value giving 100% convergence with no reliance on
# extrapolated free-field data. At the resulting radius it is a ~83% relative
# band (urban within a factor ~1.8 of free-field), against ~47% for the
# pressure rule at ITS radius — the impulse test remains ~1.8x looser.
IMPULSE_CRITERION = {
    'thr_I_scaled': 20.0,   # Pa.s/kg^(1/3)
}

# How a 91-element per-angle radius array collapses to one scalar radius.
# ONE setting drives BOTH the convergence radius and the MaxR / Z_urban radius
# — they measure the same object and must be measured the same way. There is
# deliberately no separate setting for each. See processing/radius_estimator.py.
RADIUS_ESTIMATOR = {
    'method': 'req',        # 'req' | 'max' | 'p95'
    'percentile': 95,       # used only when method is a percentile
}
