"""
================================================================================
  NextGen Energy Suite  ⚡  v3.0
  Module 1 — AI B2B Energy Optimizer
  ─────────────────────────────────────────────────────────────────────────────
  Problem  : Commercial buildings waste thousands of euros by running high-load
             equipment during peak-pricing grid intervals.  Contract demand
             breaches trigger expensive utility penalties.  CO₂ footprint goes
             unreported.

  Solution : Ingests 24-hour industrial load profiles + day-ahead EPEX spot
             prices + carbon intensity signals → runs three optimisation layers:
               1. LOAD SHAVING    — curtail non-critical loads during peaks
               2. LOAD SHIFTING   — reschedule flexible loads to off-peak slots
               3. BATTERY DISPATCH — model on-site BESS charge/discharge cycles
             Produces a full cost/carbon audit + ROI report.

  Algorithms   : Percentile price zoning · Greedy load-shift · BESS LP heuristic
  Dependencies : pandas ≥ 1.5, numpy ≥ 1.22
  Python       : 3.10+
  Run          : python b2b_energy_optimizer.py
================================================================================
"""

import sys
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
import os
import ml_engine

# ── Encoding safety for Windows cp1252 terminals ─────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VERSION = "3.0.0"

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

FACILITY_NAME    = "NovaTech Manufacturing GmbH"
FACILITY_TYPE    = "Heavy Industry"
FACILITY_AREA_M2 = 8_500          # m² — for intensity KPI
CONTRACT_DEMAND  = 90             # kW — contracted peak demand limit
DEMAND_PENALTY   = 14.50          # €/kW/month over contract limit
WORKING_DAYS     = 22             # per month
CARBON_PRICE_EUR = 0.065          # €/kg CO₂ (EU ETS proxy)

# 24-hour load profile (kW) — typical weekday
CONSUMPTION_KW: list[float] = [
    12, 11, 10,  9, 15, 25,   # 00–05  off-shift maintenance
    40, 55, 60, 65, 70, 75,   # 06–11  morning production ramp
    80, 78, 75, 70, 65, 50,   # 12–17  peak production shift
    45, 35, 30, 25, 18, 14,   # 18–23  evening wind-down
]

# Day-ahead spot prices (€/kWh) — EPEX Spot style
SPOT_PRICES_EUR: list[float] = [
    0.098, 0.092, 0.081, 0.078, 0.110, 0.148,
    0.218, 0.276, 0.302, 0.321, 0.348, 0.352,
    0.319, 0.298, 0.281, 0.264, 0.252, 0.278,
    0.322, 0.301, 0.221, 0.180, 0.142, 0.118,
]

if os.getenv("ML_MODE", "false").lower() == "true" and ml_engine.ML_AVAILABLE:
    try:
        CONSUMPTION_KW, SPOT_PRICES_EUR = ml_engine.generate_tomorrow_forecast()
    except Exception as e:
        print(f"⚠️ ML forecast failed, falling back to static data: {e}")

# Grid CO₂ intensity (kg CO₂ / kWh) — varies by generation mix
CARBON_INTENSITY: list[float] = [
    0.28, 0.27, 0.25, 0.24, 0.26, 0.30,
    0.38, 0.41, 0.40, 0.38, 0.36, 0.34,
    0.33, 0.32, 0.31, 0.30, 0.29, 0.31,
    0.35, 0.37, 0.34, 0.30, 0.28, 0.27,
]

# On-site solar PV generation (kW per hour)
SOLAR_PV_KW: list[float] = [
    0, 0, 0, 0, 0, 0,
    3, 8, 16, 22, 27, 30,
    31, 29, 25, 20, 12, 5,
    1, 0, 0, 0, 0, 0,
]

# ── Battery Energy Storage System (BESS) ─────────────────────────────────────
BESS_CAPACITY_KWH   = 120.0   # usable kWh
BESS_MAX_CHARGE_KW  =  40.0   # max charge rate
BESS_MAX_DISCHARGE_KW= 40.0   # max discharge rate
BESS_EFFICIENCY     = 0.92    # round-trip efficiency
BESS_INITIAL_SOC    = 0.30    # 30 % starting SoC
BESS_MIN_SOC        = 0.10    # 10 % minimum SoC floor
BESS_MAX_SOC        = 0.95    # 95 % maximum SoC ceiling
BESS_CYCLE_COST_EUR = 0.020   # €/kWh cycled (degradation)

