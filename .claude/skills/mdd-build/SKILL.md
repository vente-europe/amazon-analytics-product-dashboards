---
name: mdd-build
description: Build a Marketing Deep-Dive (MDD) bucket for a dashboard — fetch top-N competitor listings via SP-API, analyze bullets/description in-context, and write a segment-scoped mdd-{segment}.json that the dashboard renderer consumes. Use when the user says "build MDD for X", "Marketing Deep-Dive for {country} {segment}", "add MDD", or "fetch competitor listings".
---

# Marketing Deep-Dive (MDD) Builder

Produces data for the Marketing Deep-Dive tab of a dashboard. Zero paid-API cost: SP-API catalog calls are free (seller refresh token), and the competitive analysis (claims matrix, VOC gap, whitespace, saturation, recommendations) is done **by Claude reading the listings in-context** — not by a paid LLM API.

## When to use

Triggers:
- "Build MDD for {country} {segment}"
- "Marketing Deep-Dive for {dashboard}"
- "Add MDD", "fetch competitor listings for MDD"
- "Next country for MDD" / "Now do FR" (after a prior bucket is done)

## Inputs required from the user

| Input | Default if missing |
|---|---|
| Dashboard folder | The current CWD if inside a dashboard project |
| Country code | Ask (DE / FR / IT / ES / UK / US …) |
| Segment split | Ask: single bucket, or split by segment (Prevention/Treatment, Rx/OTC, etc.)? Match the dashboard's existing segment column. |
| Top-N count | "Big market" → **15**, "smaller market" → **10**. Ask if ambiguous. For very small segments (< top-N), take all available products. |

## Reference implementations

- **Single-bucket (anti-fungus pattern)** — `projects/Console/dashboards/anti-fungus-nail-polish/scripts/{fetch_competitor_listings.py, build_mdd.py}`. One country, one MDD tab, one `mdd.json`.
- **Segment-split, hand-curated tagging (EU lice pattern)** — `projects/Console/dashboards/eu-lice-treatment-analysis/scripts/{fetch_competitor_listings.py, build_mdd.py}`. Multi-country, per-segment tabs, `mdd-{segment}.json` per country. Theme assignments per ASIN are hardcoded after Claude reads each listing. **Best quality** but slowest to ship.
- **Segment-split, regex tagging (EU wasp pattern)** — `projects/Console/dashboards/eu-wasp-analysis/scripts/{fetch_competitor_listings.py, build_wasp_mdd.py}`. Same multi-country, per-segment shape as lice, but theme tagging is **regex-based on title + bullets + description** (multilingual: DE/FR/EN patterns in one regex per theme). One script handles all 6 buckets in one run via nested `for code in ('DE','FR','UK'): for seg in ('lure','electric'):`. Auto-generates `vocGap` by cross-referencing the dashboard's existing `reviews/{CODE}/{Segment}/voc.json` `negativeTopics` against the regex-tagged competitor themes. **Faster to ship** (a few hours vs a day), with quality scaling on how cleanly competitors phrase claims (UK English listings tag better than terse DE technical bullets). Image URLs must be normalised: SP-API returns `{variant, url, width, height}` dicts; extract `img['url']` before storing into `competitors[].mainImage` and `images[]` or the dashboard renders `[object Object]`.

**Picking between hand-curated and regex tagging:**
- Use **hand-curated** when listings are dense, claims are subtle, or you need premium accuracy (pharma, dermo).
- Use **regex** when listings are punchy and use predictable language (consumer goods, traps/zappers/repellents). Pair it with the auto VOC-gap step for an end-to-end pipeline that runs in seconds.

## Pipeline

### Step 1 — Pick top-N ASINs per bucket

Read the country's X-Ray CSV and rank by **30d ASIN Revenue** (`ASIN Revenue` column). Filter by segment (column varies — usually `Segment`, `Focus`, or `Type`; eu-lice uses `Focus`).

CSV number parsing: Helium 10 exports use **US format** — `,` as thousand separator, `.` as decimal. Strip `,` and `€`, then `float()`. **Do not** treat `.` as a thousand separator.

Write one text file per bucket:
```
data/competitor-listings/{CODE}/asins-{segment}.txt
```
One ASIN per line. Deduplicate — H10 exports sometimes contain dupes.

### Step 2 — Fetch catalog listings via SP-API

