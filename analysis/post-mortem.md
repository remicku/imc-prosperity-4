# Post-mortem: IMC Prosperity 4

Final result: #845 worldwide, #39 in France.

## The arc

**Phase 1 (rounds 1 and 2): learning that data comes first.** My first five versions of generic market making plateaued around +2,200 on the platform test. Regressing the historical CSVs changed the problem entirely: one product was a deterministic trend (`INTARIAN_PEPPER_ROOT`, R² = 0.9999), the other a clean mean reversion around 10,000 (`ASH_COATED_OSMIUM`). Once the fair value is known, the job is to exploit it aggressively; switching from passive quoting to aggressive accumulation multiplied the platform test PnL by about 3.5. Round 2 was a round of rigor: two bugs fixed (worth about +37K per day on the worst backtest day) and a manual challenge solved with plain game theory (rank 108 worldwide, my best individual result of the competition).

**Phase 2 (rounds 3 to 5): from options pricing to directional trading.** Round 3 established the Black-Scholes calibration (sigma, TTE convention, per-strike biases) but ended with the most avoidable loss of my competition: the best version was not ready at the 48-hour deadline and a fallback was submitted. Round 4 was the technical peak: counterparty profiling from the newly visible trade identities, and above all the decision to stop quoting strikes whose delta could not be hedged within position limits, turning a risk constraint into a product selection criterion. Round 5 demanded a full pivot: 50 new products, a directional regime, classification by historical consistency, and accepting that a simple historical bias beats a sophisticated intraday signal.

**Strategy evolution across the competition**: generic market making, then exploitation of deterministic patterns, then options pricing with hedging discipline, then directional trend following. The invariant was the loop: data analysis, calibration, implementation, backtest, iteration, every round.

## Cross-round lessons

1. **Process beats model.** My largest avoidable loss was operational, not analytical: submitting a fallback version in round 3 (about 15K) because the developed strategy was not ready at the 48-hour deadline. Fix: candidate file ready early, checksum before submission.
2. **Backtest is not live.** Observed gaps ranged from 2x to 10x; the platform simulates a day that is not in the historical data. A fixed-data backtester is the reference for comparing versions, never for predicting live PnL.
3. **Hedge the right risk.** Delta hedging a mean-reverting underlying's own moves destroys value (round 3, v2: about -38K versus baseline). Delta hedging an options book through the underlying works (round 4). And what cannot be hedged should not be market made at all (round 4, v3: about 22K of losses avoided).
4. **Edge must clear the noise.** At 251% volatility scored over 100 shared simulations, an edge below about 0.20 per unit is noise: the round 4 straddle at about 0.12 lost, the shorts at 0.30 and 0.23 won. Default on exotics: sell.
5. **Variance reduction is expensive.** Round 5: halving the Tier 2 size cost about 10K of upside for an essentially identical drawdown.
6. **Known fair values get hardcoded** (OSMIUM at 10,000, HYDROGEL at 10,000). Dynamically estimating a stable value only adds noise.
7. **Manual challenges are games, not markets.** Real participant distributions are not uniform (the round 2 Speed distribution spiked massively at 0%), revealed averages are reusable data (avg_b2 = 859 from round 3), your own volume moves the price in a one-shot auction (round 1), and when every team runs the same model the crowd's error is yours (round 4).

## What I would do differently

- Set up a submission pipeline from round 1: final file frozen hours before the deadline, checksum verified. That is the 15K lesson of round 3.
- Size one-shot auction orders against the depth available at my price, not against the budget (FLAX and MUSHROOM, round 1).
- Archive assets continuously (result pages, leaderboard, logs). The platform closed after the competition; the round 1 to 4 result pages were saved, the round 5 page and the leaderboard were not.
- Distrust refined model corrections at extreme parameter values: the Broadie-Glasserman-Kou correction, correct in theory, flipped a decision at 251% volatility and cost about 29K. Test the sensitivity before acting on it.
- Apply edge thresholds as soon as they are formulated, not one lesson later.
- Budget 48-hour rounds like sprints: the candidate version must exist at mid-round, the last hours are for validation, not development.
