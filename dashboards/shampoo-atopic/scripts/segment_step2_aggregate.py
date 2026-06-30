"""
Shampoo-Atopic segmentation — STEP 2 (per marketplace).

Merges the per-chunk classification results, applies line-identity overrides for
Tom's reference brands/lines, writes the final filtered+segmented X-Ray and a
human-readable audit, and prints the review summary.

Usage:  py scripts/segment_step2_aggregate.py IT [ASIN1 ASIN2 ...overrides]

Reads : _classify/{MARKET}/_results_chunk*.csv  (written by the API agents)
        data/x-ray/shampoo-atopic-{MARKET}-merged.csv
Writes: data/x-ray/shampoo-atopic-{MARKET}.csv          (kept shampoos + Segment)
        _classify/{MARKET}/classification-audit.csv
"""
import csv, glob, os, sys

MARKET = (sys.argv[1] if len(sys.argv) > 1 else 'DE').upper()
# Optional line-identity overrides: ASINs that ARE reference lines (Bioderma Node,
# Ducray Extra Doux/Mild, Emolium, Physiogel, Eloderm, Mediderm) but whose own
# listing copy is thin -> force Irritated / Atopic. Pass as extra argv.
OVERRIDE = set(a.strip() for a in sys.argv[2:])

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLS_DIR = os.path.join(ROOT, '_classify', MARKET)
SEG = 'Irritated / Atopic'


def num(s):
    try: return float(str(s).replace(',', '').replace('€', '').replace('£', '').replace('$', '').strip() or 0)
    except: return 0


cls = {}
for fn in sorted(glob.glob(os.path.join(CLS_DIR, '_results_chunk*.csv'))):
    for r in csv.DictReader(open(fn, encoding='utf-8-sig')):
        cls[r['asin'].strip()] = {k: (v or '').strip() for k, v in r.items()}
for a in OVERRIDE:
    if a in cls and cls[a]['is_shampoo'] == 'Y':
        cls[a]['segment'] = SEG; cls[a]['_override'] = 'line-identity'

merged = list(csv.DictReader(open(
    os.path.join(ROOT, 'data', 'x-ray', f'shampoo-atopic-{MARKET}-merged.csv'), encoding='utf-8-sig')))
hdr = list(merged[0].keys())
by_asin = {r['ASIN']: r for r in merged}

kept, dropped = [], []
for a, c in cls.items():
    row = by_asin.get(a)
    if not row: continue
    if c['is_shampoo'] == 'Y':
        row['Segment'] = SEG if c['segment'] == SEG else ''
        kept.append((a, row, c))
    else:
        dropped.append((a, row, c))
kept.sort(key=lambda x: -num(x[1]['ASIN Revenue']))

with open(os.path.join(ROOT, 'data', 'x-ray', f'shampoo-atopic-{MARKET}.csv'),
          'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=hdr); w.writeheader()
    for a, row, c in kept: w.writerow(row)

with open(os.path.join(CLS_DIR, 'classification-audit.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['asin', 'brand', 'revenue', 'is_shampoo', 'segment', 'confidence',
                'product_type', 'evidence', 'title'])
    for a, c in sorted(cls.items(), key=lambda kv: -num(by_asin.get(kv[0], {}).get('ASIN Revenue', 0))):
        row = by_asin.get(a, {})
        w.writerow([a, row.get('Brand', ''), int(num(row.get('ASIN Revenue', 0))), c['is_shampoo'],
                    c['segment'], c.get('confidence', ''), c.get('product_type', ''),
                    c.get('evidence', ''), row.get('Product Details', '')[:80]])

ia = [k for k in kept if k[2]['segment'] == SEG]
cos = [k for k in kept if k[2]['segment'] != SEG]
print(f'[{MARKET}] kept shampoos {len(kept)} | Irritated/Atopic {len(ia)} | cosmetic {len(cos)} | '
      f'dropped non-shampoo {len(dropped)} | overrides {sorted(OVERRIDE)}')
print(f'  30d revenue (Irritated/Atopic): €{int(sum(num(r["ASIN Revenue"]) for _,r,_ in ia)):,}')
print(f'  final: data/x-ray/shampoo-atopic-{MARKET}.csv | audit: {CLS_DIR}/classification-audit.csv')
