# ADR 002: Hardcode fair values for demonstrably stable products

Date: round 1 (April 2026) · Status: applied in rounds 1, 2, 3 and 4

## Context

`ASH_COATED_OSMIUM` showed a long-term mean of 10,000 with a standard deviation around 5. The early versions estimated its fair value from the instantaneous mid price, which made the quotes follow the noise they were supposed to fade.

## Decision

When the data shows a stable long-term level, hardcode it as the fair value instead of estimating it dynamically.

## Consequences

OSMIUM's backtest contribution roughly doubled, from about 2,500 to about 6,000 per day. The same call was reused for `HYDROGEL_PACK` at 10,000 in rounds 3 and 4, where it powered the main mean reversion engine (about 27K per day in the round 3 backtest). The risk accepted: a real regime change in the product would be exploited against us until the constant is revisited. Estimating a value that does not move only adds noise.
