"""
Build standalone index.html for the `shampoo-atopic` TOPLINE dashboard.

5 EU markets — DE · UK · FR · IT · ES — single "Irritated / Atopic" shampoo segment.

Unlike the `atopic` topline (parent-level collapse), this reads the ALREADY
claim-segmented, ASIN-deduped per-market files:
    data/x-ray/shampoo-atopic-{CODE}.csv
Each is one row per kept shampoo. We aggregate at ASIN level (sum ASIN Revenue /
ASIN Sales) and filter to Segment == "Irritated / Atopic" (so DE's option-B file
contributes only its 115 atopic rows, matching the option-A markets).

Currency: everything shown in € . UK figures are native £ converted to € at
GBP_TO_EUR (live mid-market rate, see constant). 12M projection = 30d × 12 (flat
topline convention).
"""
import csv, os, re, json

BASE = os.path.dirname(os.path.abspath(__file__))
XDIR = os.path.join(BASE, 'data', 'x-ray')

MULTIPLIER  = 12          # 30d -> 12M flat
SEGMENT     = 'Irritated / Atopic'
GBP_TO_EUR  = 1.16117     # mid-market rate captured 2026-06-30 (edit when refreshing UK)

MARKETS = [
    {'code': 'DE', 'name': 'Germany',        'flag': '🇩🇪', 'color': '#2563eb', 'cur': '€'},
    {'code': 'UK', 'name': 'United Kingdom',  'flag': '🇬🇧', 'color': '#dc2626', 'cur': '£'},
    {'code': 'FR', 'name': 'France',          'flag': '🇫🇷', 'color': '#0891b2', 'cur': '€'},
    {'code': 'IT', 'name': 'Italy',           'flag': '🇮🇹', 'color': '#7c3aed', 'cur': '€'},
    {'code': 'ES', 'name': 'Spain',           'flag': '🇪🇸', 'color': '#d97706', 'cur': '€'},
]
XRAY_LINKS = {'DE': '#', 'UK': '#', 'FR': '#', 'IT': '#', 'ES': '#'}


def numv(v):
    if v is None:
        return 0.0
    s = re.sub(r'[^\d.,-]', '', str(v).strip())
    if not s:
        return 0.0
    try:
        return float(s.replace(',', ''))
    except ValueError:
        return 0.0


def price_col(header):
    for c in header:
        if re.search(r'price', c, re.I):
            return c
    return None


market_data = {}
global_brand = {}      # brand -> {'rev12m','units12m'}

for m in MARKETS:
    code = m['code']
    fx = GBP_TO_EUR if code == 'UK' else 1.0
    path = os.path.join(XDIR, f'shampoo-atopic-{code}.csv')
    with open(path, encoding='utf-8-sig', newline='') as fh:
        rd = csv.DictReader(fh)
        rows = [r for r in rd if (r.get('Segment') or '').strip() == SEGMENT]
        pcol = price_col(rd.fieldnames)

    items, brands = [], {}
    for r in rows:
        units30 = numv(r.get('ASIN Sales'))
        rev30   = numv(r.get('ASIN Revenue')) * fx
        price   = numv(r.get(pcol)) * fx if pcol else 0.0
        brand   = (r.get('Brand') or '').strip() or '(no brand)'
        it = {
            'asin':    (r.get('ASIN') or '').strip(),
            'brand':   brand,
            'title':   (r.get('Product Details') or '').strip(),
            'price':   round(price, 2),
            'rev12m':  round(rev30 * MULTIPLIER),
            'units12m': round(units30 * MULTIPLIER),
            'rating':  numv(r.get('Ratings')),
            'reviews': int(numv(r.get('Review Count'))),
        }
        items.append(it)
        b = brands.setdefault(brand, {'rev12m': 0, 'units12m': 0, 'asins': 0})
        b['rev12m']   += it['rev12m']
        b['units12m'] += it['units12m']
        b['asins']    += 1
        g = global_brand.setdefault(brand, {'rev12m': 0, 'units12m': 0})
        g['rev12m']   += it['rev12m']
        g['units12m'] += it['units12m']

    rev12m   = sum(i['rev12m'] for i in items)
    units12m = sum(i['units12m'] for i in items)
    items.sort(key=lambda i: i['rev12m'], reverse=True)
    market_data[code] = {
        'asins':     len(items),
        'rev12m':    rev12m,
        'units12m':  units12m,
        'brands':    len(brands),
        'avg_price': round(rev12m / units12m, 2) if units12m else 0,
        'items':     items,
        'brand_agg': brands,
    }
    print(f'  [{code}] atopic shampoos {len(items)} | 12M €{rev12m:,} | {units12m:,} units | '
          f'{len(brands)} brands' + (f'  (£→€ ×{GBP_TO_EUR})' if code == 'UK' else ''))

