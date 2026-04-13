> Living document — Update after every bug fix or new pattern found.

# Dashboard Hub — Console Project

## Purpose

Unified Dashboard Hub — a single app where the team accesses all Amazon product analytics dashboards in one place. Replaces individual standalone dashboards with a sidebar-navigated, template-driven system.

## Tech Stack

- Vanilla HTML + JS + CSS (no framework, no build tools)
- Chart.js 4.4.4 + ChartDataLabels 2.2.0 (via CDN)
- Static files — works on `file://` and GitHub Pages
- No server required

## Architecture

- **Central config** (`config.json`) — sidebar registry, lists all dashboards
- **Per-dashboard config** (`dashboards/{id}/config.json`) — local settings, tab list
- **Per-dashboard data** (`dashboards/{id}/dashboard.json`) — **config only, no hardcoded values** (exception: Reviews VOC data which is AI-analyzed)
- **Data engine** (`js/data-engine.js`) — CSV parser, seasonality calculator, aggregation, table sorting
- **Templates** — `templates/topline/` (fixed layout), `templates/detailed/` (tab shell)
- **Tab templates** — `templates/tabs/{name}/template.html` (modular, pluggable)

## CRITICAL RULE: Zero Hardcoded Values

**Every single number in the dashboard must come from data files or their analysis.** Nothing is manually typed into JSON or templates.

- KPIs — computed from CSV data at runtime
- Insight text — auto-generated from computed segment shares, dominance, price divergence
- Charts — data from aggregated CSV
- Tables — data from aggregated CSV
- Methodology notes — auto-generated (mentions data source, method, ASIN counts)

`dashboard.json` contains **only configuration** — which CSV file to load, export month, segment column name. Never numeric data.

**Exception:** Reviews VOC tab — review analysis data (themes, quotes, strategy insights) is AI-generated and stored in `baseTabs.reviews`. This is because VOC analysis requires AI interpretation, not simple CSV aggregation. The VOC build script is at `scripts/build_voc.py`.

## Data Pipeline

### Tabs 1 & 2 (Total Market, Market Structure) — fully auto-computed:
```
X-Ray CSV (data/x-ray/)
  → DataEngine.loadXRay() parses CSV client-side
  → Products with price, brand, type, 30d sales

Sales CSVs (data/sales-data/)
  → DataEngine.loadSalesData() loads per-ASIN daily sales
  → Sum actual daily units for last 12 months per ASIN

Seasonality (DataEngine.calculateSeasonality)
  → Monthly index from ASINs with sales data
  → ASINs WITHOUT sales files: baseline = 30d / export_month_index, 12M = baseline × sum(indices)

Revenue = 12M units × listed ASIN price

Aggregation → segments, brands, totals → stored in data._computed
```

### Tab 3 (Reviews) — AI-analyzed:
```
Review JSON files (reviews/)
  → scripts/build_voc.py reads + tags + analyzes
  → VOC_DATA structure saved to dashboard.json baseTabs.reviews
  → Template renders from this data
```

### Addon tabs — mixed:
- **KW Analysis** — data in `addonTabs.keyword-analysis` (from H10 Niche export)
- **Other addons** — populated when added

## Dashboard Types

| Type | Template | Tabs | Data Source |
|------|----------|------|------------|
| **Detailed** | Tab shell + modular tabs | 3 base + addons | X-Ray CSV + Sales CSVs + Reviews JSON |
| **Topline** | Fixed layout, no tabs | Single page | Currently hardcoded in dashboard.json — **TODO: make data-driven from CSV** |

### Detailed — Base Tabs (always positions 1–3)

1. **Total Market** — auto-computed from CSV: segment KPIs (dynamic count), revenue/unit pies, segment summary table, brand pies per segment, auto-generated insight text
2. **Market Structure** — auto-computed from CSV: per-segment sub-tabs with pill selector, concentration KPIs (HHI, top 1/3/5/10 share), brand pies, price vs revenue scatter, brand summary table, top 20 ASINs table
3. **Reviews VOC** — from AI analysis: KPIs, star distribution bar, customer profile (4 stacked bars), sub-tabs (Customer Insights / Review Browser), anchor nav (sticky), usage scenarios, negative/positive sentiment (expandable rows with quotes), strategy insights, buyers motivation, customer expectations, review browser with filters

