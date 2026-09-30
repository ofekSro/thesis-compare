# CLAUDE.md - compare_v7

Guidance for Claude Code and its agents in this repo. Hard cap: 500 lines.
Detail lives in README.md, docs/ and WORKLOG.md, which are read on demand.

---

## 0. What this project is - read before judging any request

compare_v7 is the analysis code (stages 3 and 4 below) of an MSc thesis in
civil engineering, Structural Engineering and Construction Management
Division, Technion: *Prediction of Blast Loading in Urban Environments: A
CFD-Based Parametric Study for Developing Engineering Guidelines*. Author:
the owner. Advisor: Dr. Hezi Grisaro. The approved research proposal is the
authority on scope; this section summarises it.

**Motivation.** Most people now live in cities, and accidental urban
explosions (Beirut 2020, Tianjin 2015, gas-transport accidents, unexploded
wartime ordnance) produce loads that free-field relations cannot describe:
reflections, diffraction, channelling along streets, shielding behind
buildings, and non-linear superposition of wave fronts. Existing tools either
cost a full CFD run per case or predict pressure at a single point. The
literature rarely maps the *general* phenomena of amplification, shielding
and channelling against the geometry that causes them.

**Aim.** To develop a predictive capability for blast loads in an urban
environment, so that expected damage to structures and people can be
assessed. Secondary aims, in the proposal's order:
1. understand how the problem parameters (charge characteristics, urban
   geometry) govern the pressure regime in the space;
2. compare peak pressure and impulse of a wave travelling along a street with
   the free-field wave;
3. compare the reflected peak pressure and impulse on a building inside the
   grid with the same building standing alone in the free field;
4. compare safety distances derived from a free-field explosion with those in
   an urban environment, for several damage levels;
5. derive simple engineering rules for rapid order-of-magnitude estimates,
   with stated domains of validity and uncertainty envelopes.

**Method.** Four stages. (1) Mesh-convergence study. (2) Definition of the
parametric space (urban geometries, charge weights) and automated case
generation and execution in MATLAB. (3) A database of 2-D maps of peak
pressure and maximum impulse on the street floor and on building surfaces,
plus gauge time histories. (4) Systematic analysis of that database to
identify recurring behaviour and distil engineering rules with validity
limits and safety margins. The CFD solver is Viper-Blast (GPU-based Euler
solver, ideal-gas EOS: the study concerns wave propagation in air, not the
detonation products). The parametric grid is 96 configurations of an
idealised periodic city (building footprint, street width, height, charge
weight, street or intersection detonation).

**Contribution.** A systematic map from geometric features to amplification,
shielding and channelling, rather than point predictions; and, for planners
and safety authorities, simple rules with conservative uncertainty envelopes
for loads and safety distances without running a simulation.

**What this repo does.** Reads the Viper-Blast fields, measures the distance
beyond which the urban field is indistinguishable from the free field
(convergence radius), measures the urban scaled distance that carries the same
load as a free-field distance (Z_urban), fits regression models over the 96
configurations, and produces the tables and figures of thesis chapters 9
and 10. The framework is the standard one of the field: Hopkinson-Cranz
scaling, Kingery-Bulmash free-air curves, UFC 3-340-02.

**Scope line.** The charge is a given design-basis input. The city geometry
and the load on it are the variables. Nothing here concerns making, handling
or improving an explosive, and any request that does is declined whatever
the framing. The vocabulary of the field (charge, TNT, detonation, impulse)
is ordinary inside that line.

---

## 1. Owner directives - binding

1. **No change without the owner's explicit approval, and only after the
   owner has understood what the change means.** This covers every file:
   code, tests, docs, README, tables, this file. Before touching anything,
   state in Hebrew: what will change, why, which numerical outputs or
   results of record could move, and which thesis sections depend on them.
   Then stop and wait. "Review only", "propose", "dry run" and every
   `/verify` run produce findings, never edits. This applies to agents as
   much as to the main session: an agent that would edit code returns a
   proposal instead.
2. **The worklog is written only when the owner asks** (`/worklog`). Never
   automatically, never by a hook, never by an agent. See §6.
3. **Results of record never change silently.** See §3. A change that moves
   one of them is reported with old and new values before it is made, and
   recorded in WORKLOG.md after.
4. **Never "fix" a formula, threshold, coefficient or criterion on your own
   judgement**, even when it looks wrong. Report it as a finding with the
   evidence. The owner decides. This includes `docs/ALGORITHM.md`: it was
   written with AI assistance and may itself be wrong. When code and document
   disagree, that is a finding, not a bug to patch on either side.
