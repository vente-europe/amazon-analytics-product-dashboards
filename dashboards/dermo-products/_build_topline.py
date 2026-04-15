"""
Buduje standalone index.html dla dermo-products (topline, 4 rynki DE/FR/IT/ES).

Czyta Dermo-Products-{CODE}.csv z data/x-ray/{CODE}/, filtruje do segmentów
Cream/Wash/Oil, agreguje 30d revenue + units per rynek i per (segment × rynek),
projektuje 12M jako 30d × 12, i składa samowystarczalny HTML (styl: Fruit Flies
International topline, z heatmapą segment × rynek).
"""
import csv, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))

# Rynki w kolejności dominacji (DE największy, ES najmniejszy)
MARKETS = [
    {'code': 'DE', 'name': 'Germany', 'name_pl': 'Niemcy',    'flag': '🇩🇪', 'color': '#2563eb'},
    {'code': 'FR', 'name': 'France',  'name_pl': 'Francja',   'flag': '🇫🇷', 'color': '#0891b2'},
    {'code': 'IT', 'name': 'Italy',   'name_pl': 'Włochy',    'flag': '🇮🇹', 'color': '#7c3aed'},
    {'code': 'ES', 'name': 'Spain',   'name_pl': 'Hiszpania', 'flag': '🇪🇸', 'color': '#d97706'},
]

# Segmenty do pokazania (reszta — Check/Other/puste — pomijamy w agregacji)
SEGMENTS = ['Cream', 'Wash', 'Oil']
SEGMENT_COLORS = {
    'Cream': '#2563eb',  # niebieski — dominujący segment
    'Wash':  '#16a34a',  # zielony
    'Oil':   '#d97706',  # pomarańczowy
}

# Linki do Google Sheets dla każdego rynku (kolejność: DE, FR, IT, ES)
XRAY_LINKS = {
    'DE': 'https://docs.google.com/spreadsheets/d/1_i9_eaJUx9YhG0XFUOWb97YEn_Jj79U6wqcapMYK9Yw/edit?gid=1649983910#gid=1649983910',
    'FR': 'https://docs.google.com/spreadsheets/d/1fD-QisOAi2_GUpHItXgeUu2bN19iti9w0KrtbOP51Jc/edit?gid=2058240202#gid=2058240202',
    'IT': 'https://docs.google.com/spreadsheets/d/1coY3TXsKNt-z_ruNg5Krdm-UPNywG5wIwep9XqZFlOo/edit?gid=1574144490#gid=1574144490',
    'ES': 'https://docs.google.com/spreadsheets/d/1u-S0NnaPOJB2qh0KSvxOum4bvQt5Ydrp7-VPNngGvKI/edit?gid=1593778489#gid=1593778489',
}

# Mnożnik 30d → 12M. Topline używa flat ×12 (prosty, bez sezonowości).
# Dla szczegółowego dashboardu można potem podmienić na sezonalność.
MULTIPLIER = 12

def numv(v):
    """Parsuje liczbę z CSV (usuwa EUR/USD/$, przecinki tysięczne, itd.)"""
    if v is None: return 0.0
    s = str(v).strip()
    if not s or s.lower() == 'nan': return 0.0
    s = re.sub(r'[^\d.,-]', '', s).replace(',', '.')
    # jeśli jest wiele kropek, to ostatnia jest dziesiętna a wcześniejsze tysięczne
    if s.count('.') > 1:
        parts = s.split('.')
        s = ''.join(parts[:-1]) + '.' + parts[-1]
    try: return float(s)
    except: return 0.0

def load_market(code):
    """Zwraca listę produktów (dict) dla danego rynku, tylko z segmentem Cream/Wash/Oil."""
    path = os.path.join(BASE, 'data', 'x-ray', code, f'Dermo-Products-{code}.csv')
    if not os.path.exists(path):
        print(f'  [{code}] brak pliku {path}')
        return []
    rows = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            seg = (row.get('Segment') or '').strip()
            if seg not in SEGMENTS:
                continue  # pomijamy Check/Other/puste
            # kolumna cenowa — różne warianty w zależności od lokalizacji (Price EUR/Price US$)
            price_col = next((k for k in row.keys() if k and 'price' in k.lower()), None)
            sales30d = numv(row.get('ASIN Sales'))
            rev30d   = numv(row.get('ASIN Revenue'))
            price    = numv(row.get(price_col)) if price_col else 0.0
            # jeśli sales pusty ale mamy revenue + cenę → policz sales
            if sales30d == 0 and rev30d > 0 and price > 0:
                sales30d = round(rev30d / price)
            # jeśli revenue pusty ale mamy sales + cenę → policz revenue
            if rev30d == 0 and sales30d > 0 and price > 0:
                rev30d = sales30d * price
            rows.append({
                'asin':     (row.get('ASIN') or '').strip(),
                'segment':  seg,
                'sales30d': sales30d,
                'rev30d':   rev30d,
                'brand':    (row.get('Brand') or 'Unknown').strip() or 'Unknown',
            })
    return rows

# ── Zbierz dane dla wszystkich rynków ───────────────────────────────────
data_by_market = {}
# Globalny agregat marek (wszystkie rynki razem) do pie charts poniżej tabeli
global_brand = {}  # brand -> {'rev12m': X, 'units12m': Y}
for m in MARKETS:
    rows = load_market(m['code'])
    units30d = sum(r['sales30d'] for r in rows)
    rev30d   = sum(r['rev30d']   for r in rows)
    units12m = round(units30d * MULTIPLIER)
    rev12m   = round(rev30d * MULTIPLIER)
    # agregacja per segment w tym rynku
    per_seg = {s: {'units12m': 0, 'rev12m': 0} for s in SEGMENTS}
    for r in rows:
        s = r['segment']
        per_seg[s]['units12m'] += round(r['sales30d'] * MULTIPLIER)
        per_seg[s]['rev12m']   += round(r['rev30d']   * MULTIPLIER)
        # Global brand aggregation (wszystkie rynki razem)
        b = global_brand.setdefault(r['brand'], {'rev12m': 0, 'units12m': 0})
        b['rev12m']   += round(r['rev30d']   * MULTIPLIER)
        b['units12m'] += round(r['sales30d'] * MULTIPLIER)
    data_by_market[m['code']] = {
        'units30d': units30d,
        'rev30d':   rev30d,
        'units12m': units12m,
        'rev12m':   rev12m,
        'per_seg':  per_seg,
        'asin_count': len(rows),
    }
    print(f'  [{m["code"]}] {len(rows)} ASIN, {units30d:,.0f} szt/30d, €{rev30d:,.0f}/30d')

