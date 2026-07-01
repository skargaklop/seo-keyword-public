"""
Web scraper module — supports both synchronous and asynchronous scraping,
with caching support (improvements #6, #7).
"""

import asyncio
import re
import ssl
import warnings
from typing import Optional, List, Callable, Tuple, Any
from urllib.parse import urljoin

import aiohttp
import trafilatura
import requests
import urllib3
from dataclasses import dataclass, field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.settings import SCRAPING_CONFIG, SCRAPER_CONFIG
from utils.logger import logger
from utils.cache import scraping_cache
from utils.url_safety import URLSafetyError, validate_safe_url_with_ips


# MODULE_CONTRACT: scraper
# Purpose: Web content extraction with URL safety validation, async support, and result caching
# Rationale: Safely scrapes web pages for SEO analysis while blocking requests to private/internal/loopback addresses
# Dependencies: trafilatura, aiohttp, requests, tenacity, utils.url_safety, utils.cache, utils.logger
# Exports: WebScraper (class with scrape_urls, scrape_url), ScrapedContent (dataclass)
# LINKS: requirements.xml#UC-001, technology.xml#DEP-002, development-plan.xml#MOD-005
# MODULE_MAP: scraper
# Public Functions: WebScraper.scrape_urls(), WebScraper.scrape_url(), WebScraper.scrape_urls_with_browser_fallback()
# Private Helpers: _fetch_url(), _fetch_url_async(), _extract_text(), _extract_metadata(), _build_llm_context(), _validate_url_scheme(), _scrape_urls_sync(), _scrape_urls_async(), _scrape_url_async(), _is_certificate_verification_error(), _extract_requests_peer_ip(), _extract_aiohttp_peer_ip(), _assert_peer_ip_matches_allowlist(), _scraped_content_from_browser_result(), _is_block_content()
# Key Semantic Blocks: block_scraper_fetch_url_content, block_scraper_safety_validate, block_scraper_extract_page_text
# Critical Flows: URL safety validation -> async/sync fetch with redirect following -> trafilatura extraction -> cache store
# Verification: verification-plan.xml#V-MOD-005
# CHANGE_SUMMARY: Replaced shallow GRACE markers with complete module-level contracts

# Config values
TIMEOUT: int = SCRAPING_CONFIG.get("timeout_seconds", 30)
MAX_RETRIES: int = 3
MAX_REDIRECTS: int = 5

# CLASS_CONTRACT: ScrapedContent
# Purpose: Carry extracted page metadata, text, success state, and scrape errors.
# LINKS: requirements.xml#UC-001
@dataclass
class ScrapedContent:
    url: str
    title: str = ""
    meta_description: str = ""
    meta_keywords: List[str] = field(default_factory=list)
    text: str = ""
    success: bool = False
    error: Optional[str] = None

