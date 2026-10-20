# Free-field table: ring mean of the reference field (2026-10-20)

Closes the provenance gap of PHY-16 (`docs/audit/2026-09-27/physics.md`).
Commit of the table: `219c13e`. Previous, axis-sampled table: `4300e59`
(kept locally as `data/free_field_data_OLD.csv`).

## How the table is built

Scripts: `docs/audit/2026-10-20/scripts/` — run from the repo root:

```
python docs/audit/2026-10-20/scripts/ff_gauges.py . <out>
python docs/audit/2026-10-20/scripts/ff_ring.py   . <out>
```

`<out>/free_field_data_ring_mean.csv` reproduces `data/free_field_data.csv`
exactly (checked 2026-10-20).

1. **Grid per (W, Z).** The FF gauges in `data/Gauges/ff_*kg/{1,2,3}` (D44
   runs, 14–15/10) sit on the axis at r = Z·W^⅓, Z = 1–30. For each (W, Z) the
   finest grid is taken whose gauge was not clamped to the box edge and does
   not lie in the last metre of the box. The last fine cell is corrupted:
   at W = 1000, Z = 10 (r = 99.975 m) the fine grid gives I = 212 Pa·s against
   274 on the medium grid.
2. **Ring mean.** On that grid, the mean of `refP`/`refI` (`data/raw_npz`)
   over all cells with |r − Z·W^⅓| < h, each cell corrected to r with the
   local log-log slope of the ring. 75 to several thousand cells per ring
   (median 977).

## Checks

- **Gauge vs VTK, same cell:** pressure 0.00% at all 150 points; impulse
  0.00% except Z = 1–3 (gauge up to 1.3% lower, W = 50, Z = 1). No gauge has
  its peak at the last sample (no run was cut).
- **Ring mean vs axis (gauge):** pressure +1% to +9%, growing with Z;
  impulse within ±1%.
- **Anisotropy, diagonal (45° ± 5°) vs axis (0°/90° ± 5°):** pressure 3–9% at
  Z = 3–8, 4–13% at Z = 10–20, 16–18% at Z = 30; impulse within ±2%.
- **Old table vs gauges (Z ≤ 20):** median 0.23% (P), 0.17% (I); up to 2.7%
  at Z = 1–2. In pressure only, just past the fine box: W = 1000, Z = 10
  −7.9%; W = 500, Z = 13 −6.3%.

## Known weakness: pressure step at the grid seams

Within one grid the local slope dlnP/dlnZ is about −1.5. At the switch from
the fine to the medium grid it is −3.66 (W = 500, Z 12→13) and −3.02
(W = 1000, Z 9→10). On the fine grid P at fixed Z rises with W by +7% to
+15% against W = 50; once a weight is on the medium grid it sits −5% to −11%
below. The ring mean does not remove the step (slopes −3.30 and −2.70). The
scaled impulse is equal across weights within ~1% throughout.

R_conv and Λ compare cell by cell on the same grid, so the step cancels in
them. It does enter every use of the table itself.

## Numbers derived from the table, old → new

| quantity | old table | ring-mean table |
|---|---|---|
| Z where P_ff = 10 kPa, per W (50/250/500/1000/1500) | 11.33 / 11.97 / 12.13 / 11.27 / 11.27, mean 11.59 | 11.71 / 12.24 / 12.19 / 11.39 / 11.56, mean 11.82 |
| I_ff/W^⅓ there [Pa·s/kg^⅓] | 24.33 / 22.99 / 21.87 / 24.32 / 24.41, mean 23.58 | 23.58 / 22.38 / 22.42 / 24.14 / 23.80, mean 23.26 |
| CV of P across W (Z = 1–20) | median 4.7%, max 8.7% | median 4.1%, max 7.3% |
| CV of I/W^⅓ across W | median 0.3%, max 1.6% | median 0.3%, max 0.6% |
| Z_conv,P < Z(P_ff = 10 kPa), req_soft3 | 83/96 | 85/96 |
| Z_conv,P < Z(P_ff = 10 kPa), reqdir_soft3 | 83/96 | 86/96 |
| CFD Z where I/W^⅓ = 20 | 13.64–13.79 | 13.70–13.82 |

The impulse floor of D35 stays at 23.6 Pa·s/kg^⅓ (owner, 2026-10-20).

## Effect on the record

Phase 1 re-run with the new table (2026-10-20): in both req_soft3 and
reqdir_soft3 only the `P_ff`/`I_ff` columns of `max_radius_per_Z_*.csv` move
(P_ff median +3.86%, max 9.55%; I_ff median +0.03%, max 3.34%, reqdir_soft3),
plus 10 MaxR values at Z = 1 in req_soft3 (max −2.9%, outside the fit
domain). R_conv, the Z_urban fit rows, CV and coefficients are unchanged.
The table fell back for 0.0% of the exceedance levels.
The CFD-vs-KB comparison was re-run on the new table; see
`cfd_vs_kb_ufc_note.md`.
