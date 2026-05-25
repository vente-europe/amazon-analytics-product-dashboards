"""Build a single-tab standalone dashboard for Fruit Flies (US) using u-main-segments.

Data lives locally in this folder's `data/` and `reviews/` subfolders.
Re-run after any X-Ray / sales-data refresh.
"""
import pandas as pd, json, os, statistics, glob
from datetime import timedelta
from collections import defaultdict

# === Source data (local) ===
# Current X-Ray = May 2026 multi-keyword merge (210 ASINs from 3 H10 exports:
# `plug in fly trap`, `flying insect trap`, `fruit fly trap`). 31 ASINs are
# still unsegmented and get skipped at read time. See data-snapshot-feb-vs-may-2026.md
# for the Feb→May rotation analysis (~67% turnover, 68 ASINs persist).
XRAY = 'data/x-ray/merged-may-segmented.csv'
SALES_DIR = 'data/sales-data'

# === Display config ===
EXPORT_MONTH = 4        # May (0-based) — early build-up into summer peak
EXPORT_DATE_ISO = '2026-05-24'
WINDOW_START_ISO = '2026-04-24'
CURRENCY = '$'
COUNTRY_NAME = 'United States'
COUNTRY_CODE = 'US'
TITLE = 'Fruit Flies (US)'

# === Segment normalization ===
SEGMENT_MAP = {
    'electric traps': 'Electric Traps',
    'sticky traps':   'Sticky Traps',
    'sticky trap':    'Sticky Traps',
    'lure':           'Lure',
    'passive attractor': 'Passive Attractor',
}
SEGMENT_ORDER = ['Lure', 'Sticky Traps', 'Passive Attractor', 'Electric Traps']
SEGMENT_COLORS = {
    'Lure':              '#16a34a',
    'Sticky Traps':      '#f59e0b',
    'Passive Attractor': '#8b5cf6',
    'Electric Traps':    '#dc2626',
}
BRAND_PALETTE = ['#2563eb','#dc2626','#16a34a','#f59e0b','#8b5cf6','#0891b2','#db2777','#65a30d']

# === Helpers ===
def norm_segment(v):
    if pd.isna(v) or str(v).strip() == '': return None
    return SEGMENT_MAP.get(str(v).strip().lower())

def numv(v):
    if pd.isna(v): return 0
    s = str(v).replace(',','').replace('$','').replace('€','').strip()
    try: return float(s)
    except: return 0

def load_sales_12m(asin):
    p = os.path.join(SALES_DIR, f'{asin}-sales-3y.csv')
    if not os.path.exists(p): return None
    try:
        s = pd.read_csv(p); s['Time'] = pd.to_datetime(s['Time'])
        cutoff = s['Time'].max() - timedelta(days=365)
        return float(s[s['Time'] >= cutoff]['Sales'].sum())
    except Exception: return None

def load_sales_monthly(asin):
    p = os.path.join(SALES_DIR, f'{asin}-sales-3y.csv')
    if not os.path.exists(p): return None
    try:
        s = pd.read_csv(p); s['Time'] = pd.to_datetime(s['Time'])
        cutoff = s['Time'].max() - timedelta(days=365)
        s = s[s['Time'] >= cutoff].copy()
        s['month'] = s['Time'].dt.month - 1
        return s.groupby('month')['Sales'].sum().to_dict(), s['Time'].min(), s['Time'].max()
    except Exception: return None

# === Load X-Ray (utf-8-sig strips BOM so first col resolves as "Product Details") ===
df = pd.read_csv(XRAY, encoding='utf-8-sig')
def find(names):
    for n in names:
        for c in df.columns:
            if c.strip().lower() == n.lower(): return c
    return None

asin_col   = find(['ASIN'])
title_col  = find(['Product Details'])
brand_col  = find(['Brand'])
type_col   = find(['Type','Segment'])
price_col  = next((c for c in df.columns if 'price' in c.lower()), None)
sales_col  = find(['ASIN Sales'])
rev_col    = find(['ASIN Revenue'])
review_col = find(['Review Count'])

