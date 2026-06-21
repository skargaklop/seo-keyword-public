// MODULE_CONTRACT: utils/batch_parse_serp.js
// Purpose: CSS-class-agnostic Google SERP parser for browser-based scraping
// Rationale: Google auto-generates CSS class names; we use STABLE anchors instead
// Dependencies: none (runs in browser context via page.evaluate)
// Exports: IIFE function returning JSON array of SERP results
// LINKS: utils/browser_scraper.py#_execute_cloakbrowser_serp
// MODULE_MAP: utils/batch_parse_serp.js
// Public Functions: parse
// Private Helpers: sanitizeUrl, getContainer, parse
// Key Semantic Blocks: block_serp_parse_results, block_rich_snippet_extraction, block_serp_handle_pagination, block_serp_detect_containers, block_serp_define_patterns, block_serp_parse_items
// Critical Flows: h3 discovery -> container resolution -> URL sanitization -> snippet extraction -> rich snippet parsing -> deduped JSON output
// Verification: utils/browser_scraper.py#scrape_serp
// SEMANTIC_BLOCKS: block_serp_parse_results, block_rich_snippet_extraction, block_serp_handle_pagination
// VERIFICATION: utils/browser_scraper.py#scrape_serp
// CHANGE_SUMMARY: Added file-local GRACE metadata for browser-side SERP parsing and parser contract tracing.

/**
 * Google SERP batch parser — runs INSIDE the browser via page.evaluate()
 * No CSS class dependencies. Uses semantic HTML + ARIA + text patterns.
 * Returns JSON array of { title, url, snippet, rich_snippet }
 *
 * PHILOSOPHY:
 * Google auto-generates CSS class names that change constantly.
 * Instead of CSS classes, we use STABLE anchors:
 *   - Semantic HTML: h3 for titles, cite for URLs, a[href] for links
 *   - ARIA attributes: aria-label, role="img"
 *   - Text patterns: regex for prices, ratings, stock status
 *   - Data attributes: data-hveid (more stable than .classes)
 *
 * CONTRACT:
 * Input: (none) - operates on current document
 * Output: Array<{title, url, snippet, rich_snippet}>
 * Failure Mode: Returns empty array on parse errors
 */

