"""
Currency rate utilities for converting Google Ads CPC values.
Uses the official NBU JSON endpoint as the exchange-rate source.
"""

from datetime import date
from typing import ClassVar

import requests


class CurrencyRateService:
    """Convert between UAH, USD, and EUR using NBU daily rates."""

    SUPPORTED_CURRENCIES: ClassVar[tuple[str, ...]] = ("UAH", "USD", "EUR")
    NBU_RATES_URL: ClassVar[str] = (
        "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
    )
    _cached_rates: ClassVar[dict[str, float] | None] = None
    _cached_date: ClassVar[date | None] = None

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
