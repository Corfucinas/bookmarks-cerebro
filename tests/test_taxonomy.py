"""Tests for cerebro.taxonomy."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.taxonomy import TaxonomyNode, load_taxonomy, validate_taxonomy

# ---------------------------------------------------------------------------
# load_taxonomy — empty / minimal files
# ---------------------------------------------------------------------------


def test_load_taxonomy_empty_file(tmp_path: Path):
    """An entirely empty YAML file must not crash; root has no children."""
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    root = load_taxonomy(empty)
    assert root.name == "__root__"
    assert len(root.children) == 0


def test_load_taxonomy_empty_roots_list(tmp_path: Path):
    """A YAML file with `roots: []` returns a root with no children."""
    f = tmp_path / "empty_roots.yaml"
    f.write_text("roots: []\n", encoding="utf-8")
    root = load_taxonomy(f)
    assert root.name == "__root__"
    assert len(root.children) == 0


def test_load_taxonomy_with_roots(tmp_path: Path):
    """Sanity check: a populated taxonomy loads children."""
    f = tmp_path / "taxonomy.yaml"
    f.write_text(
        "roots:\n"
        "  - name: AI\n"
        "    description: Artificial Intelligence\n"
        "    children:\n"
        "      - name: Models\n",
        encoding="utf-8",
    )
    root = load_taxonomy(f)
    assert len(root.children) == 1
    assert root.children[0].name == "AI"
    assert len(root.children[0].children) == 1


# ---------------------------------------------------------------------------
# validate_taxonomy — rule enforcement
# ---------------------------------------------------------------------------


def test_validate_taxonomy_valid():
    """The repo's taxonomy.yaml passes validation with default rules."""
    repo_root = Path(__file__).resolve().parents[1]
    root = load_taxonomy(repo_root / "taxonomy.yaml")
    errors = validate_taxonomy(root, rules={"max_top_level": 20})
    assert errors == [], f"Unexpected validation errors: {errors}"


def test_validate_taxonomy_too_many_top():
    """A root with more than max_top_level children is flagged."""
    root = TaxonomyNode(name="__root__")
    for i in range(20):
        root.children.append(TaxonomyNode(name=f"Cat{i}", parent=root))
    errors = validate_taxonomy(root, rules={"max_top_level": 15})
    assert any("Too many top-level" in e for e in errors)


def test_validate_taxonomy_too_deep():
    """A taxonomy exceeding max_depth is flagged."""
    root = TaxonomyNode(name="__root__")
    n = TaxonomyNode(name="L1", parent=root)
    root.children.append(n)
    n2 = TaxonomyNode(name="L2", parent=n)
    n.children.append(n2)
    n3 = TaxonomyNode(name="L3", parent=n2)
    n2.children.append(n3)
    n4 = TaxonomyNode(name="L4", parent=n3)
    n3.children.append(n4)
    errors = validate_taxonomy(root, rules={"max_depth": 3})
    assert any("exceeds max depth" in e for e in errors)


# ---------------------------------------------------------------------------
# TaxonomyNode — all_nodes, find, breadcrumb, is_leaf
# ---------------------------------------------------------------------------


def _small_tree() -> TaxonomyNode:
    root = TaxonomyNode(name="__root__")
    a = TaxonomyNode(name="A", parent=root)
    b = TaxonomyNode(name="B", parent=root)
    a1 = TaxonomyNode(name="A1", parent=a)
    a.children.append(a1)
    root.children.extend([a, b])
    return root


def test_taxonomy_node_all_nodes():
    """all_nodes returns the root plus every descendant."""
    root = _small_tree()
    names = [n.name for n in root.all_nodes()]
    assert names == ["__root__", "A", "A1", "B"]


def test_taxonomy_node_find_existing():
    """find locates a nested node by name."""
    root = _small_tree()
    found = root.find("A1")
    assert found is not None
    assert found.name == "A1"


def test_taxonomy_node_find_non_existing():
    """find returns None for an absent name."""
    root = _small_tree()
    assert root.find("ZZZ") is None


def test_taxonomy_node_breadcrumb():
    """breadcrumb returns the chain from root to the node."""
    root = _small_tree()
    a1 = root.find("A1")
    assert a1 is not None
    assert a1.breadcrumb == ["__root__", "A", "A1"]


def test_taxonomy_node_is_leaf():
    """is_leaf is True for childless nodes, False for parents."""
    root = _small_tree()
    a1 = root.find("A1")
    assert a1 is not None
    assert a1.is_leaf is True
    a = root.find("A")
    assert a is not None
    assert a.is_leaf is False


def test_taxonomy_node_all_leaves():
    """all_leaves returns only the leaf nodes."""
    root = _small_tree()
    leaves = [n.name for n in root.all_leaves()]
    assert leaves == ["A1", "B"]
