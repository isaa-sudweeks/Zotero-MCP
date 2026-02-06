"""MCP stdio server for Zotero tools (SDK-based)."""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import os
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from . import __version__
from .logging_utils import Timer, configure_logging, correlation_id_scope, log_event
from .zotero_client import (
    ZoteroError,
    add_item_to_collection,
    attach_arxiv_pdf,
    create_item,
    extract_exact_arxiv_query,
    extract_exact_doi_query,
    filter_items_exact_match,
    get_item,
    get_item_template,
    load_config_from_env,
    load_upload_max_bytes,
    list_collections,
    list_item_children,
    parse_arxiv_id,
    parse_next_start,
    parse_total_results,
    search_items,
    upload_attachment,
    validate_upload_file,
)

server = Server("zotero-mcp")
logger = configure_logging()

DEFAULT_SORT = "relevance"
FALLBACK_SORT = "dateModified"
KNOWN_SORT_VALUES = [
    "relevance",
    "dateAdded",
    "dateModified",
    "title",
    "creator",
    "date",
    "publisher",
    "publicationTitle",
    "itemType",
    "numChildren",
    "numTags",
    "language",
]


def _canonical_sort_value(value: str) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    lookup = {entry.lower(): entry for entry in KNOWN_SORT_VALUES}
    return lookup.get(value.lower())


