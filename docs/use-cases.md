# Use Cases

Real-world applications built on the Resolved Markets API. Each section includes a description, architectural approach, and a working code sketch to get you started.

---

## Market Making Simulation

Backtest market-making strategies by replaying historical orderbook snapshots. The API captures up to 10 snapshots a second for each orderbook (one every 100 ms) on crypto up/down markets. Other categories get at most one snapshot every 500 ms to 5 seconds for each orderbook. This gives you the granularity needed to simulate realistic order placement, fill probability estimation, and inventory risk tracking without risking capital on a live market.

**Approach:** Fetch paginated historical snapshots for a given market and time range using `GET /v1/markets/:id/snapshots` with `order=asc`. The rows are in `data` and use snake_case keys. Iterate through them chronologically, simulating passive limit orders at each step. For each snapshot, check whether your resting orders would have been filled based on the best bid/ask crossing your price. Track PnL, inventory exposure, and fill rates over time.

```python
import requests
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

API_URL = "https://api.resolvedmarkets.com"
API_KEY = "rm_your_key"
HEADERS = {"X-API-Key": API_KEY}


@dataclass
class MarketMakerSim:
    spread_target: float = 0.02   # how wide to quote around mid
    order_size: float = 100.0
    inventory: float = 0.0
    pnl: float = 0.0
    fills: list = field(default_factory=list)

    def quote(self, mid_price: float) -> tuple[float, float]:
        """Generate bid/ask quotes around the mid price."""
        half = self.spread_target / 2
        # Skew quotes based on inventory to reduce risk
        skew = -0.001 * self.inventory
        bid = mid_price - half + skew
        ask = mid_price + half + skew
        return round(bid, 4), round(ask, 4)

    def check_fills(self, my_bid: float, my_ask: float, snapshot: dict):
        """Check if the market would have filled our orders."""
        best_ask = snapshot["best_ask"]
        best_bid = snapshot["best_bid"]

        # Our bid gets filled if market's best ask drops to our bid
        if best_ask <= my_bid:
            self.inventory += self.order_size
            self.pnl -= my_bid * self.order_size
            self.fills.append(("BUY", my_bid, snapshot["timestamp"]))

        # Our ask gets filled if market's best bid rises to our ask
        if best_bid >= my_ask:
            self.inventory -= self.order_size
            self.pnl += my_ask * self.order_size
            self.fills.append(("SELL", my_ask, snapshot["timestamp"]))


def fetch_snapshots(market_id: str, from_ts: str, to_ts: str, side: str = "UP"):
    """Paginate through all snapshots in the time range."""
    offset = 0
    limit = 1000
    while True:
        resp = requests.get(
            f"{API_URL}/v1/markets/{market_id}/snapshots",
            headers=HEADERS,
            params={
                "from": from_ts, "to": to_ts,
                "side": side, "order": "asc",
                "limit": limit, "offset": offset,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        snapshots = data["data"]
        if not snapshots:
            break
        yield from snapshots
        offset += limit
        if offset >= data["total"]:
            break


def run_backtest(market_id: str, from_ts: str, to_ts: str):
    sim = MarketMakerSim(spread_target=0.02)

    for snap in fetch_snapshots(market_id, from_ts, to_ts):
        mid = snap["mid_price"]
        my_bid, my_ask = sim.quote(mid)
        sim.check_fills(my_bid, my_ask, snap)

    print(f"Total fills: {len(sim.fills)}")
    print(f"Final inventory: {sim.inventory}")
    print(f"PnL: {sim.pnl:.4f}")
    print(f"Inventory risk (abs): {abs(sim.inventory) * sim.fills[-1][1] if sim.fills else 0:.2f}")


# Example: backtest on a BTC market over 1 hour
now = datetime.now(timezone.utc)
run_backtest(
    "0x1234abcd...",
    (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    now.strftime("%Y-%m-%dT%H:%M:%SZ"),
)
```

---

## Liquidity Monitoring Dashboard

A live dashboard that tracks bid/ask depth, spread trends, and liquidity imbalances, updated every 2 seconds. Useful for traders who need to see at a glance where liquidity is concentrating or thinning out, and for market operators monitoring platform health.

