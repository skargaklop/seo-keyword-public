# MODULE_CONTRACT: utils/currency_rates
# Purpose: Currency rate utilities for converting Google Ads CPC values.
# Rationale: Keep the module boundary explicit for GRACE adoption and review.
# Dependencies: datetime, typing, requests
# Exports: CurrencyRateService
# LINKS: requirements.xml#UC-001, development-plan.xml#MOD-001
# MODULE_MAP: utils/currency_rates.py
# Public Functions: exported callables and classes defined in this module
# Private Helpers: internal helpers and private methods defined in this module
# Key Semantic Blocks: main workflow paths and state transitions in this module
# Critical Flows: preserve existing runtime behavior and integrations
# Verification: python -m py_compile, python -m ruff check ., python -m pytest -q
# CHANGE_SUMMARY: Added file-local module metadata and declaration contracts.

from datetime import date
from typing import ClassVar

import requests

# CLASS_CONTRACT: CurrencyRateService
# Purpose: Convert UAH, USD, and EUR amounts using cached NBU daily rates.
# LINKS: requirements.xml#UC-001
class CurrencyRateService:
    SUPPORTED_CURRENCIES: ClassVar[tuple[str, ...]] = ("UAH", "USD", "EUR")
    NBU_RATES_URL: ClassVar[str] = (
        "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
    )
    _cached_rates: ClassVar[dict[str, float] | None] = None
    _cached_date: ClassVar[date | None] = None
    # FUNCTION_CONTRACT: _get_rates_to_uah
    # Purpose: Implement the  get rates to uah helper for this module.
    # Input: (none)
    # Output: dict[str, float]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @classmethod
    def _get_rates_to_uah(cls) -> dict[str, float]:
        today = date.today()
        if cls._cached_rates is not None and cls._cached_date == today:
            return cls._cached_rates

        response = requests.get(cls.NBU_RATES_URL, timeout=10)
        response.raise_for_status()
        payload = response.json()

        rates: dict[str, float] = {"UAH": 1.0}
        for item in payload:
            currency_code = str(item.get("cc", "")).upper()
            if currency_code in {"USD", "EUR"}:
                rates[currency_code] = float(item["rate"])

        missing = [
            currency for currency in ("USD", "EUR") if currency not in rates
        ]
        if missing:
            raise ValueError(f"Missing NBU rates for: {', '.join(missing)}")

        cls._cached_rates = rates
        cls._cached_date = today
        return rates
    # FUNCTION_CONTRACT: convert_amount
    # Purpose: Implement the convert amount helper for this module.
    # Input: amount (float), from_currency (str), to_currency (str)
    # Output: float
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @classmethod
    def convert_amount(
        cls, amount: float, from_currency: str, to_currency: str
    ) -> float:
        source = str(from_currency).upper()
        target = str(to_currency).upper()

        if source == target:
            return amount

        unsupported = [
            code
            for code in (source, target)
            if code not in cls.SUPPORTED_CURRENCIES
        ]
        if unsupported:
            raise ValueError(f"Unsupported currency code(s): {', '.join(unsupported)}")

        rates_to_uah = cls._get_rates_to_uah()
        amount_in_uah = amount if source == "UAH" else amount * rates_to_uah[source]
        return amount_in_uah if target == "UAH" else amount_in_uah / rates_to_uah[target]
