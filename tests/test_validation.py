import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from zotero_mcp import server as server_module
from zotero_mcp.zotero_client import ZoteroError


def test_validate_search_args_strips_and_dedupes():
    args = {"query": "  neural networks ", "limit": 10, "sort": "date", "tags": ["ai", "ai", "ml"]}
    validated = server_module._validate_search_args(args)
    assert validated["query"] == "neural networks"
    assert validated["limit"] == 10
    assert validated["sort"] == "date"
    assert validated["tags"] == ["ai", "ml"]


def test_validate_search_args_normalizes_sort_case():
    args = {"query": "cats", "sort": "DATEMODIFIED"}
    validated = server_module._validate_search_args(args)
    assert validated["sort"] == "dateModified"


def test_validate_search_args_defaults():
    validated = server_module._validate_search_args({"query": "cats"})
    assert validated["limit"] == 25
    assert validated["sort"] == "relevance"
    assert validated["tags"] is None


@pytest.mark.parametrize(
    "args,message",
    [
        (None, "Arguments must be an object."),
        ({}, "query is required and must be a non-empty string."),
        ({"query": ""}, "query is required and must be a non-empty string."),
        ({"query": "ok", "limit": "10"}, "limit must be an integer."),
        ({"query": "ok", "limit": 0}, "limit must be between 1 and 100."),
        ({"query": "ok", "limit": 101}, "limit must be between 1 and 100."),
        ({"query": "ok", "sort": ""}, "sort must be a non-empty string."),
        ({"query": "ok", "tags": [""]}, "tags must be an array of non-empty strings."),
        ({"query": "ok", "tags": [1]}, "tags must be an array of non-empty strings."),
    ],
)
def test_validate_search_args_errors(args, message):
    with pytest.raises(ZoteroError) as excinfo:
        server_module._validate_search_args(args)
    assert excinfo.value.code == "ZOTERO_VALIDATION_ERROR"
    assert excinfo.value.message == message


def test_validate_get_item_args_validates():
    validated = server_module._validate_get_item_args({"item_key": " ABC123 "})
    assert validated == {"item_key": "ABC123"}


@pytest.mark.parametrize(
    "args,message",
    [
        (None, "Arguments must be an object."),
        ({}, "item_key is required and must be a non-empty string."),
        ({"item_key": ""}, "item_key is required and must be a non-empty string."),
    ],
)
def test_validate_get_item_args_errors(args, message):
    with pytest.raises(ZoteroError) as excinfo:
        server_module._validate_get_item_args(args)
    assert excinfo.value.code == "ZOTERO_VALIDATION_ERROR"
    assert excinfo.value.message == message


def test_validate_list_collections_args_defaults():
    validated = server_module._validate_list_collections_args({})
    assert validated["limit"] == 25
    assert validated["start"] == 0


@pytest.mark.parametrize(
    "args,message",
    [
        (None, "Arguments must be an object."),
        ({"limit": "10"}, "limit must be an integer."),
        ({"limit": 0}, "limit must be between 1 and 100."),
        ({"limit": 101}, "limit must be between 1 and 100."),
        ({"start": "0"}, "start must be an integer."),
        ({"start": -1}, "start must be greater than or equal to 0."),
    ],
)
def test_validate_list_collections_args_errors(args, message):
    with pytest.raises(ZoteroError) as excinfo:
        server_module._validate_list_collections_args(args)
    assert excinfo.value.code == "ZOTERO_VALIDATION_ERROR"
    assert excinfo.value.message == message


def test_validate_create_args_minimal():
    validated = server_module._validate_create_args({"item_type": "journalArticle", "title": "Paper"})
    assert validated["item_type"] == "journalArticle"
    assert validated["title"] == "Paper"
    assert validated["creators"] is None
    assert validated["tags"] is None


def test_validate_create_args_creators_name():
    creators = [{"creator_type": "author", "name": "Ada Lovelace"}]
    validated = server_module._validate_create_args(
        {"item_type": "book", "title": "Title", "creators": creators}
    )
    assert validated["creators"] == creators


