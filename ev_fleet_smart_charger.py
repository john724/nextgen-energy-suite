"""
================================================================================
  NextGen Energy Suite  ⚡  v3.0
  Module 3 — EV Fleet Smart Charging Optimizer
  ─────────────────────────────────────────────────────────────────────────────
  Problem  : Commercial EV fleets (logistics, taxis, delivery) plug in
             immediately after shifts—exactly when grid prices peak.
             Unmanaged charging risks demand charge penalties and strains
             depot infrastructure.

  Solution : A constraint-aware multi-vehicle scheduling engine that:
               1. SMART SCHEDULE   — assigns cheapest hours per vehicle
                  subject to hard departure/SoC/charger capacity constraints
               2. V2G DISPATCH     — models Vehicle-to-Grid discharge during
                  extreme peak hours to generate grid revenue
               3. SOLAR PRIORITY   — routes on-site solar to charging at
                  near-zero marginal cost
               4. BATTERY SoH      — tracks per-vehicle degradation with a
                  Wöhler-curve approximation
               5. DEMAND CHARGE    — flags and penalises depot hours that
                  breach the utility demand charge threshold

  Algorithms   : Constrained greedy · V2G heuristic · Priority queue
  Dependencies : none (pure Python stdlib)
  Python       : 3.10+
  Run          : python ev_fleet_smart_charger.py
================================================================================
"""

import sys
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import os
import ml_engine

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VERSION = "3.0.0"

# ═══════════════════════════════════════════════════════════════════════════════
#  DEPOT CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DEPOT_NAME           = "NextGen Logistics Depot — Athens Hub"
CHARGER_KW           = 22.0       # kW per AC Type-2 bay
MAX_SIMULTANEOUS     = 4          # maximum concurrent charging bays
BATTERY_DEG_EUR_KWH  = 0.0002    # €/kWh cycled (cell degradation amortisation)
DEMAND_LIMIT_KW      = 88.0       # kW — utility demand charge threshold
DEMAND_CHARGE_EUR_KW = 12.0       # €/kW/month over limit
V2G_ENABLED          = True       # allow Vehicle-to-Grid discharge
V2G_RESERVE_SOC      = 0.25       # minimum SoC before V2G can activate
V2G_PRICE_THRESHOLD  = 0.30       # €/kWh — grid price must exceed this for V2G
V2G_DISCHARGE_RATE   = 10.0       # kW — V2G discharge rate per vehicle

# 24-hour day-ahead spot prices (€/kWh)
SPOT_PRICES: dict[int, float] = {
     0: 0.097,  1: 0.091,  2: 0.081,  3: 0.077,  4: 0.108,  5: 0.146,
     6: 0.217,  7: 0.274,  8: 0.299,  9: 0.318, 10: 0.345, 11: 0.350,
    12: 0.316, 13: 0.296, 14: 0.278, 15: 0.261, 16: 0.249, 17: 0.275,
    18: 0.319, 19: 0.298, 20: 0.219, 21: 0.178, 22: 0.140, 23: 0.116,
}

if os.getenv("ML_MODE", "false").lower() == "true" and ml_engine.ML_AVAILABLE:
    try:
        _, _ml_prices = ml_engine.generate_tomorrow_forecast()
        for h in range(24):
            SPOT_PRICES[h] = _ml_prices[h]
    except Exception as e:
        print(f"⚠️ ML forecast failed, falling back to static data: {e}")

# On-site solar PV generation (kW per hour)
SOLAR_KW: dict[int, float] = {
     0: 0,  1: 0,  2: 0,  3: 0,  4: 0,  5: 0,
     6: 3,  7: 7,  8: 14,  9: 20, 10: 26, 11: 30,
    12: 32, 13: 30, 14: 26, 15: 20, 16: 12,  17: 6,
    18: 2,  19: 0,  20: 0,  21: 0,  22: 0,  23: 0,
}

