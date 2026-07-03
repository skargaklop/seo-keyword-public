#!/usr/bin/env python3
"""Bounded BFS crawler for SEO leak audit."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
import urllib3
from bs4 import BeautifulSoup

try:
    import validators
except (
    ModuleNotFoundError
):  # pragma: no cover - optional fallback for bare environments
    validators = None

from extract_signals import extract_signals

USER_AGENT = "seo-google-leak-deep-audit/1.0 (+https://local)"
SKIP_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".zip",
    ".rar",
    ".mp4",
    ".mp3",
    ".css",
    ".js",
    ".xml",
    ".json",
}
SKIP_PATH_PATTERNS = (
    r"/calendar",
    r"/wp-admin",
    r"/cart",
    r"/checkout",
    r"/login",
    r"/tag/",
    r"/author/.+/.+/.+/.+",
)
PAGINATION_QUERY_KEYS = {
    "page",
    "paged",
    "p",
    "pg",
    "page_no",
    "pagenumber",
    "offset",
    "start",
    "stranica",
    "pagina",
}
PAGINATION_SUPPORT_QUERY_KEYS = {
    "limit",
    "per_page",
    "page_size",
    "items_per_page",
    "count",
}
TRACKING_QUERY_KEY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {
    "gclid",
    "fbclid",
    "yclid",
    "msclkid",
    "_ga",
    "_gid",
    "_gac",
}
MAX_SITEMAP_FILES = 50


def _is_http_url(value: str) -> bool:
    parsed = urlparse((value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_pagination_query(query: str) -> str:
    if not query:
        return ""
    normalized_pairs: list[tuple[str, str]] = []
    has_pagination_key = False
    for key, value in parse_qsl(query, keep_blank_values=False):
        key_norm = str(key).strip().lower()
        value_norm = str(value).strip()
        if not key_norm or not value_norm:
            return ""
        if key_norm in PAGINATION_QUERY_KEYS:
            has_pagination_key = True
        elif key_norm not in PAGINATION_SUPPORT_QUERY_KEYS:
            return ""
        if not re.fullmatch(r"\d{1,6}", value_norm):
            return ""
        normalized_pairs.append((key_norm, str(int(value_norm))))

    if not has_pagination_key:
        return ""

    normalized_pairs.sort()
    return urlencode(normalized_pairs, doseq=True)

def _normalize_generic_query(query: str) -> str:
    if not query:
        return ""
    normalized_pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(query, keep_blank_values=False):
        key_norm = str(key).strip()
        value_norm = str(value).strip()
        if not key_norm or not value_norm:
            continue
        key_lower = key_norm.lower()
        if key_lower.startswith(TRACKING_QUERY_KEY_PREFIXES) or key_lower in TRACKING_QUERY_KEYS:
            continue
        normalized_pairs.append((key_lower, value_norm))
    if not normalized_pairs:
        return ""
    normalized_pairs.sort()
    return urlencode(normalized_pairs, doseq=True)


def _normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc
    path = parsed.path or "/"
    query = parsed.query
    if not netloc and parsed.path:
        # Handles strings like example.com/path
        reparsed = urlparse(f"{scheme}://{raw}")
        netloc = reparsed.netloc
        path = reparsed.path or "/"
        query = reparsed.query
    if not netloc:
        return ""
    path = re.sub(r"/{2,}", "/", path)
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    normalized_query = _normalize_pagination_query(query)
    if query and not normalized_query:
        normalized_query = _normalize_generic_query(query)
    return urlunparse((scheme.lower(), netloc.lower(), path, "", normalized_query, ""))


def _is_internal(url: str, base_host: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.lower() == base_host.lower()


def _looks_like_trap(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.query and not _normalize_pagination_query(parsed.query):
        # Keep crawl deterministic and avoid parameter traps.
        return True
    lower_path = parsed.path.lower()
    if any(lower_path.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
    if any(re.search(pattern, lower_path) for pattern in SKIP_PATH_PATTERNS):
        return True
    if re.search(r"/\d{4}/\d{2}/\d{2}", lower_path):
        return True
    return False


def _is_safe_seed_url(url: str) -> bool:
    parsed = urlparse(url)
    if not parsed.query:
        return True
    if _normalize_pagination_query(parsed.query):
        return True
    if len(parsed.query) > 80:
        return False
    pairs = parse_qsl(parsed.query, keep_blank_values=False)
    if not pairs or len(pairs) > 3:
        return False
    for key, value in pairs:
        key_lower = str(key or "").strip().lower()
        value_norm = str(value or "").strip()
        if not key_lower or not value_norm:
            return False
        if key_lower.startswith(TRACKING_QUERY_KEY_PREFIXES) or key_lower in TRACKING_QUERY_KEYS:
            return False
        if len(value_norm) > 64:
            return False
    return True


def _make_robot_parser(start_url: str) -> RobotFileParser | None:
    parsed = urlparse(start_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    robot_parser = RobotFileParser()
    robot_parser.set_url(robots_url)
    try:
        robot_parser.read()
    except Exception:
        return None
    return robot_parser


def _load_source_text(
    source: str, session: requests.Session, timeout: int
) -> tuple[str, str] | None:
    source_value = (source or "").strip()
    if not source_value:
        return None

    if _is_http_url(source_value):
        try:
            response = session.get(source_value, timeout=timeout, allow_redirects=True)
        except requests.exceptions.SSLError:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            try:
                response = session.get(
                    source_value,
                    timeout=timeout,
                    allow_redirects=True,
                    verify=False,
                )
            except requests.RequestException:
                return None
        except requests.RequestException:
            return None
        if int(response.status_code) >= 400:
            return None
        payload = response.content
        if str(response.url).lower().endswith(".gz"):
            try:
                payload = gzip.decompress(payload)
            except OSError:
                pass
        return payload.decode("utf-8", errors="ignore"), str(response.url)

    source_path = Path(source_value)
    if not source_path.exists() or not source_path.is_file():
        return None
    payload = source_path.read_bytes()
    if source_path.suffix.lower() == ".gz":
        try:
            payload = gzip.decompress(payload)
        except OSError:
            pass
    return payload.decode("utf-8", errors="ignore"), str(source_path.resolve())


def _xml_tag_name(tag: str) -> str:
    return str(tag).split("}", 1)[-1].lower()


def _xml_child_elements(node: ET.Element, child_tag: str) -> list[ET.Element]:
    target = child_tag.lower()
    return [child for child in list(node) if _xml_tag_name(child.tag) == target]


def _xml_first_child_text(node: ET.Element, child_tag: str) -> str:
    for child in _xml_child_elements(node, child_tag):
        text_value = (child.text or "").strip()
        if text_value:
            return text_value
    return ""


def _parse_sitemap_document(
    root: ET.Element,
    source_reference: str,
    fallback_base_url: str,
) -> tuple[list[str], set[str]]:
    """Return nested sitemap sources and page URLs from a sitemap XML document."""
    nested_sources: list[str] = []
    page_urls: set[str] = set()
    root_name = _xml_tag_name(root.tag)

    if root_name == "sitemapindex":
        for sitemap_node in _xml_child_elements(root, "sitemap"):
            loc_value = _xml_first_child_text(sitemap_node, "loc")
            if not loc_value:
                continue
            nested_source = _resolve_sitemap_reference(
                loc_value,
                source_reference=source_reference,
                fallback_base_url=fallback_base_url,
            )
            if nested_source:
                nested_sources.append(nested_source)
        return nested_sources, page_urls

    if root_name == "urlset":
        for url_node in _xml_child_elements(root, "url"):
            loc_value = _xml_first_child_text(url_node, "loc")
            if not loc_value:
                continue
            page_url = _resolve_page_reference(
                loc_value,
                source_reference=source_reference,
                fallback_base_url=fallback_base_url,
            )
            normalized = _normalize_url(page_url)
            if normalized:
                page_urls.add(normalized)
        return nested_sources, page_urls

    # Fallback: accept generic <loc> for non-standard sitemap-like files.
    for node in root.iter():
        if _xml_tag_name(node.tag) != "loc":
            continue
        loc_value = (node.text or "").strip()
        if not loc_value:
            continue
        page_url = _resolve_page_reference(
            loc_value,
            source_reference=source_reference,
            fallback_base_url=fallback_base_url,
        )
        normalized = _normalize_url(page_url)
        if normalized:
            page_urls.add(normalized)
    return nested_sources, page_urls


def _resolve_sitemap_reference(
    candidate: str, source_reference: str, fallback_base_url: str
) -> str:
    if _is_http_url(candidate):
        return candidate
    if _is_http_url(source_reference):
        return urljoin(source_reference, candidate)

    source_path = Path(source_reference)
    if source_path.exists():
        return str((source_path.parent / candidate).resolve())

    if fallback_base_url:
        return urljoin(fallback_base_url, candidate)
    return candidate


def _resolve_page_reference(
    candidate: str, source_reference: str, fallback_base_url: str
) -> str:
    if _is_http_url(candidate):
        return candidate
    if _is_http_url(source_reference):
        return urljoin(source_reference, candidate)
    if fallback_base_url:
        return urljoin(fallback_base_url, candidate)
    return candidate


def _extract_sitemap_seed_urls(
    sources: list[str],
    session: requests.Session,
    timeout: int,
    fallback_base_url: str,
) -> set[str]:
    seed_urls: set[str] = set()
    pending_sources: deque[str] = deque(
        [(source or "").strip() for source in sources if str(source).strip()]
    )
    visited_sources: set[str] = set()

    while pending_sources and len(visited_sources) < MAX_SITEMAP_FILES:
        source = pending_sources.popleft()
        if not source or source in visited_sources:
            continue
        visited_sources.add(source)
        loaded = _load_source_text(source, session=session, timeout=timeout)
        if not loaded:
            continue
        xml_text, source_reference = loaded
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            continue

        nested_sources, page_urls = _parse_sitemap_document(
            root,
            source_reference=source_reference,
            fallback_base_url=fallback_base_url,
        )
        for nested_source in nested_sources:
            if nested_source not in visited_sources:
                pending_sources.append(nested_source)
        seed_urls.update(page_urls)

    return seed_urls


def _extract_html_sitemap_seed_urls(
    sources: list[str],
    session: requests.Session,
    timeout: int,
    fallback_base_url: str,
) -> set[str]:
    seed_urls: set[str] = set()
    for source in sources:
        source_value = (source or "").strip()
        if not source_value:
            continue
        loaded = _load_source_text(source_value, session=session, timeout=timeout)
        if not loaded:
            continue
        html_text, source_reference = loaded
        soup = BeautifulSoup(html_text, "lxml")
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href", "")).strip()
            if (
                not href
                or href.startswith("#")
                or href.lower().startswith("javascript:")
            ):
                continue
            page_url = _resolve_page_reference(
                href,
                source_reference=source_reference,
                fallback_base_url=fallback_base_url,
            )
            normalized = _normalize_url(page_url)
            if normalized:
                seed_urls.add(normalized)
    return seed_urls


def crawl_site(
    site_url: str,
    max_pages: int = 300,
    concurrency: int = 10,
    delay_ms: int = 200,
    respect_robots: bool = True,
    timeout: int = 15,
    sitemap_sources: list[str] | None = None,
    sitemap_page_sources: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Crawl internal pages and extract SEO signals."""
    normalized_start = _normalize_url(site_url)
    is_valid = (
        validators.url(normalized_start)
        if validators is not None
        else bool(urlparse(normalized_start).netloc)
    )
    if not is_valid:
        raise ValueError(f"Invalid URL: {site_url}")

    base_host = urlparse(normalized_start).netloc
    robot_parser = _make_robot_parser(normalized_start) if respect_robots else None
    seed_session = requests.Session()
    seed_session.headers.update({"User-Agent": USER_AGENT})
    concurrency = max(1, int(concurrency or 1))

    queue: deque[tuple[str, int, str]] = deque([(normalized_start, 0, "start")])
    queued: set[str] = {normalized_start}
    visited: set[str] = set()
    results: list[dict[str, Any]] = []
    results_by_url: dict[str, dict[str, Any]] = {}

    def enqueue_target(target_url: str, depth: int, source: str = "link") -> None:
        normalized_target = _normalize_url(target_url)
        if not normalized_target:
            return
        if normalized_target in visited or normalized_target in queued:
            return
        if not _is_internal(normalized_target, base_host):
            return
        if source in {"sitemap", "sitemap_page"}:
            if not _is_safe_seed_url(normalized_target):
                return
        elif _looks_like_trap(normalized_target):
            return
        queue.append((normalized_target, depth, source))
        queued.add(normalized_target)

    seed_urls: set[str] = set()
    if sitemap_sources:
        seed_urls.update(
            _extract_sitemap_seed_urls(
                sitemap_sources,
                session=seed_session,
                timeout=timeout,
                fallback_base_url=normalized_start,
            )
        )
    if sitemap_page_sources:
        seed_urls.update(
            _extract_html_sitemap_seed_urls(
                sitemap_page_sources,
                session=seed_session,
                timeout=timeout,
                fallback_base_url=normalized_start,
            )
        )
    seed_urls_sorted = sorted(seed_urls)
    seed_urls_clean = [url for url in seed_urls_sorted if not urlparse(url).query]
    seed_urls_query = [url for url in seed_urls_sorted if urlparse(url).query]
    for seed_url in seed_urls_clean:
        enqueue_target(seed_url, depth=1, source="sitemap")
    for seed_url in seed_urls_query:
        enqueue_target(seed_url, depth=1, source="sitemap")

    def fetch_one(
        target_url: str, depth: int, source: str
    ) -> tuple[dict[str, Any], str]:
        session = getattr(thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"User-Agent": USER_AGENT})
            thread_local.session = session
            created_sessions.append(session)

        # Some e-commerce sites grow per-visit cookies (e.g., "recently viewed") until
        # the Cookie header becomes too large and triggers persistent HTTP 400s.
        # Keep crawl deterministic by not carrying cookies across pages.
        cookies = getattr(session, "cookies", None)
        if cookies is not None:
            try:
                cookies.clear()
            except Exception:
                pass

        page_record: dict[str, Any] = {
            "url": target_url,
            "requested_url": target_url,
            "depth": depth,
            "source": source,
            "status": None,
            "fetch_error": None,
            "content_type": "",
        }
        html = ""
        response = None

        try:
            response = session.get(target_url, timeout=timeout, allow_redirects=True)
        except requests.exceptions.SSLError:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            try:
                response = session.get(
                    target_url, timeout=timeout, allow_redirects=True, verify=False
                )
            except requests.RequestException as exc:
                page_record["fetch_error"] = str(exc)
                return page_record, ""
        except requests.RequestException as exc:
            page_record["fetch_error"] = str(exc)
            return page_record, ""

        final_url = _normalize_url(str(getattr(response, "url", "")))
        status = int(getattr(response, "status_code", 0) or 0)
        page_record["url"] = final_url or target_url
        page_record["status"] = status
        page_record["content_type"] = (
            response.headers.get("content-type", "") if response is not None else ""
        )
        requested_url_value = str(page_record.get("requested_url") or "").strip()
        resolved_url_value = str(page_record.get("url") or "").strip()
        if requested_url_value and resolved_url_value and requested_url_value != resolved_url_value:
            page_record["aliases"] = [requested_url_value]
            page_record["alias_sources"] = {requested_url_value: source}
        if response is not None and "text/html" in page_record["content_type"]:
            html = response.text

        if status >= 400 or not html:
            return page_record, ""

        try:
            extracted = extract_signals(html, page_record["url"])
            page_record.update(extracted)
            # Merge X-Robots-Tag header signal with meta tag signal.
            x_robots = response.headers.get("X-Robots-Tag", "") if response is not None else ""
            if "noindex" in x_robots.lower():
                page_record["is_noindex"] = True
        except Exception as exc:
            page_record["fetch_error"] = f"extract_error: {exc}"
            return page_record, ""

        return page_record, target_url

    thread_local = threading.local()
    created_sessions: list[requests.Session] = []

    next_request_start = time.monotonic()
    in_flight: dict[Any, tuple[str, int, str]] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        while (queue or in_flight) and len(results) < max_pages:
            while (
                queue
                and len(in_flight) < concurrency
                and (len(results) + len(in_flight)) < max_pages
            ):
                url, depth, source = queue.popleft()
                if url in visited:
                    continue
                visited.add(url)

                if _looks_like_trap(url) and source not in {"sitemap", "sitemap_page"}:
                    continue
                if robot_parser is not None and not robot_parser.can_fetch(USER_AGENT, url):
                    continue

                if delay_ms > 0:
                    now = time.monotonic()
                    if now < next_request_start:
                        time.sleep(next_request_start - now)
                    next_request_start = time.monotonic() + (delay_ms / 1000.0)

                future = executor.submit(fetch_one, url, depth, source)
                in_flight[future] = (url, depth, source)

            if not in_flight:
                continue

            done, _ = wait(list(in_flight.keys()), return_when=FIRST_COMPLETED)
            for future in done:
                url, depth, _source = in_flight.pop(future)
                try:
                    page_record, original_url = future.result()
                except Exception as exc:
                    page_record = {
                        "url": url,
                        "requested_url": url,
                        "depth": depth,
                        "source": _source,
                        "status": None,
                        "fetch_error": f"unhandled_error: {exc}",
                        "content_type": "",
                    }
                    original_url = url

                final_url_value = str(page_record.get("url") or "").strip()
                if final_url_value and final_url_value in results_by_url:
                    existing = results_by_url[final_url_value]
                    alias_value = str(page_record.get("requested_url") or "").strip()
                    if alias_value and alias_value != final_url_value:
                        aliases = existing.setdefault("aliases", [])
                        if alias_value not in aliases:
                            aliases.append(alias_value)
                        alias_source = str(page_record.get("source") or "").strip()
                        if alias_source:
                            alias_sources = existing.setdefault("alias_sources", {})
                            alias_sources[alias_value] = alias_source
                    continue

                results.append(page_record)
                if final_url_value:
                    results_by_url[final_url_value] = page_record

                final_canonical_url = page_record.get("url", "")
                if final_canonical_url and final_canonical_url != original_url:
                    visited.add(final_canonical_url)
                    queued.add(final_canonical_url)

                for link in page_record.get("links", {}).get("internal", []):
                    enqueue_target(link.get("url", ""), depth + 1)

                for pagination_url in page_record.get("pagination_links", []):
                    enqueue_target(str(pagination_url), depth + 1)

    for session in created_sessions:
        try:
            session.close()
        except Exception:
            pass

    return results


