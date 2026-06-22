from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest
import requests
from tenacity import wait_none

from config.settings import SERP_CONFIG
from utils.serp_client import (
    BraveSearchAdapter,
    BrowserCloakbrowserAdapter,
    DataForSeoAdapter,
    SearchApiIoAdapter,
    ScraperApiAdapter,
    SerpApiAdapter,
    SerperDevAdapter,
    SerpstackAdapter,
    PROVIDER_REGISTRY,
    SERPClient,
    SERPKnowledgeGraph,
    SERPOrganicResult,
    SERPPeopleAlsoAsk,
    SERPProviderAdapter,
    SERPSearchResult,
    _SerpSearchSpec,
    ScaleSERPAdapter,
    SerpstatAdapter,
    ValueSERPAdapter,
    ZenserpAdapter,
    _build_tbs_value,
    _build_serp_request_params,
    _normalize_serp_payload,
    create_serp_client,
)


SERP_ENV_VARS = [
    "SERPER_API_KEY",
    "SERPAPI_KEY",
    "BRAVE_SEARCH_API_KEY",
    "SEARCHAPI_IO_KEY",
    "ZENSERP_KEY",
    "SCRAPERAPI_KEY",
    "DATAFORSEO_LOGIN",
    "DATAFORSEO_PASSWORD",
    "SERPSTAT_TOKEN",
    "SERPSTACK_KEY",
    "SCALESERP_KEY",
    "VALUESERP_KEY",
]


# Purpose:  response implementation
def _response(payload, status_code=200):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    response.status_code = status_code
    return response


# Purpose:  clear serp env implementation
def _clear_serp_env(monkeypatch):
    for env_var in SERP_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


# Purpose:  FakeAdapter implementation
class _FakeAdapter(SERPProviderAdapter):
    provider_name = "fake"
    env_var = "FAKE_KEY"

    # Purpose:   init   implementation
    def __init__(self, outcomes=None):
        super().__init__("fake-key")
        self.outcomes = list(outcomes or [])
        self.calls = []

    # Purpose: search implementation
    def search(self, query, num_results, gl, hl, timeout, extra_params=None):
        self.calls.append(
            {
                "query": query,
                "num_results": num_results,
                "gl": gl,
                "hl": hl,
                "timeout": timeout,
            }
        )
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        return SERPSearchResult(keyword=query, provider=self.provider_name, success=True)


# Purpose:  LimitedRetryFakeAdapter implementation
class _LimitedRetryFakeAdapter(_FakeAdapter):
    max_retries = 1


# Purpose:  client implementation
def _client(adapter):
    client = SERPClient(
        "fake",
        "fake-key",
        adapter,
        num_results=5,
        gl="ua",
        hl="uk",
        timeout=9,
    )
    return client


# Purpose: FakeBrowserScraper implementation
class _FakeBrowserScraper:
    # Purpose: scrape serp implementation
    def scrape_serp(self, query, params):
        assert query == "wood shavings"
        assert params["google_domain"] == "google.com.ua"
        assert params["total_results_target"] == 15
        assert params["pages_max"] == 2
        return SimpleNamespace(
            success=True,
            errors=[],
            parsed_content={
                "results": [
                    {
                        "position": "2",
                        "title": "Result",
                        "url": "https://example.test/page",
                        "snippet": "Snippet",
                        "displayed_link": "example.test",
                        "rich_snippet": {"rating": "5"},
                    }
                ],
                "people_also_ask": [{"question": "Question?", "answer": "Answer"}],
                "related_searches": [{"query": "related query"}],
            },
            metadata={"engine": "cloakbrowser"},
        )


# Purpose: FakeEmptyBrowserScraper implementation
class _FakeEmptyBrowserScraper:
    # Purpose: scrape serp implementation
    def scrape_serp(self, query, params):
        return SimpleNamespace(
            success=True,
            errors=[],
            parsed_content={"results": [], "people_also_ask": [], "related_searches": []},
            metadata={"engine": "cloakbrowser", "status": "empty_results"},
        )


# Purpose: Test serp config loads
def test_serp_config_loads():
    assert isinstance(SERP_CONFIG, dict)
    assert {"provider", "num_results", "gl", "hl", "timeout_seconds"}.issubset(SERP_CONFIG)


# Purpose: Test serp config defaults
def test_serp_config_defaults():
    assert SERP_CONFIG["timeout_seconds"] == 30


# Purpose: Test serp organic result creation
def test_serp_organic_result_creation():
    result = SERPOrganicResult(position=1, title="Title", url="https://example.com", snippet="Snippet")

    assert result.position == 1
    assert result.url == "https://example.com"


# Purpose: Test serp search result with defaults
def test_serp_search_result_with_defaults():
    result = SERPSearchResult(keyword="keyword", provider="serper_dev")

    assert result.organic == []
    assert result.related_searches == []
    assert result.people_also_ask == []
    assert result.knowledge_graph is None
    assert result.success is True


# Purpose: Test serp search result failure
def test_serp_search_result_failure():
    result = SERPSearchResult(keyword="keyword", provider="serper_dev", success=False, error="failed")

    assert result.success is False
    assert result.error == "failed"


