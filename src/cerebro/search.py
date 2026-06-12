"""Semantic search over enriched bookmarks using TF-IDF + cosine similarity.

Fast, dependency-light: reuses scikit-learn already required by classifier.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger("cerebro")


def _text_for_indexing(bookmark: dict[str, Any]) -> str:
    """Collapse bookmark fields into a single searchable string."""
    parts = [
        bookmark.get("title", ""),
        bookmark.get("description", ""),
        " ".join(bookmark.get("tags", [])),
        " ".join(bookmark.get("category_breadcrumbs", [])),
        bookmark.get("domain", ""),
    ]
    return " ".join(parts)


def build_index(
    bookmarks: list[dict[str, Any]],
) -> tuple[TfidfVectorizer, np.ndarray, list[dict[str, Any]]]:
    """Fit TF-IDF on all bookmarks and return (vectorizer, matrix, bookmarks)."""
    corpus = [_text_for_indexing(bm) for bm in bookmarks]
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(corpus)
    logger.info(f"Search index built: {matrix.shape[0]} docs, {matrix.shape[1]} terms")
    return vectorizer, matrix, bookmarks


def search(
    query: str,
    vectorizer: TfidfVectorizer,
    matrix: np.ndarray,
    bookmarks: list[dict[str, Any]],
    top_k: int = 10,
    min_score: float = 0.05,
) -> list[dict[str, Any]]:
    """Return top-k matching bookmarks with similarity scores."""
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, matrix).flatten()
    ranked = np.argsort(-scores)
    results = []
    for idx in ranked[:top_k]:
        score = float(scores[idx])
        if score < min_score:
            break
        bm = bookmarks[idx].copy()
        bm["search_score"] = round(score, 4)
        results.append(bm)
    return results


def search_from_file(
    json_path: Path,
    query: str,
    top_k: int = 10,
    min_score: float = 0.05,
) -> list[dict[str, Any]]:
    """Load enriched JSON, build index, run query, return results."""
    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)
    bookmarks = data.get("bookmarks", []) if isinstance(data, dict) else data
    vectorizer, matrix, bookmarks = build_index(bookmarks)
    return search(query, vectorizer, matrix, bookmarks, top_k, min_score)
