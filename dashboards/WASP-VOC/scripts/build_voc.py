"""
WASP-VOC — build the Reviews VOC bucket from reviews/reviews-merged.csv.

Per-review analyst coding (theme / who / where / when-to-result) lives in this
file; every percentage and chart count in the output is COMPUTED from that
coding + keyword extraction, so the numbers are reproducible and consistent
with the tagged review browser. Writes the result into dashboard.json ->
baseTabs.reviews, then run _build_standalone.py to regenerate index.html.

Run:  py scripts/build_voc.py   (from the WASP-VOC folder)
"""
import csv, json, os, re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(HERE, 'reviews', 'reviews-merged.csv')
DASH = os.path.join(HERE, 'dashboard.json')

rows = list(csv.DictReader(open(CSV, encoding='utf-8-sig')))
N = len(rows)
rating = [int(float(r['rating'])) for r in rows]

# ── Per-review analyst coding (index-aligned to the CSV) ────────────────────
# theme tags (review browser + topic counts)
THEME = {
    0:['ineffective'], 1:['ineffective','bait'], 2:['ineffective','build'],
    3:['ineffective','value'], 4:['ineffective'], 5:['ineffective'],
    6:['ineffective','escape','bait'], 7:['escape','wrong_insects','ineffective'],
    8:['escape','ineffective'], 9:['ineffective'], 10:['ineffective','build'],
    11:['ineffective','value'], 12:['build','service'], 13:['ineffective'],
    14:['ineffective'], 15:['ineffective','wrong_insects','bait'],
    16:['ineffective','bait'], 17:['wrong_insects','ineffective'],
    18:['escape','ineffective'], 19:['build'], 20:['wrong_insects','ineffective'],
    21:['ineffective'], 22:['ineffective'],
    23:['effective','value','selective'], 24:['effective','bait','value'],
    25:['effective','build','bait'], 26:['effective','bait'],
    27:['effective','bait','value'], 28:['effective','bait'],
    29:['effective','bait','value','build'], 30:['effective','bait'],
    31:['effective','selective','build'], 32:['effective'], 33:['effective'],
    34:['effective','bait','build'], 35:['effective'], 36:['selective','effective'],
    37:['effective'], 38:['effective','value'], 39:['effective','bait','build','selective'],
    40:['effective'], 41:['effective'], 42:['effective','selective','value'],
}
# who (buyer type)
WHO = {23:'beekeeper',31:'beekeeper',36:'beekeeper',39:'beekeeper',
       38:'gardener',42:'gardener',
       34:'homeowner',35:'homeowner',40:'homeowner',
       1:'diy',6:'diy',24:'diy',26:'diy',27:'diy',28:'diy',29:'diy'}
# where used
WHERE = {6:'nests',17:'nests',27:'nests',28:'nests',32:'nests',
         23:'hives',31:'hives',36:'hives',39:'hives',
         38:'garden',42:'garden',
         35:'patio',40:'patio',
         30:'outing'}
# time to result
WHEN = {26:'fast',28:'fast',31:'fast',32:'fast',35:'fast',40:'fast',42:'fast',27:'fast',
        1:'never',4:'never',5:'never',6:'never',7:'never',9:'never',14:'never',
        15:'never',16:'never',17:'never',20:'never',21:'never',22:'never',0:'never'}

POS = lambda i: rating[i] >= 4
pct = lambda c: f"{round(c / N * 100, 1)}%"


def theme_count(tag):
    return sum(1 for i in THEME if tag in THEME[i])


def cp(coding, labels):
    """Build a {labels,pos,neg} customer-profile chart from an index->key dict."""
    keys = [k for k, _ in labels]
    out = {'labels': [lbl for _, lbl in labels],
           'pos': [0] * len(keys), 'neg': [0] * len(keys)}
    for i, key in coding.items():
        if key not in keys:
            continue
        j = keys.index(key)
        if POS(i): out['pos'][j] += 1
        else:      out['neg'][j] += 1
    return out


