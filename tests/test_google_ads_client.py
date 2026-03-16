from types import SimpleNamespace

import pandas as pd
import pytest

from utils.google_ads_client import GoogleAdsHandler


class _FakeKeywordPlanIdeaService:
    def __init__(self) -> None:
        self.requests = []
        self.idea_requests = []

    def generate_keyword_historical_metrics(self, request):
        self.requests.append(request)
        metrics = SimpleNamespace(
            avg_monthly_searches=390,
            competition="HIGH",
            competition_index=86,
            low_top_of_page_bid_micros=7_080_000,
            high_top_of_page_bid_micros=23_090_000,
            monthly_search_volumes=[],
        )
        return SimpleNamespace(
            results=[
                SimpleNamespace(
                    text="buy stretch film",
                    keyword_metrics=metrics,
                )
            ]
        )

    def generate_keyword_ideas(self, request):
        self.idea_requests.append(request)
        metrics = SimpleNamespace(
            avg_monthly_searches=120,
            competition="MEDIUM",
            competition_index=52,
            low_top_of_page_bid_micros=3_000_000,
            high_top_of_page_bid_micros=9_000_000,
            monthly_search_volumes=[],
        )
        return [
            SimpleNamespace(
                text="stretch film wholesale",
                keyword_idea_metrics=metrics,
            )
        ]


class _FakeGeoTargetConstantService:
    @staticmethod
    def geo_target_constant_path(location_id: str) -> str:
        return f"geoTargetConstants/{location_id}"


class _FakeGoogleAdsService:
    def __init__(self) -> None:
        self.search_calls = []

    @staticmethod
    def language_constant_path(language_id: str) -> str:
        return f"languageConstants/{language_id}"

    def search(self, customer_id: str, query: str):
        self.search_calls.append((customer_id, query))
        return iter([SimpleNamespace(customer=SimpleNamespace(currency_code="UAH"))])


class _FakeCurrencyRateService:
    def __init__(self) -> None:
        self.calls = []

    def convert_amount(
        self, amount: float, from_currency: str, to_currency: str
    ) -> float:
        self.calls.append((amount, from_currency, to_currency))
        if from_currency == to_currency:
            return amount
        if (from_currency, to_currency) == ("UAH", "USD"):
            return round(amount / 40, 6)
        raise AssertionError(f"Unexpected conversion: {from_currency}->{to_currency}")


class _FakeClient:
    def __init__(self) -> None:
        self.idea_service = _FakeKeywordPlanIdeaService()
        self.google_ads_service = _FakeGoogleAdsService()
        self.enums = SimpleNamespace(
            KeywordPlanNetworkEnum=SimpleNamespace(GOOGLE_SEARCH="GOOGLE_SEARCH")
        )

    def get_service(self, service_name: str):
        if service_name == "KeywordPlanIdeaService":
            return self.idea_service
        if service_name == "GeoTargetConstantService":
            return _FakeGeoTargetConstantService()
        if service_name == "GoogleAdsService":
            return self.google_ads_service
        raise AssertionError(f"Unexpected service: {service_name}")

    @staticmethod
    def get_type(type_name: str):
        if type_name == "GenerateKeywordHistoricalMetricsRequest":
            return SimpleNamespace(
                customer_id=None,
                keywords=[],
                geo_target_constants=[],
                keyword_plan_network=None,
                language=None,
            )
        if type_name == "GenerateKeywordIdeasRequest":
            return SimpleNamespace(
                customer_id=None,
                geo_target_constants=[],
                keyword_plan_network=None,
                language=None,
                include_adult_keywords=None,
                keyword_seed=SimpleNamespace(keywords=[]),
                url_seed=SimpleNamespace(url=None),
                keyword_and_url_seed=SimpleNamespace(url=None, keywords=[]),
            )
        raise AssertionError(f"Unexpected type: {type_name}")


