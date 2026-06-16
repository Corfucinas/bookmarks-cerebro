"""Behavior-lock regression tests for cerebro.crosslinks.find_crosslinks."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.crosslinks import find_crosslinks
from cerebro.models import Bookmark


def _bm(
    id: str,
    url: str,
    title: str,
    tags: list[str] | None = None,
    description: str = "",
    domain: str = "",
    category_breadcrumbs: list[str] | None = None,
) -> Bookmark:
    """Minimal Bookmark factory for crosslinks tests."""
    return Bookmark(
        id=id,
        url=url,
        title=title,
        tags=tags or [],
        description=description,
        domain=domain,
        category_breadcrumbs=category_breadcrumbs or [],
    )


def test_shared_tags_3plus_creates_relation():
    """Bookmarks sharing 3+ tags get related_ids pointing to each other."""
    b1 = _bm("a", "https://x.com/1", "X1", tags=["rust", "async", "tokio", "web"])
    b2 = _bm("b", "https://y.com/2", "Y2", tags=["rust", "async", "tokio", "cli"])
    b3 = _bm("c", "https://z.com/3", "Z3", tags=["rust", "async"])  # only 2 shared

    result = find_crosslinks([b1, b2, b3])

    assert "b" in result[0].related_ids  # b1 sees b2 (3 shared: rust, async, tokio)
    assert "a" in result[1].related_ids  # b2 sees b1
    assert "c" not in result[0].related_ids  # b1-b3 only 2 shared
    assert "c" not in result[1].related_ids  # b2-b3 only 2 shared
    assert result[2].related_ids == []  # b3 has no 3+ shared with anyone


def test_shared_domain_creates_relation():
    """Bookmarks on the same domain get related_ids pointing to each other."""
    b1 = _bm("a", "https://docs.rs/tokio", "Tokio Docs", domain="docs.rs")
    b2 = _bm("b", "https://docs.rs/serde", "Serde Docs", domain="docs.rs")
    b3 = _bm("c", "https://crates.io/foo", "Crate Foo", domain="crates.io")

    result = find_crosslinks([b1, b2, b3])

    assert "b" in result[0].related_ids  # b1 sees b2 (same domain)
    assert "a" in result[1].related_ids  # b2 sees b1
    assert "c" not in result[0].related_ids  # different domain
    assert "c" not in result[1].related_ids


def test_url_mention_in_title_or_description_creates_relation():
    """A bookmark whose title/description contains another bookmark's URL gets related."""
    b1 = _bm("a", "https://docs.rs/tokio", "Tokio Docs")
    b2 = _bm(
        "b",
        "https://blog.x.com/post",
        "Great post about Tokio",
        description="See also https://docs.rs/tokio for the official docs",
    )
    b3 = _bm("c", "https://other.com/page", "Unrelated page")

    result = find_crosslinks([b1, b2, b3])

    assert "a" in result[1].related_ids  # b2 mentions b1's URL in description
    assert "b" not in result[0].related_ids  # b1 does not mention b2's URL
    assert result[2].related_ids == []  # b3 unrelated


def test_max_related_limit_respected():
    """find_crosslinks caps related_ids at 10 per bookmark."""
    # Create 12 bookmarks all sharing 3+ tags with a central bookmark
    shared_tags = ["rust", "async", "tokio"]
    center = _bm("center", "https://center.com", "Center", tags=shared_tags)
    satellites = [
        _bm(f"s{i}", f"https://sat{i}.com", f"Sat{i}", tags=shared_tags + [f"extra{i}"])
        for i in range(12)
    ]

    result = find_crosslinks([center] + satellites)

    center_related = result[0].related_ids
    assert len(center_related) <= 10
    # All satellites should be candidates, but only 10 make the cut
    assert all(rid.startswith("s") for rid in center_related)


def test_bookmark_not_related_to_self():
    """A bookmark never appears in its own related_ids."""
    b1 = _bm(
        "a",
        "https://docs.rs/tokio",
        "Tokio Docs",
        tags=["rust", "async", "tokio"],
        description="Check out https://docs.rs/tokio for details",
        domain="docs.rs",
    )

    result = find_crosslinks([b1])

    assert "a" not in result[0].related_ids
    assert result[0].related_ids == []
