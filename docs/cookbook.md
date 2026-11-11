# Cookbook

Copy-paste recipes for the Resolved Markets API. Every example is complete and runnable.

**Base URL:** `https://api.resolvedmarkets.com`
**Auth:** `X-API-Key: rm_your_key` header on all requests.

Replace `rm_your_key` with your actual API key and `YOUR_MARKET_ID` with the `conditionId` of a market from the `/v1/markets/live` endpoint. The JavaScript recipes need Node.js 18 or later; save a recipe that uses `import` or a top-level `await` as a `.mjs` file.

---

## 1. Get the Current BTC Spread

Fetch the live orderbook for a BTC market and read the bid-ask spread of its UP book. `up` is `null` when the server has no book for that side yet.

### cURL

```bash
curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook" | \
  jq '.up | {bestBid, bestAsk, spread}'
```

### JavaScript

```javascript
const res = await fetch(
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook",
  { headers: { "X-API-Key": "rm_your_key" } }
);
if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
const { up } = await res.json();
if (up) {
  console.log(`Best Bid: ${up.bestBid}, Best Ask: ${up.bestAsk}, Spread: ${up.spread.toFixed(4)}`);
}
```

### Python

```python
import requests

res = requests.get(
    "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook",
    headers={"X-API-Key": "rm_your_key"},
)
res.raise_for_status()
up = res.json()["up"]
if up:
    print(f"Best Bid: {up['bestBid']}, Best Ask: {up['bestAsk']}, Spread: {up['spread']:.4f}")
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
if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
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
res.raise_for_status()
for m in res.json():
    print(f"{m['slug']} — {m['question']}")
```

---

## 3. Stream Orderbooks Every 2 Seconds

Connect via WebSocket, authenticate, subscribe to BTC, and log each `orderbook` message. The server sends one every 2 seconds, with the books of every tracked BTC market. One connection follows one coin: open one connection for each coin.

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
  } else if (msg.type === "orderbook") {
    for (const m of msg.markets) {
      if (!m.up) continue;
      console.log(
        `[${new Date().toISOString()}] ${m.timeframe} UP ` +
        `bid=${m.up.bestBid} ask=${m.up.bestAsk} spread=${(m.up.bestAsk - m.up.bestBid).toFixed(4)}`
      );
    }
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
    elif msg.get("type") == "orderbook":
        for m in msg["markets"]:
            up = m["up"]
            if up:
                spread = up["bestAsk"] - up["bestBid"]
                print(f"{m['timeframe']} UP bid={up['bestBid']} ask={up['bestAsk']} spread={spread:.4f}")

ws = websocket.WebSocketApp(
    "wss://api.resolvedmarkets.com/ws/orderbook",
    on_open=on_open,
    on_message=on_message,
)
ws.run_forever()
```

### websocat

cURL has no WebSocket support, so this recipe uses [websocat](https://github.com/vi/websocat). The command sends the auth message, waits 2 seconds for the auth reply, and then subscribes to one coin on the same connection. `-n` keeps the connection open after the two messages. `-B` raises the message size limit of websocat (64 KiB by default): the first `markets` message is about 95 KB on Pro and about 4.6 MB on Scale and Enterprise. `jq` prints one short line for each message. The stream runs until you press Ctrl+C.

```bash
(echo '{"type":"auth","apiKey":"rm_your_key"}'; sleep 2; echo '{"type":"subscribe","crypto":"BTC"}') | \
  websocat -n -B 16777216 --text "wss://api.resolvedmarkets.com/ws/orderbook" | \
  jq -c 'if .type == "markets" then {type, count: (.data | length)} elif .type == "orderbook" then {type, count: (.markets | length), up_mid: [.markets[] | .up.midPrice?]} else . end'
```

You see `{"type":"auth","status":"ok"}`, then one `markets` line, then one `orderbook` line every 2 seconds.

---

## 4. Download 24h of Historical Snapshots

Fetch the snapshots of the last 24 hours for a market and write them to a CSV file. One page holds up to 5,000 rows, newest first; recipe 10 pages through more rows.

### cURL

```bash
FROM=$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)
TO=$(date -u +%Y-%m-%dT%H:%M:%SZ)

curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/snapshots?from=$FROM&to=$TO&limit=5000" | \
  jq -r '["timestamp","token_side","best_bid","best_ask","mid_price","spread"], (.data[] | [.timestamp,.token_side,.best_bid,.best_ask,.mid_price,.spread]) | @csv' \
  > snapshots_24h.csv
