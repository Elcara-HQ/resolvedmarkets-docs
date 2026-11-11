# SDK & Integration Patterns

Complete integration examples for every major stack. All examples use the production API at `https://api.resolvedmarkets.com`.

---

## Node.js / TypeScript

### Install

```bash
npm install ws
# or: pnpm add ws
# Types: npm install -D @types/ws
```

### REST Client

```typescript
interface Market {
  conditionId: string;
  slug: string;
  question: string;
  category: string;
  timeframe: string;
  tokenIds: string[];
  endDate: string;
  status: "upcoming" | "live" | "settling" | "expired";
}

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
  bidDepth: number;
  askDepth: number;
  timestamp: number;
}

interface MarketOrderbook {
  market_id: string;
  question: string;
  up: BookSide | null;
  down: BookSide | null;
}

interface SnapshotRow {
  timestamp: string;
  token_side: "UP" | "DOWN";
  best_bid: number;
  best_ask: number;
  mid_price: number;
  spread: number;
  bid_depth_total: number;
  ask_depth_total: number;
}

interface SnapshotPage {
  market_id: string;
  total: number;
  limit: number;
  offset: number;
  data: SnapshotRow[];
}

interface MarketBySlug {
  market_id: string;
  slug: string;
  question: string;
  token_ids: string[];
  end_date: string | null;
  active: boolean;
}

interface PublicStats {
  snapshot_count: string;
  active_markets: number;
  prices: Record<string, number>;
}

class ResolvedMarketsClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(apiKey: string, baseUrl = "https://api.resolvedmarkets.com") {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  private async request<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: { "X-API-Key": this.apiKey },
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`API ${res.status}: ${body}`);
    }

    return res.json() as Promise<T>;
  }

  async getPublicStats(): Promise<PublicStats> {
    const res = await fetch(`${this.baseUrl}/v1/public-stats`);
    return res.json() as Promise<PublicStats>;
  }

  async listMarkets(filters: Record<string, string> = {}): Promise<Market[]> {
    const qs = new URLSearchParams(filters).toString();
    return this.request(`/v1/markets/live${qs ? `?${qs}` : ""}`);
  }

  async getOrderbook(marketId: string): Promise<MarketOrderbook> {
    return this.request(`/v1/markets/${marketId}/orderbook`);
  }

  async getSnapshots(
    marketId: string,
    params?: { limit?: number; offset?: number; side?: "UP" | "DOWN" }
  ): Promise<SnapshotPage> {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    if (params?.side) qs.set("side", params.side);
    const query = qs.toString() ? `?${qs}` : "";
    return this.request(`/v1/markets/${marketId}/snapshots${query}`);
  }

  async getMarketSummary(marketId: string): Promise<Record<string, unknown>> {
    return this.request(`/v1/markets/${marketId}/summary`);
  }

  async getMarketBySlug(slug: string): Promise<MarketBySlug> {
    return this.request(`/v1/markets/by-slug/${slug}`);
  }
}

async function main() {
  const client = new ResolvedMarketsClient(process.env.RM_API_KEY!);

  const markets = await client.listMarkets({ crypto: "BTC", timeframe: "5m" });
  const live = markets.filter((m) => m.status === "live");
  for (const market of live) {
    const book = await client.getOrderbook(market.conditionId);
    console.log(`${market.slug}: spread=${book.up?.spread}`);
  }

  if (live.length > 0) {
    const page = await client.getSnapshots(live[0].conditionId, { limit: 100, side: "UP" });
    console.log(`${page.total} snapshots; newest mid ${page.data[0]?.mid_price}`);
  }
}

main().catch(console.error);
```

### WebSocket Streaming with Reconnect

Each connection follows one coin, so `connectOrderbook` opens one connection for one coin. Call it once for each coin, up to your plan's connection limit. The server sends an `orderbook` message every 2 seconds. The client reconnects after a network error. It stops when the server closes the connection with code 4001 (auth timeout) or 4003 (invalid key, a plan without WebSocket access, or the connection limit of the plan).

