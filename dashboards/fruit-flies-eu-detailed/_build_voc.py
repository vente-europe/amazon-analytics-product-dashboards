# -*- coding: utf-8 -*-
"""
Builds _voc.html - the "Recenzje (VOC)" tab fragment for fruit-flies-eu-detailed.

UK-ONLY (that is the only market we have scraped reviews for). Reuses the
canonical templates/tabs/u-reviews-voc/template.html renderer + provecta's Polish
translation machinery (patched: headline rating from X-Ray, scraped star-bar
hidden - our 197-review sample skews critical vs the X-Ray listing rating 3.9).

Reviews: data/reviews/*.xlsx (B07PN3XFD5 PIC 191 + B0GR8MRDR2 HIULLEN 6 = 197,
UK, amazon.co.uk). Analytical labels/insights = Polish (AI-analyzed, the VOC
exception to the zero-hardcoded rule). Quotes = REAL verbatim English snippets
auto-picked from the scraped reviews (no fabrication). Percentages computed from
keyword tallies over the actual review text.

Emits _voc.html (self-contained fragment) consumed by _build_standalone.py.
"""
import os, re, sys, json, glob
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
import openpyxl

BASE = os.path.dirname(os.path.abspath(__file__))
CONSOLE = os.path.abspath(os.path.join(BASE, '..', '..'))
VOC_TPL = os.path.join(CONSOLE, 'templates', 'tabs', 'u-reviews-voc', 'template.html')

# ── Load reviews ────────────────────────────────────────────────────────────
reviews = []
for fp in sorted(glob.glob(os.path.join(BASE, 'data', 'reviews', '*.xlsx'))):
    wb = openpyxl.load_workbook(fp, read_only=True); ws = wb.active
    rows = list(ws.iter_rows(values_only=True)); hdr = rows[0]
    idx = {h: i for i, h in enumerate(hdr)}
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
            'r': rating,
            'title': (r[idx['Title']] or '').strip(),
            'content': (r[idx['Content']] or '').strip().replace('\n', ' '),
        })
    wb.close()

N = len(reviews)
star = [sum(1 for x in reviews if x['r'] == s) for s in range(1, 6)]
scraped_avg = round(sum(x['r'] for x in reviews) / N, 2)

# Headline rating from X-Ray (UK), review-count-weighted across the two ASINs.
# B07PN3XFD5 3.9 (949), B0GR8MRDR2 3.4 (15) -> ~3.9
XRAY = {'B07PN3XFD5': (3.9, 949), 'B0GR8MRDR2': (3.4, 15)}
_w = sum(v[0] * v[1] for v in XRAY.values()); _n = sum(v[1] for v in XRAY.values())
xray_avg = round(_w / _n, 1)
xray_total = _n

def text(x):
    return (x['title'] + ' ' + x['content']).lower()
TX = [(x, text(x)) for x in reviews]

def matches(pred):
    return [x for x, t in TX if pred(t)]

def share(pred):
    n = len(matches(pred))
    return n, f'{round(n / N * 100, 1)}%'