```

### JavaScript

```javascript
import fs from "node:fs";

const from = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
const to = new Date().toISOString();

const res = await fetch(
  `https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/snapshots?from=${from}&to=${to}&limit=5000`,
  { headers: { "X-API-Key": "rm_your_key" } }
);
if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
const { data } = await res.json();

const header = "timestamp,token_side,best_bid,best_ask,mid_price,spread\n";
const rows = data
  .map((s) => `${s.timestamp},${s.token_side},${s.best_bid},${s.best_ask},${s.mid_price},${s.spread}`)
  .join("\n");

fs.writeFileSync("snapshots_24h.csv", header + rows);
console.log(`Wrote ${data.length} rows to snapshots_24h.csv`);
```

### Python

```python
import csv
import requests
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
from_ts = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
to_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")

res = requests.get(
    "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/snapshots",
    headers={"X-API-Key": "rm_your_key"},
    params={"from": from_ts, "to": to_ts, "limit": 5000},
)
res.raise_for_status()
rows = res.json()["data"]

with open("snapshots_24h.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "token_side", "best_bid", "best_ask", "mid_price", "spread"])
    for s in rows:
        writer.writerow([s["timestamp"], s["token_side"], s["best_bid"], s["best_ask"], s["mid_price"], s["spread"]])

print(f"Wrote {len(rows)} rows to snapshots_24h.csv")
```

Send `from` and `to` as `YYYY-MM-DDTHH:MM:SSZ`, as above. A time with an offset such as `+00:00` (the output of Python's `isoformat()`) gets an error.

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
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  const data = await res.json();
  for (const [side, book] of [["UP", data.up], ["DOWN", data.down]]) {
    if (!book) continue;
    if (book.spread > THRESHOLD) {
      console.log(`ALERT [${side}] Spread ${book.spread.toFixed(4)} > ${THRESHOLD}`);
    } else {
      console.log(`OK    [${side}] Spread ${book.spread.toFixed(4)}`);
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
    res.raise_for_status()
    data = res.json()
    for side in ("up", "down"):
        book = data[side]
        if not book:
            continue
        tag = "ALERT" if book["spread"] > THRESHOLD else "OK   "
        print(f"{tag} [{side.upper()}] Spread {book['spread']:.4f}")
    time.sleep(10)
```

### cURL

```bash
THRESHOLD=0.05
while true; do
  curl -s -H "X-API-Key: rm_your_key" \
    "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook" | \
    jq -r --argjson t "$THRESHOLD" '{UP: .up, DOWN: .down} | to_entries[] | select(.value != null) | {side: .key, spread: .value.spread} | if .spread > $t then "ALERT \(.side) spread=\(.spread)" else "OK    \(.side) spread=\(.spread)" end'
  sleep 10
done
```

---

## 6. Compare UP vs DOWN Liquidity

Fetch the orderbook and compare the depth of the UP and DOWN books. `bidDepth` and `askDepth` are the sum of price × size of each side.

### cURL

```bash
curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook" | \
  jq '{UP: .up, DOWN: .down} | to_entries[] | select(.value != null) | {side: .key, bidDepth: .value.bidDepth, askDepth: .value.askDepth, totalLiquidity: (.value.bidDepth + .value.askDepth)}'
```

### JavaScript

```javascript
const res = await fetch(
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook",
  { headers: { "X-API-Key": "rm_your_key" } }
);
if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
const data = await res.json();

const totals = {};
for (const [side, book] of [["UP", data.up], ["DOWN", data.down]]) {
  if (!book) continue;
  totals[side] = book.bidDepth + book.askDepth;
  console.log(
    `${side}: Bid Depth = ${book.bidDepth}, Ask Depth = ${book.askDepth}, Total = ${totals[side]}`
  );
}

if (totals.UP && totals.DOWN) {
  console.log(`\nUP/DOWN liquidity ratio: ${(totals.UP / totals.DOWN).toFixed(2)}`);
}
```

### Python

```python
import requests

res = requests.get(
    "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/orderbook",
    headers={"X-API-Key": "rm_your_key"},
)
res.raise_for_status()
data = res.json()

totals = {}
for side in ("up", "down"):
    book = data[side]
    if not book:
        continue
    total = book["bidDepth"] + book["askDepth"]
    totals[side.upper()] = total
    print(f"{side.upper()}: Bid={book['bidDepth']}, Ask={book['askDepth']}, Total={total}")

if totals.get("UP") and totals.get("DOWN"):
    print(f"\nUP/DOWN liquidity ratio: {totals['UP'] / totals['DOWN']:.2f}")
```

---

## 7. Get Market by Slug

Look up a specific market using its URL slug. The response keys are snake_case: the market id is `market_id`.

### cURL

```bash
curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/by-slug/btc-updown-5m-1794423000"
```

### JavaScript

```javascript
const slug = "btc-updown-5m-1794423000";
const res = await fetch(
  `https://api.resolvedmarkets.com/v1/markets/by-slug/${slug}`,
  { headers: { "X-API-Key": "rm_your_key" } }
);
if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
const market = await res.json();
console.log(`${market.question} (ID: ${market.market_id})`);
```

### Python

```python
import requests

