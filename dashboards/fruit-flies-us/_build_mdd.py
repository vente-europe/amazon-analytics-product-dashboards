"""Build Marketing Deep-Dive JSON for Fruit Flies (US) — per segment.

Picks top-10 ASINs in each segment (Lure + Electric Traps) by 12M revenue,
tags marketing claim themes against the product title (English regex, single
language since US-only), and cross-references negative VOC topics from
voc-lure.json / voc-electric.json for gap analysis.

KNOWN LIMITATION — TITLE-ONLY THEME TAGGING.
The wasp build (build_wasp_mdd.py) tags themes against title + bullets + description
pulled from SP-API Catalog. We don't have an SP-API listing fetch wired up for
fruit-flies-us yet, so theme tagging here only inspects the product title from
the X-Ray. Many marketing claims (chemical-free, BPA-free, refill bait, etc.)
that brands put in bullets but not in titles will be MISSED. If/when we add
listings/raw/{ASIN}.json files, fold them in here to upgrade claim coverage.

Writes:
  data/mdd/mdd-lure.json
  data/mdd/mdd-electric.json
"""
import os, sys, json, re, pandas as pd
sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
XRAY = os.path.join(BASE, 'data', 'x-ray', 'merged-may-segmented.csv')
VOC_LURE     = os.path.join(BASE, 'voc-lure.json')
VOC_ELECTRIC = os.path.join(BASE, 'voc-electric.json')
OUT_DIR = os.path.join(BASE, 'data', 'mdd')
os.makedirs(OUT_DIR, exist_ok=True)

CURRENCY = '$'
MARKETPLACE = 'amazon.com'
COUNTRY_NAME = 'United States'
COUNTRY_CODE = 'US'
TOP_N = 15

SEGMENT_MAP = {
    'electric traps':    'Electric Traps',
    'sticky traps':      'Sticky Traps',
    'sticky trap':       'Sticky Traps',
    'lure':              'Lure',
    'passive attractor': 'Passive Attractor',
}

# ── Themes per segment (keys stable so they round-trip through the JSON) ──
LURE_THEMES = [
    {"key": "effective_catch",   "label": "Catches lots of fruit flies"},
    {"key": "non_toxic",         "label": "Non-toxic / natural"},
    {"key": "pesticide_free",    "label": "Pesticide / chemical-free"},
    {"key": "pet_kid_safe",      "label": "Safe for kids & pets"},
    {"key": "kitchen_friendly",  "label": "Kitchen / food-area safe"},
    {"key": "discreet_design",   "label": "Discreet / decorative design"},
    {"key": "ready_to_use",      "label": "Ready-to-use / no assembly"},
    {"key": "long_lasting_bait", "label": "Long-lasting bait"},
    {"key": "value_pack",        "label": "Value / multi-pack"},
    {"key": "indoor_outdoor",    "label": "Indoor & outdoor use"},
]

ELECTRIC_THEMES = [
    {"key": "uv_attracts",       "label": "UV light attracts insects"},
    {"key": "silent_operation",  "label": "Silent / quiet (no zap)"},
    {"key": "indoor_safe",       "label": "Safe indoor use (kitchen/bedroom)"},
    {"key": "usb_plug_in",       "label": "USB / plug-in powered"},
    {"key": "glue_board",        "label": "Sticky glue board (non-zap)"},
    {"key": "wide_coverage",     "label": "Wide coverage area"},
    {"key": "pet_kid_safe",      "label": "Pet- & child-safe (no zap)"},
    {"key": "easy_clean",        "label": "Easy-clean removable tray"},
    {"key": "discreet_design",   "label": "Discreet / night-light design"},
    {"key": "effective_catch",   "label": "Catches lots of fruit flies"},
]

