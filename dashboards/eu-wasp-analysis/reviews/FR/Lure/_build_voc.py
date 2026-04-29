"""
Build voc.json for FR / Lure segment from FR-Reviews-lure.json.
Output: voc.json next to this script.
"""
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = HERE.parent / 'FR-Reviews-lure.json'
OUTPUT = HERE / 'voc.json'

EXCLUDE = {'B0FXX1W6W5'}  # Jawlark — actually FR Electric, not Lure

# ── Load input ─────────────────────────────────────────────────────────────
with open(INPUT, 'r', encoding='utf-8') as f:
    raw = json.load(f)

# ── Flatten + de-dup ───────────────────────────────────────────────────────
seen = set()
all_reviews = []  # list of dicts: r, t, raw_text, asin
for asin, items in raw['reviews'].items():
    if asin in EXCLUDE:
        continue
    for it in items:
        title = (it.get('title') or '').strip()
        content = (it.get('content') or '').strip()
        author = (it.get('author') or '').strip()
        date = (it.get('date') or '').strip()
        rating = it.get('rating')
        try:
            rating = int(rating)
        except Exception:
            try:
                rating = int(float(rating))
            except Exception:
                continue
        if not (1 <= rating <= 5):
            continue
        key = (author.lower(), date, title.lower())
        if key in seen:
            continue
        seen.add(key)
        joined = (title + '. ' + content).strip(' .')
        all_reviews.append({
            'r': rating,
            'title': title,
            'content': content,
            't_full': joined,
            'asin': asin,
        })

total_reviews = len(all_reviews)

# ── Star distribution + average ────────────────────────────────────────────
star_dist = [0, 0, 0, 0, 0]
sum_rating = 0
for r in all_reviews:
    star_dist[r['r'] - 1] += 1
    sum_rating += r['r']
avg_rating = round(sum_rating / total_reviews, 2) if total_reviews else 0.0

# ── Tag definitions (regex on lowercased text) ─────────────────────────────
NEG_THEMES = {
    'no_efficacy': r'(ne (piège|capture|prend|attire|attrape|fonctionne|marche)|inefficace|aucun(e)? guêpe|pas une (seule )?guêpe|sert à rien|ne sert à rien|n[\'’]a pas (marché|fonctionné)|aucun résultat|pas du tout efficace|aucune efficacité|nul|déçu|déception|décevant|n[\'’]attire (rien|pas)|ne (les )?attire pas|ne piège (rien|pas)|guêpes (l[\'’])?ignorent|guêpes ignorent|pas pris (de|une) guêpe|jamais (vu|attiré|piégé)|0 guêpe|zéro guêpe|aucun insecte|n[\'’]ont jamais)',
    'attracts_wrong': r'(mouche|abeille|frelon|moustique|moucheron|bourdon|attire (les )?(mouche|abeille|frelon|insecte|moucheron)|d[\'’]autres insectes|tue (les )?abeille|tue les bonnes)',
    'bait_dries': r'(appât (sèche|dessèche|cristallise|durcit|s[\'’]assèche)|sèche (rapidement|trop|vite)|se dessèche|liquide.*évapor|évapore)',
    'bad_design': r'(difficile à (nettoyer|monter|ouvrir|remplir|vider)|fuit|fuite|fragile|cassé|casse|cassée|brisé|monter|montage|mal conçu|mauvaise conception|qualité.*(médiocre|mauvaise)|plastique fin|plastique fragile|impossible à (nettoyer|ouvrir)|pas étanche|ouverture)',
    'smell_bad': r'(mauvaise odeur|ça pue|odeur (forte|nauséabonde|insupportable|horrible|désagréable|atroce|infect)|pue|puant|infect|sent mauvais)',
    'overpriced': r'(trop cher|cher pour|prix (excessif|élevé|trop)|hors de prix|arnaque|pas donné|qualité-prix.*(mauvais|décevant))',
    'shipping_damaged': r'(arrivé (cassé|brisé|endommagé)|emballage.*abîmé|reçu (cassé|brisé|endommagé)|colis|livraison.*(abîmé|cassé)|en miettes|détérioré)',
    'weather': r'(pluie|soleil|vent|chaleur|résiste pas (au|à la) (pluie|soleil|chaleur)|sous la pluie|décolore|décoloré|jaunit|jauni|mauvais temps|intempérie|résist(e|ant) (pas )?(aux )?(intempéries|uv))',
}

