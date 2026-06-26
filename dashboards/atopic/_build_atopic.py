"""
Build standalone index.html for the `atopic` topline dashboard (DE/FR/IT/ES).

VERY top-level market view across the 4 EU atopic-skincare markets. Built on
PARENT-LEVEL revenue (the Miłosz Console method), NOT ASIN-level — because the
X-Ray exports show only a subset of each family's variants. See CLAUDE.md.

Pipeline (per market):
  1. Read the 2 keyword exports for the market from data/x-ray/raw/ (market
     detected from the amazon.<tld> domain in the URL column, not the filename).
  2. Dedup by ASIN — keep the row with the higher `ASIN Revenue`.
  3. Write the merged, deduped file to data/x-ray/atopic-{CODE}.csv with an empty
     `Segment` column inserted as the 3rd column (for Tom to fill in tomorrow).
     NOTE: no ASIN is dropped here — family dedup happens only at aggregation time.
  4. Collapse variant families to ONE value: group surviving rows by
     (brand, Parent Level Sales, Parent Level Revenue). All children of a family
     carry identical parent numbers, so the family total is counted ONCE. This is
     how two rows with the same parent revenue (often the same product surfaced by
     both keywords, or sibling variants) are de-duplicated to a single value.

12M projection = 30d × 12 (flat; topline convention). All 4 markets are Eurozone,
so everything stays in € — no currency conversion.
"""
import csv, os, re, glob, json, html

BASE = os.path.dirname(os.path.abspath(__file__))
RAW  = os.path.join(BASE, 'data', 'x-ray', 'raw')
XDIR = os.path.join(BASE, 'data', 'x-ray')

MULTIPLIER = 12  # 30d -> 12M flat

MARKETS = [
    {'code': 'DE', 'name': 'Germany', 'flag': '🇩🇪', 'color': '#2563eb'},
    {'code': 'FR', 'name': 'France',  'flag': '🇫🇷', 'color': '#0891b2'},
    {'code': 'IT', 'name': 'Italy',   'flag': '🇮🇹', 'color': '#7c3aed'},
    {'code': 'ES', 'name': 'Spain',   'flag': '🇪🇸', 'color': '#d97706'},
]

# Edit X-Ray Google Sheet links per market (placeholder '#' until sheets exist)
XRAY_LINKS = {'DE': '#', 'FR': '#', 'IT': '#', 'ES': '#'}

TLD2CODE = {'de': 'DE', 'fr': 'FR', 'it': 'IT', 'es': 'ES'}


def numv(v):
    """Parse a Helium 10 number (comma = thousands sep, dot = decimal)."""
    if v is None:
        return 0.0
    s = re.sub(r'[^\d.,-]', '', str(v).strip())
    if not s:
        return 0.0
    try:
        return float(s.replace(',', ''))
    except ValueError:
        return 0.0


def market_of(rows):
    """Detect market code from the amazon.<tld> domain in the URL column."""
    for r in rows[:8]:
        m = re.search(r'amazon\.([a-z]+)', r.get('URL') or '')
        if m and m.group(1) in TLD2CODE:
            return TLD2CODE[m.group(1)]
    return None


def load_raw_by_market():
    by_mkt = {m['code']: [] for m in MARKETS}
    fieldnames = None
    for path in sorted(glob.glob(os.path.join(RAW, '*.csv'))):
        with open(path, encoding='utf-8-sig', newline='') as fh:
            rd = csv.DictReader(fh)
            fieldnames = rd.fieldnames
            rows = list(rd)
        code = market_of(rows)
        if code is None:
            print(f'  ! skip (unknown market): {os.path.basename(path)}')
            continue
        by_mkt[code] += rows
        print(f'  + {os.path.basename(path):42s} -> {code} ({len(rows)} rows)')
    return by_mkt, fieldnames


def dedup_by_asin(rows):
    """Keep the row with the higher ASIN Revenue per ASIN (cross-keyword dedup)."""
    best = {}
    for r in rows:
        a = (r.get('ASIN') or '').strip()
        if not a:
            continue
        if a not in best or numv(r.get('ASIN Revenue')) > numv(best[a].get('ASIN Revenue')):
            best[a] = r
    return list(best.values())


def write_merged_csv(code, rows, fieldnames):
    """Write merged per-market CSV with an empty `Segment` column as 3rd column."""
    # Insert empty `Segment` column directly AFTER ASIN (convention:
    # Product Details, ASIN, Segment, ...). Idempotent.
    out_fields = [c for c in fieldnames if c != 'Segment']
    ai = out_fields.index('ASIN')
    out_fields.insert(ai + 1, 'Segment')
    path = os.path.join(XDIR, f'atopic-{code}.csv')
    with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=out_fields, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            r = dict(r)
            r.setdefault('Segment', '')
            w.writerow(r)
    return path


