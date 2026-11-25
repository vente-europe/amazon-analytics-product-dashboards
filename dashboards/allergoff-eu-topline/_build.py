"""Allergoff EU - Top Line build.

Reads the raw Helium 10 X-Ray exports in data/x-ray/raw/, detects the marketplace
from the URL domain, keeps ASINs with >= EUR 1,000 ASIN Revenue in the last 30 days,
dedupes by ASIN within a marketplace, writes data/x-ray/allergoff-{CODE}.csv and
renders index.html from _template.html (the Provecta EU Top Line page) by replacing
ONLY its CL_DATA block. Rendering engine stays verbatim.

Method (same as atopic-skin-detailed, decided 2026-11-23):
  12M units   = ASIN Sales (30d) x 12
  12M revenue = ASIN Revenue (30d) x 12
All four markets are EUR (DE/FR/IT/ES) -> no FX. Prices are gross (incl. VAT).

Run:  python _build.py
"""
import csv, glob, json, os, re, sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, 'data', 'x-ray', 'raw')
OUT_DIR = os.path.join(BASE, 'data', 'x-ray')
TEMPLATE = os.path.join(BASE, '_template.html')
OUT_HTML = os.path.join(BASE, 'index.html')

MIN_REV_30D = 1000.0           # EUR, last 30 days (Tom, 2026-11-25)
MULTIPLIER = 12
TOP_BRANDS = 10

DOMAIN_TO_CODE = {'amazon.de': 'DE', 'amazon.fr': 'FR', 'amazon.it': 'IT', 'amazon.es': 'ES'}
MARKET_META = {
    'DE': {'flag': '\U0001F1E9\U0001F1EA', 'name': 'Germany (DE)', 'color': '#2563eb'},
    'FR': {'flag': '\U0001F1EB\U0001F1F7', 'name': 'France (FR)',  'color': '#7c3aed'},
    'IT': {'flag': '\U0001F1EE\U0001F1F9', 'name': 'Italy (IT)',   'color': '#059669'},
    'ES': {'flag': '\U0001F1EA\U0001F1F8', 'name': 'Spain (ES)',   'color': '#d97706'},
}
# H10 lists the Allergoff listings under the brand "Novokill".
BRAND_ALIAS = {'novokill': 'Allergoff (Novokill)'}
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def num(v):
    s = re.sub(r'[€$£,\s]', '', str(v if v is not None else ''))
    try:
        return float(s)
    except ValueError:
        return 0.0


def market_of(rows):
    for r in rows:
        m = re.search(r'amazon\.(de|fr|it|es)/', r.get('URL') or '')
        if m:
            return DOMAIN_TO_CODE['amazon.' + m.group(1)]
    return None


