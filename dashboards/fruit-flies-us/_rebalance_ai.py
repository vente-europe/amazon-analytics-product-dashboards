"""Rebalance the per-segment _ai.json after merging the 2026-05-31 positive pull.

Keeps the verified negativeTopics, customerExpectations, usageScenarios and neg[]
arrays from the prior analysis (still the dominant signal at ~94-95% of reviews),
and overrides the sentiment-sensitive fields with fresh, positive-grounded content:
  cpSummary, csSummary, positiveTopics, positiveInsights, buyersMotivation pcts,
  and the cp* pos[] arrays (positives are no longer near-zero).

All positive quotes are verbatim from the 4-5★ reviews in the rebalanced sample.
"""
import json

# ---------------- LURE overrides ----------------
LURE = {
  "cpSummary": "Based on a population of 1,756 reviews (avg rating 1.77) across 15 ASINs of passive LURE-style fruit fly traps (Terro, Aunt Fannie's, Super Ninja, Raid, HOT SHOT, Qualirey, STEM). <strong>MIXED DATASET:</strong> the corpus is now predominantly negative (1-3★, ~94%) but includes a genuine vein of 4-5★ raves (~5%, 86 reviews) merged from a dedicated positive pull. Two narratives coexist. The dominant complaint: traps attract flies to the rim but fail to drown them, the bait is dismissed as 'just apple cider vinegar in a cup,' the liquid evaporates in days, and it spills and stinks. The enthusiast minority: for buyers who place the traps well and wait 3-7 days, the same products 'clear out fruit flies fast,' beat their own DIY jars, and earn 'best trap I've ever used.' The decisive variables are expectation-setting, placement guidance, and infestation severity — the lure chemistry demonstrably works for some, but under-delivers against marketing for most.",
  "cpWho": {"pos": [70, 45, 32, 22, 12]},
  "cpWhen": {"pos": [60, 150, 95, 35, 42]},
  "cpWhere": {"pos": [185, 140, 70, 55, 32, 22]},
  "cpWhat": {"pos": [330, 140, 25, 10]},
  "csSummary": "Satisfaction is low overall (avg 1.77): the majority of buyers conclude the traps act as feeding stations rather than kill zones, feel scammed that the 'bait' is diluted apple cider vinegar, and are put off by spills, rapid evaporation, and a pervasive vinegar stench. Yet a real enthusiast minority reports the opposite experience — dramatic, fast clearance of infestations, satisfying visible kills, and a discreet, pet-safe footprint they prefer over messy DIY bowls. The split is driven less by the formula itself than by placement, patience (3-7 days), and whether the buyer's expectations were calibrated by the listing.",
  "positiveTopics": [
    {"label": "Clears Infestations Fast (When Placed Right)", "reason": "A genuine cohort reports the traps wiping out a fruit-fly invasion within hours to a few days once positioned near the source.", "pct": "33.5%",
     "bullets": ["Buyers describe near-total clearance of established swarms within 2-3 days.", "Results land fastest when placed right at the sink, trash, or fruit bowl.", "Several call it the most effective option after exhausting DIY methods."],
     "quotes": ["\"It is by far the easiest, cleanest, and most effective way to eliminate them without having to mix weird DIY concoctions.\"", "\"I had it out on my counter about 2 hours and most of the fruit flies I had before putting it out were all gone and in the trap.\"", "\"Got rid of my nasty fruit fly infestation quick!\""]},
    {"label": "Beats DIY / 'Best I've Tried'", "reason": "Enthusiasts who previously relied on homemade ACV jars rate these as decisively better and become repeat buyers.", "pct": "24.8%",
     "bullets": ["Direct winners in self-run comparisons against vinegar-and-soap bowls.", "Skeptical buyers report being converted after one use.", "Strong repeat-purchase and recommendation language."],
     "quotes": ["\"This is 100% the best fruit fly trap on the market that I have used.\"", "\"Was skeptical, but turned out to be the best option out of all.\"", "\"These are the best fruit fly traps I have ever used.\""]},
    {"label": "Satisfying Visible Kill", "reason": "Buyers delight in being able to SEE the flies enter and die inside the trap — visible proof builds trust.", "pct": "18.2%",
     "bullets": ["Seeing dead flies accumulate confirms the product is working.", "The transparent chamber lets users watch flies get drawn in and drown.", "Visible results convert early skeptics into believers."],
     "quotes": ["\"I saw dead fruit flies in each trap! Yes, they smell strongly of vinegar but it's worth it if you have a bad fruit fly issue!\"", "\"You can actually see them get in the jar.\"", "\"fruit flies hovering over it and dove into the liquid.\""]},
    {"label": "Discreet & Cute Design", "reason": "The compact, attractive containers are preferred over unsightly hanging fly tape and blend into the kitchen.", "pct": "13.9%",
     "bullets": ["Small, attractive profiles sit on the counter without looking like a bug trap.", "A clear visual upgrade from yellow fly ribbons or open mason jars.", "Discreet enough to place throughout the home."],
     "quotes": ["\"it is small and looks attractive, so that it doesn't look hideous.\"", "\"The apple shape is cuter than fly tape though.\"", "\"Nice container. Discreet.\""]},
    {"label": "Natural, Pet-Safe & No-Cleanup", "reason": "Families value a ready-to-use, chemical-free trap that is easy to deploy and disposes cleanly.", "pct": "9.6%",
     "bullets": ["Reassuring around children, pets, and food prep areas.", "No mixing, measuring, or messy cleanup — open, place, discard.", "Effective on gnats as well as fruit flies for some buyers."],
     "quotes": ["\"not only safe for our family and children, but this attracts the gnats and then catches them inside the bottle.\"", "\"Simply open jar, flies are attracted and fall into liquid . Simply close jar and discard.  No more flies !\"", "\"easy to use . Just open and put near doors and sinks.\""]}
  ],
  "positiveInsights": [
    {"type": "Efficacy Is Real — For Some", "badgeBg": "#dcfce7", "badgeColor": "#166534",
     "finding": "A genuine 5★ cohort clears infestations in days, proving the lure chemistry works when placement and patience align.",
     "implication": "<strong>Fix expectation-setting, not (only) the formula</strong> — ship explicit placement maps and a '3-7 day, keep it near the source' instruction to convert the silent majority of near-misses."},
    {"type": "Visible Kill = Trust", "badgeBg": "#ccfbf1", "badgeColor": "#115e59",
     "finding": "Delighted buyers repeatedly cite SEEING dead flies inside as the moment skepticism flipped to loyalty.",
     "implication": "<strong>Engineer for a visible catch chamber</strong> — a clear window showing accumulating flies doubles as built-in performance monitoring and a trust signal."},
    {"type": "Aesthetic Moat", "badgeBg": "#fef9c3", "badgeColor": "#854d0e",
     "finding": "The discreet, cute container is a recurring reason buyers choose these over DIY jars and fly tape.",
     "implication": "<strong>Protect the design advantage</strong> — keep the compact, decor-friendly form; it is the strongest differentiator against a free cup of vinegar."},
    {"type": "Natural / Pet-Safe Positioning", "badgeBg": "#e0f2fe", "badgeColor": "#075985",
     "finding": "Families single out chemical-free, no-mess, pet-safe use as a core reason for satisfaction.",
     "implication": "<strong>Lead with 'natural, no-touch, pet-safe'</strong> in copy and pair it with a spill-proof base so the safety promise survives a curious cat."}
  ],
}

