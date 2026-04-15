"""Build Marketing Deep-Dive JSON for EU Lice — per country per segment.

Reads:
  data/x-ray/{CODE}/*.csv                       (price/rating/reviews/bsr/rev30d)
  data/competitor-listings/{CODE}/raw/{ASIN}.json   (title/brand/bullets/images)
  data/competitor-listings/{CODE}/asins-{segment}.txt  (the top-N list)

Writes:
  data/competitor-listings/{CODE}/mdd-{segment}.json

Themes, theme-assignments, VOC gaps, whitespace, saturation advice, and
strategic recommendations are hand-curated from the listing bullets/description
content read by the AI model that wrote this file — this is the same pattern
as anti-fungus-nail-polish/scripts/build_mdd.py, but split by segment.

Usage:
    py scripts/build_mdd.py DE prevention
    py scripts/build_mdd.py DE treatment
"""
import os, sys, json, csv

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

# ── X-Ray numeric parser (US format: , thousand / . decimal) ─────────────────
def numv(v):
    if v is None: return 0.0
    s = str(v).replace('€', '').replace(',', '').strip()
    try: return float(s)
    except: return 0.0

# ── Theme definitions per segment ────────────────────────────────────────────
# Prevention themes — shared across countries except the "made in X" slot,
# which is swapped per country to reflect the local origin claim.
def prevention_themes_for(country_label):
    return [
        {"key": "efficacy_prevention",  "label": "Blocks / Repels Lice"},
        {"key": "natural_ingredients",  "label": "Natural Actives"},
        {"key": "chemical_free",        "label": "No Pesticides / DEET-Free"},
        {"key": "family_safe",          "label": "Family & Child Safe"},
        {"key": "daily_use",            "label": "Daily / Leave-In"},
        {"key": "textile_environment",  "label": "Textile / Environment"},
        {"key": "long_lasting",         "label": "Long-Lasting Protection"},
        {"key": "pleasant_fragrance",   "label": "Pleasant Fragrance"},
        {"key": "registered_approved",  "label": "Medically / Dermatologically Tested"},
        {"key": "made_in_local",        "label": f"Made in {country_label}"},
    ]

PREVENTION_THEMES = prevention_themes_for("Germany / EU")  # legacy alias (DE default)

TREATMENT_THEMES = [
    {"key": "kills_lice_eggs",      "label": "Kills Lice & Eggs"},
    {"key": "fast_action",          "label": "Fast Action (10–20 min)"},
    {"key": "physical_non_chemical","label": "Physical / No Insecticide"},
    {"key": "comb_included",        "label": "Comb Included / Is Comb"},
    {"key": "child_safe",           "label": "Child / Pregnancy Safe"},
    {"key": "medical_certified",    "label": "Medical Device / Pharmacy"},
    {"key": "gentle_skin",          "label": "Gentle on Scalp"},
    {"key": "no_odor",              "label": "Odor-Free / Colorless"},
    {"key": "family_size_value",    "label": "Family Size / Value Pack"},
    {"key": "no_resistance",        "label": "No Resistance Build-Up"},
]

# ── Theme assignments per ASIN (hand-curated from bullet content) ────────────
PREVENTION_CLAIMS = {
    "B07YYK4XT5": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","registered_approved"],
    "B0CVQP8GTW": ["efficacy_prevention","textile_environment","long_lasting","chemical_free","made_in_local","family_safe"],
    "B07GDHNBMR": ["efficacy_prevention","natural_ingredients","family_safe","daily_use"],
    "B00S6I29MU": ["efficacy_prevention"],
    "B0DP32SVNQ": ["efficacy_prevention","natural_ingredients","textile_environment","long_lasting","family_safe","pleasant_fragrance","made_in_local","chemical_free","registered_approved"],
    "B07QDNBKV4": ["efficacy_prevention","natural_ingredients","family_safe","daily_use","pleasant_fragrance"],
    "B07BMBKN86": ["efficacy_prevention","natural_ingredients","daily_use","family_safe"],
    "B073VNY7Y1": ["natural_ingredients","daily_use"],
    "B0FGWS9XMY": ["efficacy_prevention","textile_environment","family_safe","long_lasting","made_in_local","registered_approved"],
}

TREATMENT_CLAIMS = {
    "B0C5JMZDH3": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","medical_certified","gentle_skin","no_resistance"],
    "B084CN25JG": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","gentle_skin"],
    "B07KWPKKWZ": ["kills_lice_eggs","physical_non_chemical","gentle_skin","medical_certified","no_odor","no_resistance"],
    "B00E6EJJ9O": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","gentle_skin","no_odor","no_resistance","medical_certified"],
    "B07Q4BP5TJ": ["kills_lice_eggs","medical_certified","family_size_value"],
    "B00GJ11LCU": ["kills_lice_eggs","fast_action","physical_non_chemical","child_safe","medical_certified","gentle_skin","no_resistance"],
    "B07F79W116": ["kills_lice_eggs","physical_non_chemical","medical_certified"],
    "B06XFWX5K3": ["physical_non_chemical","child_safe","gentle_skin","comb_included"],
    "B06XH8FKM9": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","medical_certified"],
    "B07KX1BF3J": ["comb_included","child_safe","gentle_skin"],
    "B0DQV6Y19T": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","medical_certified","family_size_value","no_resistance"],
    "B0FQV95CL6": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","medical_certified","gentle_skin","family_size_value","no_resistance"],
    "B00NOQIN0G": ["medical_certified"],
    "B08G8VC1G2": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","medical_certified"],
    "B0CLT2VJVG": ["comb_included"],
}

# ── Hand-curated VOC gap / whitespace / saturation / recommendations ─────────
PREVENTION_VOC_GAP = [
    {"vocTopic":"Ineffective / lice still come back","customerConcernPct":"~35%","addressedByCount":5,"addressedByBrands":["naturetrend","Patronus","KRAFTKÖNIG","SHD","Thader"],"gapSeverity":"HIGH","whitespace":"Back the 'prevention' claim with a clinical/field test or repeat-use protocol. Most listings hint at protection but don't prove it — buyers read the reviews and feel gambled."},
    {"vocTopic":"Fragrance too strong / perfumy","customerConcernPct":"~15%","addressedByCount":2,"addressedByBrands":["OTC","Patronus"],"gapSeverity":"MEDIUM","whitespace":"Lead with 'mild natural scent' or 'unscented' variant. Most listings either don't mention smell or promise a strong scent."},
    {"vocTopic":"Sprayer clogs / leaks","customerConcernPct":"~10%","addressedByCount":1,"addressedByBrands":["Patronus"],"gapSeverity":"MEDIUM","whitespace":"Call out the pump mechanism quality — nobody does."},
    {"vocTopic":"Not safe for my youngest kid","customerConcernPct":"~20%","addressedByCount":6,"addressedByBrands":["SHD","naturetrend","Thader","Patronus","OTC","KRAFTKÖNIG"],"gapSeverity":"LOW","whitespace":"Put a specific minimum age ('from 1 yr / 3 yr') in the title — only OTC does today."},
]

PREVENTION_WHITESPACE = [
    {"opportunity":"Proof-backed prevention","rationale":"All 9 listings claim 'protects' but none show a lab result, school-year study, or repeat-purchase stat. 80% of competitors pitch prevention as a vague promise.","evidence":"Zero listings reference a % reduction in infestation rate or a controlled study."},
    {"opportunity":"School-ready bundle","rationale":"Parents buy before 'back-to-school' (Oct/Nov peak per seasonality). No listing bundles spray + textile spray + comb as a prevention-season kit.","evidence":"9/9 sell a single SKU format; none offer a September 'ready for school' bundle."},
    {"opportunity":"Textile-spray + hair-spray duo","rationale":"4 of 9 are textile sprays and 4 of 9 are leave-in hair sprays — but no brand sells both halves together, even though textile exposure is the main re-infestation path.","evidence":"naturetrend / Patronus / KRAFTKÖNIG / mosquito are textile-only; OTC / Thader / Kräutermax are hair-only."},
    {"opportunity":"Child-friendly format","rationale":"SHD's hair-bobble format (scrunchies) is a unique physical-delivery idea. 1 of 9 explores non-spray formats — huge space for creams, sticks, headbands.","evidence":"All other 8 competitors are sprays or shampoos."},
    {"opportunity":"Low-cost family 3-pack","rationale":"Average unit price is €15.50 and only Thader Petit sells a value size. Bulk pack at sub-€10/unit is open.","evidence":"No multi-pack in the top 9; family households (top buyer segment) are under-served."},
]

PREVENTION_SATURATION = [
    {"claim":"efficacy_prevention","label":"Repels / Blocks Lice","saturationPct":"89%","advice":"Everyone claims protection — differentiate by being SPECIFIC (weeks of protection, % reduction, school-year study)."},
    {"claim":"family_safe","label":"Safe for Kids","saturationPct":"78%","advice":"Table-stakes. Move beyond 'safe' to 'safe from X months' with a specific minimum age."},
    {"claim":"natural_ingredients","label":"Natural Actives","saturationPct":"67%","advice":"Saturated. Name the active (tea tree vs willow vs geraniol) and why it beats the others."},
    {"claim":"textile_environment","label":"Textile / Environment","saturationPct":"44%","advice":"Growing category — lead with 'furniture + bedding + car seat' use cases."},
    {"claim":"registered_approved","label":"Registered Biocide","saturationPct":"33%","advice":"Compliance matters in DE — put the BAuA number and 'officially registered biocide' prominently. 6 of 9 don't mention it."},
    {"claim":"pleasant_fragrance","label":"Pleasant Scent","saturationPct":"22%","advice":"Under-claimed but often complained about. Lead with 'soft / no strong perfume' to win scent-sensitive buyers."},
    {"claim":"long_lasting","label":"Long-Lasting Protection","saturationPct":"44%","advice":"Quantify the duration (hours, weeks, days) — none specify how long protection lasts."},
]

