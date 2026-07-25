"""Taxonomy loader and validator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("cerebro")


@dataclass
class TaxonomyNode:
    name: str
    description: str = ""
    children: list[TaxonomyNode] = field(default_factory=list)
    parent: TaxonomyNode | None = None

    @property
    def breadcrumb(self) -> list[str]:
        if self.parent is None:
            return [self.name]
        return self.parent.breadcrumb + [self.name]

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def all_leaves(self) -> list[TaxonomyNode]:
        if self.is_leaf:
            return [self]
        leaves = []
        for child in self.children:
            leaves.extend(child.all_leaves())
        return leaves

    def all_nodes(self) -> list[TaxonomyNode]:
        nodes = [self]
        for child in self.children:
            nodes.extend(child.all_nodes())
        return nodes

    def find(self, name: str) -> TaxonomyNode | None:
        if self.name == name:
            return self
        for child in self.children:
            result = child.find(name)
            if result:
                return result
        return None


def load_taxonomy(path: Path | str) -> TaxonomyNode:
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    root_data = data.get("roots", [])
    virtual_root = TaxonomyNode(name="__root__", description="Virtual root")

    for root_item in root_data:
        node = _build_node(root_item, parent=virtual_root)
        virtual_root.children.append(node)

    return virtual_root


def _build_node(data: dict[str, Any], parent: TaxonomyNode) -> TaxonomyNode:
    node = TaxonomyNode(
        name=data["name"],
        description=data.get("description", ""),
        parent=parent,
    )
    for child_data in data.get("children", []):
        child = _build_node(child_data, parent=node)
        node.children.append(child)
    return node


def validate_taxonomy(root: TaxonomyNode, rules: dict[str, int] | None = None) -> list[str]:
    errors = []
    rules = rules or {}
    max_top = rules.get("max_top_level", 15)
    max_depth = rules.get("max_depth", 3)

    if len(root.children) > max_top:
        errors.append(f"Too many top-level categories: {len(root.children)} > {max_top}")

    for node in root.all_nodes():
        depth = len(node.breadcrumb) - 1
        if depth > max_depth:
            errors.append(f"Node '{node.name}' exceeds max depth {max_depth}")

    return errors
