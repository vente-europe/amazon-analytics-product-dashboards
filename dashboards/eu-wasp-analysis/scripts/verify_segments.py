"""
Verify segment assignment + add Wasp confirmation column for EU Wasp dashboard.

For each ASIN in data/x-ray/{CODE}/Wasp {CODE}.csv:
  1. Fetch catalog (title + bullets) via SP-API, cache to data/catalog-cache/{CODE}/{ASIN}.json
  2. Re-classify Segment as Lure / Electric / Sticky (or blank if non-wasp / unclassifiable)
     using language-specific keyword matching against title + bullets.
  3. Add Wasp column right after Segment: 'Wasp' if local-language wasp word
     (Wespe/guêpe/wasp) appears at least once in title or bullets; else blank.
  4. Write back to the same CSV (Wasp column inserted after Segment).

Usage:
    py scripts/verify_segments.py DE
    py scripts/verify_segments.py FR
    py scripts/verify_segments.py UK
"""
import os, json, time, sys, csv, re, requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

ENV_PATH = r'c:\AI Workspaces\Claude Code Workspace - Tom\.env'
load_dotenv(ENV_PATH)

CLIENT_ID     = os.getenv('SP_API_CLIENT_ID')
CLIENT_SECRET = os.getenv('SP_API_CLIENT_SECRET')
REFRESH_TOKEN = os.getenv('SP_API_REFRESH_TOKEN')

MARKETPLACES = {
    'DE': ('A1PA6795UKMFR9',  'https://sellingpartnerapi-eu.amazon.com'),
    'FR': ('A13V1IB3VIYZZH',  'https://sellingpartnerapi-eu.amazon.com'),
    'UK': ('A1F83G8C2ARO7P',  'https://sellingpartnerapi-eu.amazon.com'),
    'IT': ('APJ6JRA9NG5V4',   'https://sellingpartnerapi-eu.amazon.com'),
    'ES': ('A1RKKUPIHCS9HS',  'https://sellingpartnerapi-eu.amazon.com'),
}

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# --- Language-specific keyword sets (lowercase). Word boundaries used where partial matches
# would cause false positives (e.g. r'\bleim' avoids matching "Mülleimer"). ---
KEYWORDS = {
    'DE': {
        'wasp':     [r'wespe'],  # 'wespen' is captured by 'wespe' as substring
        'lure':     [r'köder', r'lockstoff', r'lockmittel', r'lockfl(ü|u)ssig', r'lockfalle',
                     r'anlocken', r'attraktant'],
        'electric': [r'elektrisch', r'elektronisch', r'\buv\b', r'uv-licht', r'insektenvernichter',
                     r'insektenkiller', r'elektrofalle', r'm(ü|u)ckenkiller', r'fliegenkiller',
                     r'fliegenklatsche'],
        'sticky':   [r'klebefall', r'klebepad', r'klebeband', r'klebrig', r'\bleim',
                     r'klebetafel', r'klebestreifen', r'klebstoff', r'fliegenpapier',
                     r'klebrolle', r'klebfolie', r'gelbtafel', r'gelbsticker', r'gelbsticke',
                     r'gelb-?steck'],
        # Patterns that indicate the product is a TRAP (used for default-to-Lure)
        'trap':     [r'falle', r'wespenfalle', r'insektenfalle'],
        # Excluded wasp-mentions that don't refer to pest wasps (parasitic Schlupfwespe etc.)
        'wasp_excl': [r'schlupfwespe'],
    },
    'FR': {
        'wasp':     [r'gu(ê|e)pe'],
        'lure':     [r'app(â|a)t', r'leurre', r'attractif', r'attractive', r'attractant',
                     r'appeau', r'attire[- ]gu(ê|e)pe'],
        'electric': [r'(é|e)lectrique', r'(é|e)lectronique', r'\buv\b', r'uv-', r'destructeur',
                     r'tue[- ]mouches?\s+(é|e)lectr', r'tueur\s+d', r'tapette\s+(é|e)lectr',
                     r'raquette\s+(é|e)lectr', r'lampe\s+anti'],
        'sticky':   [r'\bcollant', r'collante', r'\bglu\b', r'\bglue\s', r'\bgluau', r'adh(é|e)sif',
                     r'pi(è|e)ge\s+collant', r'ruban\s+adh', r'plaque\s+jaune', r'plaques?\s+jaunes?',
                     r'engluage', r'panneau\s+jaune'],
        'trap':     [r'pi(è|e)ge', r'pi(è|e)ge\s+(à|a)\s+gu(ê|e)pe', r'attrape[- ]gu(ê|e)pe'],
        'wasp_excl': [r'gu(ê|e)pe[- ]parasit', r'micro[- ]?gu(ê|e)pe'],
    },
    'UK': {
        'wasp':     [r'wasp'],
        'lure':     [r'\blure\b', r'\blures\b', r'\bbait\b', r'\bbaits\b', r'attractant',
                     r'attractor', r'pheromone', r'attract\s+wasp'],
        'electric': [r'\belectric\b', r'\belectronic\b', r'\buv\b', r'uv[- ]light', r'zapper',
                     r'electrocut', r'\bbug\s+zapper', r'fly\s+killer\s+lamp', r'insect\s+killer\s+lamp',
                     r'mosquito\s+killer\s+lamp', r'electric\s+(fly|insect|mosquito|wasp)'],
        'sticky':   [r'sticky', r'\bglue\b', r'glued', r'adhesive', r'sticky\s+trap',
                     r'\btrap\s+pad', r'yellow\s+sticky', r'\bglue\s+trap', r'\bglue\s+board'],
        'trap':     [r'\btrap\b', r'\btraps\b', r'wasp\s+trap'],
        'wasp_excl': [r'parasitic\s+wasp', r'parasitoid\s+wasp'],
    },
}