def collapse_parent_level(rows):
    """Group by (brand, Parent Level Sales, Parent Level Revenue) -> one family,
    counted once. Returns list of family dicts with 30d revenue/units from the
    parent total, representative = child with the highest ASIN Sales."""
    groups = {}
    for r in rows:
        brand = (r.get('Brand') or '').strip() or '(no brand)'
        pls = round(numv(r.get('Parent Level Sales')), 2)
        plr = round(numv(r.get('Parent Level Revenue')), 2)
        groups.setdefault((brand.lower(), pls, plr), []).append((brand, r))
    fams = []
    for (blow, pls, plr), kids in groups.items():
        # representative = highest ASIN Sales
        brand, rep = max(kids, key=lambda br: numv(br[1].get('ASIN Sales')))
        price = round(plr / pls, 2) if pls > 0 else numv(rep.get('Price  €'))
        fams.append({
            'asin':   (rep.get('ASIN') or '').strip(),
            'brand':  brand,
            'title':  (rep.get('Product Details') or '').strip(),
            'price':  price,
            'units30d': pls,
            'rev30d':   plr,
            'rating':   numv(rep.get('Ratings')),
            'reviews':  int(numv(rep.get('Review Count'))),
            'bsr':      int(numv(rep.get('BSR'))),
            'variants': len(kids),
        })
    return fams


# ── Build per-market aggregates ─────────────────────────────────────────────
print('Reading raw exports...')
by_mkt, fieldnames = load_raw_by_market()

market_data = {}
global_brand = {}  # brand -> {'rev12m','units12m'}
for m in MARKETS:
    code = m['code']
    raw = by_mkt[code]
    asin_rows = dedup_by_asin(raw)
    merged_path = write_merged_csv(code, asin_rows, fieldnames)
    fams = collapse_parent_level(asin_rows)
    rev30 = sum(f['rev30d'] for f in fams)
    units30 = sum(f['units30d'] for f in fams)
    brands = {}
    for f in fams:
        b = brands.setdefault(f['brand'], {'rev12m': 0, 'units12m': 0, 'families': 0})
        b['rev12m']   += round(f['rev30d'] * MULTIPLIER)
        b['units12m'] += round(f['units30d'] * MULTIPLIER)
        b['families'] += 1
        g = global_brand.setdefault(f['brand'], {'rev12m': 0, 'units12m': 0})
        g['rev12m']   += round(f['rev30d'] * MULTIPLIER)
        g['units12m'] += round(f['units30d'] * MULTIPLIER)
    fams_sorted = sorted(fams, key=lambda f: f['rev30d'], reverse=True)
    market_data[code] = {
        'raw_rows':  len(raw),
        'asin_rows': len(asin_rows),
        'families':  len(fams),
        'rev12m':    round(rev30 * MULTIPLIER),
        'units12m':  round(units30 * MULTIPLIER),
        'brands':    len(brands),
        'avg_price': round(rev30 / units30, 2) if units30 else 0,
        'fams':      fams_sorted,
        'brand_agg': brands,
    }
    print(f'  [{code}] raw={len(raw)} -> ASIN-dedup={len(asin_rows)} -> families={len(fams)} '
          f'| 12M €{round(rev30*MULTIPLIER):,} | {len(brands)} brands | merged -> {os.path.basename(merged_path)}')

# Sort markets by 12M revenue (largest first) for consistent ordering
MARKETS.sort(key=lambda m: market_data[m['code']]['rev12m'], reverse=True)

total_rev12m   = sum(market_data[m['code']]['rev12m']   for m in MARKETS)
total_units12m = sum(market_data[m['code']]['units12m'] for m in MARKETS)
total_fams     = sum(market_data[m['code']]['families'] for m in MARKETS)
total_brands   = len(global_brand)

# Top brands across all markets (revenue)
top_brands = sorted(global_brand.items(), key=lambda kv: kv[1]['rev12m'], reverse=True)


def fmt_money(v):
    return '€' + format(round(v), ',')


def fmt_int(v):
    return format(round(v), ',')