# ── Regex per theme — English only (US market) ──
LURE_RX = {
    "effective_catch":   r"(catch(es)?|trap(s)?|kill(s|er)?|eliminat|eradic|destroy|exterminat|gnat\s+killer|fly\s+killer)",
    "non_toxic":         r"(non[-\s]?toxic|natural|organic|food[-\s]?grade|plant[-\s]?based|essential\s+oil|vinegar|apple\s+cider)",
    "pesticide_free":    r"(pesticide[-\s]?free|chemical[-\s]?free|no\s+(pesticide|chemicals?|poison|insecticide)|insecticide[-\s]?free|poison[-\s]?free)",
    "pet_kid_safe":      r"(pet[-\s]?safe|kid[-\s]?safe|child[-\s]?safe|safe\s+(for|around)\s+(kids|children|pets|dogs|cats|babies|family)|family[-\s]?safe)",
    "kitchen_friendly":  r"(kitchen|food[-\s]?area|countertop|counter[-\s]?top|dining|pantry|food[-\s]?safe)",
    "discreet_design":   r"(discreet|decorative|elegant|stylish|attractive|modern|sleek|aesthetic|invisible|hidden|disguise)",
    "ready_to_use":      r"(ready[-\s]?to[-\s]?use|easy\s+(to\s+)?(use|set\s*up|install|hang|assemble)|no\s+(assembly|setup|installation)|plug[-\s]?and[-\s]?play|just\s+(open|peel|hang|set|fill|place)|prefilled|pre[-\s]?filled)",
    "long_lasting_bait": r"(long[-\s]?lasting|long[-\s]?last|lasts?\s+(weeks|months|days|up\s+to)|30\s*days?|60\s*days?|90\s*days?|month(s|ly)?\s+(supply|protection))",
    "value_pack":        r"(\d+\s*[-\s]?pack|pack\s+of\s+\d+|\d+\s*pcs?|value\s+pack|bulk|family\s+pack|multi[-\s]?pack)",
    "indoor_outdoor":    r"(indoor|outdoor|in\s*\&?\s*out|patio|garden|backyard)",
}

ELECTRIC_RX = {
    "uv_attracts":       r"(uv\s+(light|lamp|bulb|led|attract)|ultraviolet|365\s*nm|blue\s+light|attract(s|ant)?\s+(flies|insects|gnats|fruit\s+flies))",
    "silent_operation":  r"(silent|quiet|noiseless|no[-\s]?noise|whisper|no\s+zap|zap[-\s]?free|no\s+sound)",
    "indoor_safe":       r"(indoor|kitchen|bedroom|bathroom|office|home|house|living\s+room|nursery)",
    "usb_plug_in":       r"(usb|plug[-\s]?in|cordless|rechargeable|battery|wall[-\s]?plug|outlet|wired|cable|portable)",
    "glue_board":        r"(glue\s+(board|card|trap|sheet|paper)|sticky\s+(board|card|paper|sheet|catcher|trap)|adhesive\s+(board|card)|replacement\s+(glue|sticky|board)|refill\s+(glue|sticky|card))",
    "wide_coverage":     r"(coverage|covers|wide\s+area|large\s+(area|room|space)|whole[-\s]?room|big\s+room|\d+\s*(sq\.?\s*ft|square\s+f(ee|oo)t|sqft))",
    "pet_kid_safe":      r"(pet[-\s]?safe|kid[-\s]?safe|child[-\s]?safe|safe\s+(for|around)\s+(kids|children|pets|dogs|cats|babies|family)|family[-\s]?safe|no\s+zap|zap[-\s]?free|non[-\s]?zap)",
    "easy_clean":        r"(easy[-\s]?clean|easy\s+to\s+clean|removable\s+(tray|catcher|board)|slide[-\s]?out|tool[-\s]?free|dishwasher[-\s]?safe|wipe[-\s]?clean)",
    "discreet_design":   r"(discreet|decorative|elegant|stylish|night\s*light|nightlight|sleek|modern|attractive|aesthetic|disguise|hidden|invisible)",
    "effective_catch":   r"(catch(es)?|trap(s)?|kill(s|er)?|eliminat|eradic|destroy|exterminat|gnat\s+killer|fly\s+killer|fruit\s+fly\s+killer)",
}