# === Trailing-12M units from sales CSVs ===
sales_data = {}
for _, row in df.iterrows():
    u = load_sales_12m(row[asin_col])
    if u is not None: sales_data[row[asin_col]] = u

# === Median multiplier (12M ÷ Feb-30d) for ASINs without sales history ===
ratios = []
for asin, u12 in sales_data.items():
    row = df[df[asin_col]==asin].iloc[0]
    u30 = numv(row[sales_col])
    if u30 > 0: ratios.append(u12 / u30)
mult = statistics.median(ratios) if ratios else 12.0

# === Per-month seasonality curve (built from sales history) ===
monthly_totals = [0.0]*12
asins_with_history = 0
min_date = max_date = None
for asin in sales_data:
    r = load_sales_monthly(asin)
    if not r: continue
    mdict, dmin, dmax = r
    asins_with_history += 1
    for m, u in mdict.items(): monthly_totals[int(m)] += float(u)
    if min_date is None or dmin < min_date: min_date = dmin
    if max_date is None or dmax > max_date: max_date = dmax

avg_month = sum(monthly_totals)/12 if sum(monthly_totals) > 0 else 1.0
season_indices = [t/avg_month for t in monthly_totals]
MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
ordered_indices, ordered_labels = [], []
for i in range(12):
    idx = (EXPORT_MONTH + i) % 12
    ordered_indices.append(season_indices[idx])
    ordered_labels.append(MONTHS[idx])

peak_val = max(season_indices); peak_m = season_indices.index(peak_val)
trough_val = min(season_indices); trough_m = season_indices.index(trough_val)

# === Build products ===
products = []
for _, row in df.iterrows():
    asin = row[asin_col]
    seg = norm_segment(row[type_col])
    if not seg: continue
    price = numv(row[price_col])
    s30 = numv(row[sales_col]); r30 = numv(row[rev_col])
    if s30 == 0 and r30 > 0 and price > 0: s30 = round(r30 / price)
    u12 = sales_data.get(asin, round(s30 * mult))
    brand = (str(row[brand_col]).strip() if pd.notna(row[brand_col]) else '') or 'Unknown'
    products.append({
        'asin': asin,
        'title': str(row[title_col])[:300] if pd.notna(row[title_col]) else '',
        'segment': seg,
        'brand': brand,
        'price': round(price, 2),
        'units12m': round(u12),
        'revenue12m': round(u12 * price),
        'reviews': int(numv(row[review_col])),
    })

# === Per-segment aggregation ===
segments_data = []          # Tab 1 (Total Market) — just per-segment totals
market_structure = {}       # Tab 2 (Segments Market Structure) — full per-segment detail
TOP_N_PIE = 8