def test_validate_create_args_creators_first_last():
    creators = [{"creator_type": "author", "first_name": "Ada", "last_name": "Lovelace"}]
    validated = server_module._validate_create_args(
        {"item_type": "book", "title": "Title", "creators": creators}
    )
    assert validated["creators"] == creators


def test_validate_create_args_tags_strip_dedupe():
    validated = server_module._validate_create_args(
        {"item_type": "book", "title": "Title", "tags": [" AI ", "AI", "ML"]}
    )
    assert validated["tags"] == ["AI", "ML"]


@pytest.mark.parametrize(
    "args,message",
    [
        (None, "Arguments must be an object."),
        ({"title": "Title"}, "item_type is required and must be a non-empty string."),
        ({"item_type": "book"}, "title is required and must be a non-empty string."),
        ({"item_type": "book", "title": "Title", "creators": "nope"}, "creators must be an array."),
        (
            {"item_type": "book", "title": "Title", "creators": ["nope"]},
            "creators entries must be objects.",
        ),
        (
            {"item_type": "book", "title": "Title", "creators": [{"name": "Ada"}]},
            "creator_type is required for each creator.",
        ),
        (
            {"item_type": "book", "title": "Title", "creators": [{"creator_type": "author"}]},
            "creators entries must include name or first_name/last_name.",
        ),
        (
            {"item_type": "book", "title": "Title", "tags": [""]},
            "tags must be an array of non-empty strings.",
        ),
    ],
)
def test_validate_create_args_errors(args, message):
    with pytest.raises(ZoteroError) as excinfo:
        server_module._validate_create_args(args)
    assert excinfo.value.code == "ZOTERO_VALIDATION_ERROR"
    assert excinfo.value.message == message


def test_validate_upload_attachment_args_defaults(tmp_path):
    file_path = tmp_path / "file.pdf"
    file_path.write_bytes(b"%PDF-1.4 test")
    validated = server_module._validate_upload_attachment_args({"item_key": "ABC123", "file_path": str(file_path)})
    assert validated["item_key"] == "ABC123"
    assert validated["file_path"] == str(file_path)
    assert validated["title"] is None
    assert validated["content_type"] is None


@pytest.mark.parametrize(
    "args,message",
    [
        (None, "Arguments must be an object."),
        ({"file_path": "/tmp/file.pdf"}, "item_key is required and must be a non-empty string."),
        ({"item_key": "ABC"}, "Provide exactly one of file_path, file_url, or file_bytes_base64."),
        ({"item_key": "ABC", "file_path": ""}, "file_path must be a non-empty string when provided."),
        ({"item_key": "ABC", "file_url": "ftp://example.com/file.pdf"}, "file_url must be http or https."),
        (
            {"item_key": "ABC", "file_path": "FILE_PATH", "title": ""},
            "title must be a non-empty string when provided.",
        ),
        (
            {"item_key": "ABC", "file_path": "FILE_PATH", "content_type": 123},
            "content_type must be a string when provided.",
        ),
        (
            {"item_key": "ABC", "file_bytes_base64": "Zm9v"},
            "filename is required when using file_bytes_base64.",
        ),
        (
            {"item_key": "ABC", "file_bytes_base64": "NOT_BASE64", "filename": "file.pdf"},
            "file_bytes_base64 must be valid base64.",
        ),
    ],
)
def test_validate_upload_attachment_args_errors(args, message, tmp_path):
    if isinstance(args, dict) and args.get("file_path") == "FILE_PATH":
        file_path = tmp_path / "file.pdf"
        file_path.write_bytes(b"%PDF-1.4 test")
        args = dict(args)
        args["file_path"] = str(file_path)
    with pytest.raises(ZoteroError) as excinfo:
        server_module._validate_upload_attachment_args(args)
    assert excinfo.value.code == "ZOTERO_VALIDATION_ERROR"
    assert excinfo.value.message == message


