> Living document — Update after every bug fix or new pattern found.

# Anti-Fungus Nail Polish (Detailed Dashboard)

## Purpose

Deep-dive market analysis for the Anti-Fungus Nail Polish category on Amazon. Empty skeleton — awaiting X-Ray and sales data.

## Tech Stack

- Dashboard Hub (`/Console/`) — vanilla HTML + JS + Chart.js 4.4.4
- Tabs 1-2: **auto-computed from X-Ray + Sales CSVs** at runtime (zero hardcoded values)
- Tab 3: **AI-analyzed VOC data** stored in `dashboard.json.baseTabs.reviews` (German reviews translated to English, 154 reviews across 3 ASINs)
- Tab 4 Marketing Deep-Dive: **SP-API Catalog listings + AI claim tagging** stored in `dashboard.json.addonTabs["marketing-deep-dive"]`
- Marketplace: amazon.de (DE), currency EUR

## Data Sources

| Source | Location | Notes |
|--------|----------|-------|
| X-Ray (30d) | `data/x-ray/` | 72 ASINs combined from 30 Helium 10 exports (2026-04-08). Segment column: `Type` (6 segments) |
| Sales (12M) | `data/sales-data/` | 16 ASINs with 12-month daily history (renamed `-sales-3y.csv` per engine convention) |
| Reviews | `reviews/` | 3 CSV files, 154 reviews total (amazon.de, German) |
| Competitor Listings | `data/competitor-listings/raw/` | 20 JSON files from SP-API Catalog (top 20 ASINs by 30d revenue). Re-run `scripts/fetch_competitor_listings.py` to refresh |

## Tab 4 — Marketing Deep-Dive pipeline

1. `data/competitor-listings/asins.txt` — top 20 ASINs by revenue (auto-generated from X-Ray)
2. `scripts/fetch_competitor_listings.py` → pulls SP-API Catalog data (title, bullets, images, description) for each ASIN, saves to `data/competitor-listings/raw/{ASIN}.json`. Uses EU endpoint + `SP_API_REFRESH_TOKEN` (not the US one). Marketplace: `A1PA6795UKMFR9`
3. `scripts/build_mdd.py` → merges listings + VOC from Tab 3 + AI claim tagging (via Gemini Pro) into `dashboard.json.addonTabs["marketing-deep-dive"]`
4. Template: `Console/templates/tabs/marketing-deep-dive/template.html`
5. 5 sections: Competitor grid → Claims matrix → VOC-Gap table → Whitespace + Saturation → Strategic recommendations. Click a competitor card for a modal with full bullets + image stack

**No backend keywords** (SP-API Catalog doesn't expose them for ASINs you don't own). **No A+ content** (separate API, not implemented).

## Data Convention — 12M

- 12M units = sum of sales CSV daily data within trailing 12 months
- 12M revenue = 12M units × listed ASIN price (from X-Ray)
- ASINs without sales files: baseline = 30d / export_month_index, 12M = baseline × sum(seasonality indices)
- Currency: USD (update if marketplace differs)

## Known Issues

_(none yet)_

## Self-Update Rule

Update after every bug fix, data pattern discovered, or new tab added.
