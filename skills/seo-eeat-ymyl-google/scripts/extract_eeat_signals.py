#!/usr/bin/env python3
"""Extract repeatable E-E-A-T and trust signals from local HTML files or URLs."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁёІіЇїЄє0-9]{2,}", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20\d{2})\b")
TRUST_LINK_PATTERNS = {
    "about": re.compile(r"/about|/about-us|/company|/team|/pro-nas|о-нас|про нас|команда", re.IGNORECASE),
    "contact": re.compile(r"/contact|/contacts|/kontakty|контакты|контакти|support|help", re.IGNORECASE),
    "policy": re.compile(r"/privacy|/policy|/polityka|политика|політика", re.IGNORECASE),
    "terms": re.compile(r"/terms|/conditions|/umovy|услов|умов", re.IGNORECASE),
    "returns": re.compile(r"/return|/refund|/exchange|/obmin|/povernennya|возврат|повернення|обмін", re.IGNORECASE),
    "editorial": re.compile(r"editorial|review-policy|fact-check|редакц|редакц|редакцій", re.IGNORECASE),
    "medical_review": re.compile(r"medical-review|reviewed-by|проверил врач|медицинск|медичн|лікар", re.IGNORECASE),
    "authors": re.compile(r"/author|/authors|/experts|/avtor|автор", re.IGNORECASE),
}
CTA_RISK_RE = re.compile(
    r"(buy now|order now|limited time|act now|claim now|instant approval|гарантирован|"
    r"срочно|купи сейчас|оформить сейчас|получи сейчас)",
    re.IGNORECASE,
)
CLICKBAIT_RE = re.compile(
    r"(best|top|ultimate|secret|shocking|must|cheap|free|лучший|топ|секрет|шок|"
    r"дешев|бесплатн)",
    re.IGNORECASE,
)
SPAM_RE = re.compile(
    r"(\bguaranteed\b|100%|\binstant\b|\bmiracle\b|no risk|\bcasino\b|\bbetting\b|\bbonus\b|loan now|"
    r"без риска|мгновенно|чудо|казино|\bставки\b|\bставок\b|займ прямо сейчас|бонус)",
    re.IGNORECASE,
)
CONTACT_RE = re.compile(r"(\+?\d[\d\-\s\(\)]{7,}\d|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE)
ADDRESS_RE = re.compile(
    r"(street|st\.|ave|road|rd\.|office|suite|ул\.|улица|проспект|дом|офис|город)",
    re.IGNORECASE,
)
CHARSET_RE = re.compile(rb"<meta[^>]+charset=[\"']?\s*([a-zA-Z0-9_\-]+)", re.IGNORECASE)
CONTENT_TYPE_CHARSET_RE = re.compile(r"charset\s*=\s*([a-zA-Z0-9_\-]+)", re.IGNORECASE)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def tokenize(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value or "")]


def extract_declared_charset(raw: bytes, headers: Message | None = None) -> str | None:
    if headers:
        content_type = headers.get("Content-Type", "")
        match = CONTENT_TYPE_CHARSET_RE.search(content_type)
        if match:
            return match.group(1).lower()

    match = CHARSET_RE.search(raw[:4096])
    if match:
        return match.group(1).decode("ascii", errors="ignore").lower()
    return None


def decode_html(raw: bytes, declared_charset: str | None = None) -> str:
    candidates: list[str] = []
    if declared_charset:
        candidates.append(declared_charset)
    candidates.extend(["utf-8", "cp1251", "windows-1251", "koi8-r"])

    seen: set[str] = set()
    for encoding in candidates:
        normalized = encoding.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue

    return raw.decode("utf-8", errors="ignore")


def read_source(source: str) -> tuple[str, str]:
    if re.match(r"^https?://", source, re.IGNORECASE):
        request = Request(source, headers={"User-Agent": "seo-eeat-ymyl-google/1.0"})
        with urlopen(request, timeout=20) as response:
            raw = response.read()
            declared_charset = extract_declared_charset(raw, response.headers)
        return decode_html(raw, declared_charset), source

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    raw = path.read_bytes()
    html = decode_html(raw, extract_declared_charset(raw))
    return html, path.resolve().as_uri()


def extract_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.text or "").strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            if isinstance(parsed.get("@graph"), list):
                items.extend([entry for entry in parsed["@graph"] if isinstance(entry, dict)])
            else:
                items.append(parsed)
        elif isinstance(parsed, list):
            items.extend([entry for entry in parsed if isinstance(entry, dict)])
    return items


def safe_types(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def collect_person_schema_signals(
    entity: dict[str, Any],
    author_names: set[str],
    same_as: set[str],
    credentials: set[str],
) -> bool:
    if "Person" not in safe_types(entity.get("@type")):
        return False

    if entity.get("name"):
        author_names.add(normalize_text(str(entity["name"])))

    same_as_value = entity.get("sameAs")
    if isinstance(same_as_value, list):
        same_as.update(str(item) for item in same_as_value if str(item).strip())
    elif isinstance(same_as_value, str) and same_as_value.strip():
        same_as.add(same_as_value)

    for key in ("jobTitle", "honorificSuffix", "description", "knowsAbout"):
        if entity.get(key):
            credentials.add(normalize_text(str(entity[key]))[:120])

    return True


def extract_author_signals(soup: BeautifulSoup, schema_entities: list[dict[str, Any]]) -> dict[str, Any]:
    author_names: set[str] = set()
    author_links: set[str] = set()
    same_as: set[str] = set()
    has_person_schema = False
    credentials: set[str] = set()

    for entity in schema_entities:
        if collect_person_schema_signals(entity, author_names, same_as, credentials):
            has_person_schema = True

        author_value = entity.get("author")
        if isinstance(author_value, dict):
            if collect_person_schema_signals(author_value, author_names, same_as, credentials):
                has_person_schema = True
        elif isinstance(author_value, list):
            for author_entry in author_value:
                if isinstance(author_entry, dict) and collect_person_schema_signals(
                    author_entry, author_names, same_as, credentials
                ):
                    has_person_schema = True

    meta_author = soup.find("meta", attrs={"name": re.compile(r"author", re.IGNORECASE)})
    if meta_author and meta_author.get("content"):
        author_names.add(normalize_text(str(meta_author["content"])))

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        anchor_text = normalize_text(anchor.get_text(" ", strip=True))
        if re.search(r"/author|/authors|/expert|/team|/doctor|/reviewed", href, re.IGNORECASE):
            author_links.add(href)
        if re.search(r"author|expert|reviewed|доктор|автор|редактор", " ".join(anchor.get("class", [])), re.IGNORECASE):
            if anchor_text:
                author_names.add(anchor_text)
            author_links.add(href)

    return {
        "has_person_schema": has_person_schema,
        "author_names": sorted(name for name in author_names if name),
        "author_links": sorted(author_links),
        "same_as": sorted(same_as),
        "credential_hints": sorted(credentials),
    }


def extract_organization_signals(
    soup: BeautifulSoup, schema_entities: list[dict[str, Any]], page_text: str
) -> dict[str, Any]:
    organization_names: set[str] = set()
    service_names: set[str] = set()
    has_organization_schema = False
    has_service_schema = False

    for entity in schema_entities:
        entity_types = set(safe_types(entity.get("@type")))
        if entity_types & {"Organization", "MedicalOrganization", "LocalBusiness"}:
            has_organization_schema = True
            if entity.get("name"):
                organization_names.add(normalize_text(str(entity["name"])))
        if entity_types & {"Service", "Product", "MedicalWebPage"}:
            has_service_schema = True
            if entity.get("name"):
                service_names.add(normalize_text(str(entity["name"])))

    contact_matches = CONTACT_RE.findall(page_text)
    has_address_hint = bool(ADDRESS_RE.search(page_text))
    return {
        "has_organization_schema": has_organization_schema,
        "has_service_schema": has_service_schema,
        "organization_names": sorted(organization_names),
        "service_names": sorted(service_names),
        "contact_signal_count": len(contact_matches),
        "address_hint": has_address_hint,
    }


def extract_links(soup: BeautifulSoup, page_url: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    internal: list[dict[str, Any]] = []
    external: list[dict[str, Any]] = []
    base_host = urlparse(page_url).netloc.lower()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        full_url = urljoin(page_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme not in {"http", "https", "file"}:
            continue
        entry = {
            "url": full_url,
            "anchor_text": normalize_text(anchor.get_text(" ", strip=True))[:160],
        }
        if parsed.scheme == "file" or parsed.netloc.lower() == base_host:
            internal.append(entry)
        else:
            external.append(entry)
    return internal, external


def detect_trust_pages(internal_links: list[dict[str, Any]]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {name: [] for name in TRUST_LINK_PATTERNS}
    for link in internal_links:
        url = link["url"]
        anchor_text = link["anchor_text"]
        haystack = f"{url} {anchor_text}"
        for label, pattern in TRUST_LINK_PATTERNS.items():
            if pattern.search(haystack):
                found[label].append(url)
    return {label: sorted(set(urls)) for label, urls in found.items()}


def detect_answer_first(soup: BeautifulSoup) -> dict[str, Any]:
    snippets: list[str] = []
    for node in soup.find_all(["p", "li", "td"], limit=12):
        text = normalize_text(node.get_text(" ", strip=True))
        if text:
            snippets.append(text)
    top_excerpt = " ".join(snippets[:3])[:260]
    has_definition_pattern = bool(
        re.search(r"\b(is|are|means|это|означает|называется|определяется)\b", top_excerpt, re.IGNORECASE)
    )
    has_table_or_list = bool(soup.find("table") or soup.find("ul") or soup.find("ol"))
    return {
        "has_direct_answer": len(tokenize(top_excerpt)) >= 18 and (has_definition_pattern or has_table_or_list),
        "top_excerpt": top_excerpt,
        "definition_pattern": has_definition_pattern,
        "has_table_or_list_near_top": has_table_or_list,
    }


def detect_ugc(soup: BeautifulSoup) -> dict[str, Any]:
    comments = soup.find_all(attrs={"class": re.compile(r"comment|discussion|reply|forum", re.IGNORECASE)})
    authors = soup.find_all(attrs={"class": re.compile(r"author|user|name", re.IGNORECASE)})
    return {
        "has_ugc_discussion": bool(comments),
        "comment_like_blocks": len(comments),
        "unique_comment_author_hints": len(
            {normalize_text(node.get_text(" ", strip=True)) for node in authors if normalize_text(node.get_text(" ", strip=True))}
        ),
    }


def detect_ui_risks(soup: BeautifulSoup, title: str, page_text: str) -> dict[str, Any]:
    fixed_count = 0
    sticky_count = 0
    overlay_hits = 0
    cta_hits = 0

    for node in soup.find_all(True):
        attrs_joined = " ".join(
            [str(node.get("class", "")), str(node.get("id", "")), str(node.get("style", ""))]
        ).lower()
        if "position:fixed" in attrs_joined or " fixed" in attrs_joined:
            fixed_count += 1
        if "position:sticky" in attrs_joined or " sticky" in attrs_joined:
            sticky_count += 1
        if re.search(r"overlay|popup|modal|interstitial|subscribe|cookie|consent|баннер|всплыв", attrs_joined):
            overlay_hits += 1

    cta_hits += len(CTA_RISK_RE.findall(page_text))

    return {
        "fixed_elements": fixed_count,
        "sticky_elements": sticky_count,
        "overlay_keyword_hits": overlay_hits,
        "misleading_cta_hits": cta_hits,
        "clickbait_title": bool(CLICKBAIT_RE.search(title)),
        "spammy_phrase_hits": len(SPAM_RE.findall(page_text)),
    }


def classify_page_role(page_url: str) -> str:
    lowered = page_url.lower()
    if re.search(
        r"/about|/about-us|/team|/company|/pro-nas|о-нас|про-нас|компания|компанія|команда|"
        r"/povernennya|/refund|/return|/delivery|/shipping|/payment|/oplata|/dostavka",
        lowered,
    ):
        return "trust"
    if re.search(r"/contact|/contacts|/kontakty|/support|контакты|контакти", lowered):
        return "contact"
    if re.search(r"/product|/service|/pricing|checkout|cart|buy|заказ|услуги", lowered):
        return "money_or_transaction"
    if re.search(r"/blog|/article|/guide|/news|/post|статья|/novyny|/blog|/statti", lowered):
        return "informational"
    return "generic"


def collect_schema_type_hints(schema_entities: list[dict[str, Any]]) -> set[str]:
    schema_types: set[str] = set()
    for entity in schema_entities:
        schema_types.update(value.lower() for value in safe_types(entity.get("@type")))
    return schema_types


def infer_page_role(
    page_url: str,
    title: str,
    meta_desc: str,
    headings: dict[str, list[str]],
    page_text: str,
    schema_entities: list[dict[str, Any]],
) -> str:
    url_role = classify_page_role(page_url)
    if url_role != "generic":
        return url_role

    schema_types = collect_schema_type_hints(schema_entities)
    heading_text = " ".join(headings.get("h1", []) + headings.get("h2", []) + headings.get("h3", []))
    role_surface = normalize_text(" ".join([title, meta_desc, heading_text])).lower()
    surface_text = normalize_text(" ".join([title, meta_desc, heading_text, page_text[:1200]])).lower()

    if re.search(
        r"\b(contact|support|help center|контакты|контакти|связаться|поддержка|служба поддержки)\b",
        role_surface,
    ):
        return "contact"

    if re.search(
        r"\b(about|editorial|review policy|medical review|privacy|terms|returns|delivery|payment|shipping|"
        r"о проекте|о компании|про компанію|про нас|редакцион|редакцій|политик|політик|условия|умови|возврат|"
        r"повернення|обмін|автор|об авторе)\b",
        role_surface,
    ):
        return "trust"

    money_score = 0
    informational_score = 0

    if schema_types & {"service", "product", "offer"}:
        money_score += 3
    if schema_types & {"article", "blogposting", "newsarticle", "howto", "faqpage"}:
        informational_score += 3

    if re.search(
        r"\b(apply|book|buy|checkout|order|payment|pricing|quote|subscribe|transaction|loan|insurance|"
        r"оформить|заявк|купить|заказ|оплат|полис|страхован|тариф|кредит|займ|подписк)\b",
        surface_text,
    ):
        money_score += 2
    if re.search(
        r"\b(how to|guide|tutorial|article|what is|why|faq|review|чек-лист|как\b|что\b|почему\b|"
        r"разбор|инструкц|источники|личный опыт|комментарий врача)\b",
        surface_text,
    ):
        informational_score += 2

    if re.search(r"\b(телефон|email|e-mail|карта|доставка|возврат|оплата)\b", surface_text):
        money_score += 1
    if re.search(r"\b(источники|исследован|doi|pmid|проверил врач|проверила врач)\b", surface_text):
        informational_score += 1

    if money_score >= informational_score and money_score >= 2:
        return "money_or_transaction"
    if informational_score >= 2:
        return "informational"
    return "generic"


def extract_page(html: str, page_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    title = normalize_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": re.compile(r"description", re.IGNORECASE)})
    if meta_tag and meta_tag.get("content"):
        meta_desc = normalize_text(str(meta_tag["content"]))

    headings = {
        "h1": [normalize_text(tag.get_text(" ", strip=True)) for tag in soup.find_all("h1") if normalize_text(tag.get_text(" ", strip=True))],
        "h2": [normalize_text(tag.get_text(" ", strip=True)) for tag in soup.find_all("h2") if normalize_text(tag.get_text(" ", strip=True))],
        "h3": [normalize_text(tag.get_text(" ", strip=True)) for tag in soup.find_all("h3") if normalize_text(tag.get_text(" ", strip=True))],
    }

    schema_entities = extract_json_ld(soup)
    internal_links, external_links = extract_links(soup, page_url)
    trust_pages = detect_trust_pages(internal_links)
    answer_first = detect_answer_first(soup)
    ugc = detect_ugc(soup)

    media_count = len(soup.find_all(["img", "video", "iframe"]))
    image_count = len(soup.find_all("img"))
    page_text = normalize_text(soup.get_text(" ", strip=True))
    tokens = tokenize(page_text)
    top_terms = [{"term": term, "count": count} for term, count in Counter(tokens).most_common(25)]

    citation_count = len(re.findall(r"\[(?:\d+|[A-Za-z]{1,4})\]|https?://|doi\.org|pmid", page_text, re.IGNORECASE))
    year_mentions = sorted({int(year) for year in YEAR_RE.findall(page_text)})

    author_signals = extract_author_signals(soup, schema_entities)
    org_signals = extract_organization_signals(soup, schema_entities, page_text)
    ui_risks = detect_ui_risks(soup, title, page_text)
    page_role_hint = infer_page_role(page_url, title, meta_desc, headings, page_text, schema_entities)

    return {
        "url": page_url,
        "page_role_hint": page_role_hint,
        "title": title,
        "meta_description": meta_desc,
        "headings": headings,
        "word_count": len(tokens),
        "top_terms": top_terms,
        "author": author_signals,
        "organization": org_signals,
        "links": {
            "internal_count": len(internal_links),
            "external_count": len(external_links),
            "trust_pages": trust_pages,
            "external_examples": external_links[:8],
        },
        "citations": {
            "citation_count": citation_count,
            "external_link_count": len(external_links),
            "external_link_examples": external_links[:5],
        },
        "media": {
            "image_count": image_count,
            "media_block_count": media_count,
        },
        "content_structure": {
            "list_count": len(soup.find_all(["ul", "ol"])),
            "table_count": len(soup.find_all("table")),
            "faq_like_sections": len(
                [
                    heading
                    for heading in headings["h2"] + headings["h3"]
                    if "?" in heading or re.search(r"\bfaq|вопрос|question|answer\b", heading, re.IGNORECASE)
                ]
            ),
            "answer_first": answer_first,
            "year_mentions": year_mentions,
        },
        "ugc": ugc,
        "ui_risk_hints": ui_risks,
        "spam_flags": {
            "spammy_phrase_hits": ui_risks["spammy_phrase_hits"],
            "cta_risk_hits": ui_risks["misleading_cta_hits"],
            "clickbait_title": ui_risks["clickbait_title"],
        },
        "text_excerpt": page_text[:600],
    }


def summarize_site(pages: list[dict[str, Any]]) -> dict[str, Any]:
    trust_presence = {name: 0 for name in TRUST_LINK_PATTERNS}
    for page in pages:
        for label, urls in page["links"]["trust_pages"].items():
            if urls:
                trust_presence[label] += 1

    return {
        "page_count": len(pages),
        "pages_with_person_schema": sum(1 for page in pages if page["author"]["has_person_schema"]),
        "pages_with_citations": sum(1 for page in pages if page["citations"]["citation_count"] > 0),
        "pages_with_ugc": sum(1 for page in pages if page["ugc"]["has_ugc_discussion"]),
        "pages_with_ui_risks": sum(
            1
            for page in pages
            if page["ui_risk_hints"]["overlay_keyword_hits"] > 0 or page["ui_risk_hints"]["misleading_cta_hits"] > 0
        ),
        "trust_page_coverage": trust_presence,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract E-E-A-T and trust signals from HTML or URLs.")
    parser.add_argument("--source", action="append", required=True, help="URL or local HTML file path. Repeatable.")
    parser.add_argument("--output", type=Path, help="Path to output JSON.")
    args = parser.parse_args()

    pages: list[dict[str, Any]] = []
    for source in args.source:
        html, page_url = read_source(source)
        pages.append(extract_page(html, page_url))

    payload = {
        "sources": args.source,
        "pages": pages,
        "site_summary": summarize_site(pages),
    }

    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