# ── Sortuj rynki po 12M revenue (largest first) — zachowujemy konsystentną
#    kolejność we wszystkich wizualizacjach: bar chart, tabela, heatmapy ──
MARKETS.sort(key=lambda m: data_by_market[m['code']]['rev12m'], reverse=True)

# ── Top 12 marek + "Other" (osobno dla revenue i units) ─────────────────
def top_brands(metric, n=12):
    items = sorted(global_brand.items(), key=lambda kv: kv[1][metric], reverse=True)
    top = items[:n]
    rest = items[n:]
    labels = [b for b, _ in top]
    values = [v[metric] for _, v in top]
    if rest:
        labels.append(f'Other ({len(rest)})')
        values.append(sum(v[metric] for _, v in rest))
    return labels, values

brand_rev_labels,   brand_rev_values   = top_brands('rev12m')
brand_units_labels, brand_units_values = top_brands('units12m')

# Dla heatmap marek potrzebujemy per-brand per-market (top 10 wspólnych marek)
# Reagregujemy rynki → (brand, market) → rev12m/units12m
brand_market = {}  # brand -> {market_code -> {'rev12m', 'units12m'}}
for m in MARKETS:
    rows = load_market(m['code'])
    for r in rows:
        bm = brand_market.setdefault(r['brand'], {c['code']: {'rev12m': 0, 'units12m': 0} for c in MARKETS})
        bm[m['code']]['rev12m']   += round(r['rev30d']   * MULTIPLIER)
        bm[m['code']]['units12m'] += round(r['sales30d'] * MULTIPLIER)

# Top 10 marek po łącznym revenue (wspólne dla obu heatmap)
top10_by_rev = sorted(global_brand.items(), key=lambda kv: kv[1]['rev12m'], reverse=True)[:10]
hm_brand_names = [b for b, _ in top10_by_rev]
hm_rest_brands = set(global_brand.keys()) - set(hm_brand_names)

def hm_row(brand_name, metric):
    if brand_name == 'Other':
        return [sum(brand_market[b][m['code']][metric] for b in hm_rest_brands if b in brand_market) for m in MARKETS]
    bm = brand_market.get(brand_name, {})
    return [bm.get(m['code'], {}).get(metric, 0) for m in MARKETS]

brand_hm_data = {}
for b in hm_brand_names:
    brand_hm_data[b] = {
        'rev':   hm_row(b, 'rev12m'),
        'units': hm_row(b, 'units12m'),
    }
if hm_rest_brands:
    brand_hm_data[f'Other ({len(hm_rest_brands)})'] = {
        'rev':   hm_row('Other', 'rev12m'),
        'units': hm_row('Other', 'units12m'),
    }
hm_brand_order = list(brand_hm_data.keys())

# Paleta dla marek (12 top + szary na "Other")
BRAND_PALETTE = [
    '#2563eb','#dc2626','#0891b2','#d97706','#7c3aed','#16a34a',
    '#db2777','#0284c7','#ca8a04','#059669','#4f46e5','#be123c',
    '#94a3b8',  # Other
]

# ── Generuj tabele danych dla JS ────────────────────────────────────────
labels      = [m['code'] for m in MARKETS]
colors      = [m['color'] for m in MARKETS]
revenue_arr = [data_by_market[m['code']]['rev12m']   for m in MARKETS]
units_arr   = [data_by_market[m['code']]['units12m'] for m in MARKETS]

total_rev12m   = sum(revenue_arr)
total_units12m = sum(units_arr)

# Heatmapa: per segment (wiersz) × per rynek (kolumna)
seg_data_js = {}
for s in SEGMENTS:
    seg_data_js[s] = {
        'rev':   [data_by_market[m['code']]['per_seg'][s]['rev12m']   for m in MARKETS],
        'units': [data_by_market[m['code']]['per_seg'][s]['units12m'] for m in MARKETS],
    }

# ── Wiersze tabeli rynków ───────────────────────────────────────────────
def fmt_money(v):
    if v >= 1e6: return f'&euro;{v/1e6:.1f}M'
    if v >= 1e3: return f'&euro;{v/1e3:.0f}K'
    return f'&euro;{v:.0f}'

table_rows_html = ''
for m in MARKETS:
    d = data_by_market[m['code']]
    share = (d['rev12m'] / total_rev12m * 100) if total_rev12m > 0 else 0
    table_rows_html += f'''        <tr>
          <td><span class="dot" style="background:{m['color']}"></span>{m['flag']} {m['name']} ({m['code']})</td>
          <td>EUR</td>
          <td class="num">{d['units30d']:,.0f}</td>
          <td class="num">{MULTIPLIER}×</td>
          <td class="num">{d['units12m']:,.0f}</td>
          <td class="num">&euro;{d['rev12m']:,.0f}</td>
          <td class="num">{share:.1f}%</td>
        </tr>
'''
table_rows_html += f'''        <tr class="total-row">
          <td colspan="2"><strong>Total</strong></td>
          <td class="num">{sum(d["units30d"] for d in data_by_market.values()):,.0f}</td>
          <td class="num">—</td>
          <td class="num">{total_units12m:,.0f}</td>
          <td class="num">&euro;{total_rev12m:,.0f}</td>
          <td class="num">100%</td>
        </tr>
'''

# ── Przyciski X-Ray (Google Sheets) ─────────────────────────────────────
xray_buttons = ''
for m in MARKETS:
    href = XRAY_LINKS.get(m['code'], '#')
    xray_buttons += f'''    <a class="xray-btn" href="{href}" target="_blank" rel="noopener">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      {m['code']} X-Ray
    </a>
'''

# ── Podstaw dane do JS ──────────────────────────────────────────────────
import json
seg_data_json = json.dumps(seg_data_js, indent=2)
brand_hm_data_json  = json.dumps(brand_hm_data, indent=2, ensure_ascii=False)
brand_hm_order_json = json.dumps(hm_brand_order, ensure_ascii=False)

# Nagłówki kolumn heatmap — dynamiczne, zgodne z posortowanym porządkiem MARKETS
heatmap_th_cols = ''.join(f'<th class="num">{m["code"]}</th>' for m in MARKETS)

# ── Automatyczne wyliczenie insightów do summary box ────────────────────
# Sortowanie rynków po 12M revenue
markets_ranked = sorted(
    [(m, data_by_market[m['code']]) for m in MARKETS],
    key=lambda x: x[1]['rev12m'], reverse=True
)
top_mkt, top_mkt_data = markets_ranked[0]
top_mkt_share = top_mkt_data['rev12m'] / total_rev12m * 100
m2 = markets_ranked[1]; m3 = markets_ranked[2]; m4 = markets_ranked[3]