# Heuristic: confidence ranking — a stronger keyword (e.g. "lure" in title) wins over
# weak signals (e.g. "led" alone).
TITLE_WEIGHT = 3
BULLET_WEIGHT = 1

# Product-type detection from TITLE only. Products where the title clearly describes
# a non-trap MECHANISM (spray, smoke, fan, ultrasonic deterrent, fake-nest decoy,
# repellent, killer-nest-removal foam, etc.) fall outside the Lure/Electric/Sticky
# segmentation → force segment blank.
# IMPORTANT: only mechanism-based exclusions here. Different pest types (fungus gnat,
# fruit fly, moth, etc.) are still legitimate Lure/Electric/Sticky traps — they just
# have Wasp=blank in the Wasp column.
NON_TRAP_TYPES = {
    'DE': [
        r'\bspray\b', r'sprühflasche', r'wespenschaum', r'\bschaum\b',
        r'räucher', r'\brauch\b', r'\bduft\b', r'\bvape\b', r'aerosol',
        r'wedler', r'ventilator', r'fliegenwedler', r'wespenwedler',
        r'ultraschall', r'\battrapp', r'fake[- ]?nest',
        r'gefälschte', r'künstliche\s+wespennes', r'künstliches\s+wespennes',
        r'wespennest\s+blocker', r'wespennest\s+kleber',
    ],
    'FR': [
        r'\bspray\b', r'\baérosol', r'\bbombe\b', r'\bmousse\b',
        r'fum(é|e)e', r'fumig(è|e)ne', r'encens',
        r'éventail', r'ventilateur',
        r'ultrason', r'\bappât\s+factice', r'leurre.*nid', r'faux\s+nid',
        r'insecticide', r'\bhuile\s+action', r'foudroyant',
    ],
    'UK': [
        r'\bspray\b', r'\baerosol', r'\bfoam\b',
        r'\bsmoke\b', r'\bfumig', r'\bincense',
        r'\bfan\b', r'whisk',
        r'ultrasonic', r'fake\s+nest', r'fake\s+\w+\s+nest', r'decoy\s+nest', r'\bdecoy\b',
    ],
}


def get_access_token():
    print('Getting LWA access token...')
    resp = requests.post('https://api.amazon.com/auth/o2/token', data={
        'grant_type':    'refresh_token',
        'refresh_token': REFRESH_TOKEN,
        'client_id':     CLIENT_ID,
        'client_secret': CLIENT_SECRET,
    })
    resp.raise_for_status()
    return resp.json()['access_token']


