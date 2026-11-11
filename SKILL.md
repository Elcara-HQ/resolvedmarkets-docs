# Resolved Markets API — Developer Skills

Practical, copy-paste code examples for the Resolved Markets prediction market orderbook API.

**Base URL:** `https://api.resolvedmarkets.com`
**Auth:** `X-API-Key: rm_your_key` header on all authenticated endpoints
**WebSocket:** `wss://api.resolvedmarkets.com/ws/orderbook` (message-based auth within 5s; one coin per connection; an `orderbook` message every 2 s)

---

## 1. Retrieve the Snapshot History of a Market

Fetch the historical orderbook snapshots of one market and one side (`UP` or `DOWN`) in a time range, oldest first, with automatic pagination. The rows are in `data` and use snake_case keys. `from` and `to` take the UTC `Z` form, such as `2026-11-11T18:00:00Z`.

### TypeScript

```typescript
interface SnapshotRow {
  timestamp: string;
  token_side: "UP" | "DOWN";
  best_bid: number;
  best_ask: number;
  mid_price: number;
  spread: number;
  bid_depth_total: number;
  ask_depth_total: number;
  crypto_price: number;
  event_timestamp: string;
  capture_timestamp: string;
  sequence_number: string;
}

interface SnapshotPage {
  market_id: string;
  total: number;
  limit: number;
  offset: number;
  data: SnapshotRow[];
}

interface FetchSnapshotsOptions {
  apiKey: string;
  marketId: string;
  side?: "UP" | "DOWN";
  from?: string;
  to?: string;
  limit?: number;
  maxPages?: number;
}

const BASE_URL = "https://api.resolvedmarkets.com";

async function fetchAllSnapshots(options: FetchSnapshotsOptions): Promise<SnapshotRow[]> {
  const {
    apiKey,
    marketId,
    side,
    from,
    to,
    limit = 1000,
    maxPages = 100,
  } = options;

  const allSnapshots: SnapshotRow[] = [];
  let offset = 0;
  let page = 0;

  while (page < maxPages) {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
      order: "asc",
    });
    if (side) params.set("side", side);
    if (from) params.set("from", from);
    if (to) params.set("to", to);

    const url = `${BASE_URL}/v1/markets/${marketId}/snapshots?${params}`;
    const res = await fetch(url, {
      headers: { "X-API-Key": apiKey },
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`API error ${res.status}: ${body}`);
    }

    const result = (await res.json()) as SnapshotPage;
    allSnapshots.push(...result.data);

    if (allSnapshots.length >= result.total || result.data.length < limit) {
      break;
    }

    offset += limit;
    page++;
  }

  return allSnapshots;
}

// Usage
async function main(): Promise<void> {
  const now = Date.now();
  const snapshots = await fetchAllSnapshots({
    apiKey: "rm_your_key",
    marketId: "0x1234abcd...",
    side: "UP",
    from: new Date(now - 3_600_000).toISOString(),
    to: new Date(now).toISOString(),
  });

  console.log(`Fetched ${snapshots.length} snapshots`);
  for (const s of snapshots) {
    console.log(
      `seq=${s.sequence_number} mid=${s.mid_price} spread=${s.spread} ` +
      `depth=${s.bid_depth_total + s.ask_depth_total} @ ${s.timestamp}`
    );
  }
}

main().catch(console.error);
```

### Python

```python
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx

BASE_URL = "https://api.resolvedmarkets.com"


def fetch_all_snapshots(
    api_key: str,
    market_id: str,
    side: Optional[str] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    limit: int = 1000,
    max_pages: int = 100,
) -> list[dict]:
    """Fetch all paginated snapshots for a market within a time range."""
    headers = {"X-API-Key": api_key}
    all_snapshots: list[dict] = []
    offset = 0

    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30) as client:
        for _ in range(max_pages):
            params: dict = {"limit": limit, "offset": offset, "order": "asc"}
            if side:
                params["side"] = side
            if from_ts:
                params["from"] = from_ts
            if to_ts:
                params["to"] = to_ts

            resp = client.get(f"/v1/markets/{market_id}/snapshots", params=params)
            resp.raise_for_status()
            data = resp.json()

            all_snapshots.extend(data["data"])
            if len(all_snapshots) >= data["total"] or len(data["data"]) < limit:
                break

            offset += limit

    return all_snapshots


# Usage
if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    snapshots = fetch_all_snapshots(
        api_key="rm_your_key",
        market_id="0x1234abcd...",
        side="UP",
        from_ts=(now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        to_ts=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    print(f"Fetched {len(snapshots)} snapshots")
    for s in snapshots:
        print(f"seq={s['sequence_number']} mid={s['mid_price']} spread={s['spread']}")
```

---

## 2. Resilient WebSocket Manager with Auto-Reconnect

Production-grade WebSocket manager that handles authentication, exponential backoff reconnection, heartbeat detection, and event-driven state changes. Each connection follows one coin (a new `subscribe` replaces the last one), so each manager holds one coin and the usage creates one manager for each coin. Each manager uses one connection of your plan's limit. The server sends an `orderbook` message with the books of every tracked market of the coin every 2 seconds.

The manager stops when the server closes the connection with code 4003 and the reason `Invalid API key` or `Tier restriction` (a plan without WebSocket access). On 4003 `Connection limit`, it connects again after 60 seconds, because the server can count a dropped connection for up to 60 seconds. After any other close, such as a network error or 4001 (auth timeout), it reconnects with backoff.

### TypeScript

