# Auto SEO Keyword Planner — Repository Guidelines

## Project

**Auto SEO Keyword Planner**

A Streamlit-based SEO keyword research application for Ukrainian/Russian/English-speaking markets. Users scrape URLs or enter seed keywords, retrieve Google Ads metrics (search volume, competition, CPC), generate semantic keywords via multi-provider LLMs, and produce search-optimized text. Includes SERP analysis to parse Google search results for competitive research, ranking intelligence, and content gap analysis.

**Core Value:** Provide SEO specialists with verifiable metrics, competitive SERP intelligence, and AI-accelerated content generation through rapid, reproducible workflows.

### Environment & host safety

- **Tech Stack:** Python 3.12 + Streamlit.
- **GRACE Framework:** All architecture, modules, and changes adhere to GRACE governance (`MODULE_CONTRACT`, `FUNCTION_CONTRACT`, semantic boundary blocks, and documentation artifacts in `/docs`).
- **API Keys & Credentials:** Manage SERP and LLM provider credentials via local `.env` (`SERPER_API_KEY`, `SERPAPI_KEY`, `BRAVE_SEARCH_API_KEY`, `HASDATA_API_KEY`, etc.). Restrict credentials, API keys, and sensitive tokens to runtime retrieval from environment variables or ignored configuration files.
- **PowerShell Syntax:** Windows/PowerShell is the primary host environment. Use native PowerShell separators (`;`, separate lines, or explicit `if` statements).
- **Encoding & Text Safety:** Execute Python operations handling Cyrillic text with `PYTHONUTF8=1`. Store Cyrillic-containing files with UTF-8 BOM (`utf-8-sig`) and CRLF line endings. Read JSON and Markdown files with UTF-8 BOM awareness. Execute Cyrillic text operations via dedicated Python scripts with `PYTHONUTF8=1`.

## Coding patterns & conventions

- **Provider Registry:** Register external providers in Python module-level constants and approved registry dictionaries.
- **State Management:** Use Streamlit `st.session_state` exclusively for application state.
- **Data Formats:** Process tabular data using pandas DataFrames. Use `openpyxl` for Excel generation and diffing.
- **Localization (i18n):** Dict-based translation system in `config/i18n.py` with `ru`, `uk`, and `en` keys following the `<area>_<description>` naming standard. Complete coverage across all three locales is a mandatory quality gate before integrating UI changes.
- **Configuration & Limits:** Store static defaults in `settings.yaml`, runtime secrets in `.env`/`secrets.toml`, and provider sets in Python constants. Expose operational limits, thresholds, retry counts, batch sizes, and page counts in configuration or settings UI.
- **Binary Compilation & Executable Runners:** Prioritize producing standalone compiled binaries for executable tools, CLIs, and application entry points across target ecosystems whenever supported:
  - *Python*: Produce standalone compiled binaries or packaged executables using `uv` (such as `uv build`, single-file distributions, or embedded bundles) where feasible.
  - *TypeScript / Node.js*: Produce standalone compiled executable binaries using native single-binary tooling (such as `bun build --compile`, Deno compile, or Node.js Single Executable Applications) where feasible.
  - *Golang*: Compile native standalone binaries using `go build` with release flags (e.g., `-ldflags="-s -w"`).
  - *Fallback Standalone Runners*: Where compiling a standalone binary is unsupported or infeasible, generate robust standalone `.bat` runner scripts on Windows, configuring multi-tier runtime discovery, `PYTHONUTF8=1`, `chcp 65001`, and bilingual (English/Russian) diagnostic messages.
