# Audit: physics  (2026-09-27, commit 5f19029, dirty working tree)

Scope: units and conversions (Pa/kPa, Pa.s, kg, m), the dimensionless groups
(rho, Pi_2, H/s), Hopkinson-Cranz (HC) scaling of every threshold and of the
measurement itself, the free-field reference (reference simulation fields and
`data/free_field_data.csv`), consistency with Kingery-Bulmash / UFC 3-340-02,
and the dimensional consistency of the 10 kPa band and `thr_I_scaled = 20`
across charge weights. The data path audited is the production one:
`data/raw_npz` (schema v3) -> `raw_store.expand` -> `grids.process_grids` ->
`convergence.find_convergence_radius` / `free_field.find_percentile_radius` ->
`z_urban`, `convergence_models`. The working tree was audited as it stands;
each finding states whether the code involved is committed, modified or
untracked.

Documents read: `CLAUDE.md` (untracked), `docs/ALGORITHM.md` (untracked, no
date, describes the current req_soft3 production), `docs/PHYSICS_ANALYSIS_HE.md`
(untracked; quotes older coefficients, e.g. RadiusP C0 = 7.78 and LOGO max
43.4%, so it predates the soft/relwls production), `docs/THESIS_RESULTS_OUTLINE_HE.md`
§1-4 (untracked), `outputs/check_results/soft_beta_selection_note.md`, the
docstrings of `blastlib/street/strip.py` and `tools/extract_1d_peaks`, and
`blastlib/constants.py` with its rationale comments. `docs/references/INDEX.md`
does not exist, so no standard is registered in the repo.

Method: read-only Python probes kept in the session scratchpad (outside the
repo). They import `blastlib` and load `data/raw_npz/*.npz` (all 96 files are
fully local, with no offline attribute) and `data/free_field_data.csv` (local).
`data/processed_npz`, `processed_npz_v2` and `obs_npz` are OneDrive cloud-only
placeholders. They were not opened, so no download was triggered. The probes
reproduce the committed `convergence_table_req.csv` and
`convergence_table_req_soft3.csv` (RadiusP and RadiusI, all 96 configurations)
and the modified `max_radius_per_Z_req_soft3.csv` (all rows with W >= 250) with a
maximum absolute difference of 0.0. Every "counterfactual" number below
therefore differs from the current code in exactly the one respect stated.

## Summary

Units are handled correctly throughout. Pressure is converted Pa -> kPa once,
impulse stays in Pa.s, the CSV is in the same units, and both headline
thresholds are HC-admissible. Pressure at fixed Z is W-independent, and the 10
kPa free-field contour sits at Z = 11.3-12.1 across W. The scaled impulse
collapses across W to a median CV of 0.29%, and the I/W^(1/3) = 20 contour sits
at Z = 13.6-13.8 for every W.

The serious problems are in the measurement, not in the thresholds.

The most consequential problem (PHY-01) is in committed code. The building mask
is applied after the multi-grid max-fill, so a rim of about 6.5% of the
in-building fine-grid cells re-enters the analysis. Those cells carry the
solver's in-building impulse, about 0.49 Pa.s. Under the pressure-free impulse
criterion they become phantom violations that set the outermost streak in most
sectors, and in the pressure scan they act as phantom converged cells that break
genuine violation streaks. Masking them on the solver's own sentinel changes
RadiusI in all 96 configurations (median -35%) and RadiusP (hard median +11.5%,
soft beta=3 median +5.0%). That reverses the thesis-level claim that impulse
converges about 1.5x further out than pressure, and it removes the pressure
"ignition" from 50 to 500 kg.

Three further high findings share one root: the CFD mesh is fixed in metres,
not in Hopkinson units:
- the soft scanner's cell-count bias is W-dependent (PHY-02);
- the 0.15 -> 0.5 m grid seam at r = 100 m falls inside the measured pressure
  radii only for the large charges (PHY-03);
- the new per-direction MaxR_I level (uncommitted) reads a fine-grid reference
  impulse that is deficient near the fine-grid boundary (PHY-04).

The owner must decide:
- how to treat the building rim;
- whether the W-dependent mesh effects are corrected or declared;
- whether a KB/UFC validation (the CFD free field is 10-13% low in impulse and
  up to 32% low in far-field pressure against the standard curve) goes into the
  thesis before the "10 kPa = structurally negligible" argument is made.

## Findings

### PHY-01  [high]  Building-rim cells survive the mask and drive both convergence radii

- Where: `blastlib/processing/grids.py:77-99` (fill), `:108-124` (mask), `:187-215`
  (criteria). Committed at HEAD, unmodified. Production reaches it through
  `blastlib/io/raw_store.py:169-187`, which is untracked. `constants.PARAMS['thresholdP_kPa']`
  is at `blastlib/constants.py:22`.
