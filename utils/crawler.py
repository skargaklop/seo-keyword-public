# MODULE_CONTRACT: utils/crawler
# Purpose: Bounded crawl workflow with URL safety, DNS pinning, WebScraper composition, and crawl math report inputs.
# Rationale: Crawl/report workflow needs stricter frontier controls than single-page scraping while reusing existing text extraction.
# Dependencies: dataclasses, html, re, time, urllib.parse, requests, tenacity, utils.scraper, utils.url_safety, utils.logger, config.settings
# Exports: CrawlSettings, CrawlPage, CrawlResult, CrawlSafetyError, is_safe_url, normalize_url, should_follow_redirect, pin_ip_and_validate, bounded_crawl
# LINKS: requirements.xml#UC-001, knowledge-graph.xml#MOD-011, PLAN 08-03
# MODULE_MAP: utils/crawler.py
# Public Functions: is_safe_url, normalize_url, should_follow_redirect, pin_ip_and_validate, bounded_crawl
# Private Helpers: _hostname, _is_internal_domain, _registrable_domain, _same_domain, _fetch_html_bounded, _extract_links, _extract_headings, _request_once
# Key Semantic Blocks: block_crawler_safety_policy, block_crawler_dns_rebinding_guard, block_crawler_frontier_filter, block_crawler_page_collect
# Critical Flows: seed URL -> safety validation -> IP pin -> redirect validation -> bounded crawl collection
# Verification: V-P8-CRAWL
# CHANGE_SUMMARY: Phase 8 Plan 03: added crawler safety policy with SSRF blocking, URL normalization, same-domain redirect rules, DNS rebinding guard, and bounded WebScraper-composed crawl collection.

from dataclasses import dataclass, field
import html
import re
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed

from utils.logger import logger
from utils.scraper import ScrapedContent, WebScraper
from utils.url_safety import URLSafetyError, validate_safe_url_with_ips
from utils.domain import registrable_domain

INTERNAL_DOMAIN_SUFFIXES = (".local", ".internal")
MAX_REDIRECTS = 5
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "")


# CLASS_CONTRACT: CrawlSafetyError
# Purpose: Signal crawler-specific safety or bounded-fetch violations.
# LINKS: PLAN 08-03 Task 3
class CrawlSafetyError(URLSafetyError):
    pass


# CLASS_CONTRACT: CrawlSettings
# Purpose: Carry bounded crawl limits and safety toggles.
# LINKS: PLAN 08-03 Task 3
@dataclass(frozen=True)
class CrawlSettings:
    max_pages: int = 50
    max_depth: int = 3
    same_domain_only: bool = True
    timeout_seconds: int = 120
    max_response_bytes: int = 10_485_760
    max_retries: int = 1


# CLASS_CONTRACT: CrawlPage
# Purpose: Represent one fetched and extracted page in the crawl report corpus.
# LINKS: PLAN 08-03 Task 3
@dataclass
class CrawlPage:
    url: str
    depth: int
    title: str = ""
    meta_description: str = ""
    headings: list[str] = field(default_factory=list)
    body_text: str = ""


