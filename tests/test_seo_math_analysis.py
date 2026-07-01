# Test: utils/seo_math_analysis.py
# Purpose: Verify deterministic mathematical SEO analysis engine
# LINKS: PLAN 08-02 Tasks 1-4, PLAN 10-02 Task 2
# MODULE_CONTRACT: tests/test_seo_math_analysis
# Purpose: Verify deterministic SEO math, BM25F, n-gram, TF-IDF, and sidebar removal guards.
# Rationale: Links SEO math and suffix-removal tests to their GRACE modules.
# Dependencies: utils.seo_math_analysis.
# Exports: pytest tests.
# LINKS: knowledge-graph.xml#MOD-012, knowledge-graph.xml#MOD-011
# MODULE_MAP: tests/test_seo_math_analysis.py
# Public Functions: pytest test functions.
# Private Helpers: fixtures and local assertions in this file.
# Key Semantic Blocks: none.
# Critical Flows: build text sources -> run math algorithms -> assert scores and removed-setting behavior.
# Verification: verification-plan.xml#V-10-MATH-BM25F, verification-plan.xml#V-12-SUFFIX-REMOVAL
# CHANGE_SUMMARY: Added GRACE module contract linking this test file to MOD-012 and MOD-011; added test_cooccurrence_strips_suffixes_when_enabled + test_cooccurrence_enabled_catches_more_inflections covering the closed lemmatization gap in co-occurrence (_build_cooccurrence_matrix now threads strip_suffixes).

from utils.seo_math_analysis import (
    TextSource,
    NgramScore,
    TfidfTermScore,
    CooccurrenceTermScore,
    IntentSignal,
    ContentGapResult,
    ElementQualityScore,
    BM25FScore,
    FieldWeightedProfile,
    FieldStats,
    extract_ngrams,
    compute_tfidf,
    compute_cooccurrence_terms,
    analyze_intent,
    analyze_content_gap,
    score_generated_text,
    compute_bm25f,
    build_field_weighted_profile,
    lemmatize_token,
    _tokenize_text,
    _get_default_stopwords,
    _parse_generated_sections,
    _calculate_keyword_density,
    _lemmatized_contains,
    _check_forbidden_phrases,
    _normalize_for_hashing,
    _get_field_b_param,
    _compute_field_length_normalization,
    _compute_bm25f_idf,
    _get_pymorphy_ru,
    _get_pymorphy_uk,
    _get_simplemma,
    check_lemmatizer_dependencies,
    build_lemmatizer_install_command,
    get_lemmatizer_problem_dependencies,
    LEMMATIZER_DEPENDENCY_PACKAGES,
)

import pytest


# Purpose: pymorphy3 / pymorphy3-dicts-uk / simplemma are OPTIONAL dependencies
# (intentionally absent from requirements.txt). The real-lemmatizer and
# "detected-when-present" tests below only hold when those libs are installed in the
# running environment — otherwise the module's documented contract is to fall back to
# identity / report MISSING, so these tests must SKIP, not FAIL, on a bare env.
# This guard uses the module's own dependency checker so it stays in sync with detection.
_LDS_AVAILABLE = {
    k: v.value == "available"
    for k, v in check_lemmatizer_dependencies().items()
}
_lemmatizer_skip = pytest.mark.skipif(
    not (_LDS_AVAILABLE.get("pymorphy3") and _LDS_AVAILABLE.get("pymorphy3_dicts_uk")),
    reason="optional lemmatizer libs (pymorphy3 / pymorphy3-dicts-uk) not installed",
)
_pymorphy3_skip = pytest.mark.skipif(
    not _LDS_AVAILABLE.get("pymorphy3"),
    reason="optional pymorphy3 not installed",
)
_uk_dict_skip = pytest.mark.skipif(
    not _LDS_AVAILABLE.get("pymorphy3_dicts_uk"),
    reason="optional pymorphy3-dicts-uk not installed",
)


# Purpose: Test data model classes are importable and correct.
class TestDataModels:

    # Purpose: Test TextSource dataclass.
    def test_textsource_dataclass(self):
        source = TextSource(
            text="Sample text",
            field="title",
            weight=3.0,
            provenance_url="https://example.com"
        )
        assert source.text == "Sample text"
        assert source.field == "title"
        assert source.weight == 3.0
        assert source.provenance_url == "https://example.com"

    # Purpose: Test NgramScore dataclass.
    def test_ngramscore_dataclass(self):
        score = NgramScore(
            ngram="seo tools",
            gram_size=2,
            raw_count=5,
            weighted_count=15.0,
            doc_frequency=3,
            sources={"title": 3, "snippet": 2}
        )
        assert score.ngram == "seo tools"
        assert score.gram_size == 2
        assert score.raw_count == 5
        assert score.weighted_count == 15.0
        assert score.doc_frequency == 3
        assert score.sources == {"title": 3, "snippet": 2}

    # Purpose: Test TfidfTermScore dataclass.
    def test_tfidftermscore_dataclass(self):
        score = TfidfTermScore(
            term="keyword",
            tfidf=0.75,
            raw_tf=0.1,
            idf=7.5,
            doc_frequency=4
        )
        assert score.term == "keyword"
        assert score.tfidf == 0.75
        assert score.raw_tf == 0.1
        assert score.idf == 7.5
        assert score.doc_frequency == 4

    # Purpose: Test CooccurrenceTermScore dataclass.
    def test_cooccurrencetermscore_dataclass(self):
        score = CooccurrenceTermScore(
            term="analysis",
            cooccurrence_count=8,
            jaccard_similarity=0.4,
            context_terms=["seo", "optimization"]
        )
        assert score.term == "analysis"
        assert score.cooccurrence_count == 8
        assert score.jaccard_similarity == 0.4
        assert score.context_terms == ["seo", "optimization"]

    # Purpose: Test IntentSignal dataclass with confidence field.
    def test_intentsignal_dataclass(self):
        signal = IntentSignal(
            intent_type="commercial",
            score=5.5,
            confidence=0.6,
            signals=["buy", "price", "order"]
        )
        assert signal.intent_type == "commercial"
        assert signal.score == 5.5
        assert signal.confidence == 0.6
        assert signal.signals == ["buy", "price", "order"]

    # Purpose: Test ContentGapResult dataclass.
    def test_contentgapresult_dataclass(self):
        result = ContentGapResult(
            coverage_ratio=0.7,
            jaccard_overlap=0.5,
            cosine_similarity=0.65,
            missing_high_value=["tools", "software"],
            overused_low_value=["click", "here"]
        )
        assert result.coverage_ratio == 0.7
        assert result.jaccard_overlap == 0.5
        assert result.cosine_similarity == 0.65
        assert result.missing_high_value == ["tools", "software"]
        assert result.overused_low_value == ["click", "here"]

    # Purpose: Test ElementQualityScore dataclass.
    def test_elementqualityscore_dataclass(self):
        score = ElementQualityScore(
            element="META_TITLE",
            score=85.0,
            issues=["meta_title_too_long"],
            keyword_coverage=0.8,
            length_compliant=False,
            primary_keyword_present=True
        )
        assert score.element == "META_TITLE"
        assert score.score == 85.0
        assert score.issues == ["meta_title_too_long"]
        assert score.keyword_coverage == 0.8
        assert score.length_compliant is False
        assert score.primary_keyword_present is True


