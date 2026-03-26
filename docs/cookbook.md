# Cookbook

Copy-paste recipes for the Resolved Markets API. Every example is complete and runnable.

**Base URL:** `https://api.resolvedmarkets.com`
**Auth:** `X-API-Key: rm_your_key` header on all requests.

Replace `rm_your_key` with your actual API key and `YOUR_MARKET_ID` / `YOUR_TOKEN_ID` with real IDs from the `/v1/markets/live` endpoint.

---

## 1. Get the Current BTC Spread

Fetch the live orderbook for a BTC market and extract the bid-ask spread.

### cURL

```bash
curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook" | \
  jq '.tokens[0] | {bestBid, bestAsk, spread: (.bestAsk - .bestBid)}'
```

### JavaScript

```javascript
const res = await fetch(
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook",
  { headers: { "X-API-Key": "rm_your_key" } }
);
const data = await res.json();
const token = data.tokens[0];
const spread = token.bestAsk - token.bestBid;
console.log(`Best Bid: ${token.bestBid}, Best Ask: ${token.bestAsk}, Spread: ${spread.toFixed(4)}`);
```

### Python

```python
import requests

res = requests.get(
    "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook",
    headers={"X-API-Key": "rm_your_key"},
)
data = res.json()
token = data["tokens"][0]
spread = token["bestAsk"] - token["bestBid"]
print(f"Best Bid: {token['bestBid']}, Best Ask: {token['bestAsk']}, Spread: {spread:.4f}")
```

---

## 2. List All Active Crypto Markets

Retrieve every currently active crypto prediction market.

### cURL

```bash
curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/live?category=crypto"
```

### JavaScript

```javascript
const res = await fetch(
  "https://api.resolvedmarkets.com/v1/markets/live?category=crypto",
  { headers: { "X-API-Key": "rm_your_key" } }
);
const markets = await res.json();
markets.forEach((m) => console.log(`${m.slug} — ${m.question}`));
```

### Python

```python
import requests

res = requests.get(
    "https://api.resolvedmarkets.com/v1/markets/live?category=crypto",
    headers={"X-API-Key": "rm_your_key"},
)
for m in res.json():
    print(f"{m['slug']} — {m['question']}")
```

---

## 3. Stream Orderbooks in Real-Time

Connect via WebSocket, authenticate, subscribe to BTC, and log every update.

### JavaScript

```javascript
const WebSocket = require("ws");

const ws = new WebSocket("wss://api.resolvedmarkets.com/ws/orderbook");

ws.on("open", () => {
  ws.send(JSON.stringify({ type: "auth", apiKey: "rm_your_key" }));
});

ws.on("message", (raw) => {
  const msg = JSON.parse(raw);

  if (msg.type === "auth" && msg.status === "ok") {
    console.log("Authenticated");
    ws.send(JSON.stringify({ type: "subscribe", crypto: "BTC" }));
  } else if (msg.type === "snapshot") {
    console.log(
      `[${new Date().toISOString()}] ${msg.tokenSide} ` +
      `bid=${msg.bestBid} ask=${msg.bestAsk} spread=${(msg.bestAsk - msg.bestBid).toFixed(4)}`
    );
  }
});

ws.on("close", (code) => console.log("Disconnected:", code));
ws.on("error", (err) => console.error("Error:", err.message));
```

### Python

```python
import json
import websocket

def on_open(ws):
    ws.send(json.dumps({"type": "auth", "apiKey": "rm_your_key"}))

def on_message(ws, raw):
    msg = json.loads(raw)
    if msg.get("type") == "auth" and msg.get("status") == "ok":
        print("Authenticated")
        ws.send(json.dumps({"type": "subscribe", "crypto": "BTC"}))
    elif msg.get("type") == "snapshot":
        spread = msg["bestAsk"] - msg["bestBid"]
        print(f"{msg['tokenSide']} bid={msg['bestBid']} ask={msg['bestAsk']} spread={spread:.4f}")

ws = websocket.WebSocketApp(
    "wss://api.resolvedmarkets.com/ws/orderbook",
    on_open=on_open,
    on_message=on_message,
)
ws.run_forever()
```

### cURL

```bash
# cURL does not support WebSockets natively. Use websocat instead:
echo '{"type":"auth","apiKey":"rm_your_key"}' | \
  websocat "wss://api.resolvedmarkets.com/ws/orderbook" --text -n1
# Then send: {"type":"subscribe","crypto":"BTC"}
```

---

## 4. Download 24h of Historical Snapshots to CSV

Fetch the last 24 hours of snapshots for a token and write them to a CSV file.

### cURL