THEMES_BY_SEG = {'Lure': LURE_THEMES,  'Electric Traps': ELECTRIC_THEMES}
RX_BY_SEG     = {'Lure': LURE_RX,      'Electric Traps': ELECTRIC_RX}
VOC_BY_SEG    = {'Lure': VOC_LURE,     'Electric Traps': VOC_ELECTRIC}

# Hints to fuzzy-map a VOC negative-topic label → one of our theme keys.
# All matching is case-insensitive substring against the topic label.
VOC_HINTS = {
    # Lure-leaning hints (also reused for Electric where they apply)
    'effective_catch':   ['not trapped', 'doesn\'t catch', 'doesn\'t kill', 'doesn\'t work', 'flies attracted but not trapped', 'fail', 'beats', 'ineffective', 'no efficacy', 'inefficac', 'attract but not', 'attracts but not', 'fail to attract', 'fails to attract', 'gimmick', 'fly paper'],
    'non_toxic':         ['odor', 'smell', 'vinegar', 'natural', 'evaporation', 'evaporat', 'spill'],
    'pesticide_free':    ['chemical', 'pesticide', 'insecticide', 'poison', 'toxic'],
    'pet_kid_safe':      ['kid', 'pet', 'child', 'baby', 'safety'],
    'kitchen_friendly':  ['kitchen', 'food', 'countertop', 'spill', 'odor'],
    'discreet_design':   ['ugly', 'look', 'design', 'aesthetic', 'eye-sore', 'eyesore'],
    'ready_to_use':      ['setup', 'instruct', 'assembly', 'difficult', 'complicated'],
    'long_lasting_bait': ['lasts', 'short', 'last', 'evaporat', 'dries', 'dry out', 'rapid', 'overpriced', 'expensive', 'price', 'overpriced diy', 'diy substitute'],
    'value_pack':        ['overpriced', 'expensive', 'price', 'cost', 'value', 'cheap'],
    'indoor_outdoor':    ['outdoor', 'patio', 'garden'],
    # Electric-leaning hints
    'uv_attracts':       ['light fails', 'fails to attract', 'attract', 'uv', 'light doesn', 'attracts mosquitoes', 'fly paper gimmick'],
    'silent_operation':  ['noise', 'noisy', 'loud', 'sound', 'buzz', 'crackle', 'crack', 'zap noise'],
    'indoor_safe':       ['indoor', 'bedroom', 'kitchen', 'baby'],
    'usb_plug_in':       ['battery', 'usb', 'plug', 'cord', 'outlet', 'placement & outlet', 'placement and outlet', 'placement limitations'],
    'glue_board':        ['glue', 'sticky', 'paper', 'board', 'gimmick', 'dressed-up fly paper', 'fly paper'],
    'wide_coverage':     ['coverage', 'area', 'small', 'reach', 'range'],
    'easy_clean':        ['clean', 'tray', 'mess', 'gross', 'disgusting', 'wipe'],
    'discreet_design':   ['ugly', 'design', 'look', 'aesthetic'],
}

def numv(v):
    if pd.isna(v): return 0.0
    s = str(v).replace(',', '').replace('$', '').replace('€', '').strip()
    try: return float(s)
    except: return 0.0

def norm_segment(v):
    if pd.isna(v) or str(v).strip() == '': return None
    return SEGMENT_MAP.get(str(v).strip().lower())

def tag_themes(text, rxmap):
    text_lc = (text or '').lower()
    return [k for k, rx in rxmap.items() if re.search(rx, text_lc)]