```typescript
import WebSocket from "ws";
import { EventEmitter } from "events";

type ConnectionState = "disconnected" | "connecting" | "connected" | "authenticated";

interface BookSide {
  tokenId: string;
  bids: { price: number; size: number }[];
  asks: { price: number; size: number }[];
  bestBid: number;
  bestAsk: number;
  midPrice: number;
  spread: number;
  timestamp: number;
}

interface OrderbookMarket {
  marketId: string;
  crypto: string;
  timeframe: string;
  question: string;
  cryptoPrice: number;
  up: BookSide | null;
  down: BookSide | null;
}

interface OrderbookStreamEvents {
  orderbook: (market: OrderbookMarket) => void;
  stateChange: (state: ConnectionState, previous: ConnectionState) => void;
  error: (error: Error) => void;
}

class OrderbookStreamManager extends EventEmitter {
  private ws: WebSocket | null = null;
  private state: ConnectionState = "disconnected";
  private apiKey: string;
  private crypto: string;
  private url: string;
  private reconnectAttempt: number = 0;
  private maxReconnectDelay: number = 30_000;
  private baseReconnectDelay: number = 1_000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimeout: number = 45_000;
  private authTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose: boolean = false;

  constructor(apiKey: string, crypto: string, url: string = "wss://api.resolvedmarkets.com/ws/orderbook") {
    super();
    this.apiKey = apiKey;
    this.crypto = crypto.toUpperCase();
    this.url = url;
  }

  getState(): ConnectionState {
    return this.state;
  }

  getCrypto(): string {
    return this.crypto;
  }

  connect(): void {
    if (this.state !== "disconnected") return;
    this.intentionalClose = false;
    this.doConnect();
  }

  disconnect(): void {
    this.intentionalClose = true;
    this.cleanup();
    this.setState("disconnected");
  }

  private doConnect(): void {
    this.setState("connecting");
    try {
      this.ws = new WebSocket(this.url);
    } catch (err) {
      this.emit("error", err instanceof Error ? err : new Error(String(err)));
      this.scheduleReconnect();
      return;
    }

    this.ws.on("open", () => {
      this.setState("connected");
      this.reconnectAttempt = 0;

      // Send auth within 5s deadline
      this.ws!.send(JSON.stringify({ type: "auth", apiKey: this.apiKey }));

      // Set auth timeout — server closes at 5s, we detect at 6s
      this.authTimer = setTimeout(() => {
        if (this.state === "connected") {
          this.emit("error", new Error("Authentication timeout — no response within 6s"));
          this.handleDisconnect();
        }
      }, 6_000);
    });

    this.ws.on("message", (raw: WebSocket.Data) => {
      this.resetHeartbeat();

      let msg: Record<string, unknown>;
      try {
        msg = JSON.parse(raw.toString());
      } catch {
        return;
      }

      if (msg.type === "auth") {
        if (this.authTimer) {
          clearTimeout(this.authTimer);
          this.authTimer = null;
        }
        if (msg.status === "ok") {
          this.setState("authenticated");
          this.ws?.send(JSON.stringify({ type: "subscribe", crypto: this.crypto }));
        } else {
          this.emit("error", new Error(`Auth failed: ${JSON.stringify(msg)}`));
          this.intentionalClose = true;
          this.cleanup();
          this.setState("disconnected");
        }
        return;
      }

      if (msg.type === "error") {
        this.emit("error", new Error(`Server error ${msg.code}: ${msg.message}`));
        return;
      }

      if (msg.type === "orderbook") {
        for (const market of msg.markets as OrderbookMarket[]) {
          this.emit("orderbook", market);
        }
      }
    });

    this.ws.on("error", (err: Error) => {
      this.emit("error", err);
    });

    this.ws.on("close", (code: number, reason: Buffer) => {
      if (this.authTimer) {
        clearTimeout(this.authTimer);
        this.authTimer = null;
      }
      const text = reason.toString();
      if (code === 4001) {
        this.emit("error", new Error("Server closed: auth timeout (4001)"));
      }
      if (code === 4003 && text !== "Connection limit") {
        this.emit("error", new Error(`Server refused the connection (4003, ${text}): not reconnecting`));
        this.intentionalClose = true;
      }
      this.handleDisconnect(code === 4003 ? 60_000 : 0);
    });
  }

  private resetHeartbeat(): void {
    if (this.heartbeatTimer) clearTimeout(this.heartbeatTimer);
    this.heartbeatTimer = setTimeout(() => {
      this.emit("error", new Error(`No data received for ${this.heartbeatTimeout}ms`));
      this.handleDisconnect();
    }, this.heartbeatTimeout);
  }

  private handleDisconnect(minDelay: number = 0): void {
    this.cleanup();
    this.setState("disconnected");
    if (!this.intentionalClose) {
      this.scheduleReconnect(minDelay);
    }
  }

  private scheduleReconnect(minDelay: number = 0): void {
    const delay = Math.max(
      minDelay,
      Math.min(this.baseReconnectDelay * Math.pow(2, this.reconnectAttempt), this.maxReconnectDelay),
    );
    this.reconnectAttempt++;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.doConnect();
    }, delay);
  }

  private cleanup(): void {
    if (this.heartbeatTimer) {
      clearTimeout(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    if (this.authTimer) {
      clearTimeout(this.authTimer);
      this.authTimer = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.removeAllListeners();
      if (
        this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING
      ) {
        this.ws.close();
      }
      this.ws = null;
    }
  }

  private setState(newState: ConnectionState): void {
    const prev = this.state;
    if (prev === newState) return;
    this.state = newState;
    this.emit("stateChange", newState, prev);
  }
}

// Usage
const managers = ["BTC", "ETH"].map((crypto) => {
  const manager = new OrderbookStreamManager("rm_your_key", crypto);

  manager.on("stateChange", (state, prev) => {
    console.log(`${crypto} connection: ${prev} -> ${state}`);
  });

  manager.on("orderbook", (market: OrderbookMarket) => {
    if (!market.up) return;
    console.log(
      `${market.crypto} ${market.timeframe} UP: mid=${market.up.midPrice} spread=${market.up.spread}`
    );
  });

  manager.on("error", (err) => {
    console.error(`${crypto} stream error:`, err.message);
  });

  manager.connect();
  return manager;
});

// Graceful shutdown
process.on("SIGINT", () => {
  managers.forEach((manager) => manager.disconnect());
  process.exit(0);
});
```

### Python (asyncio)

```python
import asyncio
import json
import logging
from enum import Enum
from typing import Callable, Optional

import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"


class OrderbookStreamManager:
    """Production WebSocket manager with auto-reconnect and exponential backoff."""

    def __init__(
        self,
        api_key: str,
        crypto: str,
        url: str = "wss://api.resolvedmarkets.com/ws/orderbook",
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        heartbeat_timeout: float = 45.0,
    ):
        self.api_key = api_key
        self.crypto = crypto.upper()
        self.url = url
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.heartbeat_timeout = heartbeat_timeout

        self._state = ConnectionState.DISCONNECTED
        self._reconnect_attempt = 0
        self._intentional_close = False
        self._ws: Optional[WebSocketClientProtocol] = None
        self._tasks: list[asyncio.Task] = []

        # Callbacks
        self.on_orderbook: Optional[Callable[[dict], None]] = None
        self.on_state_change: Optional[Callable[[ConnectionState, ConnectionState], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    async def connect(self) -> None:
        self._intentional_close = False
        await self._connect_loop()

    async def disconnect(self) -> None:
        self._intentional_close = True
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._set_state(ConnectionState.DISCONNECTED)

    async def _connect_loop(self) -> None:
        while not self._intentional_close:
            min_delay = 0.0
            try:
                await self._do_connect()
            except websockets.ConnectionClosed as e:
                self._set_state(ConnectionState.DISCONNECTED)
                code = e.rcvd.code if e.rcvd else None
                reason = e.rcvd.reason if e.rcvd else ""
                if code == 4003 and reason != "Connection limit":
                    self._emit_error(Exception(f"Server refused the connection (4003, {reason}): not reconnecting"))
                    self._intentional_close = True
                    break
                self._emit_error(e)
                if code == 4003:
                    min_delay = 60.0
            except Exception as e:
                self._emit_error(e)
                self._set_state(ConnectionState.DISCONNECTED)

            if self._intentional_close:
                break

            delay = max(
                min_delay,
                min(self.base_delay * (2 ** self._reconnect_attempt), self.max_delay),
            )
            self._reconnect_attempt += 1
            logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempt})")
            await asyncio.sleep(delay)

    async def _do_connect(self) -> None:
        self._set_state(ConnectionState.CONNECTING)

        async with websockets.connect(self.url, max_size=None) as ws:
            self._ws = ws
            self._set_state(ConnectionState.CONNECTED)
            self._reconnect_attempt = 0

            # Authenticate
            await ws.send(json.dumps({"type": "auth", "apiKey": self.api_key}))

            try:
                auth_raw = await asyncio.wait_for(ws.recv(), timeout=6.0)
            except asyncio.TimeoutError:
                self._emit_error(Exception("Auth timeout"))
                return

            auth_msg = json.loads(auth_raw)
            if auth_msg.get("status") != "ok":
                self._emit_error(Exception(f"Auth failed: {auth_msg.get('message')}"))
                await asyncio.wait_for(ws.recv(), timeout=6.0)
                return

            self._set_state(ConnectionState.AUTHENTICATED)

            await ws.send(json.dumps({"type": "subscribe", "crypto": self.crypto}))

            # Read messages with heartbeat timeout
            while not self._intentional_close:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=self.heartbeat_timeout)
                except asyncio.TimeoutError:
                    self._emit_error(Exception(f"No data for {self.heartbeat_timeout}s"))
                    return

                msg = json.loads(raw)
                if msg.get("type") == "orderbook" and self.on_orderbook:
                    for market in msg["markets"]:
                        self.on_orderbook(market)

    def _set_state(self, new_state: ConnectionState) -> None:
        prev = self._state
        if prev == new_state:
            return
        self._state = new_state
        if self.on_state_change:
            self.on_state_change(new_state, prev)

    def _emit_error(self, err: Exception) -> None:
        logger.error(f"Stream error: {err}")
        if self.on_error:
            self.on_error(err)


# Usage
async def main():
    def handle_market(market: dict):
        up = market["up"]
        if up:
            print(f"{market['crypto']} {market['timeframe']} UP: mid={up['midPrice']} spread={up['spread']}")

    def handle_state(new: ConnectionState, prev: ConnectionState):
        print(f"Connection: {prev.value} -> {new.value}")

    managers = []
    for crypto in ["BTC", "ETH"]:
        manager = OrderbookStreamManager(api_key="rm_your_key", crypto=crypto)
        manager.on_orderbook = handle_market
        manager.on_state_change = handle_state
        manager.on_error = lambda e: print(f"Error: {e}")
        managers.append(manager)

    try:
        await asyncio.gather(*(manager.connect() for manager in managers))
    except KeyboardInterrupt:
        await asyncio.gather(*(manager.disconnect() for manager in managers))


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 3. Fetch Live Orderbook and Calculate Metrics

Fetch the live orderbook for a market and compute advanced metrics: weighted mid price, order imbalance ratio, depth at N levels, and volume-weighted average price (VWAP).

### TypeScript

```typescript
interface Level {
  price: number;
  size: number;
}