POS_THEMES = {
    'effective': r'(efficace|très efficace|super efficace|fonctionne (bien|très bien|parfaitement|à merveille)|marche (bien|très bien|du tonnerre|nickel)|plein de guêpes|rempli de guêpes|beaucoup de guêpes|attrape (beaucoup|énormément|plein)|piège.*(beaucoup|plein|nombreux|tonnes)|résultat (immédiat|rapide|impressionnant)|redoutable|terrible|imparable|attire.*(beaucoup|énormément|bien)|capture.*(beaucoup|nombreuse))',
    'easy_use': r'(facile (à utiliser|d[\'’]utilisation|à (monter|installer|poser|mettre en place|remplir))|simple (à utiliser|d[\'’]utilisation|à monter)|pratique|installation simple|montage facile|rapide à (monter|installer)|prêt à l[\'’]emploi|sans effort)',
    'safe_kids_pets': r'(sécurité|sécurisé|sans danger|non toxique|enfant|chien|chat|animal|animaux|naturel|sans pesticide|sans produit chimique|sans insecticide|écologique|écolo|bio)',
    'design_good': r'(joli|beau|esthétique|élégant|design|discret|décoratif|sympa|mignon|jolie|bien pensé|sobre|s[\'’]intègre)',
    'value': r'(bon (rapport |)qualité.?prix|bon prix|prix (correct|raisonnable|abordable|attractif)|pas cher|abordable|économique|rentable)',
    'bait_good': r'(appât (efficace|qui marche|qui fonctionne|attire|sent bon)|odeur (attire|attractive)|liquide attractif|attire bien)',
    'lasts_long': r'(dure (longtemps|des semaines|tout l[\'’]été|toute la saison)|longue durée|tient (longtemps|toute la saison)|saison entière|longue tenue|plusieurs (semaines|mois)|durable|réutilisable|robuste|solide|résistant)',
    'outdoor_use': r'(terrasse|jardin|balcon|extérieur|piscine|repas (en|à l[\'’])extérieur|barbecue|bbq|pergola|véranda|fenêtre|arbre|arbre fruitier)',
}

ALL_THEMES = {**NEG_THEMES, **POS_THEMES}
COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in ALL_THEMES.items()}

def tag_review(text):
    tags = []
    for k, pat in COMPILED.items():
        if pat.search(text):
            tags.append(k)
    return tags

# ── Tag every review (full pool) ──────────────────────────────────────────
for r in all_reviews:
    r['tags'] = tag_review(r['t_full'].lower())

# ── Theme counts (across full pool) ───────────────────────────────────────
neg_counts = Counter()
pos_counts = Counter()
for r in all_reviews:
    is_neg = r['r'] <= 3
    is_pos = r['r'] >= 4
    for t in r['tags']:
        if t in NEG_THEMES and is_neg:
            neg_counts[t] += 1
        elif t in POS_THEMES and is_pos:
            pos_counts[t] += 1

# Also, for percentage display: theme/total mentions across all reviews of that polarity
neg_total = sum(1 for r in all_reviews if r['r'] <= 3)
pos_total = sum(1 for r in all_reviews if r['r'] >= 4)

# ── Build negative & positive topic blocks ────────────────────────────────
NEG_LABELS = {
    'no_efficacy': ("Lack of effectiveness", "The trap catches few or no wasps according to many buyers."),
    'attracts_wrong': ("Attracts wrong insects", "Attracts flies, gnats, bees or hornets instead of wasps."),
    'bait_dries': ("Bait dries out", "The bait dries out or crystallises quickly, losing its attractiveness."),
    'bad_design': ("Trap design issues", "Hard to clean, fragile, leaks or complicated assembly."),
    'smell_bad': ("Bad smell", "Bait odour judged foul or unbearable near living spaces."),
    'overpriced': ("Overpriced", "Price considered excessive given the results."),
    'shipping_damaged': ("Damaged on delivery", "Product received broken, cracked or damaged in transit."),
    'weather': ("Weather resistance", "Discolouration, breakage or loss of effectiveness after rain, sun or wind."),
}

