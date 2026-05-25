"""Assemble per-segment VOC payloads from:
  - _voc_work/{slug}_all.json      (full filtered review list)
  - _voc_work/{slug}_ai.json       (Gemini-generated VOC fields)
  - dashboard.json baseTabs.reviews (for themeFilters + tagStyles + segment-tagging fallback)

Writes:
  voc-lure.json     — Lure VOC payload (1,644 reviews)
  voc-electric.json — Electric Traps VOC payload (1,200 reviews)
"""
import json, re

REVIEWS_CAP = 200

# Theme tagging — keyword regexes applied to review body for review-browser filters.
# Lure-specific themes
LURE_THEME_RULES = [
    ('no_effect',       r'\b(do(es)?\s*n[\'o]?t\s*work|did(\s*not|n[\'o]?t)\s*work|not\s*work(ing)?|useless|worthless|waste\s*of\s*money|zero\s*(catch|effect|stars?)|no\s*effect|ineffective)\b'),
    ('diy_better',      r'\b(apple\s*cider|acv|home\s*remedy|homemade|dish\s*soap|make\s*(your|my)\s*own|just\s*vinegar|same\s*as.*vinegar|cup\s*of\s*vinegar|dawn\s*dish|plastic\s*wrap)\b'),
    ('smell',           r'\b(smell|smells?|stinks?|stinky|stench|odor|odour|scent|aroma)\b'),
    ('spill_issue',     r'\b(spill|spilt|spilled|tip(s|ped)?\s*over|knock(ed)?\s*over|fall\s*over|fell\s*over|leak(s|ed|ing)?|messy)\b'),
    ('attract_no_trap', r'\b(don\'?t\s*go\s*in|wont?\s*go\s*in|sit\s*on\s*(top|the\s*rim|the\s*lid)|don\'?t\s*land|won[\'o]?t\s*land|land\s*on\s*the\s*(rim|lid)|crawl\s*around|fly\s*around)\b'),
    ('evaporates',      r'\b(evapora(te|ted|tes|ting)|dr(y|ied|ies|ying)\s*(up|out)|empty\s*(in\s*(a\s*week|days?)|after)|liquid\s*(gone|dried)|short\s*life)\b'),
    ('cute_design',     r'\b(cute|stylish|nice\s*look|nicer\s*than|aesthetic|attractive|kitchen\s*decor|fits?\s*in|discreet)\b'),
    ('easy_use',        r'\b(easy\s*to\s*(set\s*up|use)|simple|quick\s*set|no\s*mess|no.touch|set\s*and\s*forget)\b'),
    ('fast_results',    r'\b(fast|quickly|within\s*hours?|in\s*an?\s*hour|first\s*few\s*days|first\s*\d+\s*days?|first\s*24)\b'),
    ('catches_some',    r'\b(caught\s*(some|a\s*few|several|a\s*handful)|some.*dead|works\s*(ok|okay|kind\s*of|partially)|works\s*decent|kinda\s*works?|works?\s*great)\b'),
    ('packaging_issue', r'\b(arrived\s*(empty|broken|smashed)|missing|short(ed)?|did\s*not\s*come|cracked|damaged\s*package|packaging\s*broke|defective)\b'),
    ('overpriced',      r'\b(overpriced|expensive|not\s*worth.*money|rip.?off|scam(med)?|cost\s*too\s*much)\b'),
    ('compared_other',  r'\b(terro|raid|zevo|safer|brand|other\s*brand|name\s*brand|compare|compared)\b'),
    ('pet_kid_safety',  r'\b(pet|cat|dog|kid|child|children|baby|toddler|safe|natural)\b'),
]
# Electric-specific themes
ELECTRIC_THEME_RULES = [
    ('no_effect',       r'\b(do(es)?\s*n[\'o]?t\s*work|did(\s*not|n[\'o]?t)\s*work|not\s*work(ing)?|useless|worthless|waste\s*of\s*money|zero\s*(catch|effect|stars?)|no\s*effect|ineffective)\b'),
    ('diy_better',      r'\b(apple\s*cider|acv|home\s*remedy|homemade|dish\s*soap|cup\s*of\s*vinegar|vinegar.*works|jar.*caught|caught\s*more\s*flies\s*(in|with).*vinegar)\b'),
    ('light_no_attract',r'\b(light\s*does\s*n[\'o]?t\s*attract|blue\s*light|uv\s*light|light\s*doesn|light\s*is.*weak|don\'?t\s*go\s*near|ignore|happy\s*hour)\b'),
    ('hardware_fail',   r'\b(burn(t|ed)?\s*out|stop(ped)?\s*working|turn(ed)?\s*off|won[\'o]?t\s*turn\s*on|died|stopped|short\s*life|stopped\s*working|burned\s*my\s*outlet|burned\s*outlet|fan\s*stopped|flicker|dim\s*over\s*time|lights?\s*went\s*out)\b'),
    ('refill_issue',    r'\b(refill|cartridge|sticky\s*pad|did\s*not\s*come\s*with|missing|short(ed)?|expensive\s*refill|generic\s*refill)\b'),
    ('placement_outlet',r'\b(outlet|plug.in|near\s*an?\s*outlet|reach\s*the\s*outlet|wall\s*socket|placement)\b'),
    ('flypaper_gimmick',r'\b(fly\s*paper|flypaper|fly\s*tape|sticky\s*paper|just\s*a?\s*sticky|dressed.up|fancy\s*fly|nice\s*looking\s*cover|sticky\s*ribbon)\b'),
    ('gnats_only',      r'\b(catch(es|ed)?\s*gnat|works?\s*on\s*gnat|good\s*for\s*gnat|gnat.*yes|fungus\s*gnat|plant\s*gnat|plant\s*fl(y|ies))\b'),
    ('noise',           r'\b(noisy|noise|loud|sound|vibrat(e|ing|ion)|hum|buzzing|fan\s*nois|annoying\s*noise)\b'),
    ('nightlight',      r'\b(night\s*light|nightlight|night.?light|ambient|glow|illuminat)\b'),
    ('chemical_free',   r'\b(chemical.?free|non.?toxic|safe|pet\s*safe|kid\s*safe|child\s*safe|no\s*zap|no\s*spray|natural)\b'),
    ('weak_fan',        r'\b(weak\s*fan|fan.*weak|barely\s*feel|barely\s*any\s*air|low\s*suction|fly\s*through|fly\s*out|fly\s*right\s*back)\b'),
    ('compared_other',  r'\b(zevo|terro|safer|wirecutter|other\s*brand|name\s*brand|cheap(er)?|compared)\b'),
    ('catches_some',    r'\b(caught\s*(some|a\s*few|several|a\s*handful)|some.*caught|works?\s*(ok|okay|kind\s*of|partially)|works\s*good|works\s*great|kinda\s*works?|kind\s*of\s*works)\b'),
]


