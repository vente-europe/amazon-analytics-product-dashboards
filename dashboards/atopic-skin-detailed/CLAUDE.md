# Atopic Skin — Detailed (DE, FR, IT, ES)

> Standalone detailed dashboard. Living document — update after every change.

## 2026-07-08 — UK added as a 5th market (Rynek + Struktura rynku)

New market **UK** under `data/x-ray/UK/`. Eight raw Helium_10 exports were merged →
`data/x-ray/UK/Dermo-Products-UK.csv` (dedup by highest `ASIN Revenue`, prices in `£`,
`Segment` after `ASIN`, `≥£1,000/30d` floor). **Tom re-segmented the final file into the
standard `Cream / Wash / Oil` taxonomy** (matching DE/FR/IT/ES) — **104 ASINs**
(Cream 82 / Wash 11 / Oil 11). *(The earlier `_uk_classify.py` Bath Emulsion / Bath Oil
split is superseded; the file on disk is the source of truth.)*

**Where UK shows:**
- **Rynek (cross-market topline):** UK is the **5th market**, £ converted to € at
  `GBP_EUR = 1.17` (in `_build_rynek.py`, adjustable). UK ≈ €28M/12M — the largest market;
  new category total ≈ **€77.3M/12M**. Injected into the shared topline **without touching**
  `_build_topline.py` / the sibling `atopic-skin-topline` (string-replacement injections in
  `_build_rynek.py`, each guarded by an exact-match assert): append UK to `MARKETS`, £→€ on
  `rev`/`price`, a no-op `Bath Emulsion→Wash / Bath Oil→Oil` remap (defensive), dynamic market
  count + top-products pills, and note/summary text fixes.
- **Struktura rynku:** UK shown per-country in **£** via `amazon.co.uk` links
  (`CURRENCY_BY_COUNTRY['UK']='£'`, `TLD_BY_COUNTRY['UK']='co.uk'`).
- **VOC + Marketing Deep-Dive:** **no UK data** → UK is hidden from those tabs' country pills
  (`VOC_COUNTRY_CODES = ['DE','FR','IT','ES']`; `setTab` falls back off UK when entering VOC/MDD).

**Build knobs** (in `_build_standalone.py`): `COUNTRIES` (UK added), `STRUCT_SEGMENTS`,
`CURRENCY_BY_COUNTRY`, `TLD_BY_COUNTRY`, `VOC_COUNTRY_CODES`, bundle keys `currencyByCountry` /
`tldByCountry` / `vocCountries`, JS `SEG_LABELS` / `MS_SEG_ORDER`, per-tab `countryCodesForTab()`.

Working scripts (dashboard-local `_uk_*`): `_uk_fetch_listings.py` (DataForSEO
`merchant/amazon/asin/live/advanced`, `language_code='en_GB'`, bullets in `description`;
hit `40200 Payment Required` after 66/203) and `_uk_classify.py` (the superseded
Bath-Emulsion/Bath-Oil classifier — kept for reference).

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

**Tab 1 is generated FROM THIS dashboard's own X-Ray** (updated 2026-07-02).
`_build_standalone.py` runs `_build_rynek.py` first, which reuses
`../atopic-skin-topline/_build_topline.py` **verbatim as the layout source of
truth** but redirects it (via two string replacements) to read the *detailed*
`data/x-ray/{CODE}/Dermo-Products-{CODE}.csv` and write `_rynek_topline.html`
here. The main build then extracts that file's `<style>` + `<body>` and pastes
both into `#panel-market`; its inline `<script>` renders the Chart.js charts
(default-active panel, so charts size correctly).

**Why the fork:** the sibling `atopic-skin-topline` dashboard is on an OLDER
X-Ray (pre atopic-only-oil reclassification) and Tom asked to keep it untouched
while the detailed dashboard reflects the reworked segmentation + added oils.
So Tab 1's financials now match Tabs 2–4. **`atopic-skin-topline` is never read
or written by this build** (only its `_build_topline.py` is read as a template).
**To refresh Tab 1, just rebuild this dashboard** — it regenerates automatically.

## Layout (2026-07-02)

Top-level **dark header bar** (`.ad-header`: title `DASHBOARD_H2` + subtitle +
per-country **X-Ray buttons** DE·FR·IT·ES from `XRAY_LINKS`) sits **above** the
tab bar — same shape as the anti-fungus dashboard. The tab bar (`.ad-tabs`) is
sticky below it. `extract_topline()` strips the topline's own `<header>` so Tab 1
does not show a second header.

