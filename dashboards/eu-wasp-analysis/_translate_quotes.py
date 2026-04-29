"""Translate quotes (negativeTopics/positiveTopics) and reviews[].t to English
in DE and FR voc.json files. UK files unchanged. Uses deep_translator + a local
cache so re-runs are cheap.

Run: py _translate_quotes.py
"""
import json, os, sys, time
sys.stdout.reconfigure(encoding='utf-8')
from deep_translator import GoogleTranslator

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE, '_translate_cache.json')

# Load cache
cache = {}
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH, encoding='utf-8') as f:
        cache = json.load(f)

# One translator per source language
TRANSLATORS = {
    'de': GoogleTranslator(source='de', target='en'),
    'fr': GoogleTranslator(source='fr', target='en'),
}


def tr(text, src):
    if not text or not text.strip():
        return text
    key = f'{src}::{text}'
    if key in cache:
        return cache[key]
    # Google Translate has a 5000-char limit per request; chunk if needed
    if len(text) > 4500:
        # split on sentence-ish boundaries
        parts = []
        buf = ''
        for piece in text.split('. '):
            if len(buf) + len(piece) > 4000:
                parts.append(buf)
                buf = piece
            else:
                buf = (buf + '. ' + piece) if buf else piece
        if buf:
            parts.append(buf)
        out = ' '.join(TRANSLATORS[src].translate(p) for p in parts)
    else:
        out = TRANSLATORS[src].translate(text)
    cache[key] = out
    return out


def save_cache():
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def translate_voc(path, src):
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    n_quotes = 0
    n_reviews = 0
    for k in ('negativeTopics', 'positiveTopics'):
        for t in d.get(k, []):
            if t.get('quotes'):
                t['quotes'] = [tr(q, src) for q in t['quotes']]
                n_quotes += len(t['quotes'])
    for r in d.get('reviews', []):
        if r.get('t'):
            r['t'] = tr(r['t'], src)
            n_reviews += 1
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    return n_quotes, n_reviews


JOBS = [
    ('reviews/DE/Lure/voc.json', 'de'),
    ('reviews/DE/Electric/voc.json', 'de'),
    ('reviews/FR/Lure/voc.json', 'fr'),
    ('reviews/FR/Electric/voc.json', 'fr'),
]

t0 = time.time()
for path, src in JOBS:
    full = os.path.join(BASE, path.replace('/', os.sep))
    print(f'Translating {path} ({src} -> en) ...')
    sys.stdout.flush()
    nq, nr = translate_voc(full, src)
    save_cache()  # save after each file in case of interruption
    elapsed = time.time() - t0
    print(f'  {nq} quotes + {nr} review-texts done. Elapsed: {elapsed:.0f}s. Cache size: {len(cache)}')
print('All done.')