interface OrderbookSide {
  tokenId: string;
  bids: Level[];
  asks: Level[];
  bestBid: number;
  bestAsk: number;
  midPrice: number;
  spread: number;
  bidDepth: number;
  askDepth: number;
}

interface OrderbookResponse {
  market_id: string;
  question: string;
  up: OrderbookSide | null;
  down: OrderbookSide | null;
}

interface OrderbookMetrics {
  weightedMidPrice: number;
  orderImbalance: number;
  bidDepthAtLevels: number[];
  askDepthAtLevels: number[];
  bidVwap: number;
  askVwap: number;
  spreadBps: number;
}

const BASE_URL = "https://api.resolvedmarkets.com";

function calculateWeightedMidPrice(bestBid: number, bestAsk: number, bidSize: number, askSize: number): number {
  const totalSize = bidSize + askSize;
  if (totalSize === 0) return (bestBid + bestAsk) / 2;
  return (bestBid * askSize + bestAsk * bidSize) / totalSize;
}

function calculateOrderImbalance(bidDepth: number, askDepth: number): number {
  const total = bidDepth + askDepth;
  if (total === 0) return 0;
  return (bidDepth - askDepth) / total;
}

function calculateDepthAtLevels(levels: Level[], n: number): number[] {
  const depths: number[] = [];
  let cumulative = 0;
  for (let i = 0; i < Math.min(n, levels.length); i++) {
    cumulative += levels[i].size;
    depths.push(cumulative);
  }
  return depths;
}

function calculateVwap(levels: Level[], maxLevels: number = 10): number {
  let totalVolume = 0;
  let totalValue = 0;
  for (let i = 0; i < Math.min(maxLevels, levels.length); i++) {
    totalVolume += levels[i].size;
    totalValue += levels[i].price * levels[i].size;
  }
  return totalVolume === 0 ? 0 : totalValue / totalVolume;
}

async function fetchOrderbookWithMetrics(
  apiKey: string,
  marketId: string,
  side: "UP" | "DOWN" = "UP",
  depthLevels: number = 5,
): Promise<{ orderbook: OrderbookSide; metrics: OrderbookMetrics }> {
  const res = await fetch(`${BASE_URL}/v1/markets/${marketId}/orderbook`, {
    headers: { "X-API-Key": apiKey },
  });

  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }

  const data = (await res.json()) as OrderbookResponse;
  const orderbook = side === "UP" ? data.up : data.down;
  if (!orderbook) {
    throw new Error(`Market ${marketId} has no ${side} book`);
  }

  const topBidSize = orderbook.bids.length > 0 ? orderbook.bids[0].size : 0;
  const topAskSize = orderbook.asks.length > 0 ? orderbook.asks[0].size : 0;

  const metrics: OrderbookMetrics = {
    weightedMidPrice: calculateWeightedMidPrice(
      orderbook.bestBid, orderbook.bestAsk, topBidSize, topAskSize,
    ),
    orderImbalance: calculateOrderImbalance(orderbook.bidDepth, orderbook.askDepth),
    bidDepthAtLevels: calculateDepthAtLevels(orderbook.bids, depthLevels),
    askDepthAtLevels: calculateDepthAtLevels(orderbook.asks, depthLevels),
    bidVwap: calculateVwap(orderbook.bids),
    askVwap: calculateVwap(orderbook.asks),
    spreadBps: orderbook.bestAsk > 0
      ? ((orderbook.spread / orderbook.midPrice) * 10_000)
      : 0,
  };

  return { orderbook, metrics };
}

// Usage
async function main(): Promise<void> {
  const { orderbook, metrics } = await fetchOrderbookWithMetrics(
    "rm_your_key",
    "0x1234abcd...",
    "UP",
  );

  console.log(`Mid Price:          ${orderbook.midPrice}`);
  console.log(`Weighted Mid Price: ${metrics.weightedMidPrice.toFixed(6)}`);
  console.log(`Spread (bps):       ${metrics.spreadBps.toFixed(1)}`);
  console.log(`Order Imbalance:    ${metrics.orderImbalance.toFixed(4)} (>0 = bid heavy)`);
  console.log(`Bid VWAP:           ${metrics.bidVwap.toFixed(6)}`);
  console.log(`Ask VWAP:           ${metrics.askVwap.toFixed(6)}`);
  console.log(`Cumulative bid depth (top 5):`, metrics.bidDepthAtLevels);
  console.log(`Cumulative ask depth (top 5):`, metrics.askDepthAtLevels);
}

main().catch(console.error);
```

### Python

```python
import httpx

BASE_URL = "https://api.resolvedmarkets.com"


def weighted_mid_price(best_bid: float, best_ask: float, bid_size: float, ask_size: float) -> float:
    total = bid_size + ask_size
    if total == 0:
        return (best_bid + best_ask) / 2
    return (best_bid * ask_size + best_ask * bid_size) / total


def order_imbalance(total_bid_depth: float, total_ask_depth: float) -> float:
    total = total_bid_depth + total_ask_depth
    return (total_bid_depth - total_ask_depth) / total if total > 0 else 0.0


def cumulative_depth(levels: list[dict], n: int) -> list[float]:
    depths = []
    cumulative = 0.0
    for level in levels[:n]:
        cumulative += level["size"]
        depths.append(cumulative)
    return depths


def vwap(levels: list[dict], max_levels: int = 10) -> float:
    total_vol = sum(l["size"] for l in levels[:max_levels])
    if total_vol == 0:
        return 0.0
    return sum(l["price"] * l["size"] for l in levels[:max_levels]) / total_vol


def fetch_orderbook_with_metrics(
    api_key: str,
    market_id: str,
    side: str = "UP",
    depth_levels: int = 5,
) -> dict:
    with httpx.Client(base_url=BASE_URL, headers={"X-API-Key": api_key}, timeout=15) as client:
        resp = client.get(f"/v1/markets/{market_id}/orderbook")
        resp.raise_for_status()
        data = resp.json()

    book = data[side.lower()]
    if book is None:
        raise ValueError(f"Market {market_id} has no {side} book")
    top_bid_size = book["bids"][0]["size"] if book["bids"] else 0
    top_ask_size = book["asks"][0]["size"] if book["asks"] else 0

    return {
        "orderbook": book,
        "metrics": {
            "weighted_mid_price": weighted_mid_price(
                book["bestBid"], book["bestAsk"], top_bid_size, top_ask_size,
            ),
            "order_imbalance": order_imbalance(book["bidDepth"], book["askDepth"]),
            "bid_depth_at_levels": cumulative_depth(book["bids"], depth_levels),
            "ask_depth_at_levels": cumulative_depth(book["asks"], depth_levels),
            "bid_vwap": vwap(book["bids"]),
            "ask_vwap": vwap(book["asks"]),
            "spread_bps": (book["spread"] / book["midPrice"] * 10_000) if book["midPrice"] > 0 else 0,
        },
    }


if __name__ == "__main__":
    result = fetch_orderbook_with_metrics("rm_your_key", "0x1234abcd...", "UP")
    m = result["metrics"]
    print(f"Weighted Mid: {m['weighted_mid_price']:.6f}")
    print(f"Spread (bps): {m['spread_bps']:.1f}")
    print(f"Imbalance:    {m['order_imbalance']:.4f}")
    print(f"Bid VWAP:     {m['bid_vwap']:.6f}")
    print(f"Ask VWAP:     {m['ask_vwap']:.6f}")
