# -*- coding: utf-8 -*-
"""
Builds _voc_sticky.html - the "VOC - sticky traps" tab fragment for
fruit-flies-eu-detailed.

Reviews: data/reviews/sticky-trap-reviews/*.xlsx - 6 ASINs, 1,993 reviews:
  DE (5): B0B9H1JJ83 500 + B0BD9759HW 474 + B0BZ44JFQS 322 + B0CNGLFVJT 500 +
          B0CQPVNFXZ 189  (Gelbsticker/Gelbtafel type - Trauermuecken)
  US (1): B09T3T1FYN 8    (plug-in UV + sticky pad)

Analytical labels/insights = Polish (AI-analyzed, the VOC exception to the
zero-hardcoded rule). Quotes = REAL verbatim snippets (DE + EN) auto-picked
from the scraped reviews - NOT translated (per user rule: only visible UI
labels and analytical examples are translated to Polish; review browser
content stays in original language).

Emits _voc_sticky.html (self-contained fragment) consumed by _build_standalone.py.
"""
import os, re, sys, json, glob
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
import openpyxl

BASE = os.path.dirname(os.path.abspath(__file__))
CONSOLE = os.path.abspath(os.path.join(BASE, '..', '..'))
VOC_TPL = os.path.join(CONSOLE, 'templates', 'tabs', 'u-reviews-voc', 'template.html')

# ── Load reviews (DE + US mix) ──────────────────────────────────────────────
reviews = []
for fp in sorted(glob.glob(os.path.join(BASE, 'data', 'reviews', 'sticky-trap-reviews', '*.xlsx'))):
    wb = openpyxl.load_workbook(fp, read_only=True); ws = wb.active
    rows = list(ws.iter_rows(values_only=True)); hdr = rows[0]
    idx = {h: i for i, h in enumerate(hdr)}
    # market code from filename: B0XXXXXXXX-{CC}-Reviews-...
    fname = os.path.basename(fp)
    m = re.match(r'^(B0[A-Z0-9]{8})-([A-Z]{2})-', fname)
    mkt = m.group(2) if m else '?'
    for r in rows[1:]:
        if r[idx['ASIN']] is None:
            continue
        rating = r[idx['Rating']]
        try:
            rating = int(float(rating))
        except (TypeError, ValueError):
            continue
        reviews.append({
            'asin': r[idx['ASIN']],
            'market': mkt,
            'r': rating,
            'title': (r[idx['Title']] or '').strip(),
            'content': (r[idx['Content']] or '').strip().replace('\n', ' '),
        })
    wb.close()

N = len(reviews)
star = [sum(1 for x in reviews if x['r'] == s) for s in range(1, 6)]
scraped_avg = round(sum(x['r'] for x in reviews) / N, 2)
n_de = sum(1 for x in reviews if x['market'] == 'DE')
n_us = sum(1 for x in reviews if x['market'] == 'US')

# Headline rating: use scraped avg from the large sample (N=1993 is
# statistically robust). No public X-Ray rating available for DE sticky-trap
# ASINs; stated in-app.
xray_avg = scraped_avg
n_asins = len(set(x['asin'] for x in reviews))

def text(x):
    return (x['title'] + ' ' + x['content']).lower()
TX = [(x, text(x)) for x in reviews]

def matches(pred):
    return [x for x, t in TX if pred(t)]

def share(pred):
    n = len(matches(pred))
    return n, f'{round(n / N * 100, 1)}%'

