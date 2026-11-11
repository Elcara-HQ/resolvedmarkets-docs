# WebSocket API

Orderbook updates for one coin on each connection. The server sends them every 2 seconds.

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

3. Receive confirmation, then a `markets` message with every market your plan can see (items shortened here):

```json
{ "type": "auth", "status": "ok" }
{ "type": "markets", "data": [{ "conditionId": "0x1234...", "category": "crypto", "crypto": "BTC", "timeframe": "5m", "slug": "btc-updown-5m-1772448000" }] }
```

4. Subscribe to one crypto:

```json
{ "type": "subscribe", "crypto": "BTC" }
```

5. Receive one `orderbook` message at once, then one every 2 seconds. Each message holds the current books of every tracked market of the coin (fields of `up` and `down` shortened here):

```json
{
  "type": "orderbook",
  "markets": [
    {
      "marketId": "0x1234...",
      "crypto": "BTC",
      "timeframe": "5m",
      "question": "Bitcoin Up or Down - March 24, 12:00PM-12:05PM ET",
      "cryptoPrice": 87420.5,
      "up": {
        "tokenId": "abc123",
        "timestamp": 1774353600123,
        "sequenceNumber": 4821,
        "bids": [{ "price": 0.65, "size": 1500.0 }],
        "asks": [{ "price": 0.66, "size": 800.0 }],
        "bestBid": 0.65,
        "bestAsk": 0.66,
        "midPrice": 0.655,
        "spread": 0.01,
        "bidDepth": 975.0,
        "askDepth": 528.0
      },
      "down": {
        "tokenId": "def456",
        "timestamp": 1774353600098,
        "sequenceNumber": 4790,
        "bids": [{ "price": 0.34, "size": 900.0 }],
        "asks": [{ "price": 0.35, "size": 1200.0 }],
        "bestBid": 0.34,
        "bestAsk": 0.35,
        "midPrice": 0.345,
        "spread": 0.01,
        "bidDepth": 306.0,
        "askDepth": 420.0
      }
    }
  ]
}
```

`up` is the book of the first token of the market (Up or Yes), `down` the book of the second (Down or No). A side is `null` when the server has no book for that token yet.

| Field of `up` and `down` | Meaning |
|--------------------------|---------|
| `tokenId` | Token of this side |
| `timestamp` | Time of the last change of the book, in epoch milliseconds |
| `sequenceNumber` | Change counter of the book |
| `bids`, `asks` | All price levels, best price first |
| `bestBid`, `bestAsk`, `midPrice`, `spread` | Top of the book |
| `bidDepth`, `askDepth` | Sum of price × size of each side |

`up` and `down` also have other snapshot fields, such as `eventTimestamp` and `captureTimestamp`.

## One Coin per Connection

Each connection follows one coin. A new `subscribe` message replaces the coin of the connection. It does not add a coin. The server has no `unsubscribe` message.

To follow several coins, open one connection for each coin. Your plan's connection limit (see [Plan Limits](#plan-limits)) is also the number of coins that you can follow at the same time.

## Update Interval

The server sends the books of the subscribed coin every 2 seconds. Each message holds the books at the time of sending, not each change between two messages. For the full capture rate (up to 10 snapshots a second on crypto up/down markets), read the stored snapshots with `GET /v1/markets/:id/snapshots`.

The server sends the `markets` message again when the list of markets changes. It checks the list every 10 seconds.

## Plan Limits

| Tier | WebSocket connections |
|------|-----------------------|
| Free | 0 (no WebSocket access) |
| Pro | 1 |
| Scale | 5 |
| Enterprise | 10 |

The server closes the connection with code `4003` and one of these close reasons:

| Close reason | Cause | What a client does |
|--------------|-------|--------------------|
| `Invalid API key` | The key is wrong or revoked. | Stop. |
| `Tier restriction` | The plan has no WebSocket access (Free). | Stop. |
| `Connection limit` | All connections of the plan are in use. | Connect again after 60 seconds. |

The server can count a dropped connection for up to 60 seconds. A reconnect after a network error can get `Connection limit` in that time.

## Auth Timeout

If no auth message is received within 5 seconds, the connection is closed with code `4001`.

## Subscription Options

| Crypto | Description |
|--------|-------------|
| `BTC` | Bitcoin markets |
| `ETH` | Ethereum markets |
| `SOL` | Solana markets |
| `XRP` | Ripple markets |
| `DOGE` | Dogecoin markets |
| `HYPE` | Hyperliquid (HYPE) markets |
| `BNB` | BNB markets |

The value is not case-sensitive. An `orderbook` message holds every tracked crypto market of the coin: its up/down markets and, where they exist, its hit-price markets.

A coin can have several up/down markets of one timeframe at the same time: the live window and upcoming windows. The `orderbook` message does not say which window is live. The `markets` message gives the `endDate` of each market, and its `conditionId` is the `marketId` of the `orderbook` message. The live window is the up/down market of that timeframe with the earliest `endDate` in the future. The hit-price markets of a coin are strike levels of one day with the same `endDate`, so this rule does not apply to them.

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
  } else if (msg.type === "orderbook") {
    for (const m of msg.markets) {
      if (m.up) console.log(`${m.crypto} ${m.timeframe} UP: mid=${m.up.midPrice} spread=${m.up.spread}`);
    }
  }
};
```

### Python

The first `markets` message can be larger than 1 MiB on Scale and Enterprise. The Python `websockets` library closes the connection on a message larger than 1 MiB by default, so the example sets `max_size=None`.

```python
import asyncio
import json
import websockets

async def stream():
    async with websockets.connect("wss://api.resolvedmarkets.com/ws/orderbook", max_size=None) as ws:
        await ws.send(json.dumps({"type": "auth", "apiKey": "rm_your_key"}))
        auth = json.loads(await ws.recv())
        assert auth["status"] == "ok"

        await ws.send(json.dumps({"type": "subscribe", "crypto": "BTC"}))
        async for message in ws:
            data = json.loads(message)
            if data["type"] == "orderbook":
                for m in data["markets"]:
                    if m["up"]:
                        print(f"{m['crypto']} {m['timeframe']} UP: {m['up']['midPrice']}")

asyncio.run(stream())
```
