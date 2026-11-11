# Data Model

## Market (item of `GET /v1/markets/live`)

| Field | Type | Description |
|-------|------|-------------|
| `conditionId` | string | Unique market identifier (hex) |
| `slug` | string | URL slug of the Polymarket event. The markets of one event (such as the strikes of a hit-price day) share one slug |
| `question` | string | Human-readable market question |
| `label` | string | Short label, such as the strike of a hit-price market |
| `category` | string | One of: crypto, equities, social, sports, economics, weather |
| `subcategory` | string | The coin of a crypto market, else a group such as `NBA`, `FOMC` or a city |
| `configId` | string | Market config, as in `GET /v1/categories` |
| `timeframe` | string | Such as `5m`, `1d`, `hit-price`, `daily-high`, `game` or `rates` |
| `tokenIds` | string[] | Token ids. `tokenIds[0]` is the Up or Yes token, `tokenIds[1]` the Down or No token |
| `outcomes` | string[] | Outcome names, in the order of `tokenIds` |
| `endDate` | string | End of the market (ISO 8601) |
| `startDate` | string or null | Start of an up/down window (ISO 8601); `null` when the start is not known |
| `status` | string | `upcoming`, `live`, `settling` or `expired` |
| `expiresIn` | number | Milliseconds until `endDate` (0 after it) |

The list has no prices. Read the prices from the orderbook of the market.

## Orderbook side (`up` and `down` of `GET /v1/markets/:id/orderbook` and of the WebSocket `orderbook` message)

`up` or `down` is `null` when the server has no book for that token.

| Field | Type | Description |
|-------|------|-------------|
| `tokenId` | string | Token of this book |
| `bids` | Level[] | Bid levels, highest price first |
| `asks` | Level[] | Ask levels, lowest price first |
| `bestBid` | number | Highest bid price (0 when there are no bids) |
| `bestAsk` | number | Lowest ask price (0 when there are no asks) |
| `midPrice` | number | (bestBid + bestAsk) / 2; with no asks, the ask counts as 1 |
| `spread` | number | bestAsk - bestBid; with no asks, the ask counts as 1 |
| `bidDepth` | number | Sum of price × size of the bids |
| `askDepth` | number | Sum of price × size of the asks |
| `timestamp` | number | Time of the last change of the book (epoch ms) |
| `eventTimestamp` | number | When Polymarket emitted the last event (epoch ms) |
| `captureTimestamp` | number | When the server processed it (epoch ms) |
| `sequenceNumber` | number | Sequence number of the last change, for gap detection |

## Snapshot row (`data` of `GET /v1/markets/:id/snapshots`)

| Field | Type | Description |
|-------|------|-------------|
| `token_side` | string | "UP" or "DOWN" |
| `timestamp` | string | Snapshot time, UTC (`YYYY-MM-DD HH:MM:SS.mmm`) |
| `best_bid` | number | Highest bid price |
| `best_ask` | number | Lowest ask price |
| `mid_price` | number | Mid price, computed as `midPrice` above |
| `spread` | number | Spread, computed as `spread` above |
| `bid_depth_total` | number | Sum of price × size of the bids |
| `ask_depth_total` | number | Sum of price × size of the asks |
| `crypto_price` | number | Coin price when the snapshot was captured (crypto markets only) |
| `crypto_price_age_ms` | number | Age of that coin price, in milliseconds |
| `event_timestamp` | string | When Polymarket emitted the event, UTC |
| `capture_timestamp` | string | When the server processed it, UTC |
| `sequence_number` | string | Sequence number of the book, as a string |
| `bids`, `asks` | Level[] | Only with `includebook=true` |

## Level

| Field | Type | Description |
|-------|------|-------------|
| `price` | number | Price level (0-1) |
| `size` | number | Size at this level |

## Trade (`data` of `GET /v1/markets/:id/trades`)

| Field | Type | Description |
|-------|------|-------------|
| `market_id` | string | Market conditionId |
| `asset_id` | string | Token traded |
| `token_side` | string | "UP" or "DOWN" (`null` when unknown) |
| `price` | number | Trade price |
| `size` | number | Trade size |
| `side` | string | "BUY" or "SELL" |
| `timestamp` | string | Trade time, UTC (`YYYY-MM-DD HH:MM:SS.mmm`) |
| `transaction_hash` | string | On-chain transaction hash |

## Timestamps

Every orderbook side and every snapshot row has two timestamps:

| Orderbook side | Snapshot row | Source | Meaning |
|----------------|--------------|--------|---------|
| `eventTimestamp` | `event_timestamp` | Polymarket WS | When the exchange emitted the event |
| `captureTimestamp` | `capture_timestamp` | Server | When we processed and stored it |

The delta between them measures full pipeline latency.

## Sequence Numbers

Each token's orderbook maintains a monotonically increasing sequence number (`sequenceNumber` on an orderbook side, `sequence_number` in a snapshot row). Gaps may indicate:
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
