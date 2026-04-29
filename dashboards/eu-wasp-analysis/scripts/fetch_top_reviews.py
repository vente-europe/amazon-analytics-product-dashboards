"""
Wrapper that scrapes reviews for top-reviewed ASINs (per country/segment) using
the Review Scraper at projects/Review Scraper/, then copies outputs into
eu-wasp-analysis/reviews/{COUNTRY}/ with ASIN+country+segment in filenames.

Reads top_reviewed.csv at the project root (or accepts a custom list).

Usage:
    py scripts/fetch_top_reviews.py DE          # all DE entries from top_reviewed.csv
    py scripts/fetch_top_reviews.py DE Lure     # only DE Lure
    py scripts/fetch_top_reviews.py UK Sticky --max 200
"""
import os, sys, csv, subprocess, shutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BASE = Path(__file__).resolve().parents[1]              # eu-wasp-analysis/
WORKSPACE = BASE.parents[3]                             # Claude Code Workspace - Tom/
SCRAPER_DIR = WORKSPACE / 'projects' / 'Review Scraper'
SCRAPER_OUTPUT = SCRAPER_DIR / 'output'
REVIEWS_DEST = BASE / 'reviews'

MARKETPLACE_NAME = {
    'DE': 'Germany',
    'FR': 'France',
    'UK': 'United Kingdom',
}


def load_targets(country: str, segment: str | None):
    path = BASE / 'top_reviewed.csv'
    rows = []
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['country'] != country:
                continue
            if segment and r['segment'] != segment:
                continue
            rows.append(r)
    return rows


def run_scraper(country: str, segment: str, asins: list[str], max_reviews: int):
    """Run one batch through the scraper CLI. Returns the collection slug used."""
    collection = f'eu-wasp-{country.lower()}-{segment.lower()}'
    cmd = [
        sys.executable, 'main.py',
        '--asin', ','.join(asins),
        '--marketplace', MARKETPLACE_NAME[country],
        '--name', collection,
        '--max', str(max_reviews),
    ]
    # Note: the top_reviewed.py script and X-Ray loader handle the
    # `Wasp UK.csv` -> `Wasps UK.csv` rename internally; nothing to do here.
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    print(f'\n>>> {country} {segment}: scraping {len(asins)} ASIN(s) [max {max_reviews} reviews each]')
    print(f'    {" ".join(cmd)}')
    result = subprocess.run(cmd, cwd=SCRAPER_DIR, env=env)
    if result.returncode != 0:
        print(f'    Scraper exited with code {result.returncode}')
    return collection


def copy_outputs(country: str, segment: str, asins: list[str], collection: str):
    """Copy scraper output CSVs into eu-wasp-analysis/reviews/{COUNTRY}/."""
    src_root = SCRAPER_OUTPUT / collection
    dest_root = REVIEWS_DEST / country
    dest_root.mkdir(parents=True, exist_ok=True)

    copied = 0
    for asin in asins:
        src_csv = src_root / asin / 'all_reviews.csv'
        src_json = src_root / asin / 'all_reviews.json'
        if not src_csv.exists():
            print(f'    [skip] {asin}: no output CSV (scraper may have failed)')
            continue
        # Naming: {ASIN}_{COUNTRY}_{Segment}_all_reviews.{csv,json}
        prefix = f'{asin}_{country}_{segment}'
        shutil.copy2(src_csv, dest_root / f'{prefix}_all_reviews.csv')
        if src_json.exists():
            shutil.copy2(src_json, dest_root / f'{prefix}_all_reviews.json')
        # count rows
        with open(src_csv, encoding='utf-8') as f:
            n = sum(1 for _ in csv.reader(f)) - 1
        print(f'    [ok]   {asin} → {prefix}_all_reviews.csv  ({n} reviews)')
        copied += 1
    return copied


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]
    max_reviews = 500
    for flag in flags:
        if flag.startswith('--max='):
            max_reviews = int(flag.split('=', 1)[1])
        elif flag == '--max' and flags.index(flag) + 1 < len(flags):
            pass  # allow `--max 500` but skipped — use --max=500
    # support `--max 500` form
    if '--max' in sys.argv:
        i = sys.argv.index('--max')
        if i + 1 < len(sys.argv):
            max_reviews = int(sys.argv[i + 1])

    if not args:
        print('Usage: py scripts/fetch_top_reviews.py <COUNTRY> [SEGMENT] [--max N]')
        print('Examples:')
        print('  py scripts/fetch_top_reviews.py DE')
        print('  py scripts/fetch_top_reviews.py DE Lure')
        print('  py scripts/fetch_top_reviews.py UK Sticky --max 200')
        sys.exit(1)
    country = args[0].upper()
    segment = args[1].capitalize() if len(args) > 1 else None
    if country not in MARKETPLACE_NAME:
        print(f'Unknown country: {country}. Supported: {list(MARKETPLACE_NAME)}')
        sys.exit(1)

    targets = load_targets(country, segment)
    if not targets:
        print(f'No targets found for {country}' + (f' / {segment}' if segment else ''))
        sys.exit(1)

    # Group by segment so we run one scraper batch per segment
    by_seg: dict[str, list[str]] = {}
    for r in targets:
        by_seg.setdefault(r['segment'], []).append(r['asin'])

    print(f'Scraping {sum(len(v) for v in by_seg.values())} ASINs across {len(by_seg)} segment(s) for {country}')
    for seg, asins in by_seg.items():
        print(f'  {seg}: {asins}')

    total_copied = 0
    for seg, asins in by_seg.items():
        collection = run_scraper(country, seg, asins, max_reviews)
        total_copied += copy_outputs(country, seg, asins, collection)

    print(f'\n=== Done. Copied {total_copied} review CSVs to {REVIEWS_DEST / country} ===')


if __name__ == '__main__':
    main()
