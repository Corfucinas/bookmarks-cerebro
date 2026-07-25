"""Regression tests for dedup.py — exact, normalized, hash, fuzzy modes + helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from cerebro.dedup import (
    _content_hash,
    _normalize_url,
    _title_similarity,
    deduplicate_bookmarks,
    detect_duplicates,
)
from cerebro.models import Bookmark


# ---------------------------------------------------------------------------
# Helpers: _normalize_url, _content_hash, _title_similarity
# ---------------------------------------------------------------------------
def test_normalize_url_strips_protocol_www_and_trailing_slash():
    """normalize_url lowercases, strips protocol, www, and trailing slash."""
    assert _normalize_url("https://www.example.com/") == "example.com"
    assert _normalize_url("HTTP://Example.com/Path/") == "example.com/path"
    assert _normalize_url("https://www.example.com") == "example.com"


def test_normalize_url_handles_fragment():
    """normalize_url drops fragment, keeping netloc+path."""
    assert _normalize_url("https://example.com/page#frag") == "example.com/page"


def test_compute_url_hash_is_deterministic():
    """_content_hash returns same hash for same normalized URL + title."""
    bm1 = Bookmark(id="a", url="https://www.example.com/", title="Hello")
    bm2 = Bookmark(id="b", url="http://example.com", title="hello")
    # titles are lowercased before hashing -> same hash here
    assert _content_hash(bm1) == _content_hash(bm2)
    # different lowercased titles -> different hash
    bm3 = Bookmark(id="c", url="https://example.com", title="World")
    assert _content_hash(bm1) != _content_hash(bm3)
    # deterministic length 16
    assert len(_content_hash(bm1)) == 16
    # deterministic length 16
    assert len(_content_hash(bm1)) == 16


def test_title_similarity_jaccard():
    """_title_similarity computes Jaccard over word sets."""
    assert _title_similarity("Python Tutorial", "Python Tutorial") == 1.0
    assert _title_similarity("Python Tutorial", "Python Tutorials") > 0.3
    # empty strings
    assert _title_similarity("", "anything") == 0.0
    assert _title_similarity("anything", "") == 0.0
    # no alphabetic words
    assert _title_similarity("123 456", "abc") == 0.0
    # disjoint
    assert _title_similarity("rust async", "python flask") == 0.0


# ---------------------------------------------------------------------------
# detect_duplicates — mode dispatch
# ---------------------------------------------------------------------------
def test_detect_duplicates_exact_mode_groups_identical_urls():
    """Two bookmarks with identical URLs get the same duplicate_group_id."""
    bookmarks = [
        Bookmark(id="1", url="https://example.com", title="A"),
        Bookmark(id="2", url="https://example.com", title="B"),
        Bookmark(id="3", url="https://other.com", title="C"),
    ]
    result = detect_duplicates(bookmarks, mode="exact")
    assert result[0].duplicate_group_id == result[1].duplicate_group_id
    assert result[0].duplicate_group_id is not None
    assert result[2].duplicate_group_id is None
    assert result[0].duplicate_group_id.startswith("exact_")


def test_detect_duplicates_normalized_mode_groups_variants():
    """URLs differing only in trailing slash / www / https group together."""
    bookmarks = [
        Bookmark(id="1", url="https://www.example.com/", title="A"),
        Bookmark(id="2", url="http://example.com", title="B"),
        Bookmark(id="3", url="https://other.com", title="C"),
    ]
    result = detect_duplicates(bookmarks, mode="normalized")
    assert result[0].duplicate_group_id == result[1].duplicate_group_id
    assert result[0].duplicate_group_id.startswith("normalized_")
    assert result[2].duplicate_group_id is None


def test_detect_duplicates_hash_mode_groups_same_content():
    """Same normalized URL + lowercased title produce same hash -> grouped."""
    bookmarks = [
        Bookmark(id="1", url="https://www.example.com/", title="Hello"),
        Bookmark(id="2", url="http://example.com", title="hello"),
        Bookmark(id="3", url="https://other.com", title="hello"),
    ]
    result = detect_duplicates(bookmarks, mode="hash")
    assert result[0].duplicate_group_id == result[1].duplicate_group_id
    assert result[0].duplicate_group_id.startswith("hash_")
    assert result[2].duplicate_group_id is None


def test_detect_duplicates_fuzzy_mode_groups_similar_titles():
    """Similar titles above threshold are grouped; below threshold are not."""
    bookmarks = [
        Bookmark(id="1", url="https://a.com", title="Python Tutorial"),
        Bookmark(id="2", url="https://b.com", title="Python Tutorial Guide"),
        Bookmark(id="3", url="https://c.com", title="Rust Async Patterns"),
    ]
    # Jaccard({python,tutorial} & {python,tutorial,guide}) = 2/3 ~ 0.67 > 0.5 -> 1 & 2 grouped
    result = detect_duplicates(bookmarks, mode="fuzzy", similarity_threshold=0.5)
    assert result[0].duplicate_group_id == result[1].duplicate_group_id
    assert result[0].duplicate_group_id.startswith("fuzzy_")
    # 3 is its own group -> not marked
    assert result[2].duplicate_group_id is None


def test_detect_duplicates_fuzzy_mode_high_threshold_no_groups():
    """High threshold -> similar but not identical titles are NOT grouped."""
    bookmarks = [
        Bookmark(id="1", url="https://a.com", title="Python Tutorial"),
        Bookmark(id="2", url="https://b.com", title="Python Tutorials"),
        Bookmark(id="3", url="https://c.com", title="Rust Async"),
    ]
    result = detect_duplicates(bookmarks, mode="fuzzy", similarity_threshold=0.99)
    # No groups of >1 formed -> no duplicates marked
    assert all(bm.duplicate_group_id is None for bm in result)


def test_find_fuzzy_duplicates_threshold_controls_matches():
    """Lower threshold yields at least as many matches as higher threshold."""
    bookmarks = [
        Bookmark(id="1", url="https://a.com", title="Python Tutorial"),
        Bookmark(id="2", url="https://b.com", title="Python Tutorials"),
        Bookmark(id="3", url="https://c.com", title="Python Guide"),
    ]
    low = detect_duplicates(bookmarks, mode="fuzzy", similarity_threshold=0.3)
    high = detect_duplicates(bookmarks, mode="fuzzy", similarity_threshold=0.9)
    low_marked = sum(1 for bm in low if bm.duplicate_group_id is not None)
    high_marked = sum(1 for bm in high if bm.duplicate_group_id is not None)
    assert low_marked >= high_marked


# ---------------------------------------------------------------------------
# detect_duplicates — edge cases
# ---------------------------------------------------------------------------
def test_detect_duplicates_empty_input_returns_empty():
    """Empty bookmark list returns empty list without crashing."""
    assert detect_duplicates([], mode="exact") == []
    assert detect_duplicates([], mode="normalized") == []
    assert detect_duplicates([], mode="hash") == []
    assert detect_duplicates([], mode="fuzzy") == []


def test_detect_duplicates_single_bookmark_no_duplicates():
    """A single bookmark produces no duplicates and no group_id."""
    bookmarks = [Bookmark(id="1", url="https://example.com", title="Solo")]
    for mode in ("exact", "normalized", "hash", "fuzzy"):
        result = detect_duplicates(bookmarks, mode=mode)
        assert result[0].duplicate_group_id is None
        assert result[0].duplicate_urls == []


def test_detect_duplicates_all_unique_no_groups():
    """All-unique URLs -> no group_ids assigned."""
    bookmarks = [
        Bookmark(id="1", url="https://a.com", title="A"),
        Bookmark(id="2", url="https://b.com", title="B"),
        Bookmark(id="3", url="https://c.com", title="C"),
    ]
    for mode in ("exact", "normalized", "hash"):
        result = detect_duplicates(bookmarks, mode=mode)
        assert all(bm.duplicate_group_id is None for bm in result)


def test_detect_duplicates_unknown_mode_raises_value_error():
    """An unknown mode string raises ValueError."""
    with pytest.raises(ValueError, match="Unknown dedup mode"):
        detect_duplicates([], mode="bogus")


# ---------------------------------------------------------------------------
# _mark_groups — raw_folder_path merge branches (lines 138-142)
# ---------------------------------------------------------------------------
def test_mark_groups_merges_raw_folder_paths():
    """When duplicates have raw_folder_path, canonical absorbs the non-empty paths."""
    bookmarks = [
        Bookmark(id="1", url="https://example.com", title="A", raw_folder_path=None),
        Bookmark(id="2", url="https://example.com", title="B", raw_folder_path="folder1"),
        Bookmark(id="3", url="https://example.com", title="C", raw_folder_path="folder2"),
    ]
    result = detect_duplicates(bookmarks, mode="exact")
    # canonical (highest confidence_score; all 0.0 -> max returns first) absorbs both
    canonical = max(result, key=lambda bm: bm.confidence_score)
    assert "folder1" in (canonical.raw_folder_path or "")
    assert "folder2" in (canonical.raw_folder_path or "")


def test_mark_groups_appends_distinct_folder_path_with_separator():
    """Cover the elif branch: canonical already has a path, append distinct new one."""
    bookmarks = [
        Bookmark(
            id="1",
            url="https://example.com",
            title="A",
            raw_folder_path="existing",
            confidence_score=0.9,
        ),
        Bookmark(
            id="2",
            url="https://example.com",
            title="B",
            raw_folder_path="newfolder",
            confidence_score=0.1,
        ),
    ]
    result = detect_duplicates(bookmarks, mode="exact")
    canonical = max(result, key=lambda bm: bm.confidence_score)
    assert "existing" in canonical.raw_folder_path
    assert "newfolder" in canonical.raw_folder_path
    assert " | " in canonical.raw_folder_path


# ---------------------------------------------------------------------------
# deduplicate_bookmarks — legacy wrapper (lines 148-155)
# ---------------------------------------------------------------------------
def test_deduplicate_bookmarks_legacy_wrapper():
    """deduplicate_bookmarks returns (bookmarks, alias_map) for exact mode."""
    bookmarks = [
        Bookmark(id="1", url="https://example.com", title="A"),
        Bookmark(id="2", url="https://example.com", title="B"),
        Bookmark(id="3", url="https://other.com", title="C"),
    ]
    result, aliases = deduplicate_bookmarks(bookmarks)
    # bookmarks still a list
    assert len(result) == 3
    # aliases map contains the two duplicate ids
    assert "1" in aliases
    assert "2" in aliases
    assert "3" not in aliases
    # Both duplicate ids are in the alias map; the unique one is not.
    # When URLs are identical, each bookmark's duplicate_urls list is empty
    # (its own URL is filtered out of the shared URL set).
    assert "1" in aliases
    assert "2" in aliases
    assert "3" not in aliases
    assert aliases["1"] == []
    assert aliases["2"] == []


def test_deduplicate_bookmarks_no_duplicates_empty_aliases():
    """deduplicate_bookmarks with all-unique URLs returns empty alias map."""
    bookmarks = [
        Bookmark(id="1", url="https://a.com", title="A"),
        Bookmark(id="2", url="https://b.com", title="B"),
    ]
    result, aliases = deduplicate_bookmarks(bookmarks)
    assert len(result) == 2
    assert aliases == {}
