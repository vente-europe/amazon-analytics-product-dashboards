# -*- coding: utf-8 -*-
"""Build VOC analysis from grzybica-stop-de German reviews.

Deterministic parts only. AI sections (customer profile bars, strategic insights,
motivations, expectations, usage scenarios) are populated with TODO placeholders
that render an empty-ish but valid structure — fill them via a separate AI pass.

Pipeline:
  1. Aggregate reviews from reviews/{ASIN}-{Segment}.json (dedupe by text prefix)
  2. Apply regex theme tagging (German + English foot-fungus keywords)
  3. Compute stats (totalReviews, avgRating, starDist)
  4. Bucket reviews by sentiment (1-2 = neg, 4-5 = pos)
  5. Build negativeTopics / positiveTopics from theme frequencies
  6. Extract top 3 quotes per topic (machine-translate DE -> EN if available)
  7. Build themeFilters + tagStyles + csSummary
  8. Save to dashboard.json baseTabs.reviews
"""
import json, glob, os, re, sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
REVIEWS_DIR = os.path.join(BASE, 'reviews')
DASH_PATH = os.path.join(BASE, 'dashboard.json')
TRANS_CACHE = os.path.join(BASE, 'scripts', '_translate_cache.json')

# Translation: enabled by default, disabled via `--no-translate` flag.
# Google Translate throttles aggressively at scale (1500+ calls), so for fast
# rebuilds we keep cached translations and skip new ones.
NO_TRANSLATE = '--no-translate' in sys.argv
try:
    from deep_translator import GoogleTranslator
    TRANS_AVAILABLE = not NO_TRANSLATE
    if NO_TRANSLATE:
        print('[note] --no-translate flag set: using cached translations only, leaving uncached strings in German.')
except ImportError:
    TRANS_AVAILABLE = False
    print('[note] deep_translator not installed — quotes will stay German.')

# ---------------------------------------------------------------------------
# Theme tagging — German + English keywords for foot fungus / antifungal
# ---------------------------------------------------------------------------
THEMES = {
    # POSITIVE
    'effective':       r'wirkt|wirksam|hilft|super|sehr gut|klasse|empfehlen|spitze|gut geholfen|funktioniert|works|effective|excellent|great',
    'fast_results':    r'schnell|sofort|rasch|innerhalb (von )?(tag|woch)|nach (wenigen )?tagen|fast|quick(ly)?|right away|immediately',
    'easy_use':        r'einfach|leicht anzuwenden|praktisch|simple|easy to (use|apply)',
    'skin_friendly':   r'hautverträglich|hautfreundlich|sanft|mild|verträglich|gentle',
    'odorless':        r'geruchlos|kein geruch|neutraler? geruch|odorless|no smell',
    'good_value':      r'preis(\s|-|/)leistung|preiswert|günstig|good value|worth (the )?money',
    'no_recurrence':   r'nicht wiedergekommen|nicht zurück|kein rückfall|no recurrence|stayed away',

    # NEGATIVE
    'no_effect':       r'wirkt nicht|keine wirkung|hilft nicht|kein effekt|enttäusch|nutzlos|sinnlos|bringt nichts|brachte nichts|no effect|doesn.?t work|didn.?t work|useless|waste',
    'skin_irritation': r'brennt|brennen|juckt|jucken|reizung|rötung|allergisch|unverträglich|ausschlag|nebenwirkung|burning|itching|irritation|rash|side effect',
    'recurrence':      r'(pilz )?(kam|kommt|gekommen)? zurück|wiederkehrend|wieder da|came back|returned',
    'bad_smell':       r'stinkt|stinkend|unangenehmer geruch|chemisch riech|bad smell|smells (bad|chemical|awful)',
    'expensive':       r'\bteuer\b|überteuert|zu viel geld|preiswucher|expensive|overpriced|too pricey',
    'slow_results':    r'(zu )?lange( gedauert)?|mehrere wochen|wochenlang|langsam|nicht schnell|slow|takes (too )?long|forever',
    'sticky_greasy':   r'klebrig|fettig|schmierig|zieht nicht ein|hinterlässt rückstand|sticky|greasy|oily|residue',
    'packaging':       r'undicht|ausgelaufen|beschädigt|kaputt|leer angekommen|verpackung|leak|leaked|broken|damaged|empty',
    'spray_weak':      r'sprüht (nicht|kaum|wenig)|zu wenig sprüht|spray funktioniert nicht|dose leer|weak spray',
    'unclear_use':     r'anleitung (fehlt|unklar)|wie (anwenden|benutzen)|keine anweisung|unclear|no instructions',
}