# CLASS_CONTRACT: WebScraper
# Purpose: Validate, fetch, extract, cache, and aggregate web page content.
# LINKS: requirements.xml#UC-001, technology.xml#DEP-002
class WebScraper:
    # FUNCTION_CONTRACT: _is_certificate_verification_error
    # Purpose: Implement the  is certificate verification error helper for this module.
    # Input: exc (BaseException)
    # Output: bool
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _is_certificate_verification_error(exc: BaseException) -> bool:
        if isinstance(exc, (ssl.SSLCertVerificationError, aiohttp.ClientConnectorCertificateError)):
            return True
        if isinstance(exc, requests.exceptions.SSLError):
            return True

        message = str(exc).lower()
        return "certificate verify failed" in message or "certificate_verify_failed" in message
    # FUNCTION_CONTRACT: _extract_metadata
    # Purpose: Implement the  extract metadata helper for this module.
    # Input: html_content (str), url (str)
    # Output: Tuple[str, str, List[str]]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _extract_metadata(html_content: str, url: str) -> Tuple[str, str, List[str]]:
        try:
            metadata = trafilatura.extract_metadata(html_content, default_url=url)
        except Exception as e:
            logger.warning(f"Metadata extraction failed for {url}: {e}")
            return "", "", []

        if metadata is None:
            return "", "", []

        title: str = (metadata.title or "").strip()
        description: str = (metadata.description or "").strip()
        raw_tags: List[str] = list(metadata.tags or [])

        keywords: List[str] = []
        seen: set = set()
        for tag in raw_tags:
            for chunk in re.split(r"[;,]", tag):
                kw: str = chunk.strip()
                if kw and kw.lower() not in seen:
                    keywords.append(kw)
                    seen.add(kw.lower())

        return title, description, keywords
    # FUNCTION_CONTRACT: _build_llm_context
    # Purpose: Implement the  build llm context helper for this module.
    # Input: text (str), title (str), description (str), keywords (List[str])
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _build_llm_context(
        text: str,
        title: str,
        description: str,
        keywords: List[str],
    ) -> str:
        parts: List[str] = []
        if title:
            parts.append(f"Meta title: {title}")
        if description:
            parts.append(f"Meta description: {description}")
        if keywords:
            parts.append(f"Meta keywords: {', '.join(keywords)}")
        if text:
            parts.append(f"Page content:\n{text}")
        return "\n\n".join(parts).strip()
    # FUNCTION_CONTRACT: _validate_url_scheme
    # Purpose: Implement the  validate url scheme helper for this module.
    # Input: url (str)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _validate_url_scheme(url: str) -> None:
        validate_safe_url_with_ips(url)
    # FUNCTION_CONTRACT: _extract_requests_peer_ip
    # Purpose: Implement the  extract requests peer ip helper for this module.
    # Input: response (requests.Response)
    # Output: Optional[str]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _extract_requests_peer_ip(response: requests.Response) -> Optional[str]:
        candidates = [
            getattr(getattr(response.raw, "_connection", None), "sock", None),
            getattr(getattr(response.raw, "connection", None), "sock", None),
            getattr(
                getattr(getattr(getattr(response.raw, "_fp", None), "fp", None), "raw", None),
                "_sock",
                None,
            ),
        ]
        for sock in candidates:
            if sock is None:
                continue
            try:
                peer = sock.getpeername()
            except Exception:
                continue
            if isinstance(peer, tuple) and peer:
                return str(peer[0])
        return None
    # FUNCTION_CONTRACT: _extract_aiohttp_peer_ip
    # Purpose: Implement the  extract aiohttp peer ip helper for this module.
    # Input: response (aiohttp.ClientResponse)
    # Output: Optional[str]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _extract_aiohttp_peer_ip(response: aiohttp.ClientResponse) -> Optional[str]:
        transport = None
        if getattr(response, "connection", None) is not None:
            transport = getattr(response.connection, "transport", None)
        if transport is None:
            transport = getattr(getattr(response, "_protocol", None), "transport", None)
        if transport is None:
            return None
        peer = transport.get_extra_info("peername")
        if isinstance(peer, tuple) and peer:
            return str(peer[0])
        return None
    # FUNCTION_CONTRACT: _assert_peer_ip_matches_allowlist
    # Purpose: Implement the  assert peer ip matches allowlist helper for this module.
    # Input: url (str), allowed_ips (List[str]), peer_ip (Optional[str])
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _assert_peer_ip_matches_allowlist(
        url: str,
        allowed_ips: List[str],
        peer_ip: Optional[str],
    ) -> None:
        if not allowed_ips:
            return
        if not peer_ip:
            raise URLSafetyError(f"Could not verify remote peer IP for {url}")
        if peer_ip not in allowed_ips:
            raise URLSafetyError(
                f"Remote peer IP {peer_ip} did not match validated DNS results for {url}"
            )
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, TimeoutError)),
        reraise=True,
    )
    # FUNCTION_CONTRACT: _fetch_url
    # Purpose: Implement the fetch url helper for this module.
    # Input: url (str)
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _fetch_url(url: str) -> str:
        headers: dict = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        current_url = url
        with requests.Session() as session:
            for _ in range(MAX_REDIRECTS + 1):
                _, allowed_ips = validate_safe_url_with_ips(current_url)
                try:
                    response: requests.Response = session.get(
                        current_url,
                        headers=headers,
                        timeout=TIMEOUT,
                        allow_redirects=False,
                        stream=True,
                    )
                except requests.exceptions.SSLError as exc:
                    if not WebScraper._is_certificate_verification_error(exc):
                        raise

                    logger.warning(
                        f"SSL verification failed for {current_url}; retrying without certificate verification"
                    )
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
                        response = session.get(
                            current_url,
                            headers=headers,
                            timeout=TIMEOUT,
                            allow_redirects=False,
                            verify=False,
                            stream=True,
                        )
                if response.is_redirect or response.is_permanent_redirect:
                    redirect_target = response.headers.get("Location", "").strip()
                    if not redirect_target:
                        raise ValueError("Redirect response missing Location header")
                    response.close()
                    current_url = urljoin(current_url, redirect_target)
                    continue
                peer_ip = WebScraper._extract_requests_peer_ip(response)
                try:
                    WebScraper._assert_peer_ip_matches_allowlist(
                        current_url, allowed_ips, peer_ip
                    )
                except URLSafetyError:
                    response.close()
                    raise

                response.raise_for_status()
                html_content = response.text
                response.close()
                return html_content

        raise ValueError("Too many redirects while fetching URL")
    # FUNCTION_CONTRACT: _fetch_url_async
    # Purpose: Implement the  fetch url async helper for this module.
    # Input: url (str), session (aiohttp.ClientSession)
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    async def _fetch_url_async(url: str, session: aiohttp.ClientSession) -> str:
        headers: dict = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        current_url = url
        for _ in range(MAX_REDIRECTS + 1):
            _, allowed_ips = validate_safe_url_with_ips(current_url)
            async with session.get(
                current_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                allow_redirects=False,
            ) as response:
                if response.status in {301, 302, 303, 307, 308}:
                    redirect_target = response.headers.get("Location", "").strip()
                    if not redirect_target:
                        raise ValueError("Redirect response missing Location header")
                    current_url = urljoin(current_url, redirect_target)
                    continue
                WebScraper._assert_peer_ip_matches_allowlist(
                    current_url,
                    allowed_ips,
                    WebScraper._extract_aiohttp_peer_ip(response),
                )

                response.raise_for_status()
                return await response.text()

        raise ValueError("Too many redirects while fetching URL")
    # FUNCTION_CONTRACT: _extract_text
    # Purpose: Implement the  extract text helper for this module.
    # Input: html_content (str), url (str)
    # Output: ScrapedContent
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _extract_text(html_content: str, url: str) -> ScrapedContent:
        if not html_content:
            msg: str = "Empty response from server"
            logger.warning(f"{msg}: {url}")
            return ScrapedContent(url=url, success=False, error=msg)

        text: Optional[str] = trafilatura.extract(
            html_content,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        text_content: str = (text or "").strip()
        title, meta_description, meta_keywords = WebScraper._extract_metadata(html_content, url)
        has_metadata: bool = bool(title or meta_description or meta_keywords)

        if len(text_content) < 50 and not has_metadata:
            msg = "Insufficient text extracted"
            logger.warning(f"{msg}: {url}")
            return ScrapedContent(url=url, success=False, error=msg)

        if len(text_content) < 50 and has_metadata:
            logger.info(f"Using metadata fallback for {url}")

        llm_context: str = WebScraper._build_llm_context(
            text=text_content,
            title=title,
            description=meta_description,
            keywords=meta_keywords,
        )

        logger.info(f"Successfully scraped {len(llm_context)} chars from {url}")
        return ScrapedContent(
            url=url,
            title=title,
            meta_description=meta_description,
            meta_keywords=meta_keywords,
            text=llm_context,
            success=True,
        )
    # FUNCTION_CONTRACT: scrape_url
    # Purpose: Implement the scrape url helper for this module.
    # Input: url (str)
    # Output: ScrapedContent
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def scrape_url(url: str) -> ScrapedContent:
        cached = scraping_cache.get(url)
        if cached is not None:
            return cached

        try:
            logger.info(f"Scraping URL: {url}")
            html_content: str = WebScraper._fetch_url(url)
            result: ScrapedContent = WebScraper._extract_text(html_content, url)

            # Cache successful results
            if result.success:
                scraping_cache.set(url, result)

            return result

        except Exception as e:
            error_msg: str = str(e)
            logger.error(f"Failed to scrape {url}: {error_msg}")
            return ScrapedContent(url=url, success=False, error=error_msg)
    # FUNCTION_CONTRACT: _scrape_url_async
    # Purpose: Implement the  scrape url async helper for this module.
    # Input: url (str), session (aiohttp.ClientSession)
    # Output: ScrapedContent
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    async def _scrape_url_async(url: str, session: aiohttp.ClientSession) -> ScrapedContent:
        cached = scraping_cache.get(url)
        if cached is not None:
            return cached

        try:
            logger.info(f"Async scraping URL: {url}")
            html_content: str = await WebScraper._fetch_url_async(url, session)
            result: ScrapedContent = WebScraper._extract_text(html_content, url)

            if result.success:
                scraping_cache.set(url, result)

            return result
        except Exception as e:
            if WebScraper._is_certificate_verification_error(e):
                logger.warning(
                    f"Async SSL verification failed for {url}; falling back to sync scraping"
                )
                return WebScraper.scrape_url(url)

            error_msg: str = str(e)
            logger.error(f"Failed to async scrape {url}: {error_msg}")
            return ScrapedContent(url=url, success=False, error=error_msg)
    # FUNCTION_CONTRACT: scrape_urls
    # Purpose: Implement the scrape urls helper for this module.
    # Input: urls (List[str]), progress_callback (Optional[Callable] = None), use_async (bool = True)
    # Output: List[ScrapedContent]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def scrape_urls(
        urls: List[str],
        progress_callback: Optional[Callable] = None,
        use_async: bool = True,
    ) -> List[ScrapedContent]:
        if use_async:
            try:
                return WebScraper._scrape_urls_async(urls, progress_callback)
            except Exception as e:
                logger.warning(f"Async scraping failed, falling back to sync: {e}")

        # Fallback to synchronous scraping
        return WebScraper._scrape_urls_sync(urls, progress_callback)
    # FUNCTION_CONTRACT: _scraped_content_from_browser_result
    # Purpose: Convert a BrowserScrapeResult (cloakbrowser fallback) into a ScrapedContent row
    # Input: url (str), browser_result (BrowserScrapeResult)
    # Output: ScrapedContent — success carries the extracted text/metadata, failure carries the first error
    # Side Effects: none
    # Business Rules: Never raises; maps trafilatura parsed_content into ScrapedContent fields
    # Failure Modes: Returns a failed ScrapedContent when the browser result is unsuccessful
    # LINKS: requirements.xml#UC-001, utils/browser_scraper.py
    @staticmethod
    def _scraped_content_from_browser_result(url: str, browser_result: Any) -> "ScrapedContent":
        parsed = getattr(browser_result, "parsed_content", {}) or {}
        title = (parsed.get("title") or "").strip()
        description = (parsed.get("description") or "").strip()
        text_content = (parsed.get("text") or "").strip()

        if not getattr(browser_result, "success", False):
            errors = getattr(browser_result, "errors", []) or []
            error_msg = errors[0] if errors else "Browser fallback failed"
            logger.warning(f"Browser fallback failed for {url}: {error_msg}")
            return ScrapedContent(url=url, success=False, error=error_msg)

        # Reuse the same LLM-context assembly shape WebScraper._extract_text produces so downstream
        # keyword/SEO consumers see identical formatting regardless of scrape path.
        llm_context = WebScraper._build_llm_context(
            text=text_content,
            title=title,
            description=description,
            keywords=[],
        )
        logger.info(f"Browser fallback recovered {len(llm_context)} chars from {url}")
        return ScrapedContent(
            url=url,
            title=title,
            meta_description=description,
            meta_keywords=[],
            text=llm_context,
            success=True,
        )
    # FUNCTION_CONTRACT: _is_block_content
    # Purpose: Detect a requests-scrape that technically "succeeded" but landed on a captcha / Cloudflare
    #   interstitial page. Challenge pages carry a <title>, so _extract_text marks them success=True — without
    #   this check the browser fallback would never fire for the exact failure mode it exists to handle.
    # Input: result (ScrapedContent)
    # Output: bool — True when the row is a success-flagged but content-blocked page needing browser retry
    # Side Effects: None (pure check); lazily imports the shared marker detector from browser_scraper
    # Business Rules: Hard failures (success=False) return False — they are handled by the not-success branch.
    #   Genuine article content returns False so real successes are never retried.
    # Failure Modes: Never raises; any import/detection error degrades to False (treat as not-blocked).
    # LINKS: requirements.xml#UC-001, utils/browser_scraper.py#_detect_content_block
    @staticmethod
    def _is_block_content(result: "ScrapedContent") -> bool:
        if not result.success:
            return False
        haystack = " ".join(part for part in (result.title or "", result.text or "") if part).lower()
        if not haystack:
            return False
        try:
            from utils.browser_scraper import _detect_content_block
        except Exception as exc:  # pragma: no cover - defensive: optional module wiring
            logger.warning(f"_is_block_content detector unavailable: {exc}")
            return False
        return _detect_content_block(haystack)

    # FUNCTION_CONTRACT: scrape_urls_with_browser_fallback
    # Purpose: Scrape URLs via requests, then retry the FAILED ones through cloakbrowser (url_llm fallback)
    # Input: urls (List[str]), progress_callback (Optional[Callable] = None), use_async (bool = True),
    #   fallback_enabled (Optional[bool] = None), fallback_headless (Optional[bool] = None)
    # Output: List[ScrapedContent] — one per url, in input order. A real browser recovery replaces the original
    #   row; a browser-landed block page becomes a forced final failure; an untouched success stays as-is.
    # Side Effects: Reads SCRAPER_CONFIG; lazily creates a BrowserScraper via create_browser_scraper; on a real
    #   recovery PERSISTS the recovered content to scraping_cache (overwriting a stale block entry); on a
    #   browser-landed block INVALIDATES any stale cached block entry so it is not re-served.
    # Business Rules: Fallback runs ONLY when enabled AND cloakbrowser deps are available; retried URLs are those
    #   that hard-failed OR landed on a captcha/Cloudflare block page despite success=True; a browser retry that
    #   itself lands on a block page is treated as a FINAL failure (challenge/thin text never fed to the LLM);
    #   a browser retry that hard-fails keeps the original result; genuinely successful rows are untouched.
    # Failure Modes: Never raises; browser errors degrade to the original requests-scrape result
    # LINKS: requirements.xml#UC-001, utils/browser_scraper.py#scrape_content, config.settings.SCRAPER_CONFIG
    @staticmethod
    def scrape_urls_with_browser_fallback(
        urls: List[str],
        progress_callback: Optional[Callable] = None,
        use_async: bool = True,
        fallback_enabled: Optional[bool] = None,
        fallback_headless: Optional[bool] = None,
    ) -> List[ScrapedContent]:
        # Primary path: unchanged requests-based scrape.
        results = WebScraper.scrape_urls(urls, progress_callback=progress_callback, use_async=use_async)

        # Resolve the toggle (explicit arg wins, else settings). No hardcoded default — settings.yaml owns it.
        enabled = (
            fallback_enabled
            if fallback_enabled is not None
            else bool(SCRAPER_CONFIG.get("content_browser_fallback_enabled", True))
        )
        if not enabled:
            return results

        # Retry hard failures AND requests rows that "succeeded" but landed on a captcha /
        # Cloudflare interstitial page (challenge pages carry a <title>, so they are success=True).
        needs_retry = [r.url for r in results if (not r.success) or WebScraper._is_block_content(r)]
        if not needs_retry:
            return results

        # Lazy import keeps the requests-only import graph clean when no fallback is needed.
        try:
            from utils.browser_scraper import create_browser_scraper
        except Exception as exc:  # pragma: no cover - defensive: optional module wiring
            logger.warning(f"Browser fallback unavailable (import failed): {exc}")
            return results

        browser_scraper = create_browser_scraper()
        if browser_scraper is None:
            logger.info("Browser fallback skipped: cloakbrowser dependencies unavailable")
            return results

        headless = (
            fallback_headless
            if fallback_headless is not None
            else bool(SCRAPER_CONFIG.get("content_browser_fallback_headless", True))
        )

        # Recover each retry candidate via cloakbrowser. A browser result is "usable" only when it
        # succeeded AND did not itself land on a captcha/Cloudflare/Akamai block page — otherwise the
        # challenge/thin text must NOT be fed to the LLM as site content, so it becomes a final failure.
        recovered_by_url: dict = {}
        forced_failure_by_url: dict = {}
        for url in needs_retry:
            logger.info(f"Retrying failed/blocked URL via browser fallback: {url}")
            browser_result = browser_scraper.scrape_content(url, {"headless": headless})
            recovered = WebScraper._scraped_content_from_browser_result(url, browser_result)
            if recovered.success and not WebScraper._is_block_content(recovered):
                recovered_by_url[url] = recovered
                # Persist the recovery so the next rerun hits the good result instead of
                # re-scraping (and re-failing) the original path. A success-but-blocked
                # requests page may already be cached; this overwrites it with real content.
                scraping_cache.set(url, recovered)
            elif recovered.success:
                # Browser "succeeded" but landed on a block interstitial → treat as final failure.
                logger.warning(
                    f"Browser fallback for {url} landed on a block page; treating as final failure"
                )
                forced_failure_by_url[url] = ScrapedContent(
                    url=url,
                    success=False,
                    error="Page remains blocked (captcha / Cloudflare / Akamai) after browser fallback",
                )
                # Drop any stale success-but-blocked entry so a later rerun does not serve the
                # cached block page as if it were valid content.
                scraping_cache.invalidate(url)
            else:
                # Browser retry hard-failed — keep the original result in the merge below.
                logger.info(f"Browser fallback failed for {url}; keeping original result")

        if not recovered_by_url and not forced_failure_by_url:
            return results

        # Merge precedence per URL: real recovery > forced failure > original row.
        merged: List[ScrapedContent] = []
        for r in results:
            if r.url in recovered_by_url:
                merged.append(recovered_by_url[r.url])
            elif r.url in forced_failure_by_url:
                merged.append(forced_failure_by_url[r.url])
            else:
                merged.append(r)
        return merged
    # FUNCTION_CONTRACT: _scrape_urls_sync
    # Purpose: Implement the  scrape urls sync helper for this module.
    # Input: urls (List[str]), progress_callback (Optional[Callable] = None)
    # Output: List[ScrapedContent]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _scrape_urls_sync(
        urls: List[str],
        progress_callback: Optional[Callable] = None,
    ) -> List[ScrapedContent]:
        results: List[ScrapedContent] = []
        total: int = len(urls)

        for i, url in enumerate(urls):
            result: ScrapedContent = WebScraper.scrape_url(url)
            results.append(result)

            if progress_callback:
                progress_callback((i + 1) / total, f"Scraping {i + 1}/{total}: {url}")

        return results
    # FUNCTION_CONTRACT: _scrape_urls_async
    # Purpose: Implement the  scrape urls async helper for this module.
    # Input: urls (List[str]), progress_callback (Optional[Callable] = None)
    # Output: List[ScrapedContent]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _scrape_urls_async(
        urls: List[str],
        progress_callback: Optional[Callable] = None,
    ) -> List[ScrapedContent]:
        # FUNCTION_CONTRACT: _run
        # Purpose: Implement the  run helper for this module.
        # Input: (none)
        # Output: List[ScrapedContent]
        # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
        # Business Rules: Preserves the current validation and control flow for this call path.
        # Failure Modes: Propagates upstream exceptions and existing fallback paths.
        # LINKS: requirements.xml#UC-001
        async def _run() -> List[ScrapedContent]:
            async with aiohttp.ClientSession() as session:
                tasks = [WebScraper._scrape_url_async(url, session) for url in urls]
                results: List[ScrapedContent] = []
                for i, coro in enumerate(asyncio.as_completed(tasks)):
                    result = await coro
                    results.append(result)
                    if progress_callback:
                        progress_callback(
                            (i + 1) / len(urls),
                            f"Scraping {i + 1}/{len(urls)}: {result.url}",
                        )
                return results

        # Run the async event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in an async context (e.g., Streamlit), use nest_asyncio or sync fallback
                return WebScraper._scrape_urls_sync(urls, progress_callback)
            return loop.run_until_complete(_run())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_run())
            finally:
                loop.close()