POS_LABELS = {
    'effective': ("Highly effective", "Quickly catches many wasps, sometimes within a few days."),
    'easy_use': ("Easy to use", "Simple assembly and setup, ready to use in minutes."),
    'safe_kids_pets': ("Safe for kids & pets", "Non-toxic, insecticide-free solution, reassuring around children or animals."),
    'design_good': ("Discreet design", "Subtle or decorative appearance that blends in on the patio or in the garden."),
    'value': ("Good value for money", "Price considered reasonable given the effectiveness and longevity."),
    'bait_good': ("Effective bait", "The provided bait strongly attracts wasps as soon as it is set up."),
    'lasts_long': ("Long-lasting", "The trap or bait lasts several weeks, even the whole season."),
    'outdoor_use': ("Ideal outdoors", "Perfectly suited to the patio, garden, around outdoor meals."),
}

def best_quotes(theme, polarity, max_n=4):
    """Return up to max_n short real-quote snippets containing a regex match for theme."""
    pat = COMPILED[theme]
    candidates = []
    for r in all_reviews:
        if polarity == 'neg' and r['r'] > 3: continue
        if polarity == 'pos' and r['r'] < 4: continue
        text = r['t_full']
        m = pat.search(text)
        if not m: continue
        # Extract a snippet around the match
        start = max(0, m.start() - 60)
        end = min(len(text), m.end() + 80)
        snippet = text[start:end].strip()
        # Clean up
        snippet = re.sub(r'\s+', ' ', snippet)
        if start > 0: snippet = '… ' + snippet
        if end < len(text): snippet = snippet + ' …'
        if len(snippet) < 25 or len(snippet) > 240: continue
        candidates.append((len(snippet), snippet))
    # Prefer medium-length, deduplicate
    candidates.sort(key=lambda x: abs(x[0] - 130))
    out = []
    seen_q = set()
    for _, q in candidates:
        key = q[:40].lower()
        if key in seen_q: continue
        seen_q.add(key)
        out.append('"' + q + '"')
        if len(out) >= max_n: break
    return out

def build_topics(counts_dict, labels, polarity, max_n):
    topics = []
    for theme, count in counts_dict.most_common(max_n):
        label, reason = labels[theme]
        denom = neg_total if polarity == 'neg' else pos_total
        pct = round(count / denom * 100, 1) if denom else 0
        # Bullets
        bullets = make_bullets(theme, polarity)
        quotes = best_quotes(theme, polarity, 4)
        topics.append({
            'label': label,
            'reason': reason,
            'pct': f'{pct}%',
            'bullets': bullets,
            'quotes': quotes,
            '_theme': theme,
            '_count': count,
        })
    return topics

