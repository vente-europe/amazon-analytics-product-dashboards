# Allergoff EU — Top Line (DE, FR, IT, ES)

> Living document — update after every bug fix, data refresh or new pattern.

## Purpose
Top-line competitive landscape for **Allergoff** (dust mite / textile sprays) across 4 EU
Amazon markets. Hub sidebar: **"Allergoff EU"** (group `topline`, standalone). Created 2026-11-25.

## How it is built
- **Layout = Provecta EU Top Line** (`02-Projects/Dashboards/Provecta EU/index.html`,
  live `vente-europe.github.io/Provecta-EU-Top-Line/`), copied verbatim to `_template.html`.
- `_build.py` replaces **only the `CL_DATA` block** (+ page title). Rendering engine untouched.
- **Zero hardcoded numbers**: every KPI, chart value and note count comes from the CSVs.

```
python _build.py      # regenerates data/x-ray/allergoff-{CODE}.csv + index.html
```

## Data
- Raw Helium 10 X-Ray exports in `data/x-ray/raw/` (one file per marketplace, filenames as
  downloaded). Marketplace is detected from the **URL domain** (`amazon.de/fr/it/es`), not the
  filename. Two files for the same market = build error.
- Filter: **ASIN Revenue (30d) < €1,000 removed** (Tom, 2026-11-25).
- Dedupe by ASIN **within a marketplace only** (same ASIN in DE and FR stays in both).
- **No relevance exclusions** — the exports contain off-category products (e.g. DE ARDAP
  Repell vermin spray 750 ml ≈ €1.28M/12M = most of DE; FR Puressentiel air-purifying spray,
  Febreze; IT Oust, Frontline). Tom decides what to drop; do not remove on your own.
- 12M units = `ASIN Sales` × 12, 12M revenue = `ASIN Revenue` × 12 (same method as
  atopic-skin-detailed). All EUR, prices incl. VAT. H10 brand **Novokill = Allergoff**
  (`BRAND_ALIAS`); brand spellings merged case-insensitively (SANYTOL/Sanytol).

## First build (export 2026-11-25)
| Market | Raw | Dups | <€1k | Kept | 12M units | 12M revenue |
|---|---|---|---|---|---|---|
| FR | 60 | 1 | 27 | 32 | 245,760 | €3.08M |
| ES | 17 | 0 | 2 | 15 | 184,620 | €2.01M |
| DE | 39 | 0 | 27 | 12 | 117,432 | €1.72M |
| IT | 55 | 1 | 37 | 17 | 113,064 | €1.34M |
| **Total** | | | | **76** | **660,876** | **€8.15M** |

## Deploy
Working copy: `asistant-buckup/02-Projects/Console/dashboards/allergoff-eu-topline/`.
Live repo: `C:\Users\tomasz.mickiewicz\Documents\GitHub\amazon-analytics-product-dashboards`
(branch `main`) — copy the folder there, add the `config.json` entry, push `main`.
