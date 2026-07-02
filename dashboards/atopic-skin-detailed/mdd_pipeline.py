"""
Marketing Deep-Dive pipeline for atopic-skin-detailed (Polish output).

Deterministic (no LLM): builds mdd-{slug}.json per bucket from competitor listings.

  python mdd_pipeline.py DE Cream        # one bucket
  python mdd_pipeline.py ALL             # every country x segment that has listings

For each bucket:
  - competitor pool = X-Ray ASINs whose Segment == SEG (fallback: scraped review-bucket
    ASINs) that also have a listing JSON; ranked by ASIN Revenue (30d), top N.
  - listing JSON: ../dermo-products/data/competitor-listings/{CODE}/raw/{ASIN}.json
    (title, brand, bullet_points, description, images[{variant,url}])
  - claims tagged by multilingual regex over title+bullets+description (DE/FR/IT/ES/EN).
  - VOC gap uses local voc.json negativeTopics (Polish) matched to themes via PL keywords.
  - writes data/competitor-listings/{CODE}/mdd-{slug}.json (u-marketing-deep-dive contract).

All human-readable labels/narrative in POLISH; numbers derived from data.
"""
import csv, os, sys, json, re, glob
sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(BASE, '..', 'atopic-skin-topline')
TOP_N = 12
MARKETPLACE = {'DE':'amazon.de','FR':'amazon.fr','IT':'amazon.it','ES':'amazon.es'}
COUNTRY_PL  = {'DE':'Niemcy','FR':'Francja','IT':'Włochy','ES':'Hiszpania'}

# ── Claim themes: id, Polish label, and keyword stems.
#    `kw` = local-language + English stems matched against the LISTING copy.
#    `pl` = Polish stems matched against VOC negativeTopics for the gap analysis. ──
THEMES = [
    ("nawilzenie",   "Nawilżenie",              ["feuchtig","hydrat","idratant","hidratant","moistur","nawil"],                         ["nawil","sucho","sucha","suchej"]),
    ("skora_atopowa","Skóra atopowa / egzema",  ["atopisch","neurodermit","atopique","eczéma","eczema","atopica","atópic","atopic"],   ["atopow","egzem","azs"]),
    ("kojacy",       "Kojący / łagodzący",      ["beruhig","apais","lenit","calmant","calm","soothe","sooth"],                         ["koj","łagodz","lagodz","podrażn","podrazn"]),
    ("swiad",        "Redukcja świądu",         ["juckreiz","jucken","démangeais","demangeais","prurit","picazón","picor","itch"],     ["świąd","swiad","swędz","swedz"]),
    ("bariera",      "Odbudowa bariery",        ["hautbarriere","barriere","barrière","barriera","barrera","barrier"],                 ["barier"]),
    ("bez_zapachu",  "Bez zapachu / perfum",    ["parfümfrei","ohne duft","sans parfum","senza profum","sin perfum","fragrance free","unscented","fragrance-free"], ["zapach","perfum","wonn","pachn"]),
    ("dla_dzieci",   "Dla dzieci / niemowląt",  ["baby","kinder","säugl","saugl","bébé","bebe","enfant","nourrisson","bambin","neonat","bebé","niños","ninos"], ["dzieci","niemowl","dziecko"]),
    ("hipoalergiczny","Hipoalergiczny",         ["hypoallergen","hypoallergénique","hypoallergenique","ipoallergenic","hipoalerg","hypoallergenic"], ["hipoalerg","alerg","uczul"]),
    ("dermatologiczny","Dermatologicznie testowany",["dermatologisch","dermatolog","dermatológ","dermatologically"],                 ["dermatolog"]),
    ("bez_dodatkow", "Bez parabenów / SLS",     ["parabenfrei","ohne paraben","sans paraben","senza paraben","sin paraben","paraben free","paraben-free","sls-frei","sans sls","sin sls","sulfate free"], ["paraben","sls","siarcz"]),
    ("naturalny",    "Naturalny / wegański",    ["natürlich","naturlich","vegan","naturel","naturale","natural","bio","organic","biologique","ecológic"], ["natural","wegań","wegan","bio"]),
    ("wchlanianie",  "Szybkie wchłanianie",     ["zieht schnell ein","zieht ein","absorb","absorption","assorb","absor","non gras","non-greasy","nicht fettend"], ["wchłan","wchlan","tłust","tlust","lepk"]),
    ("odzywczy",     "Odżywczy / regenerujący", ["pflege","nährend","nahrend","regener","nourriss","nutriente","nutritiv","nourish","repair","répar"], ["odżyw","odzyw","regener","nawierzchni"]),
    ("cena_pojemnosc","Ekonomiczny / duża pojemność",["preiswert","günstig","gunstig","économique","economico","económic","value","großpackung","big size","ml","g "], ["cena","pojemn","tani","drog","opłac"]),
]

def numv(v):
    s = re.sub(r'[^\d.,-]', '', str(v or '')).replace(',', '')
    try: return float(s)
    except: return 0.0

