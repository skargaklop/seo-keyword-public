# Test coverage for modules: MOD-001,MOD-003
from types import SimpleNamespace

import pandas as pd
import pytest

from utils.google_ads_client import GoogleAdsHandler


# Purpose:  FakeKeywordPlanIdeaService implementation
class _FakeKeywordPlanIdeaService:
    # Purpose:   init   implementation
    def __init__(self) -> None:
        self.requests = []
        self.idea_requests = []

    # Purpose: generate keyword historical metrics implementation
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

    # Purpose: generate keyword ideas implementation
    def generate_keyword_ideas(self, request):
        self.idea_requests.append(request)
        batch_idx = len(self.idea_requests)
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
                text=f"stretch film wholesale batch_{batch_idx}",
                keyword_idea_metrics=metrics,
            )
        ]


# Purpose:  FakeGeoTargetConstantService implementation
class _FakeGeoTargetConstantService:
    # Purpose: geo target constant path implementation
    # Purpose: geo target constant path implementation
    @staticmethod
    def geo_target_constant_path(location_id: str) -> str:
        return f"geoTargetConstants/{location_id}"


# Purpose:  FakeGoogleAdsService implementation
class _FakeGoogleAdsService:
    # Purpose:   init   implementation
    def __init__(self) -> None:
        self.search_calls = []

    # Purpose: language constant path implementation
    # Purpose: language constant path implementation
    @staticmethod
    def language_constant_path(language_id: str) -> str:
        return f"languageConstants/{language_id}"

    # Purpose: search implementation
    def search(self, customer_id: str, query: str):
        self.search_calls.append((customer_id, query))
        return iter([SimpleNamespace(customer=SimpleNamespace(currency_code="UAH"))])


# Purpose:  FakeCurrencyRateService implementation
class _FakeCurrencyRateService:
    # Purpose:   init   implementation
    def __init__(self) -> None:
        self.calls = []

    # Purpose: convert amount implementation
    def convert_amount(
        self, amount: float, from_currency: str, to_currency: str
    ) -> float:
        self.calls.append((amount, from_currency, to_currency))
        if from_currency == to_currency:
            return amount
        if (from_currency, to_currency) == ("UAH", "USD"):
            return round(amount / 40, 6)
        raise AssertionError(f"Unexpected conversion: {from_currency}->{to_currency}")


# Purpose:  FakeClient implementation
class _FakeClient:
    # Purpose:   init   implementation
    def __init__(self) -> None:
        self.idea_service = _FakeKeywordPlanIdeaService()
        self.google_ads_service = _FakeGoogleAdsService()
        self.enums = SimpleNamespace(
            KeywordPlanNetworkEnum=SimpleNamespace(GOOGLE_SEARCH="GOOGLE_SEARCH")
        )

    # Purpose: get service implementation
    def get_service(self, service_name: str):
        if service_name == "KeywordPlanIdeaService":
            return self.idea_service
        if service_name == "GeoTargetConstantService":
            return _FakeGeoTargetConstantService()
        if service_name == "GoogleAdsService":
            return self.google_ads_service
        raise AssertionError(f"Unexpected service: {service_name}")

    # Purpose: get type implementation
    # Purpose: get type implementation
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


