# Audit 2026-09-30: grid merge in `blastlib/processing/grids.py`

Read-only. Commit `77ccb8e`, dirty tree (agents/skills staged, WORKLOG and
`validation_comparison_req_soft3.csv` modified, untracked scratch). Data:
`data/raw_npz` (v3, 96 files). Scripts: `scripts/merge_audit.py`,
`scripts/merge_sens.py`; output in the session scratchpad only.

Owner's premise (taken as given, not verified here): peaks are not carried
across remaps. Inside a finer box the coarser grid holds only the post-remap
residual, except where the finer stage ended before the wave arrived
(raw == 0), where the coarser value is the true value. Building cells = 0.001 kPa.

Replication check: as-is `process_grids` + `find_convergence_radius`
(`req_soft3`) reproduces `convergence_table_req_soft3.csv` exactly for
27, 60, 62, 67, 72, 02, 50, 93 (RadiusP, RadiusI, PressureAtR).

## (a) Does the mask also mask empty cells? Yes.

`mask_g = peakP_g_raw <= thresholdP_kPa` with `thresholdP_kPa = 1.01e-3`
(`grids.py:117-119`, `constants.py:22`). It masks sentinel (0.001), zero,
and 0 < P < 0.001 alike. Measured: fine empty cells masked/total: 62:
33,676/33,676; 67: 20,559/20,559. Because the cut (`cut_mask2`, `cut_mask3`)
is keyed on "finer cell masked", **every masked finer cell hands its place
back to the coarser grid**, whatever the reason for the mask (building,
not-yet-arrived, partial arrival).

## Per-grid counts of raw urban peakP (kPa)

| cfg | grid | ==0.001 | ==0 | 0<P<0.001 | >0.001 | t_urban | t_ref |
|---|---|---|---|---|---|---|---|
| 27 | 1 | 331,128 | 0 | 0 | 113,761 | 0.499 | 0.319 |
| 27 | 2 | 182,750 | 80 | 52 | 67,118 | 0.960 | 0.912 |
| 27 | 3 | 170,100 | 0 | 0 | 79,900 | 2.384 | 2.450 |
| 60 | 1 | 341,056 | 0 | 0 | 103,833 | 0.499 | 0.319 |
| 60 | 2 | 180,625 | 0 | 0 | 69,375 | 0.979 | 0.912 |
| 60 | 3 | 163,800 | 0 | 0 | 86,200 | 2.429 | 2.450 |
| 62 | 1 | 341,059 | 33,676 | 951 | 69,203 | **0.209** | 0.494 |
| 62 | 2 | 180,625 | 1,076 | 96 | 68,203 | 0.946 | 1.190 |
| 62 | 3 | 163,800 | 0 | 0 | 86,200 | 2.395 | 2.430 |
| 67 | 1 | 160,002 | 20,559 | 621 | 263,707 | 0.332 | 0.437 |
| 67 | 2 | 90,000 | 493 | 221 | 159,286 | 0.980 | 1.190 |
| 67 | 3 | 81,000 | 0 | 0 | 169,000 | 2.476 | 2.096 |
| 02 (clean) | 1 | 250,000 | 0 | 0 | 194,889 | | |
| 02 | 2 | 140,625 | 0 | 0 | 109,375 | | |
| 02 | 3 | 156,800 | 0 | 0 | 93,200 | | |
| 72 (extra) | 1 | 160,001 | 9,930 | 658 | 274,300 | 0.314 | 0.319 |
| 72 | 2 | 90,002 | 159 | 113 | 159,726 | 0.963 | 0.912 |

Reference fields: no 0, no sentinel, no 0<P<0.001 in any grid of these
configs (all cells > 0.001).

## (b) Does the cut re-admit coarser cells? Yes, in two ways.

Classification of every coarser cell that is inside the finer box and stays
valid, by the finer grid's raw value at the nearest finer cell (all 96
configs). "viol" = |ratio − 1| > 0.05 after pinning, i.e. visible to the scan.