```bash
FROM=$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)
TO=$(date -u +%Y-%m-%dT%H:%M:%SZ)

curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/snapshots?from=$FROM&to=$TO&limit=10000" | \
  jq -r '["timestamp","bestBid","bestAsk","midPrice","spread"], (.[] | [.captureTimestamp,.bestBid,.bestAsk,.midPrice,.spread]) | @csv' \
  > snapshots_24h.csv
```

### JavaScript

```javascript
const fs = require("fs");

const from = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
const to = new Date().toISOString();

const res = await fetch(
  `https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/snapshots?from=${from}&to=${to}&limit=10000`,
  { headers: { "X-API-Key": "rm_your_key" } }
);
const snapshots = await res.json();

const header = "timestamp,bestBid,bestAsk,midPrice,spread\n";
const rows = snapshots
  .map((s) => `${s.captureTimestamp},${s.bestBid},${s.bestAsk},${s.midPrice},${s.spread}`)
  .join("\n");

fs.writeFileSync("snapshots_24h.csv", header + rows);
console.log(`Wrote ${snapshots.length} rows to snapshots_24h.csv`);
```

### Python

```python
import csv
import requests
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
from_ts = (now - timedelta(hours=24)).isoformat()
to_ts = now.isoformat()

res = requests.get(
    "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/snapshots",
    headers={"X-API-Key": "rm_your_key"},
    params={"from": from_ts, "to": to_ts, "limit": 10000},
)
snapshots = res.json()

with open("snapshots_24h.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "bestBid", "bestAsk", "midPrice", "spread"])
    for s in snapshots:
        writer.writerow([s["captureTimestamp"], s["bestBid"], s["bestAsk"], s["midPrice"], s["spread"]])

print(f"Wrote {len(snapshots)} rows to snapshots_24h.csv")
```

---

## 5. Build a Spread Alert Bot

Poll the orderbook every 10 seconds and print an alert when the spread exceeds a threshold.

### JavaScript

```javascript
const API_KEY = "rm_your_key";
const MARKET_ID = "YOUR_MARKET_ID";
const THRESHOLD = 0.05;

async function checkSpread() {
  const res = await fetch(
    `https://api.resolvedmarkets.com/v1/markets/${MARKET_ID}/orderbook`,
    { headers: { "X-API-Key": API_KEY } }
  );
  const data = await res.json();
  for (const token of data.tokens) {
    const spread = token.bestAsk - token.bestBid;
    if (spread > THRESHOLD) {
      console.log(`ALERT [${token.tokenSide}] Spread ${spread.toFixed(4)} > ${THRESHOLD}`);
    } else {
      console.log(`OK    [${token.tokenSide}] Spread ${spread.toFixed(4)}`);
    }
  }
}

setInterval(checkSpread, 10_000);
checkSpread();
```

### Python

```python
import time
import requests

API_KEY = "rm_your_key"
MARKET_ID = "YOUR_MARKET_ID"
THRESHOLD = 0.05

while True:
    res = requests.get(
        f"https://api.resolvedmarkets.com/v1/markets/{MARKET_ID}/orderbook",
        headers={"X-API-Key": API_KEY},
    )
    data = res.json()
    for token in data["tokens"]:
        spread = token["bestAsk"] - token["bestBid"]
        tag = "ALERT" if spread > THRESHOLD else "OK   "
        print(f"{tag} [{token['tokenSide']}] Spread {spread:.4f}")
    time.sleep(10)
```

### cURL

```bash
THRESHOLD=0.05
while true; do
  curl -s -H "X-API-Key: rm_your_key" \
    "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook" | \
    jq --argjson t "$THRESHOLD" '.tokens[] | {side: .tokenSide, spread: (.bestAsk - .bestBid)} | if .spread > $t then "ALERT \(.side) spread=\(.spread)" else "OK    \(.side) spread=\(.spread)" end'
  sleep 10
done
```

---

## 6. Compare UP vs DOWN Liquidity

Fetch the orderbook and compare total depth on the UP and DOWN sides.

### cURL

```bash
curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook" | \
  jq '.tokens[] | {side: .tokenSide, totalBidDepth, totalAskDepth, totalLiquidity: (.totalBidDepth + .totalAskDepth)}'
```

### JavaScript

```javascript
const res = await fetch(
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook",
  { headers: { "X-API-Key": "rm_your_key" } }
);
const data = await res.json();

for (const token of data.tokens) {
  const total = token.totalBidDepth + token.totalAskDepth;
  console.log(
    `${token.tokenSide}: Bid Depth = ${token.totalBidDepth}, Ask Depth = ${token.totalAskDepth}, Total = ${total}`
  );
}

