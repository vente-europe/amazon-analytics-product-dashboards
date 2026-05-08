# -*- coding: utf-8 -*-
"""Merge competitor cards + Gemini AI sections into dashboard.json addonTabs['marketing-deep-dive'].

Builds a `bySegment` map under MDD with one entry per segment ('Cream', 'Spray')
plus a combined 'all' view, so the dashboard can render a segment-pill selector
that swaps the entire view. The shared template field names are honored:
  whitespaceOpportunities[].opportunity / rationale / evidence
  saturation[].label / saturationPct / advice
  strategicRecommendations[].type / finding / implication / badgeBg / badgeColor
"""
import json, os, sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
COMP = os.path.join(ROOT, 'scripts', '_mdd_competitors.json')
RESP_ALL    = os.path.join(ROOT, 'scripts', '_mdd_response.json')
RESP_CREAM  = os.path.join(ROOT, 'scripts', '_mdd_response_cream.json')
RESP_SPRAY  = os.path.join(ROOT, 'scripts', '_mdd_response_spray.json')
DASH = os.path.join(ROOT, 'dashboard.json')

CLAIM_THEMES = [
    {"key": "effectiveness",     "label": "Eradicates Fungus"},
    {"key": "speed",             "label": "Fast Results"},
    {"key": "natural",           "label": "Natural / Plant-based"},
    {"key": "clinical_proof",    "label": "Clinically Proven"},
    {"key": "active_ingredient", "label": "Named Active Ingredient"},
    {"key": "easy_use",          "label": "Easy to Apply"},
    {"key": "gentle_safe",       "label": "Gentle / Skin-friendly"},
    {"key": "broad_spectrum",    "label": "Broad-Spectrum / Multi-fungus"},
    {"key": "value_guarantee",   "label": "Value / Money-back"},
    {"key": "kit_combo",         "label": "Kit / Combo / Multipack"},
]
THEME_KEYS = [t['key'] for t in CLAIM_THEMES]
THEME_LABEL = {t['key']: t['label'] for t in CLAIM_THEMES}

with open(COMP, encoding='utf-8') as f: competitors = json.load(f)

# Map asin -> theme keys from the all-segments response (covers every ASIN)
with open(RESP_ALL, encoding='utf-8') as f: ai_all = json.load(f)
asin_to_themes = {row['asin']: set(row.get('themeKeys', [])) for row in ai_all['claimsMatrix']}

# Hydrate competitor cards with themes (used by competitor grid + modal)
for c in competitors:
    c['themes'] = sorted(asin_to_themes.get(c['asin'], set()))
    c['claimCount'] = len(c['themes'])

# ---------------------------------------------------------------------------
# Field remappers — translate Gemini schema -> template schema
# ---------------------------------------------------------------------------
def remap_whitespace(items):
    return [{
        'opportunity': it.get('title') or it.get('opportunity', ''),
        'rationale':   it.get('rationale', ''),
        'evidence':    it.get('evidence', ''),
    } for it in items]

def remap_saturation(items, summary_lookup):
    """Pull saturationPct from claimsSummary by matching the title to a label.
    Falls back to extracting any percentage from the evidence string."""
    import re
    out = []
    for it in items:
        title = it.get('title') or it.get('label', '')
        # 1) Try to match the saturated claim to one of the claimsSummary themes
        pct = ''
        for label, p in summary_lookup.items():
            if label.lower() in title.lower() or title.lower() in label.lower():
                pct = p; break
        # 2) Fall back to an explicit percentage in the evidence/rationale
        if not pct:
            m = re.search(r'(\d+%)', it.get('evidence', '') + ' ' + it.get('rationale', ''))
            if m: pct = m.group(1)
        out.append({
            'label':         title,
            'saturationPct': pct,
            'advice':        it.get('rationale', '') + (' Evidence: ' + it.get('evidence', '') if it.get('evidence') else ''),
        })
    return out

def remap_recommendations(items):
    out = []
    for it in items:
        actions = it.get('actions') or []
        # Compose implication from rationale + concrete actions
        impl = ''
        if actions:
            impl = '<strong>Actions:</strong> ' + ' &middot; '.join(actions)
        out.append({
            'type':       it.get('headline') or it.get('type', ''),
            'badgeBg':    it.get('badgeBg', '#dbeafe'),
            'badgeColor': it.get('badgeColor', '#1e40af'),
            'finding':    it.get('rationale', '') or it.get('finding', ''),
            'implication': impl or it.get('implication', ''),
        })
    return out

