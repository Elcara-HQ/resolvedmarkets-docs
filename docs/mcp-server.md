# MCP Server

The MCP (Model Context Protocol) server enables AI agents to query Resolved Markets data programmatically.

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
| `list_markets` | List active markets, optionally filtered by category |
| `get_orderbook` | Get live orderbook for a market |
| `get_snapshot` | Get historical snapshot at a timestamp |
| `query_snapshots` | Query historical snapshots with filters |
| `get_market_summary` | Get aggregated market statistics |
| `get_system_stats` | Get platform health and stats |

## Resources

| URI | Description |
|-----|-------------|
| `markets://live` | All currently active markets |
| `prices://latest` | Latest crypto prices |

## Claude Desktop Configuration

Add to your Claude Desktop MCP config:

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

## Example Usage

Once connected, an AI agent can:

- "List all active crypto markets" → calls `list_markets` with category filter
- "Show me the BTC orderbook" → calls `get_orderbook`
- "What was the BTC spread yesterday at noon?" → calls `get_snapshot`
- "Get the last 100 SOL snapshots" → calls `query_snapshots`
