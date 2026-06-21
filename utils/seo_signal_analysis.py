# MODULE_CONTRACT: utils/seo_signal_analysis
# Purpose: Deterministic SEO signal analysis ported from leak-audit formulas
# Rationale: Provides title alignment, content effort, topical overlap, SimHash64, and anchor signals for SERP/crawl analysis
# Dependencies: hashlib, math, re, typing, dataclasses, collections, functools (all stdlib)
# Exports: PageTextSignals, TitleAlignmentResult, ContentEffortScore, TopicalOverlapResult, SimHashResult, AnchorSignalSummary, extract_page_text_signals, compute_title_alignment, compute_content_effort_score, compute_topical_centroid_overlap, compute_simhash64, compute_anchor_signal_summary
# LINKS: PLAN 10-02 Task 3, requirements.xml#MATH-10-03
# MODULE_MAP: utils/seo_signal_analysis.py
# Public Functions: extract_page_text_signals, compute_title_alignment, compute_content_effort_score, compute_topical_centroid_overlap, compute_simhash64, compute_anchor_signal_summary
# Private Helpers: _tokenize_text, _compute_jaccard_similarity, _build_term_counter, _normalize_text, _detect_answer_first, _compute_list_table_counts
# Key Semantic Blocks: block_signal_extract_features, block_signal_title_alignment, block_signal_content_effort, block_signal_topical_overlap, block_signal_simhash_fingerprint, block_signal_anchor_analysis
# Critical Flows: Page/SERP objects -> text signals -> title/effort/topical/anchor scores
# Verification: python -m py_compile, python -m ruff check ., python -m pytest tests/test_seo_signal_analysis.py -q
# CHANGE_SUMMARY: Initial leak-inspired signal module; pure Python port without external dependencies

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


# block_signal_extract_features: Text signal extraction from page/SERP objects
# Semantic block: Normalizes and extracts text signals from various input sources


# FUNCTION_CONTRACT: _normalize_text
# Purpose: Normalize whitespace and strip HTML from text
# Input: value (str)
# Output: str
# Side Effects: (none)
# Business Rules: Collapses multiple spaces, strips leading/trailing whitespace
# Failure Modes: never raises; returns empty string for None input
# LINKS: PLAN 10-02 Task 3
def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


# FUNCTION_CONTRACT: _tokenize_text
# Purpose: Tokenize text into terms for signal analysis
# Input: text (str)
# Output: Set[str]
# Side Effects: (none)
# Business Rules: Extracts alphanumeric tokens (2+ chars) from EN/RU/UK text; lowercases
# Failure Modes: never raises; returns empty set for empty/None input
# LINKS: PLAN 10-02 Task 3
def _tokenize_text(text: Optional[str]) -> Set[str]:
    if not text:
        return set()
    tokens = re.findall(r"[a-zа-яёіїєґ0-9]{2,}", text.lower(), re.IGNORECASE)
    return set(tokens)


# FUNCTION_CONTRACT: _compute_jaccard_similarity
# Purpose: Compute Jaccard similarity between two term sets
# Input: set_a (Set[str]), set_b (Set[str])
# Output: float
# Side Effects: (none)
# Business Rules: J(A,B) = |A ∩ B| / |A ∪ B|; returns 0.0 for empty union
# Failure Modes: never raises
# LINKS: PLAN 10-02 Task 3
def _compute_jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


# FUNCTION_CONTRACT: _build_term_counter
# Purpose: Build weighted term frequency counter from text
# Input: text (str)
# Output: Counter
# Side Effects: (none)
# Business Rules: Tokenizes and counts term occurrences; returns empty Counter for empty input
# Failure Modes: never raises
# LINKS: PLAN 10-02 Task 3
def _build_term_counter(text: Optional[str]) -> Counter:
    if not text:
        return Counter()
    tokens = re.findall(r"[a-zа-яёіїєґ0-9]{2,}", text.lower(), re.IGNORECASE)
    return Counter(tokens)