def fetch_catalog_item(asin, token, marketplace_id, endpoint):
    url = f'{endpoint}/catalog/2022-04-01/items/{asin}'
    params = {
        'marketplaceIds': marketplace_id,
        'includedData':   'summaries,attributes',
    }
    headers = {
        'x-amz-access-token': token,
        'user-agent': 'EUWaspDashboard/1.0',
    }
    resp = requests.get(url, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()


def parse_item(raw):
    out = {'asin': raw.get('asin', ''), 'title': '', 'bullet_points': []}
    summaries = raw.get('summaries', [])
    if summaries:
        out['title'] = summaries[0].get('itemName', '')
    attrs = raw.get('attributes', {})
    if 'bullet_point' in attrs:
        for bp in attrs['bullet_point']:
            v = bp.get('value', '')
            if v:
                out['bullet_points'].append(v)
    return out


def detect_non_trap(title_lower, lang):
    """Return matched non-trap pattern if title indicates non-trap product, else None."""
    for pat in NON_TRAP_TYPES.get(lang, []):
        if re.search(pat, title_lower):
            return pat
    return None


def score_segment(text_title, text_bullets, kw, lang='DE'):
    """Return (segment, has_wasp, debug_scores). Segment is 'Lure'|'Electric'|'Sticky'|''."""
    t = (text_title or '').lower()
    b = ('\n'.join(text_bullets) if text_bullets else '').lower()

    # Filter out parasitic-wasp / Schlupfwespe-style mentions before checking for wasp word
    t_filt, b_filt = t, b
    for pat in kw.get('wasp_excl', []):
        t_filt = re.sub(pat, ' ', t_filt)
        b_filt = re.sub(pat, ' ', b_filt)

    has_wasp = any(re.search(p, t_filt) for p in kw['wasp']) or \
               any(re.search(p, b_filt) for p in kw['wasp'])

    # If title clearly indicates a non-trap product type, force segment blank
    non_trap = detect_non_trap(t, lang)

    scores = {'Lure': 0, 'Electric': 0, 'Sticky': 0}
    label_map = {'lure': 'Lure', 'electric': 'Electric', 'sticky': 'Sticky'}

    for key in ('lure', 'electric', 'sticky'):
        for pat in kw[key]:
            for _ in re.findall(pat, t):
                scores[label_map[key]] += TITLE_WEIGHT
            for _ in re.findall(pat, b):
                scores[label_map[key]] += BULLET_WEIGHT

    # Detect if product is a trap (used for default-to-Lure rule)
    is_trap = any(re.search(p, t) for p in kw.get('trap', [])) or \
              any(re.search(p, b) for p in kw.get('trap', []))

    # Non-trap product types fall outside Lure/Electric/Sticky → blank segment
    if non_trap:
        scores['_non_trap'] = non_trap
        return '', has_wasp, scores

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        # No explicit segment signal. If wasp + trap, default to Lure (most non-electric,
        # non-sticky wasp traps are bait/lure traps).
        if has_wasp and is_trap:
            return 'Lure', has_wasp, scores
        return '', has_wasp, scores

    return best, has_wasp, scores


def main():
    if len(sys.argv) < 2:
        print('Usage: py scripts/verify_segments.py <DE|FR|UK>')
        sys.exit(1)
    code = sys.argv[1].upper()
    if code not in MARKETPLACES:
        print(f'Unknown country: {code}')
        sys.exit(1)
    marketplace_id, endpoint = MARKETPLACES[code]
    kw = KEYWORDS[code]

    csv_path = os.path.join(BASE, 'data', 'x-ray', code, f'Wasp {code}.csv')
    cache_dir = os.path.join(BASE, 'data', 'catalog-cache', code)
    os.makedirs(cache_dir, exist_ok=True)

    # Read CSV
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        rows = list(reader)
    header = rows[0]
    data_rows = rows[1:]

    # Locate columns
    try:
        asin_idx = header.index('ASIN')
        seg_idx = header.index('Segment')
    except ValueError:
        print(f'Required columns missing in {csv_path}. Header: {header}')
        sys.exit(1)

    # If Wasp column already exists, drop it (we'll re-add in correct position)
    if 'Wasp' in header:
        wasp_idx = header.index('Wasp')
        header.pop(wasp_idx)
        for r in data_rows:
            if len(r) > wasp_idx:
                r.pop(wasp_idx)
        # Recompute indices after pop
        seg_idx = header.index('Segment')

    asins = [r[asin_idx].strip() for r in data_rows if len(r) > asin_idx and r[asin_idx].strip()]
    print(f'{code}: {len(data_rows)} rows, {len(asins)} ASINs')

    # Determine which need fetching
    to_fetch = []
    for asin in asins:
        out_path = os.path.join(cache_dir, f'{asin}.json')
        if not os.path.exists(out_path):
            to_fetch.append(asin)
    print(f'Cached: {len(asins) - len(to_fetch)}, to fetch: {len(to_fetch)}')

    if to_fetch:
        token = get_access_token()
        ok = err = 0
        for i, asin in enumerate(to_fetch, 1):
            print(f'[{i}/{len(to_fetch)}] Fetching {asin}...', end=' ')
            try:
                raw = fetch_catalog_item(asin, token, marketplace_id, endpoint)
                parsed = parse_item(raw)
                with open(os.path.join(cache_dir, f'{asin}.json'), 'w', encoding='utf-8') as f:
                    json.dump(parsed, f, indent=2, ensure_ascii=False)
                print(f'ok ({len(parsed["bullet_points"])} bullets)')
                ok += 1
            except requests.exceptions.HTTPError as e:
                code_str = e.response.status_code
                msg = e.response.text[:160]
                print(f'ERR {code_str}: {msg}')
                # Save empty so we don't retry forever; can be deleted manually
                with open(os.path.join(cache_dir, f'{asin}.json'), 'w', encoding='utf-8') as f:
                    json.dump({'asin': asin, 'title': '', 'bullet_points': [], 'error': f'{code_str}'}, f)
                err += 1
            except Exception as e:
                print(f'EXC: {e}')
                err += 1
            time.sleep(0.6)
        print(f'Fetch done: {ok} ok, {err} err')

    # Build new header: insert "Wasp" after "Segment"
    new_header = header[:seg_idx + 1] + ['Wasp'] + header[seg_idx + 1:]

    # Process each row
    new_rows = [new_header]
    summary = {'total': 0, 'wasp': 0, 'reclassified': 0, 'cleared': 0,
               'classified_lure': 0, 'classified_electric': 0,
               'classified_sticky': 0, 'classified_blank': 0,
               'no_data': 0}
    changes = []
    wasp_log = []  # (asin, segment, scores, title)

    for r in data_rows:
        asin = r[asin_idx].strip() if len(r) > asin_idx else ''
        old_seg = r[seg_idx].strip() if len(r) > seg_idx else ''

        cache_path = os.path.join(cache_dir, f'{asin}.json')
        title, bullets = '', []
        if asin and os.path.exists(cache_path):
            try:
                with open(cache_path, encoding='utf-8') as f:
                    item = json.load(f)
                title = item.get('title', '')
                bullets = item.get('bullet_points', [])
            except Exception:
                pass

        if not title and not bullets:
            new_seg = ''
            wasp = ''
            summary['no_data'] += 1
            scores = {}
        else:
            new_seg, has_wasp, scores = score_segment(title, bullets, kw, lang=code)
            wasp = 'Wasp' if has_wasp else ''

        summary['total'] += 1
        if wasp == 'Wasp':
            summary['wasp'] += 1
        if new_seg == 'Lure':       summary['classified_lure'] += 1
        elif new_seg == 'Electric': summary['classified_electric'] += 1
        elif new_seg == 'Sticky':   summary['classified_sticky'] += 1
        else:                       summary['classified_blank'] += 1

        if new_seg != old_seg:
            summary['reclassified'] += 1
            if old_seg and not new_seg:
                summary['cleared'] += 1
            changes.append((asin, old_seg, new_seg, wasp, title[:80]))

        if wasp == 'Wasp':
            wasp_log.append((asin, new_seg, scores, title[:90]))

        # Insert Wasp value at seg_idx + 1
        new_row = r[:seg_idx + 1] + [wasp] + r[seg_idx + 1:]
        # Update Segment with new value
        new_row[seg_idx] = new_seg
        new_rows.append(new_row)

    # Write back
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)

    # Print summary
    print('\n=== Summary ===')
    for k, v in summary.items():
        print(f'  {k:25s}: {v}')

    if changes:
        print(f'\n=== {len(changes)} segment changes (showing first 60) ===')
        print(f'{"ASIN":<12} {"OLD":<10} {"NEW":<10} {"WASP":<6} TITLE')
        for asin, old, new, w, t in changes[:60]:
            print(f'{asin:<12} {old:<10} {new:<10} {w:<6} {t}')
        if len(changes) > 60:
            print(f'... {len(changes) - 60} more')

    if wasp_log:
        print(f'\n=== {len(wasp_log)} WASP-marked products (verify segment) ===')
        print(f'{"ASIN":<12} {"SEG":<10} {"L/E/S":<10} TITLE')
        for asin, seg, scores, t in wasp_log:
            les = f'{scores.get("Lure",0)}/{scores.get("Electric",0)}/{scores.get("Sticky",0)}'
            print(f'{asin:<12} {seg or "(blank)":<10} {les:<10} {t}')

    print(f'\nWrote: {csv_path}')


if __name__ == '__main__':
    main()