for seg in SEGMENT_ORDER:
    seg_products = [p for p in products if p['segment'] == seg]
    seg_units = sum(p['units12m'] for p in seg_products)
    seg_rev   = sum(p['revenue12m'] for p in seg_products)

    # Brand aggregation
    bagg = defaultdict(lambda: {'units': 0, 'revenue': 0, 'asins': 0})
    for p in seg_products:
        b = bagg[p['brand']]
        b['units']   += p['units12m']
        b['revenue'] += p['revenue12m']
        b['asins']   += 1
    brand_list = [{'brand': k, 'units': v['units'], 'revenue': v['revenue'], 'asins': v['asins']}
                  for k, v in bagg.items()]
    brand_by_rev = sorted(brand_list, key=lambda x: -x['revenue'])

    # Top-N + Other rollup for the pie data
    top = brand_by_rev[:TOP_N_PIE]
    rest = brand_by_rev[TOP_N_PIE:]
    if rest:
        other = {
            'brand':   f'Other ({len(rest)})',
            'units':   sum(b['units'] for b in rest),
            'revenue': sum(b['revenue'] for b in rest),
        }
        by_units = sorted(top, key=lambda x: -x['units']) + [other]
        by_rev   = top + [other]
    else:
        by_units = sorted(top, key=lambda x: -x['units'])
        by_rev   = top

    # Tab 1 needs only the per-segment summary numbers
    segments_data.append({'name': seg, 'units': seg_units, 'revenue': seg_rev})

    # Tab 2 needs full brand list (with share + ASIN count) for the Brand Summary table
    ms_brands = [{
        'brand': b['brand'], 'units': b['units'], 'revenue': b['revenue'],
        'share': round((b['revenue'] / seg_rev * 100) if seg_rev > 0 else 0, 1),
        'asins': b['asins'],
    } for b in brand_by_rev]

    # HHI = sum of (brand share %)^2  ·  <1500 fragmented · 1500-2500 moderate · >2500 highly concentrated
    hhi = round(sum(b['share'] ** 2 for b in ms_brands))

    # Top-1/3/5/10 ASIN revenue concentration (already as %)
    sorted_asins = sorted(seg_products, key=lambda p: -p['revenue12m'])
    asin_revs = [p['revenue12m'] for p in sorted_asins]
    def _share(n):
        if seg_rev <= 0 or not asin_revs: return 0.0
        return round(sum(asin_revs[:n]) / seg_rev * 100, 1)
    top_asin_shares = [_share(1), _share(3), _share(5), _share(10)]

    top_brand = ({'name': ms_brands[0]['brand'], 'share': ms_brands[0]['share']}
                 if ms_brands else {'name': '', 'share': 0.0})

    market_structure[seg] = {
        'asinCount':       len(seg_products),
        'totalRevenue':    seg_rev,
        'hhi':             hhi,
        'topAsinShares':   top_asin_shares,
        'topBrand':        top_brand,
        'brands':          ms_brands,
        'brandsByUnits':   [{'brand': b['brand'], 'units': b['units'],   'revenue': b.get('revenue', 0)} for b in by_units],
        'brandsByRevenue': [{'brand': b['brand'], 'units': b.get('units', 0), 'revenue': b['revenue']} for b in by_rev],
        'topAsins': [{
            'asin': p['asin'], 'brand': p['brand'], 'title': p['title'],
            'units': p['units12m'], 'revenue': p['revenue12m'],
            'reviews': p['reviews'], 'price': p['price'],
        } for p in sorted_asins[:20]],
    }

total_units = sum(p['units12m'] for p in products)
total_rev   = sum(p['revenue12m'] for p in products)
xray_window_index = 12.0 / mult if mult > 0 else 1.0

# === Per-tab _TAB_DATA payloads ===
total_market_data = {
    'countryName':     COUNTRY_NAME,
    'countryCode':     COUNTRY_CODE,
    'currency':        CURRENCY,
    'segments':        SEGMENT_ORDER,
    'segmentColors':   SEGMENT_COLORS,
    'brandPalette':    BRAND_PALETTE,
    'totalUnits':      total_units,
    'totalRevenue':    total_rev,
    'segments_data':   segments_data,
    'seasonality': {
        'asinCount':   asins_with_history,
        'startDate':   str(min_date.date()) if min_date else None,
        'endDate':     str(max_date.date()) if max_date else None,
        'monthLabels': ordered_labels,
        'months':      [round(v, 3) for v in ordered_indices],
        'peakMonth':   MONTHS[peak_m],   'peakIdx':   round(peak_val, 3),
        'troughMonth': MONTHS[trough_m], 'troughIdx': round(trough_val, 3),
    },
    'projectionCounts': {
        'history':     asins_with_history,
        'seasonality': len(products) - asins_with_history,
        'flat':        0,
    },
    'xrayExportDate':  EXPORT_DATE_ISO,
    'xrayWindowStart': WINDOW_START_ISO,
    'xrayWindowIndex': round(xray_window_index, 3),
}

segments_market_structure_data = {
    'countryName':     COUNTRY_NAME,
    'countryCode':     COUNTRY_CODE,
    'currency':        CURRENCY,
    'segments':        SEGMENT_ORDER,
    'segmentColors':   SEGMENT_COLORS,
    'brandPalette':    BRAND_PALETTE,
    'marketStructure': market_structure,
}

