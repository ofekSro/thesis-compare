# Audit: physics — the impulse convergence criterion  (2026-09-28, commit 3400e26)

Scope: the per-cell impulse convergence rule behind R_conv,I. Four candidates:
(A) production "accurate-or-irrelevant" (rel 10% OR urban I/W^(1/3) < 20),
(B) pressure-relevance floor (rel 10% OR urban peak P < 10 kPa),
(C) historical scaled band (|dI|/W^(1/3) < 20), (D) accuracy-only (rel 10%).
Judged on physical grounds only, per the owner's question. The verdict is at
the end; the owner decides. [Later the same day: candidates (E) and (F) —
see the two addenda at the end.]

Documents read: `blastlib/constants.py` (PARAMS, IMPULSE_CRITERION),
`blastlib/processing/ff_reference.py`, `blastlib/processing/grids.py`,
`blastlib/io/raw_store.py`, `docs/ALGORITHM.md` (§Step 1, §Why the algorithm
is sound), `outputs/check_results/impulse_criterion_change_note.md`,
`outputs/check_results/criterion_decision_suite.csv`,
`outputs/check_results/cfd_vs_kb_ufc_note.md`, `docs/references/INDEX.md`
plus the IATG 02.20 and UFC 3-340-02 `.txt` sidecars,
`data/free_field_data.csv`, `outputs/tables/convergence_table_req_soft3.csv`,
and the read-only scratchpad `pfloor_variant_suite.csv` (candidate-B radii).

All floor-to-Z mappings quoted below were recomputed from
`data/free_field_data.csv` (log-log interpolation), not taken from comments:
I_ff/W^(1/3) = 20 at Z = 13.64–13.79 across W = 50–1500 (claimed 13.7 —
confirmed); = 25 at Z = 10.94–11.03 (claimed 11.0 — confirmed); = 15 at
Z ≈ 18.3–18.4. P_ff = 10 kPa at Z = 11.3–12.1 (claimed ~12 — confirmed);
9 kPa at 11.9–12.9; 11 kPa at 10.6–11.5; 4 kPa at Z ≈ 20, i.e. at the edge
of the tabulated range (extrapolated: ~2.9 kPa at Z = 25, ~2.0 at Z = 32).

## Summary

The physics question reduces to one point: what does "irrelevant" mean for a
location in a damage-oriented framework. Damage capacity is bounded from
below in **pressure**, not in impulse: every P–I diagram has a pressure
asymptote (quasi-static bound), and below it no impulse magnitude produces
damage in that target — a statement the repo's own registered sources carry
(UFC 3-340-02 §1, long-duration lung-damage threshold ~10 psi "at any
impulse"; IATG 02.20 Table 8 anchors every damage tier to a side-on
pressure). An impulse level alone is therefore not a relevance measure, and
the project's own decision D8 already said exactly this for damage criteria.
Candidate (A)'s floor contradicts it, is a number inherited from the rejected
band's calibration, and drives 33/96 production radii beyond Z = 20 — outside
the validated free-field range, into fields at 2–4 kPa that the framework's
own anchor declares of no engineering interest. Candidate (B) is the
physically coherent rule *within the declared damage scope* (structural
tiers ≥ ~9 kPa): it puts both radii on one relevance anchor, keeps every
radius inside the validated range, and the owner's rejection of (C) is
physically sound. (B)'s cost is honesty of wording: it is floor-dominated,
so R_conv,I must be presented as a relevance-bounded radius, never as the
radius where the impulse field merges with the free field. (D) is the honest
field-merging quantity but is not measurable with this dataset where it
matters most. Verdict: (B), with the wording and caveats of findings 4–7.

## Findings

### physics-1  [high]  Candidate (A)'s relevance floor on scaled impulse has no physical basis and contradicts the project's own D8 physics
- Where: `blastlib/constants.py:45-137` (IMPULSE_CRITERION rationale),
  `blastlib/processing/ff_reference.py:91-115`, `docs/ALGORITHM.md` §Step 1
  ("beyond R_conv,I the free-field impulse is either correct to within 10%
  or irrelevant").
- What: the clause `I_urban / W^(1/3) < 20 Pa·s/kg^(1/3)` is presented as an
  *irrelevance* statement ("the charge's impulse no longer matters at all",
  constants.py:54-55; "amplified urban impulse stays RELEVANT far beyond the
  free-field relevance range", constants.py:76-78). Physically, impulse
  magnitude alone never determines damage relevance. For any target, the P–I
  damage boundary has a pressure asymptote: at peak pressure below the
  target's quasi-static resistance, no impulse — i.e. no duration — produces
  damage, because high impulse at low peak pressure means long duration,
  which is the quasi-static regime, where response is governed by peak
  pressure alone. The repo's own registered sources state this:
  `ufc_3_340_02.txt:3623-3625` — "the threshold pressure level for petechial
  hemorrhage resulting from long-duration loads may be as low as 10 to 15
  psi" (i.e. ~69 kPa is a floor *at any impulse*, exactly as the constants
  comment itself quotes for humans); IATG 02.20 Table 8 anchors every
  structural damage tier to a side-on overpressure, none to an impulse. And
  the project's own decision D8 (constants.py:115-118) states that "impulse
  damage criteria are absolute, target-specific P–I curves that cannot
  collapse to one Hopkinson-admissible contour" — which is precisely an
  argument that no single scaled-impulse level can mark relevance. The
  criterion adopted the next day rests on the assumption D8 rejected.
- Evidence: at the locations where (A)'s floor sets the radius (Z ≈ 18.6
  median to 32.4 max), the free-field peak pressure is 4.0–4.7 kPa at
  Z = 18–20 (computed from `free_field_data.csv`) and ~2–3 kPa at Z = 25–32
  (extrapolated) — below even the lowest structural tier the framework
  anchors to (IATG 9 kPa, itself "personnel in the open are not likely to be
  seriously injured by blast"). The framework's own pressure side (PARAMS
  minPressure, audit D7) declares such locations "of no engineering interest
  even if the free field there is stronger". The impulse criterion declaring
  the same locations *relevant* is an internal contradiction. The floor
  value 20 is, by the comment's own admission (constants.py:68-69), "carried
  over from the previous band value" — a calibration of the rejected
  criterion, whose original selection was itself made on the artefact store
  (constants.py:98-103). The value has no independent physical derivation.
