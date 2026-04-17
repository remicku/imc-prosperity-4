"""
IMC Prosperity 4, round 1: market maker v7.

Two products, two regimes:
- INTARIAN_PEPPER_ROOT follows a deterministic linear trend (R² = 0.9999 on
  the historical data), so the trader accumulates a long position aggressively
  and holds it to the end of the day.
- ASH_COATED_OSMIUM mean-reverts around 10,000, so it is market made around
  that hardcoded fair value with an inventory skew.

v6 -> v7: PEPPER asks are taken at market up to a threshold derived from the
expected remaining gain, instead of waiting for the market to come to us.
"""

from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json

POSITION_LIMITS: Dict[str, int] = {
    "EMERALDS":             80,
    "TOMATOES":             80,
    "ASH_COATED_OSMIUM":    80,
    "INTARIAN_PEPPER_ROOT": 80,
}

PEPPER_SLOPE = 0.001  # price change per timestamp, measured on the historical data

BASE_SPREAD: Dict[str, float] = {
    "EMERALDS":             2.0,
    "TOMATOES":             2.0,
    "ASH_COATED_OSMIUM":    2.0,
    "INTARIAN_PEPPER_ROOT": 2.0,
}

MM_SIZE: Dict[str, int] = {
    "EMERALDS":             10,
    "TOMATOES":             10,
    "ASH_COATED_OSMIUM":    10,
    "INTARIAN_PEPPER_ROOT": 10,
}

SKEW_STRENGTH: float = 2.0


class Trader:

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

            orders = []
            pos    = position

            if product == "INTARIAN_PEPPER_ROOT":
                # PEPPER: accumulate a long position early and hold it.
                # A unit bought now and held to the end of the day is expected
                # to gain PEPPER_SLOPE * remaining ticks; we pay up to half of it.
                time_remaining = max(0, 99900 - t)
                expected_gain  = PEPPER_SLOPE * time_remaining
                aggressive_buy_limit = fair + expected_gain * 0.5

                buy_cap  = limit - pos
                sell_cap = limit + pos

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

                # Take bids above fair value
                for bid_px, bid_vol in sorted(od.buy_orders.items(), reverse=True):
                    if bid_px <= fair:
                        break
                    cap = limit + pos
                    if cap <= 0:
                        break
                    qty = min(bid_vol, cap)
                    orders.append(Order(product, bid_px, -qty))
                    pos -= qty

                # Make: bid just under fair to attract sellers, ask far above
                # so the accumulated position is not given back early
                buy_cap  = limit - pos
                sell_cap = limit + pos

                if buy_cap > 0:
                    bid_px = round(fair - spread)
                    orders.append(Order(product, bid_px, min(size, buy_cap)))

                if sell_cap > 0:
                    ask_px = round(fair + expected_gain * 0.8)
                    orders.append(Order(product, ask_px, -min(size, sell_cap)))

            else:
                # OSMIUM: classic market making around the fair value
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

        if product == "ASH_COATED_OSMIUM":
            return 10000.0

        if product == "INTARIAN_PEPPER_ROOT":
            if bids and asks:
                bb, ba = max(bids), min(asks)
                bv, av = abs(bids[bb]), abs(asks[ba])
                mid = (bb * av + ba * bv) / (bv + av)
            elif bids: mid = float(max(bids))
            elif asks: mid = float(min(asks))
            else:
                ic = data.get("pepper_intercept")
                return ic + PEPPER_SLOPE * t if ic else None

            if "pepper_intercept" not in data:
                data["pepper_intercept"] = mid - PEPPER_SLOPE * t

            return data["pepper_intercept"] + PEPPER_SLOPE * t

        else:
            if bids and asks:
                bb, ba = max(bids), min(asks)
                bv, av = abs(bids[bb]), abs(asks[ba])
                return (bb * av + ba * bv) / (bv + av)
            if bids: return float(max(bids))
            if asks: return float(min(asks))
            return None


    def _load(self, raw):
        if not raw: return {}
        try: return json.loads(raw)
        except: return {}

    def _log(self, state, result, data, t):
        print(f"\n-- t={t} --")
        for product, orders in result.items():
            pos = state.position.get(product, 0)
            od  = state.order_depths.get(product)
            b   = max(od.buy_orders,  default="-") if od else "-"
            a   = min(od.sell_orders, default="-") if od else "-"
            lim = POSITION_LIMITS.get(product, 20)
            print(f"  {product:<25s} pos={pos:+4d}/{lim} [{b}/{a}]")
            for o in orders:
                is_take = (o.quantity > 0 and od and o.price in od.sell_orders) \
                       or (o.quantity < 0 and od and o.price in od.buy_orders)
                print(f"    [{'TAKE' if is_take else 'MAKE'}] {'BUY ' if o.quantity > 0 else 'SELL'} {abs(o.quantity):3d} @ {o.price}")
