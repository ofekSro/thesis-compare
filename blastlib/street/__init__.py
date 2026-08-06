"""The street-channelling model suite: E(r) = P_urban/P_ff down the first street.

Layers, in dependency order — each importable on its own:

    constants     every number once, with the measurement that fixed it
    conventions   the reference-parity quirk ledger (Q1-Q7): smoothing,
                  exclusion cuts — accidents and conventions, preserved
    strip         the measurement: mean/mean slices of the first-street strip
    anchors       R_peak / E_peak / slope-fit decay per config, batch to CSV
    fitting       master curve g(x) + R_half constants refit (reproducible),
                  E_peak verification refit (pinned constants stay canonical)
    model         the closed-form E(r), gate and design envelope — pure, no I/O
    validation    the 88-config scoring, gate table, envelope stats
    figures       every figure writer (imports matplotlib — import explicitly)

Thin CLIs live in tools/street/; the parity harness that ties every layer to
the pinned reference artefacts is tools/street/street_parity.py.
"""
