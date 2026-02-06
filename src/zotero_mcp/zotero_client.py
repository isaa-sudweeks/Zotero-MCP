"""Zotero API client helpers (minimal, stdlib only)."""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import random
import re
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .logging_utils import Timer, configure_logging, log_event

logger = configure_logging()

DEFAULT_UPLOAD_MAX_BYTES = 50 * 1024 * 1024

_DOI_PREFIXES = (
    "doi:",
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
)
_DOI_ID_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
_ARXIV_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?arxiv\.org/(?:abs|pdf)/(.+)", re.IGNORECASE)
_ARXIV_URL_FULL_RE = re.compile(r"^(?:https?://)?(?:www\.)?arxiv\.org/(?:abs|pdf)/(.+)$", re.IGNORECASE)
_ARXIV_ID_RE = re.compile(r"^(?P<core>[a-z\\-]+/\\d{7}|\\d{4}\\.\\d{4,5})(?P<version>v\\d+)?$", re.IGNORECASE)
_ARXIV_EXTRA_RE = re.compile(r"(?:^|\\s)arxiv(?:\\s*id)?\\s*[:=]\\s*(\\S+)", re.IGNORECASE)
_DOI_EXTRA_RE = re.compile(r"(?:^|\\s)doi\\s*[:=]\\s*(\\S+)", re.IGNORECASE)

class ZoteroError(RuntimeError):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class ZoteroConfig:
    api_key: str
    user_id: str
    api_base: str


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int
    base_delay: float
    max_delay: float


@dataclass(frozen=True)
class ReadCacheConfig:
    enabled: bool
    ttl_seconds: float
    max_entries: int


def load_config_from_env() -> ZoteroConfig:
    api_key = os.environ.get("ZOTERO_API_KEY")
    user_id = os.environ.get("ZOTERO_USER_ID")
    api_base = os.environ.get("ZOTERO_API_BASE", "https://api.zotero.org")
    if not api_key or not user_id:
        log_event(
            logger,
            level=logging.WARNING,
            event="auth.missing",
            missing=[key for key in ("ZOTERO_API_KEY", "ZOTERO_USER_ID") if not os.environ.get(key)],
        )
        raise ZoteroError(
            "ZOTERO_AUTH_ERROR",
            "Zotero credentials missing. Set ZOTERO_API_KEY and ZOTERO_USER_ID.",
            {"missing": [key for key in ("ZOTERO_API_KEY", "ZOTERO_USER_ID") if not os.environ.get(key)]},
        )
    return ZoteroConfig(api_key=api_key, user_id=user_id, api_base=api_base.rstrip("/"))


def _load_retry_config() -> RetryConfig:
    max_attempts = int(os.environ.get("ZOTERO_RETRY_MAX_ATTEMPTS", "3"))
    base_delay = float(os.environ.get("ZOTERO_RETRY_BASE_DELAY", "0.5"))
    max_delay = float(os.environ.get("ZOTERO_RETRY_MAX_DELAY", "4.0"))
    if max_attempts < 1:
        max_attempts = 1
    if base_delay < 0:
        base_delay = 0.0
    if max_delay < base_delay:
        max_delay = base_delay
    return RetryConfig(max_attempts=max_attempts, base_delay=base_delay, max_delay=max_delay)


def _load_read_cache_config() -> ReadCacheConfig:
    enabled = os.environ.get("ZOTERO_READ_CACHE", "0") == "1"
    ttl_seconds = float(os.environ.get("ZOTERO_READ_CACHE_TTL", "30"))
    max_entries = int(os.environ.get("ZOTERO_READ_CACHE_MAX", "128"))
    if ttl_seconds <= 0:
        ttl_seconds = 0.0
    if max_entries < 1:
        max_entries = 1
    return ReadCacheConfig(enabled=enabled, ttl_seconds=ttl_seconds, max_entries=max_entries)


def load_upload_max_bytes() -> int:
    raw = os.environ.get("ZOTERO_UPLOAD_MAX_BYTES")
    if not raw:
        return DEFAULT_UPLOAD_MAX_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_UPLOAD_MAX_BYTES
    return value if value > 0 else DEFAULT_UPLOAD_MAX_BYTES


def normalize_doi(value: str) -> str:
    raw = value.strip()
    lowered = raw.lower()
    for prefix in _DOI_PREFIXES:
        if lowered.startswith(prefix):
            return raw[len(prefix) :].strip().lower()
    return raw.lower()