# FUNCTION_CONTRACT: _detect_answer_first
# Purpose: Detect answer-first content structure
# Input: text (str)
# Output: bool
# Side Effects: (none)
# Business Rules: Checks for definition patterns or table/list presence in early content
# Failure Modes: never raises; returns False for empty/None input
# LINKS: PLAN 10-02 Task 3
def _detect_answer_first(text: Optional[str]) -> bool:
    if not text:
        return False
    # Check for definition patterns
    has_definition = bool(re.search(
        r"\b(is|are|это|означает|means|defined)\b",
        text.lower(),
        re.IGNORECASE
    ))
    # Check for structural elements
    has_structure = bool(re.search(r"<table|<ul|<ol|<li", text, re.IGNORECASE))
    return has_definition or has_structure


# FUNCTION_CONTRACT: _compute_list_table_counts
# Purpose: Count list and table elements in HTML/text
# Input: text (str)
# Output: Tuple[int, int]
# Side Effects: (none)
# Business Rules: Counts ul/ol/list elements and table elements via regex
# Failure Modes: never raises; returns (0, 0) for empty/None input
# LINKS: PLAN 10-02 Task 3
def _compute_list_table_counts(text: Optional[str]) -> Tuple[int, int]:
    if not text:
        return 0, 0
    list_count = len(re.findall(r"<(?:ul|ol|li|list)", text, re.IGNORECASE))
    table_count = len(re.findall(r"<table", text, re.IGNORECASE))
    return list_count, table_count


# FUNCTION_CONTRACT: _count_citations
# Purpose: Count citation-style patterns in text
# Input: text (str)
# Output: int
# Side Effects: (none)
# Business Rules: Counts [1], [a], https:// patterns as citation indicators
# Failure Modes: never raises; returns 0 for empty/None input
# LINKS: PLAN 10-02 Task 3
def _count_citations(text: Optional[str]) -> int:
    if not text:
        return 0
    # Count bracket citations
    bracket_citations = len(re.findall(r"\[(?:\d+|[a-z]{1,3})\]", text, re.IGNORECASE))
    # Count https URLs as citation proxies
    url_citations = len(re.findall(r"https?://[^\s]+", text, re.IGNORECASE))
    return bracket_citations + url_citations


# FUNCTION_CONTRACT: _count_media_elements
# Purpose: Count media elements in HTML/text
# Input: text (str)
# Output: int
# Side Effects: (none)
# Business Rules: Counts img, video, audio tags in HTML
# Failure Modes: never raises; returns 0 for empty/None input
# LINKS: PLAN 10-02 Task 3
def _count_media_elements(text: Optional[str]) -> int:
    if not text:
        return 0
    img_count = len(re.findall(r"<img", text, re.IGNORECASE))
    video_count = len(re.findall(r"<(?:video|iframe)", text, re.IGNORECASE))
    audio_count = len(re.findall(r"<audio", text, re.IGNORECASE))
    return img_count + video_count + audio_count


