"""Export enriched bookmarks to JSON."""

from __future__ import annotations

import gzip
import logging
from pathlib import Path
from typing import Any

from .models import Bookmark
from .utils import save_json

logger = logging.getLogger("cerebro")


def export_json(bookmarks: list[Bookmark], output_path: Path | str, compress: bool = True) -> Path:
    """Export bookmarks to JSON file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = [bm.to_dict() for bm in bookmarks]
    save_json(output_path, data, pretty=True)
    logger.info(f"Exported {len(bookmarks)} bookmarks to {output_path}")

    if compress:
        gz_path = output_path.with_suffix(output_path.suffix + ".gz")
        with open(output_path, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                f_out.write(f_in.read())
        logger.info(f"Compressed backup: {gz_path}")

    return output_path