# ── Shiftable / Shaveable Load Catalogue ─────────────────────────────────────
SHIFTABLE_LOADS: list[dict] = [
    {"name": "Air Compressors",        "kw": 18, "min_hours": 3, "flexibility": "shift",  "priority": 1},
    {"name": "CNC Machine Batch",      "kw": 12, "min_hours": 4, "flexibility": "shift",  "priority": 2},
    {"name": "Water Heating System",   "kw":  8, "min_hours": 2, "flexibility": "shift",  "priority": 3},
    {"name": "HVAC Pre-cooling",       "kw": 10, "min_hours": 2, "flexibility": "shave",  "priority": 1},
    {"name": "Lighting (non-critical)","kw":  4, "min_hours": 0, "flexibility": "shave",  "priority": 2},
    {"name": "EV Depot Charger",       "kw": 22, "min_hours": 6, "flexibility": "shift",  "priority": 4},
]


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BESSState:
    """Tracks BESS state of charge and dispatch actions hour by hour."""
    soc: float = BESS_INITIAL_SOC
    hourly_action:  list[float] = field(default_factory=list)   # + = charge, - = discharge (kW)
    hourly_soc:     list[float] = field(default_factory=list)
    revenue_eur:    float = 0.0
    cost_eur:       float = 0.0
    cycles_equiv:   float = 0.0

    @property
    def soc_kwh(self) -> float:
        return self.soc * BESS_CAPACITY_KWH

    def charge(self, kw: float, price: float) -> float:
        """Charge BESS. Returns actual kW charged."""
        max_kw = min(BESS_MAX_CHARGE_KW, kw,
                     (BESS_MAX_SOC - self.soc) * BESS_CAPACITY_KWH / BESS_EFFICIENCY)
        max_kw = max(0.0, max_kw)
        self.soc += max_kw * BESS_EFFICIENCY / BESS_CAPACITY_KWH
        self.soc  = min(self.soc, BESS_MAX_SOC)
        self.cost_eur += max_kw * price + max_kw * BESS_CYCLE_COST_EUR
        self.cycles_equiv += max_kw / BESS_CAPACITY_KWH
        return max_kw

    def discharge(self, kw: float, price: float) -> float:
        """Discharge BESS. Returns actual kW discharged."""
        max_kw = min(BESS_MAX_DISCHARGE_KW, kw,
                     (self.soc - BESS_MIN_SOC) * BESS_CAPACITY_KWH * BESS_EFFICIENCY)
        max_kw = max(0.0, max_kw)
        self.soc -= max_kw / (BESS_CAPACITY_KWH * BESS_EFFICIENCY)
        self.soc  = max(self.soc, BESS_MIN_SOC)
        self.revenue_eur += max_kw * price - max_kw * BESS_CYCLE_COST_EUR
        self.cycles_equiv += max_kw / BESS_CAPACITY_KWH
        return max_kw


# ═══════════════════════════════════════════════════════════════════════════════
#  PROFILE BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_profile() -> tuple[pd.DataFrame, float, float, float]:
    """Construct the full 24-hour energy profile DataFrame."""
    base_date  = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    timestamps = [base_date + timedelta(hours=h) for h in range(24)]

    df = pd.DataFrame({
        "timestamp":        timestamps,
        "hour":             list(range(24)),
        "consumption_kw":   CONSUMPTION_KW,
        "spot_price_eur":   SPOT_PRICES_EUR,
        "carbon_intensity": CARBON_INTENSITY,
        "solar_pv_kw":      SOLAR_PV_KW,
    })

    # Net load after solar self-consumption
    df["net_load_kw"]    = (df["consumption_kw"] - df["solar_pv_kw"]).clip(lower=0.0)
    df["solar_export_kw"]= (df["solar_pv_kw"]   - df["consumption_kw"]).clip(lower=0.0)
    df["energy_cost_eur"]= df["net_load_kw"]   * df["spot_price_eur"]
    df["carbon_kg"]      = df["net_load_kw"]   * df["carbon_intensity"]
    df["solar_saving_eur"]= df["solar_pv_kw"].clip(upper=df["consumption_kw"]) * df["spot_price_eur"]

    # Price tier classification (quartile-based)
    p25 = df["spot_price_eur"].quantile(0.25)
    p50 = df["spot_price_eur"].quantile(0.50)
    p75 = df["spot_price_eur"].quantile(0.75)

    def classify(p):
        if p >= p75:     return "🔴 PEAK"
        elif p >= p50:   return "🟡 MID"
        else:            return "🟢 OFF-PEAK"

    df["price_tier"]      = df["spot_price_eur"].apply(classify)
    df["demand_exceeded"] = df["net_load_kw"] > CONTRACT_DEMAND

    return df, p25, p50, p75


