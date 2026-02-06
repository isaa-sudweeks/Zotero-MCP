"""Structured logging helpers with sensitive-data redaction."""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, MutableMapping, Optional

REDACTED = "[REDACTED]"

_correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "zotero_mcp_correlation_id",
    default=None,
)

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "body",
    "cookie",
    "set-cookie",
    "secret",
    "password",
    "response",
    "token",
    "zotero-api-key",
    "uploadkey",
    "prefix",
    "suffix",
    "file_path",
    "path",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_key(key: str) -> str:
    return key.lower().replace(" ", "_")


def _is_sensitive_key(key: str) -> bool:
    return _normalize_key(key) in _SENSITIVE_KEYS


def _redact_string(value: str, secrets: Optional[Iterable[str]]) -> str:
    if secrets:
        for secret in secrets:
            if secret and value == secret:
                return REDACTED
    return value


def redact(value: Any, *, secrets: Optional[Iterable[str]] = None) -> Any:
    if isinstance(value, Mapping):
        output: MutableMapping[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if _is_sensitive_key(key_str):
                output[key_str] = REDACTED
            else:
                output[key_str] = redact(item, secrets=secrets)
        return output
    if isinstance(value, list):
        return [redact(item, secrets=secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item, secrets=secrets) for item in value)
    if isinstance(value, set):
        return {redact(item, secrets=secrets) for item in value}
    if isinstance(value, str):
        return _redact_string(value, secrets)
    return value


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("zotero_mcp")
    if getattr(logger, "_configured", False):
        return logger

    level_name = os.getenv("ZOTERO_MCP_LOG_LEVEL", "INFO").upper()
    level = logging._nameToLevel.get(level_name, logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers = [handler]
    logger.propagate = False
    logger._configured = True  # type: ignore[attr-defined]
    return logger


def log_event(
    logger: logging.Logger,
    *,
    level: int,
    event: str,
    secrets: Optional[Iterable[str]] = None,
    **fields: Any,
) -> None:
    correlation_id = _correlation_id_var.get()
    payload = {
        "ts": _utc_now_iso(),
        "level": logging.getLevelName(level),
        "event": event,
        "service": "zotero-mcp",
    }
    if correlation_id:
        payload["correlation_id"] = correlation_id
    payload.update(fields)
    redacted = redact(payload, secrets=secrets)
    logger.log(level, json.dumps(redacted, separators=(",", ":")))


class Timer:
    def __init__(self) -> None:
        self._start = time.monotonic()

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._start) * 1000)


def set_correlation_id(value: Optional[str]) -> contextvars.Token[Optional[str]]:
    return _correlation_id_var.set(value)


def reset_correlation_id(token: contextvars.Token[Optional[str]]) -> None:
    _correlation_id_var.reset(token)


@contextlib.contextmanager
def correlation_id_scope(value: Optional[str]):
    token = set_correlation_id(value)
    try:
        yield
    finally:
        reset_correlation_id(token)
