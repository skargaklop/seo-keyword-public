## Project

**Auto SEO Keyword Planner**

A Streamlit-based SEO keyword research tool for Ukrainian/Russian-speaking markets. Users scrape URLs or enter keywords, get Google Ads metrics (volume, competition, CPC), generate keywords via LLM, and produce SEO-optimized text. Now adding SERP analysis to parse Google search results for competitive research and content gap analysis.

**Core Value:** Help SEO specialists find the right keywords with real metrics and generate optimized content — fast.

### Environment

- **Tech Stack:** Python 3.12 + Streamlit — no framework change
- **GRACE Framework:** All new code must follow GRACE governance (MODULE_CONTRACT, FUNCTION_CONTRACT, semantic blocks and so on)
- **API keys:** SERP API keys via .env file (SERPER_API_KEY, SERPAPI_KEY, BRAVE_SEARCH_API_KEY, HASDATA_API_KEY)


## Coding patterns & conventions

- **Conventions:** Provider registrations are in Python module-level constants. i18n uses dict-based system (not gettext) with keys following `<area>_<description>` pattern.
- **State management:** Streamlit `st.session_state` for app state. No external state library.
- **Data format:** pandas DataFrames for all tabular processing. Excel via openpyxl for price monitor.
- **i18n:** Dict-based (not gettext). All UI strings go through translation dicts in `config/i18n.py` with `ru`/`uk`/`en` keys following `<area>_<description>` convention. **i18n completeness is a non-negotiable quality gate** — every new UI label must exist in all three locale dicts before merge.
- **Config:** `settings.yaml` for static defaults, `.env`/`secrets.toml` for secrets, Python constants for provider registrations. **No hardcoded values** for configurable limits — all limits (page counts, delays, thresholds) must be adjustable in settings UI.
- **Launchers:** Every Python project gets a `.bat` launcher with multi-tier Python discovery, `PYTHONUTF8=1`, `chcp 65001`, and Russian error messages. See `skills/bat-launcher-generator/`.
- **Subagent delegation:** The orchestrator dispatches scoped subagents (general-purpose with no model override = the working route). Read-only investigation subagents get explicit "Do NOT modify any files" constraints. Use subagents with cheap models like sonnet/minimax to explore and haiku/deepseek to edit code. When dispatching a subagent, the orchestrator must ask the subagent to provide feedback about what difficulties it faced, how the problems were solved, and what was inconvenient for it. This is important for task execution quality and environment improvement. Then the orchestrator reports to user about subagents difficulties and pitfalls.
- **TDD:** Tests written before code. **MANDATORY** — the user enforces this as a standing constraint.


## Architecture

Check out the GRACE artifacts in /docs folder to get a better understanding

## Coding rules (do's and don'ts)

- **DO** write tests before implementation code (TDD mandate — session `ac6169dd`, `019e8e6e`).
- **DO** use `PYTHONUTF8=1` for any Python script handling Cyrillic on Windows.
- **DO** write `.bat` launchers for every Python project. 
- **DO** create an installation script (.bat) and create venv or install globally by user's choice.
- **DO** get explicit approval before any infrastructure change (SSH host, cron, services).
- **DO** always consider 3, 5, or 7 possible causes for a problem or ways to resolve a user request before acting.
- **DO** before "stop" always check .py files via Ruff and pytest.
- **DO** keep the GRACE artifacts up to date.
- **DO** make Targeted Edits (Narrow Patching): Prefer small, accurate file edits (narrow patches) over full file rewrites. Never fully rewrite large system, JSON, or Markdown files, as this causes formatting anomalies and massive diffs.
- **DON'T** make concurrent writes to shared files. Serialize them.
- **DON'T** commit secrets.
- **For commit message use only fix/feat/chore/docs/refactor/test types. Contributor in commit options - only user without any co author**

## Known landmines and pitfalls
- **Cyrillic encoding corruption (mojibake):** Windows Python scripts that read/write Cyrillic without `PYTHONUTF8=1` will corrupt text. Also occurs in remote `.bashrc` scripts edited from Windows. **Avoid:** Always set `PYTHONUTF8=1`, write files as UTF-8 BOM, use `dos2unix` for scripts transferred Windows→Linux.
- - **Tests passing but feature broken at integration level:** Unit tests validate function correctness but miss UI/export integration gaps. **Avoid:** Always verify features end-to-end, not just via test suite .
- **Stale config surviving feature removal:** Settings keys, i18n entries, and provider registry sets persist after features are deleted. **Avoid:** Run `grep -ri '<removed_name>'` across all files after removing any feature/provider.
- **Subagents exceeding scope:** Code-editing subagents may modify files outside the intended project directory or touch `site-packages`. **Avoid:** Include explicit scope boundary and "do not modify files outside <project_dir>" in subagent prompts.

### Symptom: Config setting appears in two places with different values
**Diagnostic:** Run `python <skill_dir>/scripts/config_audit.py scan --root <project>` → check DUPLICATE/CONFLICTING/STALE/ORPHANED categories → for specific removed items, run `check-refs --key <name>` across all file types. **Root cause:** Feature migration leaves orphaned config in YAML, Python constants, i18n dicts, and UI widgets simultaneously. **Fix:** Follow stale-provider-config-removal checklist: registry → settings → i18n → UI → imports → docs → tests.

## Communication style notes

- **Bilingual Russian/Ukrainian primary, English for English-source material.** Language choice tracks the reference material, not the task. SEO tool work is English-primary. Frustration switches to Russian profanity under stress.
- **Short imperative prompts:** "fix it", "continue", "remove", "approve, implement", "1", "yes", "Done". Expects the agent to have full context from files or prior turns. No re-explanation needed.
- **"Next." / "Next task." as task separators** within a session.
- **Standing constraint suffixes:** TDD mandate, GRACE framework compliance, "NO HARDCODED VALUES", "Answer ONLY in English" (output channel restriction).
- **Approval gate language:** For infra changes, user says "approve, implement" or "go ahead" after reviewing a proposal. Don't execute without this signal.
- **Direct feedback when wrong:** Will correct forcefully. This is a signal to stop the current approach immediately, not to argue.
- **Credentials provided inline** without privacy concern for personal infrastructure.
- **Screenshots as bug evidence:** User captures FireShot screenshots of actual UI output to demonstrate discrepancies.
- **Self-correction when shown evidence:** Will acknowledge when wrong if presented with proof.
- **Honesty & Transparency:** If you don't know the answer, state that you don't know. Rely on retrieved, accurate information rather than pre-trained guesses. Never hide mistakes; report and correct them. No sycophancy.