# FUNCTION_CONTRACT: extract_page_text_signals
# Purpose: Extract normalized text signals from page/SERP objects
# Input: page_data (Dict[str, Any])
# Output: PageTextSignals
# Side Effects: (none)
# Business Rules: Handles various input structures (SERP results, crawl data); returns empty/default values for missing fields
# Failure Modes: never raises; returns zero/default dataclass for malformed input
# LINKS: PLAN 10-02 Task 3
def extract_page_text_signals(page_data: Optional[Dict[str, Any]]) -> "PageTextSignals":
    if not page_data or not isinstance(page_data, dict):
        return PageTextSignals()

    # Extract title (multiple field names for compatibility)
    title = _normalize_text(
        page_data.get("title") or
        page_data.get("pageTitle") or
        page_data.get("ogTitle") or
        ""
    )

    # Extract meta description
    meta_description = _normalize_text(
        page_data.get("meta_description") or
        page_data.get("description") or
        page_data.get("ogDescription") or
        page_data.get("snippet") or  # SERP fallback
        ""
    )

    # Extract H1
    headings = page_data.get("headings", {})
    if isinstance(headings, dict):
        h1_list = headings.get("h1", [])
        if isinstance(h1_list, list) and h1_list:
            h1 = _normalize_text(h1_list[0])
        else:
            h1 = _normalize_text(headings.get("h1", ""))
    else:
        h1 = ""

    # Extract intro text
    intro_text = _normalize_text(
        page_data.get("intro_text") or
        page_data.get("text_excerpt") or
        page_data.get("answer_first", {}).get("top_excerpt") or
        ""
    )

    # Extract body text
    body = _normalize_text(
        page_data.get("body") or
        page_data.get("content") or
        page_data.get("text") or
        ""
    )

    # Build combined text for top terms
    combined_text = f"{title} {meta_description} {h1} {intro_text} {body}"

    # Compute top terms from combined text
    term_counter = _build_term_counter(combined_text)
    top_terms = [
        {"term": term, "count": count}
        for term, count in term_counter.most_common(50)
    ]

    # Compute word count
    word_count = len(term_counter)

    # Extract structured content counts
    list_count, table_count = _compute_list_table_counts(body)
    citation_count = _count_citations(body)
    media_count = _count_media_elements(body)

    # Detect answer-first structure
    has_answer_first = _detect_answer_first(intro_text or body[:500])

    return PageTextSignals(
        title=title,
        meta_description=meta_description,
        h1=h1,
        intro_text=intro_text[:320] if intro_text else "",  # Normalize length
        body=body[:1000] if body else "",  # Truncate for storage
        word_count=word_count,
        top_terms=top_terms,
        list_count=list_count,
        table_count=table_count,
        citation_count=citation_count,
        media_count=media_count,
        has_answer_first=has_answer_first,
    )


# block_signal_title_alignment: Title-to-content overlap analysis
# Semantic block: Computes title alignment with H1/intro and duplicate title detection


# FUNCTION_CONTRACT: compute_title_alignment
# Purpose: Compute title alignment and duplicate title risk
# Input: title (str), h1 (str), intro_text (str), all_titles (List[str])
# Output: TitleAlignmentResult
# Side Effects: (none)
# Business Rules: Computes token overlap ratios, duplicate title signature risk, and overall alignment score
# Failure Modes: never raises; returns zero-scored result for empty inputs
# LINKS: PLAN 10-02 Task 3
def compute_title_alignment(
    title: Optional[str],
    h1: Optional[str] = None,
    intro_text: Optional[str] = None,
    all_titles: Optional[List[str]] = None,
) -> "TitleAlignmentResult":
    """Compute title alignment with H1, intro, and duplicate detection.

    Calculates:
    1. Title-to-H1 token overlap ratio
    2. Title-to-intro token overlap ratio
    3. Duplicate title signature risk
    4. Overall title alignment score (0-1, higher is better)
    5. Title rewrite risk (0-1, lower is better)

    Args:
        title: Page title text
        h1: H1 heading text (optional)
        intro_text: Intro/above-fold text (optional)
        all_titles: List of all page titles for duplicate detection (optional)

    Returns:
        TitleAlignmentResult with overlap ratios and risk scores
    """
    if not title:
        return TitleAlignmentResult(
            title_h1_overlap=0.0,
            title_intro_overlap=0.0,
            duplicate_title_risk=0.0,
            title_alignment_score=0.0,
            title_rewrite_risk=1.0,  # Max risk when no title
        )

    title_tokens = _tokenize_text(title)
    if not title_tokens:
        return TitleAlignmentResult(
            title_h1_overlap=0.0,
            title_intro_overlap=0.0,
            duplicate_title_risk=0.0,
            title_alignment_score=0.0,
            title_rewrite_risk=1.0,
        )

    # Compute title-to-H1 overlap
    h1_tokens = _tokenize_text(h1 or "")
    title_h1_overlap = _compute_jaccard_similarity(title_tokens, h1_tokens)

    # Compute title-to-intro overlap
    intro_tokens = _tokenize_text(intro_text or "")
    title_intro_overlap = _compute_jaccard_similarity(title_tokens, intro_tokens)

    # Compute duplicate title signature
    duplicate_title_risk = 0.0
    if all_titles:
        title_signature = " ".join(sorted(title_tokens)[:10])
        signature_count = sum(
            1 for t in all_titles
            if " ".join(sorted(_tokenize_text(t))[:10]) == title_signature
        )
        # Avoid negative risk when signature_count is 1 (only the title itself)
        if signature_count > 1 and len(all_titles) > 0:
            duplicate_title_risk = min(1.0, (signature_count - 1) / len(all_titles))

    # Overall alignment score: average of H1 and intro overlap
    title_alignment_score = (title_h1_overlap + title_intro_overlap) / 2.0

    # Title rewrite risk: inverse of alignment with duplicate penalty
    # Formula from leak-audit: (0.45 * (1 - alignment)) + (0.25 * duplicate) + clickbait + no_answer
    # We use simplified version here without clickbait/answer detection
    title_rewrite_risk = min(
        1.0,
        (0.6 * (1.0 - title_alignment_score)) + (0.4 * duplicate_title_risk)
    )

    return TitleAlignmentResult(
        title_h1_overlap=round(title_h1_overlap, 3),
        title_intro_overlap=round(title_intro_overlap, 3),
        duplicate_title_risk=round(duplicate_title_risk, 3),
        title_alignment_score=round(title_alignment_score, 3),
        title_rewrite_risk=round(title_rewrite_risk, 3),
    )


