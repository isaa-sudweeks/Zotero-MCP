# Zotero MCP

Local, containerized MCP server that gives AI agents safe, structured access to the Zotero API.

This project targets the Docker MCP Catalog submission flow and will be published as a self-provided image so you can run it immediately before catalog approval.

**Status**: Initial design and scaffolding.

**Vision (v1)**: An agent can search your personal Zotero library for a paper. If it’s missing, the agent can upload the paper and its metadata (including PDF attachment) into your library.

**Non-goals (v1)**: Group libraries, collaboration features, and advanced Zotero workflows (notes sync, citation styles, etc.) are out of scope for the first release.

**Transport**: `stdio` only (MCP local server).

**Runtime**: Python (containerized). Packaging: `uv` + `pyproject.toml`. Entrypoint: `python -m zotero_mcp`.

## Features (Planned v1)

- Search and list items in the personal Zotero library.
- Retrieve item metadata.
- Create new items with metadata.
- Upload PDF attachments and link them to items.

## MCP Tools (Planned v1)

- `zotero_search_items` inputs: `query` (string), `limit` (int, default 25), `sort` (string, default `relevance`), `tags` (string[] optional)
- `zotero_get_item` inputs: `item_key` (string)
- `zotero_create_item` inputs: `item_type` (string), `title` (string), `creators` (array), `date` (string), `doi` (string optional), `url` (string optional), `abstract` (string optional), `tags` (string[] optional), `extra` (string optional)
- `zotero_upload_attachment` inputs: `item_key` (string), `file_path` (string), `title` (string optional), `content_type` (string optional)

## Security Model

- API keys are provided via environment variables only.
- No API keys are written to disk.
- Logs must avoid sensitive data (tokens, attachment contents).
- Minimal permission scope: personal library only.

## Rate Limits and Reliability

Zotero rate limits will be handled with conservative retry/backoff and a small, optional cache for idempotent reads. This is intended to avoid bursts and improve responsiveness without exceeding API limits.

## Quick Start (Docker)

The image will be published as a self-provided image (Option B in the Docker MCP Registry).

```bash
docker run -i --rm \
  -e ZOTERO_API_KEY=your_key_here \
  -e ZOTERO_USER_ID=your_user_id \
  zotero-mcp:latest
```

## MCP Client Configuration (Example)

This is a generic MCP `stdio` configuration example. Adjust to your host application’s config format.

```json
{
  "mcpServers": {
    "zotero": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "ZOTERO_API_KEY=your_key_here",
        "-e",
        "ZOTERO_USER_ID=your_user_id",
        "zotero-mcp:latest"
      ]
    }
  }
}
```

## Environment Variables

- `ZOTERO_API_KEY` (required): Zotero API key for personal library access.
- `ZOTERO_USER_ID` (required): Zotero user ID associated with the API key.
- `ZOTERO_API_BASE` (optional): Override base URL for testing.

## Docker MCP Registry Alignment

The Docker MCP Registry supports two submission types: Docker-built images and self-provided images. This project will follow the self-provided image path and provide full documentation, Docker deployment, and MCP compatibility.

## Roadmap

- Group library support.
- Additional Zotero objects (collections, tags, notes).
- Read-only mode.
- Configurable toolsets.

## Contributing

See `CONTRIBUTING.md` for local development and contribution guidance.
