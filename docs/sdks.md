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
import type { RequestInit } from "node:https";

interface Market {
  conditionId: string;
  slug: string;
  question: string;
  category: string;
  tokens: { tokenId: string; side: "UP" | "DOWN" }[];
}

interface Orderbook {
  tokenId: string;
  tokenSide: "UP" | "DOWN";
  bids: { price: number; size: number }[];
  asks: { price: number; size: number }[];
  bestBid: number;
  bestAsk: number;
  midPrice: number;
  spread: number;
}

interface MarketOrderbook {
  marketId: string;
  UP: Orderbook;
  DOWN: Orderbook;
}

interface Snapshot {
  tokenId: string;
  tokenSide: "UP" | "DOWN";
  bids: { price: number; size: number }[];
  asks: { price: number; size: number }[];
  bestBid: number;
  bestAsk: number;
  midPrice: number;
  spread: number;
  timestamp: string;
}

interface PublicStats {
  snapshotCount: number;
  activeMarkets: number;
  cryptoPrices: Record<string, number>;
  timestamp: string;
}

class ResolvedMarketsClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(apiKey: string, baseUrl = "https://api.resolvedmarkets.com") {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        "X-API-Key": this.apiKey,
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`API ${res.status}: ${body}`);
    }

    return res.json() as Promise<T>;
  }

  // Public (no key required)
  async getPublicStats(): Promise<PublicStats> {
    const res = await fetch(`${this.baseUrl}/v1/public-stats`);
    return res.json() as Promise<PublicStats>;
  }

  // Authenticated endpoints
  async listMarkets(): Promise<{ markets: Market[] }> {
    return this.request("/v1/markets/live");
  }

  async getOrderbook(marketId: string): Promise<MarketOrderbook> {
    return this.request(`/v1/markets/${marketId}/orderbook`);
  }

  async getSnapshots(
    marketId: string,
    params?: { limit?: number; offset?: number }
  ): Promise<{ snapshots: Snapshot[] }> {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs}` : "";
    return this.request(`/v1/markets/${marketId}/snapshots${query}`);
  }

  async getMarketSummary(marketId: string): Promise<Record<string, unknown>> {
    return this.request(`/v1/markets/${marketId}/summary`);
  }

  async getMarketBySlug(slug: string): Promise<Market> {
    return this.request(`/v1/markets/by-slug/${slug}`);
  }
}

// Usage
const client = new ResolvedMarketsClient(process.env.RM_API_KEY!);

const { markets } = await client.listMarkets();
for (const market of markets) {
  const book = await client.getOrderbook(market.conditionId);
  console.log(`${market.slug}: spread=${book.UP.spread}`);
}
```

### WebSocket Streaming with Reconnect

```typescript
import WebSocket from "ws";

type Crypto = "BTC" | "ETH" | "SOL" | "XRP";

interface SnapshotMessage {
  type: "snapshot";
  crypto: Crypto;
  tokenSide: "UP" | "DOWN";
  bids: { price: number; size: number }[];
  asks: { price: number; size: number }[];
  bestBid: number;
  bestAsk: number;
  midPrice: number;
  spread: number;
  timestamp: string;
}

function connectOrderbook(
  apiKey: string,
  cryptos: Crypto[],
  onSnapshot: (snapshot: SnapshotMessage) => void
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
        for (const crypto of cryptos) {
          ws.send(JSON.stringify({ type: "subscribe", crypto }));
        }
        return;
      }

      if (msg.type === "auth" && msg.status !== "ok") {
        console.error("Auth failed:", msg);
        alive = false;
        ws.close();
        return;
      }

      if (msg.type === "snapshot") {
        onSnapshot(msg as SnapshotMessage);
      }
    });

    ws.on("close", (code: number) => {
      if (!alive) return;
      if (code === 4001) {
        console.error("Auth timeout — check your API key");
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
const stream = connectOrderbook(
  process.env.RM_API_KEY!,
  ["BTC", "ETH"],
  (snapshot) => {
    console.log(
      `${snapshot.crypto} ${snapshot.tokenSide}: ` +
      `mid=${snapshot.midPrice} spread=${snapshot.spread}`
    );
  }
);

// Graceful shutdown
process.on("SIGINT", () => stream.close());
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


@dataclass
class ResolvedMarketsClient:
    api_key: str
    base_url: str = "https://api.resolvedmarkets.com"

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    def _get(self, path: str, params: dict | None = None) -> dict:
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

    def list_markets(self) -> list[dict]:
        return self._get("/v1/markets/live")["markets"]

    def get_orderbook(self, market_id: str) -> dict:
        return self._get(f"/v1/markets/{market_id}/orderbook")

    def get_snapshots(
        self, market_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        return self._get(
            f"/v1/markets/{market_id}/snapshots",
            params={"limit": limit, "offset": offset},
        )["snapshots"]

    def get_market_summary(self, market_id: str) -> dict:
        return self._get(f"/v1/markets/{market_id}/summary")

    def get_market_by_slug(self, slug: str) -> dict:
        return self._get(f"/v1/markets/by-slug/{slug}")


# Usage
import os

client = ResolvedMarketsClient(api_key=os.environ["RM_API_KEY"])

markets = client.list_markets()
for m in markets:
    book = client.get_orderbook(m["conditionId"])
    print(f"{m['slug']}: spread={book['UP']['spread']}")
```

