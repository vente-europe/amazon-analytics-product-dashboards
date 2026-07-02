"""
Parse a RAW Amazon review text dump into the VOC review schema.

Why: the chat input caps ~50k chars, so long review pastes get truncated.
Instead, paste the WHOLE copied Amazon review block into a plain-text file and
run this — it parses every review, dedupes, optionally machine-translates the
title + body to English, and writes the {ASIN}.json the VOC pipeline reads.

Input : reviews/<CODE>/<SEG>/_raw/<ASIN>.txt     (raw copy-paste from Amazon)
Output: reviews/<CODE>/<SEG>/<ASIN>.json          (list of {title,date,rating,review})

Usage:
  python parse_raw_reviews.py FR Oil B001KYU1H2            # translate to English (default)
  python parse_raw_reviews.py FR Oil B001KYU1H2 --lang orig  # keep original language
  python parse_raw_reviews.py FR Oil B001KYU1H2 --in path\to\file.txt  # custom input path

Notes
- The parser keys off Amazon's fixed block shape:
    <reviewer name>
    <N> out of 5 stars <title>
    Reviewed in <country> on <date>
    [Scent Name:... Size Name:...][Verified Purchase][Customer image]
    <body, may be multi-line or empty>
    [One person / N people found this helpful]
    Helpful / Report / Translate review to English
- Reviewer name is discarded (schema has no name field).
- Dedupes on (rating, title, date, review) so overlapping pastes are safe.
- English cache lives in reviews/_tr_cache_en.json (separate from the PL cache).
"""
import re, json, sys, os, zipfile, glob

BASE = os.path.dirname(os.path.abspath(__file__))          # atopic-skin-detailed
REV  = os.path.join(BASE, 'reviews')
EN_CACHE = os.path.join(REV, '_tr_cache_en.json')

RATING_RE  = re.compile(r'^\s*([0-5])(?:[.,]0)?\s+out of 5 stars\s*(.*)$')
DATE_RE    = re.compile(r'^\s*(Reviewed in .+ on .+?)\s*$')
HELPFUL_RE = re.compile(r'^\s*(?:One person|\d[\d,\.]*\s+people)\s+found this helpful\s*$', re.I)
TERM = {'helpful', 'report', 'translate review to english',
        'translate all reviews to english', 'from france', 'from germany',
        'from italy', 'from spain'}


def is_meta(line):
    l = line.strip()
    if l.lower().startswith('scent name:'):
        return True
    if 'verified purchase' in l.lower():
        return True
    if l.lower() == 'customer image':
        return True
    return False