const up = data.tokens.find((t) => t.tokenSide === "UP");
const down = data.tokens.find((t) => t.tokenSide === "DOWN");
const upTotal = up.totalBidDepth + up.totalAskDepth;
const downTotal = down.totalBidDepth + down.totalAskDepth;
console.log(`\nUP/DOWN liquidity ratio: ${(upTotal / downTotal).toFixed(2)}`);
```

### Python

```python
import requests

res = requests.get(
    "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook",
    headers={"X-API-Key": "rm_your_key"},
)
data = res.json()

totals = {}
for token in data["tokens"]:
    total = token["totalBidDepth"] + token["totalAskDepth"]
    totals[token["tokenSide"]] = total
    print(f"{token['tokenSide']}: Bid={token['totalBidDepth']}, Ask={token['totalAskDepth']}, Total={total}")

ratio = totals["UP"] / totals["DOWN"]
print(f"\nUP/DOWN liquidity ratio: {ratio:.2f}")
```

---

## 7. Get Market by Slug

Look up a specific market using its URL slug.

### cURL

```bash
curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/by-slug/will-btc-hit-100k-by-march"
```

### JavaScript

```javascript
const slug = "will-btc-hit-100k-by-march";
const res = await fetch(
  `https://api.resolvedmarkets.com/v1/markets/by-slug/${slug}`,
  { headers: { "X-API-Key": "rm_your_key" } }
);
const market = await res.json();
console.log(`${market.question} (ID: ${market.conditionId})`);
```

### Python

```python
import requests

slug = "will-btc-hit-100k-by-march"
res = requests.get(
    f"https://api.resolvedmarkets.com/v1/markets/by-slug/{slug}",
    headers={"X-API-Key": "rm_your_key"},
)
market = res.json()
print(f"{market['question']} (ID: {market['conditionId']})")
```

---

## 8. Paginate Through Historical Markets

Loop through historical markets using limit and offset.

### cURL

```bash
OFFSET=0
LIMIT=50
while true; do
  RESULT=$(curl -s -H "X-API-Key: rm_your_key" \
    "https://api.resolvedmarkets.com/v1/markets/history/recent?limit=$LIMIT&offset=$OFFSET")
  COUNT=$(echo "$RESULT" | jq 'length')
  echo "Offset $OFFSET: got $COUNT markets"
  [ "$COUNT" -lt "$LIMIT" ] && break
  OFFSET=$((OFFSET + LIMIT))
done
```

### JavaScript

```javascript
const API_KEY = "rm_your_key";
const LIMIT = 50;
let offset = 0;
let allMarkets = [];

while (true) {
  const res = await fetch(
    `https://api.resolvedmarkets.com/v1/markets/history/recent?limit=${LIMIT}&offset=${offset}`,
    { headers: { "X-API-Key": API_KEY } }
  );
  const batch = await res.json();
  allMarkets.push(...batch);
  console.log(`Fetched ${batch.length} markets at offset ${offset}`);
  if (batch.length < LIMIT) break;
  offset += LIMIT;
}

console.log(`Total: ${allMarkets.length} historical markets`);
```

### Python

```python
import requests

API_KEY = "rm_your_key"
LIMIT = 50
offset = 0
all_markets = []

while True:
    res = requests.get(
        "https://api.resolvedmarkets.com/v1/markets/history/recent",
        headers={"X-API-Key": API_KEY},
        params={"limit": LIMIT, "offset": offset},
    )
    batch = res.json()
    all_markets.extend(batch)
    print(f"Fetched {len(batch)} markets at offset {offset}")
    if len(batch) < LIMIT:
        break
    offset += LIMIT

print(f"Total: {len(all_markets)} historical markets")
```

---

## 9. Find the Tightest Spread Market

List all live markets, fetch each orderbook, and rank by smallest spread.

### JavaScript

```javascript
const API_KEY = "rm_your_key";

const marketsRes = await fetch(
  "https://api.resolvedmarkets.com/v1/markets/live?category=crypto",
  { headers: { "X-API-Key": API_KEY } }
);
const markets = await marketsRes.json();

const results = [];
for (const market of markets) {
  const obRes = await fetch(
    `https://api.resolvedmarkets.com/v1/markets/${market.conditionId}/orderbook`,
    { headers: { "X-API-Key": API_KEY } }
  );
  const ob = await obRes.json();
  for (const token of ob.tokens) {
    const spread = token.bestAsk - token.bestBid;
    results.push({ slug: market.slug, side: token.tokenSide, spread });
  }
}

results.sort((a, b) => a.spread - b.spread);
console.log("Top 5 tightest spreads:");
results.slice(0, 5).forEach((r) =>
  console.log(`  ${r.spread.toFixed(4)} — ${r.slug} (${r.side})`)
);
```

### Python

```python
import requests

API_KEY = "rm_your_key"

