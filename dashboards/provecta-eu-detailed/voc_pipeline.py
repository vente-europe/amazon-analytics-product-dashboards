"""
VOC pipeline for provecta-eu-detailed (ENGLISH output, no segments).

Two stages, per country CODE (DE/FR/IT/ES/UK):

  python voc_pipeline.py prep DE
      - reads raw reviews from reviews/DE/reviews.csv (marketplace,asin,title,date,rating,review)
      - computes EXACT stats over the FULL population (totalReviews, avgRating, starDist)
      - selects a representative sample (<=CAP, with a negatives floor) in ORIGINAL language
        (no machine translation - the analysis LLM reads DE/FR/IT/ES natively)
      - writes reviews/DE/_analysis_input.json  (stats + sample) for the LLM

  <LLM reads _analysis_input.json, writes reviews/DE/_qual.json>
      qualitative ENGLISH block matching the u-reviews-voc contract
      (cpSummary, cpWho/When/Where/What, usageScenarios, csSummary,
       negativeTopics, positiveTopics, negativeInsights, positiveInsights,
       buyersMotivation, customerExpectations; quotes translated to English)

  python voc_pipeline.py assemble DE
      - merges stats + _qual.json + the FULL review set (original language,
        deduped, multilingual regex-tagged) -> reviews/DE/voc.json
        (u-reviews-voc data contract; countryName/Code omitted - scopeBucket()
         injects them at render time)
"""
import csv, os, sys, json, re
sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
CAP = 120           # max reviews in the LLM analysis sample
NEG_FLOOR = 45      # negatives floor for the sample

# ── Multilingual theme keywords for the review BROWSER ──────────────────────
# The browser shows ALL reviews in their ORIGINAL language (no translation),
# so tags must match DE/FR/IT/ES/EN stems. id == pill label (shown as-is).
# Valid pill classes: pill-amber, pill-blue, pill-orange, pill-purple, pill-red.
MULTILINGUAL_THEMES = [
    ("Skuteczność", "pill-amber", ["wirkt","wirkung","hilft","geholfen","funktioniert","efficac","fonctionne","marche bien","funziona","eficaz","funciona","works","worked","effective","helped","did the job"]),
    ("Brak efektu / szkodniki wracają", "pill-red", ["wirkungslos","hilft nicht","nicht gewirkt","nutzlos","keine wirkung","zurück","ne fonctionne pas","inefficace","reviennent","sans effet","non funziona","inutile","tornano","nessun effetto","no funciona","inútil","inutil","vuelven","sin efecto","doesn't work","does not work","didn't work","not work","useless","no effect","still alive","came back","come back","waste of money"]),
    ("Szybkość działania", "pill-blue", ["sofort","schnell","innerhalb","rapide","vite","immédiat","immediat","subito","veloce","rapido","immediato","rápido","inmediato","fast","quick","instant","within minutes","overnight","right away"]),
    ("Zapach", "pill-orange", ["geruch","riecht","stinkt","gestank","geruchlos","odeur","sent mauvais","pue","inodore","odore","puzza","inodore","olor","huele","apesta","smell","odour","odor","stink","scent","fragrance"]),
    ("Bezpieczeństwo (dzieci/zwierzęta)", "pill-red", ["haustier","hund","katze","kinder","giftig","ungiftig","sicher","animaux","chien","chat","enfant","toxique","animali","cane","gatto","bambini","tossico","mascota","perro","gato","niño","nino","tóxico","toxico","pet","dog","cat","child","kids","toxic","poison","safe"]),
    ("Aplikacja / wygoda użycia", "pill-amber", ["anwendung","sprühkopf","spruhkopf","düse","duse","einfach anzuwenden","dosierung","application","pulvérisateur","pulverisateur","buse","facile à utiliser","applicazione","erogatore","facile da usare","aplicación","aplicacion","fácil de usar","facil de usar","easy to use","easy to apply","nozzle","spray head","trigger","instructions","apply"]),
    ("Plamy / osad", "pill-purple", ["flecken","rückstände","ruckstande","klebrig","schmierig","taches","résidus","residus","collant","macchie","residui","appiccicoso","manchas","residuos","pegajoso","stain","residue","sticky","greasy","marks"]),
    ("Opakowanie / wycieki", "pill-purple", ["verpackung","ausgelaufen","undicht","flasche","kaputt","emballage","fuite","coulé","coule","cassé","confezione","perdita","bottiglia","rotto","envase","fuga","botella","roto","packaging","leak","leaked","bottle","broken","damaged","arrived"]),
    ("Cena / wartość", "pill-orange", ["preis","teuer","günstig","gunstig","preiswert","prix","cher","pas cher","prezzo","costoso","caro","economico","precio","barato","price","expensive","cheap","value for money","overpriced","worth"]),
    ("Mrówki", "pill-blue", ["ameise","fourmi","formica","formiche","hormiga","ants","ant nest","anthill"]),
    ("Pluskwy / roztocza", "pill-red", ["bettwanze","wanzen","milbe","punaise","acarien","cimice","cimici","acaro","chinche","ácaro","bed bug","bedbug","bed-bug","dust mite","mites"]),
    ("Muchy / mole / osy", "pill-blue", ["fliege","mücke","mucke","motte","wespe","hornisse","mouche","moustique","guêpe","guepe","frelon","mosca","tarma","vespa","calabrone","zanzara","polilla","avispa","mosquito","flies","fly","moth","wasp","hornet","gnat","midge"]),
    ("Pchły / kleszcze", "pill-amber", ["floh","flöhe","flohe","zecke","puce","tique","pulce","pulci","zecca","pulga","garrapata","flea","tick"]),
    ("Karaluchy / owady biegające", "pill-purple", ["schabe","kakerlake","silberfisch","cafard","blatte","poisson d'argent","scarafagg","blatta","pesciolino","cucaracha","cochinilla","roach","cockroach","silverfish","crawling insect","spider","spinne","araignée","ragno","araña","arana"]),
]


