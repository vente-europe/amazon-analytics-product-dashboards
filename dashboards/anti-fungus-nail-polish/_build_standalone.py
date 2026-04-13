import json, pandas as pd, os, statistics
from datetime import timedelta

XRAY = 'data/x-ray/Anti-Fungus-Nail-Polish-X-Ray.csv'
SALES_DIR = 'data/sales-data'
df = pd.read_csv(XRAY, encoding='utf-8')

def find(names):
    for n in names:
        for c in df.columns:
            if c.strip().lower() == n.lower(): return c
    return None
asin_col=find(['ASIN']); title_col=find(['Product Details']); brand_col=find(['Brand'])
type_col=find(['Type','Segment','Focus']); price_col=next((c for c in df.columns if 'price' in c.lower()), None)
sales_col=find(['ASIN Sales']); rev_col=find(['ASIN Revenue']); bsr_col=find(['BSR'])
rating_col=find(['Ratings']); review_col=find(['Review Count'])

def numv(v):
    if pd.isna(v): return 0
    s = str(v).replace(',','').replace('€','').replace('$','').strip()
    try: return float(s)
    except: return 0

def load_sales_12m(asin):
    path = os.path.join(SALES_DIR, f'{asin}-sales-3y.csv')
    if not os.path.exists(path): return None
    try:
        s = pd.read_csv(path); s['Time'] = pd.to_datetime(s['Time'])
        cutoff = s['Time'].max() - timedelta(days=365)
        return float(s[s['Time'] >= cutoff]['Sales'].sum())
    except: return None

def load_sales_monthly(asin):
    """Return list of {month: 0-11, units: total} for the trailing 12 months."""
    path = os.path.join(SALES_DIR, f'{asin}-sales-3y.csv')
    if not os.path.exists(path): return None
    try:
        s = pd.read_csv(path); s['Time'] = pd.to_datetime(s['Time'])
        cutoff = s['Time'].max() - timedelta(days=365)
        s = s[s['Time'] >= cutoff].copy()
        s['month'] = s['Time'].dt.month - 1
        return s.groupby('month')['Sales'].sum().to_dict()
    except: return None

def calc_seasonality(asins, export_month):
    monthly = [0.0]*12
    month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    for asin in asins:
        m = load_sales_monthly(asin)
        if not m: continue
        for mo, u in m.items():
            monthly[int(mo)] += float(u)
    avg = sum(monthly)/12
    if avg == 0: return None
    indices = [t/avg for t in monthly]
    ordered_indices = []
    ordered_months = []
    ordered_totals = []
    for i in range(12):
        idx = (export_month + i) % 12
        ordered_indices.append(indices[idx])
        ordered_months.append(month_names[idx])
        ordered_totals.append(monthly[idx])
    return {
        'indices': indices,
        'orderedIndices': ordered_indices,
        'orderedMonths': ordered_months,
        'orderedTotals': ordered_totals,
        'avgMonth': avg,
    }

sales_data = {}
for _, row in df.iterrows():
    u = load_sales_12m(row[asin_col])
    if u is not None: sales_data[row[asin_col]] = u

seasonality = calc_seasonality(list(sales_data.keys()), 3)  # exportMonth=3 (April)

ratios = []
for asin, u12 in sales_data.items():
    row = df[df[asin_col]==asin].iloc[0]
    u30 = numv(row[sales_col])
    if u30 > 0: ratios.append(u12/u30)
mult = statistics.median(ratios) if ratios else 12

products = []
for _, row in df.iterrows():
    asin = row[asin_col]
    price = numv(row[price_col]); sales30d = numv(row[sales_col]); rev30d = numv(row[rev_col])
    if sales30d == 0 and rev30d > 0 and price > 0: sales30d = round(rev30d/price)
    units12m = sales_data.get(asin, round(sales30d * mult))
    products.append({
        'asin': asin,
        'title': str(row[title_col])[:300] if pd.notna(row[title_col]) else '',
        'type': str(row[type_col]) if pd.notna(row[type_col]) else 'Other',
        'brand': str(row[brand_col]) if pd.notna(row[brand_col]) else 'Unknown',
        'marketplace': 'DE',
        'price': round(price,2), 'sales30d': round(sales30d), 'revenue30d': round(rev30d),
        'bsr': int(numv(row[bsr_col])), 'rating': round(numv(row[rating_col]),1),
        'reviewCount': int(numv(row[review_col])), 'focus': '',
        'units12m': round(units12m), 'revenue12m': round(units12m * price),
    })

