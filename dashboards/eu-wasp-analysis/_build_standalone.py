# -*- coding: utf-8 -*-
"""Build standalone index.html · multi-segment EU dashboard template.

Configure the dashboard by editing the CONFIG block below. Drop X-Ray CSVs into
data/x-ray/{DE,FR,IT,ES}/ and (optionally) sales history into
data/sales-data/{CODE}/, review VOC JSON into reviews/{CODE}/{Segment}/voc.json,
and Marketing Deep-Dive JSON into
data/competitor-listings/{CODE}/mdd-{segment-slug}.json. Then run:

    py _build_standalone.py

→ index.html is regenerated with one tab per segment for Market Structure,
Reviews VOC, and Marketing Deep-Dive (so 3 segments → 1 + 3 + 3 + 3 = 10 tabs).
Treatment Methods tab from the source dashboard has been removed in this template.
"""
import json, os, re
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))

# ===========================================================================
# CONFIG · edit these to point the template at your product/data
# ===========================================================================

# Product / dashboard identity (used in browser title + dashboard header)
PRODUCT_NAME = 'Wasp Traps'
PRODUCT_TITLE_SUFFIX = '(DE, FR, UK)'
DASHBOARD_SUBTITLE = 'Data: Helium 10 X-Ray (30-day snapshot × 12 projection) · 3 markets (DE, FR, UK)'

# Segments · drives the tab list. Each segment becomes:
#   * one Market Structure tab     (e.g. 'Market Structure (Lure)')
#   * one Reviews VOC tab          (e.g. 'Reviews VOC · Lure')
#   * one Marketing Deep-Dive tab  (e.g. 'Marketing Deep-Dive · Lure')
# The CSV "Focus"/"Segment" column must contain values matching these names
# (case-insensitive; a row's value is matched to the segment whose name it
# equals OR starts with).
SEGMENTS = ['Lure', 'Electric']

# Which CSV column holds the segment classification. The first non-empty
# column in this list (per row) wins.
SEGMENT_COLUMNS = ['Focus', 'Segment']

# X-Ray export window. Helium 10's "last 30 days" snapshot ends on this date.
# Used by per-ASIN 12M projection: ASINs without sales history get corrected
# by the seasonality index for the export-window months, then * 12.
# IMPORTANT: update this date every time you re-export the X-Ray CSVs.
# Set to None to auto-detect (uses today's date · only safe if you rebuild
# the dashboard the same day you exported).
XRAY_EXPORT_DATE = date(2026, 4, 29)

# Per-country X-Ray CSV file names (one per country, dropped into
# data/x-ray/{CODE}/). Override to match the actual filenames you exported.
countries = [
    {'code': 'DE', 'name': 'Germany',        'flag': '\U0001F1E9\U0001F1EA', 'csv': 'Wasps DE.csv', 'currency': '€'},
    {'code': 'FR', 'name': 'France',         'flag': '\U0001F1EB\U0001F1F7', 'csv': 'Wasp FR.csv', 'currency': '€'},
    {'code': 'UK', 'name': 'United Kingdom', 'flag': '\U0001F1EC\U0001F1E7', 'csv': 'Wasps UK.csv', 'currency': '£'},
]

# X-Ray Google Sheet URLs shown as buttons in the header (one per country).
# Replace '#' with the sheet URL once it's set up.
xray_links = {
    'DE': '#',
    'FR': '#',
    'UK': '#',
}

# Currency conversion to EUR. UK X-Ray prices are in £ · converted at build
# time so the dashboard can display every market in € consistently.
# Tries live ECB rate first; falls back to FX_FALLBACK if offline.
FX_FALLBACK = {'EUR': 1.0, 'GBP': 1.18, 'USD': 0.92}

def _live_fx_to_eur():
    rates = dict(FX_FALLBACK)
    import urllib.request, json as _j
    for url in ('https://api.frankfurter.dev/v1/latest?base=EUR',
                'https://api.frankfurter.app/latest?from=EUR'):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'wasp-dashboard/1.0'})
            with urllib.request.urlopen(req, timeout=5) as r:
                d = _j.loads(r.read().decode('utf-8'))
            for ccy, v in (d.get('rates') or {}).items():
                if v: rates[ccy] = 1.0 / float(v)
            rates['EUR'] = 1.0
            print('FX (live, {}): GBP={:.4f} EUR, USD={:.4f} EUR'.format(url.split('/')[2], rates.get('GBP', 0), rates.get('USD', 0)))
            return rates
        except Exception as e:
            print('FX fetch from {} failed: {}'.format(url.split('/')[2], e))
    print('Using FX fallback rates')
    return rates

FX_TO_EUR = _live_fx_to_eur()
COUNTRY_CURRENCY = {'DE': 'EUR', 'FR': 'EUR', 'UK': 'GBP'}

# ===========================================================================
# Derived constants · do not edit
# ===========================================================================

# Resolve XRAY_EXPORT_DATE to a concrete date (today if None)
if XRAY_EXPORT_DATE is None:
    XRAY_EXPORT_DATE = date.today()

XRAY_WINDOW_START = XRAY_EXPORT_DATE - timedelta(days=29)
SEASONALITY_WINDOW_START = date(XRAY_EXPORT_DATE.year - 1, XRAY_EXPORT_DATE.month, 1)
SEASONALITY_WINDOW_END   = date(XRAY_EXPORT_DATE.year, XRAY_EXPORT_DATE.month, 1) - timedelta(days=1)
ASIN_12M_WINDOW_START = XRAY_EXPORT_DATE - timedelta(days=364)
ASIN_12M_WINDOW_END   = XRAY_EXPORT_DATE

def _slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

# Segment slug map: human name -> URL-safe slug. Used to build tab IDs and
# MDD filenames so the Python and JS sides agree.
SEGMENT_SLUGS = {seg: _slug(seg) for seg in SEGMENTS}

# Color per segment, used everywhere the dashboard renders a segment
# (KPI card border, pie slice, badge background). Cycles if you have
# more segments than colors.
SEGMENT_PALETTE = ['#16a34a', '#dc2626', '#2563eb', '#f59e0b', '#8b5cf6', '#0891b2', '#db2777', '#65a30d']

# Tab list · auto-generated from SEGMENTS. Order: Main Segments, then all
# Reviews VOC tabs, then all MDD tabs. Market Structure tabs were removed
# because the same per-segment data (Brand Summary + Top 20 ASINs + brand
# pies + brand-share line charts) now lives inside the Main Segments tab.
EM_DASH = '·'
tabs = [{'id': 'main-segments', 'label': 'Main Segments'}]
for _seg in SEGMENTS:
    tabs.append({'id': 'reviews-' + SEGMENT_SLUGS[_seg],
                 'label': 'Reviews VOC ' + EM_DASH + ' ' + _seg,
                 'segment': _seg})
for _seg in SEGMENTS:
    tabs.append({'id': 'marketing-deep-dive-' + SEGMENT_SLUGS[_seg],
                 'label': 'Marketing Deep-Dive ' + EM_DASH + ' ' + _seg,
                 'segment': _seg})


# ── CSV helpers ──────────────────────────────────────────────────────────────
def numv(v):
    if v is None: return 0.0
    s = str(v).replace(',', '').replace('€', '').replace('$', '').strip()
    if s == '' or s.lower() == 'nan': return 0.0
    try: return float(s)
    except: return 0.0

def read_csv(path):
    import csv
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

