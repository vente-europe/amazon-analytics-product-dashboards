# -*- coding: utf-8 -*-
"""Split the combined all-markets X-Ray master back into the 4 per-country files.

SINGLE SOURCE OF TRUTH: a colleague edits ONE sheet
(data/x-ray/Atopic-Skin-Detailed-ALL-markets.csv, with a Marketplace column) in
Google Sheets. When it's downloaded back here, this splits it by the Marketplace
column into the per-country files the build reads
(data/x-ray/{CODE}/Dermo-Products-{CODE}.csv) — dropping the Marketplace helper
column so the format the build expects is preserved exactly.

_build_standalone.py runs this FIRST, so segment edits made in the one sheet
round-trip into the dashboard automatically. If the master is absent, the build
just uses the existing per-country files as-is (backward compatible).

Run standalone: python _split_master_xray.py
"""
import csv, os, sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
CODES = ['DE', 'FR', 'IT', 'ES']
MASTER = os.path.join(BASE, 'data', 'x-ray', 'Atopic-Skin-Detailed-ALL-markets.csv')


def split():
    if not os.path.exists(MASTER):
        print('  master not found -> using existing per-country X-Ray files as-is')
        return False
    with open(MASTER, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        rows = list(rd)
        header = rd.fieldnames or []
    if 'Marketplace' not in header:
        print('  master has no Marketplace column -> skipping split (files left as-is)')
        return False

    out_cols = [c for c in header if c != 'Marketplace']  # restore original per-country format
    dist = Counter((r.get('Marketplace') or '').strip() for r in rows)
    unknown = {k: v for k, v in dist.items() if k not in CODES}
    if unknown:
        print(f'  WARNING: rows with unrecognised Marketplace are dropped: {unknown}')

    total = 0
    for code in CODES:
        sub = [r for r in rows if (r.get('Marketplace') or '').strip() == code]
        outp = os.path.join(BASE, 'data', 'x-ray', code, f'Dermo-Products-{code}.csv')
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        with open(outp, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=out_cols, extrasaction='ignore')
            w.writeheader()
            w.writerows(sub)
        total += len(sub)
        print(f'  {code}: {len(sub)} rows -> data/x-ray/{code}/Dermo-Products-{code}.csv')
    print(f'  master ({len(rows)} rows) split -> {total} rows across {len(CODES)} per-country files')
    return True


if __name__ == '__main__':
    split()