# block_signal_content_effort: Content effort scoring
# Semantic block: Computes effort score based on length, structure, citations, media


# FUNCTION_CONTRACT: compute_content_effort_score
# Purpose: Compute content effort score based on multiple signals
# Input: word_count (int), list_count (int), table_count (int), citation_count (int), media_count (int), has_answer_first (bool)
# Output: ContentEffortScore
# Side Effects: (none)
# Business Rules: Weighted formula: 35% length + 20% structure + 20% citations + 15% media + 10% answer-first
# Failure Modes: never raises; returns zero-scored result for empty inputs
# LINKS: PLAN 10-02 Task 3
def compute_content_effort_score(
    word_count: Optional[int] = None,
    list_count: int = 0,
    table_count: int = 0,
    citation_count: int = 0,
    media_count: int = 0,
    has_answer_first: bool = False,
) -> "ContentEffortScore":
    """Compute content effort score.

    Formula (port from leak-audit analyze_leak_checks.py):
    - length_score = min(1.0, word_count / 900)
    - structure_score = min(1.0, (list_count + table_count) / 4)
    - citations_score = min(1.0, citation_count / 6)
    - media_score = min(1.0, media_count / 4)
    - answer_score = 1.0 if has_answer_first else 0.0

    Final effort = (0.35 * length) + (0.20 * structure) + (0.20 * citations) +
                  (0.15 * media) + (0.10 * answer)

    Args:
        word_count: Total word count in content (None treated as 0)
        list_count: Number of list elements
        table_count: Number of table elements
        citation_count: Number of citation markers
        media_count: Number of media elements (images, videos, audio)
        has_answer_first: Whether content has answer-first structure

    Returns:
        ContentEffortScore with component scores and overall effort (0-1)
    """
    # Handle None inputs
    wc = max(0, int(word_count or 0))

    # Component scores (clamped to 0-1)
    length_score = min(1.0, max(0.0, wc / 900.0))
    structure_score = min(1.0, max(0.0, (list_count + table_count) / 4.0))
    citations_score = min(1.0, max(0.0, citation_count / 6.0))
    media_score = min(1.0, max(0.0, media_count / 4.0))
    answer_score = 1.0 if has_answer_first else 0.0

    # Weighted combination
    effort_score = (
        (0.35 * length_score) +
        (0.20 * structure_score) +
        (0.20 * citations_score) +
        (0.15 * media_score) +
        (0.10 * answer_score)
    )

    # Classify effort level
    effort_level = "high" if effort_score >= 0.7 else "medium" if effort_score >= 0.4 else "low"

    return ContentEffortScore(
        length_score=round(length_score, 3),
        structure_score=round(structure_score, 3),
        citations_score=round(citations_score, 3),
        media_score=round(media_score, 3),
        answer_score=round(answer_score, 3),
        effort_score=round(effort_score, 3),
        effort_level=effort_level,
    )


