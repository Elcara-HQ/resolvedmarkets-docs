# API Reference

Base URL: `https://api.resolvedmarkets.com`

## Public Endpoints (No Auth)

### GET /health

Health check with pipeline readiness status.

**Response:**
```json
{
  "status": "healthy",
  "clickhouse": true,
  "redis": true,
  "ws_clob": true,
  "ws_trade": true,
  "pipeline_ready": true,
  "uptime": 123456
}
```

Status values: `"healthy"` (all systems up), `"starting"` (API up, pipeline initializing), `"degraded"` (infrastructure issue).

### GET /v1/public-stats

Platform statistics.

**Response:**
```json
{
  "snapshot_count": 50234567,
  "active_markets": 142,
  "prices": { "BTC": 87420.50, "ETH": 3421.80, "SOL": 187.25, "XRP": 2.34 }
}
```

---

## Market Endpoints (API Key Required)

### GET /v1/categories

List all market categories with active market counts.

**Response:**
```json
[
  { "id": "crypto-updown", "category": "crypto", "displayName": "Crypto Up/Down", "activeMarkets": 16 },
  { "id": "spx-updown", "category": "equities", "displayName": "S&P 500 Up/Down", "activeMarkets": 1 },
  { "id": "elon-tweets", "category": "social", "displayName": "Elon Musk Tweets", "activeMarkets": 30 },
  { "id": "nba", "category": "sports", "displayName": "NBA", "activeMarkets": 30 },
  { "id": "fed-decisions", "category": "economics", "displayName": "Fed/FOMC Decisions", "activeMarkets": 10 },
  { "id": "weather", "category": "weather", "displayName": "Weather & Climate", "activeMarkets": 15 },
  { "id": "daily-temperature", "category": "weather", "displayName": "Daily Temperature", "activeMarkets": 30 }
]
```

### GET /v1/markets/live

List active markets. Supports filtering by category and subcategory.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | string | No | Filter: crypto, equities, social, sports, economics, weather |
| `subcategory` | string | No | Filter: BTC, SPX, Elon, NBA, FOMC, NYC, etc. |

**Response:**
```json
[
  {
    "conditionId": "0x1234...",
    "category": "social",
    "subcategory": "Elon",
    "label": "260-279",
    "timeframe": "weekly",
    "tokenIds": ["abc...", "def..."],
    "outcomes": ["Yes", "No"],
    "slug": "elon-musk-of-tweets-march-20-march-27",
    "expired": false,
    "expiresIn": 172800000
  }
]
```

### GET /v1/markets/history/recent

Recently active markets from materialized view. Same query params as `/v1/markets/history`.

### GET /v1/markets/history

Full historical markets with pagination.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | string | No | Filter by category |
| `subcategory` | string | No | Filter by subcategory |
| `crypto` | string | No | Legacy filter (BTC, ETH, SOL, XRP) |
| `timeframe` | string | No | Filter by timeframe |

### GET /v1/markets/by-slug/:slug

Look up a market by its URL slug. Supports exact, partial, and fuzzy matching.

**Example:** `GET /v1/markets/by-slug/spx-opens-up-or-down-on-march-27-2026`

### GET /v1/markets/by-slug/:slug/orderbook

Live orderbook for a market by slug. Same response as `/v1/markets/:id/orderbook`.

### GET /v1/markets/:id/orderbook

Live orderbook for a market by conditionId. Returns both UP/DOWN (or Yes/No) token books.

**Response:**
```json
{
  "marketId": "0x1234...",
  "crypto": "BTC",
  "timeframe": "5m",
  "cryptoPrice": 87420.50,
  "up": {
    "bestBid": 0.52, "bestAsk": 0.53,
    "midPrice": 0.525, "spread": 0.01,
    "bids": [{"price": 0.52, "size": 1500}],
    "asks": [{"price": 0.53, "size": 800}]
  },
  "down": { "..." : "..." }
}
```

### GET /v1/markets/:id/snapshots

Paginated historical orderbook snapshots. Subject to tier history depth limits.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `side` | string | No | Filter: `UP` or `DOWN` |
| `from` | string | No | Start timestamp (clamped by tier) |
| `to` | string | No | End timestamp |
| `limit` | number | No | Max rows (default 500, max 5000) |
| `offset` | number | No | Pagination offset |

### GET /v1/markets/:id/summary

Aggregated market statistics: price ranges, spreads, depth averages, per-side breakdowns.

---

## Exchange Endpoints (API Key Required)

### GET /v1/exchange/orderbook