# ── Theme predicates (keyword rules over real text) ─────────────────────────
P = {
    'efficacy_fails': lambda t: any(w in t for w in ["doesn't work", "does not work", "didn t work", "didnt work",
        "did not work", "not work", "useless", "waste of money", "no flies", "caught 0", "caught none",
        "rubbish", "not worth", "don't buy", "dont buy", "ineffective", "no luck"]),
    'not_sticky': lambda t: any(w in t for w in ["fly off", "flew off", "fly right", "fly back", "back off",
        "not stick", "not sticky", "not very sticky", "doesn't stick", "don't stick", "drag itself",
        "not strong enough", "nothing sticks", "not sticky enough"]),
    'efficacy_works': lambda t: (any(w in t for w in ["works", "worked", "effective", "does the job",
        "did the job", "brilliant", "really works", "so pleased", "got rid", "cleared", "caught a lot",
        "catches", "does what it says", "recommend"]) and not any(w in t for w in ["doesn't work",
        "did not work", "not work", "didnt work", "didn t work"])),
    'patience': lambda t: any(w in t for w in ["few days", "couple of days", "third day", "3rd day",
        "2 days", "two days", "be patient", "patience", "took a while", "takes a while", "wait", "at first",
        "days before", "eventually", "within hours", "within a week", "week or two"]),
    'smell': lambda t: any(w in t for w in ["smell", "stink", "reek", "vinegar through", "reeks"]),
    'price': lambda t: any(w in t for w in ["expensive", "overpriced", "waste of money", "pricey",
        "value for money", "good value", "cheap", "cost", "price"]),
    'diy': lambda t: any(w in t for w in ["cider vinegar", "own trap", "homemade", "home made", "make my own",
        "made my own", "jar", "washing up liquid", "cling film", "own cider"]),
    'ease': lambda t: any(w in t for w in ["easy", "simple", "set up", "set-up", "assemble", "easy to use"]),
    'repeat': lambda t: any(w in t for w in ["every year", "every summer", "each summer", "second year",
        "2nd year", "3rd year", "third year", "buy every", "ordered more", "bought again", "this is my second",
        "buy them every"]),
    'plants': lambda t: any(w in t for w in ["plant", "gnat", "houseplant", "house plant"]),
    'seasonal': lambda t: any(w in t for w in ["summer", "weather", "winter", "cold", "end of summer",
        "autumn", "this time of year"]),
}
STYLE = {
    'efficacy_fails': 'pill-red', 'not_sticky': 'pill-red', 'smell': 'pill-orange',
    'price': 'pill-amber', 'diy': 'pill-amber', 'patience': 'pill-purple',
    'efficacy_works': 'pill-blue', 'ease': 'pill-blue', 'repeat': 'pill-blue',
    'plants': 'pill-blue', 'seasonal': 'pill-purple',
}
LABEL = {
    'efficacy_works': 'Skuteczny', 'efficacy_fails': 'Nieskuteczny', 'not_sticky': 'Słaba lepkość',
    'smell': 'Zapach octu', 'price': 'Cena / wartość', 'diy': 'Domowy zamiennik',
    'patience': 'Wymaga cierpliwości', 'ease': 'Łatwość użycia', 'repeat': 'Ponowny zakup',
    'plants': 'Rośliny / ziemiórki', 'seasonal': 'Sezonowość',
}

def pick_quotes(pred, n=4, ratings=None, maxlen=200):
    """Return up to n REAL verbatim snippets (English) matching pred, from the
    given rating band, preferring substantive-but-not-huge content."""
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

# ── Customer Profile stacked bars (grounded in keyword buckets × rating) ─────
def cp(buckets):
    labels, pos, neg = [], [], []
    for lab, pred in buckets:
        m = matches(pred)
        labels.append(lab)
        pos.append(sum(1 for x in m if x['r'] >= 4))
        neg.append(sum(1 for x in m if x['r'] <= 3))
    return {'labels': labels, 'pos': pos, 'neg': neg}

cpWho = cp([
    ('Problem w kuchni', lambda t: 'kitchen' in t or 'fruit' in t),
    ('Właściciele roślin', lambda t: 'plant' in t or 'gnat' in t),
    ('Mieszkanie / wynajem', lambda t: 'flat' in t or 'apartment' in t or 'apartement' in t),
    ('Powracający klienci', P['repeat']),
])
cpWhen = cp([
    ('Lato / szczyt', lambda t: 'summer' in t),
    ('Chłodniejsza pora', lambda t: any(w in t for w in ['cold', 'winter', 'end of summer', 'weather', 'autumn'])),
    ('Co roku', P['repeat']),
    ('Nagła inwazja', lambda t: any(w in t for w in ['infestation', 'invasion', 'overrun', 'influx', 'suddenly', 'out of nowhere', 'came from'])),
])
cpWhere = cp([
    ('Kuchnia', lambda t: 'kitchen' in t),
    ('Rośliny doniczkowe', lambda t: 'plant' in t or 'gnat' in t),
    ('Mieszkanie', lambda t: 'flat' in t or 'apartment' in t),
    ('Kosz / zlew / bio', lambda t: any(w in t for w in ['bin', 'drain', 'sink', 'food waste', 'compost'])),
    ('Sypialnia / pokój', lambda t: 'bedroom' in t or ' room' in t),
])
cpWhat = cp([
    ('Muszki owocówki', lambda t: 'fruit fl' in t or 'fruitfl' in t),
    ('Ziemiórki (rośliny)', lambda t: 'gnat' in t or ('plant' in t and 'fl' in t)),
    ('Inne muchy / owady', lambda t: any(w in t for w in ['house fl', 'normal fl', 'drain fl', 'spider', 'insect', 'bug'])),
])

# ── Usage scenarios / motivation / expectations (Polish + tallied pct) ──────
def row(label, reason, pred):
    _, p = share(pred)
    return {'label': label, 'reason': reason, 'pct': p}