```typescript
import WebSocket from "ws";

type Crypto = "BTC" | "ETH" | "SOL" | "XRP" | "DOGE" | "HYPE" | "BNB";

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
  crypto: Crypto;
  timeframe: string;
  question: string;
  cryptoPrice: number;
  up: BookSide | null;
  down: BookSide | null;
}

function connectOrderbook(
  apiKey: string,
  crypto: Crypto,
  onMarket: (market: OrderbookMarket) => void
): { close: () => void } {
  const WS_URL = "wss://api.resolvedmarkets.com/ws/orderbook";
  let ws: WebSocket;
  let alive = true;
  let reconnectDelay = 1000;

  function connect() {
    ws = new WebSocket(WS_URL);

    ws.on("open", () => {
      reconnectDelay = 1000;
      ws.send(JSON.stringify({ type: "auth", apiKey }));
    });

    ws.on("message", (raw: Buffer) => {
      const msg = JSON.parse(raw.toString());

      if (msg.type === "auth" && msg.status === "ok") {
        ws.send(JSON.stringify({ type: "subscribe", crypto }));
        return;
      }

      if (msg.type === "error") {
        console.error(`Server error ${msg.code}: ${msg.message}`);
        return;
      }

      if (msg.type === "orderbook") {
        for (const market of msg.markets as OrderbookMarket[]) {
          onMarket(market);
        }
      }
    });

    ws.on("close", (code: number, reason: Buffer) => {
      if (!alive) return;
      if (code === 4001 || code === 4003) {
        console.error(`Server closed the connection (${code}, ${reason.toString()}): not reconnecting`);
        alive = false;
        return;
      }
      console.log(`Disconnected (${code}), reconnecting in ${reconnectDelay}ms...`);
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    });

    ws.on("error", (err: Error) => {
      console.error("WebSocket error:", err.message);
    });
  }

  connect();

  return {
    close: () => {
      alive = false;
      ws?.close();
    },
  };
}

// Usage
const cryptos: Crypto[] = ["BTC", "ETH"];
const streams = cryptos.map((crypto) =>
  connectOrderbook(process.env.RM_API_KEY!, crypto, (market) => {
    if (!market.up) return;
    console.log(
      `${market.crypto} ${market.timeframe} UP: ` +
      `mid=${market.up.midPrice} spread=${market.up.spread}`
    );
  })
);

// Graceful shutdown
process.on("SIGINT", () => streams.forEach((stream) => stream.close()));
```

---

## Python

### Install

```bash
pip install requests websockets
```

### REST Client

```python
from __future__ import annotations

import requests
from dataclasses import dataclass
from typing import Any


@dataclass
class ResolvedMarketsClient:
    api_key: str
    base_url: str = "https://api.resolvedmarkets.com"

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key}

    def _get(self, path: str, params: dict | None = None) -> Any:
        resp = requests.get(
            f"{self.base_url}{path}", headers=self._headers, params=params, timeout=10
        )
        resp.raise_for_status()
        return resp.json()

    def public_stats(self) -> dict:
        """No auth required."""
        resp = requests.get(f"{self.base_url}/v1/public-stats", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def list_markets(self, **filters: str) -> list[dict]:
        return self._get("/v1/markets/live", params=filters)

    def get_orderbook(self, market_id: str) -> dict:
        return self._get(f"/v1/markets/{market_id}/orderbook")

    def get_snapshots(
        self, market_id: str, *, limit: int = 500, offset: int = 0
    ) -> list[dict]:
        return self._get(
            f"/v1/markets/{market_id}/snapshots",
            params={"limit": limit, "offset": offset},
        )["data"]

    def get_market_summary(self, market_id: str) -> dict:
        return self._get(f"/v1/markets/{market_id}/summary")

    def get_market_by_slug(self, slug: str) -> dict:
        return self._get(f"/v1/markets/by-slug/{slug}")


import os

client = ResolvedMarketsClient(api_key=os.environ["RM_API_KEY"])

for m in client.list_markets(crypto="BTC", timeframe="5m"):
    if m["status"] != "live":
        continue
    book = client.get_orderbook(m["conditionId"])
    if book["up"]:
        print(f"{m['slug']}: spread={book['up']['spread']}")
```

