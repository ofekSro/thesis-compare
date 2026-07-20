# compare_v7 — Urban Blast Convergence Analysis

Refactored version of `compare_v6`. Same numerical behaviour, cleaner structure:
a shared `blastlib` package, three entry-point scripts, and each standalone tool
isolated in its own folder under `tools/`.

The original `compare_v6` folder is untouched and remains the reference.

---

## 1. First-time setup

### Install dependencies

```
pip install -r requirements.txt
pip install -r requirements-optional.txt    # only if you want tools/view_3d
```

### Copy the data files (manual, one time)

Nothing is copied automatically. Copy these from the old folder into the new one:

**Required for the main pipeline**

| From `compare_v6\` | To `compare_v7\` |
|---|---|
| `free_field_data.csv` | `data\free_field_data.csv` |
| `MAT_files\config_*.npz` (96 files, ~6.4 GB) | `data\processed_npz\` |

**Required only for specific tools**

| From `compare_v6\` | To `compare_v7\` | Needed by |
|---|---|---|
| `OBS_MAT_files\config_*.npz` | `data\obs_npz\` | `tools/view_3d` |
| `1ds\viper1d_th_*.txt` (6 files) | `data\viper1d\` | `tools/extract_1d_peaks` |
| `all_vtks\*.vtk` | `data\vtk\` | only to regenerate the NPZs |
| `all_vtks\OBS\*.vtk` | `data\vtk\OBS\` | only for `run_preprocess_obs.py` |

**Optional** — copy these only *after* the validation run below, otherwise they
would mask a Phase-1 regression:

| From `compare_v6\` | To `compare_v7\` |
|---|---|
| `convergence_table.csv`, `max_radius_per_Z.csv`, `theta_radius_P.csv`, `theta_radius_I.csv` | `outputs\tables\` |
| `cv_summary.csv`, `best_*.csv`, `final_production_*.csv` | `outputs\tables\` |
| `ALGORITHM_DESCRIPTION.txt` and the other `*.txt` notes | `docs\` |

> **OneDrive tip:** the NPZ files are cloud placeholders. Before the first run,
> right-click `data\processed_npz\` → *Always keep on this device*, and consider
> pausing sync while the pipeline writes its ~600 figures.

---

## 2. Running the GUI launcher

```
python run_gui.py
```

A tkinter window (standard library only — no extra dependencies) with one tab
per tool. The **Analysis** tab is the default. Every tab has a Run button, a
Cancel button, a status indicator, and its own scrollable log.

Every option available on the command line is exposed. Settings that would break
comparability with the validated baseline (`test_fraction`, `target_mape`, and
the validation tolerances) sit in a collapsed **Advanced** section, pre-filled
with their validated defaults and marked with a warning.

Notes:

- Leaving a folder/file field blank uses the default from `blastlib/paths.py`.
- Required inputs are checked *before* a run starts; if something is missing you
  get a message naming the file and how to obtain it, not a crash.
- **Cancel** takes effect at the next progress line (within one config). A
  cancelled run may have written only part of its output — the log says so.
- **Z Surface 3D** and **3D Viewer** run on the main thread because their
  plotting toolkits require it, so the window is unresponsive while their own
  window is open. They cannot be cancelled mid-run.
- The **3D Viewer** tab disables itself with an explanation if `pyvista` is not
  installed.

The GUI is a thin launcher: it only calls the same `main()` functions the CLI
calls, passing `progress=` to stream output into the log. No analysis logic
lives in `gui/`.

## 3. Running the analysis from the command line

```
python run_analysis.py                          # asks the familiar questions
python run_analysis.py --phase all --n-iter 500 # fully non-interactive
python run_analysis.py --phase 1                # Phase 1 only (NPZ → tables)
python run_analysis.py --phase 2 --n-iter 500   # Phase 2 only (regression)
```

Phase 1 reads `data/processed_npz/*.npz` + `data/free_field_data.csv`, writes the
CSV tables to `outputs/tables/` and figures to `outputs/figures/`.
Phase 2 runs the cross-validated regression over those tables.

> **Important:** `--n-iter` is passed to `StratifiedShuffleSplit(n_splits=...)`,
> so changing it changes the *entire* sequence of train/test splits — results are
> only comparable between runs that used the same value.

### Regenerating the NPZ files from raw VTKs

```
python run_preprocess.py            # data/vtk/       → data/processed_npz/
python run_preprocess_obs.py        # data/vtk/OBS/   → data/obs_npz/
```

---

## 4. Validating the migration

The pipeline is deterministic (the only randomness is `random_state=42`), so the
new code must reproduce the old numbers exactly. After copying the **required**
data:

```
python run_analysis.py --phase all --n-iter 500
python tools\check_formulas\check_formulas.py
python tools\validate_migration\compare_outputs.py "..\compare_v6"
```

The last command prints a PASS/FAIL table for all 11 result CSVs and the figure
folders, and exits non-zero if anything differs. The shipped `compare_v6` outputs
were produced with 500 iterations, which is why the run above uses `--n-iter 500`.

If only Phase-2 rows differ, the likely cause is a library upgrade since the
baseline was produced (e.g. scikit-learn changing its shuffling internals). To
confirm, re-run the *original* code in your current environment: copy the old
`*.py` + `MAT_files` + `free_field_data.csv` into a scratch folder (never modify
`compare_v6` itself) and drive its prompts with

```
Get-Content answers.txt | python main_ff_compare.py     # answers.txt: "1" then "500"
```

then compare against that instead.

---

## 5. Tools

Each is independent and takes `--help`. All write under `outputs/`.

| Tool | Purpose |
|---|---|
| `tools\check_formulas\check_formulas.py` | Validate saved coefficients against the best CV test split |
| `tools\formulas_printer\formulas_printer.py` | Print the fitted formulas in readable form |
| `tools\pi_effects\pi_effects.py` | ~40 diagnostic plots of R and Z vs each Pi group |
| `tools\radius_methods\radius_methods.py` | Compare max / p95 / equivalent-area radius definitions |
| `tools\regime_graphs\regime_graphs.py` | The two thesis figures on the height-effect sign flip |
| `tools\z_surface_3d\z_surface_3d.py` | 3D surface of Z_P (hardcoded production coefficients) |
| `tools\view_3d\view_3d.py` | Interactive pyvista 3D viewer (needs the optional deps) |
| `tools\extract_1d_peaks\extract_1d_peaks.py` | Peak P/I from the 1-D viper1d runs |
| `tools\migrate_vtks\migrate_vtks.py` | One-time raw-VTK import (pass the REFERENCES folder) |
| `tools\validate_migration\compare_outputs.py` | The migration check described above |

> `tools/z_surface_3d` uses **hardcoded** production-fit coefficients. If you
> re-run the regression, compare them against
> `outputs/tables/final_production_convergence_coefficients.csv` and update the
> `COEF` dict by hand — it will not update itself.

---

## 6. Layout

```
blastlib/          shared core (importable package)
  paths.py         every directory name, defined once
  constants.py     MAX_HEIGHT, PARAMS
  geometry.py      area/volume density, exclusion radius, 3-resolution concat
  config/          config-name parsing, VTK config discovery
  io/              NPZ store, binary VTK readers
  processing/      grid merging, convergence radius, free-field lookup
  regression/      CV orchestrator, models, stats, output, plots
  plotting/        figure generation
run_analysis.py    Phase 1 + Phase 2 entry point
run_preprocess.py  VTK → NPZ
run_preprocess_obs.py
run_gui.py         GUI entry point
gui/               tkinter launcher
  runner.py        background execution, cancellation, preflight (no tkinter)
  specs.py         declarative tab/parameter definitions (no tkinter, no logic)
  widgets.py       reusable presentation pieces
  app.py           builds the window from specs, binds widgets to the runner
tools/             standalone tools, one folder each
data/              inputs (you copy these)
outputs/           everything generated (safe to delete and regenerate)
```

### Notes for future work

- Every entry point exposes `main(...)` with keyword arguments and never prompts;
  prompting lives only in `cli()` and only when stdin is an interactive terminal.
  The GUI calls `main()` directly and passes `progress=<callback>` to receive
  log lines.
- The GUI layers are split so a visual restyle never touches logic: `runner.py`
  and `specs.py` import no tkinter, so restyling means editing only
  `widgets.py` / `app.py`. Exposing another parameter means editing `specs.py`
  alone.
- All output directories are parameters defaulting to `blastlib/paths.py`, so
  nothing depends on the current working directory.
- The `.npz` files no longer store the six `logRatio*` arrays (nothing ever read
  them). Legacy files that still contain them load fine; files written by this
  version will *not* load in the old `compare_v6` code.