# Purpose: TestGoogleAdsHandler implementation
class TestGoogleAdsHandler:
    # Purpose: Test init client returns none when customer id missing
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

    # Purpose: Test uses selected languages without double counting and converts cpc
    def test_uses_selected_languages_without_double_counting_and_converts_cpc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_client = _FakeClient()
        fake_rates = _FakeCurrencyRateService()
        monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1234567890")
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
        metrics_df = handler.get_keyword_metrics(["buy stretch film"], force_refresh=True)

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
                "1234567890",
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

    # Purpose: Test get keyword ideas uses keyword seed and returns compatible columns
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
            force_refresh=True,
        )

        assert len(fake_client.idea_service.idea_requests) == 1
        request = fake_client.idea_service.idea_requests[0]
        assert request.keyword_seed.keywords == ["stretch film", "packing film"]
        assert request.keyword_and_url_seed.url is None
        assert request.language == "languageConstants/1031"
        assert request.geo_target_constants == ["geoTargetConstants/2804"]
        assert request.keyword_plan_network == "GOOGLE_SEARCH"
        assert ideas_df.loc[0, "Keyword"] == "stretch film wholesale batch_1"
        assert ideas_df.loc[0, "Source URL"] == "https://example.com/stretch-film"
        assert ideas_df.loc[0, "Avg Monthly Searches"] == 120
        assert ideas_df.loc[0, "CPC Currency"] == "USD"

    # Purpose: Test get keyword ideas uses keyword and url seed when page url provided
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
            force_refresh=True,
        )

        request = fake_client.idea_service.idea_requests[0]
        assert request.keyword_seed.keywords == []
        assert request.url_seed.url is None
        assert request.keyword_and_url_seed.url == "https://example.com/moving-boxes"
        assert request.keyword_and_url_seed.keywords == ["moving boxes"]

    # Purpose: Test get keyword ideas uses url seed when only page url provided
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
            force_refresh=True,
        )

        request = fake_client.idea_service.idea_requests[0]
        assert request.keyword_seed.keywords == []
        assert request.url_seed.url == "https://example.com/moving-boxes"
        assert request.keyword_and_url_seed.url is None
        assert request.keyword_and_url_seed.keywords == []
        assert ideas_df.loc[0, "Source URL"] == "https://example.com/moving-boxes"

    # Purpose: Test get keyword ideas returns empty only when url and keywords missing
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

    # --- TDD RED: Task 1 batching test (plan 14-01) ---
    # Purpose: Test get keyword ideas batches keyword seed at 20
    def test_get_keyword_ideas_batches_keyword_seed_at_20(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_keyword_ideas must split >20 keywords into batches of 20."""
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

        # 45 keywords -> should produce 3 batches: 20 + 20 + 5
        keywords = [f"keyword_{i}" for i in range(45)]
        ideas_df = handler.get_keyword_ideas(keywords, force_refresh=True)

        # Verify batching: 3 API calls (one per batch of 20)
        assert len(fake_client.idea_service.idea_requests) == 3

        # First batch: keywords 0-19
        assert len(fake_client.idea_service.idea_requests[0].keyword_seed.keywords) == 20
        assert fake_client.idea_service.idea_requests[0].keyword_seed.keywords[0] == "keyword_0"
        assert fake_client.idea_service.idea_requests[0].keyword_seed.keywords[19] == "keyword_19"

        # Second batch: keywords 20-39
        assert len(fake_client.idea_service.idea_requests[1].keyword_seed.keywords) == 20
        assert fake_client.idea_service.idea_requests[1].keyword_seed.keywords[0] == "keyword_20"
        assert fake_client.idea_service.idea_requests[1].keyword_seed.keywords[19] == "keyword_39"

        # Third batch: keywords 40-44 (5 remaining)
        assert len(fake_client.idea_service.idea_requests[2].keyword_seed.keywords) == 5
        assert fake_client.idea_service.idea_requests[2].keyword_seed.keywords[0] == "keyword_40"

        # Results should be concatenated (3 batches x 1 result each = 3 rows)
        assert len(ideas_df) == 3

    # Purpose: Test get keyword ideas no batch when under 20
    def test_get_keyword_ideas_no_batch_when_under_20(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_keyword_ideas with <=20 keywords should not batch."""
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

        keywords = [f"kw_{i}" for i in range(15)]
        handler.get_keyword_ideas(keywords, force_refresh=True)

        # Single API call, no batching
        assert len(fake_client.idea_service.idea_requests) == 1
        assert len(fake_client.idea_service.idea_requests[0].keyword_seed.keywords) == 15

    # Purpose: Test get keyword ideas exact 20 no batch
    def test_get_keyword_ideas_exact_20_no_batch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_keyword_ideas with exactly 20 keywords should not batch."""
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

        keywords = [f"kw_{i}" for i in range(20)]
        handler.get_keyword_ideas(keywords, force_refresh=True)

        assert len(fake_client.idea_service.idea_requests) == 1
        assert len(fake_client.idea_service.idea_requests[0].keyword_seed.keywords) == 20