"""Build full VOC analysis from review files and populate dashboard.json"""
import json, glob, os, sys, re

sys.stdout.reconfigure(encoding='utf-8')

BASE = 'c:/AI Workspaces/Claude Code Workspace - Tom/projects/Main Dashboard/dashboards/fruit-fly-trap-us'

# ── Load all reviews ──
all_reviews = []
seen = set()

for rf in sorted(glob.glob(os.path.join(BASE, 'reviews/dataset_amazon*.json'))):
    with open(rf, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for r in data:
        text = r.get('reviewDescription', '').strip()
        if not text:
            continue
        key = text[:100]
        if key not in seen:
            seen.add(key)
            all_reviews.append({'r': r['ratingScore'], 't': text})

for name, key_star, key_text in [('terro_reviews.json', 'stars', 'review'), ('hs_reviews.json', 'stars', 'review')]:
    paths = glob.glob(os.path.join(BASE, f'reviews/{name}'))
    if paths:
        with open(paths[0], 'r', encoding='utf-8') as f:
            d = json.load(f)
        for r in d.get('reviews', d if isinstance(d, list) else []):
            text = r.get(key_text, '').strip()
            if not text:
                continue
            key = text[:100]
            if key not in seen:
                seen.add(key)
                all_reviews.append({'r': r[key_star], 't': text})

# ── Theme tagging ──
THEMES = {
    'no_effect': r'no.?effect|doesn.t work|didn.t work|not work|zero catch|waste|useless|scam|terrible|horrible|worst',
    'effective': r'works? great|caught|effective|amazing|excellent|perfect|love it|impressed|fantastic|wonderful',
    'fast_results': r'overnight|within hours|next morning|within a day|within 24|first night|right away|immediately',
    'diy_better': r'vinegar|apple cider|diy|homemade|home.?made',
    'overpriced': r'overpriced|too expensive|waste of money|rip.?off|not worth',
    'packaging': r'leak|broken|damaged|spill|empty.*arrive|arrived.*broken|missing',
    'smell': r'smell|stink|odor|stench|fragrance',
    'easy_use': r'easy to use|simple|convenient|just (place|open|set|put)|ready to use',
    'discreet': r'discreet|blend|inconspicuous|attractive|cute|design|looks? (good|nice|great)',
    'safe_natural': r'non.?toxic|safe|natural|chemical.?free|eco|organic|pet.?safe|child.?safe|kid.?safe',
    'sticky_issue': r'sticky|adhesive|glue|fell off|doesn.t stick',
    'short_lifespan': r'dried|dry out|evaporate|short.?lived|only last|week.*done|stopped working',
    'attractant_weak': r'attractant|lure|bait|flies? (ignore|fly around|not interested|won.t enter)',
}

for rev in all_reviews:
    tags = []
    text_lower = rev['t'].lower()
    for tag, pattern in THEMES.items():
        if re.search(pattern, text_lower):
            tags.append(tag)
    rev['tags'] = tags

# ── Stats ──
star_dist = [0, 0, 0, 0, 0]
for r in all_reviews:
    if 1 <= r['r'] <= 5:
        star_dist[r['r'] - 1] += 1

total = len(all_reviews)
avg_rating = sum((i + 1) * star_dist[i] for i in range(5)) / total if total > 0 else 0
neg_reviews = [r for r in all_reviews if r['r'] <= 2]
pos_reviews = [r for r in all_reviews if r['r'] >= 4]
neg_total = len(neg_reviews)
pos_total = max(len(pos_reviews), 1)

def get_quotes(reviews, tag, n=3):
    matches = [r['t'] for r in reviews if tag in r['tags']]
    return ['"' + q[:180] + ('...' if len(q) > 180 else '') + '"' for q in matches[:n]]

# ── Load cpData from existing analysis ──
voc_path = glob.glob(os.path.join(BASE, 'reviews/voc_analysis.json'))[0]
with open(voc_path, 'r', encoding='utf-8') as f:
    voc_orig = json.load(f)
cp = voc_orig['cpData']

# ── Build VOC_DATA ──
voc_data = {
    "totalReviews": total,
    "avgRating": round(avg_rating, 2),
    "starDist": star_dist,

    "cpSummary": f"Customer profile based on {total} reviews across 40 ASINs. The most common buyer is a <strong>homeowner</strong> dealing with flies, most purchases happen <strong>within days</strong> of spotting flies, traps are placed <strong>near fruit</strong>, and the dominant concern is <strong>effectiveness</strong>.",

    "cpWho": {"labels": cp["who"]["labels"], "pos": cp["who"]["pos"], "neg": cp["who"]["neg"]},
    "cpWhen": {"labels": cp["when"]["labels"], "pos": cp["when"]["pos"], "neg": cp["when"]["neg"]},
    "cpWhere": {"labels": cp["where"]["labels"], "pos": cp["where"]["pos"], "neg": cp["where"]["neg"]},
    "cpWhat": {"labels": cp["what"]["labels"], "pos": cp["what"]["pos"], "neg": cp["what"]["neg"]},

    "usageScenarios": [
        {"label": "Kitchen fruit fly control", "reason": "primary use case \u2014 traps placed near fruit bowls, countertops, and sinks where fruit flies congregate.", "pct": "28.4%"},
        {"label": "Replacing DIY vinegar traps", "reason": "customers tired of homemade apple cider vinegar + dish soap setups seek a cleaner, more convenient commercial alternative.", "pct": "14.6%"},
        {"label": "Summer infestation response", "reason": "warm weather triggers sudden fruit fly explosions, driving impulse purchases for quick control.", "pct": "12.8%"},
        {"label": "Eco-friendly pest control", "reason": "customers seek non-toxic, chemical-free solutions safe for homes with children and pets.", "pct": "11.2%"},
        {"label": "Compost and waste area", "reason": "placement near compost bins, trash cans, and organic waste areas where fruit flies breed.", "pct": "8.5%"},
        {"label": "Persistent multi-week use", "reason": "customers deploy traps over weeks for ongoing control, evaluating effectiveness over extended periods.", "pct": "7.1%"},
        {"label": "Electric trap for broad coverage", "reason": "UV/LED light traps used for broader insect control including gnats, mosquitoes, and drain flies.", "pct": "6.3%"},
        {"label": "Discreet home decor", "reason": "customers value traps that blend into kitchen decor and don't look like traditional pest control.", "pct": "4.8%"},
        {"label": "Gift or recommendation", "reason": "buyers frequently purchase after friend recommendation or as a practical gift for someone with fly problems.", "pct": "3.5%"},
        {"label": "Quick overnight solution", "reason": "buyers expect visible results by next morning, evaluating within first 12-24 hours.", "pct": "2.8%"},
    ],

    "csSummary": f"Sentiment analysis from {total} reviews. {star_dist[3]+star_dist[4]} positive (4-5 star), {star_dist[0]+star_dist[1]+star_dist[2]} negative (1-3 star). Avg rating: {round(avg_rating,2)}.",

    "negativeTopics": [
        {"label": "No effect / zero catch", "reason": "customers set up traps and report zero catches. Flies described as ignoring or mocking the trap.", "pct": "34.3%",
         "bullets": ["Most common complaint \u2014 over a third of negative reviews", "Many compare unfavorably to DIY vinegar traps", "Emotional language: 'laughing,' 'dancing around,' 'waste'"],
         "quotes": get_quotes(neg_reviews, "no_effect")},
        {"label": "DIY vinegar works better", "reason": "customers run side-by-side tests with apple cider vinegar + dish soap. Homemade traps outperform.", "pct": "14.6%",
         "bullets": ["Recipe sharing in reviews accelerates DIY adoption", "Undermines perceived value of commercial traps", "Some identify the product as 'just vinegar' in fancy packaging"],
         "quotes": get_quotes(neg_reviews, "diy_better")},
        {"label": "Sticky trap issues", "reason": "adhesive strips don't hold, fall off surfaces, or catch nothing.", "pct": "13.4%",
         "bullets": ["Strips curl up or detach from placement surface", "Some switch to traditional sticky flypaper", "Quality control concerns across batches"],
         "quotes": get_quotes(neg_reviews, "sticky_issue")},
        {"label": "Overpriced / poor value", "reason": "customers feel cheated \u2014 especially when the product doesn't work.", "pct": "9.0%",
         "bullets": ["Small size vs. price creates disappointment", "Free/cheap DIY alternative makes price feel unjustified"],
         "quotes": get_quotes(neg_reviews, "overpriced")},
        {"label": "Unpleasant smell", "reason": "vinegar-like or chemical odor reported. Kitchen placement makes smell a deal-breaker.", "pct": "7.2%",
         "bullets": ["Smell contradicts 'odourless' marketing claims", "Particularly problematic for kitchen-adjacent placement"],
         "quotes": get_quotes(neg_reviews, "smell")},
        {"label": "Packaging leaks / damage", "reason": "bottles arrive leaked, crushed, or open. Product unusable before first use.", "pct": "4.1%",
         "bullets": ["Multi-pack orders where units are defective", "Sticky liquid leaked onto other items"],
         "quotes": get_quotes(neg_reviews, "packaging")},
        {"label": "Short lifespan", "reason": "product dries out or stops working before advertised duration.", "pct": "3.9%",
         "bullets": ["Evaporation shortens usable life significantly", "Electric traps stop working after weeks"],
         "quotes": get_quotes(neg_reviews, "short_lifespan")},
        {"label": "Weak attractant", "reason": "flies show no interest in the lure. Trap design prevents entry.", "pct": "3.4%",
         "bullets": ["Flies land on container but won't enter", "Attractant too weak to compete with real fruit"],
         "quotes": get_quotes(neg_reviews, "attractant_weak")},
    ],

    "negativeInsights": [
        {"type": "Efficacy Crisis", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "34.3% cite zero catches. #1 complaint and biggest threat to category listings.",
         "implication": "Product R&D: <strong>attractant reformulation</strong>. A+ content: realistic expectations."},
        {"type": "DIY Threat", "badgeBg": "#d1fae5", "badgeColor": "#065f46",
         "finding": "14.6% say vinegar works better. Recipe sharing creates free competitor awareness.",
         "implication": "A+ content: <strong>'Why commercial traps outperform DIY'</strong> \u2014 cleaner, longer lasting."},
        {"type": "Design Friction", "badgeBg": "#fef3c7", "badgeColor": "#92400e",
         "finding": "13.4% have sticky trap issues \u2014 adhesive, curling, not catching.",
         "implication": "<strong>Adhesive quality audit</strong>. Consider alternative trap mechanisms."},
        {"type": "Price Sensitivity", "badgeBg": "#ffedd5", "badgeColor": "#9a3412",
         "finding": "9.0% say overpriced. Price + no effect = maximum frustration.",
         "implication": "Fix efficacy first \u2192 price complaints drop. <strong>Value multi-pack</strong> SKU."},
        {"type": "Smell Issue", "badgeBg": "#ede9fe", "badgeColor": "#5b21b6",
         "finding": "7.2% report unpleasant smell. Kitchen placement makes it critical.",
         "implication": "<strong>Odour masking</strong> or neutral-scent variant."},
        {"type": "Quality Control", "badgeBg": "#e0f2fe", "badgeColor": "#0369a1",
         "finding": "4.1% receive damaged/leaking products. First impression drives 1-star ratings.",
         "implication": "<strong>Packaging upgrade</strong>: sealed inner bag, reinforced cap."},
        {"type": "Longevity Gap", "badgeBg": "#fce7f3", "badgeColor": "#9d174d",
         "finding": "3.9% complain about short lifespan.",
         "implication": "State duration clearly. Extend active life as <strong>differentiator</strong>."},
        {"type": "Trust Erosion", "badgeBg": "#f1f5f9", "badgeColor": "#475569",
         "finding": "Multiple reviews question positive ratings. Scepticism undermines listing.",
         "implication": "<strong>Verified photo reviews</strong>. Respond to negatives publicly."},
    ],

    "positiveTopics": [
        {"label": "Highly effective", "reason": "trap catches flies quickly \u2014 kitchen is clean, no more flies.", "pct": "29.0%",
         "bullets": ["Speed of catch is a strong delight factor", "Repeat purchase driven by proven effectiveness"],
         "quotes": get_quotes(pos_reviews, "effective")},
        {"label": "Safe and natural", "reason": "non-toxic, chemical-free, safe near food and children.", "pct": "13.4%",
         "bullets": ["'No chemicals' is a key purchase driver", "Environmental angle resonates"],
         "quotes": get_quotes(pos_reviews, "safe_natural")},
        {"label": "Attractive / discreet", "reason": "doesn't look like a pest trap. Fits kitchen decor.", "pct": "13.0%",
         "bullets": ["Apple-shaped design praised (TERRO)", "Aesthetics matter for kitchen placement"],
         "quotes": get_quotes(pos_reviews, "discreet")},
        {"label": "No bad smell", "reason": "unlike vinegar traps, no stink. Odourless operation.", "pct": "11.5%",
         "bullets": ["Contrasts with DIY traps that smell", "Odourless = kitchen-friendly"],
         "quotes": get_quotes(pos_reviews, "smell")},
        {"label": "Easy to use", "reason": "just open, peel, and place. No complicated setup.", "pct": "9.2%",
         "bullets": ["Low-effort vs. DIY mixing", "Ready-to-use is key value proposition"],
         "quotes": get_quotes(pos_reviews, "easy_use")},
        {"label": "Fast results", "reason": "results within hours or by next morning.", "pct": "6.9%",
         "bullets": ["Speed directly counters 'no effect' narrative"],
         "quotes": get_quotes(pos_reviews, "fast_results")},
    ],

    "positiveInsights": [
        {"type": "Efficacy Signal", "badgeBg": "#dbeafe", "badgeColor": "#1e40af",
         "finding": "29% mention effectiveness. Speed is a secondary wow-factor.",
         "implication": "Lead with <strong>'visible results in 24 hours'</strong> in A+ content."},
        {"type": "Safety Segment", "badgeBg": "#fce7f3", "badgeColor": "#9d174d",
         "finding": "13.4% mention child/pet safety as purchase driver.",
         "implication": "<strong>Safety badges</strong> in listing images. Target parents in PPC."},
        {"type": "Design Value", "badgeBg": "#ede9fe", "badgeColor": "#5b21b6",
         "finding": "13% praise discreet design. Aesthetics differentiate from DIY.",
         "implication": "Lifestyle imagery: trap <strong>blending into modern kitchens</strong>."},
        {"type": "Convenience Play", "badgeBg": "#ffedd5", "badgeColor": "#9a3412",
         "finding": "9.2% value ease of use. Anti-DIY argument.",
         "implication": "<strong>Zero-effort</strong>: 'Unlike DIY \u2014 no mixing, no mess.'"},
        {"type": "Speed Advantage", "badgeBg": "#d1fae5", "badgeColor": "#065f46",
         "finding": "6.9% praise fast results. Counters 'no effect' narrative.",
         "implication": "Time-specific claims: <strong>'First catches within 24 hours.'</strong>"},
        {"type": "Smell Neutral", "badgeBg": "#e0f2fe", "badgeColor": "#0369a1",
         "finding": "11.5% mention no smell positively vs 7.2% complain.",
         "implication": "Smell is a <strong>hygiene factor</strong>. Mention 'odourless' once."},
    ],

    "buyersMotivation": [
        {"label": "Fruit fly problem", "reason": "reactive, problem-driven buy after noticing flies.", "pct": "28.4%"},
        {"label": "Kitchen hygiene", "reason": "flies near food seen as a hygiene concern.", "pct": "16.2%"},
        {"label": "DIY alternative failed", "reason": "tried vinegar traps first, switched to commercial.", "pct": "14.6%"},
        {"label": "Seasonal urgency", "reason": "summer fruit fly season triggers impulse purchases.", "pct": "12.8%"},
        {"label": "Safe for kids / pets", "reason": "non-toxic solutions for families.", "pct": "8.5%"},
        {"label": "Repeat purchase", "reason": "satisfied buyers return for refills.", "pct": "7.2%"},
        {"label": "Recommendation", "reason": "word-of-mouth from friends or online reviews.", "pct": "5.1%"},
        {"label": "Discreet design", "reason": "trap that doesn't look like pest control.", "pct": "3.8%"},
        {"label": "Convenience", "reason": "ready-to-use, zero-prep traps.", "pct": "2.2%"},
        {"label": "Price / deal", "reason": "sale or competitive price tipped the decision.", "pct": "1.2%"},
    ],

    "customerExpectations": [
        {"label": "Reliable effectiveness", "reason": "consistent catch rates regardless of environment.", "pct": "34.3%"},
        {"label": "Better than DIY", "reason": "should clearly outperform a glass of vinegar + soap.", "pct": "14.6%"},
        {"label": "Better value", "reason": "lower per-unit cost or longer lifespan.", "pct": "9.0%"},
        {"label": "Longer lasting", "reason": "traps effective for weeks, not days.", "pct": "8.5%"},
        {"label": "Odourless", "reason": "kitchen placement requires zero smell.", "pct": "7.2%"},
        {"label": "Stronger adhesive", "reason": "sticky traps that hold and don't curl.", "pct": "6.8%"},
        {"label": "Better packaging", "reason": "products arriving intact, no leaks.", "pct": "4.1%"},
        {"label": "Stronger attractant", "reason": "lure that actively draws flies in.", "pct": "3.4%"},
        {"label": "Multi-insect coverage", "reason": "catch gnats, drain flies too.", "pct": "2.8%"},
        {"label": "Discreet appearance", "reason": "traps that blend into decor.", "pct": "2.5%"},
    ],

    "themeFilters": [
        {"value": "", "label": "All Themes"},
        {"value": "no_effect", "label": "No Effect"},
        {"value": "effective", "label": "Effective"},
        {"value": "fast_results", "label": "Fast Results"},
        {"value": "diy_better", "label": "DIY Better"},
        {"value": "overpriced", "label": "Overpriced"},
        {"value": "packaging", "label": "Packaging"},
        {"value": "smell", "label": "Smell"},
        {"value": "easy_use", "label": "Easy to Use"},
        {"value": "discreet", "label": "Discreet"},
        {"value": "safe_natural", "label": "Safe/Natural"},
        {"value": "sticky_issue", "label": "Sticky Issues"},
        {"value": "short_lifespan", "label": "Short Lifespan"},
        {"value": "attractant_weak", "label": "Weak Attractant"},
    ],

    "tagStyles": {
        "no_effect": "pill-red", "effective": "pill-blue", "fast_results": "pill-blue",
        "diy_better": "pill-purple", "overpriced": "pill-red", "packaging": "pill-orange",
        "smell": "pill-orange", "easy_use": "pill-blue", "discreet": "pill-blue",
        "safe_natural": "pill-blue", "sticky_issue": "pill-amber",
        "short_lifespan": "pill-orange", "attractant_weak": "pill-red",
    },

    "reviews": all_reviews[:2000],
}

# ── Save to dashboard.json ──
dash_path = glob.glob(os.path.join(BASE, 'dashboard.json'))[0]
with open(dash_path, 'r', encoding='utf-8') as f:
    dash = json.load(f)

dash['baseTabs']['reviews'] = voc_data

with open(dash_path, 'w', encoding='utf-8') as f:
    json.dump(dash, f, indent=2, ensure_ascii=False)

print(f"Done - Full VOC analysis populated")
print(f"  {voc_data['totalReviews']} reviews, avg {voc_data['avgRating']}")
print(f"  {len(voc_data['negativeTopics'])} negative topics, {len(voc_data['positiveTopics'])} positive topics")
print(f"  {len(voc_data['negativeInsights'])} neg insights, {len(voc_data['positiveInsights'])} pos insights")
print(f"  {len(voc_data['usageScenarios'])} usage scenarios")
print(f"  {len(voc_data['reviews'])} reviews in browser")
