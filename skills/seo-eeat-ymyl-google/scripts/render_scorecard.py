#!/usr/bin/env python3
"""Render a scorecard-first markdown report from structured signals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROLE_LABELS = {
    "generic": "общая",
    "informational": "информационная",
    "money_or_transaction": "денежная/транзакционная",
    "trust": "страница доверия",
    "contact": "контакты",
}

SIGNAL_LABELS = {
    "untrustworthy_ymyl_claims": "недостоверные YMYL claims",
    "Person schema": "schema `Person`",
    "Citations": "источники",
}

LOCALIZATION_REPLACEMENTS = [
    ("strong authorship signals", "сильные сигналы авторства"),
    ("External reputation", "Внешняя репутация"),
    ("external reputation", "внешняя репутация"),
    ("firsthand narrative", "повествование на основе личного опыта"),
    ("trust pages", "страницы доверия"),
    ("trust-страницы", "страницы доверия"),
    ("доверие-страницы", "страницы доверия"),
    ("review process", "процесс проверки"),
    ("review-процесс", "процесс проверки"),
    ("medical review policy", "политика медицинской проверки"),
    ("Виден medical review", "Видна медицинская проверка"),
    ("medical review", "медицинская проверка"),
    ("Виден медицинская проверка", "Видна медицинская проверка"),
    ("reviewer", "рецензент"),
    ("journal source", "публикация в профильном издании"),
    ("guidelines", "рекомендации"),
    ("accuracy/trust", "точность и доверие"),
    ("reputation gap", "пробел в подтверждении репутации"),
    ("hurts trust", "снижает доверие"),
    ("hurt trust", "снизили доверие"),
    ("понижает trust", "понижает доверие"),
    ("Понижает trust", "Понижает доверие"),
    ("raises trust", "повышает доверие"),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def split_allowed_values(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def stringify_metric_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value)


def parse_metric_catalog(path: Path) -> list[dict[str, str]]:
    metrics: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("### `") and line.endswith("`"):
            if current:
                metrics.append(current)
            metric_id = line.removeprefix("### `").removesuffix("`")
            current = {
                "metric_id": metric_id,
                "label": metric_id,
                "allowed_values": "Unclear",
            }
            continue

        if current and line.startswith("- `") and "`:" in line:
            key_part, value_part = line[2:].split("`:", 1)
            key = key_part.removeprefix("`")
            current[key] = value_part.strip().strip("`")

    if current:
        metrics.append(current)

    return metrics


def escape_table_cell(value: Any) -> str:
    text = str(value)
    return text.replace("|", r"\|").replace("\n", "<br>")


def localize_narrative_text(value: Any) -> str:
    text = str(value)
    for source, target in LOCALIZATION_REPLACEMENTS:
        text = text.replace(source, target)
    return text


def localize_role(value: Any) -> str:
    return ROLE_LABELS.get(str(value), str(value))


def localize_signal(value: Any) -> str:
    text = str(value)
    if text in SIGNAL_LABELS:
        return SIGNAL_LABELS[text]
    return localize_narrative_text(text.replace("_", " "))


def render_list(items: list[str], fallback: str = "- [Заполнить]") -> str:
    if not items:
        return fallback
    return "\n".join(f"- {localize_narrative_text(item)}" for item in items)


def render_sampled_urls(pages: list[dict[str, Any]]) -> str:
    if not pages:
        return "- [Заполнить выборку URL]"
    return "\n".join(
        f"- `{page.get('url', 'N/A')}` — роль: `{localize_role(page.get('page_role_hint', 'generic'))}`"
        for page in pages
    )


def render_hard_gates(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "- Hard-gate findings не заполнены. Добавь только подтвержденные риски с evidence."
    lines: list[str] = []
    for finding in findings:
        lines.append(
            "- "
            + " | ".join(
                [
                    f"сигнал: {localize_signal(finding.get('signal', 'N/A'))}",
                    f"url: {finding.get('page_url', 'N/A')}",
                    f"наблюдаемое подтверждение: {localize_narrative_text(finding.get('observed_evidence', 'N/A'))}",
                    f"влияние: {localize_narrative_text(finding.get('rating_impact', 'N/A'))}",
                ]
            )
        )
    return "\n".join(lines)


def metric_default(metric_id: str) -> str:
    return "N/A" if metric_id in {"needs_met", "special_flags"} else "Unclear"


def render_metrics(metrics: dict[str, Any], catalog: list[dict[str, str]]) -> str:
    rows = [
        "| Метрика | Значение | Допустимые значения |",
        "| --- | --- | --- |",
    ]
    for item in catalog:
        metric_id = item.get("metric_id", "unknown_metric")
        label = item.get("label", metric_id)
        allowed_values = item.get("allowed_values", metric_default(metric_id))
        value = metrics.get(metric_id, metric_default(metric_id))
        rows.append(
            f"| {escape_table_cell(label)} | {escape_table_cell(stringify_metric_value(value))} | {escape_table_cell(allowed_values)} |"
        )
    return "\n".join(rows)


def special_flags_allowed(value: Any, allowed_values: str) -> bool:
    allowed = set(split_allowed_values(allowed_values))
    if isinstance(value, list):
        normalized_values = [str(item).strip() for item in value if str(item).strip()]
    else:
        normalized = str(value).strip()
        normalized_values = [item.strip() for item in normalized.split(",")] if "," in normalized else [normalized]

    if not normalized_values:
        return False
    if any(item not in allowed for item in normalized_values):
        return False
    if "N/A" in normalized_values and len(normalized_values) > 1:
        return False
    return True


def metric_value_allowed(value: Any, allowed_values: str) -> bool:
    normalized = str(value).strip()
    options = split_allowed_values(allowed_values)
    for option in options:
        if option == "0-100":
            if normalized.isdigit() and 0 <= int(normalized) <= 100:
                return True
            continue
        if normalized == option:
            return True
    return False


def validate_metrics(metrics: dict[str, Any], catalog: list[dict[str, str]]) -> None:
    invalid: list[str] = []
    catalog_by_id = {item.get("metric_id", ""): item for item in catalog}
    for metric_id, value in metrics.items():
        catalog_item = catalog_by_id.get(metric_id)
        if not catalog_item:
            continue
        allowed_values = catalog_item.get("allowed_values", metric_default(metric_id))
        if metric_id == "special_flags":
            is_allowed = special_flags_allowed(value, allowed_values)
        else:
            is_allowed = metric_value_allowed(value, allowed_values)
        if not is_allowed:
            invalid.append(f"{metric_id}={value!r} (allowed: {allowed_values})")

    if invalid:
        raise ValueError("Invalid metric values: " + ", ".join(invalid))


def render_page_quality_summary(data: dict[str, Any]) -> str:
    summary = data.get("page_quality_summary", {})
    rating = summary.get("page_quality", data.get("metrics", {}).get("page_quality", "Unclear"))
    reasons = summary.get("reasons", [])
    lines = [f"- Итоговая оценка: `{rating}`"]
    if reasons:
        lines.extend(f"- {localize_narrative_text(reason)}" for reason in reasons)
    else:
        lines.append("- Причины оценки не заполнены.")
    return "\n".join(lines)


def render_eeat(data: dict[str, Any]) -> str:
    metrics = data.get("metrics", {})
    explanations = data.get("eeat_explanations", {})
    keys = [
        ("experience", "Experience"),
        ("expertise", "Expertise"),
        ("authoritativeness", "Authoritativeness"),
        ("trustworthiness", "Trustworthiness"),
        ("overall_eeat", "Overall E-E-A-T"),
    ]
    lines: list[str] = []
    for key, label in keys:
        lines.append(f"- {label}: `{metrics.get(key, 'Unclear')}`")
        lines.append(
            f"  Обоснование: {localize_narrative_text(explanations.get(key, '[Заполнить пояснение на основе evidence]'))}"
        )
    return "\n".join(lines)


def render_optional_needs_met(data: dict[str, Any]) -> str:
    metrics = data.get("metrics", {})
    context = data.get("query_context")
    needs_met = metrics.get("needs_met", "N/A")
    if not context:
        return "- `Needs Met`: `N/A`\n- Контекст запроса отсутствует."
    return "\n".join(
        [
            f"- Контекст запроса: {localize_narrative_text(context)}",
            f"- `Needs Met`: `{needs_met}`",
            f"- Обоснование: {localize_narrative_text(data.get('needs_met_reason', '[Заполнить]'))}",
        ]
    )


def render_evidence_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Сигнал | URL страницы | Наблюдаемое подтверждение | Влияние на оценку |",
        "| --- | --- | --- | --- |",
    ]
    if not rows:
        lines.append("| [Заполнить] | [Заполнить] | [Заполнить] | [Заполнить] |")
        return "\n".join(lines)

    lines.extend(
        f"| {escape_table_cell(localize_signal(row.get('signal', 'N/A')))} | {escape_table_cell(row.get('page_url', 'N/A'))} | "
        f"{escape_table_cell(localize_narrative_text(row.get('observed_evidence', 'N/A')))} | "
        f"{escape_table_cell(localize_narrative_text(row.get('rating_impact', 'N/A')))} |"
        for row in rows
    )
    return "\n".join(lines)


def render_priority_actions(data: dict[str, Any], template: str) -> str:
    actions = data.get("priority_actions", {})
    replacements = {
        "CRITICAL_ACTIONS": render_list(actions.get("critical", actions.get("Critical", []))),
        "HIGH_ACTIONS": render_list(actions.get("high", actions.get("High", []))),
        "MEDIUM_ACTIONS": render_list(actions.get("medium", actions.get("Medium", []))),
    }
    return fill_template(template, replacements)


def fill_template(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def build_default_payload(raw: dict[str, Any]) -> dict[str, Any]:
    pages = raw.get("pages", [])
    if "metrics" in raw:
        return raw
    return {
        "site_type": raw.get("site_type", "[Заполнить тип сайта]"),
        "ymyl_tier": raw.get("ymyl_tier", "Unclear"),
        "sampled_urls": pages,
        "hard_gate_findings": raw.get("hard_gate_findings", []),
        "metrics": raw.get("metrics", {}),
        "page_quality_summary": raw.get("page_quality_summary", {}),
        "eeat_explanations": raw.get("eeat_explanations", {}),
        "query_context": raw.get("query_context"),
        "needs_met_reason": raw.get("needs_met_reason"),
        "evidence_matrix": raw.get("evidence_matrix", []),
        "priority_actions": raw.get("priority_actions", {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a scorecard-first markdown report.")
    parser.add_argument("--input", required=True, type=Path, help="Path to input JSON.")
    parser.add_argument("--output", required=True, type=Path, help="Path to site-scorecard.md.")
    parser.add_argument("--evidence-output", type=Path, help="Optional path to page-evidence-matrix.md.")
    parser.add_argument("--template", type=Path, help="Optional site scorecard template.")
    parser.add_argument("--matrix-template", type=Path, help="Optional evidence matrix template.")
    parser.add_argument("--action-template", type=Path, help="Optional priority actions template.")
    args = parser.parse_args()

    raw = load_json(args.input)
    data = build_default_payload(raw)

    base_dir = Path(__file__).resolve().parent.parent
    site_template_path = args.template or (base_dir / "assets" / "site-scorecard-template.md")
    matrix_template_path = args.matrix_template or (base_dir / "assets" / "page-evidence-matrix-template.md")
    action_template_path = args.action_template or (base_dir / "assets" / "action-plan-template.md")
    metric_catalog_path = base_dir / "references" / "qrg-metric-catalog.md"

    site_template = site_template_path.read_text(encoding="utf-8")
    matrix_template = matrix_template_path.read_text(encoding="utf-8")
    action_template = action_template_path.read_text(encoding="utf-8")
    metric_catalog = parse_metric_catalog(metric_catalog_path)
    validate_metrics(data.get("metrics", {}), metric_catalog)
    evidence_table = render_evidence_table(data.get("evidence_matrix", []))

    replacements = {
        "SITE_TYPE_SECTION": "\n".join(
            [
                f"- Тип сайта: {localize_narrative_text(data.get('site_type', '[Заполнить]'))}",
                f"- YMYL Tier: {data.get('ymyl_tier', data.get('metrics', {}).get('ymyl_tier', 'Unclear'))}",
                f"- Обоснование: {localize_narrative_text(data.get('site_type_reason', '[Заполнить пояснение на основе evidence]'))}",
            ]
        ),
        "SAMPLED_URLS": render_sampled_urls(data.get("sampled_urls", [])),
        "HARD_GATE_FINDINGS": render_hard_gates(data.get("hard_gate_findings", [])),
        "QRG_METRICS_REGISTER": render_metrics(data.get("metrics", {}), metric_catalog),
        "PAGE_QUALITY_SUMMARY": render_page_quality_summary(data),
        "EEAT_SCORECARD": render_eeat(data),
        "OPTIONAL_NEEDS_MET": render_optional_needs_met(data),
        "EVIDENCE_MATRIX": evidence_table,
        "PRIORITY_ACTIONS": render_priority_actions(data, action_template),
    }
    site_report = fill_template(site_template, replacements)

    matrix_report = fill_template(matrix_template, {"EVIDENCE_TABLE": evidence_table})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(site_report, encoding="utf-8")

    if args.evidence_output:
        args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_output.write_text(matrix_report, encoding="utf-8")


if __name__ == "__main__":
    main()