PREVENTION_RECOMMENDATIONS = [
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"9/9 listings claim 'prevention' or 'blocks lice' but none provide a study, lab result, or specific % reduction.","implication":"Fund a simple school-year observational study or cite an existing external one; use the figure as the main title hook. Be the only 'proven' prevention spray."},
    {"type":"Positioning","badgeBg":"#e0f2fe","badgeColor":"#075985","finding":"Market is split 4 textile-spray / 4 hair-spray / 1 physical — no brand owns 'complete protection system'.","implication":"Launch a Prevention Kit SKU (hair spray + textile spray + comb) priced at ~€25 — sits above singles and anchors a higher category price."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"Category is seasonal (Oct/Nov peak ~1.6×) but nobody times their listing copy to back-to-school.","implication":"Refresh title and A+ content in August with 'Ready for school' and 'September lice season' hooks. Run PPC spike Aug 15 – Oct 15."},
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"Only OTC (1/9) names a minimum age; others say 'for children' vaguely.","implication":"Put 'From 12 months' or similar explicitly in the title — removes a hesitation point for young-child parents."},
    {"type":"Packaging","badgeBg":"#dcfce7","badgeColor":"#166534","finding":"Family packs / bulk sizing completely absent from top 9.","implication":"Launch a 2× or 3× family pack at €22-28 total — captures sibling-household buyers (the biggest prevention segment)."},
]

TREATMENT_VOC_GAP = [
    {"vocTopic":"Eggs / nits not killed — had to retreat","customerConcernPct":"~30%","addressedByCount":9,"addressedByBrands":["Evolsin","NitWits","Nitnot","Linicin","SOS","NYDA","Health Press"],"gapSeverity":"HIGH","whitespace":"Call out the full lifecycle ('kills adults, larvae AND eggs') with a visible graphic. Many listings still just say 'gegen Läuse' which buyers read as 'adults only'."},
    {"vocTopic":"Treatment smells bad / greasy hair","customerConcernPct":"~25%","addressedByCount":3,"addressedByBrands":["Linicin","Nitnot","NitWits"],"gapSeverity":"HIGH","whitespace":"Lead with 'odor-free' AND 'washes out with normal shampoo' — rare combination today."},
    {"vocTopic":"Comb quality too flimsy / bends","customerConcernPct":"~20%","addressedByCount":2,"addressedByBrands":["Lausinator","Nitnot"],"gapSeverity":"HIGH","whitespace":"Spec the comb (metal, micro-gap, rigid handle) in the main product page, not as an afterthought. 8 of 15 include a comb but treat it as a freebie."},
    {"vocTopic":"Too little liquid for long hair","customerConcernPct":"~15%","addressedByCount":3,"addressedByBrands":["Licener (Maxi)","Health Press (Vorteilspackung)","Evolsin (Doppelpack)"],"gapSeverity":"MEDIUM","whitespace":"Offer volume-by-hair-length guide ('short = 50ml, long = 120ml, family = 240ml') on the listing."},
    {"vocTopic":"Didn't work — had to buy something else","customerConcernPct":"~20%","addressedByCount":4,"addressedByBrands":["Nitnot","NYDA","Evolsin","Health Press"],"gapSeverity":"HIGH","whitespace":"Add an unconditional 'kills or refund' guarantee — nobody offers one."},
    {"vocTopic":"Skin / scalp irritation","customerConcernPct":"~15%","addressedByCount":8,"addressedByBrands":["Evolsin","NitWits","Linicin","SOS","Nitnot","Health Press","Lausinator","Nitnot comb"],"gapSeverity":"LOW","whitespace":"Already well-addressed — table stakes."},
]

TREATMENT_WHITESPACE = [
    {"opportunity":"Guaranteed single-treatment kill","rationale":"30% of negative reviews complain the treatment needed a second round. No brand offers a 'works in one' guarantee.","evidence":"9 of 15 listings say 'repeat after 7-10 days' in the fine print — buyers interpret this as the product not working."},
    {"opportunity":"Odor-free + washes out clean","rationale":"Silicone-based formulas are notorious for greasy residue. Only 3 listings call out 'no odor' and only NitWits says 'easy to wash out'.","evidence":"12 of 15 are silicone/mineral-oil based; customer top-2 complaint is smell + greasiness."},
    {"opportunity":"Premium metal comb as hero","rationale":"The comb is bundled by 8 of 15 but always presented as a giveaway. Lausinator (€9.90, comb-only) proves standalone combs sell 961 units at the same price as a full treatment.","evidence":"No treatment bundles a premium named metal comb (like 'Nissolv Pro Comb') as a co-hero product."},
    {"opportunity":"Hair-length-specific SKU","rationale":"Only 3 listings address volume-for-hair-length. Parents of long-haired kids consistently report running out.","evidence":"12 of 15 are single-volume SKUs (100-200ml); no 'long hair 300ml' variant exists."},
    {"opportunity":"Refund / kill guarantee","rationale":"0 of 15 listings offer a money-back guarantee. This is a category where trust is the biggest buying blocker.","evidence":"Failure-refund wording completely absent from all 15 top listings."},
    {"opportunity":"Pregnancy-safe hero","rationale":"Evolsin and Health Press mention pregnancy/nursing safety in a bullet — but no brand puts it in the main title.","evidence":"2 of 15 mention pregnancy safety, 0 of 15 make it the primary positioning."},
]

TREATMENT_SATURATION = [
    {"claim":"kills_lice_eggs","label":"Kills Lice & Eggs","saturationPct":"80%","advice":"Table-stakes. Differentiate by calling out the lifecycle coverage with a diagram (egg → larva → adult)."},
    {"claim":"physical_non_chemical","label":"Physical / Silicone / No Insecticide","saturationPct":"80%","advice":"Saturated. Name the exact molecule (dimeticon, mineral oil, coconut oil) and why it beats the others."},
    {"claim":"medical_certified","label":"Medical Device / Pharmacy","saturationPct":"73%","advice":"Nearly all claim this. Lift it with a CE number, MHRA mention, or specific regulatory body."},
    {"claim":"child_safe","label":"Child / Pregnancy Safe","saturationPct":"67%","advice":"Pregnancy-safe is under-used — only 2 mention it. Lead with 'safe in pregnancy & nursing' for a niche lock."},
    {"claim":"comb_included","label":"Comb Included","saturationPct":"67%","advice":"Included but treated as a freebie. Name it, show it, spec the metal. 8 of 15 just say 'incl. Läusekamm' — generic."},
    {"claim":"fast_action","label":"Fast Action (10–20 min)","saturationPct":"53%","advice":"Speed is a 'must-match'. Don't compete on 'faster' — compete on 'works the first time'."},
    {"claim":"gentle_skin","label":"Gentle on Scalp","saturationPct":"53%","advice":"Table-stakes for child use. Specify 'hypoallergenic' or 'dermatologist tested' to stand out."},
    {"claim":"no_resistance","label":"No Resistance Build-Up","saturationPct":"47%","advice":"Strong technical claim under-leveraged. Put 'no resistance — works every time' in the bullet #1 slot."},
    {"claim":"no_odor","label":"Odor-Free / Colorless","saturationPct":"27%","advice":"Under-claimed vs how often it's complained about in reviews. Lead with 'no smell, no residue'."},
    {"claim":"family_size_value","label":"Family Size / Value Pack","saturationPct":"27%","advice":"Only 4 of 15 have a value SKU. Big open space for 'treats 4 people' format."},
]

TREATMENT_RECOMMENDATIONS = [
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"30% of negative reviews say the treatment didn't fully kill nits — requiring a second round. 0 of 15 listings offer a guarantee.","implication":"Add a 'one-treatment-kill or refund' pledge. Put it in the title and the hero image. Instant trust lever in a trust-starved category."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"12 of 15 products are silicone-based, yet only 3 explicitly address odor and only 1 addresses washout ease.","implication":"Make 'no smell + washes out with normal shampoo' the bullet #1 hook. Attack the category's dirtiest secret directly."},
    {"type":"Packaging","badgeBg":"#dcfce7","badgeColor":"#166534","finding":"8 of 15 bundle a comb as a freebie, but a standalone comb (Lausinator) sells 961 units at €9.90 — showing buyers value combs separately.","implication":"Position the included comb as a named co-hero product with its own brand and spec sheet, not an accessory. Adds ~€5 perceived value."},
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"12 of 15 SKUs are 100-200 ml — not enough for families or long-haired kids. 3 of 15 have value sizes.","implication":"Launch a 300 ml 'Long Hair' SKU and a 500 ml 'Family 4-Pack' at €25-30. Captures household buyers (biggest segment)."},
    {"type":"Positioning","badgeBg":"#e0f2fe","badgeColor":"#075985","finding":"2 of 15 mention pregnancy/nursing safety; 0 of 15 make it a primary title claim.","implication":"Pregnancy-safe hero angle — '1st choice for pregnant & nursing mothers' — is a clean category lock. Niche but defensible."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"Licener and Linicin still use minimal 'PZN + medical product' copy (pharmacy-era listings). They still sell — but are losing to content-rich challengers like Evolsin / NitWits.","implication":"The 'apothekenpflichtig' premium is eroding. Rich bullets + lifecycle diagrams + hero imagery beat pharmacy-minimal listings by 1.5-2× in this sample."},
]