slug = "btc-updown-5m-1794423000"
res = requests.get(
    f"https://api.resolvedmarkets.com/v1/markets/by-slug/{slug}",
    headers={"X-API-Key": "rm_your_key"},
)
res.raise_for_status()
market = res.json()
print(f"{market['question']} (ID: {market['market_id']})")
```

---

## 8. Walk Through Historical Markets by Date

The market history routes have no `offset`. Request one day at a time with `since` and `before`: a day returns the markets that were captured on that day. A market that spans midnight is in two days, so keep each `market_id` once. One request returns at most 5,000 markets; narrow the filters if a day reaches that limit.

### cURL

```bash
for DAY in 2026-11-08 2026-11-09 2026-11-10; do
  curl -s -H "X-API-Key: rm_your_key" \
    "https://api.resolvedmarkets.com/v1/markets/history?crypto=BTC&since=$DAY&before=${DAY}T23:59:59Z&limit=5000" | \
    jq -r --arg day "$DAY" '"\($day): \(.markets | length) markets"'
done
```

### JavaScript

```javascript
const API_KEY = "rm_your_key";
const days = ["2026-11-08", "2026-11-09", "2026-11-10"];
const allMarkets = new Map();

for (const day of days) {
  const res = await fetch(
    `https://api.resolvedmarkets.com/v1/markets/history?crypto=BTC&since=${day}&before=${day}T23:59:59Z&limit=5000`,
    { headers: { "X-API-Key": API_KEY } }
  );
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  const { markets } = await res.json();
  for (const m of markets) allMarkets.set(m.market_id, m);
  console.log(`${day}: ${markets.length} markets`);
}

console.log(`Total: ${allMarkets.size} historical markets`);
```

### Python

```python
import requests

API_KEY = "rm_your_key"
days = ["2026-11-08", "2026-11-09", "2026-11-10"]
all_markets = {}

for day in days:
    res = requests.get(
        "https://api.resolvedmarkets.com/v1/markets/history",
        headers={"X-API-Key": API_KEY},
        params={"crypto": "BTC", "since": day, "before": f"{day}T23:59:59Z", "limit": 5000},
    )
    res.raise_for_status()
    markets = res.json()["markets"]
    for m in markets:
        all_markets[m["market_id"]] = m
    print(f"{day}: {len(markets)} markets")

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
if (!marketsRes.ok) throw new Error(`API ${marketsRes.status}: ${await marketsRes.text()}`);
const markets = await marketsRes.json();

const results = [];
for (const market of markets) {
  const obRes = await fetch(
    `https://api.resolvedmarkets.com/v1/markets/${market.conditionId}/orderbook`,
    { headers: { "X-API-Key": API_KEY } }
  );
  if (!obRes.ok) continue;
  const ob = await obRes.json();
  for (const [side, book] of [["UP", ob.up], ["DOWN", ob.down]]) {
    if (book) results.push({ question: market.question, side, spread: book.spread });
  }
}

results.sort((a, b) => a.spread - b.spread);
console.log("Top 5 tightest spreads:");
results.slice(0, 5).forEach((r) =>
  console.log(`  ${r.spread.toFixed(4)} — ${r.question} (${r.side})`)
);
```

### Python

```python
import requests

API_KEY = "rm_your_key"

res = requests.get(
    "https://api.resolvedmarkets.com/v1/markets/live?category=crypto",
    headers={"X-API-Key": API_KEY},
)
res.raise_for_status()
markets = res.json()

results = []
for market in markets:
    res = requests.get(
        f"https://api.resolvedmarkets.com/v1/markets/{market['conditionId']}/orderbook",
        headers={"X-API-Key": API_KEY},
    )
    if not res.ok:
        continue
    ob = res.json()
    for side in ("up", "down"):
        if ob[side]:
            results.append({"question": market["question"], "side": side.upper(), "spread": ob[side]["spread"]})

