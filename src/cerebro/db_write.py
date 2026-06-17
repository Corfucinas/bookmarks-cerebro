"""Write-side CRUD helpers for the SQLite backend.

All functions take an open :class:`sqlalchemy.orm.Session` and mutate the
database within the caller's transaction (committed by the session scope).
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from src.cerebro.db_convert import _bookmark_to_row
from src.cerebro.db_read import get_bookmark
from src.cerebro.db_schema import audit_log_table, bookmarks_table, tags_table
from src.cerebro.models import Bookmark


def upsert_bookmark(session: Session, bookmark: Bookmark) -> None:
    """Insert a bookmark or update it on ``id`` conflict."""
    row = _bookmark_to_row(bookmark)
    stmt = sqlite_insert(bookmarks_table).values(row)
    update_dict = {k: stmt.excluded[k] for k in row if k != "id"}
    session.execute(stmt.on_conflict_do_update(index_elements=["id"], set_=update_dict))
    _sync_tags(session, bookmark)
    _log_action(session, bookmark.id, "upsert")


def _sync_tags(session: Session, bookmark: Bookmark) -> None:
    """Replace normalized tags for a bookmark."""
    session.execute(sa.delete(tags_table).where(tags_table.c.bookmark_id == bookmark.id))
    for tag in bookmark.tags:
        session.execute(
            sa.insert(tags_table).values(bookmark_id=bookmark.id, tag=tag),
        )


def _log_action(
    session: Session, bookmark_id: str, action: str, details: dict[str, Any] | None = None
) -> None:
    """Append an audit log entry."""
    session.execute(
        sa.insert(audit_log_table).values(
            action=action,
            bookmark_id=bookmark_id,
            details=details or {},
        ),
    )


def update_bookmark_tags(session: Session, bookmark_id: str, tags: list[str]) -> bool:
    """Replace tags for a bookmark. Returns True if the bookmark exists."""
    existing = get_bookmark(session, bookmark_id)
    if existing is None:
        return False
    existing.tags = list(tags)
    upsert_bookmark(session, existing)
    return True


def delete_bookmark(session: Session, bookmark_id: str) -> bool:
    """Delete a bookmark by ID. Returns True if a row was removed."""
    result = session.execute(
        sa.delete(bookmarks_table).where(bookmarks_table.c.id == bookmark_id),
    )
    _log_action(session, bookmark_id, "delete")
    return bool(getattr(result, "rowcount", 0))


def save_bookmarks(session: Session, bookmarks: list[Bookmark]) -> int:
    """Bulk upsert bookmarks and return the number written."""
    for bookmark in bookmarks:
        upsert_bookmark(session, bookmark)
    return len(bookmarks)


def append_bookmark_tags(session: Session, bookmark_id: str, tags: list[str]) -> bool:
    """Append unique tags to a bookmark, preserving existing order."""
    existing = get_bookmark(session, bookmark_id)
    if existing is None:
        return False
    ordered = list(existing.tags)
    seen = set(existing.tags)
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            ordered.append(tag)
    existing.tags = ordered
    upsert_bookmark(session, existing)
    return True


__all__ = [
    "upsert_bookmark",
    "update_bookmark_tags",
    "delete_bookmark",
    "save_bookmarks",
    "append_bookmark_tags",
]