## 2026-07-20 — the combined master is now ACTUALLY used (it wasn't)

The round-trip below was designed correctly but **never executed**. `_split_master_xray.py`
matched the master by exact filename, while Google Sheets downloads it with the tab name
appended (`Atopic-Skin-Detailed-ALL-markets - Atopic-Skin-Detailed-ALL-markets.csv`). The
lookup missed, the split printed `master not found`, and the build fell through to the
stale per-country files **without failing**. Everything shipped from those files instead.

Fixed in `_split_master_xray.py`:
- **glob** for `Atopic-Skin-Detailed-ALL-markets*.csv` (ignores `.bak`), so the Sheets
  download filename works untouched
- **per-line encoding fallback** (UTF-8 -> cp1252): the master is genuinely mixed — older
  rows are cp1252/mojibake, newly appended rows clean UTF-8. A plain UTF-8 read raises.
- **dedupe by ASIN** within a marketplace, first occurrence wins (DE had `B00V4PHBO8` twice)
- **UK added to `CODES`**; markets absent from the master leave their per-country file
  untouched and say so in the log
- **missing master = hard error**, never a silent fallback

**The per-country files are derived artefacts — never hand-edit them.** The next build
overwrites them from the master. That is exactly how the drift happened: DE/UK were edited
per-country while the master moved separately.

What changed on first real split (per-country files had been stale):
| Market | Before | After | Note |
|---|---|---|---|
| DE | 145 | 144 | dup `B00V4PHBO8` dropped; `B0BDDNK31J` (bedrop Propolis, Cream) absent from master -> Cream 106 -> 105 |
| ES | 196 | 127 | 52 of the removed are `Check`/`Other` (never rendered); 25 segments reclassified, master is the newer call (shower oils `Wash` -> `Oil`) |
| FR / IT | 166 / 233 | unchanged | identical |
| UK | 103 | untouched | **not in the master** — still the one market outside the single source of truth |

DE segment totals after the split (30d x 12): Cream 105 ASIN / 1 095 000 szt / EUR 16.5M ·
Wash 14 / 82 152 / EUR 0.68M · Oil 25 / 67 896 / EUR 1.09M.

**UK stays out of the master — Tom's decision, 2026-07-20.** UK (103 ASINs) keeps living in
`data/x-ray/UK/Dermo-Products-UK.csv` and is the one hand-maintained per-country file. The
split detects its absence, leaves the file alone, and logs it every run. So "the combined
master is the single source of truth" holds for **DE / FR / IT / ES**; UK is the deliberate
exception. If UK is ever added to the master (`Marketplace = UK`), the split picks it up
automatically and starts overwriting that file — no code change needed, but any hand edits
made in the meantime would be lost.

## X-Ray: single source of truth (combined master)

The editable master is **`data/x-ray/Atopic-Skin-Detailed-ALL-markets.csv`** (873
rows, all 4 markets, with a **`Marketplace`** column DE/FR/IT/ES inserted right
after `URL`). This is the file to upload/share in Google Sheets — a colleague can
filter by Marketplace and reclassify segments in one place.

Round-trip (single source of truth):
1. Colleague edits the master in Google Sheets (segments etc.).
2. Download it back over `data/x-ray/Atopic-Skin-Detailed-ALL-markets.csv`.
3. `python _build_standalone.py` runs `_split_master_xray.py` FIRST, splitting the
   master by `Marketplace` into `data/x-ray/{CODE}/Dermo-Products-{CODE}.csv`
   (Marketplace column dropped to restore the build format), then rebuilds Tabs 1-4.

So the per-country CSVs are now **derived** from the master. `_export_combined_xray.py`
was the one-time bootstrap that built the master FROM the per-country files; going
forward, edit the master. If the master is absent, the build falls back to the
existing per-country files (backward compatible). Round-trip is loss-less (verified:
split reproduces identical per-country data).

## Data file locations