def _tool_list() -> List[types.Tool]:
    return [
        types.Tool(
            name="zotero_list_collections",
            description="List collections in the personal Zotero library.",
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 25},
                    "start": {"type": "integer", "minimum": 0, "default": 0},
                },
            },
            outputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ok": {"type": "boolean"},
                    "data": {
                        "type": ["object", "null"],
                        "properties": {
                            "collections": {"type": "array"},
                            "total": {"type": "integer"},
                            "next_start": {"type": "integer"},
                        },
                    },
                    "error": {
                        "type": ["object", "null"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "details": {"type": "object"},
                        },
                    },
                },
                "required": ["ok", "data", "error"],
            },
        ),
        types.Tool(
            name="zotero_search_items",
            description="Search and list items in the personal Zotero library.",
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {"type": "string", "minLength": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 25},
                    "sort": {"type": "string", "default": DEFAULT_SORT},
                    "start": {"type": "integer", "minimum": 0, "default": 0},
                    "offset": {"type": "integer", "minimum": 0},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "uniqueItems": True,
                    },
                },
                "required": ["query"],
            },
            outputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ok": {"type": "boolean"},
                    "data": {
                        "type": ["object", "null"],
                        "properties": {
                            "items": {"type": "array"},
                            "total": {"type": "integer"},
                            "next_start": {"type": "integer"},
                            "sort_used": {"type": "string"},
                        },
                    },
                    "error": {
                        "type": ["object", "null"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "details": {"type": "object"},
                        },
                    },
                },
                "required": ["ok", "data", "error"],
            },
        ),
        types.Tool(
            name="zotero_get_sort_values",
            description="Return the server's known Zotero sort values and fallbacks.",
            inputSchema={"type": "object", "additionalProperties": False, "properties": {}},
            outputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ok": {"type": "boolean"},
                    "data": {
                        "type": ["object", "null"],
                        "additionalProperties": False,
                        "properties": {
                            "values": {"type": "array", "items": {"type": "string"}},
                            "default": {"type": "string"},
                            "fallback": {"type": "string"},
                        },
                        "required": ["values", "default", "fallback"],
                    },
                    "error": {
                        "type": ["object", "null"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "details": {"type": "object"},
                        },
                    },
                },
                "required": ["ok", "data", "error"],
            },
        ),
        types.Tool(
            name="zotero_get_item",
            description="Fetch metadata for a single item in the personal Zotero library.",
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "item_key": {"type": "string", "minLength": 1},
                },
                "required": ["item_key"],
            },
            outputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ok": {"type": "boolean"},
                    "data": {
                        "type": ["object", "null"],
                        "properties": {
                            "item": {"type": "object"},
                        },
                    },
                    "error": {
                        "type": ["object", "null"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "details": {"type": "object"},
                        },
                    },
                },
                "required": ["ok", "data", "error"],
            },
        ),
        types.Tool(
            name="zotero_create_item",
            description="Create a new item in the personal Zotero library.",
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "item_type": {"type": "string", "minLength": 1},
                    "title": {"type": "string", "minLength": 1},
                    "creators": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "creator_type": {"type": "string", "minLength": 1},
                                "name": {"type": "string", "minLength": 1},
                                "first_name": {"type": "string", "minLength": 1},
                                "last_name": {"type": "string", "minLength": 1},
                            },
                            "required": ["creator_type"],
                        },
                    },
                    "date": {"type": "string"},
                    "doi": {"type": "string"},
                    "url": {"type": "string"},
                    "abstract": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "uniqueItems": True,
                    },
                    "extra": {"type": "string"},
                },
                "required": ["item_type", "title"],
            },
            outputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ok": {"type": "boolean"},
                    "data": {
                        "type": ["object", "null"],
                        "properties": {
                            "item_key": {"type": "string"},
                            "version": {"type": "integer"},
                            "item": {"type": "object"},
                        },
                    },
                    "error": {
                        "type": ["object", "null"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "details": {"type": "object"},
                        },
                    },
                },
                "required": ["ok", "data", "error"],
            },
        ),
        types.Tool(
            name="zotero_upload_attachment",
            description=(
                "Upload a file attachment and link it to an existing item."
                " Content type is inferred when omitted."
            ),
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "item_key": {"type": "string", "minLength": 1},
                    "file_path": {"type": "string", "minLength": 1},
                    "file_url": {"type": "string", "minLength": 1},
                    "file_bytes_base64": {"type": "string", "minLength": 1},
                    "filename": {"type": "string", "minLength": 1},
                    "title": {"type": "string"},
                    "content_type": {"type": "string"},
                },
                "required": ["item_key"],
                "anyOf": [
                    {"required": ["item_key", "file_path"]},
                    {"required": ["item_key", "file_url"]},
                    {"required": ["item_key", "file_bytes_base64", "filename"]},
                ],
            },
            outputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ok": {"type": "boolean"},
                    "data": {
                        "type": ["object", "null"],
                        "properties": {
                            "attachment_key": {"type": "string"},
                            "parent_item_key": {"type": "string"},
                            "title": {"type": "string"},
                            "content_type": {"type": "string"},
                            "size": {"type": "integer"},
                            "version": {"type": "integer"},
                        },
                    },
                    "error": {
                        "type": ["object", "null"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "details": {"type": "object"},
                        },
                    },
                },
                "required": ["ok", "data", "error"],
            },
        ),
        types.Tool(
            name="zotero_attach_arxiv_pdf",
            description="Fetch an arXiv PDF and attach it to an existing item.",
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "item_key": {"type": "string", "minLength": 1},
                    "arxiv_id": {"type": "string", "minLength": 1},
                    "title": {"type": "string"},
                },
                "required": ["item_key", "arxiv_id"],
            },
            outputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ok": {"type": "boolean"},
                    "data": {
                        "type": ["object", "null"],
                        "properties": {
                            "attachment_key": {"type": "string"},
                            "parent_item_key": {"type": "string"},
                            "title": {"type": "string"},
                            "content_type": {"type": "string"},
                            "size": {"type": "integer"},
                            "version": {"type": "integer"},
                            "arxiv_id": {"type": "string"},
                            "pdf_url": {"type": "string"},
                        },
                    },
                    "error": {
                        "type": ["object", "null"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "details": {"type": "object"},
                        },
                    },
                },
                "required": ["ok", "data", "error"],
            },
        ),
        types.Tool(
            name="zotero_add_item_to_collection",
            description="Add an item to a collection by collection key or name.",
            inputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "item_key": {"type": "string", "minLength": 1},
                    "collection_key": {"type": "string", "minLength": 1},
                    "collection_name": {"type": "string", "minLength": 1},
                },
                "required": ["item_key"],
            },
            outputSchema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "ok": {"type": "boolean"},
                    "data": {
                        "type": ["object", "null"],
                        "properties": {
                            "item_key": {"type": "string"},
                            "collection_key": {"type": "string"},
                        },
                    },
                    "error": {
                        "type": ["object", "null"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                            "details": {"type": "object"},
                        },
                    },
                },
                "required": ["ok", "data", "error"],
            },
        ),
    ]


