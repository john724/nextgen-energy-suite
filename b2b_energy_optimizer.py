import pandas as pd
import numpy as np

# Προσομοίωση δεδομένων κατανάλωσης (σε kW) και τιμών ρεύματος (€/kWh)
hours = list(range(24))
consumption = [12, 11, 10, 9, 15, 25, 40, 55, 60, 65, 70, 75, 80, 78, 75, 70, 65, 50, 45, 35, 30, 25, 18, 14]
energy_prices = [0.10, 0.09, 0.08, 0.08, 0.11, 0.15, 0.22, 0.28, 0.30, 0.32, 0.35, 0.35, 0.32, 0.30, 0.28, 0.26, 0.25, 0.28, 0.32, 0.30, 0.22, 0.18, 0.14, 0.12]

df = pd.DataFrame({'Hour': hours, 'Consumption_kW': consumption, 'Price_EUR': energy_prices})

def generate_savings_recommendations(data):
    print("=== [AI B2B Energy Optimizer] Analyzing Consumption Patterns ===")
    threshold_price = data['Price_EUR'].quantile(0.75) # Το 25% των πιο ακριβών ωρών
    
    for index, row in data.iterrows():
        if row['Price_EUR'] >= threshold_price and row['Consumption_kW'] > 50:
            potential_savings = row['Consumption_kW'] * 0.20 * row['Price_EUR'] # Υπόθεση 20% μείωσης φορτίου
            print( f"⚠️ Hour {int(row['Hour'])}:00 -> High Price Alert (€{row['Price_EUR']}/kWh). "
                   f"Recommendation: Turn off non-essential HVAC/Cooling units. Est. Savings: €{potential_savings:.2f}")

generate_savings_recommendations(df)
