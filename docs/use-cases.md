# Use Cases

Real-world applications built on the Resolved Markets API. Each section includes a description, architectural approach, and a working code sketch to get you started.

---

## Market Making Simulation

Backtest market-making strategies by replaying historical orderbook snapshots. The API captures snapshots at ~20Hz per token, giving you the granularity needed to simulate realistic order placement, fill probability estimation, and inventory risk tracking without risking capital on a live market.

**Approach:** Fetch paginated historical snapshots for a given market and time range using `GET /v1/markets/:id/snapshots`. Iterate through them chronologically, simulating passive limit orders at each step. For each snapshot, check whether your resting orders would have been filled based on the best bid/ask crossing your price. Track PnL, inventory exposure, and fill rates over time.

```python
import requests
from dataclasses import dataclass, field

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
        best_ask = snapshot["bestAsk"]
        best_bid = snapshot["bestBid"]

        # Our bid gets filled if market's best ask drops to our bid
        if best_ask <= my_bid:
            self.inventory += self.order_size
            self.pnl -= my_bid * self.order_size
            self.fills.append(("BUY", my_bid, snapshot["eventTimestamp"]))

        # Our ask gets filled if market's best bid rises to our ask
        if best_bid >= my_ask:
            self.inventory -= self.order_size
            self.pnl += my_ask * self.order_size
            self.fills.append(("SELL", my_ask, snapshot["eventTimestamp"]))


def fetch_snapshots(market_id: str, from_ts: str, to_ts: str, token_side: str = "UP"):
    """Paginate through all snapshots in the time range."""
    offset = 0
    limit = 1000
    while True:
        resp = requests.get(
            f"{API_URL}/v1/markets/{market_id}/snapshots",
            headers=HEADERS,
            params={
                "from": from_ts, "to": to_ts,
                "tokenSide": token_side,
                "limit": limit, "offset": offset,
            },
        )
        data = resp.json()
        snapshots = data["snapshots"]
        if not snapshots:
            break
        yield from snapshots
        offset += limit
        if offset >= data["total"]:
            break


def run_backtest(market_id: str, from_ts: str, to_ts: str):
    sim = MarketMakerSim(spread_target=0.02)

    for snap in fetch_snapshots(market_id, from_ts, to_ts):
        mid = snap["midPrice"]
        my_bid, my_ask = sim.quote(mid)
        sim.check_fills(my_bid, my_ask, snap)

    print(f"Total fills: {len(sim.fills)}")
    print(f"Final inventory: {sim.inventory}")
    print(f"PnL: {sim.pnl:.4f}")
    print(f"Inventory risk (abs): {abs(sim.inventory) * sim.fills[-1][1] if sim.fills else 0:.2f}")


# Example: backtest on a BTC market over 1 hour
run_backtest("0x1234abcd...", "2026-03-24T10:00:00Z", "2026-03-24T11:00:00Z")
```

---

## Liquidity Monitoring Dashboard

A real-time dashboard that tracks bid/ask depth, spread trends, and liquidity imbalances across all active markets. Useful for traders who need to see at a glance where liquidity is concentrating or thinning out, and for market operators monitoring platform health.

**Approach:** Connect to the WebSocket endpoint at `wss://api.resolvedmarkets.com/ws/orderbook` and subscribe to each crypto. On every snapshot event, update in-memory state and render depth bars, spread sparklines, and a bid/ask imbalance ratio. Use `GET /v1/markets/live` on page load to populate the market list.

```jsx
import { useEffect, useRef, useState } from "react";

const API_URL = "https://api.resolvedmarkets.com";
const WS_URL = "wss://api.resolvedmarkets.com/ws/orderbook";
const API_KEY = "rm_your_key";
const CRYPTOS = ["BTC", "ETH", "SOL", "XRP"];

function useOrderbookStream(apiKey) {
  const [books, setBooks] = useState({});
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "auth", apiKey }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "auth" && msg.status === "ok") {
        // Subscribe to all cryptos after successful auth
        CRYPTOS.forEach((crypto) => {
          ws.send(JSON.stringify({ type: "subscribe", crypto }));
        });
      }

      if (msg.type === "snapshot") {
        setBooks((prev) => ({
          ...prev,
          [`${msg.crypto}_${msg.tokenSide}`]: {
            bestBid: msg.bestBid,
            bestAsk: msg.bestAsk,
            spread: msg.spread,
            midPrice: msg.midPrice,
            totalBidDepth: msg.bids.reduce((sum, l) => sum + l.size, 0),
            totalAskDepth: msg.asks.reduce((sum, l) => sum + l.size, 0),
            updatedAt: msg.timestamp,
          },
        }));
      }
    };

    return () => ws.close();
  }, [apiKey]);

  return books;
}

function LiquidityCard({ label, data }) {
  if (!data) return <div className="card loading">{label}: waiting...</div>;

  const imbalance = data.totalBidDepth / (data.totalBidDepth + data.totalAskDepth);
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
        <span>Bid depth:</span> {data.totalBidDepth.toLocaleString()}
        {" | "}
        <span>Ask depth:</span> {data.totalAskDepth.toLocaleString()}
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

On Polymarket, every market has an UP token and a DOWN token whose prices should sum to approximately 1.00. When the sum deviates significantly (e.g., > 1.02 or < 0.98), there is a potential arbitrage opportunity: buy the underpriced side, or sell both when the sum exceeds 1.00. This use case monitors that spread in real-time.

**Approach:** Poll `GET /v1/markets/live` to get all active markets with their current token prices. For each market, compute `UP.price + DOWN.price` and flag deviations. For higher frequency detection, use the WebSocket stream to track both token sides of the same market and alert immediately when the invariant breaks.

```python
import requests
import time
from datetime import datetime

