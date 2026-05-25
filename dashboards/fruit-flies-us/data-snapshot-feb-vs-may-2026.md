# Data snapshot comparison: Feb vs May 2026

> Notatka analityczna z porównania dwóch snapshotów X-Ray dla Fruit Flies — US dashboard.
> Zachowana żeby było jasne dlaczego dashboard zbudowany na Feb data nie odzwierciedla pełnie sytuacji rynku w maju.

**Created:** 2026-05-24

---

## TL;DR

Między 25 lutego 2026 a 24 maja 2026 nastąpił **~67% turnover** ASINów na pierwszych stronach search results dla fruit fly traps. Tylko **68 z 207 ASINów** ze starego snapshotu pojawia się w nowym. Główne przyczyny: **inne keywordy w search** (Feb = 1 keyword, May = 3 keywordy) + naturalna rotacja Amazon SERP + nadchodzący sezon fruit flies (lato).

---

## Co konkretnie zrobione w każdym snapshocie

### Old (dashboard live)
- **Plik:** `Data/x-ray/Fruit-Flies-US-new-merged-data.csv`
- **Date:** 2026-02-25 (3 miesiące temu)
- **Keywords:** prawdopodobnie tylko `fruit fly trap` (single search) — nie udokumentowane explicite
- **Unique ASINs:** 207
- **Segmentation:** ręcznie nadana w kolumnie `Type` (4 segmenty)

### New (dziś)
- **Plik:** `Data/x-ray/may/merged-may.csv` (post-merge) → `merged-may-segmented.csv` (z kolumną Segment)
- **Date:** 2026-05-24
- **Keywords użyte (3 osobne X-Ray exporty z H10):**
  1. `plug in fly trap`
  2. `flying insect trap`
  3. `fruit fly trap`
- **Raw rows:** 299 (3 pliki połączone)
- **Sponsored skipped (`($)` prefix):** 52
- **Unique ASINs po dedupe:** 210
- **Segmentation:** kombinacja
  - 68 ASINów: mapped from old file (ich segment dziedziczony)
  - 111 ASINów: auto-assigned do `Electric Traps` (heuristic regex w tytule: `plug[-\s]?in` / `UV` / `zapper` / `electric`)
  - 31 ASINów: nadal unassigned (czekają na ręczne przypisanie)

---

## Liczbowe porównanie

### Overlap ASINów

| Metric | Liczba |
|---|---:|
| Old unique ASINs | 207 |
| New unique ASINs | 210 |
| **Wspólne (overlap)** | **68** (32.9% z old) |
| **Zniknęły** (były w Feb, brak w May) | **139** (67.1% z old) |
| **Pojawiły się** (są w May, brak w Feb) | **142** (67.6% z new) |

### Segment distribution (po pełnej segmentacji)

| Segment | Old (Feb) | New (May) | Delta | Old % | New % |
|---|---:|---:|---:|---:|---:|
| Electric Traps | 86 | 138 | +52 | 41.5% | 65.7% |
| Sticky Traps | 74 | 20 | −54 | 35.7% | 9.5% |
| Lure | 40 | 18 | −22 | 19.3% | 8.6% |
| Passive attractor | 7 | 3 | −4 | 3.4% | 1.4% |
| (unassigned) | 0 | 31 | +31 | 0% | 14.8% |
| **TOTAL** | **207** | **210** | | 100% | 100% |

⚠️ New (May) Electric counter zawiera 111 auto-assigned heuristycznie (regex w tytule) — wymaga manualnej weryfikacji żeby uznać te liczby za w pełni rzetelne.

---

## Co tłumaczy tak dużą różnicę

### 1. Inny keyword set (główna przyczyna)

Feb: 1 keyword (likely `fruit fly trap`) = wąskie pokrycie głównie "fruit fly trap" produktów (mieszany electric/sticky/lure).

May: 3 keywordy = każdy keyword wciąga inną grupę produktów:
- `plug in fly trap` → mocno przeskewowane na Electric Traps (Zevo, Safer, etc.)
- `flying insect trap` → mix electric + bug zapper + flying-pest traps
- `fruit fly trap` → klasyczne fruit fly produkty (sticky + lure)

Wniosek: **65.7% Electric w May vs 41.5% Electric w Feb to NIE jest realny wzrost rynku electric — to artefakt różnego keyword setu** (jeden z 3 keywordów był wprost electric-specific).

### 2. Rotacja Amazon SERP

Amazon search wyniki naturalnie rotują w czasie (BSR fluctuates, sponsored slots się zmieniają, nowi sprzedawcy wchodzą). Nawet to samo zapytanie po 3 miesiącach pokazuje inne wyniki.

### 3. Sezonowość fruit flies

Fruit flies są problemem sezonowym (lato = peak owoców = peak much). Maj/czerwiec to początek high season:
- Nowi sprzedawcy wpychają nowe produkty na rynek przed peak
- BSR rośnie dla całej kategorii
- Reklamy się intensyfikują = sponsored pool większy

Z 52 sponsored w 3 plikach May (~17% raw rows) widać że Amazon Ads konkurencja jest agresywna.

### 4. New listings

142 ASINy które pojawiły się w May to mix:
- Nowi sprzedawcy (np. STEM, Pestie, Tihilgam, BietrunPro, Forhimn — wszyscy nowi dla naszej bazy)
- Stare brandy które wprowadziły nowe SKU (np. ZEVO nowe warianty)
- Refille i akcesoria które dla wcześniejszych searchów nie wpadły w ranking

---

## Implikacje dla dashboardu

1. **Dashboard pokazuje stan z Feb 2026** — nieaktualny o ~3 miesiące, przed sezonem.
2. **Segmentacja `Type` w starym pliku oparta o pojedynczy keyword** — może nie odzwierciedlać pełnej struktury rynku.
3. **Realny rozkład segmentów lepiej oceniać per-keyword** zamiast łączyć:
   - Per `plug in fly trap` → ~100% Electric (z definicji)
   - Per `fruit fly trap` → mix sticky/lure/electric (szeroka kategoria)
   - Per `flying insect trap` → mix electric + zapper
4. **Refresh dashboardu na May data** wymaga:
   - Dokończenia segmentacji 31 unassigned + weryfikacji 111 auto-assigned
   - Decyzji czy łączyć 3 keywordy w jeden dashboard, czy zrobić per-keyword view
   - Decyzji czy 12M sales calculations używać starego baselineu czy regenerować z świeżych sales-units CSV per ASIN

---

## Decision points (do twojego namysłu)

1. **Czy refreshować dashboard z May data?**
   - Pro: aktualne, przed-sezonowe insighty
   - Con: 67% turnover ASINów = praktycznie nowy dashboard (nie inkrementalny update)
2. **Czy ograniczyć analizę do core 68 ASINów (overlap)?**
   - Pro: można pokazać 3-month change (sales/BSR/reviews) dla tych samych produktów
   - Con: tracimy 142 nowych ASINów które definiują obecny rynek
3. **Czy zrobić osobny "Pre-Season Snapshot" view** na bazie May data?
   - Pro: zachowuje Feb data jako benchmark, dodaje May jako "what's hot now"
   - Con: dwa dashboardy = więcej do utrzymania
