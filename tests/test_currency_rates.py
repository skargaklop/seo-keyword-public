import pytest

from utils.currency_rates import CurrencyRateService


# Purpose:  FakeResponse implementation
class _FakeResponse:
    # Purpose:   init   implementation
    def __init__(self, payload):
        self._payload = payload

    # Purpose: raise for status implementation
    def raise_for_status(self) -> None:
        return None

    # Purpose: json implementation
    def json(self):
        return self._payload


# Purpose: TestCurrencyRateService implementation
class TestCurrencyRateService:
    # Purpose: setup method implementation
    def setup_method(self) -> None:
        CurrencyRateService._cached_rates = None
        CurrencyRateService._cached_date = None

    # Purpose: Test converts supported currencies via uah
    def test_converts_supported_currencies_via_uah(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = []

        # Purpose: fake get implementation
        def fake_get(url: str, timeout: int):
            calls.append((url, timeout))
            return _FakeResponse(
                [
                    {"cc": "USD", "rate": 40.0},
                    {"cc": "EUR", "rate": 50.0},
                ]
            )

        monkeypatch.setattr("utils.currency_rates.requests.get", fake_get)

        assert CurrencyRateService.convert_amount(400.0, "UAH", "USD") == 10.0
        assert CurrencyRateService.convert_amount(10.0, "USD", "UAH") == 400.0
        assert CurrencyRateService.convert_amount(10.0, "USD", "EUR") == 8.0
        assert CurrencyRateService.convert_amount(10.0, "EUR", "USD") == 12.5
        assert calls == [
            ("https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json", 10)
        ]

    # Purpose: Test returns same amount for same currency
    def test_returns_same_amount_for_same_currency(self) -> None:
        assert CurrencyRateService.convert_amount(12.34, "USD", "USD") == 12.34

    # Purpose: Test raises for unsupported currency
    def test_raises_for_unsupported_currency(self) -> None:
        with pytest.raises(ValueError):
            CurrencyRateService.convert_amount(10.0, "GBP", "USD")