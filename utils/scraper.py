"""
Web scraper module — supports both synchronous and asynchronous scraping,
with caching support (improvements #6, #7).
"""

import asyncio
import re
import ssl
import warnings
from typing import Optional, List, Callable, Tuple
from urllib.parse import urljoin

import aiohttp
import trafilatura
import requests
import urllib3
from dataclasses import dataclass, field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.settings import SCRAPING_CONFIG
from utils.logger import logger
from utils.cache import scraping_cache
from utils.url_safety import URLSafetyError, validate_safe_url_with_ips

# Config values
TIMEOUT: int = SCRAPING_CONFIG.get("timeout_seconds", 30)
MAX_RETRIES: int = 3
MAX_REDIRECTS: int = 5


@dataclass
class ScrapedContent:
    url: str
    title: str = ""
    meta_description: str = ""
    meta_keywords: List[str] = field(default_factory=list)
    text: str = ""
    success: bool = False
    error: Optional[str] = None


class WebScraper:
    @staticmethod
    def _is_certificate_verification_error(exc: BaseException) -> bool:
        """Return True when the exception represents an SSL certificate validation failure."""
        if isinstance(exc, (ssl.SSLCertVerificationError, aiohttp.ClientConnectorCertificateError)):
            return True
        if isinstance(exc, requests.exceptions.SSLError):
            return True

        message = str(exc).lower()
        return "certificate verify failed" in message or "certificate_verify_failed" in message

    @staticmethod
    def _extract_metadata(html_content: str, url: str) -> Tuple[str, str, List[str]]:
        """Extract metadata (title, description, keywords) from HTML."""
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

    @staticmethod
    def _build_llm_context(
        text: str,
        title: str,
        description: str,
        keywords: List[str],
    ) -> str:
        """Build text context for downstream LLM processing."""
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

    @staticmethod
    def _validate_url_scheme(url: str) -> None:
        """Validate URL safety before any outbound request."""
        validate_safe_url_with_ips(url)

    @staticmethod
    def _extract_requests_peer_ip(response: requests.Response) -> Optional[str]:
        """Best-effort peer IP extraction from a requests response."""
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

    @staticmethod
    def _extract_aiohttp_peer_ip(response: aiohttp.ClientResponse) -> Optional[str]:
        """Best-effort peer IP extraction from an aiohttp response."""
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

    @staticmethod
    def _assert_peer_ip_matches_allowlist(
        url: str,
        allowed_ips: List[str],
        peer_ip: Optional[str],
    ) -> None:
        """Reject connections whose peer IP differs from the validated DNS answer."""
        if not allowed_ips:
            return
        if not peer_ip:
            raise URLSafetyError(f"Could not verify remote peer IP for {url}")
        if peer_ip not in allowed_ips:
            raise URLSafetyError(
                f"Remote peer IP {peer_ip} did not match validated DNS results for {url}"
            )

    @staticmethod
    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, TimeoutError)),
        reraise=True,
    )
    def _fetch_url(url: str) -> str:
        """Internal method to fetch URL content with retries."""
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

    @staticmethod
    async def _fetch_url_async(url: str, session: aiohttp.ClientSession) -> str:
        """Async method to fetch URL content (improvement #7)."""
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

    @staticmethod
    def _extract_text(html_content: str, url: str) -> ScrapedContent:
        """Extract text from HTML content using trafilatura."""
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

    @staticmethod
    def scrape_url(url: str) -> ScrapedContent:
        """
        Scrape content from a single URL with caching support.
        Returns ScrapedContent object.
        """
        # Check cache first (improvement #6)
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

    @staticmethod
    async def _scrape_url_async(url: str, session: aiohttp.ClientSession) -> ScrapedContent:
        """Async scrape a single URL (improvement #7)."""
        # Check cache first
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

    @staticmethod
    def scrape_urls(
        urls: List[str],
        progress_callback: Optional[Callable] = None,
        use_async: bool = True,
    ) -> List[ScrapedContent]:
        """
        Scrape multiple URLs. Uses async by default (improvement #7).

        Args:
            urls: List of URLs to scrape.
            progress_callback: Optional callback for progress updates.
            use_async: Whether to use async scraping (default: True).
        """
        if use_async:
            try:
                return WebScraper._scrape_urls_async(urls, progress_callback)
            except Exception as e:
                logger.warning(f"Async scraping failed, falling back to sync: {e}")

        # Fallback to synchronous scraping
        return WebScraper._scrape_urls_sync(urls, progress_callback)

    @staticmethod
    def _scrape_urls_sync(
        urls: List[str],
        progress_callback: Optional[Callable] = None,
    ) -> List[ScrapedContent]:
        """Synchronous scraping of multiple URLs."""
        results: List[ScrapedContent] = []
        total: int = len(urls)

        for i, url in enumerate(urls):
            result: ScrapedContent = WebScraper.scrape_url(url)
            results.append(result)

            if progress_callback:
                progress_callback((i + 1) / total, f"Scraping {i + 1}/{total}: {url}")

        return results

    @staticmethod
    def _scrape_urls_async(
        urls: List[str],
        progress_callback: Optional[Callable] = None,
    ) -> List[ScrapedContent]:
        """Async scraping of multiple URLs (improvement #7)."""

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
