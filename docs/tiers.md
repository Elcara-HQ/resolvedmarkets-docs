# Tiers & Pricing

## Plans

| Feature | Free | Pro ($17/mo) | Enterprise ($249/mo) |
|---------|------|-------------|----------------------|
| Crypto markets | BTC (4 markets) | All (BTC/ETH/SOL/XRP) | Everything |
| Orderbook depth | 20 levels | Full depth | Full depth |
| Weather data | 7-day daily | Unlimited | Unlimited |
| Sports / Social / Equities | -- | All included | All + odds |
| Hyperliquid perp data | -- | BTC/ETH/SOL/XRP | BTC/ETH/SOL/XRP |
| Rate limit | 60/min | 500/min | 3000/min |
| History access | 24 hours | Unlimited | Unlimited |
| WebSocket | -- | 1 connection | 10 connections |
| MCP access | Read-only | Full | Full |
| Max API keys | 1 | 5 | 20 |
| Support | Community | Priority | White-glove onboarding |
| Infrastructure | Shared | Shared | Dedicated server |
| Custom endpoints | -- | -- | Yes |

## Credit System

Each API request costs credits based on endpoint complexity:

| Request type | Cost |
|-------------|------|
| Simple queries (markets/live, categories, orderbook) | 1 credit |
| Historical snapshots (snapshot at timestamp) | 5 credits |
| Time-series queries (market snapshots, exchange history) | 10 credits |

Free-tier users are exempt from credit deduction (rate-limited only). Paid tiers receive monthly credits with their subscription. Credits never expire.

### Credit Packs (add-on)

| Pack | Price | Credits |
|------|-------|---------|
| Starter | $2 | 1,000 |
| Standard | $10 | 10,000 |
| Bulk | $49 | 100,000 |

Response headers show credit usage:

```
X-Credits-Cost: 5
X-Credits-Remaining: 48500
```

When credits are exhausted, you'll receive a `402` status with instructions to purchase more.

## Payment Methods

Three payment options are available:

- **Card** — Subscribe via Clerk Billing (powered by Stripe). Manage subscriptions from the pricing page.
- **Crypto** — Pay with 200+ cryptocurrencies via NOWPayments (BTC, ETH, USDT, etc.)
- **x402 Micropayments** — Pay per request with USDC on Base ($0.001/request). No account needed. Send `X-PAYMENT` header with signed payment proof.

## Rate Limits

Rate limit headers are included in every response:

```
X-RateLimit-Limit: 500
X-RateLimit-Remaining: 487
X-RateLimit-Reset: 1711278060
```

When rate limited, you'll receive a `429` status with error code `RATE_LIMITED`.

x402 paid requests bypass tier rate limits entirely.