with open('dashboard.json',encoding='utf-8') as f: dash = json.load(f)
reviews = dash['baseTabs']['reviews']
mdd = dash['addonTabs']['marketing-deep-dive']

bundle = {
    'title': 'Anti-Fungus Nail Polish — Market Analysis',
    'subtitle': f'Data: Helium 10 X-Ray (amazon.de, 30-day snapshot, 2026-04-08) · {len(sales_data)}/{len(products)} ASINs with sales history · 12M projected via x{mult:.2f} median multiplier',
    'currency': '€', 'exportMonth': 3,
    'salesFilesFound': len(sales_data),
    'salesFilesMissing': len(products) - len(sales_data),
    'products': products, 'reviews': reviews, 'mdd': mdd,
    'seasonality': seasonality,
}

with open('../../css/hub.css',encoding='utf-8') as f: css = f.read()
with open('../../js/data-engine.js',encoding='utf-8') as f: engine = f.read()
with open('../../templates/tabs/total-market/template.html',encoding='utf-8') as f: tab1 = f.read()
with open('../../templates/tabs/market-structure/template.html',encoding='utf-8') as f: tab2 = f.read()
with open('../../templates/tabs/reviews/template.html',encoding='utf-8') as f: tab3 = f.read()
with open('../../templates/tabs/marketing-deep-dive/template.html',encoding='utf-8') as f: tab4 = f.read()

css_override = '''
/* Standalone overrides — undo hub flex layout, expand to full width */
body { display: block !important; min-height: auto !important; }
.dashboard-header { width: 100% !important; }
.dashboard-body { width: 100% !important; max-width: none !important; margin: 0 !important; padding: 24px 32px !important; }
.insight { background: #f8fafc !important; border-left: none !important; color: #475569 !important; padding: 12px 16px; border-radius: 6px; }
'''

shell = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Anti-Fungus Nail Polish — Market Analysis</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<style>
/*<<CSS>>*/
/*<<OVERRIDE>>*/
</style>
</head>
<body>
<div class="dashboard-header" style="background:#0f2942;color:#fff;padding:18px 28px;display:flex;justify-content:space-between;align-items:center;gap:24px">
  <div style="flex:1;min-width:0">
    <h2 id="hdrTitle" style="margin:0;font-size:1.35rem;font-weight:600;color:#fff"></h2>
    <span id="hdrSub" style="font-size:.78rem;color:#cbd5e1;display:block;margin-top:4px"></span>
  </div>
  <a href="https://docs.google.com/spreadsheets/d/1QxFPXmRscsLhsVi9nop3WLEzkjriJx1Ks5UAdBjbjJY/edit?gid=1702510194#gid=1702510194" target="_blank" rel="noopener" style="background:#16a34a;color:#fff;padding:10px 16px;border-radius:6px;font-size:.82rem;font-weight:600;text-decoration:none;white-space:nowrap;display:inline-flex;align-items:center;gap:8px;box-shadow:0 1px 3px rgba(0,0,0,.2);transition:background .15s">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>
    Edit X-Ray data
  </a>
</div>
<div class="dashboard-body" style="max-width:1600px;margin:0 auto;padding:24px">
  <div class="tabs" id="tabBar"></div>
  <div id="dt-total-market" class="panel active"></div>
  <div id="dt-market-structure" class="panel"></div>
  <div id="dt-reviews" class="panel"></div>
  <div id="dt-marketing-deep-dive" class="panel"></div>
