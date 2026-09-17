# ADR 005: Do not market make strikes whose delta cannot be hedged within position limits

Date: round 4 (April 2026) · Status: applied in round 4 v3 (submitted configuration of the strategy)

## Context

`VEV_5000` and `VEV_5100` carry deltas of about 0.975 and 0.878. At the 300-contract option position limit, hedging them requires about 292 and 263 units of `VELVETFRUIT_EXTRACT`, above its 200 limit. Quoting those strikes therefore accumulates directional VEF exposure that cannot be neutralized: it is a directional bet taken through an instrument with a wider spread than the underlying itself. Historical P&L agreed: -20,070 and -1,617 over 3 days, while the hedgeable strikes were net positive.

## Decision

Remove `VEV_5000` and `VEV_5100` from market making entirely. Keep `VEV_5200` (delta about 0.65, net +6,467 historically) but demand a wider edge (3.5) on it. Hedge the remaining book with a clamped VEF target position and skew the VEF quotes toward it.

## Consequences

On the historical days, about 22K of losses avoided and daily PnL variance cut from ±37K to ±13K. Backtest total went from 98,385 (v2) to 120,082 (v3). The general form of the rule: position limits are not just constraints on size, they define which products are tradable at all. A market maker's universe is the set of products whose risk it can actually carry.
