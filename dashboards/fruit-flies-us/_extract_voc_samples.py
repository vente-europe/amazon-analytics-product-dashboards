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