@server.list_tools()
async def list_tools() -> List[types.Tool]:
    return _tool_list()


def _normalize_creators(creators: Any) -> List[Dict[str, str]]:
    if not isinstance(creators, list):
        return []
    normalized: List[Dict[str, str]] = []
    for creator in creators:
        if not isinstance(creator, dict):
            continue
        creator_type = creator.get("creatorType")
        if not creator_type:
            continue
        entry: Dict[str, str] = {"creator_type": str(creator_type)}
        if creator.get("name"):
            entry["name"] = str(creator["name"])
        else:
            if creator.get("firstName"):
                entry["first_name"] = str(creator["firstName"])
            if creator.get("lastName"):
                entry["last_name"] = str(creator["lastName"])
        normalized.append(entry)
    return normalized


def _normalize_tags(tags: Any) -> List[str]:
    if not isinstance(tags, list):
        return []
    output: List[str] = []
    for tag in tags:
        if isinstance(tag, dict) and tag.get("tag"):
            output.append(str(tag["tag"]))
        elif isinstance(tag, str):
            output.append(tag)
    return output


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    return {
        "item_key": item.get("key", ""),
        "item_type": data.get("itemType", ""),
        "title": data.get("title", ""),
        "creators": _normalize_creators(data.get("creators")),
        "date": data.get("date", ""),
        "doi": data.get("DOI", ""),
        "url": data.get("url", ""),
        "abstract": data.get("abstractNote", ""),
        "tags": _normalize_tags(data.get("tags")),
        "extra": data.get("extra", ""),
        "version": item.get("version", 0),
    }


def _normalize_attachment(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    if data.get("itemType") != "attachment":
        return None
    attachment = {
        "attachment_key": item.get("key", ""),
        "title": data.get("title", ""),
    }
    content_type = data.get("contentType")
    if content_type:
        attachment["content_type"] = content_type
    size = data.get("fileSize") if data.get("fileSize") is not None else data.get("size")
    if isinstance(size, int):
        attachment["size"] = size
    return attachment


def _normalize_collection(collection: Dict[str, Any]) -> Dict[str, Any]:
    data = collection.get("data") if isinstance(collection.get("data"), dict) else {}
    meta = collection.get("meta") if isinstance(collection.get("meta"), dict) else {}
    payload: Dict[str, Any] = {
        "collection_key": collection.get("key", ""),
        "name": data.get("name", ""),
        "parent_key": data.get("parentCollection", ""),
        "version": collection.get("version", 0),
    }
    num_items = meta.get("numItems")
    if isinstance(num_items, int):
        payload["num_items"] = num_items
    return payload


def _validate_search_args(args: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "Arguments must be an object.")
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "query is required and must be a non-empty string.")
    limit = args.get("limit", 25)
    if not isinstance(limit, int):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "limit must be an integer.")
    if limit < 1 or limit > 100:
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "limit must be between 1 and 100.")
    sort = args.get("sort", DEFAULT_SORT)
    if not isinstance(sort, str) or not sort:
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "sort must be a non-empty string.")
    normalized_sort = _canonical_sort_value(sort)
    if normalized_sort:
        sort = normalized_sort
    start = args.get("start", 0)
    offset = args.get("offset")
    if start is None:
        start = 0
    if not isinstance(start, int):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "start must be an integer.")
    if start < 0:
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "start must be greater than or equal to 0.")
    if offset is not None:
        if not isinstance(offset, int):
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "offset must be an integer.")
        if offset < 0:
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "offset must be greater than or equal to 0.")
        if start and offset != start:
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "Provide only one of start or offset.")
        if not start:
            start = offset
    tags = args.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or not all(isinstance(tag, str) and tag for tag in tags):
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "tags must be an array of non-empty strings.")
        tags = list(dict.fromkeys(tags))
    return {"query": query.strip(), "limit": limit, "sort": sort, "start": start, "tags": tags}


def _validate_get_item_args(args: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "Arguments must be an object.")
    item_key = args.get("item_key")
    if not isinstance(item_key, str) or not item_key.strip():
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "item_key is required and must be a non-empty string.")
    return {"item_key": item_key.strip()}


