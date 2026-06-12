"""Exact-URL duplicate detection with alias preservation."""

from __future__ import annotations

import logging
from collections import defaultdict

from src.cerebro.models import Bookmark

logger = logging.getLogger("cerebro")


def detect_duplicates(bookmarks: list[Bookmark]) -> list[Bookmark]:
    """Group bookmarks by exact URL. Mark duplicates, preserve aliases."""
    url_groups: dict[str, list[Bookmark]] = defaultdict(list)
    for bm in bookmarks:
        url_groups[bm.url].append(bm)

    duplicates_found = 0
    group_id = 0
    for _url, group in url_groups.items():
        if len(group) > 1:
            duplicates_found += len(group) - 1
            gid = f"dup_{group_id:04d}"
            group_id += 1
            all_paths = [bm.raw_folder_path for bm in group if bm.raw_folder_path]
            all_urls = [bm.url for bm in group]
            # Pick canonical: highest confidence or first
            canonical = max(group, key=lambda bm: bm.confidence_score)
            for bm in group:
                bm.duplicate_group_id = gid
                bm.duplicate_urls = list(set(all_urls))
                if (
                    bm.id != canonical.id
                    and bm.raw_folder_path
                    and bm.raw_folder_path not in all_paths
                ):
                    all_paths.append(bm.raw_folder_path)

    logger.info(f"Duplicate detection: {duplicates_found} duplicates across {group_id} groups")
    return bookmarks
