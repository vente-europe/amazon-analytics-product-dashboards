"""
Wyprodukuj audyt klasyfikacji: dla każdego ASIN-a wypluje jakiego segmentu
dostał, który sygnał niszy go trafił (i w którym polu: Title/Bullets/Desc)
oraz który słowo-klucz formy produktu go zakwalifikowało do Cream/Wash/Oil.

Wynik: plik audit-{CODE}.md w katalogu dashboardu + wydruk do stdout.

Użycie:  py scripts/audit_segments.py DE
"""
import csv, json, glob, os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify_segments import NICHE_STRONG, FORM_WASH, FORM_OIL, FORM_CREAM, EXCLUDE, text_lower

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def find_hits_in(field_name, field_text, patterns):
    """Zwraca listę trafień w danym polu (z etykietą skąd: T/B/D)."""
    low = text_lower(field_text)
    return [(p, field_name) for p in patterns if p in low]

def audit(d):
    title = (d.get('title') or '')
    bullets = ' '.join(d.get('bullet_points') or [])
    desc = (d.get('description') or '')
    title_low = text_lower(title)

    # Exclude (sprawdzane tylko w tytule)
    for pat, reason in EXCLUDE:
        if pat in title_low:
            return {
                'segment': 'Other',
                'why': f'exclude: {reason}',
                'exclude_pattern': pat,
                'niche_hits': [],
                'form_hit': None,
            }

    # Niche hits — per field
    niche_T = find_hits_in('T', title, NICHE_STRONG)
    niche_B = find_hits_in('B', bullets, NICHE_STRONG)
    niche_D = find_hits_in('D', desc, NICHE_STRONG)
    all_niche = niche_T + niche_B + niche_D

    # Form — title only, Wash → Oil → Cream priority
    form_hit = None
    form_label = None
    for t in FORM_WASH:
        if t in title_low:
            form_hit = t; form_label = 'Wash'; break
    if not form_hit:
        for t in FORM_OIL:
            if t in title_low:
                form_hit = t; form_label = 'Oil'; break
    if not form_hit:
        for t in FORM_CREAM:
            if t in title_low:
                form_hit = t; form_label = 'Cream'; break

    if not all_niche:
        return {
            'segment': 'Check',
            'why': 'no niche signal in title+bullets+desc',
            'niche_hits': [],
            'form_hit': form_hit,
            'form_label': form_label,
        }
    if not form_hit:
        return {
            'segment': 'Check',
            'why': 'niche OK but form word missing in title',
            'niche_hits': all_niche[:5],
            'form_hit': None,
            'form_label': None,
        }
    return {
        'segment': form_label,
        'why': f'niche + form ({form_hit})',
        'niche_hits': all_niche[:5],
        'form_hit': form_hit,
        'form_label': form_label,
    }

def main():
    if len(sys.argv) < 2:
        print('Usage: py scripts/audit_segments.py {DE|FR|IT|ES}')
        sys.exit(1)
    code = sys.argv[1].upper()
    csv_path = os.path.join(BASE, 'data', 'x-ray', code, f'Dermo-Products-{code}.csv')
    raw_dir = os.path.join(BASE, 'data', 'competitor-listings', code, 'raw')

    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))

    # mapping ASIN → (brand, title, segment_assigned)
    xray_by_asin = {}
    for r in rows:
        xray_by_asin[(r.get('ASIN') or '').strip()] = {
            'brand': (r.get('Brand') or '').strip(),
            'title': (r.get('Product Details') or '').strip()[:80],
            'segment': (r.get('Segment') or '').strip(),
        }

    # Iteruj po cached SP-API raw JSONach
    results = []
    for fp in sorted(glob.glob(os.path.join(raw_dir, '*.json'))):
        asin = os.path.basename(fp).replace('.json', '')
        if asin not in xray_by_asin:
            continue  # produkt został odfiltrowany <€1000
        try:
            d = json.load(open(fp, encoding='utf-8'))
        except Exception:
            continue
        x = xray_by_asin[asin]
        verdict = audit(d)
        results.append({
            'asin': asin,
            'brand': x['brand'][:18],
            'title': x['title'],
            'assigned_seg': x['segment'],
            **verdict,
        })

    # Sort: segment first, then brand
    seg_order = {'Cream': 0, 'Wash': 1, 'Oil': 2, 'Check': 3, 'Other': 4}
    results.sort(key=lambda r: (seg_order.get(r.get('assigned_seg'), 9), r['brand'].lower()))

    # Zapis do pliku markdown
    out_md = os.path.join(BASE, f'audit-{code}.md')
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write(f'# Audyt klasyfikacji segmentów — {code}\n\n')
        f.write(f'Razem: {len(results)} ASIN.  Klasyfikator czyta: Title (T), Bullets (B), Description (D) — NIGDY zdjęć.\n\n')
        from collections import Counter
        cnt = Counter(r.get('assigned_seg') or 'Empty' for r in results)
        f.write('## Podsumowanie\n\n')
        for seg in ['Cream','Wash','Oil','Check','Other']:
            f.write(f'- **{seg}**: {cnt.get(seg,0)}\n')
        f.write('\n## Per ASIN\n\n')
        f.write('| ASIN | Brand | Seg | Why | Niche hits (where) | Form word |\n')
        f.write('|---|---|---|---|---|---|\n')
        for r in results:
            niche_str = ', '.join(f'`{h[0]}`[{h[1]}]' for h in (r.get('niche_hits') or [])[:4]) or '—'
            form_str = f'`{r["form_hit"]}`' if r.get('form_hit') else '—'
            title_short = r['title'][:55].replace('|','\\|')
            f.write(f'| `{r["asin"]}` | {r["brand"]} | **{r["assigned_seg"]}** | {r["why"]} | {niche_str} | {form_str} |\n')

    print(f'Zapisano: {out_md} ({len(results)} wierszy)')
    print(f'\nPodsumowanie {code}:')
    from collections import Counter
    cnt = Counter(r.get('assigned_seg') or 'Empty' for r in results)
    for seg in ['Cream','Wash','Oil','Check','Other']:
        print(f'  {seg}: {cnt.get(seg,0)}')

if __name__ == '__main__':
    main()
