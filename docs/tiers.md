# Tiers & Pricing

## Plans

| Feature | Free | Pro ($17/mo) | Scale ($49/mo) | Enterprise ($549/mo) |
|---------|------|--------------|----------------|----------------------|
| Annual billing | -- | $126/yr | $360/yr | -- |
| Monthly credits | 5,000 | 50,000 | 500,000 | 5,000,000 |
| Rate limit | 300/min | 300/min | 1,000/min | 3,000/min |
| Crypto markets | All coins | All coins | All coins | All coins |
| Sports / Weather / Economics / Social / Equities | -- | -- | Included | Included |
| Hyperliquid perp data | -- | -- | Included | Included |
| Orderbook depth | Full depth | Full depth | Full depth | Full depth |
| History access | Unlimited | Unlimited | Unlimited | Unlimited |
| WebSocket | -- | 1 connection | 5 connections | 10 connections |
| CSV / TSV export | -- | -- | Yes | Yes |
| MCP access | Full | Full | Full | Full |
| Max API keys | 2 | 5 | 10 | 20 |
| Team access | -- | -- | -- | Add members |
| Support | Community | Priority | Priority | White-glove |
| Infrastructure | Shared | Shared | Shared | Dedicated |
| Custom endpoints | -- | -- | -- | Yes |

Free and Pro include the crypto category only. All other categories and the Hyperliquid exchange endpoints start at Scale. A request for a category outside your plan returns `403` with `tier_not_allowed`.

## Credit System

Every plan, Free included, is metered in credits. Each API request costs credits based on the endpoint:

| Request type | Cost |
|-------------|------|
| Simple queries (markets/live, categories, orderbook, market history, exchange endpoints, `/api/snapshot/latest`) | 1 credit |
| Snapshot at a timestamp (`/api/snapshot`) and market summary | 3 credits |
| Paginated time-series (market snapshots, trades, wallet fills) | 5 credits per page |
| Backtest run or backtest agent call | 25 credits |

Each plan receives its monthly credits at the start of each billing month. The balance is topped up to the plan amount; unused credits do not add up from month to month.

### Credit Packs (add-on)

Credit packs are top-ups for paid plans. A Free account must subscribe first. Use a pack within the billing period: the next renewal only tops the balance up to the plan amount.

| Pack | Price | Credits |
|------|-------|---------|
| `credits_10k` | $5 | 10,000 |
| `credits_100k` | $20 | 100,000 |
| `credits_500k` | $50 | 500,000 |

Response headers show credit usage:

```
X-Credits-Cost: 5
X-Credits-Remaining: 48500
```

When credits are exhausted, you'll receive a `402` status with the credits required and the credits remaining.

## Payment Methods

Three payment options are available:

- **Card** — Subscribe via Clerk Billing (powered by Stripe). Manage subscriptions from the pricing page. Credit packs use Stripe Checkout.
- **Crypto** — Pay with 200+ cryptocurrencies via NOWPayments (BTC, ETH, USDT, etc.)
- **x402 Micropayments** — Pay per request with USDC on Base ($0.001/request). No account needed. Send `X-PAYMENT` header with signed payment proof.

## Rate Limits

Rate limit headers are included in every response:

```
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 287
X-RateLimit-Reset: 1711278060
```

When rate limited, you'll receive a `429` status with a `Retry-After` header.

x402 paid requests bypass tier rate limits entirely.