def load_xray(code):
    rows = {}
    path = os.path.join(BASE, 'data', 'x-ray', code, f'Dermo-Products-{code}.csv')
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            a = (r.get('ASIN') or '').strip()
            price_col = next((k for k in r if k and 'price' in k.lower()), None)
            rows[a] = {
                'segment': (r.get('Segment') or '').strip(),
                'brand': (r.get('Brand') or 'Unknown').strip() or 'Unknown',
                'price': round(numv(r.get(price_col)), 2) if price_col else 0,
                'rating': numv(r.get('Ratings')),
                'reviews': int(numv(r.get('Review Count'))),
                'bsr': int(numv(r.get('BSR'))),
                'rev30d': round(numv(r.get('ASIN Revenue'))),
            }
    return rows

def listing_path(code, asin):
    return os.path.join(SRC, 'data', 'competitor-listings', code, 'raw', f'{asin}.json')

def load_listing(code, asin):
    p = listing_path(code, asin)
    if not os.path.exists(p): return None
    try: return json.load(open(p, encoding='utf-8'))
    except: return None

def img_url(im):
    return im.get('url') if isinstance(im, dict) else im


def distinct_images(images):
    """One URL per Amazon image VARIANT (MAIN, PT01, PT02, ...), largest size.

    SP-API lists the SAME photo several times by size (2000 / 500 / 75 px), and
    each size gets a DIFFERENT image id (…/I/<id>.jpg) — so URL/id de-dup can't
    collapse them and every picture renders 2-3x. The stable per-photo key is the
    `variant` field. Group by variant, keep the biggest (area) URL per variant,
    return MAIN first then PT01, PT02, ... — i.e. the actual gallery, once each.
    """
    groups, order, fallback = {}, [], []
    for im in images or []:
        if not isinstance(im, dict):
            u = img_url(im)
            if u:
                fallback.append(u)
            continue
        u = im.get('url')
        if not u:
            continue
        var = im.get('variant')
        if not var:
            fallback.append(u)
            continue
        area = (im.get('width') or 0) * (im.get('height') or 0)
        if var not in groups:
            groups[var] = (area, u)
            order.append(var)
        elif area > groups[var][0]:
            groups[var] = (area, u)
    ordered_vars = sorted(order, key=lambda v: (0,) if v == 'MAIN' else (1, v))
    urls = [groups[v][1] for v in ordered_vars]
    seen = set(urls)
    for u in fallback:  # keep any variant-less extras, de-duped by exact URL
        if u not in seen:
            urls.append(u)
            seen.add(u)
    return urls

def claims_in(text):
    """set of theme ids whose local-language keywords appear in `text`."""
    t = (text or '').lower()
    return set(tid for tid, label, kw, plk in THEMES if any(k in t for k in kw))

