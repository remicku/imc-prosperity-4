"""
IMC Prosperity 4, round 5: submitted trader (Tier 2 at full size).

50 products, position limit 10 each. Purely directional, no market making:
the historical days show near-monotone intraday trends, so the trader takes
the full ±10 in the trend direction from the first tick and holds.

- Tier 1: same direction on all 3 historical days, direction hardcoded.
- Tier 2: same direction on 2 days out of 3, historical bias hardcoded.
- Tier 3: noise or negligible slope, not traded.

Execution crosses the spread: take the available liquidity, then rest the
remainder at the touch so it fills on the next ticks. Backtest on the 3
historical days: about 621K in total with take-only fills.
"""

from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List, Optional

# Position limit, identical for all 50 products
LIMIT = 10

# Tier 1: same direction on all 3 historical days
TIER1_LONG = {
    "OXYGEN_SHAKE_GARLIC",
    "GALAXY_SOUNDS_BLACK_HOLES",
    "PANEL_2X4",
    "SNACKPACK_VANILLA",
}
TIER1_SHORT = {
    "MICROCHIP_OVAL",
    "PEBBLES_XS",
    "UV_VISOR_AMBER",
    "PEBBLES_S",
    "ROBOT_IRONING",
    "SNACKPACK_PISTACHIO",
    "TRANSLATOR_ASTRO_BLACK",
    "SNACKPACK_CHOCOLATE",
}

# Tier 2: historical bias, same direction on 2 days out of 3 (+1 long, -1 short)
TIER2_BIAS: Dict[str, int] = {
    # Microchips
    "MICROCHIP_SQUARE":              +1,
    "MICROCHIP_TRIANGLE":            -1,
    "MICROCHIP_RECTANGLE":           -1,
    "MICROCHIP_CIRCLE":              +1,
    # Pebbles
    "PEBBLES_XL":                    +1,
    "PEBBLES_M":                     +1,
    "PEBBLES_L":                     -1,
    # Sleep pods
    "SLEEP_POD_POLYESTER":           +1,
    "SLEEP_POD_SUEDE":               +1,
    "SLEEP_POD_COTTON":              +1,
    "SLEEP_POD_NYLON":               +1,
    # UV visors
    "UV_VISOR_MAGENTA":              +1,
    "UV_VISOR_RED":                  +1,
    # Robots
    "ROBOT_MOPPING":                 +1,
    "ROBOT_DISHES":                  +1,
    "ROBOT_VACUUMING":               -1,
    "ROBOT_LAUNDRY":                 -1,
    # Translators
    "TRANSLATOR_VOID_BLUE":          +1,
    "TRANSLATOR_SPACE_GRAY":         -1,
    "TRANSLATOR_GRAPHITE_MIST":      -1,
    # Galaxy / oxygen / snackpack
    "GALAXY_SOUNDS_SOLAR_WINDS":     +1,
    "OXYGEN_SHAKE_MORNING_BREATH":   -1,
    "OXYGEN_SHAKE_CHOCOLATE":        +1,
    "SNACKPACK_STRAWBERRY":          +1,
}

# Tier 3: not traded (noise or negligible slope)
TIER3_SKIP = {
    "SLEEP_POD_LAMB_WOOL",
    "TRANSLATOR_ECLIPSE_CHARCOAL",
    "GALAXY_SOUNDS_DARK_MATTER",
    "GALAXY_SOUNDS_SOLAR_FLAMES",
    "OXYGEN_SHAKE_EVENING_BREATH",
    "PANEL_4X4",
    "UV_VISOR_YELLOW",
    "PANEL_1X2",
    "PANEL_1X4",
    "SNACKPACK_RASPBERRY",
    "UV_VISOR_ORANGE",
}


# Helpers

def best_levels(od: OrderDepth):
    bb = max(od.buy_orders) if od.buy_orders else None
    ba = min(od.sell_orders) if od.sell_orders else None
    return bb, ba


def push_to_target(
    product: str,
    pos: int,
    target: int,
    od: OrderDepth,
) -> List[Order]:
    """
    Push the position toward `target` (+10 or -10) across the spread:
    take the existing book first, then rest the remainder at the touch.
    """
    if pos == target:
        return []

    orders: List[Order] = []
    bb, ba = best_levels(od)

    # Buy side
    if target > pos:
        need = target - pos
        for ask_px in sorted(od.sell_orders.keys()):
            if need <= 0:
                break
            ask_vol = abs(od.sell_orders[ask_px])
            qty = min(ask_vol, need)
            orders.append(Order(product, ask_px, qty))
            need -= qty
        if need > 0:
            # Not enough liquidity to take: rest the remainder at the best ask,
            # where it catches the next asks that appear
            if ba is not None:
                orders.append(Order(product, ba, need))
            elif bb is not None:
                orders.append(Order(product, bb + 1, need))

    # Sell side
    else:
        need = pos - target
        for bid_px in sorted(od.buy_orders.keys(), reverse=True):
            if need <= 0:
                break
            bid_vol = od.buy_orders[bid_px]
            qty = min(bid_vol, need)
            orders.append(Order(product, bid_px, -qty))
            need -= qty
        if need > 0:
            if bb is not None:
                orders.append(Order(product, bb, -need))
            elif ba is not None:
                orders.append(Order(product, ba - 1, -need))

    return orders


# Trader

class Trader:

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        t = state.timestamp

        for product, od in state.order_depths.items():

            if product in TIER3_SKIP:
                continue

            # Directional target
            if product in TIER1_LONG:
                target = +LIMIT
            elif product in TIER1_SHORT:
                target = -LIMIT
            elif product in TIER2_BIAS:
                target = TIER2_BIAS[product] * LIMIT
            else:
                continue  # unknown product: skip

            pos = state.position.get(product, 0)
            orders = push_to_target(product, pos, target, od)
            if orders:
                result[product] = orders

        # Light logging, ten times per day
        if t % 100000 == 0:
            n_orders = sum(len(v) for v in result.values())
            print(f"-- t={t} | products={len(result)} | orders={n_orders}")

        return result, 0, ""
