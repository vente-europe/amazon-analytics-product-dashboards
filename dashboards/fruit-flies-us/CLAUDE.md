> Living document — update after every bug fix or new pattern found.

# Fruit Flies (US) — Standalone (single-tab proof of `u-*` composition)

## Purpose

First dashboard built by composing the new canonical `u-*` standalone tab templates. Currently a single tab — **u-main-segments** — pointed at the Amazon US fruit fly trap category.

This is the workflow reference: future dashboards are assembled the same way — pick `u-*` tabs in the order Tom specifies, fill the data contract, build.

## Data source (local — canonical home for the fruit fly US data)

All source data lives inside this folder. Standard Console layout — every dashboard has its own `data/` and `reviews/` subfolders.

| Source | Path | Files |
|---|---|---|
| **X-Ray (current — May 24, 2026)** | `data/x-ray/merged-may-segmented.csv` | 210 ASINs from 3 H10 keyword exports (`plug in fly trap`, `flying insect trap`, `fruit fly trap`), segmented via `Segment` column (31 still unassigned — get skipped at build, awaiting manual classification) |
| X-Ray (raw May merge, pre-segmentation) | `data/x-ray/merged-may.csv` | Same 210 ASINs without the Segment column |
| X-Ray (previous — Feb 25, 2026) | `data/x-ray/Fruit-Flies-US-new-merged-data.csv` | 207 ASINs, single-keyword pull, segmented via `Type` column. **Kept for historical comparison — see `data-snapshot-feb-vs-may-2026.md`.** |
| X-Ray (earlier Feb export) | `data/x-ray/Fruit-flies-traps-24-02.csv` | Older Feb-24 export, fewer ASINs |
| X-Ray (auxiliary) | `data/x-ray/merged-variations.csv` | Variation-merge intermediate file from the Feb run |
| Per-ASIN daily sales | `data/sales-data/` | 80 CSVs (`{ASIN}-sales-3y.csv`) — only ~46 currently match the May X-Ray ASINs (per the Feb→May rotation: ~67% of old ASINs no longer appear) |
| DD / Niche | `data/dd/` | H10 Niche competitors + keywords (2 CSVs) — feeds future Keyword Analysis tab |
| Reviews | `reviews/` | 13 files — 5 scraper JSON dumps, `terro_*.json`, `hs_reviews.json`, `voc_analysis.json`, plus a `.docx` summary |

### Feb → May snapshot rotation

See [data-snapshot-feb-vs-may-2026.md](data-snapshot-feb-vs-may-2026.md) for the full analysis. Headlines:

- **~67% ASIN turnover** between Feb and May SERPs (only 68 of 207 old ASINs persist in the May 210). Causes: different keywords pulled (1 vs 3), natural Amazon SERP rotation, summer-peak ramp.
- **Segmentation rebuilt** in May: 68 ASINs inherit their old segment, 111 auto-assigned to Electric Traps via title regex, 31 still unassigned.
- **Multiplier collapsed** from ×31.52 (Feb, deep trough) to ×13.63 (May, closer to average month). xrayWindowIndex 0.381 → 0.880.

Re-run `python _build_standalone.py` after any X-Ray / sales-data refresh in `data/`.

## Tabs

| # | Tab | Template | Data |
|---|-----|----------|------|
| 1 | Total Market | `templates/tabs/u-main-segments/template.html` | Built into `_TAB_DATA` by `_build_standalone.py` |
| 2 | Segments Market Structure | `templates/tabs/u-segments-market-structure/template.html` | Built into `_TAB_DATA` by `_build_standalone.py` |
| 3 | Reviews VOC · Lure | `templates/tabs/u-reviews-voc/template.html` (urv→urvL) | `voc-lure.json` (per-segment AI VOC) |
| 4 | Reviews VOC · Electric | `templates/tabs/u-reviews-voc/template.html` (urv→urvE) | `voc-electric.json` (per-segment AI VOC) |
| 5 | Marketing Deep-Dive · Lure | `templates/tabs/u-marketing-deep-dive/template.html` (mdd-→mddL-) | `data/mdd/mdd-lure.json` |
| 6 | Marketing Deep-Dive · Electric | `templates/tabs/u-marketing-deep-dive/template.html` (mdd-→mddE-) | `data/mdd/mdd-electric.json` |

Two-instance-per-page template reuse is done by substring-prefixing the template
file at build time so the IDs/CSS-classes never collide:
- u-reviews-voc — `urv` → `urvL` / `urvE`
- u-marketing-deep-dive — `mdd-` → `mddL-` / `mddE-` (covers both `#mdd-root` and `#u-mdd-modal` / `#u-mdd-tab-root`)

## Marketing Deep-Dive (Tabs 5 + 6)

- Top-15 ASINs per segment by 12M revenue (Lure: 33 ASINs total → top 15; Electric Traps: 144 → top 15). Adjust `TOP_N` in `_build_mdd.py` to change.
- Theme tagging is **title-only** — we don't fetch SP-API listings for this dashboard yet, so claims that brands put only in bullets/descriptions are MISSED. The themes-claimed counts are therefore a lower bound on real adoption rates.
- VOC gap analysis cross-references the per-segment `voc-*.json` `negativeTopics` against the claim adoption matrix using `VOC_HINTS` in `_build_mdd.py`.
- Re-run `python _build_mdd.py` after any X-Ray refresh or VOC rebuild, then `python _build_standalone.py` to bundle into `index.html`.

