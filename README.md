# Zotero MCP

Local MCP server that gives AI agents safe, structured access to the Zotero API (Docker packaging included).

This project targets the Docker MCP Catalog submission flow and will be published as a self-provided image once a published image is available.

**Status**: Core tools implemented (search, get, create, upload, collections). Reliability (retry + read cache) and structured logging are in place. Tests exist but require dependencies; Dockerfile is present and local image validation is pending.

**Vision (v1)**: An agent can search your personal Zotero library for a paper. If it’s missing, the agent can upload the paper and its metadata (including a file attachment, typically a PDF) into your library.

**Non-goals (v1)**: Group libraries, collaboration features, and advanced Zotero workflows (notes sync, citation styles, etc.) are out of scope for the first release.

**Transport**: `stdio` only (MCP local server).

**Runtime**: Python 3.11+. Packaging: `uv` + `pyproject.toml`. Entrypoint: `python -m zotero_mcp`.

**MCP SDK**: Uses the official MCP Python SDK (`mcp`) with `stdio` transport in `src/zotero_mcp/server.py`.

## Features (v1)

- List collections in the personal Zotero library. (Implemented)
- Search and list items in the personal Zotero library. (Implemented)
- Retrieve item metadata (including attachments). (Implemented)
- Create new items with metadata. (Implemented)
- Upload file attachments (typically PDFs) and link them to items. (Implemented)
- Add an item to a collection by name or key. (Implemented)

## MCP Tools (v1)

Current tool surface for v1. Tools below reflect the current implementation.

**Common rules**
- All tools operate on the personal library only.
- `item_key` is the Zotero item key (8-character string).
- `tags` are strings; duplicates are ignored.
- `creators` entries use Zotero's basic creator shape: `creator_type`, `first_name`, `last_name`, or `name` for single-field creators.
- `collection_name` matching is case-insensitive exact-match; ambiguous matches return an error with the candidate keys.
- Errors are returned as MCP tool errors with codes like `ZOTERO_AUTH_ERROR`, `ZOTERO_NOT_FOUND`, `ZOTERO_RATE_LIMITED`, `ZOTERO_VALIDATION_ERROR`, `ZOTERO_UPSTREAM_ERROR`.
- Tool results are wrapped in a standard envelope: `{ "ok": true|false, "data": ..., "error": ... }`.
- Pagination input is supported via `start` (or `offset` as an alias) and `next_start` in responses when Zotero supplies it.

**Tool: `zotero_search_items`**
- Purpose: search and list items in the personal library.
- Inputs
- `query` (string, required): free-text search query.
- `limit` (int, optional, default 25, min 1, max 100): max items to return.
- `sort` (string, optional, default `relevance`): sort key, forwarded to Zotero. If Zotero rejects `relevance`, the server retries with `dateModified` and returns `sort_used`.
- `start` (int, optional, default 0, min 0): starting offset into the result set.
- `offset` (int, optional, min 0): alias for `start` (use one or the other).
- `tags` (string[], optional): filter to items containing all tags.
- Output
- `items` (array): list of items with fields `item_key`, `version`, `item_type`, `title`, `creators`, `date`, `doi`, `url`, `abstract`, `tags`, `extra`.
- `total` (int): total items matched (if available from Zotero).
- `next_start` (int, optional): pagination cursor if Zotero provides a next page.
- `sort_used` (string, optional): populated when a fallback sort was applied.

**Tool: `zotero_list_collections`**
- Purpose: list collections in the personal library.
- Inputs
- `limit` (int, optional, default 25, min 1, max 100): max collections to return.
- `start` (int, optional, default 0, min 0): starting offset into the result set.
- Output
- `collections` (array): list of collections with fields `collection_key`, `name`, `parent_key`, `version`, `num_items` (when available).
- `total` (int): total collections (if available from Zotero).
- `next_start` (int, optional): pagination cursor if Zotero provides a next page.

**Tool: `zotero_get_item`**
- Purpose: fetch metadata for a single item.
- Inputs
- `item_key` (string, required).
- Output
- `item` (object): item with fields `item_key`, `version`, `item_type`, `title`, `creators`, `date`, `doi`, `url`, `abstract`, `tags`, `extra`, plus `attachments` (array of attachment summaries).

**Tool: `zotero_create_item`**
- Purpose: create a new bibliographic item in the personal library.
- Inputs
- `item_type` (string, required): Zotero item type (e.g., `journalArticle`).
- `title` (string, required).
- `creators` (array, optional, default `[]`).
- `date` (string, optional).
- `doi` (string, optional).
- `url` (string, optional).
- `abstract` (string, optional).
- `tags` (string[], optional).
- `extra` (string, optional).
- Output
- `item_key` (string): created item key.
- `version` (int): Zotero item version.

