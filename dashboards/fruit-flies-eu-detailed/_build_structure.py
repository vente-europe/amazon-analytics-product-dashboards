"""
Builds _structure.html - the "Struktura rynku" (Market Structure) tab fragment
for fruit-flies-eu-detailed. Modelled on the fruit-fly-trap-DE dashboard's
Tab 2 (pack-size x brand analysis), extended to 4 EU markets via country pills
+ an "All EU" pooled view.

Reads the consolidated CSV (with the new `Pack` column = traps per multipack),
applies the SAME German-seasonality 12M multiplier as the Rynek tab
(data/seasonality-de.json, July export -> ~x7.90), computes per-view aggregates
in Python, and emits a self-contained fragment: an embedded STRUCT JSON + a
renderer that (re)draws on country-pill change. Exposes window.__structRender so
the shell can trigger the first render when the tab is opened (charts must draw
while the panel is visible).

Consumed by _build_standalone.py (inlined into the second tab panel).
Polish UI. All money EUR (UK GBP converted upstream in _consolidate.py).
"""
import csv, os, re, sys, json
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE, 'data', 'x-ray', 'fruit-flies-eu-consolidated.csv')

# --- Seasonality multiplier (identical to _build_rynek.py) ------------------
EXPORT_MONTH = 7
_seas = json.load(open(os.path.join(BASE, 'data', 'seasonality-de.json'), encoding='utf-8'))
SEAS_INDEX = {int(k): v for k, v in _seas['index'].items()}
MULT = round(12.0 / SEAS_INDEX[EXPORT_MONTH], 4)
_month_names = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru']

MARKETS = [
    {'code': 'FR', 'name': 'Francja',         'domain': 'fr'},
    {'code': 'IT', 'name': 'Włochy',          'domain': 'it'},
    {'code': 'ES', 'name': 'Hiszpania',       'domain': 'es'},
    {'code': 'UK', 'name': 'Wielka Brytania', 'domain': 'co.uk'},
]
CODES = [m['code'] for m in MARKETS]
DOMAINS = {m['code']: m['domain'] for m in MARKETS}
NAMES = {m['code']: m['name'] for m in MARKETS}

def numv(v):
    if v is None: return 0.0
    s = re.sub(r'[^\d.,-]', '', str(v)).replace(',', '')
    try: return float(s)
    except ValueError: return 0.0

# --- Load products with Pack ------------------------------------------------
prods_by_code = {c: [] for c in CODES}
with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
    r = csv.DictReader(f)
    fields = r.fieldnames or []
    price_col = next((k for k in fields if k and 'price' in k.lower()), None)
    if 'Pack' not in fields:
        raise SystemExit('no Pack column in consolidated CSV - update the Excel first')
    for row in r:
        code = (row.get('Country') or '').strip().upper()
        if code not in prods_by_code:
            continue
        asin = (row.get('ASIN') or '').strip()
        price = numv(row.get(price_col))
        pack = int(numv(row.get('Pack'))) or 1
        if not asin or price <= 0:
            continue
        rev30 = numv(row.get('ASIN Revenue'))
        u30 = round(rev30 / price) if price > 0 else 0
        prods_by_code[code].append({
            'asin': asin,
            'brand': (row.get('Brand') or 'Unknown').strip() or 'Unknown',
            'title': (row.get('Product Details') or '').strip()[:160],
            'pack': pack,
            'price': round(price, 2),
            'eurPerTrap': round(price / pack, 2) if pack else price,
            'units12m': round(u30 * MULT),
            'rev12m': round(rev30 * MULT),
            'reviews': int(numv(row.get('Review Count'))),
            'rating': numv(row.get('Ratings')),
        })

