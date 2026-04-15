> Living document — Update after every bug fix or new pattern found.

# EU Lice Treatment Analysis (Standalone Dashboard)

## Purpose

Multi-country market analysis for the lice treatment category across **DE, FR, IT, ES**. 4 top tabs × 4 country pills = 16 panels of analysis. Built as a standalone HTML dashboard so it works on `file://` and can later be plugged into the Console hub via the `template: "standalone"` iframe path.

## Status

**Phase 2 — All 4 tabs rendered, data-driven from per-country X-Ray CSVs. Seasonality live.**

## 12M projection methodology (important)

**X-Ray export date is hard-coded** to `2026-03-15` (`XRAY_EXPORT_DATE` at the top of `_build_standalone.py`). The H10 X-Ray CSVs were pulled mid-March, so their "last 30 days" column represents **Feb 14 → Mar 15 2026**, not trailing from today. File mtimes are unreliable (they got bumped by later file ops) — always use the constant.

**Per-ASIN 12M units** is computed in `build_country()` with a 2-tier fallback:

1. **ASINs with a per-ASIN sales CSV** in `data/sales-data/{CODE}/{ASIN}-sales-3y.csv` → sum the daily `Sales` column over the trailing 365 days ending at `XRAY_EXPORT_DATE` (`ASIN_12M_WINDOW_START..ASIN_12M_WINDOW_END`). Real, accurate, no correction needed.
2. **ASINs without sales history** → correct the X-Ray 30-day figure by the country's Feb/Mar total-market seasonality index, then × 12:
   ```
   xray_idx       = (season.months['Feb'] + season.months['Mar']) / 2
   avg_monthly    = xray_30d_sales / xray_idx
   units12m       = round(avg_monthly * 12)
   ```
   This removes the bias from H10's 30-day window landing in a specific part of the year.

Projection method counts print per country on every build: `[history=12 seasonality=31 flat=0]`.

## Total-market seasonality (per country)

Computed in `compute_seasonality()` from every `-sales-3y.csv` in `data/sales-data/{CODE}/`:

- Sum daily `Sales` across **all ASINs** in the country → aggregate monthly totals
- Use the 12 complete calendar months before `XRAY_EXPORT_DATE`'s month: **Mar 2025 → Feb 2026** (`SEASONALITY_WINDOW_START..SEASONALITY_WINDOW_END`)
- Normalize each month's total by the 12-month mean → index array `[Jan..Dec]`, mean = 1.0
- Emit `peakMonth`, `troughMonth`, `peakIdx`, `troughIdx`, `asinCount`, window dates

Exposed on `main_segments_data[code]['seasonality']` and rendered as a single bar chart per country at the bottom of the Main Segments tab (explicitly **not split** by Prevention/Treatment per user decision). An info line above the chart states the data source (total market, N products, window dates).

Current peaks: **DE Nov 1.59×, FR Oct 1.27×, IT Oct 1.84×, ES Oct 1.89×** — Oct/Nov back-to-school season dominates. Seasonality-corrected 12M totals are ~1–4% below flat ×12 across all countries (Feb/Mar is slightly above average, so ×12 was a mild overestimate).

### Renderer map

| Tab | Renderer | Source aggregator |
|---|---|---|
| `main-segments` | `renderMainSegments` | `build_country().segments` |
| `market-structure-prevention` | `renderMarketStructure(country, 'Prevention')` | `market_structure(prev products)` |
| `market-structure-treatment`  | `renderMarketStructure(country, 'Treatment')`  | `market_structure(tx products)` |
| `treatment-methods` | `renderTreatmentMethods` | `treatment_methods(classified products)` |
| `reviews-prevention` | `renderReviews(country, 'reviews-prevention')` | `reviews/{CODE}/Prevention/voc.json` via `load_voc(code, 'Prevention')` |
| `reviews-treatment`  | `renderReviews(country, 'reviews-treatment')`  | `reviews/{CODE}/Treatment/voc.json`  via `load_voc(code, 'Treatment')`  |
| `marketing-deep-dive` | `renderMarketingDeepDive` | `data/competitor-listings/{CODE}/mdd.json` loaded via `load_mdd()` |

The two Market Structure tabs share one renderer parameterized by segment name. Treatment Methods has its own because its data shape (Physical/Chemical/combo × Type × Brand) is fundamentally different.

### Shared IIFE helpers (used by every renderer)

`esc`, `fmtInt`, `fmtShort`, `fmtMoney`, `fmtMoneyShort`, `pct`, `destroyCharts`, `pie`, `brandColor`, `makeAllTablesSortable`, `SEG_COLORS`, `METHOD_COLORS`, `BRAND_COLORS`, `BRAND_PALETTE_JS`. All declared at the top of the `bootstrap()` IIFE, never nested inside a renderer.

### Known placeholders (waiting for sales history)

- Main Segments — `% Unit Share — Brand vs. Total (All) (12M)` line chart (still placeholder — not wired to sales history yet)
- Market Structure (Prevention / Treatment) — Price Positioning scatter
- Treatment Methods — Price Positioning scatter

(Total Market Seasonality bar chart is now LIVE on Main Segments, one per country, built from `data/sales-data/{CODE}/`.)

### Marketing Deep-Dive — data drop-in pattern

MDD tab renders from `data/competitor-listings/{DE,FR,IT,ES}/mdd.json`. Each file matches the shape consumed by `projects/Console/templates/tabs/marketing-deep-dive/template.html`: `competitors[]`, `claimsMatrix{themes,rows}`, `claimsSummary[]`, `vocGap[]`, `whitespaceOpportunities[]`, `saturation[]`, `strategicRecommendations[]`, `totalCompetitors`, `marketplace`. Missing file → empty-state card. Raw SP-API pulls live under `data/competitor-listings/{CODE}/raw/` per country (following the anti-fungus pattern).