- **Standalone Launchers:** Provide standalone `.bat` launchers with multi-tier Python discovery, `PYTHONUTF8=1`, `chcp 65001`, and bilingual (English/Russian) diagnostics.
- **Core Immutability & SOLID Extension:** Treat upstream engines, vendor cores, framework libraries, and installed dependencies (e.g., installed `site-packages`) as strictly read-only. Implement all customizations, new behaviors, and integrations through public extension points—plugins, adapters, addons, modules, hooks, and external wrappers—in strict accordance with SOLID architecture principles (especially the Open/Closed Principle).
- **Contract-Driven Guardrails (CDD):** Protect application boundaries and internal state against malformed payloads and LLM hallucinations by enforcing strict schema validation (`pydantic` v2) at entry and exit points.
- **Observability-Driven Development (ODD) & Rich Logging:** Embed runtime observability directly into code: structured JSON telemetry (`structlog` or standard library logging with JSON formatters), plain-language 3-part error messages (what failed, why, recovery action), trace context propagation (`trace_id`, `span_id`), and machine-readable diagnostics.
- **Automated Pre-Commit Quality Gates:** Establish automated pre-commit hook scripts (or project GitHub check scripts) enforcing all required linters, formatters, type verifications, and regression tests tailored to project requirements, guaranteeing that code passes all automated checks prior to commit creation.
- **Agent Client Protocol (ACP) Tooling Compliance:** When authoring or extending arbitrary tools, integration servers, or bridges for AI agents, strictly comply with Agent Client Protocol (ACP) schema contracts and specifications.
- **Evidence-Backed Reporting & Direct Citations:** Back all analysis, findings, progress updates, and completion claims in user reports with concrete evidence, including direct quotes, code excerpts, reproducible commands, and clickable markdown links to exact source files and line ranges.
- **Proactive Context Management:** Manage context window headroom proactively using compaction commands before degradation occurs. Structure continuation summaries across defined anchors: primary objective, touched files, verified state, active constraints, and immediate next steps.
- **Exhaustive Deprecation & Reference Cleanup:** When deleting, renaming, or migrating a feature, provider, or setting, reconcile all references comprehensively across registry definitions, UI widgets, settings schemas, localization files, imports, and documentation.
- **Source File Length:** Maintain all source files under 1000 lines.

## Multi-agent delegation and handoffs

- **Task Decomposition & Model Routing:** The main orchestrator focuses on task decomposition into small, measurable, short-timed tasks with explicit allowed paths, acceptance criteria, and stop conditions. Spawn subagents by default with clean, fresh context windows and a shared repository handoff file. By default, subagents use model `flash-combined` (preferred for decomposed, short-timed tasks, exploration, and standard code edits) and `heavy-combined` for heavy tasks (complex logic, large multi-file refactoring, deep architectural reasoning) without explicit user instructions.
- **Path-Bounded Scopes:** Assign subagents strict directory and file boundaries. Subagents operate strictly as leaf workers within their assigned scope without spawning recursive workers.
- **Read-Only Scopes:** Restrict investigation and review subagents strictly to analysis and inspection, dispatching them with read-only allowed tools wherever possible.
- **Subagent Feedback Persistence:** When dispatching a subagent, require difficulty/pitfall feedback and save it in `[[EXPERIENCE.md]]` in the root project folder near `[[AGENTS.md]]`/`[[CLAUDE.md]]`. The orchestrator reports subagent difficulties and pitfalls to the user.
- **Output Verification & Waiting:** Await complete execution of all delegated workers, verify their tangible on-disk outputs and logs, and confirm final status only after all worker processes have concluded.

## Engineering principles

GRACE planning and code design explicitly respect DRY, KISS, YAGNI, SOLID, CRAP avoidance, and God object / SRP control before approving architecture, contracts, steps, or execution packets.

- **DRY:** Remove duplication only when the shared responsibility is real, named, and verified.
- **KISS:** Choose the smallest understandable module shape that satisfies approved requirements.
- **YAGNI:** Exclude speculative features, future-proofing, unused interfaces, and configurable knobs.
- **CRAP avoidance:** Reduce risky complexity with small verified steps instead of adding abstractions around untested behavior.
- **God object / SRP:** Treat mixed dependency clusters, broad public APIs, and unrelated reasons to change as God object signals. Extract only when target units have one clear responsibility and verification can prove behavior was preserved.
- **SOLID:** Plan modules around one reason to change, prefer extension through approved contracts or adapters, preserve substitutable implementations, keep public interfaces narrow, and wire concrete dependencies at the edge.
- **Tradeoffs:** Balance SOLID and DRY against KISS and YAGNI to preserve simplicity. If SRP suggests splitting a God object, plan characterization tests, coverage, or narrower verification first.