Copy `scripts/fetch_competitor_listings.py` from **eu-lice** (not anti-fungus — eu-lice's is parameterized by country + segment). Keys:

- Reads from `c:\AI Workspaces\Claude Code Workspace - Tom\.env` → `SP_API_CLIENT_ID`, `SP_API_CLIENT_SECRET`, `SP_API_REFRESH_TOKEN`.
- EU refresh token works for DE / FR / IT / ES / UK / NL / SE / PL. US needs a separate token.
- Marketplace IDs: DE `A1PA6795UKMFR9`, FR `A13V1IB3VIYZZH`, IT `APJ6JRA9NG5V4`, ES `A1RKKUPIHCS9HS`, UK `A1F83G8C2ARO7P`, NL `A1805IZSGTT6HS`, US `ATVPDKIKX0DER`.
- Endpoint: `https://sellingpartnerapi-eu.amazon.com` for EU, `https://sellingpartnerapi-na.amazon.com` for NA.
- Extracts: `title`, `brand`, `browse_classification`, `images[]` (MAIN + PT0..PTN sorted), `bullet_points[]`, `description`, `product_type`.
- Rate limit: `time.sleep(1)` between calls. Catalog Items API is ~2/s burst, 2/s sustained.
- Caches — skips if `raw/{ASIN}.json` already exists.

Run:
```bash
py scripts/fetch_competitor_listings.py DE prevention
py scripts/fetch_competitor_listings.py DE treatment
```

Raw JSONs land in `data/competitor-listings/{CODE}/raw/{ASIN}.json`.

### Step 3 — Read listings and classify claims (Claude in-context)

**This is the only step Claude actually "thinks" about.** Read every raw JSON for the bucket and classify each product against a category-specific set of claim themes.

**Define themes per segment, not globally.** Prevention and treatment products make different claims — don't reuse the same theme list. Aim for 8-10 themes per segment that cover 90% of what competitors actually say.

Examples:
- Lice Prevention themes: `efficacy_prevention`, `natural_ingredients`, `chemical_free`, `family_safe`, `daily_use`, `textile_environment`, `long_lasting`, `pleasant_fragrance`, `registered_approved`, `made_in_germany`
- Lice Treatment themes: `kills_lice_eggs`, `fast_action`, `physical_non_chemical`, `comb_included`, `child_safe`, `medical_certified`, `gentle_skin`, `no_odor`, `family_size_value`, `no_resistance`

For each ASIN, read the title + every bullet + the first ~400 chars of description and emit a list of theme keys that product claims. Be strict — only mark a theme if the listing **explicitly** says it.

### Step 4 — Hand-author the strategic sections

These cannot be computed from the matrix alone. Claude writes them after reading the bullets:

- **`vocGap`** — top 4-6 customer complaints (from the dashboard's Reviews VOC tab if it exists, otherwise inferred from bullets + category knowledge). For each: how many listings address it, which brands, severity, and the whitespace phrase.
- **`whitespaceOpportunities`** — 5-6 strategic opportunities not yet claimed by the top competitors, each with rationale + evidence.
- **`saturation`** — one entry per theme: saturation %, one-line advice for how to differentiate.
- **`strategicRecommendations`** — 5-6 actionable recommendations tagged by type (`Product`, `Messaging`, `Positioning`, `Packaging`). Each has `finding` + `implication`, plus `badgeBg`/`badgeColor` colors for the pill.

Store the hand-authored content as Python constants at the top of `scripts/build_mdd.py`, keyed by segment. This keeps them in version control alongside the matrix logic.

### Step 5 — Write `build_mdd.py`

Copy from eu-lice `scripts/build_mdd.py`. What it does:

1. Load X-Ray CSV → index by ASIN (for `price`, `rating`, `reviews`, `bsr`, `rev30d`, `sales30d`).
2. Read each raw catalog JSON for the bucket.
3. For each competitor, emit:
   ```json
   {
     "asin", "brand", "title", "price", "rating", "reviews", "bsr",
     "rev30d", "sales30d", "mainImage", "images[]", "bullets[]",
     "description", "themes[]", "claimCount"
   }
   ```
4. Build `claimsMatrix = { themes: [...], rows: [{asin, brand, cells: [0|1]}] }`.
5. Build `claimsSummary` — count per theme, `pct = count/total`, `topBrands` = top 3 by `rev30d` that claim the theme.
6. Attach the hand-authored `vocGap`, `whitespaceOpportunities`, `saturation`, `strategicRecommendations`.
7. Wrap in the MDD top-level object (`totalCompetitors`, `marketplace`, `currency`, `exportMonth`, `segment`, …) and write to `data/competitor-listings/{CODE}/mdd-{segment}.json`.

Run:
```bash
py scripts/build_mdd.py DE prevention
py scripts/build_mdd.py DE treatment
```

### Step 6 — Wire the tab(s) into the dashboard's `_build_standalone.py` (standalone dashboards only)

If the dashboard already has a single `marketing-deep-dive` tab and the user wants it **split by segment**, do the eu-lice refactor:

1. **Tabs list** — replace `{'id':'marketing-deep-dive', ...}` with two entries:
   ```python
   {'id': 'marketing-deep-dive-prevention', 'label': 'Marketing Deep-Dive — Prevention'},
   {'id': 'marketing-deep-dive-treatment',  'label': 'Marketing Deep-Dive — Treatment'},
   ```
2. **`load_mdd`** — parameterize by segment, read `mdd-{segment}.json`:
   ```python
   def load_mdd(code, segment):
       path = os.path.join(BASE, 'data', 'competitor-listings', code, f'mdd-{segment}.json')
       ...
   mdd_prevention_data = {c['code']: load_mdd(c['code'], 'prevention') for c in countries}
   mdd_treatment_data  = {c['code']: load_mdd(c['code'], 'treatment')  for c in countries}
   ```
3. **Tabs config in `D.tabs`** — two entries, one per segment, pointing at the two data dicts.
4. **Renderer** — add a `tabId` parameter so one function serves both tabs:
   ```js
   function renderMarketingDeepDive(country, tabId) {
     var D2 = (D.tabs[tabId] && D.tabs[tabId].countries[country.code]) || {};
     ...
   }
   ```
5. **Dispatcher** — route both tab IDs to the renderer with their tabId:
   ```js
   else if (state.tab === 'marketing-deep-dive-prevention') renderMarketingDeepDive(country, 'marketing-deep-dive-prevention');
   else if (state.tab === 'marketing-deep-dive-treatment')  renderMarketingDeepDive(country, 'marketing-deep-dive-treatment');
   ```

For **hub-integrated (non-standalone) dashboards**, the Console `templates/tabs/marketing-deep-dive/template.html` already reads `_TAB_DATA`. Just make sure each segment tab points at the correct MDD data block in the dashboard's `dashboard.json`.

### Step 7 — Rebuild and verify

```bash
py _build_standalone.py
```

Then grep `index.html` to confirm the new content landed:
- Both tab IDs present
- A handful of competitor brand names present
- At least one `vocGap.vocTopic` string present
- At least one `strategicRecommendations.finding` present

## Per-country rollout pattern

When the user says "now do FR" after DE is done:

1. `py scripts/build_mdd.py` and `fetch_competitor_listings.py` are already written — reuse them.
2. Pick top-N for FR from FR X-Ray → write `asins-prevention.txt` + `asins-treatment.txt` into `data/competitor-listings/FR/`.
3. `py scripts/fetch_competitor_listings.py FR prevention` + `… FR treatment` — fetches FR listings. Takes ~25-40 s per bucket at 1 call/s.
4. **Read every fetched listing** — FR bullets are in French, so translate in your head while classifying themes. Do not skip reads.
5. Add `FR` claim assignments + segment-specific VOC gap / whitespace / recommendations to `build_mdd.py`. **Per-country nuances matter** — don't blindly copy DE themes. French pharmacy culture, regulatory regime (ANSM vs BAuA), and brand mix differ.
6. `py scripts/build_mdd.py FR prevention` + `… FR treatment`.
7. `py _build_standalone.py` → verify.

## Important conventions

- **Never use paid LLM APIs** for the analysis. Claude reading bullets in-context is the intended flow. The `_gemini_output.json` / Gemini naming in some older scripts is misleading — no Gemini call was made.
- **Theme assignments live in `build_mdd.py`** as `{asin: [themes]}` dicts. Version-controlled, reviewable, re-runnable.
- **VOC gap + whitespace + recommendations live in `build_mdd.py`** as Python constants. Do not put them in JSON data files — keeping them next to the classification logic makes audits easier.
- **Top-N counts**: "big market" = 15 per segment, "smaller market" = 10. If a segment has fewer than N products total, take all available.
- **30d revenue**, not 12M, for ranking. The goal is "who's winning right now", not long-term. The user explicitly confirmed this.
- **Language**: listings come in the country's native language (DE=German, FR=French, etc.). Translate mentally during classification. Keep the original bullets in the JSON — the renderer displays them as-is.
- **Anti-fungus has a legacy `mdd.json` layout** (single file per country, no segment split). The new `mdd-{segment}.json` layout is the standard. `load_mdd()` in eu-lice falls back to the legacy filename when `segment == 'treatment'`, so the anti-fungus dashboard still works without modification.

## Gotchas

- **X-Ray CSV numbers** — Helium 10 uses US format (`,` thousand, `.` decimal). Wrong parser = top products ranked by cents.
- **Duplicate ASIN rows** — H10 exports may repeat ASINs. Dedupe before ranking.
- **SP-API auth expires** — access token expires in ~1 hour. Fetch script requests a fresh one on each run; don't cache across sessions.
- **Throttled calls** — if you hit 429, increase `time.sleep` to 2-3 s.
- **`_TAB_DATA` vs `D.tabs[tabId]`** — the hub-based tab template reads `window._TAB_DATA`; the standalone renderer reads `D.tabs[tabId].countries[code]`. Use whichever the host expects; don't mix.
- **Renderer helpers must live at IIFE top level** (see eu-lice CLAUDE.md) — never nest helpers inside `renderMarketingDeepDive` or other renderers will `ReferenceError`.
- **exportMonth is 0-based** (Jan=0, Mar=2, …). Match the dashboard's convention.

## Self-update rule

Update this SKILL.md after every new pattern learned — new dashboard type, new country, new theme convention, new renderer wiring, or new cost/API gotcha.
