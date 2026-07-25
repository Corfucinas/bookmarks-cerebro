"""Tests for cerebro.search."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.search import build_index, search


def _make_bookmarks() -> list[dict]:
    return [
        {
            "title": "Rust async patterns",
            "description": "tokio and async/await",
            "tags": ["rust", "async"],
            "category_breadcrumbs": ["Programming", "Rust"],
            "domain": "rust-lang.org",
        },
        {
            "title": "Python data science",
            "description": "pandas and numpy",
            "tags": ["python", "data"],
            "category_breadcrumbs": ["Data", "Analytics"],
            "domain": "pandas.pydata.org",
        },
    ]


# ---------------------------------------------------------------------------
# search — empty query
# ---------------------------------------------------------------------------


def test_search_empty_query_returns_empty():
    """Empty query must return [] rather than NaN-contaminated results."""
    bms = _make_bookmarks()
    vectorizer, matrix, stored = build_index(bms)
    assert search("", vectorizer, matrix, stored) == []


def test_search_whitespace_only_returns_empty():
    """Whitespace-only query must return [] rather than NaN-contaminated results."""
    bms = _make_bookmarks()
    vectorizer, matrix, stored = build_index(bms)
    assert search("   ", vectorizer, matrix, stored) == []


def test_search_real_query_returns_results():
    """Sanity check: a real query still returns results."""
    bms = _make_bookmarks()
    vectorizer, matrix, stored = build_index(bms)
    results = search("rust async", vectorizer, matrix, stored)
    assert len(results) >= 1
    assert all("search_score" in r for r in results)