**Tool: `zotero_upload_attachment`**
- Purpose: attach a file to an existing item.
- Inputs
- `item_key` (string, required): parent item key to attach to.
- `file_path` (string, optional): local path to file in the container/runtime (must exist and be readable).
- `file_url` (string, optional): http/https URL to fetch and upload.
- `file_bytes_base64` (string, optional): base64-encoded file bytes to upload.
- `filename` (string, required when using `file_bytes_base64`): filename to associate with the upload.
- `title` (string, optional): attachment title (defaults to filename).
- `content_type` (string, optional): inferred from file extension when omitted (fallback `application/octet-stream`).
- Provide exactly one of `file_path`, `file_url`, or `file_bytes_base64`.
- Output
- `attachment_key` (string): created attachment item key.
- `version` (int): attachment item version.
- `parent_item_key`, `title`, `content_type`, `size` are included when available.

**Tool: `zotero_attach_arxiv_pdf`**
- Purpose: fetch an arXiv PDF and attach it to an existing item.
- Inputs
- `item_key` (string, required): parent item key to attach to.
- `arxiv_id` (string, required): arXiv identifier or arXiv URL (e.g., `1706.03762v1` or `https://arxiv.org/abs/1706.03762`).
- `title` (string, optional): attachment title (defaults to filename).
- Output
- `attachment_key` (string): created attachment item key.
- `version` (int): attachment item version.
- `parent_item_key`, `title`, `content_type`, `size`, `arxiv_id`, `pdf_url` are included when available.

**Tool: `zotero_get_sort_values`**
- Purpose: return known Zotero sort values plus server defaults.
- Inputs: none.
- Output
- `values` (string[]): known sort keys.
- `default` (string): default sort used by the server.
- `fallback` (string): fallback sort used when `relevance` is rejected.

**Tool: `zotero_add_item_to_collection`**
- Purpose: add an item to a collection by collection key or name.
- Inputs
- `item_key` (string, required): item key to add.
- `collection_key` (string, optional): collection key to add to.
- `collection_name` (string, optional): collection name to resolve (case-insensitive exact match).
- Output
- `item_key` (string): item key added.
- `collection_key` (string): resolved collection key used for the add.

## MCP Tool Schemas (Request/Response)

All tools accept JSON objects as input. Responses are JSON objects with a common envelope. Schemas below reflect the current implementation.

Common response envelope:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

On error:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

Shared schema fragments:

```json
{
  "$defs": {
    "creator": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "creator_type": { "type": "string" },
        "first_name": { "type": "string" },
        "last_name": { "type": "string" },
        "name": { "type": "string" }
      },
      "required": ["creator_type"],
      "oneOf": [
        { "required": ["first_name", "last_name"] },
        { "required": ["name"] }
      ]
    },
    "tag": {
      "type": "string",
      "minLength": 1
    }
  }
}
```

### `zotero_search_items`

Request schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "query": { "type": "string", "minLength": 1 },
    "limit": { "type": "integer", "minimum": 1, "maximum": 100, "default": 25 },
    "sort": { "type": "string", "default": "relevance" },
    "start": { "type": "integer", "minimum": 0, "default": 0 },
    "offset": { "type": "integer", "minimum": 0 },
    "tags": {
      "type": "array",
      "items": { "$ref": "#/$defs/tag" },
      "uniqueItems": true
    }
  },
  "required": ["query"]
}
```

Response `data` schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "item_key": { "type": "string" },
          "item_type": { "type": "string" },
          "title": { "type": "string" },
          "creators": { "type": "array", "items": { "$ref": "#/$defs/creator" } },
          "date": { "type": "string" },
          "doi": { "type": "string" },
          "url": { "type": "string" },
          "abstract": { "type": "string" },
          "tags": { "type": "array", "items": { "$ref": "#/$defs/tag" } },
          "extra": { "type": "string" },
          "version": { "type": "integer" }
        },
        "required": ["item_key", "item_type", "title", "version"]
      }
    },
    "total": { "type": "integer", "minimum": 0 },
    "next_start": { "type": "integer", "minimum": 0 },
    "sort_used": { "type": "string" }
  },
  "required": ["items", "total"]
}
```

### `zotero_get_item`

