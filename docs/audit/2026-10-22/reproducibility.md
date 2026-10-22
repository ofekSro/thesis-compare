# Audit: reproducibility  (2026-10-22, commit eec48dc, tree dirty)

Pre-commit check for D37 (the D34 cut on `refP{g}_fill` / `refI{g}_fill`).

**HEAD moved during the audit.** I started at `1b9dac7`. At 13:55 the owner committed `eec48dc` ("reqdir91_soft3: production tables after D37 (n_iter 500)"), which holds the 4 regenerated tables. `blastlib/processing/grids.py`, `tests/test_grids_merge.py`, `docs/DECISIONS.md` (D37) and `blastlib/constants.py` are still uncommitted. All runs below used the working-tree (WT) code. Where I needed the pre-D37 code I built a scratch copy of WT with `grids.py` and `constants.py` taken from `1b9dac7` ("HEAD-code" below). Nothing was written into the repo except this file. Scratch outputs were deleted at the end.

Commands run in the repo: the fast and full pytest suites, `run_analysis.py --phase 1 --no-figures` (full 96 configs, never into `outputs/`), `--phase 2 --n-iter 20 --no-figures`, `tools/logo_cv/logo_cv.py --out-dir <scratch>`, `tools/check_formulas/check_formulas.py --out-dir <scratch>`. Not run: `--phase all --n-iter 500`, any `tools/` CLI that writes into `outputs/`. After every run `git status --porcelain outputs` was identical to the start.

## Carry-over from 2026-09-27

Source: `docs/audit/2026-09-27/reproducibility.md`, rows REP-01 to REP-12 of SUMMARY.md, and the D entries citing them (D1, D18, D29). Statuses come from today's code, tables and tests.

| old id | sev | status | evidence | decision |
|---|---|---|---|---|
| REP-01 | high | **regressed** | The old defect (production Z_urban from uncommitted code) was fixed by D1(b): `z_urban.py`, `free_field.py`, `raw_store.py` etc. are committed and `git diff HEAD -- blastlib` now shows only `constants.py` and `grids.py`. It is back for D37: the 4 tables of `eec48dc` come from the uncommitted `grids.py` (see Findings, REP-01). HEAD code regenerates `max_radius_per_Z_reqdir91_soft3.csv` of `1b9dac7` exactly, and does NOT regenerate the one of `eec48dc` (max abs diff 2.26 min, max rel 0.27). | D1 (in force): "commits together". Not followed in `eec48dc`. |
| REP-02 | high | resolved | `paths.default_npz_dir` is in `blastlib/paths.py`, tracked, introduced in `5105dea` (`git log -S`). `paths.py` is not in the WT diff. | D29 (fixed) |
| REP-03 | medium | resolved | Anchor tests run: `tests/test_npz_anchors.py` re-pinned on `raw_npz` at `1f72a79` (62.328853560057645 / 38.15139013777145). Fast suite 162 passed, 0 skipped; full 168 passed, 0 skipped. | D18 (REP-03 part) |
| REP-04 | medium | open (worse) | WT still mixes code states. Today `req_soft3` and `reqdir_soft3` max_radius tables regenerate with HEAD-code but not with WT code (Findings REP-13); `req` and `p95` do not regenerate with either (REP-05). | none |
| REP-05 | medium | open | `convergence_table_req.csv` and `_p95.csv` regenerated from `raw_npz` differ from the tracked ones (convergence table `req`: max abs 266, columns RadiusP, RadiusI, PressureAtR, ImpulseAtR). The convergence path is not touched by D37, so this is the older drift. | none |
| REP-06 | medium | partially | `tools/z_surface_3d/z_surface_3d.py` COEF now equals `final_production_convergence_coefficients_reqdir91_soft3.csv` (10.075/-0.750/2.390/0.424 and 11.544/-0.768/1.925/0.657). `blast_calculator.html:236-260` still holds the 2026-09-28 `req_soft3` values (CONV_P det1 C0 9.844992, ZU P1 C0 0.095400); they equal neither the tracked `req_soft3` tables (C0 10.1448; Z_urban C0 0.1245) nor `reqdir91_soft3`. | none |
| REP-07 | low | open | `tests/conftest.py:26-30` still tests `Path.exists()`. `data/raw_npz` has no `P` (pinned) flag (`attrib`: `A` only). All v1/v2/raw stores are local today (no `O` flag), so nothing downloads now. | D18 (REP-07 part says "anchors ran") |
| REP-08 | low | partially | pytest 9.1.1 is installed in the working interpreter. No lock file; `requirements.txt` gives lower bounds only (h5py added). The environment differs from the last audit (numpy 2.4.4 vs 2.4.6, pandas 3.0.1 vs 3.0.3, scikit-learn 1.8.0 vs 1.9.0), and the regenerated tables are still byte-identical to the tracked ones. | D18: "not recorded" |
| REP-09 | low | open | CLAUDE.md:175 and `run_analysis.py:558` still say `--n-iter` changes the whole split sequence. Measured again: `cv_summary` of an `--n-iter 20` run equals rows 0-19 of the committed n_iter=500 file with max abs diff 0 (all columns). | D18: "not recorded" |
| REP-10 | low | partially | `WORKLOG.md`, `CLAUDE.md`, `docs/ALGORITHM.md`, `ALGORITHM_HE.md` are tracked. `docs/TRACEABILITY.md` does not exist. `CLAUDE.md`, `ALGORITHM*.md`, `WORKLOG.md`, `DECISIONS.md` are modified and uncommitted. | none |
| REP-11 | info | open | `git ls-files --eol`: index LF, working tree CRLF. | none |
| REP-12 | info | open | `outputs/tables/cv_summary.csv`, `max_radius_per_Z.csv` and the other unsuffixed legacy tables are still tracked and no current command writes them. | none |

