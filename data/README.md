# data/ — municipal input dataset

## File: `datos_red_real_municipios.csv`

One row per municipality (383 municipalities of Extremadura, Spain), derived from the
municipal file published with the open-access source article (see provenance below).
Field layout (anonymised, see note):

| Column | Description | Units |
|---|---|---|
| `municipio` | Municipality name | — |
| `poblacion` | Population | inhabitants |
| `planta_id` | Identifier of the assigned CDW treatment plant group (32 groups; integer key, operator names withheld) | — |
| `distancia_km` | Road-network distance from the municipality to its assigned plant group | km |
| `produccion_t` | Annual CDW generation (`0.5 t/(inhab·yr) × poblacion`) | t/yr |
| `tkm` | Transport intensity (`produccion_t × distancia_km`) | t·km |
| `C_trans` | Unit transport cost at the source-article tariff of 0.35 €/(t·km) | €/t |
| `C_trat` | Unit treatment cost at the plant | €/t |
| `C_tot` | Total unit cost reported by the source dataset (`C_trans + C_trat` plus any fixed surcharge) | €/t |

The model script reads `municipio, poblacion, planta_id, distancia_km, produccion_t, C_trat,
C_trans`; the remaining columns are kept for transparency and reuse.

## Provenance and licence

Source: Torrecilla-Pinero, J.A., Ceballos-Martínez, J.M., Plaza Caballero, P.,
Cruces López, A., Cuartero, A. (2026). *Spatial cost inequality in construction and demolition
waste management in sparsely populated regions: Evidence from Extremadura, Spain*. Waste
Management Bulletin, 4(3), 100355.

- DOI: [10.1016/j.wmb.2026.100355](https://doi.org/10.1016/j.wmb.2026.100355)
- Licence of the source: open access, **CC BY 4.0**.

This derived file is redistributed under the same **CC BY 4.0** licence. When you reuse it,
please attribute the source article above (and cite this repository, see the main `README.md`).

## Anonymisation and cleaning note

- The source CSV contains two fields with real company identities: `planta_nombre`
  (treatment operator/company name) and `planta_municipio` (plant location). These are
  **confidential** and were **removed** from this public release.
- `planta_id` is retained as an anonymous key (integer only, no operator name) so that the
  municipality-to-plant assignment, distances and cost structure remain fully reproducible.
  Note that the assignment itself is published in the open-access source article, so an
  interested reader could re-identify operators from that source.
- Minor cleaning: three municipality names contained a corrupted character (non-breaking
  space) from a legacy encoding and were restored to their proper accented form
  (e.g. `Talaván`, `Alcántara`, `Cáceres`). No numeric value was modified.
- The dataset contains no personal data: all fields are municipality-level aggregates.
