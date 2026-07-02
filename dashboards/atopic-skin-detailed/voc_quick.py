"""
Quick VOC analysis over a pooled all-reviews.json (original language).

Processes EVERY review (no bulk translation): tags recurring themes via
multilingual keyword sets (FR/IT/ES/EN), splits by sentiment (star rating),
then selects a few representative example quotes per theme and translates
ONLY those to English for review.

Usage:
  python voc_quick.py FR Oil
  python voc_quick.py IT Oil --examples 3

Reads : reviews/<CODE>/<SEG>/all-reviews.json
Writes: reviews/<CODE>/<SEG>/_voc_quick.json   (themes + translated examples)
Prints: a readable summary you can eyeball.
"""
import json, os, sys, re
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
REV = os.path.join(BASE, 'reviews')
EN_CACHE = os.path.join(REV, '_tr_cache_en.json')

# theme -> compiled multilingual keyword regex (FR / IT / ES / EN)
THEMES = {
    'Dry / atopic / eczema skin': r'(s[eè]ch|secch|seca|dry|ecz[eé]?ma|atopi|dermatit|d[eé]mangea|prurit|pican|irrita|sensib|itch)',
    'Stretch marks / pregnancy':  r'(vergetur|smagliatur|estr[ií]as|stretch mark|grossess|gravidanz|embaraz|enceint|incint|pregnan|maternit)',
    'Scars / spots / marks':      r'(cicatri|t[aâ]che|macchi|manch|cicatr|scar|spot|blemish|imperfezion|imperfeccion)',
    'Scent / smell':              r'(odeur|parfum|sent\b|odor|profum|olor|huele|smell|scent|fragran|cacao|cocoa|chocolat|cioccolat)',
    'Greasy / absorption':        r'(gras|grass|collant|colle\b|p[eé]n[eè]tr|absor|unto|appiccic|penetr|greasy|sticky|absorb|graso|pega)',
    'Hydration / nourishing':     r'(hydrat|nourriss|idrata|nutri|hidrata|nutre|moistur|nourish)',
    'Texture / application':      r'(textur|applic|pompe|[eé]tale|flacon|stende|dispenser|aplica|apply|pump|bottle|dosator)',
    'Price / value':              r'(prix|cher\b|co[uû]teux|prezz|caro|costos|econom|price|expensive|cheap|value|precio)',
    'Irritation / allergy':       r'(allergi|r[eé]action|reazion|reacci[oó]n|allerg|breakout|bouton|brufol|granit)',
    'Packaging / delivery':       r'(livrais|emballa|colis|fuite|coul[eé]|consegn|imballa|versato|rotto|perd|entrega|embalaj|deliver|packag|leak|spill|broken)',
    'Effectiveness / results':    r'(efficac|r[eé]sultat|marche|fonctionne|risultat|funziona|result|works?|effective|eficaz|funciona)',
}
THEMES = {k: re.compile(v, re.I) for k, v in THEMES.items()}


def sentiment(r):
    return 'neg' if r <= 2 else ('pos' if r >= 4 else 'neu')


def load(code, seg):
    p = os.path.join(REV, code, seg, 'all-reviews.json')
    return json.load(open(p, encoding='utf-8'))


def blob(rv):
    return (rv.get('title', '') + '. ' + rv.get('review', '')).strip()