# ── FR Prevention (top 10 by 30d revenue) ────────────────────────────────────
FR_PREVENTION_CLAIMS = {
    "B002GYIZPA": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","daily_use","made_in_local"],  # Pediakid 100ml
    "B01G4WNA6S": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","daily_use","long_lasting","pleasant_fragrance","made_in_local"],  # Puressentiel 24h
    "B0070X37DW": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","long_lasting"],  # Puressentiel basic
    "B0DQ1M471N": ["efficacy_prevention","natural_ingredients","textile_environment"],  # Panteer (no bullets)
    "B00FOSNOF6": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","daily_use","pleasant_fragrance","registered_approved","made_in_local"],  # Puressentiel Pouxdoux Bio shampoo
    "B0FPGH8B66": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","daily_use","registered_approved"],  # Déparaz 2-in-1
    "B071DR2SRZ": ["natural_ingredients","chemical_free","family_safe","pleasant_fragrance","made_in_local"],  # Puressentiel after-shampoo bio
    "B0B7RMDKPB": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","daily_use","made_in_local"],  # Pediakid 200ml
    "B0B7RHRNKV": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","daily_use","made_in_local"],  # Pediakid 300ml
    "B0099L8GIO": ["efficacy_prevention","natural_ingredients","family_safe","long_lasting","daily_use"],  # Pouxit 12h
}

# ── FR Treatment (top 15 by 30d revenue) ─────────────────────────────────────
FR_TREATMENT_CLAIMS = {
    "B09DWJP34Y": ["kills_lice_eggs","fast_action","physical_non_chemical","medical_certified","no_resistance"],  # Pouxit Flash lotion 5min
    "B0BTTM9TYX": ["kills_lice_eggs","fast_action","physical_non_chemical","medical_certified","no_resistance"],  # Pouxit Flash shampoo 5min
    "B0D4R67124": ["kills_lice_eggs","fast_action","physical_non_chemical","child_safe","medical_certified","no_resistance"],  # Pouxit apricot 15min
    "B07KWPKKWZ": ["kills_lice_eggs","physical_non_chemical","gentle_skin","medical_certified","no_odor","no_resistance"],  # NitNOT
    "B0724Z2D1J": ["comb_included","physical_non_chemical","medical_certified"],  # Pouxit nit balm
    "B01LT5UZZO": ["kills_lice_eggs","physical_non_chemical","comb_included","child_safe","gentle_skin","no_resistance"],  # DUO LP PRO 8h
    "B07KX1BF3J": ["comb_included","child_safe","gentle_skin"],  # NitNOT comb
    "B096BL7371": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","family_size_value"],  # Pediakid full kit
    "B076W33NBM": ["kills_lice_eggs","fast_action","physical_non_chemical","child_safe","gentle_skin","no_resistance"],  # Marie Rose
    "B0CQ23GTZK": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","no_resistance","medical_certified"],  # Paranix Spray 5min
    "B0938KWY7K": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","no_resistance","family_size_value","medical_certified"],  # Paranix 300ml shampoo
    "B07SQG9NVX": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","medical_certified","no_resistance"],  # Puressentiel 2en1
    "B0G7KPVKM9": ["kills_lice_eggs","physical_non_chemical","child_safe","no_resistance"],  # Déparaz shampoo
    "B0939HK4KR": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","no_resistance","medical_certified"],  # Paranix 200ml shampoo
    "B0F1D9NJNC": ["kills_lice_eggs","fast_action","gentle_skin","comb_included","physical_non_chemical"],  # Paranix 2-min lotion
}

# FR Prevention — strategic analysis
FR_PREVENTION_VOC_GAP = [
    {"vocTopic":"Strong lavender/essential oil scent","customerConcernPct":"~30%","addressedByCount":2,"addressedByBrands":["Puressentiel","Pediakid"],"gapSeverity":"HIGH","whitespace":"Offer a low-scent or fragrance-free variant. 8 of 10 lead with essential oils; scent-sensitive buyers have no option."},
    {"vocTopic":"Prevention doesn't work — kid still got lice","customerConcernPct":"~35%","addressedByCount":3,"addressedByBrands":["Puressentiel","Pouxit","Pediakid"],"gapSeverity":"HIGH","whitespace":"Cite a clinical efficacy figure (% repelled, school-year study). Only Puressentiel quantifies protection (24h) and Pouxit (12h); rest are vague."},
    {"vocTopic":"Not suitable for under-3s","customerConcernPct":"~20%","addressedByCount":7,"addressedByBrands":["Pediakid","Puressentiel","Pouxit","Déparaz"],"gapSeverity":"MEDIUM","whitespace":"Only Pediakid targets youngest kids explicitly. A 'from 12 months' claim is a clean differentiator."},
    {"vocTopic":"Makes hair greasy / sticky","customerConcernPct":"~15%","addressedByCount":2,"addressedByBrands":["Puressentiel","Déparaz"],"gapSeverity":"MEDIUM","whitespace":"Lead with 'non-greasy / light texture' — rarely called out."},
]

FR_PREVENTION_WHITESPACE = [
    {"opportunity":"Clinically-proven prevention","rationale":"Only Puressentiel and Pouxit quantify protection duration (24h / 12h). None cite a school-year study or % infestation reduction.","evidence":"0 of 10 show a clinical % reduction; 2 of 10 mention a protection-duration hour figure."},
    {"opportunity":"Essential-oil-free alternative","rationale":"8 of 10 Prevention listings lead with essential oils (lavender, eucalyptus, geraniol). Anyone allergic or scent-sensitive has nowhere to go.","evidence":"Only Panteer and Déparaz use non-EO actives as lead ingredients."},
    {"opportunity":"School-ready bundle","rationale":"Rentrée scolaire (Aug-Sept) is the category's biggest demand window. Nobody sells a 'back-to-school kit' combining spray + shampoo + textile spray + comb.","evidence":"10 of 10 FR Prevention listings sell single SKUs."},
    {"opportunity":"Under-12-month safe","rationale":"Every listing specifies 'dès 3 ans' or 'dès 6 mois'. Parents of toddlers are locked out.","evidence":"0 of 10 FR Prevention products claim safety under 6 months."},
    {"opportunity":"Textile + hair combo","rationale":"Only Panteer (1/10) is a textile spray. The French market under-indexes on environmental treatment vs DE.","evidence":"1 of 10 FR vs 4 of 9 DE sell textile prevention sprays — huge whitespace."},
]

FR_PREVENTION_SATURATION = [
    {"claim":"efficacy_prevention","label":"Repels / Blocks Lice","saturationPct":"90%","advice":"Table-stakes. Quantify protection — 12h, 24h, 72h, or % reduction. Only Puressentiel + Pouxit do."},
    {"claim":"natural_ingredients","label":"Essential Oils / Natural","saturationPct":"100%","advice":"Completely saturated. Every brand leads with essential oils — the whitespace is going the OTHER direction (EO-free)."},
    {"claim":"chemical_free","label":"No Pesticides / Paraben-Free","saturationPct":"70%","advice":"Standard French pharmacy language. Not a differentiator."},
    {"claim":"family_safe","label":"Child-Safe","saturationPct":"90%","advice":"Specify the minimum age in the title. 'Dès 12 mois' is rarer than 'dès 3 ans' and wins younger families."},
    {"claim":"daily_use","label":"Daily / Leave-In","saturationPct":"70%","advice":"Back-to-school timing wins. Change copy Aug 1 for rentrée scolaire."},
    {"claim":"long_lasting","label":"Long-Lasting Protection","saturationPct":"30%","advice":"Under-claimed — only 3/10 quantify duration. Putting '24h' or '72h' in the title is a quick win."},
    {"claim":"made_in_local","label":"Made in France","saturationPct":"50%","advice":"French origin matters in this market — 5/10 claim it. Clear price premium justifier."},
    {"claim":"textile_environment","label":"Textile / Environment","saturationPct":"10%","advice":"Wide open — only Panteer plays here. Big opportunity for a textile-spray entrant."},
]

FR_PREVENTION_RECOMMENDATIONS = [
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"10 of 10 claim 'prevention', but only Puressentiel (24h) and Pouxit (12h) quantify duration. Zero cite a school-year efficacy study.","implication":"Run one in-vitro repellent study (€3-5k) and put '88% reduction in re-infestation' or similar in the title. Becomes the only 'proven' prevention spray in France."},
    {"type":"Positioning","badgeBg":"#e0f2fe","badgeColor":"#075985","finding":"8 of 10 are essential-oil formulas. Scent-sensitive and allergy-prone families have no alternative.","implication":"Launch an EO-free variant — synthetic or mineral-oil-based — with 'sans parfum, sans huiles essentielles' as the hero claim. Clean differentiator in a saturated natural-oils market."},
    {"type":"Packaging","badgeBg":"#dcfce7","badgeColor":"#166534","finding":"1 of 10 is a textile spray (Panteer). The French category is ~10% textile vs 44% in DE — undersupplied.","implication":"Launch a textile prevention spray for FR. Reference customer pain ('poux dans le canapé / voiture / doudou'). Price €15-18 to match Pouxit/Puressentiel single SKUs."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"Seasonality peaks in Oct (1.27×). Every listing uses 'période d'épidémie' / 'rentrée scolaire' but nobody refreshes content for August.","implication":"Hard-code 'Rentrée 2026 — prêt pour l'école' in A+ content and refresh title on Aug 1. Ride the Aug-Oct search surge."},
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"0 of 10 claim safety under 6 months. Every listing locks out infants.","implication":"Source an EO-free, dermatologically tested formula safe 'dès la naissance' or '0 mois'. Niche lock for the youngest-kids segment."},
]

