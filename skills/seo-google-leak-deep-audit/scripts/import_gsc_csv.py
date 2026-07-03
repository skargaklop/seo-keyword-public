#!/usr/bin/env python3
"""Import and normalize Google Search Console CSV exports."""

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
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))
    return path


def _to_float(raw: str) -> float:
    if raw is None:
        return 0.0
    text = str(raw).strip().replace(" ", "").replace("%", "")
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
    sniffer = csv.Sniffer()
    delimiter = ","
    try:
        dialect = sniffer.sniff(sample, delimiters=",;\t")
        delimiter = dialect.delimiter
    except csv.Error:
        pass
    reader = csv.DictReader(lines, delimiter=delimiter)
    return [dict(row) for row in reader]


def load_gsc_csv(path: Path, site_origin: str | None = None) -> dict[str, Any]:
    """Load GSC page/query export and normalize columns."""
    rows = _read_csv_rows(path)
    normalized_rows: list[dict[str, Any]] = []

    for row in rows:
        mapped: dict[str, Any] = {"source_row": row}
        for key, value in row.items():
            cleaned = _clean_header(key)
            if cleaned in {
                "url",
                "page",
                "pages",
                "страница",
                "страницы",
                "сторінка",
                "сторінки",
                "популярныестраницы",
                "toppages",
            }:
                mapped["url"] = _normalize_url(str(value), site_origin=site_origin)
            elif cleaned in {
                "query",
                "queries",
                "запрос",
                "запросы",
                "запит",
                "запити",
                "популярныезапросы",
                "topqueries",
                "поисковыйзапросприобычномпоискеgoogle",
            }:
                mapped["query"] = (value or "").strip()
            elif cleaned in {
                "clicks",
                "клики",
                "кліки",
                "kлики",
                "кликипорезультатамобычногопоискаgoogle",
            }:
                mapped["clicks"] = _to_float(str(value))
            elif cleaned in {
                "impressions",
                "показы",
                "покази",
                "показывобычномпоискеgoogle",
            }:
                mapped["impressions"] = _to_float(str(value))
            elif cleaned in {"ctr", "ctrдлякликовпорезультатамобычногопоискаgoogle"}:
                mapped["ctr"] = _to_float(str(value))
            elif cleaned in {
                "position",
                "позиция",
                "позиція",
                "средняяпозицияврезультатахобычногопоискаgoogle",
            }:
                mapped["position"] = _to_float(str(value))

        mapped.setdefault("url", "")
        mapped.setdefault("query", "")
        mapped.setdefault("clicks", 0.0)
        mapped.setdefault("impressions", 0.0)
        mapped.setdefault("ctr", 0.0)
        mapped.setdefault("position", 0.0)
        normalized_rows.append(mapped)

    by_url: dict[str, dict[str, float]] = {}
    for row in normalized_rows:
        url = row.get("url", "")
        if not url:
            continue
        bucket = by_url.setdefault(
            url,
            {
                "clicks": 0.0,
                "impressions": 0.0,
                "ctr": 0.0,
                "position": 0.0,
                "rows": 0.0,
            },
        )
        bucket["clicks"] += float(row.get("clicks", 0.0))
        bucket["impressions"] += float(row.get("impressions", 0.0))
        bucket["ctr"] += float(row.get("ctr", 0.0))
        bucket["position"] += float(row.get("position", 0.0))
        bucket["rows"] += 1

    for bucket in by_url.values():
        rows_count = bucket.get("rows", 1.0) or 1.0
        bucket["ctr"] = bucket["ctr"] / rows_count
        bucket["position"] = bucket["position"] / rows_count

    return {
        "source": str(path),
        "rows": normalized_rows,
        "by_url": by_url,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import GSC CSV and output normalized JSON.")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--site-origin", help="Site origin, e.g. https://example.com")
    parser.add_argument("--output", type=Path, default=Path("cache/gsc.json"))
    args = parser.parse_args()

    payload = load_gsc_csv(args.csv_path, site_origin=args.site_origin)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {args.output}")
    print(f"Rows: {len(payload['rows'])}, URLs: {len(payload['by_url'])}")


if __name__ == "__main__":
    main()
