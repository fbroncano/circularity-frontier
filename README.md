# Circularity Frontier — Selective On-Site Recycling and the Equity Cost of CDW Mandates

Per-capita cost and CO2 indicators of the construction and demolition waste (CDW) loop, and a
scenario model of **on-site (mobile) recycling** for the 383 municipalities of Extremadura
(SW Spain), assigned to 32 CDW treatment plant groups over the real road network.

This repository is the public, self-contained companion of the manuscript *"Selective On-Site Recycling Removes the Equity Cost of Construction Waste Mandates in Low-Density Regions"*,
submitted to *Resources, Conservation & Recycling*. It is released to support the
manuscript's Data Availability statement.

## What it does

For every municipality it builds two per-capita indicators of the current, plant-based CDW
loop (generation → treatment → reuse of recycled aggregate at worksites) and then evaluates
four policy scenarios of on-site crushing (mobile units) against it:

| Scenario | Meaning |
|---|---|
| S0 | No on-site crushing; all CDW follows the plant route (current baseline). |
| S1 | Blanket mandate: a share `p` of every municipality's CDW is crushed on site, regardless of viability. |
| S2 | Selective: on-site only where it improves per-capita cost **or** direct CO2 without worsening the other (Pareto-dominance rule). |
| S2_cap | S2 with a hard annual fleet capacity `CAP_ANUAL_T` (t/yr); capacity is allocated to the municipalities with the largest unit cost saving. |
| S3 | Selective with the fixed campaign cost `F` shared at the level of each plant catchment ("cluster"): a rotating/shared mobile unit. |

A differential credit for avoided natural-aggregate production (EF5_NA) applies to net CO2 of
on-site municipalities only, after selection, and never drives the selection rule. Regional
metrics are population-weighted; losers (municipalities whose per-capita cost exceeds S0) are
tracked to expose the equity failure of blanket mandates.

## Method (summary)

Generation is `G_m = 0.5 · pop_m` (t/yr). For each municipality *m* assigned to plant *p* with
road distance `d_planta,m`, the return haul `d_obra` is the population-weighted mean road
distance of the plant's catchment, and `d_tot,m = d_planta,m + d_obra`. Per-capita loop cost and
CO2 of the plant route are:

```
LC_m (€/inhab·yr) = (C_trat,m + C_trans,m + 0.35 · d_obra) · 0.5
CE_m (kg/inhab·yr) = 0.5 · (EF1 · d_tot,m + E_PLANT)
```

where `0.35` €/(t·km) is the transport tariff of the source article, `EF1` the truck emission factor and
`E_PLANT` the stationary plant factor. On-site crushing of the volume `V_m = G_m · p` costs
`c_b = F/(G_m·p) + v_op` €/t (S1/S2; `F` shared over the cluster pool in S3) and emits EF3;
mixed per-capita indicators follow `LC_m(p) = p·c_b·0.5 + (1−p)·LC_m` and
`CE_m(p) = p·EF3·0.5 + (1−p)·CE_m − credit_m`, with
`credit_m = (rec_share_onsite − rec_share_base) · p · EF5_NA · 0.5` (kg/inhab·yr). Regional
figures are `Σ LC_m · pop_m` (€/yr) and `Σ CE_m · pop_m / 1000` (t CO2/yr). Robustness is
tested over a 378-combination grid (`v_op × F × EF1 × p`; see `results/`).

## Data provenance

