# -*- coding: utf-8 -*-
"""Build the competitor card data + Gemini-input prompt for the MDD tab.

This script does NOT call Gemini. It:
  1. Reads the X-Ray CSV, filters to Cream + Spray ASINs
  2. Reads each ASIN's SP-API listing JSON
  3. Composes competitor cards (title, brand, bullets, images, price, rev30d, rating, reviews, bsr)
  4. Saves cards to scripts/_mdd_competitors.json
  5. Builds a compact Gemini prompt asking for claimsMatrix, claimsSummary, vocGap,
     whitespace, saturation, strategicRecommendations and writes to scripts/_mdd_prompt.txt

Then a separate orchestrator (Claude/Gemini call) reads the prompt + saves the
response, and `merge_mdd.py` merges everything into dashboard.json.
"""
import json, csv, os, sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
XRAY = os.path.join(ROOT, 'data', 'x-ray', 'Grzybica-Stop-DE-X-Ray.csv')
RAW_DIR = os.path.join(ROOT, 'data', 'competitor-listings', 'raw')
DASH = os.path.join(ROOT, 'dashboard.json')

OUT_COMPETITORS = os.path.join(ROOT, 'scripts', '_mdd_competitors.json')
OUT_PROMPT      = os.path.join(ROOT, 'scripts', '_mdd_prompt.txt')

CLAIM_THEMES = [
    {"key": "effectiveness",    "label": "Eradicates Fungus"},
    {"key": "speed",            "label": "Fast Results"},
    {"key": "natural",          "label": "Natural / Plant-based"},
    {"key": "clinical_proof",   "label": "Clinically Proven"},
    {"key": "active_ingredient","label": "Named Active Ingredient"},
    {"key": "easy_use",         "label": "Easy to Apply"},
    {"key": "gentle_safe",      "label": "Gentle / Skin-friendly"},
    {"key": "broad_spectrum",   "label": "Broad-Spectrum / Multi-fungus"},
    {"key": "value_guarantee",  "label": "Value / Money-back"},
    {"key": "kit_combo",        "label": "Kit / Combo / Multipack"},
]

# ---------------------------------------------------------------------------
# Load X-Ray rows for Cream + Spray
# ---------------------------------------------------------------------------
with open(XRAY, encoding='utf-8-sig', newline='') as fh:
    rows = list(csv.reader(fh))
h = rows[0]
def col(name): return h.index(name)
ASIN, SEG, BRAND, TITLE = col('ASIN'), col('Segment'), col('Brand'), col('Product Details')
PRICE_COL = next((i for i, c in enumerate(h) if 'price' in c.lower()), None)
REV_COL   = col('ASIN Revenue')
RATING_COL = col('Ratings')
REV_CNT_COL = col('Review Count')
BSR_COL    = col('BSR')

def numv(s):
    if not s: return 0.0
    s = s.replace(',', '').replace('€', '').replace('£', '').replace('$', '').strip().strip('"')
    try: return float(s)
    except: return 0.0

xray_rows = []
for r in rows[1:]:
    if r[SEG] in ('Cream', 'Spray'):
        xray_rows.append({
            'asin':    r[ASIN],
            'segment': r[SEG],
            'brand':   r[BRAND] or 'Unknown',
            'price':   numv(r[PRICE_COL]) if PRICE_COL is not None else 0,
            'rev30d':  numv(r[REV_COL]),
            'rating':  numv(r[RATING_COL]),
            'reviews': int(numv(r[REV_CNT_COL])),
            'bsr':     int(numv(r[BSR_COL])),
            'xray_title': r[TITLE],
        })

print(f'Loaded {len(xray_rows)} Cream+Spray rows from X-Ray')

# ---------------------------------------------------------------------------
# Merge SP-API listing data
# ---------------------------------------------------------------------------
def img_url(img):
    if isinstance(img, dict): return img.get('url') or ''
    return img or ''

competitors = []
for x in xray_rows:
    p = os.path.join(RAW_DIR, x['asin'] + '.json')
    if not os.path.exists(p): continue
    with open(p, encoding='utf-8') as f: lst = json.load(f)
    images_raw = lst.get('images', []) or []
    image_urls = [img_url(im) for im in images_raw if img_url(im)]
    main_image = image_urls[0] if image_urls else ''
    competitors.append({
        'asin':       x['asin'],
        'segment':    x['segment'],
        'brand':      lst.get('brand') or x['brand'],
        'title':      lst.get('title') or x['xray_title'],
        'price':      x['price'],
        'rating':     x['rating'],
        'reviews':    x['reviews'],
        'bsr':        x['bsr'],
        'rev30d':     x['rev30d'],
        'mainImage':  main_image,
        'images':     image_urls,
        'bullets':    lst.get('bullet_points') or [],
        'description': lst.get('description') or '',
        # 'themes' filled in by Gemini step
    })

# Sort by 30d revenue desc — most relevant competitors first
competitors.sort(key=lambda c: c['rev30d'], reverse=True)

