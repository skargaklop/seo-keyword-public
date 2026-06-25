# Test: results.py pure helpers — scroll-to-top markup + export filename suffix
# MODULE_CONTRACT: tests/test_results_helpers
# Purpose: Verify the pure UI/filename helpers added for the scroll-to-top button
#          and input-aware export filenames.
# Rationale: These helpers are pure (no Streamlit runtime needed for the slug; the
#            markup helper returns a static string), so they are unit-testable directly.
# Dependencies: components.results
# Exports: pytest tests
# Verification: python -m pytest tests/test_results_helpers.py -q
# CHANGE_SUMMARY: New — covers _scroll_to_top_markup and build_export_filename_suffix.


from components.results import _scroll_to_top_markup, build_export_filename_suffix


# --- Scroll-to-top markup ---------------------------------------------------

class TestScrollToTopMarkup:
    # Purpose: The markup must include a button, the smooth-scroll call, and the
    # localized label (used for both aria-label and title).
    def test_scroll_to_top_markup_contains_button_and_scrollto(self):
        markup = _scroll_to_top_markup(label="Наверх")

        assert "scrollTo" in markup
        assert "<button" in markup
        assert "Наверх" in markup

    def test_scroll_to_top_markup_uses_console_namespace(self):
        # Consistency: stays inside the existing .console-* CSS namespace.
        assert "console-scrolltop" in _scroll_to_top_markup(label="x")


# --- Export filename suffix -------------------------------------------------

class TestBuildExportFilenameSuffix:
    # Purpose: Single keyword input becomes a snake_case infix with a leading underscore.
    def test_suffix_single_keyword(self):
        assert build_export_filename_suffix(["купить собаку"]) == "_купить_собаку"

    # Purpose: URL input has its scheme stripped, path separators become underscores.
    def test_suffix_single_url(self):
        result = build_export_filename_suffix(["https://example.com/products/dog-food"])
        assert result == "_example_com_products_dog_food"

    # Purpose: Several inputs keep only the first slug + a "plus <count-1>" tail.
    def test_suffix_multiple_appends_plus_count(self):
        assert build_export_filename_suffix(["alpha", "beta", "gamma"]) == "_alpha_plus_2"

    # Purpose: No inputs ⇒ empty infix (existing filename behavior unchanged).
    def test_suffix_empty_returns_empty_string(self):
        assert build_export_filename_suffix([]) == ""
        assert build_export_filename_suffix(None) == ""

    # Purpose: Long input is truncated to keep the Windows path under control.
    def test_suffix_truncates_long_input(self):
        result = build_export_filename_suffix(["x" * 200])
        # Infix is "_" + slug (+ optional _plus_N); slug body must be ≤ 40 chars.
        body = result[1:]  # strip leading underscore
        assert len(body) <= 40
        assert set(body) <= set("x")

    # Purpose: Punctuation collapsed, lowercased.
    def test_suffix_lowercases_and_collapses_separators(self):
        assert build_export_filename_suffix(["Hello,,  World!!"]) == "_hello_world"

    # Purpose: Input that slugifies to nothing still yields an empty infix.
    def test_suffix_only_punctuation_returns_empty(self):
        assert build_export_filename_suffix(["!!!"]) == ""
