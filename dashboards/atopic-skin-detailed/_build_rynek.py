# -*- coding: utf-8 -*-
"""Generate the Rynek (Tab 1) topline view for atopic-skin-detailed FROM THIS
dashboard's own (current) X-Ray — WITHOUT touching the atopic-skin-topline dashboard.

Tab 1 used to be a verbatim paste of the sibling atopic-skin-topline/index.html.
That topline is on an OLDER X-Ray (pre atopic-only-oil reclassification), so its
sales figures disagreed with the rest of this (detailed) dashboard. Per Tom
(2026-07-02): the detailed dashboard must reflect the reworked segmentation +
added oils that we downloaded here, and the topline must stay untouched.

Solution: reuse atopic-skin-topline/_build_topline.py verbatim as the single
source of truth for the topline LAYOUT, but redirect it at runtime:
  * BASE      -> this (detailed) folder, so load_market() reads data/x-ray/{CODE}/... here
  * out_path  -> _rynek_topline.html here (never the topline's own index.html)

2026-07-08 — UK added as a 5th market (Tom). UK X-Ray is in GBP with its own
segment names (Bath Emulsion / Bath Oil). We inject, via string replacement (so the
sibling topline that shares _build_topline.py is NEVER affected):
  * UK appended to MARKETS
  * UK £ -> € conversion at GBP_EUR (rev + price) inside load_market
  * UK segment remap Bath Emulsion -> Wash, Bath Oil -> Oil (so it folds into the
    topline's Cream/Wash/Oil taxonomy)
  * display-text fixes (market count, hierarchy sentence, "UK not included" note,
    dynamic top-products market pills)

_build_standalone.py runs this first, then inlines _rynek_topline.html into Tab 1.
"""
import os, sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, '..', 'atopic-skin-topline', '_build_topline.py')

GBP_EUR = 1.17  # UK £ -> € conversion rate (approx; adjust here if needed)

src = open(SRC, encoding='utf-8').read()

# Redirect data source (BASE) to the detailed folder and the output to a local file.
src = src.replace(
    "BASE = os.path.dirname(os.path.abspath(__file__))",
    "BASE = r'''" + BASE + "'''", 1)
src = src.replace(
    "out_path = os.path.join(BASE, 'index.html')",
    "out_path = os.path.join(BASE, '_rynek_topline.html')", 1)