# ── Theme predicates (DE + EN keyword rules) ────────────────────────────────
P = {
    # Positive efficacy
    'efficacy_works': lambda t: any(w in t for w in [
        'funktioniert', 'wirkt', 'super', 'top produkt', 'perfekt', 'zuverlässig',
        'zufrieden', 'empfehlen', 'gut', 'macht was es soll', 'einwandfrei',
        'works', 'effective', 'does the job', 'brilliant', 'catches', 'trapping',
    ]) and not any(w in t for w in [
        'nicht funktioniert', 'funktioniert nicht', 'keinerlei wirkung', 'kein effekt',
        'doesn\'t work', 'did not work', 'not effective', 'not work',
    ]),
    # Negative efficacy
    'efficacy_fails': lambda t: any(w in t for w in [
        'funktioniert nicht', 'nicht funktioniert', 'keinerlei wirkung', 'kein effekt',
        'schrott', 'schlecht', 'nutzlos', 'aucun effet', 'nichts geholfen',
        'nicht wirksam', 'unwirksam', 'wirkt nicht', 'kein erfolg',
        'doesn\'t work', 'did not work', 'not work', 'useless', 'waste of money',
        'ineffective', 'not effective', 'not worth',
    ]),
    # Stickiness (adhesive quality)
    'not_sticky': lambda t: any(w in t for w in [
        'klebt nicht', 'nicht klebrig', 'zu wenig kleber', 'wenig klebstoff',
        'kleber lässt nach', 'löst sich', 'kleben zusammen', 'aneinander',
        'kleben aneinander', 'aneinander kleben', 'kleben an der',
        'not sticky', 'not very sticky', 'don\'t stick', 'peels off', 'come off',
    ]),
    'very_sticky': lambda t: any(w in t for w in [
        'sehr klebrig', 'super klebrig', 'stark klebrig', 'klebt gut', 'gut klebrig',
        'bleiben kleben', 'bleiben haften', 'haften bleiben',
        'very sticky', 'strong sticky', 'stick well', 'stays stuck',
    ]),
    # Product type / usage
    'plants_gnats': lambda t: any(w in t for w in [
        'trauermücken', 'trauermucken', 'blumentopf', 'blumentöpfe', 'blumentopfen',
        'pflanze', 'pflanzen', 'topfpflanze', 'zimmerpflanze', 'ziemiórki',
        'gnat', 'plant', 'houseplant', 'flower pot', 'potted plant', 'fungus',
    ]),
    'fruit_flies': lambda t: any(w in t for w in [
        'obstfliege', 'obstfliegen', 'küchenfliege', 'kuchenfliege', 'fruchtfliege',
        'fruchtfliegen', 'kleinfliege', 'kleinfliegen', 'mini mücke',
        'fruit fly', 'fruit flies', 'kitchen fly', 'fruit fli',
    ]),
    # Value
    'price_value': lambda t: any(w in t for w in [
        'preis leistung', 'preis-leistung', 'preiswert', 'günstig', 'guenstig',
        'zu teuer', 'billig', 'gutes preis',
        'value for money', 'good value', 'cheap', 'affordable', 'inexpensive',
    ]),
    'price_high': lambda t: any(w in t for w in [
        'zu teuer', 'überteuert', 'teuer für', 'zu hoch', 'nicht günstig',
        'expensive', 'overpriced', 'too pricey', 'not worth the price',
    ]),
    # Size / form factor
    'size_issue': lambda t: any(w in t for w in [
        'zu groß', 'zu gross', 'etwas groß', 'zu klein', 'kleiner als',
        'grösse', 'grosse', 'größe',
        'too big', 'too small', 'wrong size', 'sizing',
    ]),
    # Ease
    'ease': lambda t: any(w in t for w in [
        'einfach', 'unkompliziert', 'schnell aufgebaut', 'einfach anzuwenden',
        'praktisch', 'leicht zu', 'kinderleicht',
        'easy', 'simple', 'straightforward', 'quick to use', 'user-friendly',
    ]),
    # Repeat purchase
    'repeat': lambda t: any(w in t for w in [
        'gern wieder', 'gerne wieder', 'kaufe wieder', 'immer wieder', 'nachbestellt',
        'jedes jahr', 'jeden sommer', 'wieder kaufen', 'wieder bestellt',
        'buy again', 'ordered more', 'every year', 'every summer', 'this is my second',
        'buying more',
    ]),
    # Fast results
    'fast_result': lambda t: any(w in t for w in [
        'sofort', 'innerhalb weniger', 'schon nach', 'nach kurzer zeit',
        'schnell voll', 'innerhalb einer woche', 'nach einer woche',
        'immediate', 'within hours', 'within a week', 'right away', 'instantly',
        'from the first minute',
    ]),
    # Aesthetics
    'aesthetic': lambda t: any(w in t for w in [
        'formschön', 'formschoen', 'unauffällig', 'diskret', 'hübsch',
        'discreet', 'looks nice', 'attractive', 'blend in',
    ]),
}
STYLE = {
    'efficacy_fails': 'pill-red', 'not_sticky': 'pill-red', 'price_high': 'pill-amber',
    'size_issue': 'pill-orange', 'efficacy_works': 'pill-blue', 'very_sticky': 'pill-blue',
    'ease': 'pill-blue', 'repeat': 'pill-blue', 'plants_gnats': 'pill-purple',
    'fruit_flies': 'pill-purple', 'price_value': 'pill-blue', 'fast_result': 'pill-blue',
    'aesthetic': 'pill-blue',
}
LABEL = {
    'efficacy_works': 'Skuteczny', 'efficacy_fails': 'Nieskuteczny',
    'not_sticky': 'Słaba lepkość', 'very_sticky': 'Mocno klejący',
    'plants_gnats': 'Rośliny / ziemiórki', 'fruit_flies': 'Muszki owocówki',
    'price_value': 'Dobry stosunek ceny', 'price_high': 'Za drogie',
    'size_issue': 'Problem z rozmiarem', 'ease': 'Łatwość użycia',
    'repeat': 'Ponowny zakup', 'fast_result': 'Szybki efekt',
    'aesthetic': 'Dyskretny wygląd',
}

