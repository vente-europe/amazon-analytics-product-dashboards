"""
Buduje standalone index.html dla moth-topline (topline, 5 rynków UK/DE/ES/FR/IT).

SKELETON — skopiowany z atopic-skin-topline. TODO przed użyciem:
  1. Wrzuć X-Ray CSV do data/x-ray/{CODE}/Moth-{CODE}.csv (5 rynków)
  2. Zmień SEGMENTS na właściwe segmenty rynku moli (np. Pheromone trap,
     Sticky trap, Spray, Cedar/Lavender repellent)
  3. Wpisz prawdziwe URL-e Google Sheets w XRAY_LINKS (obecnie '#')

Czyta Moth-{CODE}.csv z data/x-ray/{CODE}/, filtruje do zdefiniowanych
SEGMENTS, agreguje 30d revenue + units per rynek i per (segment × rynek),
projektuje 12M jako 30d × 12, i składa samowystarczalny HTML.
"""
import csv, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))

# Rynki w kolejności wskazanej przez użytkownika: UK, DE, ES, FR, IT
MARKETS = [
    {'code': 'UK', 'name': 'United Kingdom', 'name_pl': 'Wielka Brytania', 'flag': '🇬🇧', 'color': '#dc2626'},
    {'code': 'DE', 'name': 'Germany',        'name_pl': 'Niemcy',          'flag': '🇩🇪', 'color': '#2563eb'},
    {'code': 'ES', 'name': 'Spain',          'name_pl': 'Hiszpania',       'flag': '🇪🇸', 'color': '#d97706'},
    {'code': 'FR', 'name': 'France',         'name_pl': 'Francja',         'flag': '🇫🇷', 'color': '#0891b2'},
    {'code': 'IT', 'name': 'Italy',          'name_pl': 'Włochy',          'flag': '🇮🇹', 'color': '#7c3aed'},
]

SEGMENTS = ['Physical Trap', 'Killer Spray', 'Repellent']
SEGMENT_COLORS = {
    'Physical Trap': '#2563eb',  # niebieski — dominujący segment (sticky/pheromone/light)
    'Killer Spray':  '#dc2626',  # czerwony — agresywne insektycydy
    'Repellent':     '#16a34a',  # zielony — naturalne (lawenda/cedr/saszetki)
}

# Linki do Google Sheets dla każdego rynku — TODO: wstaw prawdziwe URL-e
XRAY_LINKS = {
    'UK': '#',
    'DE': '#',
    'ES': '#',
    'FR': '#',
    'IT': '#',
}

# Mnożnik 30d → 12M. Topline używa flat ×12 (prosty, bez sezonowości).
# Dla szczegółowego dashboardu można potem podmienić na sezonalność.
MULTIPLIER = 12

def numv(v):
    """Parsuje liczbę z CSV w angielskim formacie Helium 10.
    H10 eksportuje: przecinek = separator tysięcy, kropka = dziesiętna.
    Przykłady: '7,543' → 7543, '78,977.16' → 78977.16, '10.48' → 10.48.
    """
    if v is None: return 0.0
    s = str(v).strip()
    if not s or s.lower() == 'nan': return 0.0
    # Usuń symbole walut, spacje, wszystko poza cyframi, . , -
    s = re.sub(r'[^\d.,-]', '', s)
    if not s: return 0.0
    # Przecinki w H10 to zawsze separator tysięcy — usuwamy je
    s = s.replace(',', '')
    try: return float(s)
    except: return 0.0

def load_market(code):
    """Zwraca listę produktów (dict) dla danego rynku, tylko z segmentem Cream/Wash/Oil."""
    path = os.path.join(BASE, 'data', 'x-ray', code, f'Moth-{code}.csv')
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
                'price':    price,
                'brand':    (row.get('Brand') or 'Unknown').strip() or 'Unknown',
                'title':    (row.get('Product Details') or '').strip()[:180],
                'rating':   numv(row.get('Ratings')),
                'reviews':  int(numv(row.get('Review Count'))),
                'bsr':      int(numv(row.get('BSR'))),
            })
    return rows

# ── Filtruj rynki tylko do tych, które mają dane (Moth-{CODE}.csv exists) ──
MARKETS = [m for m in MARKETS if os.path.exists(os.path.join(BASE, 'data', 'x-ray', m['code'], f'Moth-{m["code"]}.csv'))]
print(f'Active markets: {[m["code"] for m in MARKETS]}')

