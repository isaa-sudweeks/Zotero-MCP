# Agents

- Coordinator: Orchestrates subagents, sequencing, and task intake.
- Monitor: Reviews other agents' progress and proposes new tasks.
- Documentation: Maintains all user/agent-facing documentation.
- Task-1: Confirm project structure and Python runtime; define packaging/entrypoint.
- Task-2: Define MCP tool surfaces for v1.
- Task-3: Map Zotero API endpoints to tool behaviors.
- Task-4: Define request/response schemas for each MCP tool.
- Task-5: Implement Zotero auth handling via env vars only.
- Task-6: Implement MCP stdio server skeleton.
- Task-7: Implement library search/list tool.
- Task-8: Implement item metadata fetch tool.
- Task-9: Implement create-item tool.
- Task-10: Implement PDF attachment upload flow.
- Task-11: Add conservative retry/backoff and optional read cache.
- Task-12: Add structured logging with sensitive-data redaction.
- Task-13: Add unit tests for tool schemas and request validation.
- Task-14: Add integration tests with mocked Zotero responses.
- Task-15: Add Dockerfile and container entrypoint.
- Task-16: Add docker run examples and MCP client config example.
- Task-17: Validate Docker image runs locally.
- Task-18: Prepare Docker MCP Registry submission assets (metadata, docs, image).
- Task-19: Write a short release checklist for v1.

# Current Status (2026-02-06)

- Implemented: core MCP tools (search/get/create/upload), auth via env vars, stdio server, retry/backoff with `Retry-After`, read cache, structured logging with redaction + correlation IDs, pagination inputs, smoke test script, Dockerfile + run examples, registry assets, release checklist.
- Pending: local Docker build/run validation (blocked by daemon permissions), test execution in an environment with deps.

# Responsibilities / Scope / Files

Coordinator
- Responsibilities: Orchestrate agents, track dependencies, update tasks list.
- Scope: All tasks, sequencing decisions.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP/Tasks.md, /Volumes/T7 Touch/Personal Projects/Zotero MCP/agents.md

Monitor
- Responsibilities: Review agent progress, propose missing tasks, flag blockers.
- Scope: Non-editing; propose only.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP/Tasks.md, /Volumes/T7 Touch/Personal Projects/Zotero MCP/agents.md

Documentation
- Responsibilities: Maintain all user/agent-facing text.
- Scope: README, CONTRIBUTING, docs, and guidance files.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP/README.md, /Volumes/T7 Touch/Personal Projects/Zotero MCP/CONTRIBUTING.md, /Volumes/T7 Touch/Personal Projects/Zotero MCP/agents.md, /Volumes/T7 Touch/Personal Projects/Zotero MCP/Tasks.md

Task-1
- Responsibilities: Confirm project structure and Python runtime; define packaging/entrypoint.
- Scope: Build system and entrypoint.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP/pyproject.toml, /Volumes/T7 Touch/Personal Projects/Zotero MCP/README.md

Task-2
- Responsibilities: Define MCP tool surfaces for v1.
- Scope: Tool definitions for search/get/create/upload.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP/README.md, /Volumes/T7 Touch/Personal Projects/Zotero MCP/Tasks.md

Task-3
- Responsibilities: Map Zotero API endpoints to tool behaviors.
- Scope: API mapping notes/specs.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP/README.md, /Volumes/T7 Touch/Personal Projects/Zotero MCP/Tasks.md

Task-4
- Responsibilities: Define request/response schemas for each MCP tool.
- Scope: Schemas and validation rules.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP/README.md

Task-5
- Responsibilities: Implement Zotero auth handling via env vars only.
- Scope: Auth plumbing.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-6
- Responsibilities: Implement MCP stdio server skeleton.
- Scope: Server bootstrap.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-7
- Responsibilities: Implement library search/list tool.
- Scope: Search/list functionality.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-8
- Responsibilities: Implement item metadata fetch tool.
- Scope: Get item functionality.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-9
- Responsibilities: Implement create-item tool.
- Scope: Create item functionality.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-10
- Responsibilities: Implement PDF attachment upload flow.
- Scope: Attachment upload functionality.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-11
- Responsibilities: Add conservative retry/backoff and optional read cache.
- Scope: Client robustness.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-12
- Responsibilities: Add structured logging with sensitive-data redaction.
- Scope: Logging.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-13
- Responsibilities: Add unit tests for tool schemas and request validation.
- Scope: Unit tests.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-14
- Responsibilities: Add integration tests with mocked Zotero responses.
- Scope: Integration tests.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-15
- Responsibilities: Add Dockerfile and container entrypoint.
- Scope: Containerization.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP/Dockerfile

Task-16
- Responsibilities: Add docker run examples and MCP client config example.
- Scope: Docs for container usage.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP/README.md

Task-17
- Responsibilities: Validate Docker image runs locally.
- Scope: Local validation.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-18
- Responsibilities: Prepare Docker MCP Registry submission assets (metadata, docs, image).
- Scope: Registry assets.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP

Task-19
- Responsibilities: Write a short release checklist for v1.
- Scope: Release doc.
- Files: /Volumes/T7 Touch/Personal Projects/Zotero MCP/README.md