```

---

## 4. Historical Spread Analysis

Download snapshots over a time range and compute spread statistics: average, min, max, standard deviation, and a time series suitable for charting.

### Python (pandas)

```python
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import pandas as pd
import numpy as np

BASE_URL = "https://api.resolvedmarkets.com"


def fetch_snapshots_df(
    api_key: str,
    market_id: str,
    from_ts: str,
    to_ts: str,
    side: str = "UP",
    limit: int = 1000,
) -> pd.DataFrame:
    """Download all snapshots in a time range into a DataFrame."""
    headers = {"X-API-Key": api_key}
    rows = []
    offset = 0

    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30) as client:
        while True:
            resp = client.get(
                f"/v1/markets/{market_id}/snapshots",
                params={
                    "from": from_ts,
                    "to": to_ts,
                    "side": side,
                    "order": "asc",
                    "limit": limit,
                    "offset": offset,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            rows.extend(data["data"])

            if len(rows) >= data["total"] or len(data["data"]) < limit:
                break
            offset += limit

    df = pd.DataFrame(rows)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def analyze_spread(df: pd.DataFrame) -> dict:
    """Compute spread statistics from a snapshot DataFrame."""
    if df.empty:
        return {"error": "No data"}

    spread = df["spread"]
    mid = df["mid_price"]

    # Spread in basis points relative to mid price
    spread_bps = (spread / mid) * 10_000

    stats = {
        "count": len(df),
        "time_range": {
            "from": str(df["timestamp"].min()),
            "to": str(df["timestamp"].max()),
        },
        "spread": {
            "mean": float(spread.mean()),
            "median": float(spread.median()),
            "min": float(spread.min()),
            "max": float(spread.max()),
            "std": float(spread.std()),
            "p5": float(spread.quantile(0.05)),
            "p95": float(spread.quantile(0.95)),
        },
        "spread_bps": {
            "mean": float(spread_bps.mean()),
            "median": float(spread_bps.median()),
            "std": float(spread_bps.std()),
        },
        "mid_price": {
            "mean": float(mid.mean()),
            "min": float(mid.min()),
            "max": float(mid.max()),
        },
    }

    return stats


def spread_time_series(df: pd.DataFrame, resample: str = "1min") -> pd.DataFrame:
    """Resample spread data for charting. Returns timestamp, mean spread, and mid price."""
    if df.empty:
        return pd.DataFrame()

    ts = df.set_index("timestamp")[["spread", "mid_price"]]
    resampled = ts.resample(resample).agg(
        spread_mean=("spread", "mean"),
        spread_max=("spread", "max"),
        spread_min=("spread", "min"),
        mid_price=("mid_price", "mean"),
        count=("spread", "count"),
    ).dropna()

    return resampled.reset_index()


# Usage
if __name__ == "__main__":
    api_key = "rm_your_key"
    market_id = "0x1234abcd..."
    now = datetime.now(timezone.utc)

    df = fetch_snapshots_df(
        api_key=api_key,
        market_id=market_id,
        from_ts=(now - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        to_ts=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        side="UP",
    )

    print(f"Fetched {len(df)} snapshots")

    stats = analyze_spread(df)
    print(f"\nSpread Statistics:")
    print(f"  Mean:   {stats['spread']['mean']:.6f}")
    print(f"  Median: {stats['spread']['median']:.6f}")
    print(f"  Min:    {stats['spread']['min']:.6f}")
    print(f"  Max:    {stats['spread']['max']:.6f}")
    print(f"  StdDev: {stats['spread']['std']:.6f}")
    print(f"  P5-P95: {stats['spread']['p5']:.6f} - {stats['spread']['p95']:.6f}")
    print(f"\nSpread (bps): mean={stats['spread_bps']['mean']:.1f}, std={stats['spread_bps']['std']:.1f}")

    # Time series for charting
    ts = spread_time_series(df, resample="5min")
    print(f"\nTime series ({len(ts)} data points):")
    print(ts.head(10).to_string(index=False))

    # Optional: save for plotting
    # ts.to_csv("spread_timeseries.csv", index=False)
```

---

## 5. Multi-Market Liquidity Scanner

Scan all active markets, rank them by total liquidity (bid + ask depth), and flag markets where spread is unusually wide compared to their recent average.

Each scan costs 1 credit for the list, 1 credit for each orderbook and 3 credits for each summary. To scan fewer markets, add `category`, `crypto` or `timeframe` to the list request. The scanner waits for `Retry-After` on a 429 and stops on a 401 or 402. It skips a market on any other error, for example a 410 when the market ended during the scan.

### TypeScript

```typescript
const BASE_URL = "https://api.resolvedmarkets.com";

interface Market {
  conditionId: string;
  slug: string;
  question: string;
  category: string;
}

interface BookSide {
  spread: number;
  bidDepth: number;
  askDepth: number;
}

interface MarketOrderbook {
  up: BookSide | null;
  down: BookSide | null;
}

interface MarketSummary {
  avg_spread: number | null;
}

interface LiquidityReport {
  conditionId: string;
  slug: string;
  question: string;
  category: string;
  totalDepth: number;
  bidDepth: number;
  askDepth: number;
  spreadUp: number;
  spreadDown: number;
  avgSpread: number;
  spreadWidening: boolean;
}

class ApiStopError extends Error {}

async function getJson<T>(url: string, headers: Record<string, string>): Promise<T | null> {
  for (;;) {
    const res = await fetch(url, { headers });
    if (res.status === 429) {
      const wait = Number(res.headers.get("retry-after")) || 60;
      await new Promise((resolve) => setTimeout(resolve, wait * 1000));
      continue;
    }
    if (res.status === 401 || res.status === 402) {
      throw new ApiStopError(`API ${res.status}: ${await res.text()}`);
    }
    if (!res.ok) return null;
    return (await res.json()) as T;
  }
}

async function scanMarketLiquidity(apiKey: string): Promise<LiquidityReport[]> {
  const headers = { "X-API-Key": apiKey };

  // 1. Get all active markets
  const marketsRes = await fetch(`${BASE_URL}/v1/markets/live`, { headers });
  if (!marketsRes.ok) throw new Error(`Failed to list markets: ${marketsRes.status}`);
  const markets = (await marketsRes.json()) as Market[];

  const reports: LiquidityReport[] = [];

  // 2. Fetch orderbook and summary for each market
  for (const market of markets) {
    try {
      const obData = await getJson<MarketOrderbook>(`${BASE_URL}/v1/markets/${market.conditionId}/orderbook`, headers);
      const up = obData?.up;
      const down = obData?.down;
      if (!up || !down) continue;

      const sumData = await getJson<MarketSummary>(`${BASE_URL}/v1/markets/${market.conditionId}/summary`, headers);
      if (!sumData) continue;

      const totalDepth = up.bidDepth + up.askDepth + down.bidDepth + down.askDepth;

      const currentAvgSpread = (up.spread + down.spread) / 2;
      const historicalAvgSpread = sumData.avg_spread;

      // Flag if current spread is more than 2x the historical average
      const spreadWidening = historicalAvgSpread !== null && currentAvgSpread > historicalAvgSpread * 2;

      reports.push({
        conditionId: market.conditionId,
        slug: market.slug,
        question: market.question,
        category: market.category,
        totalDepth,
        bidDepth: up.bidDepth + down.bidDepth,
        askDepth: up.askDepth + down.askDepth,
        spreadUp: up.spread,
        spreadDown: down.spread,
        avgSpread: currentAvgSpread,
        spreadWidening,
      });
    } catch (err) {
      if (err instanceof ApiStopError) throw err;
      console.warn(`Skipping ${market.slug}: ${err}`);
    }
  }

  // 3. Sort by total depth descending
  reports.sort((a, b) => b.totalDepth - a.totalDepth);

  return reports;
}

// Usage
async function main(): Promise<void> {
  const reports = await scanMarketLiquidity("rm_your_key");

  console.log("=== Market Liquidity Rankings ===\n");
  for (const [i, r] of reports.entries()) {
    const warning = r.spreadWidening ? " ** SPREAD WIDENING **" : "";
    console.log(
      `${i + 1}. [${r.category}] ${r.slug}\n` +
      `   Depth: $${r.totalDepth.toFixed(0)} (bid=$${r.bidDepth.toFixed(0)} ask=$${r.askDepth.toFixed(0)})\n` +
      `   Spread UP: ${r.spreadUp.toFixed(4)}  DOWN: ${r.spreadDown.toFixed(4)}${warning}\n`,
    );
  }

  const alerts = reports.filter((r) => r.spreadWidening);
  if (alerts.length > 0) {
    console.log(`\n=== SPREAD ALERTS (${alerts.length}) ===`);
    for (const a of alerts) {
      console.log(`  - ${a.slug}: spread ${a.avgSpread.toFixed(4)} (widened)`);
    }
  }
}

main().catch(console.error);
```

### Python

```python
import time

import httpx

BASE_URL = "https://api.resolvedmarkets.com"


def get_json(client: httpx.Client, path: str):
    while True:
        resp = client.get(path)
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", 60)))
            continue
        if resp.status_code in (401, 402):
            resp.raise_for_status()
        if resp.status_code != 200:
            return None
        return resp.json()


def scan_market_liquidity(api_key: str) -> list[dict]:
    headers = {"X-API-Key": api_key}
    reports = []

    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30) as client:
        markets_resp = client.get("/v1/markets/live")
        markets_resp.raise_for_status()
        markets = markets_resp.json()

        for market in markets:
            cid = market["conditionId"]
            ob = get_json(client, f"/v1/markets/{cid}/orderbook")
            if not ob or not ob["up"] or not ob["down"]:
                continue
            summary = get_json(client, f"/v1/markets/{cid}/summary")
            if summary is None:
                continue

            up, down = ob["up"], ob["down"]
            total_depth = up["bidDepth"] + up["askDepth"] + down["bidDepth"] + down["askDepth"]
            avg_spread = (up["spread"] + down["spread"]) / 2
            widening = summary["avg_spread"] is not None and avg_spread > summary["avg_spread"] * 2

            reports.append({
                "conditionId": cid,
                "slug": market["slug"],
                "question": market["question"],
                "category": market["category"],
                "total_depth": total_depth,
                "bid_depth": up["bidDepth"] + down["bidDepth"],
                "ask_depth": up["askDepth"] + down["askDepth"],
                "spread_up": up["spread"],
                "spread_down": down["spread"],
                "avg_spread": avg_spread,
                "spread_widening": widening,
            })

    reports.sort(key=lambda r: r["total_depth"], reverse=True)
    return reports


if __name__ == "__main__":
    reports = scan_market_liquidity("rm_your_key")

    for i, r in enumerate(reports, 1):
        flag = " ** WIDENING **" if r["spread_widening"] else ""
        print(f"{i}. [{r['category']}] {r['slug']}")
        print(f"   Depth: ${r['total_depth']:.0f}  Spread: {r['avg_spread']:.4f}{flag}")

    alerts = [r for r in reports if r["spread_widening"]]
    if alerts:
        print(f"\nSPREAD ALERTS ({len(alerts)}):")
        for a in alerts:
            print(f"  - {a['slug']}: {a['avg_spread']:.4f}")
```

---

## 6. Build a Price Alert System

Complete alert system that polls orderbooks at configurable intervals, triggers alerts when spread exceeds a threshold or mid price crosses a user-defined level. Supports multiple markets and alert types.

Each poll costs 1 credit for each market in the rules. At the default interval of 5 seconds, one market uses 17,280 credits a day. The system pauses for `Retry-After` on a 429 and stops on a 401 or 402. On any other error, it skips the market until the next poll.

### TypeScript (Node.js)

```typescript
const BASE_URL = "https://api.resolvedmarkets.com";

type AlertType = "spread_threshold" | "price_cross_above" | "price_cross_below" | "depth_drop";

interface AlertRule {
  id: string;
  marketId: string;
  side: "UP" | "DOWN";
  type: AlertType;
  threshold: number;
  message?: string;
}

interface AlertEvent {
  rule: AlertRule;
  currentValue: number;
  threshold: number;
  timestamp: string;
}

type AlertHandler = (event: AlertEvent) => void;

class PriceAlertSystem {
  private apiKey: string;
  private rules: AlertRule[] = [];
  private pollInterval: number;
  private timer: ReturnType<typeof setInterval> | null = null;
  private previousMidPrices: Map<string, number> = new Map();
  private previousDepths: Map<string, number> = new Map();
  private handlers: AlertHandler[] = [];
  private running: boolean = false;
  private pausedUntil: number = 0;

  constructor(apiKey: string, pollIntervalMs: number = 5_000) {
    this.apiKey = apiKey;
    this.pollInterval = pollIntervalMs;
  }

  addRule(rule: AlertRule): void {
    this.rules.push(rule);
  }

  removeRule(ruleId: string): void {
    this.rules = this.rules.filter((r) => r.id !== ruleId);
  }

  onAlert(handler: AlertHandler): void {
    this.handlers.push(handler);
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    console.log(`Alert system started. Polling every ${this.pollInterval}ms with ${this.rules.length} rules.`);
    this.timer = setInterval(() => this.poll(), this.pollInterval);
    this.poll(); // Initial poll
  }

  stop(): void {
    this.running = false;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    console.log("Alert system stopped.");
  }

  private async poll(): Promise<void> {
    if (Date.now() < this.pausedUntil) return;
    // Group rules by market to minimize API calls
    const marketIds = new Set(this.rules.map((r) => r.marketId));

    for (const marketId of marketIds) {
      try {
        const res = await fetch(`${BASE_URL}/v1/markets/${marketId}/orderbook`, {
          headers: { "X-API-Key": this.apiKey },
        });
        if (res.status === 429) {
          const wait = Number(res.headers.get("retry-after")) || 60;
          console.warn(`Rate limited, pausing for ${wait}s`);
          this.pausedUntil = Date.now() + wait * 1000;
          return;
        }
        if (res.status === 401 || res.status === 402) {
          console.error(`API ${res.status}: ${await res.text()}, stopping`);
          this.stop();
          return;
        }
        if (!res.ok) {
          console.warn(`API ${res.status} for ${marketId}, skipped`);
          continue;
        }

        const data = await res.json() as any;
        const marketRules = this.rules.filter((r) => r.marketId === marketId);

        for (const rule of marketRules) {
          const book = rule.side === "UP" ? data.up : data.down;
          if (!book) continue;
          this.evaluateRule(rule, book);
        }
      } catch (err) {
        console.error(`Poll error for ${marketId}: ${err}`);
      }
    }
  }

  private evaluateRule(rule: AlertRule, book: any): void {
    const key = `${rule.marketId}:${rule.side}`;
    const now = new Date().toISOString();

    switch (rule.type) {
      case "spread_threshold": {
        if (book.spread > rule.threshold) {
          this.fireAlert({ rule, currentValue: book.spread, threshold: rule.threshold, timestamp: now });
        }
        break;
      }

      case "price_cross_above": {
        const prevMid = this.previousMidPrices.get(key);
        if (prevMid !== undefined && prevMid <= rule.threshold && book.midPrice > rule.threshold) {
          this.fireAlert({ rule, currentValue: book.midPrice, threshold: rule.threshold, timestamp: now });
        }
        this.previousMidPrices.set(key, book.midPrice);
        break;
      }

      case "price_cross_below": {
        const prevMid = this.previousMidPrices.get(key);
        if (prevMid !== undefined && prevMid >= rule.threshold && book.midPrice < rule.threshold) {
          this.fireAlert({ rule, currentValue: book.midPrice, threshold: rule.threshold, timestamp: now });
        }
        this.previousMidPrices.set(key, book.midPrice);
        break;
      }

      case "depth_drop": {
        const totalDepth = book.bidDepth + book.askDepth;
        const prevDepth = this.previousDepths.get(key);
        if (prevDepth !== undefined) {
          const dropPct = (prevDepth - totalDepth) / prevDepth;
          if (dropPct > rule.threshold) {
            this.fireAlert({
              rule,
              currentValue: dropPct,
              threshold: rule.threshold,
              timestamp: now,
            });
          }
        }
        this.previousDepths.set(key, totalDepth);
        break;
      }
    }
  }

  private fireAlert(event: AlertEvent): void {
    for (const handler of this.handlers) {
      try {
        handler(event);
      } catch (err) {
        console.error("Alert handler error:", err);
      }
    }
  }
}

// Usage
const alerts = new PriceAlertSystem("rm_your_key", 5_000);

// Alert when BTC UP spread exceeds 0.03
alerts.addRule({
  id: "btc-spread",
  marketId: "0x1234abcd...",
  side: "UP",
  type: "spread_threshold",
  threshold: 0.03,
});

// Alert when mid price crosses above 0.70
alerts.addRule({
  id: "btc-price-above-70",
  marketId: "0x1234abcd...",
  side: "UP",
  type: "price_cross_above",
  threshold: 0.70,
});

// Alert when mid price crosses below 0.50
alerts.addRule({
  id: "btc-price-below-50",
  marketId: "0x1234abcd...",
  side: "UP",
  type: "price_cross_below",
  threshold: 0.50,
});

// Alert when depth drops more than 30% between polls
alerts.addRule({
  id: "btc-depth-drop",
  marketId: "0x1234abcd...",
  side: "UP",
  type: "depth_drop",
  threshold: 0.30,
});

alerts.onAlert((event) => {
  console.log(
    `[ALERT] ${event.rule.type} on ${event.rule.marketId} ${event.rule.side}\n` +
    `  Value: ${event.currentValue.toFixed(6)} | Threshold: ${event.threshold}\n` +
    `  Time: ${event.timestamp}`,
  );
});

alerts.start();

process.on("SIGINT", () => {
  alerts.stop();
  process.exit(0);
});
```

---

## 7. Export Orderbook Data to Parquet/CSV

Bulk-download historical snapshots with pagination, flatten bid/ask arrays, and export to Parquet and CSV formats for backtesting pipelines.

### Python (pandas + pyarrow)

```python
"""
Export Resolved Markets orderbook snapshots to Parquet and CSV.

Requirements:
  pip install httpx pandas pyarrow
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd

BASE_URL = "https://api.resolvedmarkets.com"


def download_snapshots(
    api_key: str,
    market_id: str,
    from_ts: str,
    to_ts: str,
    side: str = "UP",
    limit: int = 1000,
    max_records: Optional[int] = None,
) -> list[dict]:
    """Download all snapshots for a market in a time range with pagination."""
    headers = {"X-API-Key": api_key}
    all_snapshots: list[dict] = []
    offset = 0

    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30) as client:
        while True:
            resp = client.get(
                f"/v1/markets/{market_id}/snapshots",
                params={
                    "from": from_ts,
                    "to": to_ts,
                    "side": side,
                    "order": "asc",
                    "includebook": "true",
                    "limit": limit,
                    "offset": offset,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            all_snapshots.extend(data["data"])
            print(f"  Downloaded {len(all_snapshots)}/{data['total']} snapshots...")

            if max_records and len(all_snapshots) >= max_records:
                all_snapshots = all_snapshots[:max_records]
                break

            if len(all_snapshots) >= data["total"] or len(data["data"]) < limit:
                break

            offset += limit

    return all_snapshots


def flatten_snapshot(snapshot: dict, max_levels: int = 10) -> dict:
    """Flatten a snapshot dict, expanding bid/ask arrays into columns."""
    flat: dict = {
        "timestamp": snapshot["timestamp"],
        "token_side": snapshot["token_side"],
        "best_bid": snapshot["best_bid"],
        "best_ask": snapshot["best_ask"],
        "mid_price": snapshot["mid_price"],
        "spread": snapshot["spread"],
        "bid_depth_total": snapshot["bid_depth_total"],
        "ask_depth_total": snapshot["ask_depth_total"],
        "event_timestamp": snapshot["event_timestamp"],
        "capture_timestamp": snapshot["capture_timestamp"],
        "sequence_number": snapshot["sequence_number"],
    }

    # Flatten bids: bid_0_price, bid_0_size, bid_1_price, ...
    for i in range(max_levels):
        if i < len(snapshot["bids"]):
            flat[f"bid_{i}_price"] = snapshot["bids"][i]["price"]
            flat[f"bid_{i}_size"] = snapshot["bids"][i]["size"]
        else:
            flat[f"bid_{i}_price"] = None
            flat[f"bid_{i}_size"] = None

    # Flatten asks
    for i in range(max_levels):
        if i < len(snapshot["asks"]):
            flat[f"ask_{i}_price"] = snapshot["asks"][i]["price"]
            flat[f"ask_{i}_size"] = snapshot["asks"][i]["size"]
        else:
            flat[f"ask_{i}_price"] = None
            flat[f"ask_{i}_size"] = None

    return flat


def export_to_files(
    api_key: str,
    market_id: str,
    from_ts: str,
    to_ts: str,
    side: str = "UP",
    output_dir: str = "./exports",
    max_levels: int = 10,
    max_records: Optional[int] = None,
) -> dict[str, str]:
    """Download snapshots and export to both Parquet and CSV."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Downloading snapshots for {market_id} ({side})...")
    snapshots = download_snapshots(
        api_key=api_key,
        market_id=market_id,
        from_ts=from_ts,
        to_ts=to_ts,
        side=side,
        max_records=max_records,
    )

    if not snapshots:
        print("No snapshots found.")
        return {}

    print(f"Flattening {len(snapshots)} snapshots (top {max_levels} levels)...")
    rows = [flatten_snapshot(s, max_levels) for s in snapshots]
    df = pd.DataFrame(rows)

    # Convert timestamps
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])
    df["capture_timestamp"] = pd.to_datetime(df["capture_timestamp"])

    # Add derived columns
    df["latency_ms"] = (df["capture_timestamp"] - df["event_timestamp"]).dt.total_seconds() * 1000
    df["total_depth"] = df["bid_depth_total"] + df["ask_depth_total"]
    df["imbalance"] = (df["bid_depth_total"] - df["ask_depth_total"]) / df["total_depth"]

    # Generate filenames
    safe_id = market_id[:16].replace("0x", "")
    from_date = from_ts[:10]
    to_date = to_ts[:10]
    base_name = f"snapshots_{safe_id}_{side}_{from_date}_{to_date}"

    csv_path = out / f"{base_name}.csv"
    parquet_path = out / f"{base_name}.parquet"

    # Export CSV
    df.to_csv(csv_path, index=False)
    print(f"CSV: {csv_path} ({csv_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Export Parquet (compressed)
    df.to_parquet(parquet_path, index=False, engine="pyarrow", compression="snappy")
    print(f"Parquet: {parquet_path} ({parquet_path.stat().st_size / 1024 / 1024:.1f} MB)")

    print(f"\nSchema: {len(df.columns)} columns, {len(df)} rows")
    print(f"Time range: {df['event_timestamp'].min()} to {df['event_timestamp'].max()}")
    print(f"Avg latency: {df['latency_ms'].mean():.1f}ms")

    return {"csv": str(csv_path), "parquet": str(parquet_path)}


# Usage
if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    paths = export_to_files(
        api_key="rm_your_key",
        market_id="0x1234abcd...",
        from_ts=(now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        to_ts=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        side="UP",
        output_dir="./exports",
        max_levels=10,
    )

    if paths:
        # Quick verification
        df = pd.read_parquet(paths["parquet"])
        print(f"\nVerification: {len(df)} rows loaded from Parquet")
        print(df.describe())
```

---

## 8. MCP Agent Integration

Configure AI tools (Claude Desktop, Cursor, Windsurf) to connect to the Resolved Markets MCP server for natural-language queries against live orderbook data.

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%/Claude/claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "resolved-markets": {
      "command": "npx",
      "args": ["-y", "@elcara-hq/resolvedmarkets-mcp"],
      "env": {
        "HF_API_URL": "https://api.resolvedmarkets.com",
        "HF_API_KEY": "rm_your_key"
      }
    }
  }
}
```

### Cursor Configuration

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "resolved-markets": {
      "command": "npx",
      "args": ["-y", "@elcara-hq/resolvedmarkets-mcp"],
      "env": {
        "HF_API_URL": "https://api.resolvedmarkets.com",
        "HF_API_KEY": "rm_your_key"
      }
    }
  }
}
```

### Windsurf Configuration

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "resolved-markets": {
      "command": "npx",
      "args": ["-y", "@elcara-hq/resolvedmarkets-mcp"],
      "env": {
        "HF_API_URL": "https://api.resolvedmarkets.com",
        "HF_API_KEY": "rm_your_key"
      }
    }
  }
}
```

