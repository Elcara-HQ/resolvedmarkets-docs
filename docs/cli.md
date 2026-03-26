# CLI

The Resolved Markets CLI provides command-line access to the API.

## Installation

```bash
npm install -g resolved-markets-cli
```

## Configuration

Set your API key:

```bash
rm-api config --set-key YOUR_API_KEY
```

Or via environment variable:

```bash
export RESOLVED_MARKETS_API_KEY=rm_your_key
```

## Key Resolution Order

1. `--api-key` flag (highest priority)
2. `RM_API_KEY` environment variable
3. Saved config from `rm-api config --set-key`
