#!/usr/bin/env sh
set -e

# Allow the container to run arbitrary commands, defaulting to the MCP server.
if [ "$#" -eq 0 ]; then
  set -- python -m zotero_mcp
fi

exec "$@"