(function() {
  'use strict';

  const R = [];
  const seen = new Set();

  // SKIP_TITLES: Common non-result text patterns that appear in h3 elements
  const SKIP = new Set([
    'Результати веб-пошуку','Результаты поиска','Відео','Video',
    'videos','images','shopping','news','maps','People also ask',
    'Люди також питають','Люди также спрашивают','Люди також запитують',
    'Результати','Результаты','Results',
  ]);

  // $: Normalize whitespace helper
  const $ = s => (s || '').replace(/\s+/g, ' ').trim();

  // SANITIZE: URL validation to prevent XSS and injection attacks
  // CR-03 FIX: Ensure URLs are properly sanitized before inclusion in results
  const sanitizeUrl = (url) => {
    if (!url || typeof url !== 'string') return '';
    // Only allow http/https protocols
    if (!url.startsWith('http://') && !url.startsWith('https://')) return '';
    // Remove any potential JavaScript or data URIs
    const cleaned = url.trim();
    // Basic validation: must contain domain
    if (!/^https?:\/\/[\w.-]+/i.test(cleaned)) return '';
    return cleaned;
  };

  // SEMANTIC_BLOCK: block_serp_detect_containers
  // Find the container div for a result by climbing from h3 to data-hveid or fixed height

  /**
   * Get container element for a result based on h3 heading
   * Uses data-hveid attribute as primary anchor (more stable than CSS classes)
   * Falls back to climbing 8 levels up from h3
   * @param {Element} h3 - The heading element
   * @returns {Element|null} Container element or null if not found
   */
  function getContainer(h3) {
    let c = h3.parentElement;
    while (c && c.tagName !== 'BODY') {
      if (c.hasAttribute && c.hasAttribute('data-hveid')) return c;
      c = c.parentElement;
    }
    // Fallback: climb fixed number of levels
    c = h3.parentElement;
    for (let i = 0; i < 8 && c && c.tagName !== 'BODY'; i++) c = c.parentElement;
    return (c && c.tagName !== 'BODY') ? c : null;
  }

  // SEMANTIC_BLOCK: block_serp_define_patterns
  // Pre-compiled regex patterns for rich snippet extraction

  /**
   * Regular expression patterns for extracting structured data
   * Compiled once for performance (avoids inline regex literal issues)
   */
  const RE = {
    // URL detection patterns
    urlLine:        /^https?:\/\//i,
    domainUrlLine:  /^[\w.-]+\.[\w]{2,}[\s/]/,
    cyrillic:       /[Ѐ-ӿ]/,

    // Pricing patterns (Ukrainian/Russian markets)
    pricing:        /^[\d\s]+[.,]?\d*\s*(?:грн|₴|\$)/,
    domainHttp:     /^[\w.-]+\.[\w]{2,}https?:\/\//,

    // Rating patterns (e.g., "4.5 з 5", "4,5/5")
    rating:         /([\d,]+)\s*(?:з\s*(\d+)|\/\s*(\d+))/,

    // Price extraction (e.g., "від 1 500 грн", "$25.99")
    price:          /(?:від\s*)?([\d\s]+[.,]\d*)\s*(грн|₴|\$|€|£)/i,
    price2:         /([\d\s]+[.,]\d*)\s*(грн|₴)/i,

    // Stock status patterns
    stock:          /У наявності|Немає в наявності|В наявності|Закінчується|In stock|Out of stock/ig,

    // Shipping info patterns
    shipping:       /(Безкоштовна доставка|Вартість доставки[^\n]*?)(?=\s*·|$)/i,

    // Domain extraction from URL
    domainExtract:  /(https?:\/\/)?([\w.-]+\.[\w]{2,})/,
  };

  // SEMANTIC_BLOCK: block_serp_parse_items
  // Parse a single SERP result from h3 heading

  /**
   * Parse a single SERP result from its h3 heading element
   * Extracts title, URL, snippet, and rich snippet data
   * @param {Element} h3 - The heading element for a result
   * @returns {Object|null} Parsed result object or null if invalid
   */
  function parse(h3) {
    const title = $(h3.textContent);

    // VALIDATION: Skip invalid titles
    if (!title || title.length < 5 || title.length > 300) return null;
    if (SKIP.has(title) || SKIP.has(title.toLowerCase())) return null;
    if (title.endsWith('?') && title.length < 60) return null;

    const box = getContainer(h3);
    if (!box) return null;

    // EXTRACT URL
    let url = '';
    { let c = h3; while (c && c.tagName !== 'BODY') {
      if (c.tagName === 'A' && c.href && c.href.startsWith('http')) { url = c.href; break; }
      c = c.parentElement;
    }}
    if (!url) {
      const lk = box.querySelector('a[href^="http"]');
      if (lk) url = lk.href;
    }
    // CR-03 FIX: Sanitize URL to prevent XSS
    url = sanitizeUrl(url);
    if (!url) return null;
    if (seen.has(url)) return null;  // Deduplicate
    seen.add(url);

    const fullText = $(box.textContent);

    // EXTRACT SNIPPET
    // Strategy: Find longest div text with meaningful content
    let snippet = '';
    {
      const cands = [];
      for (const d of box.querySelectorAll('div')) {
        const t = $(d.textContent);
        if (t.length < 40) continue;  // Too short
        if (t === title) continue;  // Skip title itself
        if (t.indexOf(title) >= 0 && t.length < title.length + 10) continue;  // Title with prefix
        if (RE.urlLine.test(t)) continue;  // Skip URL-only text
        if (RE.domainUrlLine.test(t) && !RE.cyrillic.test(t)) continue;  // Skip domain lines
        if (RE.pricing.test(t)) continue;  // Skip pricing-only lines
        if (RE.domainHttp.test(t)) continue;  // Skip domain+http artifacts
        cands.push(t);
      }

      // Sort by Cyrillic content count (prefer content with Ukrainian/Russian) then length
      cands.sort((a, b) => {
        const aN = (a.match(RE.cyrillic) || []).length;
        const bN = (b.match(RE.cyrillic) || []).length;
        return (aN !== bN) ? (bN - aN) : (b.length - a.length);
      });

      if (cands.length > 0) snippet = cands[0].substring(0, 500);
    }

    // EXTRACT RICH SNIPPETS
    // SEMANTIC_BLOCK: block_rich_snippet_extraction

    const rs = {};

    // RATING: Extract from aria-label (e.g., "Оцінка 4,5 з 5")
    const ra = box.querySelector(
      '[aria-label*="Оцінка" i], [aria-label*="star" i], ' +
      '[aria-label*="звезд" i], [aria-label*="rating" i], ' +
      '[role="img"][aria-label]'
    );
    if (ra) {
      const lbl = ra.getAttribute('aria-label') || '';
      const m = lbl.match(RE.rating);
      if (m) {
        rs.rating = m[1].replace(',', '.');
        rs.rating_max = parseFloat(m[2] || m[3] || 5);
      }
    }

    // REVIEWS: Extract review count and label
    const rv = box.querySelector(
      '[aria-label*="відгук" i], [aria-label*="отзыв" i], ' +
      '[aria-label*="review" i], a[href*="/oshop"]'
    );
    if (rv) {
      const lbl = rv.getAttribute('aria-label') || '';
      if (lbl) rs.reviews_label = lbl;
      const rt = $(rv.textContent);
      if (rt) rs.reviews = rt;
    }

    // PRICE: Extract price from full text
    const pm = fullText.match(RE.price);
    if (pm) rs.price = $(pm[0]);
    else {
      const pm2 = fullText.match(RE.price2);
      if (pm2) rs.price = $(pm2[0]);
    }

    // AVAILABILITY: Extract stock status
    const am = fullText.match(RE.stock);
    if (am) {
      rs.availability = am[0];
      const dot = box.querySelector('[style*="#81c995"], [style*="background: #81c995"]');
      if (dot) rs.in_stock = true;
    }

    // SHIPPING: Extract shipping info
    const sm = fullText.match(RE.shipping);
    if (sm) rs.shipping = $(sm[0]);

    // DOMAIN + BREADCRUMB: Extract from cite element
    const cite = box.querySelector('cite');
    if (cite) {
      const ct = $(cite.textContent);
      const dm = ct.match(RE.domainExtract);
      if (dm) {
        rs.domain = dm[2];
        const bc = ct.replace(/https?:\/\/[^\s]+\s*/, '');
        if (bc && bc !== dm[2]) rs.breadcrumb = $(bc);
      }
    }

    return { title, url, snippet, rich_snippet: rs };
  }

  // MAIN: Iterate all h3 elements and parse results
  for (const h3 of document.querySelectorAll('h3')) {
    try { const res = parse(h3); if (res) R.push(res); } catch (e) { /* skip malformed */ }
  }

  return R;
})();