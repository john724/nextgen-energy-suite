# Changelog

All notable changes to **NextGen Energy Suite** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [3.0.0] — 2026-06-27

### 🚀 Major Release — Complete Rewrite

#### Module 1 — AI B2B Energy Optimizer
- **Added** Battery Energy Storage System (BESS) dispatch layer (charge cheap, discharge peak)
- **Added** On-site solar PV net-load calculation and self-consumption tracking
- **Added** EU ETS carbon cost pricing on CO₂ saved
- **Added** Contract demand breach detection with penalty estimation
- **Added** BESS payback period ROI calculation
- **Added** Energy intensity KPI (kWh/m²/day)
- **Added** ASCII sparkline price chart in terminal output
- **Added** Per-load carbon value in shaving recommendations
- **Improved** Load shift planner now includes carbon saving alongside cost saving
- **Fixed** Price tier classification now correctly uses quartile boundaries

#### Module 2 — MicroGrid P2P Trading Engine
- **Added** Multi-round clearing (up to 5 rounds; residuals re-enter each round)
- **Added** Network distribution loss model (0.5% per trade)
- **Added** Consumer surplus and producer surplus calculation per trade
- **Added** Welfare analysis section (total community gain)
- **Added** Carbon value captured (EU ETS proxy per trade)
- **Added** 7th microgrid participant (Community Hall G7)
- **Added** Participant location metadata field
- **Added** Annual welfare projection (365-day extrapolation)
- **Improved** Seller/buyer ranking now uses effective_ask/bid with corridor clamping
- **Fixed** Round-robin matching now correctly stops when no further deals are possible

#### Module 3 — EV Fleet Smart Charging Optimizer
- **Added** Vehicle-to-Grid (V2G) dispatch for capable vehicles
- **Added** Wöhler-curve battery degradation approximation (nonlinear DoD penalty)
- **Added** 7th vehicle: Arrival Truck Prototype (200 kWh)
- **Added** V2G revenue reported per-vehicle and in fleet summary
- **Added** Per-vehicle carbon footprint tracking
- **Added** Depot load profile includes CO₂/h column
- **Added** SoC progress bar in terminal output (█ visual)
- **Improved** Solar-adjusted effective_price correctly handles per-charger solar offset
- **Fixed** Overnight `hours_available` wraps midnight correctly (arrival > departure)

#### Repository
- **Added** `banner.png` — cover image for GitHub
- **Added** `CHANGELOG.md` — this file
- **Added** `CONTRIBUTING.md` — contribution guidelines
- **Added** `LICENSE` — MIT License
- **Updated** `README.md` — complete rewrite with badges, architecture, algorithm deep-dives

---

## [2.0.0] — 2026-06-21

### Module 1 — B2B Energy Optimizer
- **Added** Demand-exceeded flag for contract limit monitoring
- **Added** Monthly and annual savings projections
- **Added** Load shaving per-hour grouped display

### Module 2 — MicroGrid P2P Trader
- **Added** UUID-based trade IDs for ledger entries
- **Added** Grid fallback settlement for unmatched demand
- **Added** Platform fee split between buyer and seller

### Module 3 — EV Fleet Smart Charger
- **Added** Solar offset in effective price calculation
- **Added** Battery degradation cost tracking
- **Added** Naive (ASAP) cost baseline comparison
- **Fixed** Overnight charging window (midnight wrap-around)

---

## [1.0.0] — 2026-06-21 (initial)

- Basic consumption profile analysis (Module 1)
- Simple P2P matching without auction (Module 2)
- Single-vehicle price-sort scheduling (Module 3)
