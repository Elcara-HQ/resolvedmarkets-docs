# Overview

Resolved Markets captures high-fidelity orderbook data from Polymarket prediction markets. It tracks BTC, ETH, SOL, and XRP markets across crypto, sports, economics, and weather categories.

## What It Does

- Captures orderbook snapshots at ~20Hz per token via event-driven triggers
- Records trades in real-time from Polymarket's CLOB (Central Limit Order Book)
- Stores everything in ClickHouse for historical analysis
- Serves data via REST API, WebSocket streams, and MCP server

## How It Works

Each Polymarket market has two tokens — **UP** and **DOWN** — each with its own orderbook. Prices are inversely correlated and sum to ~1.00.

The data pipeline:

```
Polymarket WS          Binance WS
     |                      |
     v                      v
CLOBCollector      CryptoPriceCollector
     |                      |
     v                      |
OrderbookManager  <---------+
     |
     v (event callback)
 SnapshotCapturer (throttled to 50ms/token)
     |
     v (batch: 800 snapshots, 2s flush)
 ClickHouseBatchWriter --> ClickHouse
```

## Market Categories

| Category | Examples |
|----------|----------|
| **Crypto** | BTC, ETH, SOL, XRP up/down prediction markets (5m, 15m, 1h, 1d) |
| **Sports** | NBA, NFL, EPL match outcomes |
| **Economics** | FOMC rate decisions, Non-Farm Payrolls |
| **Weather** | Daily temperatures (30 cities), hurricanes, Arctic conditions |

## Key Concepts

- **conditionId** — Unique market identifier (hex string)
- **tokenId** — Two per market (UP and DOWN), used for WebSocket subscriptions
- **slug** — Human-readable market identifier, e.g. `btc-updown-5m-1772448000`
- **eventTimestamp** — When Polymarket emitted the orderbook event
- **captureTimestamp** — When the server processed and stored it
- **sequenceNumber** — Monotonically increasing per token, for gap detection