Counts: resolved 2, regressed 1, partially 3, open 6, superseded 0 (total 12). Old high ids not resolved: REP-01 (regressed). REP-02 resolved.

## Environment

| item | value | note |
|---|---|---|
| Python | 3.12.10 (Microsoft Store) | |
| numpy | 2.4.4 | req >=1.24, ok |
| pandas | 3.0.1 | req >=2.0, ok |
| scipy | 1.17.1 | ok |
| scikit-learn | 1.8.0 | req >=1.3, ok. The last audit saw 1.9.0 on the same machine; the cv outputs are identical, so the pinned Phase-2 numbers do not depend on 1.8 vs 1.9 here. |
| matplotlib | 3.10.8 | ok |
| pytest | 9.1.1 | installed |
| git EOL | index LF, checkout CRLF (`core.autocrlf=true`) | Byte comparisons below were made on working-tree files. |

## Data present

| directory | files | state |
|---|---|---|
| `data/raw_npz` (v3) | 96 | local, not pinned (no `P` flag) |
| `data/processed_npz`, `processed_npz_v2`, `obs_npz` | 96 each | local (no `O` flag), tests read them without download (15 s run) |
| `data/raw_npz_2026-09-28`, `raw_npz_midcheck`, `raw_npz_pre-rerun` | 96 each | local backups, not read by the pipeline |
| `data/free_field_data.csv` | 1 | local, tracked |
| `data/vtk` | 1 entry, `data/viper1d` 0 | not needed |

## Tests

- Fast: `python -m pytest -q -m "not slow" -rs`: **162 passed, 0 failed, 0 skipped**, 6 deselected (slow), 14 s.
- Full: `python -m pytest -q -rs`: **168 passed, 0 failed, 0 skipped**, 243 s (the 6 slow tests: 70 s, 43 s, 42 s, 38 s, 30 s, 1.6 s).
- The anchor tests (`test_npz_anchors.py`, `test_street_anchors.py`) ran and did not skip. `test_reference_fill_carries_the_cut` is among the 162.
- 6 RuntimeWarnings were seen last time; not re-counted.

## Pinned artefacts

| file | tracked | last commit | guard test ran? |
|---|---|---|---|
| RadiusP anchors 62.3288... / 38.1513... (inline) | test tracked | `1f72a79` (2026-10-19) | yes, `test_npz_anchors.py` passed |
| `outputs/check_results/street_anchors.csv` | yes | `1f72a79` | yes, `test_anchors_match_pinned` (slow) passed |
| `outputs/check_results/master_curve_g.csv` | yes | `1f72a79` | yes, `test_constants_match_pinned` (slow) passed |
| `outputs/check_results/e_profile_validation.csv` | yes | `1f72a79` | yes, `test_validation_matches_pinned` (slow) passed |
| `outputs/check_results/street_parity_report.md` | yes | `1ca6101` (2026-10-07) | no guard test; produced by `tools/street/street_parity.py`, not run |
| `outputs/check_results/soft_beta_selection_note.md` | yes | `77ccb8e` (2026-09-29) | none (a note; its beta=3 figures predate D37, D44, D45) |
| `final_production_z_urban_coefficients_*.csv` | yes | reqdir91 at `eec48dc` | `test_z_urban_domain.py` (bounds) passed on WT tables |