def analyze(reviews, n_examples=3):
    total = len(reviews)
    dist = Counter(r['rating'] for r in reviews)
    avg = round(sum(r['rating'] for r in reviews) / total, 2) if total else 0
    out = {}
    for name, rx in THEMES.items():
        hits = [r for r in reviews if rx.search(blob(r))]
        if not hits:
            continue
        buckets = {'neg': [], 'pos': []}
        for r in hits:
            s = sentiment(r['rating'])
            if s in buckets and r.get('review', '').strip():
                buckets[s].append(r)
        # representative = longest bodies (most informative), dedup by first 60 chars
        def pick(rs):
            rs = sorted(rs, key=lambda r: len(r['review']), reverse=True)
            seen, chosen = set(), []
            for r in rs:
                k = r['review'][:60].lower()
                if k in seen:
                    continue
                seen.add(k)
                chosen.append(r)
                if len(chosen) >= n_examples:
                    break
            return chosen
        out[name] = {
            'mentions': len(hits),
            'share': round(100 * len(hits) / total, 1),
            'neg_count': sum(1 for r in hits if r['rating'] <= 2),
            'pos_count': sum(1 for r in hits if r['rating'] >= 4),
            'neg_examples': pick(buckets['neg']),
            'pos_examples': pick(buckets['pos']),
        }
    return {'total': total, 'avg': avg, 'dist': dict(sorted(dist.items())), 'themes': out}


def translate(strings):
    from deep_translator import GoogleTranslator
    cache = json.load(open(EN_CACHE, encoding='utf-8')) if os.path.exists(EN_CACHE) else {}
    todo = sorted({s for s in strings if s.strip() and s not in cache})
    if todo:
        tr = GoogleTranslator(source='auto', target='en')
        for i in range(0, len(todo), 20):
            chunk = todo[i:i + 20]
            try:
                res = tr.translate_batch(chunk)
            except Exception:
                res = []
                for s in chunk:
                    try:
                        res.append(tr.translate(s))
                    except Exception:
                        res.append(s)
            for s, t in zip(chunk, res):
                cache[s] = t or s
        json.dump(cache, open(EN_CACHE, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    return cache


def main():
    args = [a for a in sys.argv[1:]]
    n_ex = 3
    if '--examples' in args:
        i = args.index('--examples'); n_ex = int(args[i + 1]); del args[i:i + 2]
    code, seg = args[0], args[1]
    reviews = load(code, seg)
    res = analyze(reviews, n_ex)

    # gather example strings to translate (only what we display)
    ex_strings = []
    for t in res['themes'].values():
        for r in t['neg_examples'] + t['pos_examples']:
            ex_strings.append(r['review'])
            ex_strings.append(r.get('title', ''))
    cache = translate(ex_strings)

    def en(s):
        return cache.get(s, s)

    # console summary
    print('=' * 72)
    print('%s / %s  |  %d reviews  |  avg %.2f stars  |  dist %s'
          % (code, seg, res['total'], res['avg'], res['dist']))
    print('=' * 72)
    order = sorted(res['themes'].items(), key=lambda kv: kv[1]['mentions'], reverse=True)
    for name, t in order:
        print('\n### %s  --  %d mentions (%.1f%%)  |  %d neg / %d pos'
              % (name, t['mentions'], t['share'], t['neg_count'], t['pos_count']))
        for r in t['neg_examples']:
            print('   [-%d*] %s' % (r['rating'], en(r['review'])[:240]))
        for r in t['pos_examples']:
            print('   [+%d*] %s' % (r['rating'], en(r['review'])[:240]))

    # persist an English-translated result for building the dashboard box content
    dump = {'code': code, 'seg': seg, 'total': res['total'], 'avg': res['avg'], 'dist': res['dist'], 'themes': {}}
    for name, t in res['themes'].items():
        dump['themes'][name] = {
            'mentions': t['mentions'], 'share': t['share'],
            'neg_count': t['neg_count'], 'pos_count': t['pos_count'],
            'neg_examples': [{'rating': r['rating'], 'en': en(r['review']), 'orig': r['review']} for r in t['neg_examples']],
            'pos_examples': [{'rating': r['rating'], 'en': en(r['review']), 'orig': r['review']} for r in t['pos_examples']],
        }
    outp = os.path.join(REV, code, seg, '_voc_quick.json')
    json.dump(dump, open(outp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('\nwrote %s' % outp)


if __name__ == '__main__':
    main()
