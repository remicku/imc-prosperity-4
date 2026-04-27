"""
IMC Prosperity 4, round 3: trader v3.

- HYDROGEL_PACK: mean reversion around a hardcoded fair value of 10,000.
- VELVETFRUIT_EXTRACT (VEV): market making around the volume-weighted mid.
- VEV_* calls: Black-Scholes fair values with sigma calibrated on the
  historical data (0.287 annualized, mean error near zero, MAE 2.37) plus a
  per-strike bias correction. Time to expiry counts down from 5 days, at one
  million ticks per day.

v1 -> v3: HYDROGEL size 10 -> 20, VEV_4500 edge 6 -> 3.5, options quoting
spread 1.5 -> 1.0. The v2 delta hedge through VEV was dropped: hedging a
mean-reverting underlying's own moves lost money in backtest.
"""

from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List, Optional
import json, math

# Constants

POSITION_LIMITS: Dict[str, int] = {
    "HYDROGEL_PACK":          200,
    "VELVETFRUIT_EXTRACT":    200,
    "VEV_4000":               300,
    "VEV_4500":               300,
    "VEV_5000":               300,
    "VEV_5100":               300,
    "VEV_5200":               300,
    "VEV_5300":               300,
    "VEV_5400":               300,
    "VEV_5500":               300,
    "VEV_6000":               300,
    "VEV_6500":               300,
}

SIGMA      = 0.287   # annualized volatility, calibrated (mean error near 0, MAE 2.37)
MM_SPREAD  = 1.0     # options half-spread when quoting (v1: 1.5)
SKEW_STR   = 1.5     # inventory skew strength
TAKE_EDGE  = 2.5     # minimum edge to take, above the calibration MAE

# Per-strike correction: market price minus Black-Scholes, measured on the historical data
STRIKE_BIAS: Dict[float, float] = {
    4000.0: 0.0, 4500.0: 0.0,
    5000.0: +0.2, 5100.0: -0.2, 5200.0: +0.0,
    5300.0: +0.3, 5400.0: -2.0, 5500.0: +0.4,
    6000.0: 0.0,  6500.0: 0.0,
}

# (half-spread, size, take edge) for the delta-one products
PRODUCT_PARAMS = {
    "HYDROGEL_PACK":       (8.0, 20, 4.0),   # v3: size 10 -> 20
    "VELVETFRUIT_EXTRACT": (2.5, 15, 1.5),
}

# (take edge, size) per strike
OPT_PARAMS: Dict[float, tuple] = {
    4000.0: (6.0, 5),
    4500.0: (3.5, 5),   # v3: edge 6 -> 3.5
    5000.0: (2.5, 10),
    5100.0: (2.5, 10),
    5200.0: (2.5, 10),
    5300.0: (2.5, 10),
    5400.0: (2.5, 10),
    5500.0: (2.5, 10),
}

SKIP_PRODUCTS = {"VEV_6000", "VEV_6500"}


# Black-Scholes without scipy

def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def bs_call(S: float, K: float, T: float, sigma: float) -> float:
    if T < 1e-7:
        return max(0.0, S - K)
    sq = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / sq
    d2 = d1 - sq
    return S * _ncdf(d1) - K * _ncdf(d2)


# Helpers

def weighted_mid(od: OrderDepth) -> Optional[float]:
    bids, asks = od.buy_orders, od.sell_orders
    if bids and asks:
        bb, ba = max(bids), min(asks)
        bv, av = abs(bids[bb]), abs(asks[ba])
        return (bb * av + ba * bv) / (bv + av)
    if bids: return float(max(bids))
    if asks: return float(min(asks))
    return None


def place_orders(
    product: str,
    pos: int,
    limit: int,
    fair: float,
    spread: float,
    size: int,
    take_edge: float,
    od: OrderDepth,
) -> List[Order]:
    orders: List[Order] = []

    # Take asks below fair minus edge
    for ask_px, ask_vol in sorted(od.sell_orders.items()):
        if ask_px > fair - take_edge:
            break
        cap = limit - pos
        if cap <= 0:
            break
        qty = min(abs(ask_vol), cap)
        orders.append(Order(product, ask_px, qty))
        pos += qty

    # Take bids above fair plus edge
    for bid_px, bid_vol in sorted(od.buy_orders.items(), reverse=True):
        if bid_px < fair + take_edge:
            break
        cap = limit + pos
        if cap <= 0:
            break
        qty = min(bid_vol, cap)
        orders.append(Order(product, bid_px, -qty))
        pos -= qty

    # Make with inventory skew
    ratio  = pos / limit
    skew   = ratio * spread * SKEW_STR
    bid_px = round(fair - spread - skew)
    ask_px = round(fair + spread - skew)

    if limit - pos > 0:
        orders.append(Order(product, bid_px, min(size, limit - pos)))
    if limit + pos > 0:
        orders.append(Order(product, ask_px, -min(size, limit + pos)))

    return orders


# Trader

class Trader:

    def run(self, state: TradingState):
        t      = state.timestamp
        result: Dict[str, List[Order]] = {}

        # 1. VEV fair value
        vev_fair: Optional[float] = None
        if "VELVETFRUIT_EXTRACT" in state.order_depths:
            vev_fair = weighted_mid(state.order_depths["VELVETFRUIT_EXTRACT"])
        if vev_fair is None:
            vev_fair = 5250.0

        # 2. Time to expiry. One calendar day is one million ticks, so a
        # round only burns about 0.1 day of theta.
        tte_years = max(0.001, 5.0 - t / 1_000_000.0) / 365.0

        # 3. Delta-one products
        for product in ["HYDROGEL_PACK", "VELVETFRUIT_EXTRACT"]:
            if product not in state.order_depths:
                continue
            od    = state.order_depths[product]
            pos   = state.position.get(product, 0)
            limit = POSITION_LIMITS[product]
            spr, sz, edge = PRODUCT_PARAMS[product]
            fair  = 10000.0 if product == "HYDROGEL_PACK" else vev_fair

            orders = place_orders(product, pos, limit, fair, spr, sz, edge, od)
            if orders:
                result[product] = orders

        # 4. Options
        for product, od in state.order_depths.items():
            if not product.startswith("VEV_"):
                continue
            if product in SKIP_PRODUCTS:
                continue

            K    = float(product.split("_")[1])
            bias = STRIKE_BIAS.get(K, 0.0)
            fair = bs_call(vev_fair, K, tte_years, SIGMA) + bias
            edge, sz = OPT_PARAMS.get(K, (TAKE_EDGE, 10))

            pos   = state.position.get(product, 0)
            limit = POSITION_LIMITS.get(product, 300)

            orders = place_orders(product, pos, limit, fair, MM_SPREAD, sz, edge, od)
            if orders:
                result[product] = orders

        self._log(state, result, t, vev_fair, tte_years * 365)
        return result, 0, ""

    def _log(self, state, result, t, vev_fair, tte_days):
        if t % 20000 != 0:
            return
        vev_s = f"{vev_fair:.1f}"
        print(f"\n-- t={t} | VEV={vev_s} | TTE={tte_days:.4f}d --")
        for product, orders in result.items():
            pos = state.position.get(product, 0)
            lim = POSITION_LIMITS.get(product, 300)
            takes = [o for o in orders if
                     (o.quantity > 0 and state.order_depths.get(product) and
                      o.price in state.order_depths[product].sell_orders) or
                     (o.quantity < 0 and state.order_depths.get(product) and
                      o.price in state.order_depths[product].buy_orders)]
            print(f"  {product:<30s} pos={pos:+4d}/{lim} takes={len(takes)}")