Add more tabs by inlining additional `u-*` templates into the shell and extending `_TAB_DATA` to match each template's data contract.

## Reviews VOC pipeline (Tabs 3 + 4)

The VOC pools started as a **negative-only** scrape (the `dataset_amazon-reviews-scraper_*.json` files only held 1-3★ reviews). On 2026-06-01 a **positive pull** (`reviews/us-fruitfly-positive-2026-05-31/`, 39 ASINs / 296 reviews, mostly 4-5★) was merged in to rebalance.

Pipeline order:
1. `python _extract_voc_samples.py` — builds `_voc_work/{slug}_all.json` + `_sample.json`. Ingests: (a) the `dataset_*` scrape segment-filtered to Lure/Electric, (b) the positive folder **gated to ASINs already in the pools** (17 Sticky/Passive/off-X-Ray ASINs skipped — no tab), and (c) the legacy **aggregate `terro_reviews.json` + `hs_reviews.json`** files (stars+review only, no ASIN) → assigned to **Lure** by brand, deduped by normalized review text against the existing pool (+509 new; ~238 already present via dataset are skipped). Result: **Lure 2,265 / Electric 1,264** (Lure avg 1.77→2.11 because the aggregate files are a full scrape, ~51% positive). **Caveat:** the AI topic %s in `lure_ai.json` were computed before this +509 supplement — KPIs (total/avg/starDist) recompute correctly in `_assemble_voc.py`, but `negativeTopics`/`positiveTopics` percentages are approximate until the AI analysis is re-run.
2. `python _build_ai_prompt.py` → `_voc_work/{slug}_prompt.txt` (Gemini re-analysis prompt; Gemini's `analyze-document` MCP is currently pinned to a retired model, so re-analysis was authored in-context).
3. `python _rebalance_ai.py` — overrides the sentiment-sensitive fields in `_voc_work/{slug}_ai.json` (cpSummary, csSummary, positiveTopics, positiveInsights, cp* `pos[]` arrays) with positive-grounded content; **keeps** the verified `negativeTopics`, `customerExpectations`, `usageScenarios`, and `neg[]` arrays.
4. `python _assemble_voc.py` → `voc-lure.json` / `voc-electric.json`. Two extras here: (a) the review-browser list is **deduped by full normalized text** before the 200-cap, so variant-syndicated reviews never show twice (esp. adjacent after the date sort); (b) each `negativeTopic` gets a **real `foundIn` string** — `NEG_TOPIC_REGEX` (per segment, keyed by AI topic label) counts matching negative (1-3★) pool reviews → `"Found in X of Y negative reviews (Z%)"`, replacing the AI-estimated `pct` with a verifiable regex count (standalone-style) and re-sorting topics by real prevalence. Regexes are heuristics (efficacy topics broadened to the dominant "doesn't work / caught nothing" language) — approximate, like the standalone's `neg_themes`. (c) `sync_insight_numbers` rewrites the leading quantity in each quantified `negativeInsight` finding (mapped via `INSIGHT_TOPIC`) to the real regex topic % — so "Efficacy Crisis: 35.0%" in the insights matches the topic dropdown instead of the stale AI estimate ("Over 40%").
5. `python _build_standalone.py` → `index.html` (loads the two `voc-*.json` at lines ~413-414; the printed "1,644/1,200" summary is a **stale legacy recompute block**, NOT what the tabs render).

Brand coverage: Lure VOC = Aunt Fannie's, Qualirey, Terro, Super Ninja, Raid, **HOT SHOT**, STEM (all single/dual-ASIN). Electric VOC = Zevo, LFSYS, VEYOFLY, BugMD, FVOAI. Terro and HOT SHOT are Lure-only.

## Segments (normalized from the X-Ray `Type` column)

Canonical 4 — order matters (drives KPI card column + pie slice order):

1. **Lure** (40 ASINs)
2. **Sticky Traps** (74 ASINs — `Sticky Traps` + `Sticky traps` merged via `SEGMENT_MAP`)
3. **Passive Attractor** (7 ASINs — `Passive attractor` cased up)
4. **Electric Traps** (86 ASINs)

`SEGMENT_COLORS`: Lure green · Sticky Traps amber · Passive Attractor purple · Electric Traps red.

## 12M projection methodology (with May 2026 data)

- **179 ASINs in scope** (210 May ASINs minus 31 unsegmented).
- **46 ASINs** have per-ASIN sales history → real trailing-365-day sum.
- **133 ASINs** without history → projected as `30d × x13.63` (median of actual 12M ÷ May-30d ratios across the 46 with history). Equivalent to `30d ÷ 0.880 × 12` (May seasonality index = 0.880).
- Peak month **Oct (2.02×)**, trough **Mar (0.36×)** — May is close to an average month, so the projection multiplier is modest.

These figures + the per-month curve drive the seasonality bar chart and the EN/PL methodology panel at the bottom of the tab.

## Build / re-build

```
python _build_standalone.py
```

Regenerates `index.html`. No additional steps; the build inlines `css/hub.css` and the `u-main-segments` template at build time, so a single self-contained file is produced.

## Self-Update Rule

Update this file when adding tabs, changing the data source, or hitting a build/render issue.