# Grid CO₂ intensity by hour (kg CO₂/kWh)
CARBON_INTENSITY: dict[int, float] = {
     0: 0.28,  1: 0.27,  2: 0.25,  3: 0.24,  4: 0.26,  5: 0.30,
     6: 0.38,  7: 0.41,  8: 0.40,  9: 0.38, 10: 0.36, 11: 0.34,
    12: 0.33, 13: 0.32, 14: 0.31, 15: 0.30, 16: 0.29, 17: 0.31,
    18: 0.35, 19: 0.37, 20: 0.34, 21: 0.30, 22: 0.28, 23: 0.27,
}


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ElectricVehicle:
    """One commercial EV in the managed fleet."""
    vehicle_id:       str
    model:            str
    battery_cap_kwh:  float    # nominal usable capacity
    soc_current_pct:  float    # state of charge at plug-in (0–100)
    soc_target_pct:   float    # required SoC at departure (0–100)
    arrival_hour:     int      # hour plugged in
    departure_hour:   int      # hard departure deadline
    priority:         int      # 1 = highest (dispatched first by scheduler)
    v2g_capable:      bool = True   # whether vehicle supports V2G

    # Computed by scheduler
    scheduled_hours:  list[int]   = field(default_factory=list)
    v2g_hours:        list[int]   = field(default_factory=list)
    total_kwh:        float = 0.0
    grid_kwh:         float = 0.0
    solar_kwh:        float = 0.0
    v2g_kwh:          float = 0.0
    energy_cost_eur:  float = 0.0
    v2g_revenue_eur:  float = 0.0
    degradation_eur:  float = 0.0
    carbon_kg:        float = 0.0

    # ── Computed properties ─────────────────────────────────────────────────

    @property
    def energy_needed_kwh(self) -> float:
        return max(0.0, (self.soc_target_pct - self.soc_current_pct) / 100.0
                        * self.battery_cap_kwh)

    @property
    def hours_available(self) -> list[int]:
        """Overnight-safe availability window."""
        if self.arrival_hour < self.departure_hour:
            return list(range(self.arrival_hour, self.departure_hour))
        else:
            return list(range(self.arrival_hour, 24)) + list(range(0, self.departure_hour))

    @property
    def soc_after_kwh(self) -> float:
        """SoC% after all scheduled charging minus V2G discharge."""
        net_kwh  = self.total_kwh - self.v2g_kwh
        gain_pct = net_kwh / self.battery_cap_kwh * 100 if self.battery_cap_kwh else 0
        return min(100.0, self.soc_current_pct + gain_pct)

    @property
    def is_ready(self) -> bool:
        return self.soc_after_kwh >= self.soc_target_pct - 0.5   # ±0.5% tolerance

    @property
    def tco_cost_eur(self) -> float:
        """Total cost of ownership: energy + degradation - V2G revenue."""
        return self.energy_cost_eur + self.degradation_eur - self.v2g_revenue_eur

    @property
    def charging_window_h(self) -> int:
        return len(self.hours_available)

    # ── Wöhler-curve degradation approximation ──────────────────────────────

    def degradation_cycles(self, kwh: float, depth_pct: float) -> float:
        """
        Simplified Wöhler approximation: deeper cycles → more degradation.
        Returns degradation cost (€) for this kwh at given DoD.
        """
        base_cost = kwh * BATTERY_DEG_EUR_KWH
        dod_factor = 1.0 + (depth_pct / 100.0) ** 1.5   # nonlinear depth penalty
        return base_cost * dod_factor