5. **Git.** Remote `github.com/ofekSro/thesis-compare`, branch `compare-v7`.
   Commit only when the owner asks, with the message style of the history
   (`area: what changed`). Push only after the owner approves that push.
   Never amend, never rewrite history.
6. **Scope.** Touch only what the request names. Do not tidy, rename or
   restyle files the owner did not mention. List them as candidates instead.
7. **Stay inside this folder.** Agents and the main session read and write
   only under the repo root. The thesis, the proposal, `compare_v6` and any
   other folder are off limits unless the owner names them in the request.
   Ask before leaving.

---

## 2. Orientation

Three stages, one package:

- `run_preprocess.py`: raw VTK fields -> `data/raw_npz/` (schema v3, no
  criterion baked in). Older `processed_npz` (v1/v2) stores are read
  transparently and give identical numbers (`tests/test_raw_store.py`).
- `run_analysis.py --phase 1`: NPZ -> convergence radii, MaxR per Z, tables
  under `outputs/tables/`, figures under `outputs/figures/<method>/`.
- `run_analysis.py --phase 2`: cross-validated regression over those tables
  -> production coefficients.
- `blastlib/`: the shared core. `constants.py` holds the criteria and the
  radius estimator and explains each choice in a long comment. Read those
  comments before judging a threshold. `street/` is the street-channelling
  model with its own doc (`docs/STREET_CHANNELLING_MODEL.md`).
- `tools/`: standalone CLIs, one folder each, all writing under `outputs/`.
- `gui/`: tkinter launcher only. No analysis logic lives there.
- `tests/`: pytest. Data-dependent tests skip cleanly when the NPZ stores are
  absent; `slow` marks full 96-config sweeps.

Full layout and every CLI flag: README.md §2-§6.

---

## 3. Results of record

These are the numbers the thesis cites. They are versioned in git on purpose
(`.gitignore` keeps `outputs/tables/*.csv` and `outputs/check_results/*`) and
they must be reproducible from the code at the same commit.

- `outputs/tables/final_production_*.csv` - the production fits.
- `outputs/tables/convergence_table_*.csv`, `max_radius_per_Z_*.csv`,
  `cv_summary*.csv`, `best_*.csv` and the coefficient CSVs.
- `outputs/check_results/*.csv` and `*.md` - gate reports, parity reports,
  selection notes (`soft_beta_selection_note.md`, `street_parity_report.md`).
- The pinned artefacts that `tests/test_npz_anchors.py`,
  `tests/test_street_anchors.py` and the street parity suite compare against.

Figures (`outputs/figures/`, ~3500 PNG) are regenerable and not of record.

Suffix rule: every table and figure carries the radius-estimator token that
produced it (`_req`, `_p95`, `_req_soft3`). Production is `req_soft3`
(`blastlib/constants.py::RADIUS_ESTIMATOR`). Never compare tables with
different suffixes as if they were the same run.


---

## 4. Verification - what "correct" means here

There is no external anchor for the urban results. Correctness is argued from
four directions, and a review reports on each separately:

1. **Algorithm vs documentation.** `docs/ALGORITHM.md` describes the method.
   Chapter 9 of the thesis was written from this repo. Code, document and
   chapter must agree, and none of the three is automatically right.
2. **Physics and units.** Dimensionless groups (`rho = b^2/(b+s)^2`,
   `Pi_2 = s/W^(1/3)`, `H/s`), Hopkinson-Cranz scaling of every threshold
   (see the `IMPULSE_CRITERION` comment for why a fixed Pa.s band is
   inadmissible), free-field reference from `data/free_field_data.csv`.
   Standards are registered in `docs/references/INDEX.md` when present.
3. **Statistics.** `StratifiedShuffleSplit` with `random_state=42`;
   `--n-iter` changes the whole split sequence, so results are comparable
   only at equal `n_iter` (production baseline: 500). Review for leakage
   between train and test, selection on the test set, degrees of freedom
   against 96 configurations, reporting of uncertainty, extrapolation outside
   the domain of validity (`ALGORITHM.md` §"Domain of validity").
4. **Reproducibility.** The pipeline is deterministic. Pinned artefacts
   regenerate byte for byte from the code at the same commit. `compare_v6` is
   history, not a reference: the criteria and models have changed since, and
   `tools/validate_migration` documents the migration only.

Arbitrary choices that a reviewer must treat as choices, not facts: the
10 kPa pressure band, `thr_I_scaled = 20`, `beta = 3`, the `req` equivalent-
area collapse, `MAX_HEIGHT = 24`, `random_state = 42`. Each has a rationale
in `constants.py` or in `outputs/check_results/`. A review checks that the
rationale holds and reports sensitivity where it is known.

