# Contributing

Thanks for your interest in improving Zotero MCP. The project is early-stage, so this file captures the intended workflow. If you hit gaps, open an issue or submit a PR with improvements.

## Getting Started

1. Fork and clone the repo.
2. Install dependencies with `uv`.
3. Export required environment variables for local runs.
4. Run the server locally with `uv run python -m zotero_mcp`.

## Development Notes

- Use Python for all server logic.
- The MCP server uses the official MCP Python SDK with `stdio` transport.
- Do not commit API keys or tokens.
- Keep user data and attachment contents out of logs.
- `uv` is the preferred local dev workflow.
- Use the env vars in `README.md` (`ZOTERO_API_KEY`, `ZOTERO_USER_ID`, optional retry/cache/logging knobs).

## Testing

Tests are available. Install dev deps and run:

```bash
uv run --extra test python -m pytest -q
```

## Pull Requests

1. Keep PRs small and focused.
2. Describe user-visible behavior changes in the PR description.
3. Include tests where possible.
