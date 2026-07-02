# -*- coding: utf-8 -*-
"""Combine the 5 per-market X-Ray CSVs into ONE shareable file for Google Sheets.

Reads data/x-ray/shampoo-atopic-{CODE}.csv (DE/UK/FR/IT/ES) and writes a single
data/x-ray/Shampoo-Atopic-ALL-markets.csv with a new **Marketplace** column inserted
right after the URL column (value derived from the product URL's amazon.<tld>, falling
back to the source file's code). Lets a colleague filter by marketplace and
review/reassign segments in one sheet.

Header normalisation: the UK file uses "Price  £" / "Fees  £" while the € markets use
"Price  €" / "Fees  €". Both are collapsed to currency-neutral "Price" / "Fees" columns
(the Marketplace column tells the reader which currency the row is in: UK = GBP, rest = EUR).

Does NOT touch the per-country files (the dashboard build still reads those).
Run: python _export_combined_xray.py
"""
import csv, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
CODES = ['DE', 'UK', 'FR', 'IT', 'ES']
OUT = os.path.join(BASE, 'data', 'x-ray', 'Shampoo-Atopic-ALL-markets.csv')

TLD_MAP = {'de': 'DE', 'fr': 'FR', 'it': 'IT', 'es': 'ES',
           'co.uk': 'UK', 'com': 'US', 'nl': 'NL'}

# Map any currency-suffixed header to its neutral name.
RENAME = {'Price  €': 'Price', 'Price  £': 'Price', 'Price €': 'Price', 'Price £': 'Price',
          'Fees  €': 'Fees', 'Fees  £': 'Fees', 'Fees €': 'Fees', 'Fees £': 'Fees'}


def marketplace_from_url(url, fallback):
    m = re.search(r'amazon\.([a-z.]+?)/', (url or '') + '/')
    if m:
        return TLD_MAP.get(m.group(1), m.group(1).upper())
    return fallback


def norm_key(k):
    return RENAME.get(k, k)


def main():
    header = None
    out_rows = []
    per_market = {}
    for code in CODES:
        path = os.path.join(BASE, 'data', 'x-ray', f'shampoo-atopic-{code}.csv')
        with open(path, encoding='utf-8-sig', newline='') as f:
            rd = csv.DictReader(f)
            cols = [norm_key(c) for c in rd.fieldnames]
            if header is None:
                url_i = cols.index('URL') if 'URL' in cols else len(cols)
                header = cols[:url_i + 1] + ['Marketplace'] + cols[url_i + 1:]
            n = 0
            for r in rd:
                row = {norm_key(k): v for k, v in r.items()}
                row['Marketplace'] = marketplace_from_url(row.get('URL'), code)
                out_rows.append(row)
                n += 1
            per_market[code] = n

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction='ignore')
        w.writeheader()
        w.writerows(out_rows)

    print(f'wrote {OUT}')
    print(f'  rows: {len(out_rows)}  ({", ".join(f"{k}={v}" for k, v in per_market.items())})')
    from collections import Counter
    mk = Counter(r['Marketplace'] for r in out_rows)
    seg = Counter(r.get('Segment', '') for r in out_rows)
    print(f'  Marketplace column: {dict(mk)}')
    print(f'  Segment column: {dict(seg)}')
    print(f'  "Marketplace" inserted after "URL" (column #{header.index("Marketplace") + 1})')


if __name__ == '__main__':
    main()