## Verification & quality strategy

- **Modern Verification Over Legacy TDD:** Direct all verification efforts toward Spec-Driven contracts, Observability (ODD), and real End-to-End (E2E) execution paths. Retain existing repository test suites strictly as regression baselines by executing them to confirm backward compatibility.
- **Structural Code Discovery:** Leverage structural indexing tools (`ast-index`, `graphify`, `tree-sitter`) for precise structural codebase comprehension, dependency mapping, and relationship exploration prior to executing modifications.
- **Verification Depth:** End-to-End (E2E) verification across complete user and API paths is explicitly encouraged and permitted as the definitive validation standard. Execute genuine CLI commands, API requests, database queries, or browser sessions with reproducible outputs and verifiable evidence.
- **Playwriter & Mandatory Screenshots:** For browser testing, E2E checks, and DOM interaction, use the **Playwriter CLI** (`playwriter`) with the `playwriter` skill whenever installed. Capture and provide screenshots of completed tasks and final interface states as definitive visual evidence upon completing any UI or browser-verifiable work.
- **Web Project Performance & Lighthouse Standards:** When working on web projects, actively utilize Chrome DevTools and run Lighthouse audits, optimizing bundle sizes, assets, rendering performance, and Core Web Vitals to achieve top performance ratings (90+).
- **Frictionless Anti-Bot Form Protection:** When developing web forms, implement modern anti-bot practices that remain invisible to human users (such as honeypot fields, time-gate submission thresholds, cryptographic proof-of-work puzzles, or background behavioral heuristics), sustaining rapid page load speeds and seamless user experience.
- **Minimum check:** When omitting a full test run, execute `python -m py_compile` on modified files and inspect references.
- **Preferred Quality, Linting & Observability Stacks by Ecosystem:**
  - **Python:**
    - *Linter & Formatter*: `ruff`. Projects configure `pyproject.toml` to block blind `except Exception:` and silent pass anti-patterns (e.g., `BLE001`, `S110`), using at minimum:
      ```toml
      [tool.ruff.lint]
      extend-select = ["B", "BLE001", "C4", "PERF", "RUF043", "S110", "SIM", "UP"]
      ```
    - *Type Checking*: `ty` or `pyright` / `mypy`.
    - *Security & Auditing*: `bandit` (AST security analysis), `pip-audit` (dependency vulnerability scanning).
    - *Structured Logging & Observability*: `structlog` (with OpenTelemetry JSON conventions) or native `logging` with structured JSON formatters.
    - *Invariant Testing & Mutation*: `hypothesis` (Property-Based Testing for state invariants), `schemathesis` (OpenAPI contract-based property testing), `mutmut` (mutation testing to expose dead/tautological code).
    - *Contract & Schema Linting*: `spectral` for OpenAPI specification linting.
    - *Browser & E2E*: `playwriter` CLI (if installed).
  - **TypeScript / Node.js:**
    - *Linter & Formatter*: `biome` or `oxlint` (fastest) / `eslint` + `prettier`.
    - *Type Checking*: `tsc --noEmit`.
    - *Runtime Contracts & Validation*: `zod` or `arktype` (high-performance runtime parsing).
    - *Structured Logging & Observability*: `pino` (high-performance JSON logger) or `@opentelemetry/api` + SDK tracing.
    - *Invariant Testing & Mutation*: `fast-check` (Property-Based Testing for domain invariants), `stryker` (`@stryker-mutator/core` for mutation coverage).
    - *Browser & E2E*: `playwriter` CLI (if installed).
  - **Golang:**
    - *Linter & Static Analysis*: `golangci-lint run` (with `govet`, `staticcheck`, `errcheck`, `revive`).
    - *Structured Logging & Observability*: `log/slog` (standard library structured logger) or `uber-go/zap` + OpenTelemetry Go SDK (`go.opentelemetry.io/otel`).
    - *Invariant Testing & Fuzzing*: `go test -fuzz` (native Go fuzzing for boundary invariant exploration) or `pgregory.net/rapid` (Property-Based Testing).
    - *Integration & E2E*: `testcontainers-go` for containerized service dependencies, `playwriter` CLI for web UI.
  - **AI & LLM-Specific Observability & Evaluation:**
    - *Agent Tracing & Telemetry*: Integrate `langfuse` (self-hosted MIT) or `arize-phoenix` to trace LLM execution graphs, prompt chains, token usage, latency, and cost context.
    - *Prompt Regression & Evaluation*: Use `promptfoo` for automated CLI-based prompt regression tests, assertion evaluations, and LLM output guardrail checks.