def pick_quotes(pred, n=4, ratings=None, maxlen=200):
    """Return up to n REAL verbatim snippets (DE + EN mixed) matching pred,
    from the given rating band. NOT translated."""
    pool = [x for x, t in TX if pred(t) and (ratings is None or x['r'] in ratings)
            and len(x['content']) >= 25]
    pool.sort(key=lambda x: abs(len(x['content']) - 120))
    out, seen = [], set()
    for x in pool:
        c = x['content'].strip()
        if len(c) > maxlen:
            c = c[:maxlen].rsplit(' ', 1)[0] + '…'
        key = c[:40].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) >= n:
            break
    return out

# ── Customer Profile stacked bars ────────────────────────────────────────────
def cp(buckets):
    labels, pos, neg = [], [], []
    for lab, pred in buckets:
        m = matches(pred)
        labels.append(lab)
        pos.append(sum(1 for x in m if x['r'] >= 4))
        neg.append(sum(1 for x in m if x['r'] <= 3))
    return {'labels': labels, 'pos': pos, 'neg': neg}

cpWho = cp([
    ('Właściciele roślin', P['plants_gnats']),
    ('Problem w kuchni', P['fruit_flies']),
    ('Wartość / oszczędny', P['price_value']),
    ('Powracający klienci', P['repeat']),
])
cpWhen = cp([
    ('Szybki efekt', P['fast_result']),
    ('Nagła inwazja', lambda t: any(w in t for w in ['plage', 'invasion', 'befall', 'überall', 'ueberall', 'infestation', 'suddenly'])),
    ('Co roku', P['repeat']),
    ('Sezonowo', lambda t: any(w in t for w in ['sommer', 'summer', 'saison', 'winter'])),
])
cpWhere = cp([
    ('Doniczki / rośliny', P['plants_gnats']),
    ('Kuchnia', lambda t: any(w in t for w in ['küche', 'kueche', 'kitchen'])),
    ('Okno / parapet', lambda t: any(w in t for w in ['fensterscheibe', 'fenster', 'window'])),
    ('Kosz / bio', lambda t: any(w in t for w in ['bio', 'müll', 'muell', 'kompost', 'bin', 'compost'])),
])
cpWhat = cp([
    ('Ziemiórki (rośliny)', P['plants_gnats']),
    ('Muszki owocówki', P['fruit_flies']),
    ('Inne małe muchy', lambda t: any(w in t for w in ['kleinfliegen', 'kleine fliegen', 'mini mücken', 'small flies', 'insect', 'bug'])),
])

# ── Usage scenarios / motivation / expectations ─────────────────────────────
def row(label, reason, pred):
    _, p = share(pred)
    return {'label': label, 'reason': reason, 'pct': p}

usageScenarios = sorted([
    row('Rośliny doniczkowe (ziemiórki)', 'Najczęstsze zastosowanie: żółte sticker wetknięte w ziemię doniczek, do walki z Trauermücken (ziemiórkami).', P['plants_gnats']),
    row('Kuchnia (owoce / kosz)', 'Muszki owocówki wokół owoców, kosza, zlewu.', P['fruit_flies']),
    row('Parapet / okno', 'Naklejane na szybę tam, gdzie owady się gromadzą przy świetle.', lambda t: any(w in t for w in ['fensterscheibe', 'fenster', 'window'])),
    row('Bio-odpady / kompost', 'Kosz bio, kompostownik, resztki jedzenia jako źródło.', lambda t: any(w in t for w in ['bio', 'müll', 'muell', 'kompost', 'bin'])),
], key=lambda x: float(x['pct'][:-1]), reverse=True)

