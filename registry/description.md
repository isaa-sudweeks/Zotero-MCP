# Zotero MCP

Zotero MCP is a containerized MCP stdio server that lets agents search, fetch, and create items in a personal Zotero library, plus upload PDF attachments. It is designed for local execution with credentials supplied via environment variables only.

## Highlights

- Search and list items by query and tags.
- Fetch full metadata for a single item.
- Create new items with core bibliographic metadata.
- Upload PDF attachments and link them to existing items.

## Security Model

- Auth is provided by environment variables only.
- Logs are structured JSON with redaction for sensitive values.
- No credentials are stored on disk by default.

## Transport

- MCP stdio (stdin/stdout), compatible with Docker-based MCP clients.