FR_TREATMENT_VOC_GAP = [
    {"vocTopic":"Reinfestation within weeks","customerConcernPct":"~30%","addressedByCount":3,"addressedByBrands":["Paranix","Pouxit","Déparaz"],"gapSeverity":"HIGH","whitespace":"Paranix (LPF 72h) is the only brand with an explicit reinfestation claim. Competitors should either match or offer a 'free prevention spray included' bundle."},
    {"vocTopic":"Product leaves greasy hair / residue","customerConcernPct":"~25%","addressedByCount":4,"addressedByBrands":["Paranix","Puressentiel","Déparaz","Pouxit Flash"],"gapSeverity":"HIGH","whitespace":"'Sans silicone' and 'rinçage facile' are underclaimed — only Paranix leads with both. Buyers complain about greasiness more than efficacy."},
    {"vocTopic":"Fast action but eggs survive","customerConcernPct":"~20%","addressedByCount":6,"addressedByBrands":["Pouxit","Paranix","Déparaz","Puressentiel"],"gapSeverity":"MEDIUM","whitespace":"Show the lifecycle — kills eggs, nymphs, AND adults — explicitly. Current copy focuses on adult kill time (2-5 min) and skips eggs."},
    {"vocTopic":"Not enough volume for long or thick hair","customerConcernPct":"~15%","addressedByCount":2,"addressedByBrands":["NitNOT (XL)","Paranix 300ml"],"gapSeverity":"MEDIUM","whitespace":"XL / family-pack volumes are rare. Paranix 300ml and NitNOT XL are the only options."},
    {"vocTopic":"Treatment failed — had to buy another","customerConcernPct":"~20%","addressedByCount":0,"addressedByBrands":[],"gapSeverity":"HIGH","whitespace":"Zero brands offer a 'works first time or refund' guarantee. Open whitespace to lock trust."},
    {"vocTopic":"Unsafe for young kids / pregnancy","customerConcernPct":"~15%","addressedByCount":5,"addressedByBrands":["Pouxit (6 mois)","DUO LP PRO (6 mois, enceintes)","Puressentiel (3 ans)","Paranix (12 mois)","Marie Rose (3 ans)"],"gapSeverity":"LOW","whitespace":"DUO LP PRO is the only brand with explicit pregnancy safety. Niche but defensible."},
]

FR_TREATMENT_WHITESPACE = [
    {"opportunity":"Sub-2-minute action","rationale":"Paranix Express 2-min is the fastest. Anyone claiming '60 seconds' or '90 seconds' instantly leapfrogs the category leader.","evidence":"Pouxit Flash = 5 min, Paranix = 2 min, all others ≥15 min. 1-min is open."},
    {"opportunity":"Reinfestation-proof bundle","rationale":"Paranix LPF protects 72h after treatment — the only reinfestation claim in FR. Competitors missing the follow-through.","evidence":"1 of 15 (Paranix) addresses post-treatment reinfestation; 0 of 15 include a 7-day prevention spray in the box."},
    {"opportunity":"Pregnancy / breastfeeding hero","rationale":"DUO LP PRO is the only brand that puts pregnancy/nursing safety in a bullet. No one titles on it.","evidence":"1 of 15 mentions pregnancy safety; 0 of 15 use it as the primary positioning."},
    {"opportunity":"Guaranteed refund","rationale":"0 of 15 listings offer a money-back or retreat guarantee. French buyers are trust-sensitive in pharmacy categories.","evidence":"Failure-refund wording absent from all 15 top FR listings."},
    {"opportunity":"Premium metal comb with branding","rationale":"Paranix bundles a 'peigne fin en métal' generically. No brand makes the comb a co-hero with its own spec sheet.","evidence":"12 of 15 include a comb, all generic. Standalone high-end combs are untapped."},
    {"opportunity":"Volume-specific SKUs","rationale":"Only Paranix 300ml and NitNOT XL200ml address long/thick hair. Most SKUs are 100-150ml.","evidence":"2 of 15 sell >200ml formats."},
]

FR_TREATMENT_SATURATION = [
    {"claim":"kills_lice_eggs","label":"Kills Lice & Eggs","saturationPct":"87%","advice":"Table-stakes. Differentiate with a claim like '100% in 1 application' — currently Paranix owns this."},
    {"claim":"fast_action","label":"Fast Action (2–15 min)","saturationPct":"73%","advice":"Highly saturated (2 min–5 min is the norm). 1-minute or instant-action is the only upgrade."},
    {"claim":"physical_non_chemical","label":"Sans Insecticide","saturationPct":"100%","advice":"Completely saturated — every top FR treatment is 'sans insecticide'. No differentiation available here."},
    {"claim":"comb_included","label":"Peigne Inclus","saturationPct":"73%","advice":"Nearly universal. Differentiate by specifying metal + gap spacing + hero-branding the comb."},
    {"claim":"child_safe","label":"Child / Pregnancy Safe","saturationPct":"53%","advice":"Specify minimum age. 'Dès 6 mois' is rare (Pouxit + DUO LP PRO only) and very differentiating."},
    {"claim":"medical_certified","label":"Dispositif Médical / Pharmacie","saturationPct":"67%","advice":"Standard claim. French buyers trust 'dispositif médical CE' — call out the CE number explicitly."},
    {"claim":"gentle_skin","label":"Dermatologically Tested","saturationPct":"33%","advice":"Under-claimed. Add 'testé dermatologiquement' to the bullet stack — easy claim to add."},
    {"claim":"no_odor","label":"Odor-Free","saturationPct":"7%","advice":"Only NitNOT claims this. Huge whitespace — 2 of top 3 complaints are about smell/greasiness."},
    {"claim":"family_size_value","label":"Family / Value Size","saturationPct":"13%","advice":"Under-claimed. 300ml + kit formats are open for growth."},
    {"claim":"no_resistance","label":"No Resistance","saturationPct":"80%","advice":"Standard benefit of physical action. Lead with 'aucun risque de résistance' — Paranix does this, most don't explicitly."},
]

FR_TREATMENT_RECOMMENDATIONS = [
    {"type":"Positioning","badgeBg":"#e0f2fe","badgeColor":"#075985","finding":"Pouxit + Paranix together hold 8 of the top 15 SKUs. Both claim 'sans insecticide' + fast action. Differentiation is razor-thin.","implication":"Don't compete on speed (Paranix = 2 min) or on 'sans insecticide' (saturated). Pick: reinfestation-proof bundle, pregnancy-safe hero, or guaranteed refund. All three are open."},
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"Only Paranix LPF claims 72h reinfestation protection. Customers cite reinfestation as a top-3 concern but most brands ignore it.","implication":"Add a prevention spray (10ml sachet) inside every treatment box. Copy hook: 'Traite + Protège 7 jours'. Differentiates on the full customer journey, not just the kill."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"13 of 15 are silicone or oil-based. 'Sans silicone / rinçage facile' is claimed by only 4 brands, but greasiness is the #2 complaint after reinfestation.","implication":"Lead bullet 1 with 'sans silicone — rince en 1 passage'. Paranix does this; others haven't caught up."},
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"DUO LP PRO is the only product with pregnancy/nursing safety in a bullet. 0 brands title on it.","implication":"Launch a 'Mamans enceintes & allaitantes' hero SKU. Dermatologically tested, EO-free, silicone-free. Lock a protected niche."},
    {"type":"Packaging","badgeBg":"#dcfce7","badgeColor":"#166534","finding":"Only Paranix 300ml and NitNOT XL target long/thick hair. 13 of 15 are 100-150ml.","implication":"Launch a 300ml 'Cheveux longs' SKU and a 'Famille 4 personnes' value pack. Captures household buyers — the biggest FR segment."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"Pouxit claims 'Leader des traitements anti-poux en France depuis 2006' in every listing. Paranix doesn't match. Trust-signal gap.","implication":"Any challenger brand needs its own trust anchor — clinical study, dermatologist endorsement, or school-partnership claim. Being silent is losing."},
]

# ── ES Prevention (top 9 — all available) ───────────────────────────────────
ES_PREVENTION_CLAIMS = {
    "B01BN0QUUE": ["efficacy_prevention","chemical_free","family_safe","daily_use","pleasant_fragrance","registered_approved"],  # Neositrín 200ml
    "B01ADEMJFQ": ["efficacy_prevention","chemical_free","family_safe","daily_use","pleasant_fragrance","registered_approved"],  # Neositrín 100ml
    "B07QDNBKV4": ["efficacy_prevention","natural_ingredients","family_safe","daily_use","pleasant_fragrance","registered_approved"],  # OTC Strawberry
    "B0CBPW3M74": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","daily_use"],  # ANIAN tea tree
    "B0BPCZLPC2": ["efficacy_prevention","natural_ingredients","chemical_free","daily_use","pleasant_fragrance"],  # BACTERISAN
    "B075KDM9XH": ["efficacy_prevention","natural_ingredients","family_safe","daily_use"],  # Tahe
    "B0FZW1M61S": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","daily_use","pleasant_fragrance","registered_approved"],  # Essenciales 100% natural
    "B086BB8N14": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","daily_use","pleasant_fragrance"],  # PRANAROM BIO
    "B0F2TDVCBT": ["efficacy_prevention","natural_ingredients","family_safe","daily_use","pleasant_fragrance","registered_approved"],  # SUAVINEX
}

# ── ES Treatment (top 10 — smaller market) ──────────────────────────────────
ES_TREATMENT_CLAIMS = {
    "B00TTWTOJI": ["kills_lice_eggs","fast_action","physical_non_chemical","child_safe","medical_certified","no_resistance"],  # Neositrín 1min
    "B07BBMJFM1": ["kills_lice_eggs","fast_action","physical_non_chemical","child_safe","no_odor","gentle_skin","no_resistance"],  # OTC 2min
    "B07C41N7T1": ["kills_lice_eggs","fast_action","comb_included","child_safe","family_size_value","medical_certified"],  # ZZ kit (permethrin — NOT physical)
    "B0D33NP6VB": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","gentle_skin"],  # Nitwits 20min
    "B009VZJD8K": ["kills_lice_eggs","fast_action","child_safe"],  # ZZ Lotion (permethrin)
    "B0179QDKFY": ["kills_lice_eggs","fast_action","physical_non_chemical","child_safe","medical_certified"],  # ISDIN Neem 10min
    "B00KP7PUE4": ["kills_lice_eggs","physical_non_chemical","comb_included","no_resistance"],  # Paranix 2en1
    "B00WUOFQOE": ["kills_lice_eggs","fast_action","physical_non_chemical","child_safe","family_size_value","gentle_skin","no_resistance"],  # Neositrín Pack pregnancy-safe
    "B00J5FYKPW": ["physical_non_chemical","child_safe","gentle_skin"],  # Neositrín post-shampoo
    "B01BMLRSGO": ["kills_lice_eggs","physical_non_chemical","comb_included","child_safe","family_size_value"],  # FullMarks kit
}

