"""Tests for SEO signal analysis module.

Tests cover:
- Page text signal extraction from various input formats
- Title alignment and rewrite risk calculation
- Content effort scoring with all components
- Topical centroid overlap detection
- SimHash64 stability and collision handling
- Anchor signal summary computation
- Empty/partial data handling without exceptions
"""

from __future__ import annotations

# MODULE_CONTRACT: tests/test_seo_signal_analysis
# Purpose: Verify leak-inspired SEO signal extraction and scoring.
# Rationale: Links signal-analysis tests to their GRACE module.
# Dependencies: pytest, utils.seo_signal_analysis.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-013
# MODULE_MAP: tests/test_seo_signal_analysis.py
# Public Functions: pytest test functions.
# Private Helpers: local fixtures and assertions in this file.
# Key Semantic Blocks: none.
# Critical Flows: construct page text inputs -> compute SEO signals -> assert stable result objects.
# Verification: verification-plan.xml#V-10-SEO-SIGNALS
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-013.

import pytest

from utils.seo_signal_analysis import (
    PageTextSignals,
    TitleAlignmentResult,
    ContentEffortScore,
    SimHashResult,
    extract_page_text_signals,
    compute_title_alignment,
    compute_content_effort_score,
    compute_topical_centroid_overlap,
    compute_simhash64,
    compute_anchor_signal_summary,
)
import re


# Purpose: Test page text signal extraction from various inputs.
class TestPageTextSignalsExtraction:

    # Purpose: Test extraction from SERP result format.
    def test_extract_from_serp_result(self):
        page_data = {
            "title": "Best SEO Tools 2024",
            "snippet": "Compare top SEO tools for keyword research and analysis.",
            "link": "https://example.com/seo-tools",
        }
        signals = extract_page_text_signals(page_data)

        assert signals.title == "Best SEO Tools 2024"
        assert signals.meta_description == "Compare top SEO tools for keyword research and analysis."
        assert signals.word_count > 0
        assert isinstance(signals.top_terms, list)

    # Purpose: Test extraction from crawl data format.
    def test_extract_from_crawl_data(self):
        page_data = {
            "url": "https://example.com/page",
            "title": "Complete Guide to Python",
            "meta_description": "Learn Python programming from basics to advanced.",
            "headings": {
                "h1": ["Python Programming Tutorial"],
                "h2": ["Variables", "Functions", "Classes"],
            },
            "intro_text": "This guide covers everything you need to know about Python.",
            "body": "<p>Python is a high-level programming language.</p><ul><li>Easy syntax</li><li>Powerful libraries</li></ul>",
        }
        signals = extract_page_text_signals(page_data)

        assert signals.title == "Complete Guide to Python"
        assert signals.h1 == "Python Programming Tutorial"
        assert "Python" in signals.intro_text
        assert signals.list_count >= 1

    # Purpose: Test extraction with minimal fields.
    def test_extract_from_minimal_data(self):
        page_data = {"title": "Test Page"}
        signals = extract_page_text_signals(page_data)

        assert signals.title == "Test Page"
        assert signals.meta_description == ""
        assert signals.h1 == ""

    # Purpose: Test extraction with None input.
    def test_extract_empty_input(self):
        signals = extract_page_text_signals(None)
        assert isinstance(signals, PageTextSignals)
        assert signals.title == ""
        assert signals.word_count == 0

    # Purpose: Test extraction with non-dict input.
    def test_extract_invalid_input(self):
        signals = extract_page_text_signals("not a dict")
        assert isinstance(signals, PageTextSignals)
        assert signals.title == ""

    # Purpose: Test accurate word count.
    def test_word_count_computation(self):
        page_data = {
            "title": "Keyword Research Guide",
            "body": "This is a test with multiple words. Some words are repeated for testing purposes.",
        }
        signals = extract_page_text_signals(page_data)
        assert signals.word_count > 5

    # Purpose: Test list and table element detection.
    def test_list_table_detection(self):
        page_data = {
            "body": """
            <ul><li>Item 1</li><li>Item 2</li></ul>
            <ol><li>First</li><li>Second</li></ol>
            <table><tr><td>Cell 1</td></tr></table>
            """
        }
        signals = extract_page_text_signals(page_data)
        assert signals.list_count >= 2
        assert signals.table_count >= 1

    # Purpose: Test citation marker detection.
    def test_citation_counting(self):
        page_data = {
            "body": "Research shows [1] that SEO is important. Studies [2][3] confirm this. See https://example.com/paper for details."
        }
        signals = extract_page_text_signals(page_data)
        assert signals.citation_count >= 3

    # Purpose: Test media element detection.
    def test_media_counting(self):
        page_data = {
            "body": '<img src="photo.jpg"><video src="video.mp4"></video><audio src="sound.mp3"></audio>'
        }
        signals = extract_page_text_signals(page_data)
        assert signals.media_count == 3

    # Purpose: Test answer-first structure detection.
    def test_answer_first_detection(self):
        page_data = {"intro_text": "SEO is the practice of optimizing websites for search engines."}
        signals = extract_page_text_signals(page_data)
        assert signals.has_answer_first is True

        page_data = {"intro_text": "<table><tr><td>Data here</td></tr></table>"}
        signals = extract_page_text_signals(page_data)
        assert signals.has_answer_first is True

    # Purpose: Test top terms are limited to 50.
    def test_top_terms_limit(self):
        page_data = {
            "body": " ".join([f"word{i} " * 10 for i in range(100)])
        }
        signals = extract_page_text_signals(page_data)
        assert len(signals.top_terms) <= 50