def extract_exact_doi_query(query: str) -> Optional[str]:
    if not isinstance(query, str):
        return None
    raw = query.strip()
    if not raw:
        return None
    lowered = raw.lower()
    candidate = raw
    for prefix in _DOI_PREFIXES:
        if lowered.startswith(prefix):
            candidate = raw[len(prefix) :].strip()
            break
    if not candidate or any(ch.isspace() for ch in candidate):
        return None
    if not _DOI_ID_RE.match(candidate):
        return None
    return normalize_doi(candidate)


def extract_exact_arxiv_query(query: str) -> Optional[Tuple[str, Optional[str]]]:
    if not isinstance(query, str):
        return None
    raw = query.strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered.startswith("arxiv:"):
        raw = raw.split(":", 1)[1].strip()
    match = _ARXIV_URL_FULL_RE.match(raw)
    if match:
        raw = match.group(1)
    if not raw or any(ch.isspace() for ch in raw):
        return None
    if raw.lower().endswith(".pdf"):
        raw = raw[:-4]
    raw = raw.strip()
    match = _ARXIV_ID_RE.match(raw)
    if not match:
        return None
    core = match.group("core").lower()
    version = match.group("version")
    if version:
        version = version.lower()
    return core, version


def parse_arxiv_id(value: str) -> Optional[Tuple[str, Optional[str]]]:
    raw = value.strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered.startswith("arxiv:"):
        raw = raw.split(":", 1)[1].strip()
    match = _ARXIV_URL_RE.search(raw)
    if match:
        raw = match.group(1)
    if raw.lower().endswith(".pdf"):
        raw = raw[:-4]
    raw = raw.strip()
    match = _ARXIV_ID_RE.match(raw)
    if not match:
        return None
    core = match.group("core").lower()
    version = match.group("version")
    if version:
        version = version.lower()
    return core, version


def filter_items_exact_match(
    items: Iterable[Dict[str, Any]],
    *,
    doi: Optional[str] = None,
    arxiv_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    normalized_doi = normalize_doi(doi) if doi else None
    parsed_arxiv = parse_arxiv_id(arxiv_id) if arxiv_id else None
    if arxiv_id and not parsed_arxiv:
        return []
    output: List[Dict[str, Any]] = []
    for item in items:
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        if normalized_doi:
            if not _item_matches_doi(data, normalized_doi):
                continue
        if parsed_arxiv:
            if not _item_matches_arxiv(data, parsed_arxiv):
                continue
        output.append(item)
    return output


def _item_matches_doi(data: Dict[str, Any], normalized_doi: str) -> bool:
    doi = data.get("DOI")
    if isinstance(doi, str) and normalize_doi(doi) == normalized_doi:
        return True
    extra = data.get("extra")
    if isinstance(extra, str):
        for match in _DOI_EXTRA_RE.finditer(extra):
            if normalize_doi(match.group(1)) == normalized_doi:
                return True
    return False


def _item_matches_arxiv(data: Dict[str, Any], parsed: Tuple[str, Optional[str]]) -> bool:
    target_core, target_version = parsed
    candidates: List[str] = []
    archive_id = data.get("archiveID") or data.get("archiveId")
    if isinstance(archive_id, str) and archive_id.strip():
        candidates.append(archive_id)
    extra = data.get("extra")
    if isinstance(extra, str):
        candidates.extend(match.group(1) for match in _ARXIV_EXTRA_RE.finditer(extra))
    for candidate in candidates:
        parsed_candidate = parse_arxiv_id(candidate)
        if not parsed_candidate:
            continue
        candidate_core, candidate_version = parsed_candidate
        if candidate_core != target_core:
            continue
        if target_version is None:
            return True
        if candidate_version == target_version:
            return True
    return False


def infer_content_type(file_path: str) -> str:
    guess, _ = mimetypes.guess_type(file_path)
    if guess:
        return guess
    return "application/octet-stream"


def validate_upload_file(file_path: str) -> os.stat_result:
    if not os.path.exists(file_path):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "file_path does not exist.")
    if not os.path.isfile(file_path):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "file_path must point to a local file.")
    if not os.access(file_path, os.R_OK):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "file_path is not readable.")
    stat = os.stat(file_path)
    max_bytes = load_upload_max_bytes()
    if stat.st_size > max_bytes:
        raise ZoteroError(
            "ZOTERO_VALIDATION_ERROR",
            "file_path exceeds upload size limit.",
            {"size": stat.st_size, "max_bytes": max_bytes},
        )
    return stat