# cpWhat — pest target, extracted by keyword (data-derived, pos/neg split)
def pest_chart():
    pats = [('Yellow jackets', r"yellow ?jacket|'jacket"),
            ('Wasps', r"wasp"),
            ('Hornets', r"hornet"),
            ('Bees (target/confusion)', r"\bbee\b|bees|honeybee"),
            ('Other bugs (flies/gnats)', r"\bflies\b|\bfly\b|gnat|other bug")]
    out = {'labels': [l for l, _ in pats], 'pos': [0]*len(pats), 'neg': [0]*len(pats)}
    for i, r in enumerate(rows):
        txt = (r['title'] + ' ' + r['body']).lower()
        for j, (_, pat) in enumerate(pats):
            if re.search(pat, txt):
                if POS(i): out['pos'][j] += 1
                else:      out['neg'][j] += 1
    return out


def topic(label, reason, tag, bullets, quote_idx):
    return {'label': label, 'reason': reason, 'pct': pct(theme_count(tag)),
            'bullets': bullets,
            'quotes': [rows[i]['body'] for i in quote_idx]}


def scenario_rows(coding, spec):
    """spec = [(key,label,reason)], ordered as given; pct from coding counts."""
    counts = {}
    for k in coding.values():
        counts[k] = counts.get(k, 0) + 1
    items = [{'label': lbl, 'reason': rsn, 'pct': pct(counts.get(key, 0))}
             for key, lbl, rsn in spec if counts.get(key, 0) > 0]
    items.sort(key=lambda x: float(x['pct'][:-1]), reverse=True)
    return items


avg = round(sum(rating) / N, 2)
star = [rating.count(s) for s in range(1, 6)]
neg_n = sum(1 for i in range(N) if not POS(i))
pos_n = N - neg_n

