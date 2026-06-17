"""BookmarkClassifier orchestration: hybrid domain + keyword + ML + folder fallback.

This module owns the orchestration layer that ties together:
- DOMAIN_RULES / KEYWORD_RULES from `classifier_rules`
- Raw folder mapping from `classifier_mapping`
- ML fallback from `classifier_ml`

The public API (`BookmarkClassifier`, `classify_bookmarks`) is re-exported from
`classifier.py` for backward compatibility.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from src.cerebro.classifier_mapping import map_raw_folder
from src.cerebro.classifier_ml import MLClassifier
from src.cerebro.classifier_rules import DOMAIN_RULES, KEYWORD_RULES
from src.cerebro.models import Bookmark
from src.cerebro.taxonomy import load_taxonomy
from src.cerebro.utils import extract_tld_plus_one

logger = logging.getLogger("cerebro")

# Confidence constants — kept here as the orchestration layer owns the
# confidence assignment for each classification tier.
DOMAIN_MATCH_CONFIDENCE = 0.90
RAW_FOLDER_MATCH_CONFIDENCE = 0.50
DEFAULT_FALLBACK_CONFIDENCE = 0.30
DEFAULT_FALLBACK_CATEGORY: list[str] = ["Reference", "Utilities"]

# Re-classification threshold for the second pass after ML training.
RECLASSIFY_CONFIDENCE_THRESHOLD = 0.60


class BookmarkClassifier:
    """Classify bookmarks into taxonomy using a hybrid approach.

    Classification order (first match wins):
    1. Domain rules (high confidence)
    2. Keyword rules (medium-high confidence)
    3. ML fallback (if trained)
    4. Raw folder mapping (low confidence)
    5. Default fallback (lowest confidence)
    """

    def __init__(self, taxonomy_path: Path | str) -> None:
        self.taxonomy = load_taxonomy(taxonomy_path)
        self.leaves = self.taxonomy.all_leaves()
        self.ml = MLClassifier(self.leaves)

    def classify(self, bookmark: Bookmark) -> tuple[list[str], float]:
        """Return (breadcrumbs, confidence_score)."""
        domain = extract_tld_plus_one(bookmark.url)
        if domain in DOMAIN_RULES:
            breadcrumbs = DOMAIN_RULES[domain]
            return breadcrumbs, DOMAIN_MATCH_CONFIDENCE

        text = f"{bookmark.title} {bookmark.url}".lower()
        for keywords, breadcrumbs, confidence in KEYWORD_RULES:
            if any(kw in text for kw in keywords):
                return breadcrumbs, confidence

        if self.ml.ready:
            return self.ml.classify(text)

        if bookmark.raw_folder_path:
            mapped = map_raw_folder(bookmark.raw_folder_path)
            if mapped:
                return mapped, RAW_FOLDER_MATCH_CONFIDENCE

        return DEFAULT_FALLBACK_CATEGORY, DEFAULT_FALLBACK_CONFIDENCE

    def train_ml(self, bookmarks: list[Bookmark]) -> None:
        """Train ML fallback on already-classified bookmarks.

        Reads each bookmark's current `confidence_score` and
        `category_breadcrumbs` (set by the prior heuristic pass) to build
        the training set. This is behavior-equivalent to the original
        implementation which re-ran `classify()` on each bookmark, because
        at training time `ml.ready` is False and `classify()` returns the
        same deterministic heuristic result that the first pass already
        stored on the bookmark.
        """
        self.ml.train(bookmarks)


def classify_bookmarks(
    bookmarks: list[Bookmark],
    taxonomy_path: Path | str,
    train_ml: bool = True,
) -> list[Bookmark]:
    """Classify all bookmarks and return enriched list.

    Two-pass pipeline:
    1. Heuristic pass — domain + keyword + raw-folder fallback.
    2. (Optional) ML pass — train on high-confidence results, then
       re-classify low-confidence bookmarks using the trained model.
    """
    classifier = BookmarkClassifier(taxonomy_path)

    logger.info("Running heuristic classification...")
    for bm in bookmarks:
        breadcrumbs, confidence = classifier.classify(bm)
        bm.category_breadcrumbs = breadcrumbs
        bm.confidence_score = confidence

    if train_ml:
        logger.info("Training ML fallback...")
        classifier.train_ml(bookmarks)
        for bm in bookmarks:
            if bm.confidence_score < RECLASSIFY_CONFIDENCE_THRESHOLD:
                breadcrumbs, confidence = classifier.classify(bm)
                bm.category_breadcrumbs = breadcrumbs
                bm.confidence_score = confidence

    histogram = Counter(bm.category_path for bm in bookmarks)
    logger.info("Category distribution:")
    for path, count in histogram.most_common(15):
        logger.info(f"  {path}: {count}")

    return bookmarks
