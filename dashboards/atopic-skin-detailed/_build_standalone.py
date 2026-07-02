# -*- coding: utf-8 -*-
"""Build standalone index.html for the Atopic Skin (Detailed) dashboard.

3-tab standalone, ALL static UI text in POLISH:
  Tab 1 · Rynek              — faithful copy of the dermo-products TOPLINE
  Tab 2 · Recenzje (VOC)     — per country x segment, renderReviews(bucket)
  Tab 3 · Marketing Deep-Dive — per country x segment, renderMarketingDeepDive(bucket)

Markets: DE / FR / IT / ES (order by market size DE -> FR -> IT -> ES).

Data sources (all read at build time, inlined into index.html):
  * Tab 1  : dashboards/dermo-products/index.html  (the rendered topline;
             its <style> block and <body> inner content are pasted VERBATIM
             into the Rynek panel; the topline's own inline <script> renders
             its Chart.js charts because that panel is visible at load).
  * VOC    : reviews/{CODE}/{Segment}/voc.json          -> D.voc[CODE][Segment]  (or null)
  * MDD    : data/competitor-listings/{CODE}/mdd-{slug}.json -> D.mdd[CODE][Segment] (or null)
             slug = segment.lower()

Run (Windows):
    python _build_standalone.py
"""
import csv, json, os, re, sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
CONSOLE = os.path.abspath(os.path.join(BASE, '..', '..'))          # .../Console
# Tab 1 (Rynek) is generated FROM THIS dashboard's own (current) X-Ray via
# _build_rynek.py — the reworked segmentation + added oils, NOT the stale
# atopic-skin-topline build. See _build_rynek.py. Regenerated on every build below.
RYNEK_HTML   = os.path.join(BASE, '_rynek_topline.html')
TOPLINE_HTML = RYNEK_HTML
VOC_TPL  = os.path.join(CONSOLE, 'templates', 'tabs', 'u-reviews-voc', 'template.html')
MDD_TPL  = os.path.join(BASE, 'templates', 'tabs', 'u-marketing-deep-dive', 'template.html')  # dashboard-local szelki-style MDD
MS_TPL   = os.path.join(BASE, 'templates', 'tabs', 'market-structure', 'template.html')       # dashboard-local Polish Market Structure
ENGINE_JS_PATH = os.path.join(CONSOLE, 'js', 'data-engine.js')                                # DataEngine (aggregation + sortable tables)

# ── Identity ────────────────────────────────────────────────────────────────
PRODUCT_TITLE = 'Atopic Skin — Detailed (DE, FR, IT, ES)'
DASHBOARD_H2  = 'Atopic Skin — Analiza szczegółowa'
DASHBOARD_SUB = 'Rynki: Niemcy · Francja · Włochy · Hiszpania · Dane: Helium 10 X-Ray + analiza recenzji (VOC) + Marketing Deep-Dive'

# Per-country X-Ray Google Sheets (top-right header buttons, like the multi-market
# convention). Reused from the topline; '#' placeholder if a sheet is missing.
XRAY_LINKS = {
    'DE': 'https://docs.google.com/spreadsheets/d/1_i9_eaJUx9YhG0XFUOWb97YEn_Jj79U6wqcapMYK9Yw/edit?gid=1649983910#gid=1649983910',
    'FR': 'https://docs.google.com/spreadsheets/d/1fD-QisOAi2_GUpHItXgeUu2bN19iti9w0KrtbOP51Jc/edit?gid=2058240202#gid=2058240202',
    'IT': 'https://docs.google.com/spreadsheets/d/1coY3TXsKNt-z_ruNg5Krdm-UPNywG5wIwep9XqZFlOo/edit?gid=1574144490#gid=1574144490',
    'ES': 'https://docs.google.com/spreadsheets/d/1u-S0NnaPOJB2qh0KSvxOum4bvQt5Ydrp7-VPNngGvKI/edit?gid=1593778489#gid=1593778489',
}

# ── Countries (order by market size) ────────────────────────────────────────
COUNTRIES = [
    {'code': 'DE', 'name': 'Niemcy',    'flag': '\U0001F1E9\U0001F1EA'},
    {'code': 'FR', 'name': 'Francja',   'flag': '\U0001F1EB\U0001F1F7'},
    {'code': 'IT', 'name': 'Włochy',    'flag': '\U0001F1EE\U0001F1F9'},
    {'code': 'ES', 'name': 'Hiszpania', 'flag': '\U0001F1EA\U0001F1F8'},
]

# Segments shown in the dashboard. Check (holding bucket) is EXCLUDED.
# Oil is now included (atopic-only oil set with VOC + szelki-style MDD).
SEGMENT_ORDER = ['Cream', 'Wash', 'Oil']
# Fallback segments per country if reviews/{CODE}/ has no subfolders yet.
DEFAULT_SEGMENTS = {
    'DE': ['Cream', 'Wash'],
    'FR': ['Cream', 'Wash'],
    'IT': ['Cream', 'Wash'],
    'ES': ['Cream', 'Wash'],
}


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# ── Detect segments per country from reviews/{CODE}/ subfolders ──────────────
def detect_segments(code):
    d = os.path.join(BASE, 'reviews', code)
    found = []
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            if os.path.isdir(os.path.join(d, name)):
                found.append(name)
    if not found:
        found = DEFAULT_SEGMENTS.get(code, ['Cream', 'Wash'])
    # only segments in SEGMENT_ORDER are shown (Check + Oil excluded); no extras appended
    ordered = [s for s in SEGMENT_ORDER if s in found]
    return ordered