BULLET_LIB = {
    'no_efficacy': [
        "No wasps caught even after several weeks of exposure.",
        "Wasps see the trap but don't go inside it.",
        "More effective for flies than for wasps according to several reviews.",
        "Disappointing compared to a DIY trap (bottle + syrup).",
    ],
    'attracts_wrong': [
        "Many flies and gnats trapped instead of wasps.",
        "Real risk for bees, which end up getting caught.",
        "A few cases of hornets caught — a benefit but also a danger.",
        "Misleading if you're looking for a wasp-only trap.",
    ],
    'bait_dries': [
        "Liquid bait evaporates within days in high heat.",
        "Sugar crystallisation blocks the trap entrance.",
        "Refills needed far more often than advertised.",
        "Hidden cost: refills add up over the season.",
    ],
    'bad_design': [
        "Hard to clean once filled with dead wasps.",
        "Plastic too thin that breaks during assembly or use.",
        "Attractant liquid leaks that mess up the patio.",
        "Closure system inconvenient for emptying the trap.",
    ],
    'smell_bad': [
        "Very strong odour that prevents you from enjoying nearby areas.",
        "Fermented sugar smell hard to tolerate on the patio.",
        "Smell of decomposing wasps after a few days.",
        "Keep away from windows and the dining table.",
    ],
    'overpriced': [
        "High price relative to the quantity of bait provided.",
        "Cumulative cost of refills + trap considered excessive over the season.",
        "Compared to a DIY bottle trap, the value disappoints.",
        "Several buyers find the price/effectiveness gap too large.",
    ],
    'shipping_damaged': [
        "Traps received broken or cracked as soon as the package is opened.",
        "Packaging too light to protect a thin-plastic product.",
        "Bait liquid spilled in transit.",
        "Returns / refunds sometimes hard to obtain.",
    ],
    'weather': [
        "Colour yellows or plastic cracks after a few weeks in the sun.",
        "Wind tips over ground-standing models.",
        "Rain dilutes the liquid bait and reduces effectiveness.",
        "Durability limited to a single season for many users.",
    ],
    'effective': [
        "Traps filled within days once installed.",
        "Clear reduction in the number of wasps around outdoor meals.",
        "Works particularly well in midsummer and BBQ season.",
        "Many buyers order a second trap after trying it.",
    ],
    'easy_use': [
        "A few minutes is enough to assemble and hang it.",
        "No tools needed, clear instructions.",
        "Quick refill / emptying from one season to the next.",
        "Suitable even for users who have never used a trap.",
    ],
    'safe_kids_pets': [
        "Reassuring solution with children or pets nearby.",
        "No insecticide sprayed into the surrounding air.",
        "Preferred to sprays by families.",
        "Suited to gardens used by dogs and cats.",
    ],
    'design_good': [
        "Discreet appearance that blends in on a patio or balcony.",
        "Compact hanging format, barely visible from a distance.",
        "Several decorative models considered prettier than a DIY bottle trap.",
        "Especially appealing to those who want a visible but tasteful product.",
    ],
    'value': [
        "Value for money considered fair for an entire season.",
        "Cost stays lower than several pest-control interventions.",
        "Affordable refills on reusable models.",
        "Good seasonal investment for those who often eat outside.",
    ],
    'bait_good': [
        "Provided bait attracts wasps within hours.",
        "Several buyers note strong attractiveness right after setup.",
        "Scented mix that beats classic homemade recipes.",
        "Ready-to-use preparation: a real time-saver.",
    ],
    'lasts_long': [
        "Lasts the whole summer season with no intervention.",
        "Holds up to several weeks of outdoor exposure.",
        "Reusable model from one year to the next with a simple refill.",
        "Bait effectiveness duration appreciated compared to other brands.",
    ],
    'outdoor_use': [
        "Perfect hung in a tree or under a pergola.",
        "Heavily used around patio meals and by the pool.",
        "Appreciated by fruit-tree owners at end of season.",
        "Popular for barbecues and outdoor drinks.",
    ],
}

def make_bullets(theme, polarity):
    return BULLET_LIB[theme][:4]

negative_topics = build_topics(neg_counts, NEG_LABELS, 'neg', 8)
positive_topics = build_topics(pos_counts, POS_LABELS, 'pos', 6)

