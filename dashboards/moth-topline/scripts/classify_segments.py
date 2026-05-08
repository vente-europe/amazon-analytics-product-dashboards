"""Classify each ASIN in Moth-{CODE}.csv as Killer Spray / Physical Trap / Repellent.

Reads SP-API listing JSON from data/competitor-listings/{CODE}/raw/{ASIN}.json
(produced by scripts/fetch_listings.py) and scores title + bullets + description
against multilingual keyword sets per segment. The highest-scoring segment wins;
ties or all-zero rows are marked "Check" for manual review.

Output: rewrites data/x-ray/{CODE}/Moth-{CODE}.csv with a new "Segment" column
inserted as the 3rd column (after ASIN), per Console convention.

Usage:
    py scripts/classify_segments.py DE
"""
import csv
import glob
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Manual overrides — ASINs the keyword classifier can't disambiguate.
# Keyed by ASIN, value is the segment to assign. Resolved BEFORE scoring.
OVERRIDES = {
    # DE
    'B07VJGXFLN': 'Physical Trap',  # Legona ichneumon wasps (biological control)
    'B0CQP6L1HC': 'Physical Trap',  # Raid Lichtfalle (light trap) refill
    # UK
    'B01HZ7LLYE': 'Repellent',      # Rentokil Moth Balls
    'B09Q99YWG6': 'Physical Trap',  # Lakeland Moth Stop trap refills
    'B0CV7YYMRD': 'Physical Trap',  # Premium pheromone moth traps
    # ES
    'B073ZLH82Y': 'Repellent',      # ZUM Polillas — perfumes/protects (sachet-style)
    'B0BH98V4VJ': 'Killer Spray',   # Panteer Spray antipolillas 500ml
    'B0DGY19Q3N': 'Physical Trap',  # Orion Trampa Polilla Alimentos (food moth trap)
    # IT
    'B0822HYBT4': 'Physical Trap',  # Schädlingsmeister Pheromone Moth Trap
    'B0FKBTC9WQ': 'Physical Trap',  # Veddelholzer Clothes Moth Trap (triangular)
    'B00UCB67YK': 'Physical Trap',  # Polil Food Moth Detector Trap
    'B00DJ7D8UA': 'Physical Trap',  # Autan Trappola Antitarme (sticky food moth trap)
    'B00FKRFZVW': 'Repellent',      # Nuncas Antitarme sheets (passive cabinet protection)
}

# ── PHYSICAL TRAP — pheromone / sticky / glue traps ────────────────────────
TRAP = [
    'pheromon', 'pheromone', 'feromon', 'lockstoff',
    'klebefalle', 'mottenfalle', 'kleidermottenfalle', 'lebensmittelmottenfalle',
    'mottenfallen', 'klebepad', 'klebepads', 'klebestreifen', 'klebeband',
    'sticky trap', 'glue trap', 'monitoring trap', 'pheromone trap',
    'piege', 'piege a mites', 'piege a phéromones', 'piege a teignes', 'piege adhesif',
    'trampa', 'trampa adhesiva', 'trampa de feromonas', 'trampa para polillas',
    'trappola', 'trappola adesiva', 'trappola a feromoni',
    'fallen', 'falle ',
]

# ── KILLER SPRAY — insecticide sprays, foggers, killing agents ─────────────
KILLER = [
    'spray', 'spruh', 'sprueh', 'sprühen', 'sprühdose', 'aerosol',
    'insektizid', 'insecticide', 'insetticida', 'insecticida',
    'killer', 'kills', 'kill ', 'totet', 'tötet', 'abtotend', 'abtötend', 'vernichtet',
    'mottenspray', 'mottenfrei', 'mottenkiller', 'anti-motten spray',
    'permethrin', 'pyrethrum', 'pyrethroid', 'transfluthrin', 'cypermethrin',
    'pulverizador', 'aerosol antipolillas', 'spray antimotti', 'spray anti-mites',
    'fogger', 'nebler', 'vernebler', 'foam', 'schaum',
    'biozid', 'biocide', 'biocida',
    'elimina', 'eliminates', 'erradica', 'extermine',
]

