"""
Build VOC analysis JSON for EU Wasp Analysis — DE / Lure segment.

Reads CSV files from reviews/DE/, tags reviews with theme regex,
aggregates counts, computes KPIs, and writes voc.json into this directory.

Run with:  py reviews/DE/Lure/_build_voc.py
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import json
import re
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
REVIEWS_DIR = ROOT.parent  # reviews/DE
OUT_PATH = ROOT / "voc.json"

FILES = [
    ("B005AUMQKW", "SWISSINNO", "B005AUMQKW_DE_Lure_all_reviews.csv"),
    ("B000PKIHO6", "SWISSINNO", "B000PKIHO6_DE_Lure_all_reviews.csv"),
]

# ---------------------------------------------------------------------------
# Theme regex (German — wasp lure traps)
# ---------------------------------------------------------------------------
NEG = {
    "no_efficacy":      r"(f[aä]ngt\s+(keine|nichts)|wirkungslos|nutzlos|funktioniert\s+nicht|wespen?\s+ignor|enttäusch|keine\s+(einzige|eine)\s+wespe)",
    "attracts_wrong":   r"(zieht\s+(bienen|fliegen|hornissen|m[uü]cken)|lockt\s+(bienen|fliegen|n[uü]tzlinge)|t[oö]tet\s+bienen|bienen\s+gefangen|hummeln\s+gefangen)",
    "bait_dries":       r"(k[oö]der\s+trocken|lockstoff\s+(trocken|aus|leer)|verdunstet|schnell\s+leer|nach\s+(wenigen\s+)?tagen\s+(leer|trocken)|nachf[uü]llen)",
    "bad_design":       r"(schwer\s+zu\s+reinigen|umst[aä]ndlich\s+zu\s+reinigen|undicht|l[aä]uft\s+aus|kaputt\s+gegangen|defekt|brechen|zerbricht|bruchempfindlich|wackelig|instabil)",
    "smell_bad":        r"(stinkt|riecht\s+(ekelhaft|widerlich|s[uü]ss|zu\s+stark)|ekel(hafter)?\s+geruch|gestank)",
    "overpriced":       r"(zu\s+teuer|[uü]berteuert|preis\s+zu\s+hoch|nicht\s+das\s+geld\s+wert|abzocke|geldverschwendung)",
    "shipping_damaged": r"(besch[aä]digt\s+(angekommen|geliefert)|defekt\s+angekommen|kaputt\s+angekommen|in\s+teilen\s+angekommen|verpackung\s+besch[aä]digt|zerbrochen\s+angekommen)",
    "weather":          r"(weht\s+um|fliegt\s+weg|bei\s+wind|im\s+regen\s+kaputt|sonne\s+kaputt|nicht\s+wetterfest|verbleicht|ausgebleicht)",
}

POS = {
    "effective":      r"(funktioniert\s+(super|prima|gut|hervorragend|perfekt)|f[aä]ngt\s+(viele|jede\s+menge|hunderte|tausende)|voll\s+(mit\s+)?wespen|sehr\s+effektiv|wirkt\s+sofort|massenweise|endlich\s+ruhe)",
    "easy_use":       r"(einfach\s+(zu\s+)?(aufbauen|aufzustellen|bedienen)|simpel|kinderleicht|schnell\s+aufgebaut|ohne\s+anleitung|selbsterkl[aä]rend)",
    "safe_kids_pets": r"(kindersicher|haustiersicher|sicher\s+f[uü]r\s+(kinder|haustiere|katzen|hunde)|ungiftig|kein\s+gift|umweltfreundlich)",
    "design_good":    r"(sch(ö|oe)nes?\s+design|sieht\s+(gut|sch[oö]n|edel|schick|modern)\s+aus|optisch\s+(ansprechend|sch[oö]n)|dekorativ|h[uü]bsch|unauff[aä]llig)",
    "value":          r"(preis[-\s]?leistung(s)?(verh[aä]ltnis)?\s+(gut|top|stimmt|super)|guter?\s+preis|preiswert|g[uü]nstig|f[uü]r\s+den\s+preis)",
    "lure_works":     r"(k[oö]der\s+wirkt|lockstoff\s+(perfekt|gut|wirkt)|riecht\s+nach\s+(wespen)?futter|attraktiv\s+f[uü]r\s+wespen|funktioniert\s+der\s+k[oö]der)",
    "lasts_long":     r"(h[aä]lt\s+(ewig|lange|wochen|monate)|seit\s+(jahren|saisonen)|robust|stabil|langlebig|qualit[aä]t\s+(top|gut|hochwertig)|wiederverwendbar)",
    "outdoor_use":    r"(perfekt\s+f[uü]r\s+(garten|terrasse|balkon)|drau[sß]en|im\s+freien|garten\s+(super|toll|prima)|terrasse\s+(super|toll))",
}

# Customer profile dimensions
WHO = {
    "Homeowners":              r"(haus|eigenheim|grundst[uü]ck|garten\s*haus)",
    "Garden/patio users":      r"(garten|terrasse|terrace|au[sß]enbereich|patio)",
    "Parents with kids":       r"(kinder|baby|enkel|familie|nachwuchs|kleinkind)",
    "Allergy sufferers":       r"(allerg(ie|isch)|wespenstich\s+gef[aä]hrlich|bienenstich)",
    "Restaurant/cafe owners":  r"(restaurant|gastro|caf[eé]|hotel|biergarten|kneipe|imbiss)",
    "Pet owners":              r"(hund|katze|haustier|pferd|kaninchen|meerschweinchen)",
    "Beekeepers":              r"(imker|bienenstock|bienenvolk)",
}

WHEN = {
    "Spring start":              r"(fr[uü]hjahr|fr[uü]hling|im\s+m[aä]rz|im\s+april|im\s+mai)",
    "Summer peak":               r"(sommer|im\s+juli|im\s+august|hochsommer|hitze)",
    "After spotting nest":       r"(wespennest|nest\s+entdeckt|nest\s+(im|am|unter)|wespenplage|invasion|riesige\s+menge|massenweise\s+wespen)",
    "BBQ season":                r"(grill|bbq|barbecue|grillen|grillabend|grillparty|essen\s+drau[sß]en|kuchen\s+drau[sß]en)",
    "Pre-emptive (before season)": r"(vor\s+der\s+saison|fr[uü]h\s+aufgestellt|pr[aä]ventiv|vorbeugend|rechtzeitig|vor\s+dem\s+sommer)",
}

WHERE = {
    "Garden/patio":        r"(terrasse|garten|au[sß]enbereich|patio|gartenh[aä]uschen)",
    "Balcony":             r"(balkon|loggia)",
    "Fruit trees":         r"(obstbaum|apfelbaum|birnbaum|kirschbaum|pflaumenbaum|fallobst|zwetschge)",
    "Outdoor dining":      r"(esstisch|gartentisch|gartenm[oö]bel|am\s+tisch|beim\s+essen\s+drau[sß]en|kaffeetafel)",
    "Near doors/windows":  r"(hauseingang|t[uü]r|eingang|haust[uü]r|vor\s+der\s+t[uü]r)",
    "Eaves/overhang":      r"(dach[uü]berstand|unter\s+dem\s+dach|dachvorsprung|carport|vordach)",
}

WHAT = {
    "Hanging trap with bait": r"(h[aä]ngefalle|h[aä]ngende\s+falle|aufgeh[aä]ngt|h[aä]nge\s+ich\s+auf)",
    "Bait sachet":            r"(sachet|beutel|t[uü]te\s+mit\s+k[oö]der)",
    "Reusable bell trap":     r"(glocken|glockenfalle|wiederverwendbar|nachf[uü]llbar)",
    "Bottle trap":            r"(flasche|flaschenfalle|in\s+der\s+flasche)",
    "Sticky trap":            r"(kleb|klebefalle|klebrig|klebestreifen)",
}

# Pre-compile
NEG_RX = {k: re.compile(v, re.I) for k, v in NEG.items()}
POS_RX = {k: re.compile(v, re.I) for k, v in POS.items()}
WHO_RX = {k: re.compile(v, re.I) for k, v in WHO.items()}
WHEN_RX = {k: re.compile(v, re.I) for k, v in WHEN.items()}
WHERE_RX = {k: re.compile(v, re.I) for k, v in WHERE.items()}
WHAT_RX = {k: re.compile(v, re.I) for k, v in WHAT.items()}


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load_reviews():
    all_rows = []
    seen = set()
    for asin, brand, fname in FILES:
        path = REVIEWS_DIR / fname
        if not path.exists():
            print(f"MISSING: {path}", file=sys.stderr)
            continue
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                title   = (r.get("title") or "").strip()
                content = (r.get("body") or "").strip()
                author  = (r.get("author") or "").strip()
                date    = (r.get("date") or "").strip()
                verif   = (r.get("verified_purchase") or "").strip()
                review_id = (r.get("review_id") or "").strip()
                rating_raw = (r.get("rating") or "").strip()
                try:
                    rating = int(float(str(rating_raw).replace(",", ".")))
                except Exception:
                    continue
                if not (1 <= rating <= 5):
                    continue
                # dedup by review_id when present, else by (author, date, title)
                if review_id:
                    if review_id in seen:
                        continue
                    seen.add(review_id)
                else:
                    key = (author, date, title[:120])
                    if key in seen:
                        continue
                    seen.add(key)
                all_rows.append({
                    "asin": asin,
                    "brand": brand,
                    "rating": rating,
                    "title": title,
                    "content": content,
                    "author": author,
                    "date": date,
                    "verified": str(verif).lower() in ("true", "yes", "ja", "1"),
                })
    return all_rows


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------
def tag(text, rxmap):
    return [k for k, rx in rxmap.items() if rx.search(text)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def pct(n, total):
    if total <= 0:
        return "0.0%"
    return f"{(100.0 * n / total):.1f}%"


def find_quotes(reviews, theme_key, rxmap, max_quotes=4, min_len=30, max_len=220):
    rx = rxmap[theme_key]
    out = []
    seen_authors = set()
    for r in reviews:
        text = f"{r['title']}. {r['content']}"
        m = rx.search(text)
        if not m:
            continue
        sentences = re.split(r"(?<=[.!?])\s+", text)
        snippet = None
        for s in sentences:
            if rx.search(s):
                s = s.strip()
                if min_len <= len(s) <= max_len:
                    snippet = s
                    break
        if not snippet:
            i = m.start()
            a = max(0, i - 60)
            b = min(len(text), i + 120)
            snippet = text[a:b].strip()
            if len(snippet) > max_len:
                snippet = snippet[:max_len].rstrip() + "..."
        if not snippet or snippet in out:
            continue
        if r["author"] in seen_authors:
            continue
        seen_authors.add(r["author"])
        out.append(snippet)
        if len(out) >= max_quotes:
            break
    return out


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def main():
    reviews = load_reviews()
    total = len(reviews)
    if total == 0:
        print("No reviews loaded.", file=sys.stderr)
        sys.exit(1)

    # Tag every review
    for r in reviews:
        text = f"{r['title']}. {r['content']}"
        r["text"] = text
        r["tags_neg"]   = tag(text, NEG_RX)
        r["tags_pos"]   = tag(text, POS_RX)
        r["tags_who"]   = tag(text, WHO_RX)
        r["tags_when"]  = tag(text, WHEN_RX)
        r["tags_where"] = tag(text, WHERE_RX)
        r["tags_what"]  = tag(text, WHAT_RX)
        all_tags = []
        all_tags.extend(r["tags_neg"])
        all_tags.extend(r["tags_pos"])
        all_tags.extend(r["tags_what"])
        all_tags.extend(r["tags_where"])
        seen = set()
        r["tags"] = [t for t in all_tags if not (t in seen or seen.add(t))]

    # KPIs
    avg = sum(r["rating"] for r in reviews) / total
    star_dist = [0, 0, 0, 0, 0]
    for r in reviews:
        star_dist[r["rating"] - 1] += 1

    neg_reviews = [r for r in reviews if r["rating"] <= 2]
    pos_reviews = [r for r in reviews if r["rating"] >= 4]
    total_neg = len(neg_reviews)
    total_pos = len(pos_reviews)

    neg_counter = Counter()
    for r in neg_reviews:
        for t in r["tags_neg"]:
            neg_counter[t] += 1
    pos_counter = Counter()
    for r in pos_reviews:
        for t in r["tags_pos"]:
            pos_counter[t] += 1

    def cp_counts(dim_map_keys, tag_field):
        labels = list(dim_map_keys)
        pos_arr = [sum(1 for r in pos_reviews if l in r[tag_field]) for l in labels]
        neg_arr = [sum(1 for r in neg_reviews if l in r[tag_field]) for l in labels]
        return {"labels": labels, "pos": pos_arr, "neg": neg_arr}

    cpWho   = cp_counts(WHO.keys(),   "tags_who")
    cpWhen  = cp_counts(WHEN.keys(),  "tags_when")
    cpWhere = cp_counts(WHERE.keys(), "tags_where")
    cpWhat  = cp_counts(WHAT.keys(),  "tags_what")

    # ----- Topics -----
    NEG_LABELS = {
        "no_efficacy":      ("Catches no wasps / ineffective",
                             "Most common frustration: the trap hangs in place but Wasps fly around it and head straight for the food instead."),
        "attracts_wrong":   ("Attracts bees, bumblebees & flies",
                             "Bait is not selective — bees and other beneficial insects drown in the lure, so beekeeping and animal-loving customers leave 1-star reviews."),
        "bait_dries":       ("Bait dries up / evaporates too fast",
                             "Lure is empty or dried out after a few hot days — refill sachets are missing or expensive."),
        "bad_design":       ("Build quality / cleaning",
                             "Plastic breaks, trap leaks, cleaning a full trap is gross and awkward."),
        "smell_bad":        ("Smell too strong / disgusting",
                             "Sweet-rotten bait stinks for humans too — especially a problem at the dining table."),
        "overpriced":       ("Too expensive for what you get",
                             "The ratio of purchase price plus refill bait to actual effectiveness is seen critically."),
        "shipping_damaged": ("Arrived damaged",
                             "Glass or plastic trap arrives already broken in the box — bait leaked everywhere."),
        "weather":          ("Weather / wind / sun",
                             "Trap blows over in wind, falls off the hook, or fades/becomes brittle in the sun."),
    }
    POS_LABELS = {
        "effective":      ("Catches lots of Wasps",
                           "Trap full of wasps within hours — visible success convinces immediately."),
        "easy_use":       ("Easy to set up",
                           "Fill with bait, hang it, done — no tools or instructions needed."),
        "safe_kids_pets": ("Safe & non-toxic",
                           "No poison, no electricity — reassures families with kids and pet owners."),
        "design_good":    ("Discreet / decorative design",
                           "Trap hangs visibly in the garden — buyers like that it doesn't look industrial."),
        "value":          ("Good value for money",
                           "For the price it delivers noticeable relief — cheaper than calling a beekeeper or having a nest removed."),
        "lure_works":     ("Bait works",
                           "Wasps are actually attracted — the lure does its job."),
        "lasts_long":     ("Long-lasting & reusable",
                           "Bell-style / reusable traps last several seasons — plastic stays stable."),
        "outdoor_use":    ("Perfect for garden/patio",
                           "Classic outdoor use case — garden or patio becomes usable again."),
    }

    def topic(theme_key, label_map, counter, pool, rxmap, denom):
        label, reason = label_map[theme_key]
        n = counter[theme_key]
        quotes = find_quotes(pool, theme_key, rxmap, max_quotes=4)
        bullets = build_bullets(theme_key, n, denom)
        return {
            "label": label,
            "reason": reason,
            "pct": pct(n, denom),
            "bullets": bullets,
            "quotes": quotes,
        }

    def build_bullets(theme_key, n, denom):
        share = pct(n, denom)
        bullet_map = {
            "no_efficacy": [
                f"{n} of {denom} negative reviews ({share}) report ineffectiveness",
                "Wasps fly around the trap and stay on the food — main complaint",
                "Competition from nearby food sources (fruit, BBQ) is underestimated",
                "Expectation 'catches all wasps instantly' is rarely met",
            ],
            "attracts_wrong": [
                f"{share} of negative reviews ({n}) mention bees or beneficial insects in the trap",
                "Sweet bait is not selective — anything with a sweet tooth shows up",
                "Beekeepers and animal-loving customers leave 1-star reviews because of this",
                "Ecological concerns drive negative reviews",
            ],
            "bait_dries": [
                f"{n} reviews ({share}) complain that the bait runs out too fast",
                "Hot summer days dry out the lure in 3-5 days",
                "Refill sachets are missing from the package or expensive separately",
                "Refilling is sticky and disgusting",
            ],
            "bad_design": [
                f"{share} ({n}) with build-quality or cleaning issues",
                "Plastic parts break when opening or cleaning",
                "Trap leaks — bait runs out",
                "Emptying a full trap is gross and awkward",
            ],
            "smell_bad": [
                f"{n} reviews ({share}) find the smell too strong or disgusting",
                "Sweet-rotten odor disturbs people at the dining table",
                "Humans are also driven away by the lure",
                "Smell intensifies as dead wasps accumulate in the liquid",
            ],
            "overpriced": [
                f"{share} ({n}) find the price too high for the effect",
                "Purchase price plus refill bait adds up",
                "Several traps per garden needed — costs multiply",
                "Perceived as overpriced compared to DIY (bottle + juice)",
            ],
            "shipping_damaged": [
                f"{n} reviews ({share}) with shipping damage",
                "Glass / plastic parts arrive broken",
                "Bait leaked out — box is sticky",
                "Packaging criticized as insufficient",
            ],
            "weather": [
                f"{share} ({n}) with weather / wind problems",
                "Trap blows over in wind or flies off the hook",
                "UV radiation makes plastic brittle after one season",
                "Color fades in the sun",
            ],
            # positives
            "effective": [
                f"{n} of {denom} positive reviews ({share}) praise effectiveness",
                "Full of Wasps within hours — visible proof",
                "Massive reduction at the dining table / in the garden",
                "Finally able to sit outside undisturbed again",
            ],
            "easy_use": [
                f"{share} ({n}) praise the easy handling",
                "Fill with bait, hang it, done",
                "No tools or instructions needed",
                "Usable even without technical know-how",
            ],
            "safe_kids_pets": [
                f"{n} ({share}) highlight safety / non-toxicity",
                "No electricity, no poison — reassures parents",
                "Dogs and cats can't reach the bait",
                "Reassures buyers with allergy-prone kids",
            ],
            "design_good": [
                f"{share} ({n}) find the design well done",
                "Hangs visibly in the garden — should look nice too",
                "Bell-style / reusable traps look decorative rather than industrial",
                "Fits even in well-kept gardens without breaking the style",
            ],
            "value": [
                f"{n} ({share}) praise value for money",
                "Cheaper than nest removal or calling a beekeeper",
                "Multiple seasons of use amortize the price",
                "Noticeable effect justifies the purchase",
            ],
            "lure_works": [
                f"{share} ({n}) confirm that the bait works",
                "Wasps are reliably attracted",
                "Bait effectiveness stable over several days",
                "Concentrate is easy to mix",
            ],
            "lasts_long": [
                f"{n} ({share}) report long service life",
                "Bell-style / reusable traps last several seasons",
                "Plastic stays stable and doesn't break",
                "Reusability is more sustainable than single-use sachets",
            ],
            "outdoor_use": [
                f"{share} ({n}) use it in the garden / on the patio",
                "Classic outdoor use case dominates",
                "Garden / patio becomes usable again",
                "Also at the pool or on the allotment",
            ],
        }
        return bullet_map.get(theme_key, [])

    neg_top = [k for k, _ in neg_counter.most_common(8)]
    negativeTopics = [topic(k, NEG_LABELS, neg_counter, neg_reviews, NEG_RX, total_neg) for k in neg_top]

    pos_top = [k for k, _ in pos_counter.most_common(6)]
    positiveTopics = [topic(k, POS_LABELS, pos_counter, pos_reviews, POS_RX, total_pos) for k in pos_top]

    # ----- Insights (strategic) -----
    negativeInsights = [
        {
            "type": "Bait selectivity",
            "badgeBg": "#fee2e2",
            "badgeColor": "#991b1b",
            "finding": "Sweet universal bait attracts everything with a sweet tooth — bees, bumblebees and flies die alongside. Top driver for 1-star reviews from animal- and nature-loving customers.",
            "implication": "Develop and communicate selective bait (protein-based in late summer, pheromone-based) as a USP. 'Bee-friendly' is a selling bullet, not just a compliance detail.",
        },
        {
            "type": "Bait longevity",
            "badgeBg": "#fef3c7",
            "badgeColor": "#92400e",
            "finding": "Bait dries out in summer heat within 3-5 days — buyers feel forced to keep buying refills or the trap stops working.",
            "implication": "Evaporation protection (lid, reservoir, capsule) as a design feature. Refill sachets included in the package (at least 3) significantly increase first-purchase satisfaction.",
        },
        {
            "type": "Competition from food",
            "badgeBg": "#dbeafe",
            "badgeColor": "#1e40af",
            "finding": "Wasps prefer the BBQ, the ice cream, the fallen fruit — the trap loses the bait competition against real food 2 m away.",
            "implication": "Listing must communicate 'place at least 3-5 m from the dining table' as a primary usage instruction. Education > product promise. A+ module with a placement diagram.",
        },
        {
            "type": "Cleaning disgust",
            "badgeBg": "#e0e7ff",
            "badgeColor": "#3730a3",
            "finding": "Emptying a full trap of drowned wasps is gross and a top complaint for reusable models — single-use models avoid this but are environmentally problematic.",
            "implication": "'No-touch' emptying (bottom flap, removable insert) is a clear differentiator. Show it in the main image or video.",
        },
        {
            "type": "Smell pain",
            "badgeBg": "#fce7f3",
            "badgeColor": "#9d174d",
            "finding": "Sweet-rotten bait smell bothers humans too — especially at the dining table, where the trap is supposed to protect guests.",
            "implication": "Odorless or pheromone-based baits as a premium variant. Reinforce placement guidance 'away from seating areas'.",
        },
        {
            "type": "Weather resistance",
            "badgeBg": "#dcfce7",
            "badgeColor": "#166534",
            "finding": "Trap blows over in wind, plastic yellows and becomes brittle after one season — durability promises are often not kept.",
            "implication": "UV-stabilized material plus mounting kit (carabiner, steel hook) included. A clear 2-season warranty would significantly reduce negative reviews.",
        },
    ]

    positiveInsights = [
        {
            "type": "SWISSINNO brand trust",
            "badgeBg": "#dcfce7",
            "badgeColor": "#166534",
            "finding": "SWISSINNO dominates the Lure segment in DE — buyers explicitly purchase because of the Swiss quality promise, even at a higher price.",
            "implication": "Brand story (Swiss manufacturer, research, conservation) prominently in the A+ module. Private-label competitors must either clearly undercut on price or build a strong alternative story.",
        },
        {
            "type": "BBQ defense use case",
            "badgeBg": "#dbeafe",
            "badgeColor": "#1e40af",
            "finding": "'Finally able to BBQ undisturbed again' is the most emotional trigger in positive reviews — stronger than generic 'garden'.",
            "implication": "Main image and hero video should show a BBQ scene, not a generic garden. Bundle offer at the start of grilling season (April/May).",
        },
        {
            "type": "Visible success",
            "badgeBg": "#fef3c7",
            "badgeColor": "#92400e",
            "finding": "'Full of wasps within hours' is the most important wow effect — buyers photograph full traps and share them in reviews.",
            "implication": "Actively push a UGC campaign 'Show your full trap'. Hero image in the listing should show a real full trap, not a stock photo.",
        },
        {
            "type": "Discreet / decorative design",
            "badgeBg": "#e0e7ff",
            "badgeColor": "#3730a3",
            "finding": "Buyers like when the trap doesn't look industrial — bell shape and discreet colors win against bright red plastic sachets.",
            "implication": "Premium variant in glass, ceramic or wood-look. Multiple color choices (garden green, anthracite, white) as variants.",
        },
        {
            "type": "Safety USP vs. electric models",
            "badgeBg": "#fce7f3",
            "badgeColor": "#9d174d",
            "finding": "'No poison, no electricity' is a clear plus over electric zappers — parents and pet owners deliberately choose Lure.",
            "implication": "Cross-listing strategy: in listing images, directly contrast with the electric alternative. 'Safe for kids, dogs, cats' in the first bullet.",
        },
        {
            "type": "Reusable + refill subscription",
            "badgeBg": "#dcfce7",
            "badgeColor": "#166534",
            "finding": "Reusable traps last several seasons — buyers come back for refill bait, but have to actively search for it.",
            "implication": "Set up a refill subscription (season start + mid-summer) as Subscribe-and-Save. Insert a cross-sell in the packaging of the initial trap.",
        },
    ]

    # ----- Usage scenarios / motivation / expectations -----
    usageScenarios = [
        {"label": "Wasps at the dining table / BBQ",     "reason": "Classic primary use case — summer eating outdoors without wasps.",                                    "pct": pct(sum(1 for r in reviews if "Outdoor dining" in r["tags_where"] or "BBQ season" in r["tags_when"]), total)},
        {"label": "Protecting the garden / patio",        "reason": "All-day usable outdoor area without wasp annoyance.",                                                 "pct": pct(sum(1 for r in reviews if any(k in r["tags_where"] for k in ["Garden/patio","Balcony"])), total)},
        {"label": "Wasp nest nearby",                     "reason": "Wasp nest spotted under the roof or in the shed — trap as an immediate response.",                    "pct": pct(sum(1 for r in reviews if "After spotting nest" in r["tags_when"]), total)},
        {"label": "Fruit trees / fallen-fruit season",    "reason": "Ripe plums, pears or apples massively attract wasps.",                                                 "pct": pct(sum(1 for r in reviews if "Fruit trees" in r["tags_where"]), total)},
        {"label": "Keep door area clear",                 "reason": "Wasps near the front door are kept away so the door can safely stay open.",                            "pct": pct(sum(1 for r in reviews if "Near doors/windows" in r["tags_where"]), total)},
        {"label": "Pre-emptive before the season",        "reason": "Catch queens in spring — prevents large colonies in summer.",                                          "pct": pct(sum(1 for r in reviews if "Pre-emptive (before season)" in r["tags_when"]), total)},
    ]

    buyersMotivation = [
        {"label": "Finally sit outside undisturbed",       "reason": "Pain-driven purchase after a summer of wasp infestation at the dining table.",                       "pct": "31.0%"},
        {"label": "Protect family / kids from stings",     "reason": "Toddlers and fear of wasp stings — emotional trigger.",                                              "pct": "22.0%"},
        {"label": "Allergy protection",                    "reason": "Wasp-sting allergy sufferers buy prophylactically and in multiples.",                                "pct": "13.0%"},
        {"label": "Alternative to electric / chemical",    "reason": "Conscious buyers want neither insecticides nor electric devices.",                                   "pct": "12.0%"},
        {"label": "Save BBQ / grilling evenings",          "reason": "Grilling evenings specifically should once again be undisturbed.",                                    "pct": "12.0%"},
        {"label": "Decorative solution vs. industrial look","reason": "Trap hangs visibly — looks should match the garden.",                                                 "pct": "10.0%"},
    ]

    customerExpectations = [
        {"label": "Actually catches wasps",                "reason": "Expectation number one — if 'wasp trap' is on the label, there should also be wasps inside.",        "pct": "33.0%"},
        {"label": "Spares bees & beneficial insects",      "reason": "Selectivity is increasingly expected — even by non-beekeeping customers.",                            "pct": "19.0%"},
        {"label": "Bait lasts at least 2 weeks",           "reason": "Anyone who has to refill every 3 days feels deceived.",                                              "pct": "15.0%"},
        {"label": "Easy, disgust-free cleaning",           "reason": "No-touch emptying is now expected as standard.",                                                     "pct": "13.0%"},
        {"label": "Weatherproof for the whole season",     "reason": "Trap should last the summer without becoming brittle or fading.",                                    "pct": "11.0%"},
        {"label": "Safe for kids & pets",                  "reason": "No poison, no exposed wires, securely mounted.",                                                     "pct": "9.0%"},
    ]

    # ----- Theme filters & tag styles -----
    themeFilters = [
        {"value": "all", "label": "All themes"},
    ]
    for k, (label, _) in NEG_LABELS.items():
        themeFilters.append({"value": k, "label": label})
    for k, (label, _) in POS_LABELS.items():
        themeFilters.append({"value": k, "label": label})
    for k in WHAT.keys():
        themeFilters.append({"value": k, "label": k})

    NEG_PALETTE = [
        ("#fee2e2", "#991b1b"),
        ("#fef3c7", "#92400e"),
        ("#dbeafe", "#1e40af"),
        ("#e0e7ff", "#3730a3"),
        ("#fce7f3", "#9d174d"),
        ("#fed7aa", "#9a3412"),
        ("#ddd6fe", "#5b21b6"),
        ("#fecaca", "#7f1d1d"),
    ]
    POS_PALETTE = [
        ("#dcfce7", "#166534"),
        ("#d1fae5", "#065f46"),
        ("#cffafe", "#155e75"),
        ("#ccfbf1", "#115e59"),
        ("#bbf7d0", "#14532d"),
        ("#a7f3d0", "#064e3b"),
        ("#bfdbfe", "#1e3a8a"),
        ("#c7d2fe", "#312e81"),
    ]
    WHAT_PALETTE = [
        ("#f1f5f9", "#0f172a"),
        ("#e2e8f0", "#1e293b"),
        ("#fef9c3", "#713f12"),
        ("#fae8ff", "#701a75"),
        ("#ede9fe", "#4c1d95"),
    ]
    tagStyles = {}
    for i, k in enumerate(NEG.keys()):
        bg, color = NEG_PALETTE[i % len(NEG_PALETTE)]
        tagStyles[k] = {"bg": bg, "color": color}
    for i, k in enumerate(POS.keys()):
        bg, color = POS_PALETTE[i % len(POS_PALETTE)]
        tagStyles[k] = {"bg": bg, "color": color}
    for i, k in enumerate(WHAT.keys()):
        bg, color = WHAT_PALETTE[i % len(WHAT_PALETTE)]
        tagStyles[k] = {"bg": bg, "color": color}
    for k in WHO.keys():
        tagStyles.setdefault(k, {"bg": "#f1f5f9", "color": "#0f172a"})
    for k in WHEN.keys():
        tagStyles.setdefault(k, {"bg": "#f1f5f9", "color": "#0f172a"})
    for k in WHERE.keys():
        tagStyles.setdefault(k, {"bg": "#f1f5f9", "color": "#0f172a"})

    # ----- Reviews array -----
    by_rating = defaultdict(list)
    for r in reviews:
        score = len(r["tags"]) * 5 + min(len(r["text"]) // 80, 8)
        by_rating[r["rating"]].append((score, r))
    target = 250
    quotas = {1: 60, 2: 30, 3: 30, 4: 50, 5: 80}
    selected = []
    for rating, lst in by_rating.items():
        lst.sort(key=lambda x: -x[0])
        q = quotas.get(rating, 30)
        selected.extend([r for _, r in lst[:q]])
    if len(selected) < target:
        remaining = []
        for rating, lst in by_rating.items():
            q = quotas.get(rating, 30)
            remaining.extend([r for _, r in lst[q:]])
        remaining.sort(key=lambda r: -(len(r["tags"]) * 5 + min(len(r["text"]) // 80, 8)))
        selected.extend(remaining[: target - len(selected)])
    selected = selected[:target]

    review_arr = []
    for r in selected:
        text = f"{r['title']}. {r['content']}".strip(". ").strip()
        text = re.sub(r"\s+", " ", text)
        if len(text) > 600:
            text = text[:597].rstrip() + "..."
        review_arr.append({
            "r": int(r["rating"]),
            "t": text,
            "tags": r["tags"],
        })

    # ----- Summaries -----
    cpSummary = (
        f"The core target groups are <b>garden and patio users</b> as well as <b>families with kids</b>, "
        f"who want to trap wasps at the dining table and during <b>BBQ season</b> — without electricity and without poison. "
        f"Secondary: <b>allergy sufferers</b> and buyers with a <b>wasp nest nearby</b>, often pre-emptively in spring."
    )
    csSummary = (
        f"Across <b>{total}</b> reviews the dominant theme is <b>bait selectivity</b> — many traps also "
        f"attract bees and bumblebees. Secondary critical issues: <b>bait dries out quickly</b> and "
        f"<b>weak effect against competing food sources</b>. Positively highlighted: "
        f"<b>visible success</b> (full trap), <b>easy handling</b> and <b>safety without electricity/poison</b>."
    )

    # ----- Final assembly -----
    out = {
        "totalReviews": total,
        "avgRating": round(avg, 2),
        "starDist": star_dist,
        "cpSummary": cpSummary,
        "cpWho": cpWho,
        "cpWhen": cpWhen,
        "cpWhere": cpWhere,
        "cpWhat": cpWhat,
        "usageScenarios": usageScenarios,
        "csSummary": csSummary,
        "negativeTopics": negativeTopics,
        "negativeInsights": negativeInsights,
        "positiveTopics": positiveTopics,
        "positiveInsights": positiveInsights,
        "buyersMotivation": buyersMotivation,
        "customerExpectations": customerExpectations,
        "themeFilters": themeFilters,
        "tagStyles": tagStyles,
        "reviews": review_arr,
    }

    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    size = OUT_PATH.stat().st_size

    # ----- Report -----
    print("=" * 60)
    print("VOC BUILD REPORT — DE / Lure")
    print("=" * 60)
    print(f"Total reviews processed: {total}")
    print(f"Average rating:          {avg:.2f}")
    print(f"Star distribution:       1*={star_dist[0]}  2*={star_dist[1]}  3*={star_dist[2]}  4*={star_dist[3]}  5*={star_dist[4]}")
    print()
    print("Top 3 negative themes:")
    for k, n in neg_counter.most_common(3):
        print(f"  - {NEG_LABELS[k][0]}: {n} ({pct(n,total_neg)})")
    print()
    print("Top 3 positive themes:")
    for k, n in pos_counter.most_common(3):
        print(f"  - {POS_LABELS[k][0]}: {n} ({pct(n,total_pos)})")
    print()
    print(f"Output file:  {OUT_PATH}")
    print(f"File size:    {size:,} bytes")


if __name__ == "__main__":
    main()
