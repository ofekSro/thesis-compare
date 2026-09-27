# MaxR level and Z_urban fit domain: change of record (made 2026-08-03, committed 2026-09-27)

The tables below were regenerated on 2026-08-03 by code that stayed
uncommitted until 2026-09-27. This note records what changed and by how much,
as CLAUDE.md §1.3 requires. Numbers are copied from
`docs/audit/2026-09-27/reproducibility.md` and `choices.md`.

## What changed in the code

1. **Per-direction exceedance level for MaxR** (`run_analysis.py`,
   `blastlib/processing/free_field.py::reference_level_per_theta`). The level
   that MaxR is measured against is now the ring median of the reference
   field in each 1° sector at r_free = Z·W^(1/3). Before, it was the scalar
   from `data/free_field_data.csv`. Sectors with no reference cells fall back
   to the scalar. The rationale is the ~9.6 % anisotropy of the free field on
   the Cartesian mesh.
2. **Two new fit-domain conditions** in `z_urban.z_urban_valid_mask`:
   `R_free < R_conv` and `R_free > exclude_r`.
3. **`B_open` upper bound raised from 8 to 20** in the `range_switch` fit.
   This has no effect on `req_soft3`, where the optimum is 7.14. It matters
   only for `req`, where it is 8.33.
4. `max_radius_per_Z_*` gains the columns `R_free` and `ExcludeR`.

## Production Z_urban coefficients, `req_soft3` (old = commit 5f19029)

| Det | Target | coef | old | new | change |
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

The production convergence coefficients (`RadiusP`, `RadiusI`) are unchanged.

## Other moves

- **Predictions:** on the new domain, det 1 moves by a median of -0.62 % (max
  |4.2 %|) and det 2 by -0.85 % (max |2.4 %|). The large coefficient moves
  reflect weak identification of C1 and B (corr 0.97; audit STA-05), not a
  large change in Z_urban.
- **MaxR_P:** changed in 1915 of 1915 finite rows; median -2.05 %, 5-95 %
  range [-7.75 %, +0.11 %].
- **MaxR_I:** changed in 1911 of 1919 rows; median +0.10 %, 5-95 % range
  [-0.39 %, +3.99 %].
- **Fit-domain rows** (det 1 / det 2): pressure 328/319 -> 280/311, impulse
  384/368 -> 340/360.
- **`cv_summary_req_soft3` medians over 500 splits:** z_P 8.495 -> 8.417, z_I
  9.491 -> 9.404, worst 9.860 -> 9.852. conv_P and conv_I are unchanged.
- **Attribution** (det 1 pressure B_open): old code on old tables 4.012, old
  code on new tables 3.287, new code on old tables 6.787, new code on new
  tables 7.139. The new domain moves it most; the new level moves it less.
- The `req` tables were regenerated in the same run. In addition, they now
  hold relwls/quad convergence fits instead of the legacy output that had
  stayed in them since 78352a6 (audit REP-05).

## Not changed here, still open

- `docs/ALGORITHM.md`, `ALGORITHM_HE.md` and `blast_calculator.html` still
  quote the old Z_urban coefficients (audit ALG-02, REP-06).
- The `req_soft2`, `req_soft4` and `p95` Z_urban tables were made by the old
  code (audit REP-04).
- Audit findings on this change that the owner has not yet decided:
  - PHY-04: the per-direction level reads a deficient fine-grid reference
    near the grid edge, for impulse at W >= 1000.
  - STA-02 / ALG-03: the domain is decided with the measured target.
  - CHO-04: the impulse reference shows no anisotropy.