# CLASS_CONTRACT: CrawlResult
# Purpose: Aggregate collected pages, crawl errors, and execution metadata.
# LINKS: PLAN 08-03 Task 3
@dataclass
class CrawlResult:
    pages: list[CrawlPage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    visited_count: int = 0
    elapsed_seconds: float = 0.0
    limit_reached: bool = False


# block_crawler_safety_policy: Crawl URL validation and canonicalization
# Semantic block: Blocks unsafe schemes, internal hosts, private/link-local targets, and unstable URL variants before crawl frontier use.


# FUNCTION_CONTRACT: _hostname
# Purpose: Extract lowercase hostname from a URL string.
# Input: url (str)
# Output: str
# Side Effects: none
# Business Rules: Returns empty string when parsing fails or URL has no hostname.
# Failure Modes: never raises.
# LINKS: PLAN 08-03 Task 2
def _hostname(url: str) -> str:
    try:
        return (urlparse(str(url)).hostname or "").lower()
    except Exception:
        return ""


# FUNCTION_CONTRACT: _is_internal_domain
# Purpose: Detect internal-only hostname suffixes excluded from crawling.
# Input: hostname (str)
# Output: bool
# Side Effects: none
# Business Rules: Blocks .local and .internal names before DNS lookup.
# Failure Modes: never raises.
# LINKS: PLAN 08-03 Task 2
def _is_internal_domain(hostname: str) -> bool:
    hostname = str(hostname or "").lower().rstrip(".")
    return any(hostname.endswith(suffix) for suffix in INTERNAL_DOMAIN_SUFFIXES)


# FUNCTION_CONTRACT: is_safe_url
# Purpose: Return whether URL passes crawl SSRF safety checks.
# Input: url (str)
# Output: bool
# Side Effects: may resolve DNS through validate_safe_url_with_ips.
# Business Rules: Allows only http/https public targets; blocks localhost, private/link-local IPs, and .local/.internal domains.
# Failure Modes: returns False for malformed or unsafe URLs.
# LINKS: PLAN 08-03 Task 2
def is_safe_url(url: str) -> bool:
    hostname = _hostname(url)
    if not hostname or _is_internal_domain(hostname):
        return False
    try:
        validate_safe_url_with_ips(str(url).strip())
    except URLSafetyError:
        return False
    return True


# FUNCTION_CONTRACT: normalize_url
# Purpose: Canonicalize URLs for crawl duplicate detection.
# Input: url (str), base (str)
# Output: str
# Side Effects: none
# Business Rules: Resolves relative URLs, lowercases scheme/host, strips fragments, and sorts query parameters.
# Failure Modes: returns empty string for unparseable/empty input.
# LINKS: PLAN 08-03 Task 2
def normalize_url(url: str, base: str = "") -> str:
    if not url:
        return ""
    absolute_url = urljoin(base, str(url).strip()) if base else str(url).strip()
    parsed = urlparse(absolute_url)
    if not parsed.scheme or not parsed.netloc:
        return ""

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return ""

    netloc = hostname
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunparse((scheme, netloc, parsed.path or "/", "", query, ""))


# FUNCTION_CONTRACT: _registrable_domain
# Purpose: Compute the registrable (eTLD+1) same-site grouping key for crawl scoping.
# Input: hostname (str)
# Output: str — the registrable domain; falls back to the lowercased host if resolution yields ""
# Side Effects: none externally; delegates to utils.domain's cached offline PSL lookup
# Business Rules: Delegates to utils.domain.registrable_domain (Public Suffix List via tldextract).
#   Falls back to the bare host when the PSL yields no registrable domain (e.g. single-label host),
#   so same-domain scoping degrades gracefully instead of treating all hosts as external.
# Failure Modes: never raises.
# LINKS: PLAN 08-03 Task 2, utils/domain.py#registrable_domain
def _registrable_domain(hostname: str) -> str:
    host = str(hostname or "").lower().strip()
    if not host:
        return ""
    registered = registrable_domain(host)
    return registered or host


# FUNCTION_CONTRACT: _same_domain
# Purpose: Check whether target host is within the current crawl domain boundary.
# Input: target_hostname (str), current_domain (str)
# Output: bool
# Side Effects: none
# Business Rules: Allows exact host, subdomain, and shared registrable domain such as blog.example.com -> example.com.
# Failure Modes: never raises.
# LINKS: PLAN 08-03 Task 2
def _same_domain(target_hostname: str, current_domain: str) -> bool:
    target = str(target_hostname or "").lower().rstrip(".")
    current = str(current_domain or "").lower().rstrip(".")
    if not target or not current:
        return False
    return (
        target == current
        or target.endswith(f".{current}")
        or current.endswith(f".{target}")
        or _registrable_domain(target) == _registrable_domain(current)
    )


# block_crawler_dns_rebinding_guard: IP pinning and redirect validation
# Semantic block: Pins the resolved IP before fetch and rejects redirects that resolve outside the pinned address or domain scope.


# FUNCTION_CONTRACT: pin_ip_and_validate
# Purpose: Normalize a URL, validate crawl safety, and pin its first resolved IP.
# Input: url (str)
# Output: tuple[str, str]
# Side Effects: resolves DNS.
# Business Rules: URL must be safe; first resolved IP becomes the redirect comparison pin.
# Failure Modes: raises URLSafetyError for unsafe/unresolved URLs.
# LINKS: PLAN 08-03 Task 2
def pin_ip_and_validate(url: str) -> tuple[str, str]:
    normalized_url = normalize_url(url)
    if not normalized_url:
        raise URLSafetyError("Invalid URL format")
    hostname = _hostname(normalized_url)
    if _is_internal_domain(hostname):
        raise URLSafetyError(f"Requests to internal hosts are not allowed: {hostname}")

    _, resolved_ips = validate_safe_url_with_ips(normalized_url)
    if not resolved_ips:
        raise URLSafetyError(f"Host resolution failed: {hostname}")
    return normalized_url, resolved_ips[0]


# FUNCTION_CONTRACT: should_follow_redirect
# Purpose: Validate whether crawler may follow an HTTP redirect target.
# Input: target_url (str), same_domain_only (bool), current_domain (str), pinned_ip (str = None)
# Output: bool
# Side Effects: resolves DNS for target_url.
# Business Rules: Blocks unsafe targets, DNS pin changes, and cross-domain redirects when same-domain mode is active.
# Failure Modes: returns False for invalid or unsafe redirect targets.
# LINKS: PLAN 08-03 Task 2
def should_follow_redirect(
    target_url: str,
    same_domain_only: bool,
    current_domain: str,
    pinned_ip: str | None = None,
) -> bool:
    try:
        normalized_target, target_ip = pin_ip_and_validate(target_url)
    except URLSafetyError:
        return False

    if pinned_ip and target_ip != pinned_ip:
        return False

    if same_domain_only and not _same_domain(_hostname(normalized_target), current_domain):
        return False

    return True


# FUNCTION_CONTRACT: _extract_headings
# Purpose: Extract h1-h6 text from fetched HTML.
# Input: html_content (str)
# Output: list[str]
# Side Effects: none
# Business Rules: Keeps heading text only, strips nested tags, deduplicates in first-seen order.
# Failure Modes: never raises.
# LINKS: PLAN 08-03 Task 3
def _extract_headings(html_content: str) -> list[str]:
    headings: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"<h[1-6][^>]*>(.*?)</h[1-6]>",
        html_content or "",
        flags=re.IGNORECASE | re.DOTALL,
    ):
        text = re.sub(r"<[^>]+>", " ", match.group(1))
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            headings.append(text)
    return headings


