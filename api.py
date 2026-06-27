"""
================================================================================
  NextGen Energy Suite — FastAPI Backend
  ─────────────────────────────────────────────────────────────────────────────
  Serves the optimization engines as REST APIs and hosts the static dashboard.
================================================================================
"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the core modules
import b2b_energy_optimizer as b2b
import microgrid_p2p_trader as p2p
import ev_fleet_smart_charger as ev

app = FastAPI(
    title=os.getenv("APP_NAME", "NextGen Energy Suite API"),
    description="REST API for NextGen Energy Suite modules.",
    version="3.1.0"
)

# ── API ENDPOINTS ─────────────────────────────────────────────────────────────

@app.get("/api/b2b")
def get_b2b_optimization():
    """Runs the B2B Energy Optimizer and returns the metrics."""
    df, p25, p50, p75 = b2b.build_profile()
    bess, df_bess = b2b.run_bess_dispatch(df, p25, p75)
    shave_recs = b2b.analyse_peak_hours(df, p75)
    shift_results = b2b.find_load_shift_windows(df, p25, p75)
    metrics = b2b.compute_metrics(df, df_bess, shave_recs, shift_results, bess)
    
    # Prepare chart data
    chart_data = {
        "hours": df["hour"].tolist(),
        "spot_prices": df["spot_price_eur"].tolist(),
        "net_load_kw": df["net_load_kw"].tolist(),
        "carbon_intensity": df["carbon_intensity"].tolist()
    }
    
    return {
        "metrics": metrics,
        "chart_data": chart_data,
        "facility_name": os.getenv("B2B_FACILITY_NAME", b2b.FACILITY_NAME)
    }

@app.get("/api/p2p")
def get_p2p_trading():
    """Runs the MicroGrid P2P Trading Engine and returns the results."""
    neighborhood = p2p.build_neighborhood()
    engine = p2p.P2PClearingEngine(neighborhood)
    total_trades = engine.run()
    
    cs = sum(t.consumer_surplus for t in engine.ledger)
    ps = sum(t.producer_surplus for t in engine.ledger)
    total_energy = sum(t.energy_kwh for t in engine.ledger)
    avg_price = (sum(t.price_eur_kwh * t.energy_kwh for t in engine.ledger) / total_energy) if total_energy else 0.0
    total_demand = sum(p.consumption for p in engine.participants)
    local_cover = (total_energy / total_demand * 100) if total_demand else 0.0
    
    metrics = {
        "trades_cleared": total_trades,
        "total_p2p_energy_kwh": total_energy,
        "consumer_surplus_eur": cs,
        "producer_surplus_eur": ps,
        "avg_price_eur": avg_price,
        "local_coverage_pct": local_cover
    }
    
    participants = []
    for p in engine.participants:
        participants.append({
            "name": p.name,
            "role": "Prosumer" if p.is_prosumer else "Consumer",
            "net_benefit": (p.revenue_eur - p.spending_eur - p.fees_paid_eur) - (max(0.0, (p.solar_generation + p.battery_storage - p.consumption) * p2p.GRID_EXPORT_PRICE) - p.consumption * p2p.GRID_IMPORT_PRICE)
        })
        
    return {
        "metrics": metrics,
        "participants": participants
    }

@app.get("/api/ev")
def get_ev_fleet():
    """Runs the EV Fleet Smart Charger and returns the schedules."""
    fleet = ev.build_fleet()
    optimiser = ev.EVFleetOptimiser(fleet)
    optimiser.schedule()
    
    total_cost = sum(v.tco_cost_eur for v in optimiser.fleet)
    total_naive = sum(optimiser.naive_cost(v) for v in optimiser.fleet)
    saving = total_naive - sum(v.energy_cost_eur for v in optimiser.fleet)
    total_v2g = sum(v.v2g_revenue_eur for v in optimiser.fleet)
    ready = sum(1 for v in optimiser.fleet if v.is_ready)
    
    metrics = {
        "fleet_size": len(fleet),
        "vehicles_ready": ready,
        "optimised_cost_eur": total_cost,
        "naive_cost_eur": total_naive,
        "smart_charge_saving_eur": saving,
        "v2g_revenue_eur": total_v2g,
        "annual_benefit_eur": (saving + total_v2g) * 250
    }
    
    vehicles = []
    for v in optimiser.fleet:
        vehicles.append({
            "id": v.vehicle_id,
            "model": v.model,
            "ready": v.is_ready,
            "cost": v.tco_cost_eur,
            "v2g_revenue": v.v2g_revenue_eur
        })
        
    return {
        "metrics": metrics,
        "vehicles": vehicles,
        "depot_name": os.getenv("EV_DEPOT_NAME", ev.DEPOT_NAME)
    }

# ── STATIC DASHBOARD ──────────────────────────────────────────────────────────

# Ensure the static directory exists
os.makedirs("static", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)

# Mount the static directory to serve HTML, CSS, JS
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    """Redirect root to the static dashboard."""
    return RedirectResponse(url="/static/index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"Starting server on port {port}...")
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