# ═══════════════════════════════════════════════════════════════════════════════
#  BESS DISPATCH HEURISTIC
# ═══════════════════════════════════════════════════════════════════════════════

def run_bess_dispatch(df: pd.DataFrame, p25: float, p75: float) -> tuple[BESSState, pd.DataFrame]:
    """
    Simple rule-based BESS dispatch:
      • Cheap hours  (≤ p25) → charge if SoC < ceiling
      • Expensive hrs(≥ p75) → discharge to shave peak
    Returns updated BESSState and a column-augmented copy of df.
    """
    bess  = BESSState()
    bess_cols = []

    for _, row in df.iterrows():
        price = row["spot_price_eur"]
        load  = row["net_load_kw"]
        action_kw = 0.0

        if price <= p25 and bess.soc < BESS_MAX_SOC:
            # Cheap → charge
            headroom = min(BESS_MAX_CHARGE_KW, (BESS_MAX_SOC - bess.soc) * BESS_CAPACITY_KWH)
            charged  = bess.charge(headroom, price)
            action_kw = charged        # positive = grid draw for charging
        elif price >= p75 and load > 20.0 and bess.soc > BESS_MIN_SOC:
            # Peak → discharge to offset load
            needed   = min(load * 0.50, BESS_MAX_DISCHARGE_KW)   # discharge ≤ 50% of load
            discharged = bess.discharge(needed, price)
            action_kw = -discharged   # negative = grid relief

        bess.hourly_action.append(action_kw)
        bess.hourly_soc.append(bess.soc * 100)   # store as %

    df = df.copy()
    df["bess_action_kw"] = bess.hourly_action
    df["bess_soc_pct"]   = bess.hourly_soc

    # Adjust net load and cost after BESS
    df["net_load_bess_kw"]    = (df["net_load_kw"] + df["bess_action_kw"]).clip(lower=0.0)
    df["energy_cost_bess_eur"]= df["net_load_bess_kw"] * df["spot_price_eur"]
    df["carbon_bess_kg"]      = df["net_load_bess_kw"] * df["carbon_intensity"]

    return bess, df


# ═══════════════════════════════════════════════════════════════════════════════
#  ANALYSIS ENGINES
# ═══════════════════════════════════════════════════════════════════════════════

def analyse_peak_hours(df: pd.DataFrame, p75: float) -> pd.DataFrame:
    """Identify peak hours and compute per-load shaving savings."""
    peak = df[df["spot_price_eur"] >= p75].copy()
    rows = []
    for _, row in peak.iterrows():
        for load in SHIFTABLE_LOADS:
            if load["flexibility"] != "shave":
                continue
            if row["net_load_kw"] > 40.0:
                saving_eur    = load["kw"] * row["spot_price_eur"]
                carbon_saved  = load["kw"] * row["carbon_intensity"]
                carbon_val_eur= carbon_saved * CARBON_PRICE_EUR
                rows.append({
                    "hour":           int(row["hour"]),
                    "load_name":      load["name"],
                    "load_kw":        load["kw"],
                    "priority":       load["priority"],
                    "price_eur_kwh":  row["spot_price_eur"],
                    "saving_eur":     saving_eur,
                    "carbon_saved_kg":carbon_saved,
                    "carbon_value_eur":carbon_val_eur,
                    "total_benefit_eur": saving_eur + carbon_val_eur,
                })
    rec = pd.DataFrame(rows)
    if not rec.empty:
        rec.sort_values(["hour", "priority"], inplace=True)
    return rec


