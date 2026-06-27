"""
================================================================================
  NextGen Energy Suite  ⚡  v3.0
  Module 2 — MicroGrid Peer-to-Peer (P2P) Energy Trading Engine
  ─────────────────────────────────────────────────────────────────────────────
  Problem  : Prosumers (consumers with solar / battery storage) sell surplus
             energy to the utility grid at sub-optimal feed-in tariffs
             (e.g. €0.08/kWh) while neighbours buy from the same grid at
             retail (€0.28/kWh). The spread is community value wasted.

  Solution : A full virtual energy marketplace operating inside a defined
             microgrid boundary:
               • Bilateral double-auction price discovery (mid-point clearing)
               • Multi-round matching engine (residual unmatched volume
                 re-enters the next round)
               • Blockchain-style immutable trade ledger with UUID trade IDs
               • Per-participant settlement with grid-only baseline comparison
               • Battery storage arbitrage signals for prosumers
               • Welfare analysis (consumer surplus, producer surplus)
               • Grid fallback for any unmet residual demand

  Algorithms   : Double auction · Greedy volume matching · Welfare surplus
  Dependencies : none (pure Python stdlib)
  Python       : 3.10+
  Run          : python microgrid_p2p_trader.py
================================================================================
"""

import sys
import uuid
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from collections import defaultdict

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VERSION = "3.0.0"

# ═══════════════════════════════════════════════════════════════════════════════
#  MARKET CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

GRID_IMPORT_PRICE     = 0.28    # €/kWh — retail price (consumers)
GRID_EXPORT_PRICE     = 0.08    # €/kWh — feed-in tariff (producers)
P2P_PRICE_FLOOR       = 0.10    # €/kWh — minimum clearing price
P2P_PRICE_CEILING     = 0.25    # €/kWh — maximum clearing price
PLATFORM_FEE_PCT      = 0.015   # 1.5 % — platform clearing fee
GRID_CARBON_KG_KWH    = 0.34    # kg CO₂/kWh avoided when trading locally
CARBON_PRICE_EUR_KG   = 0.065   # EU ETS proxy for carbon value
MAX_ROUNDS            = 5       # max matching rounds per session
NETWORK_LOSS_PCT      = 0.005   # 0.5 % distribution loss per trade
SETTLEMENT_PERIOD     = "Hourly"
MICROGRID_NAME        = "Helios Community MicroGrid — Zone 7"


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Participant:
    """One prosumer / consumer node on the virtual microgrid bus."""
    name:             str
    node_id:          str
    has_solar:        bool
    has_battery:      bool
    solar_generation: float    # kWh available this period
    consumption:      float    # kWh required this period
    battery_storage:  float    # kWh in battery available to sell
    min_ask_price:    float    # €/kWh — producer floor price
    max_bid_price:    float    # €/kWh — consumer ceiling price
    location:         str = "" # optional district tag

    # ── Runtime state ────────────────────────────────────────────────────────
    energy_sold:       float = field(default=0.0)
    energy_bought:     float = field(default=0.0)
    revenue_eur:       float = field(default=0.0)
    spending_eur:      float = field(default=0.0)
    fees_paid_eur:     float = field(default=0.0)
    grid_fallback_kwh: float = field(default=0.0)
    trades_as_seller:  int   = field(default=0)
    trades_as_buyer:   int   = field(default=0)

    @property
    def available_to_sell(self) -> float:
        total_supply = self.solar_generation + self.battery_storage
        net          = total_supply - self.consumption - self.energy_sold
        return max(0.0, round(net, 6))

    @property
    def still_needs(self) -> float:
        return max(0.0, round(self.consumption - self.energy_bought, 6))

    @property
    def net_position(self) -> float:
        """Positive = net seller, negative = net buyer."""
        return self.energy_sold - self.energy_bought

    @property
    def self_sufficiency_pct(self) -> float:
        """% of own consumption met by own generation."""
        own_met = min(self.solar_generation + self.battery_storage, self.consumption)
        return own_met / self.consumption * 100 if self.consumption else 0.0

    @property
    def is_prosumer(self) -> bool:
        return self.has_solar or self.has_battery