- Consequence: `outputs/tables/convergence_table_req_soft3.csv` RadiusI (all
  96 rows), the quad power-law RadiusI coefficients of record, the Λ_I refit
  (larger fit domain), the anchors 133.19/141.36 m, and every thesis
  statement built on "impulse stays relevant far beyond pressure"
  (impulse_criterion_change_note.md's headline ordering claim).
- Options: (1) adopt candidate (B) and regenerate the impulse record;
  (2) keep (A) but re-derive the floor from a physical argument that
  survives the P–I asymptote objection (none was found in this audit);
  (3) keep (A) as an explicitly *load-fidelity* product (not relevance) and
  strike every "irrelevant"/"relevance" wording — which then re-opens the
  owner's Z = 32 objection unanswered.

### physics-2  [high]  Under (A), 33/96 radii of record lie beyond the validated free-field range (Z > 20)
- Where: `outputs/tables/convergence_table_req_soft3.csv` (RadiusI);
  `blastlib/processing/ff_reference.py:8-14` (module docstring);
  `outputs/check_results/cfd_vs_kb_ufc_note.md`.
- What: the tabulated free-field reference (`free_field_data.csv`) ends at
  Z = 20, and the CFD-vs-KB cross-check (PHY-06) shows the CFD *pressure*
  deficit against Kingery–Bulmash growing with distance (0.86 at Z = 10,
  0.70 at Z = 20 — "shock front smearing on a mesh fixed in metres") with no
  validation of either field beyond Z = 20 at all. `ff_reference.py` itself
  warns: "Treat any result whose radius exceeds Z=20 as unsupported." The
  production path does use the true reference VTK fields (v3 raw store keeps
  refI, `raw_store.py:14-19`), so the CSV-reconstruction caveat does not
  apply literally — but the *validation* of the far field does: nothing
  beyond Z = 20 has been cross-checked against any standard, and the
  measured mesh fidelity is deteriorating in exactly the direction that
  matters for peaks.
- Evidence: recomputed from the production table: Z_conv,I = RadiusI/W^(1/3)
  exceeds 20 in 33 of 96 configurations (max 32.43, config_61); it exceeds
  18.4 (the I_scaled = 15 free-field contour, near the table edge) in 51 of
  96. Under (B) the count beyond Z = 20 is 0/96 (max 17.48).
- Consequence: a third of the impulse radii of record, and the regression
  fitted over them, rest on far-field CFD data whose fidelity is unquantified
  and whose free-field counterpart is unvalidated. Any candidate that lets
  the radius ride into Z > 20 (A, and D in deep-canyon configs) inherits
  this independently of the relevance argument of physics-1.
- Options: (1) a criterion whose radii stay inside the validated range —
  (B) does by measurement, not by construction; (2) extend the free-field
  validation (tabulation + KB cross-check + mesh study) to Z ≈ 33 and keep
  (A); (3) keep (A) and flag every Z > 20 radius as unsupported in the
  tables and the thesis.

### physics-3  [low]  The owner's rejection of the scaled band (C) is physically sound — confirmed
- Where: `blastlib/processing/ff_reference.py:118-121`;
  `outputs/check_results/impulse_criterion_change_note.md` §What changed.
- What: |I_urban − I_ff|/W^(1/3) < 20 is Hopkinson-admissible (it picks one
  scaled contour per weight — verified: the band equals the local free-field
  impulse exactly where I_ff/W^(1/3) = 20, i.e. Z = 13.6–13.8 for every W).
  But as a *convergence* statement it is an absolute band, so the permitted
  relative error is 20/(I_ff/W^(1/3)), which crosses 100% at Z ≈ 13.7 and
  grows without bound: a cell at twice the free-field impulse counts as
  converged at Z > 13.7. A criterion whose guarantee ("free-field methods may
  be used beyond R") weakens without bound with distance cannot deliver that
  guarantee. The rejection is correct, and it generalises: *any* absolute
  band, scaled or not, fails the same way; only a relative band, or a
  relevance floor that ends the question, can close it.
- Evidence: the Z ≈ 13.7 crossing recomputed from `free_field_data.csv`
  (13.64–13.79 across all five weights).
- Consequence: none — this confirms a decision already taken.
- Options: none needed; record the generalised form of the argument in the
  thesis (it explains why the replacement had to change *form*, not value).

### physics-4  [medium]  (B) is floor-dominated: its meaning must be stated as a relevance radius, never a field-merging radius
- Where: scratchpad `pfloor_variant_suite.csv` (read-only); would govern the
  wording of `docs/ALGORITHM.md` §Step 1 and thesis ch. 9.
- What: under (B) the 10% accuracy clause trims the floor-only radius by a
  median of 1.5% (recomputed: 1.47%; > 5% in 8/96 configs), so R_conv,I,(B)
  is, to first order, the urban 10 kPa peak-overpressure contour. That is a
  legitimate physical object — "the boundary of the region where urban
  impulse can matter for the anchored damage class" — but it is *not* "the
  radius where the urban impulse field converges to the free field". Between
  R_(B) (median Z 13.8) and the accuracy radius the urban impulse remains
  amplified above 10% while urban P < 10 kPa; the free-field substitution
  there is justified by irrelevance, not by accuracy. If the thesis calls
  R_conv,I a convergence/merging radius while adopting (B), a reader who
  checks the field will find the impulse ratio far from 1 just outside it.
- Evidence: (B) medians confirmed from the scratchpad: median 13.82, p90
  15.55, max 17.48; Z_I > Z_P in 96/96 (ratio to production RadiusP: median
  1.39, min 1.14). Redundancy of the impulse floor as a third clause
  confirmed (median 13.72 with it vs 13.82 without): wherever
  I_urban/W^(1/3) < 20 in these fields, urban P < 10 kPa almost always
  holds already.
- Consequence: thesis wording of aims 2 and 4; the definition sentence of
  R_conv,I in ch. 9.
- Required wording (physics verdict on semantics): "R_conv,I is a
  **relevance-bounded convergence radius**: beyond it, at every point,
  either the free-field impulse is accurate to within 10%, or the urban
  peak overpressure is below 10 kPa (IATG 02.20 Table 8 anchored), below
  which the anchored structural damage class is insensitive to impulse of
  any magnitude. It is not the radius at which the urban impulse field
  merges with the free field; the merging radius is larger and, in
  channelling configurations, lies beyond the validated range of this
  study."
- Options: (1) adopt that wording with (B); (2) additionally report the
  pure-accuracy radius (D) as a *descriptive* column where it is measurable
  (Z ≤ 20), clearly separated from the engineering radius; (3) rename the
  quantity (e.g. R_rel,I) to prevent the misreading at the source.

### physics-5  [medium]  The 10 kPa floor is a CFD-field value; on the standard's (KB) scale the boundary sits further out
- Where: `outputs/check_results/cfd_vs_kb_ufc_note.md` §Threshold locations;
  `blastlib/processing/grids.py:206-208` (floor tests the raw urban CFD
  peak).
- What: PHY-06 measured the CFD pressure field 14–18% below KB at Z ≈ 12 and
  the CFD 10 kPa contour at Z = 11.3–12.1 vs KB's 13.4. Since the CFD
  under-resolves peaks, a location where the CFD reads P < 10 kPa may truly
  be at 11–12 kPa; the (B) floor therefore converges some cells that a
  KB-referenced 10 kPa boundary would not, making R_conv,I,(B) smaller than
  its stated physical anchor implies. The same caveat already attaches to
  the pressure criterion (the note's "thesis-facing consequence").
- Evidence: floor sensitivity from the scratchpad: floor 9 kPa → median
  14.61 (+5.7%), 11 kPa → 13.13 (−5.0%), elasticity ≈ −0.5. Correcting the
  ~18% local peak deficit (physical 10 kPa ≈ CFD ~8.2 kPa) would move the
  median radius by roughly +8–10%.
- Consequence: safety-distance statements (aim 4) that quote R_conv,I
  against IATG damage levels; the "conservative envelope" claim of the
  proposal.
- Options: (1) carry the PHY-06 one-line caveat on every anchored statement,
  as that note already requires; (2) set the CFD floor at the KB-equivalent
  value (~8–9 kPa) so the physical anchor is honoured in KB terms; (3) add
  an explicit margin to the published radii and say why.

### physics-6  [medium]  The IATG Table 8 tier descriptions in the D8a rationale comment are shifted by one tier
- Where: `blastlib/constants.py:30-39`; source
  `IATG-02.20-...txt:1065-1098` (9 and 11 kPa tiers) and `:1123-1151`
  (16 kPa tier).
- What: the comment attributes "acceptable protection for low-density areas
  ... average damage up to ~20% of replacement cost" to the **9 kPa** tier
  and "damage to main structural members, repairs > 20%" to the **11 kPa**
  tier, concluding the floor "sits at the standard's boundary between
  repairable and structural damage". Per the sidecar: the 9 kPa tier
  (DQ = 14.8Q^(1/3), PTRD) is "average damage costing in the range of 10% of
  total replacement cost"; the 11 kPa tier (DQ = 11.1Q^(1/3), Blue Line IBD)
  is the "acceptable level of protection for low-density areas ... up to 20%
  of replacement cost"; "damage to main structural members ... more than 20%"
  belongs to the **16 kPa** tier (DQ = 9.6Q^(1/3)). The floor value (between
  the 9 and 11 kPa tiers) survives; its characterisation does not — 10 kPa
  sits at the standard's ~10%-repair to ~20%-repair boundary, and the
  repairable-vs-structural boundary is at 16 kPa.
- Evidence: quotes above, verified against the registered sidecar.
- Consequence: any thesis sentence quoting the D8a rationale verbatim would
  misquote the standard. The anchoring of the 10 kPa value itself stands.
- Options: (1) correct the comment's tier descriptions (owner edit);
  (2) re-examine whether the intended anchor was the structural-member
  boundary — in which case the floor argument would point at 16 kPa, a
  materially different (smaller-radius) criterion; the owner should decide
  which damage boundary the floor is meant to mark.

### physics-7  [medium]  The 10 kPa floor defines the product's damage scope: light targets (glazing-level, 2–5 kPa) are outside it — for both radii
- Where: `blastlib/constants.py:21-43` (PARAMS), IATG sidecar lines
  1011–1038 (2–3 kPa and 5 kPa tiers, glass breakage).
- What: the P–I asymptote argument that justifies (B) is target-class
  specific. IATG's own lower tiers put substantial glass breakage at 5 kPa
  and occasional breakage at 2–3 kPa; window panes have pressure asymptotes
  well below 10 kPa and short natural periods (~10–50 ms) comparable to the
  measured pulse durations, so at Z = 14–20 (P ≈ 4–7 kPa, t_d ≈ 20–70 ms
  from 2I/P on the free-field table) glazing damage remains physically
  possible and impulse-sensitive. The 10 kPa floor discards this region for
  the impulse radius exactly as the identical floor already discards it for
  the pressure radius. This is a coherent, *declared* scope choice (D7/D8:
  structural anchor now, R_human and target-specific products later) — but
  it means aim 4's "several damage levels" cannot include levels below
  ~9 kPa from these radii.
- Evidence: t_d ≈ 2I/P computed from `free_field_data.csv`: 20–23 ms (W=50),
  34–54 ms (W=500), 58–72 ms (W=1500) over Z = 12–20.
- Consequence: thesis domain-of-validity statements; aim 4 damage levels;
  the future R_human/glazing products must not reuse R_conv,I.
- Options: (1) state the scope limit explicitly wherever R_conv is offered
  for safety distances; (2) plan the low-pressure damage levels as a
  separate product on the unbanded ratio fields; (3) both.

### physics-8  [low]  The "far from impulsive" argument offered for (B) is overstated; the asymptote argument is the correct and sufficient one
- Where: the owner's argument as posed (context of this audit); would appear
  in thesis ch. 9 justification text.
- What: at Z = 14–20 the free-field positive-phase duration estimate
  2I/P ≈ 20–70 ms is comparable to the natural periods of damage-governing
  envelope components (glass ~10–50 ms, wall panels ~20–100 ms) — the
  loading regime there is dynamic, not clearly quasi-static, and urban
  multi-shock loading lengthens effective durations further. So "the loading
  is far from impulsive for structural targets" does not hold uniformly and
  should not carry the justification. It also does not need to: the pressure
  asymptote is the quasi-static *bound* — in the dynamic and impulsive
  regimes the pressure required for damage is higher still, so P below the
  asymptote excludes damage in every regime. One honest caveat: P–I diagrams
  assume a single pulse; repeated urban pulses spaced near a component's
  period can accumulate response somewhat in lightly damped targets. This
  does not overturn the bound for the anchored class at 3–7 kPa but should
  be acknowledged rather than silently assumed away.
- Evidence: durations above; UFC long-duration threshold quote
  (`ufc_3_340_02.txt:3623-3625`) as the source-backed form of the asymptote
  statement.
- Consequence: justification text only.
- Options: base the thesis justification on the asymptote bound (with the
  multi-pulse caveat), not on regime classification.

### physics-9  [low]  The 10% accuracy band is the right kind of number; keep its physical justification primary
- Where: `blastlib/constants.py:62-67`; `docs/ALGORITHM.md:124-127`.
- What: a convergence band must sit clearly above the numerical noise floor
  or it measures the mesh, not the physics. The impulse mesh-convergence
  tolerance is 5%; the CFD-vs-KB impulse deficit (~12%) is common-mode
  between urban and reference runs and largely cancels in the ratio; the
  reference-reconstruction error (0.4%) does not enter the production path
  (true refI fields, v3 store). 10% = 2× mesh tolerance is the minimal
  defensible margin — physically sound. The documented selection, however,
  leans on LOGO predictability ("tighter bands are strictly more stable and
  more predictable", constants.py:65-67), which is a regression-convenience
  argument the owner's question explicitly excludes. The physical argument
  stands on its own and should be the one the thesis states; the stability
  observation is a consequence of floor-dominance (physics-4), not a
  justification.
- Evidence: band-trim measurements (physics-4); mesh tolerance as documented.
- Consequence: justification text; none numerical.
- Options: reorder the rationale (physics first, sweep as confirmation).

### physics-10  [medium]  Residual exposure beyond R is estimator-level and unquantified — for every candidate
- Where: `docs/ALGORITHM.md:107-137` (K = 3 streak scan, equivalent-area
  collapse); shared with RadiusP.
- What: the far-to-near scan stops at the first three-consecutive-cell
  violation per sector, and the equivalent-area collapse places the scalar R
  below the per-sector radii of the widest lobes. Therefore, under *any*
  per-cell rule including (B), isolated (< 3-cell) violating cells with
  P ≥ 10 kPa, and whole sectors whose per-angle radius exceeds R_eq, can lie
  beyond the published radius. The direct answer to "does any config have
  amplified impulse with P ≥ 10 kPa beyond the (B) radius" is: by
  construction, only in these two estimator-level forms; their magnitude
  was not quantified in this audit (it requires the NPZ field store, cloud
  placeholders — not downloaded). This is not a defect of (B) relative to
  the alternatives — it is identical for the pressure radius of record —
  but the thesis guarantee sentence must say "in the equivalent-area sense"
  rather than "at every point", or the per-sector maxima must be reported.
- Evidence: estimator definition as documented; not run against fields.
- Consequence: the strength of the guarantee sentence in ch. 9.
- Options: (1) quantify once the store is local (count of violating cells
  with P ≥ 10 kPa beyond R per config, and max per-sector radius vs R_eq);
  (2) weaken the guarantee wording; (3) publish p95-of-sectors alongside
  R_eq.

## Verdict

**Candidate (B) — the pressure-relevance floor — is the physically correct
criterion**, within the framework's declared damage scope (structural tiers,
IATG ≥ ~9 kPa), for these reasons in order of weight:

1. Relevance in a damage framework is bounded in pressure, not impulse: the
   P–I pressure asymptote makes "urban peak P < 10 kPa" a statement that no
   impulse magnitude can matter there for the anchored target class. It is
   the only irrelevance statement available that is simultaneously
   physical, standard-anchored (IATG Table 8), Hopkinson-consistent (an
   absolute pressure level picks one scaled contour, cross-weight spread
   ~5%), and identical in meaning to the pressure radius's own floor — the
   two radii become commensurable, which aim 4 requires.
2. (A)'s impulse floor is physically ungrounded as a relevance measure
   (physics-1), inherits its value from a rejected calibration, and pushes a
   third of the record beyond the validated field (physics-2). (C)'s
   rejection is sound and generalises to all absolute bands (physics-3).
   (D) is the honest *field-merging* quantity but is unmeasurable where it
   matters (it rides into Z > 20) and answers a descriptive question, not
   the engineering one the radius exists for.
3. The dimensional objection to (B) — "a pressure quantity terminates an
   impulse measurement" — fails physically: the clause does not measure
   impulse, it decides whether the location can matter, and that decision
   lives on P–I diagrams whose lower boundary is a pressure. The impulse
   floor 20 as a third clause is measured redundant (median 13.72 vs 13.82)
   and adds nothing physical; parsimony favours dropping it.

Mandatory conditions on adopting (B): the thesis must use the
relevance-radius wording of physics-4 (never "field-merging"); carry the
CFD-vs-KB floor caveat of physics-5 on every standard-anchored statement;
state the damage-scope limit of physics-7; and either quantify or soften
the guarantee per physics-10. The floor value 10 kPa is defensible as
anchored (between IATG's 9 and 11 kPa tiers, elasticity ≈ −0.5), but the
tier descriptions in the rationale comment must be fixed (physics-6) and
the owner should confirm 10 kPa — not 16 kPa — is the damage boundary the
product is meant to mark. The 10% band is the right kind of number
(physics-9).

## Checked and found consistent

- Floor-to-Z mappings in constants.py: I/W^(1/3) = 20 → Z 13.64–13.79,
  = 25 → Z ≈ 11.0; P = 10 kPa → Z 11.3–12.1 (all recomputed, spread ≤ 1%,
  Hopkinson collapse holds).
- Candidate-(A) production statistics: median Z_conv,I 18.64, max 32.43,
  Z_I > Z_P in 96/96 — match the change note and the decision suite.
- Candidate-(B) statistics: median 13.82, p90 15.55, max 17.48; accuracy
  trim median 1.47%, > 5% in 8/96; floors 9/11 kPa → medians 14.61/13.13;
  impulse-floor clause redundant (13.72) — all match the brief.
- `impulse_converged` (ff_reference.py:91-115) implements the documented
  (A) rule exactly; grids.py applies it per level on the true refI fields
  (v3 raw store), pressure floor on the raw urban peak — code and
  ALGORITHM.md §Step 1 agree.
- The v3 raw store carries the true reference fields, so the Z ≤ 20
  reconstruction caveat in ff_reference.py does not silently contaminate
  the production path (the *validation* gap of physics-2 remains).
- UFC 3-340-02 lung-damage pressure-asymptote quote and IATG Table 8 tier
  pressures (2–3, 5, 9, 11, 16, 21, 70 kPa) verified in the registered
  sidecars.
- The scaled band's Hopkinson admissibility argument (fixed Pa·s band picks
  a different contour per weight; W^(1/3) division restores one contour) —
  arithmetic confirmed.

## Not checked

- Field-level quantification of residual violations beyond R under (B)
  (physics-10): requires `data/raw_npz` locally (OneDrive placeholders; a
  read would trigger multi-GB downloads — not done in a review).
- Whether config_61's Z = 32.4 (A) radius is limited by the simulation
  domain extent (needs grid dims from the store).
- The thesis chapter text itself (not provided to this audit); the wording
  requirements above are stated against ALGORITHM.md only.
- The K = 3 and equivalent-area choices, the soft pressure criterion, and
  the regression models — outside this question's scope except where they
  bound the guarantee (physics-10).

---

## Addendum: candidate (E), the impulse-only mirror  (2026-09-28, later the same day)

Owner's counter-proposal (E), the exact structural mirror of the pressure
criterion, entirely in impulse:

    converged  iff  |I_urban − I_ff| / W^(1/3) < x   OR   I_urban / W^(1/3) < y

with x = y, "like pressure does it" (|dP| < 10 kPa OR P_urban < 10 kPa).
Stated motive: isolation — each load quantity gets its own self-contained
criterion, no cross-contamination between the pressure and impulse products.

Additional evidence for this addendum: the owner's measurement landed in
full — scratchpad `mirror_variant_suite.csv` (96/96 configs, variants
x = y ∈ {15, 20, 25} and x = 20 / y = 25, K = 3, `req` estimator, same
harness as the earlier suites; the generating script
`mirror_variant_suite.py` was read and implements exactly the rule above) —
plus the historical scaled-band record on the clean store
(`conv_scaledband_clean.csv`, scratchpad, read-only) as the x-only
comparator, and `criterion_decision_suite.csv` (flooronly column) as the
y-only comparator. Headline measured numbers:

| variant | median Z | p90 | max | n(Z > 20) | n(Z_I < Z_P) |
|---|---|---|---|---|---|
| (E) x=y=15 | 9.36 | 15.67 | 27.46 | 3 | 49/96 |
| (E) x=y=20 | 7.58 | 12.36 | 24.42 | 1 | 76/96 |
| (E) x=y=25 | 6.31 | 10.66 | 15.81 | 0 | 88/96 |
| (E) x=20, y=25 | 7.58 | 12.36 | 24.42 | 1 | 76/96 |
| x-only = (C), historical | 7.58 | — | — | — | 76/96 |
| y-only (floor 20) ≈ (A) | 18.84 | — | — | — | — |
| (B), for reference | 13.82 | 15.55 | 17.48 | 0 | 0/96 |

### physics-11  [high]  The symmetry with the pressure criterion is formal, not physical: only pressure possesses a damage-anchored absolute scale
- Where: `blastlib/processing/grids.py:206-216` (pressure band + floor),
  `docs/ALGORITHM.md:110-111` ("a 10 kPa band, below which load differences
  are structurally negligible"); IATG 02.20 Table 8 sidecar.
- What: the question rightly notes that physics-3's argument ("any absolute
  band's permitted relative error grows without bound") applies verbatim to
  the pressure criterion, which this audit did not flag. Resolved
  explicitly, in two legs — and the presumed defense ("the floor caps the
  band's unboundedness at the same value") is *not* the load-bearing one:
  - **Currency.** The pressure band's value, 10 kPa, is stated in the same
    physical currency as the damage-anchor ladder itself (IATG Table 8
    tiers are absolute side-on pressures: 2–3, 5, 9, 11, 16, 21, 70 kPa).
    The pressure guarantee beyond R_conv,P is therefore interpretable and
    *marginable*: "the free-field prediction errs by less than 10 kPa" can
    be carried directly into a Table 8 assessment, and a user who wants
    conservatism can add 10 kPa to the prediction. For impulse no damage
    currency exists — decision D8's own finding: impulse damage thresholds
    are absolute, target-specific, and non-Hopkinson-collapsible. "The
    prediction errs by less than 20 Pa·s/kg^(1/3)" cannot be translated
    into a damage statement for any target, and cannot be margined,
    because 20 Pa·s/kg^(1/3) is decisive for a light short-period target
    near its impulse asymptote and meaningless for a heavy target in the
    quasi-static regime. Same structure, but only one side has a value
    with physics in it.
  - **Relative unboundedness capped by the relevance quantum.** For
    pressure, exactly where the band becomes relatively loose (P_ff below
    ~10 kPa, Z ≳ 12), the permitted urban pressure of a converged cell is
    bounded by P_ff + 10 < 20 kPa, and the error is bounded by the
    framework's own relevance quantum — an under-prediction smaller than
    the level below which "load differences are structurally negligible".
    The floor clause and the band clause both derive from that one
    anchored number, which is what makes band = floor coherent. For
    impulse with x = y = 20 the same arithmetic runs — beyond Z ≈ 13.7 a
    violating cell needs I_urban ≥ I_ff + 20 scaled, i.e. urban/free-field
    ratio ≥ 1.91 at Z = 12, ≥ 2.02 at Z = 14, ≥ 2.31 at Z = 18 (computed,
    W = 500; x = 15 still permits 1.7–2.0×, x = 25 permits 2.1–2.6×) —
    but the cap it delivers, "error < 20 Pa·s/kg^(1/3)", is a quantum of
    nothing: no negligibility statement backs it (physics-1). The
    guarantee sentence "beyond R, free-field impulse is within
    20 Pa·s/kg^(1/3), or urban impulse is below 20 Pa·s/kg^(1/3)" is
    grammatically coherent and engineering-empty: both clauses are stated
    in a currency with no exchange rate to damage. (E) inherits physics-1
    twice — once per clause.
  - Corollary flagged for completeness (see physics-15): the pressure
    criterion's own guarantee must be worded as an error bound ("errs by
    < 10 kPa"), not as accuracy — it, too, permits ~2–3.5× relative
    deviations in the far field, bounded only absolutely.
- Evidence: permitted-ratio table computed from `free_field_data.csv`
  (values above); IATG tier list verified in the sidecar.
- Consequence: (E)'s guarantee cannot support the thesis sentence the
  radius exists for ("beyond R_conv, free-field methods may be used to
  assess blast loads for damage/safety-distance purposes").
- Options: (1) reject (E); (2) if the mirror form is kept for symmetry's
  sake, derive x from a target-class impulse-negligibility argument first —
  this audit found none that survives D8, and D8 is the owner's own
  decision.

### physics-12  [high]  Measured: (E) is the rejected criterion (C) with an inert floor bolted on — the under-prediction failure and the implausible ordering both return
- Where: scratchpad `mirror_variant_suite.csv` vs
  `conv_scaledband_clean.csv` (historical (C) on the clean store) and
  `outputs/tables/convergence_table_req_soft3.csv` (Z_P, and candidate-B
  column from `pfloor_variant_suite.csv`).
- What: the a-priori expectation in the question — that (E) with
  x = y = 20 would ride the floor to the (A)-like far contour (median
  ~18.6, max ~32, reviving the owner's Z = 32 objection) — is
  **contradicted by the measurement**. The band clause dominates, not the
  floor: (E) x=y=20 reproduces the historical scaled band per config
  (median 7.58 vs 7.58; median ratio E/C = 1.00; E ≤ C in 63/96, the floor
  only shaving edges), because beyond Z ≈ 13.7 the band converges every
  cell short of ~2× amplification, so the scan stops near where (C)
  stopped. The floor is nearly inert: x=20/y=25 is identical to x=20/y=20
  in 72/96 configs (max difference 0.51 in Z), and y-only would give
  median 18.84 — the OR takes the band's much smaller radius. Consequences
  measured:
  - The owner's Z = 32 objection does *not* return (only config_61 exceeds
    Z = 20, at 24.4; none at x = y = 25). But the escape is purchased by
    exactly the failure that motivated the 2026-09-28 revision: beyond
    (E)'s radius, cells at up to ~1.9–2.3× the free-field impulse count as
    converged (physics-11 numbers) — the under-prediction the owner
    rejected (C) for, verbatim.
  - The physically implausible ordering returns: Z_I < Z_P in 76/96 at
    x = y = 20 (88/96 at 25) — the pre-revision "impulse converges earlier
    than pressure" that the change note calls out ("reverberation feeds
    impulse long after peaks align"). Under (B): 0/96.
  - (E) < (B) in 85–96/96 (median ratio 0.58 at x = y = 20). The annulus
    between the two radii — median Z 7.6 to 13.8 — is territory where the
    urban peak pressure is largely ≥ 10 kPa (B ≈ the urban 10 kPa
    contour), i.e. *engineering-relevant by the framework's own anchor*,
    and where (E) licenses free-field impulse substitution with permitted
    errors up to ~2×. This is the concrete exposure: not far-field
    irrelevant cells, but relevant mid-field ones.
- Evidence: table and counts above, all recomputed from the named files.
  Corroboration only (not grounds — the verdict is physical): the owner's
  LOGO numbers for (E) degrade monotonically as the band loosens (13.9/11.1
  at x=y=15, 15.9/12.3 at 20, 17.4/13.6 at 25, vs 8.97/7.7 for (B)) — a
  radius that is a lawful function of the geometry groups should not lose
  lawfulness as its defining band is varied; this is what a
  criterion-artefact radius looks like.
- Consequence: adopting (E) would regenerate the impulse record onto
  radii that are the rejected 2026-07..09 record under a new name, with a
  weaker guarantee (the extra OR-clause only removes violations).
- Options: (1) reject (E); (2) if the owner wants the mirror anyway,
  publish the permitted-ratio profile (x/I_ff_scaled vs Z) next to every
  radius so the guarantee's actual strength is visible — this audit
  expects that display to be decisive on its own.

### physics-13  [medium]  Isolation is a product-design preference, not a physical virtue — and the isolated impulse-field product the owner wants already exists as (D), not (E)
- Where: the owner's stated motive; `docs/ALGORITHM.md` (shared estimator,
  exclusion radius), CLAUDE.md §0 aims 2–4.
- What: taken seriously on its merits. The convergence radius exists (per
  the proposal's aims) to mark where free-field *methods* suffice for
  damage and safety-distance assessment. Damage is a joint P–I property of
  one physical wave field; the physics offers no reason that boundary
  should decompose into two independent single-quantity boundaries, and
  the framework already shares the estimator, the exclusion radius and the
  K-rule between the two scans — isolation was never total. Worse for the
  isolation goal: aim 4 compares the two radii, which requires them to
  *mean the same thing*; (E) delivers symmetry of form with asymmetry of
  meaning (pressure's radius carries a damage-quantum error bound,
  impulse's an unanchored fidelity bound), so the isolated pair is less
  comparable, not more. The counter-view deserves its due: (B) is
  floor-dominated (accuracy clause trims median 1.5%), so R_conv,I,(B)
  measures the urban pressure field twice and the impulse field almost not
  at all — a real information cost, already owned by physics-4. But that
  is a *presentation* problem, not a physics failure: the criterion's
  question is "where is free-field impulse substitution safe", and a bound
  achieved by irrelevance is a valid bound. (E) is indeed "more of an
  impulse-field product" (band-dominated, physics-12) — but the metric it
  measures the impulse field with is the absolute band whose relative
  permissiveness grows without bound, i.e. the owner's own rejected
  yardstick. The honest isolated impulse-field measurement is the relative
  band (D), restricted to where it is measurable (Z ≤ 20), published as a
  *descriptive* companion — "where the impulse field actually merges" —
  alongside (B)'s engineering radius. That split gives the owner isolation
  where it is physically meaningful (field description) and the shared
  damage anchor where it is required (engineering boundary).
- Evidence: dominance measurements in physics-4 (B) and physics-12 (E).
- Consequence: how ch. 9 frames the two radii and their comparison.
- Options: (1) (B) as the radius of record + (D) as a descriptive column;
  (2) (B) alone with the physics-4 wording; (3) (E) — carries physics-11/12.

### physics-14  [medium]  No defensible anchor exists for the absolute impulse floor y; the co-location anchor (y = 25) is the pressure floor smuggled through the free-field curve, degraded in transfer — and empirically inert anyway
- Where: the owner's y candidates; `free_field_data.csv` mappings
  (recomputed: y = 20 → ff Z = 13.64–13.79; y = 25 → Z = 10.94–11.03 vs
  the pressure floor's Z = 11.3–12.1).
- What: y = 20 is the inherited calibration (physics-1) — no anchor.
  y = 25's co-location argument ("the free-field impulse level co-located
  with the damage-relevance range") is honest as *provenance*: it is
  transparent, fixed, and derived from the standard free-field mapping
  rather than from the urban pressure field, so the owner's isolation is
  indeed preserved in the measurement. But the physical content does not
  transfer. The co-location holds on the *free-field* curve; the floor is
  applied to the *urban* field, and the transfer is valid only where the
  urban I–P relationship matches the free-field one — which is precisely
  what urban channelling destroys, by this project's own headline finding
  (impulse amplification outlives pressure amplification; that is why (A)'s
  urban-impulse floor rode to Z 32 while the urban 10 kPa contour sits at
  ~14). Concretely: a location with urban I/W^(1/3) = 30 and urban
  P = 5 kPa passes y = 25's relevance test while the damage physics says
  irrelevant; a shielded location with urban P = 12 kPa and I/W^(1/3) = 20
  fails it while being pressure-relevant. The isolation is preserved in
  the arithmetic and lost in the meaning: the calibration is exactly where
  a standard may legitimately enter (as IATG enters the pressure floor);
  the measurement is where the urban field must be interrogated with a
  test that means something at that location, and an impulse level does
  not (physics-1). Verdict on y: the least-bad choice inside (E) is
  **y = 25** (honest provenance; also the only x = y variant with all 96
  radii ≤ 20) — and it does not matter, because the floor is nearly inert
  next to the band (x20/y25 ≡ x20/y20 in 72/96, max ΔZ = 0.51): the fatal
  clause of (E) is x, not y.
- Evidence: mappings and inertness counts above.
- Consequence: no (x, y) tuning rescues (E); see the verdict's trilemma.
- Options: none beyond those of physics-11/12.

### physics-15  [low]  Corollary surfaced by the symmetry question: the pressure criterion's guarantee must be worded as an absolute error bound, not as accuracy
- Where: `docs/ALGORITHM.md:110-111`; `blastlib/processing/grids.py:210-216`.
- What: examining the mirror forced an honest look at the pressure side,
  which the original audit scoped out. Beyond R_conv,P a converged cell may
  carry urban pressure up to P_ff + 10 kPa — at Z = 16–20 that is a
  permitted relative deviation of ~2.8–3.5×, and it can in principle move a
  location across IATG tiers (e.g. predicted 6 kPa, true 15.9 kPa spans the
  9/11/16 kPa tiers). The criterion is still defensible (physics-11:
  currency + relevance-quantum), but the thesis sentence for R_conv,P must
  read "beyond R_conv,P the free-field prediction errs by less than 10 kPa
  — one relevance quantum — " and not "is accurate"; a conservative user
  adds the quantum. This does not reopen the pressure record (bit-identical
  and out of this question's scope); it constrains wording only.
- Evidence: arithmetic from `free_field_data.csv` far-field P_ff values.
- Consequence: ch. 9 wording for the pressure radius; none numerical.
- Options: adopt the error-bound wording; optionally report the permitted
  absolute margin explicitly alongside safety-distance uses.

### Addendum verdict

**(E) is not physically sound for any (x, y).** The requirements it tries
to reconcile form a trilemma, and the tension is physical, not accidental.
For an impulse convergence radius one can have at most two of:

  (i)  an impulse-only criterion (isolation);
  (ii) a bounded-relative-error guarantee — "free field may be used beyond
       R" without under-prediction at any location that matters;
  (iii) radii that terminate at sensible distances inside the validated
       domain (Z ≤ 20).

(D) gives (i) + (ii) and fails (iii) (rides beyond the validated range in
channelling configs). (E) gives (i) + (iii) and fails (ii) — measured: it
reproduces the rejected (C) radii to a median ratio of 1.00 and permits
~2× under-prediction in mid-field territory that the framework's own anchor
declares relevant, while restoring the implausible Z_I < Z_P ordering in
76–88 of 96 configs. (B) gives (ii) + (iii) and concedes (i). (A) achieves
only (i) cleanly. The reason no (x, y) escapes: within the impulse field
alone, the only bounded-error convergence statement is relative accuracy;
relative accuracy does not terminate before the validated domain ends,
because urban impulse amplification persists (the project's own finding);
the only physical terminator of that ride is a relevance statement; and
relevance is pressure-bounded (physics-1). Isolation and the engineering
guarantee are therefore mutually exclusive for impulse — that is the plain
answer to the owner's "why does it have to depend on pressure": because
the question the radius answers ("does this location still matter?") is a
damage question, and damage questions are answered in pressure first.

Ranking after (E): **(B)** remains the physically correct criterion, with
the physics-4 wording and the physics-5/7/10 caveats; **(D)** is the
recommended *descriptive* companion if the owner wants an isolated
impulse-field product (Z ≤ 20 only, clearly not the engineering radius);
**(A)** and **(E)** are both physically unsound, for dual reasons — (A)
fails on the floor (unanchored relevance, unvalidated far field), (E) on
the band (unanchored fidelity, rejected guarantee). The pressure
criterion's own wording gains one obligation (physics-15). The owner
decides.

---

## Addendum 2: candidate (F), the absolute-impulse mirror  (2026-09-28, same day)

Owner's extension: the same two-clause impulse-only structure, in absolute
Pa·s rather than Hopkinson-scaled units:

    converged  iff  |I_urban − I_ff| < x [Pa·s]   OR   I_urban < y [Pa·s]

Implicit argument, treated fairly: real damage thresholds ARE absolute —
P–I curves for actual targets are stated in Pa and Pa·s — so an absolute
floor is arguably more damage-meaningful than any scaled level (which D8
found meaningless). Assessed on the repo's own measurements plus recomputed
free-field mappings; (F) itself was not run on the fields, and does not
need to be — its failure is provable from the collapse arithmetic alone.

### physics-16  [high]  (F) is Hopkinson-inadmissible: an absolute clause makes the criterion itself a function of W and breaks the Z collapse the framework rests on
- Where: `blastlib/constants.py:84-92` (the measured 3.10× argument, made
  for the band and applying identically to a floor);
  `blastlib/constants.py:121-127` (D8's measured consequence for the
  129 Pa·s human floor); recomputation from `free_field_data.csv`.
- What: Hopkinson–Cranz says two geometrically scaled configurations at
  equal Z have identical scaled fields — so any *criterion* applied to
  those fields must be W-invariant in scaled space, or two physically
  identical (scaled) cities receive different Z radii purely because the
  measuring stick changed with W. An absolute band or floor is per-weight
  equivalent to a scaled level x/W^(1/3) (resp. y/W^(1/3)), which varies
  by (1500/50)^(1/3) = 3.107× across this study's weights. This is not a
  small distortion of the collapse; it is its removal: R_conv/W^(1/3)
  acquires an explicit W-dependence that is not a function of the Π
  groups, and the entire regression layer (fits over 96 configs in
  (ρ, H/s, Π₂)) loses its object. The repo already measured exactly this
  for the band: a fixed Pa·s band picks a different scaled contour per
  weight — Z = 4.98/8.65/10.86/13.77/15.78 across W = 50..1500
  (constants.py:88-92), which this audit reproduced independently: those
  five values are precisely the free-field contour I_ff = 200 Pa·s
  (recomputed from `free_field_data.csv`, matching to 0.01 in Z). For the
  floor, D8 measured the consequence on the concrete candidate
  y = 129 Pa·s (the UFC Fig. 1-2 human i_min at 70 kg): it "would cut 17
  of the 24 W = 50 configurations [and] break the Z collapse the whole
  regression framework rests on" (constants.py:121-127).
- Evidence (recomputed): y = 129 Pa·s ≡ scaled floor 35.0 (W = 50) down
  to 11.3 (W = 1500) — the same criterion sits at free-field Z = 7.85 for
  the small charge and *beyond the validated Z = 20 table edge* for
  W = 1000 and 1500 (I_ff at Z = 20 is 138 and 158 Pa·s > 129). With the
  measured floor elasticity d ln R / d ln floor ≈ −0.9 (decision suite),
  the effective-floor spread 35.0/11.3 = 3.1× implies per-weight radius
  shifts of order 3.1^0.9 ≈ 2.8× at fixed geometry — larger than the
  entire geometry-driven dynamic range of the measured radii (B: 7.6 to
  17.5). The W-dependence injected by the clause would dominate the
  physics the study exists to map.
- Consequence: under (F) no single R_conv,I table collapses in Z; the
  quad/unified/any regression over the 96 configs is structurally
  mis-specified; cross-weight comparisons (the study's central axis)
  become criterion artefacts.
- Options: (1) reject (F) as a convergence criterion — this is the only
  physics-consistent option found; (2) if absolute levels are wanted, use
  them where they belong (physics-17), not in the field-collapse rule.

### physics-17  [medium]  The instinct behind (F) is correct — absolute P–I currency is damage-meaningful — but it belongs in aim-4 per-target products computed ON the fields, not in the convergence rule
- Where: `blastlib/constants.py:115-133` (D8 and the R_human deferral);
  CLAUDE.md §0 aims 4–5; UFC 3-340-02 Fig. 1-2 sidecar.
- What: the owner's implicit argument deserves its due, and it is half
  right. Yes: real damage thresholds are absolute, and D8's finding that
  scaled impulse levels are damage-meaningless is exactly the observation
  that motivates (F). But the same D8 record closes the other half:
  absolute impulse is target-meaningful only *jointly with pressure* on a
  target-specific P–I curve — the floor y alone is still not a damage
  statement (the pressure asymptote gates it; physics-1), and no
  target-independent absolute y exists: candidate levels span orders of
  magnitude across target classes (glazing ~tens of Pa·s, human lung
  ~129 Pa·s at an arbitrary 70 kg body mass — the arbitrariness D8 cited
  when it evaluated and REJECTED that floor — structural panels hundreds
  to thousands). Any single y silently picks one target and one parameter
  value. The constructive reading is therefore the honest one: **(F) is
  not a convergence criterion; it is the first step toward the per-target
  damage products of aim 4** — R_human, glazing distances, per-tier
  safety contours — which are correctly computed by evaluating the local
  (P, I) pair of the *urban field itself* against the full absolute P–I
  curve of a named target, per charge weight, with no Z collapse claimed.
  There, absolute Pa and Pa·s are not a defect but the point; the
  deliverable is per-weight contours, which is what a non-collapsible
  quantity honestly yields. The division of labour: the stage-3/4
  field-collapse rule must be Hopkinson-invariant (relative band +
  pressure-anchored floor, candidate B); the aim-4 product layer is where
  absolute target physics enters. (F) collapses the two layers into one
  and inherits the failure modes of both — the unanchored band of (E) in
  even less defensible units, plus the broken collapse of physics-16.
- Evidence: D8 record as cited; the per-weight contour computation of
  physics-16 (y = 129 → Z from 7.9 to beyond 20 across W).
- Consequence: none numerical if rejected; a positive programme for aim 4
  if the owner takes the constructive reading.
- Options: (1) reject (F) for R_conv and register the absolute-P–I
  per-target product as the planned aim-4 deliverable (R_human et al.,
  already deferred by D8); (2) nothing else survives the collapse
  argument.

### Addendum 2 verdict — final ranking over all candidates

(F) is the weakest candidate as a convergence criterion: it fails before
measurement, on Hopkinson admissibility alone (physics-16) — a failure
mode none of (A)–(E) has — and on top of it would inherit (E)'s unanchored
band (physics-11) in units the repo has already measured to be
inadmissible (3.10×, constants.py:84-92). Its underlying instinct
(absolute damage currency) is right and already has a home: the aim-4
per-target P–I products on the urban fields (physics-17), where this
audit encourages the owner to spend it.

Final physics ranking, all candidates, as a convergence criterion:

1. **(B)** — physically correct within the declared structural damage
   scope; adopt with the physics-4 wording and the physics-5/7/10 caveats.
2. **(D)** — recommended descriptive companion only ("where the impulse
   field actually merges", Z ≤ 20); not the engineering radius.
3. **(A)** — unsound: unanchored relevance floor, third of the record in
   the unvalidated far field (physics-1/2).
4. **(E) ≈ (C)** — unsound: reproduces the rejected band (ratio 1.00),
   guarantee empty in an unanchored currency (physics-11/12).
5. **(F)** — inadmissible: breaks the Z collapse itself (physics-16);
   redirect its instinct to aim-4 per-target products (physics-17).

The owner decides.