buyersMotivation = sorted([
    row('Inwazja ziemiórek przy roślinach', 'Nagły wysyp much wokół roślin doniczkowych - główny wyzwalacz zakupu.', lambda t: P['plants_gnats'](t) and any(w in t for w in ['plage', 'befall', 'invasion', 'suddenly', 'überall'])),
    row('Tania alternatywa dla sprayów', 'Chęć taniego, nietoksycznego rozwiązania zamiast insektycydów.', P['price_value']),
    row('Prosta obsługa (bez elektryki, bez baterii)', 'Passive: wetknąć i zapomnieć. Bez prądu, bez wymiany baterii.', P['ease']),
    row('Bezpieczne dla dzieci i zwierząt', 'Brak substancji chemicznych - komfort psychiczny w domu z dziećmi lub pupilami.', lambda t: any(w in t for w in ['kind', 'children', 'haustier', 'pet', 'sicher', 'safe'])),
], key=lambda x: float(x['pct'][:-1]), reverse=True)

customerExpectations = sorted([
    row('Mocniejszy klej / trwałość', 'Oczekiwanie że lep nie odpadnie, nie skleją się między sobą, złapane owady zostaną.', P['not_sticky']),
    row('Mniejsze rozmiary do doniczek', 'Sticker często za duży do małych doniczek - potrzeba mniejszych wariantów.', P['size_issue']),
    row('Szybszy widoczny efekt', 'Frustracja gdy efekt trwa dłużej niż tydzień.', lambda t: any(w in t for w in ['zu langsam', 'dauert', 'too slow', 'takes time']) or 'nach einer woche' in t),
    row('Trwalsze działanie sezonowo', 'Sticker traci lepkość / kolor za szybko przy dłuższym użyciu.', lambda t: any(w in t for w in ['lässt nach', 'laesst nach', 'nachlassen', 'fade', 'weeks only'])),
    row('Lepszy stosunek cena/ilość', 'Postrzegane jako drogie względem prostoty produktu.', P['price_high']),
], key=lambda x: float(x['pct'][:-1]), reverse=True)

# ── Sentiment topics ─────────────────────────────────────────────────────────
def topic(label, pred, bullets, qratings):
    _, p = share(pred)
    return {'label': label, 'reason': bullets[0], 'pct': p,
            'bullets': bullets, 'quotes': pick_quotes(pred, 4, qratings)}

negativeTopics = [
    topic('Zero efektu / muchy ignorują', P['efficacy_fails'],
          ['Najczęstsza skarga 1-2★: mimo zainstalowania, muchy się nie łapią.',
           'Częste niemieckie określenie: "Schrott", "keinerlei Wirkung".',
           'Silnie skorelowane ze złym umiejscowieniem, brakiem światła (dla UV) lub kończącym się sezonem.'], (1, 2, 3)),
    topic('Sticker klei się do siebie / odpada', P['not_sticky'],
          ['Recenzje wskazują że sticker klei się do sąsiedniego arkusza w opakowaniu.',
           'Kleber schwacher niż oczekiwany - muchy się nie przyklejają lub odpadają.',
           'Podważa podstawową funkcję produktu.'], (1, 2, 3)),
    topic('Za drogie za to co dostaję', P['price_high'],
          ['Klienci porównują z konkurencją i uznają za overpriced.',
           'Postrzeganie: "Gleiche Menge gibt es deutlich günstiger".'], (1, 2, 3)),
    topic('Problem z rozmiarem stickerów', P['size_issue'],
          ['Wielu użytkowników skarży się że sticker za duży do małych doniczek.',
           'Trudność w odklejaniu od arkusza / pozycjonowaniu w ciasnych miejscach.'], (1, 2, 3)),
]
positiveTopics = [
    topic('Działa - kończy problem z muszkami', P['efficacy_works'],
          ['Dominujący wątek 4-5★: sticker działa jak reklamowany, muchy się łapią.',
           'Niemieckie określenia: "funktioniert einwandfrei", "macht was es soll".',
           'Silna korelacja z zastosowaniem przy roślinach (Trauermücken).'], (4, 5)),
    topic('Skuteczny na ziemiórki (rośliny)', P['plants_gnats'],
          ['Główne zastosowanie w tym segmencie: żółty sticker w ziemi doniczkowej.',
           'Recenzje pokazują "nach einer Woche schwarz vor Trauermücken".',
           'Rynek roślinny bardzo silny - wyraźnie różny use case od kuchennego.'], (4, 5)),
    topic('Bardzo lepki - muchy trzymają się', P['very_sticky'],
          ['Klienci chwalą siłę kleju - "bleiben dran kleben".',
           'Kontrast do skarg 1★ o słabej lepkości - polaryzacja produktu.'], (4, 5)),
    topic('Ponowny zakup - gerne wieder', P['repeat'],
          ['Silny sygnał retencji: "gern wieder", "ordered more".',
           'Powtarzalny zakup sezonowy - potencjał subskrypcji / większych opakowań.'], (4, 5)),
    topic('Szybki efekt widoczny w dniach', P['fast_result'],
          ['Klienci raportują widoczny efekt "sofort", "innerhalb weniger Tage".',
           'W przeciwieństwie do pułapek z octem, sticker nie wymaga cierpliwości.'], (4, 5)),
]

