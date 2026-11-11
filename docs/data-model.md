# Data Model

## Market

| Field | Type | Description |
|-------|------|-------------|
| `conditionId` | string | Unique market identifier (hex) |
| `slug` | string | URL-friendly market identifier |
| `question` | string | Human-readable market question |
| `category` | string | One of: crypto, equities, social, sports, economics, weather |
| `tokens` | Token[] | UP and DOWN tokens with orderbooks |
| `endDate` | string | Market resolution date (ISO 8601) |
| `active` | boolean | Whether market is currently trading |

## Token

| Field | Type | Description |
|-------|------|-------------|
| `tokenId` | string | Unique token identifier |
| `outcome` | string | "Yes" or "No" |
| `side` | string | "UP" or "DOWN" |
| `price` | number | Current token price (0-1) |

## Orderbook Snapshot

| Field | Type | Description |
|-------|------|-------------|
| `tokenId` | string | Token this snapshot belongs to |
| `tokenSide` | string | "UP" or "DOWN" |
| `bids` | Level[] | Bid levels sorted by price descending |
| `asks` | Level[] | Ask levels sorted by price ascending |
| `bestBid` | number | Highest bid price |
| `bestAsk` | number | Lowest ask price |
| `midPrice` | number | (bestBid + bestAsk) / 2 |
| `spread` | number | bestAsk - bestBid |
| `totalBidDepth` | number | Sum of all bid sizes |
| `totalAskDepth` | number | Sum of all ask sizes |
| `eventTimestamp` | string | When Polymarket emitted the event |
| `captureTimestamp` | string | When our server processed it |
| `sequenceNumber` | number | Monotonically increasing, for gap detection |
| `cryptoPriceStalenessMs` | number | Ms since last crypto price update |

## Level

| Field | Type | Description |
|-------|------|-------------|
| `price` | number | Price level (0-1) |
| `size` | number | Size at this level |

## Trade

| Field | Type | Description |
|-------|------|-------------|
| `tokenId` | string | Token traded |
| `price` | number | Trade price |
| `size` | number | Trade size |
| `side` | string | "buy" or "sell" |
| `timestamp` | string | Trade timestamp (ISO 8601) |

## Timestamps

Every snapshot includes two timestamps:

| Field | Source | Meaning |
|-------|--------|---------|
| `eventTimestamp` | Polymarket WS | When the exchange emitted the event |
| `captureTimestamp` | Server | When we processed and stored it |

The delta between them measures full pipeline latency.

## Sequence Numbers

Each token's orderbook maintains a monotonically increasing sequence number. Gaps may indicate:
- **Throttled captures** — a minimum interval for each orderbook, set by the market category: 100 ms on crypto up/down markets (up to 10 snapshots a second), up to 5 seconds in the slowest categories (see [Capture Rates](#capture-rates))
- **Deduplicated captures** — identical orderbook state skipped
- **Data loss** — check pipeline health metrics to distinguish

## Capture Rates

Snapshots are event-driven. The capture interval is the minimum time between two snapshots of one orderbook. A quiet orderbook gets fewer snapshots. The two tokens of a market (UP/DOWN or Yes/No) have separate orderbooks.

| Capture interval | Max snapshots for each orderbook | Markets |
|------------------|----------------------------------|---------|
| 100 ms | 10 a second | Crypto up/down |
| 500 ms | 2 a second | Crypto hit price, NBA, NFL, English Premier League, FIFA World Cup, ATP Tour, WTA Tour |
| 1 s | 1 a second | Stocks, stock indices, commodities, forex, earnings |
| 2 s | 1 every 2 seconds | Fed rates, Nonfarm Payroll, daily city temperature, private companies, company KPIs |
| 3 s | 1 every 3 seconds | Elon Musk tweets |
| 5 s | 1 every 5 seconds | Hurricanes, global temperature and climate, acquisitions, IPOs, prediction markets |

`GET /v1/categories` returns the `captureIntervalMs` of each market config.
