# WebSocket API

Real-time orderbook streaming via WebSocket.

## Endpoint

```
wss://api.resolvedmarkets.com/ws/orderbook
```

## Connection Flow

1. Connect to the WebSocket endpoint
2. Send auth message within **5 seconds**:

```json
{ "type": "auth", "apiKey": "rm_your_key" }
```

3. Receive confirmation:

```json
{ "type": "auth", "status": "ok" }
```

4. Subscribe to a crypto:

```json
{ "type": "subscribe", "crypto": "BTC" }
```

5. Receive real-time updates:

```json
{
  "type": "snapshot",
  "crypto": "BTC",
  "tokenSide": "UP",
  "tokenId": "abc123",
  "bids": [{ "price": 0.65, "size": 1500.00 }],
  "asks": [{ "price": 0.66, "size": 800.00 }],
  "bestBid": 0.65,
  "bestAsk": 0.66,
  "midPrice": 0.655,
  "spread": 0.01,
  "timestamp": "2026-03-24T12:00:00.123Z"
}
```

## Auth Timeout

If no auth message is received within 5 seconds, the connection is closed with code `4001`.

## Subscription Options

| Crypto | Description |
|--------|-------------|
| `BTC` | Bitcoin markets |
| `ETH` | Ethereum markets |
| `SOL` | Solana markets |
| `XRP` | Ripple markets |

## Code Examples

### JavaScript

```javascript
const ws = new WebSocket("wss://api.resolvedmarkets.com/ws/orderbook");

ws.onopen = () => {
  ws.send(JSON.stringify({ type: "auth", apiKey: "rm_your_key" }));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "auth" && msg.status === "ok") {
    ws.send(JSON.stringify({ type: "subscribe", crypto: "BTC" }));
  } else if (msg.type === "snapshot") {
    console.log(`${msg.crypto} ${msg.tokenSide}: mid=${msg.midPrice} spread=${msg.spread}`);
  }
};
```

### Python

```python
import asyncio
import json
import websockets

async def stream():
    async with websockets.connect("wss://api.resolvedmarkets.com/ws/orderbook") as ws:
        await ws.send(json.dumps({"type": "auth", "apiKey": "rm_your_key"}))
        auth = json.loads(await ws.recv())
        assert auth["status"] == "ok"

        await ws.send(json.dumps({"type": "subscribe", "crypto": "BTC"}))
        async for message in ws:
            data = json.loads(message)
            if data["type"] == "snapshot":
                print(f"{data['crypto']} {data['tokenSide']}: {data['midPrice']}")

asyncio.run(stream())
```
