#!/usr/bin/env python3
"""Parses a Netscape Bookmark file and generates a taxonomy analysis report."""

import json
import os
import sys
from collections import defaultdict
from html.parser import HTMLParser


class BookmarkParser(HTMLParser):
    """Custom parser for Netscape Bookmark HTML format."""

    def __init__(self):
        super().__init__()
        self.bookmarks = []
        self.folder_stack = []
        self.current_folder_attrs = None
        self.in_h3 = False
        self.h3_text = ""
        self.in_a = False
        self.a_attrs = {}
        self.a_text = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tag_lower = tag.lower()

        if tag_lower == "dl":
            if self.current_folder_attrs:
                folder_name = self.h3_text.strip()
                if folder_name:
                    self.folder_stack.append(
                        {
                            "name": folder_name,
                            "attrs": self.current_folder_attrs,
                        }
                    )
                self.current_folder_attrs = None
                self.h3_text = ""

        elif tag_lower == "h3":
            self.in_h3 = True
            self.h3_text = ""
            self.current_folder_attrs = attrs_dict

        elif tag_lower == "a":
            self.in_a = True
            self.a_attrs = attrs_dict
            self.a_text = ""

    def handle_endtag(self, tag):
        tag_lower = tag.lower()

        if tag_lower == "h3":
            self.in_h3 = False

        elif tag_lower == "a":
            self.in_a = False
            href = (self.a_attrs or {}).get("href", "").strip()
            title = self.a_text.strip()
            add_date = self.a_attrs.get("add_date", "")
            icon = self.a_attrs.get("icon", "")
            folder_path = " / ".join(f["name"] for f in self.folder_stack)
            self.bookmarks.append(
                {
                    "title": title,
                    "url": href,
                    "add_date": add_date,
                    "icon": icon,
                    "folder_path": folder_path,
                }
            )
            self.a_attrs = {}
            self.a_text = ""

        elif tag_lower == "dl":
            if self.folder_stack:
                self.folder_stack.pop()

    def handle_data(self, data):
        if self.in_h3:
            self.h3_text += data
        elif self.in_a:
            self.a_text += data


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_path = os.path.join(base_dir, "bookmarks_6_11_26.html")
    out_json = os.path.join(base_dir, "analysis", "taxonomy_report.json")

    if not os.path.isfile(input_path):
        print(f"Error: bookmark file not found at {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as fh:
        html_content = fh.read()

    parser = BookmarkParser()
    parser.feed(html_content)

    bookmarks = parser.bookmarks
    total_bookmarks = len(bookmarks)

    folder_counts = defaultdict(int)
    for bm in bookmarks:
        folder_counts[bm["folder_path"]] += 1

    top_20 = sorted(folder_counts.items(), key=lambda x: (-x[1], x[0]))[:20]
    top_10_names = [name for name, _ in top_20[:10]]

    sampled = {}
    for folder in top_10_names:
        bms = [bm for bm in bookmarks if bm["folder_path"] == folder]
        bms_sorted = sorted(bms, key=lambda x: (x["title"] or "").lower())
        sampled[folder] = [
            {
                "url": bm["url"],
                "title": bm["title"],
                "current_folder": bm["folder_path"],
            }
            for bm in bms_sorted[:5]
        ]

    # Build full taxonomy tree
    all_folders = set(folder_counts.keys())
    for path in list(all_folders):
        if not path:
            continue
        parts = path.split(" / ")
        for i in range(1, len(parts)):
            parent = " / ".join(parts[:i])
            all_folders.add(parent)

    nodes = {}
    for path in all_folders:
        parts = path.split(" / ") if path else []
        name = parts[-1] if parts else "Bookmarks"
        nodes[path] = {
            "name": name,
            "path": path,
            "bookmark_count": folder_counts.get(path, 0),
            "children": [],
        }

    root_key = ""
    if root_key not in nodes:
        nodes[root_key] = {
            "name": "Bookmarks",
            "path": "",
            "bookmark_count": 0,
            "children": [],
        }

    for path, node in nodes.items():
        if path == root_key:
            continue
        parts = path.split(" / ")
        parent_path = " / ".join(parts[:-1])
        parent = nodes.get(parent_path)
        if parent is not None:
            parent["children"].append(node)
        else:
            nodes[root_key]["children"].append(node)

    taxonomy = nodes[root_key]

    report = {
        "summary": {
            "total_bookmarks": total_bookmarks,
            "unique_leaf_folders": len(folder_counts),
            "top_20_overloaded_categories": [
                {"folder": name, "count": count} for name, count in top_20
            ],
        },
        "samples_from_top_10": sampled,
        "full_taxonomy": taxonomy,
    }

    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as jf:
        json.dump(report, jf, indent=2, ensure_ascii=False)

    print(f"Report written to {out_json}\n")

    print("=" * 60)
    print("BOOKMARK TAXONOMY ANALYSIS REPORT")
    print("=" * 60)
    print(f"Total bookmarks parsed: {total_bookmarks}")
    print(f"Unique leaf folders: {len(folder_counts)}\n")

    print("-" * 60)
    print("TOP 20 MOST OVERLOADED CATEGORIES")
    print("-" * 60)
    for rank, (name, count) in enumerate(top_20, 1):
        display = name if name else "(root)"
        print(f"{rank:2d}. {display:<50s} {count:4d}")

    print("\n" + "-" * 60)
    print("SAMPLE BOOKMARKS FROM TOP 10 OVERLOADED CATEGORIES")
    print("-" * 60)
    for idx, folder in enumerate(top_10_names, 1):
        count = folder_counts[folder]
        print(f"\n[{idx}] {folder or '(root)'}  ({count} bookmarks)")
        for s in sampled[folder]:
            print(f"    - {s['title'][:70]}")
            print(f"      URL: {s['url'][:80]}")

    print("\n" + "=" * 60)
    print("END OF REPORT")
    print("=" * 60)


if __name__ == "__main__":
    main()
