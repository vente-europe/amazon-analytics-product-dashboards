#!/usr/bin/env python
"""Fetch title + bullets for merged UK ASINs via DataForSEO, cache to _uk_listings.json.
Parallel (thread pool). Credentials read from workspace .env (never hardcoded)."""
import os, sys, io, json, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ENV = r"c:/AI Workspaces/Claude Code Workspace - Tom/.env"
def load_env():
    u = p = None
    for line in open(ENV, encoding='utf-8'):
        if line.startswith('DATAFORSEO_USERNAME='): u = line.split('=', 1)[1].strip()
        if line.startswith('DATAFORSEO_PASSWORD='): p = line.split('=', 1)[1].strip()
    return u, p

U, P = load_env()
API = 'https://api.dataforseo.com/v3/merchant/amazon/asin/live/advanced'

raw = json.load(open('_uk_merged_raw.json', encoding='utf-8'))
asins = [r['ASIN'].strip() for r in raw['rows']]

CACHE = '_uk_listings.json'
cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}
lock = Lock()

todo = [a for a in asins if a not in cache or not cache[a].get('title')]
print(f'total {len(asins)}, cached {len(cache)}, to fetch {len(todo)}', flush=True)

def flatten_pi(pi):
    out = []
    if isinstance(pi, list):
        for sec in pi:
            for c in (sec.get('contents') or []):
                for row in (c.get('rows') or []):
                    if row.get('text'): out.append(row['text'])
                if c.get('title'): out.append(c['title'])
    return ' '.join(out)

def fetch(a):
    try:
        post = [{'asin': a, 'location_name': 'United Kingdom', 'language_code': 'en_GB'}]
        r = requests.post(API, auth=(U, P), json=post, timeout=180)
        task = r.json()['tasks'][0]
        res = task.get('result')
        if not res:
            return a, {'title': '', 'bullets': '', 'product_information': '',
                       'error': f"{task.get('status_code')}:{task.get('status_message')}"[:120]}
        items = res[0].get('items') or []
        item = next((it for it in items if it.get('type') == 'amazon_product_info' or it.get('title')), None)
        if item:
            return a, {'title': item.get('title') or '', 'bullets': item.get('description') or '',
                       'product_information': flatten_pi(item.get('product_information'))}
        return a, {'title': '', 'bullets': '', 'product_information': '', 'miss': True}
    except Exception as e:
        return a, {'title': '', 'bullets': '', 'product_information': '', 'error': str(e)[:120]}

done = 0
with ThreadPoolExecutor(max_workers=5) as ex:
    futs = [ex.submit(fetch, a) for a in todo]
    for f in as_completed(futs):
        a, v = f.result()
        with lock:
            cache[a] = v
            done += 1
            if done % 20 == 0:
                json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
                print(f'  {done}/{len(todo)} ...', flush=True)

json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
got = sum(1 for a in asins if cache.get(a, {}).get('title'))
print(f'done. listings with title: {got}/{len(asins)}', flush=True)
