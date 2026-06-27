"""
================================================================================
  NextGen Energy Suite — Machine Learning Engine (v3.2)
  ─────────────────────────────────────────────────────────────────────────────
  Simulates a real-world ML pipeline by generating synthetic historical data,
  training predictive models (Random Forest for load, MLP for price), and
  saving them for inference by the optimization modules.
================================================================================
"""

import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

# ── DATA GENERATION (Synthetic Historical Data) ───────────────────────────────

def generate_historical_data(days=365):
    """Generates 1 year of synthetic hourly data for training."""
    print(f"🧠 Generating {days} days of synthetic historical training data...")
    base_date = datetime(2025, 1, 1)
    
    records = []
    for d in range(days):
        current_date = base_date + timedelta(days=d)
        is_weekend = 1 if current_date.weekday() >= 5 else 0
        
        # Base daily temperature curve (colder at night, warmer in afternoon)
        # Add seasonal variation (summer hotter, winter colder)
        season_offset = math.sin((d / 365.0) * 2 * math.pi) * 10
        base_temp = 15 + season_offset
        
        for h in range(24):
            # Hour features
            temp = base_temp + (math.sin((h - 6) / 24.0 * 2 * math.pi) * 5) + random.uniform(-2, 2)
            solar_irradiance = max(0, math.sin((h - 6) / 12.0 * math.pi)) if 6 <= h <= 18 else 0
            
            # Load Simulation
            # Base load is lower on weekends and at night
            if is_weekend:
                load = 15 + random.uniform(0, 5)
            else:
                if 6 <= h <= 18:
                    load = 60 + (temp - 15)*0.5 + random.uniform(-10, 15)  # AC load correlates with temp
                else:
                    load = 20 + random.uniform(0, 10)
            
            # Spot Price Simulation (EPEX style)
            # Prices spike during morning (8-10) and evening (18-20) peaks, drop at night
            base_price = 0.10
            if 7 <= h <= 11 or 17 <= h <= 21:
                base_price = 0.25 + random.uniform(0.05, 0.15)
            elif 12 <= h <= 16:
                base_price = 0.20 - (solar_irradiance * 0.05) + random.uniform(-0.02, 0.05)
            else:
                base_price = 0.08 + random.uniform(0.01, 0.05)
                
            records.append({
                "hour": h,
                "is_weekend": is_weekend,
                "temperature": round(temp, 1),
                "solar_irradiance": round(solar_irradiance, 2),
                "target_load_kw": round(max(5, load), 1),
                "target_price_eur": round(max(0.01, base_price), 3)
            })
            
    return pd.DataFrame(records)

# ── MODEL TRAINING ────────────────────────────────────────────────────────────

def train_and_save_models():
    """Trains the ML models and saves them to the models/ directory."""
    if not ML_AVAILABLE:
        print("❌ scikit-learn is not installed. Run: pip install scikit-learn joblib")
        return False
        
    os.makedirs(MODELS_DIR, exist_ok=True)
    
    df = generate_historical_data()
    
    print("🧠 Training Consumption Predictor (Random Forest)...")
    X_load = df[["hour", "is_weekend", "temperature"]]
    y_load = df["target_load_kw"]
    
    rf_model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
    rf_model.fit(X_load, y_load)
    joblib.dump(rf_model, os.path.join(MODELS_DIR, "consumption_model.joblib"))
    
    print("🧠 Training Price Forecaster (Neural Network MLP)...")
    X_price = df[["hour", "is_weekend", "solar_irradiance"]]
    y_price = df["target_price_eur"]
    
    # Scale features for MLP
    scaler = StandardScaler()
    X_price_scaled = scaler.fit_transform(X_price)
    
    mlp_model = MLPRegressor(hidden_layer_sizes=(32, 16), max_iter=500, random_state=42)
    mlp_model.fit(X_price_scaled, y_price)
    
    joblib.dump(mlp_model, os.path.join(MODELS_DIR, "price_model.joblib"))
    joblib.dump(scaler, os.path.join(MODELS_DIR, "price_scaler.joblib"))
    
    print("✅ Models trained and saved successfully to models/")
    return True

# ── INFERENCE / PREDICTION ────────────────────────────────────────────────────

def generate_tomorrow_forecast():
    """Uses the trained models to predict load and price for the next 24 hours."""
    if not ML_AVAILABLE:
        raise ImportError("scikit-learn is required for ML inference.")
        
    try:
        rf_model = joblib.load(os.path.join(MODELS_DIR, "consumption_model.joblib"))
        mlp_model = joblib.load(os.path.join(MODELS_DIR, "price_model.joblib"))
        scaler = joblib.load(os.path.join(MODELS_DIR, "price_scaler.joblib"))
    except FileNotFoundError:
        print("⚠️  Models not found. Training new models on the fly...")
        train_and_save_models()
        rf_model = joblib.load(os.path.join(MODELS_DIR, "consumption_model.joblib"))
        mlp_model = joblib.load(os.path.join(MODELS_DIR, "price_model.joblib"))
        scaler = joblib.load(os.path.join(MODELS_DIR, "price_scaler.joblib"))

    # Simulate tomorrow's weather forecast (typical weekday)
    tomorrow_is_weekend = 0
    predictions = []
    
    for h in range(24):
        # Tomorrow's simulated weather
        temp = 18 + (math.sin((h - 6) / 24.0 * 2 * math.pi) * 6)
        solar = max(0, math.sin((h - 6) / 12.0 * math.pi)) if 6 <= h <= 18 else 0
        
        # Predict Load
        X_load = pd.DataFrame([{"hour": h, "is_weekend": tomorrow_is_weekend, "temperature": temp}])
        pred_load = rf_model.predict(X_load)[0]
        
        # Predict Price
        X_price = pd.DataFrame([{"hour": h, "is_weekend": tomorrow_is_weekend, "solar_irradiance": solar}])
        X_price_scaled = scaler.transform(X_price)
        pred_price = mlp_model.predict(X_price_scaled)[0]
        
        predictions.append({
            "hour": h,
            "predicted_consumption_kw": round(max(5, pred_load), 1),
            "predicted_spot_price_eur": round(max(0.01, pred_price), 3)
        })
        
    df_forecast = pd.DataFrame(predictions)
    return df_forecast["predicted_consumption_kw"].tolist(), df_forecast["predicted_spot_price_eur"].tolist()

if __name__ == "__main__":
    import math # required for local execution context if math wasn't globally scoped properly but it is
    train_and_save_models()