**Approach:** Connect to the WebSocket endpoint at `wss://api.resolvedmarkets.com/ws/orderbook` with one connection for each crypto, because each connection follows one coin. On each `orderbook` message (every 2 seconds), update in-memory state and render depth bars, spread sparklines, and a bid/ask imbalance ratio. Use `GET /v1/markets/live` on page load to populate the market list.

The example opens 7 connections, one for each coin. Only Enterprise (10 connections) allows 7; on Pro (1) or Scale (5), list fewer coins in `CRYPTOS`. It shows the live 5m up/down market of each coin. A coin has several 5m markets at the same time: the live window and upcoming windows. The example reads the `endDate` of each market from the `markets` message and shows the 5m market with the earliest `endDate` in the future.

```jsx
import { useEffect, useState } from "react";

const API_URL = "https://api.resolvedmarkets.com";
const WS_URL = "wss://api.resolvedmarkets.com/ws/orderbook";
const API_KEY = "rm_your_key";
const CRYPTOS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "HYPE", "BNB"];
const TIMEFRAME = "5m";

function sideStats(side) {
  return {
    bestBid: side.bestBid,
    bestAsk: side.bestAsk,
    spread: side.spread,
    midPrice: side.midPrice,
    bidDepth: side.bidDepth,
    askDepth: side.askDepth,
    updatedAt: side.timestamp,
  };
}

function useOrderbookStream(apiKey) {
  const [books, setBooks] = useState({});

  useEffect(() => {
    const sockets = CRYPTOS.map((crypto) => {
      const ws = new WebSocket(WS_URL);
      const endDates = new Map();

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "auth", apiKey }));
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        if (msg.type === "auth" && msg.status === "ok") {
          ws.send(JSON.stringify({ type: "subscribe", crypto }));
        }

        if (msg.type === "markets") {
          for (const m of msg.data) endDates.set(m.conditionId, new Date(m.endDate).getTime());
        }

        if (msg.type === "orderbook") {
          const now = Date.now();
          const market = msg.markets
            .filter((m) => m.timeframe === TIMEFRAME && endDates.get(m.marketId) > now)
            .sort((a, b) => endDates.get(a.marketId) - endDates.get(b.marketId))[0];
          if (!market || !market.up || !market.down) return;
          setBooks((prev) => ({
            ...prev,
            [`${crypto}_UP`]: sideStats(market.up),
            [`${crypto}_DOWN`]: sideStats(market.down),
          }));
        }
      };

      return ws;
    });

    return () => sockets.forEach((ws) => ws.close());
  }, [apiKey]);

  return books;
}

function LiquidityCard({ label, data }) {
  if (!data) return <div className="card loading">{label}: waiting...</div>;

  const imbalance = data.bidDepth / (data.bidDepth + data.askDepth);
  const imbalancePct = (imbalance * 100).toFixed(1);
  const isSkewed = imbalance > 0.65 || imbalance < 0.35;

  return (
    <div className={`card ${isSkewed ? "alert" : ""}`}>
      <h3>{label}</h3>
      <div className="metric">
        <span>Spread:</span> <strong>{(data.spread * 100).toFixed(2)}%</strong>
      </div>
      <div className="metric">
        <span>Mid:</span> <strong>{data.midPrice.toFixed(4)}</strong>
      </div>
      <div className="depth-bar">
        <div className="bid-bar" style={{ width: `${imbalancePct}%` }} />
        <div className="ask-bar" style={{ width: `${100 - imbalancePct}%` }} />
      </div>
      <div className="metric">
        <span>Bid depth:</span> {data.bidDepth.toLocaleString()}
        {" | "}
        <span>Ask depth:</span> {data.askDepth.toLocaleString()}
      </div>
      {isSkewed && <div className="warning">Liquidity imbalance: {imbalancePct}% bid-heavy</div>}
    </div>
  );
}

export default function LiquidityDashboard() {
  const books = useOrderbookStream(API_KEY);

  return (
    <div className="dashboard-grid">
      {CRYPTOS.map((crypto) =>
        ["UP", "DOWN"].map((side) => (
          <LiquidityCard
            key={`${crypto}_${side}`}
            label={`${crypto} ${side}`}
            data={books[`${crypto}_${side}`]}
          />
        ))
      )}
    </div>
  );
}
```