markets = requests.get(
    "https://api.resolvedmarkets.com/v1/markets/live?category=crypto",
    headers={"X-API-Key": API_KEY},
).json()

results = []
for market in markets:
    ob = requests.get(
        f"https://api.resolvedmarkets.com/v1/markets/{market['conditionId']}/orderbook",
        headers={"X-API-Key": API_KEY},
    ).json()
    for token in ob["tokens"]:
        spread = token["bestAsk"] - token["bestBid"]
        results.append({"slug": market["slug"], "side": token["tokenSide"], "spread": spread})

results.sort(key=lambda r: r["spread"])
print("Top 5 tightest spreads:")
for r in results[:5]:
    print(f"  {r['spread']:.4f} — {r['slug']} ({r['side']})")
```

### cURL

```bash
# Fetch all markets, then query each orderbook and sort by spread
MARKETS=$(curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/live?category=crypto")

echo "$MARKETS" | jq -r '.[].conditionId' | while read -r ID; do
  curl -s -H "X-API-Key: rm_your_key" \
    "https://api.resolvedmarkets.com/v1/markets/$ID/orderbook" | \
    jq -r --arg id "$ID" '.tokens[] | "\(.bestAsk - .bestBid) \($id) \(.tokenSide)"'
done | sort -n | head -5
```

---

## 10. Export Snapshots for Backtesting

Query snapshots for a specific token side within a time range, suitable for backtesting strategies.

### JavaScript

```javascript
const fs = require("fs");

const API_KEY = "rm_your_key";
const MARKET_ID = "YOUR_MARKET_ID";
const TOKEN_SIDE = "UP";
const FROM = "2026-03-25T00:00:00Z";
const TO = "2026-03-26T00:00:00Z";
const LIMIT = 10000;

let offset = 0;
let allSnapshots = [];

while (true) {
  const url = new URL(`https://api.resolvedmarkets.com/v1/markets/${MARKET_ID}/snapshots`);
  url.searchParams.set("from", FROM);
  url.searchParams.set("to", TO);
  url.searchParams.set("tokenSide", TOKEN_SIDE);
  url.searchParams.set("limit", LIMIT);
  url.searchParams.set("offset", offset);

  const res = await fetch(url, { headers: { "X-API-Key": API_KEY } });
  const batch = await res.json();
  allSnapshots.push(...batch);
  console.log(`Fetched ${batch.length} snapshots at offset ${offset}`);
  if (batch.length < LIMIT) break;
  offset += LIMIT;
}

const header = "captureTimestamp,bestBid,bestAsk,midPrice,spread,totalBidDepth,totalAskDepth\n";
const rows = allSnapshots
  .map((s) =>
    [s.captureTimestamp, s.bestBid, s.bestAsk, s.midPrice, s.spread, s.totalBidDepth, s.totalAskDepth].join(",")
  )
  .join("\n");

fs.writeFileSync("backtest_data.csv", header + rows);
console.log(`Exported ${allSnapshots.length} snapshots to backtest_data.csv`);
```

### Python

```python
import csv
import requests

API_KEY = "rm_your_key"
MARKET_ID = "YOUR_MARKET_ID"
TOKEN_SIDE = "UP"
FROM = "2026-03-25T00:00:00Z"
TO = "2026-03-26T00:00:00Z"
LIMIT = 10000

all_snapshots = []
offset = 0

while True:
    res = requests.get(
        f"https://api.resolvedmarkets.com/v1/markets/{MARKET_ID}/snapshots",
        headers={"X-API-Key": API_KEY},
        params={
            "from": FROM,
            "to": TO,
            "tokenSide": TOKEN_SIDE,
            "limit": LIMIT,
            "offset": offset,
        },
    )
    batch = res.json()
    all_snapshots.extend(batch)
    print(f"Fetched {len(batch)} snapshots at offset {offset}")
    if len(batch) < LIMIT:
        break
    offset += LIMIT

fields = ["captureTimestamp", "bestBid", "bestAsk", "midPrice", "spread", "totalBidDepth", "totalAskDepth"]
with open("backtest_data.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(all_snapshots)

print(f"Exported {len(all_snapshots)} snapshots to backtest_data.csv")
```

### cURL

```bash
FROM="2026-03-25T00:00:00Z"
TO="2026-03-26T00:00:00Z"

curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/snapshots?from=$FROM&to=$TO&tokenSide=UP&limit=10000" | \
  jq -r '["captureTimestamp","bestBid","bestAsk","midPrice","spread","totalBidDepth","totalAskDepth"], (.[] | [.captureTimestamp,.bestBid,.bestAsk,.midPrice,.spread,.totalBidDepth,.totalAskDepth]) | @csv' \
  > backtest_data.csv
```
