"""Live page fetching: HEAD requests, OG tag extraction, dead link detection.

Uses urllib (stdlib) to avoid adding new dependencies."""

from __future__ import annotations

import logging
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from bs4 import BeautifulSoup

from src.cerebro.models import Bookmark

logger = logging.getLogger("cerebro")

DEFAULT_TIMEOUT = 15
MAX_WORKERS = 20
RETRIES = 2

DEAD_STATUSES = {404, 410, 500, 502, 503, 504}
SOFT_DEAD_STATUSES = {401, 403, 429, 451}


def _is_dead(status: int | None) -> bool:
    if status is None:
        return True
    return status in DEAD_STATUSES


def _is_soft_dead(status: int | None) -> bool:
    return status in SOFT_DEAD_STATUSES if status else False


def _create_ssl_context() -> ssl.SSLContext:
    """Create permissive SSL context for broken cert sites."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _fetch_head(url: str, timeout: int) -> Any:
    """Perform HEAD request. Returns response or None on failure."""
    req = urllib.request.Request(url, method="HEAD")
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=_create_ssl_context())
    except urllib.error.HTTPError as e:
        # HTTPError is a subclass of addinfourl; return it so caller sees status
        return e
    except Exception:
        return None


def _fetch_get(url: str, timeout: int) -> Any:
    """Perform GET request."""
    req = urllib.request.Request(url, method="GET")
    req.add_header(
        "User-Agent",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=_create_ssl_context())
    except urllib.error.HTTPError as e:
        return e
    except Exception:
        return None


def _read_body(resp: Any) -> str:
    """Safely read and decode response body."""
    try:
        data = resp.read()
        content_type = resp.headers.get("Content-Type", "")
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
        decoded: str = data.decode(charset, errors="replace")
        return decoded
    except Exception:
        return ""


def _extract_og_tags(soup: BeautifulSoup) -> dict[str, str | None]:
    """Extract Open Graph and fallback meta tags."""
    og: dict[str, str | None] = {
        "title": None,
        "description": None,
        "image": None,
        "type": None,
    }
    for tag in soup.find_all("meta"):
        prop = tag.attrs.get("property", "")
        name = tag.attrs.get("name", "")
        raw_content = tag.attrs.get("content")
        content = raw_content if isinstance(raw_content, str) else None
        if prop == "og:title":
            og["title"] = content
        elif prop == "og:description":
            og["description"] = content
        elif prop == "og:image":
            og["image"] = content
        elif prop == "og:type":
            og["type"] = content
        elif name == "description" and not og["description"]:
            og["description"] = content
    return og


def _fetch_page(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Fetch URL: HEAD first, then GET for HTML. Returns metadata dict."""
    result: dict[str, Any] = {
        "status": None,
        "is_dead": True,
        "is_soft_dead": False,
        "title": None,
        "description": None,
        "og_title": None,
        "og_description": None,
        "og_image": None,
        "og_type": None,
        "canonical_url": None,
        "error": None,
    }

    # Try HEAD first
    head_resp = None
    for attempt in range(RETRIES):
        head_resp = _fetch_head(url, timeout)
        if head_resp is not None:
            break
        if attempt < RETRIES - 1:
            time.sleep(1)

    if head_resp is not None:
        try:
            status = head_resp.getcode()
        except AttributeError:
            status = 0
        result["status"] = status
        if _is_dead(status):
            result["is_dead"] = True
            return result
        if _is_soft_dead(status):
            result["is_soft_dead"] = True
        else:
            content_type = head_resp.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                result["is_dead"] = False
                return result

    # GET for body
    for attempt in range(RETRIES):
        get_resp = _fetch_get(url, timeout)
        if get_resp is None:
            if attempt < RETRIES - 1:
                time.sleep(1)
            continue

        try:
            status = get_resp.getcode()
        except AttributeError:
            status = 0
        result["status"] = status
        result["is_dead"] = _is_dead(status)
        result["is_soft_dead"] = _is_soft_dead(status)

        if status >= 400:
            return result

        content_type = get_resp.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            result["is_dead"] = False
            return result

        html = _read_body(get_resp)
        if not html:
            result["error"] = "Empty body"
            return result

        soup = BeautifulSoup(html, "html.parser")
        og = _extract_og_tags(soup)
        result["og_title"] = og.get("title")
        result["og_description"] = og.get("description")
        result["og_image"] = og.get("image")
        result["og_type"] = og.get("type")

        title_tag = soup.find("title")
        result["title"] = title_tag.get_text(strip=True) if title_tag else None

        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical and canonical.attrs.get("href"):
            result["canonical_url"] = canonical.attrs["href"]
        else:
            result["canonical_url"] = url

        return result

    result["error"] = "All GET attempts failed"
    return result


def fetch_bookmarks(
    bookmarks: list[Bookmark],
    max_workers: int = MAX_WORKERS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[Bookmark]:
    """Fetch all bookmarks in parallel. Dead links marked. OG tags stored."""
    total = len(bookmarks)
    logger.info(f"Fetching {total} bookmarks with {max_workers} workers...")

    fetched = 0
    dead = 0
    soft_dead = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_bm = {executor.submit(_fetch_page, bm.url, timeout): bm for bm in bookmarks}
        for future in as_completed(future_to_bm):
            bm = future_to_bm[future]
            try:
                result = future.result(timeout=timeout + 5)
            except Exception as e:
                logger.warning(f"Fetch exception for {bm.url}: {e}")
                result = {
                    "status": None,
                    "is_dead": True,
                    "is_soft_dead": False,
                    "error": str(e),
                }

            bm.fetched_metadata = result
            bm.is_dead_link = result.get("is_dead", True)
            bm.http_status = result.get("status")

            fetched += 1
            if result.get("is_dead"):
                dead += 1
            elif result.get("is_soft_dead"):
                soft_dead += 1

            if fetched % 100 == 0 or fetched == total:
                alive = fetched - dead - soft_dead
                logger.info(
                    f"Fetched {fetched}/{total} — dead={dead}, soft_dead={soft_dead}, alive={alive}"
                )

    alive = total - dead - soft_dead
    logger.info(f"Fetch complete: {total} total, {dead} dead, {soft_dead} soft-dead, {alive} alive")
    return bookmarks
