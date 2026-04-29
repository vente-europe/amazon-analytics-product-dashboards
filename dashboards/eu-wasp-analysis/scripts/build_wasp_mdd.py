"""Build Marketing Deep-Dive JSON for EU Wasp dashboard — per country per segment.

Reads:
  data/x-ray/{CODE}/Wasps?* DE/FR/UK.csv         (price/rating/reviews/bsr/sales/rev)
  data/competitor-listings/{CODE}/asins-{seg}.txt (top-N ASINs per segment)
  data/competitor-listings/{CODE}/raw/{ASIN}.json (title/brand/bullets fetched via SP-API)
  reviews/{CODE}/{Segment}/voc.json               (Reviews VOC analysis for gap-mapping)

Writes:
  data/competitor-listings/{CODE}/mdd-{segment}.json

Run:
  py scripts/build_wasp_mdd.py DE lure
  py scripts/build_wasp_mdd.py DE electric
  ... etc
"""
import os, sys, json, csv, re
sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

XRAY_FILES = {'DE': 'Wasps DE.csv', 'FR': 'Wasp FR.csv', 'UK': 'Wasps UK.csv'}
CURRENCY = {'DE': '€', 'FR': '€', 'UK': '£'}
MARKETPLACE = {'DE': 'amazon.de', 'FR': 'amazon.fr', 'UK': 'amazon.co.uk'}
EXPORT_MONTH = 4  # April 2026 (0-indexed: 3)

# ── Themes per segment (keys must be stable for the dashboard) ──
LURE_THEMES = [
    {"key": "effective_catch",     "label": "Catches lots of wasps"},
    {"key": "bee_friendly",        "label": "Bee-friendly / selective"},
    {"key": "reusable_refill",     "label": "Reusable / refillable"},
    {"key": "weatherproof",        "label": "Weatherproof / outdoor"},
    {"key": "safe_kids_pets",      "label": "Safe for kids & pets"},
    {"key": "discreet_design",     "label": "Discreet / decorative design"},
    {"key": "no_chemicals",        "label": "No chemicals / poison-free"},
    {"key": "easy_setup",          "label": "Easy to set up / hang"},
    {"key": "long_lasting_bait",   "label": "Long-lasting bait"},
    {"key": "outdoor_dining",      "label": "BBQ / patio / dining defense"},
]

ELECTRIC_THEMES = [
    {"key": "powerful_zapper",     "label": "Powerful zap / kills instantly"},
    {"key": "quiet_operation",     "label": "Quiet / silent operation"},
    {"key": "indoor_safe",         "label": "Safe indoor use (bedroom)"},
    {"key": "outdoor_weatherproof","label": "Weatherproof outdoor"},
    {"key": "usb_rechargeable",    "label": "USB rechargeable / portable"},
    {"key": "wide_coverage",       "label": "Wide coverage area"},
    {"key": "safe_kids_pets",      "label": "Pet- & child-safe grid"},
    {"key": "easy_clean",          "label": "Easy-clean tray"},
    {"key": "uv_attracts",         "label": "UV light attracts insects"},
    {"key": "long_lifespan",       "label": "Durable / long lifespan"},
]

