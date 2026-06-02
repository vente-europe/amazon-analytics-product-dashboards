"""Extract per-segment review subsets + stratified samples for Gemini VOC analysis.

Writes:
  _voc_work/lure_all.json         — all 1,644 Lure reviews
  _voc_work/electric_all.json     — all 1,200 Electric Traps reviews
  _voc_work/lure_sample.json      — stratified ~200-review sample for Gemini
  _voc_work/electric_sample.json  — stratified ~200-review sample for Gemini
"""
import pandas as pd, json, os, glob, random
from collections import defaultdict

random.seed(20260524)

REVIEWS_DIR = 'reviews'
WORK_DIR = '_voc_work'
os.makedirs(WORK_DIR, exist_ok=True)

VOC_SEGMENTS = {'Lure', 'Electric Traps'}
SAMPLE_SIZE = 200

SEGMENT_MAP = {
    'electric traps': 'Electric Traps', 'sticky traps': 'Sticky Traps',
    'sticky trap': 'Sticky Traps', 'lure': 'Lure', 'passive attractor': 'Passive Attractor',
}
def norm_segment(v):
    if pd.isna(v) or str(v).strip() == '': return None
    return SEGMENT_MAP.get(str(v).strip().lower())

# May X-Ray (primary)
df = pd.read_csv('data/x-ray/merged-may-segmented.csv', encoding='utf-8-sig')
asin_col = next((c for c in df.columns if c.strip().lower() == 'asin'), None)
type_col = next((c for c in df.columns if c.strip().lower() in ('type', 'segment')), None)
brand_col = next((c for c in df.columns if c.strip().lower() == 'brand'), None)

asin_seg, asin_brand = {}, {}
for _, r in df.iterrows():
    s = norm_segment(r.get(type_col))
    if s: asin_seg[r[asin_col]] = s
    if pd.notna(r.get(brand_col)):
        bv = str(r[brand_col]).strip()
        if bv: asin_brand[r[asin_col]] = bv

# Feb fallback
try:
    feb_df = pd.read_csv('data/x-ray/Fruit-Flies-US-new-merged-data.csv', encoding='utf-8-sig')
    feb_asin = next((c for c in feb_df.columns if c.strip().lower() == 'asin'), None)
    feb_type = next((c for c in feb_df.columns if c.strip().lower() == 'type'), None)
    feb_brand = next((c for c in feb_df.columns if c.strip().lower() == 'brand'), None)
    for _, r in feb_df.iterrows():
        a = r.get(feb_asin)
        if pd.isna(a): continue
        if a not in asin_seg and feb_type:
            s = norm_segment(r.get(feb_type))
            if s: asin_seg[a] = s
        if a not in asin_brand and feb_brand and pd.notna(r.get(feb_brand)):
            bv = str(r[feb_brand]).strip()
            if bv: asin_brand[a] = bv
except FileNotFoundError:
    pass

# Load + dedup
seen, raw = set(), []
for path in sorted(glob.glob(os.path.join(REVIEWS_DIR, 'dataset_amazon-reviews-scraper_*.json'))):
    try:
        with open(path, encoding='utf-8') as fh: arr = json.load(fh)
    except: continue
    if not isinstance(arr, list): continue
    for r in arr:
        a = r.get('productAsin')
        if not a: continue
        url = r.get('reviewUrl') or ''
        key = (a, url) if url else (a, r.get('reviewTitle', '') + '|' + str(r.get('date', '')))
        if key in seen: continue
        seen.add(key)
        seg = asin_seg.get(a)
        if seg not in VOC_SEGMENTS: continue
        rating = r.get('ratingScore')
        try: rating = int(rating)
        except: rating = None
        if rating is None or rating < 1 or rating > 5: continue
        raw.append({
            'asin': a, 'segment': seg, 'brand': asin_brand.get(a, 'Unknown'),
            'rating': rating, 'date': (r.get('date') or '')[:10],
            'title': r.get('reviewTitle') or '', 'body': r.get('reviewDescription') or '',
        })

