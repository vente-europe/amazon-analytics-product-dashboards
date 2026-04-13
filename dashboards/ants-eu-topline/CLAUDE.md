> Living document — Update after every bug fix or new pattern found. No permission needed for additions. Ask before removing.

# Ants — EU Top Line (Topline Dashboard)

## Purpose

High-level KPI overview for the Ant Control category across 5 EU marketplaces (UK, DE, FR, ES, IT). Revenue and unit projections based on 30-day X-Ray data.

## Tech Stack

- Dashboard Hub (`/Console/`) — vanilla HTML + JS + Chart.js 4.4.4
- Fixed Topline template — no modular tabs
- Data rendered from `dashboard.json`

## Data Sources

| Source | Location | Notes |
|--------|----------|-------|
| X-Ray (30d) | `data/x-ray/` | Per-marketplace CSVs (UK: 61, DE: 42, FR: 63, IT: 23, ES: 31 ASINs) |

## Data Convention

- **Seasonality:** Flat ×12 multiplier (30-day × 12 = annual)
- **Currency:** EUR (€). GBP → EUR at ECB rate 1.195
- **Brand data:** Top 10 brands + Other, all markets combined

## Known Issues

_(none yet)_

## Self-Update Rule

Update this file after every bug fix, data pattern discovered, or configuration change.