The street suite reads `peak`/`impulse` fields and the filled urban fields, not `refP_fill`; the slow street tests pass with the D37 code, so D37 did not move them.

## Smoke pipeline

Full Phase 1 (96 configs, `--no-figures`, `--radius-method reqdir91_soft3 --npz-dir` default `raw_npz`) into scratch, WT code, 340 s. Compared with the WT working files (identical to `eec48dc` blobs):

| table | rows | max abs diff | max rel diff | verdict |
|---|---|---|---|---|
| `convergence_table_reqdir91_soft3.csv` | 96 | 0 | 0 | byte-identical |
| `max_radius_per_Z_reqdir91_soft3.csv` | 1920 | 0 | 0 | byte-identical |
| `theta_radius_P_reqdir91_soft3.csv` | 91 | 0 | 0 | identical |
| `theta_radius_I_reqdir91_soft3.csv` | 91 | 0 | 0 | identical |

Phase 2 into scratch, same Phase-1 tables, `--n-iter 20` (4 s):

| table | max abs | max rel | verdict |
|---|---|---|---|
| `final_production_z_urban_coefficients_reqdir91_soft3.csv` | 0 | 0 | byte-identical to the tracked file |
| `final_production_convergence_coefficients_reqdir91_soft3.csv` | 0 | 0 | identical |
| `cv_summary_reqdir91_soft3.csv` (rows 0-19 of the tracked 1000-row file) | 0 | 0 | identical, all columns |
| `best_z_urban_coefficients_*`, `best_convergence_coefficients_*`, `best_test_configs_*` | differ | | expected: the "best split" is picked from the n_iter pool; not comparable at 20 vs 500 |

Not reproduced: `cv_summary` rows 20-499 and the `best_*` files (need n_iter=500, the production run).

Other products regenerated from the committed tables and WT code, into scratch:
- `logo_cv.py` (zurban conditional, zurban deployable, conv): all 6 files `logo_cv_reqdir91_soft3_relwls_quad*.csv` and `logo_summary_*.csv` are identical (max abs 0), 4 s. They are untracked (see REP-14).
- `check_formulas.py`: `validation_comparison_reqdir91_soft3.csv` identical (40 rows, max abs 0); this file depends on the convergence path and on `best_test_configs`, not on MaxR, so D37 does not touch it.

## Determinism

Phase 2 (`--n-iter 20`) run twice on the same Phase-1 tables: all 10 output CSVs byte-identical. Phase 1 was run once with WT code and reproduces the tracked tables byte for byte (an independent earlier run), which also shows run-to-run determinism for Phase 1. No difference between identical runs.

## D37 effect on the other estimator tokens (question 3)

HEAD-code = `1b9dac7` `grids.py` + `constants.py`. Full Phase 1 for each.

| token (tracked tables) | HEAD-code vs tracked | WT-code (D37) vs tracked | MaxR_P rows moved by D37 | MaxR_I rows moved by D37 | convergence / theta tables |
|---|---|---|---|---|---|
| `reqdir91_soft3` | exact | **differs from `1b9dac7`'s tables**, exact vs `eec48dc` | 1916 / 1920, max rel 0.136 | 1752 / 1920, max rel 0.208 | unchanged (0) |
| `reqdir_soft3` | exact | **no longer reproduces**: max abs 2.96, max rel 0.147 (P 0.057, I 0.137 between code states) | 1915 | 1752 | unchanged (0) |
| `req_soft3` | exact | **no longer reproduces**: max abs 2.25, max rel 0.21; 2 `beyond_P` flips | 1877 | 1711 | unchanged (0) |
| `req` | not reproducible even at HEAD-code (convergence table differs: max abs 266) | not reproducible | - | - | differ for pre-existing reasons |
| `p95` | same | same | - | - | differ for pre-existing reasons |
| `req_soft4`, `req_soft2`, `req_soft6/8/12` | not run | not run; same code path as `req_soft3`, so expected to move too | | | |

