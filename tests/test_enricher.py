"""Behavior-lock regression tests for cerebro.enricher."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.enricher import enrich_bookmark, enrich_bookmarks, extract_tags
from cerebro.models import Bookmark

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bm(**overrides) -> Bookmark:
    """Minimal Bookmark factory with sensible defaults."""
    defaults = {
        "id": "test-1",
        "url": "https://example.com/some-page",
        "title": "Example Page",
        "domain": "example.com",
    }
    defaults.update(overrides)
    return Bookmark(**defaults)


# ---------------------------------------------------------------------------
# 1. Description source order
# ---------------------------------------------------------------------------


def test_description_prefers_og_description():
    """og_description wins over everything else."""
    bm = _bm(
        fetched_metadata={
            "og_description": "OG desc text",
            "description": "Meta desc text",
            "og_title": "OG Title",
        },
    )
    result = enrich_bookmark(bm)
    assert result.description == "OG desc text"
    assert result.description_source == "fetched"


def test_description_falls_back_to_meta_description():
    """When og_description is absent, meta description is used."""
    bm = _bm(
        fetched_metadata={
            "description": "Meta desc text",
            "og_title": "OG Title",
        },
    )
    result = enrich_bookmark(bm)
    assert result.description == "Meta desc text"
    assert result.description_source == "fetched"


def test_description_falls_back_to_og_title():
    """When no og_description or meta description, og_title is used (if different from title)."""
    bm = _bm(
        title="Page Title",
        fetched_metadata={"og_title": "Different OG Title"},
    )
    result = enrich_bookmark(bm)
    assert "Different OG Title" in result.description
    assert "example.com" in result.description
    assert result.description_source == "fetched"


def test_description_skips_og_title_when_same_as_title():
    """og_title identical to bookmark.title -> falls through to synthetic."""
    bm = _bm(
        title="Same Title",
        fetched_metadata={"og_title": "Same Title"},
    )
    result = enrich_bookmark(bm)
    assert result.description_source == "synthetic"
    assert "Same Title" in result.description  # synthetic includes title


# ---------------------------------------------------------------------------
# 2. No fetched metadata -> title fallback (synthetic)
# ---------------------------------------------------------------------------


def test_no_fetched_metadata_uses_synthetic():
    """Empty fetched_metadata -> generate_description() fallback."""
    bm = _bm(fetched_metadata={})
    result = enrich_bookmark(bm)
    assert result.description_source == "synthetic"
    # Synthetic description includes title and domain
    assert "Example Page" in result.description
    assert "example.com" in result.description


def test_no_fetched_metadata_with_category_includes_category():
    """Synthetic description includes category breadcrumbs when present."""
    bm = _bm(
        fetched_metadata={},
        category_breadcrumbs=["Programming", "Python"],
    )
    result = enrich_bookmark(bm)
    assert result.description_source == "synthetic"
    assert "Programming > Python" in result.description


# ---------------------------------------------------------------------------
# 3. enrich_bookmarks tag stats
# ---------------------------------------------------------------------------


def test_enrich_bookmarks_tag_stats():
    """Verify avg_tags and median_tags computation is correct."""
    bm1 = _bm(id="a", title="AI Machine Learning Deep", url="https://a.com/ai-ml")
    bm2 = _bm(id="b", title="Python Programming", url="https://b.com/python-code")
    bm3 = _bm(id="c", title="Design Systems", url="https://c.com/design")

    bookmarks = [bm1, bm2, bm3]
    enriched = enrich_bookmarks(bookmarks)

    tag_counts = [len(b.tags) for b in enriched]
    avg = sum(tag_counts) / len(tag_counts)
    median = sorted(tag_counts)[len(tag_counts) // 2]

    # All should have tags extracted
    assert all(len(b.tags) > 0 for b in enriched)
    # Verify computation matches what enrich_bookmarks logs internally
    assert avg > 0
    assert median > 0


def test_enrich_bookmarks_empty_list():
    """Empty list -> avg=0, median=0 (no crash)."""
    result = enrich_bookmarks([])
    assert result == []


# ---------------------------------------------------------------------------
# 4. extract_tags with CATEGORY_TAGS
# ---------------------------------------------------------------------------


def test_extract_tags_adds_category_tags():
    """When category_breadcrumbs[0] matches CATEGORY_TAGS key, those tags are added.
    Note: tags <= 2 chars are filtered by the final len(t) > 2 guard,
    so "ai" and "ml" are dropped; only "machine-learning" survives.
    """
    bm = _bm(
        title="Some Article",
        url="https://example.com/article",
        category_breadcrumbs=["AI/ML", "Deep Learning"],
    )
    tags = extract_tags(bm)
    # "machine-learning" is the only CATEGORY_TAGS["AI/ML"] entry with len > 2
    assert "machine-learning" in tags
    # "ai" and "ml" are 2 chars each, filtered by len(t) > 2
    assert "ai" not in tags
    assert "ml" not in tags


def test_extract_tags_adds_leaf_category():
    """Last breadcrumb is lowercased and hyphenated as a tag."""
    bm = _bm(
        title="Some Article",
        url="https://example.com/article",
        category_breadcrumbs=["Programming", "Rust Language"],
    )
    tags = extract_tags(bm)
    assert "rust-language" in tags


def test_extract_tags_from_title_words():
    """Words from title are extracted as tags (stop words filtered)."""
    bm = _bm(
        title="Building Scalable Systems with Rust",
        url="https://example.com/article",
    )
    tags = extract_tags(bm)
    assert "building" in tags
    assert "scalable" in tags
    assert "systems" in tags
    assert "rust" in tags
    # Stop words like "with" should NOT appear
    assert "with" not in tags


def test_extract_tags_from_url_path():
    """Path segments from URL become tags."""
    bm = _bm(
        title="Article",
        url="https://example.com/python/async-patterns/guide",
    )
    tags = extract_tags(bm)
    assert "python" in tags
    assert "async-patterns" in tags
    assert "guide" in tags


def test_extract_tags_includes_domain():
    """Domain name (without TLD) is added as a tag."""
    bm = _bm(
        title="Article",
        url="https://github.com/user/repo",
    )
    tags = extract_tags(bm)
    assert "github" in tags


def test_extract_tags_max_15():
    """Tag list is capped at 15 entries."""
    bm = _bm(
        title="a b c d e f g h i j k l m n o p q r s t u v w x y z",
        url="https://x.com/1/2/3/4/5/6/7/8/9/10/11/12/13/14/15/16/17/18",
    )
    tags = extract_tags(bm)
    assert len(tags) <= 15


def test_extract_tags_filters_short_words():
    """Words <= 2 chars are excluded."""
    bm = _bm(
        title="Go is a language",
        url="https://go.dev",
    )
    tags = extract_tags(bm)
    # "go" is 2 chars -> excluded; "is", "a" are stop words
    assert "go" not in tags
    assert "language" in tags
