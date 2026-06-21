# MODULE_CONTRACT: utils
# Purpose: Utility subpackage for shared helpers used across the application
# Rationale: Groups infrastructure modules (cache, cleanup, logger, validators, etc.) into one import surface
# Dependencies: utils.cache, utils.cleanup, utils.currency_rates, utils.excel_exporter, utils.file_handler, utils.google_ads_client, utils.history, utils.keyword_processor, utils.llm_handler, utils.logger, utils.pipeline, utils.rate_limiter, utils.scraper, utils.url_safety, utils.validator
# Exports: all utility modules
# LINKS: requirements.xml#UC-001, knowledge-graph.xml#MOD-001
# MODULE_MAP: utils/__init__.py
# Public Functions: (none)
# Private Helpers: (none)
# Key Semantic Blocks: block_utils_pkg_init_imports
# Critical Flows: import surface for app.py and components
# Verification: V-SUITE
# CHANGE_SUMMARY: Added module-level contracts for utils package init