# --- Positive-review supplement (us-fruitfly-positive-2026-05-31) ---
# Balances the negative-only scrape with the 2026-05-31 positive pull.
# Gated to ASINs ALREADY present in the Lure/Electric pools — the 17 unmatched
# ASINs (Sticky/Passive/off-X-Ray) are intentionally ignored (decision 2026-06-01).
import re as _re
POSITIVE_DIR = os.path.join(REVIEWS_DIR, 'us-fruitfly-positive-2026-05-31')
pool_asin_seg = {r['asin']: r['segment'] for r in raw}  # asin -> Lure / Electric Traps
_MONTHS = {m: i for i, m in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December'], 1)}

def _parse_pos_date(s):
    m = _re.search(r'([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})', s or '')
    if not m:
        return ''
    mon = _MONTHS.get(m.group(1))
    if not mon:
        return ''
    return f'{int(m.group(3)):04d}-{mon:02d}-{int(m.group(2)):02d}'

pos_added = 0
if os.path.isdir(POSITIVE_DIR):
    for asin in sorted(os.listdir(POSITIVE_DIR)):
        seg = pool_asin_seg.get(asin)
        if seg not in VOC_SEGMENTS:            # skip the 17 ASINs not in existing pools
            continue
        rpath = os.path.join(POSITIVE_DIR, asin, 'reviews.json')
        if not os.path.isfile(rpath):
            continue
        with open(rpath, encoding='utf-8') as fh:
            arr = json.load(fh)
        if not isinstance(arr, list):
            continue
        for r in arr:
            try:
                rating = int(r.get('rating'))
            except (TypeError, ValueError):
                continue
            if rating < 1 or rating > 5:
                continue
            title = (r.get('title') or '').strip()
            body = (r.get('review') or r.get('body') or '').strip()
            key = (asin, 'pos|' + (title + '|' + str(r.get('date', '')))[:120])
            if key in seen:
                continue
            seen.add(key)
            raw.append({
                'asin': asin, 'segment': seg, 'brand': asin_brand.get(asin, 'Unknown'),
                'rating': rating, 'date': _parse_pos_date(r.get('date')),
                'title': title, 'body': body,
            })
            pos_added += 1
print(f'positive supplement: +{pos_added} reviews across pool ASINs')

# --- Aggregate Terro / HOT SHOT supplement (terro_reviews.json + hs_reviews.json) ---
# These legacy aggregate files hold {stars, review} only (no ASIN/title). Both brands
# are Lure-only, so every review is assigned to the Lure segment. Deduplicated by
# normalized review text against the existing pool (and within themselves) so the
# ~238 reviews already captured via the dataset scrape are NOT double-counted.
def _norm_body(t):
    # FULL normalized text (not truncated) — an 80-char prefix wrongly merged distinct
    # reviews that share an opening sentence, dropping ~57 genuine Terro/HS reviews.
    return _re.sub(r'\s+', ' ', (t or '').strip().lower())

_existing_bodies = {_norm_body(r['body']) for r in raw}
agg_added = 0
for fname, brand in [('terro_reviews.json', 'Terro'), ('hs_reviews.json', 'HOT SHOT')]:
    p = os.path.join(REVIEWS_DIR, fname)
    if not os.path.exists(p):
        continue
    with open(p, encoding='utf-8') as fh:
        data = json.load(fh)
    lst = data.get('reviews', data) if isinstance(data, dict) else data
    for r in lst:
        body = (r.get('review') or '').strip()
        if not body:
            continue
        try:
            rating = int(r.get('stars'))
        except (TypeError, ValueError):
            continue
        if rating < 1 or rating > 5:
            continue
        nb = _norm_body(body)
        if nb in _existing_bodies:          # already in pool (dataset) or duplicate within agg
            continue
        _existing_bodies.add(nb)
        raw.append({
            'asin': '', 'segment': 'Lure', 'brand': brand,
            'rating': rating, 'date': '', 'title': '', 'body': body,
        })
        agg_added += 1
print(f'aggregate Terro/HOT SHOT supplement: +{agg_added} Lure reviews')


def stratified_sample(bucket, k):
    """Sample k reviews, balancing by (brand, rating) buckets."""
    if len(bucket) <= k:
        return list(bucket)
    by_bucket = defaultdict(list)
    for r in bucket:
        by_bucket[(r['brand'], r['rating'])].append(r)
    n_buckets = len(by_bucket)
    per = max(1, k // n_buckets)
    sample = []
    for key, items in by_bucket.items():
        random.shuffle(items)
        sample.extend(items[:per])
    # Top up randomly if we're short
    if len(sample) < k:
        extras = [r for r in bucket if r not in sample]
        random.shuffle(extras)
        sample.extend(extras[:k - len(sample)])
    # Trim if over
    if len(sample) > k:
        random.shuffle(sample)
        sample = sample[:k]
    return sample

for seg in ['Lure', 'Electric Traps']:
    bucket = [r for r in raw if r['segment'] == seg]
    seg_slug = 'lure' if seg == 'Lure' else 'electric'
    with open(os.path.join(WORK_DIR, f'{seg_slug}_all.json'), 'w', encoding='utf-8') as f:
        json.dump(bucket, f, ensure_ascii=False)
    sample = stratified_sample(bucket, SAMPLE_SIZE)
    # Strip to fields Gemini needs (saves tokens)
    sample_min = [{'asin': r['asin'], 'brand': r['brand'], 'rating': r['rating'],
                   'title': r['title'], 'body': r['body']} for r in sample]
    with open(os.path.join(WORK_DIR, f'{seg_slug}_sample.json'), 'w', encoding='utf-8') as f:
        json.dump(sample_min, f, ensure_ascii=False, indent=1)
    print(f'{seg}: full={len(bucket)} sample={len(sample)}')
