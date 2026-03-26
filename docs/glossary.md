# Glossary

Quick-reference glossary of terms used across the Resolved Markets platform.

| Term | Definition |
|------|------------|
| **conditionId** | Unique identifier for a Polymarket prediction market. Each market (e.g., "Will BTC be above $70k in 1 hour?") has one conditionId and contains two tokens (UP and DOWN). |
| **tokenId** | Unique identifier for an individual token within a market. Each market has two tokenIds: one for the UP token and one for the DOWN token. |
| **slug** | Human-readable URL-friendly identifier for a market (e.g., `btc-usdt-5m`, `solana-usdt-1h`). Used with the `/v1/markets/by-slug/:slug` endpoint. |
| **spread** | The difference between the best ask and best bid price in an orderbook, expressed in the same units as the price. A smaller spread indicates tighter liquidity. |
| **midPrice** | The average of the best bid and best ask prices: `(bestBid + bestAsk) / 2`. Used as a fair-value estimate for a token. |
| **bestBid** | The highest price at which a buyer is willing to purchase a token. The top of the bid side of the orderbook. |
| **bestAsk** | The lowest price at which a seller is willing to sell a token. The top of the ask side of the orderbook. |
| **totalBidDepth** | The sum of all order sizes on the bid (buy) side of the orderbook. Indicates total buying interest across all price levels. |
| **totalAskDepth** | The sum of all order sizes on the ask (sell) side of the orderbook. Indicates total selling interest across all price levels. |
| **eventTimestamp** | The timestamp assigned by Polymarket when a WebSocket event (book update or price change) was emitted. Used to measure exchange-side timing. |
| **captureTimestamp** | The timestamp recorded by the Resolved Markets backend when a snapshot was processed and stored. The difference between `captureTimestamp` and `eventTimestamp` measures ingestion latency. |
| **sequenceNumber** | An incrementing counter assigned to each captured snapshot per token. Used for gap detection in the data stream. Non-consecutive numbers may result from throttling or deduplication. |
| **cryptoPriceStalenessMs** | The number of milliseconds since the last real-time crypto price update was received from Binance. Low values (under 1000ms) indicate a fresh price; high values suggest the Binance WebSocket feed may be stale or disconnected. |
| **token_side** | An enum value of either `UP` or `DOWN` indicating which side of a binary prediction market a token represents. UP tokens gain value if the condition resolves true; DOWN tokens gain value if it resolves false. |
| **CLOB** | Central Limit Order Book. The matching engine used by Polymarket where buy and sell orders are placed at specific prices. Resolved Markets connects to the CLOB via WebSocket to stream orderbook data. |
| **orderbook snapshot** | A complete point-in-time capture of all bid and ask price levels for a token, including derived metrics (spread, mid price, depth). Captured at up to ~20Hz per token. |
| **delta / price_change event** | An incremental update from the Polymarket WebSocket indicating that specific price levels in the orderbook have changed. Applied on top of the current in-memory orderbook state by the OrderbookManager. |
| **book event** | A full orderbook snapshot event from the Polymarket WebSocket. Replaces the entire in-memory orderbook state for a token. Sent on initial subscription and periodically for resynchronization. |
| **MCP** | Model Context Protocol. A protocol for connecting AI agents (such as Claude) to external data sources. The Resolved Markets MCP server exposes tools and resources for querying orderbook data programmatically from AI assistants. |
| **tier** | The subscription level of a user account. Tiers (Free, Pro, Enterprise) determine rate limits, history access depth, WebSocket connection limits, and available features. |
| **credit pack** | A prepaid bundle of API credits that can be purchased via crypto payment. Credits are consumed per API request and provide an alternative to monthly tier subscriptions. |
| **rate limit** | The maximum number of API requests a user can make per minute, determined by their tier. Exceeding the limit returns HTTP 429. |
| **timeframe** | The duration window for a prediction market. Polymarket crypto markets are tracked across four timeframes: 5 minutes (5m), 15 minutes (15m), 1 hour (1h), and 1 day (1d). |
| **market category** | The cryptocurrency asset a market is based on. Resolved Markets tracks four categories: BTC (Bitcoin), ETH (Ethereum), SOL (Solana), and XRP (Ripple). |
| **NOWPayments** | A third-party crypto payment gateway used by Resolved Markets to process tier upgrades and credit pack purchases. Payments are verified via HMAC-SHA512 signed webhooks. |