SEGMENTS_BY_COUNTRY = {c['code']: detect_segments(c['code']) for c in COUNTRIES}


# ── Load VOC + MDD JSON buckets (null when absent) ──────────────────────────
def load_json(path, label):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'  warn: failed to load {label}: {e}')
        return None


def load_voc(code, segment):
    return load_json(os.path.join(BASE, 'reviews', code, segment, 'voc.json'), f'VOC {code}/{segment}')


def load_mdd(code, segment):
    slug = segment.lower()
    return load_json(os.path.join(BASE, 'data', 'competitor-listings', code, f'mdd-{slug}.json'), f'MDD {code}/{segment}')


voc_data = {}
mdd_data = {}
for c in COUNTRIES:
    code = c['code']
    voc_data[code] = {}
    mdd_data[code] = {}
    for seg in SEGMENTS_BY_COUNTRY[code]:
        voc_data[code][seg] = load_voc(code, seg)
        mdd_data[code][seg] = load_mdd(code, seg)


# ── Market Structure: per-country products from X-Ray (Cream/Wash/Oil only) ──
# 12M projection = 30d sales × 12 (no per-ASIN sales history in this project,
# same flat multiplier the atopic-skin-topline Rynek tab uses). Revenue = units × price.
STRUCT_SEGMENTS = ['Cream', 'Wash', 'Oil']


def _pnum(val):
    s = re.sub(r'[$€£,\s]', '', str('' if val is None else val))
    try:
        return float(s)
    except Exception:
        return 0.0


def load_structure(code):
    path = os.path.join(BASE, 'data', 'x-ray', code, f'Dermo-Products-{code}.csv')
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames or []
        price_col = next((c for c in cols if 'price' in c.lower()), None)
        for r in rd:
            seg = (r.get('Segment') or '').strip()
            if seg not in STRUCT_SEGMENTS:
                continue
            asin = (r.get('ASIN') or '').strip()
            if not asin:
                continue
            price = _pnum(r.get(price_col)) if price_col else 0.0
            sales30d = _pnum(r.get('ASIN Sales'))
            rev30d = _pnum(r.get('ASIN Revenue'))
            if sales30d == 0 and rev30d > 0 and price > 0:
                sales30d = round(rev30d / price)
            units12m = round(sales30d * 12)
            out.append({
                'asin': asin,
                'title': (r.get('Product Details') or '').strip()[:300],
                'type': seg,
                'brand': ((r.get('Brand') or '').strip() or 'Unknown'),
                'price': round(price, 2),
                'sales30d': round(sales30d),
                'revenue30d': round(rev30d),
                'bsr': int(_pnum(r.get('BSR'))),
                'rating': round(_pnum(r.get('Ratings')), 1),
                'reviewCount': int(_pnum(r.get('Review Count'))),
                'units12m': units12m,
                'revenue12m': round(units12m * price),
            })
    return out


structure_data = {c['code']: load_structure(c['code']) for c in COUNTRIES}


# Default selection: first country (DE), first available segment preferring Cream.
def default_segment(code):
    segs = SEGMENTS_BY_COUNTRY[code]
    if 'Cream' in segs:
        return 'Cream'
    return segs[0] if segs else ''


DEFAULT_COUNTRY = COUNTRIES[0]['code']
DEFAULT_SEG = default_segment(DEFAULT_COUNTRY)


# ── Extract Tab 1 (topline) style + body ────────────────────────────────────
def build_rynek():
    """Regenerate _rynek_topline.html from this dashboard's own X-Ray (Tab 1)."""
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(BASE, '_build_rynek.py')],
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        raise SystemExit('Rynek (Tab 1) build failed:\n' + (r.stderr or r.stdout))
    print('Rynek (Tab 1) rebuilt from local X-Ray -> _rynek_topline.html')


def extract_topline():
    with open(TOPLINE_HTML, encoding='utf-8') as f:
        html = f.read()
    m_style = re.search(r'<style>(.*?)</style>', html, re.S)
    topline_css = m_style.group(1) if m_style else ''
    m_body = re.search(r'<body>(.*?)</body>', html, re.S)
    topline_body = m_body.group(1) if m_body else ''
    # Drop the topline's own <header> (title + X-Ray buttons): the detailed shell
    # now has ONE top-level header above the tabs, so Tab 1 must not double it up.
    topline_body = re.sub(r'<header>.*?</header>', '', topline_body, flags=re.S)
    return topline_css, topline_body


build_rynek()
TOPLINE_CSS, TOPLINE_BODY = extract_topline()


