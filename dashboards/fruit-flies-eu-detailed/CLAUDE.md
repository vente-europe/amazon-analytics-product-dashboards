# Fruit Flies EU — Detailed

> Living document — update after every bug fix or new pattern found.

## What this is

Single-tab standalone dashboard for the **Fruit Fly Trap** category across 4 EU
Amazon markets: **FR, IT, ES, UK**. Registered in the Console hub
(`config.json` id `fruit-flies-eu-detailed`, group `detailed`, template
`standalone`).

**Two tabs**, Polish UI, segment-less (pack-size structure instead of a product
segment):
- **Tab 1 "Rynek"** — Total Market / cross-market topline. The
  atopic-skin-detailed / provecta-eu-detailed **Rynek** tab rebuilt for fruit
  flies. Built by `_build_rynek.py` → `_rynek_topline.html`.
- **Tab 2 "Struktura rynku"** — pack-size × brand market structure per country
  (+ an "All EU" pooled view via pills), modelled on the **fruit-fly-trap-DE**
  dashboard's Market Structure tab. Built by `_build_structure.py` →
  `_structure.html`. Charts render lazily the first time the tab opens
  (`window.__structRender`) so canvases size correctly.
- **Tab 3 "Recenzje (VOC)"** — **UK-only** Voice-of-Customer. Built by
  `_build_voc.py` → `_voc.html`, which **reuses the canonical
  `templates/tabs/u-reviews-voc/template.html` renderer + Provecta's Polish
  transform** (patch + string translations). Single "Wielka Brytania (UK)" pill
  (only UK has scraped reviews). Renders lazily via `window.__vocRender`. See the
  VOC section below.

## Language & currency

- **Polish UI** (matches the atopic/provecta detailed dashboards Tom referenced).
- **All values in EUR.** UK X-Ray was in GBP; converted to EUR at **1.1666**
  (interbank rate fetched 2026-07-29) upstream, during data consolidation.

## Data source (single file)

`data/x-ray/fruit-flies-eu-consolidated.csv` — produced by the sibling topline's
consolidation step (`../fruit-fly-trap-eu-topline/data/xray/_consolidate.py`).
That file already:
- carries a **`Country`** column (FR / IT / ES / UK) right after `ASIN`,
- is **deduped by ASIN within each country**,
- has every monetary column in **EUR** (headers `Price €` / `Fees €`; UK GBP
  converted at 1.1666).

So `_build_rynek.py` does **not** convert currency again — it only aggregates.
If the source X-Ray refreshes: re-run `_consolidate.py` in the topline folder,
copy the new `fruit-flies-eu-consolidated.csv` here, then re-run the build.

## Build pipeline

```
python _build_standalone.py
```

1. Runs `_build_rynek.py` → tab 1 body (`_rynek_topline.html`): reads the
   consolidated CSV, splits by `Country`, reads `data/seasonality-de.json`,
   aggregates per market (30d × seasonal multiplier).
2. Runs `_build_structure.py` → tab 2 fragment (`_structure.html`): reads the
   consolidated CSV incl. the **`Pack`** column, same seasonal multiplier, builds
   per-country + "All EU" pack-size × brand aggregates, emits an embedded-JSON
   renderer (pack/brand pies, brand-by-pack, price-by-pack, price-vs-share bubble
   scatter, pack & brand tables, top ASINs, DE seasonality index chart).
3. Runs `_build_voc.py` → tab 3 fragment (`_voc.html`): reads
   `data/reviews/*.xlsx` (UK), computes grounded theme %s + picks real quotes,
   transforms the `u-reviews-voc` template to Polish, embeds the VOC bucket.
4. Assembles the `ad-*` shell (header + 3-tab bar + 3 panels) → `index.html`.
   Tabs 2 & 3 draw lazily on first open via `window.__structRender()` /
   `window.__vocRender()`.

### VOC tab (Tab 3, UK only)

- **Reviews:** `data/reviews/*.xlsx` — H10-style scrape. Currently
  `B07PN3XFD5` (PIC, 191) + `B0GR8MRDR2` (HIULLEN, 6) = **197 reviews**, amazon.co.uk.
- **Needs `openpyxl`** — install into the real Python 3.11
  (`C:\Users\tommi\AppData\Local\Programs\Python\Python311\python.exe -m pip install openpyxl`).
  Run the whole build with THAT python so the `_build_voc.py` subprocess inherits it.
- **Renderer:** reuses `templates/tabs/u-reviews-voc/template.html` via
  `to_named_renderer` + `apply_patches` (VOC_PATCH) + `apply_translations`
  (VOC_STR) — the same machinery Provecta uses. If that template changes, the
  verbatim patch anchors in `_build_voc.py` may break (it raises a clear error).