def build(code, seg):
    slug = seg.lower()
    xr = load_xray(code)
    # competitor pool
    seg_asins = [a for a, v in xr.items() if v['segment'] == seg]
    if not seg_asins:  # fallback: scraped review-bucket ASINs (segmentation mismatch, e.g. FR/Oil)
        seg_asins = [os.path.splitext(os.path.basename(p))[0]
                     for p in glob.glob(os.path.join(SRC, 'reviews', code, seg, '*.json'))]
    avail = [a for a in seg_asins if os.path.exists(listing_path(code, a))]
    avail.sort(key=lambda a: xr.get(a, {}).get('rev30d', 0), reverse=True)
    picks = avail[:TOP_N]
    if not picks:
        print(f'  {code}/{seg}: no competitor listings — skipped'); return

    competitors = []
    for a in picks:
        lst = load_listing(code, a) or {}
        x = xr.get(a, {})
        bullets = [b for b in (lst.get('bullet_points') or []) if b]
        desc = lst.get('description') or ''
        title = lst.get('title') or ''
        imgs = distinct_images(lst.get('images'))   # one URL per variant, largest size
        main = imgs[0] if imgs else None             # MAIN variant is first
        t_claims = claims_in(title)
        b_claims = claims_in(' '.join(bullets))
        allc = t_claims | b_claims
        theme_src = {}
        for tid in allc:
            src = []
            if tid in t_claims: src.append('T')
            if tid in b_claims: src.append('BP')
            theme_src[tid] = src
        order = [t[0] for t in THEMES]
        rev30 = x.get('rev30d', 0)
        competitors.append({
            'asin': a, 'brand': (lst.get('brand') or x.get('brand') or 'Unknown'),
            'title': title, 'img': main, 'imgs': imgs[:8], 'bullets': bullets[:8],
            'themes': sorted(allc, key=lambda tid: order.index(tid)),
            'themeSrc': theme_src,
            'price': x.get('price', 0), 'rating': x.get('rating', 0),
            'reviews': x.get('reviews', 0), 'rev30': rev30, 'archival': rev30 == 0,
        })
    n = len(competitors)

    order = [t[0] for t in THEMES]
    label_by_id = {t[0]: t[1] for t in THEMES}
    def count_of(tid): return sum(1 for c in competitors if tid in c['themes'])

    # matrix columns = claims present in >=1 competitor, in THEMES order
    used_ids = [tid for tid in order if count_of(tid) > 0]
    themes_out = [{'key': tid, 'label': label_by_id[tid]} for tid in used_ids]

    # adoption (sorted desc by count)
    adoption = sorted(
        [{'key': tid, 'label': label_by_id[tid], 'count': count_of(tid),
          'pct': round(count_of(tid) / n * 100)} for tid in used_ids],
        key=lambda a: a['count'], reverse=True)
    avg_claims = round(sum(len(c['themes']) for c in competitors) / n, 1) if n else 0

    # VOC gap — match Polish negativeTopics to themes via PL keywords
    voc_path = os.path.join(BASE, 'reviews', code, seg, 'voc.json')
    voc_gap = []
    if os.path.exists(voc_path):
        voc = json.load(open(voc_path, encoding='utf-8'))
        for nt in (voc.get('negativeTopics') or [])[:6]:
            blob = (nt.get('label', '') + ' ' + nt.get('reason', '')).lower()
            match = next((t for t in THEMES if any(k in blob for k in t[3])), None)
            addressed = count_of(match[0]) if match else 0
            brands = []
            if match:
                for c in competitors:
                    if match[0] in c['themes'] and c['brand'] not in brands:
                        brands.append(c['brand'])
            pct = round(addressed / n * 100) if n else 0
            sev = 'HIGH' if addressed == 0 else ('MED' if addressed <= max(1, n * 0.25) else 'LOW')
            voc_gap.append({
                'vocTopic': nt.get('label', ''), 'vocPct': numv(nt.get('pct')),
                'theme': match[1] if match else '',
                'addressed': addressed, 'total': n, 'pct': pct,
                'sev': sev, 'brands': brands[:5],
            })

    # whitespace (<30%) + saturation (all claims, tiered advice)
    whitespace = [{'label': a['label'], 'pct': a['pct'],
                   'why': f"Tylko {a['count']}/{n} konkurentów komunikuje ten claim — przestrzeń do wyróżnienia."}
                  for a in adoption if a['pct'] < 30]
    def sat_advice(pct):
        if pct >= 70: return 'Claim obowiązkowy (≥70%) — musisz go mieć; wyróżnij się dowodem/konkretem.'
        if pct >= 30: return 'Wysycenie średnie — komunikuj z konkretem (składnik, badanie), nie ogólnikiem.'
        return 'Biała plama (<30%) — okazja do wyróżnienia, jeśli produkt to spełnia.'
    saturation = [{'label': a['label'], 'pct': a['pct'], 'advice': sat_advice(a['pct'])} for a in adoption]

    # typed strategic recommendations (Polish)
    recs = []
    high = [g for g in voc_gap if g['sev'] == 'HIGH']
    if high:
        recs.append({'type': 'Messaging',
                     'finding': 'Negatywy VOC dotyczą: ' + ', '.join(g['vocTopic'] for g in high[:3]) + ' — a żaden czołowy konkurent nie adresuje tego w tytule/bulletach.',
                     'impl': 'Zaadresuj te obawy wprost w tytule i bulletach — natychmiastowa przewaga komunikacyjna.'})
    if whitespace:
        recs.append({'type': 'Pozycjonowanie',
                     'finding': 'Nisko wysycone claimy: ' + ', '.join(w['label'] for w in whitespace[:4]) + '.',
                     'impl': 'Jeśli produkt spełnia te cechy — wyeksponuj je; konkurencja tego nie robi.'})
    top_sat = [a for a in adoption if a['pct'] >= 70]
    if top_sat:
        recs.append({'type': 'Produkt',
                     'finding': 'Nasycone (obowiązkowe) claimy: ' + ', '.join(a['label'] for a in top_sat[:4]) + '.',
                     'impl': 'To parytet kategorii — musisz je mieć, ale wyróżnij się dowodem, nie samą obecnością.'})

    mdd = {
        'totalCompetitors': n,
        'marketplace': MARKETPLACE.get(code, f'amazon.{code.lower()}'),
        'avgClaims': avg_claims,
        'competitors': competitors,
        'themes': themes_out,
        'adoption': adoption,
        'vocGap': voc_gap,
        'whitespace': whitespace,
        'saturation': saturation,
        'recs': recs,
    }
    outdir = os.path.join(BASE, 'data', 'competitor-listings', code)
    os.makedirs(outdir, exist_ok=True)
    json.dump(mdd, open(os.path.join(outdir, f'mdd-{slug}.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'  {code}/{seg}: mdd-{slug}.json ({n} comp, {len(themes_out)} claims, {len(voc_gap)} VOC-gap, {len(whitespace)} whitespace)')

def all_buckets():
    # Gate on LOCAL reviews (they were moved here from atopic-skin-topline); build a
    # bucket if it has either a local review set OR a local voc.json.
    for code in ['DE','FR','IT','ES']:
        for seg in ['Check','Cream','Oil','Wash']:
            d = os.path.join(BASE, 'reviews', code, seg)
            if glob.glob(os.path.join(d, '*.json')) or os.path.exists(os.path.join(d, 'voc.json')):
                build(code, seg)

if __name__ == '__main__':
    if sys.argv[1] == 'ALL':
        all_buckets()
    else:
        build(sys.argv[1], sys.argv[2])