# === Reviews VOC payload (Lure + Electric Traps only) ====================
# Sources:
#  - reviews/dataset_amazon-reviews-scraper_*.json  → list[dict] with productAsin/ratingScore/
#                                                     reviewTitle/reviewDescription/date/reviewUrl
#    The two `_12-43-51-069*.json` files are exact duplicates of each other → dedup by (asin, reviewUrl).
#  - reviews/terro_reviews.json, hs_reviews.json, terro_merged.json, all_reviews.csv → SKIPPED.
#    They either lack ASIN (terro/hs JSONs are pre-aggregated review dumps with only stars/review
#    fields) or contain only one ASIN (all_reviews.csv = 450 reviews for B0BX4GQF68, already
#    covered by the scraper JSONs). Including them would double-count or break the per-ASIN→segment
#    mapping. Future enhancement: re-scrape terro/hs by ASIN to fold them into the per-ASIN dataset.
REVIEWS_DIR = 'reviews'
VOC_SEGMENTS = ['Lure', 'Electric Traps']
REVIEWS_CAP = 200
TOP_BRANDS_CAP = 8

# Build asin → segment map: May X-Ray first (Segment col), Feb X-Ray fallback (Type col).
asin_seg_map = {}
asin_brand_map = {}
for _, r in df.iterrows():
    s = norm_segment(r.get(type_col))
    if s: asin_seg_map[r[asin_col]] = s
    if pd.notna(r.get(brand_col)):
        bval = str(r[brand_col]).strip()
        if bval: asin_brand_map[r[asin_col]] = bval

try:
    feb_df = pd.read_csv('data/x-ray/Fruit-Flies-US-new-merged-data.csv', encoding='utf-8-sig')
    feb_asin = next((c for c in feb_df.columns if c.strip().lower() == 'asin'), None)
    feb_type = next((c for c in feb_df.columns if c.strip().lower() == 'type'), None)
    feb_brand = next((c for c in feb_df.columns if c.strip().lower() == 'brand'), None)
    for _, r in feb_df.iterrows():
        a = r.get(feb_asin)
        if a is None or pd.isna(a): continue
        if a not in asin_seg_map and feb_type:
            s = norm_segment(r.get(feb_type))
            if s: asin_seg_map[a] = s
        if a not in asin_brand_map and feb_brand and pd.notna(r.get(feb_brand)):
            bval = str(r[feb_brand]).strip()
            if bval: asin_brand_map[a] = bval
except FileNotFoundError:
    pass

# Load & dedup scraper JSONs
seen = set()
raw_reviews = []
for path in sorted(glob.glob(os.path.join(REVIEWS_DIR, 'dataset_amazon-reviews-scraper_*.json'))):
    try:
        with open(path, encoding='utf-8') as fh:
            arr = json.load(fh)
    except Exception:
        continue
    if not isinstance(arr, list): continue
    for r in arr:
        a = r.get('productAsin')
        if not a: continue
        url = r.get('reviewUrl') or ''
        key = (a, url) if url else (a, r.get('reviewTitle','') + '|' + str(r.get('date','')))
        if key in seen: continue
        seen.add(key)
        seg = asin_seg_map.get(a)
        if seg not in VOC_SEGMENTS: continue
        rating = r.get('ratingScore')
        try: rating = int(rating)
        except: rating = None
        if rating is None or rating < 1 or rating > 5: continue
        raw_reviews.append({
            'asin':   a,
            'segment': seg,
            'brand':  asin_brand_map.get(a, 'Unknown'),
            'rating': rating,
            'date':   (r.get('date') or '')[:10],
            'title':  r.get('reviewTitle') or '',
            'body':   r.get('reviewDescription') or '',
        })

