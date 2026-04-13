> Living document — Update after every bug fix or new pattern found. No permission needed for additions. Ask before removing.

# Fruit Flies — International (Topline Dashboard)

## Purpose

Multi-marketplace comparison for Fruit Fly Traps across 6 EU markets (DE, UK, FR, IT, ES, NL). Includes segment breakdown (Lure, Sticky, Electric, Fruit-Bait, Other) with revenue and unit heatmaps.

## Tech Stack

- Dashboard Hub (`/Console/`) — vanilla HTML + JS + Chart.js 4.4.4
- Fixed Topline template — no modular tabs
- Data rendered from `dashboard.json`

## Data Sources

| Source | Location | Notes |
|--------|----------|-------|
| X-Ray (30d) | `data/x-ray/` | 6 marketplace CSVs |

## Data Convention

- **Seasonality:** Custom ×21 multiplier (peak season Jun–Aug at 4×, rest at 1×). Total = 5 + (3×4) + 4 = 21
- **Currency:** EUR (€). GBP → EUR at ECB rate 1.195
- **Segments:** Lure, Sticky, Electric, Fruit-Bait, Other — with per-market revenue/unit heatmaps

## Known Issues

_(none yet)_

## Self-Update Rule

Update this file after every bug fix, data pattern discovered, or configuration change.