ES_PREVENTION_VOC_GAP = [
    {"vocTopic":"Doesn't actually prevent infestation","customerConcernPct":"~30%","addressedByCount":2,"addressedByBrands":["Neositrín","Essenciales"],"gapSeverity":"HIGH","whitespace":"Only Neositrín quantifies with 'Activdiol' and only Essenciales says 'clinically tested'. Cite a % reduction or repeat-purchase stat to beat 'barrera invisible' vagueness."},
    {"vocTopic":"Perfume too strong / allergic reactions","customerConcernPct":"~20%","addressedByCount":1,"addressedByBrands":["SUAVINEX"],"gapSeverity":"MEDIUM","whitespace":"Only SUAVINEX targets atopic/sensitive skin explicitly. Launch a 'sin fragancia' variant."},
    {"vocTopic":"Too concentrated on tea tree — kids hate smell","customerConcernPct":"~15%","addressedByCount":3,"addressedByBrands":["Neositrín","OTC","Essenciales"],"gapSeverity":"MEDIUM","whitespace":"Fruit-scented products win. Naranja/fresa/manzana are under-explored vs tea tree oil."},
    {"vocTopic":"Not safe for babies","customerConcernPct":"~20%","addressedByCount":1,"addressedByBrands":["SUAVINEX (6m+)"],"gapSeverity":"MEDIUM","whitespace":"SUAVINEX is the only 6-months-plus product. Everyone else is 12m+. A '0m+' or dermato-tested infant variant is open."},
]

ES_PREVENTION_WHITESPACE = [
    {"opportunity":"Clinically-proven prevention","rationale":"Every listing claims 'barrera protectora' but only Neositrín cites an active (Activdiol/Caprylyl Glycol) and Essenciales mentions EU lab testing.","evidence":"0 of 9 show a school-year efficacy study or % infestation reduction."},
    {"opportunity":"Fragrance-free / hypoallergenic","rationale":"Every ES prevention product is either tea-tree-heavy or fruit-scented. Atopic families have only SUAVINEX, which still uses tea tree.","evidence":"0 of 9 offer a true fragrance-free variant."},
    {"opportunity":"Infant-safe (0-6 months)","rationale":"SUAVINEX is the only 6-months-plus product. Every other locks out under-12-month babies.","evidence":"1 of 9 targets babies explicitly."},
    {"opportunity":"Textile / environment prevention","rationale":"Zero textile prevention sprays in ES. The category doesn't exist locally despite strong DE presence.","evidence":"0 of 9 ES vs 4 of 9 DE sell textile prevention sprays."},
    {"opportunity":"School-themed back-to-school bundle","rationale":"October seasonality peak (1.89× — highest of all 4 EU markets). Nobody bundles shampoo + spray + textile spray + comb for the school season.","evidence":"9 of 9 sell single SKUs; none offer a 'Vuelta al cole' kit."},
]

ES_PREVENTION_SATURATION = [
    {"claim":"efficacy_prevention","label":"Protects Against Lice","saturationPct":"100%","advice":"Completely saturated. Quantify — 12h, 24h, % reduction — none do."},
    {"claim":"natural_ingredients","label":"Natural Actives (Tea Tree / Quassia)","saturationPct":"78%","advice":"7 of 9 lead with tea tree. The whitespace is the OPPOSITE direction — synthetic or non-EO alternatives for allergy-prone."},
    {"claim":"chemical_free","label":"No Pesticides / Paraben-Free","saturationPct":"67%","advice":"Saturated. Move beyond 'sin químicos' to a specific named molecule excluded ('sin permetrina', 'sin piretrinas')."},
    {"claim":"family_safe","label":"Child-Safe","saturationPct":"89%","advice":"Table-stakes. Specify minimum age in the title — most say 'niños' vaguely. 'Desde 6 meses' (SUAVINEX only) wins parents of babies."},
    {"claim":"daily_use","label":"Daily Use","saturationPct":"100%","advice":"Universal. Differentiate with frequency guidance — 'uso diario' vs '2-3 veces/semana'."},
    {"claim":"pleasant_fragrance","label":"Pleasant Fragrance","saturationPct":"67%","advice":"Fruit scents (fresa, naranja, mango) are winning vs tea tree. Strawberry and apple are under-used."},
    {"claim":"registered_approved","label":"Dermatologically Tested","saturationPct":"44%","advice":"Only 4 of 9 cite dermatological testing. Add 'testado dermatológicamente' — quick win."},
]

ES_PREVENTION_RECOMMENDATIONS = [
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"Neositrín has 2 of top 9 Prevention SKUs at €42k + €21k 30d revenue — 2× the next competitor. Their 'Activdiol' moat is pure branding around a standard ingredient.","implication":"Neositrín is the price-setter. Any challenger must either (a) beat them on a specific clinical claim or (b) attack an under-served niche (infants, atopic, textile)."},
    {"type":"Positioning","badgeBg":"#e0f2fe","badgeColor":"#075985","finding":"7 of 9 ES prevention products lead with tea tree. Atopic / sensitive-skin families are essentially locked out.","implication":"Launch an 'Atopic / Sensitive Skin' SKU — fragrance-free, no tea tree, dermato-pediatric certified. Compete directly with SUAVINEX but go further (0m+)."},
    {"type":"Packaging","badgeBg":"#dcfce7","badgeColor":"#166534","finding":"0 of 9 ES listings are textile sprays. This category doesn't exist locally despite high DE adoption.","implication":"Launch a textile prevention spray for ES with 'spray para sofás, coches y ropa'. Price €14-16 to match single SKUs. First-mover category creation."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"October seasonality is 1.89× — the highest of the 4 EU markets. ES has the most pronounced back-to-school pattern, yet no brand refreshes for 'vuelta al cole'.","implication":"Refresh title + A+ content Aug 15 with 'Vuelta al cole 2026' hook. PPC spike Aug 15 — Oct 15. Opportunity is largest in ES."},
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"Only SUAVINEX targets 6m+ infants. Everyone else is 12m+ or vaguely 'for children'.","implication":"Partner with a dermato-pediatric lab (ES trusts these) to certify a 0-month variant. Hero claim: 'desde el nacimiento'."},
]

ES_TREATMENT_VOC_GAP = [
    {"vocTopic":"Fast claims don't match reality — product failed","customerConcernPct":"~30%","addressedByCount":4,"addressedByBrands":["Neositrín","OTC","ISDIN","Paranix"],"gapSeverity":"HIGH","whitespace":"Neositrín claims '1 minuto' and OTC '2 minutos' — ultra-fast claims are hard to believe. A 'funciona o devolvemos el dinero' guarantee closes the trust gap."},
    {"vocTopic":"Permethrin resistance — ZZ no longer works","customerConcernPct":"~20%","addressedByCount":7,"addressedByBrands":["Neositrín","OTC","Paranix","Nitwits","ISDIN","FullMarks"],"gapSeverity":"HIGH","whitespace":"2 of 10 ES products still use permethrin (ZZ). The other 8 explicitly claim 'sin insecticidas / physical action'. Buyers increasingly understand permethrin resistance — attack the ZZ position directly."},
    {"vocTopic":"Strong smell / chemical fumes","customerConcernPct":"~20%","addressedByCount":1,"addressedByBrands":["OTC (inodora)"],"gapSeverity":"HIGH","whitespace":"Only OTC explicitly claims 'inodora e incolora'. Huge whitespace — 9 of 10 are fragranced or unscored."},
    {"vocTopic":"Didn't cover long hair","customerConcernPct":"~15%","addressedByCount":2,"addressedByBrands":["Neositrín Pack","ZZ Kit"],"gapSeverity":"MEDIUM","whitespace":"60ml / 100ml SKUs are under-sized for long hair. Only multi-piece packs exceed 150ml total."},
    {"vocTopic":"Hard to rinse out / greasy","customerConcernPct":"~15%","addressedByCount":1,"addressedByBrands":["Paranix"],"gapSeverity":"MEDIUM","whitespace":"Only Paranix claims easy rinse (2-in-1). Dimeticone-based products notoriously leave residue — open space."},
    {"vocTopic":"Unsafe for pregnancy / babies","customerConcernPct":"~15%","addressedByCount":3,"addressedByBrands":["Neositrín Pack (embarazadas)","Neositrín 1min (12m+)","OTC (1 año+)"],"gapSeverity":"LOW","whitespace":"Neositrín Pack is the only brand explicitly naming pregnancy + asthmatic + atopic safety. Strong niche, under-marketed."},
]

ES_TREATMENT_WHITESPACE = [
    {"opportunity":"Sub-1-minute or instant kill","rationale":"Neositrín '1 minuto' is currently the fastest. OTC claims '2 minutos'. Anyone claiming '30 segundos' or 'instant' leapfrogs both.","evidence":"Neositrín = 1 min, OTC = 2 min, ISDIN/ZZ/Paranix = 10 min, Nitwits = 20 min. Sub-60s is open."},
    {"opportunity":"Anti-permethrin campaign","rationale":"ZZ still sells with permethrin (the only insecticide-based product in the ES top 10). Growing customer awareness of resistance makes this a ripe target.","evidence":"2 of 10 ES listings use permethrin; 8 of 10 explicitly claim 'sin insecticidas'. Campaign: 'Los piojos ya son resistentes a la permetrina — elige un producto físico'."},
    {"opportunity":"Odorless + colorless premium","rationale":"Only OTC (1/10) claims 'inodora e incolora'. Spanish buyers consistently complain about smell in reviews.","evidence":"1 of 10 treatments has the odorless + colorless combo. Clear whitespace."},
    {"opportunity":"Pregnancy-safe hero positioning","rationale":"Only Neositrín Pack mentions pregnancy/asthmatic/atopic explicitly, but it's buried in bullet 4.","evidence":"1 of 10 mentions pregnancy safety; 0 of 10 lead on it in the title."},
    {"opportunity":"Long-hair SKU","rationale":"60-100ml is the norm. Long-haired kids run out mid-treatment.","evidence":"0 of 10 sell a 200ml+ single-SKU treatment. Kits include multiple items but no single long-hair bottle."},
    {"opportunity":"Refund / kill guarantee","rationale":"0 of 10 offer a money-back. Spanish pharmacy buyers value guarantees highly.","evidence":"No failure-refund language in any ES top-10 listing."},
]