# Purpose: Test serperdev adapter normalizes
def test_serperdev_adapter_normalizes():
    payload = {
        "organic": [{"position": 2, "title": "One", "link": "https://one.test", "snippet": "First"}],
        "relatedSearches": [{"query": "related one"}, "related two"],
        "peopleAlsoAsk": [{"question": "Question?", "snippet": "Answer"}],
        "knowledgeGraph": {"title": "Entity", "type": "Thing", "description": "Description"},
    }

    with patch("utils.serp_client.requests.post", return_value=_response(payload)) as post:
        result = SerperDevAdapter("key").search("keyword", 10, "ua", "uk", 30)

    post.assert_called_once()
    assert post.call_args.kwargs["timeout"] == 30
    assert post.call_args.kwargs["headers"]["X-API-KEY"] == "key"
    assert result.provider == "serper_dev"
    assert result.organic[0] == SERPOrganicResult(2, "One", "https://one.test", "First")
    assert result.related_searches == ["related one", "related two"]
    assert result.people_also_ask == [SERPPeopleAlsoAsk("Question?", "Answer")]
    assert result.knowledge_graph == SERPKnowledgeGraph("Entity", "Thing", "Description")


# Purpose: Test serpapi adapter normalizes
def test_serpapi_adapter_normalizes():
    payload = {
        "organic_results": [{"position": 1, "title": "One", "link": "https://one.test", "snippet": "First"}],
        "related_searches": [{"query": "related"}],
        "related_questions": [{"question": "Question?", "answer": "Answer"}],
        "knowledge_graph": {"title": "Entity", "type": "Thing", "description": "Description"},
    }

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        result = SerpApiAdapter("key").search("keyword", 10, "ua", "uk", 30)

    get.assert_called_once()
    assert get.call_args.kwargs["timeout"] == 30
    assert get.call_args.kwargs["params"]["api_key"] == "key"
    assert result.provider == "serpapi"
    assert result.organic[0].url == "https://one.test"
    assert result.related_searches == ["related"]
    assert result.people_also_ask[0].snippet == "Answer"
    assert result.knowledge_graph.title == "Entity"


# Purpose: Test brave adapter normalizes
def test_brave_adapter_normalizes():
    payload = {
        "web": {
            "results": [
                {"title": "One", "url": "https://one.test", "description": "First"},
                {"title": "Two", "url": "https://two.test", "description": "Second"},
            ]
        }
    }

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        result = BraveSearchAdapter("key").search("keyword", 2, "ua", "uk", 30)

    assert get.call_args.kwargs["timeout"] == 30
    assert get.call_args.kwargs["headers"]["X-Subscription-Token"] == "key"
    assert [item.position for item in result.organic] == [1, 2]
    assert result.related_searches == []
    assert result.people_also_ask == []


# SearchApi.io adapter tests
# Purpose: Test searchapi io adapter normalizes
def test_searchapi_io_adapter_normalizes():
    payload = {
        "organic_results": [{"position": 1, "title": "One", "link": "https://one.test", "snippet": "First"}],
        "related_searches": [{"query": "related"}],
        "people_also_ask": [{"question": "Question?", "snippet": "Answer"}],
        "knowledge_graph": {"title": "Entity", "type": "Thing", "description": "Description"},
    }

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        result = SearchApiIoAdapter("key").search("keyword", 10, "ua", "uk", 30)

    get.assert_called_once()
    assert get.call_args.kwargs["params"]["api_key"] == "key"
    assert get.call_args.kwargs["params"]["engine"] == "google"
    assert result.provider == "searchapi_io"
    assert result.organic[0].title == "One"


# Purpose: Test searchapi io adapter passes page param
def test_searchapi_io_adapter_passes_page_param():
    payload = {"organic_results": []}

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        SearchApiIoAdapter("key").search("keyword", 10, "ua", "uk", 30, extra_params={"page": 2})

    assert get.call_args.kwargs["params"]["page"] == 2


# Zenserp adapter tests
# Purpose: Test zenserp adapter normalizes
def test_zenserp_adapter_normalizes():
    payload = {
        "organic": [{"title": "One", "url": "https://one.test", "description": "First"}],
        "related_searches": [{"query": "related"}],
        "questions": [{"question": "Question?", "answer": "Answer"}],
    }

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        result = ZenserpAdapter("key").search("keyword", 10, "ua", "uk", 30)

    assert get.call_args.kwargs["headers"]["apikey"] == "key"
    assert result.organic[0].url == "https://one.test"


# Purpose: Test zenserp adapter fallback to destination
def test_zenserp_adapter_fallback_to_destination():
    payload = {"organic": [{"title": "One", "destination": "https://one.test", "description": "First"}]}

    with patch("utils.serp_client.requests.get", return_value=_response(payload)):
        result = ZenserpAdapter("key").search("keyword", 10, "ua", "uk", 30)

    assert result.organic[0].url == "https://one.test"


# Purpose: Test zenserp adapter maps google domain
def test_zenserp_adapter_maps_google_domain():
    payload = {"organic": []}

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        ZenserpAdapter("key").search("keyword", 10, "ua", "uk", 30, extra_params={"google_domain": "google.de"})

    assert get.call_args.kwargs["params"]["search_engine"] == "google.de"


# ScraperAPI adapter tests
# Purpose: Test scraperapi adapter normalizes
def test_scraperapi_adapter_normalizes():
    payload = {"organic_results": [{"title": "One", "link": "https://one.test", "snippet": "First"}]}

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        result = ScraperApiAdapter("key").search("keyword", 10, "ua", "uk", 30)

    assert get.call_args.kwargs["params"]["api_key"] == "key"
    assert get.call_args.kwargs["params"]["query"] == "keyword"  # NOT q
    assert get.call_args.kwargs["params"]["GL"] == "ua"  # key is uppercase, value passed as-is
    assert get.call_args.kwargs["params"]["HL"] == "uk"
    assert result.provider == "scraperapi"