# --- Aggregation per view ---------------------------------------------------
def top_n_other(items, n, key):
    """items: list of (label, dict). Returns labels/values with 'Pozostałe (k)'."""
    s = sorted(items, key=lambda kv: kv[1][key], reverse=True)
    top, rest = s[:n], s[n:]
    labels = [l for l, _ in top]
    values = [round(v[key]) for _, v in top]
    if rest:
        labels.append(f'Pozostałe ({len(rest)})')
        values.append(round(sum(v[key] for _, v in rest)))
    return labels, values

def build_view(prods):
    total_u = sum(p['units12m'] for p in prods) or 1
    total_r = sum(p['rev12m'] for p in prods) or 1
    total_traps = sum(p['units12m'] * p['pack'] for p in prods) or 1

    pk = defaultdict(lambda: {'u': 0, 'r': 0, 'n': 0, 'psum': 0.0, 'traps': 0})
    br = defaultdict(lambda: {'u': 0, 'r': 0, 'n': 0, 'psum': 0.0})
    bp = defaultdict(lambda: {'u': 0, 'r': 0, 'n': 0, 'psum': 0.0})  # (brand,pack)
    for p in prods:
        a = pk[p['pack']]; a['u'] += p['units12m']; a['r'] += p['rev12m']; a['n'] += 1; a['psum'] += p['price']; a['traps'] += p['units12m'] * p['pack']
        b = br[p['brand']]; b['u'] += p['units12m']; b['r'] += p['rev12m']; b['n'] += 1; b['psum'] += p['price']
        c = bp[(p['brand'], p['pack'])]; c['u'] += p['units12m']; c['r'] += p['rev12m']; c['n'] += 1; c['psum'] += p['price']

    # KPIs
    dom_pack = max(pk.items(), key=lambda kv: kv[1]['u']) if pk else (0, {'u': 0})
    multipack_u = sum(v['u'] for k, v in pk.items() if k > 1)
    hhi = sum(((v['u'] / total_u * 100) ** 2) for v in br.values())
    kpis = {
        'nPackFormats': len(pk),
        'domPack': dom_pack[0],
        'domPackShare': round(dom_pack[1]['u'] / total_u * 100, 1),
        'avgEurPerTrap': round(total_r / total_traps, 2),
        'multipackShare': round(multipack_u / total_u * 100, 1),
        'nBrands': len(br),
        'hhi': round(hhi),
        'totalU': total_u, 'totalR': total_r,
    }

    # Pack pies (sorted by units desc)
    pack_units = sorted(([f'{k}-pak', v['u']] for k, v in pk.items()), key=lambda x: x[1], reverse=True)
    pack_rev   = sorted(([f'{k}-pak', v['r']] for k, v in pk.items()), key=lambda x: x[1], reverse=True)

    # Brand pies (top 10 + Other)
    bu_labels, bu_values = top_n_other(list(br.items()), 10, 'u')
    brv_labels, brv_values = top_n_other(list(br.items()), 10, 'r')

    # Brand share within top-3 pack sizes (by units)
    top_packs = [k for k, _ in sorted(pk.items(), key=lambda kv: kv[1]['u'], reverse=True)[:3]]
    top_pack_pies = []
    for tp in top_packs:
        items = [(b, {'u': bp[(b, p)]['u']}) for (b, p) in bp if p == tp]
        lab, val = top_n_other(items, 6, 'u')
        top_pack_pies.append({'pack': tp, 'labels': lab, 'values': val})

    # Price by pack (avg list price + avg EUR/trap), pack asc
    price_by_pack = []
    for k in sorted(pk.keys()):
        v = pk[k]
        price_by_pack.append({
            'pack': k,
            'avgPrice': round(v['psum'] / v['n'], 2) if v['n'] else 0,
            'avgPerTrap': round(v['r'] / v['traps'], 2) if v['traps'] else 0,
        })

    # Scatter: brand x pack bubbles (x=avg price, y=unit share %, r~rev)
    scatter = []
    for (b, p), v in bp.items():
        scatter.append({
            'x': round(v['psum'] / v['n'], 2) if v['n'] else 0,
            'y': round(v['u'] / total_u * 100, 2),
            'rev': round(v['r']),
            'brand': b, 'pack': p,
        })

    # Pack summary table (by rev desc)
    pack_table = []
    for k, v in sorted(pk.items(), key=lambda kv: kv[1]['r'], reverse=True):
        pack_table.append({
            'pack': k, 'n': v['n'],
            'units12m': v['u'], 'rev12m': v['r'],
            'unitShare': round(v['u'] / total_u * 100, 1),
            'revShare': round(v['r'] / total_r * 100, 1),
            'avgPrice': round(v['psum'] / v['n'], 2) if v['n'] else 0,
            'avgPerTrap': round(v['r'] / v['traps'], 2) if v['traps'] else 0,
        })

    # Brand summary table (by rev desc)
    brand_table = []
    for b, v in sorted(br.items(), key=lambda kv: kv[1]['r'], reverse=True):
        brand_table.append({
            'brand': b, 'n': v['n'],
            'units12m': v['u'], 'rev12m': v['r'],
            'unitShare': round(v['u'] / total_u * 100, 1),
            'revShare': round(v['r'] / total_r * 100, 1),
            'avgPrice': round(v['psum'] / v['n'], 2) if v['n'] else 0,
        })

    # Top ASINs (by rev desc, 15)
    top_asins = sorted(prods, key=lambda p: p['rev12m'], reverse=True)[:15]

    return {
        'kpis': kpis,
        'packUnits': pack_units, 'packRev': pack_rev,
        'brandUnits': {'labels': bu_labels, 'values': bu_values},
        'brandRev': {'labels': brv_labels, 'values': brv_values},
        'topPackPies': top_pack_pies,
        'priceByPack': price_by_pack,
        'scatter': scatter,
        'packTable': pack_table,
        'brandTable': brand_table,
        'topAsins': top_asins,
    }

