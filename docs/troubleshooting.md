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
| Free       | 60/min     |
| Pro        | 500/min    |
| Enterprise | 3000/min   |

Upgrade your tier at the [pricing page](https://resolvedmarkets.com/pricing) if you need higher throughput.

---

### Gaps in snapshot sequence numbers

**Symptom:** Sequential snapshots for a token have non-consecutive `sequenceNumber` values.

**Cause:** Gaps do not necessarily indicate data loss. The capture pipeline throttles snapshots to a 50ms minimum interval per token and deduplicates consecutive identical orderbook states using top-5 bid/ask level fingerprinting. Events that arrive within the throttle window or produce duplicate fingerprints are intentionally skipped.

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

**Cause:** Authentication alone does not start the data stream. You must explicitly subscribe to one or more crypto symbols.

**Fix:** After receiving the auth confirmation, send a subscribe message:
```json
{ "type": "subscribe", "crypto": "BTC" }
```
Valid crypto values are `BTC`, `ETH`, `SOL`, and `XRP`.

---

### API key returns 401 Unauthorized

**Symptom:** Requests with a valid-looking `rm_` API key return HTTP 401.

**Cause:** The key may have been revoked, or it may belong to a different user account.

**Fix:** List your active keys by calling `GET /v1/api-keys` (requires Clerk authentication). If the key does not appear in the list, it has been revoked. Generate a new key via `POST /v1/api-keys`.

---

### Historical snapshots return empty results

**Symptom:** `GET /v1/markets/:id/snapshots` returns an empty array even though the market has been active.

**Cause:** Your tier restricts how far back you can query historical data.

**Fix:** Check your tier's history window:

| Tier       | History Access |
|------------|----------------|
| Free       | 1 hour         |
| Pro        | 30 days        |
| Enterprise | Full archive   |

Adjust your query's time range to fall within your tier's window, or upgrade for deeper history.

---

### Market not found when searching by slug

**Symptom:** `GET /v1/markets/by-slug/:slug` returns 404 for a Solana market you know exists.

**Cause:** Solana markets use inconsistent slug prefixes depending on their timeframe. Short timeframes (5m, 15m) use the `sol-` prefix, while longer timeframes (1h, 1d) use the `solana-` prefix.

**Fix:** Try both slug variants. For example, if `sol-usdt-1h` returns 404, try `solana-usdt-1h`, and vice versa. Other tokens (BTC, ETH, XRP) use consistent prefixes across all timeframes.

---

### CORS errors when calling the API from a browser

**Symptom:** Browser console shows `Access-Control-Allow-Origin` errors when making fetch or XMLHttpRequest calls to the API.

**Cause:** The Resolved Markets API is designed for server-to-server communication and does not set permissive CORS headers for browser-origin requests.

**Fix:** Do not call the API directly from client-side JavaScript. Instead, set up a server-side proxy (e.g., a Next.js API route or Express endpoint) that forwards requests to the Resolved Markets API and returns the results to your frontend.

---

### Stale crypto prices in snapshot data

**Symptom:** The `cryptoPriceStalenessMs` field in snapshots shows large values (several seconds or more), and the associated crypto price looks outdated.

**Cause:** The backend streams real-time trades from Binance WebSocket to track current crypto prices. If the Binance WebSocket connection drops or experiences issues, the last known price becomes stale. The `cryptoPriceStalenessMs` field measures how many milliseconds have elapsed since the last Binance price update.

**Fix:** Check the `cryptoPriceStalenessMs` value before relying on the crypto price. Values under 1000ms are generally fresh. If you consistently see high staleness, the backend's Binance connection may need attention. For self-hosted instances, check the backend logs for WebSocket reconnection errors.

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
