"""Merge all Helium 10 X-Ray CSVs in a country folder.

- Concatenates every Helium_10_Xray_*.csv in data/x-ray/{CODE}/
- Deduplicates by ASIN (keeps the first occurrence)
- Drops rows where ASIN Revenue < MIN_REVENUE
- Writes Moth-{CODE}.csv next to the inputs

Usage:
    py _merge_xray.py DE
    py _merge_xray.py DE 1000      # custom revenue floor
"""
import csv
import glob
import os
import sys

MIN_REVENUE_DEFAULT = 1000.0


def parse_number(value):
    if value is None:
        return None
    s = str(value).strip().replace('"', '')
    if not s or s.upper() == 'N/A':
        return None
    s = s.replace(',', '').replace('€', '').replace('£', '').replace('$', '').strip()
    try:
        return float(s)
    except ValueError:
        return None


def merge(code: str, min_revenue: float):
    base = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(base, 'data', 'x-ray', code)
    if not os.path.isdir(src_dir):
        sys.exit(f'No such folder: {src_dir}')

    files = sorted(glob.glob(os.path.join(src_dir, 'Helium_10_Xray_*.csv')))
    if not files:
        sys.exit(f'No Helium_10_Xray_*.csv files in {src_dir}')

    print(f'Found {len(files)} files in {src_dir}')

    all_rows = []
    header = None
    for fp in files:
        with open(fp, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f)
            try:
                row_header = next(reader)
            except StopIteration:
                continue
            if header is None:
                header = row_header
            for row in reader:
                if not row or all(not c.strip() for c in row):
                    continue
                all_rows.append(row)
    print(f'Total rows read: {len(all_rows)}')

    asin_idx = header.index('ASIN')
    rev_idx = header.index('ASIN Revenue')

    seen = set()
    unique_rows = []
    for row in all_rows:
        if len(row) <= max(asin_idx, rev_idx):
            continue
        asin = row[asin_idx].strip()
        if not asin or asin in seen:
            continue
        seen.add(asin)
        unique_rows.append(row)
    print(f'Unique ASINs: {len(unique_rows)}')

    filtered = []
    for row in unique_rows:
        rev = parse_number(row[rev_idx])
        if rev is None or rev < min_revenue:
            continue
        filtered.append(row)
    print(f'After ASIN Revenue >= {min_revenue:.0f}: {len(filtered)}')

    out_path = os.path.join(src_dir, f'Moth-{code}.csv')
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(filtered)
    print(f'Wrote {out_path}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('Usage: py _merge_xray.py <CODE> [MIN_REVENUE]')
    code = sys.argv[1].upper()
    min_rev = float(sys.argv[2]) if len(sys.argv) > 2 else MIN_REVENUE_DEFAULT
    merge(code, min_rev)