def write_jsonl(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Write rows to JSONL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_bool(value: str) -> bool:
    """Parse bool-ish CLI values."""
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl a site and extract leak-audit signals."
    )
    parser.add_argument("site_url", help="Start URL")
    parser.add_argument("--max-pages", type=int, default=300)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Max concurrent in-flight page fetches (respects --delay-ms between request starts).",
    )
    parser.add_argument("--delay-ms", type=int, default=200)
    parser.add_argument("--respect-robots", default="true")
    parser.add_argument(
        "--sitemap",
        action="append",
        default=[],
        help="XML sitemap source (URL or local file path). Repeat flag for multiple sources.",
    )
    parser.add_argument(
        "--sitemap-page",
        action="append",
        default=[],
        help="HTML sitemap page source (URL or local file path). Repeat flag for multiple sources.",
    )
    parser.add_argument("--output", type=Path, default=Path("cache/crawl.jsonl"))
    args = parser.parse_args()

    _ = args.concurrency
    rows = crawl_site(
        site_url=args.site_url,
        max_pages=args.max_pages,
        concurrency=args.concurrency,
        delay_ms=args.delay_ms,
        respect_robots=parse_bool(args.respect_robots),
        sitemap_sources=args.sitemap,
        sitemap_page_sources=args.sitemap_page,
    )
    write_jsonl(rows, args.output)
    print(f"Crawled pages: {len(rows)}")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
