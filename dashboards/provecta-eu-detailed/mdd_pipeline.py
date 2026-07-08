"""
Marketing Deep-Dive pipeline for provecta-eu-detailed (ENGLISH output, no segments).

Deterministic (no LLM): builds mdd.json per country from competitor listings.

  python mdd_pipeline.py DE          # one market
  python mdd_pipeline.py ALL         # all five

For each market:
  - competitor pool = X-Ray ASINs ranked by ASIN Revenue (30d) that have a
    listing JSON in data/competitor-listings/{CODE}/raw/, top N.
  - claims tagged by multilingual regex over title+bullets (DE/FR/IT/ES/EN),
    with source attribution (T = title, BP = bullets).
  - VOC gap uses local reviews/{CODE}/voc.json negativeTopics (English) matched
    to themes via English keywords.
  - writes data/competitor-listings/{CODE}/mdd.json (u-marketing-deep-dive contract).
"""
import csv, os, sys, json, re, glob
sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
TOP_N = 12
MARKETPLACE = {'DE': 'amazon.de', 'FR': 'amazon.fr', 'IT': 'amazon.it', 'ES': 'amazon.es', 'UK': 'amazon.co.uk'}

# ── Claim themes: id, Polish label, listing stems (DE/FR/IT/ES/EN), VOC stems (PL). ──
#    `kw` matched against LISTING copy (local language); PL stems matched against
#    the Polish negativeTopics from voc.json for the gap analysis.
THEMES = [
    ("fast_action",    "Szybkie działanie",             ["sofort","schnell wirk","wirkt schnell","rapide","action immédiate","immediat","azione rapida","effetto immediato","rapido","acción rápida","accion rapida","inmediato","fast","fast-acting","quick","instant","immediate","in minuten","within"], ["wolno","powol","szybk","natychmiast","czeka"]),
    ("long_lasting",   "Długotrwała ochrona",           ["langzeit","wochen","monate","lang anhaltend","dauerhaft","longue durée","longue duree","semaines","mois","lunga durata","settimane","mesi","larga duración","larga duracion","semanas","meses","long-lasting","long lasting","lasts","weeks","months","up to"], ["zanika","krótko","krotko","przestaje","nietrwa","dni, nie","po kilku dniach","efekt mija"]),
    ("kills_eliminates","Zabija / eliminuje",           ["tötet","totet","abtöt","abtot","bekämpf","bekampf","vernicht","élimine","elimine","extermin","uccide","elimina","stermina","mata","kills","kill","eliminate","destroy","wipes out"], ["nieskuteczn","nie działa","nie dziala","brak efektu","przeży","przezy","bezużyteczn","bezuzyteczn","inwazj","nie eliminuje","nie zabija","nie łapi","nie lapi","nie łapa","omijają","omijaja"]),
    ("odourless",      "Bezzapachowy / niska woń",      ["geruchlos","geruchsneutral","geruchsarm","ohne geruch","sans odeur","inodore","senza odore","inodoro","sin olor","odourless","odorless","odour-free","odor-free","no smell","low odour","low odor"], ["zapach","śmierdz","smierdz","odór","odor","woń"]),
    ("safe_kids_pets", "Bezpieczny dla dzieci i zwierząt", ["haustier","kinder","sicher für","sicher fur","ungiftig","animaux domestiques","enfants","sans danger","animali domestici","bambini","sicuro per","mascotas","niños","ninos","seguro para","pet-safe","pet safe","child-safe","children","pets","non-toxic","non toxic"], ["bezpiecz","toksycz","dzieci","zwierz","pies","psa","kot","trując","trujac","zatru","zdrowi","astm"]),
    ("indoor_outdoor", "Do wnętrz i na zewnątrz",       ["innen","außen","aussen","innenbereich","außenbereich","intérieur","interieur","extérieur","exterieur","interno","esterno","interior","exterior","indoor","outdoor"], ["wewnątrz","wewnatrz","zewnątrz","zewnatrz","ogrod","ogród"]),
    ("no_residue",     "Bez plam / osadu",              ["keine flecken","fleckenfrei","rückstandsfrei","ruckstandsfrei","sans tache","sans résidu","sans residu","senza macchie","senza residui","sin manchas","sin residuos","no stain","stain-free","no residue","residue-free","non-staining"], ["plam","osad","lepk","tłust","tlust","ślisk","slisk","film"]),
    ("easy_use",       "Łatwa aplikacja / gotowy do użycia", ["gebrauchsfertig","einfache anwendung","anwendungsfertig","einfach anzuwenden","prêt à l'emploi","pret a l'emploi","facile à utiliser","facile a utiliser","pronto all'uso","pronto uso","facile da usare","listo para usar","fácil de usar","facil de usar","ready to use","ready-to-use","easy to use","easy application","spray head"], ["trudn","dysz","spryskiwacz","aplikacj","instrukcj","wyciek","montaż","montaz","składani","skladani","obsług","obslug"]),
    ("wide_spectrum",  "Na wiele owadów / szerokie spektrum", ["alle insekten","ungeziefer","universal","gegen insekten","kriechend","fliegend","tous les insectes","tous insectes","rampants","volants","tutti gli insetti","striscianti","volanti","todos los insectos","rastreros","voladores","all insects","crawling and flying","crawling & flying","multi-insect","broad spectrum"], ["inne owady","różne owady","rozne owady","gatunk"]),
    ("barrier_prevent","Bariera / prewencja",           ["barriere","barrière","vorbeugend","schutz vor","schützt","schutzt","préventif","preventif","protège","protege","barriera","preventivo","protegge","barrera","preventiva","protege","barrier","prevent","protection against","repel","repellent","keeps away","keep away"], ["wraca","powrac","prewencj","zapobieg","barier"]),
    ("professional",   "Klasa profesjonalna",           ["profi","professionell","professionnel","usage professionnel","professionale","uso professionale","profesional","uso profesional","professional","pro-grade","professional strength"], ["profesjonal","tępiciel","tepiciel","dezynsekc"]),
    ("natural_eco",    "Naturalny / eko",               ["natürlich","naturlich","pflanzlich","ohne chemie","biozidfrei","naturel","origine végétale","vegetale","naturale","natural","plant-based","eco-friendly","ecológico","ecologico","chemical-free","organic","bio "], ["chemi","natural","eko"]),
    ("value_size",     "Ekonomiczny / duże opakowanie", ["großpackung","grosspackung","ergiebig","vorteilspack","économique","economique","grand format","formato convenienza","conveniente","económico","economico","gran formato","value","large size","twin pack","pack of","doppelpack","2er pack","lot de"], ["cena","drog","wartość","wartosc","ilość","ilosc","opłac","oplac","podwyż","podwyz","mało","malo"]),
]