# Purpose: Test scraperapi adapter timeout floor
def test_scraperapi_adapter_timeout_floor():
    payload = {"organic_results": []}

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        ScraperApiAdapter("key").search("keyword", 10, "ua", "uk", 30)

    # Timeout floor of 70
    assert get.call_args.kwargs["timeout"] == 70


# Purpose: Test scraperapi adapter max retries override
def test_scraperapi_adapter_max_retries_override():
    assert ScraperApiAdapter.max_retries == 1


# Purpose: Test scraperapi adapter maps google domain to tld
def test_scraperapi_adapter_maps_google_domain_to_tld():
    payload = {"organic_results": []}

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        ScraperApiAdapter("key").search("keyword", 10, "ua", "uk", 30, extra_params={"google_domain": "google.com.ua"})

    assert get.call_args.kwargs["params"]["tld"] == "com.ua"


# DataForSEO adapter tests
# Purpose: Test dataforseo adapter normalizes
def test_dataforseo_adapter_normalizes():
    payload = {
        "status_code": 20000,
        "tasks": [
            {
                "status_code": 20000,
                "result": [
                    {
                        "items": [
                            {"type": "organic", "title": "One", "url": "https://one.test", "description": "First"}
                        ]
                    }
                ]
            }
        ],
    }

    with patch("utils.serp_client.requests.post", return_value=_response(payload)) as post:
        result = DataForSeoAdapter("login:password").search("keyword", 10, "us", "en", 30)

    # Check Basic auth header
    auth_header = post.call_args.kwargs["headers"]["Authorization"]
    assert auth_header.startswith("Basic ")
    assert result.organic[0].title == "One"


# Purpose: Test dataforseo adapter body error
def test_dataforseo_adapter_body_error():
    payload = {"status_code": 50000, "status_message": "Invalid credentials"}

    with patch("utils.serp_client.requests.post", return_value=_response(payload)):
        with pytest.raises(ValueError, match="DataForSEO API error"):
            DataForSeoAdapter("login:password").search("keyword", 10, "us", "en", 30)


# Purpose: Test dataforseo adapter task level error
def test_dataforseo_adapter_task_level_error():
    payload = {"status_code": 20000, "tasks": [{"status_code": 50000, "status_message": "Task failed"}]}

    with patch("utils.serp_client.requests.post", return_value=_response(payload)):
        with pytest.raises(ValueError, match="DataForSEO task error"):
            DataForSeoAdapter("login:password").search("keyword", 10, "us", "en", 30)


# Purpose: Test dataforseo adapter field translation
def test_dataforseo_adapter_field_translation():
    payload = {"status_code": 20000, "tasks": [{"status_code": 20000, "result": [{"items": []}]}]}

    with patch("utils.serp_client.requests.post", return_value=_response(payload)) as post:
        DataForSeoAdapter("login:password").search(
            "keyword", 10, "us", "en", 30, extra_params={"google_domain": "google.de"}
        )

        # Check body params
        body = post.call_args.kwargs["json"][0]
        assert body["language_code"] == "en"  # hl -> language_code
        assert body["se_domain"] == "google.de"  # google_domain -> se_domain
        assert body["depth"] == 10  # num_results -> depth


# Purpose: Test dataforseo adapter gl to location mapping
def test_dataforseo_adapter_gl_to_location_mapping():
    payload = {"status_code": 20000, "tasks": [{"status_code": 20000, "result": [{"items": []}]}]}

    with patch("utils.serp_client.requests.post", return_value=_response(payload)) as post:
        DataForSeoAdapter("login:password").search("keyword", 10, "us", "en", 30)

        body = post.call_args.kwargs["json"][0]
        assert body["location_name"] == "United States"  # gl -> location_name


# Purpose: Test dataforseo adapter unknown gl omits location
def test_dataforseo_adapter_unknown_gl_omits_location():
    payload = {"status_code": 20000, "tasks": [{"status_code": 20000, "result": [{"items": []}]}]}

    with patch("utils.serp_client.requests.post", return_value=_response(payload)) as post:
        DataForSeoAdapter("login:password").search("keyword", 10, "zz", "en", 30)

        body = post.call_args.kwargs["json"][0]
        assert "location_name" not in body  # unknown gl code


# Serpstat adapter tests
# Purpose: Test serpstat adapter normalizes
def test_serpstat_adapter_normalizes():
    payload = {
        "result": {"data": [{"keyword": "related one"}, {"keyword": "related two"}]}
    }

    with patch("utils.serp_client.requests.post", return_value=_response(payload)) as post:
        result = SerpstatAdapter("token").search("keyword", 10, "ua", "uk", 30)

    # URL is first positional arg with token in query string
    assert "token=" in post.call_args.args[0]
    assert result.provider == "serpstat"
    assert result.organic == []  # Serpstat does NOT provide organic results
    assert result.related_searches == ["related one", "related two"]


# Purpose: Test serpstat adapter json rpc error
def test_serpstat_adapter_json_rpc_error():
    payload = {"error": {"message": "Invalid token"}}

    with patch("utils.serp_client.requests.post", return_value=_response(payload)):
        with pytest.raises(ValueError, match="Serpstat JSON-RPC error"):
            SerpstatAdapter("token").search("keyword", 10, "ua", "uk", 30)