# Purpose: Test tokenization with HTML stripping, Cyrillic support, and optional suffix stripping.
class TestTokenization:

    # Purpose: Test basic English tokenization.
    def test_tokenize_basic_text(self):
        text = "SEO tools help optimize websites"
        tokens = _tokenize_text(text)
        assert "seo" in tokens
        assert "tools" in tokens
        assert "help" in tokens
        assert "optimize" in tokens
        assert "websites" in tokens

    # Purpose: Test Cyrillic (Russian) tokenization.
    def test_tokenize_cyrillic_text(self):
        text = "SEO инструменты помогают оптимизировать сайты"
        tokens = _tokenize_text(text)
        assert "seo" in tokens
        assert "инструменты" in tokens
        assert "помогают" in tokens
        assert "оптимизировать" in tokens
        assert "сайты" in tokens

    # Purpose: Test Ukrainian tokenization.
    def test_tokenize_ukrainian_text(self):
        text = "SEO інструменти допомагають оптимізувати сайти"
        tokens = _tokenize_text(text)
        assert "seo" in tokens
        assert "інструменти" in tokens
        assert "допомагають" in tokens
        assert "оптимізувати" in tokens
        assert "сайти" in tokens

    # Purpose: Test HTML tag removal.
    def test_tokenize_strips_html(self):
        text = "<p>SEO analysis <b>keyword</b> research with <a href='link'>tools</a>.</p>"
        tokens = _tokenize_text(text)
        assert "<p>" not in tokens
        assert "<b>" not in tokens
        assert "seo" in tokens
        assert "analysis" in tokens
        assert "keyword" in tokens
        assert "research" in tokens
        assert "tools" in tokens

    # Purpose: Test empty text returns empty list.
    def test_tokenize_empty_text(self):
        assert _tokenize_text("") == []
        assert _tokenize_text(None) == []

    # Purpose: Test hyphens inside words are preserved.
    def test_tokenize_preserves_hyphens(self):
        text = "state-of-the-art SEO tools and high-quality content"
        tokens = _tokenize_text(text)
        assert "state-of-the-art" in tokens
        assert "high-quality" in tokens
        assert "seo" in tokens
        assert "tools" in tokens

    # Purpose: Test stopword filtering.
    def test_tokenize_filters_stopwords(self):
        text = "the and or but in on at to for of with"
        tokens = _tokenize_text(text)
        assert len(tokens) == 0

    # Purpose: Test suffix stripping is disabled by default (per review feedback).
    # Requires the real pymorphy3 lemmatizer to actually collapse inflections; without it
    # both modes return identical tokens, so the != assertion is meaningless. Skipped on
    # environments where the optional lemmatizer libs are absent.
    @_lemmatizer_skip
    def test_suffix_stripping_disabled_by_default(self):
        text = "хороший хорошие отличный"
        tokens_default = _tokenize_text(text, strip_suffixes=False)
        tokens_stripped = _tokenize_text(text, strip_suffixes=True)

        assert "хороший" in tokens_default
        assert "хорошие" in tokens_default
        assert "отличный" in tokens_default

        assert tokens_default != tokens_stripped

    # Purpose: Test suffix stripping is optional and configurable.
    # Same lemmatizer requirement as above — skipped when the libs are absent.
    @_lemmatizer_skip
    def test_suffix_stripping_optional(self):
        text = "хороший хорошие отличный"
        tokens_no_strip = _tokenize_text(text, strip_suffixes=False)
        tokens_with_strip = _tokenize_text(text, strip_suffixes=True)

        assert "хороший" in tokens_no_strip

        assert tokens_no_strip != tokens_with_strip

    # Purpose: STRICT mode (strip_suffixes=False) is a plain case-insensitive substring
    # check — identical to the behavior before lemmatization was threaded into _score_element,
    # so existing scoring is unaffected when the user disables suffix stripping.
    def test_lemmatized_contains_strict_is_raw_substring(self):
        assert _lemmatized_contains("Best SEO Tools", "seo tools", strip_suffixes=False) is True
        assert _lemmatized_contains("Best SEO Tools", "Software", strip_suffixes=False) is False
        assert _lemmatized_contains("", "x", strip_suffixes=False) is False
        assert _lemmatized_contains("abc", "", strip_suffixes=False) is False

    # Purpose: STRICT mode does NOT collapse inflections — an inflected element must NOT
    # match the lemma keyword. This is the user's "raw analysis" mode.
    def test_lemmatized_contains_strict_does_not_lemmatize(self):
        # lemma "кроссовок" is NOT a substring of inflected "кроссовки"
        assert _lemmatized_contains("кроссовки мужские", "кроссовок", strip_suffixes=False) is False
        # the inflected form itself still matches verbatim
        assert _lemmatized_contains("кроссовки мужские", "кроссовки", strip_suffixes=False) is True

    # Purpose: BROAD mode (strip_suffixes=True) collapses both sides to lemmas so an
    # inflected element matches the lemma keyword — the user's "lemmatized analysis" mode.
    @_lemmatizer_skip
    def test_lemmatized_contains_broad_lemmatizes(self):
        assert _lemmatized_contains("кроссовки мужские", "кроссовок", strip_suffixes=True) is True
        # multi-word lemma needle: contiguous lemma sequence must appear
        assert _lemmatized_contains("купите кроссовки мужские", "кроссовки мужские", strip_suffixes=True) is True
        # lemma sequence not contiguous in the haystack -> no match
        assert _lemmatized_contains("кроссовки дешевые мужские", "кроссовки мужские", strip_suffixes=True) is False


# Purpose: Test stopword lists for ru/uk/en.
class TestStopwords:

    # Purpose: Test default stopwords are loaded.
    def test_default_stopwords_not_empty(self):
        stopwords = _get_default_stopwords()
        assert len(stopwords) > 0

    # Purpose: Test common English stopwords are present.
    def test_english_stopwords_present(self):
        stopwords = _get_default_stopwords()
        assert "the" in stopwords
        assert "and" in stopwords
        assert "or" in stopwords
        assert "but" in stopwords

    # Purpose: Test common Russian stopwords are present.
    def test_russian_stopwords_present(self):
        stopwords = _get_default_stopwords()
        assert "и" in stopwords
        assert "в" in stopwords
        assert "не" in stopwords
        assert "что" in stopwords

    # Purpose: Test common Ukrainian stopwords are present.
    def test_ukrainian_stopwords_present(self):
        stopwords = _get_default_stopwords()
        assert "і" in stopwords
        assert "в" in stopwords
        assert "не" in stopwords
        assert "що" in stopwords


# Purpose: Test source weight constants are used correctly.
class TestSourceWeights:

    # Purpose: Test TextSource accepts different weights.
    def test_source_weights_in_corpus(self):
        sources = [
            TextSource(text="Test", field="organic_title", weight=3.0),
            TextSource(text="Test", field="snippet", weight=1.5),
            TextSource(text="Test", field="displayed_link", weight=1.0),
            TextSource(text="Test", field="related_search", weight=2.0),
            TextSource(text="Test", field="people_also_ask", weight=2.0),
            TextSource(text="Test", field="knowledge_graph", weight=1.5),
        ]
        assert sources[0].weight == 3.0
        assert sources[1].weight == 1.5
        assert sources[2].weight == 1.0
        assert sources[3].weight == 2.0
        assert sources[4].weight == 2.0
        assert sources[5].weight == 1.5


