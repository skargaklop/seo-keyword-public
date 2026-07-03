#!/usr/bin/env python3
"""Quick validation for the seo-eeat-ymyl-google skill."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = [
    "SKILL.md",
    "references/qrg-page-quality.md",
    "references/ymyl-thresholds.md",
    "references/eeat-scorecard-model.md",
    "references/needs-met-and-intent.md",
    "references/qrg-metric-catalog.md",
    "references/output-contract.md",
    "scripts/extract_eeat_signals.py",
    "scripts/render_scorecard.py",
    "assets/site-scorecard-template.md",
    "assets/page-evidence-matrix-template.md",
    "assets/action-plan-template.md",
]

REQUIRED_METRIC_FIELDS = (
    "metric_id",
    "label",
    "allowed_values",
    "source_logic",
    "required_evidence",
    "report_required",
)

TEXT_FILE_SUFFIXES = {".md", ".py", ".json", ".html"}
MAX_SKILL_CHAR_COUNT = 9000


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def extract_markdown_section(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    assert_true(match is not None, f"Missing markdown section: {heading}")
    return match.group(1).strip()


def validate_required_files(base_dir: Path) -> None:
    for relative_path in REQUIRED_FILES:
        assert_true((base_dir / relative_path).exists(), f"Missing required file: {relative_path}")


def validate_metric_catalog(base_dir: Path) -> None:
    catalog_path = base_dir / "references" / "qrg-metric-catalog.md"
    text = catalog_path.read_text(encoding="utf-8")
    sections = re.findall(r"### `[^`]+`\n(?:- .+\n?)+", text)
    assert_true(sections, "Metric catalog must contain metric sections.")

    for section in sections:
        for field in REQUIRED_METRIC_FIELDS:
            assert_true(f"`{field}`:" in section, f"Metric section is missing `{field}` field.")


def validate_utf8_text_files(base_dir: Path) -> None:
    for path in base_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_FILE_SUFFIXES:
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise AssertionError(f"UTF-8 decode failed for {path.relative_to(base_dir)}: {exc}") from exc


def validate_output_contract(base_dir: Path) -> None:
    contract_text = (base_dir / "references" / "output-contract.md").read_text(encoding="utf-8")
    assert_true("## Допустимые значения по метрикам" in contract_text, "Output contract must define metric allowed values.")
    for heading in (
        "`Тип сайта / YMYL Tier`",
        "`Выборка URL`",
        "`Находки hard-gates`",
        "`Реестр QRG-метрик`",
        "`Сводка по Page Quality`",
        "`Матрица evidence`",
        "`Приоритетные действия`",
        "`Needs Met (опционально)`",
    ):
        assert_true(heading in contract_text, f"Output contract must define Russian report section label: {heading}")
    for label in (
        "`Purpose Clarity`",
        "`Overall E-E-A-T`",
        "`Needs Met`",
        "`Special Flags`",
    ):
        assert_true(label in contract_text, f"Output contract must include {label}.")


def validate_skill_rules(base_dir: Path) -> None:
    skill_text = (base_dir / "SKILL.md").read_text(encoding="utf-8")
    for phrase in (
        "`Page Quality` и `Needs Met` не смешивать",
        "hard-gate findings могут принудительно понижать итог",
    ):
        assert_true(phrase in skill_text, f"SKILL.md must include rule: {phrase}")

    lowered = skill_text.lower()
    for phrase in (
        "медицинский сайт",
        "финансовый/transactional сайт",
        "обычный контентный сайт",
        "сначала вызывай субагента",
        "пройди hard-gates",
        "явно различать `experience` и `expertise`",
        "scorecard-first",
        "полный metric register",
        ):
            assert_true(phrase in lowered, f"SKILL.md must include discovery/behavior phrase: {phrase}")


def validate_skill_structure(base_dir: Path) -> None:
    skill_text = (base_dir / "SKILL.md").read_text(encoding="utf-8")
    sections = {
        "Когда применять": extract_markdown_section(skill_text, "Когда применять"),
        "Discovery-сценарии": extract_markdown_section(skill_text, "Discovery-сценарии"),
        "Ожидаемый вход": extract_markdown_section(skill_text, "Ожидаемый вход"),
        "Workflow": extract_markdown_section(skill_text, "Workflow"),
        "Что читать": extract_markdown_section(skill_text, "Что читать"),
        "Lite Scripts": extract_markdown_section(skill_text, "Lite Scripts"),
        "Правила языка и контекста": extract_markdown_section(skill_text, "Правила языка и контекста"),
    }

    discovery = sections["Discovery-сценарии"].lower()
    for scenario in (
        "медицинский сайт",
        "финансовый/transactional сайт",
        "обычный контентный сайт",
    ):
        assert_true(scenario in discovery, f"SKILL.md must include discovery scenario: {scenario}")

    expected_inputs = sections["Ожидаемый вход"].lower()
    for input_hint in (
        "домен или список url",
        "query",
        "локальные html",
    ):
        assert_true(input_hint in expected_inputs, f"SKILL.md input section must mention: {input_hint}")

    reference_map = sections["Что читать"]
    for reference_name in (
        "references/qrg-page-quality.md",
        "references/ymyl-thresholds.md",
        "references/eeat-scorecard-model.md",
        "references/needs-met-and-intent.md",
        "references/qrg-metric-catalog.md",
        "references/output-contract.md",
    ):
        assert_true(reference_name in reference_map, f"SKILL.md must map reference: {reference_name}")

    lite_scripts = sections["Lite Scripts"]
    for script_name in (
        "scripts/extract_eeat_signals.py",
        "scripts/render_scorecard.py",
    ):
        assert_true(script_name in lite_scripts, f"SKILL.md Lite Scripts section must mention: {script_name}")

    context_rules = sections["Правила языка и контекста"].lower()
    for rule in (
        "основной текст skill-а",
        "не делать bilingual-дубли",
        "субагент",
        "сжатую сводку",
    ):
        assert_true(rule in context_rules, f"SKILL.md language/context rules must mention: {rule}")


def validate_reference_coverage(base_dir: Path) -> None:
    ymyl_text = (base_dir / "references" / "ymyl-thresholds.md").read_text(encoding="utf-8").lower()
    for phrase in (
        "health",
        "finance",
        "legal",
        "safety",
        "civic",
        "shopping/transactions",
    ):
        assert_true(phrase in ymyl_text, f"ymyl-thresholds.md must explicitly cover category: {phrase}")


def validate_frontmatter_description(base_dir: Path) -> None:
    skill_text = (base_dir / "SKILL.md").read_text(encoding="utf-8")
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---", skill_text, re.DOTALL)
    assert_true(frontmatter_match is not None, "SKILL.md must start with frontmatter.")

    frontmatter = frontmatter_match.group(1)
    description_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    assert_true(description_match is not None, "SKILL.md frontmatter must include description.")

    description = description_match.group(1)
    for phrase in (
        "E-E-A-T",
        "YMYL",
        "Google Search Quality Rater Guidelines",
        "Page Quality",
        "Needs Met",
    ):
        assert_true(phrase in description, f"SKILL.md description must include discovery phrase: {phrase}")


def validate_workflow_order(base_dir: Path) -> None:
    skill_text = (base_dir / "SKILL.md").read_text(encoding="utf-8").lower()
    workflow_match = re.search(r"## workflow\s+(.*?)(?:\n## |\Z)", skill_text, re.DOTALL)
    assert_true(workflow_match is not None, "SKILL.md must contain a Workflow section.")
    workflow_text = workflow_match.group(1)
    ordered_phrases = (
        "сначала вызывай субагента",
        "пройди hard-gates",
        "присвой `page quality`",
        "заполни e-e-a-t scorecard",
        "отдельно оцени `needs met`",
    )
    positions = [workflow_text.find(phrase) for phrase in ordered_phrases]
    assert_true(all(position >= 0 for position in positions), "SKILL.md workflow phrases must all be present.")
    assert_true(
        positions == sorted(positions),
        "SKILL.md workflow must keep subagent -> hard-gates -> Page Quality -> E-E-A-T -> Needs Met order.",
    )


def validate_token_economy(base_dir: Path) -> None:
    skill_text = (base_dir / "SKILL.md").read_text(encoding="utf-8")
    assert_true(
        len(skill_text) <= MAX_SKILL_CHAR_COUNT,
        f"SKILL.md must stay compact and under {MAX_SKILL_CHAR_COUNT} characters.",
    )


def validate_template_sections(base_dir: Path) -> None:
    template_text = (base_dir / "assets" / "site-scorecard-template.md").read_text(encoding="utf-8")
    for heading in (
        "# Тип сайта / YMYL Tier",
        "# Выборка URL",
        "# Находки hard-gates",
        "# Реестр QRG-метрик",
        "# Сводка по Page Quality",
        "# E-E-A-T Scorecard",
        "# Needs Met (опционально)",
        "# Матрица evidence",
        "# Приоритетные действия",
    ):
        assert_true(heading in template_text, f"Scorecard template is missing heading: {heading}")

    evidence_template = (base_dir / "assets" / "page-evidence-matrix-template.md").read_text(encoding="utf-8")
    assert_true(
        "# Матрица evidence" in evidence_template,
        "Evidence matrix template must be a standalone deliverable with its own heading.",
    )
    assert_true(
        "{{EVIDENCE_TABLE}}" in evidence_template,
        "Evidence matrix template must include evidence table placeholder.",
    )


def run_fixture_tests(base_dir: Path) -> None:
    subprocess.run(
        [sys.executable, str(base_dir / "scripts" / "fixtures" / "run_fixture_tests.py")],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick validation for seo-eeat-ymyl-google.")
    parser.add_argument("--skip-fixtures", action="store_true", help="Skip fixture smoke tests.")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    validate_required_files(base_dir)
    validate_utf8_text_files(base_dir)
    validate_metric_catalog(base_dir)
    validate_output_contract(base_dir)
    validate_skill_rules(base_dir)
    validate_skill_structure(base_dir)
    validate_reference_coverage(base_dir)
    validate_frontmatter_description(base_dir)
    validate_workflow_order(base_dir)
    validate_token_economy(base_dir)
    validate_template_sections(base_dir)

    if not args.skip_fixtures:
        run_fixture_tests(base_dir)

    print("Quick validation passed.")


if __name__ == "__main__":
    main()