def tag_review(body, rules):
    txt = (body or '').lower()
    return [tag for tag, pattern in rules if re.search(pattern, txt)]


# --- Load source data ---
with open('dashboard.json', encoding='utf-8') as f:
    _agg = json.load(f)
agg_reviews = _agg['baseTabs']['reviews']

# Reuse the aggregate dashboard's themeFilters and tagStyles structure (render-only metadata).
# For the per-segment dashboards, we replace the theme list with segment-specific themes.
LURE_THEME_FILTERS = [
    {'value': '',                  'label': 'All Themes'},
    {'value': 'no_effect',         'label': 'No Effect'},
    {'value': 'attract_no_trap',   'label': 'Lands But Won\'t Drown'},
    {'value': 'diy_better',        'label': 'DIY ACV Better'},
    {'value': 'smell',             'label': 'Strong Smell'},
    {'value': 'spill_issue',       'label': 'Spillage'},
    {'value': 'evaporates',        'label': 'Evaporates Fast'},
    {'value': 'cute_design',       'label': 'Cute Design'},
    {'value': 'easy_use',          'label': 'Easy to Use'},
    {'value': 'fast_results',      'label': 'Fast Results'},
    {'value': 'catches_some',      'label': 'Catches Some'},
    {'value': 'packaging_issue',   'label': 'Packaging / Defective'},
    {'value': 'overpriced',        'label': 'Overpriced'},
    {'value': 'compared_other',    'label': 'Comparison'},
    {'value': 'pet_kid_safety',    'label': 'Pet / Kid Safety'},
]
ELECTRIC_THEME_FILTERS = [
    {'value': '',                  'label': 'All Themes'},
    {'value': 'no_effect',         'label': 'No Effect'},
    {'value': 'light_no_attract',  'label': 'Light Fails to Attract'},
    {'value': 'diy_better',        'label': 'DIY ACV Better'},
    {'value': 'hardware_fail',     'label': 'Hardware Failure'},
    {'value': 'refill_issue',      'label': 'Refill Issues'},
    {'value': 'placement_outlet',  'label': 'Outlet / Placement'},
    {'value': 'flypaper_gimmick',  'label': 'Dressed-up Fly Paper'},
    {'value': 'gnats_only',        'label': 'Works on Gnats Only'},
    {'value': 'noise',             'label': 'Noisy Fan'},
    {'value': 'weak_fan',          'label': 'Weak Fan / Bugs Escape'},
    {'value': 'nightlight',        'label': 'Nightlight Use'},
    {'value': 'chemical_free',     'label': 'Chemical-Free'},
    {'value': 'compared_other',    'label': 'Comparison'},
    {'value': 'catches_some',      'label': 'Catches Some'},
]
TAG_STYLES = {
    'no_effect':        'pill-red',
    'attract_no_trap':  'pill-red',
    'diy_better':       'pill-orange',
    'smell':            'pill-orange',
    'spill_issue':      'pill-orange',
    'evaporates':       'pill-orange',
    'light_no_attract': 'pill-red',
    'hardware_fail':    'pill-red',
    'refill_issue':     'pill-orange',
    'placement_outlet': 'pill-orange',
    'flypaper_gimmick': 'pill-orange',
    'noise':            'pill-orange',
    'weak_fan':         'pill-orange',
    'packaging_issue':  'pill-orange',
    'overpriced':       'pill-orange',
    'cute_design':      'pill-green',
    'easy_use':         'pill-green',
    'fast_results':     'pill-green',
    'catches_some':     'pill-green',
    'gnats_only':       'pill-green',
    'nightlight':       'pill-green',
    'chemical_free':    'pill-green',
    'pet_kid_safety':   'pill-blue',
    'compared_other':   'pill-blue',
}