def _validate_list_collections_args(args: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "Arguments must be an object.")
    limit = args.get("limit", 25)
    if not isinstance(limit, int):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "limit must be an integer.")
    if limit < 1 or limit > 100:
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "limit must be between 1 and 100.")
    start = args.get("start", 0)
    if start is None:
        start = 0
    if not isinstance(start, int):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "start must be an integer.")
    if start < 0:
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "start must be greater than or equal to 0.")
    return {"limit": limit, "start": start}


def _validate_add_item_to_collection_args(args: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "Arguments must be an object.")
    item_key = args.get("item_key")
    if not isinstance(item_key, str) or not item_key.strip():
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "item_key is required and must be a non-empty string.")
    collection_key = args.get("collection_key")
    if collection_key is not None:
        if not isinstance(collection_key, str) or not collection_key.strip():
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "collection_key must be a non-empty string when provided.")
        collection_key = collection_key.strip()
    collection_name = args.get("collection_name")
    if collection_name is not None:
        if not isinstance(collection_name, str) or not collection_name.strip():
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "collection_name must be a non-empty string when provided.")
        collection_name = collection_name.strip()
    if not collection_key and not collection_name:
        raise ZoteroError(
            "ZOTERO_VALIDATION_ERROR",
            "Provide collection_key or collection_name.",
        )
    return {"item_key": item_key.strip(), "collection_key": collection_key, "collection_name": collection_name}


def _resolve_collection_key_by_name(*, config, collection_name: str) -> str:
    normalized = collection_name.casefold()
    matches: List[str] = []
    start = 0
    while True:
        collections, headers = list_collections(config=config, limit=100, start=start)
        for collection in collections:
            data = collection.get("data") if isinstance(collection.get("data"), dict) else {}
            name = data.get("name", "")
            if isinstance(name, str) and name.casefold() == normalized:
                key = collection.get("key")
                if isinstance(key, str) and key:
                    matches.append(key)
        next_start = parse_next_start(headers)
        if next_start is None:
            break
        start = next_start
    if not matches:
        raise ZoteroError("ZOTERO_NOT_FOUND", "Collection not found.", {"collection_name": collection_name})
    unique_matches = sorted(set(matches))
    if len(unique_matches) > 1:
        raise ZoteroError(
            "ZOTERO_AMBIGUOUS_COLLECTION",
            "Multiple collections matched the provided name. Use collection_key instead.",
            {"collection_name": collection_name, "matches": unique_matches},
        )
    return unique_matches[0]


def _validate_create_args(args: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "Arguments must be an object.")
    item_type = args.get("item_type")
    if not isinstance(item_type, str) or not item_type.strip():
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "item_type is required and must be a non-empty string.")
    title = args.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "title is required and must be a non-empty string.")
    creators = args.get("creators")
    if creators is not None:
        if not isinstance(creators, list):
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "creators must be an array.")
        for creator in creators:
            if not isinstance(creator, dict):
                raise ZoteroError("ZOTERO_VALIDATION_ERROR", "creators entries must be objects.")
            creator_type = creator.get("creator_type")
            if not isinstance(creator_type, str) or not creator_type.strip():
                raise ZoteroError("ZOTERO_VALIDATION_ERROR", "creator_type is required for each creator.")
            has_name = bool(isinstance(creator.get("name"), str) and creator.get("name").strip())
            has_first = bool(isinstance(creator.get("first_name"), str) and creator.get("first_name").strip())
            has_last = bool(isinstance(creator.get("last_name"), str) and creator.get("last_name").strip())
            if not has_name and not (has_first or has_last):
                raise ZoteroError(
                    "ZOTERO_VALIDATION_ERROR",
                    "creators entries must include name or first_name/last_name.",
                )
    tags = args.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or not all(isinstance(tag, str) and tag.strip() for tag in tags):
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "tags must be an array of non-empty strings.")
        tags = list(dict.fromkeys([tag.strip() for tag in tags]))
    return {
        "item_type": item_type.strip(),
        "title": title.strip(),
        "creators": creators,
        "date": args.get("date"),
        "doi": args.get("doi"),
        "url": args.get("url"),
        "abstract": args.get("abstract"),
        "tags": tags,
        "extra": args.get("extra"),
    }


