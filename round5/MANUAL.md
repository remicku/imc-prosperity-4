# Round 5 manual: Ignith and the Ashflow Alpha news

## The game

Nine tradable products on the Ignith exchange, one day of trading, decisions based solely on a news digest (Ashflow Alpha). Budget 1,000,000 XIRECs. Two twists:

- **Quadratic fees per product**: `fee = (v / 100)^2 x budget` where v is the percentage of budget put into that product. Concentration is punished; unused budget expires worthless but costs nothing.
- **Bounded herding**: each product has an anchor return and a predefined range around it, and the aggregate of participant submissions moves the realized return inside that range.

## Approach

Three layers:

1. **Direction from critical news reading.** Each headline was classified: genuinely new information, already priced in, or hype without fundamentals.
2. **Herding mechanics.** Since aggregated flow moves returns within a bounded range, consensus signals remain profitable: if everyone buys the obvious good news, the return moves further in that direction, up to the cap. This argues for taking the clear consensus trades rather than being contrarian, and for skipping stories the crowd has already fully priced.
3. **Sizing against quadratic fees.** With expected return R per product, the fee-optimal size is `v* = 50 x R` (in percent of budget). Summed over the book this deployed only about half the budget, which is the correct outcome under quadratic costs, not a lack of conviction.

## The calls

- **BUY Sulfur Reactor**: index inclusion, forced flows from tracking funds.
- **BUY Thermalite Core**: +174% reported growth.
- **BUY Magma Ink**: merger plus demand growth.
- **SELL Lava Cake**: health crisis and a lawsuit.
- **SELL Pyroflex Cells**: a doubled tax.
- **SKIP Volcanic Incense**: good story, already priced in.
- **SKIP Scoria Paste**: hype without fundamentals.
- **Obsidian Cutlery**: first classified as a SELL, flipped to **BUY** on re-verification (the news described a supply shock, which supports the price). The initial misread was caught by systematically re-deriving each direction before locking the allocation.

Final allocation prepared for submission: Sulfur BUY 11%, Thermalite BUY 10%, Lava Cake SELL 11%, Pyroflex SELL 8%, Magma Ink BUY 6%, Obsidian BUY 3%, Ashes SELL 2%, two skips. About 51% of budget deployed, roughly 46,800 in fees.

## Result

The manual result for round 5 was not archived before the platform closed. What I can document is the process above.