# FUNCTION_CONTRACT: _extract_links
# Purpose: Extract conservative anchor href targets from HTML.
# Input: html_content (str), base_url (str)
# Output: list[str]
# Side Effects: none
# Business Rules: Reads a[href] only, normalizes against base URL, skips empty/mail/javascript fragments.
# Failure Modes: never raises.
# LINKS: PLAN 08-03 Task 3
def _extract_links(html_content: str, base_url: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"<a\s+[^>]*href\s*=\s*[\"']([^\"']+)[\"']",
        html_content or "",
        flags=re.IGNORECASE,
    ):
        href = html.unescape(match.group(1)).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        normalized = normalize_url(href, base=base_url)
        if normalized and normalized not in seen:
            seen.add(normalized)
            links.append(normalized)
    return links


# FUNCTION_CONTRACT: _request_once
# Purpose: Fetch one URL with manual redirect and response-size safeguards.
# Input: session, url, current_domain, pinned_ip, settings, request_timeout
# Output: tuple[str, str]
# Side Effects: performs one or more HTTP requests through requests.Session.
# Business Rules: Validates redirects, content type, peer IP, and max response bytes before returning HTML.
# Failure Modes: raises CrawlSafetyError, URLSafetyError, or requests exceptions.
# LINKS: PLAN 08-03 Task 3
def _request_once(
    session: requests.Session,
    url: str,
    current_domain: str,
    pinned_ip: str,
    settings: CrawlSettings,
    request_timeout: float,
) -> tuple[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0 Safari/537.36"
        )
    }
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        response = session.get(
            current_url,
            headers=headers,
            timeout=request_timeout,
            allow_redirects=False,
            stream=True,
        )
        try:
            if response.is_redirect or response.is_permanent_redirect:
                redirect_target = response.headers.get("Location", "").strip()
                if not redirect_target:
                    raise CrawlSafetyError("Redirect response missing Location header")
                next_url = normalize_url(redirect_target, base=current_url)
                if not should_follow_redirect(
                    next_url,
                    same_domain_only=settings.same_domain_only,
                    current_domain=current_domain,
                    pinned_ip=pinned_ip,
                ):
                    raise CrawlSafetyError(f"Unsafe redirect blocked: {next_url}")
                current_url = next_url
                continue

            WebScraper._assert_peer_ip_matches_allowlist(
                current_url,
                [pinned_ip],
                WebScraper._extract_requests_peer_ip(response),
            )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise CrawlSafetyError(f"Unsupported content type: {content_type}")

            chunks: list[bytes] = []
            total_bytes = 0
            for chunk in response.iter_content(chunk_size=65_536):
                if not chunk:
                    continue
                total_bytes += len(chunk)
                if total_bytes > settings.max_response_bytes:
                    raise CrawlSafetyError("Response exceeded max_response_bytes")
                chunks.append(chunk)
            return current_url, b"".join(chunks).decode(
                response.encoding or "utf-8",
                errors="replace",
            )
        finally:
            response.close()

    raise CrawlSafetyError("Too many redirects while crawling URL")