### Claude Code Configuration

Add to `.claude/settings.json` or `~/.claude.json`:

```json
{
  "mcpServers": {
    "resolved-markets": {
      "command": "npx",
      "args": ["-y", "@elcara-hq/resolvedmarkets-mcp"],
      "env": {
        "HF_API_URL": "https://api.resolvedmarkets.com",
        "HF_API_KEY": "rm_your_key"
      }
    }
  }
}
```

### Example Prompts for Each MCP Tool

Once connected, use these prompts in any MCP-enabled AI tool:

**`list_markets` — List active markets**
```
List all active crypto prediction markets on Resolved Markets.
```
```
Show me only the sports markets that are currently trading.
```

**`get_orderbook` — Live orderbook data**
```
Show me the current BTC orderbook with bid and ask levels.
```
```
What's the spread on the ETH market "will-eth-be-above-4000-on-march-25"?
```

**`get_snapshot` — Historical point-in-time data**
```
What was the BTC prediction market orderbook at 2026-03-24 noon UTC?
```
```
Show me the SOL market snapshot from yesterday at market close.
```

**`query_snapshots` — Query historical data with filters**
```
Get the last 50 snapshots for the BTC UP token from the past hour.
```
```
Query all ETH snapshots between 9am and 10am today. Show me the spread trend.
```

