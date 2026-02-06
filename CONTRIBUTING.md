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
- For local testing, create a Zotero API key with least-privilege permissions (see README "API Key Permissions").

## Testing

Tests are available. Install dev deps and run:

```bash
uv run --extra test python -m pytest -q
```

Notes:
- Test deps may require network access to build/install (e.g., `hatchling`).
- Offline installs require a prebuilt lockfile and a warmed cache. See the README "Local Development (uv)" notes for a sample workflow.
- Some sandboxed environments have hit `TimeoutError` reading `entry_points.txt` when pytest auto-loads plugins. Workaround: disable plugin auto-load for the run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

- If you still hit the timeout or missing deps, run tests in a fully provisioned host environment.

## Pull Requests

1. Keep PRs small and focused.
2. Describe user-visible behavior changes in the PR description.
3. Include tests where possible.