### Async WebSocket Streaming

Each connection follows one coin, so the example runs one `stream_orderbook` for each coin. `max_size=None` lets the first `markets` message through: it can be larger than the 1 MiB default limit of `websockets`. On code 4001 (auth timeout) or 4003 (invalid key, a plan without WebSocket access, or the connection limit of the plan), `stream_orderbook` raises `PermissionError` and does not reconnect.

```python
import asyncio
import json
import os
import websockets
from websockets.exceptions import ConnectionClosed


async def stream_orderbook(
    api_key: str,
    crypto: str,
    on_market,
    *,
    reconnect: bool = True,
):
    url = "wss://api.resolvedmarkets.com/ws/orderbook"
    delay = 1.0

    while True:
        try:
            async with websockets.connect(url, max_size=None) as ws:
                delay = 1.0
                await ws.send(json.dumps({"type": "auth", "apiKey": api_key}))

                auth = json.loads(await ws.recv())
                if auth.get("code") in (4001, 4003):
                    raise PermissionError(f"Server refused the connection ({auth['code']}): {auth.get('message')}")
                if auth.get("status") != "ok":
                    raise RuntimeError(f"Auth failed: {auth}")

                await ws.send(json.dumps({"type": "subscribe", "crypto": crypto}))

                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("type") == "orderbook":
                        for market in msg["markets"]:
                            await on_market(market)

        except PermissionError:
            raise

        except ConnectionClosed as e:
            code = e.rcvd.code if e.rcvd else None
            if code in (4001, 4003):
                raise PermissionError(f"Server closed the connection ({code}): {e.rcvd.reason}") from e
            if not reconnect:
                raise
            print(f"Disconnected ({code}), reconnecting in {delay}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)

        except Exception as e:
            if not reconnect:
                raise
            print(f"Error: {e}, reconnecting in {delay}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


# Usage
async def handle_market(market: dict):
    up = market["up"]
    if up:
        print(
            f"{market['crypto']} {market['timeframe']} UP: "
            f"mid={up['midPrice']} spread={up['spread']}"
        )


async def main():
    api_key = os.environ["RM_API_KEY"]
    await asyncio.gather(
        *(stream_orderbook(api_key, crypto, handle_market) for crypto in ["BTC", "ETH"])
    )


asyncio.run(main())
```

---

## Go

### Dependencies

```bash
go get github.com/gorilla/websocket
```

### REST Client