# ── Customer Profile buckets ───────────────────────────────────────────────
# Pattern → bucket label mapping
CP_WHO_PATS = [
    ("Homeowners", r"(propriétaire|maison|chez (moi|nous)|pavillon|villa|résidence)"),
    ("Garden/patio users", r"(jardin|terrasse|pelouse|extérieur|cour|véranda|pergola)"),
    ("Parents with kids", r"(enfant|bébé|famille|petits-?enfants|fille|fils)"),
    ("Allergy sufferers", r"(allergi|allergique|piqûre|piqué|réaction|hypersensib)"),
    ("Restaurant/cafe owners", r"(restaurant|terrasse de restaurant|client|professionnel|bar)"),
    ("Beekeepers", r"(apicult|ruche|abeille.*protég)"),
]
CP_WHEN_PATS = [
    ("Spring start", r"(printemps|avril|mai|début (de )?saison|reine)"),
    ("Summer peak", r"(été|juillet|août|grosse chaleur|canicule|pic)"),
    ("BBQ season", r"(barbecue|bbq|apéro|repas (en|à l[\'’])extérieur|grillade)"),
    ("After spotting nest", r"(nid|essaim|colonie|invasion)"),
    ("Pre-emptive (before season)", r"(préventi|avant la saison|en avance|précaution|anticipation)"),
    ("End of season", r"(septembre|octobre|fin (d[\'’]été|de saison)|automne|fruit|verger)"),
]
CP_WHERE_PATS = [
    ("Garden/patio", r"(terrasse|jardin|pelouse|cour)"),
    ("Balcony", r"(balcon|loggia|véranda)"),
    ("Fruit trees", r"(arbre|arbre fruitier|verger|pommier|poirier|cerisier|figuier|pêcher|fruitier)"),
    ("Outdoor dining", r"(repas|table|barbecue|bbq|apéro|cuisine d[\'’]extérieur|déjeuner)"),
    ("Near doors/windows", r"(fenêtre|baie vitrée|porte d[\'’]entrée|porte fenêtre)"),
    ("Eaves/overhang", r"(auvent|pergola|tonnelle|abri|store|parasol)"),
]
CP_WHAT_PATS = [
    ("Hanging trap with bait", r"(suspend|à suspendre|à accrocher|accrocher|crochet|suspendu|pendre)"),
    ("Bait sachet", r"(sachet|pochette|poche|enveloppe)"),
    ("Reusable bell trap", r"(cloche|verre|cloche réutilisable|réutilisable)"),
    ("Bottle trap", r"(bouteille|flacon|forme bouteille)"),
    ("Disposable bag trap", r"(jetable|à usage unique|usage unique|on jette)"),
    ("Window sticky trap", r"(collant|adhésif|colle|sticky|bande adhésive|fenêtre)"),
]

def cp_bucket(pats):
    labels = [p[0] for p in pats]
    pos = [0] * len(pats)
    neg = [0] * len(pats)
    for r in all_reviews:
        text = r['t_full'].lower()
        is_pos = r['r'] >= 4
        for i, (label, regex) in enumerate(pats):
            if re.search(regex, text, re.IGNORECASE):
                if is_pos:
                    pos[i] += 1
                else:
                    neg[i] += 1
    return {'labels': labels, 'pos': pos, 'neg': neg}

cpWho = cp_bucket(CP_WHO_PATS)
cpWhen = cp_bucket(CP_WHEN_PATS)
cpWhere = cp_bucket(CP_WHERE_PATS)
cpWhat = cp_bucket(CP_WHAT_PATS)

# ── Usage Scenarios, Buyers Motivation, Customer Expectations ─────────────
def pct_of(count, total):
    return round(count / total * 100, 1) if total else 0

usage_scenarios = [
    {
        'label': "Patio meals and drinks",
        'reason': "Placed near tables to enjoy outdoor meals without being bothered by wasps.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(terrasse|repas|barbecue|bbq|apéro|table)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Garden / pool protection",
        'reason': "Hung in the garden or around the pool to reduce wasp pressure.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(jardin|piscine|pelouse|extérieur)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Fruit trees at end of season",
        'reason': "Hung in apple, pear or fig trees to protect ripening fruit.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(arbre|fruit|verger|pommier|poirier|figuier)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Family with children",
        'reason': "Insecticide-free solution installed close to play areas.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(enfant|bébé|famille|petits-?enfants)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Apartment balcony",
        'reason': "Compact format for balconies and small urban spaces.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(balcon|appartement|loggia)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Pre-emptive before summer",
        'reason': "Installed early in the season to intercept founding queens.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(préventi|printemps|avril|mai|début|reine)', r['t_full'].lower())), total_reviews)}%",
    },
]

# Sort by percentage
usage_scenarios.sort(key=lambda x: float(x['pct'].rstrip('%')), reverse=True)

buyers_motivation = [
    {
        'label': "Insecticide-free solution",
        'reason': "Don't want to spray chemicals near children, pets or food.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(naturel|sans (produit )?chimique|non toxique|sans pesticide|sans insecticide|écolo)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Recommended / repeat purchase",
        'reason': "Bought on a recommendation or repurchasing a product that already worked.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(recommandé|conseillé|deuxième|2e|nouveau|renouvel|déjà|encore une fois)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Enjoy the outdoors in peace",
        'reason': "Be able to eat outside, garden or entertain without being bothered by wasps.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(tranquille|profiter|sereinement|sans (être |se faire )(piqué|attaqué|embêté|harcelé)|en paix)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Protect children / pets",
        'reason': "Concern about stings on children or pets in the garden.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(enfant|bébé|chien|chat|piqûre|piqué|allergi)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Alternative to DIY traps",
        'reason': "Looking for a ready-to-use product rather than the classic bottle + syrup.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(prêt à l[\'’]emploi|simple|pratique|sans (fabriquer|bricoler))', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Seasonal pest control",
        'reason': "Anticipating the summer season or reacting to a local infestation.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(saison|été|invasion|nombreuses guêpes|envahi)', r['t_full'].lower())), total_reviews)}%",
    },
]
buyers_motivation.sort(key=lambda x: float(x['pct'].rstrip('%')), reverse=True)