# Purpose: Test serpstat adapter se param format
def test_serpstat_adapter_se_param_format():
    payload = {"result": {"data": []}}

    with patch("utils.serp_client.requests.post", return_value=_response(payload)) as post:
        SerpstatAdapter("token").search("keyword", 10, "ua", "uk", 30)

        body = post.call_args.kwargs["json"]
        assert body["params"]["se"] == "g_ua"  # gl -> g_{gl} format


# Remaining original tests
# Purpose: Test adapter handles empty response
def test_adapter_handles_empty_response():
    with patch("utils.serp_client.requests.post", return_value=_response({})):
        result = SerperDevAdapter("key").search("keyword", 10, "ua", "uk", 30)

    assert result.success is True
    assert result.organic == []
    assert result.related_searches == []
    assert result.people_also_ask == []
    assert result.knowledge_graph is None


# Purpose: Test client search success
def test_client_search_success():
    adapter = _FakeAdapter()
    client = _client(adapter)

    result = client.search("keyword")

    assert result.success is True
    assert result.keyword == "keyword"
    assert adapter.calls[0]["timeout"] == 9


# Purpose: Test client retries on failure
def test_client_retries_on_failure():
    success = SERPSearchResult(keyword="keyword", provider="fake", success=True)
    adapter = _FakeAdapter(
        [
            requests.RequestException("first"),
            requests.RequestException("second"),
            requests.RequestException("third"),
            success,
        ]
    )
    client = _client(adapter)

    with patch("utils.serp_client.wait_exponential", return_value=wait_none()):
        result = client.search("keyword")

    assert result is success
    assert len(adapter.calls) == 4


# Purpose: Test client uses adapter max retries when set
def test_client_uses_adapter_max_retries_when_set():
    adapter = _LimitedRetryFakeAdapter([requests.RequestException("failed"), SERPSearchResult(keyword="keyword", provider="fake", success=True)])
    client = _client(adapter)

    with patch("utils.serp_client.wait_exponential", return_value=wait_none()):
        result = client.search("keyword")

    assert result.success is False
    assert result.error == "failed"
    assert len(adapter.calls) == 1


# Purpose: Test client defaults to four attempts without adapter override
def test_client_defaults_to_four_attempts_without_adapter_override():
    adapter = _FakeAdapter([requests.RequestException("failed")] * 4)
    client = _client(adapter)

    with patch("utils.serp_client.wait_exponential", return_value=wait_none()):
        result = client.search("keyword")

    assert result.success is False
    assert result.error == "failed"
    assert len(adapter.calls) == 4


# Purpose: Test client returns failure after retries exhausted
def test_client_returns_failure_after_retries_exhausted():
    adapter = _FakeAdapter([requests.RequestException("failed")] * 4)
    client = _client(adapter)

    with patch("utils.serp_client.wait_exponential", return_value=wait_none()):
        result = client.search("keyword")

    assert result.success is False
    assert result.error == "failed"
    assert len(adapter.calls) == 4


# Purpose: Test client defensive empty key
def test_client_defensive_empty_key():
    with pytest.raises(ValueError):
        SERPClient("fake", "", _FakeAdapter())


# Purpose: Test client batch processes all
def test_client_batch_processes_all():
    client = _client(_FakeAdapter())

    results = client.search_batch(["one", "two", "three"])

    assert [result.keyword for result in results] == ["one", "two", "three"]
    assert all(result.success for result in results)


# Purpose: Test client batch catches per keyword error
def test_client_batch_catches_per_keyword_error():
    adapter = _FakeAdapter(
        [
            SERPSearchResult(keyword="one", provider="fake", success=True),
            ValueError("bad keyword"),
            SERPSearchResult(keyword="three", provider="fake", success=True),
        ]
    )
    client = _client(adapter)

    results = client.search_batch(["one", "two", "three"])

    assert len(results) == 3
    assert results[0].success is True
    assert results[1].success is False
    assert results[1].error == "bad keyword"
    assert results[2].success is True


# Purpose: Test client batch progress callback
def test_client_batch_progress_callback():
    client = _client(_FakeAdapter())
    calls = []

    client.search_batch(["one", "two", "three"], progress_callback=lambda index, total: calls.append((index, total)))

    assert calls == [(1, 3), (2, 3), (3, 3)]


# Purpose: Test factory returns client with key
def test_factory_returns_client_with_key(monkeypatch):
    _clear_serp_env(monkeypatch)
    monkeypatch.setenv("SERPER_API_KEY", "key")

    client = create_serp_client({"provider": "serper_dev", "num_results": 4, "gl": "ua", "hl": "uk"})

    assert isinstance(client, SERPClient)
    assert isinstance(client.adapter, SerperDevAdapter)
    assert client.num_results == 4


# Purpose: Test factory returns none without key
def test_factory_returns_none_without_key(monkeypatch):
    _clear_serp_env(monkeypatch)

    assert create_serp_client({"provider": "serper_dev"}) is None


# Purpose: Test factory selects correct adapter
def test_factory_selects_correct_adapter(monkeypatch):
    _clear_serp_env(monkeypatch)
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "key")

    client = create_serp_client({"provider": "brave_search"})

    assert isinstance(client.adapter, BraveSearchAdapter)