def insight(t, bg, fg, finding, impl):
    return {'type': t, 'badgeBg': bg, 'badgeColor': fg, 'finding': finding, 'implication': impl}

negativeInsights = [
    insight('Skuteczność / lepkość', '#fee2e2', '#991b1b',
            'Najczęstsza skarga 1-2★ to zero efektu ("keinerlei Wirkung") lub słaba lepkość.',
            'Wzmocnić klej, lepiej oddzielać arkusze w opakowaniu, komunikować "starker Kleber" w bulletach.'),
    insight('Rozmiar produktu', '#ffedd5', '#9a3412',
            'Sticker często za duży do małych doniczek (~20-25 cm średnicy).',
            'Wprowadzić mini wariant dla doniczek 10-15 cm, lub perforację do dzielenia.'),
    insight('Cena / wartość', '#fef3c7', '#92400e',
            'Klienci porównują z tańszą konkurencją i uznają za overpriced.',
            'Uzasadnić cenę jakością (mocniejszy klej, dłuższa trwałość, atrakcyjny design) lub uruchomić większy multipack z lepszym €/szt.'),
    insight('Oczekiwania sezonu', '#ede9fe', '#5b21b6',
            'Skargi że sticker "traci moc" po 2-3 tygodniach - naturalne dla żółtych lepów, ale klienci nie wiedzą.',
            'Na listingu: "wymieniać co 3-4 tyg. w wysokim sezonie" - edukacja + up-sell subskrypcji.'),
]
positiveInsights = [
    insight('Rośliny doniczkowe (główny rynek)', '#dcfce7', '#166534',
            'Segment ziemiórek to najsilniejszy driver zakupu - jasny use case.',
            'W tytule / A+ eksponować "Trauermücken / Blumentopf / Zimmerpflanzen" - to jest core keyword pool.'),
    insight('Retencja / powtarzalny zakup', '#dbeafe', '#1e40af',
            'Klienci wracają regularnie ("gern wieder") - segment sezonowo-powtarzalny.',
            'Subskrypcja lub duże opakowania (60-100 szt.) z lepszym €/szt.'),
    insight('Passive vs active', '#dcfce7', '#166534',
            'Brak elektryki, brak baterii, brak konserwacji - kluczowa zaleta dla części klientów.',
            'W komunikacji przeciwstawiać się do lampom UV: "kein Strom, keine Batterie, kein Lärm".'),
    insight('Dyskretny wygląd', '#dbeafe', '#1e40af',
            'Niektórzy chwalą "formschön" - wariant designerski dla wnętrz.',
            'Wariant premium (kolorowe, w kształty) dla klientów estetyzujących.'),
]

# ── Tag reviews for the browser (original content, no translation) ──────────
themeFilters = [{'value': k, 'label': LABEL[k]} for k in [
    'efficacy_works', 'efficacy_fails', 'not_sticky', 'very_sticky',
    'plants_gnats', 'fruit_flies', 'price_value', 'price_high',
    'size_issue', 'ease', 'repeat', 'fast_result', 'aesthetic',
]]
tagStyles = {k: STYLE[k] for k in STYLE}
reviews_out = []
for x, t in TX:
    tags = [k for k, pred in P.items() if pred(t)]
    body = x['content'] if len(x['content']) >= 8 else (x['title'] or x['content'])
    reviews_out.append({'r': x['r'], 't': body[:600], 'tags': tags})

