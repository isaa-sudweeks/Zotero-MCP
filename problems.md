# Problems

- Tests cannot run in this environment because the `mcp` dependency is not installed; `python -m pytest -q` fails with `ModuleNotFoundError: No module named 'mcp'`.
- `uv` is not available here, so `uv run --extra test python -m pytest -q` cannot be used.
- Installing test dependencies via `python -m pip install -e .[test]` failed due to lack of network access for build deps (`hatchling`).
- Docker image validation is blocked by lack of access to the Docker daemon: `permission denied while trying to connect to the docker API at unix:///Users/isaacsudweeks/.docker/run/docker.sock`.