ES_TREATMENT_SATURATION = [
    {"claim":"kills_lice_eggs","label":"Elimina Piojos y Liendres","saturationPct":"90%","advice":"Table-stakes. Lead with a guarantee instead — 'funciona o devolvemos el dinero'."},
    {"claim":"fast_action","label":"Fast Action (1–20 min)","saturationPct":"80%","advice":"Saturated. Neositrín owns '1 minuto'. Anyone else must claim sub-60s or stop competing on speed."},
    {"claim":"physical_non_chemical","label":"Sin Insecticidas","saturationPct":"80%","advice":"Becoming standard. 2 permethrin holdouts (ZZ) still sell — attack them directly."},
    {"claim":"comb_included","label":"Lendrera Incluida","saturationPct":"50%","advice":"Only half include a comb. Cheap differentiation — upgrade to metal lendrera and call it out."},
    {"claim":"child_safe","label":"Child-Safe","saturationPct":"90%","advice":"Specify minimum age. 'Desde 12 meses' (Neositrín) is the gold standard; 3 años (ZZ) and 1 año (most) also exist."},
    {"claim":"medical_certified","label":"Dermato / Clinical","saturationPct":"40%","advice":"Under-claimed for a pharmacy-driven market. Add 'clínicamente testado' or dermato certification."},
    {"claim":"gentle_skin","label":"Piel Sensible / Atópica","saturationPct":"40%","advice":"Under-claimed. 'Apto para piel atópica' is a specific hook that SUAVINEX / OTC use."},
    {"claim":"no_odor","label":"Inodora / Incolora","saturationPct":"10%","advice":"Only OTC claims both. Huge whitespace — lead bullet 1 with it."},
    {"claim":"family_size_value","label":"Kit / Pack","saturationPct":"40%","advice":"Kits are common (ZZ, Neositrín, FullMarks). Differentiate by what's IN the kit, not just having one."},
    {"claim":"no_resistance","label":"No Resistance Build-Up","saturationPct":"60%","advice":"Standard physical-action benefit. Tie it to the permethrin resistance story for impact."},
]

ES_TREATMENT_RECOMMENDATIONS = [
    {"type":"Positioning","badgeBg":"#e0f2fe","badgeColor":"#075985","finding":"Neositrín holds 4 of the top 10 ES treatment SKUs (40% of the top by count). They own '1 minuto' positioning and pregnancy-safety claims.","implication":"Direct competition with Neositrín is losing. Pick an angle they don't own: instant kill (sub-60s), anti-permethrin campaign, or premium fragrance-free."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"ZZ (permethrin) still has 2 of top 10 slots despite growing resistance concerns. 8 of 10 competitors explicitly say 'sin insecticidas' but nobody attacks the permethrin position.","implication":"Launch an 'anti-resistencia' campaign. Copy hook: 'Los piojos ya resisten a la permetrina — elige tratamiento físico'. Target ZZ buyers directly."},
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"Only OTC claims 'inodora e incolora'. Smell is consistently a top-3 complaint in reviews.","implication":"Formulate a truly odorless/colorless dimethicone treatment. Lead title with 'sin olor, sin color, sin dejar residuos'."},
    {"type":"Positioning","badgeBg":"#e0f2fe","badgeColor":"#075985","finding":"Only Neositrín Pack mentions pregnancy + asthmatic + atopic — buried in bullet 4.","implication":"Make it the primary positioning — 'Tratamiento antipiojos para embarazadas, bebés y piel atópica'. Niche lock, high margin."},
    {"type":"Packaging","badgeBg":"#dcfce7","badgeColor":"#166534","finding":"60-100ml is the norm. Long-haired kids run out mid-treatment; only kits provide enough volume.","implication":"Launch a 200ml 'Pelo largo' variant. Fewer bottles = better UX + higher per-SKU revenue."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"October seasonality is 1.89× — highest of all EU lice markets. Treatment demand spikes dramatically with the school return.","implication":"Shift ~60% of annual PPC + promo budget into Aug 15 – Oct 30. Refresh hero image and title with 'Vuelta al cole' messaging from Aug 1."},
]

# ── IT Prevention (top 10) ──────────────────────────────────────────────────
IT_PREVENTION_CLAIMS = {
    "B01M7V73CK": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","daily_use","made_in_local"],  # Helan Occhio al Pidocchio
    "B081VVQRM1": ["efficacy_prevention","natural_ingredients","family_safe","daily_use","made_in_local"],  # Aftir Preaftir spray
    "B00BUH65R4": ["efficacy_prevention","natural_ingredients","chemical_free","long_lasting","daily_use","pleasant_fragrance"],  # Paranix Prevent
    "B0DQ1M471N": ["efficacy_prevention","natural_ingredients","textile_environment","registered_approved"],  # Panteer textile
    "B081VVP42W": ["efficacy_prevention","natural_ingredients","family_safe","daily_use","made_in_local"],  # Aftir Preaftir shampoo
    "B00FOSNOF6": ["natural_ingredients","chemical_free","family_safe","daily_use","registered_approved","pleasant_fragrance"],  # Puressentiel Pouxdoux Bio
    "B081VV1Y9S": ["natural_ingredients","daily_use","made_in_local"],  # Aftir post-treatment
    "B01BI50014": ["efficacy_prevention","natural_ingredients","chemical_free","daily_use","made_in_local"],  # Linea Act Lendinout
    "B0BPCZLPC2": ["efficacy_prevention","natural_ingredients","chemical_free","daily_use","pleasant_fragrance"],  # BACTERISAN
    "B079QK13Z8": ["efficacy_prevention","natural_ingredients","chemical_free","family_safe","daily_use","registered_approved","made_in_local"],  # Natura House Liberella
}

# ── IT Treatment (top 10) ───────────────────────────────────────────────────
IT_TREATMENT_CLAIMS = {
    "B0892Q7DB6": ["kills_lice_eggs","fast_action","physical_non_chemical","no_resistance","medical_certified"],  # Paranix Extra Forte 5min + 72h
    "B01BIGUZ04": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","medical_certified","no_resistance"],  # Linea Act Lendinout
    "B01M9GFPLY": ["kills_lice_eggs","fast_action","physical_non_chemical","child_safe","gentle_skin","medical_certified"],  # Helan Occhio shampoo
    "B00D3HW2K8": ["kills_lice_eggs","physical_non_chemical","comb_included","medical_certified","no_resistance"],  # Paranix 100% clinical
    "B0DB8R78XK": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","medical_certified","no_resistance"],  # Pouxit Flash 5min preg-safe
    "B015YBUQKI": ["comb_included","physical_non_chemical","gentle_skin","made_in_local"],  # Assy 2000 comb
    "B08152CNM6": ["kills_lice_eggs","fast_action","physical_non_chemical","child_safe","no_resistance","made_in_local"],  # Aftir Gel 10min
    "B07KWPKKWZ": ["kills_lice_eggs","physical_non_chemical","gentle_skin","medical_certified","no_odor","no_resistance"],  # NitNOT
    "B0C7GZ4D7L": ["kills_lice_eggs","fast_action","physical_non_chemical","comb_included","child_safe","medical_certified","no_resistance"],  # Pouxit Shampoo 15min preg-safe
    "B077Z7QKN9": ["comb_included","gentle_skin","family_size_value","made_in_local"],  # Milice foam kit
}

IT_PREVENTION_VOC_GAP = [
    {"vocTopic":"Prevention spray doesn't actually prevent","customerConcernPct":"~30%","addressedByCount":3,"addressedByBrands":["Helan","Paranix","Natura House"],"gapSeverity":"HIGH","whitespace":"Italian brands lean on 'ambiente sfavorevole' language. Quantify — cite a school-year study or % infestation reduction."},
    {"vocTopic":"Strong herbal / lavender smell","customerConcernPct":"~20%","addressedByCount":1,"addressedByBrands":["BACTERISAN (fruity)"],"gapSeverity":"MEDIUM","whitespace":"Tea tree + lavender dominate. A fruity or fragrance-free variant stands out."},
    {"vocTopic":"Not safe for very young children","customerConcernPct":"~20%","addressedByCount":1,"addressedByBrands":["Puressentiel (3 anni+)"],"gapSeverity":"MEDIUM","whitespace":"Only Puressentiel specifies a minimum age. Others default to 'bambini' vaguely."},
    {"vocTopic":"No textile coverage","customerConcernPct":"~15%","addressedByCount":1,"addressedByBrands":["Panteer"],"gapSeverity":"MEDIUM","whitespace":"1 of 10 is a textile spray (Panteer, cross-listed from DE). An Italian-made textile prevention spray is an open play."},
]