cpSummary = (
    f"Kupujący sticker traps to głównie <b>właściciele roślin doniczkowych</b> "
    f"walczący z ziemiórkami (Trauermücken), rzadziej gospodarstwa domowe z problemem "
    f"muszek owocówek w kuchni. Segment silnie <b>niemieckojęzyczny</b> "
    f"({n_de:,} DE + {n_us} US recenzji na {n_asins} ASINów). "
    f"Sentyment: <b>{round((star[3]+star[4])/N*100)}%</b> recenzji 4-5★ vs "
    f"<b>{round((star[0]+star[1]+star[2])/N*100)}%</b> 1-3★; głównym driverem satysfakcji "
    f"jest siła kleju i skuteczność na Trauermücken."
)
csSummary = (
    'Recenzje spolaryzowane wokół dwóch osi: <b>siła kleju</b> (klei czy odpada) '
    'i <b>skuteczność na Trauermücken</b> (główne zastosowanie). Ten sam produkt zbiera '
    '"keinerlei Wirkung" i "nach einer Woche schwarz vor Trauermücken". Wtórne skargi: '
    'rozmiar stickerów za duży do małych doniczek, cena względem konkurencji.'
)

VOC_DATA = {
    'countryName': 'Niemcy (główny rynek) + USA',
    'countryCode': 'DE',
    'countryTld': 'de',
    'segmentName': 'Sticky Traps', 'currency': '€',
    'productCount': n_asins, 'totalReviews': N, 'avgRating': xray_avg,
    'starDist': star,
    'cpSummary': cpSummary, 'cpWho': cpWho, 'cpWhen': cpWhen, 'cpWhere': cpWhere, 'cpWhat': cpWhat,
    'usageScenarios': usageScenarios,
    'csSummary': csSummary,
    'negativeTopics': negativeTopics, 'positiveTopics': positiveTopics,
    'negativeInsights': negativeInsights, 'positiveInsights': positiveInsights,
    'buyersMotivation': buyersMotivation, 'customerExpectations': customerExpectations,
    'themeFilters': themeFilters, 'tagStyles': tagStyles,
    'reviews': reviews_out,
}

# ── Reuse the canonical template + polish transform ─────────────────────────
def extract_template(path):
    html = open(path, encoding='utf-8').read()
    css = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    body = re.search(r'<script>\s*\(function\(\)\{(.*)\}\)\(\);\s*</script>', html, re.S).group(1)
    return css, body

def to_named_renderer(body, fn_name, root_var_line):
    body = body.replace('var D = window._TAB_DATA;', '', 1)
    body = body.replace(root_var_line, '', 1)
    return 'function ' + fn_name + '(D, root){\n' + body + '\n}'

VOC_CSS, VOC_BODY = extract_template(VOC_TPL)
VOC_FN = to_named_renderer(VOC_BODY, 'renderReviewsSticky',
                           "var root = document.getElementById('u-reviews-voc-root');")

