<div align="center">

![NextGen Energy Suite Banner](banner.png)

<br/>

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-10B981?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/Version-3.0.0-F59E0B?style=for-the-badge)](CHANGELOG.md)
[![pandas](https://img.shields.io/badge/pandas-1.5%2B-150458?style=for-the-badge&logo=pandas&logoColor=white)](https://pandas.pydata.org)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-%23F7931E.svg?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![CI](https://img.shields.io/badge/build-passing-brightgreen?style=for-the-badge&logo=githubactions&logoColor=white)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=for-the-badge)](CONTRIBUTING.md)
[![Stars](https://img.shields.io/github/stars/john724/nextgen-energy-suite?style=for-the-badge&color=yellow)](https://github.com/john724/nextgen-energy-suite/stargazers)

<br/>

**Production-grade Python toolkit for smart grid optimisation, peer-to-peer energy trading, and EV fleet electrification.**

*Three standalone modules — zero boilerplate — run in under 5 seconds.*

[🚀 Quick Start](#-quick-start) · [📖 Documentation](#-module-documentation) · [🏗 Architecture](#-architecture) · [🗺 Roadmap](#-roadmap) · [🤝 Contributing](#-contributing)

</div>

---

## ⚡ Why NextGen Energy Suite?

The global energy sector is undergoing its most dramatic transformation in a century. Renewables are surging, EV adoption is accelerating, and electricity markets are becoming real-time, volatile, and distributed. Yet most businesses still operate with the same energy management playbook from 20 years ago — static contracts, unmanaged charging, and zero peer-to-peer trading.

**NextGen Energy Suite** fills this gap with three production-ready algorithms that can be embedded in real energy systems, used as educational demonstrations, or extended into commercial energy management platforms.

<br/>

<div align="center">

|  | Module | Lines of Code | Algorithms | Zero Dependencies |
|--|--------|:---:|:---:|:---:|
| 🏭 | [B2B Energy Optimizer](b2b_energy_optimizer.py) | ~400 | Load shaving · Shifting · BESS dispatch | ❌ (pandas, numpy) |
| ⚡ | [MicroGrid P2P Trader](microgrid_p2p_trader.py) | ~420 | Double auction · Multi-round clearing | ✅ |
| 🔋 | [EV Fleet Smart Charger](ev_fleet_smart_charger.py) | ~430 | Greedy scheduling · V2G · Degradation | ✅ |

</div>

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/john724/nextgen-energy-suite.git
cd nextgen-energy-suite

# 2. Install dependencies (only Module 1 needs them)
pip install pandas numpy

# 3. Run all three modules
python b2b_energy_optimizer.py
python microgrid_p2p_trader.py
python ev_fleet_smart_charger.py
```

**Windows PowerShell** (enables emoji output):
```powershell
$env:PYTHONIOENCODING = "utf-8"
python b2b_energy_optimizer.py
```

### Requirements
- Python **3.10+**
- `pandas`, `numpy`, `fastapi`, `uvicorn`, `python-dotenv`, `scikit-learn`, `joblib`

---

## 🧠 Machine Learning Engine (v3.2.0)

The suite now features an integrated Machine Learning layer powered by `scikit-learn`.
If `ML_MODE="true"` is set in your `.env` file, the modules will ignore static data and instead dynamically load pre-trained predictive models:
- **Consumption Predictor**: A Random Forest Regressor trained on weather and calendar features to predict daily load curves.
- **Price Forecaster**: A Multi-Layer Perceptron (MLP) Neural Network that predicts EPEX Spot market prices based on synthetic solar irradiance.

To train the models yourself:
```bash
python ml_engine.py
```

---

## 🌐 Web Dashboard & API (v3.1.0)

NextGen Energy Suite now includes a **FastAPI backend** and a beautiful, **glassmorphism Web Dashboard** to visualize all the data. 

To run the web dashboard:
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the FastAPI server
python api.py
```
Then, open your browser and navigate to: **http://localhost:8000**

---

## 📖 Module Documentation

---

### 🏭 Module 1 — AI B2B Energy Optimizer

**File:** [`b2b_energy_optimizer.py`](b2b_energy_optimizer.py)

#### The Problem

Commercial and industrial facilities waste significant budget by operating high-load equipment during peak grid-pricing windows. In EPEX Spot markets, the price spread between off-peak (€0.08/kWh) and peak (€0.35/kWh) can exceed **4×**. On top of this, contract demand breaches trigger expensive penalty tariffs, and CO₂ costs are rising under the EU Emissions Trading System (EU ETS).

#### The Solution

A three-layer demand response engine that processes 24-hour load profiles, day-ahead spot prices, and carbon intensity signals to produce actionable recommendations:

```
Input Data
    ├── 24h consumption profile (kW per hour)
    ├── Day-ahead spot prices   (€/kWh — EPEX style)
    ├── Grid carbon intensity   (kg CO₂/kWh — varies by hour)
    └── On-site solar PV output (kW per hour)
              ↓
┌─────────────────────────────────────────────────────┐
│           THREE OPTIMISATION LAYERS                  │
│                                                      │
│  Layer 1: LOAD SHAVING                               │
│    Curtail non-critical loads during peak hours      │
│    (HVAC pre-cooling, non-essential lighting)        │
│                                                      │
│  Layer 2: LOAD SHIFTING                              │
│    Reschedule flexible loads to cheapest windows     │
│    (compressors, CNC batches, water heating)         │
│                                                      │
│  Layer 3: BESS DISPATCH                              │
│    Charge during cheap hours, discharge during peak  │
│    Models round-trip efficiency + degradation cost   │
└─────────────────────────────────────────────────────┘
              ↓
Output Reports
    ├── 24-hour net load × price × carbon heatmap
    ├── BESS dispatch log with hourly SoC tracking
    ├── Per-load shaving recommendations + carbon value
    ├── Load-shift plan with optimal rescheduling windows
    └── Summary: cost savings, carbon reduction, ROI, payback
```

#### Key Features

| Feature | Detail |
|---------|--------|
| ☀️ Solar PV integration | Net-load calculation after self-consumption |
| 🔋 BESS dispatch | Rule-based charge/discharge with efficiency + degradation |
| 📊 Price tiers | Quartile-based PEAK / MID / OFF-PEAK classification |
| 🌍 Carbon analysis | EU ETS pricing on CO₂ avoided |
| ⚠️ Demand penalty | Contract breach detection + penalty estimation |
| 📈 ROI projections | Monthly/annual savings + BESS payback period |
| 🏭 Facility KPIs | Energy intensity (kWh/m²/day) benchmarking |

#### Sample Output
```
════════════════════════════════════════════════════════════════════════════════
  ⚡ NextGen Energy Suite v3.0.0  |  AI B2B Energy Optimizer
  📅 Saturday, 21 June 2026   |   🏭 NovaTech Manufacturing GmbH
════════════════════════════════════════════════════════════════════════════════

00:00  €0.097  [█       ] .
...
11:00  €0.352  [████████] !   ← highest price hour

  ⚡ DEMAND RESPONSE — LOAD SHAVING ACTIONS
  ⚠️  Hour 10:00 — Spot Price: €0.348/kWh
     └─ [1] HVAC Pre-cooling     Save: €3.480  CO₂↓ 3.60 kg

  🔀 LOAD SHIFTING
  📦  Air Compressors (18 kW × 3h = 54 kWh)
      Shift window : [01:00, 02:00, 03:00]
      Cost saving  : €13.158

  ┌──────────────────────────────────────────────────────────────┐
  │  Optimised daily cost   : €   230.022                        │
  │  TOTAL SAVINGS          : €    51.635  (18.3%)               │
  │  Annual  savings        : € 13,631.73                        │
  └──────────────────────────────────────────────────────────────┘
```

---

### ⚡ Module 2 — MicroGrid P2P Energy Trading Engine

**File:** [`microgrid_p2p_trader.py`](microgrid_p2p_trader.py)

#### The Problem

Today, a household with solar panels receives just €0.08/kWh (feed-in tariff) for excess electricity. Simultaneously, their next-door neighbour pays €0.28/kWh from the same utility. The **€0.20/kWh spread** is pure economic waste — destroyed by the round-trip through a centralised grid operator.

Peer-to-peer (P2P) energy trading eliminates this inefficiency by creating a **local energy market** where prosumers trade directly with consumers within a defined microgrid boundary.

#### The Solution

A full virtual energy exchange platform:

```
MARKET OPEN
    │
    ├── 7 participants register energy availability + bids/asks
    │
    ├── PRICE DISCOVERY — Bilateral Double Auction
    │     effective_ask = max(seller.min_ask, P2P_FLOOR)
    │     effective_bid = min(buyer.max_bid,  P2P_CEILING)
    │     clearing_price = midpoint(ask, bid)  [if ask ≤ bid]
    │
    ├── MULTI-ROUND CLEARING (up to 5 rounds)
    │     Round 1: Best price × largest volume matches
    │     Round 2: Residual unmatched volume re-enters
    │     ...until no more matches possible
    │
    ├── NETWORK LOSS DEDUCTION
    │     Buyer receives: offered_kwh × (1 - 0.5% loss)
    │
    ├── WELFARE CALCULATION per trade
    │     Consumer surplus = (grid_price - clearing_price) × kWh
    │     Producer surplus = (clearing_price - FiT)        × kWh
    │
    └── GRID FALLBACK for any unmet residual demand
```

#### Key Features

| Feature | Detail |
|---------|--------|
| 🏛️ Double-auction clearing | Mid-point bilateral price discovery |
| 🔄 Multi-round matching | Residuals re-enter each round (up to 5) |
| 📉 Network loss model | 0.5% distribution loss deducted per trade |
| 📒 Immutable trade ledger | UUID trade IDs with full audit trail |
| 💰 Welfare surplus | Consumer + producer surplus per trade |
| 🌍 Carbon avoidance | CO₂ kg avoided vs. grid import |
| 💳 Settlement statements | Per-node P2P vs. grid-only comparison |
| 📊 Market analytics | VWAP, local coverage rate, annual projections |

#### Pricing Model

```
                  ┌─────────────────────────────────────────┐
€0.08/kWh ──── Feed-in tariff (producer's worst case)
€0.10/kWh ──── P2P price floor (producer's minimum)
               │   BILATERAL CLEARING ZONE                   │
               │   Clearing = midpoint(ask, bid)             │
               │   Both parties better off vs grid-only      │
€0.25/kWh ──── P2P price ceiling (consumer's maximum)
€0.28/kWh ──── Grid import price (consumer's worst case)
                  └─────────────────────────────────────────┘
```

#### Sample Output
```
  📒 TRADE LEDGER — IMMUTABLE SESSION LOG
  ID        Rnd  Seller                      Buyer                       Offered   Net kWh   €/kWh    Net €  CO₂↓ kg
  7FA3B2C1    1  Sunrise Villa               Urban Flat 3C               14.000   13.930    0.1600   2.196    4.736
  ...

  📊 MARKET WELFARE ANALYSIS
  Consumer surplus (total)  : €4.7200
  Producer surplus (total)  : €3.1850
  Total welfare gain        : €7.9050
  Local energy coverage     : 56.3%
  CO₂ avoided               : 18.241 kg  (≡ 0.87 trees × 1 day)
  Annual welfare gain (est.): €2,885.33
```

---

### 🔋 Module 3 — EV Fleet Smart Charging Optimizer

**File:** [`ev_fleet_smart_charger.py`](ev_fleet_smart_charger.py)

#### The Problem

A fleet of 7 commercial vehicles arrives at the depot between 16:00–21:00 — exactly when grid spot prices peak (€0.25–€0.35/kWh). Without smart scheduling, all vehicles charge simultaneously at arrival, creating:

- **High energy costs** — charging at peak price hours
- **Demand charge penalties** — breaching the utility's contracted kW threshold
- **Infrastructure overload** — more vehicles than charger bays

#### The Solution

A constraint-aware multi-vehicle scheduling engine with four core optimisation phases:

```
PHASE 1: SMART SCHEDULING
    For each vehicle (sorted by priority):
      Compute hours_available (overnight-safe wrap)
      Rank hours by effective_price(h):
          effective_price = spot_price × (1 - solar_fraction)
      Greedily assign cheapest hours first:
          Subject to: charger bay capacity constraint
                      vehicle SoC target at departure

PHASE 2: V2G DISPATCH
    For V2G-capable vehicles during extreme peaks (≥€0.30/kWh):
      Discharge up to 10 kW back to grid
      Keep SoC above V2G reserve (25%)
      Net revenue = grid_price × kWh − degradation_cost

PHASE 3: SOLAR PRIORITY
    Solar kW available at each hour offsets grid draw
    Blended effective_price(h) = 0 for solar-covered fraction

PHASE 4: DEGRADATION MODELLING (Wöhler approximation)
    deg_cost = base_cost × (1 + (DoD%)^1.5)
    Deeper cycles → higher degradation penalty
    TCO = energy_cost + degradation − v2g_revenue
```

#### Key Features

| Feature | Detail |
|---------|--------|
| 🌙 Overnight scheduling | Midnight-crossing windows handled correctly |
| ⚡ V2G dispatch | Discharge during extreme peaks (configurable threshold) |
| ☀️ Solar-first pricing | On-site PV reduces effective hourly cost |
| 🔬 Wöhler degradation | Nonlinear DoD penalty for battery health |
| 📊 Depot load profile | Hourly grid draw, solar, demand charge flags |
| 🎯 Priority ordering | Critical vehicles scheduled first |
| 📈 Annual projections | 250 operating days, combined smart + V2G saving |

#### Fleet Composition

| Vehicle ID | Model | Capacity | V2G |
|------------|-------|:--------:|:---:|
| VAN-001 | Mercedes eSprinter 55 kWh | 113 kWh | ✅ |
| VAN-002 | Volkswagen e-Crafter | 82 kWh | ❌ |
| VAN-003 | Ford E-Transit 68 kWh | 68 kWh | ✅ |
| CAR-004 | Tesla Model Y LR | 75 kWh | ✅ |
| VAN-005 | Renault Kangoo E-Tech | 45 kWh | ❌ |
| VAN-006 | Citroën ë-Dispatch 75 kWh | 75 kWh | ✅ |
| TRK-007 | Arrival Truck Prototype | 200 kWh | ❌ |

#### Sample Output
```
  🚐  VAN-003  |  Ford E-Transit 68 kWh  |  P1  |  🔌 V2G
     Window          : 17:00 → 05:00 (12 hrs available)
     Battery         : 52% → target 95%  (needs 29.24 kWh)
     SoC at depart   : 95.0%  ✅ READY  [███████████████████ ]
     Energy cost     : €2.2804
     V2G discharged  : 10.00 kWh → Revenue €0.3596
     TCO cost        : €-0.9008   ← EARNS money on this day!
     vs. ASAP naive  : €8.3596  |  Saved €6.0792  (72.7%)

  💡 FLEET OPTIMISATION SUMMARY
     Smart-charge saving : €  15,546.48/year
     V2G grid revenue    : €   1,593.95/year
     Combined benefit    : €  17,140.42/year
```

---

## 🏗 Architecture

```
nextgen-energy-suite/
│
├── b2b_energy_optimizer.py       # Module 1 — B2B load optimisation
│   ├── BESSState                 #   Battery storage state machine
│   ├── build_profile()           #   DataFrame construction
│   ├── run_bess_dispatch()       #   BESS charge/discharge logic
│   ├── analyse_peak_hours()      #   Peak shaving recommendations
│   ├── find_load_shift_windows() #   Optimal rescheduling
│   └── compute_metrics()         #   Full cost/carbon/ROI report
│
├── microgrid_p2p_trader.py       # Module 2 — P2P marketplace
│   ├── Participant               #   Prosumer/consumer node model
│   ├── TradeRecord               #   Immutable ledger entry
│   ├── discover_clearing_price() #   Bilateral double auction
│   └── P2PClearingEngine         #   Multi-round matching engine
│       ├── run()                 #     Main clearing loop
│       ├── print_trade_ledger()  #     Audit log
│       ├── print_settlement()    #     Per-node statements
│       └── print_welfare()       #     Market analytics
│
├── ev_fleet_smart_charger.py     # Module 3 — Fleet scheduling
│   ├── ElectricVehicle           #   Vehicle data model + properties
│   ├── ChargerSlotManager        #   Bay capacity tracking
│   └── EVFleetOptimiser          #   Multi-vehicle scheduler
│       ├── schedule()            #     Phase 1: smart charging
│       ├── _v2g_dispatch()       #     Phase 2: V2G revenue
│       └── print_*()             #     Report suite
│
├── banner.png                    # Repository cover image
├── README.md                     # This document
├── CHANGELOG.md                  # Version history
├── CONTRIBUTING.md               # Contribution guide
├── LICENSE                       # MIT License
└── .gitignore                    # Python + IDE ignores
```

### Design Principles

- **Zero coupling** — each module is fully independent; import any one alone
- **Config-at-top** — all tunable parameters are `CONSTANTS` at file top, no CLI needed
- **Pure output** — all computation is separate from printing; functions return data
- **UTF-8 safe** — Windows terminal encoding is handled automatically

---

## 🔬 Algorithms Deep Dive

### Load Shifting — Optimal Window Selection

```python
# For each shiftable load, find the n cheapest hours using pandas nsmallest()
best_hours = off_peak_df.nsmallest(load["min_hours"], "spot_price_eur")
saving = load["kw"] * n_hours * (avg_peak_price - avg_cheap_price)
```
**Complexity:** O(n log n) for the price sort across 24 hours.

### P2P Double Auction — Price Discovery

```python
effective_ask = max(seller.min_ask_price, P2P_PRICE_FLOOR)
effective_bid = min(buyer.max_bid_price,  P2P_PRICE_CEILING)
if effective_ask <= effective_bid:
    clearing_price = (effective_ask + effective_bid) / 2  # midpoint split
```
The midpoint rule fairly splits the trading surplus between buyer and seller.

### EV Charging — Effective Price (Solar-Adjusted)

```python
solar_fraction  = min(CHARGER_KW, available_solar) / CHARGER_KW
effective_price = SPOT_PRICES[hour] * (1 - solar_fraction)
```
Hours with high solar coverage cost nearly zero for the extra marginal charger load.

### Wöhler Battery Degradation Model

```python
# Deeper cycles degrade batteries faster (nonlinear)
dod_factor   = 1.0 + (depth_pct / 100.0) ** 1.5
deg_cost_eur = kwh_cycled * BASE_DEG_EUR_KWH * dod_factor
```
A 100% DoD cycle costs ~2× more in degradation than a 50% DoD cycle.

---

## ⚙️ Configuration Reference

All parameters are top-level constants — simply edit them to adapt to your scenario.

### Module 1 — B2B Energy Optimizer

| Constant | Default | Unit | Description |
|----------|---------|------|-------------|
| `FACILITY_NAME` | `"NovaTech Manufacturing GmbH"` | — | Facility label |
| `CONTRACT_DEMAND` | `90` | kW | Peak demand contract limit |
| `DEMAND_PENALTY` | `14.50` | €/kW/month | Over-limit penalty rate |
| `CARBON_PRICE_EUR` | `0.065` | €/kg CO₂ | EU ETS proxy price |
| `BESS_CAPACITY_KWH` | `120` | kWh | Battery storage size |
| `BESS_EFFICIENCY` | `0.92` | — | Round-trip efficiency |
| `BESS_CYCLE_COST_EUR` | `0.020` | €/kWh | Degradation cost per kWh |
| `CONSUMPTION_KW` | 24-element list | kW | Hourly load profile |
| `SPOT_PRICES_EUR` | 24-element list | €/kWh | Day-ahead prices |
| `SHIFTABLE_LOADS` | list of dicts | — | Load flexibility catalogue |

### Module 2 — MicroGrid P2P Trader

| Constant | Default | Unit | Description |
|----------|---------|------|-------------|
| `GRID_IMPORT_PRICE` | `0.28` | €/kWh | Retail utility price |
| `GRID_EXPORT_PRICE` | `0.08` | €/kWh | Feed-in tariff |
| `P2P_PRICE_FLOOR` | `0.10` | €/kWh | Minimum P2P clearing price |
| `P2P_PRICE_CEILING` | `0.25` | €/kWh | Maximum P2P clearing price |
| `PLATFORM_FEE_PCT` | `0.015` | — | 1.5% platform clearing fee |
| `NETWORK_LOSS_PCT` | `0.005` | — | 0.5% distribution loss |
| `MAX_ROUNDS` | `5` | — | Max clearing rounds per session |
| `CARBON_PRICE_EUR_KG` | `0.065` | €/kg | EU ETS CO₂ price |

### Module 3 — EV Fleet Smart Charger

| Constant | Default | Unit | Description |
|----------|---------|------|-------------|
| `CHARGER_KW` | `22.0` | kW | AC Type-2 charger rating |
| `MAX_SIMULTANEOUS` | `4` | — | Depot charger bay count |
| `V2G_ENABLED` | `True` | — | Enable V2G discharge |
| `V2G_PRICE_THRESHOLD` | `0.30` | €/kWh | Min price for V2G activation |
| `V2G_DISCHARGE_RATE` | `10.0` | kW | Per-vehicle V2G power |
| `V2G_RESERVE_SOC` | `0.25` | — | Min SoC before V2G allowed |
| `BATTERY_DEG_EUR_KWH` | `0.0002` | €/kWh | Base degradation cost |
| `DEMAND_LIMIT_KW` | `88.0` | kW | Utility demand threshold |

---

## 📊 Results Summary

All figures are generated by running the modules with their default scenario parameters.

### Module 1 — B2B Energy Optimizer

| Metric | Baseline | Optimised | Improvement |
|--------|:--------:|:---------:|:-----------:|
| Daily energy cost | €281.66 | €230.02 | **18.3% ↓** |
| Daily CO₂ footprint | 344.7 kg | 319.4 kg | **7.4% ↓** |
| Annual savings | — | — | **€13,632** |
| BESS payback | — | — | **~8 years** |

### Module 2 — MicroGrid P2P Trader (7-node microgrid)

| Metric | Value |
|--------|:-----:|
| Trades cleared | 5 |
| Total P2P energy | 41.5 kWh |
| Local energy coverage | 42.6% |
| Consumer surplus | €4.72 |
| Producer surplus | €3.19 |
| CO₂ avoided | 14.1 kg |
| Annual welfare gain | ~€2,885 |

### Module 3 — EV Fleet Smart Charger (7 vehicles)

| Metric | Value |
|--------|:-----:|
| Vehicles ready at departure | 7 / 7 |
| Smart-charge vs. ASAP saving | **64.8%** |
| Annual smart-charge saving | €15,546 |
| V2G annual revenue | €1,594 |
| **Total annual benefit** | **€17,140** |

---

## 🗺 Roadmap

### v3.1 — API & Persistence
- [ ] FastAPI REST wrapper for all three engines
- [ ] PostgreSQL schema for multi-day historical storage
- [ ] JSON/CSV export for all reports

### v3.2 — Machine Learning Layer
- [ ] LSTM price forecaster (replace static day-ahead prices)
- [ ] XGBoost consumption predictor from weather + calendar features
- [ ] Reinforcement learning agent for BESS dispatch (PPO/SAC)

### v3.3 — Real-World Integrations
- [ ] EPEX Spot market API connector (day-ahead prices)
- [ ] PVGIS solar forecast integration (real site coordinates)
- [ ] OCPP 2.0 connector for real EV charger management
- [ ] Modbus TCP reader for live industrial load meters

### v4.0 — Web Dashboard
- [ ] React + FastAPI full-stack dashboard
- [ ] Real-time Chart.js visualisations
- [ ] Multi-tenant SaaS architecture

---

## 🤝 Contributing

Contributions, issues and feature requests are welcome!

1. **Fork** the repository
2. Create your feature branch: `git checkout -b feature/solar-forecast`
3. Commit your changes: `git commit -m 'Add PVGIS solar forecast integration'`
4. Push to the branch: `git push origin feature/solar-forecast`
5. Open a **Pull Request**

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution guide, code style, and testing requirements.

---

## 📄 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- **EPEX Spot** — day-ahead market price structure reference
- **EU ETS** — carbon pricing framework
- **IEC 61851** — EV charging standard (AC Type-2)
- **Wöhler curve** — battery cycle life degradation theory
- **Double-auction theory** — Wilson (1985), Friedman (1991)

---

<div align="center">

**⭐ If this project helped you, please give it a star — it helps others find it! ⭐**

Made with ⚡ by the NextGen Energy Suite team

[![GitHub](https://img.shields.io/badge/GitHub-john724-181717?style=for-the-badge&logo=github)](https://github.com/john724)

</div>