### Async WebSocket Streaming

```python
import asyncio
import json
import os
import websockets
from websockets.exceptions import ConnectionClosed


async def stream_orderbook(
    api_key: str,
    cryptos: list[str],
    on_snapshot,
    *,
    reconnect: bool = True,
):
    url = "wss://api.resolvedmarkets.com/ws/orderbook"
    delay = 1.0

    while True:
        try:
            async with websockets.connect(url) as ws:
                delay = 1.0
                await ws.send(json.dumps({"type": "auth", "apiKey": api_key}))

                auth = json.loads(await ws.recv())
                if auth.get("status") != "ok":
                    raise RuntimeError(f"Auth failed: {auth}")

                for crypto in cryptos:
                    await ws.send(json.dumps({"type": "subscribe", "crypto": crypto}))

                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("type") == "snapshot":
                        await on_snapshot(msg)

        except ConnectionClosed as e:
            if e.code == 4001:
                raise RuntimeError("Auth timeout — check your API key") from e
            if not reconnect:
                raise
            print(f"Disconnected ({e.code}), reconnecting in {delay}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)

        except Exception as e:
            if not reconnect:
                raise
            print(f"Error: {e}, reconnecting in {delay}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)


# Usage
async def handle_snapshot(snapshot: dict):
    print(
        f"{snapshot['crypto']} {snapshot['tokenSide']}: "
        f"mid={snapshot['midPrice']} spread={snapshot['spread']}"
    )


asyncio.run(
    stream_orderbook(
        api_key=os.environ["RM_API_KEY"],
        cryptos=["BTC", "ETH"],
        on_snapshot=handle_snapshot,
    )
)
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
	ConditionID string  `json:"conditionId"`
	Slug        string  `json:"slug"`
	Question    string  `json:"question"`
	Category    string  `json:"category"`
}

type OrderLevel struct {
	Price float64 `json:"price"`
	Size  float64 `json:"size"`
}

type Orderbook struct {
	TokenID   string       `json:"tokenId"`
	TokenSide string       `json:"tokenSide"`
	Bids      []OrderLevel `json:"bids"`
	Asks      []OrderLevel `json:"asks"`
	BestBid   float64      `json:"bestBid"`
	BestAsk   float64      `json:"bestAsk"`
	MidPrice  float64      `json:"midPrice"`
	Spread    float64      `json:"spread"`
}

type MarketOrderbook struct {
	MarketID string    `json:"marketId"`
	UP       Orderbook `json:"UP"`
	DOWN     Orderbook `json:"DOWN"`
}

func (c *Client) doGet(path string, result interface{}) error {
	req, err := http.NewRequest("GET", c.BaseURL+path, nil)
	if err != nil {
		return err
	}
	req.Header.Set("X-API-Key", c.APIKey)
	req.Header.Set("Content-Type", "application/json")

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

func (c *Client) ListMarkets() ([]Market, error) {
	var resp struct {
		Markets []Market `json:"markets"`
	}
	if err := c.doGet("/v1/markets/live", &resp); err != nil {
		return nil, err
	}
	return resp.Markets, nil
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

```go
package resolvedmarkets