# ── Build JSON payload for the front-end ────────────────────────────────────
payload = {
    'markets': [{
        'code': m['code'], 'name': m['name'], 'flag': m['flag'], 'color': m['color'],
        'xray': XRAY_LINKS.get(m['code'], '#'),
        **{k: market_data[m['code']][k] for k in
           ('raw_rows', 'asin_rows', 'families', 'rev12m', 'units12m', 'brands', 'avg_price')},
        'fams': [{
            'asin': f['asin'], 'brand': f['brand'], 'title': f['title'],
            'price': f['price'], 'rev12m': round(f['rev30d'] * MULTIPLIER),
            'units12m': round(f['units30d'] * MULTIPLIER), 'rating': f['rating'],
            'reviews': f['reviews'], 'variants': f['variants'],
        } for f in market_data[m['code']]['fams'][:20]],
        'topBrands': sorted(
            [{'brand': b, **v} for b, v in market_data[m['code']]['brand_agg'].items()],
            key=lambda x: x['rev12m'], reverse=True)[:10],
    } for m in MARKETS],
    'totals': {
        'rev12m': total_rev12m, 'units12m': total_units12m,
        'families': total_fams, 'brands': total_brands, 'nMarkets': len(MARKETS),
    },
    'topBrands': [{'brand': b, 'rev12m': v['rev12m'], 'units12m': v['units12m']}
                  for b, v in top_brands[:12]],
}

DATA_JSON = json.dumps(payload, ensure_ascii=False)

# ── HTML ────────────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Atopic Skincare — EU Market Topline (DE · FR · IT · ES)</title>
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
      <h1>Atopic Skincare — EU Market Topline</h1>
      <div class="sub">Germany · France · Italy · Spain &nbsp;|&nbsp; Source: Helium 10 X-Ray (30d snapshot × 12 = 12M projection) &nbsp;|&nbsp; Parent-level revenue, de-duplicated</div>
    </div>
    <div class="xray-btns" id="xrayBtns"></div>
  </div>
</header>
<div class="wrap">

  <div class="kpis" id="kpis"></div>

  <div class="method">
    <b>How the market size is counted — parent-level, de-duplicated.</b>
    Each market pools two keyword exports; exact-duplicate ASINs are merged (keeping the higher-revenue row).
    Amazon repeats the <i>same family sales estimate</i> on every colour/size variant, and each export shows only a
    subset of a family's variants — so summing ASINs both double-counts and undercounts. Instead, every variant family
    is counted <b>once</b> at its <b>Parent Level Revenue</b> (rows sharing the same brand + parent sales + parent
    revenue are collapsed to a single value). Figures are 12-month projections (30-day snapshot × 12). All four markets
    are Eurozone, shown in €. <i>Not yet segmented</i> — every product is treated as one "atopic" pool for now.
    <span class="pl">PL: Wielkość rynku liczona na poziomie rodziny (Parent Level Revenue) — każda rodzina wariantów liczona raz, duplikaty z dwóch fraz scalone. Projekcja 12M = snapshot 30 dni × 12. Segmentacja w kolejnym kroku.</span>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Revenue by Market (12M)</h2>
      <div class="desc">Parent-level revenue, 12-month projection</div>
      <div class="chart-box"><canvas id="revBar"></canvas></div>
    </div>
    <div class="card">
      <h2>Market Share by Revenue (12M)</h2>
      <div class="desc">Share of total EU atopic revenue</div>
      <div class="chart-box"><canvas id="revPie"></canvas></div>
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Units by Market (12M)</h2>
      <div class="desc">Parent-level units sold, 12-month projection</div>
      <div class="chart-box"><canvas id="unitsBar"></canvas></div>
    </div>
    <div class="card">
      <h2>Top Brands — EU Pooled (12M Revenue)</h2>
      <div class="desc">All 4 markets combined, top 12 brands</div>
      <div class="chart-box"><canvas id="brandBar"></canvas></div>
    </div>
  </div>

  <div class="card">
    <h2>Market Summary</h2>
    <div class="desc">One row per market — families counted at parent level</div>
    <table id="summaryTbl"></table>
  </div>

  <div class="card">
    <h2>Top 20 Products per Market</h2>
    <div class="desc">Ranked by parent-level 12M revenue. "Variants" = variant children visible in the export for that family.</div>
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

// Edit X-Ray buttons
document.getElementById('xrayBtns').innerHTML = D.markets.map(m=>
  `<a href="${m.xray}" target="_blank">${m.flag} ${m.code} X-Ray</a>`).join('');

// KPIs
const kpis = [
  {lbl:'Total Market (12M)', val:fmtM(D.totals.rev12m), note:'parent-level revenue'},
  {lbl:'Units (12M)', val:fmtI(D.totals.units12m), note:'projected'},
  {lbl:'Product Families', val:fmtI(D.totals.families), note:'parents (de-duplicated)'},
  {lbl:'Markets', val:D.totals.nMarkets, note:'DE · FR · IT · ES'},
  {lbl:'Brands', val:D.totals.brands, note:'across all markets'},
];
document.getElementById('kpis').innerHTML = kpis.map(k=>
  `<div class="kpi"><div class="lbl">${k.lbl}</div><div class="val">${k.val}</div><div class="note">${k.note}</div></div>`).join('');

