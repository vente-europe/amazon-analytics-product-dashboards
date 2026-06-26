"""
WASP-VOC — single-market, Reviews-VOC-only standalone dashboard.

Composes the canonical `u-reviews-voc` tab template (self-contained CSS) into a
single index.html. Reads its data from dashboard.json -> baseTabs.reviews
(the VOC_DATA bucket — AI-analyzed, see Console CLAUDE.md "Zero Hardcoded Values"
exception for Reviews VOC).

Run:  py _build_standalone.py    (from this folder)

Until real review data lands in baseTabs.reviews (totalReviews > 0) this writes a
placeholder index.html with build instructions, so the sidebar entry isn't blank.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, '..', '..', 'templates', 'tabs', 'u-reviews-voc', 'template.html')

with open(os.path.join(HERE, 'dashboard.json'), encoding='utf-8') as f:
    dash = json.load(f)

voc = dash['baseTabs']['reviews']
title = dash.get('title', 'Wasp VOC')
subtitle = dash.get('subtitle', '')
xray_link = dash.get('xrayLink', '#')

BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f1f5f9;color:#1e293b;font-size:13px}
.dashboard-header{background:#0f2942;color:#fff;padding:18px 28px;display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap}
.dashboard-header h1{margin:0;font-size:1.35rem;font-weight:600;color:#fff}
.dashboard-header span{font-size:.78rem;color:#cbd5e1;display:block;margin-top:4px}
.xray-btn{background:#16a34a;color:#fff;padding:10px 16px;border-radius:6px;font-size:.82rem;font-weight:600;text-decoration:none;white-space:nowrap;display:inline-flex;align-items:center;gap:8px;box-shadow:0 1px 3px rgba(0,0,0,.2);transition:background .15s}
.xray-btn:hover{background:#15803d}
.dashboard-body{max-width:1600px;margin:0 auto;padding:24px 32px}
h2{color:#1e293b}
"""

XRAY_BTN = ('<a class="xray-btn" href="' + xray_link + '" target="_blank" rel="noopener">'
            '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>'
            'Edit X-Ray data</a>') if xray_link and xray_link != '#' else ''

HEAD = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + title + '</title>'
        '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>'
        '<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>'
        '<style>' + BASE_CSS + '</style></head>')


def header_html(sub):
    return ('<div class="dashboard-header"><div style="flex:1;min-width:0">'
            '<h1>' + title + '</h1><span>' + sub + '</span></div>' + XRAY_BTN + '</div>')


if not voc.get('totalReviews'):
    # No review data yet — write a placeholder so the sidebar entry renders cleanly.
    body = (header_html(subtitle) +
            '<div class="dashboard-body">'
            '<div style="background:#fff;border-radius:8px;padding:28px 32px;box-shadow:0 1px 3px rgba(0,0,0,.07);border-left:4px solid #0f2942">'
            '<h2 style="margin-bottom:12px">Awaiting review data</h2>'
            '<p style="color:#475569;line-height:1.7;font-size:.9rem">This dashboard is scaffolded but has no Voice-of-Customer data yet. To populate it:</p>'
            '<ol style="color:#475569;line-height:1.9;font-size:.88rem;margin:12px 0 0 20px">'
            '<li>Drop scraped review files into <code>reviews/</code>.</li>'
            '<li>Run the VOC analysis to fill <code>dashboard.json &rarr; baseTabs.reviews</code> '
            '(the <code>VOC_DATA</code> shape — see the contract at the top of '
            '<code>templates/tabs/u-reviews-voc/template.html</code>).</li>'
            '<li>Set <code>countryName</code> / <code>countryCode</code> (single market) and the <code>xrayLink</code> in <code>dashboard.json</code>.</li>'
            '<li>Re-run <code>py _build_standalone.py</code> &rarr; this page becomes the full Reviews VOC dashboard.</li>'
            '</ol></div></div>')
    html = HEAD + '<body>' + body + '</body></html>'
    with open(os.path.join(HERE, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    print('Placeholder index.html written (no review data yet).')
else:
    with open(TEMPLATE, encoding='utf-8') as f:
        template = f.read()
    # subtitle in dashboard.json is already the canonical one-liner; if it's
    # empty fall back to deriving it from the VOC identity.
    sub = subtitle or (voc.get('countryName', '') +
                       (' (' + voc['countryCode'] + ')' if voc.get('countryCode') else '') +
                       ' · ' + str(voc['totalReviews']) + ' reviews')
    body = (header_html(sub) +
            '<div class="dashboard-body">'
            '<script>window._TAB_DATA = ' + json.dumps(voc, ensure_ascii=False) + ';</script>' +
            template +
            '</div>')
    html = HEAD + '<body>' + body + '</body></html>'
    with open(os.path.join(HERE, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    print('index.html built: {:,} bytes ({} reviews)'.format(
        os.path.getsize(os.path.join(HERE, 'index.html')), voc['totalReviews']))