STRUCT = {}
all_prods = []
for c in CODES:
    STRUCT[c] = build_view(prods_by_code[c])
    all_prods.extend([dict(p, _mkt=c) for p in prods_by_code[c]])
STRUCT['ALL'] = build_view(all_prods)

# Attach market code onto ALL-view top ASINs so links resolve; per-country get their own code.
for c in CODES:
    for p in STRUCT[c]['topAsins']:
        p['_mkt'] = c
STRUCT['ALL']['topAsins'] = [dict(p) for p in STRUCT['ALL']['topAsins']]  # already carry _mkt

VIEWS = [['ALL', 'Wszystkie (EU)']] + [[m['code'], f"{m['name']} ({m['code']})"] for m in MARKETS]
SEAS_ARR = [SEAS_INDEX[i] for i in range(1, 13)]

struct_json = json.dumps(STRUCT, ensure_ascii=False)
seas_json = json.dumps({'index': SEAS_ARR, 'names': _month_names, 'exportMonth': EXPORT_MONTH, 'mult': MULT}, ensure_ascii=False)
views_json = json.dumps(VIEWS, ensure_ascii=False)
domains_json = json.dumps(DOMAINS)

FRAG = '''
<div class="ms2-wrap">
  <div class="ms2-pillrow">
    <span class="ms2-pilllabel">Rynek:</span>
    <span id="ms2Pills"></span>
  </div>
  <div id="ms2Root"></div>
</div>
<script>
(function(){
  var STRUCT = ''' + struct_json + ''';
  var SEAS = ''' + seas_json + ''';
  var VIEWS = ''' + views_json + ''';
  var DOMAINS = ''' + domains_json + ''';
  var BRAND_COLORS = ['#2563eb','#dc2626','#0891b2','#d97706','#7c3aed','#16a34a','#db2777','#0284c7','#ca8a04','#059669','#4f46e5','#94a3b8'];
  var PACK_COLORS = {1:'#94a3b8',2:'#2563eb',3:'#0891b2',4:'#16a34a',6:'#d97706',8:'#7c3aed',10:'#db2777',12:'#dc2626'};
  var charts = [];
  function destroyCharts(){ charts.forEach(function(c){ try{c.destroy();}catch(e){} }); charts = []; }
  function packColor(p){ return PACK_COLORS[p] || '#64748b'; }
  function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
  function fmtMoney(v){ v=Math.round(v); if(v>=1e6) return '€'+(v/1e6).toFixed(1)+'M'; if(v>=1e3) return '€'+(v/1e3).toFixed(0)+'K'; return '€'+v; }
  function fmtInt(v){ return Math.round(v).toLocaleString('en-EU'); }

  function doughnut(id, labels, values, colors, fmtVal){
    var el = document.getElementById(id); if(!el) return;
    var total = values.reduce(function(a,b){return a+b;},0) || 1;
    charts.push(new Chart(el, {
      type:'doughnut',
      data:{ labels:labels, datasets:[{ data:values, backgroundColor:colors, borderWidth:2, borderColor:'#fff' }] },
      options:{ responsive:true, maintainAspectRatio:false, cutout:'52%',
        plugins:{
          legend:{ position:'right', labels:{ font:{size:10}, padding:6, boxWidth:10, boxHeight:10,
            generateLabels:function(){ return labels.map(function(l,i){ var pct=(values[i]/total*100).toFixed(1); return { text:l+'  '+pct+'%', fillStyle:colors[i%colors.length], strokeStyle:colors[i%colors.length], lineWidth:0, index:i }; }); } } },
          tooltip:{ callbacks:{ label:function(ctx){ var pct=(ctx.parsed/total*100).toFixed(1); return ' '+fmtVal(ctx.parsed)+' ('+pct+'%)'; } } },
          datalabels:{ display:function(ctx){ return (ctx.dataset.data[ctx.dataIndex]/total)>0.04; }, formatter:function(v){ return (v/total*100).toFixed(0)+'%'; }, color:'#fff', font:{size:10,weight:'700'} }
        } }
    }));
  }

  function packPie(id, arr, fmtVal){
    var labels = arr.map(function(x){return x[0];});
    var values = arr.map(function(x){return x[1];});
    var colors = arr.map(function(x){ return packColor(parseInt(x[0])); });
    doughnut(id, labels, values, colors, fmtVal);
  }

  function render(view){
    destroyCharts();
    var D = STRUCT[view]; var k = D.kpis;
    var root = document.getElementById('ms2Root');
    var conc = k.hhi > 2500 ? 'silnie skoncentrowany' : (k.hhi > 1500 ? 'umiarkowanie skoncentrowany' : 'rozdrobniony');
    var html = '';

    // KPI strip
    html += '<div class="ms2-kpis">'+
      kpi(k.nPackFormats, 'Formaty opakowań') +
      kpi(k.domPack+'-pak', 'Dominujący format ('+k.domPackShare+'% szt.)') +
      kpi('€'+k.avgEurPerTrap.toFixed(2), 'Śr. cena za pułapkę') +
      kpi(k.multipackShare+'%', 'Udział multipack (szt.)') +
      kpi(k.nBrands, 'Marki') +
      kpi(k.hhi.toLocaleString('en-EU'), 'HHI - '+conc) +
    '</div>';

    // Brand pies (units + revenue) - directly under the KPI strip, rest pushed down.
    html += row2(
      card('Udział marek - jednostki (12M)', canvas('msBrandU', 340)),
      card('Udział marek - przychód (12M)', canvas('msBrandR', 340)));

    // Pack pies
    html += row2(
      card('Udział formatów opakowań - sztuki (12M)', canvas('msPackU')),
      card('Udział formatów opakowań - przychód (12M)', canvas('msPackR')));
    // Brand share within top pack sizes
    var pieCards = D.topPackPies.map(function(tp,i){ return card('Marki w formacie '+tp.pack+'-pak (szt.)', canvas('msTP'+i)); }).join('');
    if (pieCards) html += '<div class="ms2-row3">'+pieCards+'</div>';
    // Price by pack
    html += row2(
      card('Cena wg formatu opakowania (śr. cena vs cena/pułapkę)', canvas('msPrice')),
      card('Cena za pułapkę wg formatu (€)', canvas('msPerTrap')));
    // Scatter
    html += card('Cena vs udział w sztukach (bąbel = przychód 12M, kolor = format)', canvas('msScatter', 320));
    // Pack table
    html += card('Pełny rozkład - formaty opakowań', tableWrap('msPackTable'));
    // Brand table
    html += card('Podsumowanie marek (12M)', tableWrap('msBrandTable'));
    // Top ASINs
    html += card('Top 15 ASIN wg przychodu (12M)', tableWrap('msAsinTable'));
    // Seasonality
    html += card('Miesięczny indeks sezonowości (rynek DE, 1.0 = średni miesiąc)', canvas('msSeas', 240) +
      '<div class="ms2-note">Krzywa z rynku niemieckiego (dashboard Fruit Fly Trap DE) - używana jako proxy dla FR/IT/ES/UK. Eksport w lipcu (indeks '+SEAS.index[SEAS.exportMonth-1].toFixed(2)+'), stąd mnożnik 12M = ×'+SEAS.mult.toFixed(2)+'.</div>');

    root.innerHTML = html;

    // Draw charts
    packPie('msPackU', D.packUnits, fmtInt);
    packPie('msPackR', D.packRev, fmtMoney);
    doughnut('msBrandU', D.brandUnits.labels, D.brandUnits.values, BRAND_COLORS, fmtInt);
    doughnut('msBrandR', D.brandRev.labels, D.brandRev.values, BRAND_COLORS, fmtMoney);
    D.topPackPies.forEach(function(tp,i){
      var colors = tp.labels.map(function(_,j){ return BRAND_COLORS[j%BRAND_COLORS.length]; });
      doughnut('msTP'+i, tp.labels, tp.values, colors, fmtInt);
    });
    // Price by pack (grouped bar: avg price + avg per trap)
    barChart('msPrice', D.priceByPack.map(function(x){return x.pack+'-pak';}),
      [{label:'Śr. cena €', data:D.priceByPack.map(function(x){return x.avgPrice;}), color:'#2563eb'},
       {label:'€ / pułapkę', data:D.priceByPack.map(function(x){return x.avgPerTrap;}), color:'#16a34a'}]);
    barChart('msPerTrap', D.priceByPack.map(function(x){return x.pack+'-pak';}),
      [{label:'€ / pułapkę', data:D.priceByPack.map(function(x){return x.avgPerTrap;}), color:'#d97706'}]);
    scatterChart('msScatter', D.scatter);
    // Seasonality bar
    barChart('msSeas', SEAS.names, [{label:'Indeks', data:SEAS.index, color:'#7c3aed', line:1.0}]);

    buildPackTable(D.packTable);
    buildBrandTable(D.brandTable);
    buildAsinTable(D.topAsins, view);
  }

  function kpi(v,l){ return '<div class="ms2-kpi"><div class="ms2-kpi-v">'+v+'</div><div class="ms2-kpi-l">'+l+'</div></div>'; }
  function card(title, body){ return '<div class="ms2-card"><h3>'+title+'</h3>'+body+'</div>'; }
  function canvas(id, h){ return '<div class="ms2-cw" style="height:'+(h||300)+'px"><canvas id="'+id+'"></canvas></div>'; }
  function row2(a,b){ return '<div class="ms2-row2">'+a+b+'</div>'; }
  function tableWrap(id){ return '<div class="ms2-tblwrap"><table id="'+id+'" class="ms2-tbl"></table></div>'; }

  function barChart(id, labels, series){
    var el=document.getElementById(id); if(!el) return;
    charts.push(new Chart(el, {
      type:'bar',
      data:{ labels:labels, datasets:series.map(function(s){ return { label:s.label, data:s.data, backgroundColor:s.color, borderRadius:3, borderSkipped:false }; }) },
      options:{ responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{ display:series.length>1, position:'bottom', labels:{font:{size:10},boxWidth:12} },
          datalabels:{ display:false },
          tooltip:{ callbacks:{ label:function(ctx){ return ' '+ctx.dataset.label+': '+ctx.parsed.y.toFixed(2); } } } },
        scales:{ x:{ grid:{display:false}, ticks:{font:{size:10}} }, y:{ grid:{color:'#e2e8f0'}, ticks:{font:{size:10}} } } }
    }));
  }

  function scatterChart(id, points){
    var el=document.getElementById(id); if(!el) return;
    var maxRev = Math.max.apply(null, points.map(function(p){return p.rev;}).concat([1]));
    var byPack = {};
    points.forEach(function(p){ (byPack[p.pack]=byPack[p.pack]||[]).push(p); });
    var datasets = Object.keys(byPack).map(function(pk){
      return { label:pk+'-pak', backgroundColor:packColor(parseInt(pk))+'cc', borderColor:packColor(parseInt(pk)),
        data: byPack[pk].map(function(p){ return { x:p.x, y:p.y, r:4+Math.sqrt(p.rev/maxRev)*22, brand:p.brand, pack:p.pack, rev:p.rev }; }) };
    });
    charts.push(new Chart(el, {
      type:'bubble',
      data:{ datasets:datasets },
      options:{ responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{ position:'bottom', labels:{font:{size:10},boxWidth:10} }, datalabels:{display:false},
          tooltip:{ callbacks:{ label:function(ctx){ var d=ctx.raw; return d.brand+' ('+d.pack+'-pak): €'+d.x.toFixed(2)+', '+d.y.toFixed(1)+'% szt., '+fmtMoney(d.rev); } } } },
        scales:{ x:{ title:{display:true,text:'Śr. cena €',font:{size:10}}, grid:{color:'#e2e8f0'}, ticks:{font:{size:10}} },
                 y:{ title:{display:true,text:'Udział w sztukach %',font:{size:10}}, grid:{color:'#e2e8f0'}, ticks:{font:{size:10}} } } }
    }));
  }

  function sortableTable(id, cols, rows, defKey){
    var sortKey=defKey, sortDir='desc';
    function draw(){
      rows.sort(function(a,b){ var va=a[sortKey], vb=b[sortKey];
        if(typeof va==='number'&&typeof vb==='number') return sortDir==='asc'?va-vb:vb-va;
        return sortDir==='asc'?String(va).localeCompare(String(vb)):String(vb).localeCompare(String(va)); });
      var h='<thead><tr>';
      cols.forEach(function(c){ h+='<th class="'+(c.num?'num':'')+(c.key===sortKey?(sortDir==='asc'?' sa':' sd'):'')+'" data-k="'+c.key+'">'+c.label+'</th>'; });
      h+='</tr></thead><tbody>';
      rows.forEach(function(r){ h+='<tr>'; cols.forEach(function(c){ h+='<td class="'+(c.num?'num':'')+'">'+(c.fmt?c.fmt(r[c.key],r):esc(r[c.key]))+'</td>'; }); h+='</tr>'; });
      h+='</tbody>';
      var t=document.getElementById(id); t.innerHTML=h;
      t.querySelectorAll('th').forEach(function(th){ th.onclick=function(){ var k=th.dataset.k; if(sortKey===k) sortDir=sortDir==='asc'?'desc':'asc'; else {sortKey=k;sortDir='desc';} draw(); }; });
    }
    draw();
  }

  function buildPackTable(rows){
    sortableTable('msPackTable', [
      {key:'pack',label:'Format',num:true,fmt:function(v){return v+'-pak';}},
      {key:'n',label:'ASIN',num:true},
      {key:'units12m',label:'Sztuki 12M',num:true,fmt:fmtInt},
      {key:'rev12m',label:'Przychód 12M',num:true,fmt:fmtMoney},
      {key:'unitShare',label:'% szt.',num:true,fmt:function(v){return v+'%';}},
      {key:'revShare',label:'% przych.',num:true,fmt:function(v){return v+'%';}},
      {key:'avgPrice',label:'Śr. cena €',num:true,fmt:function(v){return '€'+v.toFixed(2);}},
      {key:'avgPerTrap',label:'€/pułapkę',num:true,fmt:function(v){return '€'+v.toFixed(2);}},
    ], rows, 'rev12m');
  }
  function buildBrandTable(rows){
    sortableTable('msBrandTable', [
      {key:'brand',label:'Marka',num:false},
      {key:'n',label:'ASIN',num:true},
      {key:'units12m',label:'Sztuki 12M',num:true,fmt:fmtInt},
      {key:'rev12m',label:'Przychód 12M',num:true,fmt:fmtMoney},
      {key:'unitShare',label:'% szt.',num:true,fmt:function(v){return v+'%';}},
      {key:'revShare',label:'% przych.',num:true,fmt:function(v){return v+'%';}},
      {key:'avgPrice',label:'Śr. cena €',num:true,fmt:function(v){return '€'+v.toFixed(2);}},
    ], rows, 'rev12m');
  }
  function buildAsinTable(rows, view){
    sortableTable('msAsinTable', [
      {key:'asin',label:'ASIN',num:false,fmt:function(v,r){ var dom=DOMAINS[r._mkt]||'de'; return '<a class="ms2-asin" href="https://www.amazon.'+dom+'/dp/'+encodeURIComponent(v)+'" target="_blank" rel="noopener">'+esc(v)+'</a>'; }},
      {key:'brand',label:'Marka',num:false},
      {key:'pack',label:'Format',num:true,fmt:function(v){return v+'-pak';}},
      {key:'title',label:'Tytuł',num:false,fmt:function(v){return '<span class="ms2-title" title="'+esc(v)+'">'+esc(v)+'</span>';}},
      {key:'price',label:'Cena €',num:true,fmt:function(v){return '€'+Number(v).toFixed(2);}},
      {key:'eurPerTrap',label:'€/pułapkę',num:true,fmt:function(v){return '€'+Number(v).toFixed(2);}},
      {key:'units12m',label:'Sztuki 12M',num:true,fmt:fmtInt},
      {key:'rev12m',label:'Przychód 12M',num:true,fmt:fmtMoney},
      {key:'reviews',label:'Recenzje',num:true,fmt:fmtInt},
    ], rows, 'rev12m');
  }

  // Country pills
  var pillHost = document.getElementById('ms2Pills');
  var current = 'ALL';
  VIEWS.forEach(function(v,i){
    var b=document.createElement('button');
    b.className='ms2-pill'+(i===0?' active':''); b.textContent=v[1]; b.dataset.view=v[0];
    b.onclick=function(){ pillHost.querySelectorAll('.ms2-pill').forEach(function(x){x.classList.remove('active');}); b.classList.add('active'); current=v[0]; render(current); };
    pillHost.appendChild(b);
  });

  // Exposed so the shell can render on first tab open (panel must be visible).
  window.__structRender = function(){ render(current); };
})();
</script>
'''

# Style guard: no em/en dashes.
FRAG = FRAG.replace('—', '-').replace('–', '-')

out_path = os.path.join(BASE, '_structure.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(FRAG)

print(f'_structure.html: {os.path.getsize(out_path):,} bytes')
print(f'Seasonal multiplier: x{MULT}')
for c in ['ALL'] + CODES:
    k = STRUCT[c]['kpis']
    print(f"  [{c}] {k['nBrands']} brands, {k['nPackFormats']} pack formats, dom {k['domPack']}-pak ({k['domPackShare']}%), HHI {k['hhi']}, avg €/trap {k['avgEurPerTrap']}")