// Summary table
const st = document.getElementById('summaryTbl');
st.innerHTML = '<thead><tr><th class="l">Market</th><th>12M Revenue</th><th>Share</th><th>12M Units</th><th>Families</th><th>ASINs</th><th>Brands</th><th>Avg Price</th></tr></thead><tbody>'
  + D.markets.map(m=>`<tr>
      <td class="l"><span class="flag">${m.flag}</span>${esc(m.name)}</td>
      <td>${fmtM(m.rev12m)}</td>
      <td>${(m.rev12m/D.totals.rev12m*100).toFixed(1)}%</td>
      <td>${fmtI(m.units12m)}</td>
      <td>${m.families}</td>
      <td>${m.asin_rows}</td>
      <td>${m.brands}</td>
      <td>€${m.avg_price.toFixed(2)}</td>
    </tr>`).join('')
  + `<tr style="font-weight:800;background:#f1f5f9"><td class="l">Total</td><td>${fmtM(D.totals.rev12m)}</td><td>100%</td><td>${fmtI(D.totals.units12m)}</td><td>${D.totals.families}</td><td>${D.markets.reduce((s,m)=>s+m.asin_rows,0)}</td><td>${D.totals.brands}</td><td>—</td></tr></tbody>`;

Chart.register(ChartDataLabels);
const noDL = {datalabels:{display:false}};

// Revenue bar
new Chart(revBar,{type:'bar',data:{labels:D.markets.map(m=>m.code),
  datasets:[{data:D.markets.map(m=>m.rev12m),backgroundColor:D.markets.map(m=>m.color)}]},
  options:{plugins:{legend:{display:false},datalabels:{anchor:'end',align:'top',formatter:fmtM,font:{weight:700,size:10}}},
  scales:{y:{ticks:{callback:v=>'€'+(v/1e6).toFixed(1)+'M'}}}}});

// Revenue pie
new Chart(revPie,{type:'doughnut',data:{labels:D.markets.map(m=>m.name),
  datasets:[{data:D.markets.map(m=>m.rev12m),backgroundColor:D.markets.map(m=>m.color)}]},
  options:{plugins:{legend:{position:'right'},datalabels:{color:'#fff',font:{weight:700,size:11},
    formatter:(v)=>(v/D.totals.rev12m*100).toFixed(0)+'%'}}}});

// Units bar
new Chart(unitsBar,{type:'bar',data:{labels:D.markets.map(m=>m.code),
  datasets:[{data:D.markets.map(m=>m.units12m),backgroundColor:D.markets.map(m=>m.color)}]},
  options:{plugins:{legend:{display:false},datalabels:{anchor:'end',align:'top',formatter:fmtI,font:{weight:700,size:10}}},
  scales:{y:{ticks:{callback:v=>(v/1e3).toFixed(0)+'k'}}}}});

// Brand bar
new Chart(brandBar,{type:'bar',data:{labels:D.topBrands.map(b=>b.brand),
  datasets:[{data:D.topBrands.map(b=>b.rev12m),backgroundColor:'#2563eb'}]},
  options:{indexAxis:'y',plugins:{legend:{display:false},datalabels:{anchor:'end',align:'right',formatter:fmtM,font:{weight:700,size:9},clamp:true}},
  scales:{x:{ticks:{callback:v=>'€'+(v/1e6).toFixed(1)+'M'}}}}});

// Product table with market pills
const pills = document.getElementById('prodPills');
pills.innerHTML = D.markets.map((m,i)=>
  `<button class="pill${i===0?' active':''}" data-c="${m.code}" style="${i===0?`background:${m.color}`:''}">${m.flag} ${m.name}</button>`).join('');

function renderProducts(code){
  const m = D.markets.find(x=>x.code===code);
  const t = document.getElementById('prodTbl');
  t.innerHTML = '<thead><tr><th class="l">#</th><th class="l">Brand</th><th class="l">Product</th><th>Price</th><th>12M Revenue</th><th>12M Units</th><th>Variants</th><th>Rating</th><th>Reviews</th></tr></thead><tbody>'
    + m.fams.map((f,i)=>`<tr>
        <td class="l">${i+1}</td>
        <td class="l"><span class="badge" style="background:${m.color}">${esc(f.brand)}</span></td>
        <td class="l" title="${esc(f.title)}">${esc(f.title.slice(0,70))}${f.title.length>70?'…':''}</td>
        <td>€${f.price.toFixed(2)}</td>
        <td>${fmtM(f.rev12m)}</td>
        <td>${fmtI(f.units12m)}</td>
        <td>${f.variants}</td>
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

out = HTML.replace('__DATA__', DATA_JSON)
with open(os.path.join(BASE, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(out)

print('\n=== TOTALS ===')
print(f'  Total market 12M: {fmt_money(total_rev12m)} | {fmt_int(total_units12m)} units | '
      f'{total_fams} families | {total_brands} brands')
print(f'  Wrote index.html ({len(out):,} bytes)')