def build_segment(seg, df, top_n=TOP_N):
    themes = THEMES_BY_SEG[seg]
    rx     = RX_BY_SEG[seg]
    theme_keys = [t['key'] for t in themes]

    # Pull every ASIN in this segment with a price, sort by 12M revenue desc, take top-N.
    rows = []
    for _, r in df.iterrows():
        if norm_segment(r.get('Segment')) != seg: continue
        asin = str(r.get('ASIN') or '').strip()
        if not asin: continue
        title = str(r.get('Product Details') or '').strip()
        brand = str(r.get('Brand') or '').strip() or 'Unknown'
        price = numv(r.get('Price  US$') or r.get('Price US$') or r.get('Price'))
        sales30d = numv(r.get('ASIN Sales'))
        rev30d   = numv(r.get('ASIN Revenue'))
        if rev30d == 0 and sales30d > 0 and price > 0: rev30d = sales30d * price
        rev12m = rev30d * 12  # rough — fruit-flies build uses median multiplier (~x13.63) for ranking purposes 30d×12 is fine.
        rows.append({
            'asin': asin, 'brand': brand, 'title': title,
            'price': round(price, 2),
            'rating':  numv(r.get('Ratings')),
            'reviews': int(numv(r.get('Review Count'))),
            'bsr':     int(numv(r.get('BSR'))) if not pd.isna(r.get('BSR')) else 0,
            'rev30d':  round(rev30d, 2),
            'rev12m':  round(rev12m, 2),
            'sales30d':int(sales30d),
            'mainImage': (str(r.get('Image URL')).strip() if not pd.isna(r.get('Image URL')) else ''),
            'images':  [str(r.get('Image URL')).strip()] if not pd.isna(r.get('Image URL')) else [],
            'bullets': [],
            'description': '',
        })
    rows.sort(key=lambda x: -x['rev12m'])
    top = rows[:top_n]

    # Theme tagging (title only — see file-header note)
    theme_counts = {k: 0 for k in theme_keys}
    theme_brands = {k: [] for k in theme_keys}
    matrix_rows = []
    for c in top:
        c_themes = tag_themes(c['title'], rx)
        c['themes'] = c_themes
        c['claimCount'] = len(c_themes)
        for k in c_themes:
            theme_counts[k] += 1
            if c['brand'] and c['brand'] not in theme_brands[k]:
                theme_brands[k].append(c['brand'])
        matrix_rows.append({
            'asin': c['asin'], 'brand': c['brand'],
            'cells': [1 if k in c_themes else 0 for k in theme_keys],
        })

    n_comp = len(top)
    claims_summary = []
    for t in themes:
        n = theme_counts[t['key']]
        claims_summary.append({
            'theme': t['key'],
            'label': t['label'],
            'count': n,
            'pct':   round(n / n_comp * 100, 1) if n_comp else 0,
            'topBrands': theme_brands[t['key']][:5],
        })
    claims_summary.sort(key=lambda x: -x['count'])

    # VOC gap analysis — cross-reference per-segment voc-*.json negativeTopics
    voc_gap = []
    voc_path = VOC_BY_SEG[seg]
    if os.path.exists(voc_path):
        with open(voc_path, encoding='utf-8') as f:
            voc = json.load(f)
        for nt in voc.get('negativeTopics', [])[:8]:
            label = nt.get('label', '')
            label_lc = label.lower()
            # Match topic label → theme keys via VOC_HINTS
            matched = []
            for tk in theme_keys:
                if any(h.lower() in label_lc for h in VOC_HINTS.get(tk, [])):
                    matched.append(tk)
            covering_brands = set()
            covering_count = 0
            for c in top:
                if any(t in c['themes'] for t in matched):
                    covering_count += 1
                    if c['brand']: covering_brands.add(c['brand'])
            try:
                pct = float(str(nt.get('pct', '0')).replace('%', ''))
            except Exception:
                pct = 0.0
            severity = 'HIGH' if pct >= 20 and covering_count <= 1 else ('MEDIUM' if pct >= 10 and covering_count <= 2 else 'LOW')
            voc_gap.append({
                'vocTopic': label,
                'customerConcernPct': f'{pct:.1f}%',
                'addressedByCount': covering_count,
                'addressedByBrands': sorted(covering_brands)[:5],
                'gapSeverity': severity,
                'whitespace': 'true' if covering_count == 0 else 'false',
            })

    # Whitespace + saturation buckets driven by adoption rate
    whitespace = []
    saturation = []
    for cs in claims_summary:
        if cs['pct'] <= 25:
            whitespace.append({
                'opportunity': f'{cs["label"]} (only {cs["count"]} of {n_comp} competitors)',
                'rationale':   f'{cs["pct"]}% of top-{n_comp} listings make this claim in their title — whitespace to differentiate.',
                'evidence':    f'Currently claimed by: {", ".join(cs["topBrands"][:3]) or "none"}',
            })
        if cs['pct'] >= 60:
            saturation.append({
                'label':         cs['label'],
                'saturationPct': f'{cs["pct"]}%',
                'advice':        'Table-stakes claim — must include, but adding it does not differentiate.',
            })
    whitespace = whitespace[:6]
    saturation = saturation[:6]

    # Strategic recommendations: combine HIGH-severity gaps + top whitespace
    recs = []
    for g in [g for g in voc_gap if g['gapSeverity'] == 'HIGH'][:3]:
        recs.append({
            'type':       'VOC Gap',
            'badgeBg':    '#fee2e2',
            'badgeColor': '#991b1b',
            'finding':    f'{g["customerConcernPct"]} of negative reviews cite "{g["vocTopic"]}" — only {g["addressedByCount"]} of {n_comp} top sellers address this in their title.',
            'implication':f'Lead with a direct counter-claim in bullets and A+ content. Closing this gap targets the {g["customerConcernPct"]} pool of dissatisfied buyers head-on.',
        })
    for ws in whitespace[:2]:
        recs.append({
            'type':       'Whitespace',
            'badgeBg':    '#dbeafe',
            'badgeColor': '#1e40af',
            'finding':    ws['opportunity'],
            'implication':ws['rationale'],
        })

    return {
        'countryName':           COUNTRY_NAME,
        'countryCode':           COUNTRY_CODE,
        'currency':              CURRENCY,
        'marketplace':           MARKETPLACE,
        'segmentName':           seg,
        'totalCompetitors':      n_comp,
        'competitors':           top,
        'claimsMatrix':          {'themes': themes, 'rows': matrix_rows},
        'claimsSummary':         claims_summary,
        'vocGap':                voc_gap,
        'whitespaceOpportunities': whitespace,
        'saturation':            saturation,
        'strategicRecommendations': recs,
        'brandPalette':          ['#2563eb','#dc2626','#16a34a','#f59e0b','#8b5cf6','#0891b2','#db2777','#65a30d'],
    }


def main():
    df = pd.read_csv(XRAY, encoding='utf-8-sig')
    for seg, out_name in [('Lure', 'mdd-lure.json'), ('Electric Traps', 'mdd-electric.json')]:
        payload = build_segment(seg, df)
        out_path = os.path.join(OUT_DIR, out_name)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print(f'Wrote {out_path}  ({os.path.getsize(out_path):,} bytes)')
        print(f'  segment: {seg}  · top-{payload["totalCompetitors"]} by 12M revenue')
        print(f'  themes claimed (top 5):')
        for cs in payload['claimsSummary'][:5]:
            print(f'    {cs["label"]:42s}: {cs["count"]:>2}/{payload["totalCompetitors"]} ({cs["pct"]}%)')
        print(f'  voc gaps: {len(payload["vocGap"])}  whitespace: {len(payload["whitespaceOpportunities"])}  saturation: {len(payload["saturation"])}  recs: {len(payload["strategicRecommendations"])}')
        print()


if __name__ == '__main__':
    main()
