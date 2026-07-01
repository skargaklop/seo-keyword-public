# MODULE_CONTRACT: cli
# Purpose: Headless, Streamlit-independent command-line interface package for the SEO planner.
# Rationale: docs/cli-plan.md — a fully independent CLI that orchestrates the project's utils/ stage
#   callables without ever importing streamlit or the Streamlit-coupled modules (utils.pipeline,
#   config.i18n).
# Dependencies: ONLY the 7 streamlit-free utils/ modules (validator, scraper, llm_handler,
#   google_ads_client, serp_client, google_trends_client, excel_exporter) + config.settings +
#   utils.logger. NEVER streamlit, utils.pipeline, or config.i18n.
# Exports: cli.main (entry), cli.pipeline, cli.merge, cli.output, cli.checkpoint, cli.registration.
# LINKS: knowledge-graph.xml#MOD-032, docs/cli-plan.md
# MODULE_MAP: cli/__init__.py
# Public Functions: none.
# Private Helpers: none.
# Key Semantic Blocks: none.
# Critical Flows: package import -> expose CLI package boundary and implementation links for MOD-032.
# Verification: verification-plan.xml#V-18-MAIN, verification-plan.xml#V-18-PIPELINE
# CHANGE_SUMMARY: Phase A — package marker created.

"""seos-cli package: Streamlit-independent CLI for the SEO keyword planner."""