- What: the mask that removes building footprints is computed on the filled
  field:

  ```
  peakP1   = np.maximum(peakP1,   peakP2_interp)      # grids.py:84
  ...
  mask1 = peakP1 <= threshold_p                          # grids.py:109
  ```

  The solver writes 0.001 kPa (1 Pa) peak overpressure and about 0.49 Pa.s
  impulse into every in-footprint cell. `thresholdP_kPa = 1.01/1000` kPa is a
  detector for that value. The "mask threshold [kPa]" comment and the outline's
  "removes numerical background" (`THESIS_RESULTS_OUTLINE_HE.md:22`) do not say
  this. Next to a wall, the bilinear interpolation of the medium grid mixes in
  street cells, so the max-filled value exceeds 1.01 Pa and the footprint cell
  is not masked. It then enters the scan with inconsistent operands:
  - Impulse: the criterion uses the raw operands
    (`impulse_converged(data['impulse1'], data['refI1'], ...)`, `grids.py:206`).
    The raw urban value there is 0.49 Pa.s, so |dI|/W^(1/3) >= 20 wherever the
    free-field scaled impulse exceeds 20, i.e. inside Z ~ 13.7. The cell is not
    pinned. Its stored ratio (filled urban / filled reference) is about 0.05-0.46,
    so the scanner counts it as a violation. Since 2026-07-27 (b11863d) the impulse
    rule deliberately has no pressure term, and that term was what used to pin
    these cells.
  - Pressure: raw P = 0.001 kPa < 10 kPa, so the floor pins the ratio to 1 and the
    cell counts as converged inside the building. There it can reset a genuine
    violation streak formed by the street cells in front of the wall. Under the
    soft path the gate (`P_raw >= 10`) sets w = 0, with the same effect.
- Evidence:
  - Rim size. In-footprint fine-grid cells that are valid after the mask:
    16,228 of 250,000 (6.5%) in configs 01/02/03 (b15 s5), and 10,853 (3.3%) in
    config 20 (b30 s5). Of these, unpinned impulse violations number 3,372
    (config 01, W=50), 13,479 (02, W=500), 9,389 (20, W=500) and 16,090
    (03, W=1500). Pressure violations among them: 0.
  - Streak composition, config 02 (W=500, b15 s5 h4). The outermost 3-cell
    violation streak that sets the sector radius lies at 96.7 / 107.4 / 106.9 /
    84.1 m for theta = 10/30/60/80 deg. Every cell in it is an in-building cell:
    raw I = 0.49 Pa.s, I_ref = 161-205 Pa.s, ratio 0.05-0.46. With those cells
    masked, the outermost genuine streaks lie at 15.0 / 45.4 / 49.1 / 22.8 m,
    with ratios 1.58-2.30 and |dI|/W^(1/3) of about 27.
  - Counterfactual: mask every cell whose raw solver peak overpressure is <=
    `thresholdP_kPa`, on each grid, before the scan. Nothing else changes.

    | quantity (96 configs) | current | rim masked |
    |---|---|---|
    | RadiusI change | - | median -35.3%, IQR -49.6..-18.0%, range -65.9..+13.7%; 80/96 beyond +/-10% |
    | RadiusI change by W (median) | - | 50: -20.5%, 250: -46.7%, 500: -35.3%, 1000: -44.5%, 1500: -39.6% |
    | median Z_conv,I | 11.61 | 7.58 |
    | configs with Z_conv,I > 13.8 | 17 | 7 |
    | RadiusP hard change | - | median +11.5%, max +91.3%, 76/96 > 5% (W=50 median +35.2%) |
    | RadiusP soft beta=3 (production) | - | median +5.0%, max +66.0%, 48/96 > 5% (W=50 median +19.8%) |
    | median Z_conv,P hard / soft | 7.54 / 8.99 | 8.58 / 9.88 |

  - HC ratios over the core families (b15/b30 at W = 50/500/1500, median over
    the 24 paired geometries):
    - hard RadiusP: Z500/Z50 goes from 1.200 to 0.989;
    - soft RadiusP: Z500/Z50 goes from 1.213 to 1.045;
    - RadiusI: Z500/Z50 goes from 0.986 to 0.760, and Z1500/Z500 from 0.971 to
      0.864.
  - Symptom in the table of record: `ImpulseAtR` is below 20% of the free-field
    impulse at Z_conv,I in 25 of 96 configurations, e.g. 0.60 Pa.s for config 40
    at 60.5 m, W=50.
- Consequence:
  - All RadiusI and RadiusP values in `convergence_table_req*.csv`, and everything
    fitted or selected from them:
    - `final_production_convergence_coefficients_*`;
    - the `beyond_P/I` flags and the `R_free < R_conv` condition of
      `z_urban_valid_mask`, which define the Z_urban fit rows;
    - the Z_conv clip on Z_urban;
    - the LOGO and CV summaries, `safe_domain_req_soft3.csv`, and the ALGORITHM
      coefficient tables.
  - Thesis-level claims that change:
    - "impulse holds 1.5x further, Z 11.6 vs 7.5" (`PHYSICS_ANALYSIS_HE.md:64,71,611`;
      outline §3.4). With the rim masked the order reverses: 7.6 vs 8.6 (hard)
      or 9.9 (soft).
    - "channelling short-range, reverberation through the fabric Z 12-16"
      (`PHYSICS_ANALYSIS_HE.md:89-90`). The through-fabric sectors are the ones
      that cross building walls.
    - "pressure ignition 50->500 kg +20%, impulse clean Hopkinson"
      (`PHYSICS_ANALYSIS_HE.md:257-261,638`).
  - The `thr_I_scaled = 20` calibration is also affected. Its rationale is "100%
    convergence" and "thr ~ 7 only 50-86% converge"
    (`constants.py:44-46`, outline §3.2.2). Phantom rim violations extend to
    wherever I_ff/W^(1/3) exceeds the threshold, so the calibration was plausibly
    shaped by this artefact. That is an inference; it was not tested.
