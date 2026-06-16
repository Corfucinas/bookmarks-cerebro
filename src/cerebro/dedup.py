"""Duplicate detection: exact URL, normalized URL, content hash, and fuzzy title similarity."""

from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict
from urllib.parse import urlparse

from src.cerebro.models import Bookmark

logger = logging.getLogger("cerebro")


def _normalize_url(url: str) -> str:
    """Strip protocol, www, trailing slash, and fragment for comparison."""
    url = url.lower().strip()
    parsed = urlparse(url)
    netloc = parsed.netloc or parsed.path.split("/")[0]
    netloc = netloc.removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{netloc}{path}"


def _content_hash(bookmark: Bookmark) -> str:
    """MD5 hash of normalized URL + lowercase title."""
    text = f"{_normalize_url(bookmark.url)}::{bookmark.title.lower().strip()}"
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:16]


def _title_similarity(a: str, b: str) -> float:
    """Simple Jaccard similarity over word sets."""
    words_a = set(re.findall(r"[a-zA-Z]+", a.lower()))
    words_b = set(re.findall(r"[a-zA-Z]+", b.lower()))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def detect_duplicates(
    bookmarks: list[Bookmark],
    mode: str = "exact",
    similarity_threshold: float = 0.85,
) -> list[Bookmark]:
    """Detect duplicates by exact URL, normalized URL, content hash, or fuzzy title.

    Modes:
      exact      — exact URL string match (default)
      normalized — ignore protocol/www/trailing-slash
      hash       — hash of normalized URL + title
      fuzzy      — Jaccard title similarity >= threshold
    """
    if mode == "exact":
        return _dedup_exact(bookmarks)
    if mode == "normalized":
        return _dedup_normalized(bookmarks)
    if mode == "hash":
        return _dedup_hash(bookmarks)
    if mode == "fuzzy":
        return _dedup_fuzzy(bookmarks, similarity_threshold)
    raise ValueError(f"Unknown dedup mode: {mode}")


def _dedup_exact(bookmarks: list[Bookmark]) -> list[Bookmark]:
    url_groups: dict[str, list[Bookmark]] = defaultdict(list)
    for bm in bookmarks:
        url_groups[bm.url].append(bm)
    return _mark_groups(bookmarks, url_groups, "exact")


def _dedup_normalized(bookmarks: list[Bookmark]) -> list[Bookmark]:
    groups: dict[str, list[Bookmark]] = defaultdict(list)
    for bm in bookmarks:
        groups[_normalize_url(bm.url)].append(bm)
    return _mark_groups(bookmarks, groups, "normalized")


def _dedup_hash(bookmarks: list[Bookmark]) -> list[Bookmark]:
    groups: dict[str, list[Bookmark]] = defaultdict(list)
    for bm in bookmarks:
        groups[_content_hash(bm)].append(bm)
    return _mark_groups(bookmarks, groups, "hash")


def _dedup_fuzzy(bookmarks: list[Bookmark], threshold: float) -> list[Bookmark]:
    """O(n²) pairwise title similarity — only use on small sets or sampled data."""
    n = len(bookmarks)
    visited = [False] * n
    groups: list[list[Bookmark]] = []

    for i in range(n):
        if visited[i]:
            continue
        group = [bookmarks[i]]
        visited[i] = True
        for j in range(i + 1, n):
            if visited[j]:
                continue
            sim = _title_similarity(bookmarks[i].title, bookmarks[j].title)
            if sim >= threshold:
                group.append(bookmarks[j])
                visited[j] = True
        if len(group) > 1:
            groups.append(group)

    group_map: dict[str, str] = {}
    for gidx, group in enumerate(groups):
        gid = f"fuzzy_{gidx:04d}"
        for bm in group:
            bm.duplicate_group_id = gid
            bm.duplicate_urls = [x.url for x in group if x.url != bm.url]
            group_map[bm.id] = gid

    logger.info(f"Fuzzy dedup: {len(groups)} groups, threshold={threshold}")
    return bookmarks


def _mark_groups(
    bookmarks: list[Bookmark],
    groups: dict[str, list[Bookmark]],
    mode: str,
) -> list[Bookmark]:
    duplicates_found = 0
    group_id = 0
    for _key, group in groups.items():
        if len(group) > 1:
            duplicates_found += len(group) - 1
            gid = f"{mode}_{group_id:04d}"
            group_id += 1
            canonical = max(group, key=lambda bm: bm.confidence_score)
            all_urls = {bm.url for bm in group}
            for bm in group:
                bm.duplicate_group_id = gid
                bm.duplicate_urls = [u for u in all_urls if u != bm.url]
                if bm.id != canonical.id and bm.raw_folder_path:
                    if not canonical.raw_folder_path:
                        canonical.raw_folder_path = bm.raw_folder_path
                    elif bm.raw_folder_path not in (canonical.raw_folder_path or "").split(" | "):
                        canonical.raw_folder_path += " | " + bm.raw_folder_path

    logger.info(f"Dedup ({mode}): {duplicates_found} duplicates across {group_id} groups")
    return bookmarks


def deduplicate_bookmarks(bookmarks: list[Bookmark]) -> tuple[list[Bookmark], dict[str, list[str]]]:
    """Legacy wrapper: exact dedup returning (bookmarks, alias_map)."""
    bookmarks = _dedup_exact(bookmarks)
    aliases: dict[str, list[str]] = defaultdict(list)
    for bm in bookmarks:
        if bm.duplicate_group_id:
            aliases[bm.id] = bm.duplicate_urls
    return bookmarks, dict(aliases)