Request schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "item_key": { "type": "string", "minLength": 1 }
  },
  "required": ["item_key"]
}
```

Response `data` schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "item": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "item_key": { "type": "string" },
        "item_type": { "type": "string" },
        "title": { "type": "string" },
        "creators": { "type": "array", "items": { "$ref": "#/$defs/creator" } },
        "date": { "type": "string" },
        "doi": { "type": "string" },
        "url": { "type": "string" },
        "abstract": { "type": "string" },
        "tags": { "type": "array", "items": { "$ref": "#/$defs/tag" } },
        "extra": { "type": "string" },
        "version": { "type": "integer" },
        "attachments": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "attachment_key": { "type": "string" },
              "title": { "type": "string" },
              "content_type": { "type": "string" },
              "size": { "type": "integer" }
            },
            "required": ["attachment_key", "title"]
          }
        }
      },
      "required": ["item_key", "item_type", "title", "version"]
    }
  },
  "required": ["item"]
}
```

### `zotero_get_sort_values`

Request schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {}
}
```

Response `data` schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "values": { "type": "array", "items": { "type": "string" } },
    "default": { "type": "string" },
    "fallback": { "type": "string" }
  },
  "required": ["values", "default", "fallback"]
}
```

### `zotero_create_item`

Request schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "item_type": { "type": "string", "minLength": 1 },
    "title": { "type": "string", "minLength": 1 },
    "creators": { "type": "array", "items": { "$ref": "#/$defs/creator" } },
    "date": { "type": "string" },
    "doi": { "type": "string" },
    "url": { "type": "string" },
    "abstract": { "type": "string" },
    "tags": { "type": "array", "items": { "$ref": "#/$defs/tag" }, "uniqueItems": true },
    "extra": { "type": "string" }
  },
  "required": ["item_type", "title"]
}
```

Response `data` schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "item_key": { "type": "string" },
    "version": { "type": "integer" },
    "item": { "type": "object" }
  },
  "required": ["item_key", "version"]
}
```

### `zotero_upload_attachment`

Uploads must provide exactly one of `file_path`, `file_url`, or `file_bytes_base64` (with `filename`). Local files must be readable and within the configured size limit. When `content_type` is omitted, the server infers it from the URL response header or filename extension (fallback `application/octet-stream`).

Request schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "item_key": { "type": "string", "minLength": 1 },
    "file_path": { "type": "string", "minLength": 1 },
    "file_url": { "type": "string", "minLength": 1 },
    "file_bytes_base64": { "type": "string", "minLength": 1 },
    "filename": { "type": "string", "minLength": 1 },
    "title": { "type": "string" },
    "content_type": { "type": "string" }
  },
  "required": ["item_key"],
  "anyOf": [
    { "required": ["item_key", "file_path"] },
    { "required": ["item_key", "file_url"] },
    { "required": ["item_key", "file_bytes_base64", "filename"] }
  ]
}
```

Response `data` schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "attachment_key": { "type": "string" },
    "parent_item_key": { "type": "string" },
    "title": { "type": "string" },
    "content_type": { "type": "string" },
    "size": { "type": "integer" },
    "version": { "type": "integer" }
  },
  "required": ["attachment_key", "parent_item_key", "version"]
}
```

### `zotero_attach_arxiv_pdf`

Fetches an arXiv PDF by identifier or URL and uploads it as an attachment.

Request schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "item_key": { "type": "string", "minLength": 1 },
    "arxiv_id": { "type": "string", "minLength": 1 },
    "title": { "type": "string" }
  },
  "required": ["item_key", "arxiv_id"]
}
```

Response `data` schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "attachment_key": { "type": "string" },
    "parent_item_key": { "type": "string" },
    "title": { "type": "string" },
    "content_type": { "type": "string" },
    "size": { "type": "integer" },
    "version": { "type": "integer" },
    "arxiv_id": { "type": "string" },
    "pdf_url": { "type": "string" }
  },
  "required": ["attachment_key", "parent_item_key", "version", "arxiv_id", "pdf_url"]
}
```

### `zotero_list_collections`

Request schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "limit": { "type": "integer", "minimum": 1, "maximum": 100, "default": 25 },
    "start": { "type": "integer", "minimum": 0, "default": 0 }
  }
}
```

Response `data` schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "collections": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "collection_key": { "type": "string" },
          "name": { "type": "string" },
          "parent_key": { "type": "string" },
          "version": { "type": "integer" },
          "num_items": { "type": "integer" }
        },
        "required": ["collection_key", "name", "version"]
      }
    },
    "total": { "type": "integer", "minimum": 0 },
    "next_start": { "type": "integer", "minimum": 0 }
  },
  "required": ["collections", "total"]
}
```