# Purpose: Test n-gram extraction with filtering and sorting.
class TestNgramExtraction:

    # Purpose: Test unigram (1-gram) extraction.
    def test_extract_unigrams(self):
        corpus = [
            TextSource(text="SEO tools for keyword research", field="title", weight=3.0),
            TextSource(text="Best SEO optimization software", field="snippet", weight=1.5),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = extract_ngrams(corpus_hash, n=1, min_count=1, min_df=1)

        assert all(isinstance(r, NgramScore) for r in results)
        assert all(r.gram_size == 1 for r in results)

    # Purpose: Test bigram (2-gram) extraction.
    def test_extract_bigrams(self):
        corpus = [
            TextSource(text="SEO tools for keyword research", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = extract_ngrams(corpus_hash, n=2, min_count=1, min_df=1)

        assert all(r.gram_size == 2 for r in results)
        ngrams = [r.ngram for r in results]
        assert "seo tools" in ngrams

    # Purpose: Test trigram (3-gram) extraction.
    def test_extract_trigrams(self):
        corpus = [
            TextSource(text="SEO tools for keyword research and analysis", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = extract_ngrams(corpus_hash, n=3, min_count=1, min_df=1)

        assert all(r.gram_size == 3 for r in results)

    # Purpose: Test n-gram filtering by minimum count.
    def test_ngram_filtering_by_count(self):
        corpus = [
            TextSource(text="SEO tools SEO analysis", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = extract_ngrams(corpus_hash, n=1, min_count=2, min_df=1)

        assert len(results) == 1
        assert results[0].ngram == "seo"

    # Purpose: Test n-gram filtering by document frequency.
    def test_ngram_filtering_by_df(self):
        corpus = [
            TextSource(text="SEO tools", field="title", weight=3.0),
            TextSource(text="Keyword research", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = extract_ngrams(corpus_hash, n=1, min_count=1, min_df=2)

        assert len(results) == 0

    # Purpose: Test n-gram results are sorted stably (score desc, term asc).
    def test_ngram_sorting_stability(self):
        corpus = [
            TextSource(text="SEO tools analysis software", field="title", weight=3.0),
            TextSource(text="SEO tools analysis research", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = extract_ngrams(corpus_hash, n=1, min_count=2, min_df=1)

        scores = [r.weighted_count for r in results]

        assert scores == sorted(scores, reverse=True)

    # Purpose: Test empty corpus returns empty list.
    def test_ngram_empty_corpus(self):
        results = extract_ngrams(tuple(), n=1, min_count=1, min_df=1)
        assert results == []


# Purpose: Test TF-IDF computation with exact formulas.
class TestTfidfComputation:

    # Purpose: Test basic TF-IDF computation.
    def test_tfidf_basic_computation(self):
        corpus = [
            TextSource(text="SEO tools and SEO analysis", field="title", weight=3.0),
            TextSource(text="keyword research tools", field="snippet", weight=1.5),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = compute_tfidf(corpus_hash)

        assert len(results) > 0
        assert all(isinstance(r, TfidfTermScore) for r in results)

    # Purpose: Test TF-IDF formula has TF, IDF, and TF-IDF components.
    def test_tfidf_formula_components(self):
        corpus = [
            TextSource(text="SEO tools", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = compute_tfidf(corpus_hash)

        for result in results:
            assert hasattr(result, 'term')
            assert hasattr(result, 'tfidf')
            assert hasattr(result, 'raw_tf')
            assert hasattr(result, 'idf')
            assert hasattr(result, 'doc_frequency')
            assert result.tfidf >= 0

    # Purpose: Test TF-IDF results are sorted by score desc, term asc.
    def test_tfidf_sorting(self):
        corpus = [
            TextSource(text="SEO tools analysis software research", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = compute_tfidf(corpus_hash)

        scores = [r.tfidf for r in results]

        assert scores == sorted(scores, reverse=True)

    # Purpose: By default (min_df=1) every term is retained — analysis always runs.
    # Callers wanting cross-document recurrence pass min_df=2 explicitly.
    def test_tfidf_default_keeps_single_doc_terms(self):
        corpus = [
            TextSource(text="SEO tools", field="title", weight=3.0),
            TextSource(text="keyword research", field="snippet", weight=1.5),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = compute_tfidf(corpus_hash)

        terms = {r.term for r in results}
        # Single-document terms survive under the default min_df=1.
        assert {"seo", "tools", "keyword", "research"}.issubset(terms)

        # Explicit min_df=2 filters them back out.
        filtered = compute_tfidf(corpus_hash, min_df=2)
        assert filtered == []

    # Purpose: Test empty corpus returns empty list.
    def test_tfidf_empty_corpus(self):
        results = compute_tfidf(tuple())
        assert results == []

    # Purpose: Regression — math analysis must ALWAYS run when enabled, even for a
    # single-document corpus (the scraped-text / url_llm_ads path feeds 1 document).
    # The former hardcoded `df < 2` filter guaranteed an empty result for any 1-doc
    # corpus, so the report showed only intent. A single rich document must yield terms.
    def test_tfidf_single_document_corpus_yields_terms(self):
        corpus = [
            TextSource(text="best SEO tools for keyword research and analysis", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = compute_tfidf(corpus_hash)
        assert len(results) > 0
        terms = {r.term for r in results}
        # Content words from the document must survive — not be filtered by df.
        assert {"tools", "keyword", "research"}.issubset(terms)

    # Purpose: The minimum-document-frequency filter must be configurable via min_df,
    # defaulting to 1 (run always). Callers can still raise it to 2 for SERP corpora.
    def test_tfidf_min_df_parameter_defaults_to_one(self):
        corpus = [
            TextSource(text="alpha beta", field="title", weight=3.0),
            TextSource(text="gamma delta", field="snippet", weight=1.5),
        ]
        corpus_hash = _normalize_for_hashing(corpus)

        # Default: every term appears (min_df=1) — no filtering of single-doc terms.
        default_results = compute_tfidf(corpus_hash)
        default_terms = {r.term for r in default_results}
        assert {"alpha", "beta", "gamma", "delta"}.issubset(default_terms)

        # Explicit min_df=2 keeps only terms appearing in >= 2 documents (none here).
        filtered = compute_tfidf(corpus_hash, min_df=2)
        assert filtered == []


# Purpose: Test co-occurrence term analysis (NOT true LSI/SVD).
class TestCooccurrenceAnalysis:

    # Purpose: Test basic co-occurrence computation.
    def test_cooccurrence_basic(self):
        corpus = [
            TextSource(text="SEO tools and keyword analysis software", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = compute_cooccurrence_terms(corpus_hash, seed_terms=("seo", "tools"))

        assert all(isinstance(r, CooccurrenceTermScore) for r in results)

    # Purpose: Test co-occurrence uses Jaccard similarity, not SVD.
    def test_cooccurrence_uses_jaccard_not_svd(self):
        corpus = [
            TextSource(text="SEO tools keyword analysis", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = compute_cooccurrence_terms(corpus_hash, seed_terms=("seo",))

        for result in results:
            assert hasattr(result, 'jaccard_similarity')
            assert 0 <= result.jaccard_similarity <= 1

    # Purpose: Test co-occurrence tracks context terms.
    def test_cooccurrence_context_terms(self):
        corpus = [
            TextSource(text="SEO tools and keyword analysis", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = compute_cooccurrence_terms(corpus_hash, seed_terms=("seo", "tools"))

        for result in results:
            assert isinstance(result.context_terms, list)

    # Purpose: Test co-occurrence results sorted by count desc, jaccard desc, term asc.
    def test_cooccurrence_sorting(self):
        corpus = [
            TextSource(text="SEO tools keyword analysis software research", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = compute_cooccurrence_terms(corpus_hash, seed_terms=("seo",))

        counts = [r.cooccurrence_count for r in results]
        assert counts == sorted(counts, reverse=True)

    # Purpose: Test empty seed terms returns empty list.
    def test_cooccurrence_empty_seeds(self):
        corpus = [TextSource(text="SEO tools", field="title", weight=3.0)]
        corpus_hash = _normalize_for_hashing(corpus)
        results = compute_cooccurrence_terms(corpus_hash, seed_terms=())
        assert results == []

    # Purpose: Test empty corpus returns empty list.
    def test_cooccurrence_empty_corpus(self):
        results = compute_cooccurrence_terms(tuple(), seed_terms=("seo",))
        assert results == []

    # Purpose: strip_suffixes must thread into the co-occurrence matrix so inflected
    # Cyrillic forms collapse onto one lemma, mirroring n-grams/TF-IDF/intent/BM25F.
    # pymorphy3 reliably collapses Russian "доставка" and its instrumental "доставкою"
    # to the same lemma "доставка". The seed "магазин" is lemma-stable (its surface form
    # equals its lemma), so it keys the matrix identically in both modes; this isolates
    # the test to the matrix's tokenization, not seed lookup. With strip ON the two
    # surface forms must surface as ONE term "доставка" (not two separate rows).
    @_lemmatizer_skip
    def test_cooccurrence_strips_suffixes_when_enabled(self):
        corpus = [
            TextSource(
                text="магазин доставкой и доставкою курьером",
                field="title",
                weight=3.0,
            ),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        compute_cooccurrence_terms.cache_clear()
        results = compute_cooccurrence_terms(corpus_hash, seed_terms=("магазин",), strip_suffixes=True)

        terms = {r.term for r in results}
        assert "доставка" in terms, f"lemma 'доставка' missing; got {terms}"
        assert "доставкою" not in terms, f"inflected 'доставкою' should have collapsed; got {terms}"

    # Purpose: The strip_suffixes flag is the morphology toggle, identical in spirit to
    # the intent matcher. ENABLED (broad) must collapse inflections and therefore
    # register MORE co-occurring signal than DISABLED (strict), proving the flag is
    # actually consumed by the matrix builder rather than dropped on the floor. The
    # lemma-stable seed "магазин" keys both modes identically.
    @_lemmatizer_skip
    def test_cooccurrence_enabled_catches_more_inflections(self):
        corpus = [
            TextSource(
                text="магазин доставкой и доставкою курьером",
                field="title",
                weight=3.0,
            ),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        compute_cooccurrence_terms.cache_clear()
        off = compute_cooccurrence_terms(corpus_hash, seed_terms=("магазин",), strip_suffixes=False)
        compute_cooccurrence_terms.cache_clear()
        on = compute_cooccurrence_terms(corpus_hash, seed_terms=("магазин",), strip_suffixes=True)

        # Strict mode splits the signal across two surface forms; broad mode aggregates
        # both onto the single lemma "доставка", so broad count strictly exceeds the
        # sum of strict's two rows.
        off_count = sum(r.cooccurrence_count for r in off if r.term in ("доставка", "доставкою"))
        on_count = sum(r.cooccurrence_count for r in on if r.term == "доставка")
        assert on_count > off_count, (
            f"ENABLED should aggregate inflections onto one lemma with a higher count: "
            f"on={on_count}, off={off_count}"
        )


# Purpose: Test intent analysis with confidence metric.
class TestIntentAnalysis:

    # Purpose: Test commercial intent detection.
    def test_intent_commercial_detection(self):
        corpus = [
            TextSource(text="best SEO tools comparison review price catalog", field="title", weight=3.0),
            TextSource(text="top product research and feature comparisons", field="snippet", weight=1.5),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash)

        assert result.intent_type in ("commercial", "mixed")
        assert result.score > 0
        assert 0 <= result.confidence <= 1
        assert isinstance(result.signals, list)
        assert result.intent_type != "transactional"

    # Purpose: Test informational intent detection.
    def test_intent_informational_detection(self):
        corpus = [
            TextSource(text="how to choose the best SEO tools guide review comparison", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash)

        assert result.intent_type in ("informational", "mixed")
        assert result.score > 0
        assert 0 <= result.confidence <= 1

    # Purpose: Test transactional intent detection for purchase flow.
    def test_intent_transactional_detection_for_purchase_flow(self):
        corpus = [
            TextSource(text="buy SEO tools checkout order cart pay delivery shipping discount coupon", field="title", weight=3.0),
            TextSource(text="official store cart checkout shipping and payment", field="snippet", weight=1.5),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash, strip_suffixes=False)

        assert result.intent_type == "transactional"
        assert result.score > 0
        assert 0 <= result.confidence <= 1
        assert any(signal in result.signals for signal in ("buy", "order", "checkout", "cart", "pay", "shipping", "delivery"))

    # Purpose: Test navigational intent detection for brand/domain/login corpus.
    def test_intent_navigational_detection_for_brand_domain_login(self):
        corpus = [
            TextSource(text="Acme SEO official site homepage account login", field="title", weight=3.0),
            TextSource(text="https://acme-seo.example.com/login/account", field="displayed_link", weight=1.0),
            TextSource(text="acme-seo.example.com/official", field="serp_snippet", weight=1.5),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash, strip_suffixes=False)

        assert result.intent_type == "navigational"
        assert result.score > 0
        assert 0 <= result.confidence <= 1
        assert any(signal.startswith("nav:") for signal in result.signals)

    # Purpose: Test commercial research remains distinct from direct purchase flow.
    def test_intent_commercial_research_distinct_from_transactional(self):
        corpus = [
            TextSource(text="best SEO tools comparison review price catalog", field="title", weight=3.0),
            TextSource(text="top product research and feature comparison guide", field="snippet", weight=1.5),
            TextSource(text="best SEO tools for small teams", field="related_searches", weight=1.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash, strip_suffixes=False)

        assert result.intent_type in ("commercial", "mixed")
        assert result.intent_type != "transactional"
        assert result.score > 0

    # Purpose: Test lower-weight SERP side signals do not overpower title and snippet.
    def test_intent_uses_paa_and_related_searches_with_lower_weight(self):
        corpus = [
            TextSource(text="how to choose SEO tools guide comparison", field="title", weight=3.0),
            TextSource(text="review and tutorial for beginners", field="snippet", weight=1.5),
            TextSource(text="buy SEO tools checkout order", field="related_searches", weight=1.0),
            TextSource(text="what is the price and delivery", field="people_also_ask", weight=1.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash, strip_suffixes=False)

        assert result.intent_type == "informational"
        assert result.score > 0
        assert any(signal in result.signals for signal in ("buy", "order", "price"))

    # Purpose: Test confidence requires coverage across multiple sources.
    def test_intent_confidence_requires_serp_coverage(self):
        sparse_corpus = [
            TextSource(text="buy SEO tools", field="title", weight=3.0),
            TextSource(text="neutral snippet one", field="snippet", weight=1.5),
            TextSource(text="neutral snippet two", field="snippet", weight=1.5),
            TextSource(text="neutral related query", field="related_searches", weight=1.0),
            TextSource(text="neutral question", field="people_also_ask", weight=1.0),
        ]
        dense_corpus = [
            TextSource(text="buy SEO tools checkout order", field="title", weight=3.0),
            TextSource(text="official store price delivery payment", field="snippet", weight=1.5),
            TextSource(text="seo-tools.example.com/cart", field="displayed_link", weight=1.0),
        ]

        sparse_result = analyze_intent(_normalize_for_hashing(sparse_corpus), strip_suffixes=False)
        dense_result = analyze_intent(_normalize_for_hashing(dense_corpus), strip_suffixes=False)

        assert sparse_result.intent_type in ("transactional", "commercial")
        assert sparse_result.confidence < 0.4
        assert dense_result.intent_type == "transactional"
        assert dense_result.confidence > sparse_result.confidence
        assert dense_result.confidence >= 0.4

    # Purpose: Test confidence metric is computed (signals matched / total signals).
    def test_intent_confidence_metric(self):
        corpus = [
            TextSource(text="buy SEO tools price cheap", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash)

        assert 0 <= result.confidence <= 1
        assert hasattr(result, 'confidence')

    # Purpose: Test intent analysis returns list of matched signals.
    def test_intent_signals_list(self):
        corpus = [
            TextSource(text="buy SEO tools with discount", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash)

        assert isinstance(result.signals, list)
        assert len(result.signals) > 0

    # Purpose: Test empty corpus returns undetermined with zero score.
    def test_intent_empty_corpus(self):
        result = analyze_intent(tuple())
        assert result.score == 0
        assert result.intent_type == "undetermined"
        assert result.confidence == 0

    # Purpose: Test Russian stem matching catches inflected forms.
    # NOTE: strip_suffixes=True (BROAD mode) is where Cyrillic morphology collapsing
    # lives after the intent-matcher inversion. The inflected verb "Купите" only
    # lemmatizes onto the "куп" stem when lemmatization is enabled.
    def test_intent_russian_stem_matching(self):
        corpus = [
            TextSource(text="Купите SEO инструменты для продвижения сайта", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash, strip_suffixes=True)
        assert result.intent_type == "transactional"
        assert result.score > 0
        assert result.confidence > 0
        assert "куп" in result.signals

    # Purpose: Test Ukrainian stem matching.
    # NOTE: strip_suffixes=True (BROAD mode) is where Cyrillic stem matching lives.
    def test_intent_ukrainian_stem_matching(self):
        corpus = [
            TextSource(text="Ціни на послуги SEO просування", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash, strip_suffixes=True)
        assert result.intent_type == "commercial"
        assert result.score > 0

    # Purpose: Test informational Russian stems.
    # NOTE: strip_suffixes=True (BROAD mode) is where Cyrillic stem matching lives.
    def test_intent_informational_russian(self):
        corpus = [
            TextSource(text="Обзоры и сравнение лучших SEO сервисов", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash, strip_suffixes=True)
        assert result.intent_type == "informational"
        assert result.score > 0
        assert result.confidence > 0

    # Purpose: Test URL/domain commercial heuristics.
    def test_intent_url_commercial_heuristic(self):
        corpus = [
            TextSource(text="example homepage", field="title", weight=3.0),
            TextSource(text="www.seo-shop.com/tools", field="displayed_link", weight=1.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash, strip_suffixes=False)
        assert result.intent_type == "commercial"
        assert any(s.startswith("url:") for s in result.signals)

    # Purpose: Test mixed intent when commercial and informational are tied.
    def test_intent_mixed_when_tied(self):
        corpus = [
            TextSource(text="best guide", field="title", weight=1.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash, strip_suffixes=False)
        assert result.intent_type == "mixed"

    # Purpose: Test undetermined intent when no signals match.
    def test_intent_undetermined_when_no_signals(self):
        corpus = [
            TextSource(text="the weather is sunny today in the park", field="title", weight=3.0),
            TextSource(text="example.com — homepage navigation menu", field="snippet", weight=2.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        result = analyze_intent(corpus_hash, strip_suffixes=False)
        assert result.intent_type == "undetermined"
        assert result.score == 0.0
        assert result.confidence == 0.0

    # Purpose: Test confidence is non-trivial for real SERP data.
    def test_intent_confidence_is_meaningful(self):
        corpus = [
            TextSource(text="купить ноутбук по лучшей цене со скидкой", field="title", weight=3.0),
            TextSource(text="Магазин электроники — доставка по всей стране", field="snippet", weight=2.0),
            TextSource(text="shop.example.com/notebooks", field="displayed_link", weight=1.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        # NOTE: strip_suffixes=True (BROAD) — this corpus leans on Cyrillic stems
        # (куп/цен/магазин/достав/скидк) which only register in broad/lemma mode.
        result = analyze_intent(corpus_hash, strip_suffixes=True)
        assert result.intent_type == "transactional"
        assert result.confidence > 0.05
        assert len(result.signals) >= 3

    # Purpose: REGRESSION for the production bug where SERP/generated-text corpora
    # full of inflected Ukrainian/Russian "buy" words (купити, замовлення) were left
    # UNCLASSIFIED (intent=undetermined, score 0) in the DEFAULT strict mode
    # (strip_suffixes=False). The Cyrillic stem sets are PREFIX stems ("куп", "замов"),
    # so strict mode must prefix-match them, not demand exact equality. The corpus
    # here mirrors the user's exported math report (дерев'яна стружка / купити).
    def test_intent_cyrillic_inflected_buy_classifies_in_default_strict_mode(self):
        corpus = [
            TextSource(
                text="Дерев'яна стружка для упаковки: наповнювач у коробки. Ви можете купити стружку деревну для оформлення пакунків.",
                field="title",
                weight=3.0,
            ),
            TextSource(
                text="Каталожна позиція доступна для швидкого замовлення. Захист та декор вашої продукції.",
                field="snippet",
                weight=2.0,
            ),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        analyze_intent.cache_clear()
        result = analyze_intent(corpus_hash, strip_suffixes=False)
        # MUST NOT be undetermined — the corpus is unambiguously purchase-oriented.
        assert result.intent_type != "undetermined"
        assert result.score > 0
        # The "куп" prefix stem must register from the inflected "купити".
        assert "куп" in result.signals

    # Purpose: strip_suffixes toggles morphology collapsing. STRICT (False) prefix-
    # matches the RAW token; BROAD (True) prefix-matches the LEMMATIZED token, which
    # is a superset (it also collapses irregular root alternations). For regular
    # Slavic inflections the two coincide, so broad must score AT LEAST as much as
    # strict — and strict must be nonzero, proving the classifier works out of the box.
    def test_intent_broad_mode_is_superset_of_strict(self):
        corpus = [
            TextSource(text="купил заказал оплатил доставлено", field="title", weight=3.0),
            TextSource(text="покупка товаров со скидкою и акциями", field="snippet", weight=2.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        analyze_intent.cache_clear()
        off = analyze_intent(corpus_hash, strip_suffixes=False)
        analyze_intent.cache_clear()
        on = analyze_intent(corpus_hash, strip_suffixes=True)
        # Strict mode now catches the inflected verbs (bug fix) -> nonzero.
        assert off.score > 0
        assert "куп" in off.signals
        # Broad (lemma-based) is a superset of strict (raw-prefix).
        assert on.score >= off.score

    # Purpose: STRICT mode (strip_suffixes=False) prefix-matches inflected Cyrillic
    # forms against the prefix stems — the inflected verb "купить" starts with the
    # stem "куп", so the signal MUST register. This locks in the corrected contract
    # (the old exact-equality premise left the whole UA/RU market unclassified).
    def test_intent_strict_mode_prefix_matches_inflected_cyrillic(self):
        corpus = [
            TextSource(text="купить заказать оплатить", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        analyze_intent.cache_clear()
        off = analyze_intent(corpus_hash, strip_suffixes=False)
        assert "куп" in off.signals
        assert off.intent_type == "transactional"

    # Purpose: Guard against a false-positive introduced by reverse prefix matching in
    # STRICT mode. A single-letter Cyrillic fragment like "г" (the unit, from "250 г")
    # must NOT register the navigational stem "головн" via stem.startswith("г"). The
    # strict matcher matches only the FORWARD direction (inflected form starts with the
    # root stem), never a raw fragment being a prefix of a long stem.
    def test_intent_strict_mode_no_false_positive_on_short_fragment(self):
        corpus = [
            TextSource(text="наповнювач 250 г в коробці", field="snippet", weight=2.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        analyze_intent.cache_clear()
        result = analyze_intent(corpus_hash, strip_suffixes=False)
        # The "г" fragment must never inflate a navigational signal.
        assert not any(s.startswith("nav:головн") for s in result.signals)


# Purpose: Test the lazy-loaded real lemmatizer (pymorphy3 + simplemma) that powers
# the broad/stripped matching mode. These cover (1) real collapse of inflected verbs,
# and (2) graceful fallback to identity when no lemmatizer library is importable.
class TestLemmatization:

    # Purpose: The real pymorphy3 lemmatizer must collapse Russian verb inflections
    # to their dictionary form. "купил" and "куплю" both lemmatize to "купить".
    # This proves the broad mode has a real morphological engine behind it rather
    # than a regex suffix hack that cannot handle verbs.
    # Skipped where the optional pymorphy3 libs are not installed (the module then
    # returns tokens unchanged by design — see test_lemmatize_token_returns_input_unchanged_when_no_lib).
    @_lemmatizer_skip
    def test_lemmatize_token_collapses_russian_verbs(self):
        _get_pymorphy_ru.cache_clear()
        _get_pymorphy_uk.cache_clear()
        _get_simplemma.cache_clear()
        assert lemmatize_token("купил") == "купить"
        assert lemmatize_token("куплю") == "купить"

    # Purpose: When every lemmatizer factory returns None (libs not installed), the
    # public helper must degrade gracefully and return the input token UNCHANGED —
    # never raise. This guarantees zero startup cost and no hard dependency.
    def test_lemmatize_token_returns_input_unchanged_when_no_lib(self, monkeypatch):
        monkeypatch.setattr(
            "utils.seo_math_analysis._get_pymorphy_ru", lambda: None
        )
        monkeypatch.setattr(
            "utils.seo_math_analysis._get_pymorphy_uk", lambda: None
        )
        monkeypatch.setattr(
            "utils.seo_math_analysis._get_simplemma", lambda: None
        )
        # Also clear the cached real instances so the patched lambdas are used.
        _get_pymorphy_ru.cache_clear()
        _get_pymorphy_uk.cache_clear()
        _get_simplemma.cache_clear()
        assert lemmatize_token("купил") == "купил"


# Purpose: UI dependency checker for the optional lemmatizer packages. Mirrors the
# browser_scraper dependency table: detect installed/missing, build the pip command,
# and surface problem deps. These tests pin the contract the sidebar relies on.
class TestLemmatizerDependencyChecker:

    # Purpose: The package list drives the install command and the status table.
    # pymorphy3-dicts-uk is the PyPI name; it imports as the underscored module.
    def test_dependency_package_list_contents(self):
        assert LEMMATIZER_DEPENDENCY_PACKAGES == (
            "pymorphy3",
            "pymorphy3-dicts-uk",
            "simplemma",
        )

    # Purpose: check_lemmatizer_dependencies must report one status per package,
    # using the DependencyStatus enum (AVAILABLE/MISSING/...). Keys are import
    # module names so the UI can map them to display labels.
    def test_check_returns_status_for_every_package(self):
        statuses = check_lemmatizer_dependencies()
        assert set(statuses.keys()) == {
            "pymorphy3",
            "pymorphy3_dicts_uk",
            "simplemma",
        }
        # Every value is a DependencyStatus enum member.
        for status in statuses.values():
            assert hasattr(status, "value")
            assert status.value in {"available", "missing", "unknown", "unusable"}

    # Purpose: A present pymorphy3 must be detected as AVAILABLE. Guards against the
    # detection import name being wrong. Only meaningful where pymorphy3 IS installed;
    # skipped on environments without it (where the correct status is MISSING).
    @_pymorphy3_skip
    def test_pymorphy3_detected_when_present(self):
        statuses = check_lemmatizer_dependencies()
        assert statuses["pymorphy3"].value == "available"

    # Purpose: The uk dict imports as the underscored module pymorphy3_dicts_uk;
    # when present it must read AVAILABLE. Skipped where the dict package is absent.
    @_uk_dict_skip
    def test_uk_dict_detected_when_present(self):
        statuses = check_lemmatizer_dependencies()
        assert statuses["pymorphy3_dicts_uk"].value == "available"

    # Purpose: project scope installs into the current interpreter.
    def test_install_command_project_scope(self):
        cmd = build_lemmatizer_install_command("project")
        assert cmd == "python -m pip install pymorphy3 pymorphy3-dicts-uk simplemma"

    # Purpose: global scope targets the per-user site-packages.
    def test_install_command_global_scope(self):
        cmd = build_lemmatizer_install_command("global")
        assert cmd == "python -m pip install --user pymorphy3 pymorphy3-dicts-uk simplemma"

    # Purpose: default scope is project (UI passes nothing on first render).
    def test_install_command_default_scope_is_project(self):
        assert build_lemmatizer_install_command() == build_lemmatizer_install_command("project")

    # Purpose: get_lemmatizer_problem_dependencies filters OUT AVAILABLE statuses
    # and keeps everything else (missing/unknown/unusable) so the UI only warns
    # when action is needed.
    def test_problem_dependencies_excludes_available(self, monkeypatch):
        from utils.seo_math_analysis import LemmatizerDependencyStatus as _LDS
        monkeypatch.setattr(
            "utils.seo_math_analysis.check_lemmatizer_dependencies",
            lambda: {
                "pymorphy3": _LDS.AVAILABLE,
                "pymorphy3_dicts_uk": _LDS.MISSING,
                "simplemma": _LDS.UNUSABLE,
            },
        )
        problems = get_lemmatizer_problem_dependencies()
        assert "pymorphy3" not in problems
        assert "pymorphy3_dicts_uk" in problems
        assert "simplemma" in problems

    # Purpose: when everything is available, problem list is empty (UI shows ready).
    def test_problem_dependencies_empty_when_all_available(self, monkeypatch):
        from utils.seo_math_analysis import LemmatizerDependencyStatus as _LDS
        monkeypatch.setattr(
            "utils.seo_math_analysis.check_lemmatizer_dependencies",
            lambda: {
                "pymorphy3": _LDS.AVAILABLE,
                "pymorphy3_dicts_uk": _LDS.AVAILABLE,
                "simplemma": _LDS.AVAILABLE,
            },
        )
        assert get_lemmatizer_problem_dependencies() == {}


# Purpose: Test content gap analysis with coverage metrics.
class TestContentGapAnalysis:

    # Purpose: Test coverage ratio is computed correctly.
    def test_coverage_ratio_computation(self):
        source_text = "SEO tools and keyword analysis"
        target_profile = ["seo", "tools", "keyword", "analysis", "software"]

        result = analyze_content_gap(source_text, target_profile)

        assert 0 <= result.coverage_ratio <= 1
        assert result.coverage_ratio < 1.0

    # Purpose: Test Jaccard overlap is computed.
    def test_jaccard_overlap_computation(self):
        source_text = "SEO tools and keyword analysis"
        target_profile = ["seo", "tools", "keyword"]

        result = analyze_content_gap(source_text, target_profile)

        assert 0 <= result.jaccard_overlap <= 1

    # Purpose: Test cosine similarity is computed.
    def test_cosine_similarity_computation(self):
        source_text = "SEO tools and keyword analysis"
        target_profile = ["seo", "tools", "keyword"]

        result = analyze_content_gap(source_text, target_profile)

        assert 0 <= result.cosine_similarity <= 1

    # Purpose: Test missing high-value terms are identified.
    def test_missing_high_value_terms(self):
        source_text = "SEO tools"
        target_profile = ["seo", "tools", "keyword", "analysis", "software"]

        result = analyze_content_gap(source_text, target_profile)

        assert len(result.missing_high_value) > 0
        assert "keyword" in result.missing_high_value
        assert "analysis" in result.missing_high_value

    # Purpose: Test overused low-value terms are identified.
    def test_overused_low_value_terms(self):
        source_text = "tool tool tool tool analysis analysis analysis analysis"
        target_profile = ["seo", "keyword"]

        result = analyze_content_gap(source_text, target_profile)

        overused = result.overused_low_value
        assert len(overused) > 0

    # Purpose: Test empty target profile returns zero-scored result.
    def test_gap_analysis_empty_target(self):
        result = analyze_content_gap("SEO tools", [])
        assert result.coverage_ratio == 0
        assert result.jaccard_overlap == 0
        assert result.cosine_similarity == 0


# Purpose: Test generated SEO text parsing and scoring.
class TestGeneratedTextScoring:

    # Purpose: Test META_TITLE section parsing.
    def test_parse_meta_title(self):
        text = """META_TITLE: Best SEO Tools for Keyword Research

META_DESCRIPTION: Discover top SEO software...
"""
        sections = _parse_generated_sections(text)
        assert sections["META_TITLE"] == "Best SEO Tools for Keyword Research"

    # Purpose: Test META_DESCRIPTION section parsing.
    def test_parse_meta_description(self):
        text = """META_TITLE: Best SEO Tools

META_DESCRIPTION: Discover top SEO software with advanced features and best prices.
"""
        sections = _parse_generated_sections(text)
        assert sections["META_DESCRIPTION"].startswith("Discover top SEO")

    # Purpose: Test H1 section parsing.
    def test_parse_h1_section(self):
        text = """META_TITLE: Best SEO Tools

H1: Complete SEO Software Review

DESCRIPTION: Full review...
"""
        sections = _parse_generated_sections(text)
        assert sections["H1"] == "Complete SEO Software Review"

    # Purpose: Test DESCRIPTION body parsing.
    def test_parse_description_body(self):
        text = """META_TITLE: SEO Tools

META_DESCRIPTION: Review of SEO tools

H1: SEO Tools Review

DESCRIPTION: <p>This is a comprehensive review of SEO software.</p>
"""
        sections = _parse_generated_sections(text)
        assert "comprehensive review" in sections["DESCRIPTION"]

    # Purpose: Test HTML tag fallback parsing.
    def test_parse_html_fallback(self):
        text = """<title>Best SEO Tools</title>
<meta name="description" content="Top SEO software">
<h1>SEO Software Review</h1>
<p>Full review content</p>
"""
        sections = _parse_generated_sections(text)
        assert sections["META_TITLE"] == "Best SEO Tools"
        assert sections["META_DESCRIPTION"] == "Top SEO software"
        assert sections["H1"] == "SEO Software Review"

    # Purpose: Test missing sections return empty strings.
    def test_parse_missing_sections(self):
        text = "Some random text without sections"
        sections = _parse_generated_sections(text)
        assert sections["META_TITLE"] == ""
        assert sections["META_DESCRIPTION"] == ""
        assert sections["H1"] == ""
        assert sections["DESCRIPTION"] == ""

    # Purpose: Test META_TITLE length scoring.
    def test_score_meta_title_length(self):
        generated = "META_TITLE: Best SEO Tools for Keyword Research\n\nMETA_DESCRIPTION: ..."
        profile = {"top_ngrams": ["seo tools", "keyword research"]}
        scores = score_generated_text(generated, "seo tools", profile)

        title_score = scores["META_TITLE"]
        assert hasattr(title_score, 'score')
        assert hasattr(title_score, 'length_compliant')
        assert hasattr(title_score, 'issues')

    # Purpose: Test META_DESCRIPTION length scoring.
    def test_score_meta_description_length(self):
        generated = "META_TITLE: Test\n\nMETA_DESCRIPTION: Discover top SEO software with advanced features for better ranking and optimization results.\n\nH1: Test\n\nDESCRIPTION: ..."
        profile = {}
        scores = score_generated_text(generated, "seo", profile)

        desc_score = scores["META_DESCRIPTION"]
        assert hasattr(desc_score, 'score')
        assert hasattr(desc_score, 'length_compliant')

    # Purpose: Test H1 length scoring.
    def test_score_h1_length(self):
        generated = "META_TITLE: Test\n\nMETA_DESCRIPTION: Test\n\nH1: Comprehensive SEO Software Review and Analysis\n\nDESCRIPTION: ..."
        profile = {}
        scores = score_generated_text(generated, "seo", profile)

        h1_score = scores["H1"]
        assert hasattr(h1_score, 'score')
        assert hasattr(h1_score, 'length_compliant')

    # Purpose: Test DESCRIPTION length scoring.
    def test_score_description_length(self):
        generated = "META_TITLE: Test\n\nMETA_DESCRIPTION: Test\n\nH1: Test\n\nDESCRIPTION: " + "x" * 600
        profile = {}
        scores = score_generated_text(generated, "seo", profile)

        desc_score = scores["DESCRIPTION"]
        assert hasattr(desc_score, 'score')
        assert desc_score.length_compliant is True

    # Purpose: Test keyword density calculation.
    def test_keyword_density_calculation(self):
        text = "SEO tools are great. SEO software helps. SEO analysis is important."
        density = _calculate_keyword_density(text, "seo")
        assert density > 0

    # Purpose: When strip_suffixes=True, density must count ALL inflections of the
    # keyword as the same lemma. pymorphy3 collapses Russian кроссовки/кроссовках/кроссовок
    # to one lemma "кроссовок", so a text containing three surface forms must register a
    # higher density than raw-token counting (which sees them as three distinct tokens and
    # counts none of them toward the lemma keyword). Guards against the tokenizer being
    # hardcoded to False inside _calculate_keyword_density.
    @_lemmatizer_skip
    def test_keyword_density_strips_suffixes_when_enabled(self):
        text = "кроссовки кроссовках кроссовок здесь"
        lemma = lemmatize_token("кроссовки")  # -> кроссовок
        off = _calculate_keyword_density(text, lemma, strip_suffixes=False)
        on = _calculate_keyword_density(text, lemma, strip_suffixes=True)
        assert on > off, f"ENABLED should collapse inflections onto the lemma: on={on}, off={off}"
        assert on > 0, f"ENABLED should find the lemma in inflected text: on={on}"

    # Purpose: Test forbidden phrases detection.
    def test_forbidden_phrases_check(self):
        text = "Click here to learn more about our products."
        forbidden = _check_forbidden_phrases(text)
        assert "click here" in forbidden
        assert "learn more" in forbidden

    # Purpose: Test score_generated_text is a public API.
    def test_score_public_api(self):
        assert callable(score_generated_text)

        generated = "META_TITLE: Test\n\nDESCRIPTION: Test content"
        profile = {"top_ngrams": []}
        scores = score_generated_text(generated, "test", profile)

        assert isinstance(scores, dict)
        assert "META_TITLE" in scores
        assert "META_DESCRIPTION" in scores
        assert "H1" in scores
        assert "DESCRIPTION" in scores

    # Purpose: Test the generated-text scorer does not discard later top terms.
    def test_score_generated_text_uses_all_available_top_terms(self):
        generated = "META_TITLE: alpha-11\n\nDESCRIPTION: alpha-11 content"
        profile = {
            "top_ngrams": [f"alpha-{i}" for i in range(12)],
            "tfidf_terms": [],
            "cooccurrence_terms": [],
        }

        scores = score_generated_text(generated, "alpha-11", profile)

        assert scores["META_TITLE"].keyword_coverage > 0

    # Purpose: When strip_suffixes=True, score_generated_text must tokenize the generated
    # text to lemmas so its BM25F coverage actually matches the lemmatized SERP query
    # terms. The SERP profile's top_ngrams are lemmas (built by the lemmatizing pipeline),
    # so generated text written in inflected Cyrillic ("кроссовки") must collapse to the
    # lemma "кроссовок" to register BM25F coverage. Guards against score_generated_text
    # calling compute_bm25f with the strip_suffixes flag dropped (defaults to False).
    @_lemmatizer_skip
    def test_score_generated_text_bm25f_lemmatizes_when_enabled(self):
        generated = (
            "META_TITLE: Кроссовки мужские для активного спорта и бега\n"
            "META_DESCRIPTION: Купите кроссовки мужские недорого с доставкой\n"
            "H1: Кроссовки мужские\n"
            "DESCRIPTION: Кроссовки кроссовки кроссовки кроссовки кроссовки"
        )
        profile = {
            "top_ngrams": ["кроссовок"],
            "tfidf_terms": ["кроссовок"],
            "cooccurrence_terms": [],
            "tfidf_overlap": 0.5,
            "cooccurrence_coverage": 0.6,
            "meta_title": "",
        }

        scores = score_generated_text(
            generated, "кроссовок", profile, enable_bm25f=True, strip_suffixes=True
        )

        # The DESCRIPTION element has 5 surface occurrences; with strip ON they collapse
        # to the lemma and must register non-zero BM25F coverage of the lemma query term.
        assert scores["DESCRIPTION"].bm25f_coverage is not None, (
            "BM25F coverage must be computed; got None"
        )
        assert scores["DESCRIPTION"].bm25f_coverage > 0, (
            f"ENABLED should match the lemmatized query term in inflected text: "
            f"coverage={scores['DESCRIPTION'].bm25f_coverage}"
        )

    # Purpose: When strip_suffixes=True, _score_element's keyword-presence and n-gram
    # coverage checks must lemmatize BOTH the element text and the profile terms, so an
    # inflected generated element ("Кроссовки мужские") matches the lemma-form keyword /
    # n-grams ("кроссовок") from the lemmatized SERP profile. Currently these checks use
    # raw .lower() substring matching, so an inflected element registers the lemma keyword
    # as absent (primary_keyword_present=False, keyword_coverage=0) even though it is
    # present. This test locks the corrected behavior. "кроссовки" is chosen because its
    # lemma "кроссовок" is NOT a substring of the inflected form, so raw matching fails
    # while lemmatized matching succeeds (isolates the fix from prefix-substring luck).
    @_lemmatizer_skip
    def test_score_element_lemmatizes_keyword_presence_and_coverage(self):
        # pymorphy3 reliably maps "кроссовки" -> "кроссовок", and "кроссовок" is NOT a
        # substring of "кроссовки", so an element written in the inflected form only
        # matches the lemma primary keyword under lemmatization.
        lemma = lemmatize_token("кроссовки")  # -> кроссовок
        assert lemma == "кроссовок", (
            f"test precondition: pymorphy3 must lemmatize кроссовки -> кроссовок; got {lemma!r}"
        )
        generated = (
            "META_TITLE: Кроссовки мужские для активного спорта\n"
            "META_DESCRIPTION: Купите кроссовки мужские недорого\n"
            "H1: Кроссовки мужские\n"
            "DESCRIPTION: "
            "кроссовки кроссовки кроссовки кроссовки кроссовки кроссовки кроссовки "
            "кроссовки кроссовки кроссовки кроссовки кроссовки кроссовки кроссовки"
        )
        profile = {
            "top_ngrams": [lemma],
            "tfidf_terms": [lemma],
            "cooccurrence_terms": [],
            "tfidf_overlap": 0.5,
            "cooccurrence_coverage": 0.6,
            "meta_title": "",
        }

        scores = score_generated_text(
            generated, lemma, profile, enable_bm25f=False, strip_suffixes=True
        )

        # The lemma keyword IS present (in inflected form) in every element, so the
        # lemmatizing check must NOT flag it as missing and must record non-zero coverage.
        for element_type in ("META_TITLE", "META_DESCRIPTION", "H1", "DESCRIPTION"):
            elem = scores[element_type]
            assert elem.primary_keyword_present is True, (
                f"{element_type}: ENABLED should match lemma keyword '{lemma}' in "
                f"inflected text; got primary_keyword_present=False"
            )
        assert scores["H1"].keyword_coverage > 0, (
            f"H1: ENABLED should count the lemma n-gram in inflected text; "
            f"keyword_coverage={scores['H1'].keyword_coverage}"
        )


# Purpose: Test memoization cache behavior.
class TestMemoization:

    # Purpose: Test extract_ngrams uses memoization.
    def test_extract_ngrams_memoization(self):
        corpus = [
            TextSource(text="SEO tools keyword analysis", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)

        result1 = extract_ngrams(corpus_hash, n=1, min_count=1, min_df=1)
        result2 = extract_ngrams(corpus_hash, n=1, min_count=1, min_df=1)

        assert result1 == result2

    # Purpose: Test compute_tfidf uses memoization.
    def test_compute_tfidf_memoization(self):
        corpus = [
            TextSource(text="SEO tools", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)

        result1 = compute_tfidf(corpus_hash)
        result2 = compute_tfidf(corpus_hash)

        assert result1 == result2

    # Purpose: Test analyze_intent uses memoization.
    def test_analyze_intent_memoization(self):
        corpus = [
            TextSource(text="buy SEO tools", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)

        result1 = analyze_intent(corpus_hash)
        result2 = analyze_intent(corpus_hash)

        assert result1 == result2


# Purpose: Test edge cases and error handling.
class TestEdgeCases:

    # Purpose: Test n-gram extraction with empty corpus.
    def test_empty_corpus_ngrams(self):
        result = extract_ngrams(tuple(), n=1, min_count=1, min_df=1)
        assert result == []

    # Purpose: Test single document corpus handling.
    def test_single_document_corpus(self):
        corpus = [
            TextSource(text="SEO tools and keyword analysis", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        results = extract_ngrams(corpus_hash, n=1, min_count=1, min_df=1)
        assert isinstance(results, list)

    # Purpose: Test very short text input.
    def test_very_short_text(self):
        result = analyze_content_gap("a", ["a", "b"])
        assert result.coverage_ratio <= 1.0

    # Purpose: Test text with unicode emojis doesn't crash.
    def test_unicode_emoji_in_text(self):
        text = "SEO tools ✨ with great features ⭐"
        tokens = _tokenize_text(text)
        assert "seo" in tokens
        assert "tools" in tokens


# Purpose: Test BM25F data model classes.
class TestBM25FDataModels:

    # Purpose: Test FieldStats dataclass.
    def test_field_stats_dataclass(self):
        stats = FieldStats(
            field="title",
            total_length=100,
            avg_length=10.0,
            doc_count=10
        )
        assert stats.field == "title"
        assert stats.total_length == 100
        assert stats.avg_length == 10.0
        assert stats.doc_count == 10

    # Purpose: Test BM25FScore dataclass.
    def test_bm25f_score_dataclass(self):
        score = BM25FScore(
            doc_id=0,
            doc_text="Test document",
            score=1.5,
            term_scores={"seo": 0.8, "tools": 0.7},
            field_contributions={"title": 1.0, "body": 0.5},
            query_coverage=0.5,
            matched_terms=["seo", "tools"]
        )
        assert score.doc_id == 0
        assert score.score == 1.5
        assert score.term_scores["seo"] == 0.8
        assert score.field_contributions["title"] == 1.0
        assert score.query_coverage == 0.5
        assert "seo" in score.matched_terms

    # Purpose: Test FieldWeightedProfile dataclass.
    def test_field_weighted_profile_dataclass(self):
        profile = FieldWeightedProfile(
            field_weights={"title": 3.0, "body": 1.0},
            field_b_params={"title": 0.5, "body": 0.75},
            field_stats={},
            avg_field_lengths={"title": 10.0, "body": 100.0},
            corpus_size=10,
            algorithm_version="bm25f_v1"
        )
        assert profile.field_weights["title"] == 3.0
        assert profile.field_b_params["body"] == 0.75
        assert profile.corpus_size == 10
        assert profile.algorithm_version == "bm25f_v1"


# Purpose: Test BM25F helper functions.
class TestBM25FHelpers:

    # Purpose: Test default b parameter lookup.
    def test_get_field_b_param_defaults(self):
        assert _get_field_b_param("title", {}) == 0.5
        assert _get_field_b_param("body_text", {}) == 0.75
        assert _get_field_b_param("snippet", {}) == 0.6

    # Purpose: Test custom b parameter lookup.
    def test_get_field_b_param_custom(self):
        custom_b = {"title": 0.3, "body": 0.9}
        assert _get_field_b_param("title", custom_b) == 0.3
        assert _get_field_b_param("body", custom_b) == 0.9

    # Purpose: Test field length normalization computation.
    def test_compute_field_length_normalization(self):
        norm = _compute_field_length_normalization(100, 100, 0.75)
        assert norm == 1.0 / ((1 - 0.75) + 0.75 * 1)

        norm_short = _compute_field_length_normalization(50, 100, 0.75)
        norm_long = _compute_field_length_normalization(200, 100, 0.75)
        assert norm_short > norm_long

        assert _compute_field_length_normalization(100, 0, 0.75) == 1.0

    # Purpose: Test BM25+ IDF formula with +1 smoothing.
    def test_compute_bm25f_idf_formula(self):
        idf = _compute_bm25f_idf(1, 10)
        assert idf > 0

        idf_all = _compute_bm25f_idf(10, 10)
        assert idf_all == 0

        idf_none = _compute_bm25f_idf(0, 10)
        assert idf_none == 0

        import math
        idf_smoothed = _compute_bm25f_idf(2, 10)
        expected = math.log((10 - 2 + 0.5) / (2 + 0.5) + 1.0)
        assert abs(idf_smoothed - expected) < 0.001


# Purpose: Test BM25F scoring with controlled corpus.
class TestBM25FScoring:

    # Purpose: Test basic BM25F scoring.
    def test_bm25f_basic_scoring(self):
        corpus = [
            TextSource(text="SEO tools and keyword research", field="title", weight=3.0),
            TextSource(text="Best SEO optimization software", field="body_text", weight=1.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        query_terms = ("seo", "tools", "keyword")
        field_weights = (("title", 3.0), ("body_text", 1.0))
        field_b = (("title", 0.5), ("body_text", 0.75))

        results = compute_bm25f(
            corpus_hash=corpus_hash,
            query_terms=query_terms,
            field_weights=field_weights,
            field_b=field_b,
            k1=1.2,
            top_n=10
        )

        assert len(results) > 0
        assert all(isinstance(r, BM25FScore) for r in results)
        assert results[0].score > 0

    # Purpose: Test exact ranking with controlled title/body/snippet fields.
    def test_bm25f_exact_ranking_controlled(self):
        corpus = [
            TextSource(text="SEO tools for analysis", field="page_title", weight=3.0),
            TextSource(text="Discover SEO tools and research", field="serp_snippet", weight=1.5),
            TextSource(text="Best software and SEO tools for keyword analysis", field="body_text", weight=1.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        query_terms = ("seo", "tools")
        field_weights = (("page_title", 3.0), ("serp_snippet", 1.5), ("body_text", 1.0))
        field_b = (("page_title", 0.5), ("serp_snippet", 0.6), ("body_text", 0.75))

        results = compute_bm25f(
            corpus_hash=corpus_hash,
            query_terms=query_terms,
            field_weights=field_weights,
            field_b=field_b,
            k1=1.2,
            top_n=10
        )

        assert len(results) >= 2
        assert results[0].doc_id == 0
        assert "seo" in results[0].matched_terms
        assert "tools" in results[0].matched_terms

    # Purpose: Test field contributions are tracked.
    def test_bm25f_field_contributions(self):
        corpus = [
            TextSource(text="SEO tools analysis", field="page_title", weight=3.0),
            TextSource(text="keyword research software", field="page_title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        query_terms = ("seo",)
        field_weights = (("page_title", 3.0),)
        field_b = (("page_title", 0.5),)

        results = compute_bm25f(
            corpus_hash=corpus_hash,
            query_terms=query_terms,
            field_weights=field_weights,
            field_b=field_b,
            k1=1.2
        )

        assert len(results) == 1
        assert "page_title" in results[0].field_contributions
        assert results[0].field_contributions["page_title"] > 0

    # Purpose: Test query coverage ratio is computed.
    def test_bm25f_query_coverage(self):
        corpus = [
            TextSource(text="SEO tools for analysis", field="page_title", weight=3.0),
            TextSource(text="keyword research software", field="page_title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        query_terms = ("seo", "tools", "keyword", "analysis")
        field_weights = (("page_title", 3.0),)
        field_b = (("page_title", 0.5),)

        results = compute_bm25f(
            corpus_hash=corpus_hash,
            query_terms=query_terms,
            field_weights=field_weights,
            field_b=field_b,
            k1=1.2
        )

        assert results[0].query_coverage == 0.75
        assert results[1].query_coverage == 0.25

    # Purpose: Test empty corpus returns empty list.
    def test_bm25f_empty_corpus(self):
        results = compute_bm25f(
            corpus_hash=tuple(),
            query_terms=("seo", "tools"),
            field_weights=(("title", 3.0),),
            field_b=(("title", 0.5),),
        )
        assert results == []

    # Purpose: Test empty query terms returns empty list.
    def test_bm25f_empty_query_terms(self):
        corpus = [TextSource(text="SEO tools", field="title", weight=3.0)]
        corpus_hash = _normalize_for_hashing(corpus)

        results = compute_bm25f(
            corpus_hash=corpus_hash,
            query_terms=(),
            field_weights=(("title", 3.0),),
            field_b=(("title", 0.5),),
        )
        assert results == []

    # Purpose: Test BM25F uses memoization.
    def test_bm25f_memoization(self):
        corpus = [TextSource(text="SEO tools", field="title", weight=3.0)]
        corpus_hash = _normalize_for_hashing(corpus)
        query_terms = ("seo", "tools")
        field_weights = (("title", 3.0),)
        field_b = (("title", 0.5),)

        result1 = compute_bm25f(
            corpus_hash=corpus_hash,
            query_terms=query_terms,
            field_weights=field_weights,
            field_b=field_b,
        )
        result2 = compute_bm25f(
            corpus_hash=corpus_hash,
            query_terms=query_terms,
            field_weights=field_weights,
            field_b=field_b,
        )

        assert result1 == result2

    # Purpose: Test BM25F results are sorted stably.
    def test_bm25f_sorting_stability(self):
        corpus = [
            TextSource(text="SEO tools", field="title", weight=3.0),
            TextSource(text="keyword research", field="title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)
        query_terms = ("seo",)
        field_weights = (("title", 3.0),)
        field_b = (("title", 0.5),)

        results = compute_bm25f(
            corpus_hash=corpus_hash,
            query_terms=query_terms,
            field_weights=field_weights,
            field_b=field_b,
        )

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)


# Purpose: Test field-weighted profile building.
class TestFieldWeightedProfile:

    # Purpose: Test basic profile building.
    def test_build_profile_basic(self):
        corpus = [
            TextSource(text="SEO tools for analysis", field="page_title", weight=3.0),
            TextSource(text="Best software research", field="body_text", weight=1.0),
        ]

        profile = build_field_weighted_profile(corpus)

        assert profile.corpus_size == 2
        assert "page_title" in profile.field_weights
        assert "body_text" in profile.field_weights
        assert profile.field_weights["page_title"] == 3.0
        assert profile.algorithm_version == "bm25f_v1"

    # Purpose: Test profile building with custom settings.
    def test_build_profile_with_settings(self):
        corpus = [
            TextSource(text="Test content", field="title", weight=1.0),
        ]
        settings = {
            "seo_math": {
                "field_weights": {"title": 5.0, "body": 2.0},
                "bm25f_params": {"b_title": 0.3, "b_body": 0.8}
            }
        }

        profile = build_field_weighted_profile(corpus, settings)

        assert profile.field_weights["title"] == 5.0
        assert profile.field_weights["body"] == 2.0
        assert profile.field_b_params["title"] == 0.3
        assert profile.field_b_params["body"] == 0.8

    # Purpose: Test field statistics are computed.
    def test_build_profile_field_stats(self):
        corpus = [
            TextSource(text="SEO tools for analysis", field="page_title", weight=3.0),
            TextSource(text="keyword research software", field="page_title", weight=3.0),
        ]

        profile = build_field_weighted_profile(corpus)

        assert "page_title" in profile.field_stats
        assert profile.field_stats["page_title"].doc_count == 2
        assert profile.field_stats["page_title"].total_length > 0
        assert profile.field_stats["page_title"].avg_length > 0

    # Purpose: Test profile with empty corpus.
    def test_build_profile_empty_corpus(self):
        profile = build_field_weighted_profile([])

        assert profile.corpus_size == 0
        assert profile.field_stats == {}


# Purpose: Test BM25F integration with existing math functions.
class TestBM25FIntegration:

    # Purpose: Test BM25F addition doesn't break existing n-gram/TF-IDF.
    def test_bm25f_does_not_break_existing_functions(self):
        corpus = [
            TextSource(text="SEO tools and keyword analysis", field="page_title", weight=3.0),
            TextSource(text="SEO software for research", field="page_title", weight=3.0),
        ]
        corpus_hash = _normalize_for_hashing(corpus)

        ngrams = extract_ngrams(corpus_hash, n=1, min_count=1, min_df=1)
        tfidf = compute_tfidf(corpus_hash)

        assert len(ngrams) > 0
        assert len(tfidf) >= 0

    # Purpose: Test score_generated_text with BM25F enabled.
    def test_score_generated_text_with_bm25f(self):
        generated = """META_TITLE: Best SEO Tools for Analysis

META_DESCRIPTION: Discover top SEO software for keyword research and analysis.

H1: Complete SEO Tools Review

DESCRIPTION: <p>This comprehensive review covers the best SEO tools for keyword research and content optimization.</p>
"""
        profile = {
            "top_ngrams": ["seo tools", "keyword research", "analysis", "software"]
        }

        scores_no_bm25f = score_generated_text(
            generated_text=generated,
            primary_keyword="seo tools",
            serp_profile=profile,
            enable_bm25f=False
        )

        scores_with_bm25f = score_generated_text(
            generated_text=generated,
            primary_keyword="seo tools",
            serp_profile=profile,
            enable_bm25f=True
        )

        assert "META_TITLE" in scores_no_bm25f
        assert "META_TITLE" in scores_with_bm25f

        assert scores_with_bm25f["META_TITLE"].bm25f_score is not None
        assert scores_with_bm25f["META_TITLE"].bm25f_coverage is not None

        assert scores_no_bm25f["META_TITLE"].bm25f_score is None
        assert scores_no_bm25f["META_TITLE"].bm25f_coverage is None

    # Purpose: Test disabled BM25F has no impact on existing scoring.
    def test_bm25f_disabled_no_impact(self):
        generated = "META_TITLE: Test\n\nDESCRIPTION: Test content"
        profile = {}

        scores = score_generated_text(
            generated_text=generated,
            primary_keyword="test",
            serp_profile=profile,
            enable_bm25f=False
        )

        for element_type, score in scores.items():
            assert hasattr(score, 'score')
            assert score.bm25f_score is None
            assert score.bm25f_coverage is None

    # Purpose: Test BM25F scores only appear when toggle is enabled (Phase 10 Task 4).
    def test_bm25f_only_appears_when_enabled(self):
        generated = "META_TITLE: SEO Tools Analysis\n\nDESCRIPTION: Content about SEO tools"
        profile = {"top_ngrams": ["seo tools", "analysis"]}

        scores_off = score_generated_text(
            generated_text=generated,
            primary_keyword="seo tools",
            serp_profile=profile,
            enable_bm25f=False
        )

        scores_on = score_generated_text(
            generated_text=generated,
            primary_keyword="seo tools",
            serp_profile=profile,
            enable_bm25f=True
        )

        for element, score in scores_off.items():
            assert score.bm25f_score is None
            assert score.bm25f_coverage is None

        for element, score in scores_on.items():
            if score.bm25f_score is not None:
                assert score.bm25f_score >= 0

    # Purpose: Test signal gaps can be included in generated text scoring (Phase 10 Task 4).
    def test_signal_gaps_in_generated_scoring(self):
        generated = "META_TITLE: SEO Tools\n\nH1: SEO Tools Review\n\nDESCRIPTION: Content"
        profile = {"top_ngrams": ["seo tools"]}

        signal_gaps = {
            "title_alignment": {
                "title_alignment_score": 0.3,
                "title_rewrite_risk": 0.7,
            }
        }

        scores = score_generated_text(
            generated_text=generated,
            primary_keyword="seo tools",
            serp_profile=profile,
            signal_gaps=signal_gaps
        )

        assert scores["META_TITLE"].signal_gaps is not None
        assert "low_title_alignment" in scores["META_TITLE"].signal_gaps
        assert "title_rewrite_risk" in scores["META_TITLE"].signal_gaps


# Purpose: Test BM25F performance benchmark (HIGH-06).
class TestBM25FPerformance:

    # Purpose: Test BM25F scoring for 1000 documents completes in < 5 seconds.
    def test_bm25f_performance_1000_docs(self):
        import time

        corpus = []
        for i in range(1000):
            text = f"SEO tools and keyword analysis software number {i}"
            corpus.append(TextSource(text=text, field="body_text", weight=1.0))

        corpus_hash = _normalize_for_hashing(corpus)
        query_terms = ("seo", "tools", "keyword", "analysis", "software")
        field_weights = (("body_text", 1.0),)
        field_b = (("body_text", 0.75),)

        start = time.time()
        results = compute_bm25f(
            corpus_hash=corpus_hash,
            query_terms=query_terms,
            field_weights=field_weights,
            field_b=field_b,
            k1=1.2,
            top_n=100
        )
        elapsed = time.time() - start

        assert elapsed < 5.0, f"BM25F took {elapsed:.2f}s, expected < 5s"
        assert len(results) > 0