@dataclass(frozen=True)
class TradeRecord:
    """Immutable ledger entry for one cleared bilateral trade."""
    trade_id:         str
    round_num:        int
    timestamp:        str
    seller_id:        str
    seller_name:      str
    buyer_id:         str
    buyer_name:       str
    offered_kwh:      float    # gross energy offered
    energy_kwh:       float    # net after distribution loss
    loss_kwh:         float    # network distribution loss
    price_eur_kwh:    float
    gross_value_eur:  float
    platform_fee_eur: float
    net_value_eur:    float
    carbon_avoided_kg:float
    carbon_value_eur: float
    consumer_surplus: float    # (grid_import_price - clearing_price) × kWh
    producer_surplus: float    # (clearing_price - grid_export_price) × kWh


# ═══════════════════════════════════════════════════════════════════════════════
#  PRICE DISCOVERY — Bilateral Double Auction
# ═══════════════════════════════════════════════════════════════════════════════

def discover_clearing_price(seller: Participant, buyer: Participant) -> Optional[float]:
    """
    Mid-point bilateral double auction.
    A deal clears only if seller's ask ≤ buyer's bid AND both are within
    the market's price corridor [P2P_PRICE_FLOOR, P2P_PRICE_CEILING].
    Returns the clearing price or None if no overlap.
    """
    effective_ask = max(seller.min_ask_price, P2P_PRICE_FLOOR)
    effective_bid = min(buyer.max_bid_price,  P2P_PRICE_CEILING)

    if effective_ask > effective_bid:
        return None   # price gap — no deal possible

    clearing = round((effective_ask + effective_bid) / 2, 4)
    return clearing