# FUNCTION_CONTRACT: _fetch_html_bounded
# Purpose: Fetch HTML with timeout, retry, redirect, DNS pinning, and response-size limits.
# Input: url, current_domain, pinned_ip, settings, remaining_timeout
# Output: tuple[str, str]
# Side Effects: performs HTTP request.
# Business Rules: Allows at most settings.max_retries retry attempts after first failure.
# Failure Modes: propagates final request/safety exception.
# LINKS: PLAN 08-03 Task 3
def _fetch_html_bounded(
    url: str,
    current_domain: str,
    pinned_ip: str,
    settings: CrawlSettings,
    remaining_timeout: float,
) -> tuple[str, str]:
    attempts = max(1, settings.max_retries + 1)
    request_timeout = max(1.0, min(float(settings.timeout_seconds), remaining_timeout))
    retrier = Retrying(
        stop=stop_after_attempt(attempts),
        wait=wait_fixed(0),
        retry=retry_if_exception_type((requests.RequestException, TimeoutError)),
        reraise=True,
    )
    with requests.Session() as session:
        return retrier(
            _request_once,
            session,
            url,
            current_domain,
            pinned_ip,
            settings,
            request_timeout,
        )


# block_crawler_frontier_filter: Bounded crawl queue filtering
# Semantic block: Enforces page/depth limits, duplicate normalization, URL safety, same-domain boundaries, and timeout budget.


# block_crawler_page_collect: WebScraper-composed page extraction
# Semantic block: Fetches bounded HTML for links and delegates text/metadata extraction to WebScraper.


# FUNCTION_CONTRACT: bounded_crawl
# Purpose: Crawl seed URLs within configured bounds and return extracted page text for math analysis.
# Input: seed_urls (list[str]), settings (CrawlSettings | None = None)
# Output: CrawlResult
# Side Effects: performs bounded HTTP fetches and logs crawl progress markers.
# Business Rules: No unbounded recursion; duplicate normalized URLs skipped; same-domain mode defaults on; WebScraper extracts text.
# Failure Modes: Unsafe/unfetchable pages are recorded in result.errors and crawl continues until bounds or timeout.
# LINKS: PLAN 08-03 Task 3
def bounded_crawl(
    seed_urls: list[str],
    settings: CrawlSettings | None = None,
) -> CrawlResult:
    if not seed_urls:
        return CrawlResult(errors=["No seed URLs provided for crawl"])

    settings = settings or CrawlSettings()
    max_pages = max(1, int(settings.max_pages))
    max_depth = max(0, int(settings.max_depth))
    start_time = time.monotonic()
    deadline = start_time + max(1, int(settings.timeout_seconds))

    result = CrawlResult()
    frontier: list[tuple[str, int, str, str]] = []
    visited: set[str] = set()
    queued: set[str] = set()

    for seed_url in seed_urls:
        try:
            normalized_url, pinned_ip = pin_ip_and_validate(seed_url)
        except URLSafetyError as exc:
            result.errors.append(f"{seed_url}: {exc}")
            continue
        seed_domain = _hostname(normalized_url)
        if normalized_url not in queued:
            frontier.append((normalized_url, 0, seed_domain, pinned_ip))
            queued.add(normalized_url)

    while frontier and len(result.pages) < max_pages:
        if time.monotonic() >= deadline:
            result.limit_reached = True
            result.errors.append("Crawl timeout reached")
            break

        current_url, depth, seed_domain, pinned_ip = frontier.pop(0)
        if current_url in visited:
            continue
        visited.add(current_url)

        try:
            final_url, html_content = _fetch_html_bounded(
                current_url,
                current_domain=seed_domain,
                pinned_ip=pinned_ip,
                settings=settings,
                remaining_timeout=deadline - time.monotonic(),
            )
            scraped: ScrapedContent = WebScraper._extract_text(html_content, final_url)
            if not scraped.success:
                result.errors.append(f"{final_url}: {scraped.error or 'text extraction failed'}")
            else:
                result.pages.append(
                    CrawlPage(
                        url=final_url,
                        depth=depth,
                        title=scraped.title,
                        meta_description=scraped.meta_description,
                        headings=_extract_headings(html_content),
                        body_text=scraped.text,
                    )
                )
                logger.info(
                    "[GRACE:block_crawler_page_collect:STATE] beliefState=crawl_page_collected "
                    f"Collected crawl page {len(result.pages)}/{max_pages}: {final_url}"
                )

            if depth >= max_depth or len(result.pages) >= max_pages:
                continue

            for link_url in _extract_links(html_content, final_url):
                if link_url in queued or link_url in visited:
                    continue
                if not is_safe_url(link_url):
                    continue
                if settings.same_domain_only and not _same_domain(_hostname(link_url), seed_domain):
                    continue
                try:
                    normalized_link, link_ip = pin_ip_and_validate(link_url)
                except URLSafetyError:
                    continue
                if normalized_link in queued or normalized_link in visited:
                    continue
                frontier.append((normalized_link, depth + 1, seed_domain, link_ip))
                queued.add(normalized_link)
        except Exception as exc:
            result.errors.append(f"{current_url}: {exc}")

    result.visited_count = len(visited)
    result.elapsed_seconds = time.monotonic() - start_time
    if frontier and len(result.pages) >= max_pages:
        result.limit_reached = True
    return result