# ── Extract CSS + IIFE body from a u-* template ─────────────────────────────
def extract_template(path):
    with open(path, encoding='utf-8') as f:
        html = f.read()
    m_style = re.search(r'<style>(.*?)</style>', html, re.S)
    css = m_style.group(1) if m_style else ''
    # Grab the IIFE inner: between the first "(function(){" and the trailing "})();"
    m_script = re.search(r'<script>\s*\(function\(\)\{(.*)\}\)\(\);\s*</script>', html, re.S)
    body = m_script.group(1) if m_script else ''
    return css, body


VOC_CSS, VOC_BODY = extract_template(VOC_TPL)
MDD_CSS, MDD_BODY = extract_template(MDD_TPL)

# The template IIFEs read `window._TAB_DATA` and target a fixed root id via
# document.getElementById. We convert each into a named function
# renderReviews(D, root) / renderMarketingDeepDive(D, root):
#   * replace `var D = window._TAB_DATA;` with the function's own param
#   * replace the hard-coded root lookup with the passed-in `root`
#   * translate hard-coded English UI strings to Polish

def to_named_renderer(body, fn_name, root_var_line):
    # Drop the two leading lines that fetch D + root (they become fn params)
    body = body.replace('var D = window._TAB_DATA;', '', 1)
    body = body.replace(root_var_line, '', 1)
    return 'function ' + fn_name + '(D, root){\n' + body + '\n}'


VOC_FN = to_named_renderer(
    VOC_BODY, 'renderReviews',
    "var root = document.getElementById('u-reviews-voc-root');")
MDD_FN = to_named_renderer(
    MDD_BODY, 'renderMarketingDeepDive',
    "var root = document.getElementById('u-mdd-tab-root');")

# Market Structure template is already Polish (dashboard-local), so no translation
# table is needed — just convert its IIFE into renderMarketStructure(D, root).
MS_CSS, MS_BODY = extract_template(MS_TPL)
MS_FN = to_named_renderer(
    MS_BODY, 'renderMarketStructure',
    "var root = document.getElementById('ms-tab-root');")

# DataEngine (aggregation + sortable tables) — inlined as its own <script>.
with open(ENGINE_JS_PATH, encoding='utf-8') as f:
    ENGINE_JS = f.read()

# ── Polish UI-string translations (static labels baked into the renderers) ──
# Data (themes, quotes, findings) comes from JSON; these are the fixed English
# UI chrome strings hard-coded in the u-* renderers -> translate to Polish.
VOC_STR = [
    # ── Dashboard-local: scraped review ratings are critical-skewed / unreliable,
    #    so headline rating + review count come from X-Ray. Rewrite KPI row and
    #    hide the star-distribution bar. (Runs first, on pristine template code.) ──
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

  h += '<h2 style="margin-bottom:6px">Recenzje (VOC)' + (segment ? ' · ' + esc(segment) : '') + (countryName ? ' · ' + esc(countryName) : '') + '</h2>';
  h += '<p style="margin:0 0 14px;color:#64748b;font-size:.78rem">Ocena i liczba recenzji pochodzą z danych X-Ray (Amazon). Analiza jakościowa (motywy, cytaty) na podstawie <b>' + analyzed.toLocaleString() + '</b> recenzji zebranych z najlepszych ' + (segment ? esc(segment.toLowerCase()) + ' produktów' : 'produktów') + (countryCode ? ' na amazon.' + esc(countryCode.toLowerCase()) : '') + '.</p>';
  h += '<div class="kpis" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:14px">';
  h += '<div class="kpi"><div class="kpi-v">' + (D.avgRating ? (+D.avgRating).toFixed(2) + ' ★' : '—') + '</div><div class="kpi-l">Średnia ocena (X-Ray)</div></div>';
  h += '<div class="kpi"><div class="kpi-v">' + total.toLocaleString() + '</div><div class="kpi-l">Recenzje łącznie (X-Ray)</div></div>';
  h += '<div class="kpi"><div class="kpi-v">' + analyzed.toLocaleString() + '</div><div class="kpi-l">Analizowane recenzje</div></div>';
  h += (D.productCount ? '<div class="kpi"><div class="kpi-v">' + D.productCount + '</div><div class="kpi-l">Produkty</div></div>' : '');
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
     "  // Star Distribution Bar — hidden (scraped ratings unreliable; headline avg from X-Ray)"),
    ("No data loaded for this tab.", "Brak danych VOC dla tego rynku/segmentu."),
    ("Reviews VOC", "Recenzje (VOC)"),
    ("No review data loaded", "Brak danych recenzji"),
    ("Total Reviews", "Recenzje łącznie"),
    ("Sentiment Ratio (pos:neg)", "Współczynnik sentymentu (poz:neg)"),
    ("Positive (4★+5★)", "Pozytywne (4★+5★)"),
    ("Negative (1★–3★)", "Negatywne (1★–3★)"),
    ("Star Distribution", "Rozkład gwiazdek"),
    (" <span style=\"font-size:.7rem;font-weight:400;color:#64748b\">avg</span>",
     " <span style=\"font-size:.7rem;font-weight:400;color:#64748b\">śr.</span>"),
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
    ("Showing first 200 of ", "Pierwsze 200 z "),
    (". Use filters to narrow.", ". Użyj filtrów, aby zawęzić."),
    # Sentence fragments in the intro line
    ("Based on <b>", "Na podstawie <b>"),
    (" reviews scraped from the top ", " recenzji zebranych z najlepszych "),
    (" products", " produktów"),
    (" on amazon.", " na amazon."),
]

