"""Netscape Bookmark HTML parser."""

from __future__ import annotations

import logging
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .models import Bookmark
from .utils import compute_id, epoch_to_iso, extract_domain, extract_tld_plus_one

logger = logging.getLogger("cerebro")


class BookmarkHTMLParser(HTMLParser):
    """Parse Netscape Bookmark HTML into Bookmark records."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.folder_stack: list[str] = []
        self.bookmarks: list[Bookmark] = []
        self._current_a_attrs: dict[str, str | None] = {}
        self._current_h3_attrs: dict[str, str | None] = {}
        self._in_h3 = False
        self._current_h3_text = ""
        self._in_a = False
        self._current_a_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        if tag == "h3":
            self._in_h3 = True
            self._current_h3_text = ""
            self._current_h3_attrs = attr_dict
        elif tag == "a":
            self._in_a = True
            self._current_a_text = ""
            self._current_a_attrs = attr_dict

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3":
            self._in_h3 = False
            folder_name = self._current_h3_text.strip()
            if folder_name:
                self.folder_stack.append(folder_name)
            self._current_h3_text = ""
        elif tag == "dl":
            if self.folder_stack:
                self.folder_stack.pop()
        elif tag == "a":
            self._in_a = False
            self._flush_bookmark()

    def handle_data(self, data: str) -> None:
        if self._in_h3:
            self._current_h3_text += data
        elif self._in_a:
            self._current_a_text += data

    def _flush_bookmark(self) -> None:
        href = self._current_a_attrs.get("href")
        if not href:
            return
        # Title from A tag text; fallback to title attribute; fallback to URL
        title = self._current_a_text.strip() or self._current_a_attrs.get("title") or ""
        if not title:
            title = href
        add_date = self._current_a_attrs.get("add_date")
        icon = self._current_a_attrs.get("icon")

        folder_path = "/".join(self.folder_stack) if self.folder_stack else None

        bookmark = Bookmark(
            id=compute_id(href, title),
            url=href,
            title=title,
            raw_folder_path=folder_path,
            add_date_epoch=add_date,
            add_date_iso=epoch_to_iso(add_date),
            icon=icon,
            domain=extract_domain(href),
            tld_plus_one=extract_tld_plus_one(href),
        )
        self.bookmarks.append(bookmark)
        self._current_a_attrs = {}
        self._current_a_text = ""

    def get_bookmarks(self) -> list[Bookmark]:
        return self.bookmarks


def parse_bookmarks(html_path: Path | str) -> list[Bookmark]:
    """Parse Netscape Bookmark HTML file."""
    html_path = Path(html_path)
    logger.info(f"Parsing {html_path}")

    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    parser = BookmarkHTMLParser()
    parser.feed(content)

    bookmarks = parser.get_bookmarks()
    logger.info(f"Parsed {len(bookmarks)} bookmarks")
    return bookmarks
