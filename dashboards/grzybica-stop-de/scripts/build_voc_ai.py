# -*- coding: utf-8 -*-
"""Generate AI VOC sections for grzybica-stop-de via Claude on the review corpus.

Reads dashboard.json (deterministic VOC already populated by build_voc.py),
samples ~100 reviews stratified by rating bucket, sends them to Claude with a
strict-JSON prompt, parses the response, merges into dashboard.json.

The AI fills in: cpSummary, cpWho/When/Where/What, usageScenarios,
negativeInsights, positiveInsights, buyersMotivation, customerExpectations.
It also returns English translations for the visible quotes inside
negativeTopics[].quotes and positiveTopics[].quotes.

Usage:  py scripts/build_voc_ai.py
"""
import os, sys, json, random, re, requests
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
DASH_PATH = ROOT / 'dashboard.json'
ENV_PATH  = Path('c:/AI Workspaces/Claude Code Workspace - Tom/.env')
RESPONSE_PATH = ROOT / 'scripts' / '_voc_response.json'
PROMPT_PATH   = ROOT / 'scripts' / '_voc_prompt.txt'

MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 16000

# ---------------------------------------------------------------------------
# Load API key
# ---------------------------------------------------------------------------
api_key = None
for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
    if line.startswith('ANTHROPIC_API_KEY='):
        api_key = line.split('=', 1)[1].strip()
        break
