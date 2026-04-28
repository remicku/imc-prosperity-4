"""
IMC Prosperity 4, round 4: trader v3.

Same book as round 3 (HYDROGEL_PACK, VELVETFRUIT_EXTRACT, VEV_* calls), with
sigma refitted to 0.24, per-strike biases remeasured, and two counterparty
signals read from the trade identities visible this round.

v3: VEV_5000 and VEV_5100 are no longer quoted. Their deltas (about 0.97 and
0.87) mean a full 300-contract position needs about 290 and 260 units of VEF
to hedge, above the 200 limit, so market making them is a directional bet on
VEF taken through a wider spread. Backtest P&L over the 3 historical days:

    VEV_5000  -5401  -14907    +238  = -20,070   removed
    VEV_5100  -4125   -8420  +10928  =  -1,617   removed
    VEV_5200  -2306   -5635  +14408  =  +6,467   kept, wider edge (delta 0.65)
    VEV_5300 / 5400 / 5500  net positive         kept

The remaining options book is delta hedged through VEF: the VEF quotes are
skewed toward the hedge target.
"""

from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List, Optional
import math

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

VEF_LIMIT = 200
SIGMA     = 0.24

STRIKE_BIAS: Dict[float, float] = {
    4000.0:  0.0,
    4500.0:  0.0,
    5000.0: +0.2,   # not quoted
    5100.0: -0.4,   # not quoted
    5200.0: +0.6,
    5300.0: +1.6,
    5400.0: -1.5,
    5500.0: +0.7,
}

TAKE_EDGE = 2.5
MM_SPREAD = 1.5
SKEW_STR  = 1.5

# Not quoted: delta that cannot be hedged within the VEF limit, or worthless
SKIP_PRODUCTS = {
    "VEV_5000",   # delta about 0.975: about 292 VEF per 300 contracts
    "VEV_5100",   # delta about 0.878: about 263 VEF per 300 contracts
    "VEV_6000",   # worthless
    "VEV_6500",   # worthless
}

# (half-spread, size, take edge) for the delta-one products
PRODUCT_PARAMS = {
    "HYDROGEL_PACK":       (6.0, 12, 4.0),
    "VELVETFRUIT_EXTRACT": (2.5, 15, 1.5),
}


# Black-Scholes

