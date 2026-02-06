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
- [x] Investigate pytest startup failure in sandbox (TimeoutError reading entry_points.txt); documented workaround and environment requirements.
- [x] Document that dev/test dependencies require network access (pip build deps like `hatchling`) or provide an offline/install-from-lock workflow.
- [ ] Run unit + integration tests in a clean environment (uv or venv) and record results.
- [ ] Run smoke test script against live or mocked Zotero API and record outcomes.
- [ ] Document expected Zotero API permissions/scopes for the API key.
- [ ] Add LICENSE and reference it in registry metadata.
- [ ] Add CI workflow to run unit/integration tests when deps are available (or explicitly document no CI for v1).
- [x] Add collection tooling: list collections and add item to collection by name or key.
- [x] Add exact-match search helpers for DOI and arXiv ID (avoid false positives).
- [x] Add helper to fetch and attach arXiv PDF automatically.
- [x] Add ability to retrieve valid `sort` values and/or set safe defaults when relevance fails.
- [x] Add attachment by URL or upload-bytes path so file paths are not required.
- [~] Document a shared temp dir or filesystem bridge between tool server and local workspace. (Obsoleted if attachment by URL or upload-bytes is implemented)