---

## Cross-Token Arbitrage Detection

On Polymarket, every market has an UP token and a DOWN token whose prices should sum to approximately 1.00. When the sum deviates significantly (e.g., > 1.02 or < 0.98), there is a potential arbitrage opportunity: buy the underpriced side, or sell both when the sum exceeds 1.00. This use case monitors that spread.

**Approach:** Poll `GET /v1/markets/live` to list the live markets. It returns an array of markets with no prices, so read the orderbook of each market with `GET /v1/markets/:id/orderbook`, compute `up.midPrice + down.midPrice` and flag deviations. Each orderbook request costs 1 credit and counts against your requests per minute, so filter the list (here by `crypto` and `timeframe`) and poll no more often than your plan allows. On 2026-11-11 the BTC 5m list held 4 markets, so one scan cost 5 credits with the list request. One scan every 60 seconds then uses 7,200 credits a day. Free includes 5,000 credits a month and Pro 50,000. The monitor waits for `Retry-After` on a 429 and stops on a 401 or 402. It skips a market on a network error or any other status. To check every 2 seconds, use the WebSocket stream: each `orderbook` message holds both token books of each market of one coin.

```python
import requests
import time
from datetime import datetime

API_URL = "https://api.resolvedmarkets.com"
API_KEY = "rm_your_key"
HEADERS = {"X-API-Key": API_KEY}

# Threshold: flag when UP + DOWN deviates from 1.00 by more than this
DEVIATION_THRESHOLD = 0.015


def get_json(path: str, params: dict | None = None):
    while True:
        try:
            resp = requests.get(f"{API_URL}{path}", headers=HEADERS, params=params, timeout=30)
        except requests.RequestException as e:
            print(f"Network error on {path}: {e}")
            return None
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", 60)))
            continue
        if resp.status_code in (401, 402):
            resp.raise_for_status()
        if not resp.ok:
            print(f"API {resp.status_code} on {path}, skipped")
            return None
        return resp.json()


def fetch_live_markets(crypto: str, timeframe: str) -> list[dict]:
    return get_json("/v1/markets/live", {"crypto": crypto, "timeframe": timeframe}) or []


def fetch_orderbook(condition_id: str) -> dict | None:
    return get_json(f"/v1/markets/{condition_id}/orderbook")


def check_arbitrage(markets: list[dict]) -> list[dict]:
    opportunities = []

    for market in markets:
        book = fetch_orderbook(market["conditionId"])
        if not book or not book["up"] or not book["down"]:
            continue
        up, down = book["up"], book["down"]

        price_sum = up["midPrice"] + down["midPrice"]
        deviation = abs(price_sum - 1.0)

        if deviation > DEVIATION_THRESHOLD:
            opportunities.append({
                "market": market["question"],
                "conditionId": market["conditionId"],
                "up_price": up["midPrice"],
                "down_price": down["midPrice"],
                "sum": round(price_sum, 4),
                "deviation": round(deviation, 4),
                "direction": "overpriced" if price_sum > 1.0 else "underpriced",
                "up_bid_depth": up["bidDepth"],
                "down_bid_depth": down["bidDepth"],
            })

    return sorted(opportunities, key=lambda x: x["deviation"], reverse=True)


def monitor(interval_sec: int = 60, crypto: str = "BTC", timeframe: str = "5m"):
    """Continuously monitor for arbitrage opportunities."""
    print(f"Monitoring for UP+DOWN deviations > {DEVIATION_THRESHOLD}...")

    while True:
        markets = fetch_live_markets(crypto, timeframe)
        opps = check_arbitrage(markets)

        if opps:
            print(f"\n[{datetime.now().isoformat()}] Found {len(opps)} opportunities:")
            for opp in opps:
                print(f"  {opp['market']}")
                print(f"    UP={opp['up_price']} + DOWN={opp['down_price']} = {opp['sum']}")
                print(f"    Deviation: {opp['deviation']} ({opp['direction']})")
                print(f"    Liquidity: bid_depth UP={opp['up_bid_depth']:.0f} DOWN={opp['down_bid_depth']:.0f}")
        else:
            print(".", end="", flush=True)

        time.sleep(interval_sec)


if __name__ == "__main__":
    monitor()
```

