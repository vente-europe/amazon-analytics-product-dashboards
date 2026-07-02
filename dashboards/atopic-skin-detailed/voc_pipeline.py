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
SRC  = os.path.join(BASE, 'reviews')   # raw reviews live here (moved from atopic-skin-topline)
CACHE = os.path.join(BASE, 'reviews', '_tr_cache.json')
CAP = 120           # (legacy) max reviews in the translated sample — no longer used by assemble
NEG_FLOOR = 45      # (legacy) negatives floor for the old sample

# ── Multilingual theme keywords for the review BROWSER ──────────────────────
# The browser now shows ALL reviews in their ORIGINAL language (no translation),
# so tags must match DE/FR/IT/ES/EN (+PL) stems. id == pill label (shown as-is).
# Valid pill classes: pill-amber, pill-blue, pill-orange, pill-purple, pill-red.
MULTILINGUAL_THEMES = [
    ("Nawilżenie", "pill-blue",   ["feuchtig","hydrat","idratant","hidratant","moistur","trocken","sécher","secch","seca","dry skin","nawil","sucho","sucha"]),
    ("Świąd", "pill-red",         ["juckreiz","jucken","démangea","demangea","prurit","picazón","picor","itch","świąd","swiad","swędz","swedz"]),
    ("Skóra atopowa / egzema", "pill-purple", ["atopisch","neurodermit","atopique","eczéma","eczema","atopica","atópic","atopic","dermatit","psorias","łuszcz"]),
    ("Kojenie / podrażnienie", "pill-amber", ["beruhig","reizung","gereizt","apais","irrit","lenit","calm","sooth","rossore","enrojec","redness","koj","łagodz","lagodz","podrażn","podrazn"]),
    ("Zapach", "pill-orange",     ["geruch","duft","parfum","odeur","odor","olor","smell","scent","fragranc","zapach","pachn","wonn"]),
    ("Wchłanianie / tłustość", "pill-blue", ["zieht ein","fettig","fettend","absorb","gras","grasso","grassa","grasa","greasy","sticky","klebrig","appiccic","wchłan","wchlan","tłust","tlust","lepk"]),
    ("Konsystencja", "pill-amber",["konsistenz","textur","texture","consistenc","cremig","creamy","crema","cremos","dickflüssig","thick","gęst","gest","konsystenc"]),
    ("Cena / pojemność", "pill-orange", ["preis","teuer","günstig","gunstig","prix","cher","prezzo","costoso","precio","caro","price","expensive","cheap","value for money","cena","drog","tani","pojemn"]),
    ("Opakowanie / pompka", "pill-purple", ["verpackung","pumpe","spender","emballage","pompe","confezione","dosatore","erogatore","envase","dosificador","packaging","pump","bottle","tube","opakow","pompk","plomb","dozownik","nakrętk"]),
    ("Skład", "pill-red",         ["inhaltsstoff","paraben","duftstoff","zusammensetzung","composition","ingrédient","ingredienti","ingrediente","ingredient","silicon","alcohol","alkohol","skład","sklad"]),
    ("Dla dzieci / niemowląt", "pill-blue", ["baby","kinder","säugl","saugl","bébé","bebe","enfant","nourrisson","bambin","neonat","bebé","niño","nino","child","infant","dzieci","niemowl","dziecko"]),
    ("Skuteczność / efekty", "pill-amber", ["wirkung","wirkt","hilft","geholfen","efficac","aiuta","funziona","eficaz","ayuda","funciona","works","helped","effective","result","skutecz","pomaga","pomogł","efekt","działa","dziala"]),
    ("Alergia / reakcja", "pill-red", ["allerg","unverträg","unvertrag","réaction","reaction","reazione","reacción","reaccion","rash","ausschlag","pickel","brenn","alerg","uczul","reakcj","wysyp"]),
]


def tag_all(raw):
    """Tag EVERY raw review (original language) with multilingual theme ids.
    Dedups exact (rating, text) repeats across per-ASIN files. Returns the
    browser contract: [{r, t(original text), tags[]}]."""
    pats = [(tid, [k.lower() for k in kws]) for tid, cls, kws in MULTILINGUAL_THEMES]
    seen = set()
    out = []
    for x in raw:
        txt = x['src']
        key = (x['r'], txt)
        if key in seen:
            continue
        seen.add(key)
        low = txt.lower()
        tags = [tid for tid, kws in pats if any(k in low for k in kws)][:4]
        out.append({'r': x['r'], 't': txt, 'tags': tags})
    return out

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
    qual = json.load(open(os.path.join(d, '_qual.json'), encoding='utf-8'))
    qual.pop('themeKeywords', None)
    avg, rc, prod = xray_headline(code, seg)          # avg rating from X-Ray (reliable); rc no longer shown
    if avg is None:                                    # segment absent from X-Ray — keep any prior headline
        prev = {}
        vp = os.path.join(d, 'voc.json')
        if os.path.exists(vp):
            prev = json.load(open(vp, encoding='utf-8'))
        avg = prev.get('avgRating', 0); prod = prev.get('productCount', 0)

    # ALL reviews, original language, deduped + multilingual-tagged (no translation).
    reviews = tag_all(load_raw(code, seg))

    voc = {
        'avgRating': avg,               # X-Ray weighted avg rating (headline)
        'productCount': prod,           # products in the segment/market
        'totalReviews': len(reviews),   # now == ALL analyzed reviews
        # starDist omitted — scraped ratings unreliable, bar hidden
    }
    voc.update(qual)  # cpSummary, cp*, usageScenarios, topics, insights, motivation, expectations (Polish, sample-read)
    # Browser dropdown + pill styles use the multilingual theme set (override any from _qual.json)
    voc['themeFilters'] = [{'id': t[0], 'label': t[0]} for t in MULTILINGUAL_THEMES]
    voc['tagStyles'] = {t[0]: t[1] for t in MULTILINGUAL_THEMES}
    voc['reviews'] = reviews
    json.dump(voc, open(os.path.join(d, 'voc.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    tagged = sum(1 for r in reviews if r['tags'])
    print(f'  {code}/{seg}: voc.json ({len(reviews)} reviews (ALL, original lang; {tagged} tagged), avg {avg}★ X-Ray, {prod} produktów)')

if __name__ == '__main__':
    stage, code, seg = sys.argv[1], sys.argv[2], sys.argv[3]
    (prep if stage=='prep' else assemble)(code, seg)