# Patch: headline uses scraped avg (large sample), keep the star bar visible
# (this dataset IS the population sample - no X-Ray comparison to disclaim).
VOC_PATCH = [
    ("""  var total = D.totalReviews;
  var pos = (D.starDist[3] || 0) + (D.starDist[4] || 0);
  var neg = (D.starDist[0] || 0) + (D.starDist[1] || 0) + (D.starDist[2] || 0);
  var posPct = (pos / total * 100).toFixed(1);
  var negPct = (neg / total * 100).toFixed(1);
  var ratio = neg > 0 ? (pos / neg).toFixed(1) : 'N/A';
  var segLower = segment ? esc(segment.toLowerCase()) : '';

  h += '<h2 style="margin-bottom:6px">Reviews VOC' + (segment ? ' · ' + esc(segment) : '') + (countryName ? ' · ' + esc(countryName) : '') + '</h2>';
  h += '<p style="margin:0 0 14px;color:#64748b;font-size:.78rem">Based on <b>' + total.toLocaleString() + '</b> reviews' + (segment || countryCode ? ' scraped from the top ' + (segment ? esc(segment.toLowerCase()) + ' products' : 'products') + (countryCode ? ' on amazon.' + esc(countryCode.toLowerCase()) : '') : '') + '.</p>';
  h += '<div class="kpis" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:14px">';
  h += '<div class="kpi"><div class="kpi-v">' + total.toLocaleString() + '</div><div class="kpi-l">Total Reviews</div></div>';
  h += '<div class="kpi"><div class="kpi-v">' + ratio + ' : 1</div><div class="kpi-l">Sentiment Ratio (pos:neg)</div></div>';
  h += '<div class="kpi"><div class="kpi-v" style="color:#16a34a">' + posPct + '%</div><div class="kpi-l">Positive (4★+5★)</div></div>';
  h += '<div class="kpi"><div class="kpi-v" style="color:#dc2626">' + negPct + '%</div><div class="kpi-l">Negative (1★–3★)</div></div>';
  h += '</div>';""",
     """  var total = D.totalReviews;
  var pos = (D.starDist[3] || 0) + (D.starDist[4] || 0);
  var neg = (D.starDist[0] || 0) + (D.starDist[1] || 0) + (D.starDist[2] || 0);
  var posPct = (pos / total * 100).toFixed(1);
  var negPct = (neg / total * 100).toFixed(1);
  var ratio = neg > 0 ? (pos / neg).toFixed(1) : 'N/A';

  h += '<h2 style="margin-bottom:6px">Recenzje (VOC) · Sticky Traps' + (countryName ? ' · ' + esc(countryName) : '') + '</h2>';
  h += '<p style="margin:0 0 14px;color:#64748b;font-size:.78rem">Analiza jakościowa (motywy, cytaty) na podstawie <b>' + total.toLocaleString() + '</b> recenzji zebranych z ' + (D.productCount || '') + ' najlepszych produktów sticky trap (5 amazon.de + 1 amazon.com). Recenzje w oryginalnym języku (DE + EN) - nie tłumaczone.</p>';
  h += '<div class="kpis" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:14px">';
  h += '<div class="kpi"><div class="kpi-v">' + total.toLocaleString() + '</div><div class="kpi-l">Analizowane recenzje</div></div>';
  h += '<div class="kpi"><div class="kpi-v">' + (D.avgRating ? (+D.avgRating).toFixed(2) + ' ★' : '-') + '</div><div class="kpi-l">Średnia ocena (próbka)</div></div>';
  h += '<div class="kpi"><div class="kpi-v">' + ratio + ' : 1</div><div class="kpi-l">Sentyment (poz:neg)</div></div>';
  h += '<div class="kpi"><div class="kpi-v" style="color:#16a34a">' + posPct + '%</div><div class="kpi-l">Pozytywne (4★+5★)</div></div>';
  h += '<div class="kpi"><div class="kpi-v" style="color:#dc2626">' + negPct + '%</div><div class="kpi-l">Negatywne (1★–3★)</div></div>';
  h += '</div>';"""),
]
VOC_STR = [
    ("No data loaded for this tab.", "Brak danych VOC dla tego rynku."),
    ("No review data loaded", "Brak danych recenzji"),
    ("Star Distribution", "Rozkład gwiazdek"),
    (">Customer Insights<", ">Wnioski o klientach<"),
    (">Review Browser<", ">Przeglądarka recenzji<"),
    (">Customer Profile</a>", ">Profil klienta</a>"),
    (">Usage Scenario</a>", ">Scenariusz użycia</a>"),
    (">Customer Sentiment</a>", ">Sentyment klientów</a>"),
    (">Buyers Motivation</a>", ">Motywacja kupujących</a>"),
    (">Customer Expectations</a>", ">Oczekiwania klientów</a>"),
    (">Customer Profile</div>", ">Profil klienta</div>"),
    (">Usage Scenario</div>", ">Scenariusz użycia</div>"),
    (">Customer Sentiment</div>", ">Sentyment klientów</div>"),
    (">Buyers Motivation</div>", ">Motywacja kupujących</div>"),
    (">Customer Expectations</div>", ">Oczekiwania klientów</div>"),
    (">Usage Scenario</th>", ">Scenariusz użycia</th>"),
    (">Buyers Motivation</th>", ">Motywacja kupujących</th>"),
    (">Unmet Need</th>", ">Niezaspokojona potrzeba</th>"),
    (">Reason</th>", ">Powód</th>"),
    (">Percentage</th>", ">Udział %</th>"),
    (">Negative Feedback Topic</th>", ">Temat negatywnej opinii</th>"),
    (">Reasons for Negative Feedback</th>", ">Powody negatywnej opinii</th>"),
    (">Positive Feedback Topic</th>", ">Temat pozytywnej opinii</th>"),
    (">Reasons for Positive Feedback</th>", ">Powody pozytywnej opinii</th>"),
    (">Negative Review Insights · Strategy<", ">Wnioski z negatywnych recenzji · Strategia<"),
    (">Positive Review Insights · Strategy<", ">Wnioski z pozytywnych recenzji · Strategia<"),
    (">Analysis Type</th>", ">Typ analizy</th>"),
    (">Finding (from 1★+2★ reviews)</th>", ">Ustalenie (z recenzji 1★+2★)</th>"),
    (">Finding (from 4★+5★ reviews)</th>", ">Ustalenie (z recenzji 4★+5★)</th>"),
    (">Strategic Implication</th>", ">Implikacja strategiczna</th>"),
    ("reviews 4-5 stars", "recenzje 4-5 gwiazdek"),
    ("reviews 1-3 stars", "recenzje 1-3 gwiazdek"),
    ("Review Browser <span", "Przeglądarka recenzji <span"),
    ("Filter by rating, theme, or keyword", "Filtruj wg oceny, tematu lub słowa kluczowego"),
    (">All Ratings<", ">Wszystkie oceny<"),
    (">All Themes<", ">Wszystkie tematy<"),
    ("placeholder=\"Search keyword...\"", "placeholder=\"Szukaj słowa kluczowego...\""),
    (">Clear</button>", ">Wyczyść</button>"),
    ("'Showing ' + filtered.length + ' of ' + reviews.length + ' reviews'",
     "'Wyświetlono ' + filtered.length + ' z ' + reviews.length + ' recenzji'"),
    ("Showing first 1000 of ", "Pierwsze 1000 z "),
    (". Use filters/search to reach the rest.", ". Użyj filtrów/wyszukiwarki, aby dotrzeć do pozostałych."),
]