# ── Sales history + seasonality ─────────────────────────────────────────────
def _load_sales_folder(folder, label):
    """Read all `{Segment}-{ASIN}-sales-3y.csv` files from `folder`, gated by SEGMENTS.

    Filename convention: `{Segment}-{ASIN}-sales-3y.csv`. Files whose segment
    prefix is not in SEGMENTS (e.g. leftover Sticky CSVs from before the
    segment was dropped) are skipped. ASIN-only filenames `{ASIN}-sales-3y.csv`
    are still accepted. Returns {asin: {date: units}}."""
    import csv
    result = {}
    if not os.path.isdir(folder):
        return result
    seg_lc = {s.lower() for s in SEGMENTS}
    skipped = 0
    for fname in sorted(os.listdir(folder)):
        if not fname.endswith('-sales-3y.csv'):
            continue
        m = re.search(r'(B0[A-Z0-9]{8})-sales-3y\.csv$', fname)
        if not m:
            continue
        prefix = fname[:m.start()].rstrip('-').lower()
        if prefix and prefix not in seg_lc:
            skipped += 1
            continue
        asin = m.group(1)
        path = os.path.join(folder, fname)
        series = {}
        try:
            with open(path, encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                for r in reader:
                    t = (r.get('Time') or '').strip().strip('"')
                    if len(t) < 10:
                        continue
                    try:
                        d = datetime.strptime(t[:10], '%Y-%m-%d').date()
                    except ValueError:
                        continue
                    try:
                        u = float((r.get('Sales') or '0').strip().strip('"') or 0)
                    except ValueError:
                        u = 0.0
                    series[d] = u
        except Exception as e:
            print(f'  warn: failed to read {path}: {e}')
            continue
        if series:
            result[asin] = series
    if skipped:
        print(f'  {label}: skipped {skipped} file(s) with segment prefix outside SEGMENTS={SEGMENTS}')
    return result


def load_country_daily_sales(code):
    """Sales-data files: drives seasonality curve + per-ASIN trailing-365d 12M.

    Kept as a small, hand-curated set so the seasonality shape is stable. To
    add more brand coverage to the % Unit Share line charts, drop files into
    `data/Line chart {code}/` instead — that folder only feeds the brand-share
    chart, not seasonality."""
    return _load_sales_folder(os.path.join(BASE, 'data', 'sales-data', code), code)


def load_country_linechart_sales(code):
    """Line chart files: drives the per-segment % Unit Share brand chart only.

    Folder name is literally `Line chart {code}/` (with space). Filename
    convention is the same as sales-data: `{Segment}-{ASIN}-sales-3y.csv`."""
    return _load_sales_folder(os.path.join(BASE, 'data', f'Line chart {code}'), f'{code} line-chart')


def compute_seasonality(daily_by_asin):
    """Total-market monthly seasonality index (Jan..Dec, 1.0 = average month).
    Aggregates daily sales across all ASINs in the country, bins into calendar
    months over SEASONALITY_WINDOW_START → SEASONALITY_WINDOW_END (12 complete
    months), and normalizes each month's total by the 12-month mean."""
    month_totals = [0.0] * 12  # index 0 = Jan
    for _asin, series in daily_by_asin.items():
        for d, u in series.items():
            if SEASONALITY_WINDOW_START <= d <= SEASONALITY_WINDOW_END:
                month_totals[d.month - 1] += u
    total = sum(month_totals)
    if total == 0:
        return None
    mean = total / 12.0
    indices = [round(m / mean, 3) for m in month_totals]
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    peak_i = max(range(12), key=lambda i: indices[i])
    nz = [i for i in range(12) if indices[i] > 0]
    trough_i = min(nz, key=lambda i: indices[i]) if nz else 0
    return {
        'months': indices,
        'monthLabels': month_names,
        'peakMonth': month_names[peak_i],
        'peakIdx': indices[peak_i],
        'troughMonth': month_names[trough_i],
        'troughIdx': indices[trough_i],
        'asinCount': len(daily_by_asin),
        'startDate': SEASONALITY_WINDOW_START.isoformat(),
        'endDate': SEASONALITY_WINDOW_END.isoformat(),
    }

def compute_brand_monthly_share(daily_by_asin, products, top_n=8):
    """Per-brand monthly unit share over the 12-month seasonality window.

    Only ASINs with a sales history CSV contribute (true monthly data). Brands
    are ranked by total units across the window; brands beyond top_n collapse
    into 'Other'. Returns None if no history is available."""
    if not daily_by_asin:
        return None
    asin_brand = {p['asin']: p['brand'] for p in products}

    # Build 12 month buckets matching SEASONALITY_WINDOW (Mar 2025 → Feb 2026)
    months = []
    y, m = SEASONALITY_WINDOW_START.year, SEASONALITY_WINDOW_START.month
    for _ in range(12):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    month_labels = [date(y, m, 1).strftime('%b %Y') for (y, m) in months]
    month_index = {ym: i for i, ym in enumerate(months)}

    brand_monthly = {}   # brand -> [12 floats]
    total_monthly = [0.0] * 12
    for asin, series in daily_by_asin.items():
        # Skip ASINs not in the current X-Ray (e.g., removed during cleanup
        # but sales-data CSV still on disk). Avoids "Unknown" brand label.
        if asin not in asin_brand:
            continue
        brand = asin_brand[asin]
        bucket = brand_monthly.setdefault(brand, [0.0] * 12)
        for d, u in series.items():
            if SEASONALITY_WINDOW_START <= d <= SEASONALITY_WINDOW_END:
                idx = month_index.get((d.year, d.month))
                if idx is not None:
                    bucket[idx] += u
                    total_monthly[idx] += u
    if sum(total_monthly) == 0:
        return None

    brand_totals = [(b, sum(v)) for b, v in brand_monthly.items()]
    brand_totals.sort(key=lambda x: x[1], reverse=True)
    top = brand_totals[:top_n]
    rest = brand_totals[top_n:]
    out_brands = []
    for b, _t in top:
        units = brand_monthly[b]
        share = [
            round(units[i] / total_monthly[i] * 100, 2) if total_monthly[i] > 0 else 0.0
            for i in range(12)
        ]
        out_brands.append({
            'brand': b,
            'units': [round(u, 1) for u in units],
            'share': share,
        })
    if rest:
        other_units = [0.0] * 12
        for b, _t in rest:
            for i in range(12):
                other_units[i] += brand_monthly[b][i]
        other_share = [
            round(other_units[i] / total_monthly[i] * 100, 2) if total_monthly[i] > 0 else 0.0
            for i in range(12)
        ]
        out_brands.append({
            'brand': f'Other ({len(rest)})',
            'units': [round(u, 1) for u in other_units],
            'share': other_share,
        })

    return {
        'monthLabels': month_labels,
        'totalMonthly': [round(u, 1) for u in total_monthly],
        'brands': out_brands,
        'asinCount': len(daily_by_asin),
        'brandCount': len(brand_totals),
        'startDate': SEASONALITY_WINDOW_START.isoformat(),
        'endDate':   SEASONALITY_WINDOW_END.isoformat(),
    }

def asin_12m_from_history(series):
    """Sum daily Sales in [ASIN_12M_WINDOW_START, ASIN_12M_WINDOW_END]."""
    total = 0.0
    for d, u in series.items():
        if ASIN_12M_WINDOW_START <= d <= ASIN_12M_WINDOW_END:
            total += u
    return total

def get_xray_end_date():
    """X-Ray window end date: explicit XRAY_EXPORT_DATE if set, else today."""
    return XRAY_EXPORT_DATE or date.today()


def xray_window_seasonality_index(seasonality):
    """Weighted seasonality index for the X-Ray's 30-day export window.

    Walks each of the 30 days in the window (ending on get_xray_end_date()),
    looks up the monthly seasonality index for each day's month, and averages.
    For a window like Mar 30 – Apr 29: 1 day at Mar_index + 29 days at Apr_index,
    averaged over 30 = a near-April figure."""
    if not seasonality:
        return 1.0
    indices = seasonality['months']  # 12 entries, Jan..Dec
    end_d = get_xray_end_date()
    total = 0.0
    days_counted = 0
    for i in range(30):
        d = end_d - timedelta(days=i)
        idx = indices[d.month - 1]
        if idx > 0:
            total += idx
            days_counted += 1
    if days_counted == 0:
        return 1.0
    return total / days_counted

def build_country(code, csv_name):
    rows = read_csv(os.path.join(BASE, 'data', 'x-ray', code, csv_name))
    price_col = next((k for k in rows[0].keys() if 'price' in k.lower()), None)
    fx = FX_TO_EUR.get(COUNTRY_CURRENCY.get(code, 'EUR'), 1.0)

    # Sales-data: drives seasonality curve + per-ASIN trailing-365d 12M.
    daily_by_asin = load_country_daily_sales(code)
    seasonality   = compute_seasonality(daily_by_asin)
    xray_idx      = xray_window_seasonality_index(seasonality)
    real_12m      = {a: asin_12m_from_history(s) for a, s in daily_by_asin.items()}
    proj_counts   = {'history': 0, 'seasonality': 0, 'flat': 0}

    # Line chart files: richer per-ASIN history used ONLY for the
    # % Unit Share · Brand vs. Segment Total line charts. Kept separate from
    # sales-data so dropping more files here doesn't reshape the seasonality
    # curve. Falls back to sales-data if Line chart folder is empty.
    linechart_daily = load_country_linechart_sales(code) or daily_by_asin

    products = []
    for r in rows:
        focus_raw = ''
        for col in SEGMENT_COLUMNS:
            v = (r.get(col) or '').strip()
            if v:
                focus_raw = v
                break
        # Only include products with a clear Lure/Electric/Sticky segment.
        # Blank-segment rows are excluded (the user maintains the X-Ray
        # CSVs and removes irrelevant products there).
        focus = None
        focus_lc = focus_raw.lower()
        for seg in SEGMENTS:
            if focus_lc == seg.lower() or focus_lc.startswith(seg.lower()):
                focus = seg
                break
        if focus is None:
            continue
        price = numv(r.get(price_col)) * fx  # convert to EUR
        sales30d = numv(r.get('ASIN Sales'))
        rev30d = numv(r.get('ASIN Revenue')) * fx
        if sales30d == 0 and rev30d > 0 and price > 0:
            sales30d = round(rev30d / price)
        asin = (r.get('ASIN') or '').strip()

        # 12M projection: prefer real trailing-365d sales history; otherwise
        # correct the X-Ray 30d figure by the seasonality index for the
        # X-Ray export window (auto-aligned via get_xray_end_date()) so it
        # represents an average month, then * 12. Final fallback is flat * 12.
        if asin in real_12m and real_12m[asin] > 0:
            units12m = int(round(real_12m[asin]))
            proj_counts['history'] += 1
        elif seasonality and xray_idx > 0:
            avg_monthly = sales30d / xray_idx
            units12m = int(round(avg_monthly * 12))
            proj_counts['seasonality'] += 1
        else:
            units12m = int(round(sales30d * 12))
            proj_counts['flat'] += 1
        method = ''  # template: Treatment Methods tab removed
        products.append({
            'asin': r.get('ASIN', '').strip(),
            'brand': (r.get('Brand') or 'Unknown').strip() or 'Unknown',
            'focus': focus,
            'type': (r.get('Type') or 'Unknown').strip() or 'Unknown',
            'method': method,
            'title': (r.get('Product Details') or '').strip()[:200],
            'price': round(price, 2),
            'rating': numv(r.get('Ratings')),
            'reviewCount': int(numv(r.get('Review Count'))),
            'age': int(numv(r.get('Seller Age (mo)'))),
            'units12m': units12m,
            'revenue12m': round(units12m * price),
        })

    # Segment aggregation
    segs = {}
    for p in products:
        s = segs.setdefault(p['focus'], {'units': 0, 'revenue': 0, 'count': 0, 'brands': {}})
        s['units'] += p['units12m']
        s['revenue'] += p['revenue12m']
        s['count'] += 1
        b = s['brands'].setdefault(p['brand'], {'units': 0, 'revenue': 0})
        b['units'] += p['units12m']
        b['revenue'] += p['revenue12m']

    def top_brands(bdict, metric, n=8):
        items = sorted(
            [{'brand': k, 'units': v['units'], 'revenue': v['revenue']} for k, v in bdict.items()],
            key=lambda x: x[metric], reverse=True
        )
        if len(items) <= n:
            return items
        top = items[:n]
        rest = items[n:]
        top.append({
            'brand': f'Other ({len(rest)})',
            'units': sum(x['units'] for x in rest),
            'revenue': sum(x['revenue'] for x in rest),
        })
        return top

    segments = []
    for name in SEGMENTS:
        s = segs.get(name, {'units': 0, 'revenue': 0, 'count': 0, 'brands': {}})
        segments.append({
            'name': name,
            'units': s['units'],
            'revenue': s['revenue'],
            'count': s['count'],
            'brandsByUnits': top_brands(s['brands'], 'units'),
            'brandsByRevenue': top_brands(s['brands'], 'revenue'),
        })

    total_units = sum(s['units'] for s in segments)
    total_rev = sum(s['revenue'] for s in segments)

    # Per-segment monthly brand-share: one chart per segment (Lure, Electric).
    # Reads from `linechart_daily` (data/Line chart {code}/) so dropping more
    # files there shows more brand coverage on the chart without disturbing
    # the seasonality curve (which stays based on sales-data/).
    brand_monthly_share_by_segment = {}
    for seg in SEGMENTS:
        seg_products = [p for p in products if p['focus'] == seg]
        seg_asins = {p['asin'] for p in seg_products}
        seg_daily = {a: s for a, s in linechart_daily.items() if a in seg_asins}
        share = compute_brand_monthly_share(seg_daily, seg_products)
        if share:
            brand_monthly_share_by_segment[seg] = share

    return {
        'segments': segments,
        'totalUnits': total_units,
        'totalRevenue': total_rev,
        'asinCount': len(products),
        'seasonality': seasonality,
        'brandMonthlyShareBySegment': brand_monthly_share_by_segment,
        'projectionCounts': proj_counts,
        'xrayExportDate': XRAY_EXPORT_DATE.isoformat(),
        'xrayWindowStart': XRAY_WINDOW_START.isoformat(),
        'xrayWindowIndex': round(xray_idx, 3) if xray_idx else None,
        'marketStructure': {seg: market_structure([p for p in products if p['focus'] == seg]) for seg in SEGMENTS},
    }

def treatment_methods(classified):
    """Physical vs Chemical breakdown for products with a Treatment Method classification."""
    total_units = sum(p['units12m'] for p in classified)
    total_rev   = sum(p['revenue12m'] for p in classified)

    # Per-method totals
    methods = {}
    for p in classified:
        m = methods.setdefault(p['method'], {'units': 0, 'revenue': 0, 'asins': 0, 'brands': {}, 'types': {}, 'products': []})
        m['units']   += p['units12m']
        m['revenue'] += p['revenue12m']
        m['asins']   += 1
        m['products'].append(p)
        b = m['brands'].setdefault(p['brand'], {'units': 0, 'revenue': 0})
        b['units']   += p['units12m']
        b['revenue'] += p['revenue12m']
        t = m['types'].setdefault(p['type'], {'units': 0, 'revenue': 0})
        t['units']   += p['units12m']
        t['revenue'] += p['revenue12m']

    def top_brands(bdict, metric, n=8):
        items = sorted(
            [{'brand': k, 'units': v['units'], 'revenue': v['revenue']} for k, v in bdict.items()],
            key=lambda x: x[metric], reverse=True
        )
        if len(items) <= n: return items
        top = items[:n]
        rest = items[n:]
        top.append({
            'brand': f'Other ({len(rest)})',
            'units': sum(x['units'] for x in rest),
            'revenue': sum(x['revenue'] for x in rest),
        })
        return top

    methods_out = []
    for name in ['Physical', 'Chemical', 'Physical + Chemical']:
        if name not in methods: continue
        m = methods[name]
        top3_by_units = sorted(m['products'], key=lambda p: p['units12m'], reverse=True)[:3]
        methods_out.append({
            'name': name,
            'units': m['units'],
            'revenue': m['revenue'],
            'asins': m['asins'],
            'unitShare': (m['units'] / total_units * 100) if total_units else 0,
            'revShare':  (m['revenue'] / total_rev * 100) if total_rev else 0,
            'avgPrice': (m['revenue'] / m['units']) if m['units'] else 0,
            'brandsByUnits':   top_brands(m['brands'], 'units'),
            'brandsByRevenue': top_brands(m['brands'], 'revenue'),
            'topAsinsByUnits': [{
                'asin':  p['asin'],
                'brand': p['brand'],
                'title': p['title'],
                'price': p['price'],
                'units': p['units12m'],
            } for p in top3_by_units],
        })

    # Type × Method breakdown for the summary table
    type_method = []
    for p in classified:
        type_method.append({
            'type': p['type'],
            'method': p['method'],
            'units': p['units12m'],
            'revenue': p['revenue12m'],
        })
    # group by (type, method)
    tm_agg = {}
    for r in type_method:
        key = (r['type'], r['method'])
        x = tm_agg.setdefault(key, {'units': 0, 'revenue': 0})
        x['units']   += r['units']
        x['revenue'] += r['revenue']
    type_method_rows = []
    for (t, m), v in tm_agg.items():
        type_method_rows.append({
            'type': t, 'method': m,
            'units': v['units'], 'revenue': v['revenue'],
            'unitShare': (v['units'] / total_units * 100) if total_units else 0,
            'revShare':  (v['revenue'] / total_rev * 100) if total_rev else 0,
        })
    type_method_rows.sort(key=lambda r: r['revenue'], reverse=True)

    # Brand summary (cross-method)
    brand_summary = {}
    for p in classified:
        b = brand_summary.setdefault(p['brand'], {
            'brand': p['brand'], 'revenue': 0, 'units': 0, 'asins': 0,
            'methods': set(), 'types': set(),
            'ratingsSum': 0, 'ratingsN': 0, 'reviews': 0,
        })
        b['revenue'] += p['revenue12m']
        b['units']   += p['units12m']
        b['asins']   += 1
        b['methods'].add(p['method'])
        b['types'].add(p['type'].replace('Treatment ', '').replace('Prevention ', ''))
        if p['rating'] > 0:
            b['ratingsSum'] += p['rating']
            b['ratingsN']   += 1
        b['reviews'] += p['reviewCount']
    brand_rows = []
    for b in brand_summary.values():
        brand_rows.append({
            'brand': b['brand'],
            'methods': sorted(b['methods']),
            'typesStr': ', '.join(sorted(b['types'])),
            'share': (b['revenue'] / total_rev * 100) if total_rev else 0,
            'asins': b['asins'],
            'avgRating': round(b['ratingsSum'] / b['ratingsN'], 2) if b['ratingsN'] else 0,
            'totalReviews': b['reviews'],
        })
    brand_rows.sort(key=lambda x: x['share'], reverse=True)

    # All products
    all_products = sorted(classified, key=lambda p: p['revenue12m'], reverse=True)
    all_rows = []
    for p in all_products:
        all_rows.append({
            'asin': p['asin'], 'brand': p['brand'], 'title': p['title'],
            'method': p['method'], 'price': p['price'],
            'revenue': p['revenue12m'], 'reviews': p['reviewCount'], 'age': p['age'],
        })

    return {
        'totalUnits': total_units,
        'totalRevenue': total_rev,
        'asinCount': len(classified),
        'methods': methods_out,
        'typeMethodRows': type_method_rows,
        'brandRows': brand_rows,
        'allRows': all_rows,
    }

def market_structure(seg_products):
    """Aggregates for a Market Structure tab (given one segment's products)."""
    total_units = sum(p['units12m'] for p in seg_products)
    total_rev   = sum(p['revenue12m'] for p in seg_products)
    n = len(seg_products)

    # Concentration (by revenue)
    sorted_by_rev = sorted(seg_products, key=lambda p: p['revenue12m'], reverse=True)
    def top_share(k):
        if total_rev == 0: return 0.0
        return sum(p['revenue12m'] for p in sorted_by_rev[:k]) / total_rev * 100

    # Brands
    brands_map = {}
    for p in seg_products:
        b = brands_map.setdefault(p['brand'], {'revenue': 0, 'units': 0, 'asins': 0, 'ratingsSum': 0, 'ratingsN': 0, 'reviews': 0})
        b['revenue'] += p['revenue12m']
        b['units']   += p['units12m']
        b['asins']   += 1
        if p['rating'] > 0:
            b['ratingsSum'] += p['rating']
            b['ratingsN']   += 1
        b['reviews'] += p['reviewCount']
    brands = []
    for name, b in brands_map.items():
        brands.append({
            'brand': name,
            'revenue': b['revenue'],
            'units': b['units'],
            'share': (b['revenue'] / total_rev * 100) if total_rev else 0,
            'asins': b['asins'],
            'avgRating': round(b['ratingsSum'] / b['ratingsN'], 2) if b['ratingsN'] else 0,
            'totalReviews': b['reviews'],
        })
    brands.sort(key=lambda x: x['revenue'], reverse=True)
    top_brand = brands[0] if brands else {'brand': '\u00b7', 'share': 0}

    # Types
    types_map = {}
    for p in seg_products:
        t = types_map.setdefault(p['type'], {'asins': 0, 'units': 0, 'revenue': 0, 'ratingsSum': 0, 'ratingsN': 0, 'brands': {}, 'products': []})
        t['asins']   += 1
        t['units']   += p['units12m']
        t['revenue'] += p['revenue12m']
        t['products'].append(p)
        if p['rating'] > 0:
            t['ratingsSum'] += p['rating']
            t['ratingsN']   += 1
        tb = t['brands'].setdefault(p['brand'], {'units': 0, 'revenue': 0})
        tb['units']   += p['units12m']
        tb['revenue'] += p['revenue12m']

    def top_brands_in_type(bdict, metric, n=6):
        items = sorted(
            [{'brand': k, 'units': v['units'], 'revenue': v['revenue']} for k, v in bdict.items()],
            key=lambda x: x[metric], reverse=True
        )
        if len(items) <= n: return items
        top = items[:n]
        rest = items[n:]
        top.append({
            'brand': f'Other ({len(rest)})',
            'units': sum(x['units'] for x in rest),
            'revenue': sum(x['revenue'] for x in rest),
        })
        return top

    types = []
    for name, t in types_map.items():
        top3_by_units = sorted(t['products'], key=lambda p: p['units12m'], reverse=True)[:3]
        types.append({
            'name': name,
            'asins': t['asins'],
            'units': t['units'],
            'revenue': t['revenue'],
            'unitShare': (t['units']   / total_units * 100) if total_units else 0,
            'revShare':  (t['revenue'] / total_rev   * 100) if total_rev   else 0,
            'avgRating': round(t['ratingsSum'] / t['ratingsN'], 2) if t['ratingsN'] else 0,
            'brandsByUnits':   top_brands_in_type(t['brands'], 'units'),
            'brandsByRevenue': top_brands_in_type(t['brands'], 'revenue'),
            'topAsinsByUnits': [{
                'asin':  p['asin'],
                'brand': p['brand'],
                'title': p['title'],
                'price': p['price'],
                'units': p['units12m'],
            } for p in top3_by_units],
        })
    types.sort(key=lambda x: x['revenue'], reverse=True)

    # Top ASINs (top 20 by revenue, used by Main Segments tables and Market Structure)
    top_asins = []
    for p in sorted_by_rev[:20]:
        top_asins.append({
            'asin': p['asin'], 'brand': p['brand'], 'title': p['title'],
            'price': p['price'], 'units': p['units12m'], 'revenue': p['revenue12m'],
            'revShare': (p['revenue12m'] / total_rev * 100) if total_rev else 0,
            'reviews': p['reviewCount'], 'age': p['age'],
        })

    return {
        'totalUnits': total_units,
        'totalRevenue': total_rev,
        'asinCount': n,
        'top1Share':  round(top_share(1), 1),
        'top3Share':  round(top_share(3), 1),
        'top5Share':  round(top_share(5), 1),
        'top10Share': round(top_share(10), 1),
        'topBrand':      top_brand['brand'],
        'topBrandShare': round(top_brand['share'], 1),
        'types':  types,
        'brands': brands,
        'topAsins': top_asins,
    }

# ── Build per-country data for Main Segments tab ────────────────────────────
main_segments_data = {c['code']: build_country(c['code'], c['csv']) for c in countries}

# ── Per-country VOC reviews, split by segment (Prevention / Treatment) ──
# Drop voc.json into reviews/{CODE}/Prevention/ or reviews/{CODE}/Treatment/
def load_voc(code, segment):
    path = os.path.join(BASE, 'reviews', code, segment, 'voc.json')
    if not os.path.exists(path): return {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'  warn: failed to load VOC for {code}/{segment}: {e}')
        return {}
voc_data = {seg: {c['code']: load_voc(c['code'], seg) for c in countries} for seg in SEGMENTS}

# ── Per-country Marketing Deep-Dive (optional · drop mdd.json into data/competitor-listings/{CODE}/) ──
def load_mdd(code, segment):
    """Load per-segment MDD JSON. Falls back to legacy mdd.json if present."""
    fname = f'mdd-{segment}.json'
    path = os.path.join(BASE, 'data', 'competitor-listings', code, fname)
    if not os.path.exists(path):
        # legacy single-file fallback (old anti-fungus-style layout)
        legacy = os.path.join(BASE, 'data', 'competitor-listings', code, 'mdd.json')
        if segment == 'treatment' and os.path.exists(legacy):
            path = legacy
        else:
            return {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f'  warn: failed to load MDD ({segment}) for {code}: {e}')
        return {}
mdd_data = {seg: {c['code']: load_mdd(c['code'], SEGMENT_SLUGS[seg]) for c in countries} for seg in SEGMENTS}

# ── Global brand → color map (stable across all tabs/countries/pies) ────────
BRAND_PALETTE_PY = [
    '#2563eb','#dc2626','#16a34a','#f59e0b','#8b5cf6','#0891b2','#db2777','#65a30d',
    '#ea580c','#0284c7','#9333ea','#ca8a04','#059669','#e11d48','#7c3aed','#0d9488',
    '#b45309','#4f46e5','#be123c','#15803d','#7c2d12','#1d4ed8','#b91c1c','#a16207',
]
_brand_totals = {}
for code, cdata in main_segments_data.items():
    for seg in cdata['segments']:
        for b in seg['brandsByRevenue']:
            if b['brand'].startswith('Other ('):
                continue
            _brand_totals[b['brand']] = _brand_totals.get(b['brand'], 0) + b['revenue']
_ordered_brands = sorted(_brand_totals.keys(), key=lambda k: _brand_totals[k], reverse=True)
brand_colors = {b: BRAND_PALETTE_PY[i % len(BRAND_PALETTE_PY)] for i, b in enumerate(_ordered_brands)}


def _build_tabs_dict():
    """Assembles the bundle['tabs'] mapping by looping over SEGMENTS so each
    segment gets its own Market Structure / Reviews / Marketing Deep-Dive tab.
    Tab IDs and segment metadata stay in sync with the `tabs` list at the top
    of this file."""
    out = {
        'main-segments': {
            'label': 'Main Segments',
            'countries': main_segments_data,
        },
    }
    for seg in SEGMENTS:
        slug = SEGMENT_SLUGS[seg]
        out['reviews-' + slug] = {
            'label': 'Reviews VOC ' + EM_DASH + ' ' + seg,
            'segment': seg,
            'countries': voc_data[seg],
        }
    for seg in SEGMENTS:
        slug = SEGMENT_SLUGS[seg]
        out['marketing-deep-dive-' + slug] = {
            'label': 'Marketing Deep-Dive ' + EM_DASH + ' ' + seg,
            'segment': seg,
            'countries': mdd_data[seg],
        }
    return out

bundle = {
    'title': PRODUCT_NAME + ' ' + PRODUCT_TITLE_SUFFIX,
    'subtitle': DASHBOARD_SUBTITLE,
    'currency': '\u20ac',
    'segments': SEGMENTS,
    'segmentColors': {seg: SEGMENT_PALETTE[i % len(SEGMENT_PALETTE)] for i, seg in enumerate(SEGMENTS)},
    'xrayLinks': xray_links,
    'countries': countries,
    'brandColors': brand_colors,
    'brandPalette': BRAND_PALETTE_PY,
    'tabs': _build_tabs_dict(),
}

shell = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{{TITLE}}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<style>
  *,*::before,*::after { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; background: #f1f5f9; color: #0f172a; font-size: 14px; }
  h2 { color: #1e293b; font-size: 1.2rem; font-weight: 600; margin: 0 0 16px; }
  h3 { color: #1e293b; font-size: .95rem; font-weight: 600; margin: 0 0 10px; }

  /* Header */
  .dashboard-header { background: #0f2942; color: #fff; padding: 18px 32px; display: flex; justify-content: space-between; align-items: center; gap: 24px; flex-wrap: wrap; }
  .dashboard-header h2 { margin: 0; font-size: 1.35rem; font-weight: 600; color: #fff; }
  .dashboard-header .sub { font-size: .78rem; color: #cbd5e1; display: block; margin-top: 4px; }
  .header-titles { flex: 1; min-width: 0; }
  .xray-btn-row { display: flex; gap: 8px; flex-wrap: wrap; }
  .xray-btn { background: #16a34a; color: #fff; padding: 8px 14px; border-radius: 6px; font-size: .76rem; font-weight: 600; text-decoration: none; white-space: nowrap; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 1px 3px rgba(0,0,0,.2); transition: background .15s; }
  .xray-btn:hover { background: #15803d; }
  .xray-btn svg { width: 14px; height: 14px; }

  /* Body */
  .dashboard-body { padding: 24px 32px; }

  /* Tabs */
  .tabs { display: flex; gap: 4px; border-bottom: 2px solid #e2e8f0; margin-bottom: 0; flex-wrap: wrap; position: sticky; top: 0; z-index: 30; background: #f1f5f9; padding-top: 12px; margin-left: -32px; margin-right: -32px; padding-left: 32px; padding-right: 32px; }
  .tab { padding: 10px 18px; background: transparent; border: none; cursor: pointer; font-size: .85rem; font-weight: 600; color: #64748b; border-bottom: 3px solid transparent; margin-bottom: -2px; transition: color .15s, border-color .15s; white-space: nowrap; }
  .tab:hover { color: #0f172a; }
  .tab.active { color: #0f2942; border-bottom-color: #0f2942; }

  /* Country pills */
  .country-row { display: flex; gap: 8px; margin-bottom: 0; flex-wrap: wrap; align-items: center; position: sticky; top: 47px; z-index: 29; background: #f1f5f9; padding: 14px 32px; margin-left: -32px; margin-right: -32px; border-bottom: 1px solid #e2e8f0; }
  #panel { padding-top: 18px; }
  .country-row .label { font-size: .72rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: .04em; margin-right: 6px; }
  .country-pill { padding: 8px 16px; border: 2px solid #cbd5e1; background: #fff; border-radius: 22px; cursor: pointer; font-size: .8rem; font-weight: 600; color: #475569; transition: all .15s; display: inline-flex; align-items: center; gap: 8px; }
  .country-pill:hover { border-color: #94a3b8; color: #1e293b; }
  .country-pill.active { background: #2563eb; border-color: #2563eb; color: #fff; }
  .country-pill .flag { font-size: 1rem; }

  /* Cards, KPIs */
  #panel { min-height: 300px; }
  .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.05); margin-bottom: 14px; }
  .kpi { background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 14px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
  .kpi-v { font-size: 1.3rem; font-weight: 700; color: #0f172a; line-height: 1.1; }
  .kpi-l { font-size: .7rem; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing: .04em; }
  .insight { background: #f8fafc; padding: 12px 16px; border-radius: 6px; color: #475569; font-size: .85rem; line-height: 1.55; margin-bottom: 14px; }
  .insight strong { color: #0f172a; }
  .g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
  .cw { position: relative; width: 100%; }
  .note { font-size: .72rem; color: #64748b; margin-top: 8px; line-height: 1.5; }

  /* Tables */
  .tbl-wrap { overflow-x: auto; }
  table.num-right { width: 100%; border-collapse: collapse; font-size: .82rem; }
  table.num-right th, table.num-right td { padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; }
  table.num-right th { background: #f8fafc; color: #475569; font-weight: 600; font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; }
  table.num-right tbody tr:hover { background: #f8fafc; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: .72rem; font-weight: 600; }
  .badge-prev { background: #dcfce7; color: #15803d; }
  .badge-tx { background: #fee2e2; color: #b91c1c; }

  @media (max-width: 900px) { .g2 { grid-template-columns: 1fr; } }

  /* ══════════════ Reviews VOC template styles ══════════════ */
  .voc-sub-tabs { display: flex; background: #fff; border-bottom: 2px solid #e2e8f0; gap: 2px; position: sticky; top: 0; z-index: 30; margin-bottom: 14px; }
  .voc-sub-tab { padding: 10px 18px; cursor: pointer; font-size: .8rem; font-weight: 600; color: #64748b; border-bottom: 3px solid transparent; margin-bottom: -2px; white-space: nowrap; }
  .voc-sub-tab:hover { color: #1e3a5f; }
  .voc-sub-tab.active { color: #1e3a5f; border-bottom-color: #2563eb; }
  .voc-sub-panel { display: none; }
  .voc-sub-panel.active { display: block; }
  .voc-anchor-nav { display: flex; gap: 6px; flex-wrap: wrap; padding: 10px 0; position: sticky; top: 41px; z-index: 29; background: #f1f5f9; border-bottom: 1px solid #e2e8f0; box-shadow: 0 2px 4px rgba(0,0,0,.06); margin-bottom: 14px; }
  .voc-anchor-nav a { padding: 7px 16px; border-radius: 20px; font-size: .75rem; font-weight: 600; color: #475569; background: #fff; text-decoration: none; border: 1.5px solid #e2e8f0; transition: all .15s; }
  .voc-anchor-nav a:hover, .voc-anchor-nav a.active { color: #1e3a5f; background: #dbeafe; border-color: #93c5fd; }
  .cp-charts { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 10px; }
  .cp-chart-box { background: #fff; border-radius: 8px; padding: 14px 14px 10px; box-shadow: 0 1px 3px rgba(0,0,0,.07); }
  .cp-chart-box h4 { font-size: .82rem; font-weight: 700; color: #1e293b; margin-bottom: 8px; }
  .cp-chart-wrap { position: relative; height: 230px; }
  .cp-legend { font-size: .68rem; color: #94a3b8; text-align: right; padding: 6px 0 0; }
  .us-table { width: 100%; border-collapse: collapse; font-size: .78rem; }
  .us-table th { background: #f8fafc; text-align: left; padding: 10px 14px; font-weight: 600; color: #475569; border-bottom: 2px solid #e2e8f0; white-space: nowrap; }
  .us-table td { padding: 10px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
  .us-table tr:hover td { background: #f8fafc; }
  .us-label { font-weight: 600; color: #1e293b; white-space: nowrap; }
  .us-reason { color: #64748b; line-height: 1.5; }
  .us-pct { text-align: right; white-space: nowrap; color: #1e293b; font-weight: 600; }
  .us-pct span { display: inline-block; min-width: 48px; text-align: right; }
  .us-bar-wrap { display: inline-block; width: 60px; height: 12px; background: #e2e8f0; border-radius: 3px; overflow: hidden; vertical-align: middle; margin-right: 8px; }
  .us-bar { height: 100%; background: #93c5fd; border-radius: 3px; }
  .cs-neg-zone { background: #fef2f2; border-radius: 10px; padding: 18px; margin-bottom: 22px; }
  .nf-row { cursor: pointer; transition: background .15s; }
  .nf-row:hover td { background: #fff5f5 !important; }
  .nf-arrow { display: inline-block; font-size: .65rem; margin-right: 6px; transition: transform .2s; color: #94a3b8; }
  .nf-row.open .nf-arrow { transform: rotate(90deg); }
  .nf-detail { display: none; }
  .nf-detail.open { display: table-row; }
  .nf-body { padding: 8px 16px 12px; background: #fff9f9; border-left: 3px solid #fca5a5; }
  .nf-body ul { margin: 0 0 8px 16px; font-size: .75rem; color: #334155; line-height: 1.55; }
  .nf-body ul li { margin-bottom: 2px; }
  .nf-quotes { border-top: 1px solid #fde8e8; padding-top: 6px; }
  .nf-quotes p { font-size: .72rem; color: #9a3412; font-style: italic; line-height: 1.45; margin-bottom: 3px; }
  .cs-pos-zone { background: #f0fdf4; border-radius: 10px; padding: 18px; margin-bottom: 22px; }
  .pf-row { cursor: pointer; transition: background .15s; }
  .pf-row:hover td { background: #f0fdf4 !important; }
  .pf-arrow { display: inline-block; font-size: .65rem; margin-right: 6px; transition: transform .2s; color: #94a3b8; }
  .pf-row.open .pf-arrow { transform: rotate(90deg); }
  .pf-detail { display: none; }
  .pf-detail.open { display: table-row; }
  .pf-body { padding: 8px 16px 12px; background: #f7fef9; border-left: 3px solid #86efac; }
  .pf-body ul { margin: 0 0 8px 16px; font-size: .75rem; color: #334155; line-height: 1.55; }
  .pf-body ul li { margin-bottom: 2px; }
  .pf-quotes { border-top: 1px solid #dcfce7; padding-top: 6px; }
  .pf-quotes p { font-size: .72rem; color: #166534; font-style: italic; line-height: 1.45; margin-bottom: 3px; }
  .si-table { width: 100%; border-collapse: collapse; font-size: .78rem; }
  .si-table th { background: #f8fafc; text-align: left; padding: 10px 14px; font-weight: 600; color: #475569; border-bottom: 2px solid #e2e8f0; white-space: nowrap; }
  .si-table td { padding: 10px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: top; line-height: 1.55; }
  .si-table tr:hover td { background: #f8fafc; }
  .si-badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: .7rem; font-weight: 600; line-height: 1.3; }
  .pill { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: .68rem; font-weight: 600; margin: 1px 2px; }
  .pill-red { background: #fef2f2; color: #dc2626; }
  .pill-orange { background: #fff7ed; color: #ea580c; }
  .pill-amber { background: #fffbeb; color: #d97706; }
  .pill-blue { background: #eff6ff; color: #2563eb; }
  .pill-purple { background: #faf5ff; color: #7c3aed; }
  .review-text { font-size: .78rem; color: #334155; line-height: 1.55; }
  .sec-summary { font-size: .78rem; color: #64748b; line-height: 1.55; max-width: 900px; }
  .sec-header { display: flex; align-items: center; gap: 10px; padding-top: 8px; }
  .sec-title { font-size: 1rem; font-weight: 700; color: #1e293b; }
  @media (max-width: 900px) { .cp-charts { grid-template-columns: 1fr 1fr; } }
  @media (max-width: 550px) { .cp-charts { grid-template-columns: 1fr; } }

  /* ══════════════ Marketing Deep-Dive template styles ══════════════ */
  #mdd-root .mdd-section { margin-bottom: 32px; }
  #mdd-root .mdd-sec-header { display:flex; justify-content:space-between; align-items:baseline; margin-bottom: 12px; }
  #mdd-root .mdd-sec-title { font-size: 1.05rem; font-weight: 700; color: #0f172a; }
  #mdd-root .mdd-sec-sub { font-size: .72rem; color: #64748b; }
  #mdd-root .mdd-explainer { background:#f1f5f9; border-left:3px solid #2563eb; padding:10px 12px; border-radius:4px; margin:0 0 14px; font-size:.78rem; line-height:1.55; color:#334155; }
  #mdd-root .mdd-explainer b { color:#0f172a; }
  #mdd-root .mdd-explainer code { background:#e2e8f0; padding:1px 5px; border-radius:3px; font-size:.72rem; }
  #mdd-root .mdd-comp-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:14px; }
  #mdd-root .mdd-comp-card { background:#fff; border:1px solid #e2e8f0; border-radius:8px; padding:12px; display:flex; flex-direction:column; gap:8px; transition: box-shadow .15s; cursor:pointer; }
  #mdd-root .mdd-comp-card:hover { box-shadow: 0 4px 12px rgba(15,42,66,.08); border-color:#cbd5e1; }
  #mdd-root .mdd-comp-img { width:100%; height:140px; background:#f8fafc; border-radius:6px; display:flex; align-items:center; justify-content:center; overflow:hidden; }
  #mdd-root .mdd-comp-img img { max-width:100%; max-height:100%; object-fit:contain; }
  #mdd-root .mdd-comp-brand { font-size:.7rem; font-weight:700; color:#475569; text-transform:uppercase; letter-spacing:.04em; }
  #mdd-root .mdd-comp-title { font-size:.74rem; color:#1e293b; line-height:1.35; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
  #mdd-root .mdd-comp-meta { display:flex; flex-wrap:wrap; gap:6px 10px; font-size:.68rem; color:#64748b; margin-top:auto; }
  #mdd-root .mdd-comp-meta b { color:#0f172a; }
  #mdd-root .mdd-comp-themes { display:flex; flex-wrap:wrap; gap:3px; }
  #mdd-root .mdd-theme-pill { font-size:.6rem; padding:2px 6px; border-radius:10px; background:#eff6ff; color:#1e40af; font-weight:600; }
  #mdd-root .mdd-matrix-wrap { overflow-x:auto; border:1px solid #e2e8f0; border-radius:8px; }
  #mdd-root table.mdd-matrix { width:100%; border-collapse:collapse; font-size:.72rem; }
  #mdd-root table.mdd-matrix th, #mdd-root table.mdd-matrix td { padding:8px 6px; border-bottom:1px solid #f1f5f9; text-align:center; }
  #mdd-root table.mdd-matrix th { background:#f8fafc; font-weight:600; color:#475569; font-size:.65rem; text-transform:uppercase; letter-spacing:.03em; position:sticky; top:0; z-index:1; }
  #mdd-root table.mdd-matrix th.mdd-row-h, #mdd-root table.mdd-matrix td.mdd-row-h { text-align:left; font-weight:600; color:#0f172a; min-width:140px; position:sticky; left:0; background:#fff; z-index:2; border-right:1px solid #e2e8f0; }
  #mdd-root table.mdd-matrix th.mdd-row-h { background:#f8fafc; z-index:3; }
  #mdd-root .mdd-cell-yes, #mdd-root .mdd-cell-no { display:inline-block; width:18px; height:18px; border-radius:50%; vertical-align:middle; }
  #mdd-root .mdd-cell-yes { background:#16a34a; }
  #mdd-root .mdd-cell-no { background:#e5e7eb; }
  #mdd-root .mdd-bar-row { display:grid; grid-template-columns:160px 1fr 60px; gap:10px; align-items:center; padding:6px 0; font-size:.74rem; }
  #mdd-root .mdd-bar-track { background:#f1f5f9; height:14px; border-radius:7px; overflow:hidden; }
  #mdd-root .mdd-bar-fill { height:100%; background:linear-gradient(90deg,#3b82f6,#1e40af); border-radius:7px; }
  #mdd-root .mdd-brands { font-size:.66rem; color:#64748b; margin-left:170px; margin-bottom:4px; }
  #mdd-root table.mdd-gap { width:100%; border-collapse:collapse; font-size:.74rem; background:#fff; border:1px solid #e2e8f0; border-radius:8px; overflow:hidden; }
  #mdd-root table.mdd-gap th, #mdd-root table.mdd-gap td { padding:10px 12px; border-bottom:1px solid #f1f5f9; text-align:left; vertical-align:top; }
  #mdd-root table.mdd-gap th { background:#f8fafc; font-size:.66rem; font-weight:600; color:#475569; text-transform:uppercase; letter-spacing:.03em; }
  #mdd-root .mdd-sev { display:inline-block; padding:2px 8px; border-radius:10px; font-size:.62rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
  #mdd-root .mdd-sev-HIGH { background:#fee2e2; color:#991b1b; }
  #mdd-root .mdd-sev-MEDIUM { background:#fef3c7; color:#92400e; }
  #mdd-root .mdd-sev-LOW { background:#dcfce7; color:#166534; }
  #mdd-root .mdd-ws-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; }
  #mdd-root .mdd-ws-card { background:#fff; border:1px solid #e2e8f0; border-radius:8px; padding:14px; }
  #mdd-root .mdd-ws-card h4 { margin:0 0 6px; font-size:.85rem; color:#0f172a; }
  #mdd-root .mdd-ws-rationale { font-size:.74rem; color:#475569; line-height:1.45; }
  #mdd-root .mdd-ws-evidence { font-size:.68rem; color:#64748b; margin-top:8px; padding-top:8px; border-top:1px dashed #e2e8f0; }
  #mdd-root .mdd-insight-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:12px; }
  #mdd-root .mdd-insight-card { background:#fff; border:1px solid #e2e8f0; border-radius:8px; padding:14px; }
  #mdd-root .mdd-insight-badge { display:inline-block; padding:3px 10px; border-radius:10px; font-size:.62rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em; margin-bottom:8px; }
  #mdd-root .mdd-insight-card h4 { margin:0 0 6px; font-size:.78rem; color:#0f172a; line-height:1.4; }
  #mdd-root .mdd-insight-card p { margin:6px 0 0; font-size:.72rem; color:#475569; line-height:1.5; }
  #mdd-modal { display:none; position:fixed; inset:0; background:rgba(15,42,66,.7); z-index:1000; align-items:flex-start; justify-content:center; padding:40px 20px; overflow-y:auto; }
  #mdd-modal.open { display:flex; }
  #mdd-modal .mdd-modal-body { background:#fff; max-width:1000px; width:100%; border-radius:10px; padding:24px; max-height:calc(100vh - 80px); overflow-y:auto; }
  #mdd-modal .mdd-modal-close { float:right; cursor:pointer; font-size:1.4rem; color:#64748b; line-height:1; padding:4px 8px; }
  #mdd-modal .mdd-modal-close:hover { color:#0f172a; }
  #mdd-modal .mdd-modal-imgs { display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); gap:10px; margin:16px 0; }
  #mdd-modal .mdd-modal-imgs img { width:100%; aspect-ratio:1; object-fit:contain; background:#f8fafc; border-radius:6px; border:1px solid #e2e8f0; }
  #mdd-modal .mdd-bullets { list-style:none; padding:0; margin:0; }
  #mdd-modal .mdd-bullets li { padding:8px 12px; background:#f8fafc; border-left:3px solid #3b82f6; margin-bottom:6px; font-size:.78rem; line-height:1.5; color:#1e293b; border-radius:0 6px 6px 0; }
</style>
</head>
<body>

<div class="dashboard-header">
  <div class="header-titles">
    <h2 id="hdrTitle"></h2>
    <span class="sub" id="hdrSub"></span>
  </div>
  <div class="xray-btn-row" id="xrayBtnRow"></div>
</div>

<div class="dashboard-body">
  <div class="tabs" id="tabBar"></div>
  <div class="country-row" id="countryBar"></div>
  <div id="panel"></div>
</div>

<script>
window._DASH_DATA = /*<<BUNDLE>>*/;

(function bootstrap() {
  var D = window._DASH_DATA;
  var state = { tab: Object.keys(D.tabs)[0], country: D.countries[0].code };
  var charts = [];

  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }
  function fmtInt(n) { return Math.round(n).toLocaleString('en-US'); }
  function fmtMoney(n) { return D.currency + Math.round(n).toLocaleString('en-US'); }
  function fmtShort(n) {
    n = Math.round(n);
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K';
    return String(n);
  }
  function fmtMoneyShort(n) {
    n = Math.round(n);
    if (n >= 1e6) return D.currency + (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1e3) return D.currency + (n / 1e3).toFixed(0) + 'K';
    return D.currency + n;
  }
  function pct(v, t) { return t > 0 ? (v / t * 100).toFixed(1) + '%' : '0%'; }

  function destroyCharts() { charts.forEach(function(c) { try { c.destroy(); } catch(e){} }); charts = []; }

  // ── Sortable tables (every column, every table in #panel) ─────────────────
  function parseSortValue(td) {
    if (td.dataset && td.dataset.val != null && td.dataset.val !== '') {
      var n = parseFloat(td.dataset.val);
      if (!isNaN(n)) return n;
    }
    var txt = (td.textContent || '').trim();
    var cleaned = txt.replace(/[\s,\u00a0€$£%]/g, '').replace(/\u00b7/g, '');
    if (cleaned !== '' && !isNaN(parseFloat(cleaned))) return parseFloat(cleaned);
    return txt.toLowerCase();
  }
  function sortTableByColumn(table, colIdx, dir) {
    var tbody = table.tBodies[0]; if (!tbody) return;
    var rows = Array.prototype.slice.call(tbody.rows);
    rows.sort(function(a, b) {
      var va = parseSortValue(a.cells[colIdx]);
      var vb = parseSortValue(b.cells[colIdx]);
      if (va < vb) return dir === 'asc' ? -1 : 1;
      if (va > vb) return dir === 'asc' ? 1 : -1;
      return 0;
    });
    rows.forEach(function(r) { tbody.appendChild(r); });
  }
  function makeAllTablesSortable() {
    var tables = document.querySelectorAll('#panel table');
    tables.forEach(function(table) {
      var ths = table.tHead ? table.tHead.rows[0].cells : table.rows[0].cells;
      Array.prototype.forEach.call(ths, function(th, idx) {
        if (th.dataset.sortable === '1') return;
        th.dataset.sortable = '1';
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        th.dataset.sortDir = '';
        var arrow = document.createElement('span');
        arrow.className = 'sort-arrow';
        arrow.style.cssText = 'margin-left:6px;opacity:.6;font-size:1.5em;color:#0f172a;vertical-align:middle;line-height:1';
        arrow.textContent = '\u25B4\u25BE';
        th.appendChild(arrow);
        th.addEventListener('click', function() {
          var dir = th.dataset.sortDir === 'asc' ? 'desc' : 'asc';
          Array.prototype.forEach.call(ths, function(other) {
            other.dataset.sortDir = '';
            var a = other.querySelector('.sort-arrow');
            if (a) { a.textContent = '\u25B4\u25BE'; a.style.opacity = '.6'; }
          });
          th.dataset.sortDir = dir;
          arrow.textContent = dir === 'asc' ? '\u25B4' : '\u25BE';
          arrow.style.opacity = '1';
          sortTableByColumn(table, idx, dir);
        });
      });
    });
  }

  // ── Shared pie helper (used by all renderers) ─────────────────────────────
  function pie(canvasId, labels, data, colors, moneyFmt) {
    var el = document.getElementById(canvasId);
    if (!el) return;
    var total = data.reduce(function(a,b){return a+(+b||0);}, 0);
    try {
      var ctx = el.getContext('2d');
      var capturedLabels = labels.slice();
      var capturedData = data.slice();
      var capturedColors = colors.slice();
      var capturedMoneyFmt = moneyFmt;
      var chart = new Chart(ctx, {
        type: 'pie',
        data: { labels: labels, datasets: [{ data: data, backgroundColor: colors, borderWidth: 2, borderColor: '#fff' }] },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right',
              labels: {
                boxWidth: 12, padding: 6, font: { size: 11 },
                generateLabels: function() {
                  return capturedLabels.map(function(lbl, i) {
                    var v = capturedData[i];
                    var p = total > 0 ? (v/total*100).toFixed(1) : '0.0';
                    var valStr = capturedMoneyFmt ? fmtMoneyShort(v) : fmtInt(v);
                    return {
                      text: lbl + ' \u00b7 ' + valStr + ' (' + p + '%)',
                      fillStyle: capturedColors[i],
                      strokeStyle: capturedColors[i],
                      lineWidth: 0, hidden: false, index: i
                    };
                  });
                }
              }
            },
            tooltip: { callbacks: { label: function(ctx) {
              var v = ctx.parsed; var p = total > 0 ? (v/total*100).toFixed(1) : '0';
              return ctx.label + ': ' + (moneyFmt ? fmtMoneyShort(v) : fmtInt(v)) + ' (' + p + '%)';
            } } },
            datalabels: {
              color: '#fff', font: { size: 11, weight: 'bold' },
              formatter: function(v) { var p = total > 0 ? (v/total*100) : 0; return p >= 5 ? p.toFixed(0) + '%' : ''; }
            }
          }
        },
        plugins: [ChartDataLabels]
      });
      charts.push(chart);
    } catch(e) {
      console.error('pie() failed for', canvasId, e);
      if (el && el.parentNode) {
        el.parentNode.innerHTML = '<div style="padding:20px;color:#dc2626;font-size:.8rem">Chart error: ' + (e && e.message || e) + '</div>';
      }
    }
  }

  // Header
  document.getElementById('hdrTitle').textContent = D.title;
  document.getElementById('hdrSub').textContent = D.subtitle;

  // X-Ray buttons
  var icon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>';
  var xrayBar = document.getElementById('xrayBtnRow');
  D.countries.forEach(function(c) {
    var url = (D.xrayLinks && D.xrayLinks[c.code]) || '#';
    var a = document.createElement('a');
    a.className = 'xray-btn'; a.href = url; a.target = '_blank'; a.rel = 'noopener';
    a.innerHTML = icon + '<span>' + esc(c.code) + ' X-Ray</span>';
    xrayBar.appendChild(a);
  });

  // Tab bar
  var tabBar = document.getElementById('tabBar');
  Object.keys(D.tabs).forEach(function(tabId, i) {
    var t = D.tabs[tabId];
    var btn = document.createElement('button');
    btn.className = 'tab' + (tabId === state.tab ? ' active' : '');
    btn.dataset.tab = tabId;
    btn.textContent = (i + 1) + ' \u00b7 ' + t.label;
    btn.addEventListener('click', function() {
      state.tab = tabId;
      tabBar.querySelectorAll('.tab').forEach(function(b) { b.classList.toggle('active', b.dataset.tab === tabId); });
      renderPanel();
    });
    tabBar.appendChild(btn);
  });

  // Country bar
  var countryBar = document.getElementById('countryBar');
  var label = document.createElement('span'); label.className = 'label'; label.textContent = 'Country:';
  countryBar.appendChild(label);
  D.countries.forEach(function(c) {
    var pill = document.createElement('button');
    pill.className = 'country-pill' + (c.code === state.country ? ' active' : '');
    pill.dataset.country = c.code;
    pill.innerHTML = '<span>' + esc(c.code) + '</span>';
    pill.addEventListener('click', function() {
      state.country = c.code;
      countryBar.querySelectorAll('.country-pill').forEach(function(p) { p.classList.toggle('active', p.dataset.country === c.code); });
      renderPanel();
    });
    countryBar.appendChild(pill);
  });

  // ── Colors ────────────────────────────────────────────────────────────────
  var SEG_COLORS = (D.segmentColors) || {};
  var OTHER_COLOR = '#94a3b8';
  var BRAND_PALETTE_JS = D.brandPalette || ['#2563eb','#dc2626','#16a34a','#f59e0b','#8b5cf6','#0891b2','#db2777','#65a30d'];
  // Position-based palette · slot 1 always blue, slot 2 always red, etc.,
  // consistent across all countries. (Brand names no longer drive color.)
  function brandColor(name, i) {
    if (typeof name === 'string' && name.indexOf('Other (') === 0) return OTHER_COLOR;
    return BRAND_PALETTE_JS[i % BRAND_PALETTE_JS.length];
  }

  // ── Main Segments renderer (N-segment-aware) ─────────────────────────────
  function renderMainSegments(country) {
    var D2 = D.tabs['main-segments'].countries[country.code] || {};
    var segs = D2.segments || [];
    var SEG_NAMES = D.segments || segs.map(function(s){ return s.name; });
    // Re-order segs to match SEG_NAMES order; missing segments default to zeros.
    var segMap = {};
    segs.forEach(function(s){ segMap[s.name] = s; });
    var segsOrdered = SEG_NAMES.map(function(name){
      return segMap[name] || { name: name, units: 0, revenue: 0, brandsByUnits: [], brandsByRevenue: [] };
    });
    var totalUnits = D2.totalUnits || 0;
    var totalRev   = D2.totalRevenue || 0;
    var nSeg = segsOrdered.length;
    var html = '';
    html += '<h2>Main Segments \u00b7 Total Market (12M) \u00b7 ' + esc(country.name) + '</h2>';

    // Total Category KPI strip
    html += '<div class="card" style="border-left:4px solid #1e293b;padding:14px 20px;display:flex;align-items:center;gap:36px;flex-wrap:wrap">';
    html += '  <div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#64748b;min-width:120px">Total Category</div>';
    html += '  <div><div style="font-size:1.6rem;font-weight:700;color:#1e293b;line-height:1">' + fmtMoneyShort(totalRev) + '</div><div style="font-size:.75rem;color:#64748b;margin-top:3px">Revenue \u00b7 Last 12M (projected)</div></div>';
    html += '  <div><div style="font-size:1.6rem;font-weight:700;color:#1e293b;line-height:1">' + fmtInt(totalUnits) + '</div><div style="font-size:.75rem;color:#64748b;margin-top:3px">Units Sold \u00b7 Last 12M</div></div>';
    html += '</div>';

    // Per-segment KPI cards · one column per segment
    html += '<div style="display:grid;grid-template-columns:repeat(' + nSeg + ',1fr);gap:14px;margin-bottom:14px;margin-top:14px">';
    segsOrdered.forEach(function(seg) {
      var color = SEG_COLORS[seg.name] || '#64748b';
      html += '<div class="card" style="border-left:4px solid ' + color + ';padding:14px 16px;margin-bottom:0">';
      html += '  <div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:' + color + ';margin-bottom:10px">' + esc(seg.name) + '</div>';
      html += '  <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px">';
      html += '    <div class="kpi" style="box-shadow:none;background:#f8fafc;padding:8px 10px"><div class="kpi-v" style="font-size:.95rem">' + fmtShort(seg.units) + '</div><div class="kpi-l">Units sold (12M)</div></div>';
      html += '    <div class="kpi" style="box-shadow:none;background:#f8fafc;padding:8px 10px"><div class="kpi-v" style="font-size:.95rem">' + fmtMoneyShort(seg.revenue) + '</div><div class="kpi-l">Segment Value (12M)</div></div>';
      html += '  </div></div>';
    });
    html += '</div>';

    // Insight: leader by units / revenue + avg price per segment
    var unitLeader = segsOrdered.slice().sort(function(a,b){ return b.units - a.units; })[0];
    var revLeader  = segsOrdered.slice().sort(function(a,b){ return b.revenue - a.revenue; })[0];
    var avgPriceParts = segsOrdered.map(function(s){
      var avg = s.units > 0 ? s.revenue / s.units : 0;
      return esc(s.name) + ': <strong>' + D.currency + avg.toFixed(2) + '</strong>';
    }).join(' \u00b7 ');
    html += '<div class="insight">';
    html += 'Unit leader: <strong>' + esc(unitLeader.name) + '</strong> (' + pct(unitLeader.units, totalUnits) + '). ';
    html += 'Revenue leader: <strong>' + esc(revLeader.name) + '</strong> (' + pct(revLeader.revenue, totalRev) + '). ';
    html += 'Avg price \u00b7 ' + avgPriceParts + '.';
    html += '</div>';

    // Revenue / Units pies (N slices each)
    var pieLabels = segsOrdered.map(function(s){ return s.name; });
    var pieRev    = segsOrdered.map(function(s){ return s.revenue; });
    var pieUnits  = segsOrdered.map(function(s){ return s.units; });
    var pieColors = segsOrdered.map(function(s){ return SEG_COLORS[s.name] || '#64748b'; });
    var revNote   = segsOrdered.map(function(s){ return esc(s.name) + ' ' + fmtMoneyShort(s.revenue) + ' (' + pct(s.revenue, totalRev) + ')'; }).join(' \u00b7 ');
    var unitsNote = segsOrdered.map(function(s){ return esc(s.name) + ' ' + fmtInt(s.units) + ' units (' + pct(s.units, totalUnits) + ')'; }).join(' \u00b7 ');
    html += '<div class="g2" style="align-items:start">';
    html += '  <div class="card"><h3>Revenue by Segment (12M)</h3><div class="cw" style="height:280px"><canvas id="focusRevPie"></canvas></div><div class="note">' + revNote + '. Revenue = 12M units \u00d7 listed ASIN price.</div></div>';
    html += '  <div class="card"><h3>Units by Segment (12M)</h3><div class="cw" style="height:280px"><canvas id="focusUnitsPie"></canvas></div><div class="note">' + unitsNote + '.</div></div>';
    html += '</div>';

    // Segment summary table · one row per segment
    html += '<div class="card"><h3>Segment Summary (12M)</h3><div class="tbl-wrap"><table class="num-right">';
    html += '<thead><tr><th style="text-align:left">Segment</th><th>Units (12M)</th><th>Revenue (12M)</th><th>Unit Share</th><th>Rev Share</th></tr></thead><tbody>';
    segsOrdered.forEach(function(seg) {
      var color = SEG_COLORS[seg.name] || '#64748b';
      html += '<tr><td style="text-align:left"><span class="badge" style="background:' + color + '22;color:' + color + '">' + esc(seg.name) + '</span></td>';
      html += '<td>' + fmtInt(seg.units) + '</td><td>' + fmtMoney(seg.revenue) + '</td>';
      html += '<td>' + pct(seg.units, totalUnits) + '</td><td>' + pct(seg.revenue, totalRev) + '</td></tr>';
    });
    html += '</tbody></table></div><div class="note">Revenue = 12M units \u00d7 listed ASIN price. Units use sales-history when available, otherwise the H10 X-Ray 30-day snapshot is corrected by the seasonality index for the export-window months and projected to 12 months.</div></div>';

    // Brand share pies · N segments × 2 metrics (units + revenue), arranged in 2 grids
    function brandPiesGrid(metric, money, headingTpl, noteTpl) {
      var rows = '<div style="display:grid;grid-template-columns:repeat(' + nSeg + ',1fr);gap:14px;align-items:start;margin-top:18px">';
      segsOrdered.forEach(function(seg, i) {
        var canvasId = 'brandPie_' + metric + '_' + i;
        var totalForSeg = metric === 'units' ? seg.units : seg.revenue;
        var totalStr = money ? fmtMoneyShort(totalForSeg) : (fmtInt(totalForSeg) + ' units');
        rows += '<div class="card"><h3>' + esc(headingTpl.replace('{seg}', seg.name)) + '</h3><div class="cw" style="height:340px"><canvas id="' + canvasId + '"></canvas></div><div class="note">' + esc(noteTpl.replace('{seg}', seg.name).replace('{total}', totalStr)) + '</div></div>';
      });
      rows += '</div>';
      return rows;
    }
    html += brandPiesGrid('units',   false, 'Brand Share \u00b7 {seg} (Units, 12M)',   'Brand unit share within {seg} segment. {total} total (12M).');
    html += brandPiesGrid('revenue', true,  'Brand Share \u00b7 {seg} (Revenue, 12M)', 'Brand revenue share within {seg} segment. {total} total (12M).');

    // Per-segment Brand Summary + Top 20 ASINs tables (Lure, Electric)
    var msBySeg = D2.marketStructure || {};
    var amazonDom = (country.code === 'UK') ? 'co.uk' : country.code.toLowerCase();
    (D.segments || []).forEach(function(seg) {
      var ms = msBySeg[seg];
      if (!ms || !ms.brands || !ms.brands.length) return;
      // Cap Electric at top 15 (Electric has many brands, the long tail isn't useful)
      var brandLimit = (seg === 'Electric') ? 15 : ms.brands.length;
      var brandsShown = ms.brands.slice(0, brandLimit);
      var capped = ms.brands.length > brandLimit;
      html += '<div class="card" style="margin-top:18px"><h3>Brand Summary · ' + esc(seg) + ' (12M) · ' + esc(country.name) + '</h3>';
      html += '<div class="tbl-wrap"><table class="num-right">';
      html += '<thead><tr><th style="text-align:left">Brand</th><th>Units 12M</th><th>Revenue 12M</th><th>Share</th><th>ASINs</th></tr></thead><tbody>';
      brandsShown.forEach(function(b, i) {
        var bc = (b.brand && b.brand.indexOf('Other (') === 0) ? '#64748b' : brandColor(b.brand, i);
        html += '<tr>';
        html += '<td style="text-align:left"><span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:.78rem;font-weight:600;background:' + bc + '22;color:' + bc + '">' + esc(b.brand) + '</span></td>';
        html += '<td data-val="' + b.units + '">' + fmtInt(b.units) + '</td>';
        html += '<td data-val="' + b.revenue + '">' + fmtMoney(b.revenue) + '</td>';
        html += '<td data-val="' + b.share + '">' + b.share.toFixed(1) + '%</td>';
        html += '<td data-val="' + b.asins + '">' + b.asins + '</td>';
        html += '</tr>';
      });
      html += '</tbody></table></div>';
      var noteText = brandsShown.length + ' of ' + ms.brands.length + ' brand' + (ms.brands.length === 1 ? '' : 's') + ' shown' + (capped ? ' (capped at top 15 by revenue)' : '') + ' across ' + ms.asinCount + ' ' + esc(seg) + ' ASINs. Total revenue: ' + fmtMoneyShort(ms.totalRevenue) + '.';
      html += '<div class="note">' + noteText + '</div>';
      html += '</div>';
    });
    (D.segments || []).forEach(function(seg) {
      var ms = msBySeg[seg];
      if (!ms || !ms.topAsins || !ms.topAsins.length) return;
      var asinsShown = ms.topAsins.slice(0, 20);
      // Brand → color map: rank brands by revenue (matches brand-share chart slot order
      // for the top 8). Brands beyond palette length cycle through it.
      var brandColorMap = {};
      (ms.brands || []).forEach(function(b, i) {
        if (b.brand && b.brand.indexOf('Other (') !== 0) {
          brandColorMap[b.brand] = brandColor(b.brand, i);
        }
      });
      html += '<div class="card" style="margin-top:18px"><h3>' + esc(seg) + ' ASINs · Top 20 by Revenue (12M) · ' + esc(country.name) + '</h3>';
      html += '<div class="tbl-wrap"><table class="num-right">';
      html += '<thead><tr><th style="text-align:left">ASIN</th><th style="text-align:left">Brand</th><th style="text-align:left">Title</th><th>Units 12M</th><th>Revenue 12M</th><th>Reviews</th><th>Price</th></tr></thead><tbody>';
      asinsShown.forEach(function(p) {
        var bc = brandColorMap[p.brand] || '#64748b';
        html += '<tr>';
        html += '<td style="text-align:left"><a href="https://www.amazon.' + amazonDom + '/dp/' + esc(p.asin) + '" target="_blank" rel="noopener"><code style="font-size:.75rem">' + esc(p.asin) + '</code></a></td>';
        html += '<td style="text-align:left"><span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:.78rem;font-weight:600;background:' + bc + '22;color:' + bc + '">' + esc(p.brand) + '</span></td>';
        html += '<td style="text-align:left;max-width:380px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + esc(p.title) + '">' + esc(p.title) + '</td>';
        html += '<td data-val="' + (p.units || 0) + '">' + fmtInt(p.units || 0) + '</td>';
        html += '<td data-val="' + p.revenue + '">' + fmtMoney(p.revenue) + '</td>';
        html += '<td data-val="' + (p.reviews || 0) + '">' + fmtInt(p.reviews || 0) + '</td>';
        html += '<td data-val="' + p.price + '">' + D.currency + p.price.toFixed(2) + '</td>';
        html += '</tr>';
      });
      html += '</tbody></table></div>';
      html += '<div class="note">Top ' + asinsShown.length + ' ' + esc(seg) + ' ASINs by 12M revenue. Brand colors match the Brand Share charts above (top 8 brands by revenue). Click ASIN to open on amazon.' + amazonDom + '.</div>';
      html += '</div>';
    });

    // ── % Unit Share · Brand vs. Total (All) (12M) ──
    var bmsBySeg = D2.brandMonthlyShareBySegment || {};
    var bmsSegList = (D.segments || []).filter(function(s){ return bmsBySeg[s] && bmsBySeg[s].brands && bmsBySeg[s].brands.length; });
    if (bmsSegList.length) {
      bmsSegList.forEach(function(seg, segIdx) {
        var bms = bmsBySeg[seg];
        html += '<div class="card" style="margin-top:18px"><h3>% Unit Share \u00b7 Brand vs. ' + esc(seg) + ' Total (12M)</h3>';
        html += '<div class="cw" style="height:420px"><canvas id="brandShareLine_' + segIdx + '"></canvas></div>';
        html += '<div class="note">Monthly unit share per brand as % of total ' + esc(seg) + ' units across the ' + bms.asinCount + ' ' + esc(seg) + ' ASINs with sales history (' + esc(bms.startDate) + ' \u2192 ' + esc(bms.endDate) + '). Top 8 brands shown; remaining brands collapsed into "Other". Click legend to show/hide a brand.</div>';
        html += '</div>';
      });
    } else {
      html += '<div class="card" style="margin-top:18px"><h3>% Unit Share \u00b7 Brand vs. Segment Total (12M)</h3>';
      html += '<div class="cw" style="height:220px;display:flex;align-items:center;justify-content:center;background:#f8fafc;border:2px dashed #cbd5e1;border-radius:6px;color:#94a3b8;font-size:.85rem">No sales history available for ' + esc(country.name) + '.</div></div>';
    }

    // ── Total Market Seasonality (one chart per country) ──
    var season = D2.seasonality;
    if (season && season.months && season.months.length === 12) {
      var peakRatio = (season.troughIdx > 0) ? (season.peakIdx / season.troughIdx).toFixed(2) : '\u00b7';
      var pc        = D2.projectionCounts || {};
      var xrayIdx   = D2.xrayWindowIndex;
      var xrayMult  = (xrayIdx && xrayIdx > 0) ? (12 / xrayIdx).toFixed(1) : null;
      var xrayWindowText = (D2.xrayWindowStart || '') + ' \u2192 ' + (D2.xrayExportDate || '');

      html += '<h2 style="margin-top:28px;margin-bottom:6px">Total Market Seasonality (12M, 1.0 = average month)</h2>';
      html += '<p style="margin:0 0 14px;color:#64748b;font-size:.78rem;line-height:1.5"><b>This ' + esc(country.name) + ' market only</b> (not combined with other marketplaces). Each country has its own seasonality curve computed from its own sales-data files. <b>Inputs:</b> ' + season.asinCount + ' top-selling ' + esc(country.name) + ' ASINs with daily sales history (\u2248365 daily data points per ASIN within the window). <b>Logic:</b> sum each ASIN\u2019s daily units, bin into calendar months, then each month\u2019s total \u00f7 12-month mean = the index shown below. Window: ' + esc(season.startDate) + ' to ' + esc(season.endDate) + '.</p>';
      html += '<div class="kpis" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:12px">';
      html += '  <div class="kpi"><div class="kpi-v" style="color:#15803d">' + esc(season.peakMonth) + ' (' + season.peakIdx.toFixed(2) + ')</div><div class="kpi-l">Peak Month</div></div>';
      html += '  <div class="kpi"><div class="kpi-v" style="color:#dc2626">' + esc(season.troughMonth) + ' (' + season.troughIdx.toFixed(2) + ')</div><div class="kpi-l">Trough Month</div></div>';
      html += '  <div class="kpi"><div class="kpi-v">' + season.peakIdx.toFixed(2) + 'x</div><div class="kpi-l">Peak / Avg (Best Month)</div></div>';
      html += '  <div class="kpi"><div class="kpi-v">' + peakRatio + 'x</div><div class="kpi-l">Peak / Trough Ratio</div></div>';
      html += '</div>';
      html += '<div class="card"><h3>' + esc(country.name) + ' \u00b7 Monthly Seasonality Index</h3><div class="cw" style="height:280px"><canvas id="seasonalityChart"></canvas></div><div class="note">Index = each month\u2019s total units \u00f7 12-month mean. <b>1.0</b> = average month; <b>2.0</b> = double; <b>0.1</b> = 10% of average.</div></div>';

      // Methodology explanation panel
      html += '<div class="card" style="margin-top:10px;background:#f8fafc;border-left:4px solid #2563eb">';
      html += '<h3 style="margin-top:0">How this curve drives 12-month projections for every ASIN</h3>';
      html += '<p style="margin:0 0 10px;font-size:.82rem;line-height:1.55;color:#334155">';
      html += 'The X-Ray export captures only a <b>30-day snapshot</b>. Because wasp products are highly seasonal, multiplying that 30-day figure by 12 (naive flat projection) <b>under-estimates</b> annual sales when the export window falls outside peak season, and <b>over-estimates</b> if the window is in peak season. The chart above is how we correct for this.';
      html += '</p>';
      if (xrayIdx && xrayMult) {
        var xMultNum = (12 / xrayIdx);
        // Step-by-step flow showing how the curve from a small sample is used to project ALL no-history ASINs
        html += '<div style="margin:10px 0 6px;padding:12px 14px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;font-size:.82rem;line-height:1.6;color:#334155">';
        html += '<b style="color:#0f172a">3-step flow for ' + esc(country.name) + ':</b>';
        html += '<ol style="margin:6px 0 0;padding-left:22px">';
        html += '  <li><b>Build the curve.</b> The seasonality chart above is computed from <b>' + (pc.history||0) + ' ' + esc(country.name) + ' ASINs</b> that have daily sales history (<code>*-sales-3y.csv</code> files).</li>';
        html += '  <li><b>Read the index for the X-Ray window.</b> The export covers ' + esc(xrayWindowText) + '. Walking each of those 30 days against the monthly curve gives an average index of <b style="color:#2563eb">' + xrayIdx.toFixed(2) + 'x</b> of a normal month (1.0 = average).</li>';
        html += '  <li><b>Apply that one index to ALL no-history ASINs.</b> The same <b style="color:#2563eb">' + xrayIdx.toFixed(2) + 'x</b> figure is reused for every one of the <b>' + (pc.seasonality||0) + ' ' + esc(country.name) + ' ASINs without a sales-history file</b>. Their 12M = 30-day X-Ray sales \u00f7 ' + xrayIdx.toFixed(2) + ' \u00d7 12 = <b>30-day \u00d7 ' + xrayMult + 'x</b>.</li>';
        html += '</ol>';
        html += '<div style="margin-top:8px;padding:8px 10px;background:#eff6ff;border-radius:5px;font-size:.78rem">';
        html += '<b>Worked example:</b> an ASIN with no history selling 100 units in the X-Ray\u2019s 30 days projects to <b>' + Math.round(100 * xMultNum) + ' units / 12M</b> in ' + esc(country.name) + ' (100 \u00f7 ' + xrayIdx.toFixed(2) + ' \u00d7 12).';
        html += '</div>';
        html += '<p style="margin:8px 0 0;font-size:.78rem;color:#64748b">ASINs <i>with</i> their own sales history skip this entirely: their 12M is just the actual trailing 365-day sum, no projection.</p>';
        html += '</div>';

        html += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-top:10px;font-size:.78rem;color:#475569">';
        html += '  <div><b style="color:#0f172a">X-Ray export window:</b><br>' + esc(xrayWindowText) + '</div>';
        html += '  <div><b style="color:#0f172a">Window seasonality index:</b><br>' + xrayIdx.toFixed(2) + ' (avg month = 1.0)</div>';
        html += '  <div><b style="color:#0f172a">30-day to 12M multiplier:</b><br>12 / ' + xrayIdx.toFixed(2) + ' = <b style="color:#2563eb">' + xrayMult + 'x</b></div>';
        html += '  <div><b style="color:#0f172a">' + esc(country.name) + ' ASIN breakdown:</b><br>' + (pc.history||0) + ' real history \u00b7 ' + (pc.seasonality||0) + ' seasonality \u00b7 ' + (pc.flat||0) + ' flat</div>';
        html += '</div>';

        // Polish version of the same flow
        html += '<div style="margin-top:14px;padding:12px 14px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;font-size:.78rem;line-height:1.6;color:#334155">';
        html += '<b style="color:#0f172a">PL \u00b7 Jak ten wykres wp\u0142ywa na ka\u017cdy ASIN w ' + esc(country.name) + '?</b>';
        html += '<ol style="margin:6px 0 0;padding-left:22px">';
        html += '  <li><b>Budowa krzywej.</b> Wykres powy\u017cej jest policzony z <b>' + (pc.history||0) + ' ASIN-\u00f3w ' + esc(country.name) + '</b>, kt\u00f3re maj\u0105 w\u0142asn\u0105 histori\u0119 sprzeda\u017cy (pliki <code>*-sales-3y.csv</code>).</li>';
        html += '  <li><b>Odczyt indeksu dla okna X-Ray.</b> Eksport obejmuje ' + esc(xrayWindowText) + '. \u015aredni indeks dla tych 30 dni = <b style="color:#2563eb">' + xrayIdx.toFixed(2) + 'x</b> (1.0 = miesi\u0105c \u015bredni).</li>';
        html += '  <li><b>Ten jeden indeks stosujemy do WSZYSTKICH ASIN-\u00f3w bez historii.</b> To samo <b style="color:#2563eb">' + xrayIdx.toFixed(2) + 'x</b> jest u\u017cywane dla ka\u017cdego z <b>' + (pc.seasonality||0) + ' ASIN-\u00f3w ' + esc(country.name) + ' bez pliku historii</b>. Ich 12M = 30-dniowa sprzeda\u017c X-Ray \u00f7 ' + xrayIdx.toFixed(2) + ' \u00d7 12 = <b>30 dni \u00d7 ' + xrayMult + 'x</b>.</li>';
        html += '</ol>';
        html += '<div style="margin-top:8px;padding:8px 10px;background:#eff6ff;border-radius:5px;font-size:.78rem">';
        html += '<b>Przyk\u0142ad:</b> ASIN bez historii sprzedaj\u0105cy 100 sztuk w 30-dniowym oknie X-Ray = prognoza <b>' + Math.round(100 * xMultNum) + ' szt. / 12M</b> w ' + esc(country.name) + ' (100 \u00f7 ' + xrayIdx.toFixed(2) + ' \u00d7 12).';
        html += '</div>';
        html += '<p style="margin:8px 0 0;font-size:.74rem;color:#64748b"><b>Uwaga o pr\u00f3bie:</b> krzywa pochodzi z ' + (pc.history||0) + ' ASIN-\u00f3w (top-selling), a stosujemy j\u0105 do ' + (pc.seasonality||0) + '. Zak\u0142adamy, \u017ce sezonowo\u015b\u0107 top sprzedawc\u00f3w reprezentuje sezonowo\u015b\u0107 ca\u0142ego rynku ' + esc(country.name) + '. ASIN-y <i>z</i> w\u0142asn\u0105 histori\u0105 nie u\u017cywaj\u0105 prognozy: ich 12M = realna suma 365 dni.</p>';
        html += '</div>';
      }
      html += '</div>';
    } else {
      html += '<h2 style="margin-top:28px;margin-bottom:6px">Total Market Seasonality (12M)</h2>';
      html += '<div class="card"><div class="cw" style="height:220px;display:flex;align-items:center;justify-content:center;background:#f8fafc;border:2px dashed #cbd5e1;border-radius:6px;color:#94a3b8;font-size:.85rem">No sales history available for ' + esc(country.name) + '. Drop per-ASIN sales CSVs into <code>data/sales-data/' + esc(country.code) + '/</code>.</div></div>';
    }

    document.getElementById('panel').innerHTML = html;

    // Segment pies (N slices each)
    pie('focusRevPie',   pieLabels, pieRev,   pieColors, true);
    pie('focusUnitsPie', pieLabels, pieUnits, pieColors, false);

    // Brand pies · N per metric
    function drawBrandPies(metric, money) {
      segsOrdered.forEach(function(seg, i) {
        var brands = (metric === 'units' ? seg.brandsByUnits : seg.brandsByRevenue) || [];
        var labels = brands.map(function(b){ return b.brand; });
        var data   = brands.map(function(b){ return b[metric]; });
        var colors = brands.map(function(b, j){ return brandColor(b.brand, j); });
        pie('brandPie_' + metric + '_' + i, labels, data, colors, money);
      });
    }
    drawBrandPies('units',   false);
    drawBrandPies('revenue', true);

    // Seasonality bar chart
    if (season && season.months && season.months.length === 12) {
      var seasCtx = document.getElementById('seasonalityChart');
      if (seasCtx) {
        var barColors = season.months.map(function(v) {
          if (v >= 1.2) return '#16a34a';
          if (v >= 0.9) return '#2563eb';
          if (v >= 0.6) return '#f59e0b';
          return '#dc2626';
        });
        var seasChart = new Chart(seasCtx, {
          type: 'bar',
          data: { labels: season.monthLabels, datasets: [{ data: season.months, backgroundColor: barColors, borderRadius: 4 }] },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { callback: function(v){ return v.toFixed(1) + 'x'; } } } } }
        });
        charts.push(seasChart);
      }
    }

    // Brand monthly share line chart - one per segment
    bmsSegList.forEach(function(seg, segIdx) {
      var bms = bmsBySeg[seg];
      var bmsCtx = document.getElementById('brandShareLine_' + segIdx);
      if (!bmsCtx) return;
      var datasets = bms.brands.map(function(b, i) {
        return { label: b.brand, data: b.share, borderColor: brandColor(b.brand, i), backgroundColor: brandColor(b.brand, i), borderWidth: 2, tension: 0.25, fill: false, pointRadius: 2, pointHoverRadius: 5 };
      });
      var bmsChart = new Chart(bmsCtx, {
        type: 'line',
        data: { labels: bms.monthLabels, datasets: datasets },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true, ticks: { callback: function(v){ return v + '%'; } } } } }
      });
      charts.push(bmsChart);
    });
  }

  // ── Market Structure renderer (Prevention / Treatment) ────────────────────
  function renderMarketStructure(country, segName, dataKey) {
    var D2 = D.tabs[state.tab].countries[country.code] || {};
    var types  = D2.types  || [];
    var brands = D2.brands || [];
    var topAsins = D2.topAsins || [];
    var totalUnits = D2.totalUnits || 0;
    var totalRev   = D2.totalRevenue || 0;
    var segColor = (SEG_COLORS && SEG_COLORS[segName]) || '#64748b';
    var badgeStyle = 'background:' + segColor + '22;color:' + segColor;

    var html = '';
    html += '<h2>Market Structure \u00b7 ' + segName + ' Segment (12M) \u00b7 ' + esc(country.name) + '</h2>';

    // KPI strip
    html += '<div class="kpis" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;margin-bottom:16px">';
    html += '  <div class="kpi"><div class="kpi-v">' + (D2.top1Share || 0).toFixed(1) + '%</div><div class="kpi-l">Top 1 ASIN Rev Share</div></div>';
    html += '  <div class="kpi"><div class="kpi-v">' + (D2.top3Share || 0).toFixed(1) + '%</div><div class="kpi-l">Top 3 ASINs Share</div></div>';
    html += '  <div class="kpi"><div class="kpi-v">' + (D2.top5Share || 0).toFixed(1) + '%</div><div class="kpi-l">Top 5 ASINs Share</div></div>';
    html += '  <div class="kpi"><div class="kpi-v">' + (D2.top10Share || 0).toFixed(1) + '%</div><div class="kpi-l">Top 10 ASINs Share</div></div>';
    html += '  <div class="kpi"><div class="kpi-v">' + (D2.topBrandShare || 0).toFixed(1) + '%</div><div class="kpi-l">Top Brand (' + esc(D2.topBrand || '\u00b7') + ')</div></div>';
    html += '</div>';

    // Type pies (units + revenue)
    html += '<div class="g2" style="align-items:start">';
    html += '  <div class="card"><h3>Type \u00b7 Unit Share (12M) \u00b7 ' + segName + '</h3><div class="cw" style="height:280px"><canvas id="msTypeUnitPie"></canvas></div><div class="note">' + D2.asinCount + ' ' + segName + ' ASINs across ' + types.length + ' product types. Total: ' + fmtInt(totalUnits) + ' units.</div></div>';
    html += '  <div class="card"><h3>Type \u00b7 Revenue Share (12M) \u00b7 ' + segName + '</h3><div class="cw" style="height:280px"><canvas id="msTypeRevPie"></canvas></div><div class="note">Revenue = 12M units \u00d7 listed ASIN price. Total: ' + fmtMoneyShort(totalRev) + '.</div></div>';
    html += '</div>';

    // Product Type Summary table
    html += '<div class="card"><h3>Product Type Summary (12M) \u00b7 ' + segName + '</h3><div class="tbl-wrap"><table class="num-right">';
    html += '<thead><tr><th style="text-align:left">Type</th><th>ASINs</th><th>Units 12M</th><th>Unit Share</th><th>Revenue 12M</th><th>Rev Share</th><th>Avg Rating</th></tr></thead><tbody>';
    types.forEach(function(t) {
      html += '<tr><td style="text-align:left">' + esc(t.name) + '</td>';
      html += '<td>' + t.asins + '</td>';
      html += '<td>' + fmtInt(t.units) + '</td>';
      html += '<td>' + t.unitShare.toFixed(1) + '%</td>';
      html += '<td>' + fmtMoney(t.revenue) + '</td>';
      html += '<td>' + t.revShare.toFixed(1) + '%</td>';
      html += '<td>' + (t.avgRating ? t.avgRating.toFixed(2) : '\u00b7') + '</td></tr>';
    });
    html += '</tbody></table></div><div class="note">' + segName + ' segment only \u00b7 ' + D2.asinCount + ' ASINs across ' + types.length + ' product types.</div></div>';

    // Brand Share by Type · Units
    html += '<div class="card"><h3>Brand Share by Type \u00b7 Units (12M) \u00b7 ' + segName + '</h3>';
    html += '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;margin-top:12px">';
    types.forEach(function(t, i) {
      html += '<div>';
      html += '  <p style="text-align:center;font-size:.8rem;font-weight:700;color:#475569;margin:0 0 8px">' + esc(t.name) + ' \u00b7 ' + fmtInt(t.units) + ' units \u00b7 ' + t.asins + ' ASINs</p>';
      html += '  <div class="cw" style="height:260px"><canvas id="msTypeBrandUnit_' + i + '"></canvas></div>';
      html += '</div>';
    });
    html += '</div></div>';

    // Brand Share by Type · Revenue
    html += '<div class="card"><h3>Brand Share by Type \u00b7 Revenue (12M) \u00b7 ' + segName + '</h3>';
    html += '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;margin-top:12px">';
    types.forEach(function(t, i) {
      html += '<div>';
      html += '  <p style="text-align:center;font-size:.8rem;font-weight:700;color:#475569;margin:0 0 8px">' + esc(t.name) + ' \u00b7 ' + fmtMoneyShort(t.revenue) + ' \u00b7 ' + t.asins + ' ASINs</p>';
      html += '  <div class="cw" style="height:260px"><canvas id="msTypeBrandRev_' + i + '"></canvas></div>';
      html += '</div>';
    });
    html += '</div></div>';

    // Price Positioning · TOP 3 ASINs by 12M Units per Product Type
    var hasScatter = types.some(function(t) { return t.topAsinsByUnits && t.topAsinsByUnits.length; });
    if (hasScatter) {
      html += '<div class="card" style="margin-top:18px">';
      html += '  <h3>Price Positioning \u00b7 TOP 3 ASINs by 12M Units per Product Type (' + segName + ')</h3>';
      html += '  <div class="cw" style="height:420px"><canvas id="msPriceScatter"></canvas></div>';
      html += '  <div class="note">Each Product Type contributes its top 3 ASINs ranked by 12M units. X = listed price (' + D.currency + '), Y = 12M units. Hover a point to see brand, ASIN, title.</div>';
      html += '</div>';
    }

    // Brand Summary table
    html += '<div class="card" style="margin-top:20px"><h3>Brand Summary \u00b7 ' + segName + ' (12M)</h3><div class="tbl-wrap"><table class="num-right">';
    html += '<thead><tr><th style="text-align:left">Brand</th><th>Rev (12M)</th><th>Share</th><th>ASINs</th><th>Avg Rating</th><th>Total Reviews</th></tr></thead><tbody>';
    brands.forEach(function(b) {
      html += '<tr><td style="text-align:left">' + esc(b.brand) + '</td>';
      html += '<td>' + fmtMoney(b.revenue) + '</td>';
      html += '<td>' + b.share.toFixed(1) + '%</td>';
      html += '<td>' + b.asins + '</td>';
      html += '<td>' + (b.avgRating ? b.avgRating.toFixed(2) : '\u00b7') + '</td>';
      html += '<td>' + fmtInt(b.totalReviews) + '</td></tr>';
    });
    html += '</tbody></table></div></div>';

    // Top ASINs table
    html += '<div class="card" style="margin-top:20px"><h3>Top ' + segName + ' ASINs \u00b7 by Revenue (12M)</h3><div class="tbl-wrap"><table class="num-right">';
    html += '<thead><tr><th style="text-align:left">ASIN</th><th style="text-align:left">Brand</th><th style="text-align:left">Title</th><th>Price</th><th>Revenue (12M)</th><th>Rev Share</th><th>Reviews</th><th>Age (mo)</th></tr></thead><tbody>';
    topAsins.forEach(function(p) {
      html += '<tr>';
      html += '<td style="text-align:left"><code style="font-size:.75rem">' + esc(p.asin) + '</code></td>';
      html += '<td style="text-align:left">' + esc(p.brand) + '</td>';
      html += '<td style="text-align:left;max-width:380px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + esc(p.title) + '">' + esc(p.title) + '</td>';
      html += '<td>' + D.currency + p.price.toFixed(2) + '</td>';
      html += '<td>' + fmtMoney(p.revenue) + '</td>';
      html += '<td>' + p.revShare.toFixed(1) + '%</td>';
      html += '<td>' + fmtInt(p.reviews) + '</td>';
      html += '<td>' + p.age + '</td></tr>';
    });
    html += '</tbody></table></div></div>';

    document.getElementById('panel').innerHTML = html;

    // Charts
    var typeLabels = types.map(function(t){ return t.name; });
    var typeColors = types.map(function(_, i){ return BRAND_PALETTE_JS[i % BRAND_PALETTE_JS.length]; });
    pie('msTypeUnitPie', typeLabels, types.map(function(t){ return t.units;   }), typeColors, false);
    pie('msTypeRevPie',  typeLabels, types.map(function(t){ return t.revenue; }), typeColors, true);

    types.forEach(function(t, i) {
      var bLabels = t.brandsByUnits.map(function(b){ return b.brand; });
      var bData   = t.brandsByUnits.map(function(b){ return b.units; });
      var bColors = t.brandsByUnits.map(function(b, j){ return brandColor(b.brand, j); });
      pie('msTypeBrandUnit_' + i, bLabels, bData, bColors, false);

      var rLabels = t.brandsByRevenue.map(function(b){ return b.brand; });
      var rData   = t.brandsByRevenue.map(function(b){ return b.revenue; });
      var rColors = t.brandsByRevenue.map(function(b, j){ return brandColor(b.brand, j); });
      pie('msTypeBrandRev_' + i, rLabels, rData, rColors, true);
    });

    // Price Positioning scatter (top 3 ASINs per type, by 12M units)
    if (hasScatter) {
      var scatCtx = document.getElementById('msPriceScatter');
      if (scatCtx) {
        var scatDatasets = types.map(function(t, i) {
          var color = BRAND_PALETTE_JS[i % BRAND_PALETTE_JS.length];
          return {
            label: t.name,
            data: (t.topAsinsByUnits || []).map(function(p) {
              return { x: p.price, y: p.units, asin: p.asin, brand: p.brand, title: p.title };
            }),
            backgroundColor: color,
            borderColor: color,
            pointRadius: 7,
            pointHoverRadius: 10,
          };
        }).filter(function(ds) { return ds.data.length > 0; });
        var scatChart = new Chart(scatCtx, {
          type: 'scatter',
          data: { datasets: scatDatasets },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
              legend: { position: 'bottom', labels: { font: { size: 11 }, boxWidth: 14, padding: 10 } },
              datalabels: {
                align: 'top', anchor: 'end', offset: 4,
                color: '#475569', font: { size: 9, weight: '600' },
                formatter: function(v) { return v.brand; }
              },
              tooltip: {
                callbacks: {
                  title: function(ctx) { return ctx[0].dataset.label; },
                  label: function(ctx) {
                    var p = ctx.raw;
                    return [
                      p.brand + ' \u00b7 ' + p.asin,
                      D.currency + p.x.toFixed(2) + '  \u00b7  ' + Math.round(p.y).toLocaleString() + ' units (12M)',
                      (p.title || '').slice(0, 80),
                    ];
                  }
                }
              }
            },
            scales: {
              x: { title: { display: true, text: 'Price (' + D.currency + ')', font: { size: 11, weight: '600' }, color: '#475569' }, beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { size: 10 }, color: '#64748b', callback: function(v) { return D.currency + v; } } },
              y: { title: { display: true, text: 'Units (12M)', font: { size: 11, weight: '600' }, color: '#475569' }, beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { size: 10 }, color: '#64748b' } }
            }
          }
        });
        charts.push(scatChart);
      }
    }
  }

  // ── Treatment Methods renderer ────────────────────────────────────────────
  var METHOD_COLORS = {
    'Physical':            { bg: '#dbeafe', fg: '#1d4ed8', pie: '#2563eb' },
    'Chemical':            { bg: '#fce7f3', fg: '#9d174d', pie: '#db2777' },
    'Physical + Chemical': { bg: '#ede9fe', fg: '#6d28d9', pie: '#8b5cf6' },
  };
  function methodBadge(m) {
    var c = METHOD_COLORS[m] || { bg: '#f1f5f9', fg: '#64748b', pie: '#64748b' };
    return '<span class="badge" style="background:' + c.bg + ';color:' + c.fg + '">' + esc(m) + '</span>';
  }

  function renderTreatmentMethods(country) {
    var D2 = D.tabs['treatment-methods'].countries[country.code] || {};
    var methods = D2.methods || [];
    var totalUnits = D2.totalUnits || 0;
    var totalRev   = D2.totalRevenue || 0;

    var html = '';
    html += '<h2>Treatment Method \u00b7 Physical vs Chemical (12M) \u00b7 ' + esc(country.name) + '</h2>';

    if (D2.asinCount === 0) {
      html += '<div class="card"><p style="color:#64748b;font-size:.85rem">No products with a Treatment Method classification in ' + esc(country.name) + '. Add values in the <code>Treatment Method</code> column of the X-Ray CSV (Physical / Chemical / Physical + Chemical) and rebuild.</p></div>';
      document.getElementById('panel').innerHTML = html;
      return;
    }

    // KPI strip
    html += '<div class="kpis" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:14px">';
    methods.forEach(function(m) {
      var col = (METHOD_COLORS[m.name] || {}).pie || '#64748b';
      html += '  <div class="kpi" style="border-left:4px solid ' + col + '"><div class="kpi-v">' + fmtMoneyShort(m.revenue) + '</div><div class="kpi-l">' + esc(m.name) + ' \u00b7 12M Revenue</div></div>';
      html += '  <div class="kpi" style="border-left:4px solid ' + col + '"><div class="kpi-v">' + fmtInt(m.units) + '</div><div class="kpi-l">' + esc(m.name) + ' \u00b7 12M Units</div></div>';
    });
    html += '</div>';

    // Insight
    var parts = methods.map(function(m) {
      return '<strong>' + esc(m.name) + '</strong> ' + m.unitShare.toFixed(1) + '% units / ' + m.revShare.toFixed(1) + '% revenue (avg price ' + D.currency + m.avgPrice.toFixed(2) + ')';
    });
    html += '<div class="insight"><strong>' + D2.asinCount + ' ASINs</strong> classified across ' + methods.length + ' method' + (methods.length === 1 ? '' : 's') + '. ' + parts.join(' \u00b7 ') + '.</div>';

    // Method pies
    html += '<div class="g2" style="align-items:start">';
    html += '  <div class="card"><h3>Method \u00b7 Unit Share (12M)</h3><div class="cw" style="height:280px"><canvas id="methUnitPie"></canvas></div><div class="note">Share of 12M units by Treatment Method. Total: ' + fmtInt(totalUnits) + ' units.</div></div>';
    html += '  <div class="card"><h3>Method \u00b7 Revenue Share (12M)</h3><div class="cw" style="height:280px"><canvas id="methRevPie"></canvas></div><div class="note">Share of 12M revenue by Treatment Method. Total: ' + fmtMoneyShort(totalRev) + '.</div></div>';
    html += '</div>';

    // Product Type × Method table
    html += '<div class="card"><h3>Product Type Summary by Treatment Method (12M)</h3><div class="tbl-wrap"><table class="num-right">';
    html += '<thead><tr><th style="text-align:left">Product Type</th><th>Method</th><th>Units 12M</th><th>Units Share %</th><th>Revenue 12M</th><th>Revenue Share %</th></tr></thead><tbody>';
    (D2.typeMethodRows || []).forEach(function(r) {
      html += '<tr>';
      html += '<td style="text-align:left">' + esc(r.type) + '</td>';
      html += '<td>' + methodBadge(r.method) + '</td>';
      html += '<td data-val="' + r.units + '">' + fmtInt(r.units) + '</td>';
      html += '<td data-val="' + r.unitShare.toFixed(2) + '">' + r.unitShare.toFixed(1) + '%</td>';
      html += '<td data-val="' + r.revenue + '">' + fmtMoney(r.revenue) + '</td>';
      html += '<td data-val="' + r.revShare.toFixed(2) + '">' + r.revShare.toFixed(1) + '%</td>';
      html += '</tr>';
    });
    html += '</tbody></table></div></div>';

    // Brand pies grids · Units
    html += '<div class="card" style="margin-top:18px"><h3>Brand Share by Method \u00b7 Units (12M)</h3>';
    html += '<div style="display:grid;grid-template-columns:repeat(' + methods.length + ',1fr);gap:20px;margin-top:12px">';
    methods.forEach(function(m, i) {
      html += '<div>';
      html += '  <p style="text-align:center;font-size:.8rem;font-weight:700;color:#475569;margin:0 0 8px">' + methodBadge(m.name) + ' \u00b7 ' + fmtInt(m.units) + ' units \u00b7 ' + m.asins + ' ASINs</p>';
      html += '  <div class="cw" style="height:260px"><canvas id="methBrandUnit_' + i + '"></canvas></div>';
      html += '</div>';
    });
    html += '</div></div>';

    // Brand pies grids · Revenue
    html += '<div class="card" style="margin-top:18px"><h3>Brand Share by Method \u00b7 Revenue (12M)</h3>';
    html += '<div style="display:grid;grid-template-columns:repeat(' + methods.length + ',1fr);gap:20px;margin-top:12px">';
    methods.forEach(function(m, i) {
      html += '<div>';
      html += '  <p style="text-align:center;font-size:.8rem;font-weight:700;color:#475569;margin:0 0 8px">' + methodBadge(m.name) + ' \u00b7 ' + fmtMoneyShort(m.revenue) + ' \u00b7 ' + m.asins + ' ASINs</p>';
      html += '  <div class="cw" style="height:260px"><canvas id="methBrandRev_' + i + '"></canvas></div>';
      html += '</div>';
    });
    html += '</div></div>';

    // Price Positioning · TOP 3 ASINs by 12M Units per Method
    var hasMethodScatter = methods.some(function(m) { return m.topAsinsByUnits && m.topAsinsByUnits.length; });
    if (hasMethodScatter) {
      html += '<div class="card" style="margin-top:18px">';
      html += '  <h3>Price Positioning \u00b7 TOP 3 ASINs by 12M Units per Method</h3>';
      html += '  <div class="cw" style="height:420px"><canvas id="methPriceScatter"></canvas></div>';
      html += '  <div class="note">Each Treatment Method contributes its top 3 ASINs ranked by 12M units. X = listed price (' + D.currency + '), Y = 12M units. Hover a point to see brand, ASIN, title.</div>';
      html += '</div>';
    }

    // Brand Summary table
    html += '<div class="card" style="margin-top:20px"><h3>Brand Summary \u00b7 Treatment Method (12M)</h3><div class="tbl-wrap"><table class="num-right">';
    html += '<thead><tr><th style="text-align:left">Brand</th><th>Method</th><th style="text-align:left">Types</th><th>Share %</th><th>ASINs</th><th>Avg Rating</th><th>Total Reviews</th></tr></thead><tbody>';
    (D2.brandRows || []).forEach(function(b) {
      var badges = b.methods.map(function(m){ return methodBadge(m); }).join(' ');
      html += '<tr>';
      html += '<td style="text-align:left"><strong>' + esc(b.brand) + '</strong></td>';
      html += '<td>' + badges + '</td>';
      html += '<td style="text-align:left">' + esc(b.typesStr) + '</td>';
      html += '<td data-val="' + b.share.toFixed(2) + '">' + b.share.toFixed(1) + '%</td>';
      html += '<td>' + b.asins + '</td>';
      html += '<td>' + (b.avgRating ? b.avgRating.toFixed(2) : '\u00b7') + '</td>';
      html += '<td data-val="' + b.totalReviews + '">' + fmtInt(b.totalReviews) + '</td>';
      html += '</tr>';
    });
    html += '</tbody></table></div></div>';

    // All Products table
    html += '<div class="card" style="margin-top:20px"><h3>All Products \u00b7 Treatment Method (12M)</h3><div class="tbl-wrap"><table class="num-right">';
    html += '<thead><tr><th style="text-align:left">ASIN</th><th style="text-align:left">Brand</th><th style="text-align:left">Title</th><th>Method</th><th>Price</th><th>Revenue 12M</th><th>Reviews</th><th>Age (mo)</th></tr></thead><tbody>';
    (D2.allRows || []).forEach(function(p) {
      var dom = country.code === 'DE' ? 'de' : country.code === 'FR' ? 'fr' : country.code === 'IT' ? 'it' : 'es';
      html += '<tr>';
      html += '<td style="text-align:left"><a href="https://www.amazon.' + dom + '/dp/' + esc(p.asin) + '" target="_blank" rel="noopener"><code style="font-size:.75rem">' + esc(p.asin) + '</code></a></td>';
      html += '<td style="text-align:left">' + esc(p.brand) + '</td>';
      html += '<td style="text-align:left;max-width:380px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + esc(p.title) + '">' + esc(p.title) + '</td>';
      html += '<td>' + methodBadge(p.method) + '</td>';
      html += '<td data-val="' + p.price + '">' + D.currency + p.price.toFixed(2) + '</td>';
      html += '<td data-val="' + p.revenue + '">' + fmtMoney(p.revenue) + '</td>';
      html += '<td data-val="' + p.reviews + '">' + fmtInt(p.reviews) + '</td>';
      html += '<td data-val="' + p.age + '">' + p.age + '</td>';
      html += '</tr>';
    });
    html += '</tbody></table></div></div>';

    document.getElementById('panel').innerHTML = html;

    // Charts
    var methodLabels = methods.map(function(m){ return m.name; });
    var methodColors = methods.map(function(m){ return (METHOD_COLORS[m.name] || {}).pie || '#64748b'; });
    pie('methUnitPie', methodLabels, methods.map(function(m){ return m.units;   }), methodColors, false);
    pie('methRevPie',  methodLabels, methods.map(function(m){ return m.revenue; }), methodColors, true);

    methods.forEach(function(m, i) {
      var bLabels = m.brandsByUnits.map(function(b){ return b.brand; });
      var bData   = m.brandsByUnits.map(function(b){ return b.units; });
      var bColors = m.brandsByUnits.map(function(b, j){ return brandColor(b.brand, j); });
      pie('methBrandUnit_' + i, bLabels, bData, bColors, false);

      var rLabels = m.brandsByRevenue.map(function(b){ return b.brand; });
      var rData   = m.brandsByRevenue.map(function(b){ return b.revenue; });
      var rColors = m.brandsByRevenue.map(function(b, j){ return brandColor(b.brand, j); });
      pie('methBrandRev_' + i, rLabels, rData, rColors, true);
    });

    // Price Positioning scatter (top 3 ASINs per Method, by 12M units)
    if (hasMethodScatter) {
      var mScatCtx = document.getElementById('methPriceScatter');
      if (mScatCtx) {
        var mScatDatasets = methods.map(function(m) {
          var color = (METHOD_COLORS[m.name] || {}).pie || '#64748b';
          return {
            label: m.name,
            data: (m.topAsinsByUnits || []).map(function(p) {
              return { x: p.price, y: p.units, asin: p.asin, brand: p.brand, title: p.title };
            }),
            backgroundColor: color,
            borderColor: color,
            pointRadius: 7,
            pointHoverRadius: 10,
          };
        }).filter(function(ds) { return ds.data.length > 0; });
        var mScatChart = new Chart(mScatCtx, {
          type: 'scatter',
          data: { datasets: mScatDatasets },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
              legend: { position: 'bottom', labels: { font: { size: 11 }, boxWidth: 14, padding: 10 } },
              datalabels: {
                align: 'top', anchor: 'end', offset: 4,
                color: '#475569', font: { size: 9, weight: '600' },
                formatter: function(v) { return v.brand; }
              },
              tooltip: {
                callbacks: {
                  title: function(ctx) { return ctx[0].dataset.label; },
                  label: function(ctx) {
                    var p = ctx.raw;
                    return [
                      p.brand + ' \u00b7 ' + p.asin,
                      D.currency + p.x.toFixed(2) + '  \u00b7  ' + Math.round(p.y).toLocaleString() + ' units (12M)',
                      (p.title || '').slice(0, 80),
                    ];
                  }
                }
              }
            },
            scales: {
              x: { title: { display: true, text: 'Price (' + D.currency + ')', font: { size: 11, weight: '600' }, color: '#475569' }, beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { size: 10 }, color: '#64748b', callback: function(v) { return D.currency + v; } } },
              y: { title: { display: true, text: 'Units (12M)', font: { size: 11, weight: '600' }, color: '#475569' }, beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { size: 10 }, color: '#64748b' } }
            }
          }
        });
        charts.push(mScatChart);
      }
    }
  }

  // ── Reviews VOC renderer (segment-aware: Prevention / Treatment) ─
  function renderReviews(country, tabId) {
    var segment = (D.tabs[tabId] && D.tabs[tabId].segment) || '';
    var D2 = (D.tabs[tabId] && D.tabs[tabId].countries[country.code]) || {};
    var root = document.getElementById('panel');

    if (!D2 || !D2.totalReviews) {
      root.innerHTML = '<div class="card"><h3>Reviews VOC \u00b7 ' + esc(segment) + ' \u00b7 ' + esc(country.name) + ' (' + esc(country.code) + ')</h3>' +
        '<p style="color:#64748b;font-size:.85rem;line-height:1.6">No review data loaded for <strong>' + esc(country.name) + ' \u00b7 ' + esc(segment) + '</strong>.<br>' +
        'Drop review CSVs into <code>reviews/' + esc(country.code) + '/' + esc(segment) + '/</code>, run VOC analysis, save the result to <code>reviews/' + esc(country.code) + '/' + esc(segment) + '/voc.json</code>, then rerun <code>py _build_standalone.py</code>.</p></div>';
      return;
    }

    var STAR_COLORS = { 1: '#dc2626', 2: '#ea580c', 3: '#f59e0b', 4: '#22c55e', 5: '#16a34a' };
    function bw(pctStr, maxPct) { var v = parseFloat(pctStr); return Math.round(v / maxPct * 100) + '%'; }

    var h = '';

    // KPI ROW
    var total = D2.totalReviews;
    var pos = D2.starDist[3] + D2.starDist[4];
    var neg = D2.starDist[0] + D2.starDist[1] + D2.starDist[2];
    var posPct = (pos / total * 100).toFixed(1);
    var negPct = (neg / total * 100).toFixed(1);
    var ratio = neg > 0 ? (pos / neg).toFixed(1) : 'N/A';

    h += '<h2 style="margin-bottom:6px">Reviews VOC \u00b7 ' + esc(segment) + ' \u00b7 ' + esc(country.name) + '</h2>';
    h += '<p style="margin:0 0 14px;color:#64748b;font-size:.78rem">Based on <b>' + total.toLocaleString() + '</b> reviews scraped from the <b>top 5 ' + esc(segment.toLowerCase()) + ' products</b> on amazon.' + esc(country.code.toLowerCase()) + ' (~200\u2013300 reviews per segment).</p>';
    h += '<div class="kpis" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:14px">';
    h += '<div class="kpi"><div class="kpi-v">' + total.toLocaleString() + '</div><div class="kpi-l">Total Reviews</div></div>';
    h += '<div class="kpi"><div class="kpi-v">' + ratio + ' : 1</div><div class="kpi-l">Sentiment Ratio (pos:neg)</div></div>';
    h += '<div class="kpi"><div class="kpi-v" style="color:#16a34a">' + posPct + '%</div><div class="kpi-l">Positive (4\u2605+5\u2605)</div></div>';
    h += '<div class="kpi"><div class="kpi-v" style="color:#dc2626">' + negPct + '%</div><div class="kpi-l">Negative (1\u2605\u20133\u2605)</div></div>';
    h += '</div>';

    // Star Distribution Bar
    var dist = D2.starDist;
    h += '<div class="card" style="padding:12px 16px;margin-bottom:20px">';
    h += '<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">';
    h += '<div style="font-size:.78rem;font-weight:600;color:#475569;white-space:nowrap">Star Distribution</div>';
    h += '<div style="font-size:1.1rem;font-weight:800;color:#0f2942">' + D2.avgRating.toFixed(2) + ' <span style="font-size:.7rem;font-weight:400;color:#64748b">avg</span></div>';
    h += '<div style="flex:1;display:flex;height:22px;border-radius:4px;overflow:hidden;min-width:200px">';
    dist.forEach(function(count, i) {
      var star = i + 1;
      var pct = (count / total * 100).toFixed(1);
      h += '<div style="width:' + pct + '%;background:' + STAR_COLORS[star] + ';display:flex;align-items:center;justify-content:center;color:#fff;font-size:.68rem;font-weight:600">' + (parseFloat(pct) >= 5 ? pct + '%' : '') + '</div>';
    });
    h += '</div>';
    h += '<div style="display:flex;gap:10px;flex-wrap:wrap;font-size:.68rem;color:#475569">';
    dist.forEach(function(count, i) {
      h += '<span><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:' + STAR_COLORS[i+1] + ';margin-right:3px"></span>' + (i+1) + '\u2605 ' + count + '</span>';
    });
    h += '</div></div></div>';

    // Sub-tab bar
    h += '<div class="voc-sub-tabs">';
    h += '<div class="voc-sub-tab active" data-panel="voc-ci">Customer Insights</div>';
    h += '<div class="voc-sub-tab" data-panel="voc-ca">Review Browser</div>';
    h += '</div>';

    // SUB-PANEL: Customer Insights
    h += '<div id="voc-ci" class="voc-sub-panel active">';
    h += '<div class="voc-anchor-nav">';
    h += '<a href="#voc-sec-cp" class="active" data-target="voc-sec-cp">Customer Profile</a>';
    h += '<a href="#voc-sec-us" data-target="voc-sec-us">Usage Scenario</a>';
    h += '<a href="#voc-sec-cs" data-target="voc-sec-cs">Customer Sentiment</a>';
    h += '<a href="#voc-sec-bm" data-target="voc-sec-bm">Buyers Motivation</a>';
    h += '<a href="#voc-sec-ce" data-target="voc-sec-ce">Customer Expectations</a>';
    h += '</div>';

    // Customer Profile
    h += '<div id="voc-sec-cp">';
    h += '<div class="sec-header"><div class="sec-title">Customer Profile</div></div>';
    if (D2.cpSummary) h += '<div class="sec-summary">' + D2.cpSummary + '</div>';
    h += '<div class="cp-charts">';
    h += '<div class="cp-chart-box"><h4>Who</h4><div class="cp-chart-wrap"><canvas id="vocCpWho"></canvas></div></div>';
    h += '<div class="cp-chart-box"><h4>When</h4><div class="cp-chart-wrap"><canvas id="vocCpWhen"></canvas></div></div>';
    h += '<div class="cp-chart-box"><h4>Where</h4><div class="cp-chart-wrap"><canvas id="vocCpWhere"></canvas></div></div>';
    h += '<div class="cp-chart-box"><h4>What</h4><div class="cp-chart-wrap"><canvas id="vocCpWhat"></canvas></div></div>';
    h += '</div>';
    h += '<div class="cp-legend">\u25A0 reviews 4-5 stars \u00b7 <span style="color:#ef4444">\u25A0</span> reviews 1-3 stars</div>';
    h += '</div>';

    // Usage Scenario
    h += '<div id="voc-sec-us" style="margin-top:36px">';
    h += '<div class="sec-header"><div class="sec-title">Usage Scenario</div></div>';
    h += '<div class="card" style="padding:0;overflow:hidden"><table class="us-table"><thead><tr><th style="width:22%">Usage Scenario</th><th>Reason</th><th style="width:140px;text-align:right">Percentage</th></tr></thead><tbody>';
    if (D2.usageScenarios && D2.usageScenarios.length) {
      var usMax = parseFloat(D2.usageScenarios[0].pct);
      D2.usageScenarios.forEach(function(s) {
        h += '<tr><td class="us-label">' + s.label + '</td><td class="us-reason">' + s.reason + '</td>';
        h += '<td class="us-pct"><div class="us-bar-wrap"><div class="us-bar" style="width:' + bw(s.pct, usMax) + '"></div></div><span>' + s.pct + '</span></td></tr>';
      });
    }
    h += '</tbody></table></div></div>';

    // Customer Sentiment
    h += '<div id="voc-sec-cs" style="margin-top:36px">';
    h += '<div class="sec-header"><div class="sec-title">Customer Sentiment</div></div>';
    if (D2.csSummary) h += '<div class="sec-summary">' + D2.csSummary + '</div>';
    h += '<div class="cs-neg-zone">';
    h += '<div class="card" style="padding:0;overflow:hidden;border:1.5px solid #fecaca"><table class="us-table"><thead><tr style="background:#fef2f2"><th style="width:22%;border-left:3px solid #dc2626">Negative Feedback Topic</th><th>Reasons for Negative Feedback</th><th style="width:140px;text-align:right">Percentage</th></tr></thead><tbody id="vocNegBody"></tbody></table></div>';
    h += '<div class="card" style="margin-top:22px;border:1.5px solid #fca5a5"><div class="sec-header" style="margin-bottom:10px"><div class="sec-title">Negative Review Insights \u00b7 Strategy</div></div>';
    h += '<table class="si-table"><thead><tr><th style="width:130px">Analysis Type</th><th>Finding (from 1\u2605+2\u2605 reviews)</th><th>Strategic Implication</th></tr></thead><tbody id="vocNegInsights"></tbody></table></div>';
    h += '</div>';
    h += '<div class="cs-pos-zone">';
    h += '<div class="card" style="padding:0;overflow:hidden;border:1.5px solid #bbf7d0"><table class="us-table"><thead><tr style="background:#f0fdf4"><th style="width:22%;border-left:3px solid #16a34a">Positive Feedback Topic</th><th>Reasons for Positive Feedback</th><th style="width:140px;text-align:right">Percentage</th></tr></thead><tbody id="vocPosBody"></tbody></table></div>';
    h += '<div class="card" style="margin-top:22px"><div class="sec-header" style="margin-bottom:10px"><div class="sec-title">Positive Review Insights \u00b7 Strategy</div></div>';
    h += '<table class="si-table"><thead><tr><th style="width:130px">Analysis Type</th><th>Finding (from 4\u2605+5\u2605 reviews)</th><th>Strategic Implication</th></tr></thead><tbody id="vocPosInsights"></tbody></table></div>';
    h += '</div>';
    h += '</div>';

    // Buyers Motivation
    h += '<div id="voc-sec-bm" style="margin-top:36px">';
    h += '<div class="sec-header"><div class="sec-title">Buyers Motivation</div></div>';
    h += '<div class="card" style="padding:0;overflow:hidden"><table class="us-table"><thead><tr><th style="width:22%">Buyers Motivation</th><th>Reason</th><th style="width:140px;text-align:right">Percentage</th></tr></thead><tbody>';
    if (D2.buyersMotivation && D2.buyersMotivation.length) {
      var bmMax = parseFloat(D2.buyersMotivation[0].pct);
      D2.buyersMotivation.forEach(function(m) {
        h += '<tr><td class="us-label">' + m.label + '</td><td class="us-reason">' + m.reason + '</td>';
        h += '<td class="us-pct"><div class="us-bar-wrap"><div class="us-bar" style="width:' + bw(m.pct, bmMax) + '"></div></div><span>' + m.pct + '</span></td></tr>';
      });
    }
    h += '</tbody></table></div></div>';

    // Customer Expectations
    h += '<div id="voc-sec-ce" style="margin-top:36px">';
    h += '<div class="sec-header"><div class="sec-title">Customer Expectations</div></div>';
    h += '<div class="card" style="padding:0;overflow:hidden"><table class="us-table"><thead><tr><th style="width:22%">Unmet Need</th><th>Reason</th><th style="width:140px;text-align:right">Percentage</th></tr></thead><tbody>';
    if (D2.customerExpectations && D2.customerExpectations.length) {
      var ceMax = parseFloat(D2.customerExpectations[0].pct);
      D2.customerExpectations.forEach(function(e) {
        h += '<tr><td class="us-label">' + e.label + '</td><td class="us-reason">' + e.reason + '</td>';
        h += '<td class="us-pct"><div class="us-bar-wrap"><div class="us-bar" style="width:' + bw(e.pct, ceMax) + '"></div></div><span>' + e.pct + '</span></td></tr>';
      });
    }
    h += '</tbody></table></div></div>';

    h += '</div>'; // end voc-ci

    // SUB-PANEL: Review Browser
    h += '<div id="voc-ca" class="voc-sub-panel">';
    h += '<div class="card"><h3>Review Browser <span style="font-size:.72rem;font-weight:400;color:#64748b;margin-left:8px">Filter by rating, theme, or keyword</span></h3>';
    h += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">';
    h += '<select id="vocFilterRating" style="font-size:.73rem;border:1.5px solid #cbd5e1;border-radius:5px;padding:4px 8px;background:#fff"><option value="">All Ratings</option><option value="1">1\u2605</option><option value="2">2\u2605</option><option value="3">3\u2605</option><option value="4">4\u2605</option><option value="5">5\u2605</option></select>';
    h += '<select id="vocFilterTheme" style="font-size:.73rem;border:1.5px solid #cbd5e1;border-radius:5px;padding:4px 8px;background:#fff"></select>';
    h += '<input id="vocFilterSearch" placeholder="Search keyword..." style="font-size:.73rem;border:1.5px solid #cbd5e1;border-radius:5px;padding:4px 8px;width:160px">';
    h += '<button id="vocClearBtn" style="font-size:.73rem;border:1.5px solid #cbd5e1;border-radius:5px;padding:4px 10px;background:#f8fafc;cursor:pointer">Clear</button>';
    h += '</div>';
    h += '<div id="vocResultCount" style="font-size:.72rem;color:#64748b;margin-bottom:6px"></div>';
    h += '<div class="tbl-wrap" style="max-height:520px"><table><thead><tr><th style="width:40px">\u2605</th><th>Review</th></tr></thead><tbody id="vocReviewBody"></tbody></table></div>';
    h += '</div></div>';

    root.innerHTML = h;

    // RENDERING
    if (window.Chart && window.ChartDataLabels) { try { Chart.register(ChartDataLabels); } catch(e){} }

    // Sub-tab switching
    root.querySelectorAll('.voc-sub-tab').forEach(function(tab) {
      tab.addEventListener('click', function() {
        root.querySelectorAll('.voc-sub-tab').forEach(function(t) { t.classList.remove('active'); });
        root.querySelectorAll('.voc-sub-panel').forEach(function(p) { p.classList.remove('active'); });
        tab.classList.add('active');
        var panel = document.getElementById(tab.dataset.panel);
        if (panel) panel.classList.add('active');
        Object.values(Chart.instances).forEach(function(c) { c.resize(); });
      });
    });

    // Anchor scroll
    root.querySelectorAll('.voc-anchor-nav a').forEach(function(a) {
      a.addEventListener('click', function(e) {
        e.preventDefault();
        var target = document.getElementById(a.dataset.target);
        if (target) {
          var y = target.getBoundingClientRect().top + window.pageYOffset - 90;
          window.scrollTo({ top: y, behavior: 'smooth' });
        }
        root.querySelectorAll('.voc-anchor-nav a').forEach(function(x) { x.classList.remove('active'); });
        a.classList.add('active');
      });
    });

    // Customer Profile stacked bars
    function makeStackedBar(canvasId, dataObj) {
      var ctx = document.getElementById(canvasId);
      if (!ctx || !dataObj) return;
      var chart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: dataObj.labels,
          datasets: [
            { label: '4-5 stars', data: dataObj.pos, backgroundColor: '#22c55e', borderRadius: { topLeft: 3, topRight: 3 }, barPercentage: 0.7 },
            { label: '1-3 stars', data: dataObj.neg.map(function(v) { return -v; }), backgroundColor: '#ef4444', borderRadius: { bottomLeft: 3, bottomRight: 3 }, barPercentage: 0.7 }
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: { legend: { display: false }, datalabels: { display: false },
            tooltip: { callbacks: { label: function(ctx) { return ctx.dataset.label + ': ' + Math.abs(ctx.raw); } } }
          },
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 10 }, color: '#64748b', maxRotation: 35 } },
            y: { grid: { color: '#f1f5f9' }, ticks: { font: { size: 10 }, color: '#94a3b8', callback: function(v) { return Math.abs(v); } } }
          }
        }
      });
      charts.push(chart);
    }
    if (D2.cpWho) makeStackedBar('vocCpWho', D2.cpWho);
    if (D2.cpWhen) makeStackedBar('vocCpWhen', D2.cpWhen);
    if (D2.cpWhere) makeStackedBar('vocCpWhere', D2.cpWhere);
    if (D2.cpWhat) makeStackedBar('vocCpWhat', D2.cpWhat);

    // Negative topics (expandable rows)
    if (D2.negativeTopics && D2.negativeTopics.length) {
      var negMax = parseFloat(D2.negativeTopics[0].pct);
      var negHtml = '';
      D2.negativeTopics.forEach(function(t) {
        var bullets = (t.bullets || []).map(function(b) { return '<li>' + b + '</li>'; }).join('');
        var quotes = (t.quotes || []).map(function(q) { return '<p>' + q + '</p>'; }).join('');
        negHtml += '<tr class="nf-row" style="cursor:pointer"><td class="us-label"><span class="nf-arrow">\u25B6</span> ' + t.label + '</td>';
        negHtml += '<td class="us-reason">' + t.reason + '</td>';
        negHtml += '<td class="us-pct"><div class="us-bar-wrap"><div class="us-bar" style="width:' + bw(t.pct, negMax) + ';background:#fca5a5"></div></div><span>' + t.pct + '</span></td></tr>';
        negHtml += '<tr class="nf-detail"><td colspan="3"><div class="nf-body"><ul>' + bullets + '</ul><div class="nf-quotes">' + quotes + '</div></div></td></tr>';
      });
      document.getElementById('vocNegBody').innerHTML = negHtml;
    }

    // Negative insights
    if (D2.negativeInsights) {
      document.getElementById('vocNegInsights').innerHTML = D2.negativeInsights.map(function(i) {
        return '<tr><td><span class="si-badge" style="background:' + i.badgeBg + ';color:' + i.badgeColor + '">' + i.type + '</span></td><td>' + i.finding + '</td><td>' + i.implication + '</td></tr>';
      }).join('');
    }

    // Positive topics (expandable rows)
    if (D2.positiveTopics && D2.positiveTopics.length) {
      var posMax = parseFloat(D2.positiveTopics[0].pct);
      var posHtml = '';
      D2.positiveTopics.forEach(function(t) {
        var bullets = (t.bullets || []).map(function(b) { return '<li>' + b + '</li>'; }).join('');
        var quotes = (t.quotes || []).map(function(q) { return '<p>' + q + '</p>'; }).join('');
        posHtml += '<tr class="pf-row" style="cursor:pointer"><td class="us-label"><span class="pf-arrow">\u25B6</span> ' + t.label + '</td>';
        posHtml += '<td class="us-reason">' + t.reason + '</td>';
        posHtml += '<td class="us-pct"><div class="us-bar-wrap"><div class="us-bar" style="width:' + bw(t.pct, posMax) + ';background:#86efac"></div></div><span>' + t.pct + '</span></td></tr>';
        posHtml += '<tr class="pf-detail"><td colspan="3"><div class="pf-body"><ul>' + bullets + '</ul><div class="pf-quotes">' + quotes + '</div></div></td></tr>';
      });
      document.getElementById('vocPosBody').innerHTML = posHtml;
    }

    // Positive insights
    if (D2.positiveInsights) {
      document.getElementById('vocPosInsights').innerHTML = D2.positiveInsights.map(function(i) {
        return '<tr><td><span class="si-badge" style="background:' + i.badgeBg + ';color:' + i.badgeColor + '">' + i.type + '</span></td><td>' + i.finding + '</td><td>' + i.implication + '</td></tr>';
      }).join('');
    }

    // Toggle expandable rows
    root.querySelectorAll('.nf-row').forEach(function(row) {
      row.addEventListener('click', function() {
        var detail = row.nextElementSibling;
        var isOpen = row.classList.contains('open');
        root.querySelectorAll('.nf-row.open').forEach(function(r) { r.classList.remove('open'); r.nextElementSibling.classList.remove('open'); });
        if (!isOpen) { row.classList.add('open'); detail.classList.add('open'); }
      });
    });
    root.querySelectorAll('.pf-row').forEach(function(row) {
      row.addEventListener('click', function() {
        var detail = row.nextElementSibling;
        var isOpen = row.classList.contains('open');
        root.querySelectorAll('.pf-row.open').forEach(function(r) { r.classList.remove('open'); r.nextElementSibling.classList.remove('open'); });
        if (!isOpen) { row.classList.add('open'); detail.classList.add('open'); }
      });
    });

    // Review Browser
    if (D2.themeFilters) {
      document.getElementById('vocFilterTheme').innerHTML = '<option value="">All Themes</option>' + D2.themeFilters.map(function(f) {
        return '<option value="' + f.value + '">' + f.label + '</option>';
      }).join('');
    }

    var reviews = D2.reviews || [];

    function vocFilter() {
      var rating = document.getElementById('vocFilterRating').value;
      var theme = document.getElementById('vocFilterTheme').value;
      var search = (document.getElementById('vocFilterSearch').value || '').toLowerCase();
      var filtered = reviews.filter(function(r) {
        if (rating && r.r != rating) return false;
        if (theme && (r.tags || []).indexOf(theme) === -1) return false;
        if (search && r.t.toLowerCase().indexOf(search) === -1) return false;
        return true;
      });
      document.getElementById('vocResultCount').textContent = 'Showing ' + filtered.length + ' of ' + reviews.length + ' reviews';
      var html = '';
      var limit = Math.min(filtered.length, 200);
      for (var i = 0; i < limit; i++) {
        var r = filtered[i];
        var starHtml = '<span style="color:' + STAR_COLORS[r.r] + ';font-weight:700">' + r.r + '\u2605</span>';
        var tagsHtml = (r.tags || []).map(function(t) {
          return '<span class="pill ' + ((D2.tagStyles && D2.tagStyles[t]) || 'pill-blue') + '">' + t.replace(/_/g, ' ') + '</span>';
        }).join('');
        html += '<tr><td>' + starHtml + '</td><td><div class="review-text">' + r.t.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</div>' +
          (tagsHtml ? '<div style="margin-top:4px">' + tagsHtml + '</div>' : '') + '</td></tr>';
      }
      if (filtered.length > 200) html += '<tr><td colspan="2" style="text-align:center;color:#64748b;font-size:.72rem;padding:12px">Showing first 200 of ' + filtered.length + '. Use filters to narrow.</td></tr>';
      document.getElementById('vocReviewBody').innerHTML = html;
    }

    document.getElementById('vocFilterRating').addEventListener('change', vocFilter);
    document.getElementById('vocFilterTheme').addEventListener('change', vocFilter);
    document.getElementById('vocFilterSearch').addEventListener('input', vocFilter);
    document.getElementById('vocClearBtn').addEventListener('click', function() {
      document.getElementById('vocFilterRating').value = '';
      document.getElementById('vocFilterTheme').value = '';
      document.getElementById('vocFilterSearch').value = '';
      vocFilter();
    });

    vocFilter();
  }

  // ── Marketing Deep-Dive renderer (ported from templates/tabs/marketing-deep-dive/template.html) ─
  function renderMarketingDeepDive(country, tabId) {
    var D2 = (D.tabs[tabId] && D.tabs[tabId].countries[country.code]) || {};
    var root = document.getElementById('panel');

    if (!D2 || !D2.competitors) {
      root.innerHTML = '<div class="card"><h3>Marketing Deep-Dive \u00b7 ' + esc(country.name) + ' (' + esc(country.code) + ')</h3>' +
        '<p style="color:#64748b;font-size:.85rem;line-height:1.6">No data loaded for <strong>' + esc(country.name) + '</strong>.<br>' +
        'Drop competitor listings into <code>data/competitor-listings/' + esc(country.code) + '/raw/</code>, run the MDD build pipeline, save the result to <code>data/competitor-listings/' + esc(country.code) + '/mdd.json</code> (matching the shape used by the shared Console MDD template), then rerun <code>py _build_standalone.py</code>.</p></div>';
      return;
    }

    function mfmt(n) { return D.currency + Number(n || 0).toFixed(0); }

    var h = '<div id="mdd-root">';
    h += '<h2 style="margin-bottom:12px">Marketing Deep-Dive \u00b7 ' + esc(country.name) + '</h2>';

    // Intro
    h += '<p class="sec-summary" style="margin-bottom:24px">Marketing intelligence across <b>' + D2.totalCompetitors + ' top competitors</b> on <b>' + esc(D2.marketplace || ('amazon.' + country.code.toLowerCase())) + '</b>. Listings pulled from SP-API Catalog. Claims tagged across themes and cross-referenced with VOC findings from the Reviews tab.</p>';

    // 1. Competitor Overview Grid
    h += '<div class="mdd-section">';
    h += '<div class="mdd-sec-header"><div class="mdd-sec-title">1. Competitor Overview \u00b7 Top ' + D2.totalCompetitors + ' by 30d Revenue</div><div class="mdd-sec-sub">Click a card to see full bullets, claims, and image stack</div></div>';
    h += '<div class="mdd-explainer">Each card is one competitor listing pulled from <b>Amazon SP-API Catalog</b>. Brand, title, hero image, price, rating, BSR and 30-day sales/revenue come from the X-Ray export. The <b>theme tags</b> on each card show which marketing claims the listing makes (regex-matched against title + bullets + description in the local language).</div>';
    h += '<div class="mdd-comp-grid">';
    D2.competitors.forEach(function(c, idx) {
      h += '<div class="mdd-comp-card" data-idx="' + idx + '">';
      h += '  <div class="mdd-comp-img">' + (c.mainImage ? '<img src="' + esc(c.mainImage) + '" alt="">' : '<span style="color:#cbd5e1;font-size:.7rem">no image</span>') + '</div>';
      h += '  <div class="mdd-comp-brand">' + esc(c.brand) + '</div>';
      h += '  <div class="mdd-comp-title">' + esc(c.title) + '</div>';
      h += '  <div class="mdd-comp-themes">';
      (c.themes || []).forEach(function(t) {
        h += '<span class="mdd-theme-pill">' + esc(String(t).replace(/_/g, ' ')) + '</span>';
      });
      h += '  </div>';
      h += '  <div class="mdd-comp-meta">';
      h += '    <span><b>' + mfmt(c.price) + '</b> price</span>';
      h += '    <span><b>\u2605' + (c.rating || 0).toFixed(1) + '</b> \u00b7 ' + (c.reviews || 0).toLocaleString() + '</span>';
      h += '    <span><b>' + mfmt(c.rev30d) + '</b> 30d rev</span>';
      h += '  </div>';
      h += '</div>';
    });
    h += '</div></div>';

    // 2. Claims Matrix
    if (D2.claimsMatrix && D2.claimsMatrix.themes && D2.claimsMatrix.rows) {
      var cm = D2.claimsMatrix;
      h += '<div class="mdd-section">';
      h += '<div class="mdd-sec-header"><div class="mdd-sec-title">2. Claims Matrix</div><div class="mdd-sec-sub">Rows = competitors, columns = claim themes. Filled = theme present in title/bullets.</div></div>';
      h += '<div class="mdd-explainer"><b>Heatmap:</b> a filled cell means the competitor explicitly claims that theme in their listing copy. Below the matrix, the bars rank themes by <b>adoption rate</b> across all ' + D2.totalCompetitors + ' competitors. <b>~100% bars</b> = saturated table-stakes (everybody says it). <b>Short bars</b> = whitespace candidates (few competitors are claiming it — see Section 4).</div>';
      h += '<div class="mdd-matrix-wrap"><table class="mdd-matrix">';
      h += '<thead><tr><th class="mdd-row-h">Brand \u00b7 ASIN</th>';
      cm.themes.forEach(function(t) { h += '<th>' + esc(t.label) + '</th>'; });
      h += '</tr></thead><tbody>';
      cm.rows.forEach(function(r) {
        h += '<tr><td class="mdd-row-h">' + esc(r.brand) + '<br><span style="font-weight:400;color:#94a3b8;font-size:.62rem">' + esc(r.asin) + '</span></td>';
        r.cells.forEach(function(cell) {
          h += '<td>' + (cell ? '<span class="mdd-cell-yes"></span>' : '<span class="mdd-cell-no"></span>') + '</td>';
        });
        h += '</tr>';
      });
      h += '</tbody></table></div>';

      // Claims summary bars
      if (D2.claimsSummary) {
        h += '<div style="margin-top:20px"><div class="mdd-sec-sub" style="margin-bottom:8px">Claim frequency across all ' + D2.totalCompetitors + ' listings</div>';
        var sortedClaims = D2.claimsSummary.slice().sort(function(a,b) { return (b.count||0) - (a.count||0); });
        sortedClaims.forEach(function(s) {
          h += '<div class="mdd-bar-row">';
          h += '  <div style="font-weight:600;color:#1e293b">' + esc(s.label) + '</div>';
          h += '  <div class="mdd-bar-track"><div class="mdd-bar-fill" style="width:' + s.pct + '%"></div></div>';
          h += '  <div style="text-align:right;color:#475569"><b>' + s.count + '</b> \u00b7 ' + s.pct + '%</div>';
          h += '</div>';
          h += '<div class="mdd-brands">Top brands: ' + (s.topBrands || []).map(esc).join(' \u00b7 ') + '</div>';
        });
        h += '</div>';
      }
      h += '</div>';
    }

    // 3. VOC ↔ Claims Gap Analysis
    if (D2.vocGap && D2.vocGap.length) {
      h += '<div class="mdd-section">';
      h += '<div class="mdd-sec-header"><div class="mdd-sec-title">3. VOC \u2194 Claims Gap Analysis</div><div class="mdd-sec-sub">Customer concerns from the Reviews tab vs how many of the ' + D2.totalCompetitors + ' competitors address them</div></div>';
      h += '<div class="mdd-explainer">Cross-references the <b>Reviews VOC tab\'s top complaints</b> with what competitors claim in their listings.<br>\u00b7 <b>VOC Topic</b> = a complaint theme from your Reviews analysis. \u00b7 <b>Customer %</b> = share of negative reviews mentioning it. \u00b7 <b>Addressed by</b> = how many of the ' + D2.totalCompetitors + ' competitors make a listing claim that maps to this complaint. \u00b7 <b>Severity</b>: <span class="mdd-sev mdd-sev-high">HIGH</span> = \u226520% concern AND \u22641 competitor addresses \u00b7 <span class="mdd-sev mdd-sev-medium">MED</span> = \u226510% AND \u22642 \u00b7 <span class="mdd-sev mdd-sev-low">LOW</span> = otherwise. \u00b7 <b>Whitespace</b> = <code>true</code> when zero competitors address it (the strongest signal).<br><b>How to act:</b> hunt for HIGH/MED rows or any row with high % + low addressed-by \u2014 those are listing differentiation plays.</div>';
      h += '<table class="mdd-gap"><thead><tr>';
      h += '<th>VOC Topic</th><th>Customer %</th><th>Addressed by</th><th>Severity</th><th>Whitespace</th>';
      h += '</tr></thead><tbody>';
      D2.vocGap.forEach(function(g) {
        h += '<tr>';
        h += '<td><b>' + esc(g.vocTopic) + '</b></td>';
        h += '<td><b>' + esc(g.customerConcernPct) + '</b></td>';
        h += '<td><b>' + g.addressedByCount + ' / ' + D2.totalCompetitors + '</b><br><span style="font-size:.66rem;color:#64748b">' + (g.addressedByBrands || []).map(esc).join(', ') + '</span></td>';
        h += '<td><span class="mdd-sev mdd-sev-' + g.gapSeverity + '">' + g.gapSeverity + '</span></td>';
        h += '<td>' + esc(g.whitespace) + '</td>';
        h += '</tr>';
      });
      h += '</tbody></table></div>';
    }

    // 4. Whitespace + Saturation
    if (D2.whitespaceOpportunities && D2.whitespaceOpportunities.length) {
      h += '<div class="mdd-section">';
      h += '<div class="mdd-sec-header"><div class="mdd-sec-title">4. Whitespace Opportunities</div><div class="mdd-sec-sub">High customer demand \u00d7 low competitor coverage</div></div>';
      h += '<div class="mdd-explainer">Themes claimed by <b>\u226425% of competitors</b> \u2014 empty marketing real estate. Picking one of these and leading with it in your hero bullet or A+ content gives you a claim that buyers don\'t see elsewhere on the search results page. The brands listed under each card are the only ones currently making the claim.</div>';
      h += '<div class="mdd-ws-grid">';
      D2.whitespaceOpportunities.forEach(function(w) {
        h += '<div class="mdd-ws-card">';
        h += '  <h4>' + esc(w.opportunity) + '</h4>';
        h += '  <div class="mdd-ws-rationale">' + esc(w.rationale) + '</div>';
        h += '  <div class="mdd-ws-evidence">' + esc(w.evidence) + '</div>';
        h += '</div>';
      });
      h += '</div></div>';
    }
    if (D2.saturation && D2.saturation.length) {
      h += '<div class="mdd-section">';
      h += '<div class="mdd-sec-header"><div class="mdd-sec-title">Saturated Claims \u00b7 Diminishing Returns</div><div class="mdd-sec-sub">Most-used claims where adding the same message no longer differentiates</div></div>';
      h += '<div class="mdd-explainer">Themes claimed by <b>\u226560% of competitors</b> \u2014 table-stakes. You still need to claim them (buyers expect them), but adding them won\'t move the needle. Treat as <b>parity bullets</b>, not hero bullets, and spend your differentiation budget on Whitespace items above.</div>';
      h += '<div class="mdd-ws-grid">';
      D2.saturation.forEach(function(s) {
        h += '<div class="mdd-ws-card">';
        h += '  <h4>' + esc(s.label) + ' <span style="float:right;color:#dc2626;font-size:.78rem">' + s.saturationPct + '</span></h4>';
        h += '  <div class="mdd-ws-rationale">' + esc(s.advice) + '</div>';
        h += '</div>';
      });
      h += '</div></div>';
    }

    // 5. Strategic Recommendations
    if (D2.strategicRecommendations && D2.strategicRecommendations.length) {
      h += '<div class="mdd-section">';
      h += '<div class="mdd-sec-header"><div class="mdd-sec-title">5. Strategic Recommendations</div><div class="mdd-sec-sub">Synthesized findings + actionable implications</div></div>';
      h += '<div class="mdd-explainer">Auto-derived from the highest-severity <b>VOC gaps</b> and biggest <b>whitespace</b> opportunities above. Each card pairs a finding (what the data shows) with an implication (what to do about it in your listing). Use these as a starting point for listing rewrites and A+ content priorities.</div>';
      h += '<div class="mdd-insight-grid">';
      D2.strategicRecommendations.forEach(function(r) {
        h += '<div class="mdd-insight-card">';
        h += '  <span class="mdd-insight-badge" style="background:' + esc(r.badgeBg) + ';color:' + esc(r.badgeColor) + '">' + esc(r.type) + '</span>';
        h += '  <h4>' + esc(r.finding) + '</h4>';
        h += '  <p><b>\u2192</b> ' + esc(r.implication) + '</p>';
        h += '</div>';
      });
      h += '</div></div>';
    }

    // Modal
    h += '<div id="mdd-modal"><div class="mdd-modal-body"><span class="mdd-modal-close">\u00d7</span><div id="mdd-modal-content"></div></div></div>';
    h += '</div>'; // end #mdd-root

    root.innerHTML = h;

    // Card click → modal
    var modal = document.getElementById('mdd-modal');
    var modalContent = document.getElementById('mdd-modal-content');
    root.querySelectorAll('.mdd-comp-card').forEach(function(card) {
      card.addEventListener('click', function() {
        var c = D2.competitors[parseInt(card.dataset.idx, 10)];
        var m = '';
        m += '<div style="font-size:.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px">' + esc(c.brand) + ' \u00b7 ' + esc(c.asin) + '</div>';
        m += '<h2 style="margin:0 0 12px;font-size:1.1rem;color:#0f172a;line-height:1.4">' + esc(c.title) + '</h2>';
        m += '<div style="display:flex;gap:14px;font-size:.78rem;color:#475569;flex-wrap:wrap;margin-bottom:14px">';
        m += '  <span><b>' + mfmt(c.price) + '</b> price</span>';
        m += '  <span>\u2605 <b>' + (c.rating || 0).toFixed(1) + '</b> (' + (c.reviews || 0).toLocaleString() + ' reviews)</span>';
        m += '  <span>BSR <b>' + (c.bsr ? c.bsr.toLocaleString() : '\u00b7') + '</b></span>';
        m += '  <span><b>' + mfmt(c.rev30d) + '</b> 30d revenue</span>';
        m += '</div>';
        m += '<div style="margin-bottom:14px">';
        (c.themes || []).forEach(function(t) { m += '<span class="mdd-theme-pill" style="margin-right:4px">' + esc(String(t).replace(/_/g, ' ')) + '</span>'; });
        m += '</div>';
        if (c.images && c.images.length) {
          m += '<div class="mdd-modal-imgs">';
          c.images.forEach(function(u) { m += '<img src="' + esc(u) + '" alt="">'; });
          m += '</div>';
        }
        m += '<h3 style="font-size:.82rem;color:#0f172a;margin:18px 0 8px">Bullet Points</h3>';
        if (c.bullets && c.bullets.length) {
          m += '<ul class="mdd-bullets">';
          c.bullets.forEach(function(b) { m += '<li>' + esc(b) + '</li>'; });
          m += '</ul>';
        } else {
          m += '<p style="font-size:.74rem;color:#94a3b8">No bullets available</p>';
        }
        if (c.description) {
          m += '<h3 style="font-size:.82rem;color:#0f172a;margin:18px 0 8px">Description</h3>';
          m += '<p style="font-size:.76rem;color:#475569;line-height:1.55;white-space:pre-wrap">' + esc(c.description) + '</p>';
        }
        modalContent.innerHTML = m;
        modal.classList.add('open');
      });
    });
    modal.querySelector('.mdd-modal-close').addEventListener('click', function() { modal.classList.remove('open'); });
    modal.addEventListener('click', function(e) { if (e.target === modal) modal.classList.remove('open'); });
  }

  // ── Placeholder renderer for Phase 1 tabs ─────────────────────────────────
  function renderPlaceholder(tab, country) {
    var h = '<div class="card">';
    h += '  <h2>' + esc(tab.label) + ' \u00b7 ' + esc(country.name) + ' (' + esc(country.code) + ')</h2>';
    h += '  <p style="color:#475569;font-size:.85rem;line-height:1.55">Phase 1 \u00b7 navigation shell. Data presentation for this tab will be built next, using the matching tab in <code>Nitolic \u00b7 US</code> as the visual blueprint.</p>';
    h += '</div>';
    document.getElementById('panel').innerHTML = h;
  }

  // ── Panel dispatcher ──────────────────────────────────────────────────────
  function renderPanel() {
    destroyCharts();
    var tab = D.tabs[state.tab];
    var country = D.countries.filter(function(c){ return c.code === state.country; })[0];
    try {
      // Dispatcher: tab IDs are auto-generated from SEGMENTS in Python
      // (market-structure-{slug}, reviews-{slug}, marketing-deep-dive-{slug}).
      // The segment label needed by renderMarketStructure lives on the tab metadata.
      var tabMeta = D.tabs[state.tab] || {};
      if (state.tab === 'main-segments') renderMainSegments(country);
      else if (state.tab.indexOf('market-structure-') === 0) renderMarketStructure(country, tabMeta.segment);
      else if (state.tab.indexOf('reviews-') === 0) renderReviews(country, state.tab);
      else if (state.tab.indexOf('marketing-deep-dive-') === 0) renderMarketingDeepDive(country, state.tab);
      else renderPlaceholder(tab, country);
      makeAllTablesSortable();
    } catch(e) {
      document.getElementById('panel').innerHTML =
        '<div style="padding:20px;background:#fee2e2;color:#b91c1c;border:2px solid #dc2626;border-radius:6px;font-family:monospace;font-size:.8rem;white-space:pre-wrap">' +
        'RENDER ERROR: ' + (e && e.stack ? e.stack : e) + '</div>';
    }
  }

  renderPanel();
})();
</script>
</body>
</html>
'''

shell = shell.replace('/*<<BUNDLE>>*/', json.dumps(bundle, ensure_ascii=False)).replace('{{TITLE}}', PRODUCT_NAME + ' ' + PRODUCT_TITLE_SUFFIX)
out = os.path.join(BASE, 'index.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(shell)

print(f'index.html: {os.path.getsize(out):,} bytes')
for c in countries:
    d = main_segments_data[c['code']]
    pc = d.get('projectionCounts', {})
    season = d.get('seasonality') or {}
    peak = f"peak={season.get('peakMonth','-')} ({season.get('peakIdx',0):.2f})" if season else 'no-season'
    print(f"  {c['code']}: {d['asinCount']} ASINs \u00b7 {d['totalUnits']:,} units \u00b7 {d['totalRevenue']:,.0f} EUR "
          f"[history={pc.get('history',0)} seasonality={pc.get('seasonality',0)} flat={pc.get('flat',0)}] {peak}")