# Purpose: Test title alignment and rewrite risk calculation.
class TestTitleAlignment:

    # Purpose: Test perfect title-H1-intro alignment.
    def test_perfect_alignment(self):
        result = compute_title_alignment(
            title="Best SEO Tools 2024",
            h1="Best SEO Tools 2024",
            intro_text="Best SEO Tools 2024 for keyword research",
        )
        assert result.title_h1_overlap == 1.0
        assert result.title_intro_overlap > 0.5
        assert result.title_alignment_score > 0.5
        assert result.title_rewrite_risk < 0.5

    # Purpose: Test no alignment between title and content.
    def test_no_alignment(self):
        result = compute_title_alignment(
            title="Buy Cheap Products Online",
            h1="Healthy Recipes for Kids",
            intro_text="Cooking tips for beginners",
        )
        assert result.title_h1_overlap < 0.2
        assert result.title_intro_overlap < 0.2
        assert result.title_alignment_score < 0.2
        assert result.title_rewrite_risk > 0.5

    # Purpose: Test duplicate title signature detection.
    def test_duplicate_title_detection(self):
        all_titles = [
            "Best SEO Tools 2024",
            "Best SEO Tools 2024",
            "Best SEO Tools 2024",
            "Other Page Title",
        ]
        result = compute_title_alignment(
            title="Best SEO Tools 2024",
            all_titles=all_titles,
        )
        assert result.duplicate_title_risk > 0.0

    # Purpose: Test no duplicate risk with unique titles.
    def test_no_duplicate_in_unique_set(self):
        all_titles = ["Title One", "Title Two", "Title Three"]
        result = compute_title_alignment(
            title="Unique Title",
            all_titles=all_titles,
        )
        assert result.duplicate_title_risk == 0.0

    # Purpose: Test handling of empty title.
    def test_empty_title_handling(self):
        result = compute_title_alignment(title="")
        assert result.title_alignment_score == 0.0
        assert result.title_rewrite_risk == 1.0

    # Purpose: Test handling of None title.
    def test_none_title_handling(self):
        result = compute_title_alignment(title=None)
        assert result.title_alignment_score == 0.0
        assert result.title_rewrite_risk == 1.0

    # Purpose: Test rewrite risk formula components.
    def test_rewrite_risk_formula(self):
        result = compute_title_alignment(
            title="SEO Guide for Beginners",
            h1="SEO Guide for Beginners",
            intro_text="This SEO guide covers basics",
            all_titles=["SEO Guide for Beginners"],
        )
        assert result.title_rewrite_risk < 0.3

        result = compute_title_alignment(
            title="Buy Cheap Shoes",
            h1="Healthy Food Recipes",
            intro_text="Cooking at home is fun",
            all_titles=["Buy Cheap Shoes", "Buy Cheap Shoes", "Buy Cheap Shoes"],
        )
        assert result.title_rewrite_risk > 0.6

    # Purpose: Test alignment with Ukrainian text.
    def test_multilingual_alignment(self):
        result = compute_title_alignment(
            title="Купити iPhone 15 в Києві",
            h1="iPhone 15: ціна та характеристики",
            intro_text="Асортимент iPhone 15 в Києві: великий вибір",
        )
        assert result.title_alignment_score >= 0.0