def tag_all(raw):
    """Tag EVERY raw review (original language) with multilingual theme ids.
    Dedups exact (rating, text) repeats. Returns browser contract: [{r, t, tags[]}]."""
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


def load_raw(code):
    """reviews/{CODE}/reviews.csv -> [{r, src}]. UTF-8 BOM, multiline quoted
    review fields, rating may be '1' or '5.0' (UK)."""
    path = os.path.join(BASE, 'reviews', code, 'reviews.csv')
    out = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            try:
                rating = int(round(float(r.get('rating') or 0)))
            except Exception:
                rating = 0
            txt = (r.get('review') or '').strip()
            title = (r.get('title') or '').strip()
            full = (title + '. ' + txt).strip('. ').strip() if title else txt
            if rating in (1, 2, 3, 4, 5) and full:
                out.append({'r': rating, 'src': full})
    return out


def stats(revs):
    n = len(revs)
    dist = [0, 0, 0, 0, 0]
    for x in revs:
        dist[x['r'] - 1] += 1
    avg = round(sum(x['r'] for x in revs) / n, 2) if n else 0
    return n, avg, dist


def pick_sample(revs):
    neg = sorted([x for x in revs if x['r'] <= 2], key=lambda x: len(x['src']), reverse=True)
    pos = {s: sorted([x for x in revs if x['r'] == s], key=lambda x: len(x['src']), reverse=True) for s in (3, 4, 5)}
    neg_take = min(len(neg), NEG_FLOOR)
    chosen = neg[:neg_take]
    remaining = CAP - len(chosen)
    idx = {3: 0, 4: 0, 5: 0}
    order = [5, 4, 3]
    while remaining > 0 and any(idx[s] < len(pos[s]) for s in order):
        for s in order:
            if remaining <= 0:
                break
            if idx[s] < len(pos[s]):
                chosen.append(pos[s][idx[s]]); idx[s] += 1; remaining -= 1
    chosen.sort(key=lambda x: x['r'])
    return chosen


# ---- stage: prep -----------------------------------------------------------
def prep(code):
    revs = load_raw(code)
    if not revs:
        print(f'  no reviews for {code}'); return
    n, avg, dist = stats(revs)
    sample = pick_sample(revs)
    outdir = os.path.join(BASE, 'reviews', code)
    payload = {
        'code': code,
        'totalReviews': n, 'avgRating': avg, 'starDist': dist,
        'sampleSize': len(sample),
        'sample': [{'r': x['r'], 't': x['src'][:2500]} for x in sample],
    }
    json.dump(payload, open(os.path.join(outdir, '_analysis_input.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'  {code}: N={n} avg={avg} dist={dist} sample={len(sample)} -> _analysis_input.json')


# ---- stage: assemble -------------------------------------------------------
def _numv(v):
    s = re.sub(r'[^\d.,-]', '', str(v or '')).replace(',', '')
    try:
        return float(s)
    except Exception:
        return 0.0


def xray_headline(code):
    """Whole-market rating headline from X-Ray (Amazon-displayed averages),
    weighted by review count. Returns (avg, review_count, product_count)."""
    path = os.path.join(BASE, 'data', 'x-ray', f'Provecta-{code}.csv')
    wsum = 0.0; rc = 0.0; prod = 0
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            rating = _numv(r.get('Ratings')); count = _numv(r.get('Review Count'))
            if rating > 0:
                prod += 1
                if count > 0:
                    wsum += rating * count; rc += count
    if prod == 0:
        return None, None, None
    avg = round(wsum / rc, 2) if rc else 0
    return avg, int(rc), prod


def assemble(code):
    d = os.path.join(BASE, 'reviews', code)
    qual = json.load(open(os.path.join(d, '_qual.json'), encoding='utf-8'))
    qual.pop('themeKeywords', None)
    avg, rc, prod = xray_headline(code)
    if avg is None:
        avg = 0; prod = 0

    # ALL reviews, original language, deduped + multilingual-tagged (no translation).
    reviews = tag_all(load_raw(code))

    voc = {
        'avgRating': avg,               # X-Ray weighted avg rating (headline)
        'productCount': prod,           # products in this market's X-Ray
        'totalReviews': len(reviews),   # == ALL analyzed reviews
        # starDist omitted - scraped ratings unrepresentative, bar hidden
    }
    voc.update(qual)  # ENGLISH qualitative block from _qual.json
    voc['themeFilters'] = [{'id': t[0], 'label': t[0]} for t in MULTILINGUAL_THEMES]
    voc['tagStyles'] = {t[0]: t[1] for t in MULTILINGUAL_THEMES}
    voc['reviews'] = reviews
    json.dump(voc, open(os.path.join(d, 'voc.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    tagged = sum(1 for r in reviews if r['tags'])
    print(f'  {code}: voc.json ({len(reviews)} reviews (ALL, original lang; {tagged} tagged), avg {avg} from X-Ray, {prod} products)')


if __name__ == '__main__':
    stage, code = sys.argv[1], sys.argv[2]
    (prep if stage == 'prep' else assemble)(code)