- Options:
  - (a) Build the footprint mask from the raw solver sentinel on each grid, before
    the fill, as in the counterfactual. Then re-run Phase 1 and Phase 2 and
    report old and new values.
  - (b) Keep the fill order, but add a validity gate that pins or drops any cell
    whose raw urban field is the sentinel. This is a data-validity condition, not
    the old pressure gate.
  - (c) Keep the current measurement and state in the thesis that R_conv,I is
    essentially "the outermost building wall inside the I_ff/W^(1/3) = 20
    contour", with the numbers above.

### PHY-02  [high]  The soft pressure scan has a W-dependent bias because the mesh is fixed in metres

- Where: `blastlib/processing/convergence.py:65-117` (committed);
  `constants.RADIUS_ESTIMATOR = 'req_soft3'` (`constants.py:69-72`, committed);
  `docs/ALGORITHM.md:487-512` (untracked).
- What: ALGORITHM states that the soft scanner's radius depends on cell count:
  "the number of independent draws grows with the number of cells". It then
  concludes: "the radii are only comparable across configurations because all 96
  were computed on the same mesh — the bias is largely common-mode here"
  (`ALGORITHM.md:510-512`). The mesh is the same in metres (0.15 / 0.5 / 1.0 m for
  every W, from the `spacing{g}` values in `raw_npz`). It is not the same in
  scaled units, and the model is fitted in Z. The number of cells per unit Z
  along a ray is W^(1/3)/dx:
  - fine grid: 24.6 / 42.0 / 52.9 / 66.7 / 76.3 for W = 50 / 250 / 500 / 1000 / 1500;
  - medium grid: 7.4 / 12.6 / 15.9 / 20.0 / 22.9.
  So the bias is W-dependent by construction. Unlike the thresholds, it is not
  Hopkinson-scaled.
- Evidence:
  - The owner's own coarsening measurement gives soft beta=3 RadiusP -9.1% at 2x
    coarser (`ALGORITHM.md:499-502`), an elasticity of about 0.13 per ln(cells).
    The cells-per-Z ratio between W=500 and W=50 on the fine grid is 2.15, which
    predicts about 10% less soft inflation at W=50.
  - Observed soft/hard RadiusP inflation (`convergence_table_req_soft3` over
    `_req`), median by W: 12.1% (50), 22.4% (250), 20.3% (500), 15.8% (1000),
    17.0% (1500). W=500 minus W=50 is 8.2 pp, the same order as predicted.
  - W=1000/1500 have part of their radius on the 0.5 m grid (see PHY-03), which
    is consistent with their lower inflation.
  - In the core families, soft changes Z1500/Z500 from 1.02 (hard) to 0.958, and
    the share of geometries with Z1500 < Z500 from 46% to 71%.
  - The pattern is confounded with physics. There is no controlled test that
    holds the field fixed and varies only the cells per Z.
- Consequence: production RadiusP (`req_soft3`) and its coefficients. Pi_2 =
  s/W^(1/3) is the only regressor that carries W, so a W-dependent measurement
  bias is absorbed into the C1 and C2 Pi_2 terms. It is then read as street-width
  physics. The beta selection gap rule was tested on one pair only: configs 93
  and 95, both W=250.
- Options:
  - (a) Keep beta=3 and state the W-dependent bias, with these numbers, as a
    limitation of the scaled radii.
  - (b) Make the scan step a fixed scaled length, i.e. cells per unit Z held
    constant. ALGORITHM describes a length-based prototype that restored mesh
    invariance.
  - (c) Run a controlled test: resample one W=500 field to W=50's cells per Z and
    measure the soft radius change, then decide.

### PHY-03  [high]  The 100 m fine/medium grid seam cuts the pressure radii of large charges only

- Where: the grid geometry in `data/raw_npz` (fine grid 0-100 m at 0.15 m,
  medium 0-250 m at 0.5 m); `docs/ALGORITHM.md:43-53` (untracked);
  `blastlib/processing/grids.py:177-181` comment (committed);
  `PHYSICS_ANALYSIS_HE.md` §5 and §5b.
- What: the seam sits at a fixed r = 100 m, i.e. at Z = 100/W^(1/3) = 27.1 /
  15.9 / 12.6 / 10.0 / 8.7 for W = 50 ... 1500. Peak overpressure is
  resolution-sensitive and impulse is not. So the absolute 10 kPa band is applied
  to a field whose fidelity, at fixed Z, depends on W. ALGORITHM describes the
  free-field trend as rising "monotonically at every Z <= 12", and the grids.py
  comment says "a function of scaled distance alone". Neither holds.
- Evidence:
  - Same points recorded on both grids (reference field, 30-60 deg sector).
    Peak P on the medium grid is below the fine grid by:
    - 7.4% (W=1500, r=102 m); 9.8% (W=1500, r=110);
    - 12% (W=500, r=110); 10.8% (W=1000, r=110); 16% (W=50, r=110).
    Impulse at the same points agrees to within 0.6%.
  - The CSV kinks exactly at r of about 100 m. Compared with W=50 over the same Z
    step:
    - W=500, Z 12 -> 13: -20.1% vs -11.0%;
    - W=1000, Z 9 -> 10: -20.7% vs -14.8%;
    - W=1500, Z 8 -> 9: -24.4% vs -16.7%;
    - W=250, Z 15 -> 16: -15.7% vs -8.7%.
  - Monotonicity fails in the CSV at Z = 5, 6, 9, 10, 11, 12. It also fails in the
    per-direction median of the reference field at Z = 10-12, e.g. Z=11:
    10.86 / 11.64 / 11.87 / 10.66 / 10.66 kPa.
  - Share of production RadiusP sector radii that lie beyond the fine-grid box:
    0 / 0 / 2.6 / 7.5 / 28.9% for W = 50 / 250 / 500 / 1000 / 1500 (hard `req`:
    0 / 0 / 1.4 / 3.2 / 14.1%).
  - Size of the effect, estimated from the documented elasticity d log R / d log
    p_thr of about -0.6: roughly -6% on the affected sectors, or about -2% on Req
    at W=1500. This is an estimate, not a measurement.