---

## AI Agent Trading Signals

Use the MCP (Model Context Protocol) server to let Claude or other AI agents analyze live orderbook data and generate trading signals. The hosted MCP server exposes 14 tools that agents can call directly -- no REST client code needed. The agent can reason about spread dynamics, depth imbalances, and cross-market correlations using natural language.

**Approach:** Configure the MCP server in Claude Desktop or Claude Code, then use conversational prompts to query live market data. The agent calls `list_markets`, `get_orderbook`, and `get_market_summary` tools under the hood and synthesizes the results into actionable analysis.

**Claude Desktop MCP configuration:**

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

**Example prompts for the agent:**

```
Prompt 1 - Spread Analysis:
"List all active crypto markets. For each one, get the orderbook and tell me
which market currently has the tightest spread. Flag any market where the
spread is wider than 3%."

Prompt 2 - Liquidity Imbalance Detection:
"Get the orderbook for the BTC 1-hour market. Compare total bid depth vs
total ask depth. If the imbalance exceeds 60/40, explain what that might
indicate about market sentiment."

Prompt 3 - Cross-Market Momentum:
"Get market summaries for all active BTC up/down markets (5m, 15m, 1h, 4h, 1d).
Compare the average mid prices across timeframes. Are shorter timeframes
pricing higher or lower than longer ones? What does the term structure
suggest about near-term directional bias?"

Prompt 4 - Automated Signal Generation:
"Analyze the SOL market: check the orderbook for liquidity, the summary
for recent spread trends, and the current UP/DOWN token prices. Based on
the depth imbalance, spread compression/expansion, and price level, give
me a signal: LONG, SHORT, or NEUTRAL, with a confidence level and
one-sentence rationale."
```

**What the agent does under the hood:**

1. Calls `list_markets` with category filter to enumerate active markets
2. Calls `get_orderbook` for each market of interest
3. Calls `get_market_summary` for historical context (avg spread, price range)
4. Reasons across all data to produce a synthesized signal

The MCP server handles authentication, rate limiting, and data formatting -- the agent interacts purely through structured tool calls.

---

## Academic Research Data Export

Bulk export historical orderbook data for academic research on prediction markets. Study spread dynamics, market microstructure, price discovery efficiency, and how prediction market prices converge to outcomes as expiration approaches. Snapshots are event-driven. Crypto up/down markets get up to 10 snapshots a second for each orderbook (one every 100 ms). Other categories get at most one snapshot every 500 ms to 5 seconds for each orderbook.

**Approach:** Use the paginated `GET /v1/markets/:id/snapshots` endpoint with `order=asc` to download all snapshots for a market over a given period. `includebook=true` adds the `bids` and `asks` levels to each row (then `limit` can be at most 2000). Load them into a pandas DataFrame for analysis. Export to Parquet or CSV for use in R, Stata, or other research tools.