def find_load_shift_windows(df: pd.DataFrame, p25: float, p75: float) -> list[dict]:
    """Match each shiftable load to the optimal cheap-hour window."""
    off_peak = df[df["spot_price_eur"] <= p25].copy()
    results  = []

    for load in sorted(SHIFTABLE_LOADS, key=lambda l: l["priority"]):
        if load["flexibility"] != "shift":
            continue
        if len(off_peak) < max(load["min_hours"], 1):
            continue

        n_hours         = max(load["min_hours"], 1)
        best            = off_peak.nsmallest(n_hours, "spot_price_eur")
        avg_cheap       = best["spot_price_eur"].mean()
        avg_peak        = df[df["spot_price_eur"] >= p75]["spot_price_eur"].mean()
        peak_carbon_int = df[df["spot_price_eur"] >= p75]["carbon_intensity"].mean()
        cheap_carbon_int= best["carbon_intensity"].mean()
        energy_kwh      = load["kw"] * n_hours
        cost_saving     = energy_kwh * (avg_peak - avg_cheap)
        carbon_saving   = energy_kwh * (peak_carbon_int - cheap_carbon_int)

        results.append({
            "load":                load["name"],
            "kw":                  load["kw"],
            "duration_h":          n_hours,
            "shift_to_hours":      sorted(best["hour"].tolist()),
            "avg_cheap_eur_kwh":   avg_cheap,
            "avg_peak_eur_kwh":    avg_peak,
            "estimated_cost_saving": max(cost_saving, 0.0),
            "estimated_carbon_saving_kg": max(carbon_saving, 0.0),
            "carbon_value_eur":    max(carbon_saving, 0.0) * CARBON_PRICE_EUR,
        })

    return results


