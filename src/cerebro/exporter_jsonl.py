"""Export bookmarks to JSONL (newline-delimited JSON)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.cerebro.models import Bookmark

logger = logging.getLogger("cerebro")


def export_jsonl(bookmarks: list[Bookmark], output_path: Path | str) -> Path:
    """Export bookmarks as JSONL (one JSON object per line)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for bm in bookmarks:
            f.write(json.dumps(bm.to_dict(), ensure_ascii=False) + "\n")

    logger.info(f"Exported {len(bookmarks)} bookmarks to JSONL: {output_path}")
    return output_path
