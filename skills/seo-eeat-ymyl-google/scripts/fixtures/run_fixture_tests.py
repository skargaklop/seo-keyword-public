#!/usr/bin/env python3
"""Smoke tests for seo-eeat-ymyl-google scripts."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def count_unescaped_pipes(line: str) -> int:
    return len(re.findall(r"(?<!\\)\|", line))


def extract_section(text: str, heading: str, next_heading: str | None = None) -> str:
    start = text.index(heading)
    end = text.index(next_heading, start) if next_heading and next_heading in text[start + len(heading) :] else len(text)
    return text[start:end]


def run_command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def main() -> None:
    fixtures_dir = Path(__file__).resolve().parent
    scripts_dir = fixtures_dir.parent

    extract_script = scripts_dir / "extract_eeat_signals.py"
    render_script = scripts_dir / "render_scorecard.py"
    quick_validate_script = scripts_dir.parent / "quick_validate.py"

    temp_root = Path(tempfile.mkdtemp(prefix="seo-eeat-fixtures-"))
    extracted_json = temp_root / "_extracted.json"
    scorecard_md = temp_root / "_site-scorecard.md"
    evidence_md = temp_root / "_page-evidence-matrix.md"
    scorecard_from_extract_md = temp_root / "_site-scorecard-from-extract.md"

    try:
        subprocess.run(
            [
                sys.executable,
                str(extract_script),
                "--source",
                str(fixtures_dir / "ymyl-transactional.html"),
                "--source",
                str(fixtures_dir / "informational-authorship.html"),
                "--source",
                str(fixtures_dir / "spammy-deceptive.html"),
                "--output",
                str(extracted_json),
            ],
            check=True,
        )

        extracted = json.loads(extracted_json.read_text(encoding="utf-8"))
        assert_true(len(extracted["pages"]) == 3, "Extractor must return three pages.")

        authored = next(page for page in extracted["pages"] if "informational-authorship" in page["url"])
        spammy = next(page for page in extracted["pages"] if "spammy-deceptive" in page["url"])
        transactional = next(page for page in extracted["pages"] if "ymyl-transactional" in page["url"])

        assert_true(authored["author"]["has_person_schema"], "Authorship fixture should expose Person schema.")
        assert_true(authored["citations"]["citation_count"] >= 2, "Authorship fixture should expose citations.")
        assert_true(transactional["organization"]["has_service_schema"], "Transactional fixture should expose service schema.")
        assert_true(spammy["ui_risk_hints"]["clickbait_title"], "Spam fixture should expose clickbait title risk.")
        assert_true(spammy["ui_risk_hints"]["misleading_cta_hits"] >= 1, "Spam fixture should expose CTA risk.")
        assert_true(
            transactional["page_role_hint"] == "money_or_transaction",
            "Transactional fixture should infer a money_or_transaction role from page signals.",
        )
        assert_true(
            authored["page_role_hint"] == "informational",
            "Informational authorship fixture should infer an informational role from page signals.",
        )
        assert_true(
            spammy["page_role_hint"] == "money_or_transaction",
            "Spam/deceptive loan fixture should still infer a money_or_transaction role.",
        )

        skill_text = (scripts_dir.parent / "SKILL.md").read_text(encoding="utf-8")
        assert_true(
            "Google Search Quality Rater Guidelines" in skill_text.split("---", 2)[1],
            "SKILL.md frontmatter description must include Google Search Quality Rater Guidelines for discovery.",
        )

        nested_author_html = textwrap.dedent(
            """
            <html><head><script type="application/ld+json">{
              "@context":"https://schema.org",
              "@type":"Article",
              "author":{
                "@type":"Person",
                "name":"Dr. Jane Doe",
                "sameAs":["https://linkedin.com/in/janedoe"],
                "jobTitle":"Cardiologist"
              }
            }</script></head><body><article><h1>Test</h1></article></body></html>
            """
        ).strip()
        nested_source = temp_root / "_nested-author.html"
        nested_output = temp_root / "_nested-author.json"
        nested_source.write_text(nested_author_html, encoding="utf-8")
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(extract_script),
                    "--source",
                    str(nested_source),
                    "--output",
                    str(nested_output),
                ],
                check=True,
            )
            nested = json.loads(nested_output.read_text(encoding="utf-8"))["pages"][0]["author"]
            assert_true(
                "https://linkedin.com/in/janedoe" in nested["same_as"],
                "Nested author schema should preserve sameAs links.",
            )
            assert_true(
                "Cardiologist" in nested["credential_hints"],
                "Nested author schema should preserve credential hints.",
            )
        finally:
            for path in (nested_source, nested_output):
                if path.exists():
                    path.unlink()

        nested_author_array_html = textwrap.dedent(
            """
            <html><head><script type="application/ld+json">{
              "@context":"https://schema.org",
              "@type":"Article",
              "author":[
                {
                  "@type":"Person",
                  "name":"Dr. Jane Doe",
                  "sameAs":["https://linkedin.com/in/janedoe"],
                  "jobTitle":"Cardiologist"
                },
                {
                  "@type":"Person",
                  "name":"Dr. John Roe",
                  "sameAs":["https://example.com/john-roe"],
                  "jobTitle":"Medical Reviewer"
                }
              ]
            }</script></head><body><article><h1>Test</h1></article></body></html>
            """
        ).strip()
        nested_array_source = temp_root / "_nested-author-array.html"
        nested_array_output = temp_root / "_nested-author-array.json"
        nested_array_source.write_text(nested_author_array_html, encoding="utf-8")
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(extract_script),
                    "--source",
                    str(nested_array_source),
                    "--output",
                    str(nested_array_output),
                ],
                check=True,
            )
            nested_array = json.loads(nested_array_output.read_text(encoding="utf-8"))["pages"][0]["author"]
            assert_true(
                "https://linkedin.com/in/janedoe" in nested_array["same_as"]
                and "https://example.com/john-roe" in nested_array["same_as"],
                "Author arrays should preserve sameAs links for each Person.",
            )
            assert_true(
                "Cardiologist" in nested_array["credential_hints"]
                and "Medical Reviewer" in nested_array["credential_hints"],
                "Author arrays should preserve credential hints for each Person.",
            )
        finally:
            for path in (nested_array_source, nested_array_output):
                if path.exists():
                    path.unlink()

        ukrainian_trust_html = textwrap.dedent(
            """
            <html>
              <head>
                <title>Про нас - Тестовий магазин</title>
                <meta name="description" content="Інформація про компанію та умови співпраці" />
              </head>
              <body>
                <nav>
                  <a href="/pro-nas/">Про нас</a>
                  <a href="/kontakty/">Контакти</a>
                  <a href="/dostavka-oplata/">Доставка і оплата</a>
                  <a href="/obmin-i-povernennya/">Обмін та повернення</a>
                </nav>
                <h1>Про нас</h1>
                <p>Ми допомагаємо бізнесу з пакуванням та доставкою.</p>
              </body>
            </html>
            """
        ).strip()
        ukrainian_trust_source = temp_root / "_ukrainian-trust.html"
        ukrainian_trust_output = temp_root / "_ukrainian-trust.json"
        ukrainian_trust_source.write_text(ukrainian_trust_html, encoding="utf-8")
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(extract_script),
                    "--source",
                    str(ukrainian_trust_source),
                    "--output",
                    str(ukrainian_trust_output),
                ],
                check=True,
            )
            ukrainian_trust_page = json.loads(ukrainian_trust_output.read_text(encoding="utf-8"))["pages"][0]
            trust_pages = ukrainian_trust_page["links"]["trust_pages"]
            assert_true(
                ukrainian_trust_page["page_role_hint"] == "trust",
                "Ukrainian about page should infer a trust role.",
            )
            assert_true("/pro-nas/" in trust_pages["about"][0], "Ukrainian about links should map to about trust pages.")
            assert_true("/kontakty/" in trust_pages["contact"][0], "Ukrainian contact links should map to contact trust pages.")
            assert_true(
                "/obmin-i-povernennya/" in trust_pages["returns"][0],
                "Ukrainian return/exchange links should map to returns trust pages.",
            )
        finally:
            for path in (ukrainian_trust_source, ukrainian_trust_output):
                if path.exists():
                    path.unlink()

        shipping_source = temp_root / "_shipping-page.html"
        shipping_output = temp_root / "_shipping-page.json"
        shipping_source.write_text(
            "<html><head><title>Доставка і оплата</title></head><body><h1>Доставка і оплата</h1><p>Швидка доставка по Україні.</p></body></html>",
            encoding="utf-8",
        )
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(extract_script),
                    "--source",
                    str(shipping_source),
                    "--output",
                    str(shipping_output),
                ],
                check=True,
            )
            shipping_page = json.loads(shipping_output.read_text(encoding="utf-8"))["pages"][0]
            assert_true(
                shipping_page["spam_flags"]["spammy_phrase_hits"] == 0,
                "Words like 'доставка' must not trigger spam phrase hits.",
            )
        finally:
            for path in (shipping_source, shipping_output):
                if path.exists():
                    path.unlink()

        cp1251_source = temp_root / "_cp1251-about.html"
        cp1251_output = temp_root / "_cp1251-about.json"
        cp1251_html = (
            '<html><head><meta charset="windows-1251"><title>О компании</title></head>'
            '<body><h1>О компании</h1><a href="/kontakty/">Контакты</a></body></html>'
        )
        cp1251_source.write_bytes(cp1251_html.encode("cp1251"))
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(extract_script),
                    "--source",
                    str(cp1251_source),
                    "--output",
                    str(cp1251_output),
                ],
                check=True,
            )
            cp1251_page = json.loads(cp1251_output.read_text(encoding="utf-8"))["pages"][0]
            assert_true(cp1251_page["title"] == "О компании", "CP1251 title should decode correctly.")
            assert_true(
                cp1251_page["page_role_hint"] == "trust",
                "CP1251 about page should infer a trust role after decoding.",
            )
            assert_true(
                any("/kontakty/" in url for url in cp1251_page["links"]["trust_pages"]["contact"]),
                "CP1251 trust pages should preserve contact links after decoding.",
            )
        finally:
            for path in (cp1251_source, cp1251_output):
                if path.exists():
                    path.unlink()

        subprocess.run(
            [
                sys.executable,
                str(render_script),
                "--input",
                str(fixtures_dir / "sample_render_input.json"),
                "--output",
                str(scorecard_md),
                "--evidence-output",
                str(evidence_md),
            ],
            check=True,
        )

        scorecard_text = scorecard_md.read_text(encoding="utf-8")
        evidence_text = evidence_md.read_text(encoding="utf-8")

        for required_section in (
            "# Тип сайта / YMYL Tier",
            "# Находки hard-gates",
            "# Реестр QRG-метрик",
            "# E-E-A-T Scorecard",
            "# Needs Met (опционально)",
            "# Приоритетные действия",
        ):
            assert_true(required_section in scorecard_text, f"Missing section: {required_section}")

        for required_section in (
            "# Выборка URL",
            "# Сводка по Page Quality",
            "# Матрица evidence",
        ):
            assert_true(required_section in scorecard_text, f"Missing Russian section: {required_section}")

        assert_true(
            "| Special Flags | N/A | Porn \\| Foreign Language \\| Did Not Load \\| Upsetting-Offensive \\| N/A |"
            in scorecard_text,
            "Metrics register must render Special Flags row.",
        )

        assert_true("Purpose Clarity" in scorecard_text, "Metrics register must be rendered.")
        assert_true("Медицинский информационный сайт" in scorecard_text, "Scorecard should preserve Russian content.")
        lowered_scorecard = scorecard_text.lower()
        for expected_phrase in (
            "сильные сигналы авторства",
            "внешняя репутация требует отдельной проверки",
            "повествование на основе личного опыта",
            "schema `person`",
            "источники",
            "политика медицинской проверки",
            "роль: `общая`",
            "роль: `информационная`",
            "страницы доверия",
            "процесс проверки",
        ):
            assert_true(expected_phrase in lowered_scorecard, f"Renderer should localize narrative phrase: {expected_phrase}")

        metrics_section = extract_section(scorecard_text, "# Реестр QRG-метрик", "# Сводка по Page Quality")
        metric_rows = [
            line
            for line in metrics_section.splitlines()
            if line.startswith("|") and "Метрика" not in line and "---" not in line
        ]
        assert_true(metric_rows, "Metrics register must contain table rows.")
        for row in metric_rows:
            assert_true(
                count_unescaped_pipes(row) == 4,
                f"Metrics row must remain a 3-column markdown table row: {row}",
            )

        evidence_header = "| Сигнал | URL страницы | Наблюдаемое подтверждение | Влияние на оценку |"
        assert_true("# Матрица evidence" in evidence_text, "Evidence sidecar must render its own heading.")
        assert_true(evidence_header in scorecard_text, "Main scorecard must include evidence matrix header.")
        assert_true(evidence_header in evidence_text, "Evidence sidecar must include evidence matrix header.")

        for forbidden_phrase in (
            "Site Type:",
            "role hint:",
            "Query context:",
            "Person schema present",
            "Judgment required",
            "strong authorship signals",
            "External reputation",
            "firsthand narrative",
            "Person schema |",
            "| Citations |",
            "medical review policy",
            "роль: `generic`",
            "роль: `informational`",
            "review-процесс",
            "доверие-страницы",
        ):
            assert_true(forbidden_phrase not in scorecard_text, f"Forbidden English/auto-conclusion leaked into scorecard: {forbidden_phrase}")
            assert_true(forbidden_phrase not in evidence_text, f"Forbidden English/auto-conclusion leaked into evidence matrix: {forbidden_phrase}")

        subprocess.run(
            [
                sys.executable,
                str(render_script),
                "--input",
                str(extracted_json),
                "--output",
                str(scorecard_from_extract_md),
            ],
            check=True,
        )

        scorecard_from_extract_text = scorecard_from_extract_md.read_text(encoding="utf-8")
        assert_true(
            "| [Заполнить] | [Заполнить] | [Заполнить] | [Заполнить] |" in scorecard_from_extract_text,
            "Renderer must leave evidence placeholders when explicit evidence matrix is absent.",
        )
        assert_true(
            "Person schema present" not in scorecard_from_extract_text,
            "Renderer must not invent evidence rows from extracted signals.",
        )
        assert_true(
            "Контекст запроса отсутствует." in scorecard_text,
            "Needs Met section must clearly explain missing query context in Russian.",
        )

        trust_guard_input = temp_root / "_trust-guard-input.json"
        trust_guard_output = temp_root / "_trust-guard-output.md"
        trust_guard_payload = {
            "site_type": "Тестовый сайт",
            "ymyl_tier": "Possible YMYL",
            "sampled_urls": [{"url": "https://example.test/about", "page_role_hint": "trust"}],
            "hard_gate_findings": [],
            "metrics": {"trustworthiness": "2"},
            "page_quality_summary": {"page_quality": "Medium", "reasons": ["untrustworthy claims hurt trust"]},
            "eeat_explanations": {"trustworthiness": "untrustworthy claims hurt Trustworthiness."},
            "evidence_matrix": [
                {
                    "signal": "test_signal",
                    "page_url": "https://example.test/",
                    "observed_evidence": "untrustworthy copy",
                    "rating_impact": "hurts trust",
                }
            ],
            "priority_actions": {},
        }
        trust_guard_input.write_text(json.dumps(trust_guard_payload, ensure_ascii=False), encoding="utf-8")
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(render_script),
                    "--input",
                    str(trust_guard_input),
                    "--output",
                    str(trust_guard_output),
                ],
                check=True,
            )
            trust_guard_text = trust_guard_output.read_text(encoding="utf-8")
            assert_true("unдовериеworthy" not in trust_guard_text, "Renderer must not corrupt words containing 'trust'.")
            assert_true("Trustworthiness" in trust_guard_text, "Renderer should preserve standard metric labels in narrative text.")
            assert_true("роль: `страница доверия`" in trust_guard_text, "Renderer should localize trust page roles.")
        finally:
            for path in (trust_guard_input, trust_guard_output):
                if path.exists():
                    path.unlink()

        invalid_metrics_input = temp_root / "_invalid-metrics-input.json"
        invalid_metrics_output = temp_root / "_invalid-metrics-output.md"
        invalid_metrics_payload = {
            "site_type": "Тестовый сайт",
            "ymyl_tier": "Clear YMYL",
            "metrics": {
                "page_quality": "Superb",
                "experience": "7",
                "needs_met": "MAYBE",
            },
        }
        invalid_metrics_input.write_text(json.dumps(invalid_metrics_payload, ensure_ascii=False), encoding="utf-8")
        try:
            invalid_run = run_command(
                [
                    sys.executable,
                    str(render_script),
                    "--input",
                    str(invalid_metrics_input),
                    "--output",
                    str(invalid_metrics_output),
                ],
                check=False,
            )
            assert_true(invalid_run.returncode != 0, "Renderer must fail on invalid metric values.")
            combined_output = f"{invalid_run.stdout}\n{invalid_run.stderr}"
            for expected_fragment in ("page_quality", "experience", "needs_met"):
                assert_true(
                    expected_fragment in combined_output,
                    f"Renderer error output should mention invalid metric: {expected_fragment}",
                )
        finally:
            for path in (invalid_metrics_input, invalid_metrics_output):
                if path.exists():
                    path.unlink()

        special_flags_input = temp_root / "_special-flags-input.json"
        special_flags_output = temp_root / "_special-flags-output.md"
        special_flags_payload = {
            "site_type": "Тестовый сайт",
            "ymyl_tier": "Possible YMYL",
            "metrics": {
                "special_flags": ["Foreign Language", "Did Not Load"],
                "page_quality": "Unclear",
            },
        }
        special_flags_input.write_text(json.dumps(special_flags_payload, ensure_ascii=False), encoding="utf-8")
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(render_script),
                    "--input",
                    str(special_flags_input),
                    "--output",
                    str(special_flags_output),
                ],
                check=True,
            )
            special_flags_text = special_flags_output.read_text(encoding="utf-8")
            assert_true(
                "Foreign Language, Did Not Load" in special_flags_text,
                "Renderer must support multiple Special Flags values and render them compactly.",
            )
        finally:
            for path in (special_flags_input, special_flags_output):
                if path.exists():
                    path.unlink()

        assert_true(quick_validate_script.exists(), "quick_validate.py must exist.")
        subprocess.run([sys.executable, str(quick_validate_script), "--skip-fixtures"], check=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_skill = Path(temp_dir) / "seo-eeat-ymyl-google"
            shutil.copytree(scripts_dir.parent, temp_skill)

            skill_md = temp_skill / "SKILL.md"
            oversized_text = skill_md.read_text(encoding="utf-8") + ("\n" + ("лишний текст " * 1200))
            skill_md.write_text(oversized_text, encoding="utf-8")

            oversized_run = run_command([sys.executable, str(temp_skill / "quick_validate.py"), "--skip-fixtures"], check=False)
            assert_true(oversized_run.returncode != 0, "quick_validate should fail oversized SKILL.md files.")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_skill = Path(temp_dir) / "seo-eeat-ymyl-google"
            shutil.copytree(scripts_dir.parent, temp_skill)

            skill_md = temp_skill / "SKILL.md"
            original_text = skill_md.read_text(encoding="utf-8")
            workflow_block_match = re.search(
                r"4\. Пройди hard-gates:[^\n]+\n5\. При необходимости запусти `scripts/extract_eeat_signals.py`, чтобы получить компактный JSON по страницам\.\n6\. Присвой `Page Quality`:[^\n]+\n7\. Заполни E-E-A-T scorecard:[^\n]+\n",
                original_text,
            )
            assert_true(
                workflow_block_match is not None,
                "Fixture should find workflow lines before mutating SKILL.md order.",
            )
            wrong_order_block = (
                "4. Присвой `Page Quality`: `Lowest | Low | Medium | High | Highest`.\n"
                "5. Заполни E-E-A-T scorecard: `Experience`, `Expertise`, `Authoritativeness`, `Trustworthiness`, `Overall E-E-A-T`.\n"
                "6. Пройди hard-gates: harmful purpose, deceptive purpose/design, scaled low-value content, reputation abuse, hidden/blocked main content, unsafe sensitive-data requests, untrustworthy YMYL claims.\n"
                "7. При необходимости запусти `scripts/extract_eeat_signals.py`, чтобы получить компактный JSON по страницам.\n"
            )
            wrong_order_text = original_text.replace(workflow_block_match.group(0), wrong_order_block, 1)
            skill_md.write_text(wrong_order_text, encoding="utf-8")

            wrong_order_run = run_command([sys.executable, str(temp_skill / "quick_validate.py"), "--skip-fixtures"], check=False)
            assert_true(
                wrong_order_run.returncode != 0,
                "quick_validate should fail when hard-gates appear after Page Quality/E-E-A-T in workflow.",
            )

        print("All fixture tests passed.")
    finally:
        for path in (extracted_json, scorecard_md, evidence_md, scorecard_from_extract_md):
            if path.exists():
                path.unlink()
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