if not api_key:
    print('ANTHROPIC_API_KEY not found in .env', file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Load dashboard.json
# ---------------------------------------------------------------------------
with open(DASH_PATH, encoding='utf-8') as f:
    dash = json.load(f)
voc = dash['baseTabs']['reviews']
total = voc['totalReviews']
avg = voc['avgRating']
stars = voc['starDist']
neg_topics = voc.get('negativeTopics', [])
pos_topics = voc.get('positiveTopics', [])

# ---------------------------------------------------------------------------
# Sample reviews — stratified by rating bucket
# ---------------------------------------------------------------------------
random.seed(42)
all_reviews = voc['reviews']
by_bucket = {1: [], 2: [], 3: [], 4: [], 5: []}
for r in all_reviews:
    if r['r'] in by_bucket:
        by_bucket[r['r']].append(r)

# Take a proportional sample, capped at 100 total.
TARGET_SAMPLE = 100
sample = []
totals = sum(len(v) for v in by_bucket.values())
for star, revs in by_bucket.items():
    n = max(2, round(TARGET_SAMPLE * len(revs) / totals)) if totals else 0
    sample.extend(random.sample(revs, min(n, len(revs))))

# Compact each review for prompt economy
def compact(r):
    body = (r.get('t') or '').strip().replace('\n', ' ')
    if len(body) > 350:
        body = body[:350].rsplit(' ', 1)[0] + '...'
    return f"[{r['r']}* {r['segment']} {r['asin']}] {body}"

review_block = '\n'.join(compact(r) for r in sample)
print(f'Sampled {len(sample)} reviews from {totals} total ({len(review_block):,} chars)')

# ---------------------------------------------------------------------------
# Build topic blocks for translation
# ---------------------------------------------------------------------------
def topic_for_prompt(topics, label):
    out = []
    for t in topics:
        # Reverse-derive theme key from label by lookup
        out.append({
            'label': t['label'],
            'pct': t['pct'],
            'quotes': t.get('quotes', []),
        })
    return out

neg_for_prompt = topic_for_prompt(neg_topics, 'negative')
pos_for_prompt = topic_for_prompt(pos_topics, 'positive')

# ---------------------------------------------------------------------------
# Build the prompt
# ---------------------------------------------------------------------------
PROMPT = f'''You are analyzing customer reviews for the anti-fungal foot/nail treatment category on amazon.de (Germany). Output a strict JSON object for a market-research dashboard.

CONTEXT
- Category: anti-fungal cream + spray for athlete's foot (Fußpilz) and onychomycosis (nail fungus)
- Marketplace: amazon.de (4 Cream + 4 Spray ASINs from Aliud Pharma Clotrimazol, Canesten, Lamisil, PI SOS Disinfectant)
- Total reviews in corpus: {total} unique
- Avg rating: {avg}
- Star distribution (1*..5*): {stars}
- Sample below: {len(sample)} reviews stratified across the 5 star buckets

REVIEW SAMPLE (German, original — read natively, do not translate the corpus, just the labels/quotes you output)
{review_block}

EXISTING TOPIC LABELS — translate the German quotes inside each to English (preserve quotation marks, keep one short snippet under 180 chars per quote)
NEGATIVE TOPICS:
{json.dumps(neg_for_prompt, ensure_ascii=False, indent=2)}

POSITIVE TOPICS:
{json.dumps(pos_for_prompt, ensure_ascii=False, indent=2)}

OUTPUT — return ONLY one JSON object (no prose, no markdown fences). Schema:

{{
  "cpSummary": "2-3 sentences in English describing the customer profile. Use <strong> tags around 2-3 key terms.",
  "cpWho":   {{"labels": [4 short labels], "pos": [4 counts], "neg": [4 counts]}},
  "cpWhen":  {{"labels": [4 short labels], "pos": [4 counts], "neg": [4 counts]}},
  "cpWhere": {{"labels": [4 short labels], "pos": [4 counts], "neg": [4 counts]}},
  "cpWhat":  {{"labels": [4 short labels], "pos": [4 counts], "neg": [4 counts]}},
  "usageScenarios": [array of 8-10 objects {{"label","reason","pct"}}; pct as "X.X%" summing to ~100%],
  "negativeInsights": [array of 6-8 objects {{"type","badgeBg","badgeColor","finding","implication"}}; finding+implication may use <strong>],
  "positiveInsights": [array of 5-6 objects same shape as negativeInsights],
  "buyersMotivation": [array of 8-10 objects {{"label","reason","pct"}}; pct as "X.X%" summing to ~100%],
  "customerExpectations": [array of 8-10 objects {{"label","reason","pct"}}; pct as "X.X%" summing to ~100%],
  "translatedQuotes": {{
    "negative": {{ "<topic label>": [up to 3 English quote strings with surrounding double quotes] }},
    "positive": {{ "<topic label>": [up to 3 English quote strings with surrounding double quotes] }}
  }}
}}

CONSTRAINTS
- Every output string in English; concise and dashboard-ready
- cpWho labels (examples): "First-time sufferer", "Chronic/Recurring", "Caretaker (parent/spouse)", "Athletes/Active"
- cpWhen labels (examples): "Acute outbreak", "After failed home remedy", "Long-term management", "Pre-vacation prep"
- cpWhere labels (examples): "Between toes", "Toenails", "Sole/heel", "Multiple sites"
- cpWhat labels (examples): "Effectiveness", "Skin tolerance", "Application ease", "Speed of results"
- pos/neg counts must be plausible integers consistent with bucket sizes ({stars[3]+stars[4]} positive 4-5*, {stars[0]+stars[1]} negative 1-2*); they should sum across labels to ~the bucket total but a slight overlap is fine
- badgeBg/badgeColor pairs (use as a palette, recycle across items):
  ("#fee2e2","#991b1b"), ("#d1fae5","#065f46"), ("#fef3c7","#92400e"),
  ("#dbeafe","#1e40af"), ("#ede9fe","#5b21b6"), ("#fce7f3","#9d174d"),
  ("#ffedd5","#9a3412"), ("#e0f2fe","#0369a1")
- "translatedQuotes" must include EVERY topic label from the input (use the exact "label" string as the key)
- DO NOT include a top-level "csSummary" or topic structures themselves — those stay deterministic in the dashboard'''

PROMPT_PATH.write_text(PROMPT, encoding='utf-8')
print(f'Prompt: {len(PROMPT):,} chars  ->  {PROMPT_PATH.name}')

# ---------------------------------------------------------------------------
# Call Claude
# ---------------------------------------------------------------------------
print(f'Calling Claude ({MODEL})...')
resp = requests.post(
    'https://api.anthropic.com/v1/messages',
    headers={
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    },
    json={
        'model': MODEL,
        'max_tokens': MAX_TOKENS,
        'messages': [{'role': 'user', 'content': PROMPT}],
    },
    timeout=600,
)
if resp.status_code != 200:
    print(f'ERROR {resp.status_code}: {resp.text[:1500]}', file=sys.stderr)
    sys.exit(1)
data = resp.json()
text = ''.join(b.get('text', '') for b in data.get('content', []) if b.get('type') == 'text')
usage = data.get('usage') or {}
print(f'Response: {len(text):,} chars  |  in={usage.get("input_tokens")}, out={usage.get("output_tokens")}')

# ---------------------------------------------------------------------------
# Parse JSON (tolerant of code fences)
# ---------------------------------------------------------------------------
m = re.search(r'\{.*\}\s*$', text.strip(), re.DOTALL)
if not m:
    RESPONSE_PATH.write_text(text, encoding='utf-8')
    print('Could not extract JSON; raw saved to _voc_response.json', file=sys.stderr)
    sys.exit(1)
try:
    ai = json.loads(m.group(0))
except json.JSONDecodeError as e:
    RESPONSE_PATH.write_text(text, encoding='utf-8')
    print(f'JSON parse failed: {e}; raw saved to _voc_response.json', file=sys.stderr)
    sys.exit(1)
RESPONSE_PATH.write_text(json.dumps(ai, ensure_ascii=False, indent=2), encoding='utf-8')

# ---------------------------------------------------------------------------
# Merge into dashboard.json
# ---------------------------------------------------------------------------
ai_keys = ['cpSummary', 'cpWho', 'cpWhen', 'cpWhere', 'cpWhat',
           'usageScenarios', 'negativeInsights', 'positiveInsights',
           'buyersMotivation', 'customerExpectations']
for k in ai_keys:
    if k in ai:
        voc[k] = ai[k]
    else:
        print(f'  warn: AI response missing "{k}"')

# Apply translated quotes onto existing topic structures
tq = ai.get('translatedQuotes') or {}
for bucket_key, topics in [('negative', neg_topics), ('positive', pos_topics)]:
    bucket = tq.get(bucket_key) or {}
    for t in topics:
        new_quotes = bucket.get(t['label'])
        if new_quotes:
            t['quotes'] = new_quotes
voc['negativeTopics'] = neg_topics
voc['positiveTopics'] = pos_topics

dash['baseTabs']['reviews'] = voc
with open(DASH_PATH, 'w', encoding='utf-8') as f:
    json.dump(dash, f, ensure_ascii=False, indent=2)

print()
print('Merged AI VOC into dashboard.json:')
print(f'  cpSummary: {len(voc["cpSummary"])} chars')
print(f'  cpWho/When/Where/What: {[len(voc[k]["labels"]) for k in ("cpWho","cpWhen","cpWhere","cpWhat")]} labels each')
print(f'  usageScenarios: {len(voc["usageScenarios"])}')
print(f'  negativeInsights: {len(voc["negativeInsights"])}, positiveInsights: {len(voc["positiveInsights"])}')
print(f'  buyersMotivation: {len(voc["buyersMotivation"])}, customerExpectations: {len(voc["customerExpectations"])}')
print(f'  Negative quotes translated for {sum(1 for t in neg_topics if t.get("quotes"))} of {len(neg_topics)} topics')
print(f'  Positive quotes translated for {sum(1 for t in pos_topics if t.get("quotes"))} of {len(pos_topics)} topics')
print()
print('Now run: py _build_standalone.py')
