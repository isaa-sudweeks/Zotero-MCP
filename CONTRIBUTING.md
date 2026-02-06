# Contributing

Thanks for your interest in improving Zotero MCP. The project is early-stage, so this file captures the intended workflow. If you hit gaps, open an issue or submit a PR with improvements.

## Getting Started

1. Fork and clone the repo.
2. Create a virtual environment.
3. Install dependencies from the project’s preferred package manager once it is defined.
4. Export required environment variables for local runs.

## Development Notes

- Use Python for all server logic.
- Do not commit API keys or tokens.
- Keep user data and attachment contents out of logs.

## Testing

Run unit tests and integration tests once the suite is added. The default test runner will be documented in the repo root.

## Pull Requests

1. Keep PRs small and focused.
2. Describe user-visible behavior changes in the PR description.
3. Include tests where possible.
