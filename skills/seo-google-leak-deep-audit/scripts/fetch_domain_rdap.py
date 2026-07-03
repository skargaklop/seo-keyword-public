#!/usr/bin/env python3
"""Fetch and normalize RDAP domain profile data."""

from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests


def _coerce_datetime(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _parse_domain(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        return ""
    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    domain = parsed.netloc or parsed.path
    return domain.strip().lower()


def _parse_event_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None


def extract_domain_profile_from_rdap(
    payload: dict[str, Any],
    now: str | datetime | None = None,
) -> dict[str, Any] | None:
    """Extract registration-derived age metrics from an RDAP payload."""
    if not isinstance(payload, dict):
        return None

    domain = _parse_domain(str(payload.get("ldhName") or payload.get("handle") or ""))
    events = payload.get("events")
    if not domain or not isinstance(events, list):
        return None

    registration_date_raw: str | None = None
    registration_dt: datetime | None = None
    expires_on_raw: str | None = None
    updated_on_raw: str | None = None

    for event in events:
        if not isinstance(event, dict):
            continue
        action = str(event.get("eventAction") or "").strip().lower()
        event_date_raw = event.get("eventDate")
        event_dt = _parse_event_datetime(event_date_raw)
        if event_dt is None:
            continue

        if action in {"registration", "registered", "creation", "created"}:
            if registration_dt is None or event_dt < registration_dt:
                registration_dt = event_dt
                registration_date_raw = str(event_date_raw)
        elif action in {"expiration", "expiry", "expires", "expiration date"}:
            expires_on_raw = str(event_date_raw)
        elif action in {"last changed", "last update of rdap database", "updated"}:
            updated_on_raw = str(event_date_raw)

    if registration_dt is None or registration_date_raw is None:
        return None

    current_dt = _coerce_datetime(now)
    age_days = max(0, int((current_dt - registration_dt).total_seconds() // 86400))
    age_years = round(age_days / 365.25, 3)

    profile: dict[str, Any] = {
        "domain": domain,
        "registration_date": registration_date_raw,
        "domain_age_days": age_days,
        "domain_age_years": age_years,
        "source": "rdap",
    }
    if expires_on_raw:
        profile["expires_on"] = expires_on_raw
    if updated_on_raw:
        profile["updated_on"] = updated_on_raw
    return profile


def load_domain_rdap(
    site_url_or_domain: str,
    timeout: int = 20,
    session: requests.Session | None = None,
    max_attempts: int = 3,
    retry_min_delay: float = 5.0,
    retry_max_delay: float = 10.0,
    sleep_fn: Any | None = None,
    delay_fn: Any | None = None,
) -> dict[str, Any]:
    """Load RDAP profile for a domain or site URL."""
    domain = _parse_domain(site_url_or_domain)
    if not domain:
        return {}

    http = session or requests.Session()
    sleeper = sleep_fn or time.sleep
    delay_picker = delay_fn or (lambda: random.uniform(retry_min_delay, retry_max_delay))
    last_error: Exception | None = None

    for attempt in range(1, max(1, max_attempts) + 1):
        try:
            response = http.get(
                f"https://rdap.org/domain/{domain}",
                timeout=timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "seo-google-leak-deep-audit/1.0",
                },
            )
            response.raise_for_status()
            payload = response.json()
            profile = extract_domain_profile_from_rdap(payload)
            return profile or {}
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= max(1, max_attempts):
                raise
            sleeper(delay_picker())

    if last_error:
        raise last_error
    return {}