# block_signal_topical_overlap: Topical centroid and overlap analysis
# Semantic block: Computes site-wide topical centroid and page overlap


# FUNCTION_CONTRACT: compute_topical_centroid_overlap
# Purpose: Compute site-wide topical centroid and page overlap ratios
# Input: pages (List[Dict[str, Any]])
# Output: TopicalOverlapResult
# Side Effects: (none)
# Business Rules: Builds centroid from top 60 terms across all pages; computes each page's overlap
# Failure Modes: never raises; returns empty result for empty/invalid input
# LINKS: PLAN 10-02 Task 3
def compute_topical_centroid_overlap(
    pages: Optional[List[Dict[str, Any]]]
) -> "TopicalOverlapResult":
    """Compute site-wide topical centroid and page overlap.

    Builds centroid from top 60 terms across all pages, then computes
    each page's overlap with the centroid to detect off-topic content.

    Args:
        pages: List of page dictionaries with text content

    Returns:
        TopicalOverlapResult with centroid terms, off-topic URLs, and ratios
    """
    if not pages or not isinstance(pages, list):
        return TopicalOverlapResult(
            centroid_terms=[],
            off_topic_urls=[],
            off_topic_ratio=0.0,
            mean_topical_overlap=0.0,
            site_focus_score=0.0,
        )

    # Build term counter across all pages
    global_counter: Counter = Counter()
    page_term_sets: List[Tuple[str, Set[str]]] = []

    for page in pages:
        if not isinstance(page, dict):
            continue

        # Extract text from page
        title = page.get("title", "")
        body = page.get("body", page.get("content", page.get("text", "")))
        url = page.get("url", page.get("link", ""))

        combined = f"{title} {body}"
        terms = _tokenize_text(combined)
        global_counter.update(terms)
        page_term_sets.append((url, terms))

    if not global_counter:
        return TopicalOverlapResult(
            centroid_terms=[],
            off_topic_urls=[],
            off_topic_ratio=0.0,
            mean_topical_overlap=0.0,
            site_focus_score=0.0,
        )

    # Extract centroid terms (top 60)
    centroid_terms = [term for term, _ in global_counter.most_common(60)]
    centroid_set = set(centroid_terms)

    # Compute per-page overlap
    off_topic_urls: List[str] = []
    topical_scores: List[float] = []

    for url, terms in page_term_sets:
        if not terms:
            continue
        overlap = len(terms & centroid_set) / len(terms)
        topical_scores.append(overlap)
        if overlap < 0.15:  # Threshold from leak-audit
            off_topic_urls.append(url)

    # Compute aggregate metrics
    page_count = len(topical_scores)
    off_topic_ratio = len(off_topic_urls) / page_count if page_count > 0 else 0.0
    mean_topical_overlap = sum(topical_scores) / page_count if page_count > 0 else 0.0
    site_focus_score = max(0.0, 1.0 - off_topic_ratio)

    return TopicalOverlapResult(
        centroid_terms=[{"term": t, "count": global_counter[t]} for t in centroid_terms],
        off_topic_urls=off_topic_urls[:50],  # Limit output
        off_topic_ratio=round(off_topic_ratio, 3),
        mean_topical_overlap=round(mean_topical_overlap, 3),
        site_focus_score=round(site_focus_score, 3),
    )


