"""Regression tests for classifier behavior — pins current classification logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.classifier import BookmarkClassifier, classify_bookmarks
from cerebro.models import Bookmark
from cerebro.taxonomy import load_taxonomy

TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "taxonomy.yaml"


# ---------------------------------------------------------------------------
# Test 1: Domain rules correctly categorize known domains
# ---------------------------------------------------------------------------
def test_classify_bookmarks_domain_rules():
    """Known domains map to expected category breadcrumbs with high confidence."""
    bookmarks = [
        Bookmark(id="1", title="GitHub Repo", url="https://github.com/user/repo"),
        Bookmark(id="2", title="ArXiv Paper", url="https://arxiv.org/abs/1234.5678"),
        Bookmark(id="3", title="Stack Overflow Q", url="https://stackoverflow.com/questions/1"),
        Bookmark(id="4", title="HuggingFace Model", url="https://huggingface.co/bert-base"),
        Bookmark(id="5", title="Figma Design", url="https://figma.com/file/abc"),
        Bookmark(id="6", title="K8s Docs", url="https://kubernetes.io/docs/"),
        Bookmark(id="7", title="Docker Hub", url="https://docker.com/_/nginx"),
        Bookmark(id="8", title="Wikipedia Article", url="https://wikipedia.org/wiki/Python"),
        Bookmark(id="9", title="YouTube Video", url="https://youtube.com/watch?v=abc"),
        Bookmark(id="10", title="Reddit Thread", url="https://reddit.com/r/programming"),
    ]

    result = classify_bookmarks(bookmarks, TAXONOMY_PATH, train_ml=False)

    expected = {
        "1": (["Programming", "DevEx"], 0.90),
        "2": (["Learning", "Papers"], 0.90),
        "3": (["Programming", "DevEx"], 0.90),
        "4": (["AI", "Tools"], 0.90),
        "5": (["Design", "UI-UX"], 0.90),
        "6": (["Systems", "Containers"], 0.90),
        "7": (["Systems", "Containers"], 0.90),
        "8": (["Reference", "Wikipedia"], 0.90),
        "9": (["Learning", "Tutorials"], 0.90),
        "10": (["Entertainment", "Social-Media"], 0.90),
    }

    for bm in result:
        exp_breadcrumbs, exp_conf = expected[bm.id]
        assert bm.category_breadcrumbs == exp_breadcrumbs, (
            f"Bookmark {bm.id} ({bm.url}): expected {exp_breadcrumbs}, "
            f"got {bm.category_breadcrumbs}"
        )
        assert bm.confidence_score == exp_conf, (
            f"Bookmark {bm.id}: expected confidence {exp_conf}, got {bm.confidence_score}"
        )


# ---------------------------------------------------------------------------
# Test 2: Raw-folder hints are respected when no domain/keyword match
# ---------------------------------------------------------------------------
def test_classify_bookmarks_raw_folder_hints():
    """Bookmarks with raw_folder_path get mapped when no stronger signal exists."""
    bookmarks = [
        Bookmark(
            id="a",
            title="Zzz Nothing",
            url="ftp://unknown-site.example.com/zzz",
            raw_folder_path="coding/python",
        ),
        Bookmark(
            id="b",
            title="Aaa Blank",
            url="gopher://unknown-site.example.com/aaa",
            raw_folder_path="docker",
        ),
        Bookmark(
            id="c",
            title="Bbb Empty",
            url="file:///tmp/bbb",
            raw_folder_path="interview",
        ),
        Bookmark(
            id="d",
            title="Ccc Void",
            url="ftp://unknown-site.example.com/ccc",
            raw_folder_path="guitar",
        ),
    ]

    result = classify_bookmarks(bookmarks, TAXONOMY_PATH, train_ml=False)

    expected = {
        "a": (["Programming", "Languages"], 0.50),
        "b": (["Systems", "Containers"], 0.50),
        "c": (["Career", "Interview"], 0.50),
        "d": (["Life", "Hobbies"], 0.50),
    }

    for bm in result:
        exp_breadcrumbs, exp_conf = expected[bm.id]
        assert bm.category_breadcrumbs == exp_breadcrumbs, (
            f"Bookmark {bm.id} ({bm.raw_folder_path}): expected {exp_breadcrumbs}, "
            f"got {bm.category_breadcrumbs}"
        )
        assert bm.confidence_score == exp_conf, (
            f"Bookmark {bm.id}: expected confidence {exp_conf}, got {bm.confidence_score}"
        )


# ---------------------------------------------------------------------------
# Test 3: Single bookmark classify returns non-empty category path
# ---------------------------------------------------------------------------
def test_bookmark_classifier_classify_single():
    """BookmarkClassifier.classify on a single bookmark returns a non-empty path."""
    classifier = BookmarkClassifier(TAXONOMY_PATH)

    # Domain match
    breadcrumbs, confidence = classifier.classify(
        Bookmark(id="x", title="GH", url="https://github.com/torvalds/linux")
    )
    assert len(breadcrumbs) > 0, "Domain match should produce non-empty breadcrumbs"
    assert breadcrumbs == ["Programming", "DevEx"]
    assert confidence == 0.90

    # Keyword match (no domain rule for this URL)
    breadcrumbs, confidence = classifier.classify(
        Bookmark(
            id="y",
            title="Deep Learning with PyTorch",
            url="https://example.com/dl-pytorch",
        )
    )
    assert len(breadcrumbs) > 0, "Keyword match should produce non-empty breadcrumbs"
    assert confidence > 0.0

    # Fallback (no domain, no keyword, no raw folder — use non-HTTP URL to avoid
    # the "http" keyword matching the Networking rule)
    breadcrumbs, confidence = classifier.classify(
        Bookmark(
            id="z",
            title="Completely Unknown Page",
            url="ftp://xyz-random-123.example.com/",
        )
    )
    assert len(breadcrumbs) > 0, "Fallback should produce non-empty breadcrumbs"
    assert breadcrumbs == ["Reference", "Utilities"]
    assert confidence == 0.30


# ---------------------------------------------------------------------------
# Test 4: Deterministic behavior with keyword rules (no ML)
# ---------------------------------------------------------------------------
def test_classify_bookmarks_deterministic_keyword_rules():
    """With train_ml=False, classification is purely heuristic and deterministic."""
    bookmarks = [
        Bookmark(
            id="k1",
            title="Machine Learning Basics",
            url="https://example.com/ml-basics",
        ),
        Bookmark(
            id="k2",
            title="Transformer Architecture and LLMs",
            url="https://example.com/transformers",
        ),
        Bookmark(
            id="k3",
            title="Quantitative Trading Strategies",
            url="https://example.com/quant",
        ),
        Bookmark(
            id="k4",
            title="Portfolio Optimization Theory",
            url="https://example.com/portfolio",
        ),
    ]

    # Run twice — results must be identical
    result1 = classify_bookmarks(bookmarks, TAXONOMY_PATH, train_ml=False)
    result2 = classify_bookmarks(bookmarks, TAXONOMY_PATH, train_ml=False)

    for b1, b2 in zip(result1, result2, strict=True):
        assert b1.category_breadcrumbs == b2.category_breadcrumbs, (
            f"Bookmark {b1.id}: non-deterministic classification — "
            f"run1={b1.category_breadcrumbs}, run2={b2.category_breadcrumbs}"
        )
        assert b1.confidence_score == b2.confidence_score, (
            f"Bookmark {b1.id}: non-deterministic confidence — "
            f"run1={b1.confidence_score}, run2={b2.confidence_score}"
        )

    # Verify specific keyword matches
    expected = {
        "k1": ["AI", "Deep-Learning"],
        "k2": ["AI", "LLMs"],
        "k3": ["Quant", "Strategies"],
        "k4": ["Quant", "Portfolio"],
    }
    for bm in result1:
        assert bm.category_breadcrumbs == expected[bm.id], (
            f"Bookmark {bm.id}: expected {expected[bm.id]}, got {bm.category_breadcrumbs}"
        )


# ---------------------------------------------------------------------------
# Test 5: Taxonomy leaf names are respected in classification output
# ---------------------------------------------------------------------------
def test_taxonomy_leaf_names_respected():
    """Every category breadcrumb produced by the classifier is a valid taxonomy leaf."""
    taxonomy = load_taxonomy(TAXONOMY_PATH)
    valid_leaf_paths = {"/".join(leaf.breadcrumb[1:]) for leaf in taxonomy.all_leaves()}

    bookmarks = [
        Bookmark(id="t1", title="GitHub", url="https://github.com"),
        Bookmark(id="t2", title="ArXiv", url="https://arxiv.org"),
        Bookmark(id="t3", title="ML Tutorial", url="https://example.com/ml"),
        Bookmark(id="t4", title="Unknown", url="https://xyz.example.com"),
        Bookmark(
            id="t5",
            title="Python Guide",
            url="https://example.com/python",
            raw_folder_path="coding/python",
        ),
        Bookmark(id="t6", title="Docker", url="https://docker.com"),
        Bookmark(id="t7", title="Figma", url="https://figma.com"),
        Bookmark(id="t8", title="Wikipedia", url="https://wikipedia.org"),
        Bookmark(id="t9", title="YouTube", url="https://youtube.com"),
        Bookmark(id="t10", title="Reddit", url="https://reddit.com"),
    ]

    result = classify_bookmarks(bookmarks, TAXONOMY_PATH, train_ml=False)

    for bm in result:
        path = "/".join(bm.category_breadcrumbs)
        assert path in valid_leaf_paths, (
            f"Bookmark {bm.id}: category path '{path}' is not a valid taxonomy leaf. "
            f"Valid leaves include: {sorted(valid_leaf_paths)[:10]}..."
        )