**`get_market_summary` — Aggregated statistics**
```
Give me a 24-hour summary of the BTC prediction market — average spread, depth, price range.
```
```
Compare the liquidity summary of ETH vs SOL markets.
```

**`get_system_stats` — Platform health**
```
What's the current system health? How many snapshots have been collected?
```
```
Show me the platform stats including active market count and crypto prices.
```

---

## 9. React Live Dashboard Hook

Custom React hook `useOrderbookStream` for WebSocket orderbook data in React/Next.js applications. Manages connection lifecycle, typed state, and cleanup on unmount. Each hook call opens one connection for one coin, and the server sends the books of that coin every 2 seconds. The hook uses the close-code rule of section 2: it stops on 4003 `Invalid API key` or `Tier restriction`, waits 60 seconds after 4003 `Connection limit`, and reconnects with backoff after any other close.

### TypeScript (React)

```typescript
// useOrderbookStream.ts
import { useCallback, useEffect, useRef, useState } from "react";

type ConnectionStatus = "disconnected" | "connecting" | "connected" | "authenticated" | "error";

interface Level {
  price: number;
  size: number;
}

interface BookSide {
  tokenId: string;
  bids: Level[];
  asks: Level[];
  bestBid: number;
  bestAsk: number;
  midPrice: number;
  spread: number;
  timestamp: number;
}

interface OrderbookMarket {
  marketId: string;
  crypto: string;
  timeframe: string;
  question: string;
  cryptoPrice: number;
  up: BookSide | null;
  down: BookSide | null;
}

interface UseOrderbookStreamOptions {
  apiKey: string;
  crypto: string;
  url?: string;
  enabled?: boolean;
  reconnectDelay?: number;
  maxReconnectDelay?: number;
}

interface UseOrderbookStreamResult {
  markets: OrderbookMarket[];
  status: ConnectionStatus;
  error: string | null;
  lastUpdate: Date | null;
  reconnectCount: number;
}

export function useOrderbookStream(options: UseOrderbookStreamOptions): UseOrderbookStreamResult {
  const {
    apiKey,
    crypto,
    url = "wss://api.resolvedmarkets.com/ws/orderbook",
    enabled = true,
    reconnectDelay = 1000,
    maxReconnectDelay = 30000,
  } = options;

  const [markets, setMarkets] = useState<OrderbookMarket[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [reconnectCount, setReconnectCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const mountedRef = useRef(true);

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current || !enabled) return;
    cleanup();

    setStatus("connecting");
    setError(null);

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setStatus("connected");
      ws.send(JSON.stringify({ type: "auth", apiKey }));
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;

      let msg: Record<string, unknown>;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }

      if (msg.type === "auth") {
        if (msg.status === "ok") {
          setStatus("authenticated");
          reconnectAttemptRef.current = 0;
          ws.send(JSON.stringify({ type: "subscribe", crypto: crypto.toUpperCase() }));
        } else {
          setStatus("error");
          setError("Authentication failed");
        }
        return;
      }

      if (msg.type === "error") {
        setError(String(msg.message));
        return;
      }

      if (msg.type === "orderbook") {
        setMarkets(msg.markets as OrderbookMarket[]);
        setLastUpdate(new Date());
      }
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setError("WebSocket error");
    };

    ws.onclose = (event) => {
      if (!mountedRef.current) return;
      wsRef.current = null;

      if (event.code === 4003 && event.reason !== "Connection limit") {
        setStatus("error");
        return;
      }

      setStatus("disconnected");

      if (event.code === 4001) {
        setError("Authentication timeout (5s exceeded)");
      }

      // Auto-reconnect with exponential backoff
      if (enabled) {
        const backoff = Math.min(
          reconnectDelay * Math.pow(2, reconnectAttemptRef.current),
          maxReconnectDelay,
        );
        const delay = event.code === 4003 ? Math.max(backoff, 60000) : backoff;
        reconnectAttemptRef.current++;
        setReconnectCount((c) => c + 1);
        reconnectTimerRef.current = setTimeout(connect, delay);
      }
    };
  }, [apiKey, crypto, url, enabled, reconnectDelay, maxReconnectDelay, cleanup]);

  // Connect/disconnect on enabled change
  useEffect(() => {
    mountedRef.current = true;
    if (enabled) {
      connect();
    }
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [enabled, connect, cleanup]);

  return { markets, status, error, lastUpdate, reconnectCount };
}
```