# ── Regex per theme — multilingual (DE/FR/EN) ──
LURE_RX = {
    "effective_catch":   r"(catch(es)?\s+(loads|lots|many|hundreds|hundreds)|f[äa]ngt\s+viele|capture\s+(de\s+)?nombreuses?|piège\s+efficace|wahnsinnig\s+viele|massenweise|sehr\s+effektiv|extrem\s+wirksam|highly\s+effective|wespenfang|wespen\s+fang)",
    "bee_friendly":      r"(bee[-\s]?friendly|schon(t|end)\s+f[üu]r\s+bienen|sans\s+abeilles?|safe\s+for\s+bees|protects?\s+bees|bienenschonend|epargne\s+les\s+abeilles|n'attire\s+pas\s+(les\s+)?abeilles)",
    "reusable_refill":   r"(reusable|refillable|wiederverwendbar|nachf[üu]llbar|réutilisable|rechargeable|refill|nachf[üu]ll|recharge\b)",
    "weatherproof":      r"(weather(proof|resistant)|wetter(beständig|fest)|résist(e|ant)\s+(aux\s+)?intempéries?|all[-\s]?weather|wetterbeständig|étanche\s+pluie|outdoor|im\s+freien|tout\s+temps)",
    "safe_kids_pets":    r"(safe\s+(for|around)\s+(children|kids|pets|dogs|cats|grandkids|babies)|kindersicher|haustiersicher|sicher\s+f[üu]r\s+kinder|sans\s+danger\s+(pour\s+)?(enfants?|animaux)|family[-\s]?safe|child[-\s]?safe|pet[-\s]?safe|s[üu]r\s+pour|sécurisé)",
    "discreet_design":   r"(discreet|discret|unauff[äa]llig|décoratif|decorative|elegant(es)?\s+design|sch[öo]nes?\s+design|joli|attractive\s+design|premium\s+look|stylish|design\s+(soigné|moderne|épuré))",
    "no_chemicals":      r"(no\s+(chemicals?|poison|insecticide|pesticide|toxin|toxic)|chemical[-\s]?free|insecticide[-\s]?free|sans\s+(insecticide|produit\s+chimique|pesticide)|ohne\s+(gift|chemie|insektizid)|natural|nat[üu]rlich|naturel|non[-\s]?toxic|ungiftig|sans\s+poison)",
    "easy_setup":        r"(easy\s+(to\s+)?(set[-\s]?up|use|install|hang|assemble)|just\s+(hang|fill|set|put|add)|simple\s+(à\s+)?(utilis(er)?|installer|monter)|kinderleicht|simpel|einfach\s+(zu\s+)?(aufzubauen|aufstellen)|prêt\s+à\s+l'emploi|ready\s+to\s+use|sans\s+outil|no\s+tools)",
    "long_lasting_bait": r"(long[-\s]?lasting|lasts?\s+(weeks|months|all\s+season|the\s+whole\s+season|ages|saison\s+entière|toute\s+la\s+saison)|h[äa]lt\s+(wochen|monate|saison|lang)|tient\s+(plusieurs\s+semaines|toute\s+(la\s+)?saison)|long(ue)?\s+(durée|tenue)|appât\s+(longue|qui\s+dure)|langer?\s+lebensdauer|durable\s+bait)",
    "outdoor_dining":    r"(bbq|barbecue|grill(en|ing|abend|saison|party)?|patio|terrasse|garten|jardin|esstisch|outdoor\s+dining|repas\s+en\s+(plein\s+)?ext[ée]rieur|al\s+fresco|apéro|drinks?\s+outside|dining\s+(out|outside)|au\s+jardin|im\s+garten)",
}

ELECTRIC_RX = {
    "powerful_zapper":     r"(powerful\s+(zap|grid|voltage)|hochspannung|high[-\s]?voltage|haute\s+tension|kills?\s+(instantly|on\s+contact|fast)|t[öo]tet\s+sofort|tue\s+(rapidement|instantanément)|3000\s*v|3500\s*v|4000\s*v|kv|killer|exterminate|exterminer|vernicht(et|en)|élimine\s+(en\s+)?un\s+(seul|coup))",
    "quiet_operation":     r"(quiet|silent|fl[üu]sterleise|leise|whisper[-\s]?quiet|silencieux|sans\s+bruit|kaum\s+h[öo]rbar|fast\s+ger[äa]uschlos|low\s+noise|noise[-\s]?free|geräuschlos)",
    "indoor_safe":         r"(indoor\s+(use|safe)|innenraum|innen(bereich)?|f[üu]r\s+(innen|drinnen|wohnzimmer|schlafzimmer)|usage\s+intérieur|chambre|bedroom|salon|kitchen|k[üu]che|cuisine|f[üu]r\s+drinnen)",
    "outdoor_weatherproof":r"(weatherproof|wetterfest|wetterbeständig|imperméable|étanche|ip\s*44|ip\s*54|ip\s*65|ip\s*67|outdoor[-\s]?ready|f[üu]r\s+drau[sß]en|outdoor[-\s]?(use|tauglich)|all[-\s]?weather|tout\s+temps|résist(e|ant)\s+(à\s+l')?eau)",
    "usb_rechargeable":    r"(usb[-\s]?(c|rechargeable|recharge)|rechargeable|rechargement|aufladbar|wiederaufladbar|battery[-\s]?powered|akku|batterie|cordless|sans\s+fil|portable|tragbar|nomade|sans[-\s]?fil)",
    "wide_coverage":       r"(wide\s+coverage|large\s+(area|coverage)|covers?\s+(up\s+to\s+)?\d+\s*(m|sq|m²|square|qm)|gro[sß]er?\s+(bereich|fläche)|wirkungsbereich|grande?\s+(surface|portée)|couvre\s+(jusqu'à\s+)?\d+|für\s+r[äa]ume\s+(bis|von)|whole\s+room|ganzer?\s+raum)",
    "safe_kids_pets":      r"(safe\s+(for|around)\s+(children|kids|pets|dogs|cats|babies)|child[-\s]?safe|pet[-\s]?safe|kindersicher|haustiersicher|sicher\s+f[üu]r\s+(kinder|haustiere)|sans\s+danger\s+(pour\s+)?(enfants?|animaux)|protective\s+(grid|grille|gitter)|schutzgitter|grille\s+(de\s+)?protection|safety\s+grid)",
    "easy_clean":          r"(easy\s+(to\s+)?clean|easy[-\s]?clean|removable\s+tray|reinigung\s+(einfach|leicht|kinderleicht)|nettoyage\s+(facile|simple)|tray\s+(removable|slides\s+out)|tiroir\s+amovible|sp[üu]lmaschinengeeignet|dishwasher\s+safe|tool[-\s]?free\s+(clean|cleaning)|herausnehmbar)",
    "uv_attracts":         r"(uv\s+(light|lamp|bulb|tube|365\s*nm|attracts?)|ultraviolett|lumière\s+uv|uv[-\s]?led|attractive\s+uv\s+light|attire(s)?\s+(les\s+)?(insectes?|moustiques?|mouches?)|lockt\s+(insekten|m[üu]cken|fliegen)|attracts?\s+(insects|mosquitoes|flies))",
    "long_lifespan":       r"(durable|long[-\s]?lasting|lasts?\s+(years|seasons|saisons|jahren?)|langlebig|h[äa]lt\s+(jahre|ewig|lange)|robust|hochwertig\s+verarbeitet|qualité\s+(durable|longévité)|dur(e|ée|able)\s+(plusieurs\s+)?(années|saisons)|2[-\s]?(year|jahres|ans)\s+(warranty|garantie)|garantie\s+(\d+\s+ans|\d+\s+jahre))",
}

