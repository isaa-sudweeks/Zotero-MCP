#!/usr/bin/env python3
"""Basic smoke test to verify the MCP stdio server boots."""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import subprocess
import sys
import time
from typing import Optional

DEFAULT_TIMEOUT = 5.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test: verify server startup.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Seconds to wait for startup log (default {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print server stderr while waiting.",
    )
    return parser.parse_args()


def _spawn_server() -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("ZOTERO_MCP_DEBUG", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")

    return subprocess.Popen(
        [sys.executable, "-m", "zotero_mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )


def _read_line(proc: subprocess.Popen, timeout: float) -> Optional[str]:
    if proc.stderr is None:
        return None
    ready, _, _ = select.select([proc.stderr], [], [], timeout)
    if not ready:
        return None
    return proc.stderr.readline()


def _shutdown(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=2)
    except Exception:
        proc.kill()


def main() -> int:
    args = _parse_args()
    deadline = time.monotonic() + args.timeout

    proc = _spawn_server()
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                print("Server exited before startup log.", file=sys.stderr)
                return 2

            remaining = max(0.0, deadline - time.monotonic())
            line = _read_line(proc, min(0.2, remaining))
            if not line:
                continue

            if args.verbose:
                print(line.rstrip())

            line = line.strip()
            if not line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if payload.get("event") == "server.start":
                print("OK: server.start event received")
                return 0

        print(f"Timeout waiting for startup log after {args.timeout}s.", file=sys.stderr)
        return 1
    finally:
        _shutdown(proc)


if __name__ == "__main__":
    raise SystemExit(main())