# Build per-segment payload
reviews_by_segment = {}
voc_summary = {}
for seg in VOC_SEGMENTS:
    bucket = [r for r in raw_reviews if r['segment'] == seg]
    total = len(bucket)
    if total == 0:
        reviews_by_segment[seg] = {
            'totalReviews': 0, 'avgRating': 0.0,
            'starDist': [0,0,0,0,0], 'topBrands': [], 'reviews': [],
        }
        voc_summary[seg] = {'reviews': 0, 'asins': 0}
        continue

    star_dist = [0,0,0,0,0]
    for r in bucket: star_dist[r['rating'] - 1] += 1
    avg_rating = sum(r['rating'] for r in bucket) / total

    # Per-brand aggregation
    brand_agg = defaultdict(lambda: {'reviews': 0, 'rating_sum': 0, 'asins': set()})
    for r in bucket:
        b = brand_agg[r['brand']]
        b['reviews']    += 1
        b['rating_sum'] += r['rating']
        b['asins'].add(r['asin'])
    brand_list = [{
        'brand':     b,
        'reviews':   v['reviews'],
        'share':     round(v['reviews'] / total * 100, 1),
        'avgRating': round(v['rating_sum'] / v['reviews'], 2),
        'asins':     len(v['asins']),
    } for b, v in brand_agg.items()]
    brand_list.sort(key=lambda x: (-x['reviews'], -x['avgRating']))
    top_brands = brand_list[:TOP_BRANDS_CAP]

    # Reviews sample: newest first, capped at REVIEWS_CAP
    bucket_sorted = sorted(bucket, key=lambda r: (r['date'] or ''), reverse=True)
    sample = bucket_sorted[:REVIEWS_CAP]
    reviews_payload = [{
        'rating': r['rating'],
        'date':   r['date'],
        'brand':  r['brand'],
        'asin':   r['asin'],
        'title':  r['title'],
        'body':   r['body'],
    } for r in sample]

    reviews_by_segment[seg] = {
        'totalReviews': total,
        'avgRating':    round(avg_rating, 2),
        'starDist':     star_dist,
        'topBrands':    top_brands,
        'reviews':      reviews_payload,
    }
    voc_summary[seg] = {
        'reviews': total,
        'asins':   len({r['asin'] for r in bucket}),
    }

# NOTE: the per-segment raw-review aggregation above (reviews_by_segment) is kept for
# future use but is NOT what the VOC tabs currently render. The active VOC tabs use the
# pre-built per-segment AI VOC payloads in voc-lure.json and voc-electric.json (generated
# by `_assemble_voc.py`, which combines per-segment review samples + Gemini-structured
# analysis + theme-tagging). That gives genuinely different content per segment instead
# of duplicating the whole-category aggregate from dashboard.json.
with open('voc-lure.json',     encoding='utf-8') as f: reviews_voc_lure_data     = json.load(f)
with open('voc-electric.json', encoding='utf-8') as f: reviews_voc_electric_data = json.load(f)

# === Marketing Deep-Dive payloads (top-10 per segment by 12M revenue, theme-tagged from title) ===
# Generated by _build_mdd.py — re-run that script if X-Ray or VOC data changes.
with open('data/mdd/mdd-lure.json',     encoding='utf-8') as f: mdd_lure_data     = json.load(f)
with open('data/mdd/mdd-electric.json', encoding='utf-8') as f: mdd_electric_data = json.load(f)

# === Read shared CSS + all four tab templates ===
# The u-reviews-voc template uses 'urv'-prefixed IDs internally. Because both Lure and
# Electric tabs inject this same template into separate panels, we'd end up with duplicate
# IDs in the DOM (causing document.getElementById to always hit the first match and
# breaking the second tab). Fix: per-tab prefix rewrite — Lure gets 'urvL' IDs, Electric
# gets 'urvE' IDs. All 22 urv-tokens in the template are identifiers (verified), so a
# bare string replace is safe.
with open('../../css/hub.css', encoding='utf-8') as f: hub_css = f.read()
with open('../../templates/tabs/u-main-segments/template.html', encoding='utf-8') as f: tab1_html = f.read()
with open('../../templates/tabs/u-segments-market-structure/template.html', encoding='utf-8') as f: tab2_html = f.read()
with open('../../templates/tabs/u-reviews-voc/template.html', encoding='utf-8') as f: _voc_template_raw = f.read()
tab3_html = _voc_template_raw.replace('urv', 'urvL')  # Lure tab
tab4_html = _voc_template_raw.replace('urv', 'urvE')  # Electric tab

# u-marketing-deep-dive uses the 'mdd-' prefix for both DOM IDs (#mdd-root,
# #u-mdd-modal, #u-mdd-tab-root) AND for CSS classes (.mdd-section, .mdd-comp-card,
# etc.). Substring-replacing 'mdd-' → 'mddL-' / 'mddE-' renames them all together,
# keeping each instance fully isolated from the other tab.
with open('../../templates/tabs/u-marketing-deep-dive/template.html', encoding='utf-8') as f: _mdd_template_raw = f.read()
tab5_html = _mdd_template_raw.replace('mdd-', 'mddL-')  # Lure MDD
tab6_html = _mdd_template_raw.replace('mdd-', 'mddE-')  # Electric MDD