# ── REPELLENT — lavender, cedar, sachets, mothballs, natural deterrents ────
REPELLENT = [
    'lavendel', 'lavender', 'lavande', 'lavanda',
    'zedernholz', 'zeder', 'zedern', 'cedar', 'cedarwood', 'cedro', 'bois de cedre',
    'sachet', 'sachets', 'sackchen', 'säckchen', 'duftbeutel', 'duftsackchen',
    'pochette', 'bolsita', 'bustina', 'bustine',
    'mottenkugeln', 'mothballs', 'mottenkugel', 'palline antitarme', 'naphthalin',
    'mottenring', 'mottenringe', 'cedar ring', 'cedar ball', 'cedar block',
    'kugel', 'kugeln', 'block', 'blocke', 'blöcke', 'rings',
    'duftspender', 'duft', 'aromatic', 'scented',
    'naturlich', 'natürlich', 'natural', 'naturel', 'naturale',
    'atherisch', 'ätherisch', 'essential oil', 'huile essentielle', 'aceite esencial',
    'olio essenziale', 'essenziale',
    'abwehr', 'repell', 'repellent', 'repellente', 'repulsif', 'anti-mite', 'antimite',
    'mottenschutz', 'mottenabwehr', 'mottenpapier', 'mothproofer',
    'bio', 'organic', 'biologisch',
    'minze', 'mint', 'menthe', 'menta', 'eucalyptus', 'eukalyptus', 'rosmarin', 'rosemary',
    'patchouli', 'tea tree', 'teebaum',
    'wardrobe protection', 'kleiderschutz', 'kleidermotten schutz',
]


def normalize(s):
    if not s:
        return ''
    s = s.lower()
    repl = {'ö':'o','ü':'u','ä':'a','ß':'ss','é':'e','è':'e','ê':'e','à':'a','â':'a',
            'î':'i','ô':'o','û':'u','ç':'c','ñ':'n','á':'a','í':'i','ó':'o','ú':'u'}
    for k, v in repl.items():
        s = s.replace(k, v)
    return s


def score(text, keywords):
    return sum(1 for kw in keywords if kw in text)


def classify(d, csv_title=''):
    asin = d.get('asin', '')
    if asin in OVERRIDES:
        return (OVERRIDES[asin], 'override', {})
    title_raw = d.get('title') or csv_title or ''
    bullets = ' '.join(d.get('bullet_points') or [])
    desc = d.get('description') or ''
    title_n = normalize(title_raw)
    full_n = normalize(title_raw + ' ' + bullets + ' ' + desc)

    # Title carries more signal — weight it 2x
    s_trap     = score(title_n, TRAP)     * 2 + score(full_n, TRAP)
    s_killer   = score(title_n, KILLER)   * 2 + score(full_n, KILLER)
    s_repel    = score(title_n, REPELLENT) * 2 + score(full_n, REPELLENT)

    # Spray + repellent terms together usually = repellent spray (e.g. lavender spray).
    # Only count as Killer Spray if there's a kill/insecticide signal beyond just "spray".
    kill_signal_only = sum(1 for kw in KILLER if kw != 'spray' and kw in full_n)
    if s_killer > 0 and kill_signal_only == 0 and s_repel > 0:
        s_killer = 0

    scores = {'Physical Trap': s_trap, 'Killer Spray': s_killer, 'Repellent': s_repel}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return ('Check', 'no keywords matched', scores)
    # Tie between top two?
    sorted_scores = sorted(scores.values(), reverse=True)
    if sorted_scores[0] == sorted_scores[1]:
        return ('Check', f'tie {scores}', scores)
    return (best, f'score={scores[best]}', scores)


