def optimize_charging_schedule(battery_capacity_needed, time_window_hours, hourly_prices):
    print("\n=== [EV Fleet Smart Charging Optimizer] ===")
    
    # Σύνδεση ωρών με τις τιμές τους
    indexed_prices = list(enumerate(hourly_prices[:time_window_hours]))
    # Ταξινόμηση ωρών από τη φθηνότερη στην ακριβότερη
    cheapest_hours = sorted(indexed_prices, key=lambda x: x[1])
    
    charge_rate_per_hour = 11 # 11 kW τυπικός φορτιστής AC
    energy_charged = 0
    total_cost = 0
    scheduled_hours = []
    
    for hour, price in cheapest_hours:
        if energy_charged >= battery_capacity_needed:
            break
        needed = battery_capacity_needed - energy_charged
        actual_charge = min(charge_rate_per_hour, needed)
        
        energy_charged += actual_charge
        total_cost += actual_charge * price
        scheduled_hours.append(hour)
        
    print(f"🔋 Target: {battery_capacity_needed}kWh within {time_window_hours} hours.")
    print(f"📅 Optimal Charging Hours (Sorted by priority): {scheduled_hours}")
    print(f"💰 Minimum Calculated Charging Cost: €{total_cost:.2f}")

grid_prices = [0.22, 0.20, 0.15, 0.12, 0.11, 0.14, 0.25, 0.30, 0.28, 0.22] # Τιμές νύχτας/πρωί
optimize_charging_schedule(battery_capacity_needed=45, time_window_hours=8, hourly_prices=grid_prices)