## Core coding directives

- Use `PYTHONUTF8=1` for any Python script handling Cyrillic on Windows.
- Provide standalone `.bat` launchers for every Python project.
- Confirm dependency installation preferences with user; default to global installation where standard.
- Obtain explicit approval before executing infrastructure changes (SSH host, cron, services).
- Evaluate 3, 5, or 7 possible causes for a problem or ways to resolve a user request before acting.
- Apply Targeted Edits (Narrow Patching): Keep file diffs minimal and precise, preserving existing file structure, JSON schemas, and formatting.
- Execute linters (e.g. Ruff) and regression tests on touched code before finishing tasks.
- Ensure all delegated subagents have fully concluded before finalizing work.
- Maintain GRACE artifacts continuously synchronized with code when the GRACE framework is active in the project.
- Expose operational limits, thresholds, retry counts, and page sizes in configuration or settings.
- Serialize write operations to shared files to guarantee thread and process safety.
- Restrict credentials, keys, and tokens to runtime retrieval from environment variables or ignored configuration.
- Obtain explicit approval before remote host commands or infrastructure modifications.
- Treat installed library files in `site-packages` as strictly read-only; resolve limitations via external adapters.
- Wrap installed tools externally rather than patching their source code.
- Report completion strictly for verified on-disk or in-system states backed by tangible evidence.
- Confine investigations to evidence-backed paths.
- Maintain critical infrastructure services operational while resolving resource limits.
- Maintain all source files under 1000 lines.

## Git commits & repository hygiene

- Implement changes in small, incremental steps and create commits after each verified step when authorized.
- Inspect exact staged paths before committing (`git status` and `git diff --staged`) to confirm only authorized project files are staged.
- Restrict commits to project code, keeping credentials, personal data, and live databases local.
- Use standard conventional commit types (`fix:`, `feat:`, `chore:`, `docs:`, `refactor:`, `test:`) with the user as the sole contributor.

## Known landmines & diagnostics

- **Cyrillic encoding corruption (mojibake):** Set `PYTHONUTF8=1`, write files as UTF-8 BOM, and run `dos2unix` on scripts transferred Windows→Linux.
- **Integration gaps with green unit tests:** Verify features end-to-end across complete execution paths, UI interactions, and export pipelines.
- **Stale config surviving feature removal:** Follow the feature deprecation checklist: reconcile registry entries, settings, i18n dictionaries, UI components, imports, documentation, and tests.
- **Subagent scope bounding:** Confine subagent prompts to explicit allowed directories and repository scopes.
- **Config setting appearing in multiple places with conflicting values:** Run configuration audit scripts to check duplicate, conflicting, stale, or orphaned categories across YAML, Python constants, i18n dictionaries, and UI widgets. Follow the stale provider removal checklist across registry, settings, i18n, UI, imports, docs, and tests.

## Communication style notes

- **Language:** English is the primary language for interactions and documentation.
- **Short imperative prompts:** "fix it", "continue", "remove", "approve, implement", "1", "yes", "Done" assume prior turn context.
- **"Next." / "Next task.":** Task separators within a session.
- **Approval gate language:** Wait for explicit approval ("approve, implement", "go ahead") before remote infrastructure modifications.
- **Direct feedback reception:** When receiving forceful feedback, immediately halt the current approach, acknowledge the specific issue, and execute the correction directly.
- **Honesty & Transparency:** State clearly when information is missing or uncertain. Rely on verified facts rather than speculation. Report and correct mistakes immediately.