# ── UK injection: every (old, new) below MUST match exactly once, or we abort. ──
REPLACEMENTS = [
    # 1) Append UK to MARKETS + define GBP_EUR (runs before the market loop).
    ("MULTIPLIER = 12",
     "MARKETS.append({'code': 'UK', 'name': 'United Kingdom', 'name_pl': 'Wielka Brytania', "
     "'flag': '\U0001F1EC\U0001F1E7', 'color': '#dc2626'})\n"
     "GBP_EUR = " + repr(GBP_EUR) + "\n"
     "MULTIPLIER = 12"),

    # 2) UK segment remap (Bath Emulsion -> Wash, Bath Oil -> Oil) before the filter.
    ("            seg = (row.get('Segment') or '').strip()",
     "            seg = (row.get('Segment') or '').strip()\n"
     "            if code == 'UK': seg = {'Bath Emulsion': 'Wash', 'Bath Oil': 'Oil'}.get(seg, seg)"),

    # 3) UK £ -> € conversion (revenue + price) right after price is parsed.
    ("            price    = numv(row.get(price_col)) if price_col else 0.0",
     "            price    = numv(row.get(price_col)) if price_col else 0.0\n"
     "            if code == 'UK':\n"
     "                rev30d *= GBP_EUR; price *= GBP_EUR"),

    # 4) KPI: market count + code list (dynamic).
    ('      <div class="kpi-v">4 Markets</div>',
     '      <div class="kpi-v">{len(MARKETS)} Markets</div>'),
    ('      <div class="kpi-l">DE &bull; FR &bull; IT &bull; ES</div>',
     '      <div class="kpi-l">{market_codes_bull}</div>'),

    # 5) Summary denominator + add 5th market to the hierarchy sentence.
    ("m2 = markets_ranked[1]; m3 = markets_ranked[2]; m4 = markets_ranked[3]",
     "m2 = markets_ranked[1]; m3 = markets_ranked[2]; m4 = markets_ranked[3]; "
     "m5 = markets_ranked[4] if len(markets_ranked) > 4 else None"),
    ("całego rynku europejskiego (DE+FR+IT+ES)",
     "całego rynku europejskiego (DE+FR+IT+ES+UK)"),
    ("i na końcu <strong>{m4[0]['name_pl']}</strong> (€{m4[1]['rev12m']/1e6:.1f} mln).",
     "następnie <strong>{m4[0]['name_pl']}</strong> (€{m4[1]['rev12m']/1e6:.1f} mln){hierarchy_tail}."),

    # 6) Keyword block intro: scope it to the Eurozone markets (UK keyword set not listed here).
    ("Dla każdego z czterech rynków wykonano 12 osobnych przeszukiwań",
     "Dla każdego z czterech rynków strefy euro wykonano 12 osobnych przeszukiwań"),

    # 7) Note: UK IS now included (converted £ -> €).
    ("Wielka Brytania nie jest częścią tej analizy.",
     "Wielka Brytania (atopic / eczema / dermatitis) jest wliczona jako piąty rynek — "
     "wartości funtowe przeliczono na euro po kursie ~£1 = €{:.2f} (segmentacja Cream / Wash / Oil "
     "jak w pozostałych rynkach).".format(GBP_EUR)),

    # 8) Top-products market pills -> generated from MARKETS (so UK gets a pill).
    ('''      <button class="tp-pill active" data-mkt="{MARKETS[0]['code']}">{MARKETS[0]['flag']} {MARKETS[0]['code']}</button>
      <button class="tp-pill" data-mkt="{MARKETS[1]['code']}">{MARKETS[1]['flag']} {MARKETS[1]['code']}</button>
      <button class="tp-pill" data-mkt="{MARKETS[2]['code']}">{MARKETS[2]['flag']} {MARKETS[2]['code']}</button>
      <button class="tp-pill" data-mkt="{MARKETS[3]['code']}">{MARKETS[3]['flag']} {MARKETS[3]['code']}</button>''',
     '      {tp_market_pills}'),

    # 9) Advanced-view market pills -> generated from MARKETS (keep the "All" button).
    ('''        <button class="tp-pill" data-adv-mkt="{MARKETS[0]['code']}">{MARKETS[0]['code']}</button>
        <button class="tp-pill" data-adv-mkt="{MARKETS[1]['code']}">{MARKETS[1]['code']}</button>
        <button class="tp-pill" data-adv-mkt="{MARKETS[2]['code']}">{MARKETS[2]['code']}</button>
        <button class="tp-pill" data-adv-mkt="{MARKETS[3]['code']}">{MARKETS[3]['code']}</button>''',
     '        {tp_adv_market_pills}'),

    # 10) Define the pill-generator + helper strings just before the big HTML f-string
    #     (precomputed here so no single-quote string literals live inside the
    #     '''-delimited f-string expressions — a Python 3.11 restriction).
    ("HTML = f'''<!DOCTYPE html>",
     "tp_market_pills = ''.join('<button class=\"tp-pill' + (' active' if i == 0 else '') + "
     "'\" data-mkt=\"' + m['code'] + '\">' + m['flag'] + ' ' + m['code'] + '</button>' "
     "for i, m in enumerate(MARKETS))\n"
     "tp_adv_market_pills = ''.join('<button class=\"tp-pill\" data-adv-mkt=\"' + m['code'] + "
     "'\">' + m['code'] + '</button>' for m in MARKETS)\n"
     "market_codes_bull = ' &bull; '.join(m['code'] for m in MARKETS)\n"
     "hierarchy_tail = (' i na końcu <strong>' + m5[0]['name_pl'] + '</strong> (€' + "
     "format(m5[1]['rev12m'] / 1e6, '.1f') + ' mln)') if m5 else ''\n"
     "HTML = f'''<!DOCTYPE html>"),
]

for old, new in REPLACEMENTS:
    n = src.count(old)
    if n != 1:
        raise SystemExit('UK-injection anchor matched {} times (expected 1):\n  {}'.format(n, old[:80]))
    src = src.replace(old, new, 1)

exec(compile(src, SRC, 'exec'), {'__name__': '__main__', '__file__': SRC})