def _nc(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def bs_call(S: float, K: float, T: float, sigma: float) -> float:
    if T < 1e-6: return max(0.0, S - K)
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    return S * _nc(d1) - K * _nc(d1 - sigma * math.sqrt(T))

def bs_delta(S: float, K: float, T: float, sigma: float) -> float:
    if T < 1e-6: return 1.0 if S > K else 0.0
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    return _nc(d1)


# Helpers

def weighted_mid(od: OrderDepth) -> Optional[float]:
    b, a = od.buy_orders, od.sell_orders
    if b and a:
        bb, ba = max(b), min(a)
        return (bb * abs(a[ba]) + ba * abs(b[bb])) / (abs(b[bb]) + abs(a[ba]))
    if b: return float(max(b))
    if a: return float(min(a))
    return None


def place_orders(
    product:    str,
    pos:        int,
    limit:      int,
    fair:       float,
    spread:     float,
    size:       int,
    take_edge:  float,
    od:         OrderDepth,
    target_pos: int = 0,
) -> List[Order]:
    orders: List[Order] = []

    # Take
    for ask_px, ask_vol in sorted(od.sell_orders.items()):
        if ask_px > fair - take_edge: break
        cap = limit - pos
        if cap <= 0: break
        qty = min(abs(ask_vol), cap)
        orders.append(Order(product, ask_px, qty))
        pos += qty

    for bid_px, bid_vol in sorted(od.buy_orders.items(), reverse=True):
        if bid_px < fair + take_edge: break
        cap = limit + pos
        if cap <= 0: break
        qty = min(bid_vol, cap)
        orders.append(Order(product, bid_px, -qty))
        pos -= qty

    # Make, skewed relative to target_pos
    ratio = (pos - target_pos) / limit
    skew  = ratio * spread * SKEW_STR
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
        result = {}

        # Active counterparties
        mark01_active = any(
            tr.buyer == "Mark 01"
            for trades in state.market_trades.values()
            for tr in trades
        )
        mark67_buying = any(
            tr.buyer == "Mark 67" and prod == "VELVETFRUIT_EXTRACT"
            for prod, trades in state.market_trades.items()
            for tr in trades
        )

        # VEF fair value
        vev_fair: Optional[float] = None
        if "VELVETFRUIT_EXTRACT" in state.order_depths:
            vev_fair = weighted_mid(state.order_depths["VELVETFRUIT_EXTRACT"])

        # Time to expiry: 4 days at the start of the round
        tte_days  = max(0.001, 4.0 - t / 1_000_000.0)
        tte_years = tte_days / 365.0

        # Net delta of the quoted options, hedged through a VEF target position
        net_delta = 0.0
        if vev_fair is not None:
            for prod, pval in state.position.items():
                if not prod.startswith("VEV_") or prod in SKIP_PRODUCTS:
                    continue
                K = float(prod.split("_")[1])
                net_delta += pval * bs_delta(vev_fair, K, tte_years, SIGMA)

        vef_target = int(max(-VEF_LIMIT, min(VEF_LIMIT, round(-net_delta))))

        for product, od in state.order_depths.items():

            if product in SKIP_PRODUCTS:
                continue

            pos   = state.position.get(product, 0)
            limit = POSITION_LIMITS.get(product, 300)

            # HYDROGEL
            if product == "HYDROGEL_PACK":
                spr, sz, edge = PRODUCT_PARAMS["HYDROGEL_PACK"]
                orders = place_orders(product, pos, limit, 10000.0, spr, sz, edge, od)

            # VEF, skewed toward the hedge target
            elif product == "VELVETFRUIT_EXTRACT":
                fair = vev_fair or weighted_mid(od)
                if fair is None: continue
                if mark67_buying: fair += 0.5
                spr, sz, edge = PRODUCT_PARAMS["VELVETFRUIT_EXTRACT"]
                orders = place_orders(product, pos, limit, fair, spr, sz, edge, od,
                                      target_pos=vef_target)

            # Options
            elif product.startswith("VEV_"):
                if vev_fair is None: continue
                K    = float(product.split("_")[1])
                fair = bs_call(vev_fair, K, tte_years, SIGMA) + STRIKE_BIAS.get(K, 0.0)

                if K <= 4500.0:
                    # Deep ITM: wide spread and edge, small size
                    edge, spr, sz = 6.0, 4.0, 5
                elif K == 5200.0:
                    # Delta about 0.65: wider edge
                    edge, spr, sz = 3.5, 2.0, 8
                else:
                    # OTM strikes: standard parameters, bigger size while Mark 01 is buying
                    edge = TAKE_EDGE
                    spr  = MM_SPREAD
                    sz   = 15 if (mark01_active and K >= 5300.0) else 10

                orders = place_orders(product, pos, limit, fair, spr, sz, edge, od)

            else:
                continue

            if orders:
                result[product] = orders

        self._log(state, result, t, vev_fair, tte_days, vef_target, net_delta)
        return result, 0, ""

    def _log(self, state, result, t, vev_fair, tte_days, hedge_tgt, net_delta):
        print("\n-- t={} | VEV={} | TTE={:.3f}d | Δopt={:.1f} | vef_tgt={} --".format(
            t,
            "{:.2f}".format(vev_fair) if vev_fair else "N/A",
            tte_days, net_delta, hedge_tgt))
        for product, orders in result.items():
            pos = state.position.get(product, 0)
            od  = state.order_depths.get(product)
            b   = max(od.buy_orders,  default="-") if od else "-"
            a   = min(od.sell_orders, default="-") if od else "-"
            lim = POSITION_LIMITS.get(product, 300)
            print("  {:<30s} pos={:+4d}/{} [{}/{}]".format(product, pos, lim, b, a))
            for o in orders:
                is_take = (o.quantity > 0 and od and o.price in od.sell_orders) \
                       or (o.quantity < 0 and od and o.price in od.buy_orders)
                print("    [{}] {} {:3d} @ {}".format(
                    "TAKE" if is_take else "MAKE",
                    "BUY " if o.quantity > 0 else "SELL",
                    abs(o.quantity), o.price))
