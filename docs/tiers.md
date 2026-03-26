# Tiers & Pricing

## Plans

| Feature | Free | Pro ($29/mo) | Enterprise ($99/mo) |
|---------|------|-------------|---------------------|
| Rate limit | 60/min | 500/min | 3000/min |
| History access | 1 hour | 30 days | Full archive |
| WebSocket | No | 2 connections | 10 connections |
| MCP access | No | Read-only | Full |
| Max API keys | 1 | 5 | 20 |

## Payments

Payments are processed via NOWPayments (cryptocurrency). Prepaid credit packs are also available.

## Rate Limits

Rate limit headers are included in every response:

```
X-RateLimit-Limit: 500
X-RateLimit-Remaining: 487
X-RateLimit-Reset: 1711278060
```

When rate limited, you'll receive a `429` status with error code `RATE_LIMITED`.