import (
	"encoding/json"
	"fmt"
	"log"
	"math"
	"time"

	"github.com/gorilla/websocket"
)

type Snapshot struct {
	Type      string       `json:"type"`
	Crypto    string       `json:"crypto"`
	TokenSide string       `json:"tokenSide"`
	Bids      []OrderLevel `json:"bids"`
	Asks      []OrderLevel `json:"asks"`
	BestBid   float64      `json:"bestBid"`
	BestAsk   float64      `json:"bestAsk"`
	MidPrice  float64      `json:"midPrice"`
	Spread    float64      `json:"spread"`
	Timestamp string       `json:"timestamp"`
}

func StreamOrderbook(apiKey string, cryptos []string, onSnapshot func(Snapshot)) error {
	url := "wss://api.resolvedmarkets.com/ws/orderbook"
	delay := time.Second

	for {
		err := connectAndStream(url, apiKey, cryptos, onSnapshot)
		if err != nil {
			log.Printf("Disconnected: %v, reconnecting in %v", err, delay)
			time.Sleep(delay)
			delay = time.Duration(math.Min(float64(delay*2), float64(30*time.Second)))
			continue
		}
		return nil
	}
}

func connectAndStream(url, apiKey string, cryptos []string, onSnapshot func(Snapshot)) error {
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

	var authResp map[string]string
	if err := conn.ReadJSON(&authResp); err != nil {
		return fmt.Errorf("auth read: %w", err)
	}
	if authResp["status"] != "ok" {
		return fmt.Errorf("auth failed: %v", authResp)
	}

	// Subscribe
	for _, crypto := range cryptos {
		sub := map[string]string{"type": "subscribe", "crypto": crypto}
		if err := conn.WriteJSON(sub); err != nil {
			return fmt.Errorf("subscribe: %w", err)
		}
	}

	// Read loop
	for {
		_, raw, err := conn.ReadMessage()
		if err != nil {
			return fmt.Errorf("read: %w", err)
		}

		var msg struct {
			Type string `json:"type"`
		}
		if err := json.Unmarshal(raw, &msg); err != nil {
			continue
		}

		if msg.Type == "snapshot" {
			var snap Snapshot
			if err := json.Unmarshal(raw, &snap); err != nil {
				log.Printf("decode snapshot: %v", err)
				continue
			}
			onSnapshot(snap)
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
	"os"

	rm "your-module/resolvedmarkets"
)

func main() {
	client := rm.NewClient(os.Getenv("RM_API_KEY"))

	// REST
	markets, err := client.ListMarkets()
	if err != nil {
		log.Fatal(err)
	}
	for _, m := range markets {
		book, _ := client.GetOrderbook(m.ConditionID)
		fmt.Printf("%s: spread=%.4f\n", m.Slug, book.UP.Spread)
	}

	// WebSocket
	rm.StreamOrderbook(os.Getenv("RM_API_KEY"), []string{"BTC", "ETH"}, func(s rm.Snapshot) {
		fmt.Printf("%s %s: mid=%.4f spread=%.4f\n", s.Crypto, s.TokenSide, s.MidPrice, s.Spread)
	})
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
    (path) => apiFetch<{ markets: Market[] }>(path, apiKey),
    { refreshInterval: 30_000 }
  );

  return {
    markets: data?.markets ?? [],
    isLoading,
    error,
    refresh: mutate,
  };
}
```

### useOrderbook Hook (WebSocket)

```tsx
import { useEffect, useRef, useState, useCallback } from "react";

type Crypto = "BTC" | "ETH" | "SOL" | "XRP";

interface OrderbookState {
  bids: { price: number; size: number }[];
  asks: { price: number; size: number }[];
  bestBid: number;
  bestAsk: number;
  midPrice: number;
  spread: number;
  tokenSide: string;
  timestamp: string;
}

interface UseOrderbookReturn {
  snapshots: Record<string, OrderbookState>;
  connected: boolean;
  error: string | null;
}

export function useOrderbook(
  apiKey: string,
  cryptos: Crypto[]
): UseOrderbookReturn {
  const [snapshots, setSnapshots] = useState<Record<string, OrderbookState>>({});
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

      if (msg.type === "auth") {
        if (msg.status === "ok") {
          setConnected(true);
          setError(null);
          delayRef.current = 1000;
          for (const crypto of cryptos) {
            ws.send(JSON.stringify({ type: "subscribe", crypto }));
          }
        } else {
          setError("Authentication failed");
        }
        return;
      }

      if (msg.type === "snapshot") {
        const key = `${msg.crypto}-${msg.tokenSide}`;
        setSnapshots((prev) => ({ ...prev, [key]: msg }));
      }
    };

    ws.onclose = (event) => {
      setConnected(false);
      if (event.code === 4001) {
        setError("Auth timeout — check API key");
        return;
      }
      reconnectRef.current = setTimeout(() => {
        delayRef.current = Math.min(delayRef.current * 2, 30000);
        connect();
      }, delayRef.current);
    };

    ws.onerror = () => setError("Connection error");
  }, [apiKey, cryptos]);

  useEffect(() => {
    if (!apiKey) return;
    connect();

    return () => {
      clearTimeout(reconnectRef.current);
      wsRef.current?.close();
    };
  }, [apiKey, connect]);

  return { snapshots, connected, error };
}
```

### Usage in a Component

```tsx
function OrderbookDashboard({ apiKey }: { apiKey: string }) {
  const { markets, isLoading } = useMarkets(apiKey);
  const { snapshots, connected, error } = useOrderbook(apiKey, ["BTC", "ETH"]);

  if (isLoading) return <div>Loading markets...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <span>{connected ? "Live" : "Disconnected"}</span>

      {Object.entries(snapshots).map(([key, book]) => (
        <div key={key}>
          <h3>{key}</h3>
          <p>Mid: {book.midPrice.toFixed(4)}</p>
          <p>Spread: {book.spread.toFixed(4)}</p>
          <p>Best Bid: {book.bestBid} / Best Ask: {book.bestAsk}</p>
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
  const res = await fetch(`${API_BASE}/v1/markets/live`, {
    headers: { "X-API-Key": API_KEY },
    next: { revalidate: 30 }, // ISR: refresh every 30s
  });

  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = await res.json();
  return data.markets;
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
      <p>UP mid: {book.UP.midPrice} | spread: {book.UP.spread}</p>
      <p>DOWN mid: {book.DOWN.midPrice} | spread: {book.DOWN.spread}</p>
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
      <p>Total Snapshots: {stats.snapshotCount.toLocaleString()}</p>
      <p>Active Markets: {stats.activeMarkets}</p>
      <h2>Crypto Prices</h2>
      <ul>
        {Object.entries(stats.cryptoPrices).map(([symbol, price]) => (
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
npm install -g @resolvedmarkets/mcp-server
```

### claude_desktop_config.json

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "resolved-markets": {
      "command": "npx",
      "args": ["-y", "@resolvedmarkets/mcp-server"],
      "env": {
        "HF_API_URL": "https://api.resolvedmarkets.com",
        "HF_API_KEY": "rm_your_key"
      }
    }
  }
}
```

### Available Tools

| Tool | Description |
|------|-------------|
| `list_markets` | List active markets, optionally filtered by category |
| `get_orderbook` | Get live orderbook for a market |
| `get_snapshot` | Get historical snapshot at a specific timestamp |
| `query_snapshots` | Query historical snapshots with filters |
| `get_market_summary` | Get aggregated market statistics |
| `get_system_stats` | Get platform health and stats |

### Available Resources

| URI | Description |
|-----|-------------|
| `markets://live` | All currently active markets |
| `prices://latest` | Latest crypto prices |

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
      "args": ["-y", "@resolvedmarkets/mcp-server"],
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
      "args": ["-y", "@resolvedmarkets/mcp-server"],
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
