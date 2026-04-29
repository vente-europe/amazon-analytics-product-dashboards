"""
Klasyfikator segmentów dla dashboardu dermo-products (skóra atopowa / sucha / podrażniona).

ZASADA GŁÓWNA: produkt dostaje automatyczny segment (Cream / Wash / Oil) TYLKO jeśli:
  1. Opis listingu (tytuł + bullet points + description z SP-API) zawiera MOCNY
     sygnał niszy atopowej — czyli jedno z poniższych:
       • słowo kliniczne: eczema, neurodermitis, atopic, atopique, dermatitis
       • określenie "empfindlich/sensible/sensitive skin"
       • "dermatologisch / medical / hypoallergen"
       • znana linia produktowa atopowa (Atoderm, AtopiControl, Xemose, Lipikar,
         Exomega, Haut Ruhe, Sensiderm, AT4, Locobase Repair, Dexeryl itd.)
  2. Tytuł zawiera jednoznaczne słowo określające formę produktu
     (creme/lotion/baume → Cream; waschgel/gel douche → Wash; körperöl/huile corps → Oil)

Jeśli brak sygnału niszy LUB brak jasnej formy → "Check" (ręczna weryfikacja).
Twarde wykluczenia (pet / usta / włosy / SPF / anti-age / dezodoranty) → "Other".

DLACZEGO TO DZIAŁA W OBIE STRONY:
  - Masowe marki typu Nivea / Vaseline / Palmer's reklamują się jako "dry skin"
    ale nie celują w skórę atopową — brak sygnału niszy → Check, nie Cream.
  - Produkty niszowe bez słów klucza w tytule (np. "Cerat", "Baume") lądują w Check
    zamiast zostać niepoprawnie zaklasyfikowane.

Użycie:
    py scripts/classify_segments.py DE
    py scripts/classify_segments.py FR
    py scripts/classify_segments.py IT
    py scripts/classify_segments.py ES
"""
import csv, json, glob, os, sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# ── SYGNAŁY NISZY ATOPOWEJ ───────────────────────────────────────────────
# Lista słów, które muszą wystąpić w tytule/bullets/description żeby uznać
# produkt za kierowany do skóry atopowej (nie tylko "suchej"). Obejmuje terminy
# kliniczne we wszystkich 4 językach (DE/FR/IT/ES/EN) + nazwy znanych linii
# produktowych, które same w sobie są dowodem na niszę atopową.
NICHE_STRONG = [
    'atopisch','atopie','atopic','atopica','atopique','atopiques','atopic',
    'neurodermitis','eczema','ekzem','ekzeme','eczema','dermatitis','dermatite',
    'hautbarriere','hautschutzbarriere','lipidbarriere','barriere cutanee','lipidique',
    'hypoallergen','hypoallergenique','hipoalergenico','ipoallergenico','hypoallergenic',
    'dermatologisch','dermatologique','dermatologico','dermatologically',
    'medizinisch','medical','medico',
    'juckreiz','prurit','prurito','picor','itch',
    'hautirritation','gereizte haut','peau irritee','pelle irritata','piel irritada','irritated skin',
    'reizung','irritacion','irritazione',
    'empfindliche haut','peau sensible','pelle sensibile','piel sensible','sensitive skin',
    'peau atopique','pelle atopica','piel atopica','peau tres seche','piel muy seca',
    'pelle molto secca','sehr trockene haut','very dry skin',
    # known atopic product lines / brands
    'atopicontrol','atoderm','xemose','xeracalm','lipikar','exomega','cicabiafine',
    'sensiderm','haut ruhe','at4','locobase repair','sensitive pflege','dexeryl',
    'hydrolotio','allergika','eubos','phametra','dermoscent','dermocapillaire',
    'stelatopia','a-derma','topialyse','trixera','cold cream','cicaplast',
]