```python
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

API_URL = "https://api.resolvedmarkets.com"
API_KEY = "rm_your_key"
HEADERS = {"X-API-Key": API_KEY}


def export_snapshots(
    market_id: str,
    from_ts: str,
    to_ts: str,
    side: str = "UP",
) -> pd.DataFrame:
    """Download all snapshots for a market and return as a DataFrame."""
    all_snapshots = []
    offset = 0
    limit = 1000

    while True:
        resp = requests.get(
            f"{API_URL}/v1/markets/{market_id}/snapshots",
            headers=HEADERS,
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
        snapshots = data["data"]

        if not snapshots:
            break

        all_snapshots.extend(snapshots)
        print(f"  Fetched {len(all_snapshots)} / {data['total']} snapshots")

        offset += limit
        if offset >= data["total"]:
            break

    if not all_snapshots:
        return pd.DataFrame()

    # Flatten into tabular format
    rows = []
    for snap in all_snapshots:
        rows.append({
            "event_timestamp": snap["event_timestamp"],
            "capture_timestamp": snap["capture_timestamp"],
            "token_side": snap["token_side"],
            "best_bid": snap["best_bid"],
            "best_ask": snap["best_ask"],
            "mid_price": snap["mid_price"],
            "spread": snap["spread"],
            "bid_depth_total": snap["bid_depth_total"],
            "ask_depth_total": snap["ask_depth_total"],
            "sequence_number": snap["sequence_number"],
            "bid_levels": len(snap["bids"]),
            "ask_levels": len(snap["asks"]),
            # Top-of-book detail
            "bid_1_price": snap["bids"][0]["price"] if snap["bids"] else None,
            "bid_1_size": snap["bids"][0]["size"] if snap["bids"] else None,
            "ask_1_price": snap["asks"][0]["price"] if snap["asks"] else None,
            "ask_1_size": snap["asks"][0]["size"] if snap["asks"] else None,
        })

    df = pd.DataFrame(rows)
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])
    df["capture_timestamp"] = pd.to_datetime(df["capture_timestamp"])
    df["capture_latency_ms"] = (
        df["capture_timestamp"] - df["event_timestamp"]
    ).dt.total_seconds() * 1000

    return df


def analyze_spread_dynamics(df: pd.DataFrame):
    """Basic spread analysis for a research paper."""
    print("=== Spread Dynamics ===")
    print(f"Observations: {len(df):,}")
    print(f"Time range: {df['event_timestamp'].min()} to {df['event_timestamp'].max()}")
    print(f"Mean spread: {df['spread'].mean():.6f}")
    print(f"Median spread: {df['spread'].median():.6f}")
    print(f"Std dev: {df['spread'].std():.6f}")
    print(f"Min: {df['spread'].min():.6f}, Max: {df['spread'].max():.6f}")

    # Spread by hour of day
    df["hour"] = df["event_timestamp"].dt.hour
    hourly = df.groupby("hour")["spread"].mean()
    print("\nMean spread by hour (UTC):")
    for hour, spread in hourly.items():
        print(f"  {hour:02d}:00 - {spread:.6f}")

    # Capture latency stats
    print(f"\nCapture latency (ms): mean={df['capture_latency_ms'].mean():.1f}, "
          f"p99={df['capture_latency_ms'].quantile(0.99):.1f}")


# Example: export 24 hours of BTC UP token snapshots
market_id = "0x1234abcd..."
now = datetime.now(timezone.utc)
df = export_snapshots(
    market_id,
    (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    now.strftime("%Y-%m-%dT%H:%M:%SZ"),
)

if not df.empty:
    analyze_spread_dynamics(df)

    # Export for use in other tools
    df.to_parquet("btc_up_snapshots_24h.parquet", index=False)
    print(f"\nExported {len(df):,} rows to Parquet")

    # Also export a sampled version (1 snapshot per second) for lighter analysis
    df_sampled = df.set_index("event_timestamp").resample("1s").first().dropna().reset_index()
    df_sampled.to_csv("btc_up_snapshots_1s_24h.csv", index=False)
    print(f"Exported {len(df_sampled):,} sampled rows to CSV")
```

---

## Prediction Market Analytics

Build aggregate analytics across all market categories to answer questions like: which category has the tightest spreads, deepest liquidity, and most active trading? Useful for platform operators, researchers comparing market microstructure across domains, and traders looking for the most efficient markets to participate in.

**Approach:** Fetch all active markets via `GET /v1/markets/live`, then call `GET /v1/markets/:id/summary` for each market to get aggregated statistics. Group results by category and compute cross-market metrics.

