"""
Shampoo-Atopic segmentation — STEP 1 (per marketplace).

Merges H10 X-Ray exports for a market, dedupes, applies the revenue floor +
brand keep-list, pre-drops clear non-shampoos by title, and emits the fetch list
+ ASIN chunks for the API classification step.

Usage:  py scripts/segment_step1_merge_filter.py IT      (or DE / FR / ES)

Reads : data/x-ray/{MARKET}/*.csv            (drop H10 exports here)
Writes: data/x-ray/shampoo-atopic-{MARKET}-merged.csv   (all ASINs, Segment col)
        _classify/{MARKET}/_fetch_list.csv
        _classify/{MARKET}/_chunk_1..6.txt
"""
import csv, glob, re, os, math, sys

MARKET = (sys.argv[1] if len(sys.argv) > 1 else 'DE').upper()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', 'x-ray', MARKET)
OUTDIR = os.path.join(ROOT, '_classify', MARKET)
os.makedirs(OUTDIR, exist_ok=True)

REV_FLOOR = 1000.0
# Brand keep-list (kept even < floor, IF shampoo). Pierre Fabre -> A-Derma/Ducray.
KEEP = {'drirenaeris', 'emolium', 'larocheposay', 'farmina', 'aristopharma',
        'bioderma', 'polpharmasa', 'pierrefabre', 'aderma', 'ducray'}

# Multilingual (DE/IT/FR/ES/EN) title pre-filter — only to SAVE API cost.
SHAMP = re.compile(r'\b(shampoo|shampooing|schampon|szampon|champ[uú])\b', re.I)
NONSHAMP = re.compile(r'\b(lotion|lozione|loci[oó]n|creme|crema|cream|cr[eè]me|gel|'
    r'serum|s[ié]rum|siero|[öo]l\b|olio|oil|aceite|spray|balsam|balsamo|b[aâ]ume|'
    r'conditioner|sp[üu]lung|maske|maschera|mask|mascarilla|detergente|mousse|'
    r'tonico|tonikum|tonic|t[oó]nico|peeling|scrub|deodorant|deodorante|desodorante|'
    r'b[üu]rste|brush|spazzola|cepillo|reinigung|cleansing|duschgel|waschgel|'
    r'mizellen|micellar|micellare|fluid\b|milch|latte|leche|hundeshampoo|dog)\b', re.I)


def num(s):
    try: return float(str(s).replace(',', '').replace('€', '').replace('£', '').replace('$', '').strip() or 0)
    except: return 0
def norm(s): return re.sub(r'[^a-z0-9]', '', str(s).lower())


files = glob.glob(os.path.join(SRC, '*.csv')) + glob.glob(os.path.join(SRC, '*.CSV'))
if not files:
    sys.exit(f'No CSVs in {SRC} — drop the {MARKET} X-Ray exports there first.')

rows, hdr = {}, None
for fn in files:
    r = csv.reader(open(fn, encoding='utf-8-sig'))
    h = next(r)
    if hdr is None: hdr = h
    ai, ri = h.index('ASIN'), h.index('ASIN Revenue')
    for row in r:
        if len(row) < len(h): continue
        a = row[ai].strip()
        if not a: continue
        if a not in rows or num(row[ri]) > num(rows[a][ri]): rows[a] = row

ai = hdr.index('ASIN')
out_hdr = hdr[:ai + 1] + ['Segment'] + hdr[ai + 1:]
merged_path = os.path.join(ROOT, 'data', 'x-ray', f'shampoo-atopic-{MARKET}-merged.csv')
with open(merged_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(out_hdr)
    for a, row in sorted(rows.items(), key=lambda kv: -num(kv[1][hdr.index('ASIN Revenue')])):
        w.writerow(row[:ai + 1] + [''] + row[ai + 1:])

bi, ti, ri = hdr.index('Brand'), hdr.index('Product Details'), hdr.index('ASIN Revenue')
cand = [r for r in rows.values() if num(r[ri]) >= REV_FLOOR or norm(r[bi]) in KEEP]
fetch = []
for r in cand:
    t = r[ti]
    if NONSHAMP.search(t) and not SHAMP.search(t): continue   # clear non-shampoo -> drop pre-API
    fetch.append(r)

with open(os.path.join(OUTDIR, '_fetch_list.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['asin', 'brand', 'revenue', 'title'])
    for r in fetch: w.writerow([r[ai], r[bi], int(num(r[ri])), r[ti]])

N = 6; per = math.ceil(len(fetch) / N)
for i in range(N):
    part = fetch[i * per:(i + 1) * per]
    if not part: continue
    with open(os.path.join(OUTDIR, f'_chunk_{i + 1}.txt'), 'w', encoding='utf-8') as f:
        f.write("\n".join(r[ai] for r in part))

print(f'[{MARKET}] merged {len(files)} files -> {len(rows)} ASINs | candidates {len(cand)} | '
      f'pre-dropped non-shampoo {len(cand)-len(fetch)} | TO FETCH {len(fetch)} ({N} chunks)')
print(f'  merged: {merged_path}')
print(f'  chunks: {OUTDIR}/_chunk_*.txt  -> run the API classification agents next')