# Category coloring for the review browser pills
TAG_STYLES = {
    'effective':       'pill-blue',
    'fast_results':    'pill-blue',
    'easy_use':        'pill-blue',
    'skin_friendly':   'pill-blue',
    'odorless':        'pill-blue',
    'good_value':      'pill-blue',
    'no_recurrence':   'pill-blue',
    'no_effect':       'pill-red',
    'skin_irritation': 'pill-red',
    'recurrence':      'pill-red',
    'bad_smell':       'pill-orange',
    'expensive':       'pill-red',
    'slow_results':    'pill-orange',
    'sticky_greasy':   'pill-amber',
    'packaging':       'pill-orange',
    'spray_weak':      'pill-amber',
    'unclear_use':     'pill-amber',
}

# Display labels for filters
THEME_LABELS = {
    'effective':       'Effective',
    'fast_results':    'Fast Results',
    'easy_use':        'Easy to Use',
    'skin_friendly':   'Skin-Friendly',
    'odorless':        'Odorless',
    'good_value':      'Good Value',
    'no_recurrence':   'No Recurrence',
    'no_effect':       'No Effect',
    'skin_irritation': 'Skin Irritation',
    'recurrence':      'Fungus Came Back',
    'bad_smell':       'Bad Smell',
    'expensive':       'Expensive',
    'slow_results':    'Slow Results',
    'sticky_greasy':   'Sticky / Greasy',
    'packaging':       'Packaging Issues',
    'spray_weak':      'Weak Spray',
    'unclear_use':     'Unclear Use',
}

# Topic-level descriptive blurbs (English) — shown above each topic's bullets
TOPIC_REASONS = {
    'no_effect':       'Customers report the product had no impact on the fungus despite consistent application.',
    'skin_irritation': 'Burning, itching, redness, or allergic reaction reported after applying the product.',
    'recurrence':      'Fungus returned after the treatment course finished or even during continued use.',
    'bad_smell':       'Strong chemical or unpleasant odor reported, particularly an issue for foot/sock contact.',
    'expensive':       'Customers feel the price-to-effect ratio is poor, especially when treatment fails.',
    'slow_results':    'Treatment takes weeks longer than expected; customers lose patience or stop using.',
    'sticky_greasy':   'Cream is greasy, leaves residue, or fails to absorb into the skin properly.',
    'packaging':       'Damaged, leaking, or empty packaging reported on arrival.',
    'spray_weak':      'Spray mechanism fails: weak pump, runs dry early, or fails to coat the area.',
    'unclear_use':     'Application instructions are missing, unclear, or in the wrong language.',
    'effective':       'Customers confirm visible reduction in fungal symptoms after the recommended course.',
    'fast_results':    'Visible improvement reported within days, sometimes after the first applications.',
    'easy_use':        'Simple to apply, fits into daily routine without effort.',
    'skin_friendly':   'Gentle on sensitive skin, no irritation reported.',
    'odorless':        'No noticeable smell, comfortable to wear with socks/shoes.',
    'good_value':      'Customers consider the price fair given the result.',
    'no_recurrence':   'Fungus stayed away for months after completing the course.',
}