### React Component Example: Live Spread Ticker

Each `SpreadTicker` opens one connection for one coin. Render one for each coin, up to your plan's connection limit: `<SpreadTicker apiKey={apiKey} crypto="BTC" />`.

```tsx
// SpreadTicker.tsx
import React from "react";
import { useOrderbookStream } from "./useOrderbookStream";

interface SpreadTickerProps {
  apiKey: string;
  crypto: string;
}

export function SpreadTicker({ apiKey, crypto }: SpreadTickerProps): React.ReactElement {
  const { markets, status, error, lastUpdate, reconnectCount } = useOrderbookStream({
    apiKey,
    crypto,
  });

  return (
    <div style={{ fontFamily: "monospace", padding: 20 }}>
      <h2>{crypto} Spread Ticker</h2>

      <div style={{ marginBottom: 12 }}>
        <span>Status: <strong>{status}</strong></span>
        {reconnectCount > 0 && <span> (reconnects: {reconnectCount})</span>}
        {lastUpdate && <span> | Last update: {lastUpdate.toLocaleTimeString()}</span>}
        {error && <span style={{ color: "red" }}> | Error: {error}</span>}
      </div>

      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={thStyle}>Timeframe</th>
            <th style={thStyle}>Side</th>
            <th style={thStyle}>Best Bid</th>
            <th style={thStyle}>Best Ask</th>
            <th style={thStyle}>Mid Price</th>
            <th style={thStyle}>Spread</th>
            <th style={thStyle}>Spread (bps)</th>
          </tr>
        </thead>
        <tbody>
          {markets.map((market) =>
            (["up", "down"] as const).map((side) => {
              const key = `${market.marketId}:${side}`;
              const snap = market[side];
              if (!snap) {
                return (
                  <tr key={key}>
                    <td style={tdStyle}>{market.timeframe}</td>
                    <td style={tdStyle}>{side.toUpperCase()}</td>
                    <td style={tdStyle} colSpan={5}>Waiting for data...</td>
                  </tr>
                );
              }
              const spreadBps = snap.midPrice > 0
                ? ((snap.spread / snap.midPrice) * 10000).toFixed(1)
                : "N/A";
              return (
                <tr key={key}>
                  <td style={tdStyle}>{market.timeframe}</td>
                  <td style={tdStyle}>{side.toUpperCase()}</td>
                  <td style={tdStyle}>{snap.bestBid.toFixed(4)}</td>
                  <td style={tdStyle}>{snap.bestAsk.toFixed(4)}</td>
                  <td style={tdStyle}>{snap.midPrice.toFixed(4)}</td>
                  <td style={tdStyle}>{snap.spread.toFixed(4)}</td>
                  <td style={{
                    ...tdStyle,
                    color: parseFloat(spreadBps) > 200 ? "red" : "green",
                  }}>
                    {spreadBps}
                  </td>
                </tr>
              );
            }),
          )}
        </tbody>
      </table>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  borderBottom: "2px solid #333",
};

const tdStyle: React.CSSProperties = {
  padding: "6px 12px",
  borderBottom: "1px solid #ddd",
};
```