def _filename_from_content_disposition(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    for part in value.split(";"):
        part = part.strip()
        lowered = part.lower()
        if lowered.startswith("filename*=") or lowered.startswith("filename="):
            name = part.split("=", 1)[1].strip()
            if name.lower().startswith("utf-8''"):
                name = name[7:]
            name = name.strip("\"'")
            if name:
                return name
    return None


def _filename_from_url(file_url: str) -> Optional[str]:
    parsed = urllib.parse.urlparse(file_url)
    name = os.path.basename(parsed.path or "")
    return name or None


def _read_response_bytes(response: Any, *, max_bytes: int, source_label: str) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            size = int(content_length)
        except ValueError:
            size = None
        if size is not None and size > max_bytes:
            raise ZoteroError(
                "ZOTERO_VALIDATION_ERROR",
                f"{source_label} exceeds upload size limit.",
                {"size": size, "max_bytes": max_bytes},
            )
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            raise ZoteroError(
                "ZOTERO_VALIDATION_ERROR",
                f"{source_label} exceeds upload size limit.",
                {"size": total, "max_bytes": max_bytes},
            )
    return b"".join(chunks)


def _download_file_bytes(file_url: str) -> Tuple[bytes, Optional[str], Optional[str]]:
    max_bytes = load_upload_max_bytes()
    request = urllib.request.Request(url=file_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            file_bytes = _read_response_bytes(response, max_bytes=max_bytes, source_label="file_url")
            content_type = response.headers.get("Content-Type")
            filename = _filename_from_content_disposition(response.headers.get("Content-Disposition"))
            if not filename:
                filename = _filename_from_url(file_url)
            return file_bytes, filename, content_type
    except urllib.error.HTTPError as exc:
        status = exc.code
        payload = exc.read().decode("utf-8") if exc.fp else ""
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Download failed.", {"status": status, "body": payload}) from exc
    except urllib.error.URLError as exc:
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Download failed.", {"reason": str(exc)}) from exc


def _normalize_arxiv_id(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "arxiv_id is required and must be a non-empty string.")
    lowered = raw.lower()
    if lowered.startswith("arxiv:"):
        raw = raw.split(":", 1)[1].strip()
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme in ("http", "https"):
        path = parsed.path or ""
        if "/abs/" in path:
            raw = path.split("/abs/", 1)[1]
        elif "/pdf/" in path:
            raw = path.split("/pdf/", 1)[1]
        else:
            raw = path.lstrip("/")
        raw = raw.split("?", 1)[0].split("#", 1)[0]
    raw = raw.strip()
    if raw.lower().endswith(".pdf"):
        raw = raw[:-4]
    if not raw:
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "Unable to parse arXiv identifier.")
    return raw


def _build_arxiv_pdf_url(arxiv_id: str) -> str:
    encoded = urllib.parse.quote(arxiv_id, safe="/")
    return f"https://arxiv.org/pdf/{encoded}.pdf"


def _fetch_arxiv_pdf_to_temp(arxiv_id_or_url: str) -> tuple[str, str, str]:
    arxiv_id = _normalize_arxiv_id(arxiv_id_or_url)
    pdf_url = _build_arxiv_pdf_url(arxiv_id)
    request = urllib.request.Request(pdf_url, headers={"User-Agent": "zotero-mcp"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status < 200 or response.status >= 300:
                payload = response.read().decode("utf-8", errors="replace")
                _raise_for_http_error(response.status, payload, response.headers)
                raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "arXiv PDF request failed.", {"status": response.status})
            content_length = response.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                max_bytes = load_upload_max_bytes()
                if int(content_length) > max_bytes:
                    raise ZoteroError(
                        "ZOTERO_VALIDATION_ERROR",
                        "arXiv PDF exceeds upload size limit.",
                        {"size": int(content_length), "max_bytes": max_bytes},
                    )
            content_type = response.headers.get("Content-Type", "")
            payload_bytes = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        payload = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        _raise_for_http_error(status, payload, exc.headers)
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "arXiv PDF request failed.", {"status": status}) from exc
    except urllib.error.URLError as exc:
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "arXiv PDF request failed.", {"reason": str(exc)}) from exc

    if not payload_bytes:
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Empty arXiv PDF response.")

    max_bytes = load_upload_max_bytes()
    if len(payload_bytes) > max_bytes:
        raise ZoteroError(
            "ZOTERO_VALIDATION_ERROR",
            "arXiv PDF exceeds upload size limit.",
            {"size": len(payload_bytes), "max_bytes": max_bytes},
        )

    is_pdf_header = payload_bytes.startswith(b"%PDF")
    if "pdf" not in content_type.lower() and not is_pdf_header:
        raise ZoteroError(
            "ZOTERO_UPSTREAM_ERROR",
            "arXiv response was not a PDF.",
            {"content_type": content_type},
        )

    with tempfile.NamedTemporaryFile(prefix="arxiv_", suffix=".pdf", delete=False) as handle:
        handle.write(payload_bytes)
        temp_path = handle.name

    return temp_path, arxiv_id, pdf_url


