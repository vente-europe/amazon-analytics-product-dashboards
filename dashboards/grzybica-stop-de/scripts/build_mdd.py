"""Assemble Marketing Deep-Dive data block and write to dashboard.json."""
import os, json

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Load sources
with open(os.path.join(BASE, 'scripts', '_listings.json'), encoding='utf-8') as f:
    listings = json.load(f)
with open(os.path.join(BASE, 'scripts', '_gemini_output.json'), encoding='utf-8') as f:
    gemini = json.load(f)
with open(os.path.join(BASE, 'dashboard.json'), encoding='utf-8') as f:
    dash = json.load(f)

# Claim theme keys in display order
claim_themes = [
    {"key": "effectiveness", "label": "Eradicates Fungus"},
    {"key": "speed", "label": "Fast Results"},
    {"key": "natural", "label": "Natural"},
    {"key": "clinical_proof", "label": "Clinically Proven"},
    {"key": "active_ingredient", "label": "Active Ingredient"},
    {"key": "easy_use", "label": "Easy to Use"},
    {"key": "gentle_safe", "label": "Gentle & Safe"},
    {"key": "cosmetic", "label": "Cosmetic"},
    {"key": "value_guarantee", "label": "Value/Guarantee"},
    {"key": "comprehensive_kit", "label": "Comprehensive Kit"},
]

# Map asin → themes
asin_to_themes = {c['asin']: set(c['themes']) for c in gemini['claims']}

# Build competitor cards (top 20 sorted by revenue)
competitors = []
for l in listings:
    themes = asin_to_themes.get(l['asin'], set())
    competitors.append({
        "asin": l['asin'],
        "brand": l['brand'] or 'Unknown',
        "title": l['title'],
        "price": l['price'],
        "rating": l['rating'],
        "reviews": l['reviews'],
        "bsr": l['bsr'],
        "rev30d": l['rev30d'],
        "mainImage": l['images'][0] if l['images'] else '',
        "images": l['images'],
        "bullets": l['bullets'],
        "description": l.get('description', ''),
        "themes": sorted(list(themes)),
        "claimCount": len(themes),
    })

# Build claims matrix for quick grid rendering
claims_matrix = {
    "themes": claim_themes,
    "rows": [
        {
            "asin": c['asin'],
            "brand": c['brand'],
            "cells": [1 if t['key'] in asin_to_themes.get(c['asin'], set()) else 0 for t in claim_themes]
        }
        for c in competitors
    ]
}

mdd = {
    "totalCompetitors": len(competitors),
    "marketplace": "amazon.de",
    "currency": "€",
    "exportMonth": 3,
    "competitors": competitors,
    "claimsMatrix": claims_matrix,
    "claimsSummary": gemini['claimsSummary'],
    "titleAnalysis": gemini['titleAnalysis'],
    "bulletAnalysis": gemini['bulletAnalysis'],
    "vocGap": gemini['vocGap'],
    "whitespaceOpportunities": gemini['whitespaceOpportunities'],
    "saturation": gemini['saturation'],
    "strategicRecommendations": gemini['strategicRecommendations'],
}

dash.setdefault('addonTabs', {})['marketing-deep-dive'] = mdd
with open(os.path.join(BASE, 'dashboard.json'), 'w', encoding='utf-8') as f:
    json.dump(dash, f, ensure_ascii=False, indent=2)

print(f"MDD data assembled — {len(competitors)} competitors, {len(claim_themes)} claim themes")
print(f"Claims matrix: {sum(sum(r['cells']) for r in claims_matrix['rows'])} filled cells")
print(f"Saved to dashboard.json addonTabs['marketing-deep-dive']")