### Detailed — Addon Tabs (position 4+)

- `keyword-analysis` — H10 Niche competitor + keyword ranking matrix
- (future: `voc`, `listing-communication`, `copy-brief`, `image-strategy`)

### Topline

- Fixed single-page layout: KPIs, revenue bar, unit doughnut, marketplace table, brand pies
- **TODO:** Rebuild as data-driven (read X-Ray CSV, not hardcoded values)

## dashboard.json — Config Only

```json
{
  "title": "Fruit Fly Trap — US Market Analysis",
  "subtitle": "Data: Helium 10 X-Ray",
  "currency": "$",
  "xray": {
    "file": "Fruit-Flies-US-new-merged-data.csv",
    "segmentColumn": "Type",
    "exportMonth": 1
  },
  "baseTabs": {
    "totalMarket": {},
    "marketStructure": {},
    "reviews": { ... VOC_DATA ... }
  },
  "addonTabs": {
    "keyword-analysis": { ... KW data ... }
  }
}
```

- `exportMonth`: 0-based (0=Jan, 1=Feb, 2=Mar, etc.)
- `baseTabs.reviews` is the only section with actual data (AI-analyzed VOC)
- Everything else is config pointers

## X-Ray CSV — What to Use vs NOT Use

| Column | Use for |
|--------|---------|
| `ASIN` | Identifier, matches sales CSV filenames |
| `Price US$` | 12M revenue = 12M units × this price |
| `Brand` | Brand grouping |
| `Type` | Segment column (varies by category) |
| `Ratings`, `Review Count` | Product quality metrics |
| `BSR` | Ranking |
| ~~`ASIN Sales`~~ | **NEVER for 12M** — 30-day only |
| ~~`ASIN Revenue`~~ | **NEVER for 12M** — H10 estimate, unreliable |

## Sales CSV Format

Filename: `{ASIN}-sales-3y.csv`
Columns: `Time, Sales, Trend Line, 7-Day Moving Average`
- `Time`: `"YYYY-MM-DD HH:MM:SS"` (quoted)
- `Sales`: daily units (float, quoted)

## Folder Structure Per Dashboard

```
dashboards/{DashboardName}/
├── data/
│   ├── x-ray/         ← Helium 10 X-Ray exports
│   ├── sales-data/    ← Per-ASIN daily sales CSVs ({ASIN}-sales-3y.csv)
│   └── dd/            ← DD / Niche data
├── reviews/           ← Review JSON files (scraped reviews, VOC analysis)
├── config.json        ← Dashboard config (type, tabs, marketplace)
├── dashboard.json     ← Config + Reviews VOC data
└── CLAUDE.md          ← Project-specific instructions and learnings
```

## Naming Convention

Dashboard folder: `{Product}-{Marketplace}-{Type}` or `{Product}-{Type}`
- Type: `Detailed` or `Topline` (always last)
- Marketplace: US, UK, DE, FR, IT, ES, NL, EU (included if specified)

## Key Files

| File | Purpose |
|------|---------|
| `index.html` | Hub shell (sidebar + main content area) |
| `config.json` | Central dashboard registry (sidebar entries) |
| `js/hub.js` | Router, sidebar, template loader, tab management |
| `js/data-engine.js` | CSV parser, seasonality, aggregation, table sorting |
| `css/hub.css` | All styles (sidebar + dashboard + all tab template CSS) |
| `scripts/build_voc.py` | Review analysis script — generates VOC_DATA for Reviews tab |

## Tab Template Files

