"""SQLAlchemy Core schema for Bookmarks Cerebro.

This module defines table metadata for the SQLite backend. It intentionally uses
SQLAlchemy Core (not ORM) to stay lightweight and dataclass-first.
"""

from __future__ import annotations

import sqlalchemy as sa

metadata = sa.MetaData()

bookmarks_table = sa.Table(
    "bookmarks",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("url", sa.String, nullable=False),
    sa.Column("title", sa.String, nullable=False),
    sa.Column("raw_folder_path", sa.String, nullable=True),
    sa.Column("add_date_epoch", sa.String, nullable=True),
    sa.Column("add_date_iso", sa.String, nullable=True),
    sa.Column("icon", sa.String, nullable=True),
    sa.Column("domain", sa.String, nullable=False, default=""),
    sa.Column("tld_plus_one", sa.String, nullable=False, default=""),
    sa.Column("category_breadcrumbs", sa.JSON, nullable=False, default=list),
    sa.Column("confidence_score", sa.Float, nullable=False, default=0.0),
    sa.Column("tags", sa.JSON, nullable=False, default=list),
    sa.Column("description", sa.Text, nullable=False, default=""),
    sa.Column("description_source", sa.String, nullable=False, default="synthetic"),
    sa.Column("inferred_metadata", sa.JSON, nullable=False, default=dict),
    sa.Column("fetched_metadata", sa.JSON, nullable=False, default=dict),
    sa.Column("duplicate_group_id", sa.String, nullable=True),
    sa.Column("duplicate_urls", sa.JSON, nullable=False, default=list),
    sa.Column("is_dead_link", sa.Boolean, nullable=False, default=False),
    sa.Column("http_status", sa.Integer, nullable=True),
    sa.Column("related_ids", sa.JSON, nullable=False, default=list),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    sa.Index("ix_bookmarks_url", "url"),
    sa.Index("ix_bookmarks_domain", "domain"),
    sa.Index("ix_bookmarks_is_dead_link", "is_dead_link"),
)

tags_table = sa.Table(
    "tags",
    metadata,
    sa.Column(
        "bookmark_id",
        sa.String,
        sa.ForeignKey("bookmarks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("tag", sa.String, primary_key=True),
    sa.Index("ix_tags_tag", "tag"),
)

audit_log_table = sa.Table(
    "audit_log",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("action", sa.String, nullable=False),
    sa.Column("bookmark_id", sa.String, nullable=False),
    sa.Column("details", sa.JSON, nullable=False, default=dict),
    sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
    sa.Index("ix_audit_log_bookmark_id", "bookmark_id"),
    sa.Index("ix_audit_log_timestamp", "timestamp"),
)


def create_tables(engine: sa.engine.Engine) -> None:
    """Create all schema objects on the supplied engine."""
    metadata.create_all(engine)


def drop_tables(engine: sa.engine.Engine) -> None:
    """Drop all schema objects on the supplied engine."""
    metadata.drop_all(engine)
