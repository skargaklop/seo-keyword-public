#!/usr/bin/env python3
"""Extract SEO proxy signals from raw HTML."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

TOKEN_RE = re.compile(
    r"[A-Za-zА-Яа-яЁёІіЇїЄєҐґ0-9]{2,}",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(20\d{2})\b")
CLICKBAIT_RE = re.compile(
    r"(best|top|ultimate|secret|shocking|must|cheap|free|лучш|топ|секрет|шок|дешев)",
    re.IGNORECASE,
)
TEMPLATE_PHRASES = (
    "lorem ipsum",
    "all rights reserved",
    "cookie policy",
    "terms and conditions",
    "политика конфиденциальности",
    "условия использования",
)
OVERLAY_HINT_RE = re.compile(
    r"(cookie|consent|popup|overlay|subscribe|newsletter|chat|fixed|sticky|баннер|окно)",
    re.IGNORECASE,
)


def normalize_text(value: str) -> str:
    """Normalize whitespace."""
    return re.sub(r"\s+", " ", value or "").strip()


def tokenize(value: str) -> list[str]:
    """Tokenize mixed EN/RU text."""
    return [t.lower() for t in TOKEN_RE.findall(value or "")]


def _extract_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.text or "").strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    result.append(item)
        elif isinstance(parsed, dict):
            result.append(parsed)
    return result


def _flatten_schema_entities(
    schema_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for block in schema_blocks:
        if "@graph" in block and isinstance(block["@graph"], list):
            for item in block["@graph"]:
                if isinstance(item, dict):
                    entities.append(item)
            continue
        entities.append(block)
    return entities


def _safe_rel(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).lower().strip() for v in value if str(v).strip()]
    return [str(value).lower().strip()]


def _detect_answer_first(soup: BeautifulSoup) -> dict[str, Any]:
    candidates: list[str] = []
    for tag in soup.find_all(["p", "li", "td"], limit=12):
        text = normalize_text(tag.get_text(" ", strip=True))
        if text:
            candidates.append(text)
    top_text = " ".join(candidates[:3])
    tokens = tokenize(top_text)
    has_definition_pattern = bool(
        re.search(r"\b(is|are|это|означает|defined)\b", top_text, re.IGNORECASE)
    )
    has_table_or_list = bool(soup.find("table") or soup.find("ul") or soup.find("ol"))
    has_direct_answer = len(tokens) >= 20 and (
        has_definition_pattern or has_table_or_list
    )
    return {
        "has_direct_answer": has_direct_answer,
        "top_excerpt": top_text[:260],
        "definition_pattern": has_definition_pattern,
        "has_table_or_list_near_top": has_table_or_list,
    }


def _extract_ugc_signals(soup: BeautifulSoup) -> dict[str, Any]:
    comment_nodes: list[Any] = []
    for selector in (
        {"id": re.compile(r"comments?|discussion|disqus", re.IGNORECASE)},
        {"class": re.compile(r"comments?|discussion|disqus|reply", re.IGNORECASE)},
    ):
        comment_nodes.extend(soup.find_all(attrs=selector))

    if not comment_nodes:
        return {
            "has_ugc_discussion": False,
            "comment_count": 0,
            "unique_comment_authors": 0,
        }

    seen_node_ids: set[int] = set()
    deduped_nodes: list[Any] = []
    for node in comment_nodes:
        node_id = id(node)
        if node_id in seen_node_ids:
            continue
        seen_node_ids.add(node_id)
        deduped_nodes.append(node)

    comment_items: list[Any] = []
    for node in deduped_nodes:
        comment_items.extend(
            node.find_all(
                attrs={
                    "class": re.compile(
                        r"comment|reply|message|post-item", re.IGNORECASE
                    )
                }
            )
        )
        if node.get_text(" ", strip=True):
            comment_items.append(node)

    unique_item_ids: set[int] = set()
    normalized_items: list[Any] = []
    for item in comment_items:
        node_id = id(item)
        if node_id in unique_item_ids:
            continue
        unique_item_ids.add(node_id)
        normalized_items.append(item)

    authors: set[str] = set()
    for item in normalized_items:
        author_candidates = [
            item.get("data-author", ""),
            item.get("data-user", ""),
            item.get("author", ""),
            item.get("itemprop", ""),
        ]
        author_node = item.find(
            attrs={"class": re.compile(r"author|user|name", re.IGNORECASE)}
        )
        if author_node:
            author_candidates.append(author_node.get_text(" ", strip=True))
        for candidate in author_candidates:
            cleaned = normalize_text(str(candidate))
            if cleaned and cleaned.lower() not in {"author", "name"}:
                authors.add(cleaned[:80])

    return {
        "has_ugc_discussion": True,
        "comment_count": len(normalized_items),
        "unique_comment_authors": len(authors),
    }


def _extract_author_signals(
    soup: BeautifulSoup, schema_entities: list[dict[str, Any]]
) -> dict[str, Any]:
    has_person_schema = False
    author_names: set[str] = set()
    same_as: set[str] = set()

    for entity in schema_entities:
        entity_type = entity.get("@type")
        types: list[str]
        if isinstance(entity_type, list):
            types = [str(v) for v in entity_type]
        else:
            types = [str(entity_type)] if entity_type else []
        if "Person" in types:
            has_person_schema = True
            name = normalize_text(str(entity.get("name", "")))
            if name:
                author_names.add(name)
            same_as_value = entity.get("sameAs", [])
            if isinstance(same_as_value, str):
                same_as.add(same_as_value)
            elif isinstance(same_as_value, list):
                for link in same_as_value:
                    if isinstance(link, str):
                        same_as.add(link)

        author_value = entity.get("author")
        if isinstance(author_value, dict):
            name = normalize_text(str(author_value.get("name", "")))
            if name:
                author_names.add(name)
            if author_value.get("@type") == "Person":
                has_person_schema = True
        elif isinstance(author_value, str):
            cleaned = normalize_text(author_value)
            if cleaned:
                author_names.add(cleaned)

    meta_author = soup.find(
        "meta", attrs={"name": re.compile(r"author", re.IGNORECASE)}
    )
    if meta_author and meta_author.get("content"):
        author_names.add(normalize_text(str(meta_author["content"])))

    author_links: list[str] = []
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if re.search(r"/author|/authors|/team|/about", href, re.IGNORECASE):
            author_links.append(href)
        cls = " ".join(link.get("class", []))
        if re.search(r"author", cls, re.IGNORECASE):
            text = normalize_text(link.get_text(" ", strip=True))
            if text:
                author_names.add(text)

    author_text_nodes = soup.find_all(
        attrs={"class": re.compile(r"author", re.IGNORECASE)}
    )
    for node in author_text_nodes[:5]:
        text = normalize_text(node.get_text(" ", strip=True))
        if text and len(text.split()) <= 6:
            author_names.add(text)

    return {
        "has_person_schema": has_person_schema,
        "author_names": sorted(author_names),
        "same_as": sorted(same_as),
        "author_links": sorted(set(author_links)),
    }


def _extract_links(
    soup: BeautifulSoup, url: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parsed_base = urlparse(url)
    base_host = parsed_base.netloc.lower()
    internal: list[dict[str, Any]] = []
    external: list[dict[str, Any]] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        full_url = urljoin(url, href)
        parsed = urlparse(full_url)
        if parsed.scheme not in ("http", "https"):
            continue
        entry = {
            "url": full_url,
            "anchor_text": normalize_text(anchor.get_text(" ", strip=True))[:240],
            "rel": _safe_rel(anchor.get("rel")),
        }
        if parsed.netloc.lower() == base_host:
            internal.append(entry)
        else:
            external.append(entry)
    return internal, external


def _extract_pagination_links(soup: BeautifulSoup, url: str) -> list[str]:
    pagination_links: list[str] = []
    seen: set[str] = set()

    for node in soup.find_all(["a", "link"], href=True):
        rel_values = _safe_rel(node.get("rel"))
        if not rel_values or not any(rel in {"next", "prev"} for rel in rel_values):
            continue
        href = str(node.get("href", "")).strip()
        if not href:
            continue
        full_url = urljoin(url, href)
        parsed = urlparse(full_url)
        if parsed.scheme not in ("http", "https"):
            continue
        if full_url in seen:
            continue
        seen.add(full_url)
        pagination_links.append(full_url)

    return pagination_links


def extract_signals(html: str, url: str) -> dict[str, Any]:
    """Extract on-page signals used by leak checks."""
    soup = BeautifulSoup(html, "lxml")

    title = normalize_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    canonical = ""
    canonical_tag = soup.find(
        "link", rel=lambda value: value and "canonical" in str(value).lower()
    )
    if canonical_tag:
        canonical = canonical_tag.get("href", "") or ""
    meta_desc_tag = soup.find(
        "meta", attrs={"name": re.compile(r"description", re.IGNORECASE)}
    )
    meta_description = (
        normalize_text(meta_desc_tag.get("content", "")) if meta_desc_tag else ""
    )
    viewport_tag = soup.find(
        "meta", attrs={"name": re.compile(r"viewport", re.IGNORECASE)}
    )
    robots_tag = soup.find("meta", attrs={"name": re.compile(r"robots", re.IGNORECASE)})
    robots_content = normalize_text(robots_tag.get("content", "")) if robots_tag else ""
    is_noindex = bool(re.search(r"noindex", robots_content, re.IGNORECASE))

    headings = {
        "h1": [
            normalize_text(tag.get_text(" ", strip=True))
            for tag in soup.find_all("h1")
            if normalize_text(tag.get_text(" ", strip=True))
        ],
        "h2": [
            normalize_text(tag.get_text(" ", strip=True))
            for tag in soup.find_all("h2")
            if normalize_text(tag.get_text(" ", strip=True))
        ],
        "h3": [
            normalize_text(tag.get_text(" ", strip=True))
            for tag in soup.find_all("h3")
            if normalize_text(tag.get_text(" ", strip=True))
        ],
    }

    schema_blocks = _extract_json_ld(soup)
    schema_entities = _flatten_schema_entities(schema_blocks)
    author_signals = _extract_author_signals(soup, schema_entities)
    answer_first = _detect_answer_first(soup)
    ugc_signals = _extract_ugc_signals(soup)
    internal_links, external_links = _extract_links(soup, url)
    pagination_links = _extract_pagination_links(soup, url)

    img_tags = soup.find_all("img")
    image_count = len(img_tags)
    image_with_alt_count = sum(
        1
        for tag in img_tags
        if normalize_text(str(tag.get("alt", "")))
    )
    image_alt_coverage = (
        round(image_with_alt_count / image_count, 3) if image_count else 0.0
    )
    base_host = urlparse(url).netloc.lower()
    image_internal_src_count = 0
    image_external_src_count = 0
    image_data_uri_count = 0
    for tag in img_tags:
        raw_src = str(tag.get("src") or tag.get("data-src") or "").strip()
        if not raw_src:
            continue
        if raw_src.lower().startswith("data:"):
            image_data_uri_count += 1
            continue
        full_src = urljoin(url, raw_src)
        src_host = urlparse(full_src).netloc.lower()
        if not src_host:
            continue
        if src_host == base_host:
            image_internal_src_count += 1
        else:
            image_external_src_count += 1

    for junk in soup.find_all(["script", "style", "noscript", "svg"]):
        junk.decompose()
    visible_text = normalize_text(soup.get_text(" ", strip=True))
    tokens = tokenize(visible_text)
    top_terms = [
        {"term": term, "count": count}
        for term, count in Counter(tokens).most_common(40)
    ]

    template_hits = sum(
        1 for phrase in TEMPLATE_PHRASES if phrase in visible_text.lower()
    )
    citation_count = len(
        re.findall(
            r"\[(?:\d+|[a-z]{1,3})\]|https?://", visible_text, flags=re.IGNORECASE
        )
    )
    year_mentions = sorted(
        {int(v) for v in YEAR_RE.findall(visible_text) if int(v) >= 2000}
    )
    clickbait_title = bool(CLICKBAIT_RE.search(title))

    fixed_count = 0
    sticky_count = 0
    overlay_keyword_count = 0
    popup_keyword_count = 0
    for node in soup.find_all(True):
        attrs_joined = " ".join(
            [
                str(node.get("class", "")),
                str(node.get("id", "")),
                str(node.get("style", "")),
            ]
        ).lower()
        if "position:fixed" in attrs_joined or " fixed" in attrs_joined:
            fixed_count += 1
        if "position:sticky" in attrs_joined or " sticky" in attrs_joined:
            sticky_count += 1
        if OVERLAY_HINT_RE.search(attrs_joined):
            overlay_keyword_count += 1
        if re.search(r"popup|modal|interstitial|subscribe", attrs_joined):
            popup_keyword_count += 1

    interstitial_policy_risk = bool(
        (fixed_count + sticky_count) >= 2
        and overlay_keyword_count >= 2
        and popup_keyword_count >= 1
    )

    return {
        "url": url,
        "robots": robots_content,
        "is_noindex": is_noindex,
        "title": title,
        "meta_description": meta_description,
        "canonical": canonical,
        "viewport_present": bool(viewport_tag),
        "headings": headings,
        "word_count": len(tokens),
        "tokens": tokens[:3000],
        "top_terms": top_terms,
        "schema": schema_blocks,
        "author": author_signals,
        "answer_first": answer_first,
        "intro_text": answer_first.get("top_excerpt", ""),
        "links": {
            "internal": internal_links,
            "external": external_links,
        },
        "pagination_links": pagination_links,
        "content_features": {
            "list_count": len(soup.find_all(["ul", "ol"])),
            "table_count": len(soup.find_all("table")),
            "image_count": image_count,
            "image_with_alt_count": image_with_alt_count,
            "image_alt_coverage": image_alt_coverage,
            "image_internal_src_count": image_internal_src_count,
            "image_external_src_count": image_external_src_count,
            "image_data_uri_count": image_data_uri_count,
            "citation_count": citation_count,
            "qa_blocks": len(
                [
                    h
                    for h in headings["h2"] + headings["h3"]
                    if "?" in h
                    or re.search(
                        r"\b(what|how|why|когда|как|что|почему)\b",
                        h,
                        flags=re.IGNORECASE,
                    )
                ]
            ),
            "templated_phrase_hits": template_hits,
            "year_mentions": year_mentions,
            "ugc_discussion": ugc_signals,
        },
        "dates": {
            "time_tags": [
                normalize_text(t.get_text(" ", strip=True))
                for t in soup.find_all("time")
                if normalize_text(t.get_text(" ", strip=True))
            ][:5],
            "year_mentions": year_mentions,
        },
        "ui_hints": {
            "fixed_elements": fixed_count,
            "sticky_elements": sticky_count,
            "overlay_keyword_hits": overlay_keyword_count,
            "popup_keyword_hits": popup_keyword_count,
            "interstitial_policy_risk": interstitial_policy_risk,
        },
        "text_excerpt": visible_text[:900],
        "clickbait_title": clickbait_title,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract SEO leak proxies from HTML.")
    parser.add_argument("--html-file", type=Path, help="Path to local HTML file.")
    parser.add_argument("--url", required=True, help="Page URL used for normalization.")
    parser.add_argument("--output", type=Path, help="Path to output JSON.")
    args = parser.parse_args()

    if not args.html_file or not args.html_file.exists():
        raise SystemExit("--html-file is required and must exist.")

    html = args.html_file.read_text(encoding="utf-8", errors="ignore")
    result = extract_signals(html, args.url)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
