# Tab System Plan — Modular Dashboard Architecture

## 1. Tab Template Definition Format

**Recommended: `TEMPLATE.json` per tab template folder**

Each tab template in `/templates/tabs/[name]/` gets a `TEMPLATE.json` that defines structure and data expectations — not the actual data. The rendering code stays in `template.html` alongside it.

```
/templates/tabs/
  /keyword-analysis/
    TEMPLATE.json       ← Structure definition (data fields, charts, tables, labels)
    template.html       ← HTML + CSS + rendering engine JS
    README.md           ← Optional: usage notes, data prep instructions
  /voc/
    TEMPLATE.json
    template.html
  /listing-communication/
    ...
```

**Why JSON over Markdown or JS:**
- Machine-readable — the hub can validate that required data fields exist before rendering
- Easy to diff — changes to structure are visible in version control
- Language-agnostic — no parsing ambiguity
- Consistent with `dashboard.json` and `config.json` patterns already in the hub

**TEMPLATE.json structure:**

```json
{
  "name": "Keyword Analysis",
  "id": "keyword-analysis",
  "prefix": "kwa",
  "version": "1.0",
  
  "dataSources": [
    { "type": "helium10-niche", "required": true, "description": "Helium 10 Niche export CSV" },
    { "type": "xray", "required": false, "description": "X-Ray for ASIN metadata enrichment" }
  ],
  
  "dataVariable": "KW_ANALYSIS_DATA",
  
  "requiredFields": [
    "category", "market", "source",
    "nicheMedians.price", "nicheMedians.rating",
    "competitors[]", "keywords[]"
  ],
  
  "renders": {
    "kpis": [
      { "id": "kwaMedianKpi", "label": "Niche Median Price", "field": "nicheMedians.price" },
      { "id": "kwaRatingKpi", "label": "Niche Median Rating", "field": "nicheMedians.rating" }
    ],
    "tables": [
      { "id": "kwaCompetitorTable", "label": "Competitor Details", "sortable": true },
      { "id": "kwaKeywordTable", "label": "Master Keyword List", "sortable": true }
    ],
    "charts": []
  },
  
  "css": "template-specific CSS classes used (beyond base .card, .kpi, etc.)",
  "cssClasses": ["kwa-rank-cell", "kwa-img-cell", "kwa-sticky-col"]
}
```

**Note:** The existing HTML tab templates in `projects/Dashboards/tab_templates/tabs/` remain untouched as reference. We copy/adapt them into the hub's template system.

---

## 2. Dashboard Config Schema — Tab Tracking

Each Detailed dashboard's entry in `config.json` tracks its active tabs and order:

```json
{
  "id": "fruit-fly-trap-us",
  "title": "Fruit Fly Trap — US",
  "product": "Fruit Fly Trap",
  "market": "US",
  "group": "detailed",
  "template": "detailed",
  "tabs": [
    { "id": "total-market",    "type": "base",   "label": "1 — Total Market" },
    { "id": "market-structure", "type": "base",   "label": "2 — Market Structure" },
    { "id": "reviews",         "type": "base",   "label": "3 — Reviews" },
    { "id": "keyword-analysis", "type": "addon", "label": "4 — KW Analysis",    "template": "keyword-analysis" },
    { "id": "voc",              "type": "addon", "label": "5 — Reviews VOC",     "template": "voc" },
    { "id": "listing-comm",     "type": "addon", "label": "6 — Listing Comm",    "template": "listing-communication" }
  ]
}
```

**Key rules:**
- Tabs 1–3 (`type: "base"`) are always present, always first, never removable
- Tabs 4+ (`type: "addon"`) reference a template by name in `"template"` field
- `"label"` includes the position number prefix (e.g., `"4 — KW Analysis"`) — recalculated when tabs are reordered
- Adding/removing/reordering tabs only modifies this `tabs` array — the rendering engine reads it dynamically

**When a tab is added at position N:**
1. Insert into `tabs` array at index N-1
2. Renumber all labels from position N onward
3. No other tabs are removed

**When a tab is removed:**
1. Remove from `tabs` array
2. Renumber all remaining labels sequentially

---

## 3. Topline vs Detailed — Config Difference

### Topline Dashboard
- **No `tabs` field** in config — single fixed template, no tab navigation
- Template: `templates/topline/template.html` (already built in Phase 1)
- All rendering driven by `dashboard.json` data object
- No modularity — every Topline dashboard looks identical except for data

```json
{
  "id": "ants-eu-topline",
  "title": "Ants — EU Top Line",
  "group": "topline",
  "template": "topline"
}
```

### Detailed Dashboard
- **Has `tabs` array** in config — modular tab system
- Template: `templates/detailed/template.html` (shell with tab bar + panels container)
- Base tabs (1–3) render from `dashboard.json` data sections
- Addon tabs render from their own tab template + data in `dashboard.json`

```json
{
  "id": "fruit-fly-trap-us",
  "title": "Fruit Fly Trap — US",
  "group": "detailed",
  "template": "detailed",
  "tabs": [ ... ]
}
```

### Rendering flow difference:

| Step | Topline | Detailed |
|------|---------|----------|
| Load template HTML | Single full layout | Shell with empty tab bar + panels |
| Parse data | `dashboard.json` → one `renderTopLine()` call | `dashboard.json` → per-tab rendering |
| Tab navigation | None | Dynamic tab bar from config |
| Chart.js init | All at once | Per-panel (lazy on tab switch or all at once) |

