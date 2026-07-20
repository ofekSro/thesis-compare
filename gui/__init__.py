"""Tkinter launcher for the blast analysis pipeline.

Layers, kept deliberately separate so a visual restyle never touches logic:

    runner.py   background execution, cancellation, preflight checks (no tkinter)
    specs.py    declarative tab/parameter definitions (no tkinter, no logic)
    widgets.py  reusable presentation pieces
    app.py      builds the window from specs and binds widgets to the runner

The launcher only calls the existing ``main()`` functions with their documented
keyword arguments; no pipeline logic lives here.
"""