def _serialize_creators(creators: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    if not creators:
        return []
    output: List[Dict[str, str]] = []
    for creator in creators:
        creator_type = str(creator.get("creator_type")).strip()
        if creator.get("name"):
            output.append({"creatorType": creator_type, "name": str(creator["name"]).strip()})
            continue
        payload: Dict[str, str] = {"creatorType": creator_type}
        if creator.get("first_name"):
            payload["firstName"] = str(creator["first_name"]).strip()
        if creator.get("last_name"):
            payload["lastName"] = str(creator["last_name"]).strip()
        output.append(payload)
    return output


def _extract_created_key(payload: Any) -> tuple[str, int]:
    if not isinstance(payload, dict):
        raise ZoteroError(
            "ZOTERO_UPSTREAM_ERROR",
            "Unexpected Zotero create response.",
            {"type": type(payload).__name__},
        )
    successful = payload.get("successful")
    if isinstance(successful, dict):
        for entry in successful.values():
            if isinstance(entry, dict) and entry.get("key"):
                return str(entry["key"]), int(entry.get("version", 0))
    raise ZoteroError("ZOTERO_UPSTREAM_ERROR", "Zotero create failed.", {"response": payload})


def _validate_upload_attachment_args(args: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "Arguments must be an object.")
    item_key = args.get("item_key")
    if not isinstance(item_key, str) or not item_key.strip():
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "item_key is required and must be a non-empty string.")
    file_path = args.get("file_path")
    file_url = args.get("file_url")
    file_bytes_base64 = args.get("file_bytes_base64")
    provided_sources = [file_path is not None, file_url is not None, file_bytes_base64 is not None]
    if sum(provided_sources) != 1:
        raise ZoteroError(
            "ZOTERO_VALIDATION_ERROR",
            "Provide exactly one of file_path, file_url, or file_bytes_base64.",
        )
    file_bytes: Optional[bytes] = None
    if file_path is not None:
        if not isinstance(file_path, str) or not file_path.strip():
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "file_path must be a non-empty string when provided.")
        file_path = file_path.strip()
        validate_upload_file(file_path)
    if file_url is not None:
        if not isinstance(file_url, str) or not file_url.strip():
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "file_url must be a non-empty string when provided.")
        file_url = file_url.strip()
        parsed = urllib.parse.urlparse(file_url)
        if parsed.scheme not in ("http", "https"):
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "file_url must be http or https.")
        if not parsed.netloc:
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "file_url must include a host.")
    if file_bytes_base64 is not None:
        if not isinstance(file_bytes_base64, str) or not file_bytes_base64.strip():
            raise ZoteroError(
                "ZOTERO_VALIDATION_ERROR",
                "file_bytes_base64 must be a non-empty string when provided.",
            )
        try:
            file_bytes = base64.b64decode(file_bytes_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ZoteroError("ZOTERO_VALIDATION_ERROR", "file_bytes_base64 must be valid base64.") from exc
        max_bytes = load_upload_max_bytes()
        if len(file_bytes) > max_bytes:
            raise ZoteroError(
                "ZOTERO_VALIDATION_ERROR",
                "file_bytes exceeds upload size limit.",
                {"size": len(file_bytes), "max_bytes": max_bytes},
            )
    title = args.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "title must be a non-empty string when provided.")
    content_type = args.get("content_type")
    if content_type is not None and not isinstance(content_type, str):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "content_type must be a string when provided.")
    filename = args.get("filename")
    if filename is not None and (not isinstance(filename, str) or not filename.strip()):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "filename must be a non-empty string when provided.")
    if file_bytes_base64 is not None and filename is None:
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "filename is required when using file_bytes_base64.")
    resolved_content_type = content_type.strip() if isinstance(content_type, str) and content_type.strip() else None
    return {
        "item_key": item_key.strip(),
        "file_path": file_path,
        "file_url": file_url,
        "file_bytes": file_bytes,
        "filename": filename.strip() if isinstance(filename, str) and filename.strip() else None,
        "title": title,
        "content_type": resolved_content_type,
    }