def numv(v):
    s = re.sub(r'[^\d.,-]', '', str(v or '')).replace(',', '')
    try:
        return float(s)
    except Exception:
        return 0.0


def load_xray(code):
    rows = {}
    path = os.path.join(BASE, 'data', 'x-ray', f'Provecta-{code}.csv')
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            a = (r.get('ASIN') or '').strip()
            if not a:
                continue
            price_col = next((k for k in r if k and 'price' in k.lower()), None)
            rec = {
                'brand': (r.get('Brand') or 'Unknown').strip() or 'Unknown',
                'price': round(numv(r.get(price_col)), 2) if price_col else 0,
                'rating': numv(r.get('Ratings')),
                'reviews': int(numv(r.get('Review Count'))),
                'bsr': int(numv(r.get('BSR'))),
                'rev30d': round(numv(r.get('ASIN Revenue'))),
            }
            if a not in rows or rec['rev30d'] > rows[a]['rev30d']:
                rows[a] = rec
    return rows


def listing_path(code, asin):
    return os.path.join(BASE, 'data', 'competitor-listings', code, 'raw', f'{asin}.json')


def load_listing(code, asin):
    p = listing_path(code, asin)
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return None


def img_url(im):
    return im.get('url') if isinstance(im, dict) else im


def distinct_images(images):
    """One URL per Amazon image VARIANT (MAIN, PT01, ...), largest size each."""
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
    for u in fallback:
        if u not in seen:
            urls.append(u)
            seen.add(u)
    return urls


def claims_in(text):
    t = (text or '').lower()
    return set(tid for tid, label, kw, vk in THEMES if any(k in t for k in kw))