---

## 4. Empty State / Skeleton Approach

When a tab template is added but no data exists yet:

### Strategy: Structured skeleton with labeled placeholders

```
┌─────────────────────────────────────────┐
│  KW Analysis                            │
├─────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐              │
│  │ —        │  │ —        │   KPI cards  │
│  │ Median   │  │ Median   │   with dash  │
│  │ Price    │  │ Rating   │   values     │
│  └─────────┘  └─────────┘              │
│                                         │
│  ┌─────────────────────────────────────┐│
│  │ Competitor Details Table            ││
│  │ ─────────────────────────────────── ││
│  │ No data loaded.                     ││
│  │ Upload a Helium 10 Niche export     ││
│  │ to populate this tab.               ││
│  └─────────────────────────────────────┘│
│                                         │
│  ┌─────────────────────────────────────┐│
│  │ Master Keyword List                 ││
│  │ ─────────────────────────────────── ││
│  │ No data loaded.                     ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────┘
```

**How it works:**
1. Tab template `template.html` is loaded and its HTML skeleton is injected into the panel
2. The rendering engine checks if the data section exists in `dashboard.json`
3. If data exists → render normally (charts, tables, values)
4. If data is missing → render the skeleton structure with:
   - KPI cards showing `—` as value
   - Empty table headers with column names (from TEMPLATE.json) but no rows
   - A message: _"No data loaded. Upload [expected file type] to populate this tab."_
   - Chart canvases hidden (no empty Chart.js instances)

**Benefit:** The user sees exactly what the tab will look like, knows what data is needed, and the structure is already in place — just waiting for data.

---

## 5. Data Flow for Addon Tabs

Each addon tab's data lives inside `dashboard.json` under a key matching the tab template name:

```json
{
  "title": "Fruit Fly Trap — US",
  "baseTabs": { ... },
  "addonTabs": {
    "keyword-analysis": {
      "category": "Fruit Fly Traps",
      "market": "US",
      "nicheMedians": { "price": "$9.99", "rating": "3.8" },
      "competitors": [ ... ],
      "keywords": [ ... ]
    },
    "voc": {
      "totalReviews": 1051,
      "avgRating": 3.12,
      "starDist": [237, 175, 146, 214, 279],
      ...
    }
  }
}
```

If `addonTabs["keyword-analysis"]` is missing or empty → render skeleton.

---

## 6. File Structure Summary

```
Console/
├── index.html
├── config.json                       ← Dashboard registry + tab order
├── css/hub.css
├── js/hub.js                         ← Router + rendering engines
│
├── templates/
│   ├── topline/template.html         ← Fixed TopLine layout (done)
│   ├── detailed/template.html        ← Shell with tab bar (done)
│   └── tabs/                         ← Modular tab templates (new)
│       ├── total-market/
│       │   ├── TEMPLATE.json
│       │   └── template.html
│       ├── market-structure/
│       │   ├── TEMPLATE.json
│       │   └── template.html
│       ├── reviews/
│       │   ├── TEMPLATE.json
│       │   └── template.html
│       ├── keyword-analysis/
│       │   ├── TEMPLATE.json
│       │   └── template.html
│       ├── voc/
│       │   ├── TEMPLATE.json
│       │   └── template.html
│       ├── listing-communication/
│       │   ├── TEMPLATE.json
│       │   └── template.html
│       ├── copy-brief/
│       │   ├── TEMPLATE.json
│       │   └── template.html
│       └── image-strategy/
│           ├── TEMPLATE.json
│           └── template.html
│
├── dashboards/
│   ├── fruit-fly-trap-us/
│   │   ├── dashboard.json            ← All data (baseTabs + addonTabs)
│   │   ├── xray/
│   │   └── sales/
│   ├── ants-eu-topline/
│   │   ├── dashboard.json
│   │   └── xray/
│   └── ...
```

---

## Questions

1. **Base tab templates:** Should the 3 base tabs (Total Market, Market Structure, Reviews) also be extracted into `/templates/tabs/` as separate `template.html` files? Or should their rendering stay inline in `hub.js`? Extracting them makes the system fully modular (every tab = a template file), but they're always present so maybe inline is simpler.

2. **Tab data in dashboard.json:** I proposed putting addon tab data inside `dashboard.json` under `addonTabs.{template-name}`. An alternative is separate files per tab (e.g., `dashboards/fruit-fly-trap-us/tabs/keyword-analysis.json`). Which do you prefer — single file or split?

3. **Template migration priority:** Which addon tab templates should be built first for the Fruit Fly Trap US example? All 6, or start with 1–2 to validate the system?

4. **CSS strategy:** Each tab template has its own CSS (`.kwa-*`, `.voc-*`, `.lc-*`). Should this CSS be:
   - (A) Bundled into `hub.css` upfront (all tab CSS always loaded)
   - (B) Loaded dynamically when a tab template is first used
   - (C) Embedded inside each `template.html` file within a `<style>` tag

5. **Existing Fruit Flies US data:** The standalone `Fruit Flies — US` dashboard has real data for all 9 tabs. Should I extract that data into the hub's `dashboard.json` format now, or first build the empty skeleton system and populate data later?