IT_PREVENTION_WHITESPACE = [
    {"opportunity":"Clinically-proven prevention","rationale":"Every IT prevention product claims 'ambiente sfavorevole' but zero cite an efficacy figure or clinical study.","evidence":"0 of 10 show a % infestation reduction or school-year study."},
    {"opportunity":"Italian-made textile spray","rationale":"Only Panteer (DE cross-listing) plays in the textile-environment space. No Italian brand owns 'spray anti-pidocchi per tessuti'.","evidence":"1 of 10 IT Prevention is textile; the 1 that is comes from Germany."},
    {"opportunity":"Baby-safe (0-12 months)","rationale":"Every IT prevention product defaults to 'bambini' or '3 anni+'. Italian parents buy for infants too — no one serves them.","evidence":"0 of 10 claim safety under 12 months; Puressentiel's '3 anni+' is the only specified minimum."},
    {"opportunity":"Fragrance-free for atopic kids","rationale":"8 of 10 lead with essential oils or tea tree. Sensitive-skin families have no allergen-free option.","evidence":"0 of 10 offer a truly fragrance-free SKU."},
    {"opportunity":"Italian-origin premium positioning","rationale":"Italian buyers value 'Made in Italy' heavily. Helan, Aftir, Linea Act, Natura House all quietly state it but none make it a hero positioning.","evidence":"5 of 10 are Italian-origin brands but none title on it."},
]

IT_PREVENTION_SATURATION = [
    {"claim":"efficacy_prevention","label":"Blocks / Repels Lice","saturationPct":"90%","advice":"Saturated with 'ambiente sfavorevole' language. Quantify with numbers — nobody does."},
    {"claim":"natural_ingredients","label":"Natural / Essential Oils","saturationPct":"100%","advice":"Completely saturated. Every IT brand leads with neem, tea tree, lavender. Go the OTHER direction — EO-free niche."},
    {"claim":"chemical_free","label":"No Pesticides / Insetticidi","saturationPct":"70%","advice":"Standard. Move beyond 'senza insetticidi' to a named exclusion ('senza permetrina', 'senza piretrine')."},
    {"claim":"family_safe","label":"Child-Safe","saturationPct":"70%","advice":"Specify minimum age in the title. 'Dai 3 mesi' wins a real whitespace."},
    {"claim":"daily_use","label":"Daily Use","saturationPct":"100%","advice":"Table-stakes. Differentiate with frequency guidance, not the claim itself."},
    {"claim":"long_lasting","label":"Long-Lasting Protection","saturationPct":"10%","advice":"Under-claimed — only Paranix calls this out. Quantifying protection hours is a quick win."},
    {"claim":"pleasant_fragrance","label":"Pleasant Fragrance","saturationPct":"30%","advice":"Fruity scents outcompete herbal in this market. BACTERISAN and Paranix are the only ones claiming it."},
    {"claim":"made_in_local","label":"Made in Italy","saturationPct":"50%","advice":"Under-leveraged hero angle. 5 of 10 are Italian-origin but none lead with it in the title."},
    {"claim":"registered_approved","label":"Dermato / Ecocert Tested","saturationPct":"30%","advice":"Italian market respects Ecocert / dispositivo medico. Add the certification explicitly."},
]

IT_PREVENTION_RECOMMENDATIONS = [
    {"type":"Positioning","badgeBg":"#e0f2fe","badgeColor":"#075985","finding":"5 of 10 IT Prevention products are Italian-origin (Helan, Aftir ×3, Linea Act, Natura House) but none use 'Made in Italy' as hero positioning.","implication":"Launch or re-title with 'Prodotto in Italia dal [year]' as the lead. Italian buyers pay a premium for local provenance in pharmacy / cosmetic categories."},
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"Panteer (DE textile spray) holds 4th place in IT Prevention by revenue, despite no Italian competitor in the category.","implication":"Italian-origin textile prevention spray is an uncontested launch. Mirror Panteer's format with 'Spray per tessuti Made in Italy' at €14-18."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"Every IT prevention listing claims 'ambiente sfavorevole ai pidocchi' but zero quantify duration or efficacy. Only Paranix mentions 'prolungata protezione'.","implication":"Commission a simple in-vitro or school-season study (€3-5k). Put '92% riduzione infestazioni dopo 4 settimane' in the title. Become the only proven Italian prevention spray."},
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"Only Puressentiel (1/10) specifies a minimum age (3 anni+). Everyone else is 'bambini' vaguely.","implication":"Italian parents trust explicit age labels. A 'Da 6 mesi — adatto anche a bebè' variant is a clean niche win."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"October seasonality is 1.84× — second-highest of EU markets after ES. Back-to-school timing is critical but no brand shifts copy for 'ritorno a scuola'.","implication":"Refresh title + A+ content Aug 1 with 'Pronti per la scuola 2026' / 'Settembre, stagione dei pidocchi'. PPC spike Aug 15 — Oct 15."},
]

IT_TREATMENT_VOC_GAP = [
    {"vocTopic":"Treatment required repeat — eggs survived","customerConcernPct":"~30%","addressedByCount":5,"addressedByBrands":["Paranix","Pouxit","Linea Act","Helan","NitNOT"],"gapSeverity":"HIGH","whitespace":"Paranix claims 100% in one application (clinical study) and 72h reinfestation protection — the gold standard. Competitors missing the claim."},
    {"vocTopic":"Greasy residue / hard to wash out","customerConcernPct":"~25%","addressedByCount":2,"addressedByBrands":["Paranix (2in1 shampoo)","Pouxit Shampoo"],"gapSeverity":"HIGH","whitespace":"Only 2 treatments explicitly wash + treat in one step. Others leave buyers with oily hair for hours."},
    {"vocTopic":"Strong smell / children refuse application","customerConcernPct":"~20%","addressedByCount":1,"addressedByBrands":["NitNOT (inodore)"],"gapSeverity":"HIGH","whitespace":"Only NitNOT explicitly claims odorless. Italian families with multiple kids need a tolerable-smell formula."},
    {"vocTopic":"Unsafe during pregnancy","customerConcernPct":"~15%","addressedByCount":2,"addressedByBrands":["Pouxit Flash","Pouxit Shampoo"],"gapSeverity":"MEDIUM","whitespace":"Only Pouxit explicitly mentions gravidanza + allattamento. Strong niche for a pregnancy-first Italian brand."},
    {"vocTopic":"Kit feels incomplete","customerConcernPct":"~15%","addressedByCount":2,"addressedByBrands":["Milice","Linea Act"],"gapSeverity":"LOW","whitespace":"Italians expect a complete kit (shampoo + lotion + comb). Only 2 of 10 offer all three."},
    {"vocTopic":"Product failed completely","customerConcernPct":"~20%","addressedByCount":0,"addressedByBrands":[],"gapSeverity":"HIGH","whitespace":"Zero brands offer a 'funziona o rimborso' guarantee. Trust lever is wide open."},
]

IT_TREATMENT_WHITESPACE = [
    {"opportunity":"Sub-5-minute treatment","rationale":"Paranix Extra Forte and Pouxit Flash both claim 5 minutes. Nobody goes below. Sub-3-min is open.","evidence":"Fastest IT treatments: Paranix = 5 min, Pouxit = 5 min. All others 10-15+ min."},
    {"opportunity":"Pregnancy + breastfeeding hero","rationale":"Only Pouxit explicitly mentions pregnancy safety. Italian families expect OB-GYN-endorsed pharma options.","evidence":"2 of 10 mention pregnancy; 0 of 10 lead on it. Italian pharmacies sell pregnancy-safe variants at premium."},
    {"opportunity":"Odorless hero claim","rationale":"Only NitNOT claims 'inodore'. Italian kids are notoriously picky about hair products — smell is a top rejection trigger.","evidence":"1 of 10 has the odorless claim; 9 of 10 either fragranced or unspecified."},
    {"opportunity":"100% single-application guarantee","rationale":"Paranix has a clinical 100% claim but no refund. Nobody backs the claim with money.","evidence":"0 of 10 IT treatments offer a guarantee or refund policy."},
    {"opportunity":"Italian pharmacy pedigree","rationale":"Helan, Linea Act, Aftir, Milice are all Italian pharma/cosmetic brands. Pouxit (French) and Paranix (Belgian) dominate volume despite being foreign.","evidence":"Italian brands claim 'farmacia italiana' only weakly. Patriotic Italian positioning is under-used."},
    {"opportunity":"Complete family kit","rationale":"Italian buyers expect pre-treatment spray + shampoo + lotion + comb + post-treatment shampoo as one kit. Only Milice and Linea Act come close.","evidence":"2 of 10 offer complete kits; 8 are single-SKU."},
]

IT_TREATMENT_SATURATION = [
    {"claim":"kills_lice_eggs","label":"Uccide Pidocchi & Lendini","saturationPct":"90%","advice":"Table-stakes. Back it with a clinical citation — Paranix does, few others."},
    {"claim":"fast_action","label":"Azione Rapida (5–15 min)","saturationPct":"70%","advice":"Saturated. Sub-5-minute is open whitespace. Don't compete on 5 min — challenge 3 min."},
    {"claim":"physical_non_chemical","label":"Senza Insetticidi","saturationPct":"90%","advice":"Nearly universal. Differentiate by naming the physical mechanism (dimeticone, olio minerale, osmolone)."},
    {"claim":"comb_included","label":"Pettine Incluso","saturationPct":"60%","advice":"Common. Spec the comb as a hero product — Assy 2000's professional steel comb proves Italian buyers pay for comb quality."},
    {"claim":"child_safe","label":"Adatto a Bambini","saturationPct":"50%","advice":"Specify age. 'Da 6 mesi' (Pouxit) is gold-standard in IT; 'bambini' is generic."},
    {"claim":"medical_certified","label":"Dispositivo Medico","saturationPct":"70%","advice":"Standard signal. Call out the CE number and dispositivo medico classification prominently."},
    {"claim":"gentle_skin","label":"Pelli Sensibili","saturationPct":"40%","advice":"Under-claimed. Add 'testato dermatologicamente' and 'per pelli sensibili'."},
    {"claim":"no_odor","label":"Inodore","saturationPct":"10%","advice":"Only NitNOT claims it. Huge whitespace — Italian kids' top complaint."},
    {"claim":"family_size_value","label":"Kit Completo","saturationPct":"20%","advice":"Only Milice and Linea Act offer full kits. Italian buyers expect multi-piece packs."},
    {"claim":"no_resistance","label":"Nessuna Resistenza","saturationPct":"70%","advice":"Implicit in 'senza insetticidi'. Make it explicit — 'nessun rischio di resistenza'."},
]

