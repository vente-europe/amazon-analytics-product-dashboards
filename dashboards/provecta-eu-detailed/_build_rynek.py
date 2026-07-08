"""
Builds _rynek_topline.html for provecta-eu-detailed Tab 1 (Total Market).

Cross-market topline for the ProVecta pest-control category across 5 EU
Amazon markets (FR, DE, UK, IT, ES). Reads Provecta-{CODE}.csv from
data/x-ray/, dedupes by ASIN per market, projects 12M as 30d x 12, converts
GBP to EUR at 1.195, and emits a self-contained HTML page (visual language:
atopic-skin-topline _build_topline.py, minus all segment elements).

The parent build strips <header>...</header> via regex, so all real content
lives outside the header block.
"""
import csv, os, re, sys, json
sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))

GBP_EUR = 1.195   # GBP -> EUR conversion rate for all cross-market aggregations
MULTIPLIER = 12   # 30d snapshot -> 12M projection

# Markets in fixed display order (by market size): FR, DE, UK, IT, ES
MARKETS = [
    {'code': 'FR', 'name': 'Francja',         'flag': '\U0001F1EB\U0001F1F7', 'color': '#0891b2', 'cur': '€', 'domain': 'fr'},
    {'code': 'DE', 'name': 'Niemcy',          'flag': '\U0001F1E9\U0001F1EA', 'color': '#2563eb', 'cur': '€', 'domain': 'de'},
    {'code': 'UK', 'name': 'Wielka Brytania', 'flag': '\U0001F1EC\U0001F1E7', 'color': '#dc2626', 'cur': '£', 'domain': 'co.uk'},
    {'code': 'IT', 'name': 'Włochy',          'flag': '\U0001F1EE\U0001F1F9', 'color': '#7c3aed', 'cur': '€', 'domain': 'it'},
    {'code': 'ES', 'name': 'Hiszpania',       'flag': '\U0001F1EA\U0001F1F8', 'color': '#d97706', 'cur': '€', 'domain': 'es'},
]

def numv(v):
    """Parses a number from Helium 10 CSV (comma = thousands sep, dot = decimal)."""
    if v is None: return 0.0
    s = str(v).strip()
    if not s or s.lower() == 'nan': return 0.0
    s = re.sub(r'[^\d.,-]', '', s)
    if not s: return 0.0
    s = s.replace(',', '')
    try: return float(s)
    except: return 0.0

anomalies = []

