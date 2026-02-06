# Usage

## Docker Run

```bash
docker run --rm -i \
  -e ZOTERO_API_KEY=your_key_here \
  -e ZOTERO_USER_ID=your_user_id \
  ghcr.io/your-org/zotero-mcp:0.1.0
```

## MCP Client Config

```json
{
  "mcpServers": {
    "zotero": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e",
        "ZOTERO_API_KEY=your_key_here",
        "-e",
        "ZOTERO_USER_ID=your_user_id",
        "ghcr.io/your-org/zotero-mcp:0.1.0"
      ]
    }
  }
}
```

## Required Environment Variables

- `ZOTERO_API_KEY`: Zotero API key for personal library access.
- `ZOTERO_USER_ID`: Zotero user ID associated with the API key.

## Optional Environment Variables

- `ZOTERO_API_BASE`: Override base URL for testing.
- `ZOTERO_MCP_DEBUG`: Set to `1` to include a startup log event.
- `ZOTERO_MCP_LOG_LEVEL`: Log level for JSON logs (default `INFO`).
- `ZOTERO_RETRY_MAX_ATTEMPTS`: Retry attempts for 429/5xx/network errors (default `3`).
- `ZOTERO_RETRY_BASE_DELAY`: Base backoff delay in seconds (default `0.5`).
- `ZOTERO_RETRY_MAX_DELAY`: Max backoff delay in seconds (default `4.0`).
- `ZOTERO_READ_CACHE`: Set to `1` to enable in-memory GET caching (default off).
- `ZOTERO_READ_CACHE_TTL`: Cache TTL in seconds (default `30`).
- `ZOTERO_READ_CACHE_MAX`: Max cached entries (default `128`).
