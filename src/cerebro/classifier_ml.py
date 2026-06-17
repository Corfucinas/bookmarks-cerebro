"""ML fallback classifier: TF-IDF + KNeighborsClassifier.

Encapsulates the scikit-learn pipeline used as the fallback when domain
rules and keyword rules fail to categorize a bookmark. Training operates
on already-classified bookmarks (confidence >= 0.70) and produces a
vectorizer + KNN model that predicts taxonomy leaf indices.
"""

from __future__ import annotations

import logging

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import KNeighborsClassifier

from src.cerebro.models import Bookmark
from src.cerebro.taxonomy import TaxonomyNode

logger = logging.getLogger("cerebro")

# Minimum number of classified samples required before training the ML model.
# Below this threshold the ML fallback is left disabled.
MIN_TRAINING_SAMPLES = 100

# Confidence threshold for including a bookmark as a training sample.
TRAINING_CONFIDENCE_THRESHOLD = 0.70

# Fallback category and confidence returned when ML is unavailable or fails.
ML_FALLBACK_CATEGORY: list[str] = ["Reference", "Utilities"]
ML_FALLBACK_CONFIDENCE = 0.20


class MLClassifier:
    """TF-IDF + KNeighborsClassifier wrapper used as a classification fallback.

    Holds a fitted vectorizer and KNN model together with the leaf-name → index
    map used to translate predicted indices back into taxonomy breadcrumbs.
    """

    def __init__(self, leaves: list[TaxonomyNode]) -> None:
        self.leaves = leaves
        leaf_names = ["/".join(leaf.breadcrumb[1:]) for leaf in self.leaves]
        self.leaf_name_to_index: dict[str, int] = {name: idx for idx, name in enumerate(leaf_names)}
        self.ml_classifier: KNeighborsClassifier | None = None
        self.vectorizer: TfidfVectorizer | None = None
        self._ready = False

    @property
    def ready(self) -> bool:
        """True when both vectorizer and KNN model are fitted."""
        return self._ready

    def classify(self, text: str) -> tuple[list[str], float]:
        """Predict (breadcrumbs, confidence) for a lowercased text input.

        Falls back to a low-confidence default if the model is not fitted or
        if prediction raises. The broad except here is intentional: we treat
        any sklearn failure as "ML unavailable" and degrade gracefully.
        """
        if not self.ml_classifier or not self.vectorizer:
            return ML_FALLBACK_CATEGORY, ML_FALLBACK_CONFIDENCE
        try:
            x_matrix = self.vectorizer.transform([text])
            proba = self.ml_classifier.predict_proba(x_matrix)[0]
            pred_idx = int(np.argmax(proba))
            confidence = float(proba[pred_idx])
            leaf = self.leaves[pred_idx]
            return leaf.breadcrumb[1:], confidence
        except Exception as e:  # noqa: BLE001 - intentional graceful degradation
            logger.warning(f"ML classification failed: {e}")
            return ML_FALLBACK_CATEGORY, ML_FALLBACK_CONFIDENCE

    def train(self, bookmarks: list[Bookmark]) -> None:
        """Train the ML fallback on already-classified bookmarks.

        Only bookmarks whose current classification confidence meets
        TRAINING_CONFIDENCE_THRESHOLD are used as training samples. If fewer
        than MIN_TRAINING_SAMPLES are available, the ML model is left
        untrained and a warning is logged.
        """
        classified: list[str] = []
        labels: list[int] = []
        for bm in bookmarks:
            # NOTE: classification is computed by the caller (core orchestrator)
            # to avoid a circular dependency. We read the stored result.
            confidence = bm.confidence_score
            if confidence is None or confidence < TRAINING_CONFIDENCE_THRESHOLD:
                continue
            text = f"{bm.title} {bm.url}"
            classified.append(text)
            leaf_name = "/".join(bm.category_breadcrumbs)
            idx = self.leaf_name_to_index.get(leaf_name)
            if idx is not None:
                labels.append(idx)

        if len(classified) < MIN_TRAINING_SAMPLES:
            logger.warning(f"Not enough training data: {len(classified)} samples")
            return

        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            min_df=2,
            stop_words="english",
        )
        x_matrix = self.vectorizer.fit_transform(classified)
        self.ml_classifier = KNeighborsClassifier(n_neighbors=5, weights="distance")
        self.ml_classifier.fit(x_matrix, labels)
        self._ready = True
        logger.info(f"ML classifier trained on {len(classified)} samples")
