# Reference documents

Agents: read this file before any task. Match the task against "Use for" and "Keywords", then Grep the .txt sidecar and read only the relevant pages. Cite the document in code comments as given in "Cite as". If code and document disagree, report it; do not guess.

## isiems-paper-v2
- File: ISIEMS_Paper_v2.pdf (text: ISIEMS_Paper_v2.txt)
- Covers: the owner's conference paper draft (ISIEMS 20) presenting the parametric study: idealised urban model, staged ViperBlast methodology, the three scaled parameters, the convergence-radius criteria (Eq. 2) and estimator (Eq. 3), closed-form R_conv fits (Eq. 6-7, Table 2), LOGO validation (Fig. 4). **Results quoted are from the pre-2026-09-27 record** (old mask, old impulse power law) — do not treat its numbers as current; the correction list is in the 2026-09-27 session worklog.
- Use for: cross-checking thesis/paper claims against the current record; keeping paper and repo terminology aligned (s-tilde = Pi2, Λ, ξ).
- Cite as: ISIEMS Paper v2 (draft), p. N
- Keywords: ISIEMS, conference paper, convergence radius, scaled street width, canyon aspect, LOGO, ViperBlast, amplification factor
## ufc-3-340-02
- File: ufc_3_340_02.pdf (text: ufc_3_340_02.txt; exact curve data:
  02_007.GRF = Fig. 2-7 free air, 02_015.GRF = Fig. 2-15 surface burst —
  DPlot text format, 200 points per parameter, US units; parsed by
  docs/audit/2026-09-27/scripts/kb_crosscheck.py)
- Covers: UFC 3-340-02, "Structures to Resist the Effects of Accidental Explosions" (**this copy is the 22 May 2005 DRAFT** — verify quoted values against the official 5 Dec 2008 edition before final thesis citation). 1943 pages. Chapter 2: airblast phenomena — free-air and surface-burst Kingery-Bulmash parameter curves (Fig. 2-7 free-air; Fig. 2-15 positive-phase and Fig. 2-16 negative-phase shock parameters for hemispherical TNT surface burst: peak overpressure, scaled impulse, arrival/duration vs scaled distance), reflection factors, pressure-time histories, gas pressures, loads on structures. Later chapters: structural response, dynamic design of concrete/steel, fragment effects, damage/response criteria.
- Use for: any task that compares the CFD free field against the standard curves (audit PHY-06 — the CFD-vs-KB cross-check table), verifies Kingery-Bulmash coefficients or reads P/I values at a scaled distance (the audit's memory-entered KB values must be re-derived from here), anchors thresholds to standard shock parameters, or discusses reflected-pressure/impulse loading of building faces.
- Cite as: "UFC 3-340-02 (2005 draft), Fig. 2-15" (or the specific figure/section; replace with the 2008 edition reference for the thesis)
- Keywords: UFC 3-340-02, TM 5-1300, Kingery-Bulmash, free-air burst, surface burst, hemispherical TNT, peak overpressure, scaled impulse, scaled distance, positive phase, negative phase, reflection factor, pressure-time, blast loads, accidental explosions

## iatg-02.20
- File: IATG-02.20-Quantity-separation-distances-IATG-V.3.pdf (text: IATG-02.20-Quantity-separation-distances-IATG-V.3.txt)
- Covers: UN IATG 02.20, 3rd edition, March 2021 — quantity and separation distances for ammunition storage. Hopkinson-Cranz scaled-distance QD formulation (Table 1, p. 11) with regional coefficient Q values (Tables 2-3); types of quantity distance (inside/outside, process building, inter-magazine, public traffic route, inhabited building distance — IBD, p. 9); **Table 8 (pp. 17-19): expected damage and injury effects for HD 1.1 at each QD tier, each tier anchored to a peak side-on overpressure level — 2-3, 5, 9, 11, 16, 21 and 70 kPa**; QD matrices by exposed-site type (annexes); aggregation and rounding rules; underground storage QDs.
- Use for: any task that anchors a pressure threshold to a damage level (the 10 kPa convergence band, audit decision D8/CHO-02), derives or discusses safety distances (proposal aim 4), compares urban safety distances with standard QD practice, or needs an authoritative scaled-distance Q-coefficient table.
- Cite as: "IATG 02.20:2021[E], 3rd ed., Table 8" (or the specific table/clause)
- Keywords: IATG, quantity distance, separation distance, inhabited building distance, IBD, PTRD, IMD, side-on overpressure, kPa, damage level, injury, Hopkinson-Cranz, scaled distance, Q coefficient, HD 1.1, safety distance, magazine, UNODA