| type | medium in fine box: n / viol P / viol I | coarse in medium box: n / viol P / viol I |
|---|---|---|
| wall (finer = 0.001) | 1 / 1 / 1 (62 only) | 41,415 / 21 / 35 (27, 60 only) |
| empty (finer = 0), finer ref > 0 | 5,780 / 2,418 / 3,520 (62; 72 I only) | 9,938 / 0 / 0 |
| partial (0 < finer < 0.001) | 201 / 84 / 84 (62 only) | 1,597 / 0 / 0 |

All other re-admitted cells are pinned to 1 (P_raw < 10 kPa floor or band)
and are invisible to the hard scan.

**MRG-01 (high): 62, medium grid uses its own residual reference where the fine urban stage ended early.**
Urban fine dump t = 0.209 s, reference fine dump t = 0.494 s. Where the
urban fine grid is empty the medium urban value is true (premise), but the
medium *reference* there is residual, because the reference fine stage
did see the wave. 3,056 + 84 + 1 medium cells, r = 80.4–123.2 m;
2,503 P violations, 3,141 I violations. Examples (grid 2):

| X, Z [m] | r | P2_raw | refP2_raw | fine refP1 (nearest) | ratioP | ratioI |
|---|---|---|---|---|---|---|
| 37.25, 76.75 | 85.31 | 17.59 | 0.222 | 12.37 | 79.28 | 21.19 |
| 76.75, 37.25 | 85.31 | 17.59 | 0.222 | 12.37 | 79.28 | 21.19 |
| 37.25, 77.25 | 85.76 | 17.03 | 0.221 | 12.29 | 77.08 | 21.07 |
| partial: 37.25, 75.75 (fine P1 = 4.1e-4) | 84.41 | 18.78 | 0.224 | 12.58 | 83.93 | 21.43 |
| wall: 71.75, 40.75 (fine P1 = 0.001) | 82.51 | 17.81 | 0.227 | 13.07 | 78.32 | 21.25 |

With the fine reference the first example is 17.59/12.37 = 1.42, not 79.

Effect on the record (diagnostic, not a proposal): RadiusP 108.06 m as
recorded; 99.58 m (−7.8%) with these cells removed; 104.11 m (−3.7%) with
their P ratio taken against the nearest fine reference. RadiusI unchanged
(138.76 → 138.82; the defect region lies inside R_I). PressureAtR 3.78 →
14.42 kPa (removed). This is the D32/A4 mechanism, now traced to the merge:
the defect is the mismatched reference, not the urban value.

**MRG-02 (medium): 27 and 60, coarse cells re-admitted at walls carry residual urban over residual reference.**
The nearest medium cell is a building sentinel, so `mask2_interp == 1` and
the coarse cell survives the cut. Its urban value (≈10–13 kPa) sits just
above the 10 kPa floor, so it is not pinned; its reference is residual
(≈0.1–0.25 kPa). Examples (grid 3):

| cfg | X, Z [m] | r | P3_raw | refP3_raw | medium refP2 (nearest) | ratioP | ratioI |
|---|---|---|---|---|---|---|---|
| 60 | 102.5, 102.5 | 144.96 | 12.88 | 0.102 | 9.22 | 125.70 | 67.68 |
| 60 | 102.5, 101.5 | 144.25 | 12.87 | 0.103 | 9.28 | 124.99 | 66.83 |
| 60 | 101.5, 102.5 | 144.25 | 12.87 | 0.103 | 9.28 | 124.96 | 66.82 |
| 27 | 139.5, 32.5 | 143.24 | 10.16 | 0.105 | 8.68 | 96.70 | 26.07 |
| 27 | 138.5, 32.5 | 142.26 | 10.12 | 0.109 | 8.77 | 93.08 | 28.20 |
| 27 | 0.5, 102.5 | 102.50 | 12.84 | 0.251 | 15.07 | 51.17 | 12.99 |