# Purpose: Test factory dual auth for dataforseo
def test_factory_dual_auth_for_dataforseo(monkeypatch):
    _clear_serp_env(monkeypatch)
    monkeypatch.setenv("DATAFORSEO_LOGIN", "login")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "password")

    client = create_serp_client({"provider": "dataforseo"})

    assert isinstance(client, SERPClient)
    assert isinstance(client.adapter, DataForSeoAdapter)
    # Factory combines login:password
    assert client.adapter.login == "login"
    assert client.adapter.password == "password"


# Purpose: Test factory dual auth missing password returns none
def test_factory_dual_auth_missing_password_returns_none(monkeypatch):
    _clear_serp_env(monkeypatch)
    monkeypatch.setenv("DATAFORSEO_LOGIN", "login")
    # Missing PASSWORD

    assert create_serp_client({"provider": "dataforseo"}) is None


# Purpose: Test factory maps all 12 providers
def test_factory_maps_all_12_providers(monkeypatch):
    _clear_serp_env(monkeypatch)
    expected = {
        "serper_dev": ("SERPER_API_KEY", SerperDevAdapter),
        "serpapi": ("SERPAPI_KEY", SerpApiAdapter),
        "brave_search": ("BRAVE_SEARCH_API_KEY", BraveSearchAdapter),
        "searchapi_io": ("SEARCHAPI_IO_KEY", SearchApiIoAdapter),
        "zenserp": ("ZENSERP_KEY", ZenserpAdapter),
        "scraperapi": ("SCRAPERAPI_KEY", ScraperApiAdapter),
        "dataforseo": (("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"), DataForSeoAdapter),
        "serpstat": ("SERPSTAT_TOKEN", SerpstatAdapter),
        "serpstack": ("SERPSTACK_KEY", SerpstackAdapter),
        "scaleserp": ("SCALESERP_KEY", ScaleSERPAdapter),
        "valueserp": ("VALUESERP_KEY", ValueSERPAdapter),
        "browser_cloakbrowser": ("", BrowserCloakbrowserAdapter),  # API-key-free
    }

    assert PROVIDER_REGISTRY == expected
    for provider, (env_var, adapter_class) in expected.items():
        _clear_serp_env(monkeypatch)
        if isinstance(env_var, tuple):
            for ev in env_var:
                monkeypatch.setenv(ev, "key")
        elif env_var:  # Skip empty env_var for API-key-free providers
            monkeypatch.setenv(env_var, "key")

        client = create_serp_client({"provider": provider})

        assert isinstance(client.adapter, adapter_class)


# Purpose: Test browser cloakbrowser adapter normalizes browser result
def test_browser_cloakbrowser_adapter_normalizes_browser_result(monkeypatch):
    monkeypatch.setattr(
        "utils.browser_scraper.create_browser_scraper",
        lambda config=None: _FakeBrowserScraper(),
    )

    result = BrowserCloakbrowserAdapter().search(
        "wood shavings",
        num_results=15,
        gl="ua",
        hl="uk",
        timeout=30,
        extra_params={"google_domain": "google.com.ua"},
    )

    assert result.keyword == "wood shavings"
    assert result.provider == "browser_cloakbrowser"
    assert result.success is True
    assert result.organic[0] == SERPOrganicResult(
        2,
        "Result",
        "https://example.test/page",
        "Snippet",
        "example.test",
        {"rating": "5"},
        "Rating: 5",
    )
    assert result.people_also_ask == [SERPPeopleAlsoAsk("Question?", "Answer")]
    assert result.related_searches == ["related query"]


# Purpose: Test browser cloakbrowser adapter fails when browser parser returns no organic results
def test_browser_cloakbrowser_adapter_returns_failure_for_empty_browser_parse(monkeypatch):
    monkeypatch.setattr(
        "utils.browser_scraper.create_browser_scraper",
        lambda config=None: _FakeEmptyBrowserScraper(),
    )

    result = BrowserCloakbrowserAdapter().search(
        "wood shavings",
        num_results=15,
        gl="ua",
        hl="uk",
        timeout=30,
        extra_params={"google_domain": "google.com.ua"},
    )

    assert result.keyword == "wood shavings"
    assert result.provider == "browser_cloakbrowser"
    assert result.success is False
    assert "no organic" in result.error.lower()


# Purpose: Test browser cloakbrowser adapter avoids repeated local browser retries
def test_browser_cloakbrowser_adapter_has_single_attempt_policy():
    assert BrowserCloakbrowserAdapter.max_retries == 1


# Purpose: Test browser cloakbrowser adapter returns failure when unavailable
def test_browser_cloakbrowser_adapter_returns_failure_when_unavailable(monkeypatch):
    monkeypatch.setattr("utils.browser_scraper.create_browser_scraper", lambda config=None: None)

    result = BrowserCloakbrowserAdapter().search(
        "wood shavings",
        num_results=10,
        gl="ua",
        hl="uk",
        timeout=30,
    )

    assert result.success is False
    assert result.keyword == "wood shavings"
    assert result.provider == "browser_cloakbrowser"
    assert "Browser scraping is disabled or unavailable" in result.error