# Purpose: Test content effort score computation.
class TestContentEffortScore:

    # Purpose: Test high effort content scoring.
    def test_high_effort_content(self):
        result = compute_content_effort_score(
            word_count=1200,
            list_count=5,
            table_count=3,
            citation_count=8,
            media_count=6,
            has_answer_first=True,
        )
        assert result.effort_score >= 0.7
        assert result.effort_level == "high"

    # Purpose: Test low effort content scoring.
    def test_low_effort_content(self):
        result = compute_content_effort_score(
            word_count=150,
            list_count=0,
            table_count=0,
            citation_count=0,
            media_count=0,
            has_answer_first=False,
        )
        assert result.effort_score < 0.4
        assert result.effort_level == "low"

    # Purpose: Test medium effort content.
    def test_medium_effort_content(self):
        result = compute_content_effort_score(
            word_count=600,
            list_count=2,
            table_count=1,
            citation_count=2,
            media_count=2,
            has_answer_first=False,
        )
        assert 0.4 <= result.effort_score < 0.7
        assert result.effort_level == "medium"

    # Purpose: Test length score calculation.
    def test_length_score_component(self):
        result = compute_content_effort_score(word_count=900)
        assert result.length_score == 1.0

        result = compute_content_effort_score(word_count=450)
        assert result.length_score == 0.5

    # Purpose: Test structure score calculation.
    def test_structure_score_component(self):
        result = compute_content_effort_score(list_count=2, table_count=2)
        assert result.structure_score == 1.0

        result = compute_content_effort_score(list_count=1, table_count=1)
        assert result.structure_score == 0.5

    # Purpose: Test citations score calculation.
    def test_citations_score_component(self):
        result = compute_content_effort_score(citation_count=6)
        assert result.citations_score == 1.0

    # Purpose: Test media score calculation.
    def test_media_score_component(self):
        result = compute_content_effort_score(media_count=4)
        assert result.media_score == 1.0

    # Purpose: Test answer-first score.
    def test_answer_first_component(self):
        result = compute_content_effort_score(has_answer_first=True)
        assert result.answer_score == 1.0

        result = compute_content_effort_score(has_answer_first=False)
        assert result.answer_score == 0.0

    # Purpose: Test weighted combination formula.
    def test_weighted_formula(self):
        result = compute_content_effort_score(
            word_count=900,
            list_count=4,
            citation_count=6,
            media_count=4,
            has_answer_first=True,
        )
        assert result.effort_score == 1.0

    # Purpose: Test with all zero inputs.
    def test_zero_input_handling(self):
        result = compute_content_effort_score()
        assert result.effort_score == 0.0
        assert result.effort_level == "low"


# Purpose: Test topical centroid overlap computation.
class TestTopicalOverlap:

    # Purpose: Test centroid term extraction.
    def test_topical_centroid_building(self):
        pages = [
            {"url": "https://example.com/1", "title": "SEO Tools Guide", "body": "Learn about SEO tools"},
            {"url": "https://example.com/2", "title": "Best SEO Software", "body": "Compare SEO software"},
            {"url": "https://example.com/3", "title": "SEO Tips 2024", "body": "Latest SEO tips"},
        ]
        result = compute_topical_centroid_overlap(pages)

        assert len(result.centroid_terms) > 0
        assert "seo" in {t["term"] for t in result.centroid_terms}

    # Purpose: Test off-topic page detection.
    def test_off_topic_detection(self):
        pages = [
            {"url": "https://example.com/seo-1", "title": "SEO Guide for beginners", "body": "SEO content tools keywords marketing"},
            {"url": "https://example.com/seo-2", "title": "SEO Tips and tricks", "body": "SEO advice optimization ranking"},
            {"url": "https://example.com/seo-3", "title": "SEO Tools analysis", "body": "SEO software reviews audit"},
            {"url": "https://example.com/cooking", "title": "Pizza Recipes Italian", "body": "Cooking baking dough cheese flour oven"},
        ]
        result = compute_topical_centroid_overlap(pages)

        assert result.mean_topical_overlap >= 0.0
        assert len(result.centroid_terms) > 0

    # Purpose: Test site focus score calculation.
    def test_site_focus_score(self):
        pages = [
            {"url": f"https://example.com/seo-{i}", "title": f"SEO Topic {i}", "body": "SEO content tools keyword"}
            for i in range(10)
        ]
        result = compute_topical_centroid_overlap(pages)
        assert result.site_focus_score >= 0.7

        pages = [
            {"url": f"https://example.com/page-{i}", "title": f"Topic {i}", "body": f"content about {i}"}
            for i in range(10)
        ]
        result = compute_topical_centroid_overlap(pages)
        assert 0.0 <= result.site_focus_score <= 1.0
        assert result.mean_topical_overlap >= 0.0

    # Purpose: Test with empty pages list.
    def test_empty_pages_list(self):
        result = compute_topical_centroid_overlap([])
        assert result.off_topic_ratio == 0.0
        assert result.mean_topical_overlap == 0.0
        assert result.site_focus_score == 0.0

    # Purpose: Test with None input.
    def test_none_pages_input(self):
        result = compute_topical_centroid_overlap(None)
        assert result.off_topic_ratio == 0.0
        assert len(result.centroid_terms) == 0

    # Purpose: Test centroid limited to 60 terms.
    def test_centroid_term_limit(self):
        pages = [
            {"url": f"https://example.com/{i}", "title": f"{'word ' * 10}", "body": f"{'term ' * 100}"}
            for i in range(50)
        ]
        result = compute_topical_centroid_overlap(pages)
        assert len(result.centroid_terms) <= 60

    # Purpose: Test off-topic URLs limited to 50.
    def test_off_topic_url_limit(self):
        pages = [
            {"url": f"https://example.com/off-{i}", "title": f"Off Topic {i}", "body": "random content"}
            for i in range(100)
        ]
        result = compute_topical_centroid_overlap(pages)
        assert len(result.off_topic_urls) <= 50


