# CFD free field vs UFC 3-340-02 Kingery-Bulmash curves (PHY-06)

Date: 2026-09-27. Closes the audit's demand that the CFD-vs-standard
comparison be made against a registered source instead of memory-entered
coefficients.

## Sources and method

- Standard: UFC 3-340-02 Fig. 2-15 (positive-phase shock parameters,
  hemispherical TNT surface burst — the configuration the simulations
  model), exact curve points from the owner-supplied DPlot export
  `docs/references/02_015.GRF` (200 points per parameter; `02_007.GRF`
  holds Fig. 2-7, free air, for reference). The registered PDF is the
  22 May 2005 DRAFT; verify against the 2008 edition before final
  citation.
- CFD: `data/free_field_data.csv` (reference simulations, P [kPa] and
  I [Pa.s] per W in {50..1500} at integer Z).
- Unit conversions: Z x 0.3048/lb^(1/3) (ft/lb^(1/3) -> m/kg^(1/3));
  psi -> kPa x6.894757; psi.ms/lb^(1/3) -> Pa.s/kg^(1/3) x8.9690.
  Log-log interpolation of the UFC curves at the CFD Z values.
- Full table: `cfd_vs_kb_ufc215.csv` (per Z: KB and CFD values, ratios,
  min/max over W).

## Results

CFD/KB ratio (mean over the five charge weights):

| Z | pressure | scaled impulse |
|---|---|---|
| 1 | 1.00 | 0.84 |
| 2-8 | 0.91-0.93 | 0.83-0.92 |
| 10 | 0.86 | 0.88 |
| 12 | 0.82 | 0.88 |
| 16 | 0.74 | 0.88 |
| 20 | 0.70 | 0.87 |

Z = 2..16 summary: pressure median 0.889 (range 0.740-0.930), impulse
median 0.884 (range 0.833-0.915).

- **Pressure:** the CFD runs ~7-9% below KB in the near/mid field and the
  deficit grows with distance (30% at Z = 20) — the signature of shock
  front smearing on a mesh fixed in metres (numerical dissipation of the
  peak), consistent with PHY-02/PHY-03.
- **Impulse:** a nearly flat ~12% deficit — the integral survives the
  discretisation far better than the peak, as expected.
- This CONFIRMS the audit's memory-based estimate (pressure 10-32% low,
  impulse 10-13% low) and replaces it with a sourced measurement.

## Threshold locations (D8b context)

| contour | KB (UFC 2-15) | CFD field |
|---|---|---|
| P = 10 kPa | Z = 13.4 | Z = 11.3-12.1 |
| I/W^(1/3) = 20 Pa.s/kg^(1/3) | Z = 15.7 | Z = 13.6-13.8 |

Thesis-facing consequence: the 10 kPa and thr_I = 20 criteria are
CFD-FIELD thresholds. Stated on the KB scale they sit at the equivalent
free-field contours Z ~ 13.4 and ~ 15.7 — i.e. the criteria are slightly
more permissive in KB terms than their CFD locations suggest. Any thesis
sentence anchoring a threshold to a standard damage level (e.g. the IATG
02.20 Table 8 bracket) should carry this one-line caveat.

## Update 2026-10-20: re-run on the ring-mean table

`data/free_field_data.csv` is now the ring mean of the reference field over
all directions, Z = 1–30 (`free_field_table_note.md`); the table above was
measured on the earlier axis-sampled table (`4300e59`), which lies 1–9% below
the ring mean in pressure. `cfd_vs_kb_ufc215.csv` was regenerated with
`docs/audit/2026-09-27/scripts/kb_crosscheck.py` and now runs to Z = 30.

CFD/KB ratio (mean over the five charge weights), old → new table:

| Z | pressure | scaled impulse |
|---|---|---|
| 1 | 0.997 → 1.056 | 0.840 → 0.843 |
| 2 | 0.906 → 0.936 | 0.833 → 0.828 |
| 4 | 0.920 → 0.945 | 0.915 → 0.908 |
| 8 | 0.918 → 0.934 | 0.892 → 0.890 |
| 10 | 0.860 → 0.872 | 0.884 → 0.885 |
| 12 | 0.819 → 0.849 | 0.877 → 0.882 |
| 16 | 0.740 → 0.774 | 0.876 → 0.877 |
| 20 | 0.695 → 0.736 | 0.874 → 0.875 |
| 30 | — → 0.656 | — → 0.878 |

Z = 2..16 summary: pressure median 0.889 → 0.909 (range 0.740–0.930 →
0.774–0.948); impulse median 0.884 → 0.885 (range 0.833–0.915 →
0.828–0.908). The reading is unchanged: pressure ~5–7% below KB in the
mid field with the deficit growing with distance, impulse a flat ~12% below.

Threshold locations on the new table: CFD P = 10 kPa at Z = 11.4–12.2
(KB 13.4); CFD I/W^(1/3) = 20 at Z = 13.7–13.8 (KB 15.7).