# ── SŁOWA FORMY: WASH (emulsja/żel/olejek do mycia) ─────────────────────
# Żele do mycia, syndety, mydła dermatologiczne, olejki pod prysznic.
# UWAGA: olejek pod prysznic ("shower oil", "huile de douche") to WASH, nie OIL —
# dlatego ta lista jest sprawdzana PRZED listą FORM_OIL w funkcji classify().
FORM_WASH = [
    'waschgel','duschol','duschgel','waschlotion','reinigungsol','dusch- und badeol',
    'dusch und badeol','wash gel','shower oil','shower gel','body wash','waschsyndet',
    'waschemulsion','waschmittel','gel lavant','gel douche','huile lavante','nettoyant',
    'syndet','savon','soin lavant','gel nettoyant','pain lavant','pain dermatologique',
    'detergente','bagno doccia','bagnoschiuma','bagno','doccia','olio detergente',
    'olio doccia','sapone','gel limpiador','gel bano','gel de bano','gel de ducha',
    'aceite limpiador','aceite ducha','jabon','limpiador',
    # also catch German with proper umlauts
    'waschol','reinigungsol','dusch- und badeol','dusch- & badeol','badeol',
]
# ── SŁOWA FORMY: OIL (olejek do ciała) ──────────────────────────────────
# Tylko prawdziwe olejki pielęgnacyjne do ciała (body oil, Pflegeöl, huile corps).
# Olejki pod prysznic są obsługiwane wyżej w FORM_WASH.
FORM_OIL = [
    'korperol','pflegeol','babyol','massageol','body oil','nachtol','hautol',
    'huile corps','huile corporelle','huile seche','huile soin','huile de soin','huile massage',
    'olio corpo','olio corporeo','olio secco','olio massaggio',
    'aceite corporal','aceite cuerpo','aceite seco','aceite masaje',
]
# ── SŁOWA FORMY: CREAM (krem / balsam / lotion) ────────────────────────
# Najszersza kategoria — kremy, balsamy, lotiony, maści, mleczka do ciała.
# To jest kategoria "fallback" — sprawdzana ostatnia, bo słowa typu "lotion"
# mogą się pojawić również w nazwach produktów do mycia.
FORM_CREAM = [
    'creme','crema','cream','lotion','balsam','baume','balsamo',
    'korpermilch','korperlotion','salbe','pommade','pomata','pomada',
    'gel-creme','pflegecreme','hautcreme','intensivcreme',
    'feuchtigkeitscreme','handcreme','gesichtscreme','akutcreme','korperemulsion',
    'emulsion','emulsion','emulsione','korpermilk','body milk','leche corporal',
    'latte corpo','lait corps','lait corporel','leche','latte',
]

# ── WYKLUCZENIA TWARDE (trafiają do "Other") ───────────────────────────
# Produkty, które nawet jeśli mają w liście SP-API sygnał "atopowy", są poza
# zakresem dashboardu (dla zwierząt, do ust, do włosów, przeciwsłoneczne itd.).
# Sprawdzane NAJPIERW w tytule — jeśli trafią, klasyfikacja się kończy.
EXCLUDE = [
    ('hundeshampoo','pet'),('fur hunde','pet'),('for dogs','pet'),('dogs and cats','pet'),
    ('pour chien','pet'),('pour chat','pet'),('per cani','pet'),('para perros','pet'),
    ('pferde','pet'),('equine','pet'),('chien','pet'),
    ('lippen-balsam','lip'),('lip balm','lip'),('baume levres','lip'),('stick levres','lip'),
    ('labbra','lip'),('labios','lip'),('levres','lip'),
    ('kopfhaut','scalp'),('shampoo','hair'),('shampooing','hair'),('haarpflege','hair'),
    ('cheveux','hair'),('capelli','hair'),('cabello','hair'),('scalp','hair'),
    ('sonnenschutz','sunscreen'),('sunscreen','sunscreen'),('solaire','sunscreen'),
    ('solar','sunscreen'),('lsf','sunscreen'),('spf ','sunscreen'),('spf50','sunscreen'),
    ('anti-age','anti-age'),('anti-ride','anti-age'),('anti-rides','anti-age'),
    ('anti age','anti-age'),('rughe','anti-age'),('arrugas','anti-age'),
    ('deodorant','deodorant'),('desodorante','deodorant'),('deo ','deodorant'),
    ('bicarbonate','other'),
]

# ── HELPER: normalizacja tekstu ────────────────────────────────────────
# Usuwa znaki diakrytyczne (umlauty, akcenty) żeby porównania działały niezależnie
# od wariantu pisowni. Przykład: "crème" i "creme" są traktowane jak to samo słowo.
def text_lower(s):
    return (s or '').lower().replace('ö','o').replace('ü','u').replace('ä','a').replace('ß','ss')\
        .replace('é','e').replace('è','e').replace('ê','e').replace('à','a').replace('â','a')\
        .replace('î','i').replace('ô','o').replace('û','u').replace('ç','c').replace('ñ','n')\
        .replace('á','a').replace('í','i').replace('ó','o').replace('ú','u')