usageScenarios = sorted([
    row('Kuchnia (owoce / kosz)', 'Muszki owocówki wokół owoców, kosza i zlewu - najczęstsze zastosowanie.', lambda t: 'kitchen' in t or 'fruit fl' in t),
    row('Rośliny doniczkowe', 'Ziemiórki wokół roślin doniczkowych i doniczek.', lambda t: 'plant' in t or 'gnat' in t),
    row('Mieszkanie / wynajem', 'Małe mieszkania i wynajem, gdzie liczy się dyskretny wygląd.', lambda t: 'flat' in t or 'apartment' in t),
    row('Kosz / zlew / odpady bio', 'Źródła przy koszu na bio, zlewie i odpadach.', lambda t: any(w in t for w in ['bin', 'drain', 'sink', 'compost', 'food waste'])),
], key=lambda x: float(x['pct'][:-1]), reverse=True)

buyersMotivation = sorted([
    row('Inwazja much owocówek', 'Nagły wysyp much owocówek jako główny wyzwalacz zakupu.', lambda t: any(w in t for w in ['infestation', 'overrun', 'influx', 'invasion', 'lots of', 'loads of', 'so many'])),
    row('Owoce / kosz na wierzchu', 'Owoce zostawione na wierzchu lub pełny kosz jako źródło.', lambda t: 'fruit' in t and ('left' in t or 'bowl' in t or 'ripe' in t or 'kitchen' in t)),
    row('Muszki wokół roślin', 'Ziemiórki od roślin doniczkowych.', lambda t: 'plant' in t or 'gnat' in t),
    row('Gotowa alternatywa dla domowego octu', 'Chęć gotowego rozwiązania zamiast domowej pułapki z octem.', lambda t: P['diy'](t) or 'ready' in t),
    row('Dyskretne rozwiązanie', 'Estetyczne, nierzucające się w oczy w widocznych miejscach.', lambda t: any(w in t for w in ['classy', "doesn't look", 'out of place', 'discreet', 'style', 'look'])),
], key=lambda x: float(x['pct'][:-1]), reverse=True)

customerExpectations = sorted([
    row('Mocniejszy lep / natychmiastowe łapanie', 'Oczekiwanie, że muchy przykleją się od razu, a nie odlecą.', P['not_sticky']),
    row('Szybki efekt bez czekania', 'Frustracja, gdy efekt pojawia się dopiero po 2-4 dniach.', P['patience']),
    row('Mniej intensywny zapach', 'Zapach octu zbyt intensywny w mieszkaniu.', P['smell']),
    row('Lepsza wartość / niższa cena', 'Postrzeganie jako drogie względem domowego octu.', P['price']),
    row('Skuteczność poza szczytem sezonu', 'Słabe efekty przy zakupie pod koniec sezonu / przy chłodzie.', P['seasonal']),
], key=lambda x: float(x['pct'][:-1]), reverse=True)

# ── Sentiment topics (bullets = PL analysis, quotes = REAL EN) ──────────────
def topic(label, pred, bullets, qratings):
    _, p = share(pred)
    return {'label': label, 'reason': bullets[0], 'pct': p,
            'bullets': bullets, 'quotes': pick_quotes(pred, 4, qratings)}

