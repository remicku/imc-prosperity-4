# ADR 006: Variance reduction must earn its cost

Date: round 5 (April 2026) · Status: applied for the final submission

## Context

The round 5 directional strategy took ±10 positions in 36 products. To limit exposure on the less reliable Tier 2 bucket (directional consistency 2 out of 3 historical days), a v2 halved the Tier 2 size to ±5. Both variants ran as live platform tests before the final submission: v1 (full size) +24,130, v2 (half size) +14,459, with nearly identical drawdowns (-15K and -17K).

## Decision

Submit v1. Halving Tier 2 gave up about 10K of upside while leaving the drawdown essentially unchanged, so the size reduction bought no actual risk reduction.

## Consequences

The decision was validated by the only comparable measurement available (the live test pair). The underlying point: sizing down is only worth it if the risk metric you care about actually improves. Here the drawdown was driven by the early choppiness common to both variants, not by the Tier 2 size, so cutting size was pure cost. Backtest-to-live calibration remained the open problem (about 10x gap, see the round 5 write-up), but it affected both variants equally and did not change the ranking between them.
