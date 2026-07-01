# RESUME — Atopic Skin (Detailed) build

*Paused 2026-07-01. Continue tomorrow.*

## Goal
Duplicate the **"Atopic Skin" topline** (`dashboards/dermo-products`, cross-market DE/FR/IT/ES)
into a NEW **detailed** standalone `dashboards/atopic-skin-detailed/` and add VOC + MDD.

## Decisions locked (from user)
- **3 tabs**: `Rynek` (Tab1) · `Recenzje (VOC)` (Tab2) · `Marketing Deep-Dive` (Tab3)
- **Tab 1 = faithful topline copy** (exact cross-market view from `dermo-products/index.html`;
  NO country pills on Tab 1 — pills only on VOC/MDD tabs)
- **VOC layout = country × segment** buckets, with country + segment pills
- **Language = POLISH** for ALL labels AND quotes (translate DE/FR/IT/ES → PL)
- Hub group = **detailed**, template = **standalone**

## Data available
- X-Ray copied locally: `data/x-ray/{DE,FR,IT,ES}/Dermo-Products-{CODE}.csv` ✅
- Raw reviews (source, in `dermo-products/reviews/`): 13 buckets
  - DE: Check(8) Cream(10) Oil(16) Wash(10)
  - FR: Cream(8) Oil(9) Wash(6)
  - IT: Cream(8) Oil(1) Wash(10)
  - ES: Cream(8) Oil(1) Wash(3)
- Competitor listings (source, in `dermo-products/data/competitor-listings/`): DE495 FR350 IT334 ES429

## Architecture (model on eu-wasp-analysis)
- `dashboards/eu-wasp-analysis/_build_standalone.py` = canonical shell to reuse:
  3-tab shell, country/segment pills, single dynamic panel, `renderReviews()`,
  `renderMarketingDeepDive()`, brand→color map, `makeAllTablesSortable`.
- VOC renderer + data contract: `templates/tabs/u-reviews-voc/template.html`
- MDD renderer + data contract: `templates/tabs/u-marketing-deep-dive/template.html`
- Tab1 faithful copy: extract `<style>` + `<body>` inner (header+sections+inline script)
  from `dashboards/dermo-products/index.html`, embed as the (default-visible) Rynek panel.
- Topline aggregation logic to reuse: `dashboards/dermo-products/_build_topline.py`
  (load_market, flat ×12 multiplier, segments Cream/Wash/Oil).

## Data file targets (to generate)
- VOC: `dashboards/atopic-skin-detailed/reviews/{CODE}/{Segment}/voc.json` (schema = u-reviews-voc contract, POLISH)
- MDD: `dashboards/atopic-skin-detailed/data/competitor-listings/{CODE}/mdd-{slug}.json` (schema = u-marketing-deep-dive contract, POLISH; slug = segment.lower())

## Next steps (tomorrow)
1. Author `dashboards/atopic-skin-detailed/_build_standalone.py` (shell + faithful Tab1 + VOC/MDD wiring, Polish UI; graceful "Brak danych" placeholder when a bucket JSON is missing). Build once with placeholders so it renders.
2. Register central `config.json` → add `{"id":"atopic-skin-detailed","title":"Atopic Skin — Detailed (DE, FR, IT, ES)","group":"detailed","template":"standalone","file":"index.html"}` near the dermo-products entry.
3. PILOT VOC bucket DE/Cream → validate schema + Polish quality + renders in Tab2.
4. Mass-produce remaining 12 VOC buckets (parallel sub-agents, one per bucket).
5. MDD: per country×segment pick top-N competitors from X-Ray Segment + pull listing JSON → tag claims → mdd-{slug}.json (Polish).
6. Build index.html, test, deploy `git push origin master:main`, update `02-Projects/Dashboards/tracking.md` + this folder's CLAUDE.md.

## Notes / open
- Segment pills per country should auto-reflect available buckets (DE has Check; others don't).
- Tiny buckets (ES Oil=1, ES Wash=3, IT Oil=1) → weak VOC signal; flag in those panels.
- New folder reads raw reviews/competitor-listings from sibling `../dermo-products/`; only ships derived voc.json/mdd.json + X-Ray + index.html.
