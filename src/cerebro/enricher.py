"""Bookmark metadata enrichment: tags, descriptions, domain info."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from .models import Bookmark
from .utils import extract_domain

logger = logging.getLogger("cerebro")

STOP_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "shall",
    "can",
    "need",
    "dare",
    "ought",
    "used",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "and",
    "but",
    "or",
    "yet",
    "so",
    "if",
    "because",
    "although",
    "though",
    "while",
    "where",
    "when",
    "that",
    "which",
    "who",
    "whom",
    "whose",
    "what",
    "this",
    "these",
    "those",
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
    "my",
    "your",
    "his",
    "its",
    "our",
    "their",
    "mine",
    "yours",
    "hers",
    "ours",
    "theirs",
    "myself",
    "yourself",
    "himself",
    "herself",
    "itself",
    "ourselves",
    "yourselves",
    "themselves",
    "how",
    "all",
    "any",
    "both",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "than",
    "too",
    "very",
    "just",
    "now",
    "then",
    "here",
    "there",
    "up",
    "down",
    "out",
    "off",
    "over",
    "again",
    "further",
    "once",
    "also",
    "back",
    "still",
    "even",
    "new",
    "good",
    "best",
    "better",
    "great",
    "first",
    "last",
    "long",
    "little",
    "own",
    "old",
    "right",
    "big",
    "high",
    "different",
    "small",
    "large",
    "next",
    "early",
    "young",
    "important",
    "few",
    "public",
    "bad",
    "same",
    "able",
    "via",
    "using",
    "use",
    "get",
    "gets",
    "make",
    "makes",
    "made",
    "one",
    "two",
    "three",
    "1",
    "2",
    "3",
    "10",
    "15",
    "20",
    "30",
    "50",
    "100",
}

CATEGORY_TAGS = {
    "AI/ML": ["ai", "machine-learning", "ml"],
    "Programming": ["programming", "software"],
    "Systems": ["infrastructure", "systems"],
    "Design": ["design", "frontend"],
    "Research": ["research", "learning"],
    "Productivity": ["productivity", "tools"],
    "Finance": ["finance", "trading"],
    "Life": ["life", "personal"],
    "Hardware": ["hardware", "iot"],
    "Career": ["career", "professional"],
    "Reference": ["reference", "utility"],
}


def extract_tags(bookmark: Bookmark) -> list[str]:
    """Extract tags from title, URL, and category."""
    tags: set[str] = set()

    if bookmark.category_breadcrumbs:
        top = bookmark.category_breadcrumbs[0]
        if top in CATEGORY_TAGS:
            tags.update(CATEGORY_TAGS[top])
        if len(bookmark.category_breadcrumbs) > 1:
            tags.add(bookmark.category_breadcrumbs[-1].lower().replace(" ", "-"))

    text = f"{bookmark.title} {bookmark.url}".lower()
    words = re.findall(r"[a-zA-Z]+(?:-[a-zA-Z]+)*", text)
    for word in words:
        word = word.strip("-").lower()
        if len(word) > 2 and word not in STOP_WORDS and not word.isdigit():
            tags.add(word)

    domain = extract_domain(bookmark.url)
    if domain:
        tags.add(domain.split(".")[0])

    path_parts = re.findall(r"/([a-zA-Z-]+)", bookmark.url)
    for part in path_parts:
        part = part.lower().strip("-")
        if len(part) > 2 and part not in STOP_WORDS:
            tags.add(part)

    return sorted([t for t in tags if len(t) > 2])[:15]


def generate_description(bookmark: Bookmark) -> str:
    """Generate synthetic description from available metadata."""
    parts = []

    if bookmark.title and bookmark.title != bookmark.url:
        parts.append(bookmark.title)

    if bookmark.domain:
        parts.append(f"Source: {bookmark.domain}")

    if bookmark.category_breadcrumbs:
        cat_str = " > ".join(bookmark.category_breadcrumbs)
        parts.append(f"Category: {cat_str}")

    if bookmark.tags:
        tag_str = ", ".join(bookmark.tags[:8])
        parts.append(f"Tags: {tag_str}")

    if bookmark.add_date_iso:
        parts.append(f"Added: {bookmark.add_date_iso[:10]}")

    return " | ".join(parts)


def enrich_bookmark(bookmark: Bookmark) -> Bookmark:
    """Enrich a single bookmark with tags and description."""
    bookmark.tags = extract_tags(bookmark)
    if not bookmark.description:
        bookmark.description = generate_description(bookmark)
        bookmark.description_source = "synthetic"
    return bookmark


def enrich_bookmarks(bookmarks: list[Bookmark]) -> list[Bookmark]:
    """Enrich all bookmarks in place."""
    logger.info(f"Enriching {len(bookmarks)} bookmarks...")
    for i, bm in enumerate(bookmarks):
        enrich_bookmark(bm)
        if (i + 1) % 500 == 0:
            logger.info(f"Enriched {i + 1}/{len(bookmarks)}")

    tag_counts = [len(bm.tags) for bm in bookmarks]
    avg_tags = sum(tag_counts) / len(tag_counts) if tag_counts else 0
    median_tags = sorted(tag_counts)[len(tag_counts) // 2] if tag_counts else 0
    logger.info(
        f"Tag stats: avg={avg_tags:.1f}, median={median_tags}, max={max(tag_counts) if tag_counts else 0}"
    )

    return bookmarks
