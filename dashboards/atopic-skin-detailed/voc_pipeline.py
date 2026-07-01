"""
VOC pipeline for atopic-skin-detailed (Polish output).

Two stages, per bucket (country CODE x segment SEG):

  python voc_pipeline.py prep DE Cream
      - reads raw reviews from ../dermo-products/reviews/DE/Cream/*.json (German/FR/IT/ES)
      - computes EXACT stats over the FULL population (totalReviews, avgRating, starDist)
      - selects a representative sample (<=CAP, with a negatives floor)
      - machine-translates the sample text to Polish (deep_translator/Google, cached)
      - writes reviews/DE/Cream/_analysis_input.json  (stats + PL sample) for the LLM

  <LLM reads _analysis_input.json, writes reviews/DE/Cream/_qual.json>
      qualitative Polish block (see SCHEMA note at bottom) + themeKeywords for tagging

  python voc_pipeline.py assemble DE Cream
      - merges stats + _qual.json + regex-tagged PL sample -> reviews/DE/Cream/voc.json
        (matches the u-reviews-voc data contract; countryName/Code/segmentName omitted
         because the dashboard's scopeBucket() injects them at render time)

Idempotent: translation cache persists in reviews/_tr_cache.json.
"""
import csv, os, sys, json, re, glob, time
sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(BASE, '..', 'atopic-skin-topline', 'reviews')   # raw reviews live here
CACHE = os.path.join(BASE, 'reviews', '_tr_cache.json')
CAP = 120           # max reviews in the browsable/analyzed sample
NEG_FLOOR = 45      # try to include at least this many 1-2 star reviews

def load_raw(code, seg):
    out = []
    for f in glob.glob(os.path.join(SRC, code, seg, '*.json')):
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d, list):
            for r in d:
                try:
                    rating = int(round(float(r.get('rating') or 0)))
                except Exception:
                    rating = 0
                txt = (r.get('review') or '').strip()
                title = (r.get('title') or '').strip()
                full = (title + '. ' + txt).strip('. ').strip() if title else txt
                if rating in (1,2,3,4,5) and full:
                    out.append({'r': rating, 'src': full})
    return out

def stats(revs):
    n = len(revs)
    dist = [0,0,0,0,0]
    for x in revs:
        dist[x['r']-1] += 1
    avg = round(sum(x['r'] for x in revs)/n, 2) if n else 0
    return n, avg, dist

def pick_sample(revs):
    neg = sorted([x for x in revs if x['r'] <= 2], key=lambda x: len(x['src']), reverse=True)
    pos = {s: sorted([x for x in revs if x['r'] == s], key=lambda x: len(x['src']), reverse=True) for s in (3,4,5)}
    neg_take = min(len(neg), NEG_FLOOR)
    chosen = neg[:neg_take]
    remaining = CAP - len(chosen)
    # round-robin across 3,4,5 star (longest first) to fill remaining
    idx = {3:0,4:0,5:0}
    order = [5,4,3]
    while remaining > 0 and any(idx[s] < len(pos[s]) for s in order):
        for s in order:
            if remaining <= 0: break
            if idx[s] < len(pos[s]):
                chosen.append(pos[s][idx[s]]); idx[s] += 1; remaining -= 1
    # stable order: negatives first (most useful), then by star desc
    chosen.sort(key=lambda x: x['r'])
    return chosen

# ---- translation -----------------------------------------------------------
def get_translator():
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source='auto', target='pl')

def translate_sample(sample):
    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE, encoding='utf-8'))
    tr = None
    todo = [x for x in sample if x['src'] not in cache]
    print(f'  to translate: {len(todo)} (cached: {len(sample)-len(todo)})')
    for i, x in enumerate(todo, 1):
        s = x['src'][:4800]
        try:
            if tr is None:
                tr = get_translator()
            out = tr.translate(s) or s
        except Exception as e:
            out = s  # fallback: keep original
        cache[x['src']] = out
        if i % 20 == 0:
            print(f'    {i}/{len(todo)}')
            json.dump(cache, open(CACHE,'w',encoding='utf-8'), ensure_ascii=False)
    json.dump(cache, open(CACHE,'w',encoding='utf-8'), ensure_ascii=False)
    for x in sample:
        x['pl'] = cache.get(x['src'], x['src'])
    return sample

