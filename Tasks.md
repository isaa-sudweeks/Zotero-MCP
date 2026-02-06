# Tasks

Ordered, small-batch tasks to deliver v1. Status reflects the current repo state.

- [x] Confirm project structure and Python runtime (version, packaging, entrypoint). Use `uv` + `pyproject.toml`, entrypoint `python -m zotero_mcp`.
- [x] Define MCP tool surface for v1: `zotero_search_items` with `query`, `limit`, `sort`, `tags`.
- [x] Define MCP tool surface for v1: `zotero_get_item` with `item_key`.
- [x] Define MCP tool surface for v1: `zotero_create_item` with `item_type`, `title`, `creators`, `date`, `doi`, `url`, `abstract`, `tags`, `extra`.
- [x] Define MCP tool surface for v1: `zotero_upload_attachment` with `item_key`, `file_path`, `title`, `content_type`.
- [x] Map Zotero API endpoints to tool behaviors. Mapping details:
Search: `GET /users/{userID}/items` with `q`, `tag`, `limit`, `sort`.
Get item: `GET /users/{userID}/items/{itemKey}`.
Create item: `GET /items/new?itemType=...`, then `POST /users/{userID}/items`.
Upload attachment: `GET /items/new?itemType=attachment&linkMode=imported_file`, create child item, upload file, register upload.
- [x] Define request/response schemas for `zotero_search_items`.
- [x] Define request/response schemas for `zotero_get_item`, `zotero_create_item`, `zotero_upload_attachment`.
- [x] Implement Zotero auth handling via env vars only.
- [x] Implement MCP `stdio` server skeleton.
- [x] Implement library search/list tool.
- [x] Implement item metadata fetch tool.
- [x] Implement create-item tool.
- [x] Implement PDF attachment upload flow.
- [x] Add conservative retry/backoff and optional read cache.
- [x] Add structured logging with sensitive-data redaction.
- [x] Add unit tests for tool schemas and request validation.
- [x] Add integration tests with mocked Zotero responses.
- [x] Add Dockerfile and container entrypoint.
- [x] Add docker run examples and MCP client config example.
- [ ] Validate Docker image runs locally. (Blocked: Docker daemon permissions)
- [x] Prepare Docker MCP Registry submission assets (metadata, docs, image).
- [x] Write a short release checklist for v1.
- [x] Add pagination support for search/list (`start`/`offset`, `limit`) and document defaults.
- [x] Define error model and MCP error mapping (Zotero HTTP → tool error codes/messages).
- [x] Validate `file_path` (exists, readable, size limits) and infer `content_type`.
- [x] Add 429 rate limit handling with `Retry-After` support.
- [x] Add configuration documentation for required env vars and example `.env` usage.
- [x] Add logging/tracing correlation IDs per request.
- [x] Add security note: do not log auth token or file contents; redact in errors.
- [x] Document structured logging output and controls.
- [x] Add basic smoke test / manual test script to verify server boot.