# Purpose: Test SimHash64 fingerprinting.
class TestSimHash64:

    # Purpose: Test SimHash computation from text.
    def test_simhash_from_text(self):
        result = compute_simhash64("This is a test document for SimHash fingerprinting.")
        assert result.simhash64_int != 0
        assert len(result.simhash64_hex) == 16
        assert result.term_count > 0

    # Purpose: Test SimHash from pre-extracted top terms.
    def test_simhash_from_top_terms(self):
        top_terms = [
            {"term": "seo", "count": 10},
            {"term": "tools", "count": 8},
            {"term": "guide", "count": 5},
        ]
        result = compute_simhash64(text="", top_terms=top_terms)
        assert result.simhash64_int != 0
        assert result.term_count == 3

    # Purpose: Test SimHash is deterministic.
    def test_simhash_stability(self):
        text = "Stable test content for fingerprinting"
        result1 = compute_simhash64(text)
        result2 = compute_simhash64(text)
        assert result1.simhash64_int == result2.simhash64_int
        assert result1.simhash64_hex == result2.simhash64_hex

    # Purpose: Test SimHash with empty input.
    def test_simhash_empty_input(self):
        result = compute_simhash64("")
        assert result.simhash64_int == 0
        assert result.simhash64_hex == "0000000000000000"

    # Purpose: Test SimHash collision handling (documented behavior).
    def test_simhash_collision_detection(self):
        text1 = "SEO tools are important for marketing"
        text2 = "SEO tools are important for marketing"
        text3 = "SEO tools are critical for marketing"

        result1 = compute_simhash64(text1)
        result2 = compute_simhash64(text2)
        result3 = compute_simhash64(text3)

        assert result1.simhash64_int == result2.simhash64_int

        assert result1.simhash64_int != result3.simhash64_int

    # Purpose: Test SimHash hex output format.
    def test_simhash_hex_format(self):
        result = compute_simhash64("Test content")
        assert re.match(r"^[0-9a-f]{16}$", result.simhash64_hex)

    # Purpose: Test SimHash with Unicode content.
    def test_simhash_with_unicode(self):
        result = compute_simhash64("Тест українською мовою для SEO")
        assert result.simhash64_int != 0

    # Purpose: Verify collision handling is documented in result.
    def test_simhash_collision_documentation(self):
        result = compute_simhash64("Test content")
        assert isinstance(result, SimHashResult)
        assert hasattr(result, 'simhash64_int')
        assert hasattr(result, 'term_count')