# Revenue per ASIN per rynek (efficiency)
rev_per_asin = {m['code']: (data_by_market[m['code']]['rev12m'] / data_by_market[m['code']]['asin_count']) for m in MARKETS}
best_efficiency = max(rev_per_asin.items(), key=lambda kv: kv[1])

# Segmenty — udział w revenue
seg_totals_rev = {s: sum(data_by_market[m['code']]['per_seg'][s]['rev12m'] for m in MARKETS) for s in SEGMENTS}
seg_totals_units = {s: sum(data_by_market[m['code']]['per_seg'][s]['units12m'] for m in MARKETS) for s in SEGMENTS}
seg_rev_shares = {s: seg_totals_rev[s] / total_rev12m * 100 for s in SEGMENTS}
# Średnia cena per segment
seg_avg_price = {s: (seg_totals_rev[s] / seg_totals_units[s]) if seg_totals_units[s] else 0 for s in SEGMENTS}

# Marki — top brand share, top 3, liczba unikalnych
brand_ranked = sorted(global_brand.items(), key=lambda kv: kv[1]['rev12m'], reverse=True)
top_brand_name, top_brand_data = brand_ranked[0]
top_brand_share = top_brand_data['rev12m'] / total_rev12m * 100
top3_brand_share = sum(b[1]['rev12m'] for b in brand_ranked[:3]) / total_rev12m * 100
n_unique_brands = len(global_brand)

# Średnia cena całej kategorii
avg_price_category = total_rev12m / total_units12m if total_units12m else 0

# Total ASIN count
total_asins = sum(data_by_market[m['code']]['asin_count'] for m in MARKETS)