```go
package resolvedmarkets

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

type Client struct {
	BaseURL    string
	APIKey     string
	HTTPClient *http.Client
}

func NewClient(apiKey string) *Client {
	return &Client{
		BaseURL: "https://api.resolvedmarkets.com",
		APIKey:  apiKey,
		HTTPClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

type Market struct {
	ConditionID string   `json:"conditionId"`
	Slug        string   `json:"slug"`
	Question    string   `json:"question"`
	Category    string   `json:"category"`
	Timeframe   string   `json:"timeframe"`
	TokenIDs    []string `json:"tokenIds"`
	EndDate     string   `json:"endDate"`
	Status      string   `json:"status"`
}

type OrderLevel struct {
	Price float64 `json:"price"`
	Size  float64 `json:"size"`
}

type BookSide struct {
	TokenID   string       `json:"tokenId"`
	Bids      []OrderLevel `json:"bids"`
	Asks      []OrderLevel `json:"asks"`
	BestBid   float64      `json:"bestBid"`
	BestAsk   float64      `json:"bestAsk"`
	MidPrice  float64      `json:"midPrice"`
	Spread    float64      `json:"spread"`
	Timestamp int64        `json:"timestamp"`
}

type MarketOrderbook struct {
	MarketID string    `json:"market_id"`
	Question string    `json:"question"`
	Up       *BookSide `json:"up"`
	Down     *BookSide `json:"down"`
}

func (c *Client) doGet(path string, result interface{}) error {
	req, err := http.NewRequest("GET", c.BaseURL+path, nil)
	if err != nil {
		return err
	}
	req.Header.Set("X-API-Key", c.APIKey)

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API %d: %s", resp.StatusCode, string(body))
	}

	return json.NewDecoder(resp.Body).Decode(result)
}

func (c *Client) ListMarkets(filters url.Values) ([]Market, error) {
	path := "/v1/markets/live"
	if len(filters) > 0 {
		path += "?" + filters.Encode()
	}
	var markets []Market
	if err := c.doGet(path, &markets); err != nil {
		return nil, err
	}
	return markets, nil
}

func (c *Client) GetOrderbook(marketID string) (*MarketOrderbook, error) {
	var book MarketOrderbook
	if err := c.doGet("/v1/markets/"+marketID+"/orderbook", &book); err != nil {
		return nil, err
	}
	return &book, nil
}

func (c *Client) GetMarketSummary(marketID string) (map[string]interface{}, error) {
	var summary map[string]interface{}
	if err := c.doGet("/v1/markets/"+marketID+"/summary", &summary); err != nil {
		return nil, err
	}
	return summary, nil
}
```

### WebSocket Streaming

Each connection follows one coin. `StreamOrderbook` keeps one connection for one coin; run it once for each coin. Save this code as a second file of the `resolvedmarkets` package: it uses `BookSide` and `OrderLevel` of the REST client. `StreamOrderbook` reconnects after a network error. On code 4001 (auth timeout) or 4003 (invalid key, a plan without WebSocket access, or the connection limit of the plan), it returns a `RefusedError` and does not reconnect.

```go
package resolvedmarkets

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"math"
	"time"

	"github.com/gorilla/websocket"
)

type OrderbookMarket struct {
	MarketID    string    `json:"marketId"`
	Crypto      string    `json:"crypto"`
	Timeframe   string    `json:"timeframe"`
	Question    string    `json:"question"`
	CryptoPrice float64   `json:"cryptoPrice"`
	Up          *BookSide `json:"up"`
	Down        *BookSide `json:"down"`
}

type RefusedError struct {
	Code   int
	Reason string
}

func (e *RefusedError) Error() string {
	return fmt.Sprintf("server refused the connection (%d): %s", e.Code, e.Reason)
}

func refusal(err error) error {
	var closeErr *websocket.CloseError
	if errors.As(err, &closeErr) && (closeErr.Code == 4001 || closeErr.Code == 4003) {
		return &RefusedError{Code: closeErr.Code, Reason: closeErr.Text}
	}
	return err
}

func StreamOrderbook(apiKey, crypto string, onMarket func(OrderbookMarket)) error {
	url := "wss://api.resolvedmarkets.com/ws/orderbook"
	delay := time.Second

	for {
		err := connectAndStream(url, apiKey, crypto, onMarket)
		var refused *RefusedError
		if errors.As(err, &refused) {
			return err
		}
		if err != nil {
			log.Printf("Disconnected: %v, reconnecting in %v", err, delay)
			time.Sleep(delay)
			delay = time.Duration(math.Min(float64(delay*2), float64(30*time.Second)))
			continue
		}
		return nil
	}
}

func connectAndStream(url, apiKey, crypto string, onMarket func(OrderbookMarket)) error {
	conn, _, err := websocket.DefaultDialer.Dial(url, nil)
	if err != nil {
		return fmt.Errorf("dial: %w", err)
	}
	defer conn.Close()

	// Authenticate
	auth := map[string]string{"type": "auth", "apiKey": apiKey}
	if err := conn.WriteJSON(auth); err != nil {
		return fmt.Errorf("auth send: %w", err)
	}

	var authResp struct {
		Status  string `json:"status"`
		Code    int    `json:"code"`
		Message string `json:"message"`
	}
	if err := conn.ReadJSON(&authResp); err != nil {
		return fmt.Errorf("auth read: %w", refusal(err))
	}
	if authResp.Code == 4001 || authResp.Code == 4003 {
		return &RefusedError{Code: authResp.Code, Reason: authResp.Message}
	}
	if authResp.Status != "ok" {
		return fmt.Errorf("auth failed: %+v", authResp)
	}

	// Subscribe
	sub := map[string]string{"type": "subscribe", "crypto": crypto}
	if err := conn.WriteJSON(sub); err != nil {
		return fmt.Errorf("subscribe: %w", err)
	}

	// Read loop
	for {
		_, raw, err := conn.ReadMessage()
		if err != nil {
			return fmt.Errorf("read: %w", refusal(err))
		}

		var msg struct {
			Type string `json:"type"`
		}
		if err := json.Unmarshal(raw, &msg); err != nil {
			continue
		}

		if msg.Type == "orderbook" {
			var book struct {
				Markets []OrderbookMarket `json:"markets"`
			}
			if err := json.Unmarshal(raw, &book); err != nil {
				log.Printf("decode orderbook: %v", err)
				continue
			}
			for _, m := range book.Markets {
				onMarket(m)
			}
		}
	}
}
```