MDD_STR = [
    ("No data loaded for this tab.", "Brak danych Marketing Deep-Dive dla tego rynku/segmentu."),
    ("Marketing Deep-Dive", "Marketing Deep-Dive"),
    ("No competitor data loaded", "Brak danych o konkurencji"),
    ("Marketing intelligence across <b>", "Analiza marketingowa dla <b>"),
    (" top competitors</b>", " czołowych konkurentów</b>"),
    (" on <b>", " na <b>"),
    (". Listings pulled from SP-API Catalog. Claims tagged across themes and cross-referenced with VOC findings from the Reviews tab.",
     ". Listingi pobrane z SP-API Catalog. Deklaracje otagowane wg tematów i porównane z wnioskami VOC z zakładki Recenzje."),
    ("1. Competitor Overview · Top ", "1. Przegląd konkurencji · Top "),
    (" by 30d Revenue<", " wg przychodu 30 dni<"),
    ("Click a card to see full bullets, claims, and image stack",
     "Kliknij kartę, aby zobaczyć pełne bullety, deklaracje i zdjęcia"),
    ("Each card is one competitor listing pulled from <b>Amazon SP-API Catalog</b>. Brand, title, hero image, price, rating, BSR and 30-day sales/revenue come from the X-Ray export. The <b>theme tags</b> on each card show which marketing claims the listing makes (regex-matched against title + bullets + description in the local language).",
     "Każda karta to jeden listing konkurenta pobrany z <b>Amazon SP-API Catalog</b>. Marka, tytuł, zdjęcie główne, cena, ocena, BSR oraz sprzedaż/przychód z 30 dni pochodzą z eksportu X-Ray. <b>Tagi tematów</b> na każdej karcie pokazują, jakie deklaracje marketingowe zawiera listing (dopasowane regex do tytułu + bulletów + opisu w języku lokalnym)."),
    (">' + mfmt(c.price) + '</b> price</span>", ">' + mfmt(c.price) + '</b> cena</span>"),
    (">' + mfmt(c.rev30d) + '</b> 30d rev</span>", ">' + mfmt(c.rev30d) + '</b> przych. 30d</span>"),
    ("2. Claims Matrix</div>", "2. Macierz deklaracji</div>"),
    ("Rows = competitors, columns = claim themes. Filled = theme present in title/bullets.",
     "Wiersze = konkurenci, kolumny = tematy deklaracji. Wypełnione = temat obecny w tytule/bulletach."),
    ("<b>Heatmap:</b> a filled cell means the competitor explicitly claims that theme in their listing copy. Below the matrix, the bars rank themes by <b>adoption rate</b> across all ",
     "<b>Mapa cieplna:</b> wypełniona komórka oznacza, że konkurent wprost deklaruje ten temat w treści listingu. Pod macierzą słupki porządkują tematy wg <b>wskaźnika adopcji</b> wśród wszystkich "),
    (" competitors. <b>~100% bars</b> = saturated table-stakes (everybody says it). <b>Short bars</b> = whitespace candidates (few competitors are claiming it — see Section 4).",
     " konkurentów. <b>Słupki ~100%</b> = nasycone standardy (wszyscy to mówią). <b>Krótkie słupki</b> = kandydaci na białe plamy (niewielu konkurentów to deklaruje — patrz Sekcja 4)."),
    (">Brand · ASIN<", ">Marka · ASIN<"),
    ("Claim frequency across all ", "Częstość deklaracji wśród wszystkich "),
    (" listings<", " listingów<"),
    ("Top brands: ", "Czołowe marki: "),
    ("3. VOC ↔ Claims Gap Analysis</div>", "3. Analiza luk VOC ↔ deklaracje</div>"),
    ("Customer concerns from the Reviews tab vs how many of the ",
     "Obawy klientów z zakładki Recenzje vs ilu z "),
    (" competitors address them<", " konkurentów się do nich odnosi<"),
    (">VOC Topic</th>", ">Temat VOC</th>"),
    (">Customer %</th>", ">% klientów</th>"),
    (">Addressed by</th>", ">Adresowane przez</th>"),
    (">Severity</th>", ">Waga</th>"),
    (">Whitespace</th>", ">Biała plama</th>"),
    ("4. Whitespace Opportunities</div>", "4. Białe plamy (możliwości)</div>"),
    ("High customer demand × low competitor coverage",
     "Wysoki popyt klientów × niskie pokrycie przez konkurencję"),
    ("Themes claimed by <b>≤25% of competitors</b> — empty marketing real estate. Picking one of these and leading with it in your hero bullet or A+ content gives you a claim that buyers don't see elsewhere on the search results page. The brands listed under each card are the only ones currently making the claim.",
     "Tematy deklarowane przez <b>≤25% konkurentów</b> — wolna przestrzeń marketingowa. Wybranie jednego z nich i wyeksponowanie go w głównym bullecie lub treści A+ daje deklarację, której kupujący nie widzą gdzie indziej na stronie wyników. Marki wymienione pod każdą kartą to jedyne, które obecnie tę deklarację składają."),
    ("Saturated Claims · Diminishing Returns</div>", "Nasycone deklaracje · Malejące zwroty</div>"),
    ("Most-used claims where adding the same message no longer differentiates",
     "Najczęściej używane deklaracje, gdzie powtórzenie tego samego przekazu już nie wyróżnia"),
    ("Themes claimed by <b>≥60% of competitors</b> — table-stakes. You still need to claim them (buyers expect them), but adding them won't move the needle. Treat as <b>parity bullets</b>, not hero bullets, and spend your differentiation budget on Whitespace items above.",
     "Tematy deklarowane przez <b>≥60% konkurentów</b> — standard rynkowy. Nadal trzeba je deklarować (kupujący tego oczekują), ale ich dodanie niczego nie zmieni. Traktuj jako <b>bullety parytetowe</b>, nie główne, a budżet na wyróżnienie przeznacz na białe plamy powyżej."),
    ("5. Strategic Recommendations</div>", "5. Rekomendacje strategiczne</div>"),
    ("Synthesized findings + actionable implications",
     "Zsyntetyzowane ustalenia + praktyczne implikacje"),
    ("Auto-derived from the highest-severity <b>VOC gaps</b> and biggest <b>whitespace</b> opportunities above. Each card pairs a finding (what the data shows) with an implication (what to do about it in your listing). Use these as a starting point for listing rewrites and A+ content priorities.",
     "Automatycznie wyprowadzone z najważniejszych <b>luk VOC</b> i największych <b>białych plam</b> powyżej. Każda karta łączy ustalenie (co pokazują dane) z implikacją (co z tym zrobić w listingu). Użyj ich jako punktu wyjścia do przeredagowania listingu i priorytetów treści A+."),
    ("Cross-references the <b>Reviews VOC tab's top complaints</b> with what competitors claim in their listings.",
     "Zestawia <b>najczęstsze skargi z zakładki Recenzje (VOC)</b> z tym, co konkurenci deklarują w listingach."),
    ("<b>VOC Topic</b> = a complaint theme from your Reviews analysis.",
     "<b>Temat VOC</b> = temat skargi z Twojej analizy recenzji."),
    ("<b>Customer %</b> = share of negative reviews mentioning it.",
     "<b>% klientów</b> = udział negatywnych recenzji, które o tym wspominają."),
    ("<b>Addressed by</b> = how many of the ", "<b>Adresowane przez</b> = ilu z "),
    (" competitors make a listing claim that maps to this complaint.",
     " konkurentów składa deklarację, która odpowiada tej skardze."),
    ("<b>Severity</b>: ", "<b>Waga</b>: "),
    (" = ≥20% concern AND ≤1 competitor addresses · ",
     " = ≥20% obaw ORAZ ≤1 konkurent adresuje · "),
    (" = ≥10% AND ≤2 · ", " = ≥10% ORAZ ≤2 · "),
    (" = otherwise.", " = w pozostałych przypadkach."),
    ("<b>Whitespace</b> = <code>true</code> when zero competitors address it (the strongest signal).",
     "<b>Biała plama</b> = <code>true</code>, gdy żaden konkurent tego nie adresuje (najsilniejszy sygnał)."),
    ("<b>How to act:</b> hunt for HIGH/MED rows or any row with high % + low addressed-by — those are listing differentiation plays.",
     "<b>Jak działać:</b> szukaj wierszy HIGH/MED lub dowolnego wiersza z wysokim % + niskim adresowaniem — to okazje do wyróżnienia listingu."),
    (">Bullet Points<", ">Bullety<"),
    ("No bullets available", "Brak dostępnych bulletów"),
    (">Description<", ">Opis<"),
    (" reviews)</span>", " recenzji)</span>"),
    (">' + mfmt(c.rev30d) + '</b> 30d revenue</span>", ">' + mfmt(c.rev30d) + '</b> przychód 30d</span>"),
]


