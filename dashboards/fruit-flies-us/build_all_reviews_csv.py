"""Compile EVERY review used by the CONSOLE Fruit Flies (US) standalone dashboard
into one CSV — the full Lure + Electric VOC pools that drive the two Reviews tabs.

Source: _voc_work/lure_all.json + _voc_work/electric_all.json
  (built by _extract_voc_samples.py: the dataset_*.json negative scrape segment-filtered
   to Lure / Electric Traps, PLUS the 2026-05-31 positive pull gated to those pool ASINs).

Output: console-fruit-flies-us-all-reviews.csv
Columns: segment, brand, asin, rating, title, review, date
"""
import json, os, csv
from collections import Counter

DIR = os.path.dirname(os.path.abspath(__file__))

rows = []
for slug in ('lure', 'electric'):
    pool = json.load(open(os.path.join(DIR, '_voc_work', f'{slug}_all.json'), encoding='utf-8'))
    for r in pool:
        rows.append({
            'segment': r.get('segment', ''),
            'brand':   r.get('brand', ''),
            'asin':    r.get('asin', ''),
            'rating':  r.get('rating', ''),
            'title':   (r.get('title') or '').strip(),
            'review':  (r.get('body') or '').strip(),
            'date':    r.get('date', ''),
        })

out = os.path.join(DIR, 'console-fruit-flies-us-all-reviews.csv')
cols = ['segment', 'brand', 'asin', 'rating', 'title', 'review', 'date']
with open(out, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

print(f'TOTAL reviews written: {len(rows)}')
print('By segment:', dict(Counter(r['segment'] for r in rows)))
print('By star rating:', dict(sorted(Counter(r['rating'] for r in rows).items())))
print('By brand:', dict(Counter(r['brand'] for r in rows).most_common()))
print(f'  with ASIN: {sum(1 for r in rows if r["asin"])}  |  with title: {sum(1 for r in rows if r["title"])}')
print(f'Output: {out}')
