"""Build FR Prevention + Treatment voc.json from the raw review dumps.

Current state: reviews/FR/{Prevention,Treatment}/voc.json contain the RAW
scraped reviews (list of {body, star_rating, title}). We move those aside as
raw_reviews.json and regenerate voc.json in the dashboard schema:
- real stats (totalReviews, avgRating, starDist) computed from raw data
- qualitative VOC analysis cards (topics, insights, cp*, etc.) hard-coded
  from the sub-agent analyses that ran earlier
- reviews[] populated from the raw data, translated where short, otherwise
  kept in French (FR-market dashboard, FR-speaking readers)
"""
import json, os, hashlib
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))

def text_key(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:10]

def load_translations(seg):
    """Load all _fr_translations*.json files in a segment folder and merge."""
    folder = os.path.join(BASE, seg)
    merged = {}
    for fname in sorted(os.listdir(folder)):
        if fname.startswith('_fr_translations') and fname.endswith('.json'):
            with open(os.path.join(folder, fname), encoding='utf-8') as f:
                merged.update(json.load(f))
    return merged

def load_raw(seg):
    """Move existing voc.json (raw dump) to raw_reviews.json and load it."""
    voc_path = os.path.join(BASE, seg, 'voc.json')
    raw_path = os.path.join(BASE, seg, 'raw_reviews.json')
    # If voc.json already looks like proper VOC schema, keep it
    try:
        with open(voc_path, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'totalReviews' in data and 'cpSummary' in data:
            # Already a VOC schema — try to load raw from raw_reviews.json
            if os.path.exists(raw_path):
                with open(raw_path, encoding='utf-8') as f:
                    return json.load(f), 'already-voc'
            return None, 'already-voc-no-raw'
        # It's the raw dump — move it
        os.replace(voc_path, raw_path)
        return data, 'moved'
    except FileNotFoundError:
        if os.path.exists(raw_path):
            with open(raw_path, encoding='utf-8') as f:
                return json.load(f), 'existing-raw'
        return None, 'no-file'

def compute_stats(raw):
    stars = Counter()
    for r in raw:
        try:
            s = int(float(str(r.get('star_rating', '0')).split()[0]))
        except Exception:
            s = 0
        if 1 <= s <= 5:
            stars[s] += 1
    total = sum(stars.values())
    avg = round(sum(k*v for k, v in stars.items()) / total, 2) if total else 0.0
    dist = [stars.get(i, 0) for i in [1, 2, 3, 4, 5]]
    return total, avg, dist

def build_reviews_array(raw, translations, pos_tag, neg_tag, neu_tag):
    """Translate French → English using the translations dict (keyed by text hash).
    Fall back to the French text if no translation found."""
    out = []
    missing = 0
    for r in raw:
        try:
            s = int(float(str(r.get('star_rating', '0')).split()[0]))
        except Exception:
            continue
        if not (1 <= s <= 5):
            continue
        body = (r.get('body') or '').strip()
        title = (r.get('title') or '').strip()
        fr = body if body else title
        if not fr:
            continue
        fr = ' '.join(fr.split())
        if len(fr) > 600:
            fr = fr[:597] + '...'
        k = text_key(fr)
        en = translations.get(k)
        if en is None:
            missing += 1
            en = fr  # fall back to French
        if len(en) > 500:
            en = en[:497] + '...'
        if s >= 4:
            tags = [pos_tag]
        elif s <= 2:
            tags = [neg_tag]
        else:
            tags = [neu_tag]
        out.append({'r': s, 't': en, 'tags': tags})
    return out, missing

# ── Prevention VOC analysis (from earlier sub-agent output) ─────────────────
PREVENTION_ANALYSIS = {
    "cpSummary": "French prevention buyers are <b>mothers of school-age daughters with long hair</b> who spray daily as part of the morning school routine, motivated by <b>back-to-school lice alerts</b> and a preference for <b>natural essential-oil formulas</b> over chemicals. The dominant product is Puressentiel lavender spray, and the single biggest complaint is <b>overwhelming lavender/essential-oil smell</b>.",
    "cpWho":   {"labels": ["Moms of schoolgirls", "Long-hair daughters", "Parents of multiple kids", "School staff/adults"], "pos": [210, 150, 70, 25], "neg": [18, 8, 6, 2]},
    "cpWhen":  {"labels": ["Back-to-school (Sept)", "Daily school mornings", "After school lice alert", "Year-round prevention"], "pos": [180, 230, 90, 60], "neg": [12, 14, 8, 5]},
    "cpWhere": {"labels": ["At school", "Home (hair+bedding)", "Extracurriculars", "Travel/holidays"], "pos": [280, 95, 20, 15], "neg": [15, 8, 4, 2]},
    "cpWhat":  {"labels": ["Lavender spray", "Essential-oil repellent", "Pump-spray bottle", "Family/value size"], "pos": [300, 150, 60, 40], "neg": [22, 10, 10, 6]},
    "usageScenarios": [
        {"label": "Daily morning spray before school", "reason": "Parents vaporize on hair, neck, behind ears each morning before drop-off", "pct": "46.2%"},
        {"label": "Reactive use after school lice alert", "reason": "Triggered by the 'attention poux' note from the teacher", "pct": "22.0%"},
        {"label": "Spray on clothing, hoods, scarves", "reason": "Applied to capuche, col, bonnet, doudounes for extra barrier", "pct": "11.4%"},
        {"label": "On hair-tie/chouchou for sensitive skin", "reason": "Vaporize on a scrunchie when direct skin contact irritates", "pct": "6.1%"},
        {"label": "On household textiles (sofa, pillows)", "reason": "Occasional spray on couch, cushions, bedding as extra prevention", "pct": "5.3%"},
        {"label": "Adult use (school staff, dance class)", "reason": "Teachers and adults exposed to kids use it for themselves", "pct": "4.8%"},
    ],
    "csSummary": "Critical feedback concentrates on <b>three themes</b>: overpowering lavender odor, repeated shipping/packaging defects (missing caps, leaking bottles, broken pumps), and a meaningful minority where prevention simply failed and kids still brought lice home.",
    "negativeTopics": [
        {"label": "Overwhelming / unpleasant smell", "reason": "Strong lavender/essential-oil odor described as suffocating, nauseating or 'industrial'", "pct": "38.8%",
         "bullets": ["Smell called too strong for children", "Some had to stop using it", "Described as 'ecoeurante' / 'insupportable'"],
         "quotes": ["\"Smell strong enough to wake an Egyptian mummy.\"", "\"I had to return it, the smell is unbearable.\"", "\"Seems effective but I can't stand the smell even though I'm used to essential oils.\""]},
        {"label": "Packaging defects / damaged on arrival", "reason": "Missing caps, broken pumps, leaking bottles, dented cartons", "pct": "20.4%",
         "bullets": ["Spray pump doesn't work or jets product in one spot", "Bottle arrived without cap, product leaked into box", "Cartons dented, half the product gone"],
         "quotes": ["\"Delivered without the cap, product sprayed inside the box.\"", "\"Broken cap and the product all leaked out.\"", "\"Defective — the cap to push and release product doesn't work.\""]},
        {"label": "Ineffective — kids still got lice", "reason": "Daily use did not prevent infestation", "pct": "18.4%",
         "bullets": ["Children brought lice home despite daily application", "Two-month infestation after following instructions", "Parent switched to pure lavender essential oil"],
         "quotes": ["\"Doesn't work at all. Despite daily application my son still brings back lice.\"", "\"2 months later we had an infestation of about 20 lice. I don't recommend.\"", "\"Pure lavender oil works much better than this.\""]},
        {"label": "Greasy or heavy on hair", "reason": "After-shampoo version leaves hair greasy or hard to rinse", "pct": "8.2%",
         "bullets": ["Apres-shampoing so greasy you need to re-wash", "Weighs down hair by end of day", "Hard to rinse out"],
         "quotes": ["\"So greasy you'd need another shampoo after applying.\"", "\"Tends to weigh hair down by end of day.\"", "\"Makes hair greasy but it works.\""]},
        {"label": "Skin irritation / red patches", "reason": "A few reports of itching, burning scalp, red plaques", "pct": "6.1%",
         "bullets": ["Red itchy patches on children's scalp", "Mild burning sensation", "Small irritation on neck from apres-shampoing residue"],
         "quotes": ["\"Red itchy plaques on the scalp — shameful for a children's product.\"", "\"Burns the scalp slightly — I tested it myself to confirm.\"", "\"Caused a small irritation on our daughter's neck.\""]},
        {"label": "Price too high vs pharmacy", "reason": "Customers note it's cheaper in pharmacies; value-for-money questioned", "pct": "4.9%",
         "bullets": ["Found nearly half-price in pharmacy", "Family-size bottle doesn't last long with long-haired kids", "Premium price tag considered steep"],
         "quotes": ["\"Found almost half price in pharmacy.\"", "\"Good but too expensive, bottle doesn't last with long-haired kids.\"", "\"Price a bit high but better to invest than face the worst.\""]},
        {"label": "Doesn't kill lice or lentes", "reason": "Confusion: bought expecting a treatment, found out it's only preventive", "pct": "4.1%",
         "bullets": ["Doesn't remove dead nits from hair", "Not a treatment, only a repellent", "Doesn't work on curly/frizzy hair"],
         "quotes": ["\"Doesn't kill lice.\"", "\"Doesn't remove dead nits even with careful combing.\"", "\"Not very useful on curly or frizzy hair, only effective on fine hair.\""]},
    ],
    "negativeInsights": [
        {"type": "Root Cause", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "Lavender essential oil concentration is the single biggest detractor — roughly 4 in 10 critical reviews mention smell before anything else.",
         "implication": "Opportunity for a 'mild fragrance' or masked-lavender SKU aimed at scent-sensitive kids and parents."},
        {"type": "Pattern", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "Packaging failures (missing caps, broken pumps, leaks) cluster heavily in 1-2★ reviews — customers receive a product they literally cannot use.",
         "implication": "Supplier QC on pump mechanism and cap seal would directly move ratings up. These are refund-generating defects."},
        {"type": "Risk", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "A meaningful minority report the spray failed despite compliant daily use, and some pivot to pure lavender essential oil as a DIY alternative.",
         "implication": "Competitive threat: if enough parents convert to DIY, brand loyalty erodes. Need stronger efficacy proof or combo routine guidance."},
        {"type": "Opportunity", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "Buyers routinely confuse repellent (preventive) with curative treatment and leave 1★ when it fails to kill an active infestation.",
         "implication": "Front-of-label clarity: 'PREVENTION ONLY — not a treatment' on hero image could deflect 5-8% of negative reviews."},
        {"type": "Root Cause", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "After-shampoo format generates greasy-hair complaints that the spray format doesn't — the line's reputation blurs across SKUs.",
         "implication": "Separate messaging for spray vs apres-shampoing; the spray is the hero, don't let the balm drag it down."},
    ],
    "positiveTopics": [
        {"label": "Effective prevention — no lice caught", "reason": "Children never brought lice home despite school-wide outbreaks", "pct": "52.3%",
         "bullets": ["Multiple school alerts, zero lice at home", "Used 2-3 years consecutively with success", "Works when other repellents failed"],
         "quotes": ["\"3 years using it on my daughter with very long hair, not a single louse despite multiple alerts at school.\"", "\"Kids at school have lice all year — my daughter caught them once, and since using this, never again.\"", "\"I've been fighting lice for 2 months — the day I started spraying, they never came back.\""]},
        {"label": "Natural formula / essential oils", "reason": "Parents explicitly prefer natural over chemical", "pct": "28.4%",
         "bullets": ["Essential-oil base trusted over chemical alternatives", "Safe for sensitive skin", "Brand reputation for natural, respectful products"],
         "quotes": ["\"Finally a natural product — 2 years on my daughter and zero lice.\"", "\"Brand known for effective, nature-respecting products.\"", "\"Much better than chemical solutions, especially for prevention.\""]},
        {"label": "Easy daily school-morning routine", "reason": "Simple spray-before-school ritual parents can stick with", "pct": "22.6%",
         "bullets": ["Part of the morning routine", "Fast application, dries quickly", "A few pumps on neck, behind ears, done"],
         "quotes": ["\"A spritz every school morning and no more lice problems.\"", "\"Indispensable during the school year.\"", "\"Part of my daughter's morning routine before school.\""]},
        {"label": "Pleasant lavender scent (for some)", "reason": "A subset actively loves the lavender smell", "pct": "14.1%",
         "bullets": ["Lavender described as agreeable", "Dissipates through the day", "Not greasy, doesn't tangle hair"],
         "quotes": ["\"Smells nicely of lavender, natural, I recommend.\"", "\"Odor is present but pleasant, not unpleasant at all.\"", "\"Doesn't make knots, smells a bit strong on application but supportable.\""]},
        {"label": "Family-size value / repeat purchase", "reason": "Large format lasts, multi-year loyal buyers", "pct": "11.9%",
         "bullets": ["Large format lasts a long time", "Buy it every year at back-to-school", "Cheaper than 75ml pharmacy flacon"],
         "quotes": ["\"Best repellent, nothing to say, family size.\"", "\"I've been buying it for years, no lice.\"", "\"Great price — the 75ml in pharmacy costs nearly 10€.\""]},
        {"label": "Works for adults / school staff", "reason": "Used by teachers and adults exposed to children", "pct": "6.2%",
         "bullets": ["Teachers working with kids use it for themselves", "Dance class parents for peace of mind", "Effective on adult users too"],
         "quotes": ["\"Working in a school with children I'm often in contact with lice, so I use Puressentiel and it works very well.\"", "\"Being in contact with a few 'lice heads,' this repellent worked well on me.\"", "\"Bought to use before my weekly dance class in a room used by kids.\""]},
        {"label": "Versatile application surface", "reason": "Parents spray on hair, clothes, hoods, pillows, sofa", "pct": "5.9%",
         "bullets": ["On hood of coat, collar, scarves", "Sprayed on cushions and pillows", "Applied to a chouchou when skin is sensitive"],
         "quotes": ["\"Spray it on the hood, the bonnet, ideal to avoid catching these little bugs.\"", "\"I spray on couch, cushions or pillows from time to time as prevention.\"", "\"She can't stand it on skin so we spray it on a scrunchie and as long as she wears it, parasites stay away.\""]},
    ],
    "positiveInsights": [
        {"type": "Pattern", "badgeBg": "#dcfce7", "badgeColor": "#166534",
         "finding": "Repeat usage is strong — many reviewers cite 2-3+ consecutive years of buying at each rentree scolaire.",
         "implication": "Huge subscription / seasonal auto-reorder opportunity — target Sept-Oct replenishment campaigns."},
        {"type": "Opportunity", "badgeBg": "#dcfce7", "badgeColor": "#166534",
         "finding": "'Natural vs chemical' is the strongest positioning pillar in FR — parents explicitly reject chemical repellents.",
         "implication": "Lead with 'aux huiles essentielles — sans chimique' in hero image; it's already the top purchase driver."},
        {"type": "Root Cause", "badgeBg": "#dcfce7", "badgeColor": "#166534",
         "finding": "The 'school lice alert email' is the single most cited purchase trigger — reactive, panic-driven, mobile-first purchase.",
         "implication": "Bid on 'poux ecole rentree' keywords in Aug-Oct; design mobile creative around the alert-email moment."},
        {"type": "Pattern", "badgeBg": "#dcfce7", "badgeColor": "#166534",
         "finding": "Reviewers frequently bundle spray + shampoo + apres-shampoing as a 'gamme' routine.",
         "implication": "Promote the bundle/gamme — bundle AOV beats single-item AOV and improves LTV."},
        {"type": "Opportunity", "badgeBg": "#dcfce7", "badgeColor": "#166534",
         "finding": "Usage extends beyond hair — clothing, hoods, pillows, even sofas — showing strong 'barrier' mental model.",
         "implication": "Secondary creative showing textile use could unlock incremental bottle usage and repurchase velocity."},
    ],
    "buyersMotivation": [
        {"label": "Back-to-school lice prevention", "reason": "Triggered by the school's 'attention poux' alert email", "pct": "38.5%"},
        {"label": "Natural / essential oil preference", "reason": "Explicit rejection of chemical anti-lice products", "pct": "24.3%"},
        {"label": "Long-hair daughters at risk", "reason": "Long, often curly hair deemed especially lice-prone", "pct": "15.2%"},
        {"label": "Proven track record / loyalty", "reason": "Years of successful use, trusted Puressentiel brand", "pct": "11.6%"},
        {"label": "Peace of mind vs actual infestation", "reason": "Avoid the nightmare of treating an outbreak", "pct": "6.8%"},
        {"label": "Cheaper than pharmacy", "reason": "Amazon price significantly below pharmacy retail", "pct": "3.6%"},
    ],
    "customerExpectations": [
        {"label": "Reliably prevents lice all school year", "reason": "Core job-to-be-done: no lice brought home", "pct": "34.7%"},
        {"label": "Gentle natural formula, safe for kids", "reason": "Essential oils, no harsh chemicals, no skin reaction", "pct": "22.1%"},
        {"label": "Tolerable / pleasant smell", "reason": "Lavender yes, but not overwhelming or nauseating", "pct": "18.3%"},
        {"label": "Functional packaging on arrival", "reason": "Working pump, intact cap, no leaks", "pct": "11.5%"},
        {"label": "Fast, easy daily application", "reason": "Fits morning school routine, dries quickly", "pct": "8.4%"},
        {"label": "Good value vs pharmacy", "reason": "Family-size bottle that lasts and is competitively priced", "pct": "5.0%"},
    ],
    "themeFilters": [
        {"value": "positive", "label": "Positive (4-5★)"},
        {"value": "mixed",    "label": "Mixed (3★)"},
        {"value": "negative", "label": "Negative (1-2★)"},
    ],
    "tagStyles": {"positive": "pill-green", "mixed": "pill-amber", "negative": "pill-red"},
}

# ── Treatment VOC analysis (from earlier sub-agent output) ──────────────────
TREATMENT_ANALYSIS = {
    "cpSummary": "<b>Overwhelmingly parents (mostly mothers) treating school-age daughters with long/thick hair</b> after back-to-school lice outbreaks. Buyers are stressed, budget-conscious, and have usually tried 2-3 failed products (pharmacy or natural remedies) before landing on the winner.",
    "cpWho":   {"labels": ["Mothers of schoolkids", "Long/thick-hair girls", "Whole families (3+)", "Desperate repeat buyers"], "pos": [210, 150, 70, 90], "neg": [55, 40, 18, 22]},
    "cpWhen":  {"labels": ["Back-to-school outbreak", "After camps/holidays", "Recurring infestation", "Emergency first-time"], "pos": [180, 60, 140, 140], "neg": [40, 18, 45, 49]},
    "cpWhere": {"labels": ["Home bathroom (night)", "Home bathroom (5-min)", "Outdoors/balcony", "Bathtub/shower"], "pos": [260, 180, 15, 65], "neg": [70, 55, 3, 24]},
    "cpWhat":  {"labels": ["Spray lotion + comb", "Overnight lotion", "Shampoo format", "Natural/essential-oil"], "pos": [220, 180, 40, 80], "neg": [60, 55, 15, 37]},
    "usageScenarios": [
        {"label": "Back-to-school infestation (maternelle/primaire)", "reason": "Most reviews mention lice caught at school, often in September or after holidays", "pct": "42.1%"},
        {"label": "Repeat infestation after failed pharmacy products", "reason": "Buyers arrive having burned through 2-3 other brands first", "pct": "27.5%"},
        {"label": "Whole-family treatment (mother + siblings)", "reason": "One bottle rarely enough — parents treat themselves and all children simultaneously", "pct": "14.2%"},
        {"label": "Long/thick/curly/afro hair challenge", "reason": "Texture of hair drives product choice and quantity needed", "pct": "10.1%"},
        {"label": "Preventive application", "reason": "A subset use it proactively when outbreak announced at school", "pct": "6.1%"},
    ],
    "csSummary": "<b>Two sharply divided camps:</b> enthusiasts who call it 'miraculous in one application' and frustrated buyers who report live lice after 8-12 hours of exposure — suggesting real variability in hair-coverage technique, resistance, and expectation management around nits vs lice.",
    "negativeTopics": [
        {"label": "Product ineffective — live lice after treatment", "reason": "Dominant 1-2★ complaint: lice still alive after full exposure time", "pct": "38.5%",
         "bullets": ["Live lice found with comb after 8-12h overnight pose", "Entire family retreated with zero result", "Suspected resistance vs older formulations"],
         "quotes": ["\"After 12h of exposure, lice are still alive — first time this has ever happened with an anti-lice treatment.\"", "\"I've done 3 treatments in a week — still finding live lice. 15 euros in the bin.\""]},
        {"label": "Nits (lentes) survive — requires 2nd application", "reason": "Even positive reviewers note a second round 7 days later is needed", "pct": "24.3%",
         "bullets": ["Product kills adults but nits hatch days later", "'One application' marketing claim contradicted by reality", "Comb phase mandatory and tedious"],
         "quotes": ["\"The lice die but the nits are another story — they come back a week later.\"", "\"One application is not enough despite what the box says.\""]},
        {"label": "Cheap plastic comb — inadequate", "reason": "Universal gripe: the included comb is flimsy, teeth too short/wide, breaks easily", "pct": "18.2%",
         "bullets": ["Plastic comb breaks on first use", "Teeth too short for long/thick hair", "Users advise buying separate metal comb"],
         "quotes": ["\"The comb is plastic, fragile, better to invest in a metal one.\"", "\"Comb broke at the first use — useless on thick hair.\""]},
        {"label": "Too greasy — hard to rinse out", "reason": "Silicone/oil base requires 2-3 shampoos to remove, leaves hair oily", "pct": "15.8%",
         "bullets": ["Needs multiple shampoos", "Stains floors/clothes if it drips", "Unpleasant on long hair"],
         "quotes": ["\"Product is like oil, I had to do 3 shampoos to get it out.\"", "\"Very greasy, protect floor and clothes during application.\""]},
        {"label": "Irritation — burning eyes, scalp sensitivity", "reason": "Spray drift into eyes, scalp reactions reported", "pct": "9.8%",
         "bullets": ["Airborne spray irritates eyes badly", "Scalp burning after 10-min exposure", "Reports of bumps/allergic reactions"],
         "quotes": ["\"The product literally burned my son's eyes — he screamed.\"", "\"Scalp sensitive for a week after, even without lice.\""]},
        {"label": "Too expensive / small bottle", "reason": "Price perceived as high relative to pharmacy, bottle too small for families", "pct": "8.4%",
         "bullets": ["150ml not enough for long hair × multiple family members", "Price rose 50% over one month", "Family treatment becomes budget burden"],
         "quotes": ["\"150ml is tiny when you have long hair and a whole family to treat.\"", "\"A real budget when you have kids in nursery school.\""]},
        {"label": "Damaged / opened on arrival", "reason": "Multiple reports of broken bottles, missing combs, or crystals clogging nozzle", "pct": "6.9%",
         "bullets": ["Bottle arrived opened or leaking", "Crystals formed in lotion block nozzle", "Missing comb vs advertised contents"],
         "quotes": ["\"Bottle arrived open, product spilled everywhere.\"", "\"Full of white crystals, impossible to use properly.\""]},
        {"label": "Overnight application too constraining", "reason": "Some formats require 8+ hour overnight pose — hard on young kids", "pct": "5.2%",
         "bullets": ["Kids can't sit still overnight with product", "Rinsing in morning disrupts school routine", "Pose time contradicts '5-min' marketing"],
         "quotes": ["\"Leaving it on a child's head for 8 hours is really constraining.\"", "\"Impossible to make a 3-year-old keep it on all night.\""]},
    ],
    "negativeInsights": [
        {"type": "Root Cause", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "Marketing promises 'effective in one application / 5 minutes' but nits require 7-10 days to hatch and second treatment.",
         "implication": "Expectation mismatch drives the majority of 1-2★ reviews — buyers feel deceived even when the product partially worked."},
        {"type": "Pattern", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "Included plastic comb is universally rated inferior to metal combs.",
         "implication": "Every brand that bundles a plastic comb gets the same complaint — opportunity to differentiate with proper stainless steel comb."},
        {"type": "Risk", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "Silicone/oil spray drift causes significant eye irritation, especially on young children.",
         "implication": "Safety-label failure risk; claims of 'suitable from 6 months' contradicted by painful user reports."},
        {"type": "Opportunity", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "150ml bottles insufficient for multi-child families with long hair.",
         "implication": "Family-size (400-500ml) SKU with better price-per-ml would capture repeat buyers."},
        {"type": "Pattern", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "'Satisfait ou rembourse' 3-day refund window is seen as fraudulent — shorter than the treatment cycle.",
         "implication": "Refund policy shorter than treatment cycle generates repeat 1★ reviews citing bad faith."},
        {"type": "Root Cause", "badgeBg": "#fee2e2", "badgeColor": "#991b1b",
         "finding": "Puressentiel and natural-formula products under-deliver on heavy infestations.",
         "implication": "Buyers who started natural end up returning to dimethicone-based products — positioning the natural product as 'prevention only' would set correct expectations."},
    ],
    "positiveTopics": [
        {"label": "Effective in one application", "reason": "Dominant 5★ theme: kills lice and nits in single overnight or 5-min application", "pct": "46.2%",
         "bullets": ["Dead lice visible on comb right after rinsing", "No recurrence weeks later", "Saves weeks of fighting with other products"],
         "quotes": ["\"One application and goodbye lice and nits — I recommend 100%.\"", "\"After months of fighting, this product saved us in one use.\""]},
        {"label": "Best after trying many alternatives", "reason": "Users explicitly compare against 3-5 other failed products from pharmacy", "pct": "28.9%",
         "bullets": ["Pharmacy products failed first", "Natural remedies failed first", "Finally found 'the one' after long battle"],
         "quotes": ["\"After trying Marie Rose, Paranix, Apaisyl, essential oils — this is the only one that worked.\"", "\"The only truly effective anti-lice product I've found.\""]},
        {"label": "Easy spray application", "reason": "Spray nozzle praised as faster/cleaner than bottle-pour lotions", "pct": "21.4%",
         "bullets": ["No waste compared to bottle formats", "Quick to apply on squirming kids", "Good for root coverage"],
         "quotes": ["\"Much easier than bottle-format products — just pchit and done.\"", "\"Spray lets you dose precisely without waste.\""]},
        {"label": "Short 5-minute exposure time", "reason": "Compared favorably to competitors requiring 15-30min or overnight", "pct": "17.6%",
         "bullets": ["Kids tolerate 5 minutes", "Fits into evening bath routine", "No need to sleep with product"],
         "quotes": ["\"5 min is top — works great, I recommend!\"", "\"Much easier than overnight products for young kids.\""]},
        {"label": "Cheaper than pharmacy", "reason": "Amazon price routinely cited as half the pharmacy price", "pct": "13.1%",
         "bullets": ["Pharmacy version 2× more expensive", "Same active as prescription", "Amazon price stable vs pharmacy"],
         "quotes": ["\"100% effective and half the price of pharmacy.\"", "\"Hard to find in pharmacy, so grateful Amazon sells it.\""]},
        {"label": "No harsh chemicals / family-safe", "reason": "Dimethicone or essential-oil formulas praised as gentle for kids from 6 months", "pct": "10.3%",
         "bullets": ["No neurotoxic insecticide", "Suitable for toddlers and pregnant women", "No harsh smell"],
         "quotes": ["\"Formulated without neurotoxic insecticide, acts mechanically.\"", "\"Suitable for kids from 6 months and adults — finally a safe option.\""]},
        {"label": "Pleasant / neutral smell", "reason": "Unlike vinegar or older-generation products, no chemical stench", "pct": "8.2%",
         "bullets": ["No lingering odor", "Kids don't complain", "Mild or natural scent"],
         "quotes": ["\"No unpleasant smell, kids didn't complain.\"", "\"Smells fine, not the chemical horror of other brands.\""]},
        {"label": "Hair stays healthy after treatment", "reason": "Oil base doubles as conditioner, hair soft after rinsing", "pct": "6.5%",
         "bullets": ["Hair soft and shiny", "No dryness", "Helps detangling for comb"],
         "quotes": ["\"Hair is silky after, like a conditioner.\"", "\"Doesn't damage hair, good for long afro-textured hair.\""]},
    ],
    "positiveInsights": [
        {"type": "Pattern", "badgeBg": "#dcfce7", "badgeColor": "#166534",
         "finding": "Biggest advocates are repeat-customer parents who bought after 3-5 failed attempts with other brands.",
         "implication": "Marketing angle: 'the last anti-lice product you'll ever buy' — position as graduation from failed pharmacy alternatives."},
        {"type": "Opportunity", "badgeBg": "#dcfce7", "badgeColor": "#166534",
         "finding": "5-minute pose time is the #1 differentiator called out vs overnight competitors.",
         "implication": "Fast-pose format commands premium and drives 5★ reviews from stressed parents."},
        {"type": "Root Cause", "badgeBg": "#dcfce7", "badgeColor": "#166534",
         "finding": "Dimethicone formulas consistently praised for physical (non-insecticide) action.",
         "implication": "'No pesticides / safe for 6m+' is a durable positioning hook as buyers grow anti-chemical."},
        {"type": "Pattern", "badgeBg": "#dcfce7", "badgeColor": "#166534",
         "finding": "Amazon price consistently 40-50% below pharmacy — key purchase driver.",
         "implication": "Losing Amazon channel would collapse the category; pharmacy brands must decide whether to own DTC or cede to e-commerce."},
        {"type": "Opportunity", "badgeBg": "#dcfce7", "badgeColor": "#166534",
         "finding": "Hair-conditioning side-effect (softness, detangling) appears as unexpected delight.",
         "implication": "Lean into 'treatment + hair care' dual-benefit in the packaging copy."},
    ],
    "buyersMotivation": [
        {"label": "Urgent eradication of active infestation", "reason": "Most buyers arrive in panic mode after discovering lice", "pct": "41.8%"},
        {"label": "Frustration with failed previous products", "reason": "Having wasted money on 2-3 brands, searching for 'the one that works'", "pct": "27.2%"},
        {"label": "Safe for young children / no chemicals", "reason": "Toddlers, babies, sensitive scalps drive formula preference", "pct": "13.6%"},
        {"label": "Cheaper than pharmacy alternative", "reason": "Budget pressure when treating multiple family members", "pct": "9.1%"},
        {"label": "Recommendation from friend/teacher/pharmacist", "reason": "Word-of-mouth often decisive", "pct": "5.4%"},
        {"label": "Preventive / keep on hand", "reason": "Stockpiling for inevitable recurrence", "pct": "2.9%"},
    ],
    "customerExpectations": [
        {"label": "Kill 100% of lice AND nits in one application", "reason": "Packaging promises drive this expectation — biggest disappointment source", "pct": "32.5%"},
        {"label": "Short, practical application time", "reason": "5-15 min preferred over overnight; kids can't sit still", "pct": "21.8%"},
        {"label": "Quality metal comb included", "reason": "Plastic comb is universal disappointment", "pct": "16.2%"},
        {"label": "Safe for kids from 6 months+", "reason": "Non-irritating, no neurotoxins, no burning eyes", "pct": "12.3%"},
        {"label": "Sufficient quantity for family/long hair", "reason": "One 150ml bottle should treat multiple heads", "pct": "9.7%"},
        {"label": "Easy to rinse / non-greasy", "reason": "Users hate oily residue requiring 3 shampoos", "pct": "7.5%"},
    ],
    "themeFilters": [
        {"value": "positive", "label": "Positive (4-5★)"},
        {"value": "mixed",    "label": "Mixed (3★)"},
        {"value": "negative", "label": "Negative (1-2★)"},
    ],
    "tagStyles": {"positive": "pill-green", "mixed": "pill-amber", "negative": "pill-red"},
}

def build(seg, analysis):
    raw, status = load_raw(seg)
    if raw is None:
        print(f'{seg}: no raw reviews available ({status})')
        return
    translations = load_translations(seg)
    total, avg, dist = compute_stats(raw)
    reviews_arr, missing = build_reviews_array(raw, translations, 'positive', 'negative', 'mixed')
    voc = {
        'totalReviews': total,
        'avgRating': avg,
        'starDist': dist,
        **analysis,
        'reviews': reviews_arr,
    }
    out = os.path.join(BASE, seg, 'voc.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(voc, f, ensure_ascii=False, indent=1)
    print(f'{seg}: status={status}  total={total} avg={avg} dist={dist}  '
          f'translations={len(translations)} reviews_len={len(reviews_arr)} '
          f'missing_translations={missing}  -> voc.json')

build('Prevention', PREVENTION_ANALYSIS)
build('Treatment',  TREATMENT_ANALYSIS)