```python
import requests
from collections import defaultdict
from statistics import mean, median

API_URL = "https://api.resolvedmarkets.com"
API_KEY = "rm_your_key"
HEADERS = {"X-API-Key": API_KEY}


def fetch_all_summaries() -> list[dict]:
    """Fetch live markets and their summaries."""
    resp = requests.get(f"{API_URL}/v1/markets/live", headers=HEADERS)
    resp.raise_for_status()
    markets = resp.json()

    results = []
    for market in markets:
        cid = market["conditionId"]
        try:
            summary_resp = requests.get(
                f"{API_URL}/v1/markets/{cid}/summary",
                headers=HEADERS,
            )
            summary_resp.raise_for_status()
            summary = summary_resp.json()
            if not summary["snapshot_count"]:
                continue
            summary["category"] = market["category"]
            summary["question"] = market["question"]
            results.append(summary)
        except requests.RequestException as e:
            print(f"  Skipping {cid}: {e}")

    return results


def analyze_by_category(summaries: list[dict]):
    """Group markets by category and compare metrics."""
    by_cat = defaultdict(list)
    for s in summaries:
        by_cat[s["category"]].append(s)

    print(f"{'Category':<12} {'Markets':>7} {'Avg Spread':>11} {'Med Spread':>11} "
          f"{'Avg Depth':>12} {'Snapshots':>12}")
    print("-" * 75)

    rankings = []
    for cat, markets in sorted(by_cat.items()):
        spreads = [m["avg_spread"] for m in markets]
        depths = [m["avg_bid_depth"] + m["avg_ask_depth"] for m in markets]
        snap_counts = [m["snapshot_count"] for m in markets]

        avg_spread = mean(spreads)
        med_spread = median(spreads)
        avg_depth = mean(depths)
        total_snaps = sum(snap_counts)

        print(f"{cat:<12} {len(markets):>7} {avg_spread:>11.4f} {med_spread:>11.4f} "
              f"{avg_depth:>12,.0f} {total_snaps:>12,}")

        rankings.append({
            "category": cat,
            "market_count": len(markets),
            "avg_spread": avg_spread,
            "avg_depth": avg_depth,
            "total_snapshots": total_snaps,
        })

    # Find best category for each metric
    print("\n=== Rankings ===")
    tightest = min(rankings, key=lambda r: r["avg_spread"])
    deepest = max(rankings, key=lambda r: r["avg_depth"])
    most_active = max(rankings, key=lambda r: r["total_snapshots"])
    print(f"Tightest spreads:   {tightest['category']} ({tightest['avg_spread']:.4f})")
    print(f"Deepest liquidity:  {deepest['category']} ({deepest['avg_depth']:,.0f})")
    print(f"Most data:          {most_active['category']} ({most_active['total_snapshots']:,} snapshots)")

    return rankings


def find_outlier_markets(summaries: list[dict]):
    """Find markets with unusually wide or tight spreads."""
    spreads = [s["avg_spread"] for s in summaries]
    global_mean = mean(spreads)

    print("\n=== Outlier Markets ===")
    print(f"Global average spread: {global_mean:.4f}\n")

    wide = [s for s in summaries if s["avg_spread"] > global_mean * 2]
    tight = [s for s in summaries if s["avg_spread"] < global_mean * 0.5]

    if wide:
        print("Unusually WIDE spreads (>2x average):")
        for s in sorted(wide, key=lambda x: x["avg_spread"], reverse=True):
            print(f"  {s['avg_spread']:.4f} - [{s['category']}] {s['question']}")

    if tight:
        print("\nUnusually TIGHT spreads (<0.5x average):")
        for s in sorted(tight, key=lambda x: x["avg_spread"]):
            print(f"  {s['avg_spread']:.4f} - [{s['category']}] {s['question']}")


summaries = fetch_all_summaries()
rankings = analyze_by_category(summaries)
find_outlier_markets(summaries)
```

---

## Weather Market Correlation Analysis

Compare weather prediction market prices with actual weather data to study prediction accuracy. Polymarket hosts weather markets (e.g., "Will NYC temperature exceed 90F this week?"), and this use case tracks how the market-implied probability evolves relative to observed and forecast conditions. Useful for evaluating whether prediction markets are well-calibrated for weather events.

**Approach:** Fetch weather-category markets via `GET /v1/markets/live?category=weather`, then use `GET /v1/markets/:id/snapshots` to track how the UP token mid-price (the implied probability of "Yes") changes over time. Weather markets need the Scale or Enterprise plan. Pair this with an external weather API (e.g., Open-Meteo, free and no API key required) to overlay actual observations. Compute a calibration curve: when the market says 70% probability, does the event happen ~70% of the time?

