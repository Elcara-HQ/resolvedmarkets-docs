# CLI

The Resolved Markets CLI provides command-line access to the API.

## Installation

```bash
npm install -g @elcara-hq/resolvedmarkets-cli
```

## Configuration

Set your API key:

```bash
rm-api config --set-key YOUR_API_KEY
```

Or via environment variable:

```bash
export RM_API_KEY=rm_your_key
```

## Key Resolution Order

1. `--key` flag (highest priority)
2. `RM_API_KEY` environment variable
3. Saved config from `rm-api config --set-key`
