"""
IMC Prosperity 4, round 2: market maker v8.

Same two engines as round 1 (PEPPER trend accumulation, OSMIUM mean reversion
around a hardcoded 10,000), plus two fixes found by backtesting v7 on the
round 2 data:

1. Day length. time_remaining was computed against 99,900 ticks instead of
   999,900, so a tenth of the way into the day the expected gain read zero,
   the passive PEPPER ask dropped to fair value and bots drained the position.
2. No take-sells on PEPPER. The estimated intercept sat a few points below the
   true trend, so bot bids regularly crossed the estimated fair value and
   triggered sells that unwound the position. The only exit is now the high
   passive ask.

bid() answers the Market Access Fee blind auction introduced this round.
"""

from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json

POSITION_LIMITS: Dict[str, int] = {
    "ASH_COATED_OSMIUM":    80,
    "INTARIAN_PEPPER_ROOT": 80,
    "EMERALDS":             80,
    "TOMATOES":             80,
}

PEPPER_SLOPE = 0.001     # price change per timestamp, about +1,000 per day (R² = 0.9999)
DAY_TICKS    = 999_900   # last timestamp of a day

BASE_SPREAD: Dict[str, float] = {
    "ASH_COATED_OSMIUM":    2.0,
    "INTARIAN_PEPPER_ROOT": 2.0,
}

MM_SIZE: Dict[str, int] = {
    "ASH_COATED_OSMIUM":    10,
    "INTARIAN_PEPPER_ROOT": 10,
}

SKEW_STRENGTH: float = 2.0


class Trader:

    # Market Access Fee (round 2 only): the top 50% of bids pay their bid once
    # and see 25% more order flow. That flow is worth an estimated 1,000 to
    # 2,000 per round; 2,500 aims at the top half without overpaying.
    def bid(self) -> int:
        return 2500

    def run(self, state: TradingState):
        data   = self._load(state.traderData)
        result = {}
        t      = state.timestamp

        for product, od in state.order_depths.items():
            position = state.position.get(product, 0)
            limit    = POSITION_LIMITS.get(product, 20)
            spread   = BASE_SPREAD.get(product, 2.0)
            size     = MM_SIZE.get(product, 10)

            fair = self._fair_value(od, data, product, t)
            if fair is None:
                continue

            orders: List[Order] = []
            pos = position

            if product == "INTARIAN_PEPPER_ROOT":
                # PEPPER: accumulate +80 and hold
                time_remaining       = max(0, DAY_TICKS - t)           # fix 1
                expected_gain        = PEPPER_SLOPE * time_remaining
                aggressive_buy_limit = fair + expected_gain * 0.5

                # Take every ask up to the aggressive limit
                for ask_px, ask_vol in sorted(od.sell_orders.items()):
                    if ask_px > aggressive_buy_limit:
                        break
                    cap = limit - pos
                    if cap <= 0:
                        break
                    qty = min(abs(ask_vol), cap)
                    orders.append(Order(product, ask_px, qty))
                    pos += qty

                # No take-sells on PEPPER (fix 2)

                # Make: bid to attract sellers
                buy_cap = limit - pos
                if buy_cap > 0:
                    orders.append(Order(product, round(fair - spread),
                                        min(size, buy_cap)))

                # Make: ask at the projected future price, never below fair + spread + 1
                sell_cap = limit + pos
                if sell_cap > 0:
                    ask_px = round(fair + max(expected_gain, spread + 1))
                    orders.append(Order(product, ask_px, -min(size, sell_cap)))

            else:
                # OSMIUM: mean-reversion market making
                # Take asks below fair, bids above fair
                for ask_px, ask_vol in sorted(od.sell_orders.items()):
                    if ask_px >= fair:
                        break
                    cap = limit - pos
                    if cap <= 0:
                        break
                    qty = min(abs(ask_vol), cap)
                    orders.append(Order(product, ask_px, qty))
                    pos += qty

                for bid_px, bid_vol in sorted(od.buy_orders.items(), reverse=True):
                    if bid_px <= fair:
                        break
                    cap = limit + pos
                    if cap <= 0:
                        break
                    qty = min(bid_vol, cap)
                    orders.append(Order(product, bid_px, -qty))
                    pos -= qty

                # Make: bid and ask skewed by inventory
                ratio     = pos / limit
                skew      = ratio * spread * SKEW_STRENGTH
                bid_price = round(fair - spread - skew)
                ask_price = round(fair + spread - skew)

                if limit - pos > 0:
                    orders.append(Order(product, bid_price, min(size, limit - pos)))
                if limit + pos > 0:
                    orders.append(Order(product, ask_price, -min(size, limit + pos)))

            if orders:
                result[product] = orders

        self._log(state, result, data, t)
        return result, 0, json.dumps(data)

    def _fair_value(self, od, data, product, t):
        bids = od.buy_orders
        asks = od.sell_orders

        if product == "INTARIAN_PEPPER_ROOT":
            if bids and asks:
                bb, ba = max(bids), min(asks)
                bv, av = abs(bids[bb]), abs(asks[ba])
                mid = (bb * av + ba * bv) / (bv + av)
            elif bids: mid = float(max(bids))
            elif asks: mid = float(min(asks))
            else:
                ic = data.get("pepper_intercept")
                return (ic + PEPPER_SLOPE * t) if ic else None

            if "pepper_intercept" not in data:
                data["pepper_intercept"] = mid - PEPPER_SLOPE * t

            return data["pepper_intercept"] + PEPPER_SLOPE * t

        elif product == "ASH_COATED_OSMIUM":
            # Stable long-term mean (std about 5 on the historical data)
            return 10000.0

        else:
            if bids and asks:
                bb, ba = max(bids), min(asks)
                bv, av = abs(bids[bb]), abs(asks[ba])
                return (bb * av + ba * bv) / (bv + av)
            if bids: return float(max(bids))
            if asks: return float(min(asks))
            return None

    def _load(self, raw: str) -> dict:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _log(self, state, result, data, t):
        print(f"\n-- t={t} --")
        for product, orders in result.items():
            pos = state.position.get(product, 0)
            od  = state.order_depths.get(product)
            b   = max(od.buy_orders,  default="-") if od else "-"
            a   = min(od.sell_orders, default="-") if od else "-"
            lim = POSITION_LIMITS.get(product, 20)
            if product == "INTARIAN_PEPPER_ROOT":
                ic = data.get("pepper_intercept", 0)
                fv = f"{ic + PEPPER_SLOPE * t:.1f}"
            else:
                fv = "10000.0"
            print(f"  {product:<25s} pos={pos:+4d}/{lim} [{b}/{a}] fair={fv}")
            for o in orders:
                is_take = (o.quantity > 0 and od and o.price in od.sell_orders) \
                       or (o.quantity < 0 and od and o.price in od.buy_orders)
                print(f"    [{'TAKE' if is_take else 'MAKE'}] {'BUY ' if o.quantity > 0 else 'SELL'} "
                      f"{abs(o.quantity):3d} @ {o.price}")