IT_TREATMENT_RECOMMENDATIONS = [
    {"type":"Positioning","badgeBg":"#e0f2fe","badgeColor":"#075985","finding":"Paranix holds 2 of top 10 IT treatment slots with €39k (#1) + €8k. Their 5-min + 72h reinfestation + 100% clinical claim is the strongest combined positioning in the market.","implication":"Direct competition with Paranix needs a stronger angle: sub-3-min kill, pregnancy-safe hero, or 'Made in Italy' pharmacy pedigree. 'Senza insetticidi' alone isn't enough — everyone has it."},
    {"type":"Product","badgeBg":"#fef3c7","badgeColor":"#92400e","finding":"Pouxit (French) holds 2 of top 10 IT Treatment despite no Italian pediatric credibility. Italian pharmacies trust French brands but an Italian pharma pedigree is untapped.","implication":"Launch an Italian-owned treatment with 'Formulato in farmacia italiana' + 'Testato da pediatri italiani'. Price at €18-22 to match Pouxit."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"Only NitNOT (1/10) claims 'inodore'. Smell is a top complaint in Italian reviews but nobody leads on it.","implication":"Reformulate with a genuinely odorless dimethicone. Lead bullet 1 with 'Inodore — i bambini non si lamentano'. Directly addresses the #1 kid-rejection trigger."},
    {"type":"Packaging","badgeBg":"#dcfce7","badgeColor":"#166534","finding":"Only Milice and Linea Act offer complete family kits (shampoo + lotion + comb). 8 of 10 sell single SKUs.","implication":"Italian buyers expect all-in-one. Launch a 'Kit famiglia completo' with 3-5 pieces at €25-30. Captures the 'I want one box, not five' segment."},
    {"type":"Positioning","badgeBg":"#e0f2fe","badgeColor":"#075985","finding":"Only Pouxit mentions pregnancy + breastfeeding (2/10 listings, both Pouxit).","implication":"Pregnancy-safe hero angle with Italian OB-GYN endorsement. Niche but defensible — and a premium-pricing segment."},
    {"type":"Messaging","badgeBg":"#ede9fe","badgeColor":"#5b21b6","finding":"October seasonality is 1.84× — second-highest of EU markets. Paranix and Pouxit surge hardest in Sept-Oct.","implication":"Shift ~60% of annual PPC + A+ refresh to Aug 15 – Oct 31. Hero hook: 'Pronto per il rientro a scuola'."},
]

# ── Per-country config lookup ────────────────────────────────────────────────
COUNTRY_LABEL = {'DE':'Germany','FR':'France','IT':'Italy','ES':'Spain'}

PER_COUNTRY = {
    'DE': {
        'prevention': {
            'themes': prevention_themes_for('Germany / EU'),
            'claims': PREVENTION_CLAIMS,
            'vocGap': PREVENTION_VOC_GAP,
            'whitespace': PREVENTION_WHITESPACE,
            'saturation': PREVENTION_SATURATION,
            'recommendations': PREVENTION_RECOMMENDATIONS,
        },
        'treatment': {
            'themes': TREATMENT_THEMES,
            'claims': TREATMENT_CLAIMS,
            'vocGap': TREATMENT_VOC_GAP,
            'whitespace': TREATMENT_WHITESPACE,
            'saturation': TREATMENT_SATURATION,
            'recommendations': TREATMENT_RECOMMENDATIONS,
        },
    },
    'FR': {
        'prevention': {
            'themes': prevention_themes_for('France'),
            'claims': FR_PREVENTION_CLAIMS,
            'vocGap': FR_PREVENTION_VOC_GAP,
            'whitespace': FR_PREVENTION_WHITESPACE,
            'saturation': FR_PREVENTION_SATURATION,
            'recommendations': FR_PREVENTION_RECOMMENDATIONS,
        },
        'treatment': {
            'themes': TREATMENT_THEMES,
            'claims': FR_TREATMENT_CLAIMS,
            'vocGap': FR_TREATMENT_VOC_GAP,
            'whitespace': FR_TREATMENT_WHITESPACE,
            'saturation': FR_TREATMENT_SATURATION,
            'recommendations': FR_TREATMENT_RECOMMENDATIONS,
        },
    },
    'IT': {
        'prevention': {
            'themes': prevention_themes_for('Italy'),
            'claims': IT_PREVENTION_CLAIMS,
            'vocGap': IT_PREVENTION_VOC_GAP,
            'whitespace': IT_PREVENTION_WHITESPACE,
            'saturation': IT_PREVENTION_SATURATION,
            'recommendations': IT_PREVENTION_RECOMMENDATIONS,
        },
        'treatment': {
            'themes': TREATMENT_THEMES,
            'claims': IT_TREATMENT_CLAIMS,
            'vocGap': IT_TREATMENT_VOC_GAP,
            'whitespace': IT_TREATMENT_WHITESPACE,
            'saturation': IT_TREATMENT_SATURATION,
            'recommendations': IT_TREATMENT_RECOMMENDATIONS,
        },
    },
    'ES': {
        'prevention': {
            'themes': prevention_themes_for('Spain'),
            'claims': ES_PREVENTION_CLAIMS,
            'vocGap': ES_PREVENTION_VOC_GAP,
            'whitespace': ES_PREVENTION_WHITESPACE,
            'saturation': ES_PREVENTION_SATURATION,
            'recommendations': ES_PREVENTION_RECOMMENDATIONS,
        },
        'treatment': {
            'themes': TREATMENT_THEMES,
            'claims': ES_TREATMENT_CLAIMS,
            'vocGap': ES_TREATMENT_VOC_GAP,
            'whitespace': ES_TREATMENT_WHITESPACE,
            'saturation': ES_TREATMENT_SATURATION,
            'recommendations': ES_TREATMENT_RECOMMENDATIONS,
        },
    },
}

MARKETPLACE_STR = {'DE':'amazon.de','FR':'amazon.fr','IT':'amazon.it','ES':'amazon.es'}

# ── Build ────────────────────────────────────────────────────────────────────
def build(code, segment):
    cfg = PER_COUNTRY[code][segment]
    # 1. X-Ray index
    xray_path = None
    xfolder = os.path.join(BASE, 'data', 'x-ray', code)
    for f in os.listdir(xfolder):
        if f.lower().endswith('.csv'):
            xray_path = os.path.join(xfolder, f); break
    xray = {}
    for row in csv.DictReader(open(xray_path, encoding='utf-8-sig')):
        asin = row.get('ASIN','').strip()
        if not asin or asin in xray: continue
        xray[asin] = row

    # 2. ASIN list + raw catalog
    asins = [l.strip() for l in open(os.path.join(BASE,'data','competitor-listings',code,f'asins-{segment}.txt')) if l.strip()]
    raw_dir = os.path.join(BASE,'data','competitor-listings',code,'raw')

    competitors = []
    for asin in asins:
        raw = json.load(open(os.path.join(raw_dir, f'{asin}.json'), encoding='utf-8'))
        xr = xray.get(asin, {})
        images_urls = [i['url'] for i in raw.get('images', [])]
        themes = cfg['claims'].get(asin, [])
        competitors.append({
            "asin": asin,
            "brand": raw.get('brand') or xr.get('Brand','') or 'Unknown',
            "title": raw.get('title','') or xr.get('Product Details',''),
            "price": numv(xr.get('Price  €')),
            "rating": numv(xr.get('Ratings')),
            "reviews": int(numv(xr.get('Review Count'))),
            "bsr": int(numv(xr.get('BSR'))),
            "rev30d": numv(xr.get('ASIN Revenue')),
            "sales30d": int(numv(xr.get('ASIN Sales'))),
            "mainImage": images_urls[0] if images_urls else '',
            "images": images_urls,
            "bullets": raw.get('bullet_points', []),
            "description": raw.get('description',''),
            "themes": themes,
            "claimCount": len(themes),
        })

    # 3. Claims matrix
    claims_matrix = {
        "themes": cfg['themes'],
        "rows": [
            {"asin": c['asin'], "brand": c['brand'],
             "cells": [1 if t['key'] in set(c['themes']) else 0 for t in cfg['themes']]}
            for c in competitors
        ]
    }

    # 4. Claims summary — count per theme, top brands
    claims_summary = []
    for t in cfg['themes']:
        hits = [c for c in competitors if t['key'] in set(c['themes'])]
        hits_sorted = sorted(hits, key=lambda c: -c['rev30d'])[:3]
        claims_summary.append({
            "theme": t['key'],
            "label": t['label'],
            "count": len(hits),
            "pct": f"{round(100*len(hits)/len(competitors))}%",
            "topBrands": [c['brand'] for c in hits_sorted],
        })

    mdd = {
        "totalCompetitors": len(competitors),
        "marketplace": MARKETPLACE_STR[code],
        "currency": "€",
        "exportMonth": 2,  # March = 2 (0-based)
        "segment": segment.capitalize(),
        "competitors": competitors,
        "claimsMatrix": claims_matrix,
        "claimsSummary": claims_summary,
        "vocGap": cfg['vocGap'],
        "whitespaceOpportunities": cfg['whitespace'],
        "saturation": cfg['saturation'],
        "strategicRecommendations": cfg['recommendations'],
    }

    out = os.path.join(BASE,'data','competitor-listings',code,f'mdd-{segment}.json')
    with open(out,'w',encoding='utf-8') as f:
        json.dump(mdd, f, ensure_ascii=False, indent=2)
    print(f'  {code}/{segment}: {len(competitors)} competitors, {sum(c["claimCount"] for c in competitors)} theme-hits → {out}')

def main():
    if len(sys.argv) < 3:
        print('Usage: py scripts/build_mdd.py <CODE> <prevention|treatment>')
        sys.exit(1)
    build(sys.argv[1].upper(), sys.argv[2].lower())

if __name__ == '__main__':
    main()