```
templates/tabs/
├── total-market/template.html      ← Base tab 1 (auto-computed from CSV)
├── market-structure/template.html  ← Base tab 2 (auto-computed from CSV)
├── reviews/template.html           ← Base tab 3 (reads VOC_DATA from dashboard.json)
└── keyword-analysis/template.html  ← Addon tab (reads from addonTabs)
```

## Data Update Workflow

### New dashboard:
1. User: _"Create new Detailed Dashboard for [Product] [Market]"_
2. Claude: creates folder, structure, config → appears in sidebar (empty skeleton)
3. User: drops CSV files into `data/x-ray/`, `data/sales-data/` (optional)
4. User: _"Populate the dashboard"_ or _"Load the data"_
5. Claude: sets `dashboard.json` config (filename, exportMonth) → data loads automatically

### Refresh data (new X-Ray):
1. User: drops new CSV into `data/x-ray/`
2. User: _"Update X-Ray for [Dashboard]"_ or _"Refresh data"_
3. Claude: updates filename + exportMonth in `dashboard.json` → everything recalculates

### Add Reviews analysis:
1. User: drops review JSON files into `reviews/`
2. User: _"Analyze reviews for [Dashboard]"_
3. Claude: runs `scripts/build_voc.py` (or analyzes in-context) → populates `baseTabs.reviews`

### Add addon tab:
1. User: _"Add [tab name] tab to [Dashboard]"_
2. User: drops data files if needed
3. Claude: adds tab to per-dashboard config.json, wires data → tab appears

**No auto-detection** — user controls when data is loaded. Explicit commands only.

## UI / Design Rules

- **Dashboard title** in dark blue header bar (`#0f2942`) — white text, 1.4rem, visible on all tabs
- **Dashboard body** max-width 1600px — use available horizontal space
- **Global `h2`** has `color: #1e293b` — any `h2` inside a dark container must explicitly set `color: #fff`
- **Numeric columns in tables are sortable** — use `DataEngine.makeAllTablesSortable(container)`. Only columns with numeric data get sort arrows. Text-only columns are NOT sortable.
- **Reviews tab sticky navigation** — sub-tabs (Customer Insights / Review Browser) stick at `top: 0`, anchor pills (Customer Profile, Usage Scenario, etc.) stick at `top: 41px`
- **Segment sub-tabs** in Market Structure — pill buttons with segment colors
- **Text columns in tables (ASIN, Brand, Title, etc.) must be left-aligned.** The `num-right` table class right-aligns all `<td>` by default. Any text column needs explicit `style="text-align:left"` on both `<th>` and `<td>`. Numeric columns stay right-aligned.

## Known Issues & Fixes

- **`_DASH_DATA` cleanup timing (2026-04-07):** Tab templates read `window._DASH_DATA` for computed CSV data. Previously cleared after first tab → tabs 2+ got null. Fix: keep `_DASH_DATA` alive for dashboard lifetime, clear only when switching dashboards.
- **`_TAB_DATA` null for Reviews tab (2026-04-07):** Reviews template couldn't get tab data via `_TAB_DATA`. Fix: added fallback to read directly from `_DASH_DATA.baseTabs.reviews` if `_TAB_DATA` is null. Both paths now work.
- **`bw()` function ordering (2026-04-07):** Bar width helper used in HTML building before being defined. Inline `function` declarations are hoisted in IIFEs, but moved definition to top of function for clarity and safety.
- **Sort arrows on text columns (2026-04-07):** `makeTableSortable()` was adding sort arrows to ALL columns. Fix: now checks first 5 rows — only columns where 50%+ cells are numeric get sort arrows. Text columns (labels, descriptions, reviews) have no sorting.
- **Title column right-aligned in Top ASINs table (2026-04-13):** Cell inherited `num-right` table class. Fix: added `text-align:left` to the title `<td>` inline style in [market-structure/template.html](templates/tabs/market-structure/template.html).

## Self-Update Rule

Update this file after every bug fix, new tab template, architecture change, UI fix, or pattern discovered. Also update the new-dashboard skill (`/.claude/skills/new-dashboard/SKILL.md`) if the change affects dashboard creation workflow.
