"""
Oil-enrichment classification PREP for atopic-skin-detailed.

For each market (DE/FR/IT/ES):
  - genuinely-NEW oil ASINs = in oil-{CODE}.csv but not already in Dermo-Products-{CODE}.csv
  - CHECK candidates = existing rows Segment=='Check' whose title looks oil-ish
Writes per-market:
  _oilclassify/{CODE}/_manifest.csv   (asin,source,current_segment,title)
  _oilclassify/{CODE}/_chunk_N.txt    (asins, ~CHUNK per file)
DATA ONLY — does not merge or build anything.
"""
import csv, re, os, math

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # atopic-skin-detailed
XDIR = os.path.join(BASE, 'data', 'x-ray')
OUT  = os.path.join(BASE, '_oilclassify')
CHUNK = 15
MARKETS = ['DE', 'FR', 'IT', 'ES']
OILRE = re.compile(r'\b(oil|öl|öls|body ?öl|olio|aceite|huile)\b', re.I)


def rows(f):
    return list(csv.DictReader(open(f, encoding='utf-8-sig')))


grand = 0
for c in MARKETS:
    ex  = rows(os.path.join(XDIR, c, f'Dermo-Products-{c}.csv'))
    oil = rows(os.path.join(XDIR, f'oil-{c}.csv'))
    ex_by = {(r.get('ASIN') or '').strip(): r for r in ex if (r.get('ASIN') or '').strip()}

    todo = []  # (asin, source, current_segment, title)
    seen = set()
    # genuinely-new oils
    for r in oil:
        a = (r.get('ASIN') or '').strip()
        if not a or a in seen:
            continue
        if a not in ex_by:
            todo.append((a, 'new', '', (r.get('Product Details') or '').strip()))
            seen.add(a)
    # existing Check rows with oil-ish title
    for r in ex:
        a = (r.get('ASIN') or '').strip()
        if not a or a in seen:
            continue
        if (r.get('Segment') or '').strip().lower() == 'check' and OILRE.search(r.get('Product Details') or ''):
            todo.append((a, 'check', (r.get('Segment') or '').strip(), (r.get('Product Details') or '').strip()))
            seen.add(a)

    d = os.path.join(OUT, c)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '_manifest.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['asin', 'source', 'current_segment', 'title'])
        for t in todo:
            w.writerow([t[0], t[1], t[2], t[3][:90]])
    n = math.ceil(len(todo) / CHUNK) if todo else 0
    for i in range(n):
        part = todo[i*CHUNK:(i+1)*CHUNK]
        with open(os.path.join(d, f'_chunk_{i+1}.txt'), 'w', encoding='utf-8') as f:
            f.write("\n".join(t[0] for t in part))
    nnew = sum(1 for t in todo if t[1] == 'new')
    nchk = sum(1 for t in todo if t[1] == 'check')
    grand += len(todo)
    print(f'[{c}] to-classify {len(todo)} (new {nnew} + check {nchk}) -> {n} chunks')

print(f'TOTAL to classify: {grand}')