# Purpose: Test anchor text signal analysis.
class TestAnchorSignalSummary:

    # Purpose: Test basic anchor summary computation.
    def test_basic_anchor_summary(self):
        links = [
            {"anchor_text": "SEO Guide", "url": "https://example.com/seo-guide"},
            {"anchor_text": "SEO Tools", "url": "https://example.com/seo-tools"},
            {"anchor_text": "SEO Guide", "url": "https://example.com/seo-guide"},
        ]
        result = compute_anchor_signal_summary(links)

        assert result.total_links == 3
        assert result.unique_anchors == 2
        assert len(result.top_anchors) == 2

    # Purpose: Test anchor-target mismatch detection.
    def test_anchor_mismatch_detection(self):
        links = [
            {"anchor_text": "buy shoes", "url": "https://example.com/shoes"},
            {"anchor_text": "healthy recipes", "url": "https://example.com/shoes"},
            {"anchor_text": "healthy recipes", "url": "https://example.com/shoes"},
            {"anchor_text": "healthy recipes", "url": "https://example.com/shoes"},
        ]
        page_terms_map = {
            "https://example.com/shoes": {"shoes", "footwear", "sneakers"},
        }
        result = compute_anchor_signal_summary(links, page_terms_map)

        assert result.anchor_mismatch_ratio > 0.0

    # Purpose: Test overused commercial anchor detection.
    def test_commercial_anchor_detection(self):
        links = []
        for i in range(20):
            links.append({"anchor_text": "buy cheap products", "url": f"https://example.com/page-{i}"})
        links.append({"anchor_text": "click here", "url": "https://example.com/other"})

        result = compute_anchor_signal_summary(links)
        commercial_anchors = [a["anchor"] for a in result.overused_commercial_anchors]
        assert "buy cheap products" in commercial_anchors

    # Purpose: Test with empty links list.
    def test_empty_links_input(self):
        result = compute_anchor_signal_summary([])
        assert result.total_links == 0
        assert result.unique_anchors == 0

    # Purpose: Test with None input.
    def test_none_links_input(self):
        result = compute_anchor_signal_summary(None)
        assert result.total_links == 0

    # Purpose: Test top anchors limited to 20.
    def test_top_anchors_limit(self):
        links = [
            {"anchor_text": f"Anchor {i}", "url": f"https://example.com/{i}"}
            for i in range(50)
        ]
        result = compute_anchor_signal_summary(links)
        assert len(result.top_anchors) <= 20

    # Purpose: Test mismatch targets limited to 30.
    def test_mismatch_targets_limit(self):
        page_terms_map = {
            f"https://example.com/{i}": {f"term{i}"}
            for i in range(100)
        }
        links = [
            {"anchor_text": "wrong anchor", "url": f"https://example.com/{i}"}
            for i in range(100)
        ]
        result = compute_anchor_signal_summary(links, page_terms_map)
        assert len(result.mismatch_targets) <= 30

    # Purpose: Test anchor text normalization.
    def test_link_normalization(self):
        links = [
            {"anchor_text": "  SEO  Guide  ", "url": "https://example.com/1"},
            {"anchor_text": "SEO GUIDE", "url": "https://example.com/2"},
        ]
        result = compute_anchor_signal_summary(links)
        assert result.unique_anchors == 1


# Purpose: Test graceful handling of partial/empty data.
class TestPartialDataHandling:

    # Purpose: Test extraction with only some fields present.
    def test_extract_with_missing_fields(self):
        page_data = {"title": "Only Title"}
        signals = extract_page_text_signals(page_data)
        assert signals.title == "Only Title"
        assert signals.word_count == 2
        assert signals.list_count == 0

    # Purpose: Test title alignment without H1/intro.
    def test_title_alignment_with_missing_optional_params(self):
        result = compute_title_alignment(title="Test Title")
        assert result.title_h1_overlap == 0.0
        assert result.title_intro_overlap == 0.0
        assert result.title_alignment_score == 0.0

    # Purpose: Test content effort with all defaults.
    def test_content_effort_with_defaults(self):
        result = compute_content_effort_score()
        assert result.effort_score == 0.0
        assert result.effort_level == "low"

    # Purpose: Test topical overlap with pages lacking text.
    def test_topical_overlap_with_empty_pages(self):
        pages = [
            {"url": "https://example.com/1"},
            {"url": "https://example.com/2"},
        ]
        result = compute_topical_centroid_overlap(pages)
        assert result.mean_topical_overlap == 0.0

    # Purpose: Test anchor summary without page terms map.
    def test_anchor_summary_without_page_terms(self):
        links = [
            {"anchor_text": "SEO Guide", "url": "https://example.com/guide"}
        ]
        result = compute_anchor_signal_summary(links)
        assert result.anchor_mismatch_ratio == 0.0

    # Purpose: Test all functions handle None strings gracefully.
    def test_all_functions_with_none_string(self):
        result = compute_title_alignment(None)
        assert isinstance(result, TitleAlignmentResult)

        result = compute_content_effort_score(word_count=None)
        assert isinstance(result, ContentEffortScore)

        result = compute_simhash64(None)
        assert isinstance(result, SimHashResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
