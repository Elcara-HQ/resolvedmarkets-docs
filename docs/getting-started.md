# Getting Started

## Authentication

All authenticated endpoints require an API key passed via the `X-API-Key` header:

```
X-API-Key: rm_your_key
```

API keys are prefixed with `rm_`. Get one by signing up at [resolvedmarkets.com](https://resolvedmarkets.com) and visiting the API Keys page.

## Base URL

```
https://api.resolvedmarkets.com
```

## Your First API Call

### 1. Check the API is running

```bash
curl https://api.resolvedmarkets.com/health
```

### 2. List active markets

```bash
curl -H "X-API-Key: rm_your_key" \
  https://api.resolvedmarkets.com/v1/markets/live
```

### 3. Get an orderbook

```bash
curl -H "X-API-Key: rm_your_key" \
  https://api.resolvedmarkets.com/v1/markets/{conditionId}/orderbook
```

### 4. Stream real-time data

Connect via WebSocket and authenticate:

```json
{ "type": "auth", "apiKey": "rm_your_key" }
{ "type": "subscribe", "crypto": "BTC" }
```

## Code Examples

### JavaScript

```javascript
const API_KEY = "rm_your_key";

const res = await fetch("https://api.resolvedmarkets.com/v1/markets/live", {
  headers: { "X-API-Key": API_KEY }
});
const data = await res.json();
console.log(data.markets);
```

### Python

```python
import requests

API_KEY = "rm_your_key"
headers = {"X-API-Key": API_KEY}

res = requests.get("https://api.resolvedmarkets.com/v1/markets/live", headers=headers)
print(res.json())
```

### cURL

```bash
curl -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/live?category=crypto"
```