def apply_translations(js, pairs):
    for en, pl in pairs:
        js = js.replace(en, pl)
    return js


VOC_FN = apply_translations(VOC_FN, VOC_STR)
MDD_FN = apply_translations(MDD_FN, MDD_STR)


# ── Bundle passed to the browser ────────────────────────────────────────────
bundle = {
    'countries': COUNTRIES,
    'segmentsByCountry': SEGMENTS_BY_COUNTRY,
    'defaultCountry': DEFAULT_COUNTRY,
    'defaultSegment': DEFAULT_SEG,
    'currency': '€',
    'voc': voc_data,
    'mdd': mdd_data,
    'structure': structure_data,
}

# ── Shell HTML ──────────────────────────────────────────────────────────────
SHELL_CSS = r'''
  *,*::before,*::after { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; background: #f1f5f9; color: #0f172a; font-size: 14px; }
  /* Top header bar (title + per-country X-Ray buttons) — tabs sit BELOW it */
  .ad-header { background: #0f2942; color: #fff; padding: 16px 32px; display: flex; justify-content: space-between; align-items: center; gap: 24px; flex-wrap: wrap; }
  .ad-header .ad-hd-titles { flex: 1; min-width: 0; }
  .ad-header h1 { margin: 0; font-size: 1.3rem; font-weight: 700; color: #fff; letter-spacing: .01em; }
  .ad-header .ad-hd-sub { display: block; margin-top: 4px; font-size: .76rem; color: #cbd5e1; }
  .ad-xray-btns { display: flex; gap: 8px; flex-wrap: wrap; }
  .ad-xray-btn { background: #16a34a; color: #fff; padding: 8px 14px; border-radius: 6px; font-size: .76rem; font-weight: 600; text-decoration: none; white-space: nowrap; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 1px 3px rgba(0,0,0,.2); transition: background .15s; }
  .ad-xray-btn:hover { background: #15803d; }
  .ad-xray-btn svg { width: 14px; height: 14px; }
  /* Tab bar */
  .ad-tabs { display: flex; gap: 4px; border-bottom: 2px solid #e2e8f0; flex-wrap: wrap; position: sticky; top: 0; z-index: 40; background: #f1f5f9; padding: 12px 32px 0; }
  .ad-tab { padding: 10px 18px; background: transparent; border: none; cursor: pointer; font-size: .9rem; font-weight: 600; color: #64748b; border-bottom: 3px solid transparent; margin-bottom: -2px; transition: color .15s, border-color .15s; white-space: nowrap; }
  .ad-tab:hover { color: #0f172a; }
  .ad-tab.active { color: #0f2942; border-bottom-color: #0f2942; }
  /* Pill rows */
  .ad-pillrow { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; background: #f1f5f9; padding: 12px 32px; border-bottom: 1px solid #e2e8f0; }
  .ad-pillrow.hidden { display: none; }
  .ad-pillrow .label { font-size: .72rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: .04em; margin-right: 6px; }
  .ad-pill { padding: 8px 16px; border: 2px solid #cbd5e1; background: #fff; border-radius: 22px; cursor: pointer; font-size: .8rem; font-weight: 600; color: #475569; transition: all .15s; display: inline-flex; align-items: center; gap: 8px; }
  .ad-pill:hover { border-color: #94a3b8; color: #1e293b; }
  .ad-pill.active { background: #2563eb; border-color: #2563eb; color: #fff; }
  .ad-seg-pill.active { background: #0f2942; border-color: #0f2942; }
  .ad-pill .flag { font-size: 1rem; }
  /* Panels */
  .ad-panel { display: none; }
  .ad-panel.active { display: block; }
  #panel-voc, #panel-mdd { padding: 24px 32px; min-height: 300px; }
  #panel-voc h2, #panel-mdd h2 { color: #1e293b; font-size: 1.2rem; font-weight: 600; margin: 0 0 16px; }
  #panel-voc .card, #panel-mdd .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.05); margin-bottom: 14px; }
  #panel-voc .kpi, #panel-mdd .kpi { background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 14px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
  #panel-voc .kpi-v { font-size: 1.3rem; font-weight: 700; color: #0f172a; line-height: 1.1; }
  #panel-voc .kpi-l { font-size: .7rem; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing: .04em; }
  #panel-voc .tbl-wrap, #panel-mdd .tbl-wrap { overflow-x: auto; }
  #panel-voc table, #panel-mdd table { width: 100%; border-collapse: collapse; }
  .ad-empty { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 40px 24px; text-align: center; color: #64748b; font-size: .9rem; box-shadow: 0 1px 3px rgba(0,0,0,.05); }
  .ad-warn { background: #fffbeb; border: 1px solid #fde68a; color: #92400e; border-radius: 6px; padding: 10px 14px; font-size: .78rem; margin-bottom: 14px; }
'''

