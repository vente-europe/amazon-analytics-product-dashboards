# Atopic Skin — Detailed (DE, FR, IT, ES)

> Standalone detailed dashboard. Living document — update after every change.

## What this is

A **3-tab standalone** for the "Atopic Skin" dermo category across 4 EU markets
(DE / FR / IT / ES). All static UI text is in **Polish**.

| Tab | Polish label | Source |
|-----|--------------|--------|
| 1 | `Rynek` | **Faithful copy of the `atopic-skin-topline` TOPLINE** (cross-market view) |
| 2 | `Recenzje (VOC)` | Per country × segment, `renderReviews(bucket)` (from `u-reviews-voc`) |
| 3 | `Marketing Deep-Dive` | Per country × segment, `renderMarketingDeepDive(bucket)` (from `u-marketing-deep-dive`) |

- **Tab 1 has NO pills** — it is the whole cross-market topline.
- **Tabs 2 & 3 show two pill rows**: country (`Niemcy 🇩🇪 · Francja 🇫🇷 · Włochy 🇮🇹 · Hiszpania 🇪🇸`, order = market size) and segment. Pills are hidden on Tab 1.
- Navigation state is `{ tab, country, segment }`; VOC/MDD panels are re-rendered on any change. Switching country rebuilds the segment pills from that country's segments.

## How Tab 1 works (important)

The build script reads `../atopic-skin-topline/index.html`, extracts its `<style>`
block and its `<body>` inner content, and pastes both **verbatim** into
`#panel-market`. The topline's own inline `<script>` (with its baked-in chart
data) renders the Chart.js charts. Because `#panel-market` is the default-active
(visible) panel at load, the charts size correctly. **To refresh Tab 1, rebuild
`atopic-skin-topline` first, then rebuild this dashboard.**

## Data file locations

| Data | Path | Shape |
|------|------|-------|
| VOC | `reviews/{CODE}/{Segment}/voc.json` | `u-reviews-voc` contract (POLISH content) |
| MDD | `data/competitor-listings/{CODE}/mdd-{slug}.json` (`slug = segment.lower()`) | `u-marketing-deep-dive` contract (POLISH content) |
| X-Ray (Tab 1 only, via atopic-skin-topline) | `data/x-ray/{CODE}/Dermo-Products-{CODE}.csv` | Helium 10 X-Ray |

- `SEGMENTS_BY_COUNTRY` is **auto-detected** by scanning `reviews/{CODE}/`
  subfolders (so it grows as buckets are added). Fallback defaults:
  DE = `Check, Cream, Oil, Wash`; FR/IT/ES = `Cream, Oil, Wash`.
  Preferred display order: `Check, Cream, Wash, Oil`.
- If a bucket's JSON is missing, the panel shows a Polish placeholder
  (`Brak danych VOC…` / `Brak danych Marketing Deep-Dive…`). The dashboard
  builds and renders even when **all** VOC/MDD are null.
- Raw source reviews + competitor listings live in the sibling
  `../atopic-skin-topline/` folder; this folder only ships the derived
  `voc.json` / `mdd.json`, the X-Ray CSVs, and `index.html`.

## How the renderers are composed

The two `u-*` tab templates read `window._TAB_DATA` and render into a fixed root
id. The build script transforms each template's IIFE into a named function
`renderReviews(D, root)` / `renderMarketingDeepDive(D, root)` (strips the
`window._TAB_DATA` + `getElementById` lines, wraps as a function) and applies a
Polish translation table (`VOC_STR` / `MDD_STR`) to the fixed English UI chrome.
**Only UI chrome is translated in the script — all data (themes, quotes,
findings, labels) must be Polish in the JSON itself.**

## Rebuild

```
python dashboards/atopic-skin-detailed/_build_standalone.py
```
Run from the `Console` project root (or anywhere — paths are absolute). Writes
`index.html` next to the script. Prints per-country segment list + VOC/MDD
bucket coverage.

## Hub registration

Central `config.json` entry (group `detailed`, template `standalone`), placed
right after `atopic-skin-topline`.

## Deploy

`git push origin master:main` (GitHub Pages serves from `main`).

## VOC / MDD JSON schemas

See the data contracts at the top of:
- `templates/tabs/u-reviews-voc/template.html`
- `templates/tabs/u-marketing-deep-dive/template.html`

The build script sets `countryName` / `countryCode` / `segmentName` / `currency`
on each bucket at render time (via `scopeBucket`), so those may be omitted from
the JSON — but every other key must be present and Polish.

## Build pipelines (how the VOC / MDD JSON is generated)

**`voc_pipeline.py`** — two stages per bucket:
- `python voc_pipeline.py prep <CODE> <SEG>` → reads raw reviews from
  `../atopic-skin-topline/reviews/{CODE}/{SEG}/*.json`, computes exact stats,
  selects a representative ≤120 sample (negatives floor), **machine-translates the
  sample to Polish** (deep_translator/Google, cached in `reviews/_tr_cache.json`),
  writes `_analysis_input.json`.
- An LLM reads `_analysis_input.json` and writes `_qual.json` (the qualitative
  Polish block + `themeKeywords` for regex tagging). Bounded task — no translation,
  no scripts.
- `python voc_pipeline.py assemble <CODE> <SEG>` → merges stats + `_qual.json` +
  regex-tagged Polish sample → `voc.json`.

**`mdd_pipeline.py`** — fully deterministic (no LLM):
- `python mdd_pipeline.py ALL` (or `<CODE> <SEG>`) → picks top-N competitors per
  segment (by X-Ray ASIN Revenue; falls back to the review-bucket ASINs when a
  segment is absent from that market's X-Ray, e.g. FR/Oil), pulls listing JSON from
  `../atopic-skin-topline/data/competitor-listings/{CODE}/raw/`, tags claims via a
  shared multilingual (DE/FR/IT/ES/EN) `THEMES` keyword set, cross-references VOC
  `negativeTopics` (matched via Polish keywords) for the gap analysis, and writes
  `data/competitor-listings/{CODE}/mdd-{slug}.json`.

## Key decisions / gotchas

- **Ratings come from X-Ray, not scraped reviews.** The scraped review ratings are
  critical-skewed / unreliable (bucket averages ~2.9★ vs true ~4.5★; some scrapes
  had a single star band). So the VOC headline **avg★ + review count** are computed
  **segment-level from X-Ray** (weighted by review count over all products in that
  market×segment); the scraped reviews are used **only** for qualitative themes /
  quotes / the review browser. The **star-distribution bar is hidden** (patched out
  dashboard-locally in `_build_standalone.py` `VOC_STR`). If a segment is absent
  from a market's X-Ray (FR/Oil), the assemble step preserves any prior headline.
- **Source folder was renamed mid-build**: `dermo-products` → `atopic-skin-topline`
  (by another session). All three scripts point at `../atopic-skin-topline/`.
- **Thin buckets**: IT/Oil and ES/Oil have only 1 product in X-Ray (24–91 scraped
  reviews) → smaller VOC + 1-competitor MDD. Real, not a bug.
- Valid theme pill classes: `pill-amber, pill-blue, pill-orange, pill-purple, pill-red`.