### `zotero_add_item_to_collection`

Request schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "item_key": { "type": "string", "minLength": 1 },
    "collection_key": { "type": "string", "minLength": 1 },
    "collection_name": { "type": "string", "minLength": 1 }
  },
  "required": ["item_key"]
}
```

Response `data` schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "item_key": { "type": "string" },
    "collection_key": { "type": "string" }
  },
  "required": ["item_key", "collection_key"]
}
```

## API Mapping (v1)

All endpoints are Zotero Web API v3 and use `https://api.zotero.org` with `Zotero-API-Version: 3`.

- `zotero_search_items` (implemented) -> `GET /users/{userID}/items`
- Query params: `q={query}` (quick search), `tag={tag}` (repeatable), `limit={limit}`, `sort={sort}`, `start={start}`
- `zotero_list_collections` (implemented) -> `GET /users/{userID}/collections`
- `zotero_get_item` (implemented) -> `GET /users/{userID}/items/{itemKey}`
- `zotero_create_item` (implemented) -> `GET /items/new?itemType={item_type}` (template), then `POST /users/{userID}/items`
- Body: JSON array with a single item object populated from tool inputs
- Headers: `Content-Type: application/json`, optional `Zotero-Write-Token`
- `zotero_upload_attachment` (implemented) -> multi-step file upload with child attachment item
- `GET /items/new?itemType=attachment&linkMode=imported_file` (attachment template)
- `POST /users/{userID}/items` with `parentItem={item_key}` to create attachment item
- `POST /users/{userID}/items/{attachmentKey}/file` (upload authorization: md5, filename, filesize, mtime)
- `POST {uploadUrl}` (multipart upload with `prefix`/`suffix`), then `POST /users/{userID}/items/{attachmentKey}/file` to register upload
- `zotero_attach_arxiv_pdf` (implemented) -> fetch `https://arxiv.org/pdf/{arxivId}.pdf`, then same upload flow as `zotero_upload_attachment`
- `zotero_add_item_to_collection` (implemented) -> `POST /users/{userID}/collections/{collectionKey}/items`

## Security Model

- API keys are provided via environment variables only.
- No API keys are written to disk.
- Logs must avoid sensitive data (tokens, attachment contents).
- Minimal permission scope: personal library only.

## Error Mapping

All tools return a consistent error envelope:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "ZOTERO_RATE_LIMITED",
    "message": "Zotero rate limit exceeded.",
    "details": {
      "status": 429,
      "retry_after": "120",
      "request_id": "abc123",
      "body": "{\"message\":\"Too Many Requests\"}"
    }
  }
}
```

Zotero HTTP errors are normalized into tool error codes:

- 401/403 -> `ZOTERO_AUTH_ERROR`
- 404 -> `ZOTERO_NOT_FOUND`
- 429 -> `ZOTERO_RATE_LIMITED`
- 400/409/412/413/415/422 -> `ZOTERO_VALIDATION_ERROR`
- 5xx -> `ZOTERO_UPSTREAM_ERROR`
- Other unexpected responses -> `ZOTERO_UPSTREAM_ERROR`
- Local validation failures -> `ZOTERO_VALIDATION_ERROR`

Error `details` may include:

- `status`: HTTP status code when available.
- `body`: Raw response body (string) when provided by Zotero.
- `retry_after`: `Retry-After` header value (if present).
- `request_id`: `X-Zotero-RequestID` header value (if present).

## Rate Limits and Reliability

Conservative retry/backoff is implemented for 429/5xx and network errors. Optional in-memory read caching is available for GET requests. When Zotero returns `Retry-After`, the client waits that duration (seconds or HTTP-date) before retrying.

## Logging

Logs are emitted as JSON to stderr with automatic redaction for sensitive fields (tokens, file paths, upload metadata). Each MCP tool call gets a `correlation_id` that is included on all related log lines so you can trace a single request end-to-end. Control verbosity with `ZOTERO_MCP_LOG_LEVEL`. Use `ZOTERO_MCP_DEBUG=1` to include the startup event.

## Configuration

This server reads credentials from environment variables only. `.env` files are not loaded automatically.

Required:
- `ZOTERO_API_KEY`: Zotero API key for personal library access.
- `ZOTERO_USER_ID`: Zotero user ID associated with the API key.

## Quick Start (Docker)

Docker packaging is included (see `Dockerfile`), but no published image is provided yet. Build locally:

```bash
docker build -t zotero-mcp:local .
```

Note: Some sandboxed environments (including this Codex sandbox) may not have Docker daemon access and can fail with a `permission denied while trying to connect to the docker API` error. In that case, run the build directly on your host with Docker Desktop running.

Then run it with `stdio` like this:

```bash
docker run --rm -i \
  -e ZOTERO_API_KEY=your_key_here \
  -e ZOTERO_USER_ID=your_user_id \
  zotero-mcp:local
