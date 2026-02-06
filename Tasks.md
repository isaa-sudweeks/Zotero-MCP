# Tasks

Ordered, small-batch tasks to deliver v1.

1. Confirm project structure and Python runtime (version, packaging, entrypoint). Use `uv` + `pyproject.toml`, entrypoint `python -m zotero_mcp`.
2. Define MCP tool surface for v1: `zotero_search_items` with `query`, `limit`, `sort`, `tags`.
3. Define MCP tool surface for v1: `zotero_get_item` with `item_key`.
4. Define MCP tool surface for v1: `zotero_create_item` with `item_type`, `title`, `creators`, `date`, `doi`, `url`, `abstract`, `tags`, `extra`.
5. Define MCP tool surface for v1: `zotero_upload_attachment` with `item_key`, `file_path`, `title`, `content_type`.
6. Map Zotero API endpoints to tool behaviors.
7. Define request/response schemas for each MCP tool.
8. Implement Zotero auth handling via env vars only.
9. Implement MCP `stdio` server skeleton.
10. Implement library search/list tool.
11. Implement item metadata fetch tool.
12. Implement create-item tool.
13. Implement PDF attachment upload flow.
14. Add conservative retry/backoff and optional read cache.
15. Add structured logging with sensitive-data redaction.
16. Add unit tests for tool schemas and request validation.
17. Add integration tests with mocked Zotero responses.
18. Add Dockerfile and container entrypoint.
19. Add docker run examples and MCP client config example.
20. Validate Docker image runs locally.
21. Prepare Docker MCP Registry submission assets (metadata, docs, image).
22. Write a short release checklist for v1.
