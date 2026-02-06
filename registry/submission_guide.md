# Docker MCP Registry Submission Guide (Draft)

This folder contains draft submission assets for the Docker MCP Registry self-provided image flow. Update placeholders and align the metadata schema to the latest registry requirements before submission.

## Files

- `registry/metadata.json`: Draft metadata for the registry entry.
- `registry/description.md`: Long description used by the registry listing.
- `registry/usage.md`: Docker run and MCP client configuration examples.

## Update Checklist

- Replace `ghcr.io/your-org/zotero-mcp:0.1.0` with the published image name and tag.
- Confirm the version matches the image tag.
- Verify the tool list matches `src/zotero_mcp/server.py`.
- Update repository/homepage links if the project location changes.
- Align metadata fields and naming with the registry schema.

## Image Publishing Notes

- Build from `Dockerfile` and push to your registry.
- Ensure the entrypoint stays `/app/docker-entrypoint.sh` and the default command runs `python -m zotero_mcp`.
- Validate `docker run` with required env vars before submission.
