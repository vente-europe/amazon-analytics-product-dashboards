# MDD szelki-style schema — atopic-skin-detailed

Per bucket file: `data/competitor-listings/{CODE}/mdd-{slug}.json` (slug = segment.lower()).
Renderer reads it via `window._TAB_DATA` → renders into `#u-mdd-tab-root`. All labels Polish.
Source attribution is **Title (T) + Bullets (BP) only** — SP-API has no A+/Brand Story (no `A+` tag).

```jsonc
{
  "totalCompetitors": 10,
  "marketplace": "amazon.de",
  "avgClaims": 5.3,                       // mean themes.length across competitors

  "competitors": [{
    "asin": "B0C8BWL2ZV",
    "brand": "Bioderma",
    "title": "…",
    "img": "https://…jpg",               // main image
    "imgs": ["https://…jpg", …],         // gallery (cap 8, excl. main or incl. — renderer concats [img].concat(imgs) dedup)
    "bullets": ["…", …],                 // original language, cap 8
    "themes": ["nawilzenie","kojacy"],   // claim keys present (title OR bullets)
    "themeSrc": { "nawilzenie": ["T","BP"], "kojacy": ["BP"] },  // per claim: where found. tags: "T"|"BP"
    "price": 23.63, "rating": 4.5, "reviews": 205, "rev30": 2418,
    "archival": false                    // true if rev30==0 (below sales signal)
  }],

  "themes": [                            // matrix COLUMNS = claims present in ≥1 competitor, in THEMES order
    { "key": "nawilzenie", "label": "Nawilżenie" }, …
  ],

  "adoption": [                          // sorted desc by count; drives adoption table + top-claim KPI
    { "key": "nawilzenie", "label": "Nawilżenie", "count": 9, "pct": 90 }, …
  ],

  "vocGap": [{                           // from local voc.json negativeTopics matched to themes via PL keywords
    "vocTopic": "…", "vocPct": 3.1,      // % negatives (number)
    "theme": "Kojący / łagodzący",       // claim LABEL that addresses it ("" if no match)
    "addressed": 2, "total": 10, "pct": 20,   // competitors addressing it
    "sev": "HIGH",                        // HIGH (addressed==0) | MED (<=25%) | LOW (else)
    "brands": ["…", …]
  }],

  "whitespace": [                        // claims with pct < 30
    { "label": "Redukcja świądu", "pct": 20, "why": "Tylko 2/10 konkurentów…" }
  ],

  "saturation": [                        // ALL matrix claims, tiered advice
    { "label": "Nawilżenie", "pct": 90,
      "advice": "Claim obowiązkowy (≥70%) — musisz go mieć; wyróżnij się dowodem." }
      // tiers: >=70 "obowiązkowy", 30-69 "wymaga konkretów/dowodu", <30 "biała plama — okazja"
  ],

  "recs": [                              // typed strategic recommendations
    { "type": "Messaging", "finding": "…", "impl": "…" }
    // type ∈ Produkt | Messaging | Pozycjonowanie | Packaging  (colored badges)
  ]
}
```

Renderer sections (order): intro → KPI strip (competitors, avgClaims, top claim+pct, #HIGH gaps)
→ competitor grid + click-to-expand detail → collapsible image-compare → collapsible bullet-compare
→ adoption table (sortable) → **claims matrix** (brand rows × claim cols; cells show T/BP badges or ·)
→ VOC-gap table → whitespace + saturation (side by side) → strategic recs table → methodology note.
(No A+/Brand-Story compare — data unavailable.)
