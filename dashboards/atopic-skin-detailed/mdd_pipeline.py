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

def tag_claims(text):
    t = text.lower()
    return [tid for tid, label, kw, plk in THEMES if any(k in t for k in kw)]

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
        imgs = [img_url(im) for im in (lst.get('images') or []) if img_url(im)]
        main = None
        for im in (lst.get('images') or []):
            if isinstance(im, dict) and im.get('variant') == 'MAIN':
                main = im.get('url'); break
        if not main and imgs: main = imgs[0]
        themes = tag_claims(' '.join([title] + bullets + [desc]))
        competitors.append({
            'asin': a, 'brand': (lst.get('brand') or x.get('brand') or 'Unknown'),
            'title': title, 'mainImage': main, 'images': imgs[:8],
            'themes': themes, 'price': x.get('price', 0), 'rating': x.get('rating', 0),
            'reviews': x.get('reviews', 0), 'bsr': x.get('bsr', 0), 'rev30d': x.get('rev30d', 0),
            'bullets': bullets[:8], 'description': desc[:1200],
        })
    n = len(competitors)

    # claims matrix + summary
    used = [t for t in THEMES if any(t[0] in c['themes'] for c in competitors)]
    matrix_themes = [{'id': t[0], 'label': t[1]} for t in used]
    rows = [{'brand': c['brand'], 'asin': c['asin'],
             'cells': [t[0] in c['themes'] for t in used]} for c in competitors]
    summary = []
    for t in used:
        cnt = sum(1 for c in competitors if t[0] in c['themes'])
        brands = [c['brand'] for c in competitors if t[0] in c['themes']]
        # unique, keep order
        seen = [];
        for b in brands:
            if b not in seen: seen.append(b)
        summary.append({'label': t[1], 'count': cnt, 'pct': round(cnt / n * 100),
                        'topBrands': seen[:3]})
    summary.sort(key=lambda s: s['count'], reverse=True)

    # VOC gap — match Polish negativeTopics to themes via PL keywords
    voc_path = os.path.join(BASE, 'reviews', code, seg, 'voc.json')
    voc_gap = []
    if os.path.exists(voc_path):
        voc = json.load(open(voc_path, encoding='utf-8'))
        theme_by_id = {t[0]: t for t in THEMES}
        count_by_id = {t[0]: sum(1 for c in competitors if t[0] in c['themes']) for t in THEMES}
        for nt in (voc.get('negativeTopics') or [])[:6]:
            blob = (nt.get('label', '') + ' ' + nt.get('reason', '')).lower()
            match = None
            for t in THEMES:
                if any(k in blob for k in t[3]):
                    match = t; break
            addressed = count_by_id.get(match[0], 0) if match else 0
            brands = [c['brand'] for c in competitors if match and match[0] in c['themes']][:3]
            pct_num = numv(nt.get('pct'))
            if addressed == 0:
                sev = 'HIGH'
            elif addressed <= max(1, n * 0.25):
                sev = 'MEDIUM'
            else:
                sev = 'LOW'
            voc_gap.append({
                'vocTopic': nt.get('label', ''), 'customerConcernPct': nt.get('pct', ''),
                'addressedByCount': addressed, 'addressedByBrands': brands,
                'gapSeverity': sev, 'whitespace': 'true' if addressed <= max(1, n * 0.25) else 'false',
            })

    # whitespace (<=25%) + saturation (>=60%)
    whitespace = [{'opportunity': s['label'],
                   'rationale': f"Tylko {s['count']}/{n} konkurentów deklaruje ten temat w listingu — przestrzeń do wyróżnienia.",
                   'evidence': ('Obecne marki: ' + ', '.join(s['topBrands'])) if s['topBrands'] else 'Żaden z czołowych konkurentów tego nie eksponuje.'}
                  for s in summary if s['pct'] <= 25]
    saturation = [{'label': s['label'], 'saturationPct': f"{s['pct']}%",
                   'advice': 'Standard kategorii (table-stakes) — traktuj jako wymóg, nie wyróżnik.'}
                  for s in summary if s['pct'] >= 60]

    # strategic recommendations (Polish, from gaps + whitespace)
    recs = []
    high = [g for g in voc_gap if g['gapSeverity'] == 'HIGH']
    if high:
        recs.append({'type': 'Luka VOC↔listing', 'badgeBg': '#fee2e2', 'badgeColor': '#991b1b',
                     'finding': 'Klienci skarżą się na: ' + ', '.join(g['vocTopic'] for g in high[:3]) + ', a żaden czołowy konkurent tego nie adresuje w treści listingu.',
                     'implication': 'Zaadresuj te obawy wprost w tytule i bulletach — natychmiastowa przewaga komunikacyjna.'})
    if whitespace:
        recs.append({'type': 'Białe plamy', 'badgeBg': '#fef3c7', 'badgeColor': '#92400e',
                     'finding': 'Nisko wysycone tematy: ' + ', '.join(w['opportunity'] for w in whitespace[:4]) + '.',
                     'implication': 'Jeśli produkt spełnia te cechy — wyeksponuj je, bo konkurencja tego nie robi.'})
    if saturation:
        recs.append({'type': 'Parytet', 'badgeBg': '#dcfce7', 'badgeColor': '#166534',
                     'finding': 'Nasycone deklaracje: ' + ', '.join(s['label'] for s in saturation[:4]) + '.',
                     'implication': 'Musisz je mieć, ale nie licz na wyróżnienie — poświęć im minimum miejsca.'})

    mdd = {
        'totalCompetitors': n, 'marketplace': MARKETPLACE.get(code, f'amazon.{code.lower()}'),
        'competitors': competitors,
        'claimsMatrix': {'themes': matrix_themes, 'rows': rows},
        'claimsSummary': summary,
        'vocGap': voc_gap,
        'whitespaceOpportunities': whitespace,
        'saturation': saturation,
        'strategicRecommendations': recs,
    }
    outdir = os.path.join(BASE, 'data', 'competitor-listings', code)
    os.makedirs(outdir, exist_ok=True)
    json.dump(mdd, open(os.path.join(outdir, f'mdd-{slug}.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'  {code}/{seg}: mdd-{slug}.json ({n} competitors, {len(matrix_themes)} themes, {len(voc_gap)} VOC-gap rows, {len(whitespace)} whitespace)')

def all_buckets():
    for code in ['DE','FR','IT','ES']:
        for seg in ['Check','Cream','Oil','Wash']:
            if glob.glob(os.path.join(SRC, 'reviews', code, seg, '*.json')):
                build(code, seg)

if __name__ == '__main__':
    if sys.argv[1] == 'ALL':
        all_buckets()
    else:
        build(sys.argv[1], sys.argv[2])