def build(code):
    xr = load_xray(code)
    avail = [a for a in xr if os.path.exists(listing_path(code, a))]
    avail.sort(key=lambda a: xr.get(a, {}).get('rev30d', 0), reverse=True)
    picks = avail[:TOP_N]
    if not picks:
        print(f'  {code}: no competitor listings - skipped'); return

    competitors = []
    for a in picks:
        lst = load_listing(code, a) or {}
        x = xr.get(a, {})
        bullets = [b for b in (lst.get('bullet_points') or []) if b]
        title = lst.get('title') or ''
        imgs = distinct_images(lst.get('images'))
        main = imgs[0] if imgs else None
        t_claims = claims_in(title)
        b_claims = claims_in(' '.join(bullets))
        allc = t_claims | b_claims
        theme_src = {}
        for tid in allc:
            src = []
            if tid in t_claims:
                src.append('T')
            if tid in b_claims:
                src.append('BP')
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
    def count_of(tid):
        return sum(1 for c in competitors if tid in c['themes'])

    used_ids = [tid for tid in order if count_of(tid) > 0]
    themes_out = [{'key': tid, 'label': label_by_id[tid]} for tid in used_ids]

    adoption = sorted(
        [{'key': tid, 'label': label_by_id[tid], 'count': count_of(tid),
          'pct': round(count_of(tid) / n * 100)} for tid in used_ids],
        key=lambda a: a['count'], reverse=True)
    avg_claims = round(sum(len(c['themes']) for c in competitors) / n, 1) if n else 0

    # VOC gap - match English negativeTopics to themes via EN keywords
    voc_path = os.path.join(BASE, 'reviews', code, 'voc.json')
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

    whitespace = [{'label': a['label'], 'pct': a['pct'],
                   'why': f"Tylko {a['count']}/{n} konkurentów komunikuje ten claim - przestrzeń do wyróżnienia."}
                  for a in adoption if a['pct'] < 30]

    def sat_advice(pct):
        if pct >= 70:
            return 'Claim obowiązkowy (>=70%) - musisz go mieć; wyróżnij się dowodem/konkretem.'
        if pct >= 30:
            return 'Wysycenie średnie - komunikuj z konkretem (substancja czynna, potwierdzony czas działania), nie ogólnikiem.'
        return 'Biała plama (<30%) - okazja do wyróżnienia, jeśli produkt to spełnia.'
    saturation = [{'label': a['label'], 'pct': a['pct'], 'advice': sat_advice(a['pct'])} for a in adoption]

    recs = []
    high = [g for g in voc_gap if g['sev'] == 'HIGH']
    if high:
        recs.append({'type': 'Messaging',
                     'finding': 'Negatywy VOC dotyczą: ' + ', '.join(g['vocTopic'] for g in high[:3]) + ' - a żaden czołowy konkurent nie adresuje tego w tytule/bulletach.',
                     'impl': 'Zaadresuj te obawy wprost w tytule i bulletach - natychmiastowa przewaga komunikacyjna.'})
    if whitespace:
        recs.append({'type': 'Pozycjonowanie',
                     'finding': 'Nisko wysycone claimy: ' + ', '.join(w['label'] for w in whitespace[:4]) + '.',
                     'impl': 'Jeśli produkt spełnia te cechy - wyeksponuj je; konkurencja tego nie robi.'})
    top_sat = [a for a in adoption if a['pct'] >= 70]
    if top_sat:
        recs.append({'type': 'Produkt',
                     'finding': 'Nasycone (obowiązkowe) claimy: ' + ', '.join(a['label'] for a in top_sat[:4]) + '.',
                     'impl': 'To parytet kategorii - musisz je mieć, ale wyróżnij się dowodem, nie samą obecnością.'})

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
    json.dump(mdd, open(os.path.join(outdir, 'mdd.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'  {code}: mdd.json ({n} comp, {len(themes_out)} claims, {len(voc_gap)} VOC-gap, {len(whitespace)} whitespace)')


if __name__ == '__main__':
    arg = sys.argv[1].upper() if len(sys.argv) > 1 else 'ALL'
    if arg == 'ALL':
        for c in ['FR', 'DE', 'UK', 'IT', 'ES']:
            build(c)
    else:
        build(arg)
