# -*- coding: utf-8 -*-
"""Combine the 4 per-market X-Ray CSVs into ONE shareable file for Google Sheets.

Reads data/x-ray/{CODE}/Dermo-Products-{CODE}.csv (DE/FR/IT/ES) and writes a single
data/x-ray/Atopic-Skin-Detailed-ALL-markets.csv with a new **Marketplace** column
inserted right after the URL column (value derived from the product URL's amazon.<tld>,
falling back to the source file's code). Lets a colleague filter by marketplace and
review/reclassify segments in one sheet.

Does NOT touch the per-country files (the dashboard build still reads those).
Run: python _export_combined_xray.py
"""
import csv, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
CODES = ['DE', 'FR', 'IT', 'ES']
OUT = os.path.join(BASE, 'data', 'x-ray', 'Atopic-Skin-Detailed-ALL-markets.csv')

TLD_MAP = {'de': 'DE', 'fr': 'FR', 'it': 'IT', 'es': 'ES',
           'co.uk': 'UK', 'com': 'US', 'nl': 'NL'}


def marketplace_from_url(url, fallback):
    m = re.search(r'amazon\.([a-z.]+?)/', (url or '') + '/')
    if m:
        return TLD_MAP.get(m.group(1), m.group(1).upper())
    return fallback


def main():
    header = None
    out_rows = []
    per_market = {}
    for code in CODES:
        path = os.path.join(BASE, 'data', 'x-ray', code, f'Dermo-Products-{code}.csv')
        with open(path, encoding='utf-8-sig', newline='') as f:
            rd = csv.DictReader(f)
            cols = rd.fieldnames
            if header is None:
                # Insert 'Marketplace' right after the URL column.
                url_i = cols.index('URL') if 'URL' in cols else len(cols)
                header = cols[:url_i + 1] + ['Marketplace'] + cols[url_i + 1:]
            n = 0
            for r in rd:
                r['Marketplace'] = marketplace_from_url(r.get('URL'), code)
                out_rows.append(r)
                n += 1
            per_market[code] = n

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction='ignore')
        w.writeheader()
        w.writerows(out_rows)

    print(f'wrote {OUT}')
    print(f'  rows: {len(out_rows)}  ({", ".join(f"{k}={v}" for k, v in per_market.items())})')
    # sanity: Marketplace distribution + segments per market
    from collections import Counter
    mk = Counter(r['Marketplace'] for r in out_rows)
    print(f'  Marketplace column: {dict(mk)}')
    print(f'  "Marketplace" inserted after "URL" (column #{header.index("Marketplace") + 1})')


if __name__ == '__main__':
    main()
