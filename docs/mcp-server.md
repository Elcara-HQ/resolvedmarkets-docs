# MCP Server

The MCP (Model Context Protocol) server enables AI agents to query Resolved Markets data programmatically. Every tier has full MCP access. Use the hosted endpoint `https://mcp.resolvedmarkets.com/mcp`, or run the npm package `@elcara-hq/resolvedmarkets-mcp`.

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `HF_API_URL` | `http://localhost:3001` | Backend API URL |
| `HF_API_KEY` | — | API key for authentication |
| `MCP_TRANSPORT` | `stdio` | Transport: `stdio` or `http` |
| `MCP_PORT` | `3002` | Port for HTTP transport |

## Tools

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

## Resources

| URI | Description |
|-----|-------------|
| `markets://live` | All currently active markets |
| `prices://latest` | Latest crypto prices |
| `reference://catalog` | Static reference: categories, tiers, credit costs, error codes |

## Claude Desktop Configuration

Add to your Claude Desktop MCP config:

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

## Example Usage

Once connected, an AI agent can:

- "List all active crypto markets" → calls `list_markets` with category filter
- "Show me the BTC orderbook" → calls `get_orderbook`
- "What was the BTC spread yesterday at noon?" → calls `get_snapshot`
- "Get the last 100 SOL snapshots" → calls `query_snapshots`
