"""Synthetic description generation from bookmark metadata."""

from __future__ import annotations

from src.cerebro.models import Bookmark


def generate_description(bookmark: Bookmark) -> str:
    """Generate synthetic description from available metadata."""
    parts = []

    if bookmark.title and bookmark.title != bookmark.url:
        parts.append(bookmark.title)

    if bookmark.domain:
        parts.append(f"Source: {bookmark.domain}")

    if bookmark.category_breadcrumbs:
        cat_str = " > ".join(bookmark.category_breadcrumbs)
        parts.append(f"Category: {cat_str}")

    if bookmark.tags:
        tag_str = ", ".join(bookmark.tags[:8])
        parts.append(f"Tags: {tag_str}")

    if bookmark.add_date_iso:
        parts.append(f"Added: {bookmark.add_date_iso[:10]}")

    return " | ".join(parts)