HTML = r'''<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITLE}}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<style>/* (a) shell */
{{SHELL_CSS}}
</style>
<style>/* (b) topline (verbatim) */
{{TOPLINE_CSS}}
</style>
<style>/* (c) Reviews VOC */
{{VOC_CSS}}
</style>
<style>/* (d) Marketing Deep-Dive */
{{MDD_CSS}}
</style>
<style>/* (e) Market Structure */
{{MS_CSS}}
</style>
</head>
<body>

<header class="ad-header">
  <div class="ad-hd-titles">
    <h1>{{DASHBOARD_H2}}</h1>
    <span class="ad-hd-sub">{{DASHBOARD_SUB}}</span>
  </div>
  <div class="ad-xray-btns">{{XRAY_BUTTONS}}</div>
</header>

<div class="ad-tabs">
  <button class="ad-tab active" data-tab="market">Rynek</button>
  <button class="ad-tab" data-tab="structure">Struktura rynku</button>
  <button class="ad-tab" data-tab="voc">Recenzje (VOC)</button>
  <button class="ad-tab" data-tab="mdd">Marketing Deep-Dive</button>
</div>

<div class="ad-pillrow hidden" id="ad-country-row">
  <span class="label">Rynek</span>
  <span id="ad-country-pills"></span>
</div>
<div class="ad-pillrow hidden" id="ad-segment-row">
  <span class="label">Segment</span>
  <span id="ad-segment-pills"></span>
</div>

<div class="ad-panel active" id="panel-market">
{{TOPLINE_BODY}}
</div>

<div class="ad-panel" id="panel-structure"></div>
<div class="ad-panel" id="panel-voc"></div>
<div class="ad-panel" id="panel-mdd"></div>

<script>/* DataEngine — market-structure aggregation + sortable tables */
/*<<ENGINE>>*/
</script>

<script>
var D = /*<<BUNDLE>>*/;

var SEG_LABELS = { Check: 'Sprawdzenie', Cream: 'Krem', Wash: 'Mycie', Oil: 'Olejek' };
function segLabel(s){ return SEG_LABELS[s] || s; }
var MS_SEG_ORDER = ['Cream', 'Wash', 'Oil'];

var state = { tab: 'market', country: D.defaultCountry, segment: D.defaultSegment };

/*<<VOC_FN>>*/
/*<<MDD_FN>>*/
/*<<MS_FN>>*/

function buildCountryPills(){
  var host = document.getElementById('ad-country-pills');
  host.innerHTML = '';
  D.countries.forEach(function(c){
    var b = document.createElement('button');
    b.className = 'ad-pill ad-country-pill' + (c.code === state.country ? ' active' : '');
    b.dataset.country = c.code;
    b.innerHTML = '<span class="flag">' + c.flag + '</span>' + c.name;
    b.addEventListener('click', function(){
      state.country = c.code;
      var segs = D.segmentsByCountry[c.code] || [];
      if (segs.indexOf(state.segment) === -1) state.segment = segs.indexOf('Cream') > -1 ? 'Cream' : (segs[0] || '');
      buildCountryPills();
      buildSegmentPills();
      renderActive();
    });
    host.appendChild(b);
  });
}

function buildSegmentPills(){
  var host = document.getElementById('ad-segment-pills');
  host.innerHTML = '';
  var segs = D.segmentsByCountry[state.country] || [];
  segs.forEach(function(s){
    var b = document.createElement('button');
    b.className = 'ad-pill ad-seg-pill' + (s === state.segment ? ' active' : '');
    b.dataset.segment = s;
    b.textContent = segLabel(s);
    b.addEventListener('click', function(){
      state.segment = s;
      buildSegmentPills();
      renderActive();
    });
    host.appendChild(b);
  });
}

function countryMeta(code){
  return D.countries.filter(function(c){ return c.code === code; })[0] || { code: code, name: code };
}

function scopeBucket(bucket, extra){
  // Ensure identity + currency present so the u-* renderers show correct titles.
  var c = countryMeta(state.country);
  var out = {};
  for (var k in bucket) out[k] = bucket[k];
  out.countryName = out.countryName || c.name;
  out.countryCode = out.countryCode || c.code;
  out.segmentName = out.segmentName || segLabel(state.segment);
  out.currency = out.currency || D.currency;
  if (extra) for (var k2 in extra) out[k2] = extra[k2];
  return out;
}

function renderVOC(){
  var root = document.getElementById('panel-voc');
  var bucket = (D.voc[state.country] || {})[state.segment];
  if (!bucket) {
    root.innerHTML = '<div class="ad-empty">Brak danych VOC dla tego rynku/segmentu.</div>';
    return;
  }
  root.innerHTML = '';
  renderReviews(scopeBucket(bucket), root);
}

function renderMDD(){
  var root = document.getElementById('panel-mdd');
  var bucket = (D.mdd[state.country] || {})[state.segment];
  if (!bucket) {
    root.innerHTML = '<div class="ad-empty">Brak danych Marketing Deep-Dive dla tego rynku/segmentu.</div>';
    return;
  }
  root.innerHTML = '';
  renderMarketingDeepDive(scopeBucket(bucket), root);
}

function renderStructure(){
  var root = document.getElementById('panel-structure');
  var prods = (D.structure && D.structure[state.country]) || [];
  if (!prods.length){
    root.innerHTML = '<div class="ad-empty">Brak danych struktury rynku dla tego rynku.</div>';
    return;
  }
  // Drop any stale structure charts (ids like ms0*, ms1*) so the seg-tab
  // resize-all pass never touches a detached canvas from a prior country.
  if (window.Chart) Object.keys(Chart.instances).forEach(function(k){
    var c = Chart.instances[k];
    try { if (c && c.canvas && /^ms\d/.test(c.canvas.id || '')) c.destroy(); } catch(e){}
  });
  var segs = DataEngine.aggregateSegments(prods);
  segs.sort(function(a, b){
    var ia = MS_SEG_ORDER.indexOf(a.name), ib = MS_SEG_ORDER.indexOf(b.name);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  DataEngine.assignSegmentColors(segs);
  var c = countryMeta(state.country);
  renderMarketStructure({
    segments: segs,
    currency: D.currency,
    countryName: c.name,
    tld: String(state.country).toLowerCase()
  }, root);
}

function renderActive(){
  if (state.tab === 'structure') renderStructure();
  else if (state.tab === 'voc') renderVOC();
  else if (state.tab === 'mdd') renderMDD();
}

function setTab(tab){
  state.tab = tab;
  document.querySelectorAll('.ad-tab').forEach(function(t){ t.classList.toggle('active', t.dataset.tab === tab); });
  document.getElementById('panel-market').classList.toggle('active', tab === 'market');
  document.getElementById('panel-structure').classList.toggle('active', tab === 'structure');
  document.getElementById('panel-voc').classList.toggle('active', tab === 'voc');
  document.getElementById('panel-mdd').classList.toggle('active', tab === 'mdd');
  // Country pills show on Structure/VOC/MDD; the shared Segment pills only on
  // VOC/MDD (Market Structure has its own Cream/Wash/Oil sub-tabs inside).
  var showCountry = (tab === 'structure' || tab === 'voc' || tab === 'mdd');
  var showSeg = (tab === 'voc' || tab === 'mdd');
  document.getElementById('ad-country-row').classList.toggle('hidden', !showCountry);
  document.getElementById('ad-segment-row').classList.toggle('hidden', !showSeg);
  renderActive();
}

document.querySelectorAll('.ad-tab').forEach(function(t){
  t.addEventListener('click', function(){ setTab(t.dataset.tab); });
});

buildCountryPills();
buildSegmentPills();
// Tab 1 (Rynek) is active at load so the topline charts render correctly.
</script>
</body>
</html>
'''

