"""Cross-link detection: find bookmarks that reference each other."""

from __future__ import annotations

import logging
import re
from collections import defaultdict

from src.cerebro.models import Bookmark

logger = logging.getLogger("cerebro")

_URL_PATTERN = re.compile(r"https?://[^\s\"'<>)>]+")


def _normalize_url_for_match(url: str) -> str:
    """Normalize URL for mention matching: strip protocol, www, trailing slash."""
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


def _find_url_mentions(bookmarks: list[Bookmark], url_to_id: dict[str, str]) -> dict[str, set[str]]:
    """Detect bookmarks whose title/description mention another bookmark's URL."""
    related: dict[str, set[str]] = defaultdict(set)
    for bm in bookmarks:
        text = f"{bm.title} {bm.description}"
        for match in _URL_PATTERN.findall(text):
            target_id = url_to_id.get(_normalize_url_for_match(match))
            if target_id and target_id != bm.id:
                related[bm.id].add(target_id)
    return related


def _find_domain_relations(
    domain_groups: dict[str, list[str]],
) -> dict[str, set[str]]:
    """Cross-reference bookmarks sharing the same domain."""
    related: dict[str, set[str]] = defaultdict(set)
    for ids in domain_groups.values():
        if len(ids) > 1:
            for bm_id in ids:
                related[bm_id].update(i for i in ids if i != bm_id)
    return related


def _find_tag_relations(
    bookmarks: list[Bookmark],
    tag_groups: dict[str, list[str]],
) -> dict[str, set[str]]:
    """Cross-reference bookmarks sharing 3+ tags."""
    related: dict[str, set[str]] = defaultdict(set)
    for bm in bookmarks:
        candidate_scores: dict[str, int] = defaultdict(int)
        for tag in bm.tags:
            for other_id in tag_groups[tag]:
                if other_id != bm.id:
                    candidate_scores[other_id] += 1
        for other_id, score in candidate_scores.items():
            if score >= 3:
                related[bm.id].add(other_id)
    return related


def _find_category_relations(
    cat_groups: dict[str, list[str]],
) -> dict[str, set[str]]:
    """Cross-reference bookmarks in the same top-level category."""
    related: dict[str, set[str]] = defaultdict(set)
    for ids in cat_groups.values():
        if len(ids) > 1:
            for bm_id in ids:
                related[bm_id].update(i for i in ids if i != bm_id)
    return related


def _top_related(
    bookmark: Bookmark,
    related: dict[str, set[str]],
    bm_by_id: dict[str, Bookmark],
    limit: int = 10,
) -> list[str]:
    """Score, sort, and limit the related ids for a single bookmark."""
    rel_ids = related.get(bookmark.id, set())
    my_tags = set(bookmark.tags)
    scores: dict[str, int] = {}
    for rid in rel_ids:
        other = bm_by_id.get(rid)
        if other:
            scores[rid] = len(my_tags & set(other.tags))
    return sorted(scores, key=lambda k: scores[k], reverse=True)[:limit]


def find_crosslinks(bookmarks: list[Bookmark]) -> list[Bookmark]:
    """Find related bookmarks by URL mentions, shared domain, shared tags, and category overlap.

    Populates `related_ids` on each bookmark.
    """
    url_to_id = {_normalize_url_for_match(bm.url): bm.id for bm in bookmarks}
    domain_groups: dict[str, list[str]] = defaultdict(list)
    tag_groups: dict[str, list[str]] = defaultdict(list)
    cat_groups: dict[str, list[str]] = defaultdict(list)

    for bm in bookmarks:
        domain = bm.domain or ""
        if domain:
            domain_groups[domain].append(bm.id)
        for tag in bm.tags:
            tag_groups[tag].append(bm.id)
        cat_key = "/".join(bm.category_breadcrumbs[:2]) if bm.category_breadcrumbs else ""
        if cat_key:
            cat_groups[cat_key].append(bm.id)

    related: dict[str, set[str]] = defaultdict(set)
    for chunk in (
        _find_url_mentions(bookmarks, url_to_id),
        _find_domain_relations(domain_groups),
        _find_tag_relations(bookmarks, tag_groups),
        _find_category_relations(cat_groups),
    ):
        for bm_id, ids in chunk.items():
            related[bm_id].update(ids)

    bm_by_id = {bm.id: bm for bm in bookmarks}
    for bm in bookmarks:
        bm.related_ids = _top_related(bm, related, bm_by_id)

    total_links = sum(len(bm.related_ids) for bm in bookmarks)
    logger.info(f"Cross-links: {total_links} relations across {len(bookmarks)} bookmarks")
    return bookmarks
