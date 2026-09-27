# Audit: reproducibility  (2026-09-27, commit 5f190291aa6b11b284efc3a315ee546595b421e3, tree dirty)

Branch `compare-v7`. Two states are audited separately:

- **HEAD**: the committed tree at 5f19029. I read it from git objects (`git archive HEAD` and `git show HEAD:<path>`) into a scratch folder outside the repo. Nothing was checked out or stashed.
- **WT**: the working tree as it stands.

"(a)" below means HEAD code vs HEAD tables, and "(b)" means WT code vs WT tables. All regenerated output went to a scratch directory under the session temp folder. That directory was deleted at the end. This file is the only thing written inside the repo.

Rules followed (CLAUDE.md §1, §5 and the caller's brief):
- Commands run in the repo: only the fast test suite and the Phase-2 smoke run (`--phase 2 --n-iter 20 --no-figures`) with `--tables-dir` and `--figures-dir` redirected to scratch.
- The production pipeline (`--phase all --n-iter 500`) was not run, and neither were the full Phase 1, the slow tests or any `tools/` CLI.
- No cloud placeholder was downloaded. Offline flags were re-checked after the test run: all 288 placeholders are still offline.

## Tree state

- `git status --porcelain`: 79 entries before the audit. 30 are modified tracked files and 49 are untracked.
- Modified code (19 files). Numerically relevant:
  - `blastlib/processing/free_field.py` and `run_analysis.py`: per-direction exceedance level for MaxR, plus new columns `R_free` and `ExcludeR`.
  - `blastlib/regression/z_urban.py`: two new fit-domain conditions (`R_free < R_conv`, `R_free > exclude_r`), and the `B_open` upper bound raised from 8 to 20.
  - `blastlib/io/npz_store.py` and `blastlib/paths.py`: v3 raw-store support and `default_npz_dir`.
  - `blastlib/regression/cross_validation.py`: log text only. The CSV outputs are unchanged by this diff.
- Modified results-of-record tables (11). `git diff --stat -- outputs/`:

```
 best_convergence_coefficients_req.csv              |   10 +-
 best_test_configs_req.csv                          |   34 +-
 best_z_urban_coefficients_req.csv                  |    8 +-
 best_z_urban_coefficients_req_soft3.csv            |    8 +-
 cv_summary_req.csv                                 | 1000 ++---
 cv_summary_req_soft3.csv                           | 1000 ++---
 final_production_convergence_coefficients_req.csv  |   10 +-
 final_production_z_urban_coefficients_req.csv      |    8 +-
 final_production_z_urban_coefficients_req_soft3.csv|    8 +-
 max_radius_per_Z_req.csv                           | 3842 ++++++------
 max_radius_per_Z_req_soft3.csv                     | 3842 ++++++------
 11 files changed, 4885 insertions(+), 4885 deletions(-)
```

- Untracked files the WT results depend on:
  - `blastlib/io/raw_store.py`: imported by WT `run_analysis.py` and needed to read `data/raw_npz`. It was never committed.
  - Tests: `tests/test_raw_store.py`, `test_maxr_consistency.py`, `test_z_urban_domain.py` and `test_gui_specs_soft.py`.
  - Docs: `CLAUDE.md` itself, `docs/ALGORITHM.md` and `docs/ALGORITHM_HE.md`.
  - Untracked result files: 13 tables (the `_p95` and `_req_soft2` Phase-2 outputs, plus `max_radius_per_Z_req_soft2.csv`) and 11 `outputs/check_results/*.csv`.
- Production estimator: `blastlib/constants.py::RADIUS_ESTIMATOR = {'method': 'req_soft3'}`. `constants.py` is unmodified, so production is `req_soft3` in both states.

## Environment

| item | value | note |
|---|---|---|
| Python | 3.12.10 (Microsoft Store build) | The only working interpreter. `py -0p` also lists 3.14 at `...\Programs\Python\Python314`, but that folder has no `python.exe`. |
| numpy | 2.4.6 | req. >=1.24, ok. The street parity report (2026-08-06) records 2.4.4. |
| pandas | 3.0.3 | req. >=2.0, ok. The parity report records 3.0.1. |
| scipy | 1.17.1 | req. >=1.10, ok. Same as the parity report. |
| scikit-learn | 1.9.0 | req. >=1.3, ok. No record of the version used for the committed Phase-2 tables. |
| matplotlib | 3.10.9 | req. >=3.7, ok |
| pytest | **not installed** | Listed in `requirements-optional.txt`. `python -m pytest` fails as-is. For this audit, pytest 9.1.1 was installed into the scratch folder only (`pip install --target`) and used through `PYTHONPATH`. The owner's environment was not changed. |
| pyvista / openpyxl | 0.48.4 / 3.1.5 | optional, present |
| git EOL | `core.autocrlf=true` (system gitconfig), no `.gitattributes` | Index is LF and checkout is CRLF (`git ls-files --eol`). |

`requirements.txt` gives lower bounds only. There is no lock file or recorded environment for the committed Phase-1 and Phase-2 tables.

## Data present

Attributes were read with `Get-ChildItem` and `attrib`. No file contents were read from the placeholder stores.

| directory | files | bytes | state |
|---|---|---|---|
| `data/raw_npz` (v3) | 96 | 954,350,173 | **Local.** No `O` flag. Also no `P` flag, so it is not pinned "Always keep on this device" as CLAUDE.md §5 asks. |
| `data/processed_npz` (v1) | 96 | 5,421,920,832 | **All 96 cloud placeholders** (`O`, RecallOnDataAccess) |
| `data/processed_npz_v2` | 96 | 7,770,140,736 | **All 96 cloud placeholders** |
| `data/obs_npz` | 96 | 6,440,985,892 | **All 96 cloud placeholders** |
| `data/vtk`, `data/viper1d` | 0 | - | empty |
| `data/free_field_data.csv` | 1 | 3,462 | Local, tracked, identical to HEAD |

The pipeline's default store is `raw_npz`, via `paths.default_npz_dir()` in WT. It is present. The v1 and v2 stores that the anchor tests read are absent for reproducibility purposes.

## Tests

### WT fast suite

Command: `python -m pytest -q -p no:cacheprovider -m "not slow" -rsfE`, plus 11 `--deselect` flags. `PYTHONDONTWRITEBYTECODE=1` and `--basetemp` pointed at scratch.

**100 passed, 0 failed, 0 skipped, 16 deselected**, in 4.6 s. There were 6 RuntimeWarnings (divide by zero in `blastlib/processing/grids.py:132`, `ratioI3 = impulse3 / refI3`).

Deselected by the `slow` marker (5; the full-data sweeps were not run):
- `test_street_anchors.py::test_anchor_stability_median_all_configs`
- `test_street_anchors.py::test_anchors_match_pinned`
- `test_street_master_curve.py::test_constants_match_pinned`
- `test_street_validation.py::test_validation_matches_pinned`
- `test_street_validation.py::test_envelope_true_stats`

Deselected by me (11), because each opens a v1 or v2 file that is a cloud placeholder:
- `test_npz_anchors.py::test_shipped_radius_p_v1[config_93]`, `[config_95]`: **the RadiusP anchors**
- `test_npz_anchors.py::test_shipped_radius_p_v2[config_93]`, `[config_95]`: **the RadiusP anchors**
- `test_soft_criterion.py::test_beta_inf_reduces_to_hard_on_npz[config_93]`, `[config_95]`
- `test_raw_store.py::test_expansion_matches_shipped_v2_bit_for_bit`
- `test_raw_store.py::test_coordinates_rebuilt_exactly`
- `test_raw_store.py::test_detected_as_raw` (opens the first v2 file)
- `test_gui_soft_wiring.py::test_raw_fields_probe_v1_lacks_keys`
- `test_gui_soft_wiring.py::test_raw_fields_probe_v2_ok`

Why they were deselected rather than left to skip: the `_require_config` fixture checks `Path.exists()`, which is True for a OneDrive placeholder. The documented command would therefore not skip these tests. It would download config_01, config_93 and config_95 from both stores, about 410 MB (see REP-07).

**By CLAUDE.md §5, the anchor tests did not run.** Numbers are not to be trusted on the strength of this suite alone.

Substitute check (not the test itself): the same chain as `test_npz_anchors._radius_p`, run on `data/raw_npz` with WT code:

| config | computed RadiusP (req) | anchor | bit-exact |
|---|---|---|---|
| config_93_det2_b10_s5_h15_w250 | 62.328853560057645 | 62.328853560057645 | yes |
| config_95_det2_b10_s5_h24_w250 | 38.15139013777145 | 38.15139013777145 | yes |

The raw store therefore reproduces the anchor values. The claim that v3 equals v2 bit for bit (`test_raw_store.py`, quoted in the WT README) remains unverified.

### HEAD's own fast suite on HEAD code

The extracted HEAD tree was run in scratch. It has no data folder there, so data tests skip.

**56 passed, 3 failed, 2 errors, 8 skipped, 5 deselected (slow).**
- Failed:
  - `test_street_gui_spec.py::test_street_model_tab_wiring`, `::test_street_preview_tab_wiring`: "expected exactly one tab"
  - `test_street_gui_spec.py::test_street_tabs_are_last`: the last tabs are `['Migrate VTKs', 'Validate']`
- Errors: `test_street_anchors.py::test_slope_anchor_goldens_both_widths` and `test_street_strip.py::test_strip_matches_historical`, both with `AttributeError: module 'blastlib.paths' has no attribute 'default_npz_dir'` raised from `tests/conftest.py:49`.
- Skipped (8): v1 and v2 files missing.

HEAD's committed tests fail against HEAD's committed code (see REP-02).

## Pinned artefacts

| artefact | exists | tracked | last commit | guard test | guard ran? |
|---|---|---|---|---|---|
| RadiusP anchors 62.3288... / 38.1513... (inline, `tests/test_npz_anchors.py`) | n/a | yes (test at 098056d) | 098056d | `test_shipped_radius_p_v1/_v2` | **No** (placeholders). Substitute on raw_npz is bit-exact. |
| Same anchors in `test_soft_criterion.py` (beta->inf) | n/a | yes | 430d004 | `test_beta_inf_reduces_to_hard_on_npz` | **No** (placeholders) |
| v3 == v2 bit for bit | n/a | test **untracked** | - | `test_raw_store.py::test_expansion_matches_shipped_v2_bit_for_bit` | **No** (placeholders) |
| config_93 street goldens (inline, `test_street_anchors.py` GOLDEN_93) | n/a | yes | 6a44ee8 | `test_slope_anchor_goldens_both_widths` | Yes, passed on raw_npz (WT). Errors at HEAD. |
| config_93 strip goldens (inline, `test_street_strip.py`) | n/a | yes | 6a44ee8 | `test_strip_matches_historical` | Yes, passed on raw_npz (WT). Errors at HEAD. |
| `outputs/check_results/street_anchors.csv` | yes | yes | bf8eefe | `test_anchors_match_pinned` (slow) | **No.** It is read by 3 fast tests (`test_cloud_gate_uses_floor`, `test_gate_classification`, `test_membership_is_computed`), which passed. |
| `outputs/check_results/master_curve_g.csv` | yes | yes | bf8eefe | `test_constants_match_pinned` (slow) | **No** |
| `outputs/check_results/e_profile_validation_88.csv` | yes | yes | bf8eefe | `test_validation_matches_pinned` (slow) | **No.** Rows quoted in `test_street_model.py::test_e_peak_historical_values`, which passed. |
| `outputs/check_results/street_parity_report.md` | yes | yes | 06d09ca | none (produced by `tools/street/street_parity.py`) | Not run. At HEAD the tool cannot run (REP-02). |
| `outputs/check_results/street_parity/` (rebuilt copies) | yes | **no, gitignored** (`.gitignore:22`) | - | - | - |
| `final_production_z_urban_coefficients_*.csv` | yes | soft3, soft4, req yes; p95, soft2 untracked | various | `test_z_urban_domain.py::test_no_production_coefficient_sits_on_a_bound` (test **untracked**) | Yes, passed on WT tables |

## Smoke pipeline

Command (CLAUDE.md §5, redirected):

```
python run_analysis.py --phase 2 --n-iter 20 --no-figures --tables-dir <scratch>/run_X --figures-dir <scratch>/run_X/figs [--radius-method M]
```

Each run folder held only copies of `convergence_table_M.csv` and `max_radius_per_Z_M.csv`, taken from the matching state. HEAD code was run as `<scratch>/head_src/run_analysis.py`. Each run took **2.5 to 3.2 s**. Phase 2 writes only into `--tables-dir` (checked in `cross_validation.py`, `output.py` and `plots.py`).

What is comparable at n_iter=20:
- `final_production_*`: the 100%-data refit, independent of n_iter. Compared **exactly**.
- `cv_summary`: the first 20 splits are the same at n_iter=20 and n_iter=500 (REP-09). These rows are compared with rows 0-19 of the committed 500-row file.
- `best_*` and `best_test_configs`: the committed best iteration is 180 (soft3, soft4, soft2, WT req), 475 (HEAD req) or 39 (p95). All lie outside the first 20 splits, so these files are compared **structurally only**. Columns match, row counts match (4 and 20), values differ as expected.

### Production fits (exact, max abs / max rel over all numeric cells)

The byte comparisons normalise EOL. The regenerated WT files are also **raw-byte identical** to the working-tree files, CRLF included.

| state | suffix | code | inputs | `final_production_convergence_coefficients` | `final_production_z_urban_coefficients` |
|---|---|---|---|---|---|
| (a) HEAD | req_soft3 | HEAD | HEAD | **EQUAL**, byte-identical | **EQUAL**, byte-identical |
| (b) WT | req_soft3 | WT | WT | **EQUAL**, byte-identical | **EQUAL**, byte-identical |
| (a) HEAD | req | HEAD, default models (relwls/quad) | HEAD | **DIFF** (max abs 1.12, max rel 1.40). Committed file lacks `r2_sW13sq`. | EQUAL |
| (a) HEAD | req | HEAD, `--model-p legacy --model-i legacy` | HEAD | Values EQUAL (max abs 0). Regenerated file has an extra `r2_sW13sq` column (0.0), so not byte-identical. | EQUAL |
| (b) WT | req | WT | WT | EQUAL | EQUAL |
| WT | req_soft4 (tracked, unmodified) | WT | WT (= HEAD) | EQUAL | **DIFF** (max abs 4.33 on `B_open`, max rel 1.68) |
| WT | req_soft4 | HEAD | same | EQUAL | EQUAL |
| WT | p95 (finals untracked) | WT | WT | EQUAL | **DIFF** (max abs 19.58 on `B_open`, max rel 0.98) |
| WT | p95 | HEAD | same | EQUAL | EQUAL |
| WT | req_soft2 (untracked) | WT | WT | EQUAL | **DIFF** (max abs 3.33 on `B_open`, max rel 1.68) |
| WT | req_soft2 | HEAD | same | EQUAL | EQUAL |

### cv_summary, first 20 splits vs committed rows 0-19

| suffix | code, inputs | max abs diff | cells not bit-equal |
|---|---|---|---|
| req_soft3 | HEAD, HEAD | 6.2e-15 | 2 of 140 (`conv_I`, rel 1.2e-15) |
| req_soft3 | WT, WT | 6.2e-15 | 2 of 140 (`conv_I`, rel 1.2e-15). Same cells as HEAD. |
| req | HEAD, HEAD (legacy models) | 1.8e-15 | - |
| req | HEAD, HEAD (default models) | 3.09 | committed file is legacy-model output |
| req | WT, WT | 6.2e-15 | - |
| req_soft4 / req_soft2 / p95 | HEAD code on those inputs | <= 6.2e-15 | - |
| req_soft4 / req_soft2 / p95 | WT code on those inputs | 1.19 / 1.18 / 1.48 | z columns (new fit domain) |

### Phase-1 spot check (2 of 96 configs; not the Phase-1 run)

WT `run_analysis.run_phase1` was run on a scratch folder holding copies of `config_93` and `config_95` from `data/raw_npz`, with `make_figures=False`. Outputs went to scratch.

| suffix | table | rows | vs committed WT rows |
|---|---|---|---|
| req_soft3 | convergence_table | 2 | bit-exact, same columns |
| req_soft3 | max_radius_per_Z | 40 | bit-exact, same columns |
| req | convergence_table | 2 | bit-exact |
| req | max_radius_per_Z | 40 | bit-exact |

HEAD's code cannot read the v3 store, and the v2 store it defaults to is placeholders. As a proxy, the working-tree loader dumped the Phase-1 arrays for these 2 configs from raw_npz, and HEAD's `find_percentile_radius` was run on them. It reproduced the 80 HEAD-committed MaxR values per suffix (req_soft3, req) to **max abs 2.84e-14 (about 1 ulp), not bit-exact**.

The full Phase 1 (96 configs) was **not run**. It is not among the commands this audit was permitted to run.

## Determinism

The WT req_soft3 smoke run was repeated in two separate folders. All 8 CSVs and both PNGs are **byte-identical**. HEAD code gave the same `final_production_*` bytes as the committed HEAD files, and WT code gave the same bytes as the committed WT files. No run-to-run nondeterminism was observed.

## What moved between HEAD and the working tree

- **Unchanged**: `convergence_table_req_soft3.csv`, `convergence_table_req.csv`, `final_production_convergence_coefficients_req_soft3.csv`, `best_convergence_coefficients_req_soft3.csv`, `best_test_configs_req_soft3.csv`, all soft4 and p95 tracked tables, and every tracked `outputs/check_results/*`.
- **Production Z_urban, req_soft3** (`final_production_z_urban_coefficients_req_soft3.csv`, HEAD -> WT):

| Det | Target | coef | HEAD | WT | change |
|---|---|---|---|---|---|
| 1 | Pressure | C0 | 0.0866457 | 0.0911424 | +5.2% |
| 1 | Pressure | C1_amp | 1.74566 | 2.54678 | +45.9% |
| 1 | Pressure | A_switch | 2.74340 | 2.91913 | +6.4% |
| 1 | Pressure | B_open | 4.01230 | 7.13915 | +77.9% |
| 1 | Impulse | C0 | -0.0940698 | -0.107917 | -14.7% |
| 1 | Impulse | C1_amp | 2.96312 | 3.08839 | +4.2% |
| 1 | Impulse | C2_self | 0.834425 | 0.857314 | +2.7% |
| 1 | Impulse | C3_dilute | 1.67520 | 1.54962 | -7.5% |
| 2 | Pressure | C0 | 0.129362 | 0.112800 | -12.8% |
| 2 | Pressure | C1_amp | 0.527611 | 0.431982 | -18.1% |
| 2 | Pressure | A_switch | 2.22194 | 2.16969 | -2.4% |
| 2 | Pressure | B_open | 1.18181 | 0.943299 | -20.2% |
| 2 | Impulse | C0 | -0.00634786 | +0.00678694 | sign flip |
| 2 | Impulse | C1_amp | 2.66502 | 2.66443 | -0.02% |
| 2 | Impulse | C2_self | 1.09907 | 1.09853 | -0.05% |
| 2 | Impulse | C3_dilute | 0.752618 | 0.761353 | +1.2% |

- **Production convergence, req_soft3**: identical. For example, RadiusP det1 is C0=9.063101, C1=-0.645084, C2=2.018126, C3=0.590791.
- **req (hard) production convergence**: HEAD holds legacy-model output (plain-OLS RadiusP, 4-coefficient RadiusI). WT holds relwls/quad output.

| Det | Target | coef | HEAD | WT | change |
|---|---|---|---|---|---|
| 1 | RadiusP | C0 / C1 / C2 / C3 | 7.77806 / -0.576439 / 2.29845 / 0.575613 | 7.57426 / -0.530941 / 2.28444 / 0.592652 | -2.6% / +7.9% / -0.6% / +3.0% |
| 2 | RadiusP | C0 / C1 / C2 / C3 | 10.0604 / -1.15686 / 2.18508 / 0.709827 | 9.72597 / -1.09772 / 2.18572 / 0.775481 | -3.3% / +5.1% / +0.0% / +9.2% |
| 1 | RadiusI | A / p / q / r / r2 | 13.8149 / 0.167219 / 0.0247024 / -0.0260147 / - | 14.9363 / 0.203128 / 0.0238168 / 0.0652977 / -0.100537 | new quadratic term |
| 2 | RadiusI | A / p / q / r / r2 | 13.6284 / 0.144183 / 0.0797401 / 0.0442919 / - | 14.6024 / 0.175946 / 0.0789568 / 0.125061 / -0.0889284 | new quadratic term |

- **MaxR, `max_radius_per_Z_req_soft3.csv`**: 1920 rows. WT adds the columns `R_free` and `ExcludeR`. `P_ff` and `I_ff` are identical.
  - MaxR_P changed in 1915 of 1915 finite rows. Relative change: median -2.05%, 5-95% range [-7.75%, +0.11%], extremes -19.8% and +24.5%. Largest absolute move: config_93 at Z=20, 162.10 -> 135.30 m.
  - MaxR_I changed in 1911 of 1919 rows. Relative change: median +0.10%, 5-95% range [-0.39%, +3.99%], one outlier at +336%. Largest absolute move: config_18_det1_b15_s20_h24_w1500 at Z=12, 168.21 -> 223.02 m.
  - `beyond_P`: 11 flips from True to False. `beyond_I`: 9 flips from False to True and 2 from True to False.
- **Z_urban fit-domain rows** (det1/det2, each code's own mask on its own tables):
  - Pressure: 328/319 -> 280/311.
  - Impulse: 384/368 -> 340/360.
- **cv_summary_req_soft3 medians** over 500 splits (HEAD -> WT):
  - conv_P 8.786 -> 8.786 and conv_I 7.153 -> 7.153 (unchanged).
  - z_P 8.495 -> 8.417, z_I 9.491 -> 9.404, worst 9.860 -> 9.852.
  - Splits under 10%: 263 -> 272.
  - Best iteration 180 in both. Best worst-case MAPE 7.4207 -> 7.2028.
- **Attribution** (det1 Pressure `B_open`, rows = code, columns = tables):

| | HEAD tables | WT tables |
|---|---|---|
| HEAD code | 4.012 (committed HEAD) | 3.287 |
| WT code | 6.787 | 7.139 (committed WT) |

  The uncommitted Phase-2 change (fit domain and bound) moves the coefficients the most. The Phase-1 change (per-direction MaxR level) moves them less. Both are needed to reproduce the WT file.

## Results-of-record inventory

Status: **R** = reproduced at this state, **N** = not reproduced, **-** = not checked. "Needs" gives what would test it.

| result | HEAD (a) | WT (b) | needs |
|---|---|---|---|
| `final_production_convergence_coefficients_req_soft3.csv` | R (byte) | R (byte) | - |
| `final_production_z_urban_coefficients_req_soft3.csv` | R (byte) | R (byte), **only with uncommitted code** | commit, then re-check |
| `convergence_table_req_soft3.csv` | - (HEAD code needs v2 placeholders) | spot check 2/96 bit-exact; rest - | full Phase 1 into scratch (owner approval; raw_npz is local) |
| `max_radius_per_Z_req_soft3.csv` | 2/96 configs at 2.8e-14 (HEAD algorithm on raw arrays) | 2/96 bit-exact; rest - | full Phase 1 |
| `theta_radius_P/I_req_soft3.csv` | - | - | full Phase 1 |
| `cv_summary_req_soft3.csv` | rows 0-19 to 6e-15 (2 cells not bit-equal); rows 20-499 - | same | Phase 2 at n_iter=500 into scratch (~1 min) |
| `best_convergence_coefficients_req_soft3.csv`, `best_z_urban_coefficients_req_soft3.csv`, `best_test_configs_req_soft3.csv` | - (best split is 180) | - | Phase 2 at n_iter >= 181 (production 500) |
| `final_production_convergence_coefficients_req.csv` | **N** with HEAD defaults. Values R with `legacy/legacy`, but not byte-identical (extra column). | R | - |
| `final_production_z_urban_coefficients_req.csv` | R | R | - |
| `cv_summary_req.csv` | rows 0-19 R with `legacy/legacy` only | rows 0-19 R | n_iter=500 |
| `best_*_req.csv`, `best_test_configs_req.csv` | - (best split is 475) | - (best split is 180) | n_iter=500 |
| `convergence_table_req.csv`, `max_radius_per_Z_req.csv` | as soft3 | 2/96 bit-exact | full Phase 1 |
| req_soft4 tables (`final_production_*`, `cv_summary`, `best_*`, `max_radius_per_Z`) | finals R, cv rows 0-19 R | **N** for z_urban with WT code (stale vs WT code) | decision on which code is canonical |
| p95 and req_soft2 finals (untracked) | n/a (not in any commit) | reproduced by HEAD code, **N** with WT code | - |
| `convergence_table_req_soft{2,4,6,8,12}.csv`, `convergence_table_p95.csv`, `theta_radius_*` (tracked) | - | - | Phase 1 per suffix |
| Unsuffixed legacy tables (`convergence_table.csv`, `final_production_*.csv`, ...) and `SHIPPED_*` | - | - | Not regenerable by the current CLI (the method token is always resolved, so a suffix is always added). Pre-suffix history. |
| Street pinned CSVs (`street_anchors.csv`, `master_curve_g.csv`, `e_profile_validation_88.csv`) | **N**: cannot run at HEAD (REP-02) | - (slow guards not run). Inline config_93 goldens R. | slow tests (full suite, owner approval) |
| `street_parity_report.md` | **N**: tool cannot run at HEAD | - | `tools/street/street_parity.py`, which writes under `outputs/` |
| `logo_cv_*`, `logo_summary_*`, `soft_beta_selection*`, `soft_criterion_summary.csv`, `safe_domain_req_soft3.csv`, `npz_v2_validation.csv`, `rlocal_diagnosis.csv`, `r_peak_all96.csv`, `validation_comparison_req.csv` | - | - | the respective `tools/` CLIs, which write under `outputs/` |

**Results of record that cannot be tied to the current commit: 39 files.**
- 11 tracked tables whose WT content differs from HEAD and is produced by uncommitted code.
- 4 tracked street artefacts (3 CSVs plus the parity report) whose generator cannot run at HEAD.
- 24 untracked result files (13 tables, 11 check_results CSVs) that are in no commit.

At HEAD itself, 5 of the 11 req-suffix files (`final_production_convergence_coefficients_req`, `best_convergence_coefficients_req`, `best_z_urban_coefficients_req`, `best_test_configs_req`, `cv_summary_req`) hold legacy-model output that HEAD's defaults do not reproduce.

## Findings

### REP-01 [high] The production Z_urban coefficients differ between HEAD and the working tree, and the WT values come from uncommitted code

Evidence:
- `final_production_z_urban_coefficients_req_soft3.csv` is modified. All 16 coefficients moved (table above). For det1 Pressure, `B_open` goes 4.012 -> 7.139 (+78%) and `C1_amp` goes 1.746 -> 2.547 (+46%). For det2 Impulse, `C0` changes sign.
- The WT file is regenerated byte for byte only by WT code on WT tables. HEAD code on WT tables gives `B_open` = 3.287, and WT code on HEAD tables gives 6.787.
- The WT code depends on:
  - modified `z_urban.py`: fit domain, and bound 8 -> 20;
  - modified `free_field.py` and `run_analysis.py`: MaxR level;
  - the untracked `blastlib/io/raw_store.py`, which reads `data/raw_npz`.
- The guard test for the new domain, `tests/test_z_urban_domain.py`, is untracked.
- `best_z_urban_coefficients_req_soft3.csv`, `cv_summary_req_soft3.csv` (z columns) and `max_radius_per_Z_req_soft3.csv` moved with it.
- CLAUDE.md §3 requires results of record to be reproducible from the code at the same commit, and §1.3 requires old and new values before a change is made. `WORKLOG.md` does not exist in the repo (REP-10), so no record of this move was found.

Implication (not verified): the LOGO numbers and `soft_beta_selection_note.md`, which justify beta=3, were produced with HEAD's Z_urban code. Their z-target figures may no longer match the WT code.

### REP-02 [high] HEAD is not self-contained: committed street code and tests call a function that was never committed

Evidence:
- `paths.default_npz_dir` is called in HEAD's:
  - `blastlib/street/anchors.py:155`, `fitting.py:73`, `validation.py:62`, `figures.py:160,308`;
  - `gui/street_preview.py:140`;
  - `tools/street/street_figure.py:68`, `street_parity.py:112`;
  - `tests/conftest.py:49,60`.
- `git log -S "def default_npz_dir" -- blastlib/paths.py` is empty: the definition exists only in the uncommitted `paths.py`. The callers arrived in bf8eefe and 6a44ee8.
- HEAD's fast suite on HEAD code gives 3 failed and 2 errors, for the reasons in "Tests" above. The 3 GUI failures happen because the street tabs exist only in the uncommitted `gui/specs.py`.
- Commit 06d09ca ("rebuild reproduces every pinned artefact exactly", "PASS at HEAD 6a44ee8") cannot be re-run from 6a44ee8 or from HEAD. `street_parity.py:112` evaluates `paths.default_npz_dir(soft=True)` as an argument, so it raises even when `--npz-dir` is given.
- The street pinned-artefact parity therefore depends on uncommitted code and is not tied to any commit.

### REP-03 [medium] The anchor tests and the v2/v3 equivalence tests did not run: their data is cloud-only

Evidence:
- All 96 files in `processed_npz` and `processed_npz_v2` carry the `O` attribute.
- 11 tests were deselected, listed under "Tests". They include all 4 `test_npz_anchors` cases and the 3 `test_raw_store` cases that compare against v2.
- Mitigation: the anchor chain on `raw_npz` reproduces 62.328853560057645 and 38.15139013777145 bit-exactly, and 2 of 96 configs reproduce the committed WT Phase-1 rows bit-exactly.
- Still unverified: the README claim that v3 equals v2 bit for bit, and the other 94 configs.

### REP-04 [medium] The working tree mixes tables from two code states

Evidence:
- req_soft3 and req were regenerated with WT code: their MaxR tables have `R_free` and `ExcludeR`.
- req_soft4 (tracked, cbb2312), p95 and req_soft2 (untracked) still come from HEAD-era code. Their MaxR tables lack the new columns.
- WT code does not reproduce their `final_production_z_urban_coefficients` (`B_open` max abs 4.33 / 19.58 / 3.33). HEAD code does.
- Any comparison across beta values, such as soft3 vs soft4 in the beta-selection material, would compare outputs of different Z_urban code in the WT.

### REP-05 [medium] At HEAD, the req convergence coefficients were stale against HEAD's own defaults

Evidence:
- HEAD's `final_production_convergence_coefficients_req.csv` (last touched in 78352a6) has no `r2_sW13sq` column. HEAD's default models (relwls/quad, adopted in f34cf2f) give max abs diff 1.12.
- The file reproduces numerically only with `--model-p legacy --model-i legacy`, and even then it gains an extra `r2_sW13sq`=0.0 column, so it is not byte-identical.
- The same applies to HEAD `cv_summary_req.csv`: rows 0-19 match legacy output to 1.8e-15 and default output only to 3.09. `best_*_req.csv` are affected the same way.
- The WT regenerates these with relwls/quad. Committing the WT would fix this, but it would also move the numbers.

### REP-06 [medium] Hard-coded copies of results of record disagree with the tables

Evidence:
- `blast_calculator.html:249-252` embeds HEAD's req_soft3 Z_urban coefficients to 6 dp (for example B=4.012298 and C1=1.745664 for det1 P). The WT values (7.139152, 2.546779, ...) appear nowhere in the file, so the calculator is stale against the WT tables.
- `tools/z_surface_3d/z_surface_3d.py:34-37` COEF holds (7.778, -0.576, 2.298, 0.576; 10.060, -1.157, 2.185, 0.710). These are HEAD's **req legacy-OLS** RadiusP coefficients. They match neither the production req_soft3 RadiusP (9.063, -0.645, 2.018, 0.591; 11.858, -1.375, 2.782, 0.776) nor the WT req values. CLAUDE.md §8 names this trap.

### REP-07 [low] Placeholder handling: the fixtures download instead of skipping, and raw_npz is not pinned

Evidence:
- `tests/conftest.py::_require_config` tests `Path.exists()`, which is True for OneDrive placeholders. The documented `python -m pytest -q -m "not slow"` would download about 410 MB (v1 and v2 config_01, 93, 95) rather than skip.
- `data/raw_npz` is local but has no `P` (pinned) flag. CLAUDE.md §5 asks for "Always keep on this device", and OneDrive can evict an unpinned file.

### REP-08 [low] Environment: pytest is missing, no version record, and bit-level reproducibility holds only for some tables

Evidence:
- pytest is absent from the only working interpreter. The Python 3.14 registration is broken.
- `requirements.txt` gives lower bounds only, and no environment was recorded for the Phase-1 and Phase-2 tables. The street parity report records numpy 2.4.4 and pandas 3.0.1; installed now are 2.4.6 and 3.0.3.
- Two `conv_I` cells in rows 0-19 of the committed `cv_summary_req_soft3.csv` differ from today's run at 1.2e-15 relative. HEAD MaxR values reproduce to 2.8e-14, not bit-exact. The `final_production_*` files are byte-identical.
- CLAUDE.md §4.4 ("regenerate byte for byte") therefore holds for the production files, and not for every table in this environment.

### REP-09 [low] The documentation says `--n-iter` changes the whole split sequence; with scikit-learn 1.9.0 it does not

Evidence:
- CLAUDE.md §4.3 and §8, and the `run_cross_validation` docstring, say the whole sequence changes.
- Measured: with 96 labels, the first 20 test sets from `StratifiedShuffleSplit(500, test_size=0.2, random_state=42)` equal those from `n_splits=20`. The n_iter=20 `cv_summary` reproduces rows 0-19 of every committed n_iter=500 file to <= 6.2e-15.
- What n_iter does change is the pool the `best_*` split is chosen from, and the distribution statistics.
- Recorded as a finding, not a correction: the owner decides on the wording.

### REP-10 [low] Documents that CLAUDE.md relies on for provenance are missing or untracked

Evidence:
- `WORKLOG.md` and `docs/TRACEABILITY.md` do not exist in the repo or in git history.
- `CLAUDE.md`, `docs/ALGORITHM.md` and `docs/ALGORITHM_HE.md` are untracked.
- The rules for recording changes to results of record (§1.3, §6) have nowhere to point.

### REP-11 [info] Line endings

The index is LF. The checkout and pandas 3 output on Windows are CRLF (`core.autocrlf=true` from the system gitconfig). Regenerated tables are raw-byte identical to the working-tree files, and differ from the blobs only in EOL. A byte-level comparison against `git show` output must normalise EOL.

### REP-12 [info] Legacy unsuffixed tables cannot be regenerated by the current CLI

`convergence_table.csv`, `max_radius_per_Z.csv`, `final_production_*.csv`, `cv_summary.csv`, `best_*.csv` and `theta_radius_{P,I}.csv` carry no estimator suffix. `run_phase1` and `run_phase2` always resolve a method token, so no current command writes these names. They are pre-suffix history (2582ca4). `SHIPPED_*_req.csv` are migration references.

## Checked and found consistent

- HEAD code on HEAD Phase-1 tables regenerates HEAD's `final_production_convergence_coefficients_req_soft3.csv` and `final_production_z_urban_coefficients_req_soft3.csv` byte for byte (EOL-normalised).
- WT code on WT tables regenerates WT's production files for req_soft3 and req byte for byte, raw bytes included.
- Two identical smoke runs are byte-identical: 8 CSVs and 2 PNGs.
- The RadiusP anchors (config_93, config_95) reproduce bit-exactly from `data/raw_npz`.
- WT `run_phase1` reproduces the committed WT `convergence_table` and `max_radius_per_Z` rows for config_93 and config_95 bit-exactly, for req and req_soft3.
- HEAD's MaxR algorithm reproduces HEAD's committed MaxR rows for those 2 configs to 2.8e-14.
- `cv_summary` rows 0-19 match the committed 500-row files to <= 6.2e-15 for req_soft3 (both states), WT req, and HEAD req with legacy models.
- `convergence_table_req_soft3.csv` and `final_production_convergence_coefficients_req_soft3.csv` are identical at HEAD and WT.
- The impulse-side coefficients agree between req and req_soft3 where they should: the impulse path is the same under hard and soft criteria.
- `test_no_production_coefficient_sits_on_a_bound` passes on the WT tables. The WT det1 `B_open` of 7.139 lies inside both the old bound (8) and the new one (20).
- `data/free_field_data.csv` is identical to HEAD.
- The WT fast suite passes: 100/100 of the tests run.
- No file in the repo, ignored folders included, has a modification time later than the start of the audit. The placeholder stores are still offline.

## Not checked

- **Full Phase 1** (96 configs) for any suffix, at HEAD or WT. Not among the commands permitted to this audit. At WT it needs only the local `raw_npz`; at HEAD it needs `processed_npz_v2` (7.8 GB, cloud). It would verify `convergence_table_*`, `max_radius_per_Z_*` and `theta_radius_*` in full. Suggested, with owner approval: `python -u run_analysis.py --phase 1 --no-figures --tables-dir <scratch> --figures-dir <scratch>`.
- **Phase 2 at n_iter=500 into scratch** (about 1 min at the measured 2.7 s per 20 splits). It would verify `cv_summary_*` in full and `best_*`. Needs owner approval, because it is the production Phase-2 configuration.
- **The 11 deselected tests**, the anchor tests included. Needs `processed_npz` and `processed_npz_v2` config_01, 93 and 95 made local (about 410 MB).
- **The 5 slow tests** (street pinned CSVs, master curve, validation, envelope, anchor stability). Needs the full suite, which is not on the agent's free list in CLAUDE.md §5.
- **`tools/check_formulas`, `tools/logo_cv`, `tools/street/street_parity.py`** and every other tool that writes under `outputs/`. None was run. Their outputs in `outputs/check_results/` were not regenerated.
- The untracked root files `diag_estimator.py`, `rchan.csv` and `rchan2.csv`, and the untracked `outputs/check_results/*.csv`: inspected neither for provenance nor for use.
- Figures (not of record).
- Whether the thesis text cites the HEAD or the WT coefficients. The thesis is outside the repo and off limits.
