# ADR 001: Aggressive execution on deterministic trends

Date: round 1 (April 2026) · Status: applied from round 1 v7 onward

## Context

Regression on the round 1 historical data showed `INTARIAN_PEPPER_ROOT` following a deterministic linear trend (R² = 0.9999). v6 computed the correct fair value trajectory but quoted passively, waiting for the market to come to it: +2,210 on the platform test, with a flat PnL curve over the first 40,000 ticks. Generic market making versions (v1 to v5) had plateaued at about +2,200.

## Decision

When the fair value trajectory is known, cross the spread. Take every ask priced below fair plus half the expected remaining gain, post a bid under fair to attract sellers, and place the exit ask near the projected end-of-day value so the position is not given back early.

## Consequences

Platform test went from +2,210 (v6) to +7,782 (v7), and +8,540 with the OSMIUM fair value hardcoded. The binding constraint moved from the price threshold to book depth: changing the aggressiveness multiplier had no measurable effect because the market's asks always sat within reach. Cost of the approach: the position carries overnight-style risk within the day if the model is wrong, which is acceptable only because the trend was deterministic in the data.
