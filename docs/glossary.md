# Glossary

Quick-reference glossary of terms used across the Resolved Markets platform.

| Term | Definition |
|------|------------|
| **conditionId** | Unique identifier for a Polymarket prediction market. Each market has one conditionId and contains two tokens (UP/DOWN or Yes/No). |
| **tokenId** | Unique identifier for an individual token within a market. Binary markets have two tokenIds; grouped markets may have many. |
| **slug** | Human-readable URL-friendly identifier for a market (e.g., `btc-updown-5m-1772448000`, `spx-opens-up-or-down-on-march-27-2026`). |
| **spread** | Difference between best ask and best bid price. Smaller spread = tighter liquidity. |
| **midPrice** | Average of best bid and best ask: `(bestBid + bestAsk) / 2`. Fair-value estimate for a token. An empty bid side counts as 0 and an empty ask side counts as 1, as on Polymarket; `spread` uses the same rule. `bestBid` or `bestAsk` itself shows 0 for an empty side. Snapshot rows call it `mid_price`. |
| **bestBid** | Highest price a buyer is willing to pay. Top of the bid side. |
| **bestAsk** | Lowest price a seller is willing to accept. Top of the ask side. |
| **bidDepth** | Sum of price × size over all levels on the bid side of the orderbook. Snapshot rows call it `bid_depth_total`. |
| **askDepth** | Sum of price × size over all levels on the ask side of the orderbook. Snapshot rows call it `ask_depth_total`. |
| **eventTimestamp** | Timestamp when Polymarket emitted the WebSocket event. |
| **captureTimestamp** | Timestamp when the backend processed and stored the snapshot. Difference from eventTimestamp = ingestion latency. |
| **sequenceNumber** | Incrementing counter per token for gap detection. Non-consecutive numbers indicate throttling or deduplication. |
| **crypto_price_age_ms** | Milliseconds from the last update of the coin price to the capture of the snapshot. Low values = fresh; high values = stale feed. `-1` means unknown or not a crypto market. BTC, ETH, SOL, XRP, DOGE and BNB prices come from the Binance best bid and ask (`bookTicker`); HYPE comes from Hyperliquid `allMids`. The live orderbook routes return `cryptoPriceAgeMs` as `-1`. |
| **token_side** | Enum: `UP` or `DOWN`. Indicates which side of a binary market a token represents. For Yes/No markets, Yes maps to UP, No maps to DOWN. |
| **negRisk / grouped market** | A Polymarket event with multiple sub-markets (e.g., Elon tweet count ranges with ~30 binary sub-markets). Each sub-market has its own conditionId and is tracked independently. |
| **CLOB** | Central Limit Order Book. Polymarket's matching engine. Resolved Markets connects via WebSocket to stream orderbook data. |
| **orderbook snapshot** | Complete point-in-time capture of all bid/ask levels for a token, with derived metrics. The capture rate depends on the market category. Crypto up/down markets get up to 10 snapshots a second for each orderbook (one every 100 ms). Other categories get at most one snapshot every 500 ms to 5 seconds for each orderbook. |
| **exchange snapshot** | Orderbook snapshot from an external exchange (e.g., Hyperliquid). Sampled at 1/sec intervals. Stored in `exchange_snapshots` table. |
| **delta / price_change** | Incremental orderbook update from WebSocket. Applied on top of in-memory state. |
| **book event** | Full orderbook snapshot from WebSocket. Replaces entire in-memory state for a token. |
| **MCP** | Model Context Protocol. Connects AI agents (Claude, etc.) to Resolved Markets data via tools and resources. Every tier has full access. |
| **tier** | Subscription level: Free, Pro ($17/mo), Scale ($49/mo), Enterprise ($549/mo). Determines monthly credits, rate limits, WebSocket connections, and category access. History and orderbook depth are unlimited on every tier. |
| **credit** | Unit of API consumption. Simple queries cost 1 credit, a snapshot at a timestamp or a market summary costs 3, a page of time-series costs 5. Every tier is metered: Free has 5,000 credits a month. |
| **credit pack** | Prepaid bundle of API credits for paid tiers ($5/10K, $20/100K, $50/500K). |
| **x402** | HTTP 402-based micropayment protocol. Clients pay $0.001 per request in USDC on Base — no account or API key needed. Bypasses rate limits and credit deduction. |
| **market category** | Classification of tracked markets: crypto, equities (stock indices, stocks, earnings, commodities, forex and more), social (Elon tweets), sports (NBA, NFL, EPL, FIFA World Cup, tennis), economics (FOMC/NFP), weather (temperatures/hurricanes). |
| **timeframe** | Duration window or type of a market. Crypto up/down: `5m`, `15m`, `1h`, `4h`, `1d`. Crypto hit-price: `hit-price`. Stock indices: `1d`, `monthly`, `annual`. Elon tweets: `weekly`. Sports: `game`. Fed rates: `rates` (rows captured before 2026-07-15 can have `meeting` or `annual`). Non-Farm Payrolls: `monthly`. Daily temperatures: `daily-high`, `daily-low`. Other configs use `event`, `daily`, `weekly`, `monthly`, `quarterly`, `annual`, `earnings`, `seasonal`, `valuation`, `comparison` and `leaderboard`. |
| **Clerk Billing** | Integrated payment system for card/Stripe subscriptions. Plans managed in Clerk Dashboard. |
| **NOWPayments** | Crypto payment gateway for tier upgrades and credit packs. Supports 200+ cryptocurrencies. |
| **Hyperliquid** | On-chain perpetual futures exchange. Resolved Markets collects L2 orderbook data for BTC, ETH, SOL, XRP, DOGE, HYPE, BNB perps. |
| **rate limit** | Max requests per minute by tier (Free 300, Pro 300, Scale 1,000, Enterprise 3,000). Exceeding returns HTTP 429. x402 requests bypass tier limits. |
