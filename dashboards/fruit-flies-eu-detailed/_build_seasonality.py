"""
Derives the German fruit-fly-trap monthly seasonality index and writes it to
data/seasonality-de.json (the committed, build-time input consumed by
_build_rynek.py).

Source: the German dashboard's 3-year daily sales history
    02-Projects/Dashboards/Fruit Fly Trap - DE/Data/sales-units/{ASIN}-sales-3y.csv
(the same data behind https://vente-europe.github.io/fruit-fly-trap-DE/).

Method:
  * Pool daily `Sales` across all ASINs -> market daily units per date.
  * Group by calendar month, average the market daily rate per month.
  * index[m] = month_avg_daily[m] / mean(all 12 month_avg_daily)  (avg month = 1.0)
  * Seasonal 12M multiplier for a snapshot taken in month M = 12 / index[M].

This is a build-time helper: it depends on a sibling project folder that does NOT
ship to GitHub Pages, so its OUTPUT (seasonality-de.json) is committed and read by
_build_rynek.py. Re-run only when the German sales history is refreshed.
"""
import csv, glob, json, os, re, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
DE_SALES = os.path.abspath(os.path.join(
    BASE, '..', '..', '..', 'Dashboards', 'Fruit Fly Trap - DE', 'Data', 'sales-units'))

if not os.path.isdir(DE_SALES):
    raise SystemExit(f'German sales folder not found: {DE_SALES}')

day_sum = defaultdict(float)   # 'YYYY-MM-DD' -> market daily units
files = glob.glob(os.path.join(DE_SALES, '*.csv'))
for fp in files:
    with open(fp, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            t = row.get('Time') or ''
            if not re.match(r'\d{4}-\d{2}-\d{2}', t):
                continue
            try:
                v = float(row.get('Sales') or '')
            except ValueError:
                continue
            day_sum[t[:10]] += v

mon_vals = defaultdict(list)
for d, v in day_sum.items():
    mon_vals[int(d[5:7])].append(v)

mon_avg = {m: (sum(vs) / len(vs)) for m, vs in mon_vals.items()}
mean_month = sum(mon_avg.values()) / 12.0
index = {m: round(mon_avg[m] / mean_month, 4) for m in range(1, 13)}

out = {
    'source': 'German fruit-fly-trap daily sales (02-Projects/Dashboards/Fruit Fly Trap - DE), 49 ASINs, ~2024-03..2026-03',
    'method': 'market daily units pooled across ASINs, averaged per calendar month, normalized so avg month = 1.0',
    'note': 'seasonal 12M multiplier for a snapshot in month M = 12 / index[M]',
    'index': index,               # month (1-12) -> seasonal index (avg month = 1.0)
    'days_observed': {str(m): len(mon_vals[m]) for m in range(1, 13)},
    'n_asins': len(files),
}

out_path = os.path.join(BASE, 'data', 'seasonality-de.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
print(f'Wrote {out_path}  ({len(files)} ASINs)')
for m in range(1, 13):
    print(f'  {names[m-1]}  index={index[m]:.3f}  -> x{12/index[m]:.2f}')
print(f'\nJuly (export month) multiplier = 12/{index[7]:.3f} = x{12/index[7]:.3f}')