def compute_metrics(df: pd.DataFrame, df_bess: pd.DataFrame,
                    shave_recs: pd.DataFrame, shift_results: list[dict],
                    bess: BESSState) -> dict:
    """Build the full optimisation metrics dictionary."""
    # Baseline (raw net load, with solar)
    baseline_cost   = df["energy_cost_eur"].sum()
    baseline_carbon = df["carbon_kg"].sum()
    solar_saving    = df["solar_saving_eur"].sum()

    # Shaving & shifting
    shave_cost   = shave_recs["saving_eur"].sum()      if not shave_recs.empty else 0.0
    shave_carbon = shave_recs["carbon_saved_kg"].sum() if not shave_recs.empty else 0.0
    shift_cost   = sum(r["estimated_cost_saving"]       for r in shift_results)
    shift_carbon = sum(r["estimated_carbon_saving_kg"]  for r in shift_results)

    # BESS net benefit (revenue from arbitrage minus charge costs)
    bess_net    = bess.revenue_eur - bess.cost_eur
    bess_cost_delta = df_bess["energy_cost_bess_eur"].sum() - baseline_cost

    total_cost_saving   = shave_cost + shift_cost + max(0.0, -bess_cost_delta)
    optimised_cost      = baseline_cost - total_cost_saving
    optimised_carbon    = baseline_carbon - shave_carbon - shift_carbon

    # Demand penalty
    demand_breach_hours = df[df["demand_exceeded"]]
    max_breach_kw = (demand_breach_hours["net_load_kw"] - CONTRACT_DEMAND).clip(lower=0).max() if not demand_breach_hours.empty else 0.0
    demand_penalty_eur  = max_breach_kw * DEMAND_PENALTY

    # KPIs
    intensity_kwh_m2 = df["consumption_kw"].sum() / FACILITY_AREA_M2

    return {
        "baseline_cost_eur":        baseline_cost,
        "optimised_cost_eur":       max(optimised_cost, 0.0),
        "total_cost_saving_eur":    total_cost_saving,
        "saving_pct":               total_cost_saving / baseline_cost * 100 if baseline_cost else 0,
        "solar_saving_eur":         solar_saving,
        "shave_saving_eur":         shave_cost,
        "shift_saving_eur":         shift_cost,
        "bess_arbitrage_eur":       max(0.0, -bess_cost_delta),
        "baseline_carbon_kg":       baseline_carbon,
        "optimised_carbon_kg":      optimised_carbon,
        "carbon_reduction_pct":     (baseline_carbon - optimised_carbon) / baseline_carbon * 100 if baseline_carbon else 0,
        "carbon_cost_baseline":     baseline_carbon * CARBON_PRICE_EUR,
        "carbon_cost_optimised":    optimised_carbon * CARBON_PRICE_EUR,
        "demand_penalty_eur":       demand_penalty_eur,
        "bess_cycles_equiv":        bess.cycles_equiv,
        "energy_intensity_kwh_m2":  intensity_kwh_m2,
        "solar_kwh_day":            sum(SOLAR_PV_KW),
        "solar_self_consumed_kwh":  min(sum(SOLAR_PV_KW), sum(CONSUMPTION_KW)),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  REPORTING
# ═══════════════════════════════════════════════════════════════════════════════

W = 78   # line width

def _div(char="═"):    print(char * W)
def _hdr(title: str):  _div(); print(f"  {title}"); _div()

def _bar(value: float, max_val: float, width: int = 30, fill: str = "█") -> str:
    n = int(round(value / max_val * width)) if max_val else 0
    return fill * min(n, width)

def print_banner():
    _div("═")
    print("  ⚡  NextGen Energy Suite  v{ver}  |  AI B2B Energy Optimizer".format(ver=VERSION))
    print(f"  📅  {datetime.today().strftime('%A, %d %B %Y')}   |   🏭 {FACILITY_NAME}")
    _div("═")
    print()

def print_hourly_profile(df: pd.DataFrame):
    _hdr("📊 24-HOUR NET LOAD · PRICE · CARBON PROFILE")
    max_load   = df["net_load_kw"].max()
    print(f"  {'Hr':>3}  {'Net kW':>7}  {'Solar':>6}  {'€/kWh':>7}  "
          f"{'Cost €':>8}  {'CO₂ kg':>7}  {'Tier':<12}  Load Bar")
    print("  " + "─" * 74)
    for _, r in df.iterrows():
        bar = _bar(r["net_load_kw"], max_load, 20)
        print(f"  {int(r['hour']):>3}  {r['net_load_kw']:>7.1f}  "
              f"{r['solar_pv_kw']:>6.1f}  "
              f"{r['spot_price_eur']:>7.3f}  "
              f"{r['energy_cost_eur']:>8.3f}  "
              f"{r['carbon_kg']:>7.2f}  "
              f"{r['price_tier']:<12}  {bar}")
    print(f"\n  Totals:  Net {df['net_load_kw'].sum():.0f} kWh  |  "
          f"Solar {sum(SOLAR_PV_KW):.0f} kWh  |  "
          f"Cost €{df['energy_cost_eur'].sum():.2f}  |  "
          f"CO₂ {df['carbon_kg'].sum():.1f} kg")
    print()

def print_bess_dispatch(df: pd.DataFrame, bess: BESSState):
    _hdr("🔋 BATTERY STORAGE (BESS) DISPATCH LOG")
    print(f"  Capacity: {BESS_CAPACITY_KWH:.0f} kWh  |  "
          f"Max C/D: {BESS_MAX_CHARGE_KW:.0f}/{BESS_MAX_DISCHARGE_KW:.0f} kW  |  "
          f"Eff: {BESS_EFFICIENCY*100:.0f}%  |  "
          f"Initial SoC: {BESS_INITIAL_SOC*100:.0f}%\n")
    print(f"  {'Hr':>3}  {'Action':>12}  {'SoC%':>6}  {'SoC Bar':>6}  {'Net Load kW':>11}  {'Price €':>8}  Note")
    print("  " + "─" * 68)
    for h, (action, soc, price, net) in enumerate(zip(
            bess.hourly_action, bess.hourly_soc,
            SPOT_PRICES_EUR, df["net_load_kw"].tolist())):
        note = ""
        if action >  0.5: note = f"⚡ CHARGE   +{action:.1f} kW"
        if action < -0.5: note = f"🔋 DISCHARGE {action:.1f} kW"
        soc_bar = _bar(soc, 100, 12)
        print(f"  {h:>3}  {action:>+12.1f}  {soc:>6.1f}  {soc_bar:<12}  "
              f"{net:>11.1f}  {price:>8.3f}  {note}")
    print(f"\n  Total cycles (equiv): {bess.cycles_equiv:.3f}"
          f"  |  Arbitrage revenue: €{bess.revenue_eur:.3f}"
          f"  |  Charge cost: €{bess.cost_eur:.3f}"
          f"  |  Net BESS P&L: €{bess.revenue_eur - bess.cost_eur:+.3f}")
    print()

def print_shave_recommendations(shave_recs: pd.DataFrame):
    _hdr("⚡ DEMAND RESPONSE — LOAD SHAVING ACTIONS")
    if shave_recs.empty:
        print("  ✅ No shaving actions required for today's price profile.\n"); return

    grouped = shave_recs.groupby("hour")
    for hour, grp in grouped:
        price = grp["price_eur_kwh"].iloc[0]
        print(f"\n  ⚠️  Hour {hour:02d}:00 — Spot Price: €{price:.3f}/kWh")
        for _, rec in grp.iterrows():
            print(f"     └─ [{rec['priority']}] {rec['load_name']:<28}  "
                  f"Save: €{rec['saving_eur']:.3f}  CO₂↓ {rec['carbon_saved_kg']:.2f} kg  "
                  f"Carbon val: €{rec['carbon_value_eur']:.3f}")

    totals = shave_recs[["saving_eur","carbon_saved_kg","total_benefit_eur"]].sum()
    print(f"\n  Shave totals → Cost: €{totals['saving_eur']:.3f}  "
          f"CO₂: {totals['carbon_saved_kg']:.2f} kg  "
          f"Total benefit: €{totals['total_benefit_eur']:.3f}")
    print()

def print_shift_plan(shift_results: list[dict]):
    _hdr("🔀 LOAD SHIFTING — OPTIMAL RESCHEDULING PLAN")
    if not shift_results:
        print("  ✅ No shiftable loads identified.\n"); return
    for r in shift_results:
        hrs = ", ".join(f"{h:02d}:00" for h in r["shift_to_hours"])
        total_benefit = r["estimated_cost_saving"] + r["carbon_value_eur"]
        print(f"\n  📦  {r['load']}  ({r['kw']} kW × {r['duration_h']}h = {r['kw']*r['duration_h']:.0f} kWh)")
        print(f"      Shift window : [{hrs}]")
        print(f"      Peak avg     : €{r['avg_peak_eur_kwh']:.4f}/kWh  →  Cheap avg: €{r['avg_cheap_eur_kwh']:.4f}/kWh")
        print(f"      Cost saving  : €{r['estimated_cost_saving']:.3f}  |  "
              f"Carbon saved: {r['estimated_carbon_saving_kg']:.2f} kg  |  "
              f"Carbon value: €{r['carbon_value_eur']:.3f}")
        print(f"      Total benefit: €{total_benefit:.3f}")
    total_shift_cost  = sum(r["estimated_cost_saving"] for r in shift_results)
    total_shift_carb  = sum(r["estimated_carbon_saving_kg"] for r in shift_results)
    print(f"\n  Shift totals → Cost: €{total_shift_cost:.3f}  CO₂: {total_shift_carb:.2f} kg")
    print()

def print_summary_report(m: dict, df: pd.DataFrame):
    _hdr("💡 OPTIMISATION SUMMARY & ROI REPORT")
    print(f"  Facility          : {FACILITY_NAME}")
    print(f"  Type              : {FACILITY_TYPE}  ({FACILITY_AREA_M2:,} m²)")
    print(f"  Report date       : {datetime.today().strftime('%Y-%m-%d')}")
    print(f"  Energy intensity  : {m['energy_intensity_kwh_m2']:.3f} kWh/m²/day")
    print()

    # ── Cost table ────────────────────────────────────────────────────────────
    print(f"  ┌──────────────────────────────────────────────────────────────┐")
    print(f"  │  DAILY COST BREAKDOWN                                        │")
    print(f"  │  Baseline (net of solar)      : €{m['baseline_cost_eur']:>9.3f}                │")
    print(f"  │  Solar PV self-consumption    : €{m['solar_saving_eur']:>9.3f}  saved           │")
    print(f"  │  Load shaving savings         : €{m['shave_saving_eur']:>9.3f}  saved           │")
    print(f"  │  Load shifting savings        : €{m['shift_saving_eur']:>9.3f}  saved           │")
    print(f"  │  BESS arbitrage benefit       : €{m['bess_arbitrage_eur']:>9.3f}  saved           │")
    print(f"  │  ─────────────────────────────────────────────────────────  │")
    print(f"  │  Optimised daily cost         : €{m['optimised_cost_eur']:>9.3f}                │")
    print(f"  │  TOTAL SAVINGS                : €{m['total_cost_saving_eur']:>9.3f}  ({m['saving_pct']:.1f}%)       │")
    print(f"  ├──────────────────────────────────────────────────────────────┤")
    print(f"  │  CARBON ANALYSIS                                             │")
    print(f"  │  Baseline daily CO₂           :  {m['baseline_carbon_kg']:>8.2f} kg               │")
    print(f"  │  Optimised daily CO₂          :  {m['optimised_carbon_kg']:>8.2f} kg               │")
    print(f"  │  Reduction                    :  {m['carbon_reduction_pct']:>8.1f}%                │")
    print(f"  │  Carbon cost saved (EU ETS)   : €{m['carbon_cost_baseline']-m['carbon_cost_optimised']:>9.3f}                │")
    print(f"  ├──────────────────────────────────────────────────────────────┤")

    # Demand penalty
    if m["demand_penalty_eur"] > 0:
        print(f"  │  ⚠️  DEMAND PENALTY EXPOSURE   : €{m['demand_penalty_eur']:>9.2f}/month          │")
    else:
        print(f"  │  ✅ No contract demand breach detected                        │")

    print(f"  └──────────────────────────────────────────────────────────────┘")
    print()

    # ── Projections ───────────────────────────────────────────────────────────
    monthly_cost  = m["total_cost_saving_eur"] * WORKING_DAYS
    annual_cost   = monthly_cost               * 12
    annual_co2    = m["optimised_carbon_kg"]   * 365
    bess_capex    = 800 * BESS_CAPACITY_KWH    # € — typical CAPEX estimate
    bess_payback  = bess_capex / (m["bess_arbitrage_eur"] * WORKING_DAYS * 12) if m["bess_arbitrage_eur"] > 0.01 else 999

    print(f"  📅  PROJECTIONS & ROI (Working days: {WORKING_DAYS}/month)")
    print(f"      Monthly savings           : €{monthly_cost:>10,.2f}")
    print(f"      Annual  savings           : €{annual_cost:>10,.2f}")
    print(f"      Annual CO₂ footprint      :  {annual_co2:>10,.1f} kg/year")
    print(f"      Annual CO₂ saving         :  {m['carbon_reduction_pct']*m['baseline_carbon_kg']*365/100:>10,.1f} kg/year")
    print(f"      BESS CAPEX (est.)         : €{bess_capex:>10,.0f}")
    print(f"      BESS payback period       :  {bess_payback:>10.1f} years")
    print(f"      Solar yield/day           :  {m['solar_kwh_day']:>10.1f} kWh")
    print()

    # ── Demand breach alert ───────────────────────────────────────────────────
    breach = df[df["demand_exceeded"]]
    if not breach.empty:
        print(f"  ⚠️  CONTRACT DEMAND BREACH — Hours exceeding {CONTRACT_DEMAND} kW:")
        for _, r in breach.iterrows():
            excess = r["net_load_kw"] - CONTRACT_DEMAND
            bar    = "█" * int(excess / 2)
            print(f"     Hour {int(r['hour']):02d}:00 — {r['net_load_kw']:.1f} kW  "
                  f"(+{excess:.1f} kW)  Penalty risk  {bar}")
    print()

def print_ascii_price_chart(df: pd.DataFrame):
    _hdr("📈 SPOT PRICE SPARKLINE (24h)")
    max_p = max(SPOT_PRICES_EUR)
    for _, r in df.iterrows():
        height = int(r["spot_price_eur"] / max_p * 8)
        bar    = "▉" * height
        tier_c = {"🔴 PEAK": "!", "🟡 MID": "~", "🟢 OFF-PEAK": "."}
        sym    = tier_c.get(r["price_tier"], ".")
        print(f"  {int(r['hour']):>02d}:00  €{r['spot_price_eur']:.3f}  [{bar:<8}] {sym}")
    print()

def print_footer():
    _div("─")
    print(f"  NextGen Energy Suite v{VERSION}  |  Module 1: AI B2B Energy Optimizer")
    print(f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  GitHub    : https://github.com/john724/nextgen-energy-suite")
    _div("─")


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> dict:
    print()
    print_banner()

    # ── Build profile ─────────────────────────────────────────────────────────
    df, p25, p50, p75 = build_profile()

    # ── BESS dispatch ─────────────────────────────────────────────────────────
    bess, df_bess = run_bess_dispatch(df, p25, p75)

    # ── Analysis ──────────────────────────────────────────────────────────────
    shave_recs    = analyse_peak_hours(df, p75)
    shift_results = find_load_shift_windows(df, p25, p75)
    metrics       = compute_metrics(df, df_bess, shave_recs, shift_results, bess)

    # ── Reports ───────────────────────────────────────────────────────────────
    print_ascii_price_chart(df)
    print_hourly_profile(df)
    print_bess_dispatch(df, bess)
    print_shave_recommendations(shave_recs)
    print_shift_plan(shift_results)
    print_summary_report(metrics, df)
    print_footer()

    return metrics


if __name__ == "__main__":
    main()
