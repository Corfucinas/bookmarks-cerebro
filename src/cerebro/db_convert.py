"""Conversion helpers between ``Bookmark`` dataclass instances and DB rows.

These helpers are private to the persistence layer; callers should use the
public CRUD helpers in :mod:`src.cerebro.db_read` and :mod:`src.cerebro.db_write`.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from src.cerebro.models import Bookmark


def _bookmark_to_row(bookmark: Bookmark) -> dict[str, Any]:
    """Flatten a Bookmark dataclass into a DB row dict.

    JSON columns accept Python lists/dicts directly when passed to SQLAlchemy.
    """
    return {
        "id": bookmark.id,
        "url": bookmark.url,
        "title": bookmark.title,
        "raw_folder_path": bookmark.raw_folder_path,
        "add_date_epoch": bookmark.add_date_epoch,
        "add_date_iso": bookmark.add_date_iso,
        "icon": bookmark.icon,
        "domain": bookmark.domain,
        "tld_plus_one": bookmark.tld_plus_one,
        "category_breadcrumbs": bookmark.category_breadcrumbs,
        "confidence_score": bookmark.confidence_score,
        "tags": bookmark.tags,
        "description": bookmark.description,
        "description_source": bookmark.description_source,
        "inferred_metadata": bookmark.inferred_metadata,
        "fetched_metadata": bookmark.fetched_metadata,
        "duplicate_group_id": bookmark.duplicate_group_id,
        "duplicate_urls": bookmark.duplicate_urls,
        "is_dead_link": bookmark.is_dead_link,
        "http_status": bookmark.http_status,
        "related_ids": bookmark.related_ids,
    }


def _row_to_bookmark(row: sa.Row[Any]) -> Bookmark:
    """Hydrate a Bookmark from a bookmarks_table row."""
    return Bookmark(
        id=row.id,
        url=row.url,
        title=row.title,
        raw_folder_path=row.raw_folder_path,
        add_date_epoch=row.add_date_epoch,
        add_date_iso=row.add_date_iso,
        icon=row.icon,
        domain=row.domain or "",
        tld_plus_one=row.tld_plus_one or "",
        category_breadcrumbs=list(row.category_breadcrumbs or []),
        confidence_score=float(row.confidence_score or 0.0),
        tags=list(row.tags or []),
        description=row.description or "",
        description_source=row.description_source or "synthetic",
        inferred_metadata=dict(row.inferred_metadata or {}),
        fetched_metadata=dict(row.fetched_metadata or {}),
        duplicate_group_id=row.duplicate_group_id,
        duplicate_urls=list(row.duplicate_urls or []),
        is_dead_link=bool(row.is_dead_link),
        http_status=row.http_status,
        related_ids=list(row.related_ids or []),
    )


__all__ = ["_bookmark_to_row", "_row_to_bookmark"]