- Consequence: RadiusP for W >= 1000. The claims "Z not monotone in W 17/36
  (pressure)" and "saturation 1.02 at 1500 kg" (`PHYSICS_ANALYSIS_HE.md:251,257-261,640`)
  are effects of 2-4%, the same order as this bias. The ALGORITHM sentence at
  `:47-49` is false as written. The seam is acknowledged only in
  `blastlib/street/strip.py:32`, as "grid-seam corruption past Z = 100/W^(1/3)",
  and not for R_conv.
- Options:
  - (a) Document the seam and restrict W-trend claims to Z < 100/W^(1/3).
  - (b) Quantify it with a direct test: coarsen fine-grid fields of W=500 to
    0.5 m and re-measure RadiusP.
  - (c) Keep the results and reword the ALGORITHM claim to what the data show:
    monotone up to Z = 9 in the field median, and only along the diagonal up to 12.

### PHY-04  [high]  The per-direction MaxR_I level reads a fine-grid reference that is deficient near the grid edge (uncommitted)

- Where: `run_analysis.py:286-314` and `blastlib/processing/free_field.py:73-105`
  (both **modified, uncommitted**; HEAD used the scalar CSV level);
  `grids.py:166-171` stores `refP{g}/refI{g}` raw, pre-fill (committed). The
  output is `outputs/tables/max_radius_per_Z_req_soft3.csv` (modified,
  uncommitted).
- What: the urban exceedance field is max-filled across grids
  (`impulse{g}_orig`), but the level it is compared with is the ring median of
  the raw reference. Near the edges of the fine box, the raw fine-grid reference
  impulse is low:
  - at the edge itself: an outer-boundary effect;
  - in the corner at W=1500: time truncation as well. The reference fine stage was
    dumped at t = 0.319 s against 0.495 s for the urban run.

  `strip.py:34-36` states that the raw/filled asymmetry "is a no-op only within
  grid 1". Near the edges of grid 1 it is not.
- Evidence:
  - Fine/medium reference impulse ratio on the diagonal at r = 130 / 135 / 140 m:
    - W=1500: 0.861 / 0.604 / 0.156;
    - W=1000: 0.951 / 0.930 / 0.918;
    - W=500: 0.963 / 0.949 / 0.938.
  - Config 03, Z_free = 9, theta = 20 deg (3 m from the x = 100 m edge): level
    302.7 Pa.s against 347.4 Pa.s from the grid-filled reference.
  - Config 03, Z_free = 12, theta = 45 deg: level 110.9 against 262.1 Pa.s. The
    sector MaxR is 464.6 m against 174.3 m, and Req 201.8 m against 175.6 m.
  - Counterfactual: take the level from the reference filled exactly as the
    ratios are (`max(refI1, interp(refI2))`), over all 1,440 rows with W >= 250.
    - Pressure: no change; all 481 valid rows are identical.
    - Impulse: valid rows go from 538 to 547 (9 rows now flagged beyond R_conv
      would enter). Among rows valid in both runs, 17 change by more than 1% and
      6 by more than 5%, the largest by -7.4% (config 30, Z=9: 109.1 -> 101.0 m;
      config 78, Z=10: 107.8 -> 99.9 m). All affected rows are W = 1000/1500 at
      Z_free = 9-12.
  - Secondary effect: the impulse criterion itself compares raw urban with raw
    reference over different stage windows. Replacing the fine-grid reference
    moves RadiusI (W=1500) by only -0.67% to +0.61%.
- Consequence: the MaxR_I rows and beyond_I flags of the result of record, and
  therefore the canyon_trap fit rows. The effect is limited to large charges, so
  it is a W-dependent (non-HC) bias.
- Options:
  - (a) Build the level from the grid-filled reference, like-for-like with
    `impulse{g}_orig`.
  - (b) Exclude cells within some margin of each grid's outer boundary from both
    the ring median and the exceedance search.
  - (c) Revert to the committed scalar-CSV level for impulse, which is
    isotropic-biased but free of edges, and document the trade.

### PHY-05  [medium]  The W=1000 reference coarse grid is a copy of the medium grid (spatially mis-registered x2)

- Where: `data/raw_npz/config_{74,76,...,96}_*_w1000.npz` (12 configurations,
  det 1 and 2); `blastlib/io/raw_store.py:100-110` (**untracked**), which stores
  `origin/spacing/dims` from the urban file only and never checks the reference
  geometry; `blastlib/io/vtk_pair.py` (modified).
