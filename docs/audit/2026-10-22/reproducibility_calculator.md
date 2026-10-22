# Audit: reproducibility, pre-commit check of the calculator change (2026-10-22, commit 65212ff, tree dirty)

Scope: the uncommitted change to `blast_calculator.html` (D52, D6 note, D53), the README wording, `docs/DECISIONS.md`, and the new `tests/test_blast_calculator.py`. Read-only: nothing was written except this file. Scripts and scratch output lived in the session scratchpad (outside the repo) and were deleted at the end. `git status --porcelain` was identical before and after every run.

Dirty tree at start (4 entries): ` M README.md`, ` M blast_calculator.html`, ` M docs/DECISIONS.md`, `?? tests/test_blast_calculator.py`.

## Verdict: PASS on all five checks. Nothing blocks the commit; two small items are worth fixing in wording (see Findings).

| # | check | result |
|---|---|---|
| 1 | fast tests green, skips explained | PASS: 186 passed, 0 failed, 0 skipped, 6 deselected (slow), 32 s. node v22.22.1 is present and `tests/test_blast_calculator.py` ran (6 of 6 passed) |
| 2 | no production code or result of record changed | PASS: `git diff HEAD --stat` touches only README.md, blast_calculator.html, docs/DECISIONS.md. Nothing under blastlib/, tools/, run_analysis.py, outputs/ |
| 3 | embedded CONV_P, CONV_I, ZU equal the production CSVs exactly | PASS: 40 of 40 values equal, 34 of 34 long literals appear verbatim in the CSV text |
| 4 | no user-facing text claims the domain is safe | PASS: 'התחום הבטוח' and the check mark are absent from the page |
| 5 | D53 and D6 numbers reproduce | PASS for every D6 number and every D53 mechanism number; one small imprecision in D53 (the lower end of "10%-24%", see repro-1) |

## Carry-over
No `prev_audit` was given; not applicable.

## Environment
Python 3.12.10 (Windows 11), node v22.22.1. numpy 2.4.4, pandas 3.0.1, scipy 1.17.1, scikit-learn 1.8.0, matplotlib 3.10.8, pytest 9.1.1. All satisfy requirements.txt (numpy>=1.24, pandas>=2.0, matplotlib>=3.7, scipy>=1.10, scikit-learn>=1.3). `PYTHONIOENCODING=utf-8` was set. h5py (in requirements.txt) was not checked: not used by this change.

## Data present
- data/raw_npz: 96 files, none zero-size, no cloud-recall attribute on any of them (checked with `os.stat().st_file_attributes`). Present.
- data/free_field_data.csv: present (30 rows, Z = 1..30, P_50..P_1500 and I_50..I_1500), tracked in git, last commit 219c13e (2026-10-20), unmodified in the working tree.
- outputs/tables/final_production_convergence_coefficients_reqdir91_soft3.csv: tracked, last commit 1b9dac7 (2026-10-21). final_production_z_urban_coefficients_reqdir91_soft3.csv: tracked, last commit eec48dc (2026-10-22). outputs/check_results/logo_cv_reqdir91_soft3_relwls_quad.csv: tracked, last commit fe67aad (2026-10-22). convergence_table_reqdir91_soft3.csv: tracked, last commit 1b9dac7. None has a working-tree change.

## Tests
`python -m pytest -q -m "not slow" -rs -p no:cacheprovider`: 186 passed, 0 failed, 0 skipped, 6 deselected, 32.0 s (exit 0). No skip lines at all, so nothing was skipped for missing data or missing node.
- `tests/test_blast_calculator.py` (untracked): 6 passed. It runs the page's own `<script>` in node against a stub DOM and compares to the Python chain. Its skip condition is `shutil.which('node') is None`; node is installed here, so it ran. On a machine without node it skips silently (see repro-2).
- `tests/test_npz_anchors.py`: 6 passed, none skipped (the anchor tests did not skip for lack of data). `tests/test_street_anchors.py`: 6 fast tests passed.
- The 6 deselected tests are the slow ones: test_street_anchors::test_anchor_stability_median_all_configs, test_street_anchors::test_anchors_match_pinned, test_street_master_curve::test_constants_match_pinned, test_street_validation::test_validation_matches_pinned, test_street_validation::test_envelope_true_stats, test_z_bands::test_real_config_is_read_only. They were not run. The diff touches no street code and no table, so it cannot move them.
- The new test file must be added with `git add` in the commit. The page header comment says "tests/test_blast_calculator.py fails if they drift", and D52 cites it as evidence, so a commit without it leaves a dangling reference.