Phase 2 on WT-code Phase-1 tables vs the tracked tables (`--n-iter 20`; `final_production_*` do not depend on n_iter):
- `req_soft3`: `final_production_z_urban_coefficients` max abs 0.235, max rel 0.153.
- `reqdir_soft3`: max abs 0.067 (one near-zero coefficient shows rel 11).
- `final_production_convergence_coefficients_*`: 0 for both. R_conv and its coefficients are not affected by D37.

So after D37 is committed, the max_radius and Z_urban tables of `req_soft3` and `reqdir_soft3` (and `req_soft2/4/6/8/12`, untested) can no longer be regenerated from the code at the same commit. The convergence tables of all tokens are unaffected.

## Results-of-record inventory

Reproducible here = regenerated from WT code on `data/raw_npz`.

| result | reproducible at WT code | what is needed |
|---|---|---|
| `convergence_table`, `theta_radius_*`, `final_production_convergence_coefficients` for reqdir91_soft3, reqdir_soft3, req_soft3 | yes (exact) | |
| `max_radius_per_Z_reqdir91_soft3.csv` | yes, byte-identical (needs the uncommitted `grids.py`) | commit `grids.py` |
| `final_production_z_urban_coefficients_reqdir91_soft3.csv` | yes, byte-identical (n_iter independent) | |
| `cv_summary_reqdir91_soft3.csv` | rows 0-19 identical; rows 20-499 not tested | production run (~100 s Phase 2, owner's call) |
| `best_*_reqdir91_soft3.csv`, `best_test_configs_*` | not tested | n_iter=500 |
| `logo_*_reqdir91_soft3_*` (6 files) | yes, identical | untracked |
| `validation_comparison_reqdir91_soft3.csv` | yes, identical | |
| `max_radius_per_Z_*`, `cv_summary_*`, `best_z_urban_*`, `final_production_z_urban_*` for `req_soft3`, `reqdir_soft3` | **no** (HEAD-code yes) | pre-D37 `grids.py`, or re-run and re-record |
| same files for `req_soft4/soft2/soft6/8/12` | not tested, expected no | same |
| `req`, `p95` tables | no, with either code | out of the current scope |
| `logo_*_req_soft3_*`, `logo_*_req_soft4_*`, `safe_domain_req_soft3.csv`, `config_summary_req_soft3.xlsx`, `config_summary_reqdir_soft3.xlsx`, `pressure_report_req_soft3.xlsx` | not tested; they read the max_radius table of their token, so they follow the row above | |
| street anchors, master curve, e-profile validation | yes (slow tests pass) | |
| `soft_beta_selection_note.md`, `street_parity_report.md` | not regenerated | |
| `blast_calculator.html`, `tools/z_surface_3d` COEF | calculator no; z_surface_3d yes | REP-06 |

Results of record that cannot be tied to the current commit (tree dirty at code level): the 4 tables of `eec48dc` depend on the uncommitted `grids.py` (4); the `req_soft3` and `reqdir_soft3` max_radius, cv_summary, best_z_urban, final_production_z_urban tables (8) stop regenerating once `grids.py` is committed or even today in the WT; the 6 untracked LOGO files and the untracked `validation_comparison_reqdir_soft3.csv` have no commit. Count: 4 (`eec48dc` tables, tied to the uncommitted `grids.py`) + 8 (4 per token for `req_soft3` and `reqdir_soft3`: max_radius, cv_summary, best_z_urban, final_production_z_urban) = 12 tracked tables that cannot be tied to the current code, plus the same-named tables of the untested soft tokens and 7 untracked check_results files.

## Findings

### REP-01 [high] The `eec48dc` tables are not reproducible from the committed code
- Carry: continues REP-01 (regressed). Not a challenge to D1; D1(b) says code and tables go in together.
- Evidence: `git diff HEAD --stat -- blastlib` shows `blastlib/processing/grids.py` (+10/-4) and `constants.py` uncommitted. `eec48dc` contains the 4 tables only. A scratch run of `1b9dac7`'s `grids.py` reproduces the old max_radius table (diff 0) and does not reproduce the one of `eec48dc` (max abs 2.26, max rel 0.27, `beyond_P` flips). The test `test_reference_fill_carries_the_cut` is also uncommitted.
- Consequence: at the commit that holds the new record, a clean checkout regenerates the previous record. CLAUDE.md §3 and §4.4 fail for those 4 files.
- Options: commit `grids.py`, `test_grids_merge.py`, `DECISIONS.md` (D37), and `constants.py` (the default `reqdir91_soft3` is also uncommitted, so HEAD's default is still `reqdir_soft3`; a plain `run_analysis.py` writes the wrong token) together, right after `eec48dc`. Or leave as is until that commit and do not tag `eec48dc` as the record.

### REP-13 [high] D37 breaks the reproducibility of the `req_soft3` and `reqdir_soft3` tables, and the owner's docs say they remain reproducible
- Carry: new.
- Evidence: table in "D37 effect" above. HEAD-code regenerates both tokens exactly (max_radius, convergence, theta); WT code moves 1877/1915 of 1920 MaxR_P rows (up to 13%/6%) and 1711/1752 MaxR_I rows (up to 21%/14%). Phase 2 then moves the Z_urban production coefficients by up to 0.235 (`req_soft3`). `blastlib/constants.py` (comment above `RADIUS_ESTIMATOR`) says "'reqdir_soft3' remains reproducible as the record of 2026-10-20" and "'req_soft3' remains the reproducible earlier record".
- Consequence: the comments are false after D37, and the tracked tables of those tokens (and the calculator, which holds `req_soft3` values) are history not tied to the code. Any figure or LOGO file made from them (`logo_*_req_soft3_*`, `safe_domain_req_soft3.csv`, `config_summary_*`) cannot be regenerated.
- Options: (a) state in `constants.py` and the README that earlier tokens are frozen records and their MaxR tables regenerate only with the code of the commit that made them, and record in D37 the old and new values for them; (b) add a switch (e.g. an estimator-token flag `fillcut`) so earlier tokens keep the old behaviour; (c) accept and delete the stale tokens from the tracked set. The choice is the owner's. Not tested: the soft2, soft4, soft6, soft8, soft12 tables.

### REP-14 [medium] Results of record without a commit
- Carry: new.
- Evidence: untracked: `outputs/check_results/logo_cv_reqdir91_soft3_relwls_quad*.csv`, `logo_summary_reqdir91_soft3_relwls_quad*.csv` (6 files) and `validation_comparison_reqdir_soft3.csv`. D37 quotes the LOGO MAPE (P 8.773, I 6.749) from these; I regenerated them identically (max abs 0), so they are reproducible from WT code, but they are not in git. `tools/logo_cv/logo_cv.py` (+390/-29) that produces them is modified and uncommitted.
- Consequence: the numbers cited in D37 have no commit to point to.
- Options: commit with the same commit as REP-01.

### REP-15 [low] The D37 text says a base run "returned the record with difference 0", but the base is `1b9dac7`, now superseded
- Carry: new.
- Evidence: D37 "מדידה מחדש לפני היישום". After `eec48dc` the record in git is the post-D37 one; the old values exist only in `1b9dac7`.
- Consequence: none for numbers; a reader looking for "old" values must go to `1b9dac7`.
- Options: cite the hash in D37.

### REP-04, REP-05, REP-06, REP-07, REP-08, REP-09, REP-10, REP-11, REP-12
Open or partially, as in the carry-over table, with today's evidence there. Severities unchanged (REP-04 and REP-05 medium, REP-06 medium, the rest low or info). Not repeated here. REP-09 is the only one with new evidence: a second measurement (cv_summary n_iter=20 equals rows 0-19 of the n_iter=500 file, diff 0), at sklearn 1.8.0 instead of 1.9.0, so the behaviour holds on two library versions.

## Not checked
- The production run (`--phase all --n-iter 500`): not run, per CLAUDE.md. `cv_summary` rows 20-499, `best_*` files and `best_test_configs` were not reproduced.
- Phase 1 for `req_soft2`, `req_soft4`, `req_soft6/8/12`; Phase 2 on `req` and `p95`.
- HEAD's own suite on the committed tree (`eec48dc` alone, without the uncommitted GUI and test files): I ran the WT tree, not a checkout.
- The `tools/` CLIs that write only into `outputs/` (street parity, config_summary, safe_domain, pressure_report).
- The numbers quoted in D37 for CV and LOGO beyond what the committed tables and regenerated LOGO files contain; I checked that `eec48dc` tables equal a fresh run, not the percentage changes in the decision text.
- Figures (not of record).
