# Overview

Resolved Markets captures high-fidelity orderbook data from Polymarket prediction markets and Hyperliquid perpetual futures. It tracks 6 market categories — crypto, equities, social, sports, economics, weather — plus exchange orderbook data.

## What It Does

- Captures Polymarket orderbook snapshots via event-driven triggers. The capture rate depends on the market category. Crypto up/down markets get up to 10 snapshots a second for each orderbook (one every 100 ms). Other categories get at most one snapshot every 500 ms to 5 seconds for each orderbook
- Collects Hyperliquid perpetual orderbook data (BTC/ETH/SOL/XRP/DOGE/HYPE/BNB) at 1/sec sampling
- Records trades in real-time from Polymarket's CLOB (Central Limit Order Book)
- Stores everything in ClickHouse for historical analysis
- Serves data via REST API, WebSocket streams, and MCP server
- Supports grouped (negRisk) events with multiple sub-markets (e.g., Elon tweet count ranges)

## How It Works

Each Polymarket market has two tokens — **UP** and **DOWN** (or **Yes** and **No**) — each with its own orderbook. For grouped events (like Elon tweet counts), each sub-market is a separate binary market.

The data pipeline:

```
Polymarket WS          Binance WS         Hyperliquid WS
     |                      |                    |
     v                      v                    v
CLOBCollector      CryptoPriceCollector   HyperliquidCollector
     |                      |              (L2 book deltas)
     v                      |                    |
OrderbookManager  <---------+                    v
     |                                   1/sec sampled writes
     v (event callback)                          |
 SnapshotCapturer (throttled)                    v
     |                              exchange_snapshots (ClickHouse)
     v (batch: 800 snapshots, 2s flush)
 ClickHouseBatchWriter --> snapshots_hf (ClickHouse)
```

## Market Categories

| Category | Config ids | Examples |
|----------|------------|----------|
| **Crypto** | crypto-updown, crypto-hit-price | BTC, ETH, SOL, XRP, DOGE, HYPE, BNB up/down prediction markets (5m, 15m, 1h, 4h, 1d), daily hit-price markets |
| **Equities** | indices, privates, earnings, stocks, commodities, forex, acquisitions, prediction-markets, ipos, kpis | Stock indices (S&P 500 and others), stocks, earnings, commodities, forex, private companies, IPOs, acquisitions, company KPIs |
| **Social** | elon-tweets | Elon Musk weekly tweet count ranges (negRisk grouped, ~30 sub-markets) |
| **Sports** | nba, nfl, epl, fifa-world-cup, tennis-atp, tennis-wta | NBA, NFL, EPL, FIFA World Cup, ATP and WTA tennis match outcomes |
| **Economics** | fed-rates, nonfarm-payroll | FOMC rate decisions, Non-Farm Payrolls |
| **Weather** | hurricanes, global-weather, daily-temperature | Daily temperatures (up to 53 cities), hurricanes, Arctic conditions |
| **Exchange** | -- | Hyperliquid perpetual orderbooks (BTC, ETH, SOL, XRP, DOGE, HYPE, BNB) |

The config ids are the `id` values of `GET /v1/categories`, which also gives the live market count of each config. `GET /v1/markets/live?category=weather&timeframe=daily-high` (Scale and above) lists the live city markets; the `subcategory` of each market is its city.

## Key Concepts

- **conditionId** — Unique market identifier (hex string)
- **tokenId** — Two per market (UP/DOWN or Yes/No), each with its own orderbook
- **slug** — Human-readable market identifier, e.g. `btc-updown-5m-1772448000`
- **negRisk / grouped market** — An event with multiple sub-markets (e.g., tweet count ranges). Each sub-market has its own conditionId and is tracked independently.
- **eventTimestamp** — When Polymarket emitted the orderbook event
- **captureTimestamp** — When the server processed and stored it
- **sequenceNumber** — Monotonically increasing per token, for gap detection
- **exchange snapshot** — Hyperliquid perpetual orderbook sampled at 1/sec intervals