## Pinned artefacts
The change touches none of them: no file under outputs/ or blastlib/ is modified, and `git status` is unchanged after the test run, so no test rewrote a tracked table. The artefacts that the new test compares against, all read-only:

| file | tracked | last commit | guard test ran? |
|---|---|---|---|
| outputs/tables/final_production_convergence_coefficients_reqdir91_soft3.csv | yes | 1b9dac7 (2026-10-21) | yes, test_coefficients_and_domain_constants_are_production (exact equality) |
| outputs/tables/final_production_z_urban_coefficients_reqdir91_soft3.csv | yes | eec48dc (2026-10-22) | same |
| outputs/tables/convergence_table_reqdir91_soft3.csv | yes | 1b9dac7 (2026-10-21) | yes, the 96 configs and the ENV hull come from it |

## Smoke pipeline
Not run, and not needed: the change touches no pipeline code and the caller excluded Phase 2 and LOGO. The relevant "pipeline" here is the page's JS against the Python chain, and it was exercised by the test file (96 configs x Z_free grid 1.5..20 plus both sides of each boundary, rel 1e-12; 801-point monotonicity grid; both tabs; boundary identity; D51 jump).

## Determinism
The calculator test file ran twice (once inside the full fast suite, once alone with the anchor tests) and passed both times. It has no random component. Not otherwise applicable.

## Check 3 in detail: embedded coefficients against the CSVs
Independent of the test: a script extracted the `CONV_P`, `CONV_I` and `ZU` object literals from the page, parsed them as JSON, and compared them to the two CSVs read with `pd.read_csv(..., float_precision='round_trip')`.
- 40 comparisons (CONV_P 10, CONV_I 10, ZU 16, plus `ZF_MIN = 2.0` against `Zf_min` in all 4 rows of the Z_urban CSV): 40 equal, 0 different. Python float `==`, so bit-exact.
- Key sets are complete and identical per det: CONV_P {C0,C1,C2,C3,a}, CONV_I {A,p,q,r,r2}, ZU.P {C0,C1,A,B}, ZU.I {C0,C1,C2,C3}.
- Every numeric literal with 6 or more decimals in the three blocks (34 of them) appears verbatim in the CSV text, so no digit was retyped or rounded.
- The page's `ENV` hull equals the hull of convergence_table_reqdir91_soft3.csv (b 10-30, s 5-20, H 4-24, W 50-1500; rho 0.1837-0.7347 against the page's 0.1836-0.7348, pi2 0.4368-5.4288 against 0.4367-5.4289, H/s 0.2000-4.8000 against 0.1999-4.8001, the stated "hair of tolerance").
- The Tab-2 free-field table (`FF_P`, `FF_I`, Z = 1..20) equals the median over the five weights of data/free_field_data.csv (pressure) and of I_W / W^(1/3) (scaled impulse), within the 2-decimal rounding of the literals (max abs diff 0.0048 kPa and 0.0050 Pa.s/kg^(1/3)).