def apply_patches(js, pairs):
    for before, after in pairs:
        if before not in js:
            raise SystemExit('VOC patch anchor not found - template changed? starts: ' + before[:70])
        js = js.replace(before, after)
    return js

def apply_translations(js, pairs):
    for en, pl in pairs:
        js = js.replace(en, pl)
    return js

VOC_FN = apply_patches(VOC_FN, VOC_PATCH)
VOC_FN = apply_translations(VOC_FN, VOC_STR)

# ── Emit self-contained fragment ────────────────────────────────────────────
FRAG = (
    '<style>\n' + VOC_CSS + '\n</style>\n'
    '<div class="ms2-pillrow" style="max-width:1200px;margin:0 auto;padding:20px 24px 0">'
    '<span class="ms2-pilllabel">Rynki (mix):</span>'
    '<button class="ms2-pill active" disabled>Niemcy (' + str(n_de) + ') + USA (' + str(n_us) + ')</button>'
    '<span style="font-size:.68rem;color:#94a3b8;margin-left:8px">Zebrano ' + str(N) + ' recenzji z ' + str(n_asins) + ' ASINów sticky trap</span>'
    '</div>\n'
    '<div id="u-reviews-voc-sticky-root" style="max-width:1200px;margin:0 auto;padding:8px 24px 40px"></div>\n'
    '<script>\n'
    'var VOC_DATA_STICKY = ' + json.dumps(VOC_DATA, ensure_ascii=False) + ';\n'
    + VOC_FN + '\n'
    'window.__vocStickyRender = function(){ renderReviewsSticky(VOC_DATA_STICKY, document.getElementById("u-reviews-voc-sticky-root")); };\n'
    '</script>\n'
)
FRAG = FRAG.replace('—', '-').replace('–', '-')

out = os.path.join(BASE, '_voc_sticky.html')
open(out, 'w', encoding='utf-8').write(FRAG)

print(f'_voc_sticky.html: {os.path.getsize(out):,} bytes')
print(f'reviews={N}  (DE={n_de}, US={n_us}) across {n_asins} ASINs')
print(f'scraped_avg={scraped_avg}  star={star}')
print(f'positives(4-5)={star[3]+star[4]} negatives(1-3)={star[0]+star[1]+star[2]}')
print('negativeTopics pct:', [(t['label'], t['pct'], len(t['quotes'])) for t in negativeTopics])
print('positiveTopics pct:', [(t['label'], t['pct'], len(t['quotes'])) for t in positiveTopics])