# block_signal_simhash_fingerprint: SimHash64 computation for near-duplicate detection
# Semantic block: Computes 64-bit SimHash fingerprints for content


# FUNCTION_CONTRACT: compute_simhash64
# Purpose: Compute 64-bit SimHash fingerprint for content
# Input: text (str), top_terms (Optional[List[Dict[str, Any]]])
# Output: SimHashResult
# Side Effects: (none)
# Business Rules: Uses MD5-based 64-bit hash with weighted term frequencies; returns hex string
# Failure Modes: never raises; returns zero hash for empty input
# LINKS: PLAN 10-02 Task 3
def compute_simhash64(
    text: Optional[str],
    top_terms: Optional[List[Dict[str, Any]]] = None,
) -> "SimHashResult":
    """Compute 64-bit SimHash fingerprint for content.

    SimHash algorithm:
    1. For each term, compute MD5 hash and extract first 64 bits
    2. For each bit position, add weight if bit is 1, subtract if 0
    3. Final fingerprint: set bit if accumulated value > 0

    Collision handling: When two documents have the same SimHash64,
    perform direct term comparison to confirm true duplicate.
    The 64-bit space provides ~1.8e19 possible values, making
    accidental collisions rare but possible.

    Args:
        text: Full text content (used if top_terms not provided)
        top_terms: Optional pre-extracted top terms with counts

    Returns:
        SimHashResult with hex fingerprint and hash integer
    """
    if not text and not top_terms:
        return SimHashResult(
            simhash64_hex="0000000000000000",
            simhash64_int=0,
            term_count=0,
        )

    # Build weighted terms
    weighted_terms: List[Tuple[str, float]] = []

    if top_terms:
        # Use provided top terms
        for item in top_terms:
            if isinstance(item, dict):
                term = item.get("term", "")
                count = item.get("count", 1)
                if term:
                    # Use log weight to reduce dominance of very frequent terms
                    weight = math.log1p(count)
                    weighted_terms.append((term, weight))
    else:
        # Extract from text
        term_counter = _build_term_counter(text)
        for term, count in term_counter.most_common(256):
            weight = math.log1p(count)
            weighted_terms.append((term, weight))

    if not weighted_terms:
        return SimHashResult(
            simhash64_hex="0000000000000000",
            simhash64_int=0,
            term_count=0,
        )

    # Compute SimHash
    vector = [0.0] * 64
    for term, weight in weighted_terms:
        # MD5 hash of term
        digest = hashlib.md5(term.encode("utf-8")).digest()
        # Extract first 8 bytes as 64-bit integer
        term_hash = int.from_bytes(digest[:8], "big")

        # Update vector
        for bit in range(64):
            if term_hash & (1 << bit):
                vector[bit] += weight
            else:
                vector[bit] -= weight

    # Build fingerprint
    fingerprint = 0
    for bit, value in enumerate(vector):
        if value > 0:
            fingerprint |= (1 << bit)

    return SimHashResult(
        simhash64_hex=f"{fingerprint:016x}",
        simhash64_int=fingerprint,
        term_count=len(weighted_terms),
    )


# block_signal_anchor_analysis: Anchor text signal analysis
# Semantic block: Analyzes internal link anchor consistency