def test_validate_upload_attachment_args_missing_file():
    with pytest.raises(ZoteroError) as excinfo:
        server_module._validate_upload_attachment_args({"item_key": "ABC", "file_path": "/nope/missing.pdf"})
    assert excinfo.value.code == "ZOTERO_VALIDATION_ERROR"
    assert excinfo.value.message == "file_path does not exist."


def test_validate_upload_attachment_args_size_limit(tmp_path, monkeypatch):
    file_path = tmp_path / "big.pdf"
    file_path.write_bytes(b"a" * 10)
    monkeypatch.setenv("ZOTERO_UPLOAD_MAX_BYTES", "5")
    with pytest.raises(ZoteroError) as excinfo:
        server_module._validate_upload_attachment_args({"item_key": "ABC", "file_path": str(file_path)})
    assert excinfo.value.code == "ZOTERO_VALIDATION_ERROR"
    assert excinfo.value.message == "file_path exceeds upload size limit."


def test_validate_upload_attachment_args_blank_content_type(tmp_path):
    file_path = tmp_path / "file.pdf"
    file_path.write_bytes(b"%PDF-1.4 test")
    validated = server_module._validate_upload_attachment_args(
        {"item_key": "ABC", "file_path": str(file_path), "content_type": "  "}
    )
    assert validated["content_type"] is None




def test_validate_attach_arxiv_args_validates():
    validated = server_module._validate_attach_arxiv_args({"item_key": "ABC123", "arxiv_id": "arXiv:1706.03762v1"})
    assert validated["item_key"] == "ABC123"
    assert validated["arxiv_id"] == "arXiv:1706.03762v1"


@pytest.mark.parametrize(
    "args,message",
    [
        (None, "Arguments must be an object."),
        ({}, "item_key is required and must be a non-empty string."),
        ({"item_key": ""}, "item_key is required and must be a non-empty string."),
        ({"item_key": "ABC"}, "arxiv_id is required and must be a non-empty string."),
        ({"item_key": "ABC", "arxiv_id": ""}, "arxiv_id is required and must be a non-empty string."),
        ({"item_key": "ABC", "arxiv_id": "not-a-real-id"}, "arxiv_id must be a valid arXiv identifier or URL."),
        ({"item_key": "ABC", "arxiv_id": "1706.03762", "title": ""}, "title must be a non-empty string when provided."),
    ],
)
def test_validate_attach_arxiv_args_errors(args, message):
    with pytest.raises(ZoteroError) as excinfo:
        server_module._validate_attach_arxiv_args(args)
    assert excinfo.value.code == "ZOTERO_VALIDATION_ERROR"
    assert excinfo.value.message == message


def test_validate_add_item_to_collection_args_key_only():
    validated = server_module._validate_add_item_to_collection_args({"item_key": "ITEM1", "collection_key": "COL1"})
    assert validated["item_key"] == "ITEM1"
    assert validated["collection_key"] == "COL1"
    assert validated["collection_name"] is None


def test_validate_add_item_to_collection_args_name_only():
    validated = server_module._validate_add_item_to_collection_args({"item_key": "ITEM1", "collection_name": "Reads"})
    assert validated["item_key"] == "ITEM1"
    assert validated["collection_key"] is None
    assert validated["collection_name"] == "Reads"


@pytest.mark.parametrize(
    "args,message",
    [
        (None, "Arguments must be an object."),
        ({}, "item_key is required and must be a non-empty string."),
        ({"item_key": ""}, "item_key is required and must be a non-empty string."),
        ({"item_key": "ITEM1"}, "Provide collection_key or collection_name."),
        (
            {"item_key": "ITEM1", "collection_key": ""},
            "collection_key must be a non-empty string when provided.",
        ),
        (
            {"item_key": "ITEM1", "collection_name": ""},
            "collection_name must be a non-empty string when provided.",
        ),
    ],
)
def test_validate_add_item_to_collection_args_errors(args, message):
    with pytest.raises(ZoteroError) as excinfo:
        server_module._validate_add_item_to_collection_args(args)
    assert excinfo.value.code == "ZOTERO_VALIDATION_ERROR"
    assert excinfo.value.message == message