markets = {}          # code -> list of kept rows
stats = {}            # code -> counts for the note / log
export_dates = set()
for path in sorted(glob.glob(os.path.join(RAW, '*.csv'))):
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', os.path.basename(path))
    if m:
        export_dates.add((int(m.group(1)), int(m.group(2))))
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    code = market_of(rows)
    if not code:
        sys.exit('Cannot detect marketplace for ' + path)
    if code in markets:
        sys.exit('Two raw files for ' + code + ' - keep one export per marketplace in data/x-ray/raw/')
    seen, kept, dups, below = set(), [], 0, 0
    for r in rows:
        asin = (r.get('ASIN') or '').strip()
        if not asin:
            continue
        if asin in seen:
            dups += 1
            continue
        seen.add(asin)
        if num(r.get('ASIN Revenue')) < MIN_REV_30D:
            below += 1
            continue
        kept.append(r)
    markets[code] = kept
    stats[code] = {'raw': len(rows), 'dups': dups, 'below': below, 'kept': len(kept)}
    with open(os.path.join(OUT_DIR, 'allergoff-%s.csv' % code), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(kept)

# Brand display name: alias first, else most frequent spelling across markets (SANYTOL/Sanytol).
spellings = defaultdict(Counter)
for rows in markets.values():
    for r in rows:
        b = (r.get('Brand') or '').strip() or 'Unknown'
        spellings[b.lower()][b] += 1


def brand_name(raw):
    key = ((raw or '').strip() or 'Unknown').lower()
    return BRAND_ALIAS.get(key) or spellings[key].most_common(1)[0][0]


mk_list, brand_rev, brand_units = [], Counter(), Counter()
for code, rows in markets.items():
    u30 = sum(num(r.get('ASIN Sales')) for r in rows)
    r30 = sum(num(r.get('ASIN Revenue')) for r in rows)
    meta = MARKET_META[code]
    mk_list.append({'code': code, 'flag': meta['flag'], 'name': meta['name'], 'color': meta['color'],
                    'currency': 'EUR', 'units30d': round(u30),
                    'units12m': round(u30 * MULTIPLIER), 'revenue12m': round(r30 * MULTIPLIER)})
    for r in rows:
        b = brand_name(r.get('Brand'))
        brand_rev[b] += num(r.get('ASIN Revenue')) * MULTIPLIER
        brand_units[b] += num(r.get('ASIN Sales')) * MULTIPLIER
mk_list.sort(key=lambda m: -m['revenue12m'])


def top_n(counter):
    items = counter.most_common()
    top = [{'name': n, 'value': round(v)} for n, v in items[:TOP_BRANDS]]
    rest = items[TOP_BRANDS:]
    if rest:
        top.append({'name': 'Other (%d)' % len(rest), 'value': round(sum(v for _, v in rest))})
    return top


def fmt_m(v):
    return '€%.1fM' % (v / 1e6) if v >= 1e6 else '€%dK' % round(v / 1e3)


tot_rev = sum(m['revenue12m'] for m in mk_list)
tot_units = sum(m['units12m'] for m in mk_list)
y, mo = max(export_dates) if export_dates else (None, None)
period = '%s %d' % (MONTHS[mo - 1], y) if y else ''
n_kept = sum(s['kept'] for s in stats.values())
n_below = sum(s['below'] for s in stats.values())
n_dups = sum(s['dups'] for s in stats.values())
codes = ' · '.join(m['code'] for m in mk_list)

CL = {
    'title': 'Dust Mite &amp; Textile Sprays — EU Markets  (Allergoff Competitive Landscape)',
    'subtitle': '12-Month Projection  |  Data: Last 30 Days (%s)' % period,
    'barTitle': 'Revenue by Marketplace — 12M (€)',
    'pieTitle': 'Unit Share by Marketplace — 12M',
    'tableTitle': 'Units by Marketplace — 12M',
    'currency': '€',
    'kpis': [
        {'value': fmt_m(tot_rev), 'label': 'Total 12M Revenue (all markets)'},
        {'value': '{:,}'.format(tot_units), 'label': 'Total 12M Units Sold'},
        {'value': '%d Markets' % len(mk_list), 'label': codes},
    ],
    'markets': mk_list,
    'brandRevTitle': 'Revenue Share by Brand — 12M (€)',
    'brandUnitTitle': 'Unit Share by Brand — 12M',
    'brandColors': ['#2563eb', '#dc2626', '#059669', '#d97706', '#7c3aed', '#0891b2', '#be185d',
                    '#65a30d', '#9333ea', '#ea580c', '#94a3b8'],
    'brandRevenue': top_n(brand_rev),
    'brandUnits': top_n(brand_units),
    'note': ('<strong>Data source:</strong> Helium 10 X-Ray extension — 30-day snapshot exported %s, '
             'one keyword export per marketplace (%s), duplicates removed by ASIN within each marketplace (%d). '
             '  <strong>Filter:</strong> ASINs below €%s ASIN Revenue in the last 30 days removed (%d removed, %d kept). '
             '  <strong>Methodology:</strong> 30-day figures × 12 = annual projection. Units = H10 ASIN Sales, '
             'revenue = H10 ASIN Revenue. All four markets in EUR, prices incl. VAT. '
             '  Brand “Novokill” in H10 = Allergoff. Revenue figures are category-level '
             '(all kept ASINs in each marketplace file summed), no products excluded by relevance.'
             ) % (period, ', '.join(sorted(markets)), n_dups, '{:,}'.format(int(MIN_REV_30D)), n_below, n_kept),
}

with open(TEMPLATE, encoding='utf-8') as f:
    html = f.read()
block = re.compile(r'var CL_DATA = \{.*?\n\};\n', re.S)
assert len(block.findall(html)) == 1, 'CL_DATA block not found exactly once in template'
html = block.sub(lambda _: 'var CL_DATA = ' + json.dumps(CL, ensure_ascii=False, indent=2) + ';\n', html)
html = html.replace('<title>Competitive Landscape — Provecta EU</title>', '<title>Allergoff EU — Top Line</title>')
html = html.replace('Competitive Landscape — Provecta EU</h1>', 'Allergoff EU — Top Line</h1>')
html = html.replace('Standalone template · competitive-landscape.html', '')
with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)

print('index.html written (%s bytes)' % '{:,}'.format(os.path.getsize(OUT_HTML)))
for m in mk_list:
    s = stats[m['code']]
    print('  %s: raw %d, dups %d, <1000 %d, kept %d | 12M units %s | 12M rev EUR %s' % (
        m['code'], s['raw'], s['dups'], s['below'], s['kept'],
        '{:,}'.format(m['units12m']), '{:,}'.format(m['revenue12m'])))
print('  TOTAL 12M rev EUR {:,} | units {:,}'.format(tot_rev, tot_units))
print('  Top brands (rev):', ', '.join('%s %s' % (b['name'], fmt_m(b['value'])) for b in CL['brandRevenue']))