- What: `refP3 == refP2` and `refI3 == refI2` byte for byte, with `t_ref3 =
  t_ref2 = 1.1901 s` (the urban coarse dump is at 2.49 s). The copied data belong
  to the 0.5 m / 0-250 m grid but are placed on the 1 m / 0-500 m grid, so a value
  from radius r lands at 2r. Every other weight has distinct reference grids.
  ALGORITHM's "reference simulation on the same grid resolutions"
  (`ALGORITHM.md:364-366`) does not hold for W=1000.
- Evidence:
  - Coarse-grid reference at r = 240 / 260 / 300 m: P = 9.63 / 8.56 / 6.99 kPa
    (CSV 3.28 / 2.93 / 2.39) and I = 229 / 212 / 184 Pa.s (CSV 115 / 106 / 92).
  - The coarse reference also feeds the medium-grid fill
    (`refP2 = max(refP2, interp(refP3))`).
  - Bound with a surrogate (the coarse reference replaced by the CSV curve at the
    coarse coordinates): RadiusP changes 0 to -0.53% (at most 0.46 m), RadiusI
    -0.3% to +0.55% (at most 0.68 m), MaxR at most 0.97 m.
- Consequence: small changes to 12 rows of `convergence_table_*` and their
  `max_radius_per_Z` rows. Also a data-provenance defect. The VTKs are not
  present locally, so the on-disk file could not be inspected.
- Options:
  - (a) Re-export the W=1000 coarse reference and rebuild these 12 raw files.
  - (b) Record the defect and the bound above as a known limitation.
  - (c) Have the raw store compare urban and reference grid geometry and dump
    times, and refuse on mismatch.

### PHY-06  [medium]  No Kingery-Bulmash / UFC check exists; the CFD free field is 10-32% below the hemispherical surface-burst curve

- Where: `data/free_field_data.csv` (committed) and the reference fields;
  `CLAUDE.md:62-63` ("Kingery-Bulmash free-air curves, UFC 3-340-02");
  `ALGORITHM.md:192-194,312-318`; outline §1.3 (validation placeholder), §3.2.1;
  `PHYSICS_ANALYSIS_HE.md:253,643` ("P_ff ~ 20 kPa — the accepted UFC damage
  threshold").
- What: nothing in the repo compares the CFD free field with KB or UFC, and no
  standard is registered. For comparison, the probe used the Swisdak (1994)
  simplified KB polynomials for a hemispherical surface burst (SI). These are the
  curves of UFC 3-340-02 Fig. 2-15. The coefficients were entered from memory
  and checked only by their internal continuity at the range boundaries (P:
  124.48/124.43 kPa at Z = 2.9, 4.895/4.929 at 23.8; I: 239.2/238.7 at 0.96,
  9.48/9.46 at 33.7). **Verify against the source before citing.**
- Evidence (CFD = per-direction median of the reference field, range across the
  five W):

  | Z | KB P [kPa] | CFD P [kPa] | dP | KB I/W^(1/3) | CFD I/W^(1/3) | dI |
  |---|---|---|---|---|---|---|
  | 2 | 283.7 | 229.4-278.7 | -19..-2% | 134.6 | 110.1 | -18% |
  | 4 | 64.9 | 56.5-63.6 | -13..-2% | 72.4 | 65.4 | -10% |
  | 8 | 20.4 | 17.5-19.7 | -14..-4% | 38.4 | 34.2 | -11% |
  | 12 | 11.7 | 9.2-10.5 | -21..-10% | 26.1 | 22.9 | -12% |
  | 16 | 8.07 | 5.9-6.9 | -27..-15% | 19.7 | 17.2 | -13% |
  | 20 | 6.10 | 4.2-4.7 | -32..-23% | 15.9 | 13.8 | -13% |

  KB puts 10 kPa at Z = 13.5, 20 kPa at Z = 8.1 and I/W^(1/3) = 20 at Z = 15.8.
  In the CFD these fall at Z = 11.3-12.5, 7.2-8.0 and 13.6-13.8. Units are
  confirmed by the match: I is in Pa.s, and scaled impulse is in Pa.s/kg^(1/3),
  which equals kPa.ms/kg^(1/3). If I were in kPa.s it would be 1000x off.
- Consequence: R_conv and Lambda are same-mesh differences and ratios, so they
  are partly protected. The absolute thresholds are not. "10 kPa" is 10 kPa of a
  field that at Z ~ 12 reads 10-20% below the standard curve. The physical
  justifications ("structures are unaffected", "relevance ends near Z ~ 16",
  "UFC 20 kPa threshold") are not supported by any registered source. The
  roughly 12% impulse deficit is also unexplained: charge equivalence, charge
  height or shape, or solver EOS.
- Options:
  - (a) Register UFC 3-340-02 (and/or Swisdak 1994) in `docs/references/` and add
    a CFD-vs-KB table to the thesis.
  - (b) State the thresholds as CFD-field thresholds, with their KB-equivalent
    location.
  - (c) Drop the damage-threshold attributions until they are sourced.

### PHY-07  [medium]  Pi_2 and Z are not dimensionless; the "crossover at s = W^(1/3)" is a unit artefact

- Where:
  - `blastlib/regression/convergence_models.py:16-62`, in particular `:62`:
    "fully dimensionally consistent (all terms dimensionless -> Z dimensionless)"
    (committed);
  - `blastlib/regression/z_urban.py:20` (modified);
  - `ALGORITHM.md:17-28,129,136-138,186-188` (untracked);
  - `PHYSICS_ANALYSIS_HE.md:25,33,133-147,444,456`.
- What: Z = R/W^(1/3) and Pi_2 = s/W^(1/3) both carry m/kg^(1/3). The formulas
  are HC-invariant: W -> kW with all lengths scaled by k^(1/3) leaves them
  unchanged. But they are tied to the metre and kg-TNT unit system. The fixed
  "1" in `(W^(1/3)/s - 1)`, the thresholds a in {1, 2}, and A, B and C3 all
  carry units, and ln Pi_2 and sqrt(Pi_2) have unit-dependent values. The
  canyon-term switch "s = W^(1/3), the physical crossover between a street that
  channels the blast and one that blocks it" exists only because the unit is
  1 m/kg^(1/3):
  - in ft/lb^(1/3) the same expression switches at Pi_2 = 0.397 m/kg^(1/3),
    outside the sampled range;
  - in Sachs form, s/(E/p0)^(1/3) with E = 4.184 MJ/kg and p0 = 101.325 kPa,
    Pi_2 = 1 corresponds to 0.29.

  `PHYSICS_ANALYSIS_HE.md` also gives W^(1/3) the unit "m/kg^(1/3)" and calls it a
  "blast length 3.68 m" (W=50).
- Evidence: the arithmetic above. The data may show a switch near Pi_2 of about
  1.2 (`PHYSICS_ANALYSIS_HE.md:137-145`), but the model imposes exactly 1 rather
  than fitting it.
- Consequence: the coefficient tables are valid only in m and kg TNT. The
  mechanistic reading of the canyon term, and the "three independent places,
  same number" argument (`PHYSICS_ANALYSIS_HE.md:146`, where A of about 2.2-2.7 is
  in fact a different number), rest on a unit coincidence. No number of record
  changes.
