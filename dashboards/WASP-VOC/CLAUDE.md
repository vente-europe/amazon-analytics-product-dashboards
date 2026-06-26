# Wasp VOC (Standalone Dashboard)

> Living document — update after every bug fix or new pattern found.

## Purpose

Single-market **Voice of Customer** dashboard for the wasp-control category. One tab only — Reviews VOC — built from the canonical `u-reviews-voc` tab template.

## Status

**Live — populated 2026-06-22.** Single US market, 43 reviews of one wasp / yellow-jacket lure-trap category. VOC analysed, `index.html` built.

## Scope (decided 2026-06-22)

- **Single market — United States** (`countryCode: "US"`, currency `$`)
- **Reviews VOC only** (the `u-reviews-voc` tab) — pure voice-of-customer, no Total Market / Market Structure / MDD tabs
- Sidebar label: **Wasp VOC** (registered in `../../config.json` under the `detailed` group, `template: "standalone"`)

## Data & findings

- Source: `reviews/reviews-merged.csv` — 43 English reviews, columns `rating,title,body` (read with `utf-8-sig`; the CSV has a BOM).
- Sharply **bimodal**: 15×1★ / 8×2★ / 0×3★ / 3×4★ / 17×5★ (avg 2.98). Efficacy is the swing factor — 21/43 report little or no catch; 20/43 report dramatic catches.
- The VOC bucket is built by `scripts/build_voc.py`, which holds **per-review analyst coding** (theme / who / where / time-to-result) and computes every % and chart count from it + keyword extraction (so numbers are reproducible and match the tagged review browser). This is the sanctioned "Reviews VOC is AI-analysed" exception to Zero Hardcoded Values.

## Tech stack

- Self-contained `index.html` — vanilla HTML + JS, Chart.js 4.4.4 + ChartDataLabels via CDN
- Works on `file://` and via the Hub iframe
- Composes `templates/tabs/u-reviews-voc/template.html` — that template is **self-contained** (its `.voc-*` CSS is inlined), so the build is a single string-inline: set `window._TAB_DATA` then drop the template markup after it.

## Folder layout

```
WASP-VOC/
├── CLAUDE.md
├── config.json            ← local config (name/type/marketplace)
├── dashboard.json         ← config + baseTabs.reviews (the VOC_DATA bucket)
├── _build_standalone.py   ← reads dashboard.json, inlines u-reviews-voc, writes index.html
├── index.html             ← built output
├── scripts/build_voc.py   ← per-review coding → computes the VOC bucket into dashboard.json
├── reviews/               ← reviews-merged.csv (rating,title,body)
└── data/x-ray/            ← optional — ASIN metadata source (star dist, etc.)
```

## CRITICAL RULE: Zero Hardcoded Values

Per Console CLAUDE.md — every number must come from data. The **only** exception is the Reviews VOC bucket (`baseTabs.reviews`), which is AI-analyzed (themes, quotes, strategy insights) and stored in `dashboard.json`. Nothing else is hand-typed.

## Build / re-build workflow

1. Drop scraped review files into `reviews/`.
2. Run VOC analysis → populate `dashboard.json → baseTabs.reviews`. Shape = the data contract at the top of `templates/tabs/u-reviews-voc/template.html` (`countryName`, `countryCode`, `segmentName`, `totalReviews`, `avgRating`, `starDist`, `cpSummary`, `cpWho/When/Where/What`, `usageScenarios`, `csSummary`, `negativeTopics`, `positiveTopics`, `negativeInsights`, `positiveInsights`, `buyersMotivation`, `customerExpectations`, `themeFilters`, `tagStyles`, `reviews[]`).
3. Set `countryName` / `countryCode` (single market) and `xrayLink` in `dashboard.json`.
4. Run `py _build_standalone.py` → regenerates `index.html`. When `totalReviews > 0` the build emits the full dashboard; otherwise it writes the "awaiting data" placeholder.

## Self-update rule

Update this file after every structural change, new data convention, or build-script tweak.