def read_docx(path):
    """Extract text from a .docx with the stdlib: each <w:p> paragraph -> one line."""
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml').decode('utf-8', 'replace')
    # paragraph break = </w:p>; line break inside run = <w:br/>; tabs = <w:tab/>
    xml = xml.replace('</w:p>', '\n').replace('<w:br/>', '\n').replace('<w:tab/>', ' ')
    text = re.sub(r'<[^>]+>', '', xml)          # strip all remaining tags
    # unescape the handful of XML entities Word emits
    for a, b in (('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                 ('&quot;', '"'), ('&apos;', "'"), ('&#39;', "'")):
        text = text.replace(a, b)
    return text


def read_input(path):
    if path.lower().endswith('.docx'):
        return read_docx(path)
    return open(path, encoding='utf-8').read()


def parse(text):
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    records, cur, mode, body = [], None, 'idle', []

    def flush():
        nonlocal cur, body
        if cur is not None:
            cur['review'] = re.sub(r'\s+\n', '\n', ' '.join(x.strip() for x in body)).strip()
            cur['review'] = re.sub(r'\s{2,}', ' ', cur['review']).strip()
            records.append(cur)
        cur, body = None, []

    for raw in lines:
        m = RATING_RE.match(raw)
        if m:                                    # start of a new review block
            flush()
            cur = {'title': m.group(2).strip(), 'date': '', 'rating': int(m.group(1)), 'review': ''}
            mode = 'want_date'
            continue
        if cur is None:
            continue
        if mode == 'want_date':
            d = DATE_RE.match(raw)
            if d:
                cur['date'] = d.group(1).strip()
                mode = 'body'
            continue
        # mode == 'body'
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.lower() in TERM or HELPFUL_RE.match(raw):
            flush()
            mode = 'idle'
            continue
        if is_meta(raw):
            continue
        body.append(raw)
    flush()
    return [r for r in records if r]


def dedupe(records):
    seen, out = set(), []
    for r in records:
        k = (r['rating'], r['title'], r['date'], r['review'])
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def translate_en(records):
    from deep_translator import GoogleTranslator
    cache = {}
    if os.path.exists(EN_CACHE):
        cache = json.load(open(EN_CACHE, encoding='utf-8'))
    todo = sorted({s for r in records for s in (r['title'], r['review'])
                   if s.strip() and s not in cache})
    tr = GoogleTranslator(source='auto', target='en')
    for i in range(0, len(todo), 20):                # batch in chunks of 20
        chunk = todo[i:i + 20]
        try:
            res = tr.translate_batch(chunk)
        except Exception:
            res = [safe_one(tr, s) for s in chunk]
        for s, t in zip(chunk, res):
            cache[s] = t or s
        print('  translated %d/%d' % (min(i + 20, len(todo)), len(todo)))
    json.dump(cache, open(EN_CACHE, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    for r in records:
        r['title'] = cache.get(r['title'], r['title'])
        r['review'] = cache.get(r['review'], r['review'])
    return records


def safe_one(tr, s):
    try:
        return tr.translate(s)
    except Exception:
        return s


def main():
    args = sys.argv[1:]
    lang = 'en'
    inpath = None
    pos = []
    i = 0
    while i < len(args):
        if args[i] == '--lang':
            lang = args[i + 1]; i += 2
        elif args[i] == '--in':
            inpath = args[i + 1]; i += 2
        else:
            pos.append(args[i]); i += 1
    if len(pos) < 2:
        print('usage: python parse_raw_reviews.py <CODE> <SEG> [ASIN] [--lang en|orig] [--in file]')
        print('  combined mode (no ASIN): reads every .docx/.txt/.xlsx in reviews/<CODE>/<SEG>/_raw/')
        sys.exit(1)
    code, seg = pos[0], pos[1]
    asin = pos[2] if len(pos) >= 3 else None
    raw_dir = os.path.join(REV, code, seg, '_raw')

    # Collect input file(s)
    if inpath:
        sources = [inpath]
    elif asin:                                   # single-ASIN mode
        sources = [c for c in (os.path.join(raw_dir, asin + e) for e in ('.docx', '.txt'))
                   if os.path.exists(c)]
    else:                                        # combined mode: every doc in _raw/
        sources = sorted(glob.glob(os.path.join(raw_dir, '*.docx')) +
                         glob.glob(os.path.join(raw_dir, '*.txt')))

    if not sources:
        loc = (asin + '.docx') if asin else '<anything>.docx / .txt'
        print('MISSING input. Save the raw Amazon review copy-paste into:')
        print('  %s' % os.path.join(raw_dir, loc))
        print('  (combined mode reads EVERY .docx/.txt in that _raw/ folder)')
        print('then re-run.')
        sys.exit(1)

    all_recs = []
    for src in sources:
        recs = parse(read_input(src))
        print('  read %-3d reviews  <- %s' % (len(recs), os.path.basename(src)))
        all_recs.extend(recs)
    recs = dedupe(all_recs)

    from collections import Counter
    label = asin if asin else ('%s/%s pooled' % (code, seg))
    print('[%s/%s %s] %d unique reviews (%d before dedupe)' %
          (code, seg, label, len(recs), len(all_recs)))
    print('  rating dist:', dict(sorted(Counter(r['rating'] for r in recs).items())))
    empty = sum(1 for r in recs if not r['review'].strip())
    if empty:
        print('  note: %d reviews have empty body (title-only)' % empty)

    if lang == 'en':
        print('  translating to English...')
        recs = translate_en(recs)

    outname = (asin + '.json') if asin else 'all-reviews.json'
    outpath = os.path.join(REV, code, seg, outname)
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    json.dump(recs, open(outpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('  wrote %s (%d reviews, lang=%s)' % (outpath, len(recs), lang))


if __name__ == '__main__':
    main()
