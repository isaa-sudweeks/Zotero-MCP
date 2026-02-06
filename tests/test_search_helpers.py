import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from zotero_mcp import zotero_client


def test_extract_exact_doi_query_accepts_known_forms():
    assert zotero_client.extract_exact_doi_query("10.1000/xyz123") == "10.1000/xyz123"
    assert zotero_client.extract_exact_doi_query("DOI:10.1000/XYZ123") == "10.1000/xyz123"
    assert (
        zotero_client.extract_exact_doi_query("https://doi.org/10.1000/xyz123") == "10.1000/xyz123"
    )


def test_extract_exact_doi_query_rejects_non_exact():
    assert zotero_client.extract_exact_doi_query("see 10.1000/xyz123") is None
    assert zotero_client.extract_exact_doi_query("10.1000/xyz123 extra") is None
    assert zotero_client.extract_exact_doi_query("doi: 10.1000/xyz123 extra") is None


def test_extract_exact_arxiv_query_accepts_known_forms():
    assert zotero_client.extract_exact_arxiv_query("1707.12345") == ("1707.12345", None)
    assert zotero_client.extract_exact_arxiv_query("arXiv:1707.12345v2") == ("1707.12345", "v2")
    assert zotero_client.extract_exact_arxiv_query("https://arxiv.org/abs/1707.12345v2") == (
        "1707.12345",
        "v2",
    )
    assert zotero_client.extract_exact_arxiv_query("https://arxiv.org/pdf/1707.12345.pdf") == (
        "1707.12345",
        None,
    )


def test_extract_exact_arxiv_query_rejects_non_exact():
    assert zotero_client.extract_exact_arxiv_query("see arXiv:1707.12345") is None
    assert zotero_client.extract_exact_arxiv_query("1707.12345 extra") is None
