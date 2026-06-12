"""Export bookmarks to CSV."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.cerebro.models import Bookmark

logger = logging.getLogger("cerebro")


def export_csv(bookmarks: list[Bookmark], output_path: Path | str) -> Path:
    """Export bookmarks to CSV with flat fields."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "title",
        "url",
        "domain",
        "category",
        "tags",
        "description",
        "is_dead",
        "http_status",
        "duplicate_group",
        "related_count",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for bm in bookmarks:
            writer.writerow(
                {
                    "id": bm.id,
                    "title": bm.title,
                    "url": bm.url,
                    "domain": bm.domain,
                    "category": bm.category_path,
                    "tags": " | ".join(bm.tags),
                    "description": bm.description,
                    "is_dead": "1" if bm.is_dead_link else "0",
                    "http_status": bm.http_status or "",
                    "duplicate_group": bm.duplicate_group_id or "",
                    "related_count": len(bm.related_ids),
                }
            )

    logger.info(f"Exported {len(bookmarks)} bookmarks to CSV: {output_path}")
    return output_path