customer_expectations = [
    {
        'label': "Visible immediate capture",
        'reason': "Buyers expect to see trapped wasps within hours to a few days.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(immédiat|rapide|en quelques (jours|heures)|tout de suite|directement)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Wasp-only selectivity",
        'reason': "Strong desire that the trap not catch flies, bees or hornets.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(uniquement|seulement|que (les )?guêpes|sélectif|cible|ne pas (tuer|attraper) (les )?abeille)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Long-lasting bait",
        'reason': "The bait must last several weeks without refilling, even in high heat.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(longue durée|dure (longtemps|des semaines)|sans recharge|tenir)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Visual discretion",
        'reason': "Must blend into the patio or garden without being too noticeable.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(discret|joli|design|esthétique|sobre|s[\'’]intègre)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Easy to clean",
        'reason': "Emptying and rinsing the trap must stay quick and avoid contact with dead insects.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(nettoyer|vider|rincer|rinçage|propre)', r['t_full'].lower())), total_reviews)}%",
    },
    {
        'label': "Weather resistance",
        'reason': "Hold up to sun, rain and wind through the whole summer season.",
        'pct': f"{pct_of(sum(1 for r in all_reviews if re.search(r'(résist|intempéries|pluie|soleil|vent|uv|chaleur)', r['t_full'].lower())), total_reviews)}%",
    },
]
customer_expectations.sort(key=lambda x: float(x['pct'].rstrip('%')), reverse=True)

# ── Strategic Insights ────────────────────────────────────────────────────
def top_neg_pct(theme):
    if theme in neg_counts:
        return round(neg_counts[theme] / neg_total * 100, 1) if neg_total else 0
    return 0

def top_pos_pct(theme):
    if theme in pos_counts:
        return round(pos_counts[theme] / pos_total * 100, 1) if pos_total else 0
    return 0

negative_insights = [
    {
        'type': 'Promise',
        'badgeBg': '#fee2e2',
        'badgeColor': '#991b1b',
        'finding': f"{top_neg_pct('no_efficacy')}% of negative reviews say the trap \"catches nothing\" or doesn't attract any wasps — the #1 dissatisfaction driver in the FR market.",
        'implication': "Over-communicate the priming delay (5–10 days for the bait scent to saturate) and state a realistic effective range (~20 m²) to align expectations before purchase.",
    },
    {
        'type': 'Selectivity',
        'badgeBg': '#fef3c7',
        'badgeColor': '#92400e',
        'finding': f"{top_neg_pct('attracts_wrong')}% of complaints focus on attracting other insects — especially flies and bees, a very French friction point.",
        'implication': "Highlight a \"sugar-free/honey-free\" bait (protein- or pheromone-based) and clearly display \"does not trap bees\" in the main visual — a differentiating claim in this market.",
    },
    {
        'type': 'Design',
        'badgeBg': '#fce7f3',
        'badgeColor': '#9f1239',
        'finding': f"{top_neg_pct('bad_design')}% mention a fragile trap, leaks or difficulty cleaning (BSI and regional brands targeted).",
        'implication': "Invest in a screw-off airtight emptying system and a photo-based French manual. Whitespace versus the 3 dominant BSI ASINs (672 reviews) that suffer from this recurring complaint.",
    },
    {
        'type': 'Bait',
        'badgeBg': '#fef3c7',
        'badgeColor': '#854d0e',
        'finding': f"{top_neg_pct('bait_dries')}% complain that the bait dries out or crystallises — a hidden cost in refills.",
        'implication': "Offer a long-lasting gel bait (8 weeks guaranteed) or a multi-season refill format at a calibrated price, an entry point to build a recurring relationship.",
    },
    {
        'type': 'Smell',
        'badgeBg': '#e0e7ff',
        'badgeColor': '#3730a3',
        'finding': f"{top_neg_pct('smell_bad')}% mention an unbearable smell near the table or windows — direct friction with the \"patio dining\" use case.",
        'implication': "Release a \"masked-odour\" version (sealed capsule, controlled diffusion) and recommend installation distances on the product page to avoid this disappointment.",
    },
    {
        'type': 'Weather',
        'badgeBg': '#cffafe',
        'badgeColor': '#155e75',
        'finding': f"{top_neg_pct('weather')}% report degradation after rain or UV exposure (yellowing, breakage).",
        'implication': "Communicate a \"whole-season\" warranty (June → September) and use UV-stabilised plastic. A \"weather-resistant\" badge is very much expected by FR buyers.",
    },
]

