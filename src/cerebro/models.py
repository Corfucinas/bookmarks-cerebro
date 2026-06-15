"""Core data models for Bookmarks Cerebro."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Bookmark:
    """Rich bookmark record."""

    id: str
    url: str
    title: str
    raw_folder_path: str | None = None
    add_date_epoch: str | None = None
    add_date_iso: str | None = None
    icon: str | None = None
    domain: str = ""
    tld_plus_one: str = ""
    category_breadcrumbs: list[str] = field(default_factory=list)
    confidence_score: float = 0.0
    tags: list[str] = field(default_factory=list)
    description: str = ""
    description_source: str = "synthetic"  # "fetched" | "synthetic" | ""
    inferred_metadata: dict[str, Any] = field(default_factory=dict)
    fetched_metadata: dict[str, Any] = field(default_factory=dict)
    duplicate_group_id: str | None = None
    duplicate_urls: list[str] = field(default_factory=list)
    is_dead_link: bool = False
    http_status: int | None = None
    related_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "raw_folder_path": self.raw_folder_path,
            "add_date_epoch": self.add_date_epoch,
            "add_date_iso": self.add_date_iso,
            "icon": self.icon,
            "domain": self.domain,
            "tld_plus_one": self.tld_plus_one,
            "category_breadcrumbs": self.category_breadcrumbs,
            "confidence_score": self.confidence_score,
            "tags": self.tags,
            "description": self.description,
            "description_source": self.description_source,
            "inferred_metadata": self.inferred_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Bookmark:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @property
    def category_path(self) -> str:
        return "/".join(self.category_breadcrumbs) if self.category_breadcrumbs else "Uncategorized"

    def to_full_dict(self) -> dict[str, Any]:
        """Serialize the full bookmark, including DB-only fields."""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "raw_folder_path": self.raw_folder_path,
            "add_date_epoch": self.add_date_epoch,
            "add_date_iso": self.add_date_iso,
            "icon": self.icon,
            "domain": self.domain,
            "tld_plus_one": self.tld_plus_one,
            "category_breadcrumbs": self.category_breadcrumbs,
            "confidence_score": self.confidence_score,
            "tags": self.tags,
            "description": self.description,
            "description_source": self.description_source,
            "inferred_metadata": self.inferred_metadata,
            "fetched_metadata": self.fetched_metadata,
            "duplicate_group_id": self.duplicate_group_id,
            "duplicate_urls": self.duplicate_urls,
            "is_dead_link": self.is_dead_link,
            "http_status": self.http_status,
            "related_ids": self.related_ids,
        }

    @property
    def safe_title(self) -> str:
        from src.cerebro.utils import safe_filename

        return safe_filename(self.title)