# ── Zbierz dane dla wszystkich rynków ───────────────────────────────────
data_by_market = {}
# Globalny agregat marek (wszystkie rynki razem) do pie charts poniżej tabeli
global_brand = {}  # brand -> {'rev12m': X, 'units12m': Y}
# Raw product rows per market — do top 10 per segment tables
market_rows = {}
for m in MARKETS:
    rows = load_market(m['code'])
    market_rows[m['code']] = rows
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
    rows = market_rows[m['code']]
    for r in rows:
        bm = brand_market.setdefault(r['brand'], {c['code']: {'rev12m': 0, 'units12m': 0} for c in MARKETS})
        bm[m['code']]['rev12m']   += round(r['rev30d']   * MULTIPLIER)
        bm[m['code']]['units12m'] += round(r['sales30d'] * MULTIPLIER)

# ── Top 10 produktów per segment per rynek ──────────────────────────────
# Struktura: {market_code: {segment: [top10 products, ranked by 30d revenue]}}
top_products = {}
for m in MARKETS:
    rows = market_rows[m['code']]
    by_seg = {s: [] for s in SEGMENTS}
    for r in rows:
        if r['segment'] in by_seg:
            by_seg[r['segment']].append(r)
    top_products[m['code']] = {}
    for s in SEGMENTS:
        seg_rows = sorted(by_seg[s], key=lambda x: x['rev30d'], reverse=True)[:10]
        # Dla każdego produktu projektuj 12M
        top_products[m['code']][s] = [{
            'asin':   r['asin'],
            'brand':  r['brand'],
            'title':  r['title'],
            'price':  round(r['price'], 2),
            'rev30d': round(r['rev30d']),
            'rev12m': round(r['rev30d'] * MULTIPLIER),
            'units30d': int(round(r['sales30d'])),
            'units12m': int(round(r['sales30d'] * MULTIPLIER)),
            'rating': r['rating'],
            'reviews': r['reviews'],
            'bsr':    r['bsr'],
        } for r in seg_rows]

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

# Top products — przekazujemy do JS jako jeden obiekt
top_products_json = json.dumps(top_products, ensure_ascii=False, indent=2)
# Flat lista dla advanced view (wszystkie 120 produktów z dodanym market+segment)
top_products_flat = []
for mcode, by_seg in top_products.items():
    for seg, prods in by_seg.items():
        for p in prods:
            top_products_flat.append({**p, 'market': mcode, 'segment': seg})
top_products_flat_json = json.dumps(top_products_flat, ensure_ascii=False)

# Lista kodów rynków w posortowanej kolejności
market_codes_json = json.dumps([m['code'] for m in MARKETS])

# ── Automatyczne wyliczenie insightów do summary box ────────────────────
# Sortowanie rynków po 12M revenue
markets_ranked = sorted(
    [(m, data_by_market[m['code']]) for m in MARKETS],
    key=lambda x: x[1]['rev12m'], reverse=True
)
top_mkt, top_mkt_data = markets_ranked[0]
top_mkt_share = top_mkt_data['rev12m'] / total_rev12m * 100
m2 = markets_ranked[1] if len(markets_ranked) > 1 else markets_ranked[0]

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

# Pre-rendered HTML fragment for the markets-ranked sentence (avoids quote nesting in f-string)
markets_ranked_html = ' &middot; '.join(
    f'<strong>{m["name"]}</strong> &euro;{d["rev12m"]/1e6:.1f}M'
    for m, d in markets_ranked
)

# Top-products section pill HTML (dynamic over MARKETS / SEGMENTS)
market_pills_html = '\n      '.join(
    f'<button class="tp-pill{" active" if i == 0 else ""}" data-mkt="{m["code"]}">{m["flag"]} {m["code"]}</button>'
    for i, m in enumerate(MARKETS)
)
advanced_market_pills_html = '\n        '.join(
    f'<button class="tp-pill" data-adv-mkt="{m["code"]}">{m["code"]}</button>'
    for m in MARKETS
)
advanced_segment_pills_html = '\n        '.join(
    f'<button class="tp-pill" data-adv-seg="{s}">{s}</button>'
    for s in SEGMENTS
)