# ═══════════════════════════════════════════════════════════════════════════════
#  CHARGER SLOT MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class ChargerSlotManager:
    """Tracks how many vehicles use each charger slot each hour."""

    def __init__(self):
        self._slots: dict[int, int] = {h: 0 for h in range(24)}

    def is_available(self, hour: int) -> bool:
        return self._slots.get(hour, 0) < MAX_SIMULTANEOUS

    def assign(self, hour: int):
        self._slots[hour] = self._slots.get(hour, 0) + 1

    def load_kw(self, hour: int) -> float:
        return self._slots.get(hour, 0) * CHARGER_KW

    def total_vehicles_at(self, hour: int) -> int:
        return self._slots.get(hour, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  FLEET OPTIMISER
# ═══════════════════════════════════════════════════════════════════════════════

class EVFleetOptimiser:
    """
    Multi-vehicle charging scheduler with:
      • Priority ordering
      • Solar-first cost weighting
      • V2G discharge during extreme peaks
      • Wöhler degradation model
      • Demand charge monitoring
    """

    def __init__(self, fleet: list[ElectricVehicle]):
        self.fleet  = sorted(fleet, key=lambda v: v.priority)
        self.slots  = ChargerSlotManager()

    def _effective_price(self, hour: int) -> float:
        """Blended €/kWh accounting for on-site solar offset."""
        solar_kw       = SOLAR_KW.get(hour, 0.0)
        existing_draw  = self.slots.load_kw(hour)
        avail_solar    = max(0.0, solar_kw - existing_draw)
        solar_fraction = min(CHARGER_KW, avail_solar) / CHARGER_KW
        grid_fraction  = 1.0 - solar_fraction
        return SPOT_PRICES[hour] * grid_fraction   # solar has zero marginal cost

    def _v2g_should_activate(self, hour: int) -> bool:
        return (V2G_ENABLED and SPOT_PRICES.get(hour, 0) >= V2G_PRICE_THRESHOLD)

    def schedule(self):
        """Run the full optimisation pass for all vehicles."""
        # ── Phase 1: Charge scheduling ────────────────────────────────────────
        for ev in self.fleet:
            needed = ev.energy_needed_kwh
            window = ev.hours_available

            if not window:
                continue

            ranked = sorted(window, key=lambda h: self._effective_price(h))

            for hour in ranked:
                if needed <= 0.001:
                    break
                if not self.slots.is_available(hour):
                    continue

                solar_kw   = SOLAR_KW.get(hour, 0.0)
                load_now   = self.slots.load_kw(hour)
                avail_sun  = max(0.0, solar_kw - load_now)
                solar_this = min(CHARGER_KW, avail_sun)
                kwh_this   = min(CHARGER_KW, needed)
                solar_kwh  = min(solar_this, kwh_this)
                grid_kwh   = kwh_this - solar_kwh

                # Depth of discharge for Wöhler model
                dod = (kwh_this / ev.battery_cap_kwh * 100) if ev.battery_cap_kwh else 0

                ev.scheduled_hours.append(hour)
                ev.total_kwh      += kwh_this
                ev.solar_kwh      += solar_kwh
                ev.grid_kwh       += grid_kwh
                ev.energy_cost_eur+= grid_kwh * SPOT_PRICES[hour]
                ev.degradation_eur+= ev.degradation_cycles(kwh_this, dod)
                ev.carbon_kg      += grid_kwh * CARBON_INTENSITY.get(hour, 0.34)

                needed -= kwh_this
                self.slots.assign(hour)

        # ── Phase 2: V2G discharge during extreme peaks ───────────────────────
        if V2G_ENABLED:
            for ev in self.fleet:
                if not ev.v2g_capable:
                    continue
                for hour in ev.hours_available:
                    if not self._v2g_should_activate(hour):
                        continue
                    # V2G only if EV has enough charge to spare
                    current_soc_kwh = ev.soc_after_kwh / 100.0 * ev.battery_cap_kwh
                    reserve_kwh     = V2G_RESERVE_SOC * ev.battery_cap_kwh
                    if current_soc_kwh <= reserve_kwh + V2G_DISCHARGE_RATE:
                        continue

                    v2g_kwh = min(V2G_DISCHARGE_RATE, current_soc_kwh - reserve_kwh)
                    v2g_kwh = round(v2g_kwh, 4)
                    revenue = v2g_kwh * SPOT_PRICES[hour]
                    dod     = (v2g_kwh / ev.battery_cap_kwh * 100) if ev.battery_cap_kwh else 0

                    ev.v2g_hours.append(hour)
                    ev.v2g_kwh         += v2g_kwh
                    ev.v2g_revenue_eur += revenue - ev.degradation_cycles(v2g_kwh, dod)

        # ── Round all values ──────────────────────────────────────────────────
        for ev in self.fleet:
            ev.total_kwh       = round(ev.total_kwh,       4)
            ev.grid_kwh        = round(ev.grid_kwh,        4)
            ev.solar_kwh       = round(ev.solar_kwh,       4)
            ev.v2g_kwh         = round(ev.v2g_kwh,         4)
            ev.energy_cost_eur = round(ev.energy_cost_eur, 4)
            ev.v2g_revenue_eur = round(ev.v2g_revenue_eur, 4)
            ev.degradation_eur = round(ev.degradation_eur, 4)
            ev.carbon_kg       = round(ev.carbon_kg,       4)

    def naive_cost(self, ev: ElectricVehicle) -> float:
        """Cost of ASAP (first-come-first-charged) unoptimised strategy."""
        needed = ev.energy_needed_kwh
        cost   = 0.0
        for h in ev.hours_available:
            if needed <= 0.001:
                break
            kwh   = min(CHARGER_KW, needed)
            cost += kwh * SPOT_PRICES[h]
            needed -= kwh
        return round(cost, 4)

    # ══════════════════════════════════════════════════════════════════════════
    #  REPORTS
    # ══════════════════════════════════════════════════════════════════════════

    def print_vehicle_schedules(self):
        _hdr("🔋 VEHICLE CHARGING SCHEDULES & V2G")
        for ev in self.fleet:
            naive  = self.naive_cost(ev)
            saving = naive - ev.energy_cost_eur
            pct    = saving / naive * 100 if naive else 0.0
            v2g_tag = "🔌 V2G" if ev.v2g_capable else "⛔ No V2G"

            print(f"\n  🚐  {ev.vehicle_id}  |  {ev.model}  |  P{ev.priority}  |  {v2g_tag}")
            print(f"     Window          : {ev.arrival_hour:02d}:00 → {ev.departure_hour:02d}:00 "
                  f"({ev.charging_window_h} hrs available)")
            print(f"     Battery         : {ev.soc_current_pct:.0f}% → target {ev.soc_target_pct:.0f}%  "
                  f"(needs {ev.energy_needed_kwh:.2f} kWh)")

            # SoC progress bar
            soc_bar  = "█" * int(ev.soc_after_kwh / 5)
            print(f"     SoC at depart   : {ev.soc_after_kwh:.1f}%  "
                  f"{'✅ READY' if ev.is_ready else '⚠️  NOT READY'}  [{soc_bar:<20}]")

            print(f"     Charged         : {ev.total_kwh:.2f} kWh  "
                  f"(Grid: {ev.grid_kwh:.2f} kWh  Solar: {ev.solar_kwh:.2f} kWh)")
            print(f"     Energy cost     : €{ev.energy_cost_eur:.4f}")
            print(f"     Degradation     : €{ev.degradation_eur:.4f}")

            if ev.v2g_kwh > 0.001:
                print(f"     V2G discharged  : {ev.v2g_kwh:.2f} kWh → Revenue €{ev.v2g_revenue_eur:.4f}")
                print(f"     V2G hours       : {', '.join(f'{h:02d}:00' for h in sorted(ev.v2g_hours))}")

            print(f"     TCO cost        : €{ev.tco_cost_eur:.4f}")
            print(f"     vs. ASAP naive  : €{naive:.4f}  |  Saved €{saving:.4f}  ({pct:.1f}%)")
            print(f"     Carbon          : {ev.carbon_kg:.3f} kg CO₂")

            if ev.scheduled_hours:
                h_str = "  ".join(f"{h:02d}:00" for h in sorted(ev.scheduled_hours))
                print(f"     Charging hours  : {h_str}")
        print()

    def print_depot_profile(self):
        _hdr("📊 DEPOT HOURLY LOAD PROFILE")
        print(f"  {'Hr':>3}  {'Vehs':>5}  {'Load kW':>8}  {'Solar kW':>9}  "
              f"{'Grid kW':>8}  {'€/kWh':>7}  {'CO₂ kg/h':>9}  Bar")
        print("  " + "─" * 78)

        total_grid   = 0.0
        total_solar  = 0.0
        total_cost   = 0.0
        total_carbon = 0.0
        peak_kw      = 0.0

        for h in range(24):
            n  = self.slots.total_vehicles_at(h)
            if n == 0:
                continue
            load_kw  = n * CHARGER_KW
            solar_kw = min(SOLAR_KW.get(h, 0.0), load_kw)
            grid_kw  = load_kw - solar_kw
            cost_h   = grid_kw * SPOT_PRICES[h]
            carb_h   = grid_kw * CARBON_INTENSITY.get(h, 0.34)
            bar      = "█" * n
            flag     = "⚠️ DEMAND" if load_kw > DEMAND_LIMIT_KW else ""

            peak_kw      = max(peak_kw, grid_kw)
            total_grid  += grid_kw
            total_solar += solar_kw
            total_cost  += cost_h
            total_carbon+= carb_h

            print(f"  {h:>3}  {n:>5}  {load_kw:>8.1f}  {solar_kw:>9.1f}  "
                  f"{grid_kw:>8.1f}  {SPOT_PRICES[h]:>7.3f}  {carb_h:>9.3f}  "
                  f"{bar} {flag}")

        print("  " + "─" * 78)
        print(f"  {'TOT':>3}  {'':5}  {'':8}  {total_solar:>9.1f}  "
              f"{total_grid:>8.1f}  {'':7}  {total_carbon:>9.3f}  "
              f"Cost: €{total_cost:.3f}  Peak: {peak_kw:.1f} kW")
        print()

    def print_fleet_summary(self):
        _hdr("💡 FLEET OPTIMISATION SUMMARY & PROJECTIONS")
        total_cost    = sum(ev.tco_cost_eur      for ev in self.fleet)
        total_naive   = sum(self.naive_cost(ev)  for ev in self.fleet)
        total_kwh     = sum(ev.total_kwh         for ev in self.fleet)
        total_solar   = sum(ev.solar_kwh         for ev in self.fleet)
        total_grid    = sum(ev.grid_kwh          for ev in self.fleet)
        total_v2g_rev = sum(ev.v2g_revenue_eur   for ev in self.fleet)
        total_carbon  = sum(ev.carbon_kg         for ev in self.fleet)
        ready         = sum(1 for ev in self.fleet if ev.is_ready)
        saving        = total_naive - sum(ev.energy_cost_eur for ev in self.fleet)
        solar_pct     = total_solar / total_kwh * 100 if total_kwh else 0

        print(f"  Depot             : {DEPOT_NAME}")
        print(f"  Fleet size        : {len(self.fleet)} vehicles")
        print(f"  Charger bays      : {MAX_SIMULTANEOUS} × {CHARGER_KW:.0f} kW AC Type-2")
        print(f"  V2G enabled       : {'Yes' if V2G_ENABLED else 'No'}")
        print()
        print(f"  ┌─────────────────────────────────────────────────────────┐")
        print(f"  │  ENERGY BREAKDOWN                                        │")
        print(f"  │  Total charged      : {total_kwh:>8.2f} kWh                   │")
        print(f"  │  From on-site solar : {total_solar:>8.2f} kWh  ({solar_pct:.1f}%)        │")
        print(f"  │  From grid          : {total_grid:>8.2f} kWh  ({100-solar_pct:.1f}%)        │")
        print(f"  │  V2G discharged     : {sum(ev.v2g_kwh for ev in self.fleet):>8.2f} kWh                   │")
        print(f"  ├─────────────────────────────────────────────────────────┤")
        print(f"  │  COST & SAVINGS                                          │")
        print(f"  │  Optimised fleet cost : €{total_cost:>9.4f}                  │")
        print(f"  │  Naive (ASAP) cost    : €{total_naive:>9.4f}                  │")
        print(f"  │  Smart-charge saving  : €{saving:>9.4f}  ({saving/total_naive*100 if total_naive else 0:.1f}%)      │")
        print(f"  │  V2G grid revenue     : €{total_v2g_rev:>9.4f}                  │")
        print(f"  ├─────────────────────────────────────────────────────────┤")
        print(f"  │  CARBON & READINESS                                      │")
        print(f"  │  CO₂ footprint        : {total_carbon:>9.3f} kg                  │")
        print(f"  │  Solar CO₂ avoided    : {total_solar * 0.34:>9.3f} kg                  │")
        print(f"  │  Vehicles ready       : {ready:>2} / {len(self.fleet):<2}                       │")
        print(f"  └─────────────────────────────────────────────────────────┘")
        print()

        # Annualised projections (250 working days)
        annual_saving = saving      * 250
        annual_v2g    = total_v2g_rev * 250
        annual_co2    = total_carbon  * 250
        annual_solar_co2 = total_solar * 0.34 * 250
        print(f"  📅  ANNUAL PROJECTIONS (250 operating days/year)")
        print(f"      Smart-charge saving : €{annual_saving:>10,.2f}/year")
        print(f"      V2G grid revenue    : €{annual_v2g:>10,.2f}/year")
        print(f"      Combined benefit    : €{annual_saving+annual_v2g:>10,.2f}/year")
        print(f"      Fleet CO₂ footprint : {annual_co2:>10,.1f} kg/year")
        print(f"      Solar CO₂ avoided   : {annual_solar_co2:>10,.1f} kg/year")
        print()


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

W = 78
def _div(c="═"):   print(c * W)
def _hdr(t: str):  _div(); print(f"  {t}"); _div()


# ═══════════════════════════════════════════════════════════════════════════════
#  FLEET ROSTER
# ═══════════════════════════════════════════════════════════════════════════════

def build_fleet() -> list[ElectricVehicle]:
    return [
        ElectricVehicle("VAN-001", "Mercedes eSprinter 55 kWh",
                        battery_cap_kwh=113, soc_current_pct=18, soc_target_pct=90,
                        arrival_hour=18, departure_hour=6,  priority=1, v2g_capable=True),
        ElectricVehicle("VAN-002", "Volkswagen e-Crafter",
                        battery_cap_kwh=82,  soc_current_pct=35, soc_target_pct=85,
                        arrival_hour=19, departure_hour=7,  priority=2, v2g_capable=False),
        ElectricVehicle("VAN-003", "Ford E-Transit 68 kWh",
                        battery_cap_kwh=68,  soc_current_pct=52, soc_target_pct=95,
                        arrival_hour=17, departure_hour=5,  priority=1, v2g_capable=True),
        ElectricVehicle("CAR-004", "Tesla Model Y LR (management)",
                        battery_cap_kwh=75,  soc_current_pct=40, soc_target_pct=80,
                        arrival_hour=20, departure_hour=8,  priority=3, v2g_capable=True),
        ElectricVehicle("VAN-005", "Renault Kangoo E-Tech",
                        battery_cap_kwh=45,  soc_current_pct=10, soc_target_pct=100,
                        arrival_hour=18, departure_hour=6,  priority=1, v2g_capable=False),
        ElectricVehicle("VAN-006", "Citroën ë-Dispatch 75 kWh",
                        battery_cap_kwh=75,  soc_current_pct=28, soc_target_pct=88,
                        arrival_hour=21, departure_hour=7,  priority=2, v2g_capable=True),
        ElectricVehicle("TRK-007", "Arrival Truck Prototype",
                        battery_cap_kwh=200, soc_current_pct=25, soc_target_pct=80,
                        arrival_hour=16, departure_hour=7,  priority=1, v2g_capable=False),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print()
    _div()
    print(f"  ⚡  NextGen Energy Suite  v{VERSION}  |  EV Fleet Smart Charging Optimizer")
    print(f"  📅  {datetime.today().strftime('%A, %d %B %Y')}")
    _div()
    print(f"\n  Depot          : {DEPOT_NAME}")
    print(f"  V2G mode       : {'Enabled (≥€{:.2f}/kWh threshold)'.format(V2G_PRICE_THRESHOLD) if V2G_ENABLED else 'Disabled'}")
    print(f"  Solar on-site  : {'Max ' + str(max(SOLAR_KW.values())) + ' kW peak'}")
    print(f"  Demand limit   : {DEMAND_LIMIT_KW} kW  (€{DEMAND_CHARGE_EUR_KW}/kW/month over)\n")

    fleet     = build_fleet()
    optimiser = EVFleetOptimiser(fleet)
    optimiser.schedule()

    optimiser.print_vehicle_schedules()
    optimiser.print_depot_profile()
    optimiser.print_fleet_summary()

    _div("─")
    print(f"  NextGen Energy Suite v{VERSION}  |  Module 3: EV Fleet Smart Charging")
    print(f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  GitHub    : https://github.com/john724/nextgen-energy-suite")
    _div("─")


if __name__ == "__main__":
    main()