def _validate_attach_arxiv_args(args: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(args, dict):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "Arguments must be an object.")
    item_key = args.get("item_key")
    if not isinstance(item_key, str) or not item_key.strip():
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "item_key is required and must be a non-empty string.")
    arxiv_id = args.get("arxiv_id")
    if not isinstance(arxiv_id, str) or not arxiv_id.strip():
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "arxiv_id is required and must be a non-empty string.")
    if not parse_arxiv_id(arxiv_id):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "arxiv_id must be a valid arXiv identifier or URL.")
    title = args.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ZoteroError("ZOTERO_VALIDATION_ERROR", "title must be a non-empty string when provided.")
    return {"item_key": item_key.strip(), "arxiv_id": arxiv_id.strip(), "title": title}


def _ok(data: Any) -> Dict[str, Any]:
    return {"ok": True, "data": data, "error": None}


def _err(code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"ok": False, "data": None, "error": {"code": code, "message": message, "details": details or {}}}


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    correlation_id = str(uuid.uuid4())
    with correlation_id_scope(correlation_id):
        timer = Timer()
        log_event(logger, level=logging.INFO, event="tool.call", tool=name, args=arguments or {})
        try:
            if name == "zotero_list_collections":
                validated = _validate_list_collections_args(arguments or {})
                config = load_config_from_env()
                raw_collections, headers = list_collections(config=config, **validated)
                collections = [_normalize_collection(collection) for collection in raw_collections]
                payload: Dict[str, Any] = {
                    "collections": collections,
                    "total": parse_total_results(headers) or len(collections),
                }
                next_start = parse_next_start(headers)
                if next_start is not None:
                    payload["next_start"] = next_start
                response = _ok(payload)
                log_event(
                    logger,
                    level=logging.INFO,
                    event="tool.success",
                    tool=name,
                    duration_ms=timer.elapsed_ms(),
                )
                return response
            if name == "zotero_search_items":
                validated = _validate_search_args(arguments or {})
                config = load_config_from_env()
                sort_used = validated["sort"]
                exact_doi = extract_exact_doi_query(validated["query"])
                exact_arxiv = extract_exact_arxiv_query(validated["query"])
                exact_arxiv_id = None
                search_query = validated["query"]
                if exact_doi:
                    search_query = exact_doi
                elif exact_arxiv:
                    exact_arxiv_id = exact_arxiv[0] + (exact_arxiv[1] or "")
                    search_query = exact_arxiv_id
                try:
                    raw_items, headers = search_items(
                        config=config,
                        query=search_query,
                        limit=validated["limit"],
                        sort=sort_used,
                        start=validated["start"],
                        tags=validated["tags"],
                    )
                except ZoteroError as exc:
                    if sort_used == DEFAULT_SORT and exc.code == "ZOTERO_VALIDATION_ERROR":
                        sort_used = FALLBACK_SORT
                        log_event(
                            logger,
                            level=logging.WARNING,
                            event="tool.sort_fallback",
                            tool=name,
                            fallback_sort=sort_used,
                            reason=exc.message,
                        )
                        raw_items, headers = search_items(
                            config=config,
                            query=search_query,
                            limit=validated["limit"],
                            sort=sort_used,
                            start=validated["start"],
                            tags=validated["tags"],
                        )
                    else:
                        raise
                if exact_doi or exact_arxiv_id:
                    raw_items = filter_items_exact_match(raw_items, doi=exact_doi, arxiv_id=exact_arxiv_id)
                items = [_normalize_item(item) for item in raw_items]
                payload: Dict[str, Any] = {
                    "items": items,
                    "total": len(items) if exact_doi or exact_arxiv_id else (parse_total_results(headers) or len(items)),
                }
                if sort_used != validated["sort"]:
                    payload["sort_used"] = sort_used
                if not (exact_doi or exact_arxiv_id):
                    next_start = parse_next_start(headers)
                    if next_start is not None:
                        payload["next_start"] = next_start
                response = _ok(payload)
                log_event(
                    logger,
                    level=logging.INFO,
                    event="tool.success",
                    tool=name,
                    duration_ms=timer.elapsed_ms(),
                )
                return response
            if name == "zotero_get_sort_values":
                response = _ok(
                    {
                        "values": list(KNOWN_SORT_VALUES),
                        "default": DEFAULT_SORT,
                        "fallback": FALLBACK_SORT,
                    }
                )
                log_event(
                    logger,
                    level=logging.INFO,
                    event="tool.success",
                    tool=name,
                    duration_ms=timer.elapsed_ms(),
                )
                return response
            if name == "zotero_get_item":
                validated = _validate_get_item_args(arguments or {})
                config = load_config_from_env()
                raw_item, _headers = get_item(config=config, **validated)
                item = _normalize_item(raw_item)
                children, _child_headers = list_item_children(config=config, **validated)
                attachments: List[Dict[str, Any]] = []
                for child in children:
                    attachment = _normalize_attachment(child)
                    if attachment:
                        attachments.append(attachment)
                item["attachments"] = attachments
                response = _ok({"item": item})
                log_event(
                    logger,
                    level=logging.INFO,
                    event="tool.success",
                    tool=name,
                    duration_ms=timer.elapsed_ms(),
                )
                return response
            if name == "zotero_create_item":
                validated = _validate_create_args(arguments or {})
                config = load_config_from_env()
                template = get_item_template(config=config, item_type=validated["item_type"])
                template["title"] = validated["title"]
                creators = _serialize_creators(validated.get("creators"))
                if creators:
                    template["creators"] = creators
                if validated.get("date"):
                    template["date"] = str(validated["date"])
                if validated.get("doi"):
                    template["DOI"] = str(validated["doi"])
                if validated.get("url"):
                    template["url"] = str(validated["url"])
                if validated.get("abstract"):
                    template["abstractNote"] = str(validated["abstract"])
                if validated.get("tags"):
                    template["tags"] = [{"tag": tag} for tag in validated["tags"]]
                if validated.get("extra"):
                    template["extra"] = str(validated["extra"])
                payload = create_item(config=config, item=template)
                item_key, version = _extract_created_key(payload)
                response = _ok({"item_key": item_key, "version": version, "item": template})
                log_event(
                    logger,
                    level=logging.INFO,
                    event="tool.success",
                    tool=name,
                    duration_ms=timer.elapsed_ms(),
                )
                return response
            if name == "zotero_upload_attachment":
                validated = _validate_upload_attachment_args(arguments or {})
                config = load_config_from_env()
                payload = upload_attachment(config=config, **validated)
                response = _ok(payload)
                log_event(
                    logger,
                    level=logging.INFO,
                    event="tool.success",
                    tool=name,
                    duration_ms=timer.elapsed_ms(),
                )
                return response
            if name == "zotero_attach_arxiv_pdf":
                validated = _validate_attach_arxiv_args(arguments or {})
                config = load_config_from_env()
                payload = attach_arxiv_pdf(config=config, **validated)
                response = _ok(payload)
                log_event(
                    logger,
                    level=logging.INFO,
                    event="tool.success",
                    tool=name,
                    duration_ms=timer.elapsed_ms(),
                )
                return response
            if name == "zotero_add_item_to_collection":
                validated = _validate_add_item_to_collection_args(arguments or {})
                config = load_config_from_env()
                collection_key = validated.get("collection_key")
                if not collection_key:
                    collection_key = _resolve_collection_key_by_name(
                        config=config,
                        collection_name=validated["collection_name"],
                    )
                add_item_to_collection(
                    config=config,
                    collection_key=collection_key,
                    item_key=validated["item_key"],
                )
                response = _ok({"item_key": validated["item_key"], "collection_key": collection_key})
                log_event(
                    logger,
                    level=logging.INFO,
                    event="tool.success",
                    tool=name,
                    duration_ms=timer.elapsed_ms(),
                )
                return response
            raise ValueError(f"Unknown tool: {name}")
        except ZoteroError as exc:
            log_event(
                logger,
                level=logging.WARNING,
                event="tool.error",
                tool=name,
                code=exc.code,
                message=exc.message,
                details=exc.details,
                duration_ms=timer.elapsed_ms(),
            )
            return _err(exc.code, exc.message, exc.details)


async def run() -> None:
    log_event(
        logger,
        level=logging.INFO,
        event="server.start",
        version=__version__,
        debug=os.environ.get("ZOTERO_MCP_DEBUG") == "1",
    )

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="zotero-mcp",
                server_version=__version__,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> int:
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
