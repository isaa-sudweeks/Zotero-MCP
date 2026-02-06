import json
import os
import sys
import tempfile
import unittest
from typing import Any, Dict, Tuple
from unittest.mock import patch
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from zotero_mcp.server import call_tool


class FakeResponse:
    def __init__(self, status: int, headers: Dict[str, str], body: Any) -> None:
        self.status = status
        self.headers = headers
        if body is None:
            self._body = b""
        elif isinstance(body, (bytes, bytearray)):
            self._body = bytes(body)
        else:
            self._body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class RequestRouter:
    def __init__(self, routes: Dict[Tuple[str, str], Any]) -> None:
        self.routes = routes

    def __call__(self, request: urllib.request.Request, timeout: int = 30) -> FakeResponse:
        method = request.get_method()
        key = (method, request.full_url)
        if key not in self.routes:
            raise AssertionError(f"No mocked response for {method} {request.full_url}")
        response = self.routes[key]
        if isinstance(response, list):
            if not response:
                raise AssertionError(f"No remaining mocked responses for {method} {request.full_url}")
            return response.pop(0)
        return response


def _default_env(api_base: str = "https://example.test") -> Dict[str, str]:
    return {
        "ZOTERO_API_KEY": "test-key",
        "ZOTERO_USER_ID": "12345",
        "ZOTERO_API_BASE": api_base,
    }


class IntegrationMockedTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_items_with_next_start(self) -> None:
        api_base = "https://example.test"
        query_url = (
            f"{api_base}/users/12345/items"
            "?q=deep+learning&limit=2&sort=relevance"
        )
        items = [
            {
                "key": "A1",
                "version": 10,
                "data": {
                    "itemType": "journalArticle",
                    "title": "Deep Learning",
                    "creators": [{"creatorType": "author", "name": "Goodfellow"}],
                    "DOI": "10.1000/example",
                    "tags": [{"tag": "ml"}],
                },
            }
        ]
        headers = {"total-results": "42", "link": f"<{api_base}/users/12345/items?start=2>; rel=\"next\""}
        router = RequestRouter(
            {
                ("GET", query_url): FakeResponse(200, headers, items),
            }
        )
        with patch.dict(os.environ, _default_env(api_base)):
            with patch("urllib.request.urlopen", new=router):
                response = await call_tool("zotero_search_items", {"query": "deep learning", "limit": 2})

        self.assertTrue(response["ok"])
        data = response["data"]
        self.assertEqual(data["total"], 42)
        self.assertEqual(data["next_start"], 2)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["item_key"], "A1")
        self.assertEqual(data["items"][0]["title"], "Deep Learning")
        self.assertEqual(data["items"][0]["tags"], ["ml"])

    async def test_get_item_includes_attachments(self) -> None:
        api_base = "https://example.test"
        item_url = f"{api_base}/users/12345/items/ITEM123"
        children_url = f"{api_base}/users/12345/items/ITEM123/children"
        item = {
            "key": "ITEM123",
            "version": 2,
            "data": {
                "itemType": "book",
                "title": "Sample Book",
                "creators": [{"creatorType": "author", "name": "Author"}],
            },
        }
        children = [
            {
                "key": "ATT1",
                "data": {"itemType": "attachment", "title": "Paper.pdf", "contentType": "application/pdf", "fileSize": 123},
            }
        ]
        router = RequestRouter(
            {
                ("GET", item_url): FakeResponse(200, {}, item),
                ("GET", children_url): FakeResponse(200, {}, children),
            }
        )
        with patch.dict(os.environ, _default_env(api_base)):
            with patch("urllib.request.urlopen", new=router):
                response = await call_tool("zotero_get_item", {"item_key": "ITEM123"})

        self.assertTrue(response["ok"])
        data = response["data"]["item"]
        self.assertEqual(data["item_key"], "ITEM123")
        self.assertEqual(data["title"], "Sample Book")
        self.assertEqual(len(data["attachments"]), 1)
        self.assertEqual(data["attachments"][0]["attachment_key"], "ATT1")
        self.assertEqual(data["attachments"][0]["size"], 123)

    async def test_create_item_flow(self) -> None:
        api_base = "https://example.test"
        template_url = f"{api_base}/items/new?itemType=book"
        create_url = f"{api_base}/users/12345/items"
        template = {"itemType": "book", "title": ""}
        create_payload = {"successful": {"0": {"key": "NEWITEM", "version": 3}}}
        router = RequestRouter(
            {
                ("GET", template_url): FakeResponse(200, {}, template),
                ("POST", create_url): FakeResponse(200, {}, create_payload),
            }
        )
        with patch.dict(os.environ, _default_env(api_base)):
            with patch("urllib.request.urlopen", new=router):
                response = await call_tool(
                    "zotero_create_item",
                    {"item_type": "book", "title": "My Title", "creators": [{"creator_type": "author", "name": "Jane"}]},
                )

        self.assertTrue(response["ok"])
        data = response["data"]
        self.assertEqual(data["item_key"], "NEWITEM")
        self.assertEqual(data["version"], 3)
        self.assertEqual(data["item"]["title"], "My Title")
        self.assertEqual(data["item"]["creators"][0]["name"], "Jane")

    async def test_upload_attachment_flow(self) -> None:
        api_base = "https://example.test"
        template_url = f"{api_base}/items/new?itemType=attachment&linkMode=imported_file"
        create_url = f"{api_base}/users/12345/items"
        auth_url = f"{api_base}/users/12345/items/ATTACH1/file"
        upload_url = "https://uploads.example.test/upload"

        template = {"itemType": "attachment"}
        create_payload = {"successful": {"0": {"key": "ATTACH1", "version": 7}}}
        auth_payload = {
            "url": upload_url,
            "prefix": "--prefix--",
            "suffix": "--suffix--",
            "uploadKey": "UPLOADKEY",
            "contentType": "multipart/form-data; boundary=boundary",
        }
        final_payload = {"ok": True}

        router = RequestRouter(
            {
                ("GET", template_url): FakeResponse(200, {}, template),
                ("POST", create_url): FakeResponse(200, {}, create_payload),
                ("POST", auth_url): [
                    FakeResponse(200, {}, auth_payload),
                    FakeResponse(200, {}, final_payload),
                ],
                ("POST", upload_url): FakeResponse(201, {}, None),
            }
        )

        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"%PDF-1.4 test")
            file_path = handle.name

        try:
            with patch.dict(os.environ, _default_env(api_base)):
                with patch("urllib.request.urlopen", new=router):
                    response = await call_tool(
                        "zotero_upload_attachment",
                        {"item_key": "PARENT1", "file_path": file_path, "content_type": "application/pdf"},
                    )
        finally:
            os.unlink(file_path)

        self.assertTrue(response["ok"])
        data = response["data"]
        self.assertEqual(data["attachment_key"], "ATTACH1")
        self.assertEqual(data["parent_item_key"], "PARENT1")
        self.assertEqual(data["content_type"], "application/pdf")
        self.assertGreater(data["size"], 0)


if __name__ == "__main__":
    unittest.main()