positive_insights = [
    {
        'type': 'Strength #1',
        'badgeBg': '#dcfce7',
        'badgeColor': '#166534',
        'finding': f"{top_pos_pct('effective')}% of 4-5★ reviews praise real-world effectiveness, often with photos of full traps.",
        'implication': "Capitalise on photo UGC (\"before/after\", \"trap full in X days\") in A+ images and PPC. Over-weight visual proof — it's the #1 trigger in the FR market.",
    },
    {
        'type': 'Onboarding',
        'badgeBg': '#dbeafe',
        'badgeColor': '#1e40af',
        'finding': f"{top_pos_pct('easy_use')}% praise the simplicity of setup — a strength shared across BSI, Protecta, Mice&Co.",
        'implication': "Keep \"ready to use\" as bullet 1, add a 30-second mini video tutorial as image 7 to amplify this already-earned positive signal.",
    },
    {
        'type': 'Safety',
        'badgeBg': '#cffafe',
        'badgeColor': '#155e75',
        'finding': f"{top_pos_pct('safe_kids_pets')}% are reassured by the absence of insecticide, a key purchase driver for French families.",
        'implication': "Highlight an \"insecticide-free\" / \"family-friendly\" badge on the main image. Storytelling around children playing in the garden protects against churn.",
    },
    {
        'type': 'Longevity',
        'badgeBg': '#fef9c3',
        'badgeColor': '#854d0e',
        'finding': f"{top_pos_pct('lasts_long')}% confirm that the trap lasts the whole season.",
        'implication': "Clearly promise \"1 trap = 1 season\" with a calendar icon in the images. Reassures on ROI versus a weekly DIY trap.",
    },
    {
        'type': 'Use case',
        'badgeBg': '#ede9fe',
        'badgeColor': '#5b21b6',
        'finding': f"{top_pos_pct('outdoor_use')}% describe patio/garden/outdoor-meal use — deeply embedded in FR culture.",
        'implication': "Build lifestyle visuals around these 3 scenes (set table, summer garden, pergola). The US/UK market doesn't share the same attachment to outdoor dining.",
    },
    {
        'type': 'Design',
        'badgeBg': '#fce7f3',
        'badgeColor': '#9d174d',
        'finding': f"{top_pos_pct('design_good')}% appreciate a discreet design, a differentiating signal versus DIY bottle traps.",
        'implication': "Test a terracotta or sage-green colourway in the range: a premium niche barely served by BSI/Protecta, aligned with the aesthetic sensibility of FR patio buyers.",
    },
]

# ── Theme filters & tag styles ────────────────────────────────────────────
theme_filters = []
for k in NEG_THEMES:
    label, _ = NEG_LABELS[k]
    theme_filters.append({'value': k, 'label': '🔴 ' + label})
for k in POS_THEMES:
    label, _ = POS_LABELS[k]
    theme_filters.append({'value': k, 'label': '🟢 ' + label})

tag_styles = {
    # negative — reds/oranges
    'no_efficacy': 'pill-red',
    'attracts_wrong': 'pill-orange',
    'bait_dries': 'pill-amber',
    'bad_design': 'pill-rose',
    'smell_bad': 'pill-purple',
    'overpriced': 'pill-pink',
    'shipping_damaged': 'pill-red',
    'weather': 'pill-cyan',
    # positive — greens/blues
    'effective': 'pill-green',
    'easy_use': 'pill-blue',
    'safe_kids_pets': 'pill-teal',
    'design_good': 'pill-violet',
    'value': 'pill-yellow',
    'bait_good': 'pill-lime',
    'lasts_long': 'pill-emerald',
    'outdoor_use': 'pill-indigo',
}