## Check 4 in detail: safety wording
- `grep -n "התחום הבטוח\|✓\|✔" blast_calculator.html`: no match. The diff shows the two removed lines (`✓ בתוך התחום הבטוח` banner and `ראו התחום הבטוח ב-docs/ALGORITHM.md`).
- Every other occurrence of "בטוח" / "safe" in the page: code comments and identifiers (`SAFE`, `tier === 'safe'`, an internal tier name), one string that denies the claim (`זהו <b>אינו</b> תחום בטוח ואין בו ערובה לדיוק`, line 345), and the edge banner's pointer to the section title "The safe domain" in ALGORITHM.md, with the note that its numbers are from an earlier record (line 355). None claims safety.
- `test_no_safety_claim_on_the_core_box_d6` passes (38 core-tier banners checked).
- Not a safety claim, but user-visible: the core box still shows a "typical band" of +-15% (`bandPct`), labelled "לא כוילה מחדש - D6". The page text itself reports P p90 16.9% and max 23.5% in the same box, so the +-15% label is a pre-existing, disclosed, owner-deferred item (D6 entry says it was not changed). Not a blocker.

## Check 5 in detail: D6 and D53 numbers
Recomputed from outputs/check_results/logo_cv_reqdir91_soft3_relwls_quad.csv (192 rows, Target P and I, 96 configs each) joined to convergence_table_reqdir91_soft3.csv for the geometry; box rho 0.308-0.563, pi2 = s / W^(1/3) 0.499-5.44, H/s <= 3.

D6 (SAFE box) - every number reproduces:

| quantity | recomputed | text (DECISIONS.md D6 / page) |
|---|---|---|
| configs in the box | 38 of 96 | 38 |
| below 20% on both targets | 34 of 38 | 34 of 38 |
| the 4 above 20% | config_64 (I 20.49), config_67 (P 22.92), config_70 (I 28.36, P 23.48), config_83 (P 22.27) | "4" |
| P in box: mean / max / p90 / within +-15% | 8.43 / 23.48 / 16.89 / 81.6% | 8.4 / 23.5 / 16.9 / 82% |
| I in box: mean / max / within +-15% | 6.07 / 28.36 / 94.7% | 6.1 / 28.4 / 95% |
| outside the box, inside the envelope: max P / max I | 38.29 / 31.45 | 38.3 / 31.4 |
| page edge-banner corner maxima | rho>0.563: P 38.3, I 24.9; rho<0.308: I 31.4; pi2<0.499: I 20.0; H/s>3: 24.3 (P), 24.9 (I) | ~38 / ~25; ~31; ~20; ~25 |