### Reviews VOC — data drop-in pattern (split by segment)

Reviews are now **split into two tabs per country**: `Reviews VOC — Prevention` and `Reviews VOC — Treatment`. Both tabs share one renderer (`renderReviews(country, tabId)`) — the tabId selects which segment's data to load and is shown in the header.

Each segment renders from `reviews/{CODE}/{Prevention|Treatment}/voc.json`. The VOC_DATA shape is unchanged (`totalReviews`, `avgRating`, `starDist`, `cpSummary`, `cpWho/When/Where/What`, `usageScenarios`, `negativeTopics`, `positiveTopics`, `negativeInsights`, `positiveInsights`, `buyersMotivation`, `customerExpectations`, `themeFilters`, `tagStyles`, `reviews[]`). Missing/empty files → that segment shows a clean empty-state with drop-in instructions.

Status: **DE Prevention (244 reviews) and DE Treatment (226 reviews) populated**. FR/IT/ES still empty for both segments.

Workflow when a new country's review scrape lands:
1. Drop raw review CSVs into `reviews/{CODE}/Prevention/` (top-5 prevention ASINs) and `reviews/{CODE}/Treatment/` (top-5 treatment ASINs)
2. Translate non-EN reviews to English during VOC analysis
3. Run VOC analysis per segment → produce `voc.json` matching the shape above (one file per segment subfolder)
4. Rerun `py _build_standalone.py` — both Reviews tabs light up for that country

### Known gotchas

- **`pie()` and all shared helpers must live at IIFE top level**, never nested inside a renderer. Nesting them causes `ReferenceError: pie is not defined` when another renderer tries to call them (hit this during the Market Structure port).
- **Country pills must show code only** — unicode regional-indicator pairs render as letter pairs on Windows instead of flag glyphs, so concatenating `c.flag + c.code` produces `DEDE`. Shell uses code only.
- **Countries with no method classification** — Treatment Methods renderer shows an empty-state card. When you add `Treatment Method` values to the X-Ray CSVs, ES is currently the only country with a mix; DE/FR/IT are all Physical.
- **Segment column normalization** — IT CSV had one row with `Focus = 'Treatment shampoo with comb'` (a Type value leaked into Focus). `build_country` normalizes anything not starting with 'prevention' to `Treatment`.

## Tab structure

| # | ID | Label |
|---|-----|-------|
| 1 | `main-segments` | Main Segments |
| 2 | `market-structure-prevention` | Market Structure (Prevention) |
| 3 | `market-structure-treatment` | Market Structure (Treatment) |
| 4 | `treatment-methods` | Treatment Methods |
| 5 | `reviews-prevention` | Reviews VOC — Prevention |
| 6 | `reviews-treatment` | Reviews VOC — Treatment |
| 7 | `marketing-deep-dive` | Marketing Deep-Dive |

Inside every tab, the same 4 country pills (DE → FR → IT → ES, by market size). Single panel re-renders when either tab or country changes — no hidden duplicate panels.

## Tech Stack

- Standalone HTML — Chart.js 4.4.4 + ChartDataLabels via CDN
- `_build_standalone.py` — reads data bundle + assembles `index.html`
- Self-contained — no fetch calls, opens directly via `file://`

## Folder layout

```
eu-lice-treatment-analysis/
├── CLAUDE.md
├── config.json                  ← Dashboard metadata
├── _build_standalone.py         ← Build script
├── index.html                   ← Built output (regenerate after data changes)
├── data/
│   ├── x-ray/
│   │   ├── DE/                  ← Drop Helium 10 X-Ray CSVs for Germany here
│   │   ├── FR/                  ← (and France here)
│   │   ├── IT/                  ← (Italy)
│   │   └── ES/                  ← (Spain)
│   ├── sales-data/              ← Per-ASIN historical sales CSVs (sales-3y format)
│   └── competitor-listings/     ← Future SP-API listings (if needed)
└── reviews/                     ← Future review CSVs
```

## Data convention

- **Per-country X-Ray** — every country has its own subfolder with its own H10 X-Ray exports. Combine inside each country folder before processing.
- **Segment column** — name it `Segment`, place it as the 3rd column right after `ASIN` (per Console-wide convention)
- **Currency** — EUR for all 4 markets; UK is NOT included
- **12M projection** — same approach as anti-fungus: per-ASIN sales history when available, median multiplier fallback otherwise

## X-Ray Google Sheet links

The header has 4 buttons in the top-right, one per country. URLs live in `_build_standalone.py` under `xray_links = { 'DE': '...', 'FR': '...', 'IT': '...', 'ES': '...' }`. Replace `'#'` placeholders when the sheets are ready.

## Data presentation roadmap (Phase 2 — done)

All 4 tabs ported from `projects/Dashboards/Nitolic - US/index.html` using the `.claude/skills/port-nitolic-tab/` skill. Nitolic source is hardcoded; our renderers read from `_DASH_DATA.tabs[tab].countries[country]` — swap the CSV → everything updates.

Mapping:

| New tab | Nitolic source tab | Status |
|---------|---------------------|---|
| Main Segments | TAB 1 — Main Segments | Done |
| Market Structure (Prevention) | TAB 2 — Market Structure (Prevention) | Done |
| Market Structure (Treatment) | TAB 3 — Market Structure (Treatment) | Done |
| Treatment Methods | TAB 4 — Treatment Method | Done |

## Self-Update Rule

Update this file after every structural change, new tab, new data convention, or build-script tweak.