# ---------------------------------------------------------------------------
# Builder for one segment view (or 'all')
# ---------------------------------------------------------------------------
def build_view(seg, ai):
    """Build a complete MDD view for either 'all', 'Cream' or 'Spray'."""
    if seg == 'all':
        seg_competitors = competitors
    else:
        seg_competitors = [c for c in competitors if c['segment'] == seg]
    seg_asins = {c['asin'] for c in seg_competitors}

    # Filter claimsMatrix rows to this segment
    matrix_rows = []
    for c in seg_competitors:
        cell_set = asin_to_themes.get(c['asin'], set())
        cells = [1 if k in cell_set else 0 for k in THEME_KEYS]
        matrix_rows.append({"asin": c['asin'], "brand": c['brand'], "cells": cells})

    # Recompute claimsSummary from segment-filtered listings (always reliable)
    seg_count = max(len(seg_competitors), 1)
    counts = Counter()
    brands_per_theme = {k: Counter() for k in THEME_KEYS}
    for c in seg_competitors:
        for k in c['themes']:
            counts[k] += 1
            brands_per_theme[k][c['brand']] += 1
    summary_lookup = {}
    claims_summary = []
    for k in sorted(counts.keys(), key=lambda x: -counts[x]):
        n = counts[k]
        pct = f'{round(100*n/seg_count)}%'
        top = [b for b, _ in brands_per_theme[k].most_common(3)]
        label = THEME_LABEL[k]
        claims_summary.append({"label": label, "count": n, "pct": pct, "topBrands": top})
        summary_lookup[label] = pct
    # Add zero-count themes at the bottom for completeness
    for k in THEME_KEYS:
        if k not in counts:
            label = THEME_LABEL[k]
            claims_summary.append({"label": label, "count": 0, "pct": '0%', "topBrands": []})
            summary_lookup[label] = '0%'

    return {
        "totalCompetitors": len(seg_competitors),
        "segmentLabel":     seg if seg != 'all' else 'All Segments',
        "marketplace":      "amazon.de",
        "currency":         "€",
        "exportMonth":      4,
        "competitors":      seg_competitors,
        "claimsMatrix":     {"themes": CLAIM_THEMES, "rows": matrix_rows},
        "claimsSummary":    claims_summary,
        "vocGap":           ai.get('vocGap', []),
        "whitespaceOpportunities": remap_whitespace(ai.get('whitespaceOpportunities', [])),
        "saturation":       remap_saturation(ai.get('saturation', []), summary_lookup),
        "strategicRecommendations": remap_recommendations(ai.get('strategicRecommendations', [])),
        "titleAnalysis":    {"hookFormulas": [], "topPhrases": [], "lengthDistribution": []},
        "bulletAnalysis":   {"openerPatterns": [], "themeCoverage": []},
    }

# ---------------------------------------------------------------------------
# Build views
# ---------------------------------------------------------------------------
views = {'all': build_view('all', ai_all)}

# Per-segment AI sections — fall back to all-segment AI if segment-specific
# response file is missing
def load_or_default(path, default):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f: return json.load(f)
    return default

ai_cream = load_or_default(RESP_CREAM, ai_all)
ai_spray = load_or_default(RESP_SPRAY, ai_all)

views['Cream'] = build_view('Cream', ai_cream)
views['Spray'] = build_view('Spray', ai_spray)

# Shape the MDD object: keep a default shape (so existing template still works
# if it reads top-level fields) AND a `bySegment` map for the new pill switcher.
mdd = dict(views['all'])
mdd['bySegment'] = views

with open(DASH, encoding='utf-8') as f: dash = json.load(f)
dash.setdefault('addonTabs', {})['marketing-deep-dive'] = mdd
with open(DASH, 'w', encoding='utf-8') as f:
    json.dump(dash, f, ensure_ascii=False, indent=2)

print(f'MDD merged with {len(views)} views:')
for k, v in views.items():
    print(f'  {k:8s}: {v["totalCompetitors"]} competitors, claimsSummary {len(v["claimsSummary"])}, '
          f'whitespace {len(v["whitespaceOpportunities"])}, saturation {len(v["saturation"])}, '
          f'recs {len(v["strategicRecommendations"])}')