---

## 10. Market Arbitrage Monitor

Monitor all active prediction markets and detect when the sum of UP and DOWN token mid prices deviates from 1.00. This deviation signals a potential arbitrage opportunity. Verify that sufficient depth exists to execute the trade.

Each scan costs 1 credit for the list and 1 credit for the orderbook of each listed market, and each request counts against your requests per minute. The monitor filters the list by `category` and scans every 60 seconds. It waits for `Retry-After` on a 429, stops on a 401 or 402, and skips a market on any other error. To check every 2 seconds, use the WebSocket stream of section 2.

### Python

```python
"""
Resolved Markets Arbitrage Monitor

In a binary prediction market, UP + DOWN token prices should sum to ~1.00.
Deviations represent potential arbitrage opportunities.

Requirements:
  pip install httpx
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

BASE_URL = "https://api.resolvedmarkets.com"


@dataclass
class ArbitrageSignal:
    condition_id: str
    slug: str
    question: str
    up_mid: float
    down_mid: float
    total: float
    deviation: float
    deviation_pct: float
    direction: str  # "overpriced" (>1) or "underpriced" (<1)
    up_bid_depth: float
    up_ask_depth: float
    down_bid_depth: float
    down_ask_depth: float
    executable_size: float  # Max size executable at this deviation
    timestamp: str


def calculate_executable_size(
    up_book: dict,
    down_book: dict,
    direction: str,
) -> float:
    """
    Calculate the maximum trade size that maintains the arbitrage.

    If overpriced (UP_mid + DOWN_mid > 1): sell both tokens.
      - Executable size = min(UP bid depth, DOWN bid depth)
    If underpriced (UP_mid + DOWN_mid < 1): buy both tokens.
      - Executable size = min(UP ask depth, DOWN ask depth)
    """
    if direction == "overpriced":
        return min(up_book["bidDepth"], down_book["bidDepth"])
    else:
        return min(up_book["askDepth"], down_book["askDepth"])


def get_json(client: httpx.Client, path: str, params: Optional[dict] = None):
    while True:
        resp = client.get(path, params=params)
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", 60)))
            continue
        if resp.status_code in (401, 402):
            resp.raise_for_status()
        if resp.status_code != 200:
            return None
        return resp.json()


def check_arbitrage(
    api_key: str,
    deviation_threshold: float = 0.02,
    min_executable_size: float = 100.0,
    category: str = "crypto",
) -> list[ArbitrageSignal]:
    """Scan all active markets for arbitrage opportunities."""
    headers = {"X-API-Key": api_key}
    signals: list[ArbitrageSignal] = []

    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=30) as client:
        # Get all active markets
        markets = get_json(client, "/v1/markets/live", {"category": category})
        if markets is None:
            raise RuntimeError("Could not list the live markets")

        for market in markets:
            cid = market["conditionId"]
            data = get_json(client, f"/v1/markets/{cid}/orderbook")
            if data is None:
                continue

            up = data["up"]
            down = data["down"]
            if not up or not down:
                continue

            up_mid = up["midPrice"]
            down_mid = down["midPrice"]

            # Skip if no valid mid prices
            if up_mid == 0 or down_mid == 0:
                continue

            total = up_mid + down_mid
            deviation = abs(total - 1.0)
            deviation_pct = deviation * 100

            if deviation < deviation_threshold:
                continue

            direction = "overpriced" if total > 1.0 else "underpriced"
            executable = calculate_executable_size(up, down, direction)

            if executable < min_executable_size:
                continue

            signals.append(ArbitrageSignal(
                condition_id=cid,
                slug=market["slug"],
                question=market["question"],
                up_mid=up_mid,
                down_mid=down_mid,
                total=total,
                deviation=deviation,
                deviation_pct=deviation_pct,
                direction=direction,
                up_bid_depth=up["bidDepth"],
                up_ask_depth=up["askDepth"],
                down_bid_depth=down["bidDepth"],
                down_ask_depth=down["askDepth"],
                executable_size=executable,
                timestamp=datetime.fromtimestamp(max(up["timestamp"], down["timestamp"]) / 1000, timezone.utc).isoformat(),
            ))

    # Sort by deviation descending (best opportunities first)
    signals.sort(key=lambda s: s.deviation, reverse=True)
    return signals


def monitor_loop(
    api_key: str,
    interval_seconds: float = 60.0,
    deviation_threshold: float = 0.02,
    min_executable_size: float = 100.0,
) -> None:
    """Continuously monitor for arbitrage opportunities."""
    print(f"Arbitrage monitor started (threshold={deviation_threshold}, "
          f"min_size=${min_executable_size:.0f}, interval={interval_seconds}s)")
    print("-" * 80)

    seen_signals: set[str] = set()

    while True:
        try:
            signals = check_arbitrage(
                api_key=api_key,
                deviation_threshold=deviation_threshold,
                min_executable_size=min_executable_size,
            )

            for signal in signals:
                key = f"{signal.condition_id}:{signal.direction}"

                # Log new or updated signals
                status = "NEW" if key not in seen_signals else "ONGOING"
                seen_signals.add(key)

                print(
                    f"[{status}] {signal.direction.upper()} | "
                    f"{signal.slug}\n"
                    f"  UP={signal.up_mid:.4f} + DOWN={signal.down_mid:.4f} = "
                    f"{signal.total:.4f} (deviation: {signal.deviation_pct:.2f}%)\n"
                    f"  Executable size: ${signal.executable_size:.0f}\n"
                    f"  UP depth: bid=${signal.up_bid_depth:.0f} ask=${signal.up_ask_depth:.0f}\n"
                    f"  DOWN depth: bid=${signal.down_bid_depth:.0f} ask=${signal.down_ask_depth:.0f}\n"
                    f"  Time: {signal.timestamp}\n"
                )

            # Clear stale signals
            current_keys = {f"{s.condition_id}:{s.direction}" for s in signals}
            resolved = seen_signals - current_keys
            for key in resolved:
                print(f"[RESOLVED] {key} — arbitrage opportunity closed")
            seen_signals = current_keys

            if not signals:
                print(f"No arbitrage opportunities detected. Scanning again in {interval_seconds}s...")

        except httpx.HTTPStatusError as e:
            print(f"Stopping: {e}")
            return
        except Exception as e:
            print(f"Monitor error: {e}")

        time.sleep(interval_seconds)


# Usage
if __name__ == "__main__":
    # Single scan
    signals = check_arbitrage(
        api_key="rm_your_key",
        deviation_threshold=0.02,
        min_executable_size=100.0,
    )

    if signals:
        print(f"Found {len(signals)} arbitrage opportunities:\n")
        for s in signals:
            print(f"  {s.slug}: {s.direction} by {s.deviation_pct:.2f}% "
                  f"(size=${s.executable_size:.0f})")
    else:
        print("No arbitrage opportunities found.")

    # Continuous monitoring (uncomment to run):
    # monitor_loop(
    #     api_key="rm_your_key",
    #     interval_seconds=60,
    #     deviation_threshold=0.015,
    #     min_executable_size=50.0,
    # )
```
