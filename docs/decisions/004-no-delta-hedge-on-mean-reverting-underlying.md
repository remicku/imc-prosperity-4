# ADR 004: No delta hedging through a mean-reverting underlying

Date: round 3 (April 2026) · Status: applied in round 3; superseded in scope by ADR 005 for round 4

## Context

Round 3 v2 added a delta hedge to the options book by trading the underlying `VELVETFRUIT_EXTRACT` against the book's net delta. Backtest: 78,543 versus 116,286 for the unhedged v1. VEF is mean reverting, so the hedge systematically bought after the underlying had already moved, and was then long at exactly the moment the reversion kicked in. The hedge paid twice: once crossing the spread, once on the reversion.

## Decision

Do not delta hedge by chasing a mean-reverting underlying's own moves. Accept the options book's delta exposure rather than convert it into systematic negative expectancy.

## Consequences

v1 shipped without a hedge and kept its backtest performance. The residual delta risk this left open (visible as PnL leaks on specific strike-days) was real, and round 4 resolved it correctly: hedge the options book's aggregate delta with a target position, and refuse to quote the strikes whose delta cannot be hedged at all (ADR 005). The distinction that matters: hedging the book's exposure is sound, chasing the underlying's moves is not.