with open(OUT_COMPETITORS, 'w', encoding='utf-8') as f:
    json.dump(competitors, f, ensure_ascii=False, indent=2)
print(f'Wrote {len(competitors)} competitor cards to {os.path.basename(OUT_COMPETITORS)}')

# ---------------------------------------------------------------------------
# Build compact Gemini prompt
# ---------------------------------------------------------------------------
# Pull VOC topics (already in dashboard.json) for the gap analysis
with open(DASH, encoding='utf-8') as f: dash = json.load(f)
voc = dash['baseTabs']['reviews']

neg_topics = [{'label': t['label'], 'pct': t['pct']} for t in voc.get('negativeTopics', [])]
pos_topics = [{'label': t['label'], 'pct': t['pct']} for t in voc.get('positiveTopics', [])]

# Compact each competitor for prompt economy: title + bullets joined to <=600 chars
def compact_listing(c):
    bullets = c.get('bullets') or []
    body = '. '.join(bullets)
    if len(body) > 600:
        body = body[:600].rsplit(' ', 1)[0] + '...'
    title = (c.get('title') or '')[:160]
    return f"[{c['asin']}] {c['brand']} ({c['segment']}) | {title}\\n  bullets: {body}"

listings_block = '\n\n'.join(compact_listing(c) for c in competitors)
themes_block = '\n'.join(f"- {t['key']}: {t['label']}" for t in CLAIM_THEMES)

PROMPT = f'''You are analyzing competitor Amazon listings for the anti-fungal foot/nail treatment category on amazon.de (Germany). Output a strict JSON object for the Marketing Deep-Dive dashboard tab.

CONTEXT
- {len(competitors)} competitor listings (Cream + Spray segments)
- Marketplace: amazon.de, currency EUR
- Each listing has title + bullets (German). Read them natively.

CLAIM THEMES (use these exact keys for tagging):
{themes_block}

VOC TOPICS from Tab 3 Reviews (use these exact labels in vocGap):

NEGATIVE (customer complaints):
{json.dumps(neg_topics, ensure_ascii=False, indent=2)}

POSITIVE (customer wins, optional reference):
{json.dumps(pos_topics, ensure_ascii=False, indent=2)}

LISTINGS ({len(competitors)} total):
{listings_block}

OUTPUT — return ONLY one JSON object (no markdown fences). Schema:

{{
  "claimsMatrix": [
    {{ "asin": "...", "themeKeys": ["effectiveness", "speed", ...] }}
    // one entry per competitor, listing the keys whose theme is present in title/bullets
  ],
  "claimsSummary": [
    {{ "label": "<theme label>", "count": <number of listings asserting it>,
       "pct": "<percentage>%", "topBrands": ["Brand1","Brand2","Brand3"] }}
    // one entry per claim theme, sorted by count desc
  ],
  "vocGap": [
    {{ "vocTopic": "<exact negative topic label>",
       "customerConcernPct": "<topic pct from VOC>",
       "addressedByCount": <int>,
       "addressedByBrands": ["Brand1", "Brand2", ...],
       "gapSeverity": "HIGH" | "MEDIUM" | "LOW",
       "whitespace": "<1-sentence whitespace insight, English>"
    }}
    // one entry per NEGATIVE topic above
  ],
  "whitespaceOpportunities": [
    {{ "title": "<short title>", "rationale": "<2-3 sentences>", "evidence": "<short evidence>" }}
    // 4-6 items: where customer demand exists but few competitors address it
  ],
  "saturation": [
    {{ "title": "<short title>", "rationale": "<2-3 sentences>", "evidence": "<short evidence>" }}
    // 3-4 items: where competitors are saturated; new entrants would face fierce competition
  ],
  "strategicRecommendations": [
    {{ "headline": "<short>", "badgeBg": "#hex", "badgeColor": "#hex",
       "rationale": "<2-3 sentences with optional <strong>>", "actions": ["action 1", "action 2", "action 3"] }}
    // 5-7 items
  ]
}}

CONSTRAINTS
- All output text in English
- claimsMatrix MUST have exactly {len(competitors)} entries, one per ASIN above
- vocGap MUST cover EVERY negative topic listed above; gapSeverity = HIGH if addressedByCount <= 25% of competitors and customerConcernPct >= 5%; LOW if >50% address; MEDIUM otherwise
- Recycle this badge palette: ("#fee2e2","#991b1b"), ("#d1fae5","#065f46"), ("#fef3c7","#92400e"), ("#dbeafe","#1e40af"), ("#ede9fe","#5b21b6"), ("#fce7f3","#9d174d"), ("#ffedd5","#9a3412")
- Tag a theme as present if the title or bullets clearly assert it. Tag conservatively'''

with open(OUT_PROMPT, 'w', encoding='utf-8') as f:
    f.write(PROMPT)
print(f'Wrote prompt to {os.path.basename(OUT_PROMPT)} ({len(PROMPT):,} chars)')
print(f'Competitor breakdown: Cream={sum(1 for c in competitors if c["segment"]=="Cream")}, Spray={sum(1 for c in competitors if c["segment"]=="Spray")}')