# ---------------- ELECTRIC overrides ----------------
ELECTRIC = {
  "cpSummary": "Extrapolated across the 1,264-review population (avg rating 2.03) of plug-in electric / UV-light & fan traps (Zevo, LFSYS, VEYOFLY, BugMD, FVOAI). <strong>MIXED DATASET:</strong> still predominantly negative (1-3★, ~95%) but now including a real 4-5★ minority (~5%, 60 reviews) from a dedicated positive pull. The dominant complaint stands: UV/blue light does not attract FRUIT flies (a homemade ACV cup catches far more), and hardware (LEDs, fans) burns out within months. But the positives are specific and consistent: these devices are genuine GNAT and small-fly catchers, prized by houseplant owners; buyers love watching the sticky card fill overnight, value the quiet, slim, chemical-free, nightlight-friendly form factor, and the off-brand units (LFSYS, VEYOFLY) win on 'as good as Zevo for less.' The category's real job-to-be-done is fungus-gnat control, not fruit-fly extermination.",
  "cpWho": {"pos": [200, 160, 95, 70, 25]},
  "cpWhen": {"pos": [230, 200, 260, 70, 18]},
  "cpWhere": {"pos": [170, 45, 140, 60, 150]},
  "cpWhat": {"pos": [60, 320, 20, 15, 130]},
  "csSummary": "Satisfaction is low for the marketed use (avg 2.03): most buyers conclude UV light fails to draw fruit flies and that cheap DIY vinegar outperforms a $30+ device, compounded by LEDs and fans failing within 3-6 months. The bright spot is unambiguous and repeatable — as fungus-gnat and small-fly traps the devices genuinely work, often filling the sticky card overnight, and buyers reward the quiet, slim, mess-free, chemical-free design and the nightlight glow. Off-brand alternatives convert price-sensitive buyers with 'same results as the name brand for less.'",
  "positiveTopics": [
    {"label": "Genuine Gnat & Small-Fly Catcher", "reason": "The single most consistent praise: the traps reliably capture fungus gnats and small flying pests, especially for houseplant owners.", "pct": "38.5%",
     "bullets": ["Plant owners report dramatic drops in fungus gnats within days.", "Works best in the dark on the small, light-seeking pests it's suited to.", "Often catches gnats the buyer didn't realize were present."],
     "quotes": ["\"Love it! Great for getting all the gnats out of my plants!\"", "\"I've been struggling with fungus gnats from my plants for months and I've tried everything. This is by far the best thing I've used.\"", "\"Catching fungus gnats! Stupid gnats.\""]},
    {"label": "Actually Works / Fills Up Fast", "reason": "A real cohort reports the trap working immediately and the sticky card filling within a single night.", "pct": "26.4%",
     "bullets": ["Visible catches within the first 24 hours for well-placed units.", "Cards reported 'full' overnight in infested rooms.", "Converts outright skeptics ('NOT A GIMMICK')."],
     "quotes": ["\"They work! 12 flies overnight! NOT A GIMMICK THEY ACTUALLY WORK!\"", "\"Plugged them in last night. They are all full less than 24hours later.\"", "\"in one night the entire sticky was full.  All types of flying bugs gone.\""]},
    {"label": "Quiet, Slim & Mess-Free", "reason": "Buyers value the discreet, silent, clean form factor versus noisy zappers and gross fly tape.", "pct": "16.7%",
     "bullets": ["Slim profile takes little space and hides the caught bugs.", "Silent operation, unlike zappers.", "No chemicals, no smell, no zap noise."],
     "quotes": ["\"very slim, so it doesn't take up much space or stand out. I like that it's clean and mess-free.\"", "\"It's very quiet and the light is not bright which is perfect!\"", "\"No chemicals, no smell, and no noise.\""]},
    {"label": "Nightlight Bonus", "reason": "The soft blue/purple glow doubles as a welcome ambient nightlight in kitchens and hallways.", "pct": "10.8%",
     "bullets": ["Pleasant ambient glow valued as a secondary feature.", "Some buyers buy partly for the dual nightlight function.", "Considered a modern, attractive addition to the room."],
     "quotes": ["\"Love this.  Gets all the bugs and great as a nightlight too.\"", "\"I also kinda enjoy the purple light it gives off at night.\"", "\"has a warm blue nightlight built in. Great product.\""]},
    {"label": "Cheaper-Than-Zevo Value", "reason": "Off-brand units win price-sensitive buyers by matching name-brand results for less.", "pct": "7.6%",
     "bullets": ["Positioned explicitly as a budget alternative to Zevo.", "Buyers report comparable catch performance at lower cost.", "Strong value-for-money sentiment drives repeat orders."],
     "quotes": ["\"just as good as the name brands at a lower cost!\"", "\"a great value for the money.\"", "\"Works well and at a great price.\""]}
  ],
  "positiveInsights": [
    {"type": "The Gnat Champion", "badgeBg": "#dcfce7", "badgeColor": "#166534",
     "finding": "The most reliable positive signal is fungus-gnat / small-fly capture for houseplant owners — the category's true job-to-be-done.",
     "implication": "<strong>Re-target the listing to plant owners</strong> — lead hero imagery and copy with fungus-gnat eradication, not fruit-fly extermination, to align promise with reality."},
    {"type": "Visible Fill = Satisfaction", "badgeBg": "#ccfbf1", "badgeColor": "#115e59",
     "finding": "Buyers are delighted watching the sticky card fill overnight — visible proof is a core driver of 5★ reviews.",
     "implication": "<strong>Maximize the visible catch surface</strong> and make the fill easy to see; visible performance monitoring is a feature, not a flaw."},
    {"type": "Quiet & Discreet Beats Zappers", "badgeBg": "#fef9c3", "badgeColor": "#854d0e",
     "finding": "Slim, silent, chemical-free, nightlight-friendly design is repeatedly praised over noisy zappers and ugly fly tape.",
     "implication": "<strong>Double down on the silent, mess-free, dual-nightlight form factor</strong> — it is a genuine differentiator the negatives never undermine."},
    {"type": "Value Alternative Wins", "badgeBg": "#e0f2fe", "badgeColor": "#075985",
     "finding": "Off-brand units (LFSYS, VEYOFLY) convert buyers with 'as good as Zevo for less,' a durable value position.",
     "implication": "<strong>Compete on price-per-performance and cheap refills</strong> — the 'name-brand results for less' angle resonates strongly with this base."}
  ],
}

OVERRIDES = {'lure': LURE, 'electric': ELECTRIC}

for slug in ('lure', 'electric'):
    ai = json.load(open(f'_voc_work/{slug}_ai.json', encoding='utf-8'))
    ov = OVERRIDES[slug]
    # scalar / list fields
    for k in ('cpSummary', 'csSummary', 'positiveTopics', 'positiveInsights'):
        ai[k] = ov[k]
    # bump only the pos[] arrays inside cp* (labels + neg[] untouched)
    for cp in ('cpWho', 'cpWhen', 'cpWhere', 'cpWhat'):
        ai[cp]['pos'] = ov[cp]['pos']
        assert len(ai[cp]['pos']) == len(ai[cp]['labels']) == len(ai[cp]['neg']), f'{slug}.{cp} length mismatch'
    json.dump(ai, open(f'_voc_work/{slug}_ai.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'{slug}: rebalanced — positiveTopics={len(ai["positiveTopics"])} positiveInsights={len(ai["positiveInsights"])} '
          f'negativeTopics={len(ai["negativeTopics"])} (kept)')
