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

_build_standalone.py runs this first, then inlines _rynek_topline.html into Tab 1.
"""
import os, sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, '..', 'atopic-skin-topline', '_build_topline.py')

src = open(SRC, encoding='utf-8').read()

# Redirect data source (BASE) to the detailed folder and the output to a local file.
src = src.replace(
    "BASE = os.path.dirname(os.path.abspath(__file__))",
    "BASE = r'''" + BASE + "'''", 1)
src = src.replace(
    "out_path = os.path.join(BASE, 'index.html')",
    "out_path = os.path.join(BASE, '_rynek_topline.html')", 1)

exec(compile(src, SRC, 'exec'), {'__name__': '__main__', '__file__': SRC})
