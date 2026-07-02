"""
Oil-enrichment MERGE for atopic-skin-detailed  (DATA ONLY — no build/rebuild).

Reads the per-chunk classification results, normalizes wash/rinse-off oils to
Check (safety net for inconsistent agents), then per market:
  - NEW oils not already in Dermo-Products-{CODE}.csv  -> append a row with the
    classified Segment (Oil or Check), columns mapped from oil-{CODE}.csv by name.
  - existing Check rows verified as Oil                 -> flip Segment to "Oil".
  - existing Check rows still not oil / ERR             -> leave "Check".
  - duplicates (already present, non-Check)             -> left untouched.
Writes the updated Dermo-Products-{CODE}.csv in place and an audit CSV per market.
"""
import csv, os, re, glob
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XDIR = os.path.join(BASE, 'data', 'x-ray')
CLS  = os.path.join(BASE, '_oilclassify')
MARKETS = ['DE', 'FR', 'IT', 'ES']

# wash / rinse-off forms that must NEVER be "Oil" (leave-on segment only)
WASH = re.compile(r'(lavant|detergent|struccant|doccia|bagnodoccia|da bagno|dusch|wasch|'
                  r'reinigung|cleansing|makeup|make-up|limpiador|nettoyant|liniment|'
                  r'de ducha|de ba|oleogel|bath|shower|wash|rinse|micellar|micellare)', re.I)


def rows(f):
    return list(csv.DictReader(open(f, encoding='utf-8-sig')))


def load_results(code):
    """asin -> dict(segment, product_type, evidence, step_*). Later chunks win."""
    res = {}
    for fn in sorted(glob.glob(os.path.join(CLS, code, '_res_chunk*.csv'))):
        for r in csv.DictReader(open(fn, encoding='utf-8-sig')):
            a = (r.get('asin') or '').strip()
            if a:
                res[a] = {k: (v or '').strip() for k, v in r.items()}
    return res


for code in MARKETS:
    res = load_results(code)
    # normalize: wash/rinse-off -> Check
    flips = 0
    for a, r in res.items():
        seg = r.get('segment', '')
        blob = (r.get('product_type', '') + ' ' + r.get('evidence', ''))
        if seg == 'Oil' and WASH.search(blob):
            r['segment'] = 'Check'; r['_washflip'] = '1'; flips += 1
        if seg == 'ERR':
            r['segment'] = 'Check'; r['_err'] = '1'   # unverified -> Check for review

    ex_path = os.path.join(XDIR, code, f'Dermo-Products-{code}.csv')
    ex = rows(ex_path)
    hdr = list(ex[0].keys())
    ex_by = {(r.get('ASIN') or '').strip(): r for r in ex if (r.get('ASIN') or '').strip()}
    oil = rows(os.path.join(XDIR, f'oil-{code}.csv'))
    oil_by = {(r.get('ASIN') or '').strip(): r for r in oil if (r.get('ASIN') or '').strip()}

    reclassified = 0     # existing Check -> Oil
    appended_oil = 0
    appended_check = 0
    # 1) update existing rows that were classified (only touch current 'Check')
    for a, r in ex_by.items():
        c = res.get(a)
        if not c:
            continue
        if (r.get('Segment') or '').strip().lower() == 'check' and c['segment'] == 'Oil':
            r['Segment'] = 'Oil'; reclassified += 1
    # 2) append genuinely-new oils (in oil file, not already in existing)
    new_rows = []
    for a, orow in oil_by.items():
        if a in ex_by:
            continue
        c = res.get(a)
        seg = c['segment'] if c else 'Check'      # unclassified new -> Check
        out = {col: '' for col in hdr}
        for col in hdr:
            if col == 'Segment':
                out['Segment'] = seg
            elif col in orow:
                out[col] = orow[col]
        new_rows.append(out)
        if seg == 'Oil':
            appended_oil += 1
        else:
            appended_check += 1

    merged = ex + new_rows
    with open(ex_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=hdr, extrasaction='ignore')
        w.writeheader(); w.writerows(merged)

    # audit
    with open(os.path.join(CLS, code, '_audit.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['asin', 'result_segment', 'washflip', 'err', 'confidence',
                    'step_oil', 'step_skin', 'step_atopic', 'product_type', 'evidence'])
        for a, r in sorted(res.items()):
            w.writerow([a, r.get('segment', ''), r.get('_washflip', ''), r.get('_err', ''),
                        r.get('confidence', ''), r.get('step_oil', ''), r.get('step_skin', ''),
                        r.get('step_atopic', ''), r.get('product_type', ''), r.get('evidence', '')])

    final = Counter((r.get('Segment') or '(blank)').strip() or '(blank)' for r in merged)
    print(f'[{code}] classified {len(res)} (washflips {flips}) | '
          f'reclassified Check->Oil {reclassified} | '
          f'appended new: Oil {appended_oil}, Check {appended_check} | '
          f'file now {len(merged)} rows | segments: ' + ', '.join(f'{k}={v}' for k, v in final.most_common()))
