# -*- coding: utf-8 -*-
"""Split the combined all-markets X-Ray master back into the per-country files.

SINGLE SOURCE OF TRUTH: the combined sheet is the ONLY file anyone edits
(data/x-ray/Atopic-Skin-Detailed-ALL-markets*.csv, with a Marketplace column).
Downloaded back here, this splits it by Marketplace into the per-country files
the build reads (data/x-ray/{CODE}/Dermo-Products-{CODE}.csv), dropping the
Marketplace helper column so the per-country format is preserved exactly.

The per-country files are DERIVED ARTEFACTS. Never hand-edit them: the next
build overwrites them from the master.

_build_standalone.py runs this FIRST, so segment edits made in the one sheet
round-trip into the dashboard automatically.

Three things this has to tolerate, all learned the hard way (2026-07-20):
  1. Google Sheets appends the tab name on download, so the file lands as
     "Atopic-Skin-Detailed-ALL-markets - Atopic-Skin-Detailed-ALL-markets.csv".
     We GLOB instead of matching an exact name. Previously the exact-name check
     failed, the split silently skipped, and the build quietly used stale
     per-country files for weeks.
  2. The master is MIXED-ENCODING (older rows are cp1252 / already-mojibake,
     newly appended rows are clean UTF-8), so a plain utf-8 read raises. We
     decode per line and fall back.
  3. Duplicate ASIN rows exist within a marketplace (same product pasted twice).
     First occurrence wins.

A missing master is now a HARD ERROR, not a silent fallback -- if the single
source of truth isn't there, the build must stop rather than ship stale numbers.

Run standalone: python _split_master_xray.py
"""
import csv, glob, io, os, sys
from collections import Counter, OrderedDict

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
XRAY = os.path.join(BASE, 'data', 'x-ray')
# UK included: it is a marketplace like any other. Markets absent from the
# master are left untouched (their per-country file stays as-is) and reported.
CODES = ['DE', 'FR', 'IT', 'ES', 'UK']
MASTER_GLOB = os.path.join(XRAY, 'Atopic-Skin-Detailed-ALL-markets*.csv')


def find_master():
    hits = [p for p in glob.glob(MASTER_GLOB) if not p.endswith('.bak')]
    if not hits:
        return None
    # Prefer the plain name; otherwise the most recently modified download.
    exact = os.path.join(XRAY, 'Atopic-Skin-Detailed-ALL-markets.csv')
    return exact if exact in hits else max(hits, key=os.path.getmtime)


def read_rows(path):
    """Decode per line: UTF-8 where possible, cp1252 where not."""
    lines = []
    with open(path, 'rb') as f:
        for raw in f.read().split(b'\n'):
            try:
                lines.append(raw.decode('utf-8'))
            except UnicodeDecodeError:
                lines.append(raw.decode('cp1252', errors='replace'))
    rd = csv.DictReader(io.StringIO('\n'.join(lines).lstrip('﻿')))
    return list(rd), (rd.fieldnames or [])


def split():
    master = find_master()
    if not master:
        raise SystemExit(
            'FATAL: combined master X-Ray not found.\n'
            f'  Looked for: {MASTER_GLOB}\n'
            '  The master is the single source of truth -- refusing to build '
            'from stale per-country files.'
        )
    print(f'  master: {os.path.basename(master)}')

    rows, header = read_rows(master)
    if 'Marketplace' not in header:
        raise SystemExit('FATAL: master has no Marketplace column -- cannot split.')

    out_cols = [c for c in header if c != 'Marketplace']  # restore per-country format
    dist = Counter((r.get('Marketplace') or '').strip() for r in rows)
    unknown = {k: v for k, v in dist.items() if k not in CODES}
    if unknown:
        print(f'  WARNING: rows with unrecognised Marketplace are dropped: {unknown}')

    total = 0
    for code in CODES:
        sub = [r for r in rows if (r.get('Marketplace') or '').strip() == code]
        if not sub:
            print(f'  {code}: absent from master -> per-country file left untouched')
            continue
        # Dedupe by ASIN, first occurrence wins.
        seen = OrderedDict()
        for r in sub:
            seen.setdefault((r.get('ASIN') or '').strip(), r)
        dropped = len(sub) - len(seen)
        outp = os.path.join(XRAY, code, f'Dermo-Products-{code}.csv')
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        with open(outp, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=out_cols, extrasaction='ignore')
            w.writeheader()
            w.writerows(seen.values())
        total += len(seen)
        dup = f' ({dropped} duplicate ASIN dropped)' if dropped else ''
        print(f'  {code}: {len(seen)} rows{dup} -> data/x-ray/{code}/Dermo-Products-{code}.csv')
    print(f'  master ({len(rows)} rows) split -> {total} rows')
    return True


if __name__ == '__main__':
    split()