def build_payload(seg_name, slug, theme_rules, theme_filters):
    with open(f'_voc_work/{slug}_all.json', encoding='utf-8') as f:
        all_reviews = json.load(f)
    with open(f'_voc_work/{slug}_ai.json', encoding='utf-8') as f:
        ai = json.load(f)

    total = len(all_reviews)
    avg_rating = sum(r['rating'] for r in all_reviews) / total if total else 0
    star_dist = [0]*5
    for r in all_reviews:
        star_dist[r['rating']-1] += 1

    # Sort by date desc, cap to REVIEWS_CAP for the browser
    sorted_reviews = sorted(all_reviews, key=lambda r: (r.get('date') or ''), reverse=True)
    sample = sorted_reviews[:REVIEWS_CAP]

    # Build the review-browser list (template expects {r, t, tags} where t = full text)
    reviews_payload = []
    for r in sample:
        title = (r.get('title') or '').strip()
        body  = (r.get('body') or '').strip()
        # Compose display text: title + body, brand+ASIN as a parenthetical
        combined = f'{title} — {body}' if title and body else (title or body)
        tags = tag_review(body, theme_rules)
        reviews_payload.append({
            'r':     r['rating'],
            't':     combined,
            'tags':  tags,
            'date':  r.get('date',''),
            'brand': r.get('brand',''),
            'asin':  r.get('asin',''),
            'title': title,
            'body':  body,
        })

    payload = {
        # Identity
        'countryName':  'United States',
        'countryCode':  'US',
        'currency':     '$',
        'segmentName':  seg_name,
        # Headline figures
        'totalReviews': total,
        'avgRating':    round(avg_rating, 2),
        'starDist':     star_dist,
        # AI-derived (Gemini)
        'cpSummary':            ai['cpSummary'],
        'cpWho':                ai['cpWho'],
        'cpWhen':               ai['cpWhen'],
        'cpWhere':              ai['cpWhere'],
        'cpWhat':               ai['cpWhat'],
        'usageScenarios':       ai['usageScenarios'],
        'csSummary':            ai['csSummary'],
        'negativeTopics':       ai['negativeTopics'],
        'positiveTopics':       ai['positiveTopics'],
        'negativeInsights':     ai['negativeInsights'],
        'positiveInsights':     ai['positiveInsights'],
        'buyersMotivation':     ai['buyersMotivation'],
        'customerExpectations': ai['customerExpectations'],
        # Render-only metadata
        'themeFilters': theme_filters,
        'tagStyles':    TAG_STYLES,
        # Review browser data
        'reviews':      reviews_payload,
    }
    return payload, total, round(avg_rating, 2), star_dist


lure_payload, lt, la, lsd = build_payload('Lure', 'lure', LURE_THEME_RULES, LURE_THEME_FILTERS)
elec_payload, et, ea, esd = build_payload('Electric Traps', 'electric', ELECTRIC_THEME_RULES, ELECTRIC_THEME_FILTERS)

with open('voc-lure.json',     'w', encoding='utf-8') as f: json.dump(lure_payload, f, ensure_ascii=False, indent=2)
with open('voc-electric.json', 'w', encoding='utf-8') as f: json.dump(elec_payload, f, ensure_ascii=False, indent=2)

import os
print(f'voc-lure.json:     {os.path.getsize("voc-lure.json"):>8,} bytes · {lt} reviews · avg {la} · star {lsd}')
print(f'voc-electric.json: {os.path.getsize("voc-electric.json"):>8,} bytes · {et} reviews · avg {ea} · star {esd}')

# Sanity: top 3 negative themes per segment
print()
print('Lure top negativeTopics:')
for t in lure_payload['negativeTopics'][:3]:
    print(f'  - {t["label"]} ({t["pct"]})')
print('Electric top negativeTopics:')
for t in elec_payload['negativeTopics'][:3]:
    print(f'  - {t["label"]} ({t["pct"]})')
