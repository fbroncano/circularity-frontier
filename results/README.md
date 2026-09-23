# results/ — shipped model outputs

Everything in this folder is the output of a full run, and is the exact material backing the
manuscript figures and tables. The two summary tables documented below, `p_sensibilidad.csv`
and `resumen_grid_sensibilidad.csv`, are **byte-identical** to a fresh run of
`python3 scripts/model_sensibilidad.py` from the repository root (verified).

The folder also holds the per-municipality tables `base_municipios_p0*.csv` (one per
penetration level), the capacity and EF5/rec_share sweeps `sensibilidad_capacidad.csv` and
`sensibilidad_EF5_recshare.csv`, the run log `resumen_modelo.txt`, and the four manuscript
figures. Figures 1, 2 and 4 come from `model_sensibilidad.py`; figure 3, the municipal maps,
comes from `scripts/fig3_mapas.py` and is the only one shipped as PDF as well as PNG.

## `p_sensibilidad.csv` — penetration sweep (baseline parameters)

One row per penetration share `p` from 0.05 to 1.00 (step 0.05) at the baseline parameters
`v_op = 12 €/t`, `F = 2,500 €`, `EF1 = 60 g CO2/(t·km)`, `E_PLANT = 2.5 kg CO2/t`,
`EF5_NA = 4 kg CO2/t`, `rec_share_base = 0.6`, `rec_share_onsite = 0.85`,
`CAP_ANUAL_T = 200,000 t/yr`. Columns:

| Column(s) | Description |
|---|---|
| `p` | On-site penetration share of municipal CDW generation |
| `Coste_regional_S0`, `Coste_S1`, `Coste_S2`, `Coste_S2_cap`, `Coste_S3` | Population-weighted regional annual cost per scenario (€/yr) |
| `CO2_S0_t`, `CO2_S1_t`, `CO2_S2_t`, `CO2_S2_cap_t`, `CO2_S3_t` | Regional net CO2 per scenario (t/yr), net of the EF5 avoided-aggregate credit |
| `n_onsite_S1`, `n_onsite_S2`, `n_onsite_S2_cap`, `n_onsite_S3` | Municipalities with on-site crushing per scenario (out of 383) |
| `n_perdedores_S1`, `n_perdedores_S2`, `n_perdedores_S2_cap`, `n_perdedores_S3` | "Losers": municipalities whose per-capita cost exceeds their S0 value |

## `resumen_grid_sensibilidad.csv` — full sensitivity grid

Full grid used for robustness: `v_op ∈ {8, 10, 12, 14, 16, 18}` €/t ×
`F ∈ {1,250, 2,500, 5,000}` € × `EF1 ∈ {30, 60, 120}` g CO2/(t·km) ×
`p ∈ {0.1, ..., 0.7}` = **378 rows**, with fixed `rec_share_base = 0.6`,
`rec_share_onsite = 0.85`, `EF5_NA = 4.0 kg CO2/t`, `CAP_ANUAL_T = 200,000 t/yr`. Columns:

| Column(s) | Description |
|---|---|
| `v_op`, `F`, `EF1`, `p` | Grid parameters (see main `README.md`) |
| `rec_share_base`, `rec_share_onsite`, `EF5_NA`, `CAP_ANUAL_T` | Values held fixed in the grid |
| `Coste_regional_S0`, `Coste_S1`, `Coste_S2`, `Coste_S2_cap`, `Coste_S3` | Regional annual cost per scenario (€/yr) |
| `CO2_S0_t`, `CO2_S1_t`, `CO2_S2_t`, `CO2_S2_cap_t`, `CO2_S3_t` | Regional net CO2 per scenario (t/yr) |
| `n_onsite_S1`, `n_onsite_S2`, `n_onsite_S2_cap`, `n_onsite_S3` | Municipalities with on-site crushing per scenario |
| `n_perdedores_S1`, `n_perdedores_S2`, `n_perdedores_S2_cap`, `n_perdedores_S3` | Cost "losers" per scenario |
| `pct_mejorados_S2` | Percentage of municipalities improved by S2 in at least one objective |

Region totals across all rows: 383 municipalities, 1,102,410 inhabitants, 551,205 t CDW/yr,
32 plant groups (catchments/clusters).
