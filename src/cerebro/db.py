"""SQLite persistence layer for Bookmarks Cerebro.

This module is a thin re-export facade. The implementation lives in focused
submodules:

- :mod:`src.cerebro.db_session` — session scope and database URL helpers
- :mod:`src.cerebro.db_convert` — Bookmark <-> row conversion (private)
- :mod:`src.cerebro.db_read` — read-only CRUD helpers
- :mod:`src.cerebro.db_write` — write-side CRUD helpers

The public API below is preserved for backward compatibility so existing
``from src.cerebro.db import ...`` imports continue to work unchanged.
"""

from __future__ import annotations

from src.cerebro.db_read import (
    count_bookmarks,
    count_dead_links,
    get_bookmark,
    get_bookmarks,
    get_dead_bookmarks,
    load_bookmarks,
    search_bookmarks,
    search_bookmarks_fts,
)
from src.cerebro.db_schema import create_tables
from src.cerebro.db_session import get_session
from src.cerebro.db_write import (
    append_bookmark_tags,
    delete_bookmark,
    save_bookmarks,
    update_bookmark_tags,
    upsert_bookmark,
)

__all__ = [
    "get_session",
    "upsert_bookmark",
    "get_bookmark",
    "get_bookmarks",
    "search_bookmarks",
    "search_bookmarks_fts",
    "update_bookmark_tags",
    "append_bookmark_tags",
    "delete_bookmark",
    "count_bookmarks",
    "count_dead_links",
    "get_dead_bookmarks",
    "save_bookmarks",
    "load_bookmarks",
    "create_tables",
]