D53 (free-field pressure spread between weights), from data/free_field_data.csv:
- Scaled impulse I/W^(1/3): spread (max/min - 1) at most 1.69% (Z = 2). Text: "1.7% at most". Reproduces.
- P spread over Z = 1..20 (the page's table range): 9.7% (Z = 16) to 23.7% (Z = 1). Text: 10%-24%. Reproduces for the range the page shows. Over the full table Z = 1..30 the minimum is 5.8% (Z = 27), 6.6% (Z = 28), 8.7% (Z = 29); see repro-1.
- Low-Z resolution trend: P_W / median over W is 0.861 at Z = 1 for W = 50 and 0.921-0.930 at Z = 3-8 (text 0.861 and 0.92-0.93); W = 50 is below the median by 7.0%-13.9% (text 7%-14%); W = 1500 is above it by 2.6%-6.5% (text 3%-6%).
- Slope drops (d ln P / d ln Z, steepest interval per weight), R at the upper end of the interval, with Z on the table's integer grid: W = 50: 99.5 m (Z = 27, slope -5.02); W = 250: 100.8 m (Z = 16, -2.61 then -2.26); W = 500: 103.2 m (Z = 13, -3.30); W = 1000: 100.0 m (Z = 10, -2.70); W = 1500: 103.0 m (Z = 9, -2.27). Second drop near 250 m: W = 1000 at 250.0 m (Z = 25, -3.67); W = 1500 at 251.8 m (Z = 22, -2.09). W = 250 and W = 500 cannot reach 250 m within Z <= 30. All ten R values match the text exactly.

## Results-of-record inventory
Narrow scope: this change alters none of them.

| result of record | reproducible at this commit | note |
|---|---|---|
| final_production_*_reqdir91_soft3.csv | not tested (no Phase 2 run, by instruction); unchanged by this diff | the calculator now embeds them exactly, guarded by an exact-equality test |
| convergence_table / max_radius_per_Z / cv_summary / best_* | not tested; unchanged by this diff | |
| outputs/check_results/* | not tested; unchanged by this diff | |
| pinned street and NPZ artefacts | NPZ anchors yes (6 passed); street slow guards not run | |

Results of record that cannot be tied to the current commit because of this change: 0. The dirty files are the page, two docs, and one new test; none is a result of record.

## Findings

### repro-1 [low] D53 states "10%-24% at every Z" but the table's minimum is 5.8%
- Carry: new
- Where: docs/DECISIONS.md D53 ("10%-24% (max/min - 1)"); the page comment at blast_calculator.html:518-520 repeats it ("by 10-24% at every Z").
- Evidence: over Z = 1..20, the spread is 9.7%-23.7%, which rounds to 10%-24%. Over the whole data/free_field_data.csv (Z = 1..30) it is 5.8% (Z = 27), 6.6% (Z = 28), 8.7% (Z = 29), 10.9% (Z = 30). The low values sit at Z = 27-29, where the W = 50 curve has its grid-transition drop (R = 99.5 m), so the spread there is partly offset by that drop.
- Consequence: none for the page, which shows Z <= 20 only. The D53 statement is exact for Z <= 26 (minimum 9.7%) and for the page range; it is imprecise for the CSV as a whole.
- Option: write "9.7%-23.7% for Z <= 20 (5.8%-23.7% over Z = 1..30)". Wording only; the owner decides.

### repro-2 [low] The drift guard skips silently when node is missing
- Carry: new
- Where: tests/test_blast_calculator.py, `pytestmark = pytest.mark.skipif(NODE is None, ...)`.
- Evidence: node v22.22.1 is installed here, so the six tests ran. CLAUDE.md section 5 requires anchor tests not to be skipped before a number is trusted; this file is now the only guard that the page's embedded coefficients equal the CSVs, and `-rs` reports the skip but a green run still looks green.
- Consequence: on a machine or cloud session without node, a coefficient drift between the page and the CSVs would pass unnoticed. The check in this report (a 40-value comparison without node) shows it is easy to do in pure Python, if the owner wants a node-free fallback.
- Option: none required for the commit; a node-free exact-equality test of the three literal blocks against the CSVs would close the gap. The owner decides.

### Non-blocking observations
- Line endings: git prints "LF will be replaced by CRLF" for README.md and docs/DECISIONS.md (`core.autocrlf=true`). The diff is clean (only the intended hunks), so this is cosmetic.
- The test file hard-codes the D51 record (10 of 96 configs with Lambda_P < 1 at R_conv, 8 shown, 17 with no pressure Z_urban domain, max 1.063) and "34 of 38". That is intended: it will fail on the next Phase-2 re-run until the owner updates it, the same as the embedded coefficients.

## Not checked
- Phase 2, LOGO and the production pipeline were not run (caller's instruction), so the production tables were not regenerated; their agreement with the code at this commit was not re-tested here.
- D52's "change versus the previous calculator" figures (Z_conv,I median +21.5%, range -11.1% to +54.4%, and the other three lines) were not recomputed; they need the previous page's coefficients from `git show HEAD:blast_calculator.html`.
- D52 (ב): the claim that the 17 no-domain configs are all W = 50 with b+s between 35 and 50 m was not recomputed; the count 17 is asserted by the test and it passed.
- The slow tests (6) were not run.
- The page was not opened in a browser; only its script was executed in node against a stub DOM. Layout, CSS and the Hebrew right-to-left rendering are untested.
- The "The safe domain" section of docs/ALGORITHM.md and ALGORITHM_HE.md still quotes older numbers; D6 already records this as not checked.
