import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from zotero_mcp import server as server_module


def _tool_by_name(name):
    for tool in server_module._tool_list():
        if tool.name == name:
            return tool
    raise AssertionError(f"missing tool: {name}")


def test_tool_list_names():
    names = {tool.name for tool in server_module._tool_list()}
    assert names == {
        "zotero_list_collections",
        "zotero_search_items",
        "zotero_get_sort_values",
        "zotero_get_item",
        "zotero_create_item",
        "zotero_upload_attachment",
        "zotero_attach_arxiv_pdf",
        "zotero_add_item_to_collection",
    }


def test_tool_schemas_basic_shape():
    for tool in server_module._tool_list():
        assert tool.inputSchema["type"] == "object"
        assert tool.inputSchema["additionalProperties"] is False
        assert tool.outputSchema["type"] == "object"
        assert tool.outputSchema["additionalProperties"] is False
        required = set(tool.outputSchema["required"])
        assert {"ok", "data", "error"}.issubset(required)


def test_search_schema_details():
    tool = _tool_by_name("zotero_search_items")
    schema = tool.inputSchema
    assert "query" in schema["required"]
    assert schema["properties"]["query"]["minLength"] == 1
    assert schema["properties"]["limit"]["minimum"] == 1
    assert schema["properties"]["limit"]["maximum"] == 100
    assert schema["properties"]["start"]["minimum"] == 0
    assert schema["properties"]["start"]["default"] == 0
    assert schema["properties"]["offset"]["minimum"] == 0
    assert schema["properties"]["tags"]["uniqueItems"] is True


def test_get_item_schema_details():
    tool = _tool_by_name("zotero_get_item")
    schema = tool.inputSchema
    assert "item_key" in schema["required"]
    assert schema["properties"]["item_key"]["minLength"] == 1


def test_list_collections_schema_details():
    tool = _tool_by_name("zotero_list_collections")
    schema = tool.inputSchema
    assert schema["properties"]["limit"]["minimum"] == 1
    assert schema["properties"]["limit"]["maximum"] == 100
    assert schema["properties"]["start"]["minimum"] == 0
    assert schema["properties"]["start"]["default"] == 0


def test_create_item_schema_details():
    tool = _tool_by_name("zotero_create_item")
    schema = tool.inputSchema
    assert "item_type" in schema["required"]
    assert "title" in schema["required"]
    creators = schema["properties"]["creators"]["items"]
    assert creators["additionalProperties"] is False
    assert "creator_type" in creators["required"]
    assert schema["properties"]["tags"]["uniqueItems"] is True


def test_upload_attachment_schema_details():
    tool = _tool_by_name("zotero_upload_attachment")
    schema = tool.inputSchema
    assert "item_key" in schema["required"]
    assert "file_path" not in schema["required"]
    any_of = schema.get("anyOf", [])
    required_sets = {tuple(sorted(entry.get("required", []))) for entry in any_of}
    assert tuple(sorted(["item_key", "file_path"])) in required_sets
    assert tuple(sorted(["item_key", "file_url"])) in required_sets
    assert tuple(sorted(["item_key", "file_bytes_base64", "filename"])) in required_sets
    assert "default" not in schema["properties"]["content_type"]


def test_attach_arxiv_schema_details():
    tool = _tool_by_name("zotero_attach_arxiv_pdf")
    schema = tool.inputSchema
    assert "item_key" in schema["required"]
    assert "arxiv_id" in schema["required"]
    assert schema["properties"]["arxiv_id"]["minLength"] == 1


def test_add_item_to_collection_schema_details():
    tool = _tool_by_name("zotero_add_item_to_collection")
    schema = tool.inputSchema
    assert "item_key" in schema["required"]
    assert schema["properties"]["item_key"]["minLength"] == 1
    assert schema["properties"]["collection_key"]["minLength"] == 1
    assert schema["properties"]["collection_name"]["minLength"] == 1
