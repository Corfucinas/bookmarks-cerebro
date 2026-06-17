"""Domain and keyword heuristic rules for bookmark classification.

Aggregator module that re-exports the public rule constants:
- DOMAIN_RULES: high-confidence TLD+1 → taxonomy category path
- KEYWORD_RULES: keyword list → taxonomy category path with confidence

The underlying data lives in focused sub-modules to keep each file under
250 pure LOC:
- `classifier_domain_rules`: DOMAIN_RULES
- `classifier_keyword_rules_tech`: AI/Quant/Blockchain/Systems/Security keywords
- `classifier_keyword_rules_web`: Web/Design/Programming/Data/Career keywords
- `classifier_keyword_rules_life`: Career/Hardware/Productivity/Life/Learning/Reference keywords

This file concatenates the keyword sub-lists into the single KEYWORD_RULES
list that callers consume. Behavior is identical to the original monolithic
classifier.py — this is a pure file split.
"""

from __future__ import annotations

from src.cerebro.classifier_domain_rules import DOMAIN_RULES
from src.cerebro.classifier_keyword_rules_life import KEYWORD_RULES_HARDWARE_LIFE
from src.cerebro.classifier_keyword_rules_tech import KEYWORD_RULES_TECH_SECURITY
from src.cerebro.classifier_keyword_rules_web import KEYWORD_RULES_WEB_DEV_DATA

__all__ = ["DOMAIN_RULES", "KEYWORD_RULES"]

# Concatenation order matches the original KEYWORD_RULES list exactly.
KEYWORD_RULES: list[tuple[list[str], list[str], float]] = (
    KEYWORD_RULES_TECH_SECURITY + KEYWORD_RULES_WEB_DEV_DATA + KEYWORD_RULES_HARDWARE_LIFE
)