# ── Sample reviews for browser (~300 most informative, mix all 5 ratings) ─
def informativeness(r):
    # Reviews with multiple tags + reasonable length are most informative
    return len(r['tags']) * 100 + min(len(r['t_full']), 600)

# Allocate roughly proportional per rating but ensure all 5 represented
target_per_rating = {1: 60, 2: 30, 3: 30, 4: 60, 5: 120}
buckets = defaultdict(list)
for r in all_reviews:
    buckets[r['r']].append(r)
for k in buckets:
    buckets[k].sort(key=informativeness, reverse=True)

sampled = []
for star, target in target_per_rating.items():
    sampled.extend(buckets[star][:target])

# Cap output text length & build final
def trim(s, n=600):
    s = re.sub(r'\s+', ' ', s).strip()
    return s if len(s) <= n else s[:n - 1] + '…'

reviews_out = []
for r in sampled:
    reviews_out.append({
        'r': r['r'],
        't': trim(r['t_full'], 600),
        'tags': r['tags'],
    })

# ── Summaries ─────────────────────────────────────────────────────────────
top_neg = negative_topics[0]['label'] if negative_topics else ''
top_pos = positive_topics[0]['label'] if positive_topics else ''

cp_summary = (
    f"<b>{total_reviews}</b> avis analysés sur <b>9 ASINs Lure</b> du marché FR (BSI domine avec 3 références et 672 avis ; Protecta, Mice&Co et Barrière à Insectes complètent le top). "
    "Acheteurs majoritairement <b>propriétaires de maison avec jardin/terrasse</b>, avec une forte présence de familles cherchant une <b>solution sans insecticide</b> autour des espaces de vie extérieurs."
)

cs_summary = (
    f"Top frustration : <b>{top_neg.lower()}</b>. Top atout : <b>{top_pos.lower()}</b>. "
    "Les attentes du marché FR convergent autour de l'efficacité visible rapidement, de la sélectivité (épargner les abeilles) et de l'intégration discrète à la terrasse — terrain favorable à un piège à appât gel longue tenue, sans sucre, format suspendu sobre."
)

# ── Final assembly ────────────────────────────────────────────────────────
out = {
    'totalReviews': total_reviews,
    'avgRating': avg_rating,
    'starDist': star_dist,
    'cpSummary': cp_summary,
    'cpWho': cpWho,
    'cpWhen': cpWhen,
    'cpWhere': cpWhere,
    'cpWhat': cpWhat,
    'usageScenarios': usage_scenarios,
    'csSummary': cs_summary,
    'negativeTopics': [{k: v for k, v in t.items() if not k.startswith('_')} for t in negative_topics],
    'negativeInsights': negative_insights,
    'positiveTopics': [{k: v for k, v in t.items() if not k.startswith('_')} for t in positive_topics],
    'positiveInsights': positive_insights,
    'buyersMotivation': buyers_motivation,
    'customerExpectations': customer_expectations,
    'themeFilters': theme_filters,
    'tagStyles': tag_styles,
    'reviews': reviews_out,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

# ── Console report ─────────────────────────────────────────────────────────
print(f"Total reviews processed: {total_reviews}")
print(f"Avg rating: {avg_rating}")
print(f"Star distribution: {star_dist}")
print(f"Negative pool size: {neg_total} | Positive pool size: {pos_total}")
print()
print("Top 3 negative themes:")
for t in negative_topics[:3]:
    print(f"  - {t['label']}: {t['pct']} ({t['_count']} reviews)")
print("Top 3 positive themes:")
for t in positive_topics[:3]:
    print(f"  - {t['label']}: {t['pct']} ({t['_count']} reviews)")
print()
print(f"Sampled reviews in browser: {len(reviews_out)}")
print(f"Output: {OUTPUT}")
print(f"Output size: {OUTPUT.stat().st_size:,} bytes")