_READ_CACHE: Dict[str, Tuple[float, Any, Dict[str, str]]] = {}


def _prune_cache(now: float, config: ReadCacheConfig) -> None:
    if not _READ_CACHE:
        return
    expired = [key for key, (expires_at, _data, _headers) in _READ_CACHE.items() if expires_at <= now]
    for key in expired:
        _READ_CACHE.pop(key, None)
    if len(_READ_CACHE) <= config.max_entries:
        return
    overflow = len(_READ_CACHE) - config.max_entries
    for key in list(_READ_CACHE.keys())[:overflow]:
        _READ_CACHE.pop(key, None)


def _get_cached_response(cache_key: str, config: ReadCacheConfig) -> Optional[Tuple[Any, Dict[str, str]]]:
    if not config.enabled or config.ttl_seconds <= 0:
        return None
    now = time.time()
    _prune_cache(now, config)
    entry = _READ_CACHE.get(cache_key)
    if not entry:
        return None
    expires_at, data, headers = entry
    if expires_at <= now:
        _READ_CACHE.pop(cache_key, None)
        return None
    return data, dict(headers)


def _store_cached_response(cache_key: str, data: Any, headers: Dict[str, str], config: ReadCacheConfig) -> None:
    if not config.enabled or config.ttl_seconds <= 0:
        return
    now = time.time()
    _prune_cache(now, config)
    _READ_CACHE[cache_key] = (now + config.ttl_seconds, data, dict(headers))


def _sleep_backoff(attempt: int, config: RetryConfig) -> None:
    if attempt <= 1:
        return
    delay = min(config.max_delay, config.base_delay * (2 ** (attempt - 2)))
    if delay <= 0:
        return
    jitter = delay * random.uniform(0.0, 0.2)
    time.sleep(delay + jitter)


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        seconds = float(text)
        if seconds < 0:
            return None
        return seconds
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    now = time.time()
    return max(0.0, dt.timestamp() - now)


def _sleep_retry_after(seconds: Optional[float]) -> None:
    if seconds is None:
        return
    if seconds <= 0:
        return
    time.sleep(seconds)


def _should_retry_http(status: int) -> bool:
    if status == 429:
        return True
    if 500 <= status <= 599:
        return True
    return False


def _normalize_headers(headers: Optional[Any]) -> Dict[str, str]:
    if not headers:
        return {}
    try:
        return {str(key).lower(): str(value) for key, value in headers.items()}
    except Exception:
        return {}


def _build_http_error_details(status: int, payload: str, headers: Optional[Any]) -> Dict[str, Any]:
    details: Dict[str, Any] = {"status": status}
    if payload:
        details["body"] = payload
    normalized = _normalize_headers(headers)
    retry_after = normalized.get("retry-after")
    if retry_after:
        details["retry_after"] = retry_after
    request_id = normalized.get("x-zotero-requestid") or normalized.get("x-zotero-request-id")
    if request_id:
        details["request_id"] = request_id
    return details


def _raise_for_http_error(status: int, payload: str, headers: Optional[Any]) -> None:
    details = _build_http_error_details(status, payload, headers)
    if status == 401 or status == 403:
        raise ZoteroError("ZOTERO_AUTH_ERROR", "Zotero authentication failed.", details)
    if status == 404:
        raise ZoteroError("ZOTERO_NOT_FOUND", "Zotero resource not found.", details)
    if status == 429:
        raise ZoteroError("ZOTERO_RATE_LIMITED", "Zotero rate limit exceeded.", details)
    if status in (400, 409, 412, 413, 415, 422):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "Zotero rejected the request.", details)
    if 500 <= status <= 599:
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero service error.", details)
    raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero request failed.", details)


def _build_query(params: Iterable[Tuple[str, str]]) -> str:
    return urllib.parse.urlencode(list(params), doseq=True)