negativeTopics = [
    topic('Muchy siadają, ale nie przyklejają się', P['not_sticky'],
          ['Najczęstsza skarga z recenzji 1-2★: muchy lądują na lepie i odlatują.',
           'Warstwa kleju postrzegana jako za słaba, zwłaszcza po zdjęciu folii ochronnej.',
           'Podważa to podstawową obietnicę produktu (łapanie), a nie tylko wygodę.'], (1, 2, 3)),
    topic('Nie przyciąga much', P['efficacy_fails'],
          ['Część klientów twierdzi, że muchy w ogóle ignorują pułapkę.',
           'Przynęta / ocet postrzegane jako za słabe, by ściągnąć owady.',
           'Silnie skorelowane ze złym umiejscowieniem i porą roku.'], (1, 2, 3)),
    topic('Nieprzyjemny zapach octu', P['smell'],
          ['~8% recenzji wspomina intensywny zapach octu w pomieszczeniu.',
           'Dla części klientów zapach przewyższa korzyść z łapania much.'], (1, 2, 3)),
    topic('Za drogie / strata pieniędzy', P['price'],
          ['Klienci opisują produkt jako „ocet + lepka plastikowa karta" w wysokiej cenie.',
           'Cena boleśnie odczuwalna, gdy skuteczność zawodzi.'], (1, 2, 3)),
    topic('Domowy zamiennik działa lepiej', P['diy'],
          ['Powracający wątek: ocet jabłkowy + płyn do naczyń łapie więcej za grosze.',
           'Bezpośrednie porównania „side by side" na niekorzyść produktu.'], (1, 2, 3)),
]
positiveTopics = [
    topic('Działa - kończy inwazję much', P['efficacy_works'],
          ['Dominujący wątek 4-5★: łapie dużo much i rozwiązuje problem w kilka dni.',
           'Wielu opisuje pełną pułapkę i koniec brzęczenia w kuchni.'], (4, 5)),
    topic('Wymaga cierpliwości (2-4 dni)', P['patience'],
          ['Kluczowy warunek sukcesu: efekt nie jest natychmiastowy, narasta po kilku dniach.',
           'Klienci, którzy poczekali, zmieniają ocenę z krytycznej na entuzjastyczną.'], (4, 5)),
    topic('Łatwy w użyciu i dyskretny', P['ease'],
          ['Prosty montaż i ustawienie; nierzucający się w oczy wygląd.',
           'Możliwość dolania własnego octu doceniana przez część klientów.'], (4, 5)),
    topic('Kupowany co roku', P['repeat'],
          ['Silny sygnał retencji: „kupuję co lato", „3. rok z rzędu".',
           'Zakup sezonowy, powtarzalny - potencjał subskrypcji / wielopaku.'], (4, 5)),
    topic('Skuteczny na muszki od roślin', P['plants'],
          ['Wyraźny wątek ziemiórek wokół roślin doniczkowych, nie tylko owocówek.',
           'Rozszerza realny rynek poza kuchnię.'], (4, 5)),
]

def insight(t, bg, fg, finding, impl):
    return {'type': t, 'badgeBg': bg, 'badgeColor': fg, 'finding': finding, 'implication': impl}

negativeInsights = [
    insight('Skuteczność / lepkość', '#fee2e2', '#991b1b',
            'Najczęstsza skarga 1-2★ to muchy lądujące i odlatujące (słaba lepkość / przynęta).',
            'Wzmocnić klej i stężenie przynęty; w bulletach podkreślić „mocny lep" i pokazać dowód (zdjęcia pełnej pułapki).'),
    insight('Cena / wartość', '#fef3c7', '#92400e',
            'Klienci porównują do domowego octu jabłkowego kosztującego grosze.',
            'Uzasadnić cenę (dyskretny, gotowy, bez bałaganu, wielopak) albo wprowadzić tańszy wariant.'),
    insight('Zapach', '#ffedd5', '#9a3412',
            '~8% skarży się na intensywny zapach octu w mieszkaniu.',
            'Komunikować „umieść w mniej uczęszczanym miejscu" lub popracować nad przynętą o słabszym zapachu.'),
    insight('Oczekiwania / edukacja', '#ede9fe', '#5b21b6',
            'Część ocen 1★ wynika z braku cierpliwości (ocena po 1-2 dniach) i złego umiejscowienia / sezonu.',
            'Na listingu i opakowaniu jasno: „efekty po 2-4 dniach", „umieść blisko źródła", „działa w sezonie".'),
]
positiveInsights = [
    insight('Dowód skuteczności', '#dcfce7', '#166534',
            'Recenzje 5★ chwalą szybkie łapanie i koniec inwazji.',
            'Użyć cytatów i zdjęć „przed / po" w treści A+ oraz w głównym zdjęciu.'),
    insight('Retencja / sezon', '#dbeafe', '#1e40af',
            'Wielu kupuje co roku (co lato) - powtarzalny zakup sezonowy.',
            'Subskrypcja / wielopak; kampanie sezonowe wiosna-lato.'),
    insight('Zastosowanie: rośliny', '#dcfce7', '#166534',
            'Silny wątek ziemiórek przy roślinach doniczkowych.',
            'Rozszerzyć pozycjonowanie o „muszki od roślin / ziemiórki", nie tylko owocówki.'),
    insight('UX / dyskrecja', '#dbeafe', '#1e40af',
            'Chwalony dyskretny wygląd i możliwość dolania octu.',
            'Eksponować „dyskretny, wielorazowy" jako wyróżnik na tle konkurencji.'),
]