---

## 5. Running things

```
python -m pytest -q -m "not slow"          # minutes, no data needed for most
python -m pytest -q                         # full, needs data/raw_npz or processed_npz
python run_analysis.py --phase 2 --n-iter 20 --no-figures    # short smoke run
python run_analysis.py --phase all --n-iter 500              # production, ~30 min
python tools\check_formulas\check_formulas.py
```

- An agent may run the fast tests and the short smoke run freely. It runs the
  production pipeline only when the owner asks, in the background, with
  `python -u` and no timeout.
- Before trusting any number, the fast tests must be green and the anchor
  tests must not have been skipped for lack of data.
- Data: `data/*` is gitignored and lives on OneDrive as cloud placeholders.
  Mark `data\raw_npz\` "Always keep on this device" before a run.

**Cloud sessions (claude.ai/code).** Linux VM, fresh clone of GitHub, no
OneDrive and no `data/` unless the setup script downloads it.
- Commit and push only to the session's own `claude/*` branch, never to
  `compare-v7`. The owner merges, after reading the diff. §1 applies unchanged.
- If `data/raw_npz/` is absent, say so at the start: anchor tests will skip
  and no number produced in the session may be trusted (see above).
- Agents and skills live in `.claude/`. User-level memory does not reach the
  cloud; anything a cloud session must know belongs in this file.

---

## 6. Documentation and the worklog

- **README.md** is the operating manual. Keep it true when a flag or path
  changes.
- **docs/** holds paired English and Hebrew documents (`ALGORITHM.md` /
  `ALGORITHM_HE.md`, and Hebrew-only analysis notes). Both languages are
  kept. When one is edited, say which of the pair is now ahead. When they
  disagree, neither is primary: ask the owner, who decides.
- **WORKLOG.md** (Hebrew) is the owner's research diary and the source for
  writing the thesis. One entry per session in which the owner asks for it.
  Format:

  ```
  ## 2026-09-27 - <כותרת קצרה>
  **מה ביקשתי:** ...
  **מה עשינו:** קבצים, פקודות, commits (hash).
  **מה מצאנו:** ממצאים ומספרים, לפני ואחרי כשיש שינוי.
  **החלטות:** מה הוחלט ולמה. מה נדחה ולמה.
  **שאלות פתוחות:** ...
  **לתזה:** לאיזה פרק/סעיף זה שייך ומה המשפט שכדאי לכתוב.
  ```

  Entries are appended, never rewritten. Numbers are copied from the actual
  output, never from memory.
- **docs/audit/<date>/** holds `/verify` reports. **docs/TRACEABILITY.md**
  maps thesis claims to code, tests and tables.

---

## 7. Code conventions

- Short English comments that say *why*, not what, and cite the source:
  `# ALGORITHM.md §Step 1`, `# UFC 3-340-02 Fig. 2-15`,
  `# see soft_beta_selection_note.md`. The long rationale comments in
  `constants.py` are the model. Never delete a rationale comment.
- Every public function: one-line docstring, parameters with units, return
  with units, validity limits when they exist.
- Names follow the thesis notation: `Z`, `W`, `R_conv`, `Z_urban`, `rho`,
  `Pi_2`, `H`, `s`, `b`. Keep them.
- Entry points expose `main(**kwargs)` and never prompt outside `cli()`.
  The GUI calls `main()` and passes `progress=`.
- No new dependencies without asking. `requirements.txt` is the list.
- Windows: never route file contents through PowerShell strings (Hebrew paths,
  cp1252). Use the Read/Edit/Write tools. `blastlib/progress.py` exists
  because of this.

---

## 8. Traps

- `--n-iter` changes every train/test split. Never compare runs with
  different values.
- One radius estimator drives both `R_conv` and `MaxR`/`Z_urban`. There is
  deliberately no way to set them separately.
- `tools/z_surface_3d` hard-codes production coefficients. After a
  regression re-run, compare with `final_production_convergence_coefficients_
  <method>.csv` and update the `COEF` dict by hand.
- Rows at or beyond the convergence radius stay in `max_radius_per_Z_*.csv`
  with `beyond_P`/`beyond_I` flags and are excluded from the Z_urban fit by
  `z_urban_valid_mask`. Do not drop them from the CSV.
- Files written by this version drop the `logRatio*` arrays and will not load
  in `compare_v6`.
- If only Phase-2 rows differ from the baseline, suspect a scikit-learn
  upgrade before suspecting the code (README §4).
