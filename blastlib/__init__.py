"""blastlib — shared core of the urban blast analysis pipeline (compare_v7).

Refactored from the flat compare_v6 scripts. Sub-packages:
    config     — config-name parsing and VTK config discovery
    io         — NPZ store and binary VTK readers
    processing — grid merging, convergence radius, free-field lookup
    regression — cross-validated regression (convergence radius + Z_urban)
    plotting   — figure generation for the pipeline
"""
