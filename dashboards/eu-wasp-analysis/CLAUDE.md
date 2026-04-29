> Living document — update after every bug fix or new pattern found.

# EU Wasp Analysis (Standalone Dashboard)

## Purpose

Multi-country wasp-control market analysis across **DE, FR, UK** — focused on **Lure** and **Electric** segments only.

## Status

**Phase 2 — live data loaded.** X-Ray CSVs cleaned for all 3 countries; user maintains them manually. Reviews scraped for top-5 per segment per country (partial coverage — re-run as needed).

## Tracked segments

`SEGMENTS = ['Lure', 'Electric']` only. **Sticky was removed** (most "Sticky" rows are non-wasp products like fruit-fly / cockroach traps that incidentally mention wasps). Other segment values (`Spray`, `Repellent`, `Decoy`) appear in the X-Ray CSVs but are silently excluded from the build by the `if focus is None: continue` filter — keep them in the X-Ray for the user's reference, do not add tabs for them.

## Tab structure (7 tabs)

| # | ID | Label |
|---|-----|-------|
| 1 | `main-segments` | Main Segments |
| 2 | `market-structure-lure` | Market Structure (Lure) |
| 3 | `market-structure-electric` | Market Structure (Electric) |
| 4 | `reviews-lure` | Reviews VOC — Lure |
| 5 | `reviews-electric` | Reviews VOC — Electric |
| 6 | `marketing-deep-dive-lure` | Marketing Deep-Dive — Lure |
| 7 | `marketing-deep-dive-electric` | Marketing Deep-Dive — Electric |

Inside every tab, 3 country pills (DE → FR → UK). Single panel re-renders on tab or country change.

## Folder layout

```
eu-wasp-analysis/
├── CLAUDE.md
├── _build_standalone.py        ← config block at top, then build logic
├── index.html                  ← built output (regenerate after data changes)
├── top_reviewed.csv            ← top-5 ASINs per (country, segment) — output of scripts/top_reviewed.py
├── data/
│   ├── x-ray/
│   │   ├── DE/  Wasp DE.csv      ← H10 X-Ray export
│   │   ├── FR/  Wasp FR.csv
│   │   └── UK/  Wasps UK.csv     ← note: UK file uses plural "Wasps" — the code handles this
│   ├── sales-data/{DE,FR,UK}/    ← per-ASIN daily sales (filename: `{Segment}-{ASIN}-sales-3y.csv`)
│   └── competitor-listings/{DE,FR,UK}/
├── reviews/{DE,FR,UK}/           ← scraped review CSV+JSON per ASIN: `{ASIN}_{COUNTRY}_{Segment}_all_reviews.csv`
└── scripts/
    ├── verify_segments.py        ← SP-API title/bullet fetcher + auto-classifier (used to populate Segment + Wasp helper column)
    ├── top_reviewed.py           ← ranks top-5 ASINs per segment by Review Count
    ├── fetch_top_reviews.py      ← orchestrates Review Scraper for top-N ASINs, copies outputs with renamed filenames
    ├── build_mdd.py
    └── fetch_competitor_listings.py
```

## Data conventions

### X-Ray CSV
- **Segment column** — must contain `Lure` / `Electric` / `Sticky` / `Spray` / `Repellent` / `Decoy` / `(blank)`. Build only includes Lure + Electric. Anything else is silently dropped from the build.
- **Wasp column** — populated by `verify_segments.py`, marks rows where local-language wasp word appears in title/bullets. **This is a USER HELPER COLUMN** for spotting non-wasp items during cleanup. The build script does **NOT** filter by it — user does the filtering by removing rows from the X-Ray manually.
- **UK file naming exception** — `Wasps UK.csv` (plural). DE/FR use singular `Wasp {CODE}.csv`. Handled in build script's `countries[]` config and in `top_reviewed.py`'s `load_country()`.

### Sales-data (optional)
- Filename: `{Segment}-{ASIN}-sales-3y.csv` (e.g. `Lure-B00HFDGMNO-sales-3y.csv`)
- ASIN-only filenames also supported (`{ASIN}-sales-3y.csv`)
- When user removes an ASIN from the X-Ray, **also remove its sales-data file** — orphan files cause "Unknown" brand to appear in the brand-share chart. The `compute_brand_monthly_share` function now skips orphans defensively, but cleanup is still good hygiene.

### Reviews (optional)
- Scraper output renamed to `reviews/{COUNTRY}/{ASIN}_{COUNTRY}_{Segment}_all_reviews.csv` (and `.json` pair).
- See `scripts/fetch_top_reviews.py` for the orchestration. Cookies + sticky country-locked iProyal proxy required — see workspace memory `reference_review_scraper.md`.

## 12M projection methodology

For each ASIN:
1. If `data/sales-data/{CODE}/*-{ASIN}-sales-3y.csv` exists → use real trailing 365-day sum.
2. Else divide 30d X-Ray sales by **the seasonality index for the export window** (auto-computed from `XRAY_EXPORT_DATE`), then × 12.
3. Else flat 30d × 12.

`xray_window_seasonality_index()` walks the 30 days ending on `XRAY_EXPORT_DATE` and averages the per-month seasonality indices. **No hardcoded months — it auto-aligns.**

**`XRAY_EXPORT_DATE` rule** — must be an explicit date, e.g. `date(2026, 4, 29)`. `None` means "today" but is unsafe (silent shift if rebuilding a month later). Update this single line every time the X-Ray is re-exported. Comment in build script warns about this.

## Build customisation (vs. template)

| Field in `_build_standalone.py` | Value |
|---|---|
| `PRODUCT_NAME` | `'Wasp Traps'` |
| `SEGMENTS` | `['Lure', 'Electric']` |
| `XRAY_EXPORT_DATE` | `date(2026, 4, 29)` (currently — update on re-export) |
| `countries[].csv` | `'Wasp DE.csv'`, `'Wasp FR.csv'`, `'Wasps UK.csv'` |

## Build / re-build workflow

1. (As needed) Update X-Ray CSVs in `data/x-ray/{CODE}/`.
2. Update `XRAY_EXPORT_DATE` to the actual export date.
3. Run `py _build_standalone.py` → regenerates `index.html`.
4. Open `index.html` directly in browser (or via hub iframe).

## Review scraping workflow

1. `py scripts/top_reviewed.py --csv` → regenerates `top_reviewed.csv` (top-5 per country × segment).
2. Edit `projects/Review Scraper/.env` PROXY_URL with country-locked sticky session (e.g. `_country-gb_session-XXX_lifetime-30m` for UK).
3. Refresh cookies in `projects/Review Scraper/cookies/amazon.{tld}.json` if scraper hits sign-in.
4. `py scripts/fetch_top_reviews.py UK` (or DE/FR) → runs scraper, copies outputs to `reviews/{COUNTRY}/`.

## Known gotchas

- **DE and FR cookies expire faster than UK** in this user's setup. Always re-export and verify a `/product-reviews/` page loads logged-in before running the batch.
- **Sticky proxy required** — random rotation = 0 reviews. Country must be single (`country-gb` not `country-fr,gb`) — mixed lists land on random country and Amazon's geo-trust check fails.
- **CSV files often locked** — Tom keeps X-Rays open in Excel during cleanup. Writes will fail with `PermissionError`. Wait for him to close the file rather than retrying.
- **Encoding** — when user pastes a CSV from a Windows-locale source, German umlauts may arrive as mojibake (`MÃ¼ckenlampe` instead of `Mückenlampe`). Fix with `.encode('latin-1').decode('utf-8')` round-trip before saving.

## Self-Update Rule

Update this file after every structural change, new data convention, or build-script tweak.
