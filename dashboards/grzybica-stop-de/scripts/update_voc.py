"""Refresh anti-fungus VOC INSIGHTS only (no per-review translation).

Strategy: Gemini reads German natively. Single call regenerates analytical sections
from merged corpus (existing 531 English + 1515 new German reviews).

Usage:
  1. python scripts/update_voc.py build-prompt  -> writes scripts/_voc_prompt.txt
  2. (Claude calls Gemini Pro with that prompt, saves response to scripts/_voc_response.json)
  3. python scripts/update_voc.py apply         -> merges response into dashboard.json
  4. python _build_standalone.py                -> rebuilds index.html
"""
import json, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard.json"
NEW_JSON = ROOT / "reviews" / "ES_Antifungus_Nail_Varnish_Reviews.json"
PROMPT_PATH = ROOT / "scripts" / "_voc_prompt.txt"
RESPONSE_PATH = ROOT / "scripts" / "_voc_response.json"

INSIGHT_KEYS = [
    "cpSummary", "cpWho", "cpWhen", "cpWhere", "cpWhat",
    "usageScenarios", "csSummary",
    "negativeTopics", "positiveTopics",
    "negativeInsights", "positiveInsights",
    "buyersMotivation", "customerExpectations",
]


def build_prompt():
    new = json.load(open(NEW_JSON, encoding="utf-8"))
    dash = json.load(open(DASH, encoding="utf-8"))
    voc = dash["baseTabs"]["reviews"]

    existing_reviews = voc["reviews"]
    existing_insights = {k: voc[k] for k in INSIGHT_KEYS if k in voc}

    new_compact = []
    for r in new:
        body = (r.get("review_body") or "").strip()
        if not body:
            continue
        try:
            star = int(round(float(r.get("star_rating") or 0)))
        except Exception:
            continue
        if 1 <= star <= 5:
            new_compact.append({"r": star, "t": body})

    existing_compact = [{"r": int(r.get("r") or 0), "t": r.get("t", "")} for r in existing_reviews]

    total = len(existing_compact) + len(new_compact)
    star = [0, 0, 0, 0, 0]
    for r in existing_compact + new_compact:
        if 1 <= r["r"] <= 5:
            star[r["r"] - 1] += 1
    avg = round(sum((i + 1) * c for i, c in enumerate(star)) / max(total, 1), 2)

    prompt = f"""You are refreshing the Voice-of-Customer (VOC) analysis for the anti-fungal nail polish category on amazon.de.

A previous VOC analysis was built from 531 English (translated) reviews. We are now adding {len(new_compact)} more German Amazon reviews. You read German fluently — analyze them directly. Total merged corpus: {total} reviews. Star distribution: 1*={star[0]}, 2*={star[1]}, 3*={star[2]}, 4*={star[3]}, 5*={star[4]}. Average rating: {avg}.

TASK: regenerate the customer-insights sections, integrating signals from BOTH the existing English reviews and the new German reviews. Output JSON with the SAME structure as EXISTING_INSIGHTS below — same keys, same array lengths, same field names — but updated content (percentages, counts, summary text, quotes, bullets, findings, implications) reflecting the full {total}-review corpus.

OUTPUT RULES:
1. Output ONLY a valid JSON object. No prose, no markdown, no code fences.
2. Top-level keys MUST be exactly: cpSummary, cpWho, cpWhen, cpWhere, cpWhat, usageScenarios, csSummary, negativeTopics, positiveTopics, negativeInsights, positiveInsights, buyersMotivation, customerExpectations.
3. Match nested structure exactly. cpWho/When/Where/What each have labels[], pos[], neg[] of length 6. usageScenarios, negativeTopics, positiveTopics, negativeInsights, positiveInsights, buyersMotivation, customerExpectations: keep the SAME number of items as EXISTING_INSIGHTS.
4. negativeTopics/positiveTopics items keep: label, reason, pct (string like "12.3%"), bullets (array of 3 strings), quotes (array of 3 strings, each wrapped in double quotes, max 180 chars including the quote marks).
5. Insights items keep: type, badgeBg, badgeColor, finding, implication.
6. ALL output strings (quotes, summaries, findings, labels, reasons) MUST be in English. Translate any German quotes you cite.
7. cpSummary must mention the new total of {total} reviews. csSummary similarly.
8. cpWho/When/Where/What pos[] and neg[] are integer counts proportional to the merged corpus (rough magnitudes — they don't need to sum perfectly).
9. Topic percentages reflect approximate share within negative (1-2 star) or positive (4-5 star) subsets. Themes overlap, so they don't need to sum to 100.
10. Keep label texts close to existing where the theme still applies; introduce new labels only if the German reviews surface a clearly new theme worth replacing a weak existing one.

EXISTING_INSIGHTS (current 531-review version — use as the structural template):
{json.dumps(existing_insights, ensure_ascii=False)}

EXISTING_REVIEWS (English, 531 items):
{json.dumps(existing_compact, ensure_ascii=False)}

NEW_REVIEWS (German, {len(new_compact)} items, analyze directly):
{json.dumps(new_compact, ensure_ascii=False)}

Return the regenerated insights JSON object now."""

    PROMPT_PATH.write_text(prompt, encoding="utf-8")
    print(f"Prompt written: {PROMPT_PATH}")
    print(f"  size: {len(prompt):,} chars (~{len(prompt)//4:,} tokens)")
    print(f"  merged total: {total} reviews, avg {avg}, dist {star}")


def apply():
    text = RESPONSE_PATH.read_text(encoding="utf-8").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0]
    new_insights = json.loads(text)

    new = json.load(open(NEW_JSON, encoding="utf-8"))
    dash = json.load(open(DASH, encoding="utf-8"))
    voc = dash["baseTabs"]["reviews"]

    # Merge new German reviews into reviews array (untranslated, untagged)
    existing_reviews = voc["reviews"]
    seen = set((r.get("t") or "")[:120] for r in existing_reviews)
    merged = list(existing_reviews)
    for r in new:
        body = (r.get("review_body") or "").strip()
        if not body:
            continue
        key = body[:120]
        if key in seen:
            continue
        seen.add(key)
        try:
            star = int(round(float(r.get("star_rating") or 0)))
        except Exception:
            continue
        if 1 <= star <= 5:
            merged.append({"r": star, "t": body, "tags": []})

    star_dist = [0, 0, 0, 0, 0]
    for r in merged:
        v = int(r.get("r") or 0)
        if 1 <= v <= 5:
            star_dist[v - 1] += 1
    total = sum(star_dist)
    avg = round(sum((i + 1) * c for i, c in enumerate(star_dist)) / max(total, 1), 2)

    voc["totalReviews"] = total
    voc["avgRating"] = avg
    voc["starDist"] = star_dist
    voc["reviews"] = merged

    for k in INSIGHT_KEYS:
        if k in new_insights:
            voc[k] = new_insights[k]

    json.dump(dash, open(DASH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"Applied. totalReviews={total} avg={avg} dist={star_dist}")
    print(f"  insight keys updated: {[k for k in INSIGHT_KEYS if k in new_insights]}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build-prompt"
    if cmd == "build-prompt":
        build_prompt()
    elif cmd == "apply":
        apply()
    else:
        print("usage: update_voc.py [build-prompt|apply]")
        sys.exit(1)
