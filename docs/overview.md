# Overview

Resolved Markets captures high-fidelity orderbook data from Polymarket prediction markets and Hyperliquid perpetual futures. It tracks 7 market categories — crypto, equities, social, sports, economics, weather — plus exchange orderbook data.

## What It Does

- Captures Polymarket orderbook snapshots at ~20Hz per token via event-driven triggers
- Collects Hyperliquid perpetual orderbook data (BTC/ETH/SOL/XRP) at 1/sec sampling
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

| Category | Tag | Examples |
|----------|-----|----------|
| **Crypto** | crypto-updown | BTC, ETH, SOL, XRP up/down prediction markets (5m, 15m, 1h, 1d) |
| **Equities** | spx-updown | S&P 500 (SPX) daily open — Up or Down |
| **Social** | elon-tweets | Elon Musk weekly tweet count ranges (negRisk grouped, ~30 sub-markets) |
| **Sports** | nba, nfl, epl | NBA, NFL, EPL match outcomes |
| **Economics** | fed-decisions | FOMC rate decisions, Non-Farm Payrolls |
| **Weather** | weather, daily-temperature | Daily temperatures (30 cities), hurricanes, Arctic conditions |
| **Exchange** | -- | Hyperliquid perpetual orderbooks (BTC, ETH, SOL, XRP) |

## Key Concepts

- **conditionId** — Unique market identifier (hex string)
- **tokenId** — Two per market (UP/DOWN or Yes/No), used for WebSocket subscriptions
- **slug** — Human-readable market identifier, e.g. `btc-updown-5m-1772448000`
- **negRisk / grouped market** — An event with multiple sub-markets (e.g., tweet count ranges). Each sub-market has its own conditionId and is tracked independently.
- **eventTimestamp** — When Polymarket emitted the orderbook event
- **captureTimestamp** — When the server processed and stored it
- **sequenceNumber** — Monotonically increasing per token, for gap detection
- **exchange snapshot** — Hyperliquid perpetual orderbook sampled at 1/sec intervals
