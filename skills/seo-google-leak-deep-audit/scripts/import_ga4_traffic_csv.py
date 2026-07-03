#!/usr/bin/env python3
"""Import and normalize GA4 traffic-source CSV exports."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse


def _clean_header(name: str) -> str:
    return re.sub(r"[^a-zа-я0-9]+", "", (name or "").strip().lower())


def _normalize_url(value: str, site_origin: str | None = None) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("/"):
        if not site_origin:
            return value.rstrip("/") or "/"
        value = site_origin.rstrip("/") + value
    parsed = urlparse(value if "://" in value else f"https://{value}")
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    if parsed.netloc:
        return urlunparse(
            (parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", "")
        )
    return path


def _to_float(raw: str) -> float:
    text = str(raw or "").strip().replace(" ", "").replace("%", "")
    if not text:
        return 0.0
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines:
        return []
    sample = "\n".join(lines[:25])
    delimiter = ","
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        pass
    reader = csv.DictReader(lines, delimiter=delimiter)
    return [dict(row) for row in reader]


def _read_csv_table(path: Path) -> tuple[list[list[str]], str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines:
        return [], ","
    sample = "\n".join(lines[:25])
    delimiter = ","
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        pass
    return [list(row) for row in csv.reader(lines, delimiter=delimiter)], delimiter


def _load_ga4_traffic_pivot_csv(
    path: Path, site_origin: str | None = None
) -> list[dict[str, Any]]:
    """Parse GA4 Explorations pivot export with channel-group columns (Direct, Organic, ...)."""
    table, _ = _read_csv_table(path)
    if len(table) < 3:
        return []

    header = table[0]
    subheader = table[1] if len(table) > 1 else []
    if not header or not subheader:
        return []

    metric_start = None
    for i, cell in enumerate(subheader):
        if _clean_header(cell) in {"sessions", "сеансы"}:
            metric_start = i
            break
    if metric_start is None or metric_start <= 0:
        return []

    header_clean = [_clean_header(cell) for cell in header]
    direct_idx = None
    total_idx = None
    for i, name in enumerate(header_clean):
        if name in {"direct", "прямой"}:
            direct_idx = i
        if name in {"итого", "total"}:
            total_idx = i

    rows: list[dict[str, Any]] = []
    for raw_row in table[2:]:
        if not raw_row or len(raw_row) <= metric_start:
            continue

        page_value = str(raw_row[0] or "").strip()
        if not page_value:
            continue
        if page_value.lower() in {"(not set)", "(not provided)"}:
            continue

        sessions = 0.0
        if total_idx is not None and total_idx < len(raw_row):
            sessions = _to_float(raw_row[total_idx])
        else:
            sessions = sum(_to_float(raw_row[i]) for i in range(metric_start, len(raw_row)))

        direct_sessions = 0.0
        if direct_idx is not None and direct_idx < len(raw_row):
            direct_sessions = _to_float(raw_row[direct_idx])

        url = _normalize_url(page_value, site_origin=site_origin)
        if not url:
            continue

        rows.append(
            {
                "url": url,
                "sessions": sessions,
                "direct_sessions": direct_sessions,
                "source_row": {"pivot": True, "raw": raw_row},
            }
        )

    return rows


def load_ga4_traffic_csv(path: Path, site_origin: str | None = None) -> dict[str, Any]:
    """Load GA4 traffic report with direct sessions per page."""
    rows = _read_csv_rows(path)
    normalized_rows: list[dict[str, Any]] = []

    for row in rows:
        mapped: dict[str, Any] = {"source_row": row}
        for key, value in row.items():
            cleaned = _clean_header(key)
            if cleaned in {
                "page",
                "url",
                "pagelocation",
                "pagepath",
                "страница",
                "страницы",
                "сторінка",
                "сторінки",
                "путькстранице",
                "путькстраницеиклассэкрана",
                "целеваястраница",
            }:
                mapped["url"] = _normalize_url(str(value), site_origin=site_origin)
            elif cleaned in {"sessions", "сеансы", "сеанси"}:
                mapped["sessions"] = _to_float(str(value))
            elif cleaned in {
                "directsessions",
                "directsession",
                "sessionsdirect",
                "сеансыdirect",
                "сеансыпрямой",
            }:
                mapped["direct_sessions"] = _to_float(str(value))

        mapped.setdefault("url", "")
        mapped.setdefault("sessions", 0.0)
        mapped.setdefault("direct_sessions", 0.0)
        normalized_rows.append(mapped)

    if not any(row.get("url") for row in normalized_rows):
        normalized_rows = _load_ga4_traffic_pivot_csv(path, site_origin=site_origin)

    by_url: dict[str, dict[str, float]] = {}
    for row in normalized_rows:
        url = row.get("url", "")
        if not url:
            continue
        bucket = by_url.setdefault(
            url,
            {
                "sessions": 0.0,
                "direct_sessions": 0.0,
                "direct_share": 0.0,
                "rows": 0.0,
            },
        )
        bucket["sessions"] += float(row.get("sessions", 0.0))
        bucket["direct_sessions"] += float(row.get("direct_sessions", 0.0))
        bucket["rows"] += 1

    for bucket in by_url.values():
        sessions = bucket.get("sessions", 0.0)
        if sessions > 0:
            bucket["direct_share"] = bucket.get("direct_sessions", 0.0) / sessions
        else:
            bucket["direct_share"] = 0.0

    return {
        "source": str(path),
        "rows": normalized_rows,
        "by_url": by_url,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import GA4 direct-traffic CSV and output normalized JSON."
    )
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--site-origin", help="Site origin, e.g. https://example.com")
    parser.add_argument("--output", type=Path, default=Path("cache/ga4_traffic.json"))
    args = parser.parse_args()

    payload = load_ga4_traffic_csv(args.csv_path, site_origin=args.site_origin)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved: {args.output}")
    print(f"Rows: {len(payload['rows'])}, URLs: {len(payload['by_url'])}")


if __name__ == "__main__":
    main()