# ---------------------------------------------------------------------------
# Translation cache (DE quote -> EN)
# ---------------------------------------------------------------------------
def load_cache():
    if os.path.exists(TRANS_CACHE):
        try:
            with open(TRANS_CACHE, encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_cache(c):
    with open(TRANS_CACHE, 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=2)

translate_cache = load_cache()
translator = GoogleTranslator(source='de', target='en') if TRANS_AVAILABLE else None

def translate(text):
    """Translate German -> English. Always check cache first. Only call the API
    when translation is enabled and the string isn't already cached."""
    if not text: return text
    if text in translate_cache: return translate_cache[text]
    if not TRANS_AVAILABLE: return text
    try:
        out = translator.translate(text)
        translate_cache[text] = out
        return out
    except Exception:
        return text

# ---------------------------------------------------------------------------
# Load and aggregate reviews
# ---------------------------------------------------------------------------
all_reviews = []
seen_text = set()

review_files = sorted(f for f in glob.glob(os.path.join(REVIEWS_DIR, '*.json'))
                      if 'summary' not in os.path.basename(f))

print(f'Loading {len(review_files)} review files...')
for rf in review_files:
    fname = os.path.basename(rf)
    m = re.match(r'^([B0-9A-Z]{10})-(\w+)\.json$', fname)
    if not m:
        print(f'  skip {fname} (filename pattern)')
        continue
    asin, segment = m.group(1), m.group(2)
    with open(rf, encoding='utf-8') as f: data = json.load(f)
    n_added = 0
    for r in data:
        text = (r.get('review') or '').strip()
        rating = r.get('rating')
        if not text or rating is None:
            continue
        # Dedupe by first 100 chars (catches repeated/cross-posted reviews)
        key = text[:100]
        if key in seen_text:
            continue
        seen_text.add(key)
        all_reviews.append({
            'asin': asin,
            'segment': segment,
            'r': int(rating),
            't': text,
            'title': (r.get('title') or '').strip(),
            'date': (r.get('date') or '').strip(),
        })
        n_added += 1
    print(f'  {fname}: {len(data)} -> {n_added} unique')

total = len(all_reviews)
print(f'\n{total} unique reviews aggregated.')

# ---------------------------------------------------------------------------
# Theme tagging
# ---------------------------------------------------------------------------
for rev in all_reviews:
    tags = []
    text_lower = rev['t'].lower()
    for tag, pattern in THEMES.items():
        if re.search(pattern, text_lower):
            tags.append(tag)
    rev['tags'] = tags

# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
star_dist = [0]*5
for r in all_reviews:
    if 1 <= r['r'] <= 5:
        star_dist[r['r']-1] += 1
avg_rating = sum((i+1)*star_dist[i] for i in range(5)) / total if total else 0

neg_reviews = [r for r in all_reviews if r['r'] <= 2]
pos_reviews = [r for r in all_reviews if r['r'] >= 4]
neg_total = max(len(neg_reviews), 1)
pos_total = max(len(pos_reviews), 1)

# ---------------------------------------------------------------------------
# Build topics: for each tag, count occurrences within neg/pos buckets,
# pick the most-frequent tags in each, build topic objects with quotes.
# ---------------------------------------------------------------------------
NEG_TAGS = ['no_effect','skin_irritation','recurrence','bad_smell','expensive','slow_results','sticky_greasy','packaging','spray_weak','unclear_use']
POS_TAGS = ['effective','fast_results','easy_use','skin_friendly','odorless','good_value','no_recurrence']

def get_quotes(reviews, tag, n=3, max_chars=180):
    matches = [(r['t'], r['asin'], r['segment'], r['r']) for r in reviews if tag in r['tags']]
    matches = matches[:n*3]  # take a few extra in case translation truncates
    out = []
    for text, asin, seg, rating in matches[:n]:
        snippet = text.strip().replace('\n', ' ')
        if len(snippet) > max_chars:
            snippet = snippet[:max_chars].rsplit(' ', 1)[0] + '...'
        en = translate(snippet)
        out.append('"' + en + '"')
    return out

def build_topics(reviews, tags, bucket_total, sort_neg_first=False):
    counts = Counter()
    for r in reviews:
        for t in r['tags']:
            if t in tags:
                counts[t] += 1
    topics = []
    for tag, cnt in counts.most_common():
        if cnt < 3:  # skip noise
            continue
        pct = round(100 * cnt / bucket_total, 1)
        topics.append({
            'label': THEME_LABELS[tag],
            'reason': TOPIC_REASONS[tag],
            'pct': f'{pct}%',
            'bullets': [
                f'{cnt} reviews mention this theme ({pct}% of {"negative" if sort_neg_first else "positive"} bucket).',
                'Cuts across multiple ASINs and both Cream and Spray segments.' if any(r['segment'] != reviews[0]['segment'] for r in reviews if tag in r['tags']) else 'Concentrated within a single segment.',
            ],
            'quotes': get_quotes(reviews, tag, 3),
        })
    return topics

print('\nBuilding negative topics...')
negative_topics = build_topics(neg_reviews, NEG_TAGS, neg_total, sort_neg_first=True)
print(f'  {len(negative_topics)} negative topics')

print('Building positive topics...')
positive_topics = build_topics(pos_reviews, POS_TAGS, pos_total)
print(f'  {len(positive_topics)} positive topics')

# Save translation cache after batch completes
if TRANS_AVAILABLE:
    save_cache(translate_cache)
    print(f'  translation cache: {len(translate_cache)} entries cached')

# ---------------------------------------------------------------------------
# Theme filters + tag styles
# ---------------------------------------------------------------------------
theme_filters = [{'value': '', 'label': 'All Themes'}]
for tag in list(POS_TAGS) + list(NEG_TAGS):
    theme_filters.append({'value': tag, 'label': THEME_LABELS[tag]})

# ---------------------------------------------------------------------------
# Reviews list for browser (translate review body to English)
# ---------------------------------------------------------------------------
print('\nTranslating reviews for browser (this may take a few minutes)...')
review_browser = []
for i, r in enumerate(all_reviews[:2000]):
    if i % 200 == 0 and i > 0:
        print(f'  {i}/{min(len(all_reviews), 2000)}')
        if TRANS_AVAILABLE: save_cache(translate_cache)
    body_en = translate(r['t']) if TRANS_AVAILABLE else r['t']
    title_en = translate(r['title']) if r['title'] and TRANS_AVAILABLE else r['title']
    review_browser.append({
        'r': r['r'],
        't': body_en,
        'title': title_en,
        'date': r['date'],
        'asin': r['asin'],
        'segment': r['segment'],
        'tags': r['tags'],
    })
if TRANS_AVAILABLE: save_cache(translate_cache)

# ---------------------------------------------------------------------------
# Build VOC_DATA
# ---------------------------------------------------------------------------
neg_count = star_dist[0] + star_dist[1]
pos_count = star_dist[3] + star_dist[4]

voc_data = {
    'totalReviews': total,
    'avgRating': round(avg_rating, 2),
    'starDist': star_dist,

    # AI placeholders — fill these via a separate AI pass on the corpus.
    'cpSummary': f'Customer profile based on {total} reviews across 8 ASINs (4 Cream, 4 Spray) on amazon.de. AI analysis pending — fill via update_voc.py / Claude pass.',
    'cpWho':    {'labels': [], 'pos': [], 'neg': []},
    'cpWhen':   {'labels': [], 'pos': [], 'neg': []},
    'cpWhere':  {'labels': [], 'pos': [], 'neg': []},
    'cpWhat':   {'labels': [], 'pos': [], 'neg': []},
    'usageScenarios':       [],
    'negativeInsights':     [],
    'positiveInsights':     [],
    'buyersMotivation':     [],
    'customerExpectations': [],

    # Deterministic — derived from the corpus
    'csSummary': f'Sentiment analysis from {total} reviews (DE machine-translated to EN for the browser). {pos_count} positive (4-5 star, {round(100*pos_count/total,1)}%), {neg_count} negative (1-2 star, {round(100*neg_count/total,1)}%). Avg rating {round(avg_rating,2)}.',
    'negativeTopics': negative_topics,
    'positiveTopics': positive_topics,
    'themeFilters':   theme_filters,
    'tagStyles':      TAG_STYLES,
    'reviews':        review_browser,
}

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
if os.path.exists(DASH_PATH):
    with open(DASH_PATH, encoding='utf-8') as f: dash = json.load(f)
else:
    dash = {}
dash.setdefault('baseTabs', {})['reviews'] = voc_data
with open(DASH_PATH, 'w', encoding='utf-8') as f:
    json.dump(dash, f, indent=2, ensure_ascii=False)

print(f'\nDone — VOC saved to dashboard.json')
print(f'  totalReviews: {total}, avgRating: {round(avg_rating,2)}, starDist: {star_dist}')
print(f'  negativeTopics: {len(negative_topics)}, positiveTopics: {len(positive_topics)}')
print(f'  reviews in browser: {len(review_browser)}')
print(f'  AI sections (cpWho/When/Where/What, usageScenarios, *Insights, motivations, expectations): empty placeholders — fill via Claude pass next.')