| Data | Path | Shape |
|------|------|-------|
| VOC | `reviews/{CODE}/{Segment}/voc.json` | `u-reviews-voc` contract (POLISH content) |
| MDD | `data/competitor-listings/{CODE}/mdd-{slug}.json` (`slug = segment.lower()`) | `u-marketing-deep-dive` contract (POLISH content) |
| X-Ray (Tab 1 Rynek + Tab 2 Struktura, this dashboard's own copy) | `data/x-ray/{CODE}/Dermo-Products-{CODE}.csv` | Helium 10 X-Ray |

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

## 2026-07-02 — Oil segment added + MDD redesigned (szelki-style)

- **Oil is now a shown segment** (`SEGMENT_ORDER = ['Cream','Wash','Oil']` in `_build_standalone.py`). All 4 countries show Cream/Wash/Oil pills.
- **Oil = atopic-only.** Holds only oils whose title/bullets mention atopic/eczema/dermatitis/sensitive/itchy (verified per-ASIN via DataForSEO full listings; audit in `_oilclassify/{CODE}/_audit.csv`). Non-atopic carrier oils (e.g. MAYJAM) reclassified out. Method = 2-step on **title + bullet points** (SP-API exposes no A+/Brand Story).
- **Oil reviews**: FR/IT/ES pooled into `reviews/{CODE}/Oil/all-reviews.json` via `parse_raw_reviews.py` (parses a Word/`.txt` review dump from `reviews/{CODE}/Oil/_raw/` → JSON, dedupes). DE uses per-ASIN files. Stray per-ASIN oil files moved to `reviews/_superseded/`. `voc_quick.py` = quick theme-scan helper.
- **MDD redesigned to szelki-detailed style for ALL segments.** New dashboard-local template `templates/tabs/u-marketing-deep-dive/template.html` (self-contained CSS scoped to `#u-mdd-root`, Polish). `MDD_TPL` repointed from Console-level to this BASE-local file.
  - `mdd_pipeline.py` emits the szelki schema (see `_MDD_SCHEMA.md`): `competitors[]` with `themeSrc` **source attribution (T=title / BP=bullets)**, `themes[]`, `adoption[]`, tiered `saturation[]`, `whitespace[]`, `vocGap[]`, typed `recs[]`, `avgClaims`. No `A+` source tag (SP-API limitation).
  - Renderer order: KPI strip → competitor grid + click-detail → image/bullet compares → adoption table → **source-attributed claims matrix** → VOC-gap → whitespace+saturation → typed recs → methodology.
- **`voc_pipeline.py` SRC repointed** from `../atopic-skin-topline/reviews` (now empty) to local `reviews/`.

## 2026-07-02 (later) — Struktura rynku (Market Structure) added as tab #2

- **Tab order is now** `Rynek → Struktura rynku → Recenzje (VOC) → Marketing Deep-Dive`
  (MDD stays last, matching the anti-fungus / other dashboards). Tab #2 is the new one.
- **New tab `structure`** ports the Console `market-structure` tab, per country, with
  Cream/Wash/Oil as **internal segment sub-tabs**. Reuses the **country pills** (DE/FR/IT/ES);
  the shared **segment pills are hidden** on this tab (segments live inside it via sub-tabs).
- **Dashboard-local Polish template**: `templates/tabs/market-structure/template.html`
  (reads `window._TAB_DATA`, root `#ms-tab-root`, self-contained CSS scoped to
  `#panel-structure`). Build converts its IIFE → `renderMarketStructure(D, root)` via the
  same `to_named_renderer` used for VOC/MDD — **no translation table** (template is already PL).
- **Data**: `_build_standalone.py` → `load_structure(code)` parses `data/x-ray/{CODE}/Dermo-Products-{CODE}.csv`,
  keeps only Cream/Wash/Oil, emits per-product `{asin,title,type,brand,price,sales30d,revenue30d,
  bsr,rating,reviewCount,units12m,revenue12m}` into `bundle.structure[CODE]`. **12M = 30d × 12**
  (flat — no per-ASIN sales history here, same as the Rynek topline). Revenue = units12m × price.
  Structure ASINs: DE 180, FR 95, IT 109, ES 88.
- **Engine**: Console `js/data-engine.js` is inlined once as its own `<script>` (provides
  `DataEngine` aggregation + sortable tables). `renderStructure()` (shell) aggregates the
  selected country's products, sorts segments to Cream/Wash/Oil, assigns colors, sets
  `amazon.<tld>` for ASIN links, then calls `renderMarketStructure`. Stale `ms*` Chart instances
  are destroyed before each re-render so the seg-tab resize-all never touches a detached canvas.

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