Live orderbook from Hyperliquid perpetual futures.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `exchange` | string | Yes | `hyperliquid_perp` |
| `symbol` | string | Yes | `BTC`, `ETH`, `SOL`, or `XRP` |

**Response:**
```json
{
  "exchange": "hyperliquid_perp",
  "symbol": "BTC",
  "timestamp": "2026-03-27 14:30:00.123",
  "best_bid": 87420.50,
  "best_ask": 87421.00,
  "mid_price": 87420.75,
  "spread": 0.50,
  "bid_depth_total": 4250000,
  "ask_depth_total": 3890000,
  "bids": [[87420.5, 1.2], [87420.0, 0.8]],
  "asks": [[87421.0, 0.5], [87421.5, 1.1]]
}
```

### GET /v1/exchange/snapshots

Historical exchange orderbook snapshots (1/sec sampling, lightweight — no full bid/ask arrays).

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `exchange` | string | Yes | `hyperliquid_perp` |
| `symbol` | string | Yes | `BTC`, `ETH`, `SOL`, or `XRP` |
| `from` | string | No | Start timestamp (defaults to last 24h) |
| `to` | string | No | End timestamp |
| `limit` | number | No | Max rows (default 500, max 5000) |

---

## Snapshot Endpoints (API Key Required)

### GET /api/snapshot

Historical snapshot at a specific timestamp. Subject to tier history depth limits.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | string | Yes | Timestamp (ISO 8601 or `YYYY-MM-DD HH:MM:SS`) |
| `marketId` | string | No | Filter by conditionId |
| `crypto` | string | No | Filter by crypto |
| `timeframe` | string | No | Filter by timeframe |
| `includebook` | string | No | Set to `true` for full bid/ask arrays |

### GET /api/snapshot/latest

Last 5 snapshots across all tokens. Useful for checking data freshness.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `crypto` | string | No | Filter by crypto |
| `timeframe` | string | No | Filter by timeframe |

---

## API Key Management (Clerk Auth Required)

### POST /v1/api-keys

Generate a new API key. Limited by tier (Free: 1, Pro: 5, Enterprise: 20).

### GET /v1/api-keys

List all API keys for the authenticated user.

### GET /v1/api-keys/validate

Validate an API key (pass via `X-API-Key` header).

### DELETE /v1/api-keys/:key

Revoke an API key by hash or raw key.

---

## Billing Endpoints

### GET /v1/user/tier (Clerk Auth or API Key)

Current tier, credits, and limits.

**Response:**
```json
{
  "tier": "pro",
  "creditsRemaining": 48500,
  "creditsTotal": 50000,
  "rateLimitRpm": 500,
  "wsConnectionsMax": 1,
  "historyDepthHours": 0,
  "mcpAccess": "full",
  "expiresAt": "2026-04-27T00:00:00.000Z",
  "limits": { "rpm": 500, "wsMax": 1, "historyHours": 0, "mcp": "full", "maxKeys": 5 }
}
```

### GET /v1/payments/subscription (Clerk Auth)

Current Clerk Billing subscription status.

**Response:**
```json
{
  "provider": "clerk",
  "plan": "pro",
  "tier": "pro",
  "creditsRemaining": 48500,
  "expiresAt": "2026-04-27T00:00:00.000Z",
  "limits": { "rpm": 500, "wsMax": 1, "historyHours": 0, "mcp": "full", "maxKeys": 5 }
}
```

### GET /v1/payments/packs

Available tiers and credit packs with pricing.

### POST /v1/payments/create-invoice (Clerk Auth)

Create crypto payment invoice via NOWPayments.

**Request:** `{ "pack": "pro_monthly", "currency": "usdttrc20" }`

---

## x402 Micropayments

Any protected endpoint accepts pay-per-request via the x402 protocol. Send a signed USDC payment ($0.001/request) in the `X-PAYMENT` header — no API key or account needed.

x402 requests bypass rate limits, history depth restrictions, and credit deduction.

See [x402.org](https://x402.org) for client libraries and protocol details.

---

## Error Handling

All errors follow:

```json
{ "error": "Error message", "message": "Human-readable details" }
```

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | Bad request — invalid parameters |
| 401 | Unauthorized — missing/invalid API key |
| 402 | Payment required — insufficient credits or x402 payment needed |
| 403 | Forbidden — insufficient tier |
| 404 | Not found |
| 429 | Rate limited |
| 500 | Internal server error |

### Response Headers

```
X-RateLimit-Limit: 500
X-RateLimit-Remaining: 487
X-RateLimit-Reset: 1711278060
X-Credits-Cost: 5
X-Credits-Remaining: 48500
X-History-Limit-Hours: 0
```