# Tests for remaining original adapters
# Purpose: Test serpstack adapter normalizes
def test_serpstack_adapter_normalizes():
    payload = {
        "organic_results": [
            {"rank": "3", "name": "One", "destination": "https://one.test", "text": "First"}
        ]
    }

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        result = SerpstackAdapter("key").search("keyword", 10, "ua", "uk", 30)

    assert get.call_args.kwargs["params"]["access_key"] == "key"
    assert get.call_args.kwargs["timeout"] == 30
    assert result.organic[0] == SERPOrganicResult(3, "One", "https://one.test", "First")
    assert result.related_searches == []
    assert result.people_also_ask == []


# Purpose: Test scaleserp adapter normalizes
def test_scaleserp_adapter_normalizes():
    payload = {
        "organic_results": [{"position": 1, "title": "One", "link": "https://one.test", "snippet": "First"}],
        "related_searches": [{"query": "related"}],
        "knowledge_graph": {"title": "Entity", "type": "Thing", "description": "Description"},
    }

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        result = ScaleSERPAdapter("key").search("keyword", 10, "ua", "uk", 30)

    assert get.call_args.kwargs["params"]["api_key"] == "key"
    assert get.call_args.kwargs["timeout"] == 30
    assert result.organic[0].title == "One"
    assert result.related_searches == ["related"]
    assert result.knowledge_graph.description == "Description"


# Purpose: Test scaleserp adapter omits unsupported search_type values.
def test_scaleserp_adapter_omits_search_type():
    payload = {"organic_results": []}

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        ScaleSERPAdapter("key").search(
            "keyword",
            10,
            "ua",
            "uk",
            30,
            extra_params={"search_type": "images"},
        )

    assert "search_type" not in get.call_args.kwargs["params"]


# Purpose: Test valueserp adapter normalizes
def test_valueserp_adapter_normalizes():
    payload = {
        "organic_results": [{"position": 1, "title": "One", "link": "https://one.test", "snippet": "First"}],
        "related_searches": [{"query": "related"}],
        "knowledge_graph": {"title": "Entity", "type": "Thing", "description": "Description"},
    }

    with patch("utils.serp_client.requests.get", return_value=_response(payload)) as get:
        result = ValueSERPAdapter("key").search("keyword", 10, "ua", "uk", 30)

    assert get.call_args.kwargs["params"]["api_key"] == "key"
    assert get.call_args.kwargs["timeout"] == 30
    assert result.organic[0].snippet == "First"
    assert result.related_searches == ["related"]
    assert result.knowledge_graph.type == "Thing"


# Purpose: Test shared SERP request param builder applies provider-specific overrides
def test_build_serp_request_params_applies_provider_specific_overrides():
    serpapi_params = _build_serp_request_params(
        base_params={"q": "keyword", "api_key": "key", "num": 10, "gl": "ua", "hl": "uk"},
        extra_params={
            "device": "mobile",
            "search_type": "images",
            "time_period": "day",
            "google_domain": "google.de",
            "location": "Berlin",
            "uule": "encoded",
            "start": 4,
        },
        search_type_target="tbm",
        search_type_transform=lambda value: {"images": "isch", "videos": "vid", "news": "nws", "shopping": "shop"}.get(value),
        time_period_target="tbs",
        time_period_transform=_build_tbs_value,
        google_domain_target="google_domain",
        location_target="location",
        uule_target="uule",
        pagination_target="start",
        pagination_source_key="start",
    )

    valueserp_params = _build_serp_request_params(
        base_params={"api_key": "key", "q": "keyword", "num": 10, "gl": "ua", "hl": "uk"},
        extra_params={
            "device": "tablet",
            "search_type": "news",
            "time_period": "week",
            "safe_search": "active",
            "location": "Berlin",
            "uule": "encoded",
            "page": 2,
        },
        search_type_target="search_type",
        search_type_transform=lambda value: value if value != "web" else None,
        time_period_target="time_period",
        time_period_transform=lambda value: value if value != "any" else None,
        safe_search_target="safe",
        location_target="location",
        uule_target="uule",
        pagination_target="page",
        pagination_source_key="page",
    )

    assert serpapi_params["device"] == "mobile"
    assert serpapi_params["tbm"] == "isch"
    assert serpapi_params["tbs"] == "qdr:d"
    assert serpapi_params["google_domain"] == "google.de"
    assert serpapi_params["location"] == "Berlin"
    assert serpapi_params["uule"] == "encoded"
    assert serpapi_params["start"] == 4

    assert valueserp_params["device"] == "tablet"
    assert valueserp_params["search_type"] == "news"
    assert valueserp_params["time_period"] == "week"
    assert valueserp_params["safe"] == "active"
    assert valueserp_params["location"] == "Berlin"
    assert valueserp_params["uule"] == "encoded"
    assert valueserp_params["page"] == 2