# Per-country X-Ray buttons for the top header (DE · FR · IT · ES)
_XRAY_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
             '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
             '<polyline points="14 2 14 8 20 8"/></svg>')
XRAY_BUTTONS = ''.join(
    '<a class="ad-xray-btn" href="{href}" target="_blank" rel="noopener">{svg}{code} X-Ray</a>'.format(
        href=XRAY_LINKS.get(c['code'], '#'), svg=_XRAY_SVG, code=c['code'])
    for c in COUNTRIES)

html = HTML.replace('{{TITLE}}', PRODUCT_TITLE)
html = html.replace('{{DASHBOARD_H2}}', DASHBOARD_H2)
html = html.replace('{{DASHBOARD_SUB}}', DASHBOARD_SUB)
html = html.replace('{{XRAY_BUTTONS}}', XRAY_BUTTONS)
html = html.replace('{{SHELL_CSS}}', SHELL_CSS)
html = html.replace('{{TOPLINE_CSS}}', TOPLINE_CSS)
html = html.replace('{{VOC_CSS}}', VOC_CSS)
html = html.replace('{{MDD_CSS}}', MDD_CSS)
html = html.replace('{{MS_CSS}}', MS_CSS)
html = html.replace('{{TOPLINE_BODY}}', TOPLINE_BODY)
html = html.replace('/*<<BUNDLE>>*/', json.dumps(bundle, ensure_ascii=False))
html = html.replace('/*<<ENGINE>>*/', ENGINE_JS)
html = html.replace('/*<<VOC_FN>>*/', VOC_FN)
html = html.replace('/*<<MDD_FN>>*/', MDD_FN)
html = html.replace('/*<<MS_FN>>*/', MS_FN)

