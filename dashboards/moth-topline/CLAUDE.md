# Moth Control — Topline Dashboard (Skeleton)

> Living document — update after every bug fix or new pattern found.

## Status

**Empty skeleton** — folder structure and build script copied from `dermo-products` (Atopic Skin topline). No data yet.

## Purpose

Multi-market topline view of the moth-control category. Same layout as Atopic Skin (UK / DE / ES / FR / IT) — single-page topline with revenue/units per market, segment × market heatmap, top brands per segment.

## Tech stack

- Vanilla HTML + JS + CSS, Chart.js via CDN
- Self-contained `index.html` (works on `file://` and via Hub iframe)
- Build script: `_build_topline.py` (copy of dermo-products one, with file pattern + segments swapped)

## Folder layout

```
moth-topline/
├── CLAUDE.md
├── _build_topline.py        ← config block at top (SEGMENTS, XRAY_LINKS), then build logic
├── index.html               ← empty placeholder until first build
├── data/
│   ├── x-ray/{UK,DE,ES,FR,IT}/         ← drop Moth-{CODE}.csv here
│   ├── sales-data/{UK,DE,ES,FR,IT}/    ← per-ASIN daily sales (optional)
│   └── competitor-listings/{UK,DE,ES,FR,IT}/
├── reviews/                  ← per-market review files (optional)
└── scripts/                  ← copied from dermo-products (audit/classify/fetch helpers)
```

## Before first build — TODO

1. **Drop X-Ray CSVs** into `data/x-ray/{CODE}/Moth-{CODE}.csv` (one per market: UK/DE/ES/FR/IT)
2. **Update `SEGMENTS`** in `_build_topline.py` to match the actual moth-control segments in your X-Ray. Current placeholder: `['Pheromone trap', 'Sticky trap', 'Repellent']`. Likely real segments: Pheromone trap, Sticky trap, Spray, Cedar/Lavender repellent, Mothballs.
3. **Update `XRAY_LINKS`** with the Google Sheet URLs for each market (currently `'#'` — header buttons go to the sheets).
4. **Run** `py _build_topline.py` from this folder to regenerate `index.html`.

## Hub integration

Registered in `projects/Console/config.json` under the `topline` group as `Moth (UK, DE, ES, FR, IT)`.

## Data conventions

- **X-Ray CSV** — Helium 10 export, must include `ASIN`, `Segment`, `Brand`, `Product Details`, `ASIN Sales`, `ASIN Revenue`, `Price ...`, `Ratings`, `Review Count`, `BSR`.
- **12M projection** — flat 30-day × 12 (Topline only). For seasonality, switch to a Detailed dashboard pattern.

## Self-update rule

Update this file after every structural change, new data convention, or build-script tweak.