results.sort(key=lambda r: r["spread"])
print("Top 5 tightest spreads:")
for r in results[:5]:
    print(f"  {r['spread']:.4f} — {r['question']} ({r['side']})")
```

### cURL

```bash
MARKETS=$(curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/live?category=crypto")

echo "$MARKETS" | jq -r '.[].conditionId' | while read -r ID; do
  curl -s -H "X-API-Key: rm_your_key" \
    "https://api.resolvedmarkets.com/v1/markets/$ID/orderbook" | \
    jq -r --arg id "$ID" '{UP: .up, DOWN: .down} | to_entries[] | select(.value != null) | "\(.value.spread) \($id) \(.key)"'
done | sort -n | head -5
```

---

## 10. Export Snapshots for Backtesting

Query the snapshots of one side of a market for the last 24 hours, oldest first, and page through all of them. For another range, set `FROM` and `TO` to times in the life of the market.

### JavaScript

```javascript
import fs from "node:fs";

const API_KEY = "rm_your_key";
const MARKET_ID = "YOUR_MARKET_ID";
const SIDE = "UP";
const FROM = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
const TO = new Date().toISOString();
const LIMIT = 5000;

let offset = 0;
const allSnapshots = [];

while (true) {
  const url = new URL(`https://api.resolvedmarkets.com/v1/markets/${MARKET_ID}/snapshots`);
  url.searchParams.set("from", FROM);
  url.searchParams.set("to", TO);
  url.searchParams.set("side", SIDE);
  url.searchParams.set("order", "asc");
  url.searchParams.set("limit", String(LIMIT));
  url.searchParams.set("offset", String(offset));

  const res = await fetch(url, { headers: { "X-API-Key": API_KEY } });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  const { data } = await res.json();
  allSnapshots.push(...data);
  console.log(`Fetched ${data.length} snapshots at offset ${offset}`);
  if (data.length < LIMIT) break;
  offset += LIMIT;
}

const fields = ["timestamp", "best_bid", "best_ask", "mid_price", "spread", "bid_depth_total", "ask_depth_total"];
const rows = allSnapshots.map((s) => fields.map((k) => s[k]).join(","));

fs.writeFileSync("backtest_data.csv", [fields.join(","), ...rows].join("\n"));
console.log(`Exported ${allSnapshots.length} snapshots to backtest_data.csv`);
```

### Python

```python
import csv
import requests
from datetime import datetime, timedelta, timezone

API_KEY = "rm_your_key"
MARKET_ID = "YOUR_MARKET_ID"
SIDE = "UP"
now = datetime.now(timezone.utc)
FROM = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
TO = now.strftime("%Y-%m-%dT%H:%M:%SZ")
LIMIT = 5000

all_snapshots = []
offset = 0

while True:
    res = requests.get(
        f"https://api.resolvedmarkets.com/v1/markets/{MARKET_ID}/snapshots",
        headers={"X-API-Key": API_KEY},
        params={
            "from": FROM,
            "to": TO,
            "side": SIDE,
            "order": "asc",
            "limit": LIMIT,
            "offset": offset,
        },
    )
    res.raise_for_status()
    batch = res.json()["data"]
    all_snapshots.extend(batch)
    print(f"Fetched {len(batch)} snapshots at offset {offset}")
    if len(batch) < LIMIT:
        break
    offset += LIMIT

fields = ["timestamp", "best_bid", "best_ask", "mid_price", "spread", "bid_depth_total", "ask_depth_total"]
with open("backtest_data.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(all_snapshots)

print(f"Exported {len(all_snapshots)} snapshots to backtest_data.csv")
```

### cURL

```bash
FROM=$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)
TO=$(date -u +%Y-%m-%dT%H:%M:%SZ)

curl -s -H "X-API-Key: rm_your_key" \
  "https://api.resolvedmarkets.com/v1/markets/YOUR_MARKET_ID/snapshots?from=$FROM&to=$TO&side=UP&order=asc&limit=5000" | \
  jq -r '["timestamp","best_bid","best_ask","mid_price","spread","bid_depth_total","ask_depth_total"], (.data[] | [.timestamp,.best_bid,.best_ask,.mid_price,.spread,.bid_depth_total,.ask_depth_total]) | @csv' \
  > backtest_data.csv
```
