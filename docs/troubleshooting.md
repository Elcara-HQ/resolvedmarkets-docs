# Troubleshooting

Common issues and solutions when working with the Resolved Markets API.

---

### WebSocket connection closes after 5 seconds

**Symptom:** Your WebSocket connection to `/ws/orderbook` drops almost immediately with close code `4001`.

**Cause:** The server enforces a 5-second authentication timeout. If no valid `auth` message is received within that window, the connection is terminated.

**Fix:** Send the authentication message as soon as the connection opens:
```json
{ "type": "auth", "apiKey": "rm_your_key_here" }
```
Wait for `{ "type": "auth", "status": "ok" }` before subscribing.

---

### Getting 429 Too Many Requests

**Symptom:** API responses return HTTP 429 with a rate limit error.

**Cause:** You have exceeded the rate limit for your tier.

**Fix:** Check your current tier's rate limit and throttle your requests accordingly:

| Tier       | Rate Limit |
|------------|------------|
| Free       | 300/min    |
| Pro        | 300/min    |
| Scale      | 1,000/min  |
| Enterprise | 3,000/min  |

Upgrade your tier at the [pricing page](https://resolvedmarkets.com/pricing) if you need higher throughput.

---

### Gaps in snapshot sequence numbers

**Symptom:** Sequential snapshots for a token have non-consecutive `sequenceNumber` values.

**Cause:** Gaps do not necessarily indicate data loss. The capture pipeline throttles snapshots to a minimum interval for each orderbook. The interval depends on the market category: 100 ms on crypto up/down markets, up to 5 seconds in the slowest categories. The pipeline also deduplicates consecutive identical orderbook states using top-5 bid/ask level fingerprinting. Events that arrive within the throttle window or produce duplicate fingerprints are intentionally skipped.

**Fix:** Gaps from throttling and deduplication are normal and expected. Only investigate if you observe large, sustained jumps in sequence numbers, which could indicate a WebSocket disconnection on the backend side.

---

### UP + DOWN token prices don't sum to 1.00

**Symptom:** Adding the mid prices of the UP and DOWN tokens for a market yields a value slightly different from 1.00.

**Cause:** This is normal. Each token has its own orderbook with a bid-ask spread. The mid price is the average of the best bid and best ask, so the sum of both tokens' mid prices will deviate from 1.00 by the combined spread.

**Fix:** No fix needed. This is expected behavior in any market with a spread. If you need a "fair value" estimate, use the mid prices but account for the spread when placing orders.

---

### Empty orderbook response

**Symptom:** `GET /v1/markets/:id/orderbook` returns an orderbook with empty bid and ask arrays.

**Cause:** Markets approaching resolution may have `enableOrderBook: false` set by Polymarket, which removes all liquidity from the book.

**Fix:** Check the market's status. If it is close to its resolution time, empty books are expected. Query a different active market or wait for new markets to be created.

---

### WebSocket connected and authenticated but not receiving data

**Symptom:** You successfully connect and authenticate on the WebSocket, but no orderbook updates arrive.

**Cause:** Authentication alone does not start the data stream. You must subscribe to one crypto symbol. Each connection follows one symbol: a new `subscribe` replaces the last one. To follow several symbols, open one connection for each symbol.

**Fix:** After receiving the auth confirmation, send a subscribe message:
```json
{ "type": "subscribe", "crypto": "BTC" }
```
Valid crypto values are `BTC`, `ETH`, `SOL`, `XRP`, `DOGE`, `HYPE`, and `BNB`.

---

### API key returns 401 Unauthorized

**Symptom:** Requests with a valid-looking `rm_` API key return HTTP 401.

**Cause:** The key may have been revoked, or it may belong to a different user account.

**Fix:** List your active keys by calling `GET /v1/api-keys` (requires Clerk authentication). If the key does not appear in the list, it has been revoked. Generate a new key via `POST /v1/api-keys`.

---

### Historical snapshots return empty results

**Symptom:** `GET /v1/markets/:id/snapshots` returns an empty array even though the market has been active.

**Cause:** The time range of your query holds no snapshots for that market. History is unlimited on every tier, so the tier is not the cause.

**Fix:** Set `from` and `to` so that the range covers the time when the market was active.

---

### Market not found when searching by slug

**Symptom:** `GET /v1/markets/by-slug/:slug` returns 404 for a Solana market you know exists.

**Cause:** Solana markets use inconsistent slug prefixes depending on their timeframe. The 5m, 15m, and 4h timeframes use the `sol-` prefix, while the 1h and 1d timeframes use the `solana-` prefix.

**Fix:** Try both slug variants. For example, a 15m Solana slug starts with `sol-updown-15m-`, and a 1h Solana slug starts with `solana-up-or-down-`. BTC (`btc-`, `bitcoin-`), ETH (`eth-`, `ethereum-`), and DOGE (`doge-`, `dogecoin-`) change prefix in the same way. XRP, HYPE, and BNB use one prefix for all timeframes.

---

### CORS errors when calling the API from a browser

**Symptom:** Browser console shows `Access-Control-Allow-Origin` errors when making fetch or XMLHttpRequest calls to the API.

**Cause:** The Resolved Markets API is designed for server-to-server communication and does not set permissive CORS headers for browser-origin requests.

**Fix:** Do not call the API directly from client-side JavaScript. Instead, set up a server-side proxy (e.g., a Next.js API route or Express endpoint) that forwards requests to the Resolved Markets API and returns the results to your frontend.

---

### Stale crypto prices in snapshot data

**Symptom:** The `crypto_price_age_ms` field of snapshot rows shows large values (several seconds or more), and the `crypto_price` looks outdated.

**Cause:** The backend reads coin prices from two WebSocket feeds: the Binance best bid and ask (`bookTicker`) for BTC, ETH, SOL, XRP, DOGE and BNB, and Hyperliquid `allMids` for HYPE. If a feed drops, the last known price becomes stale. `crypto_price_age_ms` is the number of milliseconds from the last price update of the coin to the capture of the snapshot. `-1` means that the age is not known or that the market is not a crypto market.

**Fix:** Check the `crypto_price_age_ms` value before relying on the crypto price. Values under 1000ms are generally fresh. If you consistently see high values, the price feed of the backend may need attention. For self-hosted instances, check the backend logs for WebSocket reconnection errors.

---

### Connection refused on localhost:3001

**Symptom:** API calls to `http://localhost:3001` fail with `ECONNREFUSED`.

**Cause:** The backend server is not running.

**Fix:** Start the development environment:
```bash
pnpm dev
```
This starts both the backend (port 3001) and frontend. To run only the backend:
```bash
cd packages/backend && pnpm dev
```
Ensure Docker is running first (`pnpm db:up`) since the backend requires ClickHouse and Redis.