def load_market(m):
    """Returns deduped product list for one market. Prices/revenue converted
    to EUR for aggregation; local price kept for the product table."""
    code = m['code']
    path = os.path.join(BASE, 'data', 'x-ray', f'Provecta-{code}.csv')
    if not os.path.exists(path):
        anomalies.append(f'[{code}] file missing: {path}')
        return []
    fx = GBP_EUR if code == 'UK' else 1.0
    by_asin = {}
    n_raw = n_skipped = 0
    with open(path, encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        price_col = next((k for k in (r.fieldnames or []) if k and 'price' in k.lower()), None)
        if not price_col:
            anomalies.append(f'[{code}] no price column found in header')
            return []
        for row in r:
            n_raw += 1
            asin = (row.get('ASIN') or '').strip()
            price_local = numv(row.get(price_col))
            if not asin or price_local <= 0:
                n_skipped += 1
                continue
            rev30d_local = numv(row.get('ASIN Revenue'))
            units30d = round(rev30d_local / price_local) if price_local > 0 else 0
            prod = {
                'asin': asin,
                'brand': (row.get('Brand') or 'Unknown').strip() or 'Unknown',
                'title': (row.get('Product Details') or '').strip()[:180],
                'price_local': round(price_local, 2),
                'price_eur': round(price_local * fx, 2),
                'rev30d_local': rev30d_local,
                'rev30d_eur': rev30d_local * fx,
                'units30d': units30d,
                'units12m': units30d * MULTIPLIER,
                'rev12m_eur': round(rev30d_local * fx * MULTIPLIER),
                'rating': numv(row.get('Ratings')),
                'reviews': int(numv(row.get('Review Count'))),
                'bsr': int(numv(row.get('BSR'))),
            }
            # Dedupe by ASIN keeping the row with higher ASIN Revenue
            prev = by_asin.get(asin)
            if prev is None or prod['rev30d_local'] > prev['rev30d_local']:
                by_asin[asin] = prod
    n_dupes = n_raw - n_skipped - len(by_asin)
    if n_skipped: anomalies.append(f'[{code}] {n_skipped} rows skipped (no ASIN or no price)')
    if n_dupes:   anomalies.append(f'[{code}] {n_dupes} duplicate ASIN rows removed (kept higher revenue)')
    return list(by_asin.values())

# -- Load all markets ------------------------------------------------------
market_rows = {}
data_by_market = {}
global_brand = {}   # brand -> {'rev12m', 'units12m'} in EUR
for m in MARKETS:
    rows = load_market(m)
    market_rows[m['code']] = rows
    units30d = sum(r['units30d'] for r in rows)
    rev30d   = sum(r['rev30d_eur'] for r in rows)
    units12m = units30d * MULTIPLIER
    rev12m   = round(rev30d * MULTIPLIER)
    for r in rows:
        b = global_brand.setdefault(r['brand'], {'rev12m': 0, 'units12m': 0})
        b['rev12m']   += r['rev12m_eur']
        b['units12m'] += r['units12m']
    data_by_market[m['code']] = {
        'units30d': units30d, 'rev30d': rev30d,
        'units12m': units12m, 'rev12m': rev12m,
        'asin_count': len(rows),
        'avg_price': (rev30d / units30d) if units30d else 0,
    }
    print(f"  [{m['code']}] {len(rows)} ASIN, {units30d:,.0f} units/30d, EUR {rev30d:,.0f}/30d -> EUR {rev12m:,.0f}/12M")

labels      = [m['code'] for m in MARKETS]
bar_labels  = [f"{m['flag']} {m['code']}" for m in MARKETS]
colors      = [m['color'] for m in MARKETS]
revenue_arr = [data_by_market[m['code']]['rev12m']   for m in MARKETS]
units_arr   = [data_by_market[m['code']]['units12m'] for m in MARKETS]
total_rev12m   = sum(revenue_arr)
total_units12m = sum(units_arr)
total_asins    = sum(data_by_market[m['code']]['asin_count'] for m in MARKETS)

# -- Top 10 brands + Other for the global pies ----------------------------
def top_brands(metric, n=10):
    items = sorted(global_brand.items(), key=lambda kv: kv[1][metric], reverse=True)
    top, rest = items[:n], items[n:]
    lab = [b for b, _ in top]
    val = [v[metric] for _, v in top]
    if rest:
        lab.append(f'Pozostałe ({len(rest)})')
        val.append(sum(v[metric] for _, v in rest))
    return lab, val

brand_rev_labels,   brand_rev_values   = top_brands('rev12m')
brand_units_labels, brand_units_values = top_brands('units12m')

# -- Brand x market matrix for heatmaps (top 12 brands + Other) -----------
brand_market = {}
for m in MARKETS:
    for r in market_rows[m['code']]:
        bm = brand_market.setdefault(r['brand'], {c['code']: {'rev12m': 0, 'units12m': 0} for c in MARKETS})
        bm[m['code']]['rev12m']   += r['rev12m_eur']
        bm[m['code']]['units12m'] += r['units12m']

top12 = sorted(global_brand.items(), key=lambda kv: kv[1]['rev12m'], reverse=True)[:12]
hm_brand_names = [b for b, _ in top12]
hm_rest_brands = set(global_brand.keys()) - set(hm_brand_names)

def hm_row(brand_name, metric):
    if brand_name == 'Other':
        return [sum(brand_market[b][m['code']][metric] for b in hm_rest_brands) for m in MARKETS]
    bm = brand_market.get(brand_name, {})
    return [bm.get(m['code'], {}).get(metric, 0) for m in MARKETS]

brand_hm_data = {}
for b in hm_brand_names:
    brand_hm_data[b] = {'rev': hm_row(b, 'rev12m'), 'units': hm_row(b, 'units12m')}
if hm_rest_brands:
    brand_hm_data[f'Pozostałe ({len(hm_rest_brands)})'] = {'rev': hm_row('Other', 'rev12m'), 'units': hm_row('Other', 'units12m')}
hm_brand_order = list(brand_hm_data.keys())

BRAND_PALETTE = [
    '#2563eb','#dc2626','#0891b2','#d97706','#7c3aed','#16a34a',
    '#db2777','#0284c7','#ca8a04','#059669','#4f46e5',
    '#94a3b8',  # Other
]

# -- Top 10 products per market + flat all-products list ------------------
top_products = {}
all_products_flat = []
for m in MARKETS:
    rows = sorted(market_rows[m['code']], key=lambda r: r['rev30d_eur'], reverse=True)
    def pack(r):
        return {
            'asin': r['asin'], 'brand': r['brand'], 'title': r['title'],
            'price': r['price_local'], 'cur': m['cur'],
            'units30d': int(r['units30d']), 'units12m': int(r['units12m']),
            'rev12m': int(r['rev12m_eur']), 'reviews': r['reviews'],
        }
    top_products[m['code']] = [pack(r) for r in rows[:10]]
    for r in rows:
        all_products_flat.append({**pack(r), 'market': m['code']})

top_products_json = json.dumps(top_products, ensure_ascii=False)
all_products_json = json.dumps(all_products_flat, ensure_ascii=False)
market_codes_json = json.dumps(labels)
amazon_domains_json = json.dumps({m['code']: m['domain'] for m in MARKETS})

# -- Executive summary insights (Polish) -----------------------------------
markets_ranked = sorted([(m, data_by_market[m['code']]) for m in MARKETS], key=lambda x: x[1]['rev12m'], reverse=True)
top_mkt, top_mkt_d = markets_ranked[0]
top_mkt_share = top_mkt_d['rev12m'] / total_rev12m * 100
m2, m3, m4, m5 = markets_ranked[1], markets_ranked[2], markets_ranked[3], markets_ranked[4]

brand_ranked = sorted(global_brand.items(), key=lambda kv: kv[1]['rev12m'], reverse=True)
top_brand_name, top_brand_d = brand_ranked[0]
top_brand_share  = top_brand_d['rev12m'] / total_rev12m * 100
top3_brand_share = sum(b[1]['rev12m'] for b in brand_ranked[:3]) / total_rev12m * 100
top10_brand_share = sum(b[1]['rev12m'] for b in brand_ranked[:10]) / total_rev12m * 100
n_unique_brands = len(global_brand)
avg_price_category = total_rev12m / total_units12m if total_units12m else 0

# Biggest brand per market
biggest_brand = {}
for m in MARKETS:
    agg = {}
    for r in market_rows[m['code']]:
        agg[r['brand']] = agg.get(r['brand'], 0) + r['rev12m_eur']
    bb = max(agg.items(), key=lambda kv: kv[1]) if agg else ('n/a', 0)
    biggest_brand[m['code']] = {'name': bb[0], 'rev': bb[1], 'share': (bb[1] / data_by_market[m['code']]['rev12m'] * 100) if data_by_market[m['code']]['rev12m'] else 0}

ranking_str = ', '.join(f"{mm['name']} €{dd['rev12m']/1e6:.2f}M ({dd['rev12m']/total_rev12m*100:.0f}%)" for mm, dd in markets_ranked)
avg_price_str = ' · '.join(f"{m['code']} €{data_by_market[m['code']]['avg_price']:.2f}" for m in MARKETS)
biggest_brand_str = ' · '.join(f"{m['code']}: {biggest_brand[m['code']]['name']} ({biggest_brand[m['code']]['share']:.0f}%)" for m in MARKETS)

concentration_word = 'silnie skoncentrowana' if top3_brand_share >= 40 else ('umiarkowanie skoncentrowana' if top3_brand_share >= 25 else 'rozdrobniona')

summary_markets_1 = (f"Liderem kategorii jest <strong>{top_mkt['name']}</strong> z <strong>€{top_mkt_d['rev12m']/1e6:.2f}M</strong> "
                     f"prognozowanego rocznego przychodu, co daje <strong>{top_mkt_share:.0f}%</strong> udziału w łącznej wartości 5 rynków "
                     f"i {top_mkt_d['rev12m']/m2[1]['rev12m']:.1f}x wielkości drugiego rynku w kolejności.")
summary_markets_2 = (f"Pełny ranking (przychód 12M): {ranking_str}. "
                     f"Łącznie pięć rynków generuje <strong>€{total_rev12m/1e6:.1f}M</strong> rocznie "
                     f"w ramach <strong>{total_asins}</strong> analizowanych ASIN-ów.")
summary_brands_1  = (f"Kategoria jest <strong>{concentration_word}</strong>: top 3 marki odpowiadają za <strong>{top3_brand_share:.0f}%</strong>, "
                     f"a top 10 marek za <strong>{top10_brand_share:.0f}%</strong> całego przychodu, "
                     f"przy <strong>{n_unique_brands}</strong> unikalnych markach ogółem.")
summary_brands_2  = (f"Globalnym liderem jest <strong>{top_brand_name}</strong> z udziałem <strong>{top_brand_share:.0f}%</strong> "
                     f"(€{top_brand_d['rev12m']/1e6:.2f}M rocznie). Największa marka na każdym rynku: {biggest_brand_str}.")
summary_price_1   = (f"Średnia cena sprzedaży w całej kategorii wynosi <strong>€{avg_price_category:.2f}</strong> za sztukę. "
                     f"Średnia cena per rynek: {avg_price_str}.")
summary_price_2   = (f"Łączny prognozowany wolumen to <strong>{total_units12m:,}</strong> sztuk rocznie. "
                     f"Dane z UK przeliczono po kursie GBP/EUR {GBP_EUR}; pozostałe rynki rozliczają się natywnie w EUR.")

# Plain-text version of exec summary for stdout sanity check
def strip_tags(s): return re.sub(r'<[^>]+>', '', s)
summary_lines = [strip_tags(x) for x in (summary_markets_1, summary_markets_2, summary_brands_1, summary_brands_2, summary_price_1, summary_price_2)]

heatmap_th_cols = ''.join(f'<th class="num">{m["flag"]} {m["code"]}</th>' for m in MARKETS)
market_pills = ''.join(f'<button class="tp-pill{" active" if i == 0 else ""}" data-mkt="{m["code"]}">{m["flag"]} {m["code"]}</button>\n      ' for i, m in enumerate(MARKETS))
adv_market_pills = '<button class="tp-pill active" data-adv-mkt="All">Wszystkie</button>\n        ' + ''.join(f'<button class="tp-pill" data-adv-mkt="{m["code"]}">{m["code"]}</button>\n        ' for m in MARKETS)

# -- Market table rows ------------------------------------------------------
table_rows_html = ''
for m in MARKETS:
    d = data_by_market[m['code']]
    share = (d['rev12m'] / total_rev12m * 100) if total_rev12m else 0
    cur_note = 'GBP (x1.195)' if m['code'] == 'UK' else 'EUR'
    table_rows_html += f'''        <tr>
          <td><span class="dot" style="background:{m['color']}"></span>{m['flag']} {m['name']} ({m['code']})</td>
          <td>{cur_note}</td>
          <td class="num">{d['asin_count']}</td>
          <td class="num">{d['units30d']:,.0f}</td>
          <td class="num">{MULTIPLIER}x</td>
          <td class="num">{d['units12m']:,.0f}</td>
          <td class="num">&euro;{d['rev12m']:,.0f}</td>
          <td class="num">{share:.1f}%</td>
        </tr>
'''
table_rows_html += f'''        <tr class="total-row">
          <td colspan="2"><strong>Razem</strong></td>
          <td class="num">{total_asins}</td>
          <td class="num">{sum(d["units30d"] for d in data_by_market.values()):,.0f}</td>
          <td class="num">-</td>
          <td class="num">{total_units12m:,.0f}</td>
          <td class="num">&euro;{total_rev12m:,.0f}</td>
          <td class="num">100%</td>
        </tr>
'''

# -- HTML template ----------------------------------------------------------
HTML = f'''<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Provecta EU - Rynek (12M)</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f1f5f9;color:#1e293b;font-size:13px}}
header{{background:#0f2942;color:#fff;padding:18px 32px;display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap}}
header .titles h1{{font-size:1.1rem;font-weight:700;letter-spacing:.01em;margin-bottom:4px}}
header .titles span{{font-size:.75rem;color:#94a3b8}}
.main{{max-width:1200px;margin:0 auto;padding:28px 24px}}
.kpi-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}}
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
/* Executive summary block - 3 insight columns, collapsible */
.summary{{background:#fff;border-radius:8px;padding:0;box-shadow:0 1px 3px rgba(0,0,0,.07);margin-bottom:24px;border-left:4px solid #0f2942;overflow:hidden}}
.summary > summary{{cursor:pointer;padding:14px 22px;font-size:.85rem;font-weight:700;color:#0f2942;text-transform:uppercase;letter-spacing:.06em;list-style:none;display:flex;align-items:center;gap:10px;user-select:none;transition:background .15s}}
.summary > summary:hover{{background:#f8fafc}}
.summary > summary::-webkit-details-marker{{display:none}}
.summary > summary::before{{content:'▸';display:inline-block;transition:transform .2s;font-size:.9rem;color:#64748b;width:14px}}
.summary[open] > summary::before{{transform:rotate(90deg)}}
.summary > summary .hint{{font-size:.66rem;font-weight:500;color:#94a3b8;text-transform:none;letter-spacing:0;margin-left:auto;font-style:italic}}
.summary-inner{{padding:2px 22px 18px}}
.summary-cols{{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}}
.summary-col h3{{font-size:.7rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #f1f5f9}}
.summary-col p{{font-size:.82rem;line-height:1.55;color:#334155;margin-bottom:8px}}
.summary-col p:last-child{{margin-bottom:0}}
.summary-col strong{{color:#0f2942}}
@media (max-width: 980px) {{ .summary-cols {{ grid-template-columns: 1fr; gap: 16px; }} }}
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
.tp-search{{padding:7px 12px;border:2px solid #cbd5e1;border-radius:18px;font-size:.75rem;color:#1e293b;min-width:220px;outline:none;transition:border-color .15s}}
.tp-search:focus{{border-color:#0f2942}}
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
    <h1>Provecta EU &middot; Rynek</h1>
    <span>Rynki: Francja &middot; Niemcy &middot; Wielka Brytania &middot; Włochy &middot; Hiszpania &middot; Dane: Helium 10 X-Ray (projekcja 30d &times; 12, EUR)</span>
  </div>
</header>

<div class="main">

  <!-- KPI Row -->
  <div class="kpi-row">
    <div class="kpi">
      <div class="kpi-v">&euro;{total_rev12m/1e6:.1f}M</div>
      <div class="kpi-l">Przychód 12M łącznie (EUR)</div>
    </div>
    <div class="kpi">
      <div class="kpi-v">{total_units12m:,}</div>
      <div class="kpi-l">Sztuki sprzedane 12M łącznie</div>
    </div>
    <div class="kpi">
      <div class="kpi-v">5 rynków</div>
      <div class="kpi-l">FR &bull; DE &bull; UK &bull; IT &bull; ES</div>
    </div>
    <div class="kpi">
      <div class="kpi-v">{total_asins}</div>
      <div class="kpi-l">Unikalne ASIN-y (odduplikowane per rynek)</div>
    </div>
  </div>

  <!-- Executive summary - auto-generated from data -->
  <details class="summary">
    <summary>Podsumowanie - kluczowe wnioski (12M) <span class="hint">kliknij żeby rozwinąć</span></summary>
    <div class="summary-inner">
    <div class="summary-cols">

      <div class="summary-col">
        <h3>Rynki</h3>
        <p>{summary_markets_1}</p>
        <p>{summary_markets_2}</p>
      </div>

      <div class="summary-col">
        <h3>Marki i koncentracja</h3>
        <p>{summary_brands_1}</p>
        <p>{summary_brands_2}</p>
      </div>

      <div class="summary-col">
        <h3>Ceny i wolumen</h3>
        <p>{summary_price_1}</p>
        <p>{summary_price_2}</p>
      </div>

    </div>
    </div>
  </details>

  <!-- Charts -->
  <div class="charts-row">
    <div class="card" style="margin:0">
      <h3>Przychód per rynek - 12M (&euro;)</h3>
      <div class="chart-wrap"><canvas id="barChart"></canvas></div>
    </div>
    <div class="card" style="margin:0">
      <h3>Udział rynków w sztukach - 12M</h3>
      <div class="chart-wrap"><canvas id="pieChart"></canvas></div>
    </div>
  </div>

  <!-- Units Table -->
  <div class="card">
    <h3>Sztuki i przychód per rynek - 12M</h3>
    <table>
      <thead>
        <tr>
          <th>Rynek</th>
          <th>Waluta</th>
          <th style="text-align:right">ASIN-y</th>
          <th style="text-align:right">Sztuki 30 dni</th>
          <th style="text-align:right">Mnożnik</th>
          <th style="text-align:right">Sztuki 12M (szac.)</th>
          <th style="text-align:right">Przychód 12M &euro;</th>
          <th style="text-align:right">Udział</th>
        </tr>
      </thead>
      <tbody>
{table_rows_html}      </tbody>
    </table>
  </div>

  <!-- Brand Share Pie Charts -->
  <div class="charts-row">
    <div class="card" style="margin:0">
      <h3>Udział marek w przychodzie - 12M (&euro;, wszystkie 5 rynków)</h3>
      <div class="chart-wrap" style="height:340px"><canvas id="brandRevPie"></canvas></div>
    </div>
    <div class="card" style="margin:0">
      <h3>Udział marek w sztukach - 12M (wszystkie 5 rynków)</h3>
      <div class="chart-wrap" style="height:340px"><canvas id="brandUnitsPie"></canvas></div>
    </div>
  </div>

  <!-- Brand Revenue Heatmap: Brand x Marketplace -->
  <div class="card">
    <h3>Przychód per marka i rynek - 12M (&euro;)</h3>
    <table class="heatmap" id="brandRevHeatmap">
      <thead>
        <tr>
          <th>Marka</th>
          {heatmap_th_cols}
          <th class="num" style="border-left:2px solid #e2e8f0">Razem</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
    <div style="margin-top:10px;font-size:.68rem;color:#64748b">Top 12 marek po łącznym przychodzie + Pozostałe. Ciemniejsze komórki = marka dominuje na tym rynku.</div>
  </div>

  <!-- Brand Units Heatmap: Brand x Marketplace -->
  <div class="card">
    <h3>Sztuki per marka i rynek - 12M</h3>
    <table class="heatmap" id="brandUnitsHeatmap">
      <thead>
        <tr>
          <th>Marka</th>
          {heatmap_th_cols}
          <th class="num" style="border-left:2px solid #e2e8f0">Razem</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
    <div style="margin-top:10px;display:flex;align-items:center;gap:6px;font-size:.68rem;color:#64748b">
      <span>Nisko</span>
      <div style="display:flex;gap:1px">
        <span style="width:18px;height:10px;background:#eff6ff;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#bfdbfe;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#93c5fd;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#3b82f6;border-radius:2px;display:inline-block"></span>
        <span style="width:18px;height:10px;background:#1d4ed8;border-radius:2px;display:inline-block"></span>
      </div>
      <span>Wysoko</span>
    </div>
  </div>

  <!-- Top 10 products per market -->
  <div class="tp-block">
    <h2>Top 10 produktów per rynek</h2>
    <p class="tp-intro">Wybierz rynek pigułką poniżej, żeby zobaczyć 10 najlepiej sprzedających się produktów, posortowanych po przychodzie 30-dniowym. Ceny podane są w walucie lokalnej (&pound; dla UK, &euro; dla pozostałych); przychód 12M zawsze w EUR. Klikaj nagłówki kolumn żeby zmienić sortowanie. Na dole sekcji pełny widok zaawansowany - wszystkie {len(all_products_flat)} produktów z filtrami rynek / marka / słowo kluczowe.</p>

    <div class="tp-pills">
      <span class="label">Rynek:</span>
      {market_pills}
    </div>

    <div id="tpTables"></div>

    <!-- Advanced: all products, all markets, with filters -->
    <details class="tp-advanced">
      <summary>&#128269; Widok zaawansowany - wszystkie {len(all_products_flat)} produktów z filtrami</summary>
      <div class="tp-intro" style="margin-top:10px">Filtruj po rynku albo wpisz markę / słowo kluczowe, sortuj dowolną kolumną. Przydatne do porównywania produktów cross-market.</div>
      <div class="tp-pills">
        <span class="label">Rynek:</span>
        {adv_market_pills}
      </div>
      <div class="tp-pills">
        <span class="label">Szukaj:</span>
        <input type="text" id="tpAdvSearch" class="tp-search" placeholder="Marka lub słowo kluczowe...">
      </div>
      <div id="tpAdvTable"></div>
    </details>
  </div>

  <!-- Methodology -->
  <div class="note">
    <strong>Metodologia:</strong> Helium 10 X-Ray - snapshot 30-dniowy per rynek, przeskalowany na 12 miesięcy przez prosty mnożnik &times;12 (bez korekty sezonowości). Duplikaty usunięte po ASIN w obrębie każdego rynku (zachowany wiersz z wyższym ASIN Revenue); wiersze bez ASIN lub bez ceny są wykluczone. Sztuki 30-dniowe oszacowane jako ASIN Revenue podzielony przez cenę katalogową. Przychody i ceny z UK przeliczone z GBP na EUR po stałym kursie {GBP_EUR} dla wszystkich agregacji cross-market; ceny produktów UK w tabeli per rynek pozostają w &pound;. Wszystkie wartości zagregowane podane są w EUR.
  </div>

</div>

<script>
Chart.register(ChartDataLabels);

const LABELS = {json.dumps(bar_labels, ensure_ascii=False)};
const CODES = {market_codes_json};
const REVENUE = {revenue_arr};
const UNITS = {units_arr};
const COLORS = {json.dumps(colors)};

// Bar chart - Revenue by Marketplace
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

// Doughnut - Unit share by Marketplace
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
      tooltip: {{ callbacks: {{ label: ctx => {{ const pct=(ctx.parsed/UNITS.reduce((a,b)=>a+b,0)*100).toFixed(1); return ' '+ctx.parsed.toLocaleString()+' szt. ('+pct+'%)'; }} }} }},
      datalabels: {{
        display: ctx => (ctx.dataset.data[ctx.dataIndex] / UNITS.reduce((a,b)=>a+b,0)) > 0.05,
        formatter: v => (v/UNITS.reduce((a,b)=>a+b,0)*100).toFixed(1) + '%',
        color: '#fff', font: {{ size: 11, weight: '700' }}
      }}
    }}
  }}
}});

// === Brand pies (top 10 + Other, across all 5 markets combined) ===
const BRAND_REV_LABELS  = {json.dumps(brand_rev_labels, ensure_ascii=False)};
const BRAND_REV_VALUES  = {brand_rev_values};
const BRAND_UNITS_LABELS = {json.dumps(brand_units_labels, ensure_ascii=False)};
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

// === Brand x Marketplace heatmaps ===
const HM_COLORS = ['#eff6ff','#bfdbfe','#93c5fd','#3b82f6','#1d4ed8'];
const HM_TEXT   = ['#1e40af','#1e40af','#1e3a5f','#ffffff','#ffffff'];

function hmColor(val, max) {{
  if (val === 0) return {{ bg: '#f8fafc', fg: '#94a3b8' }};
  const idx = Math.min(4, Math.floor((val / max) * 4.99));
  return {{ bg: HM_COLORS[idx], fg: HM_TEXT[idx] }};
}}
function fmtRev(v) {{
  if (v === 0) return '-';
  if (v >= 1e6) return '€' + (v/1e6).toFixed(1) + 'M';
  return '€' + (v/1e3).toFixed(0) + 'K';
}}
function fmtUnits(v) {{
  if (v === 0) return '-';
  if (v >= 1e6) return (v/1e6).toFixed(1) + 'M';
  return (v/1e3).toFixed(1) + 'K';
}}

const BRAND_HM_DATA = {json.dumps(brand_hm_data, ensure_ascii=False, indent=2)};
const BRAND_HM_ORDER = {json.dumps(hm_brand_order, ensure_ascii=False)};
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
  const nCols = CODES.length;
  const totals = Array(nCols).fill(0).map((_,i) => BRAND_HM_ORDER.reduce((s,b)=>s+BRAND_HM_DATA[b][field][i],0));
  const grandTotal = totals.reduce((a,b)=>a+b,0);
  const tr = document.createElement('tr');
  tr.className = 'total-row';
  tr.innerHTML = '<td class="seg-label">Razem</td>';
  totals.forEach(v => {{ tr.innerHTML += '<td class="hm" style="background:#f8fafc;color:#0f2942">'+fmtFn(v)+'</td>'; }});
  tr.innerHTML += '<td class="hm-total">' + fmtFn(grandTotal) + '</td>';
  tbody.appendChild(tr);
}}
buildBrandHeatmap('brandRevHeatmap',   'rev',   fmtRev);
buildBrandHeatmap('brandUnitsHeatmap', 'units', fmtUnits);

// === Top Products Tables ===
const TOP_PRODUCTS = {top_products_json};
const ALL_PRODUCTS = {all_products_json};
const TP_MKT_CODES = {market_codes_json};

function fmtMoneyInt(v) {{ return '€' + Math.round(v).toLocaleString('en-EU'); }}
function fmtInt(v) {{ return Math.round(v).toLocaleString('en-EU'); }}
function escHtml(s) {{ return String(s || '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]); }}
const AMAZON_DOMAIN = {amazon_domains_json};
function asinLink(asin, marketCode) {{
  const dom = AMAZON_DOMAIN[marketCode] || 'de';
  return '<a href="https://www.amazon.' + dom + '/dp/' + encodeURIComponent(asin) + '" target="_blank" rel="noopener">' + escHtml(asin) + '</a>';
}}

const TP_COLS = [
  {{key:'rank',    label:'#',        num:true,  w:'32px'}},
  {{key:'asin',    label:'ASIN',     num:false, w:'110px'}},
  {{key:'brand',   label:'Marka',    num:false, w:'120px'}},
  {{key:'title',   label:'Tytuł',    num:false, w:'auto', cls:'title'}},
  {{key:'price',   label:'Cena',     num:true}},
  {{key:'units30d',label:'Sztuki 30d',num:true,  fmt:fmtInt}},
  {{key:'units12m',label:'Sztuki 12M',num:true,  fmt:fmtInt}},
  {{key:'rev12m',  label:'Przychód 12M €', num:true, fmt:fmtMoneyInt}},
  {{key:'reviews', label:'Recenzje', num:true,  fmt:fmtInt}},
];

function buildTopTable(products, containerId, includeMarketCol, fixedMarketCode) {{
  const cols = includeMarketCol ? [{{key:'market',label:'Rynek',num:false,w:'42px'}}, ...TP_COLS.slice(1)] : TP_COLS;
  let sortKey = includeMarketCol ? 'rev12m' : 'rank';
  let sortDir = includeMarketCol ? 'desc' : 'asc';
  const rows = products.map((p, i) => ({{ ...p, rank: i + 1 }}));

  function render() {{
    rows.sort((a, b) => {{
      const va = a[sortKey]; const vb = b[sortKey];
      const na = (typeof va === 'number'); const nb = (typeof vb === 'number');
      if (na && nb) return sortDir === 'asc' ? va - vb : vb - va;
      return sortDir === 'asc' ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
    }});
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
        else if (c.key === 'price') val = (r.cur || '€') + Number(val).toFixed(2);
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

// === Main view: top 10 table for selected market ===
function renderTopTableForMarket(code) {{
  const prods = TOP_PRODUCTS[code] || [];
  if (prods.length === 0) {{
    document.getElementById('tpTables').innerHTML = '<p style="font-size:.74rem;color:#94a3b8;padding:8px 0">Brak produktów dla ' + code + '.</p>';
  }} else {{
    buildTopTable(prods, 'tpTables', false, code);
  }}
}}
document.querySelectorAll('.tp-pill[data-mkt]').forEach(btn => {{
  btn.onclick = () => {{
    document.querySelectorAll('.tp-pill[data-mkt]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderTopTableForMarket(btn.dataset.mkt);
  }};
}});
renderTopTableForMarket(TP_MKT_CODES[0]);

// === Advanced view: all products with market + keyword filters ===
let advMkt = 'All';
let advQuery = '';
function renderAdvancedTable() {{
  let filtered = ALL_PRODUCTS.slice();
  if (advMkt !== 'All') filtered = filtered.filter(p => p.market === advMkt);
  if (advQuery) {{
    const q = advQuery.toLowerCase();
    filtered = filtered.filter(p => (p.brand || '').toLowerCase().includes(q) || (p.title || '').toLowerCase().includes(q) || (p.asin || '').toLowerCase().includes(q));
  }}
  if (filtered.length === 0) {{
    document.getElementById('tpAdvTable').innerHTML = '<p style="font-size:.74rem;color:#94a3b8;padding:8px 0">Brak produktów dla wybranego filtra.</p>';
  }} else {{
    buildTopTable(filtered, 'tpAdvTable', true);
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
document.getElementById('tpAdvSearch').addEventListener('input', e => {{
  advQuery = e.target.value.trim();
  renderAdvancedTable();
}});
renderAdvancedTable();
</script>
</body>
</html>
'''

# -- Sanitize + guard: no em/en dashes anywhere in the output ---------------
# Source CSV titles/brands may contain em/en dashes; replace with plain hyphens.
HTML = HTML.replace('—', '-').replace('–', '-')
if '&mdash;' in HTML or '&ndash;' in HTML:
    raise SystemExit('ERROR: mdash/ndash entity found in generated HTML - style rule violation')

out_path = os.path.join(BASE, '_rynek_topline.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(HTML)

print(f'\n_rynek_topline.html: {os.path.getsize(out_path):,} bytes')
print(f'Total 12M revenue: EUR {total_rev12m:,.0f}')
print(f'Total 12M units:   {total_units12m:,}')
print(f'Total ASINs:       {total_asins}  |  Unique brands: {n_unique_brands}')
print('\nExec summary (plain text):')
for line in summary_lines:
    print('  - ' + line)
if anomalies:
    print('\nParsing anomalies:')
    for a in anomalies:
        print('  ! ' + a)
else:
    print('\nNo parsing anomalies.')