### Usage (main.go)

```go
package main

import (
	"fmt"
	"log"
	"net/url"
	"os"
	"sync"

	rm "your-module/resolvedmarkets"
)

func main() {
	client := rm.NewClient(os.Getenv("RM_API_KEY"))

	markets, err := client.ListMarkets(url.Values{"crypto": {"BTC"}, "timeframe": {"5m"}})
	if err != nil {
		log.Fatal(err)
	}
	for _, m := range markets {
		if m.Status != "live" {
			continue
		}
		book, err := client.GetOrderbook(m.ConditionID)
		if err != nil || book.Up == nil {
			continue
		}
		fmt.Printf("%s: spread=%.4f\n", m.Slug, book.Up.Spread)
	}

	var wg sync.WaitGroup
	for _, crypto := range []string{"BTC", "ETH"} {
		wg.Add(1)
		go func(crypto string) {
			defer wg.Done()
			err := rm.StreamOrderbook(os.Getenv("RM_API_KEY"), crypto, func(m rm.OrderbookMarket) {
				if m.Up != nil {
					fmt.Printf("%s %s UP: mid=%.4f spread=%.4f\n", m.Crypto, m.Timeframe, m.Up.MidPrice, m.Up.Spread)
				}
			})
			log.Printf("%s stream stopped: %v", crypto, err)
		}(crypto)
	}
	wg.Wait()
}
```

---

## React Hooks

### Install

```bash
npm install swr
```

### useMarkets Hook

```tsx
import useSWR from "swr";

const API_BASE = "https://api.resolvedmarkets.com";

async function apiFetch<T>(path: string, apiKey: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "X-API-Key": apiKey },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

interface Market {
  conditionId: string;
  slug: string;
  question: string;
  category: string;
}

export function useMarkets(apiKey: string) {
  const { data, error, isLoading, mutate } = useSWR(
    apiKey ? "/v1/markets/live" : null,
    (path) => apiFetch<Market[]>(path, apiKey),
    { refreshInterval: 30_000 }
  );

  return {
    markets: data ?? [],
    isLoading,
    error,
    refresh: mutate,
  };
}
```

### useOrderbook Hook (WebSocket)

Each hook call opens one connection for one coin. To show several coins, call the hook once for each coin, up to your plan's connection limit. On code 4001 or 4003, the hook puts the server's message in `error` and does not reconnect.