Counts: 27: 860 re-admitted, 12 P / 26 I violations; 60: 1,680, 9 / 9.
The same kind of cell exists in 41,415 coarse cells over 40+ configs but is
pinned there (P3_raw < 10 kPa). Whether the coarse urban value at a wall
is residual or a different geometry sampling (1 m cells straddling a
building edge) was not established.

Effect: RadiusP 27: 128.62 → 128.84 (+0.17%), 60: 114.73 → 115.02 (+0.24%);
RadiusI < 0.03%. **PressureAtR of 60: 4.20 → 14.71 kPa.** The scalar radius
barely moves; the value reported at the radius does.

**MRG-03 (low): 72, empty-fine cells re-admitted with a true reference. Not a defect.**
882 medium cells (r = 125.9–141.1 m), 464 impulse violations. Urban fine
0.314 s, reference fine 0.319 s, so the medium reference here is
not residual: refI2 281.8 vs nearest fine refI1 270.3 (example at
90.25, 90.25; urban I2 = 598.4, ratioI = 2.12). RadiusP/I unchanged (< 1e-4 m)
when removed. 67: 1,836 + 50 cells, all pinned (P2_raw ≈ 1.2 kPa); the
medium reference there is 2.06 vs fine 2.42 (15% low, partly residual),
harmless only because the floor pins them. No effect on 67's radii.

## (c) Do the criteria use raw rather than filled fields? Partly.

- Raw: the pressure band and floor (`conv_P`, `grids.py:223-231`), the impulse
  criterion (`impulse_converged` on `data['impulse*']`, `data['refI*']`),
  the soft band `absdiff` (`soft_criterion.py:117-124`). Confirmed.
- Filled: the value of every non-pinned ratio is `peakP_filled / refP_filled`
  (`grids.py:135-141`), so the hard ±5 % test in the scan, and the soft gate
  (`ratioP{g}_raw` is the same filled ratio, `grids.py:192-193`), use filled
  fields. `peakP_all`/`peakI_all` (PressureAtR, ImpulseAtR) are filled.
  MaxR uses `peakP{g}_orig` (filled) against `refP{g}_fill` (filled by design,
  PHY-04 option (a)).
- **MRG-04 (low):** measured effect on the violation flag of non-pinned cells:
  P: 0 flips in all configs checked. I (fine grid): 60 flips in 27, 18 in 60,
  8 in 62, 0 in 67. Filled ≠ raw on valid cells: e.g. 67 grid 1 27,556 urban
  and 1,524 reference cells; 62 grid 2 19,551 urban. Also note: the soft
  `ratioP{g}_raw` key is named "raw" but holds a filled ratio (naming, and a
  statement in the module docstring, `grids.py:180-185`, that is not exact).

## Time order (all 96 + references)

Source: `t_urban{g}`, `t_ref{g}` stored in `data/raw_npz` (the VTK TIME field
copied at build). **No run violates grid 1 < 2 < 3**, urban or reference.
The 10 references (det × W; det1 and det2 share the same triple) are:
W50 (0.437, 1.190, 2.096), W250 (0.385, 1.190, 2.476), W500 (0.494, 1.190,
2.430), W1000 (0.383, 1.190, 2.195), W1500 (0.319, 0.912, 2.450).

Related flag (not requested): urban fine dump earlier than reference fine
dump by more than 1 %: 05, 08, 10, 11, 23, 32, 34, 38, 62 (0.209 vs 0.494),
67 (0.332 vs 0.437), 72. Only 62 produced a visible defect (MRG-01).

**Not checked:** file mtime order. The VTKs are in `compare_v6/all_vtks`,
outside the repo (CLAUDE.md §1.7); `raw_npz` does not store mtimes.

## Not established

- The premise itself (no peak carry-over at remap) was taken from the owner.
- Why coarse urban cells at walls in 27/60 read 10–13 kPa (residual
  reverberation vs cell straddling a wall).
- Effect on MaxR / Z_urban of MRG-01/02 (only R_conv was measured).