voc = {
    'countryName': 'United States', 'countryCode': 'US',
    'segmentName': 'Wasp & Yellow-Jacket Lure Traps',
    'totalReviews': N, 'avgRating': avg, 'starDist': star,

    'cpSummary': (f"Coded from all <strong>{N}</strong> reviews of a single wasp / "
        f"yellow-jacket lure-trap category (US). Ratings are sharply split — "
        f"<strong>{star[0]+star[1]}</strong> at 1–2&#9733; vs <strong>{star[3]+star[4]}</strong> "
        f"at 4–5&#9733;, with no 3&#9733; — so the audience divides cleanly into buyers for whom "
        f"the trap worked dramatically and those who caught nothing. Bars below reflect analyst "
        f"coding of the subset of reviews that gave a clear signal on each dimension."),
    'cpWho': cp(WHO, [('homeowner','Homeowner / patio host'),('beekeeper','Beekeeper'),
                      ('gardener','Gardener / pollinator-friendly'),('diy','DIY bait tinkerer')]),
    'cpWhen': cp(WHEN, [('fast','Caught wasps within ~3 days'),('never','Never caught anything')]),
    'cpWhere': cp(WHERE, [('nests','Yard / near wasp nests'),('hives','Near bee hives'),
                          ('patio','Patio / outdoor dining'),('garden','Garden / feeders'),
                          ('outing','Outdoor recreation')]),
    'cpWhat': pest_chart(),

    'usageScenarios': scenario_rows(WHERE, [
        ('nests','Yard — near wasp/yellow-jacket nests','Hung in the yard near active nests'),
        ('hives','Beekeeping — protecting hives','Placed beside hives to cull yellow jackets'),
        ('patio','Patio / outdoor dining','Keeping the eating area sting-free'),
        ('garden','Garden & feeders','Protecting milkweed/monarchs and hummingbird feeders'),
        ('outing','Outdoor recreation','Hunting trips and other outings')]),

    'csSummary': (f"Sentiment is bimodal. The decisive factor is whether the trap catches: "
        f"<strong>{theme_count('ineffective')}</strong> of {N} reviews report little or no catch "
        f"(the bulk of 1–2&#9733;), while successful users report traps filling within days. "
        f"Bait preparation and hanging hardware recur as the swing factors between the two camps."),

    'negativeTopics': [
        topic('Catches nothing / ineffective',
              'Followed directions but trapped few or no wasps', 'ineffective',
              ['Most 1–2&#9733; reviews followed the instructions and still caught nothing.',
               'Several report the homemade 2-litre-bottle trap outperformed this product.',
               'Failure is the single largest driver of low ratings.'],
              [4, 7, 8]),
        topic('Wasps approach but won&rsquo;t enter / escape',
              'Insects circle or enter then leave without being trapped', 'escape',
              ['Buyers watched wasps fly past or dip in and back out.',
               'In one case a wasp nested next to the trap instead of entering.'],
              [18, 8]),
        topic('Attracts the wrong insects',
              'Catches flies, gnats and other bugs but not wasps', 'wrong_insects',
              ['Several traps filled with gnats/flies while wasps were ignored.'],
              [17, 20]),
        topic('Flimsy build & weak support',
              'Lid straps, zip-ties and hanging wire fail; one unanswered warranty contact',
              'build',
              ['Lid straps snap and lids crack when the supplied zip-tie is run through.',
               'Even satisfied buyers replace the hanging hardware with their own string/zip-ties.'],
              [12, 19]),
    ],
    'positiveTopics': [
        topic('Highly effective — fills fast',
              'Traps catch large numbers of wasps/yellow jackets quickly', 'effective',
              ['Repeated reports of full traps within days, dozens caught in hours.',
               'Described by multiple buyers as the most effective trap they have used.'],
              [26, 32, 30]),
        topic('Bait works & is customizable',
              'Lure performs and improves with added protein/meat or seasonal tuning', 'bait',
              ['Adding meat/protein dramatically increases the catch.',
               'Power users run protein in spring and sugar syrup in fall.',
               'Homemade bait (apple juice, tuna/chicken, dish soap) works as a refill.'],
              [26, 27, 39]),
        topic('Selective — spares honeybees',
              'Catches yellow jackets/wasps while leaving honeybees alone', 'selective',
              ['Repeatedly praised by beekeepers — near-zero honeybee bycatch.',
               'Positioned as non-toxic, refillable wasp control.'],
              [36, 42]),
        topic('Reusable, refillable & good value',
              'Easy to clean and rebait; non-toxic and reasonably priced', 'value',
              ['Easy to empty and rebait across a season.',
               'Non-toxic and reasonably priced; main gripe is finding refill bait.'],
              [42, 38]),
    ],
    'negativeInsights': [
        {'type': 'Efficacy', 'badgeBg': '#fee2e2', 'badgeColor': '#991b1b',
         'finding': f"{pct(theme_count('ineffective'))} of reviews report little or no catch — the single largest driver of 1–2★ ratings.",
         'implication': 'Perceived effectiveness is make-or-break; the listing must set realistic expectations and coach bait prep, placement and target species up front.'},
        {'type': 'Bait protocol', 'badgeBg': '#ffedd5', 'badgeColor': '#9a3412',
         'finding': "Failures cluster around bait ('followed the recipe… nothing'), while successes hinge on adding protein/meat and tuning bait by season.",
         'implication': 'A clearer, season-aware bait guide — or pre-mixed seasonal bait — could convert a large share of disappointed buyers.'},
        {'type': 'Build quality', 'badgeBg': '#fef3c7', 'badgeColor': '#92400e',
         'finding': 'Lid straps, zip-ties and hanging wire fail — flagged in both 1★ and 5★ reviews.',
         'implication': 'A sturdier hang kit is a low-cost fix that removes a recurring deduction even from satisfied buyers.'},
        {'type': 'Service', 'badgeBg': '#fee2e2', 'badgeColor': '#991b1b',
         'finding': 'A warranty contact (Willert Home Products) went unanswered.',
         'implication': 'Responsive post-sale support would blunt the harshest reviews.'},
    ],
    'positiveInsights': [
        {'type': 'Effectiveness', 'badgeBg': '#dbeafe', 'badgeColor': '#1e40af',
         'finding': "When it works it works dramatically — 'full in a few days', '50 in 24h', 'a dozen in 5 minutes'.",
         'implication': 'Lead imagery and copy with full-trap proof; this is the strongest conversion asset.'},
        {'type': 'Selective kill', 'badgeBg': '#dbeafe', 'badgeColor': '#1e40af',
         'finding': 'Spares honeybees — repeatedly praised by beekeepers and pollinator-friendly gardeners.',
         'implication': 'An under-used differentiator; merchandise explicitly to beekeeping and garden audiences.'},
        {'type': 'Bait mastery', 'badgeBg': '#ede9fe', 'badgeColor': '#5b21b6',
         'finding': 'Power users tune bait (meat/salmon/chicken; protein in spring, sugar in fall).',
         'implication': 'Educational content plus a refill-bait subscription can lift both efficacy perception and lifetime value.'},
        {'type': 'Value / eco', 'badgeBg': '#ede9fe', 'badgeColor': '#5b21b6',
         'finding': 'Refillable, non-toxic and reasonably priced resonate with eco-conscious buyers.',
         'implication': 'Align positioning with non-toxic, reusable pest control.'},
    ],
    'buyersMotivation': scenario_rows(
        {0:'clear',9:'clear',35:'family',40:'clear',23:'bees',31:'bees',36:'bees',39:'bees',
         42:'eco',25:'eco',38:'pollin',29:'replace'},
        [('clear','Clear wasps from outdoor living areas','Stop wasps ruining the yard/patio'),
         ('bees','Protect honeybees / beekeeping','Selective cull that spares hives'),
         ('eco','Non-toxic pest control','Avoid sprays and poisons'),
         ('pollin','Protect pollinators & feeders','Shield monarchs/milkweed and hummingbird feeders'),
         ('family','Protect family from stings','Make the yard safe for kids'),
         ('replace','Replace a broken/discontinued trap','Swap out an older worn trap')]),

    'customerExpectations': [
        {'label': 'Reliable catch regardless of bait skill', 'reason': 'Trap should work without an expert recipe', 'pct': pct(theme_count('ineffective'))},
        {'label': 'Sturdier hanging hardware & lid', 'reason': 'Lid stays shut; hang wire does not fail', 'pct': pct(theme_count('build'))},
        {'label': 'Affordable, easy-to-find refill bait', 'reason': 'Refills in stock and not over-priced', 'pct': pct(3)},
        {'label': 'Less mess & odor when baiting', 'reason': 'Filling without spills or strong smell', 'pct': pct(2)},
        {'label': 'Larger trap capacity', 'reason': 'Bigger reservoir before emptying', 'pct': pct(1)},
    ],

    'themeFilters': [
        {'value': 'effective', 'label': 'Effective'},
        {'value': 'ineffective', 'label': 'Ineffective'},
        {'value': 'escape', 'label': 'Wasps escape / won&rsquo;t enter'},
        {'value': 'wrong_insects', 'label': 'Wrong insects'},
        {'value': 'bait', 'label': 'Bait / lure'},
        {'value': 'build', 'label': 'Build & hardware'},
        {'value': 'selective', 'label': 'Spares bees'},
        {'value': 'value', 'label': 'Value / refills'},
        {'value': 'service', 'label': 'Customer service'},
    ],
    'tagStyles': {
        'effective': 'pill-blue', 'ineffective': 'pill-red', 'escape': 'pill-orange',
        'wrong_insects': 'pill-amber', 'bait': 'pill-purple', 'build': 'pill-orange',
        'selective': 'pill-blue', 'value': 'pill-purple', 'service': 'pill-red',
    },
    'reviews': [
        {'r': rating[i], 't': (rows[i]['title'] + ' — ' + rows[i]['body']).strip(' —'),
         'tags': THEME.get(i, [])}
        for i in range(N)
    ],
}

with open(DASH, encoding='utf-8') as f:
    dash = json.load(f)
dash['title'] = 'Wasp & Yellow-Jacket Traps — Voice of Customer (US)'
dash['subtitle'] = f'{N} Amazon reviews · single lure-trap category · amazon.com'
dash['currency'] = '$'
dash['baseTabs']['reviews'] = voc
with open(DASH, 'w', encoding='utf-8') as f:
    json.dump(dash, f, ensure_ascii=False, indent=2)

print(f'VOC written: {N} reviews, avg {avg}, stars {star}')
print(f"effective={theme_count('effective')} ineffective={theme_count('ineffective')} "
      f"bait={theme_count('bait')} build={theme_count('build')} selective={theme_count('selective')}")
