"""Cross-link detection: find bookmarks that reference each other."""

from __future__ import annotations

import logging
import re
from collections import defaultdict

from src.cerebro.models import Bookmark

logger = logging.getLogger("cerebro")


def find_crosslinks(bookmarks: list[Bookmark]) -> list[Bookmark]:
    """Find related bookmarks by URL mentions, shared domain, shared tags, and category overlap.

    Populates `related_ids` on each bookmark.
    """
    url_to_id = {bm.url: bm.id for bm in bookmarks}
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

    # 1. URL mentions in title/description
    url_pattern = re.compile(r"https?://[^\s\"'<>)>]+")
    for bm in bookmarks:
        text = f"{bm.title} {bm.description}"
        for match in url_pattern.findall(text):
            target_id = url_to_id.get(match)
            if target_id and target_id != bm.id:
                related[bm.id].add(target_id)

    # 2. Shared domain (exclude self)
    for _domain, ids in domain_groups.items():
        if len(ids) > 1:
            for bm_id in ids:
                related[bm_id].update(i for i in ids if i != bm_id)

    # 3. Shared tags (3+ shared tags = strong relation)
    for bm in bookmarks:
        candidate_scores: dict[str, int] = defaultdict(int)
        for tag in bm.tags:
            for other_id in tag_groups[tag]:
                if other_id != bm.id:
                    candidate_scores[other_id] += 1
        for other_id, score in candidate_scores.items():
            if score >= 3:
                related[bm.id].add(other_id)

    # 4. Same top-2 category
    for _cat, ids in cat_groups.items():
        if len(ids) > 1:
            for bm_id in ids:
                related[bm_id].update(i for i in ids if i != bm_id)

    # Limit to top 10 related per bookmark by score
    for bm in bookmarks:
        rel_ids = related.get(bm.id, set())
        # Score by number of shared tags
        scores: dict[str, int] = {}
        my_tags = set(bm.tags)
        for rid in rel_ids:
            other = next((b for b in bookmarks if b.id == rid), None)
            if other:
                scores[rid] = len(my_tags & set(other.tags))
        top = sorted(scores, key=lambda k: scores[k], reverse=True)[:10]
        bm.related_ids = top

    total_links = sum(len(bm.related_ids) for bm in bookmarks)
    logger.info(f"Cross-links: {total_links} relations across {len(bookmarks)} bookmarks")
    return bookmarks