# FUNCTION_CONTRACT: compute_anchor_signal_summary
# Purpose: Compute anchor text signal summary from link data
# Input: links (List[Dict[str, Any]]), page_terms_map (Optional[Dict[str, Set[str]]])
# Output: AnchorSignalSummary
# Side Effects: (none)
# Business Rules: Computes anchor distribution, mismatch ratio, and over-optimized commercial anchors
# Failure Modes: never raises; returns empty summary for invalid input
# LINKS: PLAN 10-02 Task 3
def compute_anchor_signal_summary(
    links: Optional[List[Dict[str, Any]]],
    page_terms_map: Optional[Dict[str, Set[str]]] = None,
) -> "AnchorSignalSummary":
    """Compute anchor text signal summary.

    Analyzes internal link anchor texts for:
    - Unique anchor distribution
    - Anchor-target term mismatch
    - Over-optimized commercial anchors

    Args:
        links: List of link dictionaries with 'anchor_text' and 'url' fields
        page_terms_map: Optional mapping from URL to target page term sets

    Returns:
        AnchorSignalSummary with anchor statistics and risk indicators
    """
    if not links or not isinstance(links, list):
        return AnchorSignalSummary(
            total_links=0,
            unique_anchors=0,
            top_anchors=[],
            mismatch_targets=[],
            anchor_mismatch_ratio=0.0,
            overused_commercial_anchors=[],
        )

    # Normalize and count anchors
    anchor_counter: Counter = Counter()
    normalized_links: List[Tuple[str, str]] = []

    for link in links:
        if not isinstance(link, dict):
            continue
        anchor = _normalize_text(link.get("anchor_text", link.get("text", "")))
        target = _normalize_text(link.get("url", link.get("target", "")))
        if anchor and target:
            anchor_counter[anchor.lower()] += 1
            normalized_links.append((anchor.lower(), target))

    total_links = len(normalized_links)
    unique_anchors = len(anchor_counter)

    # Top anchors
    top_anchors = [
        {"anchor": anchor, "count": count}
        for anchor, count in anchor_counter.most_common(20)
    ]

    # Anchor-target mismatch
    mismatch_targets: Counter = Counter()
    commercial_re = re.compile(
        r"(buy|price|cheap|order|service|quote|demo|trial|contact|"
        r"купить|цена|заказать|услуга|замовити|ціна)",
        re.IGNORECASE
    )

    for anchor, target in normalized_links:
        # Extract anchor terms
        anchor_terms = set(re.findall(r"[a-zа-я0-9]{2,}", anchor))

        if not anchor_terms:
            continue

        # Get target terms
        target_terms = set()
        if page_terms_map and target in page_terms_map:
            target_terms = page_terms_map[target] or set()

        # Compute overlap (always compute, even if target_terms is empty)
        overlap = len(anchor_terms & target_terms) / len(anchor_terms) if anchor_terms else 0.0
        if overlap < 0.2:  # Threshold from leak-audit
            mismatch_targets[target] += 1

    mismatch_urls = [url for url, count in mismatch_targets.items() if count >= 3]
    anchor_mismatch_ratio = len(mismatch_urls) / len(page_terms_map) if page_terms_map else 0.0

    # Overused commercial anchors
    total_internal_links = total_links
    overused_commercial = [
        {"anchor": anchor, "count": count}
        for anchor, count in anchor_counter.items()
        if commercial_re.search(anchor) and
        count >= max(8, int(0.08 * max(1, total_internal_links)))
    ]

    return AnchorSignalSummary(
        total_links=total_links,
        unique_anchors=unique_anchors,
        top_anchors=top_anchors,
        mismatch_targets=mismatch_urls[:30],
        anchor_mismatch_ratio=round(anchor_mismatch_ratio, 3),
        overused_commercial_anchors=overused_commercial[:10],
    )


# Data model classes for signal analysis


@dataclass
# Purpose: Extracted text signals from a page.
# Attributes:
# title: Normalized page title
# meta_description: Normalized meta description
# h1: Normalized H1 heading
# intro_text: First ~320 chars of above-fold content
# body: Truncated body text (first 1000 chars)
# word_count: Total word count
# top_terms: Top 50 terms with counts
# list_count: Number of list elements
# table_count: Number of table elements
# citation_count: Number of citation markers
# media_count: Number of media elements
# has_answer_first: Whether content has answer-first structure
class PageTextSignals:
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    intro_text: str = ""
    body: str = ""
    word_count: int = 0
    top_terms: List[Dict[str, Any]] = None
    list_count: int = 0
    table_count: int = 0
    citation_count: int = 0
    media_count: int = 0
    has_answer_first: bool = False

    # Purpose:   post init   implementation
    def __post_init__(self):
        if self.top_terms is None:
            self.top_terms = []


