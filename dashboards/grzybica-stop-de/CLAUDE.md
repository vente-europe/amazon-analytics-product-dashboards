> Living document — Update after every bug fix or new pattern found.

# Grzybica Stop — DE (Detailed Dashboard)

## Purpose

Deep-dive market analysis for the Grzybica Stop (anti-fungal) category on amazon.de. Empty skeleton — awaiting X-Ray, sales, and review data.

## Tech Stack

- Dashboard Hub (`/Console/`) — vanilla HTML + JS + Chart.js 4.4.4
- Standalone build (cloned from `anti-fungus-nail-polish`): `_build_standalone.py` reads X-Ray + sales + reviews + competitor listings → bakes everything into a self-contained `index.html`
- Tabs 1-2: **auto-computed from X-Ray + Sales CSVs** at build time (zero hardcoded values)
- Tab 3: **AI-analyzed VOC data** stored in `dashboard.json.baseTabs.reviews`
- Tab 4 Marketing Deep-Dive: **SP-API Catalog listings + AI claim tagging** stored in `dashboard.json.addonTabs["marketing-deep-dive"]`
- Marketplace: amazon.de (DE), currency EUR

## Data Sources

| Source | Location | Notes |
|--------|----------|-------|
| X-Ray (30d) | `data/x-ray/Grzybica-Stop-DE-X-Ray.csv` | 41 ASINs, combined from 5 H10 exports (2026-05-08), filtered to ASIN Revenue >= 1000 EUR. Segment column populated by SP-API content classification: 29 Cream, 9 Spray, 2 BathSalt, 1 Solution |
| Sales (12M) | `data/sales-data/{ASIN}-sales-3y.csv` | 4 files dropped so far, more to come from user. Build script falls back to median 30d-x-12 multiplier for ASINs without sales |
| Reviews | `reviews/` | Not yet loaded |
| Competitor Listings | `data/competitor-listings/raw/` | All 54 originally fetched ASINs cached as JSON (SP-API Catalog) |

## Source Keywords (DE)

H10 X-Ray exports were pulled using these search terms (also stored in `data/keywords.json`):

- `fußpilz behandeln`
- `Fußpilz Creme`
- `Fußpilz Spray`
- `Antimykotikum Fuß`

## Marketing Deep-Dive scope

User decision (2026-05-08): MDD pipeline should cover **all Cream AND all Spray** competitors (currently 38 ASINs), not the default top-20-by-revenue. When wiring the MDD pipeline:

1. Build `_listings.json` from raw SP-API JSONs filtered to ASINs where `Segment in ('Cream','Spray')` in the X-Ray CSV
2. Run Gemini claim tagging on those 38 listings
3. Run `scripts/build_mdd.py` to merge into `dashboard.json.addonTabs["marketing-deep-dive"]`

## Build status (2026-05-08)

- Skeleton built: `index.html` (~144 KB), Tabs 1 + 2 active, registered in Console sidebar as "Grzybica Stop (DE)"
- Tabs 3 + 4 hidden by build script until `dashboard.json` populates `baseTabs.reviews` and `addonTabs.marketing-deep-dive`
- Build is tolerant of missing `dashboard.json` and missing sales files
- Rebuild: `cd dashboards/grzybica-stop-de && py _build_standalone.py`

## Tab 4 — Marketing Deep-Dive pipeline

1. `data/competitor-listings/asins.txt` — top 20 ASINs by revenue (auto-generated from X-Ray)
2. `scripts/fetch_competitor_listings.py` → pulls SP-API Catalog data (title, bullets, images, description) for each ASIN, saves to `data/competitor-listings/raw/{ASIN}.json`. Uses EU endpoint + `SP_API_REFRESH_TOKEN`. Marketplace: `A1PA6795UKMFR9`
3. `scripts/build_mdd.py` → merges listings + VOC from Tab 3 + AI claim tagging (via Gemini Pro) into `dashboard.json.addonTabs["marketing-deep-dive"]`
4. Template: `Console/templates/tabs/marketing-deep-dive/template.html`
5. 5 sections: Competitor grid → Claims matrix → VOC-Gap table → Whitespace + Saturation → Strategic recommendations

**No backend keywords** (SP-API Catalog doesn't expose them for ASINs you don't own). **No A+ content** (separate API, not implemented).

## Data Convention — 12M

- 12M units = sum of sales CSV daily data within trailing 12 months
- 12M revenue = 12M units × listed ASIN price (from X-Ray)
- ASINs without sales files: baseline = 30d / export_month_index, 12M = baseline × sum(seasonality indices)
- Currency: EUR

## Build / regenerate

```bash
cd projects/Console/dashboards/grzybica-stop-de
py _build_standalone.py
```

After dropping new data into `data/` or `reviews/`, rerun the build to regenerate `index.html`.

## Source Keywords (DE)

H10 X-Ray exports were pulled using these search terms — listed in `data/keywords.json`:

- `fußpilz behandeln`
- `Fußpilz Creme`
- `Fußpilz Spray`
- `Antimykotikum Fuß`

**TODO:** surface these in the dashboard UI (e.g. small badge row in the header, or a "Source keywords" line under the subtitle) so the team can see which searches the underlying ASIN set came from.

## Known Issues

_(none yet)_

## Self-Update Rule

Update after every bug fix, data pattern discovered, or new tab added.