```tsx
import { useEffect, useRef, useState, useCallback } from "react";

type Crypto = "BTC" | "ETH" | "SOL" | "XRP" | "DOGE" | "HYPE" | "BNB";

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
  crypto: Crypto;
  timeframe: string;
  question: string;
  up: BookSide | null;
  down: BookSide | null;
}

interface UseOrderbookReturn {
  markets: OrderbookMarket[];
  connected: boolean;
  error: string | null;
}

export function useOrderbook(
  apiKey: string,
  crypto: Crypto
): UseOrderbookReturn {
  const [markets, setMarkets] = useState<OrderbookMarket[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout>>();
  const delayRef = useRef(1000);

  const connect = useCallback(() => {
    const ws = new WebSocket("wss://api.resolvedmarkets.com/ws/orderbook");
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "auth", apiKey }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "auth" && msg.status === "ok") {
        setConnected(true);
        setError(null);
        delayRef.current = 1000;
        ws.send(JSON.stringify({ type: "subscribe", crypto }));
        return;
      }

      if (msg.type === "error") {
        setError(msg.message);
        return;
      }

      if (msg.type === "orderbook") {
        setMarkets(msg.markets);
      }
    };

    ws.onclose = (event) => {
      setConnected(false);
      if (event.code === 4001 || event.code === 4003) {
        setError((current) => current ?? `Connection refused (${event.code}): ${event.reason}`);
        return;
      }
      reconnectRef.current = setTimeout(() => {
        delayRef.current = Math.min(delayRef.current * 2, 30000);
        connect();
      }, delayRef.current);
    };

    ws.onerror = () => setError("Connection error");
  }, [apiKey, crypto]);

  useEffect(() => {
    if (!apiKey) return;
    connect();

    return () => {
      clearTimeout(reconnectRef.current);
      if (wsRef.current) wsRef.current.onclose = null;
      wsRef.current?.close();
    };
  }, [apiKey, connect]);

  return { markets, connected, error };
}
```

### Usage in a Component

```tsx
function OrderbookDashboard({ apiKey }: { apiKey: string }) {
  const { markets, isLoading } = useMarkets(apiKey);
  const { markets: books, connected, error } = useOrderbook(apiKey, "BTC");

  if (isLoading) return <div>Loading markets...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <span>{connected ? "Live" : "Disconnected"}</span>

      {books.map((book) => book.up && (
        <div key={book.marketId}>
          <h3>{book.crypto} {book.timeframe}</h3>
          <p>Mid: {book.up.midPrice.toFixed(4)}</p>
          <p>Spread: {book.up.spread.toFixed(4)}</p>
          <p>Best Bid: {book.up.bestBid} / Best Ask: {book.up.bestAsk}</p>
        </div>
      ))}

      <h2>Markets ({markets.length})</h2>
      <ul>
        {markets.map((m) => (
          <li key={m.conditionId}>{m.question}</li>
        ))}
      </ul>
    </div>
  );
}
```

---

## Next.js Server Components

Server components fetch data at request time with zero client-side JavaScript.

### Server-side Data Fetching

```tsx
// app/markets/page.tsx

const API_BASE = "https://api.resolvedmarkets.com";
const API_KEY = process.env.RM_API_KEY!;

interface Market {
  conditionId: string;
  slug: string;
  question: string;
  category: string;
}

async function getMarkets(): Promise<Market[]> {
  const res = await fetch(`${API_BASE}/v1/markets/live?crypto=BTC`, {
    headers: { "X-API-Key": API_KEY },
    next: { revalidate: 30 }, // ISR: refresh every 30s
  });

  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

async function getOrderbook(marketId: string) {
  const res = await fetch(`${API_BASE}/v1/markets/${marketId}/orderbook`, {
    headers: { "X-API-Key": API_KEY },
    cache: "no-store", // Always fresh
  });

  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export default async function MarketsPage() {
  const markets = await getMarkets();

  return (
    <div>
      <h1>Active Markets</h1>
      {markets.map((market) => (
        <MarketCard key={market.conditionId} market={market} />
      ))}
    </div>
  );
}

async function MarketCard({ market }: { market: Market }) {
  const book = await getOrderbook(market.conditionId);

  return (
    <div>
      <h2>{market.question}</h2>
      <p>Category: {market.category}</p>
      <p>UP mid: {book.up?.midPrice} | spread: {book.up?.spread}</p>
      <p>DOWN mid: {book.down?.midPrice} | spread: {book.down?.spread}</p>
    </div>
  );
}
```