- Options:
  - (a) State the units of Z, Pi_2 and every constant explicitly, and drop
    "dimensionless".
  - (b) Rewrite the groups in Sachs-dimensionless form. The constants change, the
    fits do not.
  - (c) Treat the switch location as a fitted parameter if its physical reading
    is to be kept.

### PHY-08  [medium]  Both bands are loose in relative terms at the measured radii; beyond Z ~ 13.7 the impulse band exceeds the free field itself

- Where: `constants.py:44-48`; `ALGORITHM.md:584-588`; outline §3.2.2, §3.4;
  `ff_reference.py:13-14`.
- What: the relative strictness of each absolute band varies with Z, since the
  band is fixed while the free-field level falls. Beyond the Z where
  I_ff/W^(1/3) = 20 (Z = 13.6-13.8 for every W), even total shielding
  (I_urban = 0) counts as converged. The quoted "impulse ~83% vs pressure ~47%,
  1.8x looser" uses the hard pressure radius.
- Evidence:
  - Band / free-field level at each configuration's own radius:
    - impulse: median 0.85, p10 0.74, p90 1.05, max 1.56;
    - pressure hard: median 0.48;
    - pressure soft beta=3 (production): median 0.67, so the production ratio is
      about 1.27x, not 1.8x.
  - Current tables: 17 of 96 configurations have Z_conv,I > 13.8; 2 exceed 16
    (config 40: 16.43; config 61: 21.49). This contradicts the outline §3.4 claim
    that "all radii are at Z <= 16". Config 61 also exceeds the Z = 20 support
    limit stated in `ff_reference.py:13-14`.
  - Inside R_conv,I, 7.8-34.6% of valid fine-grid cells carry at least 30%
    impulse amplification and still count as converged (configs 65, 26, 20, 02).
  - Shielding hidden by the pressure floor is rare at street level: under 1% of
    cells in the four configurations probed.
  - These numbers are entangled with PHY-01. With the rim masked, only 7
    configurations exceed Z_conv,I = 13.8.
- Consequence: the interpretation of R_conv,I as "urban indistinguishable from
  free field", and the stated asymmetry between the two loads.
- Options:
  - (a) Report the relative band at the radius, per load and for production.
  - (b) Cap the impulse band relative to I_ff where I_ff/W^(1/3) < thr.
  - (c) State R_conv,I as an absolute scaled-excess contour rather than a
    convergence radius.

### PHY-09  [medium]  The pressure floor is on urban P in the code but on P_ff in the thesis outline

- Where: `grids.py:187-189` (`lowP1 = peakP1_raw < min_pressure`, the urban raw
  peak; committed); `soft_criterion.py:17,124-125`; `THESIS_RESULTS_OUTLINE_HE.md:70`
  ("`|P_urban - P_ff| < 10 kPa` or `P_ff < 10 kPa` (relevance floor)").
- What: the two rules are different physics:
  - a floor on P_ff would declare every cell beyond the 10 kPa free-field contour
    converged, whatever the amplification there;
  - the coded floor on urban P does not hide amplification to >= 10 kPa, but it
    does hide any shielding to below 10 kPa.
- Evidence: code as quoted. `ALGORITHM.md:371-373` says "wherever P < 10 kPa",
  which is ambiguous.
- Consequence: the thesis text for §3.2.1.
- Options:
  - (a) Correct the outline to "urban P < 10 kPa".
  - (b) Reconsider which quantity the floor should gate, as a choice.

### PHY-10  [medium]  The "three nested grids" are three solver stages with independent records, max-stitched; this is undocumented