- **Headline honesty:** the 197-review scrape skews critical (sample avg **3.6**)
  vs the X-Ray listing rating (**3.9**, weighted over the 2 UK ASINs). So the KPI
  shows the **X-Ray rating** as the population figure; the scraped star bar is
  labelled "próbka 197" with an explicit note. Analytical labels/insights are
  Polish (AI-analyzed — the VOC exception to zero-hardcoded); **quotes are real
  verbatim English snippets** auto-picked from the reviews; theme %s are keyword
  tallies over the actual text (not fabricated).
- **To add more markets later:** drop `{ASIN}-{CC}-Reviews-*.xlsx` in
  `data/reviews/`, extend `_build_voc.py` to bucket by country + add pills. For
  now it is deliberately UK-only.

`data/seasonality-de.json` is regenerated separately by `_build_seasonality.py`
(reads the DE dashboard's daily sales) — see the Seasonality section below.

### Pack column (Tab 2 input)

The consolidated CSV has a **`Pack`** column (integer traps per multipack, after
`Country`) added by Tom in the source Excel. Tab 2 is driven by it. If the Excel
is refreshed, re-copy the CSV here and rebuild. Data-hygiene note (2026-07-29
build): the Brand column had one Excel error value (`#NAME?`) and some `Unknown`
brands — surfaced as-is in the brand table, worth cleaning at source.

## Rynek tab contents (auto-computed from CSV — zero hardcoded numbers)

- KPI row: total 12M revenue, total 12M units, market count, unique ASIN count
- Auto-generated Polish executive summary (markets / brands / prices)
- Revenue-by-market bar + unit-share doughnut
- Units & revenue per-market table
- Brand-share pies (revenue + units, all markets combined)
- Brand × market heatmaps (revenue + units), top 12 brands + "Pozostałe"
- Top 10 products per market (pill selector) + advanced all-products table with
  market/keyword filters

## Method / conventions

- **12M = 30d × seasonal multiplier** (NOT flat ×12). The multiplier comes from
  the **German fruit-fly seasonality curve** — see below.
- Markets **re-sorted by 12M revenue** (largest first) for consistent visuals.
- 30d units estimated as `ASIN Revenue / Price` (like provecta), not raw
  `ASIN Sales`. **Open question:** this overstates units ~15-20% vs the H10
  `ASIN Sales` column; not yet switched (Tom to decide). Revenue is unaffected.
- Style rule: **no em/en dashes** anywhere in generated HTML (build asserts this).

## Seasonality (German curve)

Applied 2026-07-29. The flat ×12 overstated the year because the X-Ray window
(July) is fruit-fly high season. Correction:

- `_build_seasonality.py` reads the **fruit-fly-trap-DE** dashboard's 3y daily
  sales (`02-Projects/Dashboards/Fruit Fly Trap - DE/Data/sales-units/`, 49 ASINs,
  ~2024-03..2026-03), pools market daily units, averages per calendar month,
  normalizes to **avg month = 1.0**, and writes `data/seasonality-de.json`
  (committed — the DE folder does not ship to Pages).
- `_build_rynek.py` reads that JSON, `EXPORT_MONTH = 7` (July), and sets
  **multiplier = 12 / index[July] = 12 / 1.519 = ×7.90** (vs flat ×12).
- Same multiplier applied to **all 4 markets** (all exports share the July window).
- DE monthly index (avg month = 1.0): Jan 1.09 · Feb 1.16 · Mar 0.47 · Apr 0.44 ·
  May 0.51 · Jun 0.94 · **Jul 1.52** · Aug 1.80 · Sep 1.39 · Oct 0.94 · Nov 0.98 ·
  Dec 0.76. Peak Jul-Sep, trough Mar-May.
- **Caveat:** the German curve is a proxy for FR/IT/ES/UK; real per-market
  seasonality may differ. Stated in-app in the methodology note.
- Effect: total 12M revenue €8.12M → **€5.35M**; 12M units 645k → **425k**.
- To re-derive if DE sales refresh: `python _build_seasonality.py` then
  `python _build_standalone.py`. To change the export month, edit `EXPORT_MONTH`
  in `_build_rynek.py`.

## Data note (2026-07-29 build)

Category is extremely concentrated: **UK ≈ 82% of revenue** and brand
**Super Ninja ≈ 90%** of category revenue. These are raw H10 X-Ray figures — not
adjusted. Worth sanity-checking UK volume against a second source before using
the topline for decisions.

## Deploy

Console hub is one repo. Push per the workspace rule:
`git push origin master:main` (GitHub Pages serves from `main`).
Live path once deployed: the hub URL with `#fruit-flies-eu-detailed`.