# ── Szablon HTML (samowystarczalny, bez fetch) ──────────────────────────
HTML = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Moth Control &mdash; International Markets (12M)</title>
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
/* Top products block */
.tp-block{{background:#fff;border-radius:8px;padding:18px 22px;box-shadow:0 1px 3px rgba(0,0,0,.07);margin-bottom:24px;border-left:4px solid #7c3aed}}
.tp-block h2{{font-size:.85rem;font-weight:700;color:#0f2942;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;display:flex;align-items:center;gap:8px}}
.tp-block h2::before{{content:'';display:inline-block;width:22px;height:2px;background:#7c3aed}}
.tp-block .tp-intro{{font-size:.75rem;color:#475569;line-height:1.5;margin-bottom:14px}}
.tp-pills{{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;align-items:center}}
.tp-pills .label{{font-size:.7rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.04em;margin-right:4px}}
.tp-pill{{padding:7px 14px;border:2px solid #cbd5e1;background:#fff;border-radius:18px;cursor:pointer;font-size:.75rem;font-weight:600;color:#475569;transition:all .15s}}
.tp-pill:hover{{border-color:#94a3b8;color:#1e293b}}
.tp-pill.active{{background:#0f2942;border-color:#0f2942;color:#fff}}
.tp-seg-title{{font-size:.78rem;font-weight:700;color:#0f2942;margin:18px 0 8px;display:flex;align-items:center;gap:8px;padding-bottom:4px;border-bottom:1px solid #e2e8f0}}
.tp-seg-title .badge{{font-size:.62rem;background:#f1f5f9;color:#475569;padding:2px 8px;border-radius:10px;font-weight:600;text-transform:uppercase;letter-spacing:.04em}}
.tp-table{{width:100%;border-collapse:collapse;font-size:.74rem}}
.tp-table th{{background:#f8fafc;text-align:left;padding:7px 8px;font-weight:600;color:#475569;font-size:.66rem;text-transform:uppercase;letter-spacing:.04em;border-bottom:2px solid #e2e8f0;cursor:pointer;user-select:none}}
.tp-table th.sortable:hover{{background:#f1f5f9}}
.tp-table th.sortable::after{{content:' ⇅';color:#cbd5e1;font-size:.7rem}}
.tp-table th.sort-asc::after{{content:' ▲';color:#0f2942}}
.tp-table th.sort-desc::after{{content:' ▼';color:#0f2942}}
.tp-table td{{padding:7px 8px;border-bottom:1px solid #f1f5f9;vertical-align:top}}
.tp-table tr:hover td{{background:#f8fafc}}
.tp-table td.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.tp-table td.title{{max-width:380px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.tp-table td.asin a{{display:inline-flex;align-items:center;gap:3px;background:#dbeafe;color:#1d4ed8;padding:2px 7px;border-radius:3px;font-size:.68rem;font-family:ui-monospace,Menlo,Consolas,monospace;font-weight:600;text-decoration:none;transition:background .12s}}
.tp-table td.asin a:hover{{background:#bfdbfe;text-decoration:underline}}
.tp-table td.asin a::after{{content:'↗';font-size:.65rem;opacity:.7}}
.tp-advanced{{margin-top:20px;padding-top:18px;border-top:1px dashed #e2e8f0}}
.tp-advanced summary{{cursor:pointer;font-size:.75rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.04em;padding:6px 0;list-style:none;display:flex;align-items:center;gap:8px}}
.tp-advanced summary::-webkit-details-marker{{display:none}}
.tp-advanced summary::before{{content:'▸';display:inline-block;transition:transform .2s;font-size:.9rem;color:#94a3b8}}
.tp-advanced[open] summary::before{{transform:rotate(90deg)}}
.tp-advanced summary:hover{{color:#0f2942}}
</style>
</head>
<body>

<header>
  <div class="titles">
    <h1>Moth Control &mdash; International Markets</h1>
    <span>12-Month Projection (30-day &times; 12) &nbsp;|&nbsp; Data: Helium 10 X-Ray (2026-05-08)</span>
  </div>
  <div class="xray-btn-row">
{xray_buttons}  </div>
</header>

<div class="main">

  <!-- KPI Row -->
  <div class="kpi-row">
    <div class="kpi">
      <div class="kpi-v">&euro;{total_rev12m/1e6:.1f}M</div>
      <div class="kpi-l">Total 12M Revenue ({' + '.join(SEGMENTS)})</div>
    </div>
    <div class="kpi">
      <div class="kpi-v">{total_units12m:,}</div>
      <div class="kpi-l">Total 12M Units Sold (all segments)</div>
    </div>
    <div class="kpi">
      <div class="kpi-v">{len(MARKETS)} Markets</div>
      <div class="kpi-l">{' &bull; '.join(m['code'] for m in MARKETS)}</div>
    </div>
  </div>


  <!-- Executive summary — auto-generated from data -->
  <details class="summary">
    <summary>Summary &mdash; key findings (12M) <span class="hint">click to expand</span></summary>
    <div class="summary-inner">
    <div class="summary-cols">

      <div class="summary-col">
        <h3>Markets</h3>
        <p>The moth-control category leader is <strong>{top_mkt["name"]}</strong> with <strong>&euro;{top_mkt_data["rev12m"]/1e6:.1f}M</strong> in 12M revenue, accounting for <strong>{top_mkt_share:.0f}%</strong> of the analyzed market &mdash; <strong>{top_mkt_data["rev12m"]/m2[1]["rev12m"]:.1f}&times;</strong> the next market.</p>
        <p>Ranked: {markets_ranked_html}.</p>
      </div>

      <div class="summary-col">
        <h3>Segments</h3>
        <p>Across {len(MARKETS)} markets, the leading segment by revenue is <strong>{max(SEGMENTS, key=lambda s: seg_totals_rev[s])}</strong> with <strong>{max(seg_rev_shares.values()):.0f}%</strong> share. Killer Spray products typically command higher unit prices; physical traps dominate by SKU count; repellents (lavender, cedar, mothballs) anchor the natural-products tier.</p>
        <p>Total ASINs analyzed (after &ge;&euro;1k/30d filter): <strong>{total_asins}</strong>.</p>
      </div>

      <div class="summary-col">
        <h3>Brands &amp; Pricing</h3>
        <p>The category is {"highly concentrated" if top3_brand_share >= 40 else "moderately fragmented"} &mdash; the top three brands account for <strong>{top3_brand_share:.0f}%</strong> of revenue. Leader: <strong>{top_brand_name}</strong> with <strong>{top_brand_share:.0f}%</strong> share (&euro;{top_brand_data["rev12m"]/1e6:.1f}M). <strong>{n_unique_brands}</strong> unique brands compete in this niche.</p>
        <p>Average product price across the category: <strong>&euro;{avg_price_category:.0f}</strong>.</p>
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

  <!-- Top 10 produktów per segment per rynek -->
  <div class="tp-block">
    <h2>Top 10 products per segment per market</h2>
    <p class="tp-intro">Pick a market below to see the 10 best-selling products in each of the {len(SEGMENTS)} segments ({' / '.join(SEGMENTS)}), sorted by 30-day revenue. Click column headers to re-sort. The advanced view at the bottom shows all products with filters for cross-market comparison.</p>

    <div class="tp-pills">
      <span class="label">Market:</span>
      {market_pills_html}
    </div>

    <div id="tpTables"></div>

    <!-- Advanced view: all markets with filters -->
    <details class="tp-advanced">
      <summary>&#128269; Advanced view &mdash; all products with filters</summary>
      <div class="tp-intro" style="margin-top:10px">Filter by market and segment, sort any column. Useful for cross-market product comparison.</div>
      <div class="tp-pills">
        <span class="label">Market:</span>
        <button class="tp-pill active" data-adv-mkt="All">All</button>
        {advanced_market_pills_html}
      </div>
      <div class="tp-pills">
        <span class="label">Segment:</span>
        <button class="tp-pill active" data-adv-seg="All">All</button>
        {advanced_segment_pills_html}
      </div>
      <div id="tpAdvTable"></div>
    </details>
  </div>

  <div class="note">
    <strong>Data source:</strong> Helium 10 X-Ray &mdash; 30-day snapshot (2026-05-08), merged and deduplicated per market, filtered to products with &ge;&euro;1 000 revenue over the last 30 days. 30-day metrics scaled to 12 months via a flat &times;12 multiplier (no seasonality correction).
    <br><br>
    <strong>Segmentation:</strong> each product received a label based on its Amazon listing (title + bullet points + description, fetched via SP-API). The aggregation includes three category forms: <strong>Physical Trap</strong> (sticky / pheromone / light traps, parasitic-wasp cards), <strong>Killer Spray</strong> (insecticide sprays, foggers, biocides), and <strong>Repellent</strong> (lavender sachets, cedar wood, mothballs, essential-oil based repellents).
    <br><br>
    <strong>Markets in scope:</strong> {' &middot; '.join(f"{m['flag']} {m['name']}" for m in MARKETS)}.
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

// === Top Products Tables ===
const TOP_PRODUCTS = {top_products_json};
const TOP_PRODUCTS_FLAT = {top_products_flat_json};
const TP_MKT_CODES = {market_codes_json};
const TP_SEGMENTS = {json.dumps(SEGMENTS)};

function fmtMoneyInt(v) {{ return '€' + Math.round(v).toLocaleString('en-EU'); }}
function fmtInt(v) {{ return Math.round(v).toLocaleString('en-EU'); }}
function escHtml(s) {{ return String(s || '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]); }}
// Mapa rynek → domena Amazon (dla klikalnych ASIN-ów)
const AMAZON_DOMAIN = {{ DE: 'de', FR: 'fr', IT: 'it', ES: 'es' }};
function asinLink(asin, marketCode) {{
  const dom = AMAZON_DOMAIN[marketCode] || 'de';
  return '<a href="https://www.amazon.' + dom + '/dp/' + encodeURIComponent(asin) + '" target="_blank" rel="noopener">' + escHtml(asin) + '</a>';
}}

// Kolumny tabeli top 10 (główny widok per rynek)
const TP_COLS = [
  {{key:'rank',    label:'#',        num:true,  w:'32px'}},
  {{key:'asin',    label:'ASIN',     num:false, w:'110px'}},
  {{key:'brand',   label:'Brand',    num:false, w:'120px'}},
  {{key:'title',   label:'Title',    num:false, w:'auto', cls:'title'}},
  {{key:'price',   label:'Price',    num:true,  fmt:v=>'€'+v.toFixed(2)}},
  {{key:'rev30d',  label:'Rev 30d',  num:true,  fmt:fmtMoneyInt}},
  {{key:'rev12m',  label:'Rev 12M',  num:true,  fmt:fmtMoneyInt}},
  {{key:'units30d',label:'Units 30d',num:true,  fmt:fmtInt}},
  {{key:'units12m',label:'Units 12M',num:true,  fmt:fmtInt}},
  {{key:'reviews', label:'Reviews',  num:true,  fmt:fmtInt}},
];

function buildTopTable(products, containerId, segLabel, includeMarketCol, fixedMarketCode) {{
  // Sort state per table (stored on element)
  const cols = includeMarketCol ? [{{key:'market',label:'Mkt',num:false,w:'42px'}}, {{key:'segment',label:'Seg',num:false,w:'58px'}}, ...TP_COLS.slice(1)] : TP_COLS;
  let sortKey = includeMarketCol ? 'rev30d' : 'rev30d';
  let sortDir = 'desc';
  const rows = products.map((p, i) => ({{ ...p, rank: i + 1 }}));

  function render() {{
    rows.sort((a, b) => {{
      const va = a[sortKey]; const vb = b[sortKey];
      const na = (typeof va === 'number'); const nb = (typeof vb === 'number');
      if (na && nb) return sortDir === 'asc' ? va - vb : vb - va;
      return sortDir === 'asc' ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
    }});
    // Re-rank after sort
    rows.forEach((r, i) => r.rank = i + 1);
    let html = '<table class="tp-table"><thead><tr>';
    cols.forEach(c => {{
      const cls = c.num ? 'num' : '';
      const sortCls = (c.key === sortKey) ? (sortDir === 'asc' ? 'sortable sort-asc' : 'sortable sort-desc') : 'sortable';
      html += '<th class="' + cls + ' ' + sortCls + '" data-k="' + c.key + '"' + (c.w ? ' style="width:' + c.w + '"' : '') + '>' + c.label + '</th>';
    }});
    html += '</tr></thead><tbody>';
    rows.forEach(r => {{
      html += '<tr>';
      cols.forEach(c => {{
        let cls = c.num ? 'num' : (c.cls || '');
        let val = r[c.key];
        if (c.key === 'asin') {{
          const mkt = fixedMarketCode || r.market || TP_MKT_CODES[0];
          val = asinLink(val, mkt);
          cls = 'asin';
        }}
        else if (c.key === 'title') val = escHtml(val);
        else if (c.key === 'brand') val = escHtml(val);
        else if (c.fmt) val = c.fmt(val || 0);
        else val = escHtml(val);
        html += '<td class="' + cls + '"' + (c.key === 'title' ? ' title="' + escHtml(r.title) + '"' : '') + '>' + val + '</td>';
      }});
      html += '</tr>';
    }});
    html += '</tbody></table>';
    const container = document.getElementById(containerId);
    container.innerHTML = html;
    container.querySelectorAll('th.sortable').forEach(th => {{
      th.onclick = () => {{
        const k = th.dataset.k;
        if (sortKey === k) sortDir = (sortDir === 'asc' ? 'desc' : 'asc');
        else {{ sortKey = k; sortDir = 'desc'; }}
        render();
      }};
    }});
  }}
  render();
}}

// === Main view: 3 sections per selected market ===
let currentMarket = TP_MKT_CODES[0];
function renderTopTablesForMarket(code) {{
  currentMarket = code;
  const wrap = document.getElementById('tpTables');
  let html = '';
  TP_SEGMENTS.forEach((seg, i) => {{
    const n = (TOP_PRODUCTS[code] && TOP_PRODUCTS[code][seg]) ? TOP_PRODUCTS[code][seg].length : 0;
    html += '<div class="tp-seg-title">' + seg + ' <span class="badge">' + n + ' produktów</span></div>';
    html += '<div id="tpTable_' + seg + '"></div>';
  }});
  wrap.innerHTML = html;
  TP_SEGMENTS.forEach(seg => {{
    const prods = (TOP_PRODUCTS[code] && TOP_PRODUCTS[code][seg]) || [];
    if (prods.length === 0) {{
      document.getElementById('tpTable_' + seg).innerHTML = '<p style="font-size:.74rem;color:#94a3b8;padding:8px 0">Brak produktów w tej kategorii dla ' + code + '.</p>';
    }} else {{
      buildTopTable(prods, 'tpTable_' + seg, seg, false, code);
    }}
  }});
}}
document.querySelectorAll('.tp-pill[data-mkt]').forEach(btn => {{
  btn.onclick = () => {{
    document.querySelectorAll('.tp-pill[data-mkt]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderTopTablesForMarket(btn.dataset.mkt);
  }};
}});
renderTopTablesForMarket(TP_MKT_CODES[0]);

// === Advanced view: all 120 products with filters ===
let advMkt = 'All';
let advSeg = 'All';
function renderAdvancedTable() {{
  let filtered = TOP_PRODUCTS_FLAT.slice();
  if (advMkt !== 'All') filtered = filtered.filter(p => p.market === advMkt);
  if (advSeg !== 'All') filtered = filtered.filter(p => p.segment === advSeg);
  if (filtered.length === 0) {{
    document.getElementById('tpAdvTable').innerHTML = '<p style="font-size:.74rem;color:#94a3b8;padding:8px 0">Brak produktów dla wybranego filtra.</p>';
  }} else {{
    buildTopTable(filtered, 'tpAdvTable', 'Advanced', true);
  }}
}}
document.querySelectorAll('.tp-pill[data-adv-mkt]').forEach(btn => {{
  btn.onclick = () => {{
    document.querySelectorAll('.tp-pill[data-adv-mkt]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    advMkt = btn.dataset.advMkt;
    renderAdvancedTable();
  }};
}});
document.querySelectorAll('.tp-pill[data-adv-seg]').forEach(btn => {{
  btn.onclick = () => {{
    document.querySelectorAll('.tp-pill[data-adv-seg]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    advSeg = btn.dataset.advSeg;
    renderAdvancedTable();
  }};
}});
renderAdvancedTable();
</script>
</body>
</html>
'''

out_path = os.path.join(BASE, 'index.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(HTML)
print(f'\nindex.html: {os.path.getsize(out_path):,} bajtów')
print(f'Total 12M revenue ({"+".join(SEGMENTS)}): €{total_rev12m:,.0f}')
print(f'Total 12M units:   {total_units12m:,}')
for s in SEGMENTS:
    rev = sum(data_by_market[m["code"]]["per_seg"][s]["rev12m"] for m in MARKETS)
    units = sum(data_by_market[m["code"]]["per_seg"][s]["units12m"] for m in MARKETS)
    print(f'  {s}: €{rev:,.0f}  ·  {units:,} szt')