- Where: `grids.py:77-99` ("Fill missing values: fine grid filled from medium
  grid", committed); `vtk_reader.py:33-36` (modified), which points to
  "docs/ALGORITHM.md on the impulse criterion" for dump times, but no such
  section exists; `raw_store.py:109-110` (untracked); `ALGORITHM.md:75,364-366`.
- What: inside the fine-grid box, the medium grid holds only what happened after
  its stage started:
  - at r = 5-50 m, reference P of 0.13-0.55 kPa and reference I of 0-28 Pa.s;
  - the fine grid holds 8.5-5,560 kPa and 75-1,680 Pa.s at the same points.

  So `np.maximum` is not a fill. It is a max over stage records. For peak
  pressure this is the true maximum. For impulse it equals the total only where
  one stage holds the complete positive phase. The urban and reference stages
  also end at different times, e.g. fine stage 0.495 s urban vs 0.319 s
  reference at W=1500, and coarse 2.44 vs 2.10 s at W=50.
- Evidence: the probe profiles above. In the overlap zone where both stages
  saw the wave, fine and medium impulse agree to within +/-0.6%, which supports
  the stitching there.
- Consequence: the correctness of the impulse fields depends on a solver
  behaviour that the repo does not document. PHY-01 and PHY-04 are both side
  effects of this stitching.
- Options:
  - (a) Document the stage structure, the stitching rule and the dump times in
    ALGORITHM.
  - (b) Check from the solver documentation whether Peak_Impulse restarts at each
    remap.
  - (c) Flag cells whose positive phase straddles a stage end.

### PHY-11  [low]  Req is biased by +0.55% for a round field

- Where: `blastlib/processing/radius_estimator.py:136-140` (committed).
- What: A = sum(0.5 r^2 dtheta) over 91 full 1-degree bins covers 91 deg, but
  the end bins are half-width (`theta_bin_edges`).
- Evidence: `reduce_theta_radii(np.full(91,100.0),'req')` returns 100.554.
- Consequence: all radii and Z are +0.55% in common mode, so the effect is
  absorbed into C0 and A.
- Options:
  - (a) Weight the end bins by 0.5.
  - (b) Document the offset.

### PHY-12  [low]  The legacy impulse rule compares Pa.s with a kPa number

- Where: `grids.py:199-203` (committed).
- What: with `weight=None`, `|I - I_ref| < min_pressure` compares an impulse
  difference in Pa.s against the number 10, which is the kPa threshold. No
  current entry point reaches this branch (both pass `weight`), but it fails
  silently if one does.
- Options:
  - (a) Raise an error instead.
  - (b) Keep it and document it.

### PHY-13  [low]  The free-field Hopkinson statistics are quoted inconsistently

- Where: `ALGORITHM.md:45-48` ("CV ~ 4.3%", "57.4 -> 63.7 kPa at Z = 4");
  `grids.py:179` ("4.7%"); outline §2.1 ("4.7%").
- Evidence: measured CV across W (ddof 0) is 4.77% on the CSV for Z = 1-20 and
  5.24% for Z <= 12. The per-direction median of the field gives 4.76%. At Z=4
  the values run 55.3 -> 62.3 kPa (CSV) and 56.5 -> 63.6 kPa (field median); 57.4
  appears in neither. (max-min)/mean reaches 24-25% at Z = 1, against the stated
  "10-17%".
- Options: re-derive the numbers from one named source and quote them once.

### PHY-14  [low]  `PressureAtR` / `ImpulseAtR` in the table of record are single-cell values of no clear meaning

- Where: `convergence.py:192-201` (committed); `run_analysis.py:257-258`
  (modified); used by `outputs/parametric_study_B/_common.py:109-110`.
- What: each value is the peak of one cell, in the sector whose radius is
  nearest Req. Under the soft scan it is the cell nearest the expected radius.
- Evidence: PressureAtR is below 50% of P_ff(Z_conv,P) in 39 of 96 rows, and
  ImpulseAtR below 50% of I_ff in 27. Many of these are the rim cells of PHY-01.
- Options:
  - (a) Document the column as a diagnostic.
  - (b) Replace it with P_ff/I_ff at Z_conv.

### PHY-15  [low]  Urban "pressure curves" pair MaxR with the axis-sampled CSV level

- Where: `tools/config_curve/config_curve.py:5-10,72-75` and
  `tools/pressure_report/pressure_report.py:14,232` (both untracked);
  `PHYSICS_ANALYSIS_HE.md` §6c.
- What: MaxR is now measured against per-direction reference-field levels, but
  the curves plot it against `P_ff` from the CSV, which is axis-sampled.
- Evidence: at W=1500, Z=12 the level is 9.08 kPa in the CSV, 9.38 (field median)
  and 10.97 (diagonal). The difference ranges from about 3% to 10% or more at the
  seam.
- Options:
  - (a) Carry the direction-averaged level used into the table.
  - (b) Label the curve's axis as the CSV level.

### PHY-16  [low]  The provenance of `free_field_data.csv` is undocumented

- Where: `data/free_field_data.csv` (committed in 4300e59, with no provenance);
  `CLAUDE.md:165-166` ("free-field reference from data/free_field_data.csv").
- What: nothing records which run, direction or grid produced the table, or how
  integer Z was sampled. `strip.py:29-31` calls it "axis-sampled and 1-D". In
  production it now supplies only the recorded `P_ff`/`I_ff` columns and the
  fallback levels, which were used for about 0.1% of levels in the configs
  probed. CLAUDE.md overstates its role.
- Options: add a provenance note, or correct CLAUDE.md §4.

### PHY-17  [low]  Some lengths in the measurement are fixed in metres, not scaled

- Where:
  - `convergence.py:21`: K = 3 cells, i.e. 0.45 / 1.5 / 3 m by grid, which is
    0.12 m/kg^(1/3) at W=50 and 0.04 m/kg^(1/3) at W=1500 on the fine grid;
  - `free_field.py:73-74`: ring half-width 0.6 m, widening to 4 m.
- Evidence: the owner's coarsening test found the hard scan mesh-stable (+1.9% /
  -0.3%). The outward bias of the ring median, which comes from the
  area-weighting of cells, is at most about 1% in level, even at Z=2 for W=50.