# ── GŁÓWNA FUNKCJA KLASYFIKACYJNA ──────────────────────────────────────
# Wejście: słownik JSON z danymi SP-API (title, bullet_points, description, brand).
# Wyjście: (segment, reason) — segment to jeden z: Cream, Wash, Oil, Check, Other.
#
# KROKI:
#   1) Sprawdź wykluczenia twarde (zwierzęta/usta/włosy/SPF) → Other
#   2) Wykryj formę produktu patrząc na tytuł — kolejność: Wash → Oil → Cream
#      (żeby "huile de douche" poszło do Wash, nie Oil)
#   3) Sprawdź sygnał niszy atopowej w pełnym tekście listingu
#   4) Decyzja:
#      - brak sygnału niszy → Check (podejrzenie produktu masowego typu Nivea)
#      - sygnał jest, ale forma nieznana → Check (niejednoznaczny tytuł)
#      - sygnał + forma → auto-przypisanie do segmentu
def classify(d):
    title_raw = (d.get('title') or '')
    title = text_lower(title_raw)
    bullets = text_lower(' '.join(d.get('bullet_points') or []))
    desc = text_lower(d.get('description') or '')
    full = title + ' ' + bullets + ' ' + desc

    # Krok 1: wykluczenia twarde (sprawdzamy tylko tytuł — musi być wprost)
    for pat, reason in EXCLUDE:
        if pat in title:
            return ('Other', reason)

    # Krok 2: wykrywanie formy (Wash wygrywa nad Oil — shower oil = Wash!)
    form = None
    for t in FORM_WASH:
        if t in title:
            form = 'Wash'; break
    if not form:
        for t in FORM_OIL:
            if t in title:
                form = 'Oil'; break
    if not form:
        for t in FORM_CREAM:
            if t in title:
                form = 'Cream'; break

    # Krok 3: sygnał niszy atopowej — sprawdzamy CAŁY tekst (title+bullets+description)
    has_niche = any(n in full for n in NICHE_STRONG)

    # Krok 4: finalna decyzja
    if not has_niche:
        # Produkt może wyglądać jak dermo-kosmetyk, ale nie ma w opisie żadnego
        # sygnału atopowego — to jest typowy case "Nivea pielęgnacja suchej skóry".
        # Nie klasyfikujemy automatycznie, tylko flagujemy do weryfikacji.
        return ('Check', 'no niche signal')
    if form is None:
        # Nisza OK, ale tytuł nie zdradza formy (np. "Lipikar AP+" bez słowa creme).
        return ('Check', 'niche OK form unclear')
    return (form, 'ok')

# ── ORCHESTRATOR ───────────────────────────────────────────────────────
# 1. Wczytuje wszystkie pliki JSON z SP-API dla danego kraju
# 2. Uruchamia classify() na każdym produkcie
# 3. Zapisuje wyniki do kolumny Segment w scalonym pliku X-Ray
# 4. Drukuje podsumowanie (ile Cream/Wash/Oil/Check/Other)
def main():
    if len(sys.argv) < 2:
        print('Usage: py scripts/classify_segments.py {DE|FR|IT|ES}')
        sys.exit(1)
    code = sys.argv[1].upper()
    raw_dir = os.path.join(BASE, 'data', 'competitor-listings', code, 'raw')
    csv_path = os.path.join(BASE, 'data', 'x-ray', code, f'Dermo-Products-{code}.csv')
    if not os.path.isdir(raw_dir):
        print(f'No raw folder: {raw_dir}'); sys.exit(1)
    if not os.path.isfile(csv_path):
        print(f'No merged CSV: {csv_path}'); sys.exit(1)

    results = {}
    for fp in sorted(glob.glob(os.path.join(raw_dir, '*.json'))):
        d = json.load(open(fp, encoding='utf-8'))
        asin = d.get('asin','')
        seg, reason = classify(d)
        results[asin] = (seg, reason, (d.get('brand','') or '')[:22], (d.get('title') or '')[:90])

    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    hdr = rows[0]
    a_i = hdr.index('ASIN')
    s_i = hdr.index('Segment')
    filled = 0
    for row in rows[1:]:
        asin = (row[a_i] or '').strip()
        if asin in results:
            row[s_i] = results[asin][0]
            filled += 1
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        csv.writer(f).writerows(rows)

    cnt = Counter(r[0] for r in results.values())
    print(f'{code} segment counts:')
    for k in ['Cream','Wash','Oil','Check','Other']:
        print(f'  {k}: {cnt.get(k,0)}')
    print(f'  TOTAL classified: {sum(cnt.values())}')
    print(f'  Filled in CSV: {filled} / {len(rows)-1} rows')

if __name__ == '__main__':
    main()