</div>
<script>
/*<<ENGINE>>*/
</script>
<script>
window.__BUNDLE_DATA__ = /*<<BUNDLE>>*/;
</script>
<template id="tpl-total-market">/*<<TAB1>>*/</template>
<template id="tpl-market-structure">/*<<TAB2>>*/</template>
<template id="tpl-reviews">/*<<TAB3>>*/</template>
<template id="tpl-marketing-deep-dive">/*<<TAB4>>*/</template>
<script>
(function bootstrap() {
  var B = window.__BUNDLE_DATA__;
  var segments = DataEngine.aggregateSegments(B.products);
  segments = DataEngine.assignSegmentColors(segments);
  var totals = DataEngine.computeTotals(segments);
  var brandsBySegment = {};
  segments.forEach(function(seg) {
    var brands = DataEngine.aggregateByBrand(seg.products);
    brandsBySegment[seg.name] = DataEngine.topBrandsWithOther(brands, 8);
  });
  window._DASH_DATA = {
    title: B.title, subtitle: B.subtitle, currency: B.currency,
    baseTabs: { reviews: B.reviews },
    addonTabs: { 'marketing-deep-dive': B.mdd },
    _computed: {
      products: B.products, segments: segments, totals: totals,
      brandsBySegment: brandsBySegment, seasonality: B.seasonality,
      salesFilesFound: B.salesFilesFound, salesFilesMissing: B.salesFilesMissing,
      exportMonth: B.exportMonth, currency: B.currency,
    }
  };
  document.getElementById('hdrTitle').textContent = B.title;
  document.getElementById('hdrSub').textContent = B.subtitle;
  var tabs = [
    { id: 'total-market', label: '1 \u2014 Total Market' },
    { id: 'market-structure', label: '2 \u2014 Market Structure' },
    { id: 'reviews', label: '3 \u2014 Reviews VOC' },
    { id: 'marketing-deep-dive', label: '4 \u2014 Marketing Deep-Dive' },
  ];
  var bar = document.getElementById('tabBar');
  bar.innerHTML = tabs.map(function(t, i) {
    return '<button class="tab' + (i === 0 ? ' active' : '') + '" data-tab="' + t.id + '">' + t.label + '</button>';
  }).join('');
  var loaded = {};
  function loadTab(id) {
    if (loaded[id]) return;
    var panel = document.getElementById('dt-' + id);
    var tpl = document.getElementById('tpl-' + id);
    panel.innerHTML = tpl.innerHTML;
    if (id === 'reviews') window._TAB_DATA = window._DASH_DATA.baseTabs.reviews;
    else if (id === 'marketing-deep-dive') window._TAB_DATA = window._DASH_DATA.addonTabs['marketing-deep-dive'];
    else window._TAB_DATA = null;
    panel.querySelectorAll('script').forEach(function(oldScript) {
      var s = document.createElement('script');
      s.textContent = oldScript.textContent;
      oldScript.parentNode.replaceChild(s, oldScript);
    });
    loaded[id] = true;
  }
  function showTab(id) {
    document.querySelectorAll('.tab').forEach(function(t) { t.classList.toggle('active', t.dataset.tab === id); });
    document.querySelectorAll('.panel').forEach(function(p) { p.classList.toggle('active', p.id === 'dt-' + id); });
    loadTab(id);
    if (window.Chart) Object.values(Chart.instances).forEach(function(c) { c.resize(); });
  }
  bar.querySelectorAll('.tab').forEach(function(btn) {
    btn.addEventListener('click', function() { showTab(btn.dataset.tab); });
  });
  showTab('total-market');
})();
</script>
</body>
</html>
'''

shell = shell.replace('/*<<CSS>>*/', css)
shell = shell.replace('/*<<OVERRIDE>>*/', css_override)
shell = shell.replace('/*<<ENGINE>>*/', engine)
shell = shell.replace('/*<<BUNDLE>>*/', json.dumps(bundle, ensure_ascii=False))
shell = shell.replace('/*<<TAB1>>*/', tab1)
shell = shell.replace('/*<<TAB2>>*/', tab2)
shell = shell.replace('/*<<TAB3>>*/', tab3)
shell = shell.replace('/*<<TAB4>>*/', tab4)

with open('index.html','w',encoding='utf-8') as f: f.write(shell)
print(f'index.html: {os.path.getsize("index.html"):,} bytes')
print(f'Tabs: 4, MDD competitors: {len(mdd["competitors"])}')
