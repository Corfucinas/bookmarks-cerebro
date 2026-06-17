"""Bookmark metadata enrichment: tags, descriptions, domain info.

Re-exports ``extract_tags`` and ``generate_description`` for backwards
compatibility so callers can keep importing them from this module.
"""

from __future__ import annotations

import logging

from src.cerebro.description_generation import generate_description
from src.cerebro.models import Bookmark
from src.cerebro.tag_extraction import (
    CATEGORY_TAGS,
    STOP_WORDS,
    extract_tags,
)

logger = logging.getLogger("cerebro")

__all__ = [
    "CATEGORY_TAGS",
    "STOP_WORDS",
    "enrich_bookmark",
    "enrich_bookmarks",
    "extract_tags",
    "generate_description",
]


def enrich_bookmark(bookmark: Bookmark) -> Bookmark:
    """Enrich a single bookmark with tags and description."""
    bookmark.tags = extract_tags(bookmark)
    if not bookmark.description or bookmark.description_source == "synthetic":
        # Prefer fetched metadata in order: og_description > meta description > og_title > title
        fm = bookmark.fetched_metadata
        fetched_desc = fm.get("og_description") or fm.get("description")
        fetched_title = fm.get("og_title") or fm.get("title")
        if fetched_desc:
            bookmark.description = fetched_desc
            bookmark.description_source = "fetched"
        elif fetched_title and fetched_title != bookmark.title:
            bookmark.description = f"{fetched_title} | Source: {bookmark.domain}"
            bookmark.description_source = "fetched"
        else:
            bookmark.description = generate_description(bookmark)
            bookmark.description_source = "synthetic"
    else:
        # Even if we have an existing description, append fetched title if different
        fm = bookmark.fetched_metadata
        fetched_title = fm.get("og_title") or fm.get("title")
        if (
            fetched_title
            and fetched_title != bookmark.title
            and fetched_title not in bookmark.description
        ):
            bookmark.description = f"{fetched_title} | {bookmark.description}"
            bookmark.description_source = "fetched+enriched"
    return bookmark


def enrich_bookmarks(bookmarks: list[Bookmark]) -> list[Bookmark]:
    """Enrich all bookmarks in place."""
    total = len(bookmarks)
    logger.info(f"Enriching {total} bookmarks...")
    for i, bm in enumerate(bookmarks):
        enrich_bookmark(bm)
        if (i + 1) % 500 == 0:
            logger.info(f"Enriched {i + 1}/{total}")

    tag_counts = [len(bm.tags) for bm in bookmarks]
    n = len(tag_counts)
    avg_tags = sum(tag_counts) / n if tag_counts else 0
    median_tags = sorted(tag_counts)[n // 2] if tag_counts else 0
    logger.info(
        f"Tag stats: avg={avg_tags:.1f}, median={median_tags}, max={max(tag_counts) if tag_counts else 0}"
    )

    return bookmarks
