"""
Fetch product listing data from Amazon SP-API Catalog Items API for EU lice dashboard.
Reads ASINs from data/competitor-listings/{CODE}/asins-{segment}.txt, writes one JSON
per ASIN to data/competitor-listings/{CODE}/raw/{ASIN}.json.

Usage:
    py scripts/fetch_competitor_listings.py DE prevention
    py scripts/fetch_competitor_listings.py DE treatment
"""
import os, json, time, sys, requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

ENV_PATH = r'c:\AI Workspaces\Claude Code Workspace - Tom\.env'
load_dotenv(ENV_PATH)

CLIENT_ID     = os.getenv('SP_API_CLIENT_ID')
CLIENT_SECRET = os.getenv('SP_API_CLIENT_SECRET')
REFRESH_TOKEN = os.getenv('SP_API_REFRESH_TOKEN')

MARKETPLACES = {
    'DE': 'A1PA6795UKMFR9',
    'FR': 'A13V1IB3VIYZZH',
    'IT': 'APJ6JRA9NG5V4',
    'ES': 'A1RKKUPIHCS9HS',
}
ENDPOINT = 'https://sellingpartnerapi-eu.amazon.com'

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

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

def fetch_catalog_item(asin, token, marketplace_id):
    url = f'{ENDPOINT}/catalog/2022-04-01/items/{asin}'
    params = {
        'marketplaceIds': marketplace_id,
        'includedData':   'images,summaries,attributes,productTypes',
    }
    headers = {
        'x-amz-access-token': token,
        'user-agent': 'EULiceDashboard/1.0',
    }
    resp = requests.get(url, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()

def parse_item(raw):
    result = {'asin': raw.get('asin', '')}
    summaries = raw.get('summaries', [])
    if summaries:
        s = summaries[0]
        result['title'] = s.get('itemName', '')
        result['brand'] = s.get('brand', '')
        result['browse_classification'] = s.get('browseClassification', {}).get('displayName', '')

    images_data = raw.get('images', [])
    images = []
    if images_data:
        for img in images_data[0].get('images', []):
            images.append({
                'variant': img.get('variant', ''),
                'url':     img.get('link', ''),
                'width':   img.get('width', 0),
                'height':  img.get('height', 0),
            })
    def sort_key(x):
        v = x['variant']
        if v == 'MAIN': return 0
        if v.startswith('PT'):
            try: return int(v[2:])
            except: return 99
        return 99
    images.sort(key=sort_key)
    result['images'] = images

    attrs = raw.get('attributes', {})
    bullets = []
    if 'bullet_point' in attrs:
        for bp in attrs['bullet_point']:
            val = bp.get('value', '')
            if val: bullets.append(val)
    result['bullet_points'] = bullets

    descs = []
    if 'product_description' in attrs:
        for d in attrs['product_description']:
            v = d.get('value', '')
            if v: descs.append(v)
    result['description'] = '\n\n'.join(descs)

    pt = raw.get('productTypes', [])
    result['product_type'] = pt[0].get('productType', '') if pt else ''
    return result

def main():
    if len(sys.argv) < 3:
        print('Usage: py scripts/fetch_competitor_listings.py <CODE> <prevention|treatment>')
        sys.exit(1)
    code = sys.argv[1].upper()
    segment = sys.argv[2].lower()
    if code not in MARKETPLACES:
        print(f'Unknown country: {code}')
        sys.exit(1)

    asin_file = os.path.join(BASE, 'data', 'competitor-listings', code, f'asins-{segment}.txt')
    raw_dir   = os.path.join(BASE, 'data', 'competitor-listings', code, 'raw')
    os.makedirs(raw_dir, exist_ok=True)

    with open(asin_file) as f:
        asins = [l.strip() for l in f if l.strip()]
    print(f'{code}/{segment}: {len(asins)} ASINs')

    token = get_access_token()
    ok = err = 0
    for asin in asins:
        out_path = os.path.join(raw_dir, f'{asin}.json')
        if os.path.exists(out_path):
            print(f'  {asin} — cached')
            ok += 1
            continue
        print(f'Fetching {asin}...')
        try:
            raw = fetch_catalog_item(asin, token, MARKETPLACES[code])
            parsed = parse_item(raw)
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)
            print(f'  {parsed.get("brand","?")} — {len(parsed["images"])} imgs, {len(parsed["bullet_points"])} bullets')
            ok += 1
        except requests.exceptions.HTTPError as e:
            print(f'  ERROR {e.response.status_code}: {e.response.text[:200]}')
            err += 1
        time.sleep(1)

    print(f'\nDone. {ok} ok, {err} errors. Raw JSONs in: {raw_dir}')

if __name__ == '__main__':
    main()