@dataclass
# Purpose: Title alignment analysis result.
# Attributes:
# title_h1_overlap: Jaccard similarity between title and H1 (0-1)
# title_intro_overlap: Jaccard similarity between title and intro (0-1)
# duplicate_title_risk: Risk of duplicate title signature (0-1)
# title_alignment_score: Overall alignment score (0-1, higher is better)
# title_rewrite_risk: Risk of title being rewritten (0-1, lower is better)
class TitleAlignmentResult:
    title_h1_overlap: float = 0.0
    title_intro_overlap: float = 0.0
    duplicate_title_risk: float = 0.0
    title_alignment_score: float = 0.0
    title_rewrite_risk: float = 0.0


@dataclass
# Purpose: Content effort analysis result.
# Attributes:
# length_score: Length contribution score (0-1)
# structure_score: List/table contribution score (0-1)
# citations_score: Citation contribution score (0-1)
# media_score: Media contribution score (0-1)
# answer_score: Answer-first contribution score (0-1)
# effort_score: Overall weighted effort score (0-1)
# effort_level: Classified level (low/medium/high)
class ContentEffortScore:
    length_score: float = 0.0
    structure_score: float = 0.0
    citations_score: float = 0.0
    media_score: float = 0.0
    answer_score: float = 0.0
    effort_score: float = 0.0
    effort_level: str = "low"


@dataclass
# Purpose: Topical centroid overlap analysis result.
# Attributes:
# centroid_terms: Top 60 terms defining site's topical centroid
# off_topic_urls: List of URLs with low centroid overlap
# off_topic_ratio: Ratio of off-topic pages (0-1)
# mean_topical_overlap: Average overlap across all pages (0-1)
# site_focus_score: Site focus score (0-1, higher is better)
class TopicalOverlapResult:
    centroid_terms: List[Dict[str, Any]] = None
    off_topic_urls: List[str] = None
    off_topic_ratio: float = 0.0
    mean_topical_overlap: float = 0.0
    site_focus_score: float = 0.0

    # Purpose:   post init   implementation
    def __post_init__(self):
        if self.centroid_terms is None:
            self.centroid_terms = []
        if self.off_topic_urls is None:
            self.off_topic_urls = []


@dataclass
# Purpose: SimHash64 fingerprint result.
# Attributes:
# simhash64_hex: 64-bit hash as 16-character hex string
# simhash64_int: 64-bit hash as integer
# term_count: Number of terms used in fingerprint
# Collision handling:
# When simhash64_int matches between documents, compare top_terms
# directly to confirm true duplicate. The 64-bit space has
# 1.84e19 possible values, making accidental collisions rare.
class SimHashResult:
    simhash64_hex: str = "0000000000000000"
    simhash64_int: int = 0
    term_count: int = 0


@dataclass
# Purpose: Anchor text signal summary.
# Attributes:
# total_links: Total internal links analyzed
# unique_anchors: Number of unique anchor texts
# top_anchors: Top 20 anchors with counts
# mismatch_targets: URLs with anchor-target mismatch
# anchor_mismatch_ratio: Ratio of mismatched targets (0-1)
# overused_commercial_anchors: List of overused commercial anchors
class AnchorSignalSummary:
    total_links: int = 0
    unique_anchors: int = 0
    top_anchors: List[Dict[str, Any]] = None
    mismatch_targets: List[str] = None
    anchor_mismatch_ratio: float = 0.0
    overused_commercial_anchors: List[Dict[str, Any]] = None

    # Purpose:   post init   implementation
    def __post_init__(self):
        if self.top_anchors is None:
            self.top_anchors = []
        if self.mismatch_targets is None:
            self.mismatch_targets = []
        if self.overused_commercial_anchors is None:
            self.overused_commercial_anchors = []