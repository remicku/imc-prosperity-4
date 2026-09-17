# ADR 003: Fixed-data backtests compare versions; platform previews and live PnL predictions do not

Date: round 2 (April 2026) · Status: applied from round 2 onward

## Context

The platform preview scored the buggy v7 (8,061) above the corrected v8 (7,817) in round 2, while the fixed-data backtest (`prosperity4btx --match-trades none`) showed v8 recovering about 37K per day on the worst historical day. Resubmitting an identical file moved the platform score by about ±300: the preview is randomized between submissions. Later rounds confirmed a second, distinct issue: even honest backtests missed live PnL by 2x (round 4) up to 10x (round 5), because the final simulation runs on a day that is not in the historical data.

## Decision

Two rules. Version A versus version B is decided by the fixed-data backtester only, never by the platform preview. And no backtest number, however clean, is treated as a prediction of live PnL; it is a relative comparison tool.

## Consequences

v8 was submitted in round 2 despite the worse preview, correctly. In round 4, v3 was submitted despite v1's more flattering preview (the sample day happened to favor unhedged long VEF exposure), also correctly. The cost of the rule is psychological: it requires ignoring the only number that looks like feedback from the real system.
