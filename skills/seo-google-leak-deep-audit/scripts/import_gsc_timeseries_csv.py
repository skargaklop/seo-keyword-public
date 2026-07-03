#!/usr/bin/env python3
"""Import and normalize GSC time-series CSV exports."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
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


def _parse_date(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    for date_format in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, date_format).strftime("%Y-%m-%d")
        except ValueError:
            continue

    normalized = (
        value.replace("\u202f", " ")
        .replace("\u00a0", " ")
        .replace("\u2009", " ")
        .strip()
    )
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*г\.?$", "", normalized, flags=re.IGNORECASE).strip()

    month_aliases: dict[str, int] = {
        # Russian
        "янв": 1,
        "январь": 1,
        "января": 1,
        "фев": 2,
        "февр": 2,
        "февраль": 2,
        "февраля": 2,
        "мар": 3,
        "март": 3,
        "марта": 3,
        "апр": 4,
        "апрель": 4,
        "апреля": 4,
        "май": 5,
        "мая": 5,
        "июн": 6,
        "июнь": 6,
        "июня": 6,
        "июл": 7,
        "июль": 7,
        "июля": 7,
        "авг": 8,
        "август": 8,
        "августа": 8,
        "сен": 9,
        "сент": 9,
        "сентябрь": 9,
        "сентября": 9,
        "окт": 10,
        "октябрь": 10,
        "октября": 10,
        "ноя": 11,
        "нояб": 11,
        "ноябрь": 11,
        "ноября": 11,
        "дек": 12,
        "декабрь": 12,
        "декабря": 12,
        # Ukrainian
        "січ": 1,
        "січень": 1,
        "січня": 1,
        "лют": 2,
        "лютий": 2,
        "лютого": 2,
        "бер": 3,
        "березень": 3,
        "березня": 3,
        "квіт": 4,
        "квітень": 4,
        "квітня": 4,
        "трав": 5,
        "травень": 5,
        "травня": 5,
        "чер": 6,
        "черв": 6,
        "червень": 6,
        "червня": 6,
        "лип": 7,
        "липень": 7,
        "липня": 7,
        "сер": 8,
        "серп": 8,
        "серпень": 8,
        "серпня": 8,
        "вер": 9,
        "верес": 9,
        "вересень": 9,
        "вересня": 9,
        "жов": 10,
        "жовт": 10,
        "жовтень": 10,
        "жовтня": 10,
        "лис": 11,
        "лист": 11,
        "листоп": 11,
        "листопад": 11,
        "листопада": 11,
        "гру": 12,
        "груд": 12,
        "грудень": 12,
        "грудня": 12,
    }

    match = re.fullmatch(r"(\d{1,2})\s+([^\s]+)\s+(\d{4})", normalized)
    if match:
        day = int(match.group(1))
        month_raw = match.group(2).strip().lower().strip(".")
        month_token = re.sub(r"[^a-zа-яёіїєґ]+", "", month_raw)
        year = int(match.group(3))

        month = month_aliases.get(month_token)
        if month is None:
            month = month_aliases.get(month_token[:4]) or month_aliases.get(
                month_token[:3]
            )
        if month is not None:
            return f"{year:04d}-{month:02d}-{day:02d}"

    return value


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


def load_gsc_timeseries_csv(path: Path, site_origin: str | None = None) -> dict[str, Any]:
    """Load GSC date/page CSV and normalize to by_url_date buckets."""
    rows = _read_csv_rows(path)
    normalized_rows: list[dict[str, Any]] = []

    for row in rows:
        mapped: dict[str, Any] = {"source_row": row}
        for key, value in row.items():
            cleaned = _clean_header(key)
            if cleaned in {"date", "day", "дата"}:
                mapped["date"] = _parse_date(str(value))
            elif cleaned in {
                "url",
                "page",
                "pages",
                "landingpage",
                "страница",
                "страницы",
                "сторінка",
                "сторінки",
                "популярныестраницы",
                "toppages",
            }:
                mapped["url"] = _normalize_url(str(value), site_origin=site_origin)
            elif cleaned in {"clicks", "urlclicks", "клики", "кліки", "kлики"}:
                mapped["clicks"] = _to_float(str(value))
            elif cleaned in {"impressions", "показы", "покази"}:
                mapped["impressions"] = _to_float(str(value))
            elif cleaned in {"ctr"}:
                mapped["ctr"] = _to_float(str(value))
            elif cleaned in {"position", "averageposition", "позиция", "позиція"}:
                mapped["position"] = _to_float(str(value))

        mapped.setdefault("date", "")
        mapped.setdefault("url", "")
        mapped.setdefault("clicks", 0.0)
        mapped.setdefault("impressions", 0.0)
        mapped.setdefault("ctr", 0.0)
        mapped.setdefault("position", 0.0)
        normalized_rows.append(mapped)

    by_url_date: dict[str, dict[str, dict[str, float]]] = {}
    for row in normalized_rows:
        url = row.get("url", "")
        date = row.get("date", "")
        if not url or not date:
            continue
        url_bucket = by_url_date.setdefault(url, {})
        bucket = url_bucket.setdefault(
            date,
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

    for url_bucket in by_url_date.values():
        for bucket in url_bucket.values():
            rows_count = bucket.get("rows", 1.0) or 1.0
            bucket["position"] = bucket["position"] / rows_count
            clicks = bucket.get("clicks", 0.0)
            impressions = bucket.get("impressions", 0.0)
            if impressions > 0:
                bucket["ctr"] = (clicks / impressions) * 100.0
            else:
                bucket["ctr"] = bucket["ctr"] / rows_count

    return {
        "source": str(path),
        "rows": normalized_rows,
        "by_url_date": by_url_date,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import GSC time-series CSV and output normalized JSON."
    )
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--site-origin", help="Site origin, e.g. https://example.com")
    parser.add_argument("--output", type=Path, default=Path("cache/gsc_timeseries.json"))
    args = parser.parse_args()

    payload = load_gsc_timeseries_csv(args.csv_path, site_origin=args.site_origin)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved: {args.output}")
    print(f"Rows: {len(payload['rows'])}, URLs: {len(payload['by_url_date'])}")


if __name__ == "__main__":
    main()