MARKETS.sort(key=lambda m: market_data[m['code']]['rev12m'], reverse=True)

total_rev12m   = sum(market_data[m['code']]['rev12m']   for m in MARKETS)
total_units12m = sum(market_data[m['code']]['units12m'] for m in MARKETS)
total_asins    = sum(market_data[m['code']]['asins']    for m in MARKETS)
total_brands   = len(global_brand)
top_brands     = sorted(global_brand.items(), key=lambda kv: kv[1]['rev12m'], reverse=True)

CODES = '/'.join(m['code'] for m in MARKETS)

payload = {
    'markets': [{
        'code': m['code'], 'name': m['name'], 'flag': m['flag'], 'color': m['color'], 'cur': m['cur'],
        'xray': XRAY_LINKS.get(m['code'], '#'),
        **{k: market_data[m['code']][k] for k in ('asins', 'rev12m', 'units12m', 'brands', 'avg_price')},
        'items': market_data[m['code']]['items'][:20],
        'topBrands': sorted(
            [{'brand': b, **v} for b, v in market_data[m['code']]['brand_agg'].items()],
            key=lambda x: x['rev12m'], reverse=True)[:10],
    } for m in MARKETS],
    'totals': {
        'rev12m': total_rev12m, 'units12m': total_units12m,
        'asins': total_asins, 'brands': total_brands, 'nMarkets': len(MARKETS),
        'codes': ' · '.join(m['code'] for m in MARKETS),
    },
    'topBrands': [{'brand': b, 'rev12m': v['rev12m'], 'units12m': v['units12m']}
                  for b, v in top_brands[:12]],
    'fx': GBP_TO_EUR,
}
DATA_JSON = json.dumps(payload, ensure_ascii=False)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shampoo — Atopic — EU Market Topline (__CODES__)</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#f1f5f9;color:#1e293b;line-height:1.5}
.wrap{max-width:1400px;margin:0 auto;padding:0 20px 60px}
header{background:#0f2942;color:#fff;padding:22px 0;margin-bottom:26px}
header .wrap{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap}
header h1{font-size:1.4rem;font-weight:700}
header .sub{font-size:.82rem;color:#94a3b8;margin-top:4px}
.xray-btns{display:flex;gap:8px;flex-wrap:wrap}
.xray-btns a{background:#16a34a;color:#fff;text-decoration:none;font-size:.72rem;font-weight:600;padding:7px 11px;border-radius:6px;white-space:nowrap}
.xray-btns a:hover{background:#15803d}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:26px}
.kpi{background:#fff;border-radius:10px;padding:18px 16px;box-shadow:0 1px 3px rgba(0,0,0,.07);border-left:4px solid #2563eb}
.kpi .lbl{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;color:#64748b;font-weight:600}
.kpi .val{font-size:1.55rem;font-weight:800;margin-top:6px;color:#0f2942}
.kpi .note{font-size:.68rem;color:#94a3b8;margin-top:3px}
.card{background:#fff;border-radius:10px;padding:22px;box-shadow:0 1px 3px rgba(0,0,0,.07);margin-bottom:22px}
.card h2{font-size:1.05rem;color:#1e293b;margin-bottom:4px}
.card .desc{font-size:.78rem;color:#64748b;margin-bottom:16px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.chart-box{position:relative;height:300px}
.method{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:16px 20px;margin-bottom:22px;font-size:.8rem;color:#1e3a5f}
.method b{color:#0f2942}
.method .pl{color:#475569;font-style:italic;margin-top:8px;display:block;font-size:.76rem}
table{width:100%;border-collapse:collapse;font-size:.78rem}
th,td{padding:8px 10px;border-bottom:1px solid #e2e8f0;text-align:right}
th{background:#f8fafc;font-weight:700;color:#475569;cursor:pointer;white-space:nowrap;position:sticky;top:0}
th.l,td.l{text-align:left}
tbody tr:hover{background:#f8fafc}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:.68rem;font-weight:700;color:#fff}
.pills{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.pill{padding:8px 16px;border-radius:20px;border:1px solid #cbd5e1;background:#fff;font-size:.8rem;font-weight:600;cursor:pointer;color:#475569}
.pill.active{color:#fff;border-color:transparent}
.flag{font-size:1rem;margin-right:5px}
.muted{color:#94a3b8;font-size:.72rem}
.scroll{max-height:560px;overflow:auto;border:1px solid #e2e8f0;border-radius:8px}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div>
      <h1>Shampoo — Atopic — EU Market Topline</h1>
      <div class="sub" id="subline"></div>
    </div>
    <div class="xray-btns" id="xrayBtns"></div>
  </div>
</header>
<div class="wrap">

  <div class="kpis" id="kpis"></div>

  <div class="method">
    <b>How this market is sized — claim-segmented, ASIN-level.</b>
    Each market's Helium 10 X-Ray exports were merged and de-duplicated by ASIN, then every surviving listing's
    <i>title + bullet copy</i> was read (via the Amazon product API) to keep <b>only genuine shampoos</b> whose
    claims address sensitive / dry / irritated / itchy / atopic / eczema / psoriasis / seborrhoeic scalp — the
    <b>Irritated&nbsp;/&nbsp;Atopic</b> segment. Conditioners, masks, serums, 2-in-1s, sets, pet shampoos and purely
    cosmetic shampoos were excluded. Market size = sum of each kept ASIN's revenue, as a 12-month projection
    (30-day snapshot&nbsp;×&nbsp;12). All figures in&nbsp;€; <b>UK £ converted to € at __FX__</b> (mid-market, 2026-06-30).
    <span class="pl">PL: Rynek liczony na poziomie ASIN — tylko szampony (po przeczytaniu tytułu i bulletów przez API), których obietnice dotyczą skóry wrażliwej/atopowej/podrażnionej. Projekcja 12M = snapshot 30 dni × 12. Wszystko w €; UK £→€ po kursie __FX__.</span>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Revenue by Market (12M)</h2>
      <div class="desc">Irritated / Atopic shampoo revenue, 12-month projection (€)</div>
      <div class="chart-box"><canvas id="revBar"></canvas></div>
    </div>
    <div class="card">
      <h2>Market Share by Revenue (12M)</h2>
      <div class="desc">Share of total EU Irritated / Atopic shampoo revenue</div>
      <div class="chart-box"><canvas id="revPie"></canvas></div>
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Units by Market (12M)</h2>
      <div class="desc">Units sold, 12-month projection</div>
      <div class="chart-box"><canvas id="unitsBar"></canvas></div>
    </div>
    <div class="card">
      <h2>Top Brands — EU Pooled (12M Revenue)</h2>
      <div class="desc">All markets combined, top 12 brands (€)</div>
      <div class="chart-box"><canvas id="brandBar"></canvas></div>
    </div>
  </div>

  <div class="card">
    <h2>Market Summary</h2>
    <div class="desc">One row per market — Irritated / Atopic shampoos only</div>
    <table id="summaryTbl"></table>
  </div>

  <div class="card">
    <h2>Top 20 Products per Market</h2>
    <div class="desc">Ranked by 12M revenue (€). Click a country to switch.</div>
    <div class="pills" id="prodPills"></div>
    <div class="scroll"><table id="prodTbl"></table></div>
  </div>

</div>

<script>
const D = __DATA__;
const fmtM = v => '€' + Math.round(v).toLocaleString('en-US');
const fmtI = v => Math.round(v).toLocaleString('en-US');
const esc = s => (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const cmap = {}; D.markets.forEach(m=>cmap[m.code]=m.color);

document.getElementById('subline').innerHTML =
  D.markets.map(m=>m.flag+' '+m.name).join(' · ')
  + ' &nbsp;|&nbsp; Source: Helium 10 X-Ray (30d × 12 = 12M) &nbsp;|&nbsp; Claim-segmented · ASIN-level · UK £→€ '+D.fx;

document.getElementById('xrayBtns').innerHTML = D.markets.map(m=>
  `<a href="${m.xray}" target="_blank">${m.flag} ${m.code} X-Ray</a>`).join('');

const kpis = [
  {lbl:'Total Market (12M)', val:fmtM(D.totals.rev12m), note:'Irritated / Atopic shampoos, €'},
  {lbl:'Units (12M)', val:fmtI(D.totals.units12m), note:'projected'},
  {lbl:'Products (ASINs)', val:fmtI(D.totals.asins), note:'segmented shampoos'},
  {lbl:'Markets', val:D.totals.nMarkets, note:D.totals.codes},
  {lbl:'Brands', val:D.totals.brands, note:'across all markets'},
];
document.getElementById('kpis').innerHTML = kpis.map(k=>
  `<div class="kpi"><div class="lbl">${k.lbl}</div><div class="val">${k.val}</div><div class="note">${k.note}</div></div>`).join('');

const st = document.getElementById('summaryTbl');
st.innerHTML = '<thead><tr><th class="l">Market</th><th>12M Revenue</th><th>Share</th><th>12M Units</th><th>Products</th><th>Brands</th><th>Avg Price</th></tr></thead><tbody>'
  + D.markets.map(m=>`<tr>
      <td class="l"><span class="flag">${m.flag}</span>${esc(m.name)}${m.cur==='£'?' <span class="muted">(£→€)</span>':''}</td>
      <td>${fmtM(m.rev12m)}</td>
      <td>${(m.rev12m/D.totals.rev12m*100).toFixed(1)}%</td>
      <td>${fmtI(m.units12m)}</td>
      <td>${m.asins}</td>
      <td>${m.brands}</td>
      <td>€${m.avg_price.toFixed(2)}</td>
    </tr>`).join('')
  + `<tr style="font-weight:800;background:#f1f5f9"><td class="l">Total</td><td>${fmtM(D.totals.rev12m)}</td><td>100%</td><td>${fmtI(D.totals.units12m)}</td><td>${D.totals.asins}</td><td>${D.totals.brands}</td><td>—</td></tr></tbody>`;

Chart.register(ChartDataLabels);

new Chart(revBar,{type:'bar',data:{labels:D.markets.map(m=>m.code),
  datasets:[{data:D.markets.map(m=>m.rev12m),backgroundColor:D.markets.map(m=>m.color)}]},
  options:{plugins:{legend:{display:false},datalabels:{anchor:'end',align:'top',formatter:fmtM,font:{weight:700,size:10}}},
  scales:{y:{ticks:{callback:v=>'€'+(v/1e6).toFixed(1)+'M'}}}}});

new Chart(revPie,{type:'doughnut',data:{labels:D.markets.map(m=>m.name),
  datasets:[{data:D.markets.map(m=>m.rev12m),backgroundColor:D.markets.map(m=>m.color)}]},
  options:{plugins:{legend:{position:'right'},datalabels:{color:'#fff',font:{weight:700,size:11},
    formatter:(v)=>(v/D.totals.rev12m*100).toFixed(0)+'%'}}}});

new Chart(unitsBar,{type:'bar',data:{labels:D.markets.map(m=>m.code),
  datasets:[{data:D.markets.map(m=>m.units12m),backgroundColor:D.markets.map(m=>m.color)}]},
  options:{plugins:{legend:{display:false},datalabels:{anchor:'end',align:'top',formatter:fmtI,font:{weight:700,size:10}}},
  scales:{y:{ticks:{callback:v=>(v/1e3).toFixed(0)+'k'}}}}});

new Chart(brandBar,{type:'bar',data:{labels:D.topBrands.map(b=>b.brand),
  datasets:[{data:D.topBrands.map(b=>b.rev12m),backgroundColor:'#2563eb'}]},
  options:{indexAxis:'y',plugins:{legend:{display:false},datalabels:{anchor:'end',align:'right',formatter:fmtM,font:{weight:700,size:9},clamp:true}},
  scales:{x:{ticks:{callback:v=>'€'+(v/1e6).toFixed(1)+'M'}}}}});

const pills = document.getElementById('prodPills');
pills.innerHTML = D.markets.map((m,i)=>
  `<button class="pill${i===0?' active':''}" data-c="${m.code}" style="${i===0?`background:${m.color}`:''}">${m.flag} ${m.name}</button>`).join('');

function renderProducts(code){
  const m = D.markets.find(x=>x.code===code);
  const t = document.getElementById('prodTbl');
  t.innerHTML = '<thead><tr><th class="l">#</th><th class="l">Brand</th><th class="l">Product</th><th>Price</th><th>12M Revenue</th><th>12M Units</th><th>Rating</th><th>Reviews</th></tr></thead><tbody>'
    + m.items.map((f,i)=>`<tr>
        <td class="l">${i+1}</td>
        <td class="l"><span class="badge" style="background:${m.color}">${esc(f.brand)}</span></td>
        <td class="l" title="${esc(f.title)}">${esc(f.title.slice(0,70))}${f.title.length>70?'…':''}</td>
        <td>€${f.price.toFixed(2)}</td>
        <td>${fmtM(f.rev12m)}</td>
        <td>${fmtI(f.units12m)}</td>
        <td>${f.rating?f.rating.toFixed(1):'—'}</td>
        <td>${fmtI(f.reviews)}</td>
      </tr>`).join('') + '</tbody>';
}
pills.addEventListener('click',e=>{
  const b=e.target.closest('.pill'); if(!b)return;
  pills.querySelectorAll('.pill').forEach(p=>{p.classList.remove('active');p.style.background='';});
  b.classList.add('active'); b.style.background=cmap[b.dataset.c];
  renderProducts(b.dataset.c);
});
renderProducts(D.markets[0].code);
</script>
</body>
</html>"""

out = (HTML.replace('__DATA__', DATA_JSON)
           .replace('__CODES__', CODES)
           .replace('__FX__', str(GBP_TO_EUR)))
with open(os.path.join(BASE, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(out)

print('\n=== TOTALS ===')
print(f'  Total 12M: €{total_rev12m:,} | {total_units12m:,} units | '
      f'{total_asins} shampoos | {total_brands} brands | {len(MARKETS)} markets')
print(f'  Order: {CODES}')
print(f'  Wrote index.html ({len(out):,} bytes)')