# ═══════════════════════════════════════════════════════════════════════════════
#  MULTI-ROUND CLEARING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class P2PClearingEngine:
    """
    Full P2P clearing engine with:
      • Multi-round matching (residuals re-enter)
      • Distribution loss deduction
      • Per-trade welfare surplus calculation
      • Platform fee collection
      • Grid fallback for unmatched demand
    """

    def __init__(self, participants: list[Participant]):
        self.participants      = participants
        self.ledger:     list[TradeRecord] = []
        self.platform_revenue  = 0.0
        self.grid_import_total = 0.0
        self.round_stats: list[dict] = []

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _ranked_sellers(self) -> list[Participant]:
        return sorted(
            [p for p in self.participants if p.available_to_sell > 0.0001],
            key=lambda p: (p.min_ask_price, -p.available_to_sell)
        )

    def _ranked_buyers(self) -> list[Participant]:
        return sorted(
            [p for p in self.participants if p.still_needs > 0.0001],
            key=lambda p: (-p.max_bid_price, -p.still_needs)
        )

    def _make_trade(self, seller: Participant, buyer: Participant,
                    price: float, round_num: int) -> TradeRecord:
        """Execute one bilateral trade and return an immutable record."""
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        offered  = round(min(seller.available_to_sell, buyer.still_needs), 4)
        loss     = round(offered * NETWORK_LOSS_PCT, 4)
        net_kwh  = round(offered - loss, 4)

        gross    = round(offered * price, 4)
        fee      = round(gross   * PLATFORM_FEE_PCT, 4)
        net_val  = round(gross   - fee, 4)
        carbon   = round(net_kwh * GRID_CARBON_KG_KWH, 4)
        co2_val  = round(carbon  * CARBON_PRICE_EUR_KG, 4)
        c_surplus= round((GRID_IMPORT_PRICE - price) * net_kwh, 4)   # buyer benefit
        p_surplus= round((price - GRID_EXPORT_PRICE)  * offered, 4)  # seller benefit

        # Update balances
        seller.energy_sold   += offered
        seller.revenue_eur   += net_val * (1 - PLATFORM_FEE_PCT / 2)
        seller.fees_paid_eur += fee / 2
        seller.trades_as_seller += 1

        buyer.energy_bought  += net_kwh       # buyer receives net_kwh (after loss)
        buyer.spending_eur   += gross
        buyer.fees_paid_eur  += fee / 2
        buyer.trades_as_buyer += 1

        self.platform_revenue += fee

        return TradeRecord(
            trade_id         = str(uuid.uuid4())[:8].upper(),
            round_num        = round_num,
            timestamp        = ts,
            seller_id        = seller.node_id,
            seller_name      = seller.name,
            buyer_id         = buyer.node_id,
            buyer_name       = buyer.name,
            offered_kwh      = offered,
            energy_kwh       = net_kwh,
            loss_kwh         = loss,
            price_eur_kwh    = price,
            gross_value_eur  = gross,
            platform_fee_eur = fee,
            net_value_eur    = net_val,
            carbon_avoided_kg= carbon,
            carbon_value_eur = co2_val,
            consumer_surplus = c_surplus,
            producer_surplus = p_surplus,
        )

    # ── Main clearing loop ───────────────────────────────────────────────────

    def run(self) -> int:
        """Run up to MAX_ROUNDS of bilateral clearing. Returns total trades."""
        total_trades = 0

        for rnd in range(1, MAX_ROUNDS + 1):
            sellers = self._ranked_sellers()
            buyers  = self._ranked_buyers()
            if not sellers or not buyers:
                break

            round_trades = 0
            for seller in sellers:
                for buyer in buyers:
                    if seller.node_id == buyer.node_id:
                        continue
                    if seller.available_to_sell < 0.0001:
                        break
                    if buyer.still_needs < 0.0001:
                        continue

                    price = discover_clearing_price(seller, buyer)
                    if price is None:
                        continue

                    record = self._make_trade(seller, buyer, price, rnd)
                    self.ledger.append(record)
                    round_trades += 1
                    total_trades  += 1

            self.round_stats.append({"round": rnd, "trades": round_trades,
                                     "energy_kwh": sum(t.energy_kwh for t in self.ledger)})
            if round_trades == 0:
                break   # No more matching possible — stop early

        # ── Grid fallback for any remaining unmet demand ─────────────────────
        for p in self.participants:
            if p.still_needs > 0.0001:
                fallback_kwh     = p.still_needs
                p.grid_fallback_kwh = fallback_kwh
                p.spending_eur   += fallback_kwh * GRID_IMPORT_PRICE
                self.grid_import_total += fallback_kwh

        return total_trades

    # ══════════════════════════════════════════════════════════════════════════
    #  REPORTS
    # ══════════════════════════════════════════════════════════════════════════

    def print_market_open(self):
        _hdr("⚡ MARKET SESSION OPEN")
        print(f"  Microgrid       : {MICROGRID_NAME}")
        print(f"  Participants    : {len(self.participants)}  "
              f"({sum(1 for p in self.participants if p.is_prosumer)} prosumers, "
              f"{sum(1 for p in self.participants if not p.is_prosumer)} pure consumers)")
        print(f"  Grid import     : €{GRID_IMPORT_PRICE:.3f}/kWh")
        print(f"  Feed-in tariff  : €{GRID_EXPORT_PRICE:.3f}/kWh")
        print(f"  P2P corridor    : €{P2P_PRICE_FLOOR:.3f}–€{P2P_PRICE_CEILING:.3f}/kWh")
        print(f"  Platform fee    : {PLATFORM_FEE_PCT*100:.1f}%")
        print(f"  Network loss    : {NETWORK_LOSS_PCT*100:.1f}%")
        print(f"  Carbon price    : €{CARBON_PRICE_EUR_KG:.3f}/kg (EU ETS proxy)")
        print()
        print(f"  {'Node':<10}  {'Name':<32}  {'Supply kWh':>10}  {'Need kWh':>9}  "
              f"{'Min Ask':>8}  {'Max Bid':>8}  Self-suf")
        print("  " + "─" * 90)
        for p in self.participants:
            supply = p.solar_generation + p.battery_storage
            tag    = "🌞" if p.has_solar else ("🔋" if p.has_battery else "🏠")
            print(f"  {p.node_id:<10}  {tag} {p.name:<30}  {supply:>10.2f}  {p.consumption:>9.2f}  "
                  f"  €{p.min_ask_price:.3f}    €{p.max_bid_price:.3f}  {p.self_sufficiency_pct:.0f}%")
        print()

    def print_round_summary(self):
        _hdr("🔄 CLEARING ROUNDS")
        for rs in self.round_stats:
            bar = "█" * rs["trades"]
            print(f"  Round {rs['round']:>2}  {rs['trades']:>3} trade(s)  "
                  f"Cumulative: {rs['energy_kwh']:.3f} kWh  {bar}")
        print()

    def print_trade_ledger(self):
        _hdr("📒 TRADE LEDGER — IMMUTABLE SESSION LOG")
        if not self.ledger:
            print("  ⚠️  No trades cleared this session.\n"); return

        print(f"  {'ID':>8}  {'Rnd':>3}  {'Seller':<26}  {'Buyer':<26}  "
              f"{'Offered':>8}  {'Net kWh':>8}  {'€/kWh':>7}  {'Net €':>9}  "
              f"{'CO₂↓ kg':>8}  {'CO₂ €':>7}")
        print("  " + "─" * 110)
        for t in self.ledger:
            print(f"  {t.trade_id:>8}  {t.round_num:>3}  "
                  f"{t.seller_name:<26}  {t.buyer_name:<26}  "
                  f"{t.offered_kwh:>8.3f}  {t.energy_kwh:>8.3f}  "
                  f"{t.price_eur_kwh:>7.4f}  {t.net_value_eur:>9.4f}  "
                  f"{t.carbon_avoided_kg:>8.3f}  {t.carbon_value_eur:>7.4f}")
        print("  " + "─" * 110)
        tot_off   = sum(t.offered_kwh      for t in self.ledger)
        tot_net   = sum(t.energy_kwh       for t in self.ledger)
        tot_loss  = sum(t.loss_kwh         for t in self.ledger)
        tot_gross = sum(t.gross_value_eur  for t in self.ledger)
        tot_carb  = sum(t.carbon_avoided_kg for t in self.ledger)
        tot_c_val = sum(t.carbon_value_eur  for t in self.ledger)
        print(f"  {'TOTALS':>8}  {'':3}  {'':26}  {'':26}  "
              f"{tot_off:>8.3f}  {tot_net:>8.3f}  {'':7}  {tot_gross:>9.4f}  "
              f"{tot_carb:>8.3f}  {tot_c_val:>7.4f}")
        print(f"\n  Network distribution losses : {tot_loss:.3f} kWh ({NETWORK_LOSS_PCT*100:.1f}%)")
        print()

    def print_participant_settlement(self):
        _hdr("💳 PARTICIPANT SETTLEMENT STATEMENTS")
        for p in self.participants:
            icon = "🌞" if p.has_solar else ("🔋" if p.has_battery else "🏠")
            tag  = "PROSUMER" if p.is_prosumer else "CONSUMER"
            print(f"\n  {icon} {tag}  ·  {p.name}  [{p.node_id}]")
            if p.location:
                print(f"  Location: {p.location}")
            print(f"  {'─' * 65}")
            print(f"     Solar generation       : {p.solar_generation:>8.3f} kWh")
            print(f"     Battery storage (avail): {p.battery_storage:>8.3f} kWh")
            print(f"     Consumption need       : {p.consumption:>8.3f} kWh")
            print(f"     Self-sufficiency       : {p.self_sufficiency_pct:>8.1f} %")
            print()
            print(f"     ── P2P Trading Activity ────────────────────────────")
            print(f"     Energy sold  (P2P)     : {p.energy_sold:>8.3f} kWh  → Revenue  €{p.revenue_eur:.4f}")
            print(f"     Energy bought(P2P)     : {p.energy_bought:>8.3f} kWh  → Cost     €{p.spending_eur:.4f}")
            print(f"     Trades as seller       : {p.trades_as_seller:>8d}")
            print(f"     Trades as buyer        : {p.trades_as_buyer:>8d}")
            if p.grid_fallback_kwh > 0.0001:
                gf_cost = p.grid_fallback_kwh * GRID_IMPORT_PRICE
                print(f"     Grid fallback (import) : {p.grid_fallback_kwh:>8.3f} kWh  → Cost     €{gf_cost:.4f}")
            print(f"     Platform fees paid     :         €{p.fees_paid_eur:.4f}")

            # ── Grid-only baseline comparison ────────────────────────────────
            print(f"\n     ── vs. Grid-Only Baseline ──────────────────────────")
            grid_cost_baseline = p.consumption * GRID_IMPORT_PRICE
            grid_rev_baseline  = max(0.0,
                (p.solar_generation + p.battery_storage - p.consumption) * GRID_EXPORT_PRICE)
            p2p_net = p.revenue_eur - p.spending_eur - p.fees_paid_eur
            grid_net = grid_rev_baseline - grid_cost_baseline
            benefit  = p2p_net - grid_net

            print(f"     Grid-only cost         : €{grid_cost_baseline:.4f}")
            print(f"     Grid-only FiT revenue  : €{grid_rev_baseline:.4f}")
            print(f"     Grid-only net          : €{grid_net:.4f}")
            print(f"     P2P net                : €{p2p_net:.4f}")
            print(f"     P2P net benefit        : €{benefit:+.4f}  "
                  f"{'✅ BETTER' if benefit >= 0 else '❌ WORSE'} than grid-only")
        print()

    def print_welfare_analysis(self):
        _hdr("📊 MARKET WELFARE ANALYSIS")
        cs = sum(t.consumer_surplus  for t in self.ledger)
        ps = sum(t.producer_surplus  for t in self.ledger)
        total_energy = sum(t.energy_kwh for t in self.ledger)
        avg_price    = (sum(t.price_eur_kwh * t.energy_kwh for t in self.ledger)
                        / total_energy) if total_energy else 0.0
        total_demand = sum(p.consumption for p in self.participants)
        local_cover  = total_energy / total_demand * 100 if total_demand else 0.0
        total_co2    = sum(t.carbon_avoided_kg for t in self.ledger)

        print(f"  Consumer surplus (total)  : €{cs:.4f}")
        print(f"  Producer surplus (total)  : €{ps:.4f}")
        print(f"  Total welfare gain        : €{cs + ps:.4f}")
        print(f"  Platform revenue          : €{self.platform_revenue:.4f}")
        print()
        print(f"  Volume-weighted avg price : €{avg_price:.4f}/kWh")
        print(f"  Grid-import price         : €{GRID_IMPORT_PRICE:.4f}/kWh")
        print(f"  Consumer saving vs grid   : €{(GRID_IMPORT_PRICE - avg_price) * total_energy:.4f}")
        print(f"  Producer gain vs FiT      : €{(avg_price - GRID_EXPORT_PRICE) * total_energy:.4f}")
        print()
        print(f"  Local energy coverage     : {local_cover:.1f}%  (P2P/total demand)")
        print(f"  Grid import fallback      : {self.grid_import_total:.3f} kWh")
        print(f"  CO₂ avoided               : {total_co2:.3f} kg  "
              f"(≡ {total_co2/21:.2f} trees × 1 day)")
        print(f"  Carbon value captured     : €{total_co2 * CARBON_PRICE_EUR_KG:.4f}")

        # Annualised projections
        daily_welfare = cs + ps
        print(f"\n  📅 ANNUAL PROJECTIONS")
        print(f"     Annual welfare gain (est.)  : €{daily_welfare * 365:.2f}")
        print(f"     Annual CO₂ avoided (est.)   : {total_co2 * 365:,.1f} kg/year")
        print()


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

