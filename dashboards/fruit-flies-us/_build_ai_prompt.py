"""Build Gemini re-analysis prompts for each segment, embedding the rebalanced
sample (now incl. 4/5-star positives) + the existing _ai.json as an exact FORMAT
template. Writes _voc_work/{slug}_prompt.txt. We then pass each to gemini-query and
save the returned JSON back to _voc_work/{slug}_ai.json.
"""
import json, os

BODY_CAP = 300
PROMPT_SAMPLE = 200   # reviews embedded into the prompt

def stardist(pool):
    sd = [0]*5
    for r in pool:
        sd[r['rating']-1] += 1
    return sd

for slug, seg in [('lure', 'Lure'), ('electric', 'Electric Traps')]:
    pool = json.load(open(f'_voc_work/{slug}_all.json', encoding='utf-8'))
    sample = json.load(open(f'_voc_work/{slug}_sample.json', encoding='utf-8'))
    template = open(f'_voc_work/{slug}_ai.json', encoding='utf-8').read()

    total = len(pool)
    avg = round(sum(r['rating'] for r in pool)/total, 2)
    sd = stardist(pool)

    # Compact review block
    lines = []
    for i, r in enumerate(sample[:PROMPT_SAMPLE], 1):
        body = (r.get('body') or '').replace('\n', ' ').strip()
        if len(body) > BODY_CAP:
            body = body[:BODY_CAP] + '…'
        title = (r.get('title') or '').replace('\n', ' ').strip()
        lines.append(f"[{i}] {r.get('rating')}* ({r.get('brand','?')}) {title} :: {body}")
    reviews_block = '\n'.join(lines)

    prompt = f"""You are a senior Voice-of-Customer analyst. Re-analyze the Amazon US "{seg}" \
fruit-fly-trap segment from the customer reviews below.

POPULATION CONTEXT (use these exact headline numbers):
- Total reviews in segment population: {total}
- Average rating: {avg}
- Star distribution [1*,2*,3*,4*,5*]: {sd}
- ASIN/brand coverage: {len(set(r.get('asin') for r in sample))} ASINs in the sample below.

CRITICAL — WHAT CHANGED: This dataset was PREVIOUSLY negative-only (1-3 star). It NOW \
includes genuine 4-star and 5-star positive reviews (a positive-review pull was merged in). \
Your re-analysis MUST reflect that rebalance:
- positiveTopics / positiveInsights / buyersMotivation must capture REAL praise from the 4-5* reviews \
(what genuinely delighted buyers — fast results, actually catching flies, design, value), not just \
"partial successes inferred from 3-star" framing.
- customer-profile pos/neg integer counts (cpWho/cpWhen/cpWhere/cpWhat) must move toward the new, \
less-negative distribution — positives are no longer near-zero.
- negativeTopics / negativeInsights / customerExpectations still matter (negatives remain the majority) \
but should be weighted to the new population, not the old all-negative one.
- cpSummary / csSummary must DROP the old "dataset contains only 1-3 star" caveat and instead describe \
a mixed dataset (avg {avg}).

OUTPUT FORMAT — return ONLY a single JSON object, no markdown fences, no commentary. It must have \
EXACTLY the same keys, nesting, and value types as the TEMPLATE below. Copy the STRUCTURE only — \
replace ALL content with your fresh analysis of the reviews. Keep:
- the same key names and array lengths (negativeTopics: 8, positiveTopics: 5, usageScenarios: 8, \
buyersMotivation: 8, customerExpectations: 8, negativeInsights: 6, positiveInsights: 4, and the \
cpWho/cpWhen/cpWhere/cpWhat label/pos/neg shape).
- pct values as percent strings like "41.5%".
- pos/neg as arrays of integers (counts), each array same length as its labels array, scaled to the \
{total}-review population.
- badgeBg / badgeColor as hex colors (reuse the template's palette).
- inline <strong>…</strong> HTML inside cpSummary, csSummary and every insight "implication".
- All quotes must be REAL verbatim snippets taken from the reviews below (in quotes), 3 per topic.

TEMPLATE (structure to mirror — DO NOT reuse its wording/content):
{template}

REVIEWS (rating* (brand) title :: body):
{reviews_block}
"""
    open(f'_voc_work/{slug}_prompt.txt', 'w', encoding='utf-8').write(prompt)
    print(f'{slug}: prompt {len(prompt):,} chars · {len(sample)} reviews · total={total} avg={avg} star={sd}')
