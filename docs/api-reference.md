# API Reference

Base URL: `https://api.resolvedmarkets.com`

## Public Endpoints (No Auth)

### GET /health

Health check.

**Response:**
```json
{ "status": "ok", "uptime": 123456, "timestamp": "2026-03-24T12:00:00.000Z" }
```

### GET /v1/public-stats

Platform statistics.

**Response:**
```json
{
  "snapshotCount": 15234567,
  "activeMarkets": 42,
  "cryptoPrices": { "BTC": 95432.50, "ETH": 3421.80, "SOL": 187.25, "XRP": 2.34 },
  "timestamp": "2026-03-24T12:00:00.000Z"
}
```

---

## Market Endpoints (API Key Required)

### GET /v1/categories

List all market categories.

**Response:**
```json
{ "categories": ["crypto", "sports", "economics", "weather"] }
```

### GET /v1/markets/live

List active markets.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | string | No | Filter: crypto, sports, economics, weather |

**Response:**
```json
{
  "markets": [{
    "conditionId": "0x1234...",
    "slug": "will-btc-be-above-100000-on-march-25",
    "question": "Will BTC be above $100,000 on March 25?",
    "category": "crypto",
    "tokens": [
      { "tokenId": "abc123", "outcome": "Yes", "side": "UP", "price": 0.65 },
      { "tokenId": "def456", "outcome": "No", "side": "DOWN", "price": 0.35 }
    ],
    "endDate": "2026-03-25T00:00:00.000Z",
    "active": true
  }]
}
```

### GET /v1/markets/history/recent

Recently resolved markets from materialized view.

### GET /v1/markets/history

Full historical markets with pagination.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | string | No | Filter by category |
| `limit` | number | No | Results per page (default: 50, max: 200) |
| `offset` | number | No | Pagination offset |

### GET /v1/markets/by-slug/:slug

Look up a market by its URL slug.

**Example:** `GET /v1/markets/by-slug/will-btc-be-above-100000-on-march-25`

### GET /v1/markets/by-slug/:slug/orderbook

Live orderbook for a market by slug. Same response as `/v1/markets/:id/orderbook`.

### GET /v1/markets/:id/orderbook

Live orderbook for a market by conditionId. Returns both UP and DOWN token books.

**Response:**
```json
{
  "market": {
    "conditionId": "0x1234...",
    "tokens": {
      "UP": {
        "tokenId": "abc123",
        "bids": [{ "price": 0.65, "size": 1500.00 }],
        "asks": [{ "price": 0.66, "size": 800.00 }],
        "bestBid": 0.65, "bestAsk": 0.66,
        "midPrice": 0.655, "spread": 0.01,
        "totalBidDepth": 15000.00, "totalAskDepth": 12000.00
      },
      "DOWN": { "..." : "..." }
    },
    "timestamp": "2026-03-24T12:00:00.123Z"
  }
}
```

### GET /v1/markets/:id/snapshots

Paginated historical orderbook snapshots.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `limit` | number | No | Results per page (default: 100, max: 1000) |
| `offset` | number | No | Pagination offset |
| `from` | string | No | Start timestamp (ISO 8601) |
| `to` | string | No | End timestamp (ISO 8601) |
| `tokenSide` | string | No | Filter: `UP` or `DOWN` |

**Response:**
```json
{
  "snapshots": [{
    "tokenId": "abc123", "tokenSide": "UP",
    "bids": [{ "price": 0.65, "size": 1500.00 }],
    "asks": [{ "price": 0.66, "size": 800.00 }],
    "bestBid": 0.65, "bestAsk": 0.66,
    "midPrice": 0.655, "spread": 0.01,
    "totalBidDepth": 15000.00, "totalAskDepth": 12000.00,
    "eventTimestamp": "2026-03-24T12:00:00.100Z",
    "captureTimestamp": "2026-03-24T12:00:00.123Z",
    "sequenceNumber": 42567
  }],
  "total": 50000, "limit": 100, "offset": 0
}
```

### GET /v1/markets/:id/summary

Aggregated market statistics.

**Response:**
```json
{
  "summary": {
    "conditionId": "0x1234...",
    "avgSpread": 0.012, "minSpread": 0.005, "maxSpread": 0.025,
    "avgMidPrice": 0.652,
    "priceRange": { "low": 0.58, "high": 0.72 },
    "avgBidDepth": 14500.00, "avgAskDepth": 12300.00,
    "snapshotCount": 85000, "tradeCount": 3200,
    "period": "24h"
  }
}
```

---

## Snapshot Endpoints (API Key Required)

### GET /api/snapshot

Historical snapshot at a specific timestamp.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | string | Yes | ISO 8601 timestamp |
| `marketId` | string | Yes | Market conditionId |

**Example:** `GET /api/snapshot?timestamp=2026-03-24T12:00:00Z&marketId=0x1234`

### GET /api/snapshot/latest

Last 5 snapshots across all tokens.

---

## API Key Management (Clerk Auth Required)

### POST /v1/api-keys

Generate a new API key.

### GET /v1/api-keys

List all API keys for the authenticated user.

### GET /v1/api-keys/validate

Validate an API key (pass via `X-API-Key` header).

### DELETE /v1/api-keys/:key

Revoke an API key.

---

## Payment Endpoints (Clerk Auth Required)

### GET /user/tier

Current tier information.

### GET /payments/packs

Available credit packs.

### POST /payments/create-invoice

Create crypto payment invoice via NOWPayments.

**Request:** `{ "packId": "pack_starter" }`

---

## Error Handling

All errors follow:

```json
{ "error": "Error message", "code": "ERROR_CODE" }
```

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request |
| 401 | Unauthorized — missing/invalid API key |
| 403 | Forbidden — insufficient tier |
| 404 | Not found |
| 429 | Rate limited |
| 500 | Internal server error |

### Error Codes

| Code | Description |
|------|-------------|
| `INVALID_API_KEY` | Missing, malformed, or revoked |
| `RATE_LIMITED` | Rate exceeded for your tier |
| `TIER_RESTRICTED` | Feature not available on your tier |
| `MARKET_NOT_FOUND` | No market with given ID/slug |
| `INVALID_TIMESTAMP` | Not valid ISO 8601 |

### Rate Limit Headers

```
X-RateLimit-Limit: 500
X-RateLimit-Remaining: 487
X-RateLimit-Reset: 1711278060
```