# Purpose: Test shared spec-based search helper centralizes request execution and normalization.
def test_serp_provider_adapter_search_with_spec_uses_shared_request_helper():
    class _SpecAdapter(SERPProviderAdapter):
        provider_name = "spec"
        env_var = "SPEC_KEY"

        def search(self, query, num_results, gl, hl, timeout, extra_params=None):
            raise NotImplementedError

    adapter = _SpecAdapter("key")

    with patch("utils.serp_client.requests.get", return_value=_response({"organic_results": [{"title": "One", "link": "https://one.test"}], "related_searches": [{"query": "related"}]})) as get:
        spec = _SerpSearchSpec(
            provider_name="spec",
            endpoint="https://example.test/search",
            base_params_factory=lambda api_key, keyword, num_results, gl, hl: {
                "api_key": api_key,
                "q": keyword,
                "num": num_results,
                "gl": gl,
                "hl": hl,
            },
            request_param_kwargs={"pagination_target": "page", "pagination_source_key": "page"},
            normalize_kwargs={"organic_key": "organic_results", "related_key": "related_searches"},
            timeout_transform=lambda timeout: timeout + 1,
            url_transform=lambda extra_params: "https://example.test/search/alt" if extra_params and extra_params.get("alt") else "https://example.test/search",
        )

        result = adapter._search_with_spec(
            spec,
            "keyword",
            3,
            "ua",
            "uk",
            30,
            extra_params={"page": 2, "alt": True},
        )

    assert get.call_args.args[0] == "https://example.test/search/alt"
    assert get.call_args.kwargs["timeout"] == 31
    assert get.call_args.kwargs["params"]["page"] == 2
    assert result.provider == "spec"
    assert result.organic[0].url == "https://one.test"
    assert result.related_searches == ["related"]


# Purpose: Test shared SERP payload normalizer reuses provider-specific shapes
def test_normalize_serp_payload_handles_provider_field_variants():
    payload = {
        "organic_results": [
            {
                "position": 1,
                "title": "One",
                "link": "https://one.test",
                "snippet": "First",
            }
        ],
        "related_searches": [{"query": "related"}],
        "related_questions": [{"question": "Question?", "answer": "Answer"}],
        "knowledge_graph": {"title": "Entity", "type": "Thing", "description": "Description"},
    }

    result = _normalize_serp_payload(
        keyword="keyword",
        provider="serpapi",
        payload=payload,
        organic_key="organic_results",
        related_key="related_searches",
        people_also_ask_key="related_questions",
        knowledge_graph_key="knowledge_graph",
        organic_kwargs={"url_fields": ("link", "url")},
    )

    assert result.keyword == "keyword"
    assert result.provider == "serpapi"
    assert result.organic[0].url == "https://one.test"
    assert result.related_searches == ["related"]
    assert result.people_also_ask[0].question == "Question?"
    assert result.knowledge_graph.description == "Description"


# Tests for displayed_link and rich_snippet field handling
# Purpose: Test that displayed_link handles multiple field name variants.
def test_normalize_organic_with_displayed_link_variants():
    from utils.serp_client import _normalize_organic_results

    # Test displayedLink (camelCase)
    items = [{"position": 1, "title": "One", "link": "https://one.test", "snippet": "First", "displayedLink": "https://one.test/displayed"}]
    results = _normalize_organic_results(items)
    assert results[0].displayed_link == "https://one.test/displayed"

    # Test displayed_link (snake_case)
    items = [{"position": 1, "title": "One", "link": "https://one.test", "snippet": "First", "displayed_link": "https://one.test/displayed2"}]
    results = _normalize_organic_results(items)
    assert results[0].displayed_link == "https://one.test/displayed2"

    # Test display_url variant
    items = [{"position": 1, "title": "One", "link": "https://one.test", "snippet": "First", "display_url": "https://one.test/displayed3"}]
    results = _normalize_organic_results(items)
    assert results[0].displayed_link == "https://one.test/displayed3"


# Purpose: Test that rich_snippet handles multiple field name variants.
def test_normalize_organic_with_rich_snippet_variants():
    from utils.serp_client import _normalize_organic_results

    # Test richSnippet (camelCase)
    items = [{"position": 1, "title": "One", "link": "https://one.test", "snippet": "First", "richSnippet": {"type": "Review", "rating": "5"}}]
    results = _normalize_organic_results(items)
    assert results[0].rich_snippet == {"type": "Review", "rating": "5"}

    # Test rich_snippet (snake_case)
    items = [{"position": 1, "title": "One", "link": "https://one.test", "snippet": "First", "rich_snippet": {"type": "Product", "price": "$10"}}]
    results = _normalize_organic_results(items)
    assert results[0].rich_snippet == {"type": "Product", "price": "$10"}

    # Test snippet_extended variant
    items = [{"position": 1, "title": "One", "link": "https://one.test", "snippet": "First", "snippet_extended": {"type": "Article", "author": "John"}}]
    results = _normalize_organic_results(items)
    assert results[0].rich_snippet == {"type": "Article", "author": "John"}

    # Test non-dict value (should be converted to empty dict)
    items = [{"position": 1, "title": "One", "link": "https://one.test", "snippet": "First", "rich_snippet": "invalid"}]
    results = _normalize_organic_results(items)
    assert results[0].rich_snippet == {}


# Purpose: Test that Zenserp adapter has pagination enabled.
def test_zenserp_adapter_supports_pagination():
    assert ZenserpAdapter.start_param == "start"
    assert ZenserpAdapter.max_per_page == 10