# ── Tag reviews for the browser ─────────────────────────────────────────────
themeFilters = [{'value': k, 'label': LABEL[k]} for k in
                ['efficacy_works', 'efficacy_fails', 'not_sticky', 'smell', 'price', 'diy',
                 'patience', 'ease', 'repeat', 'plants', 'seasonal']]
tagStyles = {k: STYLE[k] for k in STYLE}
reviews_out = []
for x, t in TX:
    tags = [k for k, pred in P.items() if pred(t)]
    body = x['content'] if len(x['content']) >= 8 else (x['title'] or x['content'])
    reviews_out.append({'r': x['r'], 't': body[:600], 'tags': tags})

cpSummary = (
    f"Kupujący to głównie gospodarstwa domowe walczące z muszkami owocówkami w <b>kuchni</b> "
    f"(wokół owoców, kosza, zlewu) oraz właściciele <b>roślin doniczkowych</b> (ziemiórki). "
    f"Zakupy silnie <b>sezonowe</b> - szczyt latem. Sentyment spolaryzowany: "
    f"<b>{round((star[3]+star[4])/N*100)}%</b> recenzji 4-5★ vs <b>{round((star[0]+star[1]+star[2])/N*100)}%</b> 1-3★; "
    f"skuteczność zależy od <b>cierpliwości</b> (2-4 dni), umiejscowienia i pory roku."
)
csSummary = (
    'Recenzje mocno spolaryzowane wokół jednej osi - <b>skuteczności</b>. Ten sam produkt zbiera '
    '„nie złapał ani jednej" i „pozbył się inwazji w 2 dni". Kluczowe różnice: cierpliwość (efekt po kilku dniach), '
    'umiejscowienie blisko źródła i pora roku. Wtórne skargi: siła lepu, zapach octu i cena względem domowego octu.'
)

