"""
Writes data/seasonality-de.json - the German fruit-fly monthly seasonality index
consumed by _build_rynek.py and _build_structure.py.

IMPORTANT (fixed 2026-07-30): the curve is now EXTRACTED VERBATIM from the
fruit-fly-trap-DE dashboard's own published `seasIdx` array, so it matches that
dashboard 1:1. The DE dashboard computes the index from only the **4 ASINs with
full 12-month coverage** (Aeroxon, Novokill x2, PIC) - Super Ninja / ARDAP are
excluded because their limited CSV history distorts the curve.

An earlier version of this script recomputed the index by pooling ALL 49 ASINs'
daily sales, which produced a WRONG curve (Jan/Feb came out high instead of as
troughs). We no longer recompute - we mirror the DE dashboard's authoritative
array so the two dashboards always agree.

Published DE curve (avg month = 1.0): Jan .25 Feb .24 Mar .24 Apr .28 May .44
Jun .98 Jul 1.79 Aug 2.68 Sep 1.98 Oct 1.41 Nov 1.23 Dec .48
(peak Aug 2.68, trough Mar/Feb 0.24; July = 1.79 -> 12M multiplier = 12/1.79).
"""
import os, re, sys, json

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
DE_INDEX = os.path.abspath(os.path.join(
    BASE, '..', '..', '..', 'Dashboards', 'Fruit Fly Trap - DE', 'index.html'))

MONTH_NUM = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
             'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}

if not os.path.exists(DE_INDEX):
    raise SystemExit(f'DE dashboard index.html not found: {DE_INDEX}')

html = open(DE_INDEX, encoding='utf-8').read()

m_idx = re.search(r'seasIdx\s*=\s*\[([0-9.,\s]+)\]', html)
m_mon = re.search(r'seasMons\s*=\s*\[([^\]]+)\]', html)
if not m_idx or not m_mon:
    raise SystemExit('could not find seasIdx / seasMons arrays in the DE dashboard')

vals = [float(x) for x in m_idx.group(1).split(',') if x.strip()]
mons = [x.strip().strip("'\"") for x in m_mon.group(1).split(',') if x.strip()]
if len(vals) != 12 or len(mons) != 12:
    raise SystemExit(f'expected 12 values/months, got {len(vals)}/{len(mons)}')

index = {}
for mon, val in zip(mons, vals):
    index[MONTH_NUM[mon]] = round(val, 4)
index = {m: index[m] for m in range(1, 13)}

out = {
    'source': "fruit-fly-trap-DE dashboard published seasIdx array (Lure segment, "
              "4 ASINs with full 12M coverage: Aeroxon, Novokill x2, PIC; Super Ninja/ARDAP excluded)",
    'method': 'extracted verbatim from the DE dashboard index.html so both dashboards agree; avg month = 1.0',
    'note': 'seasonal 12M multiplier for a snapshot in month M = 12 / index[M]',
    'index': index,
}

out_path = os.path.join(BASE, 'data', 'seasonality-de.json')
json.dump(out, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
print(f'Wrote {out_path} (extracted from DE dashboard)')
for m in range(1, 13):
    print(f'  {names[m-1]}  index={index[m]:.2f}  -> x{12/index[m]:.2f}')
print(f'\nJuly (export month) multiplier = 12/{index[7]:.2f} = x{12/index[7]:.3f}')