```python
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

API_URL = "https://api.resolvedmarkets.com"
API_KEY = "rm_your_key"
HEADERS = {"X-API-Key": API_KEY}

# Open-Meteo API (free, no key required)
WEATHER_API = "https://api.open-meteo.com/v1/forecast"


def fetch_weather_markets() -> list[dict]:
    """Get all active weather prediction markets."""
    resp = requests.get(
        f"{API_URL}/v1/markets/live",
        headers=HEADERS,
        params={"category": "weather"},
    )
    resp.raise_for_status()
    return resp.json()


def fetch_market_probability_series(market_id: str, hours: int = 48) -> pd.DataFrame:
    """Get the UP token mid-price over time (= implied probability)."""
    now = datetime.now(timezone.utc)
    to_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    from_ts = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    all_snaps = []
    offset = 0
    while True:
        resp = requests.get(
            f"{API_URL}/v1/markets/{market_id}/snapshots",
            headers=HEADERS,
            params={
                "from": from_ts, "to": to_ts,
                "side": "UP", "order": "asc",
                "limit": 1000, "offset": offset,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not data["data"]:
            break
        all_snaps.extend(data["data"])
        offset += 1000
        if offset >= data["total"]:
            break

    df = pd.DataFrame(all_snaps)
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    # Resample to 1-minute intervals for manageable size
    df = df.set_index("timestamp").resample("1min")["mid_price"].mean().dropna().reset_index()
    df.columns = ["timestamp", "implied_probability"]
    return df


def fetch_actual_temperature(lat: float, lon: float, days: int = 3) -> pd.DataFrame:
    """Fetch hourly temperature observations from Open-Meteo."""
    resp = requests.get(WEATHER_API, params={
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m",
        "temperature_unit": "fahrenheit",
        "past_days": days,
        "forecast_days": 1,
    })
    resp.raise_for_status()
    data = resp.json()

    df = pd.DataFrame({
        "timestamp": pd.to_datetime(data["hourly"]["time"]),
        "temperature_f": data["hourly"]["temperature_2m"],
    })
    return df


def correlation_analysis(market_id: str, lat: float, lon: float, threshold_f: float):
    """
    Compare market-implied probability with actual temperature.
    Example: for a "Will NYC temp exceed 90F?" market.
    """
    print(f"Fetching market probability series for {market_id}...")
    prob_df = fetch_market_probability_series(market_id, hours=72)

    print(f"Fetching actual temperature for ({lat}, {lon})...")
    temp_df = fetch_actual_temperature(lat, lon, days=3)

    if prob_df.empty:
        print("No market data available.")
        return

    # Merge on nearest hour
    prob_df["hour"] = prob_df["timestamp"].dt.floor("h")
    temp_df["hour"] = temp_df["timestamp"].dt.floor("h")

    merged = pd.merge(prob_df, temp_df, on="hour", how="inner", suffixes=("_market", "_weather"))

    if merged.empty:
        print("No overlapping timestamps.")
        return

    # Add column: is the actual temp above the threshold right now?
    merged["above_threshold"] = merged["temperature_f"] > threshold_f

    # How does the market price respond to temperature changes?
    print(f"\n=== Correlation Analysis ===")
    print(f"Threshold: {threshold_f}F")
    print(f"Data points: {len(merged)}")

    above = merged[merged["above_threshold"]]
    below = merged[~merged["above_threshold"]]
    print(f"When temp > {threshold_f}F: avg implied prob = "
          f"{above['implied_probability'].mean():.3f} (n={len(above)})")
    print(f"When temp < {threshold_f}F: avg implied prob = "
          f"{below['implied_probability'].mean():.3f} (n={len(below)})")

    corr = merged["temperature_f"].corr(merged["implied_probability"])
    print(f"Pearson correlation (temp vs market prob): {corr:.3f}")

    # Export for further analysis
    merged.to_csv(f"weather_correlation_{market_id[:8]}.csv", index=False)
    print(f"\nExported {len(merged)} rows to CSV")


# Example: NYC temperature market
# Replace with actual conditionId from the weather markets list
weather_markets = fetch_weather_markets()
for m in weather_markets:
    print(f"  {m['conditionId'][:12]}... - {m['question']}")

# Run analysis on first weather market found (adjust lat/lon/threshold as needed)
if weather_markets:
    correlation_analysis(
        market_id=weather_markets[0]["conditionId"],
        lat=40.71,    # NYC latitude
        lon=-74.01,   # NYC longitude
        threshold_f=90.0,
    )
```