# === 2-tab shell with tab bar + per-tab data routing ===
shell = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<style>
/*<<HUBCSS>>*/
body { display: block; min-height: auto; margin: 0; background:#f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color:#1e293b; }
.dashboard-header { background:#0f2942; color:#fff; padding:18px 28px; display:flex; justify-content:space-between; align-items:center; gap:24px; }
.dashboard-body { width:100%; max-width:1600px; margin:0 auto; padding:24px 32px; }
.insight { background:#f8fafc; border-left:4px solid #2563eb; color:#475569; padding:12px 16px; border-radius:6px; margin:14px 0; font-size:.85rem; line-height:1.5; }
.note { font-size:.72rem; color:#94a3b8; margin-top:6px; line-height:1.45; }
.cw { position:relative; }
.g2 { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
/* Top tab bar */
.tabs { display:flex; background:#fff; border-bottom:2px solid #e2e8f0; gap:2px; position:sticky; top:0; z-index:40; margin-bottom:14px; padding:0 4px; }
.tabs .tab { padding:12px 22px; cursor:pointer; font-size:.85rem; font-weight:600; color:#64748b; border:0; background:transparent; border-bottom:3px solid transparent; margin-bottom:-2px; white-space:nowrap; }
.tabs .tab:hover { color:#1e3a5f; }
.tabs .tab.active { color:#1e3a5f; border-bottom-color:#2563eb; }
.panel { display:none; }
.panel.active { display:block; }
</style>
</head>
<body>
<div class="dashboard-header">
  <div style="flex:1;min-width:0">
    <h2 id="hdrTitle" style="margin:0;font-size:1.35rem;font-weight:600;color:#fff"></h2>
    <span id="hdrSub" style="font-size:.78rem;color:#cbd5e1;display:block;margin-top:4px"></span>
  </div>
</div>
<div class="dashboard-body">
  <div class="tabs" id="tabBar"></div>
  <div id="dt-total-market" class="panel active"></div>
  <div id="dt-segments-market-structure" class="panel"></div>
  <div id="dt-reviews-voc-lure" class="panel"></div>
  <div id="dt-reviews-voc-electric" class="panel"></div>
  <div id="dt-mdd-lure" class="panel"></div>
  <div id="dt-mdd-electric" class="panel"></div>
</div>
<script>
window.__BUNDLE_DATA__ = /*<<BUNDLE>>*/;
</script>
<template id="tpl-total-market">/*<<TAB1>>*/</template>
<template id="tpl-segments-market-structure">/*<<TAB2>>*/</template>
<template id="tpl-reviews-voc-lure">/*<<TAB3>>*/</template>
<template id="tpl-reviews-voc-electric">/*<<TAB4>>*/</template>
<template id="tpl-mdd-lure">/*<<TAB5>>*/</template>
<template id="tpl-mdd-electric">/*<<TAB6>>*/</template>
<script>
(function bootstrap() {
  var B = window.__BUNDLE_DATA__;
  document.getElementById('hdrTitle').textContent = B.title;
  document.getElementById('hdrSub').textContent = B.subtitle;
  var tabs = Object.keys(B.tabs).map(function(id, i) {
    return { id: id, label: (i + 1) + ' · ' + B.tabs[id].label };
  });
  var bar = document.getElementById('tabBar');
  bar.innerHTML = tabs.map(function(t, i) {
    return '<button class="tab' + (i === 0 ? ' active' : '') + '" data-tab="' + t.id + '">' + t.label + '</button>';
  }).join('');
  var loaded = {};
  function loadTab(id) {
    window._TAB_DATA = B.tabs[id].data;
    if (loaded[id]) return;
    var panel = document.getElementById('dt-' + id);
    var tpl = document.getElementById('tpl-' + id);
    panel.innerHTML = tpl.innerHTML;
    panel.querySelectorAll('script').forEach(function(oldScript) {
      var s = document.createElement('script');
      s.textContent = oldScript.textContent;
      oldScript.parentNode.replaceChild(s, oldScript);
    });
    loaded[id] = true;
  }
  function showTab(id) {
    document.querySelectorAll('.tabs .tab').forEach(function(t) { t.classList.toggle('active', t.dataset.tab === id); });
    document.querySelectorAll('.panel').forEach(function(p) { p.classList.toggle('active', p.id === 'dt-' + id); });
    loadTab(id);
    if (window.Chart) Object.values(Chart.instances).forEach(function(c) { c.resize(); });
  }
  bar.querySelectorAll('.tab').forEach(function(btn) {
    btn.addEventListener('click', function() { showTab(btn.dataset.tab); });
  });
  showTab(tabs[0].id);
})();
</script>
</body>
</html>
'''

_export_year = EXPORT_DATE_ISO.split('-')[0]
subtitle = (f'Data: Helium 10 X-Ray (amazon.com, 30-day snapshot, {MONTHS[EXPORT_MONTH]} {_export_year}, exported {EXPORT_DATE_ISO}) '
            f'· {asins_with_history}/{len(products)} ASINs with sales history '
            f'· 12M projection via x{mult:.2f} median multiplier')

bundle = {
    'title':    TITLE,
    'subtitle': subtitle,
    'tabs': {
        'total-market':              {'label': 'Total Market',              'data': total_market_data},
        'segments-market-structure': {'label': 'Segments Market Structure', 'data': segments_market_structure_data},
        'reviews-voc-lure':          {'label': 'Reviews VOC · Lure',        'data': reviews_voc_lure_data},
        'reviews-voc-electric':      {'label': 'Reviews VOC · Electric',    'data': reviews_voc_electric_data},
        'mdd-lure':                  {'label': 'Marketing Deep-Dive · Lure',     'data': mdd_lure_data},
        'mdd-electric':              {'label': 'Marketing Deep-Dive · Electric', 'data': mdd_electric_data},
    },
}

shell = shell.replace('/*<<HUBCSS>>*/', hub_css)
shell = shell.replace('__TITLE__', TITLE)
shell = shell.replace('/*<<BUNDLE>>*/', json.dumps(bundle, ensure_ascii=False))
shell = shell.replace('/*<<TAB1>>*/', tab1_html)
shell = shell.replace('/*<<TAB2>>*/', tab2_html)
shell = shell.replace('/*<<TAB4>>*/', tab4_html)
shell = shell.replace('/*<<TAB3>>*/', tab3_html)
shell = shell.replace('/*<<TAB5>>*/', tab5_html)
shell = shell.replace('/*<<TAB6>>*/', tab6_html)

with open('index.html', 'w', encoding='utf-8') as f: f.write(shell)

print(f'index.html: {os.path.getsize("index.html"):,} bytes')
print(f'Products: {len(products)}  Sales history: {asins_with_history}  Multiplier: x{mult:.2f}')
print(f'xrayWindowIndex: {xray_window_index:.3f}  (peak {MONTHS[peak_m]}={peak_val:.2f}, trough {MONTHS[trough_m]}={trough_val:.2f})')
for seg in SEGMENT_ORDER:
    sd = next((s for s in segments_data if s['name'] == seg), None)
    if sd: print(f'  {seg:20s}: {sd["units"]:>10,} units · ${sd["revenue"]:>13,}')
print(f'  {"TOTAL":20s}: {total_units:>10,} units · ${total_rev:>13,}')

print()
print(f'Reviews VOC (after dedup, segment-filtered to {", ".join(VOC_SEGMENTS)}):')
total_voc = sum(v['reviews'] for v in voc_summary.values())
for seg in VOC_SEGMENTS:
    v = voc_summary.get(seg, {'reviews': 0, 'asins': 0})
    avg = reviews_by_segment[seg].get('avgRating', 0.0)
    print(f'  {seg:20s}: {v["reviews"]:>5,} reviews · {v["asins"]:>2} ASINs · avg {avg:.2f} stars')
print(f'  {"TOTAL VOC":20s}: {total_voc:>5,} reviews')