- `data/datos_red_real_municipios.csv` is a **derived, anonymised** dataset of the municipal
  file published with the source article: Torrecilla-Pinero, J.A., Ceballos-Martínez, J.M., Plaza Caballero,
  P., Cruces López, A., Cuartero, A. (2026). *Spatial cost inequality in construction and
  demolition waste management in sparsely populated regions: Evidence from Extremadura,
  Spain*. Waste Management Bulletin 4(3):100355, DOI
  [10.1016/j.wmb.2026.100355](https://doi.org/10.1016/j.wmb.2026.100355) — open access,
  CC BY 4.0.
- The columns identifying the treatment operators (`planta_nombre`, `planta_municipio`) were
  removed; `planta_id` is retained as an anonymous key. See `data/README.md`.
- No personal data are included; municipality-level aggregates only.

## Repository structure

```
.
├── README.md                       # this file
├── LICENSE                         # MIT (code)
├── .zenodo.json                    # Zenodo deposit metadata
├── scripts/
│   ├── model_sensibilidad.py       # model + sensitivity analysis (Python ≥3.8, stdlib only)
│   └── fig3_mapas.py               # figure 3, municipal maps (needs matplotlib)
├── data/
│   ├── datos_red_real_municipios.csv   # anonymised municipal input (CC BY 4.0, from the source article)
│   ├── blender_data.json           # municipal polygons and regional outline (figure 3)
│   └── README.md                   # provenance, licence and anonymisation note
└── results/
    ├── p_sensibilidad.csv          # penetration sweep p = 0.05–1.00, baseline parameters
    ├── resumen_grid_sensibilidad.csv  # full 378-combination sensitivity grid
    ├── base_municipios_p0*.csv     # per-municipality tables, one per penetration level
    ├── sensibilidad_capacidad.csv  # fleet-capacity sweep
    ├── sensibilidad_EF5_recshare.csv  # avoided-aggregate credit sweep
    ├── resumen_modelo.txt          # full run log
    ├── fig1..fig4                  # manuscript figures (fig3 also as PDF)
    └── README.md                   # column documentation
```

## Requirements and how to run

- Python ≥ 3.8, **standard library only**. No installation required.
- Run from the repository root:

```bash
python3 scripts/model_sensibilidad.py
```

- The script reads `data/datos_red_real_municipios.csv`, prints a text log and writes all
  outputs into `results/` (the two shipped result tables are regenerated byte-for-byte).
- **matplotlib is optional.** If it is not installed the script prints a notice and produces
  the CSV and text outputs only (no figures). If it is installed (`pip install matplotlib`),
  figures 1, 2 and 4 (PNG) are also written.
- Figure 3 (municipal maps) is produced by a separate script, which reads the municipal
  polygons in `data/blender_data.json` and writes both PDF and PNG into `results/`:

```bash
python3 scripts/fig3_mapas.py
```
- Runtime is a few seconds to a few minutes depending on the machine (grid = 378 combinations
  + sweeps).

## Main parameters (base values and ranges)

| Parameter | Description | Base | Range / sweep |
|---|---|---|---|
| `v_op` | Variable cost of mobile crushing (€/t) | 12 | 8–18 |
| `F` | Fixed campaign cost of a mobile unit (€) | 2,500 | 1,250–5,000 |
| `EF1` | Truck transport emission factor (g CO2/(t·km)) | 60 | 30–120 |
| `E_PLANT` | Stationary recycling plant emission factor (kg CO2/t) | 2.5 | 1–6 (literature) |
| `EF3` | Mobile crushing emission factor (kg CO2/t) | 1.3 | — |
| `EF5_NA` | Avoided natural-aggregate production (kg CO2/t, placeholder) | 4.0 | 2–8 |
| `rec_share_base` | Fraction of CDW currently recycled via plant and used in works | 0.6 | — |
| `rec_share_onsite` | Fraction recovered when crushed on site | 0.85 | — |
| `CAP_ANUAL_T` | Annual fleet capacity for S2_cap (t/yr) | 200,000 | 50,000–400,000 |
| `p` | On-site penetration share | — | 0.05–1.00 (grid: 0.1–0.7) |
| `DOT` | CDW generation rate (t/(inhab·yr)) | 0.5 | — |

All parameter values, derivations and literature sources are documented in the manuscript
(methods) and in the module docstring of `scripts/model_sensibilidad.py`.

## Outputs

The full run writes into `results/`: the two sensitivity tables shipped here, per-municipality
tables for the base parameters at each grid penetration `p`, capacity and EF5/rec_share sweeps,
and (with matplotlib) the PNG figures used in the manuscript. Column definitions: see
`results/README.md`.

## License

- **Code** (this repository's scripts): MIT — see `LICENSE`.
- **Data** (`data/datos_red_real_municipios.csv`): CC BY 4.0 (derived from Torrecilla-Pinero et al., 2026,
  DOI 10.1016/j.wmb.2026.100355). See `data/README.md`.

## How to cite

If you use this repository, please cite (1) the article, (2) the source dataset, and
(3) this software release:

> Broncano, F., Plaza-Caballero, P., Cuartero, A., Ceballos-Martínez, J.M.,
> Torrecilla-Pinero, J.A. Selective On-Site Recycling Removes the Equity Cost of Construction Waste Mandates in Low-Density Regions.
> *Resources, Conservation & Recycling* (under review). (DOI pending.)
>
> Torrecilla-Pinero, J.A., Ceballos-Martínez, J.M., Plaza Caballero, P., Cruces López, A.,
> Cuartero, A. (2026). Spatial cost inequality in construction and demolition waste management
> in sparsely populated regions: Evidence from Extremadura, Spain. *Waste Management
> Bulletin*, 4(3), 100355. https://doi.org/10.1016/j.wmb.2026.100355
>
> Broncano, F., Plaza-Caballero, P., Cuartero, A., Ceballos-Martínez, J.M.,
> Torrecilla-Pinero, J.A. (2026). Circularity Frontier: per-capita cost and CO2 indicators of the construction and demolition waste loop and on-site recycling scenarios, Extremadura, Spain (Version 1.0.0) [Software]. Zenodo.
> https://doi.org/[Zenodo DOI]

## Reproducibility note

The two result tables shipped in `results/` are byte-identical to the output of
`python3 scripts/model_sensibilidad.py` run from this repository (verified with the released
anonymised input). No randomness or platform-dependent behaviour is used in the model.