class TestGoogleAdsHandler:
    def test_init_client_returns_none_when_customer_id_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "dev-token")
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_ID", "client-id")
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_SECRET", "client-secret")
        monkeypatch.setenv("GOOGLE_ADS_REFRESH_TOKEN", "refresh-token")
        monkeypatch.setenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "1234567890")
        monkeypatch.delenv("GOOGLE_ADS_CUSTOMER_ID", raising=False)
        monkeypatch.setattr(
            "utils.google_ads_client.GoogleAdsClient",
            SimpleNamespace(load_from_dict=lambda config: object()),
        )

        handler = GoogleAdsHandler()

        assert handler.client is None

    def test_uses_selected_languages_without_double_counting_and_converts_cpc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_client = _FakeClient()
        fake_rates = _FakeCurrencyRateService()
        monkeypatch.setattr(
            GoogleAdsHandler,
            "_init_client",
            lambda self: fake_client,
        )

        handler = GoogleAdsHandler(
            location_id="2804",
            language_id=["1031", "1036"],
            target_currency_code="USD",
            exchange_rate_service=fake_rates,
        )
        metrics_df = handler.get_keyword_metrics(["buy stretch film"])

        assert isinstance(metrics_df, pd.DataFrame)
        assert len(fake_client.idea_service.requests) == 2
        assert {
            request.language for request in fake_client.idea_service.requests
        } == {"languageConstants/1031", "languageConstants/1036"}
        assert all(
            request.keyword_plan_network == "GOOGLE_SEARCH"
            for request in fake_client.idea_service.requests
        )
        assert fake_client.google_ads_service.search_calls == [
            (
                handler.customer_id,
                "SELECT customer.currency_code FROM customer LIMIT 1",
            )
        ]
        assert metrics_df.loc[0, "Avg Monthly Searches"] == 390
        assert metrics_df.loc[0, "Low CPC"] == 0.177
        assert metrics_df.loc[0, "High CPC"] == 0.5773
        assert metrics_df.loc[0, "CPC Currency"] == "USD"
        assert fake_rates.calls == [
            (7.08, "UAH", "USD"),
            (23.09, "UAH", "USD"),
        ]

    def test_get_keyword_ideas_uses_keyword_seed_and_returns_compatible_columns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_client = _FakeClient()
        fake_rates = _FakeCurrencyRateService()
        monkeypatch.setattr(
            GoogleAdsHandler,
            "_init_client",
            lambda self: fake_client,
        )

        handler = GoogleAdsHandler(
            location_id="2804",
            language_id="1031",
            target_currency_code="USD",
            exchange_rate_service=fake_rates,
        )

        ideas_df = handler.get_keyword_ideas(
            ["stretch film", "packing film"],
            source_url="https://example.com/stretch-film",
        )

        assert len(fake_client.idea_service.idea_requests) == 1
        request = fake_client.idea_service.idea_requests[0]
        assert request.keyword_seed.keywords == ["stretch film", "packing film"]
        assert request.keyword_and_url_seed.url is None
        assert request.language == "languageConstants/1031"
        assert request.geo_target_constants == ["geoTargetConstants/2804"]
        assert request.keyword_plan_network == "GOOGLE_SEARCH"
        assert ideas_df.loc[0, "Keyword"] == "stretch film wholesale"
        assert ideas_df.loc[0, "Source URL"] == "https://example.com/stretch-film"
        assert ideas_df.loc[0, "Avg Monthly Searches"] == 120
        assert ideas_df.loc[0, "CPC Currency"] == "USD"

    def test_get_keyword_ideas_uses_keyword_and_url_seed_when_page_url_provided(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_client = _FakeClient()
        monkeypatch.setattr(
            GoogleAdsHandler,
            "_init_client",
            lambda self: fake_client,
        )

        handler = GoogleAdsHandler(
            location_id="2840",
            language_id="1000",
            target_currency_code="UAH",
        )

        handler.get_keyword_ideas(
            ["moving boxes"],
            page_url="https://example.com/moving-boxes",
            source_url="https://example.com/moving-boxes",
        )

        request = fake_client.idea_service.idea_requests[0]
        assert request.keyword_seed.keywords == []
        assert request.url_seed.url is None
        assert request.keyword_and_url_seed.url == "https://example.com/moving-boxes"
        assert request.keyword_and_url_seed.keywords == ["moving boxes"]

    def test_get_keyword_ideas_uses_url_seed_when_only_page_url_provided(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_client = _FakeClient()
        monkeypatch.setattr(
            GoogleAdsHandler,
            "_init_client",
            lambda self: fake_client,
        )

        handler = GoogleAdsHandler(
            location_id="2840",
            language_id="1000",
            target_currency_code="UAH",
        )

        ideas_df = handler.get_keyword_ideas(
            [],
            page_url="https://example.com/moving-boxes",
            source_url="https://example.com/moving-boxes",
        )

        request = fake_client.idea_service.idea_requests[0]
        assert request.keyword_seed.keywords == []
        assert request.url_seed.url == "https://example.com/moving-boxes"
        assert request.keyword_and_url_seed.url is None
        assert request.keyword_and_url_seed.keywords == []
        assert ideas_df.loc[0, "Source URL"] == "https://example.com/moving-boxes"

    def test_get_keyword_ideas_returns_empty_only_when_url_and_keywords_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_client = _FakeClient()
        monkeypatch.setattr(
            GoogleAdsHandler,
            "_init_client",
            lambda self: fake_client,
        )

        handler = GoogleAdsHandler(
            location_id="2840",
            language_id="1000",
            target_currency_code="UAH",
        )

        ideas_df = handler.get_keyword_ideas([], page_url=None, source_url=None)

        assert ideas_df.empty
        assert fake_client.idea_service.idea_requests == []
