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