def _request_json_any(
    *,
    config: ZoteroConfig,
    method: str,
    path: str,
    query: Optional[Iterable[Tuple[str, str]]] = None,
    body: Optional[Any] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Tuple[Any, Dict[str, str]]:
    timer = Timer()
    url = f"{config.api_base}{path}"
    if query:
        url = f"{url}?{_build_query(query)}"
    headers = {
        "Zotero-API-Key": config.api_key,
        "Zotero-API-Version": "3",
    }
    if extra_headers:
        headers.update(extra_headers)
    data: Optional[bytes] = None
    if body is not None:
        if isinstance(body, (bytes, bytearray)):
            data = bytes(body)
        else:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

    retry_config = _load_retry_config()
    cache_config = _load_read_cache_config()
    cache_key = f"{method}:{url}"
    if method.upper() == "GET" and body is None:
        cached = _get_cached_response(cache_key, cache_config)
        if cached is not None:
            log_event(
                logger,
                level=logging.DEBUG,
                event="zotero.cache_hit",
                method=method,
                path=path,
                secrets=[config.api_key],
            )
            return cached

    last_error: Optional[Exception] = None
    retry_after_seconds: Optional[float] = None
    for attempt in range(1, retry_config.max_attempts + 1):
        if retry_after_seconds is not None:
            log_event(
                logger,
                level=logging.INFO,
                event="zotero.retry_after",
                method=method,
                path=path,
                seconds=retry_after_seconds,
                attempt=attempt,
                secrets=[config.api_key],
            )
            _sleep_retry_after(retry_after_seconds)
            retry_after_seconds = None
        else:
            _sleep_backoff(attempt, retry_config)
        request = urllib.request.Request(url=url, method=method, headers=headers, data=data)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body_text = response.read().decode("utf-8")
                payload = json.loads(body_text) if body_text else None
                headers_out = {k.lower(): v for k, v in response.headers.items()}
                headers_out["status"] = str(response.status)
                if method.upper() == "GET" and body is None:
                    _store_cached_response(cache_key, payload, headers_out, cache_config)
                log_event(
                    logger,
                    level=logging.INFO,
                    event="zotero.request",
                    method=method,
                    path=path,
                    status=response.status,
                    attempt=attempt,
                    duration_ms=timer.elapsed_ms(),
                    secrets=[config.api_key],
                )
                return payload, headers_out
        except urllib.error.HTTPError as exc:
            status = exc.code
            payload = exc.read().decode("utf-8") if exc.fp else ""
            details = _build_http_error_details(status, payload, exc.headers)
            log_event(
                logger,
                level=logging.WARNING,
                event="zotero.request_error",
                method=method,
                path=path,
                status=status,
                attempt=attempt,
                duration_ms=timer.elapsed_ms(),
                secrets=[config.api_key],
            )
            if status == 429:
                retry_after_seconds = _parse_retry_after(details.get("retry_after"))
            if _should_retry_http(status) and attempt < retry_config.max_attempts:
                last_error = exc
                continue
            _raise_for_http_error(status, payload, exc.headers)
            raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero request failed.", details) from exc
        except urllib.error.URLError as exc:
            log_event(
                logger,
                level=logging.WARNING,
                event="zotero.request_error",
                method=method,
                path=path,
                status=None,
                attempt=attempt,
                duration_ms=timer.elapsed_ms(),
                secrets=[config.api_key],
            )
            retry_after_seconds = None
            if attempt < retry_config.max_attempts:
                last_error = exc
                continue
            raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero request failed.", {"reason": str(exc)}) from exc

    if last_error:
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero request failed.", {"reason": str(last_error)})
    raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero request failed.", {"reason": "unknown"})


def _request_json(
    *,
    config: ZoteroConfig,
    method: str,
    path: str,
    query: Optional[Iterable[Tuple[str, str]]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    data, headers = _request_json_any(config=config, method=method, path=path, query=query)
    if data is None:
        return [], headers
    if not isinstance(data, list):
        raise ZoteroError(
            "ZOTERO_UPSTREAM_ERROR",
            "Unexpected Zotero response format.",
            {"status": headers.get("status")},
        )
    return data, headers


def _request_json_object(
    *,
    config: ZoteroConfig,
    method: str,
    path: str,
    query: Optional[Iterable[Tuple[str, str]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    timer = Timer()
    url = f"{config.api_base}{path}"
    if query:
        url = f"{url}?{_build_query(query)}"
    headers = {
        "Zotero-API-Key": config.api_key,
        "Zotero-API-Version": "3",
    }

    retry_config = _load_retry_config()
    cache_config = _load_read_cache_config()
    cache_key = f"{method}:{url}"
    if method.upper() == "GET":
        cached = _get_cached_response(cache_key, cache_config)
        if cached is not None:
            data, headers_out = cached
            if isinstance(data, dict):
                log_event(
                    logger,
                    level=logging.DEBUG,
                    event="zotero.cache_hit",
                    method=method,
                    path=path,
                    secrets=[config.api_key],
                )
                return data, headers_out

    last_error: Optional[Exception] = None
    retry_after_seconds: Optional[float] = None
    for attempt in range(1, retry_config.max_attempts + 1):
        if retry_after_seconds is not None:
            log_event(
                logger,
                level=logging.INFO,
                event="zotero.retry_after",
                method=method,
                path=path,
                seconds=retry_after_seconds,
                attempt=attempt,
                secrets=[config.api_key],
            )
            _sleep_retry_after(retry_after_seconds)
            retry_after_seconds = None
        else:
            _sleep_backoff(attempt, retry_config)
        request = urllib.request.Request(url=url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                data = json.loads(body) if body else {}
                if not isinstance(data, dict):
                    raise ZoteroError(
                        "ZOTERO_UPSTREAM_ERROR",
                        "Unexpected Zotero response format.",
                        {"status": response.status},
                    )
                headers_out = {k.lower(): v for k, v in response.headers.items()}
                if method.upper() == "GET":
                    _store_cached_response(cache_key, data, headers_out, cache_config)
                log_event(
                    logger,
                    level=logging.INFO,
                    event="zotero.request",
                    method=method,
                    path=path,
                    status=response.status,
                    attempt=attempt,
                    duration_ms=timer.elapsed_ms(),
                    secrets=[config.api_key],
                )
                return data, headers_out
        except urllib.error.HTTPError as exc:
            status = exc.code
            payload = exc.read().decode("utf-8") if exc.fp else ""
            details = _build_http_error_details(status, payload, exc.headers)
            log_event(
                logger,
                level=logging.WARNING,
                event="zotero.request_error",
                method=method,
                path=path,
                status=status,
                attempt=attempt,
                duration_ms=timer.elapsed_ms(),
                secrets=[config.api_key],
            )
            if status == 429:
                retry_after_seconds = _parse_retry_after(details.get("retry_after"))
            if _should_retry_http(status) and attempt < retry_config.max_attempts:
                last_error = exc
                continue
            _raise_for_http_error(status, payload, exc.headers)
            raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero request failed.", details) from exc
        except urllib.error.URLError as exc:
            log_event(
                logger,
                level=logging.WARNING,
                event="zotero.request_error",
                method=method,
                path=path,
                status=None,
                attempt=attempt,
                duration_ms=timer.elapsed_ms(),
                secrets=[config.api_key],
            )
            retry_after_seconds = None
            if attempt < retry_config.max_attempts:
                last_error = exc
                continue
            raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero request failed.", {"reason": str(exc)}) from exc

    if last_error:
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero request failed.", {"reason": str(last_error)})
    raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero request failed.", {"reason": "unknown"})


def parse_total_results(headers: Dict[str, str]) -> Optional[int]:
    for key in ("total-results", "totalresults"):
        if key in headers:
            try:
                return int(headers[key])
            except ValueError:
                return None
    return None


def parse_next_start(headers: Dict[str, str]) -> Optional[int]:
    link_header = headers.get("link")
    if not link_header:
        return None
    parts = [part.strip() for part in link_header.split(",")]
    for part in parts:
        if 'rel="next"' not in part:
            continue
        start_index = part.find("start=")
        if start_index == -1:
            continue
        value = []
        for ch in part[start_index + len("start=") :]:
            if ch.isdigit():
                value.append(ch)
            else:
                break
        if value:
            try:
                return int("".join(value))
            except ValueError:
                return None
    return None


def search_items(
    *,
    config: ZoteroConfig,
    query: str,
    limit: int,
    sort: str,
    start: int,
    tags: Optional[List[str]],
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    params: List[Tuple[str, str]] = [
        ("q", query),
        ("limit", str(limit)),
        ("sort", sort),
    ]
    if start:
        params.append(("start", str(start)))
    if tags:
        for tag in tags:
            params.append(("tag", tag))
    path = f"/users/{urllib.parse.quote(config.user_id)}/items"
    return _request_json(config=config, method="GET", path=path, query=params)


def get_item_template(*, config: ZoteroConfig, item_type: str) -> Dict[str, Any]:
    query = [("itemType", item_type)]
    data, _ = _request_json_any(config=config, method="GET", path="/items/new", query=query)
    if not isinstance(data, dict):
        raise ZoteroError(
            "ZOTERO_UPSTREAM_ERROR",
            "Unexpected Zotero response format.",
        )
    return data


def create_item(*, config: ZoteroConfig, item: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps([item]).encode("utf-8")
    path = f"/users/{urllib.parse.quote(config.user_id)}/items"
    data, _ = _request_json_any(
        config=config,
        method="POST",
        path=path,
        body=body,
        extra_headers={"Content-Type": "application/json"},
    )
    if not isinstance(data, dict):
        raise ZoteroError(
            "ZOTERO_UPSTREAM_ERROR",
            "Unexpected Zotero response format.",
        )
    return data


def get_item(
    *,
    config: ZoteroConfig,
    item_key: str,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    path = f"/users/{urllib.parse.quote(config.user_id)}/items/{urllib.parse.quote(item_key)}"
    return _request_json_object(config=config, method="GET", path=path)


def list_item_children(
    *,
    config: ZoteroConfig,
    item_key: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    path = f"/users/{urllib.parse.quote(config.user_id)}/items/{urllib.parse.quote(item_key)}/children"
    return _request_json(config=config, method="GET", path=path)


def list_collections(
    *,
    config: ZoteroConfig,
    limit: int,
    start: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    params: List[Tuple[str, str]] = [
        ("limit", str(limit)),
    ]
    if start:
        params.append(("start", str(start)))
    path = f"/users/{urllib.parse.quote(config.user_id)}/collections"
    return _request_json(config=config, method="GET", path=path, query=params)


def add_item_to_collection(
    *,
    config: ZoteroConfig,
    collection_key: str,
    item_key: str,
) -> Tuple[Any, Dict[str, str]]:
    path = (
        f"/users/{urllib.parse.quote(config.user_id)}/collections/{urllib.parse.quote(collection_key)}/items"
    )
    body = [item_key]
    return _request_json_any(config=config, method="POST", path=path, body=body)


def _coerce_template(template: Any) -> Dict[str, Any]:
    if isinstance(template, dict):
        return dict(template)
    if isinstance(template, list) and template and isinstance(template[0], dict):
        return dict(template[0])
    raise ZoteroError(
        "ZOTERO_UPSTREAM_ERROR",
        "Unexpected Zotero template response format.",
        {"type": type(template).__name__},
    )


def _extract_created_key(payload: Any) -> Tuple[str, int]:
    if not isinstance(payload, dict):
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Unexpected Zotero create response.", {"type": type(payload).__name__})
    successful = payload.get("successful")
    if isinstance(successful, dict):
        for entry in successful.values():
            if isinstance(entry, dict) and entry.get("key"):
                return str(entry["key"]), int(entry.get("version", 0))
    raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero create failed.", {"response": payload})


def _upload_multipart(
    *,
    upload_url: str,
    prefix: str,
    suffix: str,
    file_bytes: bytes,
    content_type: Optional[str],
) -> None:
    data = prefix.encode("utf-8") + file_bytes + suffix.encode("utf-8")
    headers: Dict[str, str] = {}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url=upload_url, method="POST", headers=headers, data=data)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status < 200 or response.status >= 300:
                payload = response.read().decode("utf-8")
                _raise_for_http_error(response.status, payload, response.headers)
                raise ZoteroError(
                    "ZOTERO_UPSTREAM_ERROR",
                    "Upload failed.",
                    {"status": response.status},
                )
    except urllib.error.HTTPError as exc:
        status = exc.code
        payload = exc.read().decode("utf-8") if exc.fp else ""
        _raise_for_http_error(status, payload, exc.headers)
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Upload failed.", {"status": status, "body": payload}) from exc
    except urllib.error.URLError as exc:
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Upload failed.", {"reason": str(exc)}) from exc


def upload_attachment(
    *,
    config: ZoteroConfig,
    item_key: str,
    file_path: Optional[str],
    file_url: Optional[str],
    file_bytes: Optional[bytes],
    filename: Optional[str],
    title: Optional[str],
    content_type: Optional[str],
) -> Dict[str, Any]:
    resolved_content_type = content_type.strip() if isinstance(content_type, str) and content_type.strip() else None
    resolved_filename = filename.strip() if isinstance(filename, str) and filename.strip() else None
    resolved_mtime = time.time()
    size = 0
    if file_path:
        stat = validate_upload_file(file_path)
        resolved_filename = os.path.basename(file_path)
        with open(file_path, "rb") as handle:
            file_bytes = handle.read()
        size = stat.st_size
        resolved_mtime = stat.st_mtime
    elif file_url:
        downloaded_bytes, inferred_filename, inferred_content_type = _download_file_bytes(file_url)
        file_bytes = downloaded_bytes
        if not resolved_filename and inferred_filename:
            resolved_filename = inferred_filename
        if resolved_content_type is None and inferred_content_type:
            resolved_content_type = inferred_content_type.split(";", 1)[0].strip() or None
        size = len(file_bytes)
    elif file_bytes is not None:
        max_bytes = load_upload_max_bytes()
        if len(file_bytes) > max_bytes:
            raise ZoteroError(
                "ZOTERO_VALIDATION_ERROR",
                "file_bytes exceeds upload size limit.",
                {"size": len(file_bytes), "max_bytes": max_bytes},
            )
        size = len(file_bytes)
    else:
        raise ZoteroError(
            "ZOTERO_VALIDATION_ERROR",
            "Provide exactly one of file_path, file_url, or file_bytes.",
        )

    if not resolved_filename:
        resolved_filename = "attachment"
    resolved_title = title.strip() if isinstance(title, str) and title.strip() else resolved_filename
    if resolved_content_type is None:
        resolved_content_type = infer_content_type(resolved_filename)

    md5_hash = hashlib.md5(file_bytes).hexdigest()
    template_raw, _ = _request_json_any(
        config=config,
        method="GET",
        path="/items/new",
        query=[("itemType", "attachment"), ("linkMode", "imported_file")],
    )
    template = _coerce_template(template_raw)
    template.update(
        {
            "parentItem": item_key,
            "linkMode": "imported_file",
            "title": resolved_title,
            "filename": resolved_filename,
            "contentType": resolved_content_type,
        }
    )

    created_payload, _ = _request_json_any(
        config=config,
        method="POST",
        path=f"/users/{urllib.parse.quote(config.user_id)}/items",
        body=[template],
    )
    attachment_key, attachment_version = _extract_created_key(created_payload)

    auth_payload, _ = _request_json_any(
        config=config,
        method="POST",
        path=f"/users/{urllib.parse.quote(config.user_id)}/items/{urllib.parse.quote(attachment_key)}/file",
        body={
            "md5": md5_hash,
            "filename": resolved_filename,
            "filesize": size,
            "mtime": int(resolved_mtime),
        },
    )
    if not isinstance(auth_payload, dict):
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Unexpected upload auth response.", {"type": type(auth_payload).__name__})

    upload_url = auth_payload.get("url")
    prefix = auth_payload.get("prefix")
    suffix = auth_payload.get("suffix")
    upload_key = auth_payload.get("uploadKey")
    upload_content_type = auth_payload.get("contentType")
    if not all(isinstance(value, str) and value for value in (upload_url, prefix, suffix, upload_key)):
        raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Upload auth response missing fields.", {"response": auth_payload})

    _upload_multipart(
        upload_url=upload_url,
        prefix=prefix,
        suffix=suffix,
        file_bytes=file_bytes,
        content_type=upload_content_type,
    )

    _request_json_any(
        config=config,
        method="POST",
        path=f"/users/{urllib.parse.quote(config.user_id)}/items/{urllib.parse.quote(attachment_key)}/file",
        body={"uploadKey": upload_key},
    )

    return {
        "attachment_key": attachment_key,
        "parent_item_key": item_key,
        "title": resolved_title,
        "content_type": resolved_content_type,
        "size": size,
        "version": attachment_version,
    }


def attach_arxiv_pdf(
    *,
    config: ZoteroConfig,
    item_key: str,
    arxiv_id: str,
    title: Optional[str],
) -> Dict[str, Any]:
    temp_path, resolved_arxiv_id, pdf_url = _fetch_arxiv_pdf_to_temp(arxiv_id)
    try:
        payload = upload_attachment(
            config=config,
            item_key=item_key,
            file_path=temp_path,
            file_url=None,
            file_bytes=None,
            filename=None,
            title=title,
            content_type="application/pdf",
        )
    finally:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            log_event(
                logger,
                level=logging.WARNING,
                event="arxiv.cleanup_failed",
                error=str(exc),
            )
    payload["arxiv_id"] = resolved_arxiv_id
    payload["pdf_url"] = pdf_url
    return payload