### Public Stats (Static Page with ISR)

```tsx
// app/stats/page.tsx

async function getPublicStats() {
  const res = await fetch("https://api.resolvedmarkets.com/v1/public-stats", {
    next: { revalidate: 60 },
  });
  return res.json();
}

export default async function StatsPage() {
  const stats = await getPublicStats();

  return (
    <div>
      <h1>Platform Stats</h1>
      <p>Total Snapshots: {Number(stats.snapshot_count).toLocaleString()}</p>
      <p>Active Markets: {stats.active_markets}</p>
      <h2>Crypto Prices</h2>
      <ul>
        {Object.entries(stats.prices).map(([symbol, price]) => (
          <li key={symbol}>
            {symbol}: ${(price as number).toLocaleString()}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

---

## Claude Desktop / MCP

The MCP server gives Claude direct access to Resolved Markets data through natural language.

### Install

```bash
npm install -g @elcara-hq/resolvedmarkets-mcp
```

### claude_desktop_config.json

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

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

### Available Tools

The hosted endpoint has all 14 tools and 3 resources. The npm package can be behind it: version 1.1.0 has 12 tools (no `get_market_metadata`, no `get_trades`) and no `reference://catalog`.

| Tool | Description |
|------|-------------|
| `list_categories` | List all tracked categories with market counts |
| `list_markets` | List active markets, optionally filtered by category |
| `list_historical_markets` | List closed markets |
| `get_market` | Resolve a market by slug |
| `get_market_metadata` | Get market metadata and settled results |
| `get_orderbook` | Get live orderbook for a market |
| `get_market_summary` | Get aggregated market statistics |
| `get_snapshot` | Get historical snapshot at a timestamp |
| `get_latest_snapshots` | Get the 5 most recent snapshots |
| `query_snapshots` | Query historical snapshots with filters |
| `get_trades` | Get the executed trade tape of a market |
| `get_exchange_orderbook` | Get live Hyperliquid perp orderbook (Scale and above) |
| `get_exchange_snapshots` | Get historical Hyperliquid perp snapshots (Scale and above) |
| `get_system_stats` | Get platform health and stats |

### Available Resources

| URI | Description |
|-----|-------------|
| `markets://live` | All currently active markets |
| `prices://latest` | Latest crypto prices |
| `reference://catalog` | Static reference: categories, tiers, credit costs, error codes |

### Example Prompts

Once connected, you can ask Claude:

- "List all active crypto prediction markets"
- "Show me the current BTC orderbook and highlight any large orders"
- "What was the ETH spread at noon yesterday?"
- "Compare SOL and XRP market depth over the last hour"
- "Get the last 50 BTC snapshots and plot the mid-price trend"
- "Are there any markets with unusually wide spreads right now?"

---

## Cursor / Windsurf

### Cursor MCP Config

Add to `.cursor/mcp.json` in your project root (or global config at `~/.cursor/mcp.json`):

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

### Windsurf MCP Config

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

### Usage in IDE AI Chat

Once configured, your IDE's AI assistant can query market data inline:

- "Use resolved-markets to get the current BTC orderbook"
- "Query the last 20 ETH snapshots and summarize the spread trend"
- "Check if there are any active SOL markets with high liquidity"

The MCP tools integrate directly into the AI context, so you can reference market data while writing code, debugging trading strategies, or analyzing orderbook patterns.
