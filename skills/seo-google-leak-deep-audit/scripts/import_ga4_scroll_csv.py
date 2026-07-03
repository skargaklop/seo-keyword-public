#!/usr/bin/env python3
"""Import and normalize GA4 scroll-depth CSV exports."""

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


def load_ga4_scroll_csv(path: Path, site_origin: str | None = None) -> dict[str, Any]:
    """Load GA4 scroll event export and normalize to per-page buckets."""
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
            elif cleaned in {
                "scrollevents",
                "scroll",
                "eventcount",
                "scrollcount",
                "количествособытий",
            }:
                mapped["scroll_events"] = _to_float(str(value))
            elif cleaned in {
                "users",
                "пользователи",
                "активныепользователи",
                "користувачі",
                "активнікористувачі",
            }:
                mapped["users"] = _to_float(str(value))

        mapped.setdefault("url", "")
        mapped.setdefault("scroll_events", 0.0)
        mapped.setdefault("users", 0.0)
        normalized_rows.append(mapped)

    by_url: dict[str, dict[str, float]] = {}
    for row in normalized_rows:
        url = row.get("url", "")
        if not url:
            continue
        bucket = by_url.setdefault(
            url,
            {
                "scroll_events": 0.0,
                "users": 0.0,
                "scroll_depth_proxy": 0.0,
                "rows": 0.0,
            },
        )
        bucket["scroll_events"] += float(row.get("scroll_events", 0.0))
        bucket["users"] += float(row.get("users", 0.0))
        bucket["rows"] += 1

    for bucket in by_url.values():
        users = bucket.get("users", 0.0)
        if users > 0:
            bucket["scroll_depth_proxy"] = bucket.get("scroll_events", 0.0) / users
        else:
            bucket["scroll_depth_proxy"] = 0.0

    return {
        "source": str(path),
        "rows": normalized_rows,
        "by_url": by_url,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import GA4 scroll CSV and output normalized JSON."
    )
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--site-origin", help="Site origin, e.g. https://example.com")
    parser.add_argument("--output", type=Path, default=Path("cache/ga4_scroll.json"))
    args = parser.parse_args()

    payload = load_ga4_scroll_csv(args.csv_path, site_origin=args.site_origin)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved: {args.output}")
    print(f"Rows: {len(payload['rows'])}, URLs: {len(payload['by_url'])}")


if __name__ == "__main__":
    main()
