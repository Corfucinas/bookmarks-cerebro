"""Minimal smoke tests for cerebro modules."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.models import Bookmark
from cerebro.parser import parse_bookmarks
from cerebro.dedup import detect_duplicates
from cerebro.fetcher import _is_soft_dead
from cerebro.search import build_index, search
from cerebro.exporter_json import export_json
from cerebro.exporter_html import export_html


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
    bookmarks = [Bookmark(id="t1", title="T", url="https://x.com")]
    html = export_html(bookmarks, "/tmp/test_cerebro.html")
    assert "https://x.com" in html
    bookmarks = [Bookmark(id="t1", title="T", url="https://x.com")]
    html = export_html(bookmarks, "Test", "2026-01-01")
    assert "https://x.com" in html
