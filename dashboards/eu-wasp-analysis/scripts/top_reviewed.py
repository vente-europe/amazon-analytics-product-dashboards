"""
Top 5 ASINs by Review Count per (country, segment) for wasp-marked products.
Reads data/x-ray/{CODE}/Wasp {CODE}.csv files written by verify_segments.py.

Usage:
    py scripts/top_reviewed.py            # all 3 countries, prints to stdout
    py scripts/top_reviewed.py --csv      # also writes top_reviewed.csv at project root
"""
import os, sys, csv

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
COUNTRIES = ['DE', 'FR', 'UK']
SEGMENTS = ['Lure', 'Electric', 'Sticky']
TOP_N = 5


def parse_int(s):
    """Parse '23,429' -> 23429. Returns 0 on failure / N/A."""
    s = (s or '').strip().replace(',', '').replace('.', '')
    if not s or s.upper() == 'N/A':
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def parse_float(s):
    s = (s or '').strip().replace(',', '')
    if not s or s.upper() == 'N/A':
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_country(code):
    # UK file was renamed to "Wasps UK.csv"; DE/FR still use "Wasp {CODE}.csv"
    fname = f'Wasps {code}.csv' if code == 'UK' else f'Wasp {code}.csv'
    path = os.path.join(BASE, 'data', 'x-ray', code, fname)
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    hdr = rows[0]
    idx = {col: hdr.index(col) for col in
           ['ASIN', 'Segment', 'Wasp', 'Brand', 'Product Details',
            'Review Count', 'Ratings']}
    items = []
    for r in rows[1:]:
        items.append({
            'asin':    r[idx['ASIN']].strip(),
            'segment': r[idx['Segment']].strip(),
            'wasp':    r[idx['Wasp']].strip(),
            'brand':   r[idx['Brand']].strip(),
            'title':   r[idx['Product Details']].strip(),
            'reviews': parse_int(r[idx['Review Count']]),
            'rating':  parse_float(r[idx['Ratings']]),
        })
    return items


def main():
    write_csv = '--csv' in sys.argv

    all_top = []  # for combined CSV
    for code in COUNTRIES:
        items = load_country(code)
        wasp_items = [x for x in items if x['wasp'] == 'Wasp']
        print(f'\n========== {code} ==========')
        print(f'(total: {len(items)} rows, wasp-marked: {len(wasp_items)})')

        for seg in SEGMENTS:
            seg_items = [x for x in wasp_items if x['segment'] == seg]
            seg_items.sort(key=lambda x: x['reviews'], reverse=True)
            top = seg_items[:TOP_N]
            print(f'\n--- {code} {seg} (n={len(seg_items)}) ---')
            if not top:
                print('  (none)')
                continue
            print(f'  {"#":>2}  {"ASIN":<12} {"Reviews":>8} {"Rating":>7}  {"Brand":<22} TITLE')
            for i, x in enumerate(top, 1):
                print(f'  {i:>2}. {x["asin"]:<12} {x["reviews"]:>8,} {x["rating"]:>7.1f}  '
                      f'{x["brand"][:22]:<22} {x["title"][:80]}')
                all_top.append({
                    'country': code, 'segment': seg, 'rank': i,
                    'asin': x['asin'], 'reviews': x['reviews'], 'rating': x['rating'],
                    'brand': x['brand'], 'title': x['title'],
                })

    if write_csv:
        out_path = os.path.join(BASE, 'top_reviewed.csv')
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['country', 'segment', 'rank', 'asin',
                                              'reviews', 'rating', 'brand', 'title'])
            w.writeheader()
            w.writerows(all_top)
        print(f'\nWrote: {out_path}')


if __name__ == '__main__':
    main()