# ---- stage: prep -----------------------------------------------------------
def prep(code, seg):
    revs = load_raw(code, seg)
    if not revs:
        print(f'  no reviews for {code}/{seg}'); return
    n, avg, dist = stats(revs)
    sample = pick_sample(revs)
    sample = translate_sample(sample)
    outdir = os.path.join(BASE, 'reviews', code, seg)
    os.makedirs(outdir, exist_ok=True)
    payload = {
        'code': code, 'segment': seg,
        'totalReviews': n, 'avgRating': avg, 'starDist': dist,
        'sampleSize': len(sample),
        'sample': [{'r': x['r'], 't': x['pl']} for x in sample],
    }
    json.dump(payload, open(os.path.join(outdir,'_analysis_input.json'),'w',encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'  {code}/{seg}: N={n} avg={avg} dist={dist} sample={len(sample)} -> _analysis_input.json')

# ---- stage: assemble -------------------------------------------------------
def tag_reviews(sample, theme_keywords):
    pats = {tid: re.compile('|'.join(re.escape(k) for k in kws), re.I) for tid, kws in theme_keywords.items() if kws}
    out = []
    for x in sample:
        tags = [tid for tid, p in pats.items() if p.search(x['t'])]
        out.append({'r': x['r'], 't': x['t'], 'tags': tags[:4]})
    return out

def _numv(v):
    s = re.sub(r'[^\d.,-]', '', str(v or '')).replace(',', '')
    try: return float(s)
    except: return 0.0

def xray_headline(code, seg):
    """Market x segment rating headline from X-Ray (Amazon-displayed averages).
    Scraped review ratings are unreliable (critical-skewed), so the headline avg +
    review count come from X-Ray, computed over ALL products in this segment/market
    (weighted by review count). Returns (avg, review_count, product_count), or
    (None, None, None) if the segment is absent from this market's X-Ray (e.g. FR/Oil),
    so the caller can preserve any previously-computed headline instead of zeroing it."""
    path = os.path.join(BASE, 'data', 'x-ray', code, f'Dermo-Products-{code}.csv')
    wsum = 0.0; rc = 0.0; prod = 0
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if (r.get('Segment') or '').strip() != seg:
                continue
            rating = _numv(r.get('Ratings')); count = _numv(r.get('Review Count'))
            if rating > 0:
                prod += 1
                if count > 0:
                    wsum += rating * count; rc += count
    if prod == 0:
        return None, None, None
    avg = round(wsum / rc, 2) if rc else 0
    return avg, int(rc), prod

def assemble(code, seg):
    d = os.path.join(BASE, 'reviews', code, seg)
    ai = json.load(open(os.path.join(d,'_analysis_input.json'), encoding='utf-8'))
    qual = json.load(open(os.path.join(d,'_qual.json'), encoding='utf-8'))
    theme_kw = qual.pop('themeKeywords', {})
    avg, rc, prod = xray_headline(code, seg)
    if avg is None:  # segment absent from this market's X-Ray — keep any prior headline
        prev = {}
        vp = os.path.join(d, 'voc.json')
        if os.path.exists(vp):
            prev = json.load(open(vp, encoding='utf-8'))
        avg = prev.get('avgRating', 0); rc = prev.get('totalReviews', 0); prod = prev.get('productCount', 0)
    voc = {
        'totalReviews': rc,        # X-Ray real total review count (headline)
        'avgRating': avg,          # X-Ray weighted average rating (headline)
        'productCount': prod,      # number of products in the segment/market
        # starDist intentionally omitted — scraped ratings unreliable, bar hidden
    }
    voc.update(qual)  # cpSummary, cp*, usageScenarios, csSummary, topics, insights, motivation, expectations, themeFilters, tagStyles
    voc['reviews'] = tag_reviews(ai['sample'], theme_kw)
    json.dump(voc, open(os.path.join(d,'voc.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'  {code}/{seg}: voc.json ({len(voc["reviews"])} sample / {rc} X-Ray reviews, avg {avg}★, {prod} produktów, {len(voc.get("themeFilters",[]))} themes)')

if __name__ == '__main__':
    stage, code, seg = sys.argv[1], sys.argv[2], sys.argv[3]
    (prep if stage=='prep' else assemble)(code, seg)
