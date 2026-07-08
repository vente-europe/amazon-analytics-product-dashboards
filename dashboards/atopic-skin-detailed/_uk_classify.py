#!/usr/bin/env python
"""Classify merged UK ASINs into Cream / Bath Emulsion / Bath Oil per Tom's rules.
Form word -> from full Amazon title (H10 Product Details, available for all rows).
Condition word -> from title + bullets (bullets only for the 66 fetched via API).

Rules (case-insensitive, whole-word):
  OIL       : title has BOTH 'bath' AND 'oil'      AND condition in {atopic,eczema,dermatitis,sensitive}
  EMULSION  : title has any of {emulsion,lotion,bath,wash} AND condition in {eczema,dermatitis,sensitive,atopic}
  CREAM     : title has any of {cream,balm,gel,ointment,salve} AND condition in {atopic,eczema,dermatitis}
  else empty. Precedence: OIL > EMULSION > CREAM (bath-oil is most specific).
"""
import csv, json, io, sys, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

raw = json.load(open('_uk_merged_raw.json', encoding='utf-8'))
hdr = raw['hdr']
rows = raw['rows']
listings = json.load(open('_uk_listings.json', encoding='utf-8'))

def has(word, text):
    return re.search(r'\b' + re.escape(word) + r'\b', text) is not None

def any_word(words, text):
    return any(has(w, text) for w in words)

# condition: 'atop' is the stem of atopic/atopy (also catches range names AtopiControl/ATOPIS/
# Atoprel/Atopiclair which are unambiguously atopic-skin ranges); rest matched as whole words.
def cond(text, with_sensitive):
    if 'atop' in text: return True
    words = ['eczema', 'dermatitis', 'neurodermatitis'] + (['sensitive'] if with_sensitive else [])
    return any_word(words, text)
FORM_CREAM = ['cream', 'balm', 'baume', 'gel', 'ointment', 'salve', 'cerat', 'cerate']

def classify(title, bullets):
    t = title.lower()
    tb = (title + ' ' + bullets).lower()
    # ---- OIL: genuine bath-oil FORM (not an oil ingredient) ----
    # phrase "bath oil" / "bath & body oil"  OR  bath+oil present and NOT an emulsion/wash/soak form
    bath_oil_phrase = re.search(r'bath\s*(?:&|and|,|\s)*\s*(?:body\s+)?oil', t) is not None \
        or 'ölbad' in t or 'olbad' in t
    bath_oil_loose = has('bath', t) and has('oil', t) and not any_word(['emulsion', 'lotion', 'wash', 'soak'], t)
    if (bath_oil_phrase or bath_oil_loose) and cond(tb, True):
        return 'Oil'
    # ---- EMULSION: wash and emulsion are definitive cleanser/bath-emollient forms ----
    if has('wash', t) and cond(tb, True):
        return 'Emulsion'
    if has('emulsion', t) and cond(tb, True):
        return 'Emulsion'
    # ---- CREAM: leave-on cream/balm/gel/ointment beats a trailing "lotion/bath" descriptor ----
    if any_word(FORM_CREAM, t) and cond(tb, False):
        return 'Cream'
    # ---- EMULSION fallback: lotion / bath emollient ----
    if any_word(['emulsion', 'lotion', 'bath'], t) and cond(tb, True):
        return 'Emulsion'
    return ''

ai = hdr.index('ASIN')
out_hdr = hdr[:ai + 1] + ['Segment'] + hdr[ai + 1:]   # insert Segment immediately after ASIN

REV_FLOOR = 1000.0   # drop ASINs with monthly ASIN Revenue below £1,000
def num(x):
    return float(str(x).replace(',', '').replace('N/A', '0').strip() or 0)

dropped = 0
out_rows = []
counts = {'Cream': 0, 'Emulsion': 0, 'Oil': 0, '': 0}
detail = []
for r in rows:
    if num(r.get('ASIN Revenue', 0)) < REV_FLOOR:
        dropped += 1
        continue
    a = r['ASIN'].strip()
    title = r.get('Product Details', '') or ''
    lst = listings.get(a, {})
    bullets = ' '.join([lst.get('bullets', ''), lst.get('product_information', '')])
    seg = classify(title, bullets)
    counts[seg] += 1
    label = {'Cream': 'Cream', 'Emulsion': 'Bath Emulsion', 'Oil': 'Bath Oil', '': ''}[seg]
    nr = dict(r); nr['Segment'] = label
    out_rows.append(nr)
    detail.append((seg, a, bool(lst.get('title')), title[:70]))

with open('data/x-ray/UK/Dermo-Products-UK.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=out_hdr)
    w.writeheader()
    for r in out_rows:
        w.writerow({k: r.get(k, '') for k in out_hdr})

print(f'DROPPED (ASIN Revenue < £{int(REV_FLOOR)}):', dropped)
print('KEPT ROWS:', len(out_rows))
print('COUNTS:', {k: v for k, v in counts.items()})
print('bullets available (API ok):', sum(1 for d in detail if d[2]), '/', len(detail))
print()
for seg in ('Oil', 'Emulsion', 'Cream'):
    print(f'==== {seg} ({counts[seg]}) ====')
    for s, a, hb, t in sorted(detail):
        if s == seg:
            print(f'  {a} | {"B" if hb else "-"} | {t}')
    print()