def insert_segment_column(rows, header, asin_to_segment):
    """Return (new_header, new_rows) with Segment inserted after ASIN."""
    if 'ASIN' not in header:
        sys.exit('CSV has no ASIN column')
    a_idx = header.index('ASIN')

    if 'Segment' in header:
        # Already present — just refresh values
        s_idx = header.index('Segment')
        new_rows = [list(r) for r in rows]
        for r in new_rows:
            asin = (r[a_idx] if len(r) > a_idx else '').strip()
            if asin in asin_to_segment:
                while len(r) <= s_idx:
                    r.append('')
                r[s_idx] = asin_to_segment[asin]
        return header, new_rows

    # Insert at position a_idx + 1
    insert_at = a_idx + 1
    new_header = list(header[:insert_at]) + ['Segment'] + list(header[insert_at:])
    new_rows = []
    for r in rows:
        asin = (r[a_idx] if len(r) > a_idx else '').strip()
        seg = asin_to_segment.get(asin, 'Check')
        new_rows.append(list(r[:insert_at]) + [seg] + list(r[insert_at:]))
    return new_header, new_rows


def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: py scripts/classify_segments.py <CODE>')
    code = sys.argv[1].upper()

    raw_dir = os.path.join(BASE, 'data', 'competitor-listings', code, 'raw')
    csv_path = os.path.join(BASE, 'data', 'x-ray', code, f'Moth-{code}.csv')
    if not os.path.isdir(raw_dir):
        sys.exit(f'No raw folder: {raw_dir}')
    if not os.path.isfile(csv_path):
        sys.exit(f'No merged CSV: {csv_path}')

    # Load CSV first (we'll need title fallback for ASINs missing JSON)
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        rows_in = list(csv.reader(f))
    header = rows_in[0]
    body = rows_in[1:]
    asin_idx = header.index('ASIN')
    title_idx = header.index('Product Details') if 'Product Details' in header else None

    csv_titles = {}
    for r in body:
        if len(r) > asin_idx:
            asin = r[asin_idx].strip()
            if asin and title_idx is not None and len(r) > title_idx:
                csv_titles[asin] = r[title_idx]

    # Classify every JSON we have
    results = {}  # asin → (segment, reason, scores)
    json_files = sorted(glob.glob(os.path.join(raw_dir, '*.json')))
    print(f'Classifying {len(json_files)} listings...')
    for fp in json_files:
        try:
            d = json.load(open(fp, encoding='utf-8'))
        except Exception as e:
            print(f'  skip {os.path.basename(fp)}: {e}')
            continue
        asin = d.get('asin', '') or os.path.splitext(os.path.basename(fp))[0]
        results[asin] = classify(d, csv_titles.get(asin, ''))

    # ASINs in CSV without a JSON fall back to title-only classification
    title_only = 0
    for r in body:
        asin = (r[asin_idx] if len(r) > asin_idx else '').strip()
        if asin and asin not in results:
            results[asin] = classify({'asin': asin, 'title': csv_titles.get(asin, '')}, csv_titles.get(asin, ''))
            title_only += 1
    if title_only:
        print(f'  ({title_only} ASINs classified from title only — no SP-API data)')

    asin_to_seg = {a: r[0] for a, r in results.items()}

    new_header, new_body = insert_segment_column(body, header, asin_to_seg)
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(new_header)
        w.writerows(new_body)

    cnt = Counter(r[0] for r in results.values())
    print(f'\n{code} segment counts:')
    for k in ['Killer Spray', 'Physical Trap', 'Repellent', 'Check']:
        print(f'  {k}: {cnt.get(k, 0)}')
    print(f'  TOTAL: {sum(cnt.values())}')
    print(f'\nWrote {csv_path}')

    # Show Check rows so user can review
    check_rows = [(a, r) for a, r in results.items() if r[0] == 'Check']
    if check_rows:
        print(f'\n{len(check_rows)} rows flagged "Check" (manual review):')
        for asin, (seg, reason, scores) in check_rows[:15]:
            t = (csv_titles.get(asin, '') or '')[:80]
            print(f'  {asin}  [{reason}]  {t}')
        if len(check_rows) > 15:
            print(f'  ... and {len(check_rows) - 15} more')


if __name__ == '__main__':
    main()
