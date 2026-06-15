"""Smoke tests for SQLite persistence layer."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.db import (
    count_bookmarks,
    count_dead_links,
    delete_bookmark,
    get_bookmark,
    get_bookmarks,
    get_session,
    save_bookmarks,
    search_bookmarks,
    upsert_bookmark,
)
from cerebro.models import Bookmark


@pytest.fixture
def db_session():
    """Provide a fresh in-memory SQLite session."""
    with get_session("sqlite:///:memory:") as session:
        yield session


def _sample_bookmark(**overrides):
    defaults = {
        "id": "bm-1",
        "url": "https://example.com/page",
        "title": "Example Page",
        "domain": "example.com",
        "tags": ["python", "ml"],
        "description": "A sample page",
    }
    defaults.update(overrides)
    return Bookmark(**defaults)


def test_upsert_and_get_bookmark(db_session):
    bm = _sample_bookmark()
    upsert_bookmark(db_session, bm)
    loaded = get_bookmark(db_session, "bm-1")
    assert loaded is not None
    assert loaded.title == "Example Page"
    assert loaded.tags == ["python", "ml"]


def test_upsert_updates_existing(db_session):
    bm = _sample_bookmark()
    upsert_bookmark(db_session, bm)
    bm.title = "Updated Title"
    upsert_bookmark(db_session, bm)
    loaded = get_bookmark(db_session, "bm-1")
    assert loaded is not None
    assert loaded.title == "Updated Title"


def test_get_bookmarks_pagination(db_session):
    save_bookmarks(db_session, [_sample_bookmark(id=f"bm-{i}") for i in range(5)])
    results = get_bookmarks(db_session, limit=3)
    assert len(results) == 3


def test_search_bookmarks(db_session):
    save_bookmarks(
        db_session,
        [
            _sample_bookmark(id="a", title="Python tutorial", description="learn python"),
            _sample_bookmark(id="b", title="Rust book", description="systems programming"),
        ],
    )
    results = search_bookmarks(db_session, "python")
    assert len(results) == 1
    assert results[0].id == "a"


def test_delete_bookmark(db_session):
    bm = _sample_bookmark()
    upsert_bookmark(db_session, bm)
    assert delete_bookmark(db_session, "bm-1") is True
    assert get_bookmark(db_session, "bm-1") is None


def test_count_bookmarks_and_dead_links(db_session):
    save_bookmarks(
        db_session,
        [
            _sample_bookmark(id="live", is_dead_link=False),
            _sample_bookmark(id="dead", is_dead_link=True, http_status=404),
        ],
    )
    assert count_bookmarks(db_session) == 2
    assert count_dead_links(db_session) == 1


def test_full_dict_roundtrip(db_session):
    bm = Bookmark(
        id="full-1",
        url="https://example.com",
        title="Full",
        fetched_metadata={"og:title": "OG Title"},
        duplicate_group_id="dup-1",
        duplicate_urls=["https://example.com/old"],
        related_ids=["full-2"],
    )
    upsert_bookmark(db_session, bm)
    loaded = get_bookmark(db_session, "full-1")
    assert loaded is not None
    assert loaded.fetched_metadata == {"og:title": "OG Title"}
    assert loaded.duplicate_group_id == "dup-1"
    assert loaded.related_ids == ["full-2"]