```

To keep secrets out of shell history, use an env file:

```bash
cat > .env.zotero-mcp <<'EOF'
ZOTERO_API_KEY=your_key_here
ZOTERO_USER_ID=your_user_id
EOF

docker run --rm -i --env-file .env.zotero-mcp \
  zotero-mcp:local
```

## Local Development (uv)

```bash
uv sync
uv run python -m zotero_mcp
```

Notes on dependencies:
- Dev/test installs need network access to download build/runtime deps (for example, the build backend `hatchling`).
- Offline installs are possible if you precreate a lockfile and cache the wheels. Example flow: (1) on a machine with network, run `uv lock` and `uv sync` to populate the lockfile and `uv` cache, (2) copy `uv.lock` and the `uv` cache directory to the offline machine (set `UV_CACHE_DIR` to that cache path), (3) run `uv sync --frozen` on the offline machine to install from the cached wheels.

To use a local `.env` file, copy the example and source it before running:

```bash
cp .env.example .env.zotero-mcp
set -a
source .env.zotero-mcp
set +a
uv run python -m zotero_mcp
```

## Smoke Test (Server Boot)

Manual smoke test to confirm the MCP stdio server starts and emits a `server.start` log event. This does not require Zotero credentials because it does not call any tools.

```bash
uv run python scripts/smoke_test.py
```

Optional flags:
- `--timeout 10` to wait longer for slow environments.
- `--verbose` to print server stderr while waiting.

## MCP Client Configuration (Example)

This is a generic MCP `stdio` configuration example for local runs. Adjust to your host application’s config format.

```json
{
  "mcpServers": {
    "zotero": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "-m",
        "zotero_mcp"
      ],
      "env": {
        "ZOTERO_API_KEY": "your_key_here",
        "ZOTERO_USER_ID": "your_user_id"
      }
    }
  }
}
```

Docker-based MCP client configuration (replace the image name):

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
        "zotero-mcp:local"
      }
    }
  }
}
```

## Environment Variables

Required:
- `ZOTERO_API_KEY`: Zotero API key for personal library access.
- `ZOTERO_USER_ID`: Zotero user ID associated with the API key.

Optional:
- `ZOTERO_API_BASE`: Override base URL for testing.
- `ZOTERO_MCP_DEBUG`: Set to `1` to include a startup log event.
- `ZOTERO_MCP_LOG_LEVEL`: Log level for JSON logs (default `INFO`).
- `ZOTERO_RETRY_MAX_ATTEMPTS`: Retry attempts for 429/5xx/network errors (default `3`).
- `ZOTERO_RETRY_BASE_DELAY`: Base backoff delay in seconds (default `0.5`).
- `ZOTERO_RETRY_MAX_DELAY`: Max backoff delay in seconds (default `4.0`).
- `ZOTERO_READ_CACHE`: Set to `1` to enable in-memory GET caching (default off).
- `ZOTERO_READ_CACHE_TTL`: Cache TTL in seconds (default `30`).
- `ZOTERO_READ_CACHE_MAX`: Max cached entries (default `128`).
- `ZOTERO_UPLOAD_MAX_BYTES`: Max upload size in bytes (default `52428800`).

## Docker MCP Registry Alignment

The Docker MCP Registry supports two submission types: Docker-built images and self-provided images. This project plans to follow the self-provided image path once a published image is available.

Draft registry submission assets live in `registry/` (metadata, long description, usage examples). Update the placeholders with the published image name/tag before submission.

## Roadmap

- Group library support.
- Additional Zotero objects (collections, tags, notes).
- Read-only mode.
- Configurable toolsets.

## Release Checklist (v1)

- Confirm README matches current tool surfaces and schemas.
- Run unit tests for schema and validation.
- Run integration tests with mocked Zotero responses.
- Build Docker image and run locally via MCP stdio.
- Verify auth via env vars only; no credentials in logs.
- Verify retry/backoff, cache, and logging settings behave as documented.
- Confirm docker run and MCP client config examples work.
- Prepare registry submission assets (metadata, docs, image).
- Tag release and publish.

## Contributing

See `CONTRIBUTING.md` for local development and contribution guidance.
