"""Minimal smoke tests for cerebro modules."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.crosslinks import find_crosslinks
from cerebro.dedup import detect_duplicates
from cerebro.exporter_csv import export_csv
from cerebro.exporter_html import export_html
from cerebro.exporter_json import export_json
from cerebro.exporter_jsonl import export_jsonl
from cerebro.fetcher import _is_soft_dead
from cerebro.models import Bookmark
from cerebro.parser import parse_bookmarks
from cerebro.search import build_index, search


def test_models():
    b = Bookmark(id="test-1", title="Test", url="https://example.com", is_dead_link=False)
    assert b.title == "Test"
    assert b.url == "https://example.com"


def test_parser_roundtrip():
    bookmarks = parse_bookmarks(".github/testdata/sample.html")
    assert len(bookmarks) > 0


def test_dedup():
    b1 = Bookmark(id="a", title="A", url="https://example.com/page")
    b2 = Bookmark(id="b", title="A", url="https://example.com/page")
    b3 = Bookmark(id="c", title="B", url="https://example.com/other")
    deduped = detect_duplicates([b1, b2, b3])
    assert len(deduped) == 3  # marks duplicates, does not remove


def test_fetcher_utilities():
    assert _is_soft_dead(403) is True
    assert _is_soft_dead(200) is False


def test_search_build_index():
    bookmarks = [
        {
            "title": "Python tutorial",
            "url": "https://python.org",
            "tags": ["python"],
            "description": "",
            "category_breadcrumbs": [],
            "domain": "python.org",
        },
        {
            "title": "Rust book",
            "url": "https://rust-lang.org",
            "tags": ["rust"],
            "description": "",
            "category_breadcrumbs": [],
            "domain": "rust-lang.org",
        },
    ]
    vectorizer, matrix, bms = build_index(bookmarks)
    results = search("python", vectorizer, matrix, bms, top_k=2)
    assert len(results) > 0


def test_exporter_json():
    bookmarks = [Bookmark(id="t1", title="T", url="https://x.com")]
    path = export_json(bookmarks, "/tmp/test_cerebro.json")
    assert path.exists()
    parsed = json.loads(path.read_text())
    assert len(parsed) == 1


def test_exporter_html():
    bookmarks = [Bookmark(id="t1", title="T", url="https://x.com")]
    path = export_html(bookmarks, "/tmp/test_cerebro.html")
    assert "https://x.com" in path.read_text()


def test_exporter_csv():
    bookmarks = [Bookmark(id="t1", title="T", url="https://x.com")]
    path = export_csv(bookmarks, "/tmp/test_cerebro.csv")
    assert path.exists()
    text = path.read_text()
    assert "id,title,url" in text
    assert "https://x.com" in text


def test_exporter_jsonl():
    b1 = Bookmark(
        id="a", title="A", url="https://example.com/1", domain="example.com", tags=["python", "ml"]
    )
    b2 = Bookmark(
        id="b",
        title="B",
        url="https://example.com/2",
        domain="example.com",
        tags=["python", "ml", "rust"],
    )
    b3 = Bookmark(id="c", title="C", url="https://other.com/3", domain="other.com", tags=["games"])
    path = export_jsonl([b1, b2, b3], "/tmp/test_cerebro.jsonl")
    assert path.exists()
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 3
    parsed = json.loads(lines[0])
    assert parsed["url"] == "https://example.com/1"


def test_crosslinks():
    b1 = Bookmark(
        id="a", title="A", url="https://example.com/1", domain="example.com", tags=["python", "ml"]
    )
    b2 = Bookmark(
        id="b",
        title="B",
        url="https://example.com/2",
        domain="example.com",
        tags=["python", "ml", "rust"],
    )
    b3 = Bookmark(id="c", title="C", url="https://other.com/3", domain="other.com", tags=["games"])
    bookmarks = find_crosslinks([b1, b2, b3])
    # b1 and b2 share domain, so they should be related via domain match
    assert any(len(bm.related_ids) > 0 for bm in bookmarks)
