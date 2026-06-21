import random

class MicrogridParticipant:
    def __init__(self, name, is_producer, energy_balance):
        self.name = name
        self.is_producer = is_producer # True αν έχει φωτοβολταϊκά
        self.energy_balance = energy_balance # Θετικό = Πλεόνασμα, Αρνητικό = Ανάγκη

def execute_p2p_trades(participants):
    print("\n=== [MicroGrid P2P Energy Trading Engine] ===")
    producers = [p for p in participants if p.energy_balance > 0]
    consumers = [p for p in participants if p.energy_balance < 0]
    
    fixed_p2p_price = 0.15 # Πιο φθηνά από το δίκτυο, πιο κερδοφόρα για τον παραγωγό
    
    for prod in producers:
        for cons in consumers:
            if prod.energy_balance == 0: break
            if cons.energy_balance == 0: continue
            
            traded_energy = min(prod.energy_balance, abs(cons.energy_balance))
            prod.energy_balance -= traded_energy
            cons.energy_balance += traded_energy
            
            print(f"⚡ Trade Cleared: {prod.name} sold {traded_energy}kWh to {cons.name} at €{fixed_p2p_price}/kWh.")

# Δημιουργία γειτονιάς
neighborhood = [
    MicrogridParticipant("House_A (Solar)", True, 15.5),
    MicrogridParticipant("House_B (Solar)", True, 8.0),
    MicrogridParticipant("House_C (No Solar)", False, -12.0),
    MicrogridParticipant("House_D (No Solar)", False, -10.0)
]
execute_p2p_trades(neighborhood)