- Options: document these as non-scaled constants, or scale them with W^(1/3).

## Checked and found consistent

- VTK `Peak_Ovepressure` is gauge overpressure in Pa and is converted to kPa
  once, for urban and reference alike, in both paths (`vtk_pair.py:108-114`,
  `raw_store.py:102-105`). Far-field magnitudes (0.5-5 kPa) confirm it is not
  absolute pressure.
- `Peak_Impulse` is in Pa.s. It matches the CSV to within 1% along the diagonal
  at r = 20-110 m and KB within about 10-13% (PHY-06), while kPa.s would be
  1000x off.
- The CSV columns are P in kPa and I in Pa.s. `reference_curve` docstring units
  are correct.
- `thr_I_scaled` is in Pa.s/kg^(1/3). `impulse_converged` divides by W^(1/3)
  with W in kg from the file or the name. The scaled free-field impulse collapses
  across W (CV median 0.29%, max 1.6%), and the I/W^(1/3) = 20 contour sits at
  Z = 13.79 / 13.76 / 13.64 / 13.77 / 13.77. The threshold is HC-admissible.
- The 10 kPa band is HC-admissible in principle. Its free-field contour sits at
  Z = 11.33 / 11.97 / 12.13 / 11.27 / 11.27 (CSV), a spread of about +/-4%,
  with the caveats of PHY-03. `softCap_kPa = 20` and eta = 0.5 give w(0) = 0,
  w(10 kPa) = 0.5 and w(>= 20 kPa) = 1 for every beta.
- The legacy fixed-band contours "Z = 4.98 / 8.65 / 10.86 / 13.77 / 15.78 at 5%"
  are reproduced from the CSV: a 10 Pa.s band is 5% of I_ff at 200 Pa.s. The
  factor 3.107 = (1500/50)^(1/3) is correct.
- rho = b^2/(b+s)^2 equals the solver's footprint fraction (config 01: 0.5620 vs
  0.5625). The ranges rho 0.18-0.74, Pi_2 0.44-5.43, H/s 0.2-4.8 and
  (s/5.4)^3 <= W <= 8 s^3 are correct.
- Geometry conventions:
  - the charge is at the origin of a quarter-symmetric domain;
  - det 1 is on the street centreline at mid-block, with the building from
    x = 0 to b/2 and z = s/2 to s/2 + b;
  - det 2 is at the intersection centre;
  - `exclude_radius` is the nearest corner (det 1) or face (det 2).
- One reference serves each W: det 1 and det 2 references are byte-identical, so
  the ratio is not contaminated by det.
- Z_urban = MaxR/W^(1/3), R_free = Z W^(1/3), the Z_conv clip `Rconv/W13`, and the
  `R_free > exclude_r` and `R_free < R_conv` row conditions are all dimensionally
  consistent (m vs m, m/kg^(1/3) vs m/kg^(1/3)).
- The arithmetic in ALGORITHM "10/P_ref < 0.05 only for P_ref > 200 kPa" and
  "178% at P_ref ~ 5.6 kPa" is correct.
- Relative bands at the radius: impulse median 85% (documented 83%) and hard
  pressure 48% (documented 47%) both reproduce. Soft pressure is 67% (PHY-08).
- `VolumeDensity` (MAX_HEIGHT = 24 m) is written to the table but not used by any
  fit.
- The probes reproduce the committed convergence tables (req and req_soft3, all 96)
  and the modified `max_radius_per_Z_req_soft3.csv` (W >= 250) exactly.

## Not checked

- Solver semantics (Viper-Blast). The repo documents none of the following:
  - whether `Peak_Impulse` is the running maximum of the integral of overpressure
    over time and restarts at each stage remap;
  - the stage remap times;
  - the charge material and its equivalence (the docs say kg TNT; unverified);
  - charge height and shape;
  - the ambient p0.
- The KB/UFC coefficients against a primary source. None is registered
  (`docs/references/INDEX.md` absent); see the caveat in PHY-06.
- The thesis chapter was not provided, and `compare_v6` and the proposal are out
  of bounds.
- `data/processed_npz`, `processed_npz_v2` and `obs_npz` are cloud-only
  placeholders and were not opened. `data/vtk` and `data/viper1d` are empty, so
  the reference-grid geometry of the W=1000 coarse file could not be inspected.
- Downstream effects of PHY-01 to PHY-04 on Phase 2 (coefficients, LOGO/CV, safe
  domain). Measuring them needs a production re-run, which only the owner may
  request.
- pytest was not run: data tests would hydrate cloud placeholders and pytest
  writes a cache into the repo. `tools/check_formulas` was not run because it
  writes into `outputs/check_results`.
- The street-channelling model (`blastlib/street`) beyond the docstring statements
  cited above, and the OBS surface data.