API_URL = "https://api.resolvedmarkets.com"
API_KEY = "rm_your_key"
HEADERS = {"X-API-Key": API_KEY}

# Threshold: flag when UP + DOWN deviates from 1.00 by more than this
DEVIATION_THRESHOLD = 0.015


def fetch_live_markets(category: str | None = None) -> list[dict]:
    params = {}
    if category:
        params["category"] = category
    resp = requests.get(f"{API_URL}/v1/markets/live", headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()["markets"]


def check_arbitrage(markets: list[dict]) -> list[dict]:
    opportunities = []

    for market in markets:
        tokens = market["tokens"]
        up_token = next((t for t in tokens if t["side"] == "UP"), None)
        down_token = next((t for t in tokens if t["side"] == "DOWN"), None)

        if not up_token or not down_token:
            continue

        price_sum = up_token["price"] + down_token["price"]
        deviation = abs(price_sum - 1.0)

        if deviation > DEVIATION_THRESHOLD:
            opportunities.append({
                "market": market["question"],
                "conditionId": market["conditionId"],
                "up_price": up_token["price"],
                "down_price": down_token["price"],
                "sum": round(price_sum, 4),
                "deviation": round(deviation, 4),
                "direction": "overpriced" if price_sum > 1.0 else "underpriced",
            })

    return sorted(opportunities, key=lambda x: x["deviation"], reverse=True)


def get_depth_context(condition_id: str) -> dict:
    """Fetch orderbook to verify there is enough liquidity to act on."""
    resp = requests.get(
        f"{API_URL}/v1/markets/{condition_id}/orderbook",
        headers=HEADERS,
    )
    resp.raise_for_status()
    book = resp.json()["market"]["tokens"]
    return {
        "up_bid_depth": book["UP"]["totalBidDepth"],
        "down_bid_depth": book["DOWN"]["totalBidDepth"],
        "up_ask_depth": book["UP"]["totalAskDepth"],
        "down_ask_depth": book["DOWN"]["totalAskDepth"],
    }


def monitor(interval_sec: int = 10):
    """Continuously monitor for arbitrage opportunities."""
    print(f"Monitoring for UP+DOWN deviations > {DEVIATION_THRESHOLD}...")

    while True:
        markets = fetch_live_markets()
        opps = check_arbitrage(markets)

        if opps:
            print(f"\n[{datetime.now().isoformat()}] Found {len(opps)} opportunities:")
            for opp in opps:
                depth = get_depth_context(opp["conditionId"])
                print(f"  {opp['market']}")
                print(f"    UP={opp['up_price']} + DOWN={opp['down_price']} = {opp['sum']}")
                print(f"    Deviation: {opp['deviation']} ({opp['direction']})")
                print(f"    Liquidity: bid_depth UP={depth['up_bid_depth']:.0f} DOWN={depth['down_bid_depth']:.0f}")
        else:
            print(".", end="", flush=True)

        time.sleep(interval_sec)


if __name__ == "__main__":
    monitor()
```

---

## AI Agent Trading Signals

Use the MCP (Model Context Protocol) server to let Claude or other AI agents analyze live orderbook data and generate trading signals. The MCP server exposes 6 tools that agents can call directly -- no REST client code needed. The agent can reason about spread dynamics, depth imbalances, and cross-market correlations using natural language.

**Approach:** Configure the MCP server in Claude Desktop or Claude Code, then use conversational prompts to query live market data. The agent calls `list_markets`, `get_orderbook`, and `get_market_summary` tools under the hood and synthesizes the results into actionable analysis.

**Claude Desktop MCP configuration:**

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
"Get market summaries for all active BTC markets (5m, 15m, 1h, 1d).
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

Bulk export historical orderbook data for academic research on prediction markets. Study spread dynamics, market microstructure, price discovery efficiency, and how prediction market prices converge to outcomes as expiration approaches. The ~20Hz snapshot frequency provides granularity comparable to traditional exchange datasets.

**Approach:** Use the paginated `GET /v1/markets/:id/snapshots` endpoint to download all snapshots for a market over a given period. Load them into a pandas DataFrame for analysis. Export to Parquet or CSV for use in R, Stata, or other research tools.

```python
import requests
import pandas as pd
from datetime import datetime, timedelta

API_URL = "https://api.resolvedmarkets.com"
API_KEY = "rm_your_key"
HEADERS = {"X-API-Key": API_KEY}


def export_snapshots(
    market_id: str,
    from_ts: str,
    to_ts: str,
    token_side: str = "UP",
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
                "tokenSide": token_side,
                "limit": limit,
                "offset": offset,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        snapshots = data["snapshots"]

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
            "event_timestamp": snap["eventTimestamp"],
            "capture_timestamp": snap["captureTimestamp"],
            "token_side": snap["tokenSide"],
            "best_bid": snap["bestBid"],
            "best_ask": snap["bestAsk"],
            "mid_price": snap["midPrice"],
            "spread": snap["spread"],
            "total_bid_depth": snap["totalBidDepth"],
            "total_ask_depth": snap["totalAskDepth"],
            "sequence_number": snap["sequenceNumber"],
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
df = export_snapshots(market_id, "2026-03-23T00:00:00Z", "2026-03-24T00:00:00Z")

if not df.empty:
    analyze_spread_dynamics(df)

    # Export for use in other tools
    df.to_parquet("btc_up_snapshots_20260323.parquet", index=False)
    print(f"\nExported {len(df):,} rows to Parquet")

    # Also export a sampled version (1 snapshot per second) for lighter analysis
    df_sampled = df.set_index("event_timestamp").resample("1s").first().dropna().reset_index()
    df_sampled.to_csv("btc_up_snapshots_1s_20260323.csv", index=False)
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
    markets = resp.json()["markets"]

    results = []
    for market in markets:
        cid = market["conditionId"]
        try:
            summary_resp = requests.get(
                f"{API_URL}/v1/markets/{cid}/summary",
                headers=HEADERS,
            )
            summary_resp.raise_for_status()
            summary = summary_resp.json()["summary"]
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
        spreads = [m["avgSpread"] for m in markets]
        depths = [m["avgBidDepth"] + m["avgAskDepth"] for m in markets]
        snap_counts = [m["snapshotCount"] for m in markets]

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
    spreads = [s["avgSpread"] for s in summaries]
    global_mean = mean(spreads)

    print("\n=== Outlier Markets ===")
    print(f"Global average spread: {global_mean:.4f}\n")

    wide = [s for s in summaries if s["avgSpread"] > global_mean * 2]
    tight = [s for s in summaries if s["avgSpread"] < global_mean * 0.5]

    if wide:
        print("Unusually WIDE spreads (>2x average):")
        for s in sorted(wide, key=lambda x: x["avgSpread"], reverse=True):
            print(f"  {s['avgSpread']:.4f} - [{s['category']}] {s['question']}")

    if tight:
        print("\nUnusually TIGHT spreads (<0.5x average):")
        for s in sorted(tight, key=lambda x: x["avgSpread"]):
            print(f"  {s['avgSpread']:.4f} - [{s['category']}] {s['question']}")


summaries = fetch_all_summaries()
rankings = analyze_by_category(summaries)
find_outlier_markets(summaries)
```

---

## Weather Market Correlation Analysis

Compare weather prediction market prices with actual weather data to study prediction accuracy. Polymarket hosts weather markets (e.g., "Will NYC temperature exceed 90F this week?"), and this use case tracks how the market-implied probability evolves relative to observed and forecast conditions. Useful for evaluating whether prediction markets are well-calibrated for weather events.

**Approach:** Fetch weather-category markets via `GET /v1/markets/live?category=weather`, then use `GET /v1/markets/:id/snapshots` to track how the UP token mid-price (the implied probability of "Yes") changes over time. Pair this with an external weather API (e.g., Open-Meteo, free and no API key required) to overlay actual observations. Compute a calibration curve: when the market says 70% probability, does the event happen ~70% of the time?

```python
import requests
import pandas as pd
from datetime import datetime, timedelta

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
    return resp.json()["markets"]


def fetch_market_probability_series(market_id: str, hours: int = 48) -> pd.DataFrame:
    """Get the UP token mid-price over time (= implied probability)."""
    to_ts = datetime.utcnow().isoformat() + "Z"
    from_ts = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"

    all_snaps = []
    offset = 0
    while True:
        resp = requests.get(
            f"{API_URL}/v1/markets/{market_id}/snapshots",
            headers=HEADERS,
            params={
                "from": from_ts, "to": to_ts,
                "tokenSide": "UP",
                "limit": 1000, "offset": offset,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not data["snapshots"]:
            break
        all_snaps.extend(data["snapshots"])
        offset += 1000
        if offset >= data["total"]:
            break

    df = pd.DataFrame(all_snaps)
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["eventTimestamp"])
    # Resample to 1-minute intervals for manageable size
    df = df.set_index("timestamp").resample("1min")["midPrice"].mean().dropna().reset_index()
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