VOC_DATA = {
    'countryName': 'Wielka Brytania', 'countryCode': 'UK', 'countryTld': 'co.uk',
    'segmentName': '', 'currency': '£',
    'productCount': 2, 'totalReviews': N, 'avgRating': xray_avg,
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

# ── Reuse the canonical template + provecta's Polish transform ───────────────
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
VOC_FN = to_named_renderer(VOC_BODY, 'renderReviews',
                           "var root = document.getElementById('u-reviews-voc-root');")

# Patch: headline rating from X-Ray, hide scraped star-dist bar (sample skews
# critical: scraped avg {scraped} vs X-Ray {xray}). Verbatim anchors from template.
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
  var segLower = segment ? esc(segment.toLowerCase()) : '';
  var analyzed = (D.reviews || []).length;
  var tld = D.countryTld || (countryCode ? countryCode.toLowerCase() : '');

  h += '<h2 style="margin-bottom:6px">Recenzje (VOC)' + (countryName ? ' · ' + esc(countryName) : '') + '</h2>';
  h += '<p style="margin:0 0 14px;color:#64748b;font-size:.78rem">Ocena i liczba recenzji pochodzą z danych X-Ray (Amazon). Analiza jakościowa (motywy, cytaty) na podstawie <b>' + analyzed.toLocaleString() + '</b> recenzji zebranych z najlepszych produktów' + (tld ? ' na amazon.' + esc(tld) : '') + '.</p>';
  h += '<div class="kpis" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:14px">';
  h += '<div class="kpi"><div class="kpi-v">' + (D.avgRating ? (+D.avgRating).toFixed(1) + ' ★' : '-') + '</div><div class="kpi-l">Średnia ocena (X-Ray)</div></div>';
  h += '<div class="kpi"><div class="kpi-v">' + analyzed.toLocaleString() + '</div><div class="kpi-l">Analizowane recenzje</div></div>';
  h += (D.productCount ? '<div class="kpi"><div class="kpi-v">' + D.productCount + '</div><div class="kpi-l">Produkty (X-Ray)</div></div>' : '');
  h += '</div>';"""),
    ("""  // Star Distribution Bar
  var dist = D.starDist;
  h += '<div class="card" style="padding:12px 16px;margin-bottom:20px">';
  h += '<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">';
  h += '<div style="font-size:.78rem;font-weight:600;color:#475569;white-space:nowrap">Star Distribution</div>';
  h += '<div style="font-size:1.1rem;font-weight:800;color:#0f2942">' + (+D.avgRating).toFixed(2) + ' <span style="font-size:.7rem;font-weight:400;color:#64748b">avg</span></div>';
  h += '<div style="flex:1;display:flex;height:22px;border-radius:4px;overflow:hidden;min-width:200px">';
  dist.forEach(function(count, i) {
    var star = i + 1;
    var p = (count / total * 100).toFixed(1);
    h += '<div style="width:' + p + '%;background:' + STAR_COLORS[star] + ';display:flex;align-items:center;justify-content:center;color:#fff;font-size:.68rem;font-weight:600">' + (parseFloat(p) >= 5 ? p + '%' : '') + '</div>';
  });
  h += '</div>';
  h += '<div style="display:flex;gap:10px;flex-wrap:wrap;font-size:.68rem;color:#475569">';
  dist.forEach(function(count, i) {
    h += '<span><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:' + STAR_COLORS[i+1] + ';margin-right:3px"></span>' + (i+1) + '★ ' + count + '</span>';
  });
  h += '</div></div></div>';""",
     """  // Star Distribution Bar - rozkład ze scrape'u (197 recenzji, próbka krytyczna vs X-Ray)
  var dist = D.starDist;
  var sc = dist.reduce(function(a,b){return a+b;},0) || 1;
  var scAvg = dist.reduce(function(a,c,i){return a+c*(i+1);},0)/sc;
  h += '<div class="card" style="padding:12px 16px;margin-bottom:20px">';
  h += '<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">';
  h += '<div style="font-size:.78rem;font-weight:600;color:#475569;white-space:nowrap">Rozkład gwiazdek (próbka ' + sc + ')</div>';
  h += '<div style="font-size:1.1rem;font-weight:800;color:#0f2942">' + scAvg.toFixed(1) + ' <span style="font-size:.7rem;font-weight:400;color:#64748b">śr. próbki</span></div>';
  h += '<div style="flex:1;display:flex;height:22px;border-radius:4px;overflow:hidden;min-width:200px">';
  dist.forEach(function(count, i) {
    var p = (count / sc * 100).toFixed(1);
    h += '<div style="width:' + p + '%;background:' + STAR_COLORS[i+1] + ';display:flex;align-items:center;justify-content:center;color:#fff;font-size:.68rem;font-weight:600">' + (parseFloat(p) >= 5 ? p + '%' : '') + '</div>';
  });
  h += '</div>';
  h += '<div style="display:flex;gap:10px;flex-wrap:wrap;font-size:.68rem;color:#475569">';
  dist.forEach(function(count, i) {
    h += '<span><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:' + STAR_COLORS[i+1] + ';margin-right:3px"></span>' + (i+1) + '★ ' + count + '</span>';
  });
  h += '</div></div>';
  h += '<div style="font-size:.66rem;color:#94a3b8;margin-top:8px">Uwaga: to rozkład zebranej próbki (197), skośny krytycznie względem oceny X-Ray (' + (+D.avgRating).toFixed(1) + '★). Nagłówek używa oceny X-Ray jako reprezentatywnej dla całej populacji recenzji.</div></div>';"""),
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
    '<span class="ms2-pilllabel">Rynek:</span>'
    '<button class="ms2-pill active" disabled>Wielka Brytania (UK)</button>'
    '<span style="font-size:.68rem;color:#94a3b8;margin-left:8px">Recenzje dostępne tylko dla UK</span>'
    '</div>\n'
    '<div id="u-reviews-voc-root" style="max-width:1200px;margin:0 auto;padding:8px 24px 40px"></div>\n'
    '<script>\n'
    'var VOC_DATA_UK = ' + json.dumps(VOC_DATA, ensure_ascii=False) + ';\n'
    + VOC_FN + '\n'
    'window.__vocRender = function(){ renderReviews(VOC_DATA_UK, document.getElementById("u-reviews-voc-root")); };\n'
    '</script>\n'
)
FRAG = FRAG.replace('—', '-').replace('–', '-')

out = os.path.join(BASE, '_voc.html')
open(out, 'w', encoding='utf-8').write(FRAG)

print(f'_voc.html: {os.path.getsize(out):,} bytes')
print(f'reviews={N}  scraped_avg={scraped_avg}  xray_avg={xray_avg}  star={star}')
print(f'positives(4-5)={star[3]+star[4]} negatives(1-3)={star[0]+star[1]+star[2]}')
print('negativeTopics pct:', [(t['label'], t['pct'], len(t['quotes'])) for t in negativeTopics])
print('positiveTopics pct:', [(t['label'], t['pct'], len(t['quotes'])) for t in positiveTopics])