# Purpose: Test that _text decodes Unicode escape sequences and preserves already-decoded UTF-8.
def test_unicode_decode_in_text():
    from utils.serp_client import _text

    # Test Ukrainian text with Unicode escape sequences
    escaped = "\\u043e\\u0446\\u0456\\u043d\\u043a\\u0430 \\u043c\\u0430\\u0433\\u0430\\u0437\\u0438\\u043d\\u0443"
    decoded = _text(escaped)
    # Decode expected value the same way to avoid encoding issues in test
    expected = "\\u043e\\u0446\\u0456\\u043d\\u043a\\u0430 \\u043c\\u0430\\u0433\\u0430\\u0437\\u0438\\u043d\\u0443".encode().decode('unicode-escape')
    assert decoded == expected

    # Test mixed content
    mixed = "(50 \\u0442\\u0438\\u0441.)"
    decoded = _text(mixed)
    expected_mixed = "(50 \\u0442\\u0438\\u0441.)".encode().decode('unicode-escape')
    assert decoded == expected_mixed

    # Test already decoded UTF-8 text (should not be double-encoded/mojibake)
    utf8_text = "Коровки купить"
    assert _text(utf8_text) == "Коровки купить"

    # Test normal ASCII text
    normal = "Normal text"
    assert _text(normal) == "Normal text"

    # Test text without escape sequences but with special characters
    special = "Price: $10 — Free!"
    assert _text(special) == "Price: $10 — Free!"


# Purpose: Test that rich_snippet Unicode escape sequences are recursively decoded.
def test_unicode_decode_recursive_in_rich_snippet():
    from utils.serp_client import _normalize_organic_results, _decode_unicode_recursive

    # Test nested dict with Unicode escapes - use encode/decode to create expected values
    items = [{
        "position": 1,
        "title": "Product",
        "link": "https://example.com",
        "snippet": "Description",
        "rich_snippet": {
            "type": "\\u041e\\u0433\\u043b\\u044f\\u0434",
            "details": {
                "rating": "\\u041e\\u0446\\u0456\\u043d\\u043a\\u0430: 5",
                "delivery": "\\u0411\\u0435\\u0437\\u043a\\u043e\\u0448\\u0442\\u043e\\u0432\\u043d\\u0430 \\u0434\\u043e\\u0441\\u0442\\u0430\\u0432\\u043a\\u0430"
            }
        }
    }]
    results = _normalize_organic_results(items)
    # Create expected values using the same decoding mechanism
    expected_type = "\\u041e\\u0433\\u043b\\u044f\\u0434".encode().decode('unicode-escape')
    expected_rating = "\\u041e\\u0446\\u0456\\u043d\\u043a\\u0430: 5".encode().decode('unicode-escape')
    expected_delivery = "\\u0411\\u0435\\u0437\\u043a\\u043e\\u0448\\u0442\\u043e\\u0432\\u043d\\u0430 \\u0434\\u043e\\u0441\\u0442\\u0430\\u0432\\u043a\\u0430".encode().decode('unicode-escape')
    assert results[0].rich_snippet["type"] == expected_type
    assert results[0].rich_snippet["details"]["rating"] == expected_rating
    assert results[0].rich_snippet["details"]["delivery"] == expected_delivery

    # Test list of strings
    list_data = ["\\u041e\\u0434\\u0438\\u043d", "\\u0414\\u0432\\u0430"]
    decoded = _decode_unicode_recursive(list_data)
    expected_list = ["\\u041e\\u0434\\u0438\\u043d".encode().decode('unicode-escape'), "\\u0414\\u0432\\u0430".encode().decode('unicode-escape')]
    assert decoded == expected_list


# Purpose: Test that rich_snippet is formatted into readable text.
def test_format_rich_snippet_basic():
    from utils.serp_client import _format_rich_snippet

    # Test basic flat dict
    snippet = {"rating": "5/5", "price": "$10", "availability": "In stock"}
    formatted = _format_rich_snippet(snippet)
    assert "Rating: 5/5" in formatted
    assert "Price: $10" in formatted
    assert "Availability: In stock" in formatted

    # Test with numeric values
    snippet = {"rating": 5, "count": 100}
    formatted = _format_rich_snippet(snippet)
    assert "Rating: 5" in formatted
    assert "Count: 100" in formatted

    # Test empty dict
    assert _format_rich_snippet({}) == ""

    # Test non-dict input
    assert _format_rich_snippet("not a dict") == ""
    assert _format_rich_snippet(None) == ""


# Purpose: Test that nested rich_snippet structures are flattened.
def test_format_rich_snippet_nested():
    from utils.serp_client import _format_rich_snippet

    # Test nested dict
    snippet = {
        "rating": "4.5",
        "details": {
            "price": "$15.99",
            "brand": "Sony",
            "shipping": "Free"
        }
    }
    formatted = _format_rich_snippet(snippet)
    assert "Rating: 4.5" in formatted
    # Nested items should be included (up to 3)
    assert "Price: $15.99" in formatted or "Brand: Sony" in formatted or "Shipping: Free" in formatted


# Purpose: Test that rich_snippet lists are formatted correctly.
def test_format_rich_snippet_with_list():
    from utils.serp_client import _format_rich_snippet

    # Test list values
    snippet = {
        "features": ["Waterproof", "Wireless", "Rechargeable"],
        "rating": "5"
    }
    formatted = _format_rich_snippet(snippet)
    assert "Features:" in formatted
    assert "Waterproof" in formatted


# Purpose: Test that SERPOrganicResult includes formatted rich_snippet_text.
def test_organic_result_includes_rich_snippet_text():
    from utils.serp_client import _normalize_organic_results

    items = [{
        "position": 1,
        "title": "Product",
        "link": "https://example.com",
        "snippet": "Description",
        "rich_snippet": {"rating": "5/5", "price": "$10"}
    }]
    results = _normalize_organic_results(items)
    assert results[0].rich_snippet_text != ""
    assert "Rating: 5/5" in results[0].rich_snippet_text
    assert "Price: $10" in results[0].rich_snippet_text

# GRACE module link: MOD-006