# House style: no long dashes anywhere in the rendered dashboard. One pass over the
# final HTML normalizes Tab 1 (Rynek), every template's UI chrome, and the inlined
# VOC / MDD / structure data. Covers literal chars AND HTML entities (the Rynek
# body uses &mdash;/&ndash;). All -> plain hyphen.
for _d in ('—', '–', '―', '&mdash;', '&ndash;', '&#8212;', '&#8211;', '&#x2014;', '&#x2013;'):
    html = html.replace(_d, '-')

out = os.path.join(BASE, 'index.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)

print('index.html: {:,} bytes'.format(os.path.getsize(out)))
print('Default selection: {} / {}'.format(DEFAULT_COUNTRY, DEFAULT_SEG))
for c in COUNTRIES:
    code = c['code']
    segs = SEGMENTS_BY_COUNTRY[code]
    voc_n = sum(1 for s in segs if voc_data[code][s])
    mdd_n = sum(1 for s in segs if mdd_data[code][s])
    struct = structure_data[code]
    from collections import Counter as _C
    struct_by_seg = dict(_C(p['type'] for p in struct))
    print('  {}: segments={} | VOC buckets={}/{} | MDD buckets={}/{} | Structure ASINs={} {}'.format(
        code, segs, voc_n, len(segs), mdd_n, len(segs), len(struct), struct_by_seg))
