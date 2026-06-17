"""Bookmark classifier — public API re-export shim.

The classifier has been split into focused modules:
- `classifier_rules`: DOMAIN_RULES + KEYWORD_RULES data tables (aggregator)
- `classifier_domain_rules`: DOMAIN_RULES data table
- `classifier_keyword_rules_tech`: AI/Quant/Blockchain/Systems/Security keywords
- `classifier_keyword_rules_web`: Web/Design/Programming/Data/Career keywords
- `classifier_keyword_rules_life`: Career/Hardware/Productivity/Life/Learning/Reference keywords
- `classifier_mapping`: raw folder → taxonomy mapping
- `classifier_ml`: TF-IDF + KNeighborsClassifier ML fallback
- `classifier_core`: BookmarkClassifier orchestration + classify_bookmarks

This file re-exports the public API so existing imports
(`from src.cerebro.classifier import classify_bookmarks, BookmarkClassifier`)
continue to work unchanged.
"""

from __future__ import annotations

from src.cerebro.classifier_core import BookmarkClassifier, classify_bookmarks

__all__ = ["BookmarkClassifier", "classify_bookmarks"]