W = 78
def _div(c="═"):   print(c * W)
def _hdr(t: str):  _div(); print(f"  {t}"); _div()


# ═══════════════════════════════════════════════════════════════════════════════
#  SCENARIO — HELIOS COMMUNITY MICROGRID
# ═══════════════════════════════════════════════════════════════════════════════

def build_neighborhood() -> list[Participant]:
    return [
        Participant(
            name="Sunrise Villa",    node_id="NODE-A1",
            has_solar=True,          has_battery=True,
            solar_generation=28.5,   consumption=9.0,   battery_storage=8.0,
            min_ask_price=0.10,      max_bid_price=0.24,
            location="Block A — South-facing rooftop 6 kWp",
        ),
        Participant(
            name="Green Terrace",    node_id="NODE-B2",
            has_solar=True,          has_battery=False,
            solar_generation=16.0,   consumption=11.0,  battery_storage=0.0,
            min_ask_price=0.11,      max_bid_price=0.23,
            location="Block B — West-facing 4 kWp array",
        ),
        Participant(
            name="Urban Flat 3C",    node_id="NODE-C3",
            has_solar=False,         has_battery=False,
            solar_generation=0.0,    consumption=14.5,  battery_storage=0.0,
            min_ask_price=0.28,      max_bid_price=0.22,
            location="Block C — No generation assets",
        ),
        Participant(
            name="Corner Shop",      node_id="NODE-D4",
            has_solar=False,         has_battery=False,
            solar_generation=0.0,    consumption=20.0,  battery_storage=0.0,
            min_ask_price=0.28,      max_bid_price=0.21,
            location="Block D — Retail + EV charger",
        ),
        Participant(
            name="Eco-Home E5",      node_id="NODE-E5",
            has_solar=True,          has_battery=True,
            solar_generation=12.0,   consumption=8.0,   battery_storage=5.0,
            min_ask_price=0.12,      max_bid_price=0.22,
            location="Block E — Bifacial panels 3 kWp + 10 kWh BESS",
        ),
        Participant(
            name="Industrial Unit F6",node_id="NODE-F6",
            has_solar=False,         has_battery=False,
            solar_generation=0.0,    consumption=35.0,  battery_storage=0.0,
            min_ask_price=0.28,      max_bid_price=0.20,
            location="Block F — Light manufacturing, 3-phase supply",
        ),
        Participant(
            name="Community Hall G7",node_id="NODE-G7",
            has_solar=True,          has_battery=False,
            solar_generation=10.0,   consumption=6.0,   battery_storage=0.0,
            min_ask_price=0.11,      max_bid_price=0.23,
            location="Block G — Roof-mounted 2.5 kWp civic installation",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print()
    _div()
    print(f"  ⚡  NextGen Energy Suite  v{VERSION}  |  MicroGrid P2P Trading Engine")
    print(f"  📅  {datetime.today().strftime('%A, %d %B %Y')}")
    _div()
    print()

    neighborhood = build_neighborhood()
    engine       = P2PClearingEngine(neighborhood)

    engine.print_market_open()

    n = engine.run()
    print(f"  ✅  Clearing complete — {n} trade(s) matched across "
          f"{len(engine.round_stats)} round(s).\n")

    engine.print_round_summary()
    engine.print_trade_ledger()
    engine.print_participant_settlement()
    engine.print_welfare_analysis()

    _div("─")
    print(f"  NextGen Energy Suite v{VERSION}  |  Module 2: MicroGrid P2P Trading Engine")
    print(f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  GitHub    : https://github.com/john724/nextgen-energy-suite")
    _div("─")


if __name__ == "__main__":
    main()