# ── Szablon HTML (samowystarczalny, bez fetch) ──────────────────────────
HTML = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dermo Products (Atopic / Sensitive Skin) — International Markets (12M)</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f1f5f9;color:#1e293b;font-size:13px}}
header{{background:#0f2942;color:#fff;padding:18px 32px;display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap}}
header .titles h1{{font-size:1.1rem;font-weight:700;letter-spacing:.01em;margin-bottom:4px}}
header .titles span{{font-size:.75rem;color:#94a3b8}}
.xray-btn-row{{display:flex;gap:8px;flex-wrap:wrap}}
.xray-btn{{background:#16a34a;color:#fff;padding:8px 14px;border-radius:6px;font-size:.76rem;font-weight:600;text-decoration:none;white-space:nowrap;display:inline-flex;align-items:center;gap:6px;box-shadow:0 1px 3px rgba(0,0,0,.2);transition:background .15s}}
.xray-btn:hover{{background:#15803d}}
.xray-btn svg{{width:14px;height:14px}}
.main{{max-width:1200px;margin:0 auto;padding:28px 24px}}
.kpi-row{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:24px}}
.kpi{{background:#fff;border-radius:8px;padding:14px 18px;box-shadow:0 1px 3px rgba(0,0,0,.07)}}
.kpi-v{{font-size:1.25rem;font-weight:700;color:#0f2942;line-height:1.2}}
.kpi-l{{font-size:.68rem;color:#64748b;margin-top:5px;text-transform:uppercase;letter-spacing:.05em}}
.charts-row{{display:grid;grid-template-columns:1.4fr 1fr;gap:18px;margin-bottom:24px}}
.card{{background:#fff;border-radius:8px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,.07);margin-bottom:24px}}
.card h3{{font-size:.83rem;font-weight:600;color:#475569;margin-bottom:16px}}
.chart-wrap{{position:relative;height:300px}}
table{{width:100%;border-collapse:collapse}}
th{{background:#f8fafc;text-align:left;padding:8px 10px;font-weight:600;color:#475569;font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #e2e8f0}}
td{{padding:7px 10px;border-bottom:1px solid #f1f5f9;font-size:.82rem}}
tr:hover td{{background:#f8fafc}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}}
.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;flex-shrink:0}}
.note{{font-size:.7rem;color:#64748b;margin-top:18px;padding:10px 13px;background:#f8fafc;border-radius:6px;border-left:2px solid #cbd5e1;line-height:1.6}}
.total-row td{{font-weight:700;color:#0f2942;background:#f8fafc;border-top:2px solid #e2e8f0}}
.heatmap td.hm{{text-align:center;font-size:.78rem;font-weight:600;padding:10px 8px;min-width:70px}}
.heatmap td.hm-total{{text-align:center;font-size:.78rem;font-weight:700;padding:10px 8px;min-width:70px;border-left:2px solid #e2e8f0;background:#f8fafc;color:#0f2942}}
.heatmap .seg-label{{font-weight:600;color:#1e293b;padding:10px 12px;white-space:nowrap}}
.heatmap .total-row td{{font-weight:700;border-top:2px solid #e2e8f0;background:#f8fafc;color:#0f2942}}
/* Executive summary block — 3 kolumny insight cardów, collapsible */
.summary{{background:#fff;border-radius:8px;padding:0;box-shadow:0 1px 3px rgba(0,0,0,.07);margin-bottom:14px;border-left:4px solid #0f2942;overflow:hidden}}
.summary > summary, .kw-block > summary{{cursor:pointer;padding:14px 22px;font-size:.85rem;font-weight:700;color:#0f2942;text-transform:uppercase;letter-spacing:.06em;list-style:none;display:flex;align-items:center;gap:10px;user-select:none;transition:background .15s}}
.summary > summary:hover, .kw-block > summary:hover{{background:#f8fafc}}
.summary > summary::-webkit-details-marker, .kw-block > summary::-webkit-details-marker{{display:none}}
.summary > summary::before, .kw-block > summary::before{{content:'▸';display:inline-block;transition:transform .2s;font-size:.9rem;color:#64748b;width:14px}}
.summary[open] > summary::before, .kw-block[open] > summary::before{{transform:rotate(90deg)}}
.summary > summary .hint, .kw-block > summary .hint{{font-size:.66rem;font-weight:500;color:#94a3b8;text-transform:none;letter-spacing:0;margin-left:auto;font-style:italic}}
.summary-inner{{padding:2px 22px 18px}}
.summary h2{{display:none}}
.summary-cols{{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}}
.summary-col h3{{font-size:.7rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #f1f5f9}}
.summary-col p{{font-size:.82rem;line-height:1.55;color:#334155;margin-bottom:8px}}
.summary-col p:last-child{{margin-bottom:0}}
.summary-col strong{{color:#0f2942}}
.summary-col .big{{font-size:1.15rem;font-weight:700;color:#0f2942;display:block;margin-bottom:2px}}
.summary-col .small{{font-size:.72rem;color:#64748b;margin-top:4px;font-style:italic}}
@media (max-width: 980px) {{ .summary-cols {{ grid-template-columns: 1fr; gap: 16px; }} }}
/* Keywords block — collapsible */
.kw-block{{background:#fff;border-radius:8px;padding:0;box-shadow:0 1px 3px rgba(0,0,0,.07);margin-bottom:22px;border-left:4px solid #16a34a;overflow:hidden}}
.kw-block h2{{display:none}}
.kw-inner{{padding:2px 22px 18px}}
.kw-inner .kw-intro{{font-size:.78rem;color:#475569;line-height:1.5;margin-bottom:14px}}
.kw-cols{{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}}
.kw-market{{border:1px solid #e2e8f0;border-radius:6px;padding:12px 14px;background:#fafafa}}
.kw-market-header{{font-size:.78rem;font-weight:700;color:#0f2942;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #e2e8f0;display:flex;align-items:center;gap:6px}}
.kw-group{{margin-bottom:10px}}
.kw-group:last-child{{margin-bottom:0}}
.kw-group-label{{font-size:.68rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}}
.kw-list{{font-size:.72rem;color:#334155;line-height:1.6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
.kw-list code{{display:block;background:#f1f5f9;padding:3px 7px;border-radius:3px;margin:2px 0;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.7rem;color:#0f2942}}
@media (max-width: 980px) {{ .kw-cols {{ grid-template-columns: 1fr 1fr; gap: 14px; }} }}
@media (max-width: 600px) {{ .kw-cols {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>

<header>
  <div class="titles">
    <h1>Dermo Products (Atopic / Sensitive Skin) &mdash; International Markets</h1>
    <span>12-Month Projection (30-day &times; 12) &nbsp;|&nbsp; Data: Helium 10 X-Ray (2026-04-15)</span>
  </div>
  <div class="xray-btn-row">
{xray_buttons}  </div>
</header>

<div class="main">

  <!-- KPI Row -->
  <div class="kpi-row">
    <div class="kpi">
      <div class="kpi-v">&euro;{total_rev12m/1e6:.1f}M</div>
      <div class="kpi-l">Total 12M Revenue (Cream + Wash + Oil)</div>
    </div>
    <div class="kpi">
      <div class="kpi-v">{total_units12m:,}</div>
      <div class="kpi-l">Total 12M Units Sold (all segments)</div>
    </div>
    <div class="kpi">
      <div class="kpi-v">4 Markets</div>
      <div class="kpi-l">DE &bull; FR &bull; IT &bull; ES</div>
    </div>
  </div>

  <!-- Executive summary — automatycznie generowany z danych -->
  <details class="summary">
    <summary>Podsumowanie &mdash; kluczowe wnioski (12M) <span class="hint">kliknij żeby rozwinąć</span></summary>
    <div class="summary-inner">
    <div class="summary-cols">

      <div class="summary-col">
        <h3>Rynki</h3>
        <p>Zdecydowanym liderem kategorii są <strong>{top_mkt['name_pl']}</strong>, które generują <strong>€{top_mkt_data['rev12m']/1e6:.1f} mln</strong> rocznego przychodu i odpowiadają za <strong>{top_mkt_share:.0f}%</strong> całego rynku europejskiego (DE+FR+IT+ES). To ponad <strong>{top_mkt_data['rev12m']/m2[1]['rev12m']:.1f}-krotnie</strong> więcej niż drugi największy rynek.</p>
        <p>Pełna hierarchia: <strong>{top_mkt['name_pl']}</strong> (€{top_mkt_data['rev12m']/1e6:.1f} mln), następnie <strong>{m2[0]['name_pl']}</strong> (€{m2[1]['rev12m']/1e6:.1f} mln), <strong>{m3[0]['name_pl']}</strong> (€{m3[1]['rev12m']/1e6:.1f} mln) i na końcu <strong>{m4[0]['name_pl']}</strong> (€{m4[1]['rev12m']/1e6:.1f} mln). Rynek niemiecki jest dojrzały i rozdrobniony, natomiast we Włoszech obserwujemy najwyższy średni przychód przypadający na jeden produkt — co oznacza mniej graczy, ale silniejsze pozycje każdego z nich.</p>
      </div>

      <div class="summary-col">
        <h3>Segmenty (forma produktu)</h3>
        <p>Krem jest niekwestionowanym liderem kategorii z udziałem <strong>{seg_rev_shares['Cream']:.0f}%</strong> w przychodzie (<strong>€{seg_totals_rev['Cream']/1e6:.1f} mln</strong>). Przy średniej cenie <strong>€{seg_avg_price['Cream']:.0f}</strong> za sztukę jest to klasyczny segment premium, kierowany głównie do osób zmagających się ze skórą atopową, suchą lub podrażnioną.</p>
        <p>Produkty do mycia (<strong>Wash</strong> — żele, emulsje, olejki pod prysznic) stanowią solidne drugie miejsce z <strong>{seg_rev_shares['Wash']:.0f}%</strong> udziału (€{seg_totals_rev['Wash']/1e6:.1f} mln, średnia cena €{seg_avg_price['Wash']:.0f}). Olejki do ciała (<strong>Oil</strong>) to natomiast wąska nisza — zaledwie <strong>{seg_rev_shares['Oil']:.1f}%</strong> rynku, głównie obecna w Niemczech. Łącznie po filtrze ≥€1 000/30 dni w analizie znalazło się <strong>{total_asins}</strong> produktów w czterech krajach.</p>
      </div>

      <div class="summary-col">
        <h3>Konkurencja i ceny</h3>
        <p>Kategoria jest {'silnie skoncentrowana' if top3_brand_share >= 40 else 'umiarkowanie rozproszona'} — trzy największe marki odpowiadają łącznie za <strong>{top3_brand_share:.0f}%</strong> całego przychodu. Liderem jest <strong>{top_brand_name}</strong> z udziałem <strong>{top_brand_share:.0f}%</strong> (€{top_brand_data['rev12m']/1e6:.1f} mln rocznie). W całej niszy aktywnie działa <strong>{n_unique_brands}</strong> unikalnych marek, ale każdy rynek ma swoją odrębną hierarchię — co widać w tabeli cieplnej marek poniżej.</p>
        <p>Średnia cena produktu w kategorii wynosi <strong>€{avg_price_category:.0f}</strong> za sztukę, co potwierdza premium charakter segmentu. Dominują marki o pozycjonowaniu aptecznym i dermatologicznym (La Roche-Posay, Eucerin, Bioderma, Avène, CeraVe), a także silne marki lokalne w poszczególnych krajach.</p>
      </div>

    </div>
    </div>
  </details>

  <!-- Keywords used per marketplace -->
  <details class="kw-block">
    <summary>Słowa kluczowe użyte w analizie <span class="hint">kliknij żeby rozwinąć</span></summary>
    <div class="kw-inner">
    <p class="kw-intro">Dla każdego z czterech rynków wykonano 12 osobnych przeszukiwań w narzędziu Helium 10 X-Ray &mdash; po <strong>4 słowa kluczowe dla każdej z trzech form produktu</strong> (Cream / Wash / Oil). Wyniki zostały zmerge'owane per rynek, odduplikowane po ASIN i odfiltrowane do produktów z przychodem ≥€1 000 w ciągu ostatnich 30 dni. Poniżej pełna lista fraz &mdash; pozwala to zweryfikować, czy nie pominęliśmy żadnego istotnego kąta wyszukiwania.</p>
    <div class="kw-cols">

      <div class="kw-market">
        <div class="kw-market-header">🇩🇪 Niemcy (DE)</div>
        <div class="kw-group">
          <div class="kw-group-label">Cream</div>
          <div class="kw-list">
            <code>creme neurodermitis</code>
            <code>creme atopische haut</code>
            <code>pflegecreme trockene empfindliche haut</code>
            <code>ekzem creme körper</code>
          </div>
        </div>
        <div class="kw-group">
          <div class="kw-group-label">Wash</div>
          <div class="kw-list">
            <code>waschlotion neurodermitis</code>
            <code>duschöl atopische haut</code>
            <code>waschsyndet empfindliche haut</code>
            <code>reinigungsöl trockene haut</code>
          </div>
        </div>
        <div class="kw-group">
          <div class="kw-group-label">Oil</div>
          <div class="kw-list">
            <code>körperöl neurodermitis</code>
            <code>pflegeöl atopische haut</code>
            <code>hautöl trockene empfindliche haut</code>
            <code>körperöl ekzem</code>
          </div>
        </div>
      </div>

      <div class="kw-market">
        <div class="kw-market-header">🇫🇷 Francja (FR)</div>
        <div class="kw-group">
          <div class="kw-group-label">Cream</div>
          <div class="kw-list">
            <code>crème peau atopique</code>
            <code>crème peau sèche irritée</code>
            <code>crème émolliente</code>
            <code>crème dermatite atopique</code>
          </div>
        </div>
        <div class="kw-group">
          <div class="kw-group-label">Wash</div>
          <div class="kw-list">
            <code>gel lavant peau atopique</code>
            <code>huile lavante peau atopique</code>
            <code>nettoyant surgras</code>
            <code>syndet peau atopique</code>
          </div>
        </div>
        <div class="kw-group">
          <div class="kw-group-label">Oil</div>
          <div class="kw-list">
            <code>huile corps peau sèche</code>
            <code>huile peau atopique</code>
            <code>huile corps dermatologique</code>
            <code>huile apaisante corps</code>
          </div>
        </div>
      </div>

      <div class="kw-market">
        <div class="kw-market-header">🇮🇹 Włochy (IT)</div>
        <div class="kw-group">
          <div class="kw-group-label">Cream</div>
          <div class="kw-list">
            <code>crema pelle atopica</code>
            <code>crema pelle secca sensibile</code>
            <code>crema emolliente</code>
            <code>crema dermatite atopica</code>
          </div>
        </div>
        <div class="kw-group">
          <div class="kw-group-label">Wash</div>
          <div class="kw-list">
            <code>detergente pelle atopica</code>
            <code>bagno doccia pelle atopica</code>
            <code>olio detergente corpo</code>
            <code>sapone pelle atopica</code>
          </div>
        </div>
        <div class="kw-group">
          <div class="kw-group-label">Oil</div>
          <div class="kw-list">
            <code>olio pelle atopica</code>
            <code>olio corpo pelle secca</code>
            <code>olio doccia pelle secca</code>
            <code>olio emolliente corpo</code>
          </div>
        </div>
      </div>

      <div class="kw-market">
        <div class="kw-market-header">🇪🇸 Hiszpania (ES)</div>
        <div class="kw-group">
          <div class="kw-group-label">Cream</div>
          <div class="kw-list">
            <code>crema piel atópica</code>
            <code>crema piel seca irritada</code>
            <code>crema emoliente</code>
            <code>crema dermatitis atópica</code>
          </div>
        </div>
        <div class="kw-group">
          <div class="kw-group-label">Wash</div>
          <div class="kw-list">
            <code>gel limpiador piel atópica</code>
            <code>gel baño piel atópica</code>
            <code>aceite limpiador corporal</code>
            <code>syndet piel atópica</code>
          </div>
        </div>
        <div class="kw-group">
          <div class="kw-group-label">Oil</div>
          <div class="kw-list">
            <code>aceite piel atópica</code>
            <code>aceite corporal piel seca</code>
            <code>aceite emoliente corporal</code>
            <code>aceite ducha piel seca</code>
          </div>
        </div>
      </div>

    </div>
    </div>
  </details>

  <!-- Charts -->
  <div class="charts-row">
    <div class="card" style="margin:0">
      <h3>Revenue by Marketplace &mdash; 12M (&euro;)</h3>
      <div class="chart-wrap"><canvas id="barChart"></canvas></div>
    </div>
    <div class="card" style="margin:0">
      <h3>Unit Share by Marketplace &mdash; 12M</h3>
      <div class="chart-wrap"><canvas id="pieChart"></canvas></div>
    </div>
  </div>

  <!-- Units Table -->
  <div class="card">
    <h3>Units &amp; Revenue by Marketplace &mdash; 12M</h3>
    <table>
      <thead>
        <tr>
          <th>Marketplace</th>
          <th>Currency</th>
          <th style="text-align:right">30-Day Units</th>
          <th style="text-align:right">Multiplier</th>
          <th style="text-align:right">12M Units (est.)</th>
          <th style="text-align:right">12M Revenue &euro;</th>
          <th style="text-align:right">Share</th>
        </tr>
      </thead>
      <tbody>
{table_rows_html}      </tbody>
    </table>
  </div>

  <!-- Brand Share Pie Charts -->
  <div class="charts-row">
    <div class="card" style="margin:0">
      <h3>Brand Share by Revenue &mdash; 12M</h3>
      <div class="chart-wrap" style="height:340px"><canvas id="brandRevPie"></canvas></div>
    </div>
    <div class="card" style="margin:0">
      <h3>Brand Share by Units &mdash; 12M</h3>
      <div class="chart-wrap" style="height:340px"><canvas id="brandUnitsPie"></canvas></div>
    </div>
  </div>

  <!-- Brand Revenue Heatmap: Brand × Marketplace -->
  <div class="card">
    <h3>Revenue by Brand &amp; Marketplace &mdash; 12M (&euro;)</h3>
    <table class="heatmap" id="brandRevHeatmap">
      <thead>
        <tr>
          <th>Brand</th>
          {heatmap_th_cols}
          <th class="num" style="border-left:2px solid #e2e8f0">Total</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
    <div style="margin-top:10px;font-size:.68rem;color:#64748b">Top 10 marek po łącznym revenue + Other. Zielone komórki = brand dominuje na tym rynku.</div>
  </div>

  <!-- Brand Units Heatmap: Brand × Marketplace -->
  <div class="card">
    <h3>Units by Brand &amp; Marketplace &mdash; 12M</h3>
    <table class="heatmap" id="brandUnitsHeatmap">
      <thead>
        <tr>
          <th>Brand</th>
          {heatmap_th_cols}
          <th class="num" style="border-left:2px solid #e2e8f0">Total</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

  <!-- Segment Share Pie Charts -->
  <div class="charts-row">
    <div class="card" style="margin:0">
      <h3>Revenue Share by Segment &mdash; 12M (&euro;)</h3>
      <div class="chart-wrap"><canvas id="segRevPie"></canvas></div>
    </div>
    <div class="card" style="margin:0">
      <h3>Unit Share by Segment &mdash; 12M</h3>
      <div class="chart-wrap"><canvas id="segUnitsPie"></canvas></div>
    </div>
  </div>

  <!-- Revenue Heatmap: Segment × Marketplace -->
  <div class="card">
    <h3>Revenue by Segment &amp; Marketplace &mdash; 12M (&euro;)</h3>
    <table class="heatmap" id="revHeatmap">
      <thead>
        <tr>
          <th>Segment</th>
          {heatmap_th_cols}
          <th class="num" style="border-left:2px solid #e2e8f0">Total</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
    <div style="margin-top:10px;display:flex;align-items:center;gap:6px;font-size:.68rem;color:#64748b">
      <span>Low</span>
      <div style="display:flex;gap:1px">
        <span style="width:18px;height:10px;background:#eff6ff;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#bfdbfe;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#93c5fd;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#3b82f6;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#1d4ed8;border-radius:2px;display:inline-block"></span>
      </div>
      <span>High</span>
    </div>
  </div>

  <!-- Units Heatmap: Segment × Marketplace -->
  <div class="card">
    <h3>Units by Segment &amp; Marketplace &mdash; 12M</h3>
    <table class="heatmap" id="unitsHeatmap">
      <thead>
        <tr>
          <th>Segment</th>
          {heatmap_th_cols}
          <th class="num" style="border-left:2px solid #e2e8f0">Total</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
    <div style="margin-top:10px;display:flex;align-items:center;gap:6px;font-size:.68rem;color:#64748b">
      <span>Low</span>
      <div style="display:flex;gap:1px">
        <span style="width:18px;height:10px;background:#eff6ff;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#bfdbfe;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#93c5fd;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#3b82f6;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#1d4ed8;border-radius:2px;display:inline-block"></span>
      </div>
      <span>High</span>
    </div>
  </div>

  <div class="note">
    <strong>Źródło danych:</strong> Helium 10 X-Ray &mdash; snapshot 30-dniowy (2026-04-15), dane zmerge'owane i odduplikowane per rynek, odfiltrowane do produktów z przychodem &ge;&euro;1 000 w ciągu ostatnich 30 dni. Metryki 30-dniowe zostały przeskalowane na 12 miesięcy przez prosty mnożnik ×12 (bez korekty sezonowości).
    <br><br>
    <strong>Segmentacja:</strong> każdy produkt dostał etykietę na podstawie jego listingu SP-API (tytuł + bullet points + opis). W agregacji dashboardu uwzględniamy wyłącznie trzy kategorie formy: <strong>Cream</strong> (kremy, balsamy, lotiony, maści), <strong>Wash</strong> (żele, emulsje i olejki do mycia, także pod prysznic) oraz <strong>Oil</strong> (olejki do pielęgnacji ciała). Dwie pozostałe etykiety są celowo wyłączone z liczb powyżej:
    <br><br>
    &bull; <strong>&bdquo;Check&rdquo;</strong> &mdash; produkty, których listing zawiera wprawdzie sygnały niszy dermo (sucha / atopowa / podrażniona skóra), ale nie zawiera wyraźnego słowa kluczowego określającego formę w tytule, LUB produkty, gdzie w ogóle nie ma mocnego sygnału skóry atopowej — czyli klasyczne kremy na suchą skórę od masowych marek jak Nivea, Vaseline czy Palmer's, które są kierowane do zdrowej, lecz przesuszonej skóry, a nie do skóry atopowej. Te wiersze są flagowane do ręcznej weryfikacji przez zespół, żeby nie zanieczyszczały obrazu niszy.
    <br><br>
    &bull; <strong>&bdquo;Other&rdquo;</strong> &mdash; produkty, które jednoznacznie leżą poza zakresem analizy: szampony dla zwierząt, balsamy do ust, kosmetyki do włosów i skóry głowy, kremy przeciwsłoneczne (SPF), dezodoranty i produkty anti-age. Nawet jeśli zawierają frazy typu &bdquo;wrażliwa skóra&rdquo;, nie pasują do żadnego z trzech segmentów kategorii dermo-pielęgnacyjnej dla skóry atopowej.
    <br><br>
    <strong>Rynki w analizie:</strong> Niemcy (słowo kluczowe: Neurodermitis), Francja (peau atopique), Włochy (pelle atopica), Hiszpania (piel atópica). Wielka Brytania nie jest częścią tej analizy.
  </div>

</div>

<script>
Chart.register(ChartDataLabels);

const LABELS = {json.dumps(labels)};
const REVENUE = {revenue_arr};
const UNITS = {units_arr};
const COLORS = {json.dumps(colors)};

// Bar chart — Revenue by Marketplace
new Chart(document.getElementById('barChart'), {{
  type: 'bar',
  data: {{ labels: LABELS, datasets: [{{ data: REVENUE, backgroundColor: COLORS, borderRadius: 4, borderSkipped: false }}] }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{ callbacks: {{ label: ctx => ' €' + ctx.parsed.y.toLocaleString('en-EU',{{maximumFractionDigits:0}}) }} }},
      datalabels: {{
        anchor:'end', align:'end',
        formatter: v => '€' + (v>=1e6?(v/1e6).toFixed(1)+'M':(v/1e3).toFixed(0)+'K'),
        font:{{size:11,weight:'600'}}, color:'#1e293b'
      }}
    }},
    layout: {{ padding: {{ top: 22 }} }},
    scales: {{
      x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 12 }} }} }},
      y: {{ grid: {{ color: '#e2e8f0' }}, ticks: {{ callback: v => '€' + (v>=1e6?(v/1e6).toFixed(1)+'M':(v/1e3).toFixed(0)+'K') }} }}
    }}
  }}
}});

// Doughnut — Unit share by Marketplace
new Chart(document.getElementById('pieChart'), {{
  type: 'doughnut',
  data: {{ labels: LABELS, datasets: [{{ data: UNITS, backgroundColor: COLORS, borderWidth: 2, borderColor: '#fff' }}] }},
  options: {{
    responsive: true, maintainAspectRatio: false, cutout: '52%',
    plugins: {{
      legend: {{
        position:'bottom',
        labels: {{
          font:{{size:11}}, padding:10, boxWidth:12, boxHeight:12,
          generateLabels: chart => {{
            const total = UNITS.reduce((a,b)=>a+b,0);
            return LABELS.map((label,i) => {{
              const pct = (UNITS[i]/total*100).toFixed(1);
              return {{ text: label + '  ' + pct + '%', fillStyle: COLORS[i], strokeStyle: COLORS[i], lineWidth:0, index:i, hidden:false }};
            }});
          }}
        }}
      }},
      tooltip: {{ callbacks: {{ label: ctx => {{ const pct=(ctx.parsed/UNITS.reduce((a,b)=>a+b,0)*100).toFixed(1); return ' '+ctx.parsed.toLocaleString()+' units ('+pct+'%)'; }} }} }},
      datalabels: {{
        display: ctx => (ctx.dataset.data[ctx.dataIndex] / UNITS.reduce((a,b)=>a+b,0)) > 0.05,
        formatter: v => (v/UNITS.reduce((a,b)=>a+b,0)*100).toFixed(1) + '%',
        color: '#fff', font: {{ size: 11, weight: '700' }}
      }}
    }}
  }}
}});

// === Brand pies (top 12 + Other, across all 4 markets combined) ===
const BRAND_REV_LABELS  = {json.dumps(brand_rev_labels)};
const BRAND_REV_VALUES  = {brand_rev_values};
const BRAND_UNITS_LABELS = {json.dumps(brand_units_labels)};
const BRAND_UNITS_VALUES = {brand_units_values};
const BRAND_COLORS = {json.dumps(BRAND_PALETTE)};

function brandPie(id, labels, values, fmtVal) {{
  const total = values.reduce((a,b)=>a+b,0);
  new Chart(document.getElementById(id), {{
    type: 'doughnut',
    data: {{ labels: labels, datasets: [{{ data: values, backgroundColor: BRAND_COLORS, borderWidth: 2, borderColor: '#fff' }}] }},
    options: {{
      responsive: true, maintainAspectRatio: false, cutout: '52%',
      plugins: {{
        legend: {{
          position: 'right',
          labels: {{
            font:{{size:10}}, padding:6, boxWidth:10, boxHeight:10,
            generateLabels: chart => labels.map((label,i) => {{
              const pct = (values[i]/total*100).toFixed(1);
              return {{ text: label + '  ' + pct + '%', fillStyle: BRAND_COLORS[i % BRAND_COLORS.length], strokeStyle: BRAND_COLORS[i % BRAND_COLORS.length], lineWidth:0, index:i, hidden:false }};
            }})
          }}
        }},
        tooltip: {{ callbacks: {{ label: ctx => {{ const pct=(ctx.parsed/total*100).toFixed(1); return ' '+fmtVal(ctx.parsed)+' ('+pct+'%)'; }} }} }},
        datalabels: {{
          display: ctx => (ctx.dataset.data[ctx.dataIndex]/total) > 0.03,
          formatter: v => (v/total*100).toFixed(1)+'%',
          color: '#fff', font: {{ size: 10, weight: '700' }}
        }}
      }}
    }}
  }});
}}
brandPie('brandRevPie',   BRAND_REV_LABELS,   BRAND_REV_VALUES,   v => '€'+(v>=1e6?(v/1e6).toFixed(1)+'M':(v/1e3).toFixed(0)+'K'));
brandPie('brandUnitsPie', BRAND_UNITS_LABELS, BRAND_UNITS_VALUES, v => v>=1e6?(v/1e6).toFixed(1)+'M':(v/1e3).toFixed(1)+'K');

// === Heatmap data: Segment × Marketplace ===
const SEG_DATA = {seg_data_json};
const SEG_NAMES = {json.dumps(SEGMENTS)};
const SEG_COLORS = {json.dumps([SEGMENT_COLORS[s] for s in SEGMENTS])};
const HM_COLORS = ['#eff6ff','#bfdbfe','#93c5fd','#3b82f6','#1d4ed8'];
const HM_TEXT   = ['#1e40af','#1e40af','#1e3a5f','#ffffff','#ffffff'];

function hmColor(val, max) {{
  if (val === 0) return {{ bg: '#f8fafc', fg: '#94a3b8' }};
  const idx = Math.min(4, Math.floor((val / max) * 4.99));
  return {{ bg: HM_COLORS[idx], fg: HM_TEXT[idx] }};
}}
function fmtRev(v) {{
  if (v === 0) return '—';
  if (v >= 1e6) return '€' + (v/1e6).toFixed(1) + 'M';
  return '€' + (v/1e3).toFixed(0) + 'K';
}}
function fmtUnits(v) {{
  if (v === 0) return '—';
  if (v >= 1e6) return (v/1e6).toFixed(1) + 'M';
  return (v/1e3).toFixed(1) + 'K';
}}

function buildHeatmap(tableId, field, fmtFn) {{
  const tbody = document.querySelector('#' + tableId + ' tbody');
  let allVals = [];
  SEG_NAMES.forEach(s => SEG_DATA[s][field].forEach(v => {{ if (v > 0) allVals.push(v); }}));
  const maxVal = allVals.length ? Math.max(...allVals) : 1;

  SEG_NAMES.forEach(seg => {{
    const vals = SEG_DATA[seg][field];
    const total = vals.reduce((a,b)=>a+b,0);
    const tr = document.createElement('tr');
    tr.innerHTML = '<td class="seg-label">' + seg + '</td>';
    vals.forEach(v => {{
      const c = hmColor(v, maxVal);
      tr.innerHTML += '<td class="hm" style="background:'+c.bg+';color:'+c.fg+'">'+fmtFn(v)+'</td>';
    }});
    tr.innerHTML += '<td class="hm-total">' + fmtFn(total) + '</td>';
    tbody.appendChild(tr);
  }});

  // Total row
  const nCols = LABELS.length;
  const totals = Array(nCols).fill(0).map((_,i) => SEG_NAMES.reduce((s,seg)=>s+SEG_DATA[seg][field][i],0));
  const grandTotal = totals.reduce((a,b)=>a+b,0);
  const tr = document.createElement('tr');
  tr.className = 'total-row';
  tr.innerHTML = '<td class="seg-label">Total</td>';
  totals.forEach(v => {{ tr.innerHTML += '<td class="hm" style="background:#f8fafc;color:#0f2942">'+fmtFn(v)+'</td>'; }});
  tr.innerHTML += '<td class="hm-total">' + fmtFn(grandTotal) + '</td>';
  tbody.appendChild(tr);
}}
buildHeatmap('revHeatmap', 'rev', fmtRev);
buildHeatmap('unitsHeatmap', 'units', fmtUnits);

// === Brand × Marketplace heatmaps ===
const BRAND_HM_DATA = {brand_hm_data_json};
const BRAND_HM_ORDER = {brand_hm_order_json};
function buildBrandHeatmap(tableId, field, fmtFn) {{
  const tbody = document.querySelector('#' + tableId + ' tbody');
  let allVals = [];
  BRAND_HM_ORDER.forEach(b => BRAND_HM_DATA[b][field].forEach(v => {{ if (v > 0) allVals.push(v); }}));
  const maxVal = allVals.length ? Math.max(...allVals) : 1;
  BRAND_HM_ORDER.forEach(brand => {{
    const vals = BRAND_HM_DATA[brand][field];
    const total = vals.reduce((a,b)=>a+b,0);
    const tr = document.createElement('tr');
    tr.innerHTML = '<td class="seg-label">' + brand + '</td>';
    vals.forEach(v => {{
      const c = hmColor(v, maxVal);
      tr.innerHTML += '<td class="hm" style="background:'+c.bg+';color:'+c.fg+'">'+fmtFn(v)+'</td>';
    }});
    tr.innerHTML += '<td class="hm-total">' + fmtFn(total) + '</td>';
    tbody.appendChild(tr);
  }});
  const nCols = LABELS.length;
  const totals = Array(nCols).fill(0).map((_,i) => BRAND_HM_ORDER.reduce((s,b)=>s+BRAND_HM_DATA[b][field][i],0));
  const grandTotal = totals.reduce((a,b)=>a+b,0);
  const tr = document.createElement('tr');
  tr.className = 'total-row';
  tr.innerHTML = '<td class="seg-label">Total</td>';
  totals.forEach(v => {{ tr.innerHTML += '<td class="hm" style="background:#f8fafc;color:#0f2942">'+fmtFn(v)+'</td>'; }});
  tr.innerHTML += '<td class="hm-total">' + fmtFn(grandTotal) + '</td>';
  tbody.appendChild(tr);
}}
buildBrandHeatmap('brandRevHeatmap',   'rev',   fmtRev);
buildBrandHeatmap('brandUnitsHeatmap', 'units', fmtUnits);

// === Segment pie charts ===
const SEG_REV_TOTALS = SEG_NAMES.map(s => SEG_DATA[s].rev.reduce((a,b)=>a+b,0));
const SEG_UNIT_TOTALS = SEG_NAMES.map(s => SEG_DATA[s].units.reduce((a,b)=>a+b,0));

function segPie(id, data, fmtVal) {{
  const total = data.reduce((a,b)=>a+b,0);
  new Chart(document.getElementById(id), {{
    type: 'doughnut',
    data: {{ labels: SEG_NAMES, datasets: [{{ data, backgroundColor: SEG_COLORS, borderWidth: 2, borderColor: '#fff' }}] }},
    options: {{
      responsive: true, maintainAspectRatio: false, cutout: '52%',
      plugins: {{
        legend: {{
          position:'bottom',
          labels: {{
            font:{{size:11}}, padding:10, boxWidth:12, boxHeight:12,
            generateLabels: chart => SEG_NAMES.map((label,i) => {{
              const pct = (data[i]/total*100).toFixed(1);
              return {{ text: label+'  '+pct+'%', fillStyle: SEG_COLORS[i], strokeStyle: SEG_COLORS[i], lineWidth:0, index:i, hidden:false }};
            }})
          }}
        }},
        tooltip: {{ callbacks: {{ label: ctx => {{ const pct=(ctx.parsed/total*100).toFixed(1); return ' '+fmtVal(ctx.parsed)+' ('+pct+'%)'; }} }} }},
        datalabels: {{
          display: ctx => (ctx.dataset.data[ctx.dataIndex]/total) > 0.05,
          formatter: v => (v/total*100).toFixed(1)+'%',
          color: '#fff', font: {{ size: 11, weight: '700' }}
        }}
      }}
    }}
  }});
}}
segPie('segRevPie', SEG_REV_TOTALS, v => '€'+(v>=1e6?(v/1e6).toFixed(1)+'M':(v/1e3).toFixed(0)+'K'));
segPie('segUnitsPie', SEG_UNIT_TOTALS, v => v>=1e6?(v/1e6).toFixed(1)+'M':(v/1e3).toFixed(1)+'K');
</script>
</body>
</html>
'''

out_path = os.path.join(BASE, 'index.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(HTML)
print(f'\nindex.html: {os.path.getsize(out_path):,} bajtów')
print(f'Total 12M revenue (Cream+Wash+Oil): €{total_rev12m:,.0f}')
print(f'Total 12M units:   {total_units12m:,}')
for s in SEGMENTS:
    rev = sum(data_by_market[m["code"]]["per_seg"][s]["rev12m"] for m in MARKETS)
    units = sum(data_by_market[m["code"]]["per_seg"][s]["units12m"] for m in MARKETS)
    print(f'  {s}: €{rev:,.0f}  ·  {units:,} szt')