THEMES_BY_SEG = {'lure': LURE_THEMES, 'electric': ELECTRIC_THEMES}
RX_BY_SEG = {'lure': LURE_RX, 'electric': ELECTRIC_RX}


def numv(v):
    if v is None: return 0.0
    s = str(v).strip().strip('"').replace('\xa0', '').replace(' ', '')
    s = re.sub(r'[€$£%]', '', s)
    if not s: return 0.0
    if s.count(',') and not s.count('.'):
        s = s.replace(',', '.')
    else:
        s = s.replace(',', '')
    try: return float(s)
    except: return 0.0


def load_xray_lookup(code):
    path = os.path.join(BASE, 'data', 'x-ray', code, XRAY_FILES[code])
    out = {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows: return out
    price_col = next((k for k in rows[0].keys() if 'price' in k.lower()), None)
    for r in rows:
        asin = (r.get('ASIN') or '').strip()
        if not asin: continue
        sales30 = numv(r.get('ASIN Sales'))
        price = numv(r.get(price_col))
        rev30 = numv(r.get('ASIN Revenue'))
        if rev30 == 0 and sales30 > 0 and price > 0:
            rev30 = sales30 * price
        out[asin] = {
            'brand': (r.get('Brand') or '').strip(),
            'title': (r.get('Product Details') or '').strip(),
            'price': round(price, 2),
            'rating': numv(r.get('Ratings')),
            'reviews': int(numv(r.get('Review Count'))),
            'bsr': int(numv(r.get('BSR'))) if r.get('BSR') else 0,
            'sales30d': int(sales30),
            'rev30d': round(rev30, 2),
        }
    return out


def tag_themes(text, rxmap):
    text_lc = text.lower()
    return [k for k, rx in rxmap.items() if re.search(rx, text_lc)]


def main(code, segment):
    code = code.upper()
    seg = segment.lower()
    if seg not in ('lure', 'electric'):
        print('segment must be lure or electric'); sys.exit(1)
    if code not in XRAY_FILES:
        print(f'unknown country: {code}'); sys.exit(1)

    themes = THEMES_BY_SEG[seg]
    rx = RX_BY_SEG[seg]
    theme_keys = [t['key'] for t in themes]

    # ── Inputs ──
    asin_file = os.path.join(BASE, 'data', 'competitor-listings', code, f'asins-{seg}.txt')
    raw_dir   = os.path.join(BASE, 'data', 'competitor-listings', code, 'raw')
    voc_path  = os.path.join(BASE, 'reviews', code, seg.capitalize(), 'voc.json')
    out_path  = os.path.join(BASE, 'data', 'competitor-listings', code, f'mdd-{seg}.json')

    with open(asin_file) as f:
        asins = [l.strip() for l in f if l.strip()]

    xray = load_xray_lookup(code)

    # ── Build competitors[] ──
    competitors = []
    matrix_rows = []
    theme_counts = {k: 0 for k in theme_keys}
    theme_brands = {k: [] for k in theme_keys}

    for asin in asins:
        raw_path = os.path.join(raw_dir, f'{asin}.json')
        if not os.path.exists(raw_path):
            print(f'  skip {asin}: no raw catalog json')
            continue
        with open(raw_path, encoding='utf-8') as f:
            raw = json.load(f)
        x = xray.get(asin, {})
        title = raw.get('title') or x.get('title') or ''
        brand = raw.get('brand') or x.get('brand') or '?'
        bullets = raw.get('bullet_points') or []
        desc = raw.get('description') or ''
        # Normalize images to URL strings (raw catalog stores them as dicts)
        raw_images = raw.get('images') or []
        images = []
        for img in raw_images:
            if isinstance(img, dict) and img.get('url'):
                images.append(img['url'])
            elif isinstance(img, str):
                images.append(img)
        main_img = images[0] if images else ''

        # Tag themes from title + bullets + desc
        haystack = title + '\n' + '\n'.join(bullets) + '\n' + desc
        asin_themes = tag_themes(haystack, rx)
        cells = [1 if k in asin_themes else 0 for k in theme_keys]

        for k in asin_themes:
            theme_counts[k] += 1
            if brand and brand not in theme_brands[k]:
                theme_brands[k].append(brand)

        competitors.append({
            'asin': asin,
            'brand': brand,
            'title': title,
            'price': x.get('price', 0),
            'rating': x.get('rating', 0),
            'reviews': x.get('reviews', 0),
            'bsr': x.get('bsr', 0),
            'rev30d': x.get('rev30d', 0),
            'sales30d': x.get('sales30d', 0),
            'mainImage': main_img,
            'images': images[:8],
            'bullets': bullets,
            'description': desc[:1200],
            'themes': asin_themes,
            'claimCount': len(asin_themes),
        })
        matrix_rows.append({
            'asin': asin,
            'brand': brand,
            'cells': cells,
        })

    n_comp = len(competitors)

    # ── claimsSummary[] ──
    claims_summary = []
    for t in themes:
        n = theme_counts[t['key']]
        claims_summary.append({
            'theme': t['key'],
            'label': t['label'],
            'count': n,
            'pct': round(n / n_comp * 100, 1) if n_comp else 0,
            'topBrands': theme_brands[t['key']][:5],
        })
    claims_summary.sort(key=lambda x: -x['count'])

    # ── vocGap[] ── cross-reference Reviews VOC negativeTopics
    voc_gap = []
    if os.path.exists(voc_path):
        with open(voc_path, encoding='utf-8') as f:
            voc = json.load(f)
        # Map VOC negative-topic labels to theme keys (best-effort by keyword match)
        VOC_THEME_HINTS = {
            'effective_catch':   ['catch', 'effective', 'efficac', 'wirkung', 'no efficacy', 'inefficac', 'doesn\'t catch', 'doesn\'t kill', 'doesn\'t work'],
            'bee_friendly':      ['bee', 'biene', 'abeille', 'wrong', 'attracts', 'kills wrong'],
            'reusable_refill':   ['reusable', 'refill', 'nachf', 'rechargeable'],
            'weatherproof':      ['weather', 'wetter', 'pluie', 'wind', 'rain'],
            'safe_kids_pets':    ['safe', 'kids', 'children', 'pet', 'kinder', 'enfants', 'animaux', 'safety'],
            'discreet_design':   ['design', 'look', 'aesthetic', 'discret'],
            'no_chemicals':      ['chemical', 'poison', 'toxic', 'gift', 'insecticide'],
            'easy_setup':        ['easy', 'simple', 'einfach', 'facile', 'setup', 'install'],
            'long_lasting_bait': ['bait', 'köder', 'appât', 'last', 'dries', 'trocken', 'sèche'],
            'outdoor_dining':    ['bbq', 'barbecue', 'patio', 'terrasse', 'garten', 'jardin', 'dining'],
            'powerful_zapper':   ['kill', 'voltage', 'effective', 'wirk', 'tue', 'powerful', 'zap'],
            'quiet_operation':   ['noise', 'quiet', 'silent', 'laut', 'loud', 'crack', 'bruit'],
            'indoor_safe':       ['bedroom', 'indoor', 'innen', 'chambre'],
            'outdoor_weatherproof': ['weather', 'wetter', 'rain', 'pluie', 'outdoor'],
            'usb_rechargeable':  ['battery', 'usb', 'charge', 'akku', 'batterie'],
            'wide_coverage':     ['coverage', 'area', 'reichweite', 'surface'],
            'easy_clean':        ['clean', 'reinigen', 'nettoy', 'tray', 'schale'],
            'uv_attracts':       ['uv', 'light', 'licht', 'lumière', 'attract'],
            'long_lifespan':     ['durable', 'lasts', 'broke', 'kaputt', 'casse', 'lifespan'],
        }
        neg_topics = voc.get('negativeTopics', [])[:6]
        for nt in neg_topics:
            label = nt.get('label', '')
            label_lc = label.lower()
            # Find matching theme keys
            matched_themes = []
            for tk in theme_keys:
                hints = VOC_THEME_HINTS.get(tk, [])
                if any(h.lower() in label_lc for h in hints):
                    matched_themes.append(tk)
            # Coverage = how many competitors claim ANY matched theme
            covering_brands = set()
            covering_count = 0
            for cmp in competitors:
                if any(t in cmp['themes'] for t in matched_themes):
                    covering_count += 1
                    if cmp['brand']:
                        covering_brands.add(cmp['brand'])
            try:
                pct = float(str(nt.get('pct', '0')).replace('%', ''))
            except Exception:
                pct = 0.0
            severity = 'high' if pct >= 20 and covering_count <= 1 else ('medium' if pct >= 10 and covering_count <= 2 else 'low')
            voc_gap.append({
                'vocTopic': label,
                'customerConcernPct': pct,
                'addressedByCount': covering_count,
                'addressedByBrands': sorted(covering_brands)[:5],
                'gapSeverity': severity,
                'whitespace': covering_count == 0,
            })

    # ── whitespace + saturation ──
    whitespace_ops = []
    saturation = []
    for cs in claims_summary:
        if cs['pct'] <= 25:
            whitespace_ops.append({
                'opportunity': f'{cs["label"]} (only {cs["count"]} of {n_comp} competitors)',
                'rationale': f'{cs["pct"]}% of competitor listings make this claim. Whitespace to differentiate.',
                'evidence': f'Competitors claiming it: {", ".join(cs["topBrands"][:3]) or "none"}',
            })
        if cs['pct'] >= 60:
            saturation.append({
                'claim': cs['theme'],
                'label': cs['label'],
                'saturationPct': cs['pct'],
                'advice': 'Table stakes — must include but does not differentiate.',
            })
    whitespace_ops = whitespace_ops[:6]
    saturation = saturation[:6]

    # ── strategicRecommendations ──
    recs = []
    high_gaps = [g for g in voc_gap if g['gapSeverity'] == 'high']
    for g in high_gaps[:3]:
        recs.append({
            'type': 'VOC Gap',
            'badgeBg': '#fee2e2',
            'badgeColor': '#991b1b',
            'finding': f'{g["customerConcernPct"]}% of negative reviews cite "{g["vocTopic"]}" — only {g["addressedByCount"]} competitor(s) address this in their listing.',
            'implication': f'Lead with this in your bullets and A+ content. Direct anti-claim against the {g["customerConcernPct"]}% complaint pool wins the listing.',
        })
    for ws in whitespace_ops[:2]:
        recs.append({
            'type': 'Whitespace',
            'badgeBg': '#dbeafe',
            'badgeColor': '#1e40af',
            'finding': ws['opportunity'],
            'implication': ws['rationale'],
        })

    out = {
        'totalCompetitors': n_comp,
        'marketplace': MARKETPLACE[code],
        'currency': CURRENCY[code],
        'exportMonth': EXPORT_MONTH,
        'segment': seg.capitalize(),
        'competitors': competitors,
        'claimsMatrix': {
            'themes': themes,
            'rows': matrix_rows,
        },
        'claimsSummary': claims_summary,
        'vocGap': voc_gap,
        'whitespaceOpportunities': whitespace_ops,
        'saturation': saturation,
        'strategicRecommendations': recs,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f'Wrote {out_path}  ({os.path.getsize(out_path):,} bytes)')
    print(f'  competitors:{n_comp}  themes claimed (top 3):')
    for cs in claims_summary[:3]:
        print(f'    {cs["label"]}: {cs["count"]}/{n_comp} ({cs["pct"]}%)')
    print(f'  voc gaps: {len(voc_gap)}  whitespace: {len(whitespace_ops)}  saturation: {len(saturation)}')


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        main(sys.argv[1], sys.argv[2])
    else:
        # Run all 6 buckets
        for code in ('DE', 'FR', 'UK'):
            for seg in ('lure', 'electric'):
                print(f'\n=== {code} / {seg} ===')
                main(code, seg)
