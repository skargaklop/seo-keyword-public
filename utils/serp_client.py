"""
Multi-provider SERP client models and adapters.
"""

import csv
import io
import os
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import requests
from config.settings import load_config
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from utils.logger import logger

# MODULE_CONTRACT: utils/serp_client
# Purpose: Provide common SERP result models and a multi-provider search client for SERP analysis workflows.
# Rationale: Keeps provider-specific HTTP payloads behind adapters while returning one normalized result shape.
# Dependencies: abc, dataclasses, os, typing, requests, tenacity, config.settings, utils.logger.
# Exports: SERPOrganicResult, SERPPeopleAlsoAsk, SERPKnowledgeGraph, SERPSearchResult, SERPProviderAdapter, SerperDevAdapter, SerpApiAdapter, BraveSearchAdapter, SearchApiIoAdapter, ZenserpAdapter, ScraperApiAdapter, DataForSeoAdapter, SerpstatAdapter, SemrushAdapter, SerpstackAdapter, ScaleSERPAdapter, ValueSERPAdapter, SERPClient, create_serp_client.
# LINKS: requirements.xml#UC-006, knowledge-graph.xml#MOD-006, verification-plan.xml#V-MOD-006
# MODULE_MAP: utils/serp_client.py
# Public Functions: SERPOrganicResult, SERPPeopleAlsoAsk, SERPKnowledgeGraph, SERPSearchResult, SERPProviderAdapter.search, SerperDevAdapter.search, SerpApiAdapter.search, BraveSearchAdapter.search, SearchApiIoAdapter.search, ZenserpAdapter.search, ScraperApiAdapter.search, DataForSeoAdapter.search, SerpstatAdapter.search, SemrushAdapter.search, SerpstackAdapter.search, ScaleSERPAdapter.search, ValueSERPAdapter.search, SERPClient.search, SERPClient.search_batch, create_serp_client.
# Private Helpers: _text, _first_text, _decode_unicode_recursive, _format_rich_snippet, _normalize_organic_results, _normalize_related_searches, _normalize_people_also_ask, _normalize_knowledge_graph, _make_result, _failure_result, _raise_for_provider_error, _traject_data_normalize.
# Key Semantic Blocks: block_serp_models_normalized_result, block_serp_provider_http_request, block_serp_provider_payload_normalize, block_serp_client_retry_search, block_serp_client_batch_iterate
# Critical Flows: provider payloads normalize into SERPSearchResult for downstream workflows; adapter HTTP requests pass provider auth and timeout; failed searches become structured failure results.
# Verification: verification-plan.xml#V-MOD-006
# CHANGE_SUMMARY: Added normalized SERP dataclasses, seven provider adapters, retry-aware SERPClient orchestration, and the configured factory entry point; Phase 7 Cycle 3: removed HasData (credit-based billing), added SearchApi.io, Zenserp, ScraperAPI, DataForSEO, Serpstat adapters with monthly subscription plans; review-driven fixes: Serpstat uses keyword suggestions (not organic SERP), DataForSEO has body-level error handling + GL_TO_LOCATION mapping, ScraperAPI has max_retries=1 override, factory supports tuple env_var for dual-auth providers; displayed_link/rich_snippet field handling expanded to support multiple provider variants (displayedLink/display_url/displayUrl, richSnippet/snippet_extended/structured_snippet/richSnippets/rich_snippets), Zenserp pagination enabled via start parameter; Unicode escape sequence decoding added to _text and _decode_unicode_recursive with conditional decoding (only when \u sequences present) to prevent mojibake/double-encoding of already-decoded UTF-8 text; rich_snippet formatting added via _format_rich_snippet to convert structured rich_snippet dicts into human-readable comma-separated text (e.g., {"rating": "5", "price": "$10"} becomes "Rating: 5, Price: $10"), SERPOrganicResult now includes rich_snippet_text field.

# CLASS_CONTRACT: SERPOrganicResult
# Purpose: Represent one normalized organic SERP result.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
# Purpose: SERPOrganicResult implementation
# Purpose: SERPOrganicResult implementation
@dataclass
class SERPOrganicResult:
    position: int
    title: str
    url: str
    snippet: str
    displayed_link: str = ""
    rich_snippet: dict = field(default_factory=dict)
    rich_snippet_text: str = ""  # Human-readable formatted version of rich_snippet


# CLASS_CONTRACT: SERPPeopleAlsoAsk
# Purpose: Represent one normalized People Also Ask item.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
# Purpose: SERPPeopleAlsoAsk implementation
# Purpose: SERPPeopleAlsoAsk implementation
@dataclass
class SERPPeopleAlsoAsk:
    question: str
    snippet: str


# CLASS_CONTRACT: SERPKnowledgeGraph
# Purpose: Represent normalized knowledge graph data when a provider returns it.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
# Purpose: SERPKnowledgeGraph implementation
# Purpose: SERPKnowledgeGraph implementation
@dataclass
class SERPKnowledgeGraph:
    title: str
    type: str
    description: str


# CLASS_CONTRACT: SERPSearchResult
# Purpose: Represent the complete normalized SERP response for one keyword.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
# Purpose: SERPSearchResult implementation
# Purpose: SERPSearchResult implementation
@dataclass
class SERPSearchResult:
    keyword: str
    organic: List[SERPOrganicResult] = field(default_factory=list)
    related_searches: List[str] = field(default_factory=list)
    people_also_ask: List[SERPPeopleAlsoAsk] = field(default_factory=list)
    knowledge_graph: Optional[SERPKnowledgeGraph] = None
    provider: str = ""
    success: bool = True
    error: Optional[str] = None


# FUNCTION_CONTRACT: _text
# Purpose: Convert optional provider payload values into stable strings with selective Unicode decoding.
# Input: value (Any)
# Output: str
# Side Effects: none
# Business Rules: Missing values normalize to empty strings instead of surfacing None in UI data; Unicode escape sequences like U+043E (Cyrillic 'o') are decoded ONLY when present in the string to avoid double-encoding already-decoded UTF-8 text.
# Failure Modes: Non-string values fall back to str(value); decoding errors return original value.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        # Only decode Unicode escape sequences if they're actually present
        # This prevents double-encoding of already-decoded UTF-8 text (mojibake)
        if "\\u" in value:
            try:
                return value.encode().decode('unicode-escape')
            except (UnicodeError, AttributeError):
                return value
        return value
    return str(value)


# FUNCTION_CONTRACT: _first_text
# Purpose: Return the first non-empty string from a provider payload using candidate field names.
# Input: item (dict), fields (Sequence[str])
# Output: str
# Side Effects: none
# Business Rules: Supports provider schema drift by trying known aliases in priority order.
# Failure Modes: Returns an empty string when no candidate field is present.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _first_text(item: Dict[str, Any], fields: Sequence[str]) -> str:
    for field_name in fields:
        value = _text(item.get(field_name)).strip()
        if value:
            return value
    return ""


# FUNCTION_CONTRACT: _decode_unicode_recursive
# Purpose: Recursively decode Unicode escape sequences in dicts, lists, and strings.
# Input: data (Any) - The data structure to decode (dict, list, str, or other)
# Output: Any - Same structure type with all strings decoded
# Side Effects: none
# Business Rules: Traverses nested structures; strings like U+043E (Cyrillic 'o') are decoded ONLY when \\u escape sequences are present; preserves non-string types and already-decoded UTF-8 text to avoid mojibake.
# Failure Modes: Decoding errors return original value.
# LINKS: requirements.xml#UC-006
def _decode_unicode_recursive(data: Any) -> Any:
    if isinstance(data, str):
        # Only decode if \u escape sequences are actually present
        if "\\u" in data:
            try:
                return data.encode().decode('unicode-escape')
            except (UnicodeError, AttributeError):
                return data
        return data
    elif isinstance(data, dict):
        return {key: _decode_unicode_recursive(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_decode_unicode_recursive(item) for item in data]
    return data


# FUNCTION_CONTRACT: _format_rich_snippet
# Purpose: Convert rich_snippet dict into human-readable comma-separated text.
# Input: rich_snippet (dict) - The rich_snippet dictionary from SERP API
# Output: str - Formatted text like "Rating: 5/5, Price: $10, Free delivery"
# Side Effects: none
# Business Rules: Flattens nested structures; handles common keys like rating, price, availability, type, brand; skips empty values; max 5 items to avoid clutter.
# Failure Modes: Non-dict input returns empty string.
# LINKS: requirements.xml#UC-006
def _format_rich_snippet(rich_snippet: dict) -> str:
    if not isinstance(rich_snippet, dict) or not rich_snippet:
        return ""

    items = []

    # Define priority order for common keys
    priority_keys = ["rating", "price", "availability", "type", "brand", "category"]
    other_keys = [k for k in rich_snippet.keys() if k not in priority_keys]

    # Process priority keys first
    for key in priority_keys + other_keys:
        if key not in rich_snippet:
            continue

        value = rich_snippet[key]
        # Skip empty values
        if not value or (isinstance(value, str) and not value.strip()):
            continue

        # Handle nested values (common in rich_snippet)
        if isinstance(value, dict):
            # Recursively format nested dicts, but limit depth
            nested_items = []
            for nk, nv in value.items():
                if nv and not (isinstance(nv, str) and not nv.strip()):
                    # Capitalize key and format value
                    nk_formatted = nk.replace("_", " ").title()
                    if isinstance(nv, (int, float)):
                        nested_items.append(f"{nk_formatted}: {nv}")
                    else:
                        nv_str = str(nv).strip()
                        if nv_str:
                            nested_items.append(f"{nk_formatted}: {nv_str}")
            if nested_items:
                items.extend(nested_items[:3])  # Limit nested items
        elif isinstance(value, (int, float)):
            # Format numeric values
            key_formatted = key.replace("_", " ").title()
            items.append(f"{key_formatted}: {value}")
        elif isinstance(value, str):
            # Format string values
            key_formatted = key.replace("_", " ").title()
            items.append(f"{key_formatted}: {value.strip()}")
        elif isinstance(value, list):
            # Format list values (common for features, tags)
            key_formatted = key.replace("_", " ").title()
            list_items = [str(v).strip() for v in value if v and not (isinstance(v, str) and not v.strip())]
            if list_items:
                items.append(f"{key_formatted}: {', '.join(list_items[:3])}")  # Limit list items

    # Limit total items to avoid clutter
    if not items:
        return ""

    return ", ".join(items[:5])


# FUNCTION_CONTRACT: _normalize_organic_results
# Purpose: Normalize provider organic result arrays into SERPOrganicResult objects.
# Input: items (Iterable[dict]), title_fields (Sequence[str]), url_fields (Sequence[str]), snippet_fields (Sequence[str])
# Output: list[SERPOrganicResult]
# Side Effects: none
# Business Rules: Position defaults to one-based item order when provider position is absent; displayed_link and rich_snippet handle multiple field name variants (displayed_link/displayedLink/display_url/displayUrl; richSnippet/rich_snippet/snippet_extended/structured_snippet/richSnippets/rich_snippets).
# Failure Modes: Malformed non-dict items are skipped.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _normalize_organic_results(
    items: Iterable[Dict[str, Any]],
    title_fields: Sequence[str] = ("title",),
    url_fields: Sequence[str] = ("link", "url"),
    snippet_fields: Sequence[str] = ("snippet", "description"),
) -> List[SERPOrganicResult]:
    organic: List[SERPOrganicResult] = []
    for index, item in enumerate(items or [], start=1):
        if not isinstance(item, dict):
            continue
        position = item.get("position") or item.get("rank") or index
        try:
            position_int = int(position)
        except (TypeError, ValueError):
            position_int = index
        # Handle displayed_link with multiple field name variants
        displayed_link = (
            _first_text(item, ("displayed_link", "displayedLink", "display_url", "displayUrl"))
        )
        # Handle rich_snippet with multiple field name variants (check for dict content, not just presence)
        rich_snippet_raw = (
            item.get("richSnippet") or item.get("rich_snippet") or
            item.get("snippet_extended") or item.get("structured_snippet") or
            item.get("richSnippets") or item.get("rich_snippets") or {}
        )
        rich_snippet = _decode_unicode_recursive(rich_snippet_raw) if isinstance(rich_snippet_raw, dict) else {}
        rich_snippet_text = _format_rich_snippet(rich_snippet)
        organic.append(
            SERPOrganicResult(
                position=position_int,
                title=_first_text(item, title_fields),
                url=_first_text(item, url_fields),
                snippet=_first_text(item, snippet_fields),
                displayed_link=displayed_link,
                rich_snippet=rich_snippet,
                rich_snippet_text=rich_snippet_text,
            )
        )
    return organic


# FUNCTION_CONTRACT: _normalize_related_searches
# Purpose: Normalize related search payloads into a list of query strings.
# Input: items (Iterable[Any])
# Output: list[str]
# Side Effects: none
# Business Rules: Accepts both string and dict payloads across SERP providers.
# Failure Modes: Empty or unsupported items are omitted.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _normalize_related_searches(items: Iterable[Any]) -> List[str]:
    related: List[str] = []
    for item in items or []:
        if isinstance(item, str):
            query = item.strip()
        elif isinstance(item, dict):
            query = _first_text(item, ("query", "title", "text", "search"))
        else:
            query = ""
        if query:
            related.append(query)
    return related


# FUNCTION_CONTRACT: _normalize_people_also_ask
# Purpose: Normalize People Also Ask payloads into question/snippet records.
# Input: items (Iterable[dict])
# Output: list[SERPPeopleAlsoAsk]
# Side Effects: none
# Business Rules: Question is required; snippet is optional and defaults to empty string.
# Failure Modes: Malformed or questionless entries are omitted.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _normalize_people_also_ask(items: Iterable[Dict[str, Any]]) -> List[SERPPeopleAlsoAsk]:
    people_also_ask: List[SERPPeopleAlsoAsk] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        question = _first_text(item, ("question", "title"))
        if question:
            people_also_ask.append(
                SERPPeopleAlsoAsk(
                    question=question,
                    snippet=_first_text(item, ("snippet", "answer", "description")),
                )
            )
    return people_also_ask


# FUNCTION_CONTRACT: _normalize_knowledge_graph
# Purpose: Normalize provider knowledge graph payloads into a shared optional record.
# Input: item (dict | None)
# Output: SERPKnowledgeGraph | None
# Side Effects: none
# Business Rules: Empty knowledge graph payloads remain None to distinguish absent SERP features.
# Failure Modes: Malformed payloads return None.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _normalize_knowledge_graph(item: Optional[Dict[str, Any]]) -> Optional[SERPKnowledgeGraph]:
    if not isinstance(item, dict) or not item:
        return None
    title = _first_text(item, ("title", "name"))
    graph_type = _first_text(item, ("type", "subtitle", "category"))
    description = _first_text(item, ("description", "snippet"))
    if not any((title, graph_type, description)):
        return None
    return SERPKnowledgeGraph(title=title, type=graph_type, description=description)


# FUNCTION_CONTRACT: _make_result
# Purpose: Build a successful normalized SERP result from normalized feature lists.
# Input: keyword (str), provider (str), organic (list), related_searches (list), people_also_ask (list), knowledge_graph (SERPKnowledgeGraph | None)
# Output: SERPSearchResult
# Side Effects: none
# Business Rules: Adapter success means the provider request returned parseable JSON, even when feature lists are empty.
# Failure Modes: none
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _make_result(
    keyword: str,
    provider: str,
    organic: Optional[List[SERPOrganicResult]] = None,
    related_searches: Optional[List[str]] = None,
    people_also_ask: Optional[List[SERPPeopleAlsoAsk]] = None,
    knowledge_graph: Optional[SERPKnowledgeGraph] = None,
) -> SERPSearchResult:
    return SERPSearchResult(
        keyword=keyword,
        organic=organic or [],
        related_searches=related_searches or [],
        people_also_ask=people_also_ask or [],
        knowledge_graph=knowledge_graph,
        provider=provider,
        success=True,
    )


# FUNCTION_CONTRACT: _failure_result
# Purpose: Build a structured failed SERP result without raising to callers.
# Input: keyword (str), provider (str), error (BaseException)
# Output: SERPSearchResult
# Side Effects: none
# Business Rules: Batch processing must continue even when one keyword/provider call fails.
# Failure Modes: none
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _failure_result(keyword: str, provider: str, error: BaseException) -> SERPSearchResult:
    return SERPSearchResult(
        keyword=keyword,
        organic=[],
        related_searches=[],
        people_also_ask=[],
        knowledge_graph=None,
        provider=provider,
        success=False,
        error=str(error),
    )


# FUNCTION_CONTRACT: _raise_for_provider_error
# Purpose: Raise requests errors before parsing provider responses.
# Input: response (requests.Response)
# Output: None
# Side Effects: may raise HTTPError via response.raise_for_status()
# Business Rules: HTTP errors are retriable at the client layer.
# Failure Modes: requests.HTTPError
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _raise_for_provider_error(response: requests.Response) -> None:
    response.raise_for_status()


# FUNCTION_CONTRACT: _build_tbs_value
# Purpose: Convert internal time period value to Google tbs query string
# Input: time_period (str) вЂ” internal key like "hour", "day", "week", "month", "year"
# Output: str | None вЂ” tbs value like "qdr:h", or None for "any"
# Side Effects: none
# Business Rules: Returns None for "any" or unknown values (omit tbs param)
# Failure Modes: never raises
# LINKS: requirements.xml#UC-006
def _build_tbs_value(time_period: str) -> str | None:
    return {"hour": "qdr:h", "day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "year": "qdr:y"}.get(time_period)


# CLASS_CONTRACT: _SerpSearchSpec
# Purpose: Describe one adapter-specific GET search configuration for the shared SERP request runner.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
@dataclass(frozen=True)
class _SerpSearchSpec:
    provider_name: str
    endpoint: str
    base_params_factory: Callable[[str, str, int, str, str], Dict[str, Any]]
    request_fn: Callable[..., requests.Response] | None = None
    request_param_kwargs: Dict[str, Any] = field(default_factory=dict)
    normalize_kwargs: Dict[str, Any] = field(default_factory=dict)
    headers_factory: Callable[[str], Dict[str, str]] | None = None
    timeout_transform: Callable[[int], int] | None = None
    url_transform: Callable[[dict[str, Any] | None], str] | None = None
    payload_transform: Callable[[Dict[str, Any]], Dict[str, Any]] | None = None


# FUNCTION_CONTRACT: _run_serp_get_search
# Purpose: Execute one spec-driven SERP request and normalize the resulting payload.
# Input: spec (_SerpSearchSpec), api_key (str), keyword (str), num_results (int), gl (str), hl (str), timeout (int), extra_params (dict | None)
# Output: SERPSearchResult
# Side Effects: Performs outbound HTTP via requests.get and raises on provider errors.
# Business Rules: Adapter-specific parameter shaping, URL overrides, headers, and normalization details live in the passed spec object.
# Failure Modes: requests exceptions and JSON decoding errors propagate to the caller.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _run_serp_get_search(
    spec: _SerpSearchSpec,
    api_key: str,
    keyword: str,
    num_results: int,
    gl: str,
    hl: str,
    timeout: int,
    extra_params: dict | None = None,
) -> SERPSearchResult:
    params = _build_serp_request_params(
        base_params=spec.base_params_factory(api_key, keyword, num_results, gl, hl),
        extra_params=extra_params,
        **spec.request_param_kwargs,
    )
    url = spec.url_transform(extra_params) if spec.url_transform else spec.endpoint
    request_fn = spec.request_fn or requests.get
    payload = _perform_serp_request(
        request_fn,
        url,
        timeout=spec.timeout_transform(timeout) if spec.timeout_transform else timeout,
        params=params,
        headers=spec.headers_factory(api_key) if spec.headers_factory else None,
    )
    if spec.payload_transform:
        payload = spec.payload_transform(payload)
    return _normalize_serp_payload(
        keyword,
        spec.provider_name,
        payload,
        **spec.normalize_kwargs,
    )


# FUNCTION_CONTRACT: _build_serp_request_params
# Purpose: Build request parameters for provider adapters that share Google SERP option shaping.
# Input: base_params (Dict[str, Any]), extra_params (dict | None), search_type_target (str | None), search_type_transform (Callable | None), search_type_warning (Callable | None), time_period_target (str | None), time_period_transform (Callable | None), google_domain_target (str | None), google_domain_transform (Callable | None), location_target (str | None), uule_target (str | None), pagination_target (str | None), pagination_source_key (str | None), pagination_transform (Callable | None), device_target (str | None), safe_search_target (str | None), safe_search_source_key (str)
# Output: Dict[str, Any]
# Side Effects: None
# Business Rules: Keeps provider-specific parameter names centralized while preserving each adapter's skip rules.
# Failure Modes: Never raises on missing optional values.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _build_serp_request_params(
    *,
    base_params: Dict[str, Any],
    extra_params: dict | None = None,
    search_type_target: str | None = None,
    search_type_transform: Callable[[str], str | None] | None = None,
    search_type_warning: Callable[[str], None] | None = None,
    time_period_target: str | None = None,
    time_period_transform: Callable[[str], str | None] | None = None,
    google_domain_target: str | None = None,
    google_domain_transform: Callable[[str], str] | None = None,
    location_target: str | None = None,
    uule_target: str | None = None,
    pagination_target: str | None = None,
    pagination_source_key: str | None = None,
    pagination_transform: Callable[[Any], Any] | None = None,
    device_target: str | None = "device",
    safe_search_target: str | None = None,
    safe_search_source_key: str = "safe_search",
) -> Dict[str, Any]:
    params = dict(base_params)
    if not extra_params:
        return params

    if device_target and extra_params.get("device"):
        params[device_target] = extra_params["device"]

    if search_type_target or search_type_warning:
        search_type = extra_params.get("search_type", "web")
        if search_type not in ("web", None):
            transformed = (
                search_type_transform(search_type)
                if search_type_transform
                else search_type
            )
            if search_type_target:
                params[search_type_target] = transformed
            elif search_type_warning:
                search_type_warning(search_type)

    if time_period_target:
        time_period = extra_params.get("time_period", "any")
        if time_period != "any":
            transformed = (
                time_period_transform(time_period)
                if time_period_transform
                else time_period
            )
            if transformed:
                params[time_period_target] = transformed

    if safe_search_target and extra_params.get(safe_search_source_key):
        params[safe_search_target] = extra_params[safe_search_source_key]

    if google_domain_target and extra_params.get("google_domain"):
        domain_value = extra_params["google_domain"]
        params[google_domain_target] = (
            google_domain_transform(domain_value)
            if google_domain_transform
            else domain_value
        )

    if location_target and extra_params.get("location"):
        params[location_target] = extra_params["location"]

    if uule_target and extra_params.get("uule"):
        params[uule_target] = extra_params["uule"]

    if pagination_target and pagination_source_key and extra_params.get(pagination_source_key):
        page_value = extra_params[pagination_source_key]
        params[pagination_target] = (
            pagination_transform(page_value)
            if pagination_transform
            else page_value
        )

    return params


# FUNCTION_CONTRACT: _perform_serp_request
# Purpose: Execute a requests-based SERP call and return the parsed JSON payload.
# Input: request_fn (Callable), url (str), timeout (int), params (dict | None), headers (dict | None), json_body (dict | None)
# Output: Dict[str, Any]
# Side Effects: Performs outbound HTTP via requests and raises on provider errors.
# Business Rules: Adapter methods should own their parameter shaping while this helper owns request execution and response parsing.
# Failure Modes: requests exceptions and JSON decoding errors propagate to the caller.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _perform_serp_request(
    request_fn: Callable[..., requests.Response],
    url: str,
    *,
    timeout: int,
    params: Dict[str, Any] | None = None,
    headers: Dict[str, str] | None = None,
    json_body: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    request_kwargs: Dict[str, Any] = {"timeout": timeout}
    if params is not None:
        request_kwargs["params"] = params
    if headers is not None:
        request_kwargs["headers"] = headers
    if json_body is not None:
        request_kwargs["json"] = json_body
    response = request_fn(url, **request_kwargs)
    _raise_for_provider_error(response)
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


# FUNCTION_CONTRACT: _normalize_serp_payload
# Purpose: Normalize common provider payload shapes into SERPSearchResult objects.
# Input: keyword (str), provider (str), payload (Dict[str, Any]), organic_key (str), related_key (str | None), people_also_ask_key (str | None), knowledge_graph_key (str | None), organic_kwargs (dict | None)
# Output: SERPSearchResult
# Side Effects: None
# Business Rules: Keeps payload field-name drift in one place while preserving provider-specific normalization of related, PAA, and knowledge graph records.
# Failure Modes: Missing keys fall back to empty lists or None.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _normalize_serp_payload(
    keyword: str,
    provider: str,
    payload: Dict[str, Any],
    *,
    organic_key: str,
    related_key: str | None = None,
    people_also_ask_key: str | None = None,
    knowledge_graph_key: str | None = None,
    organic_kwargs: Dict[str, Any] | None = None,
) -> SERPSearchResult:
    organic_kwargs = organic_kwargs or {}
    return _make_result(
        keyword=keyword,
        provider=provider,
        organic=_normalize_organic_results(
            payload.get(organic_key, []),
            **organic_kwargs,
        ),
        related_searches=_normalize_related_searches(
            payload.get(related_key, [])
        ) if related_key else [],
        people_also_ask=_normalize_people_also_ask(
            payload.get(people_also_ask_key, [])
        ) if people_also_ask_key else [],
        knowledge_graph=_normalize_knowledge_graph(
            payload.get(knowledge_graph_key)
        ) if knowledge_graph_key else None,
    )


# FUNCTION_CONTRACT: _raise_for_dataforseo_body_error
# Purpose: Inspect DataForSEO response body for task-level errors that arrive on HTTP 200.
# Input: data (dict) -- parsed JSON response from DataForSEO
# Output: None
# Side Effects: may raise ValueError when body indicates failure
# Business Rules: DataForSEO returns HTTP 200 with status_code != 20000 on task failure; top-level status_code 20000 is success; each task entry also has its own status_code; non-20000 values raise ValueError with the status_message.
# Failure Modes: ValueError for task failure; passes silently on success.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _raise_for_dataforseo_body_error(data: dict[str, Any]) -> None:
    top_status = data.get("status_code")
    if top_status is not None and top_status != 20000:
        raise ValueError(f"DataForSEO API error: {data.get('status_message', 'unknown error')} (code={top_status})")
    for task_entry in data.get("tasks", []):
        task_status = task_entry.get("status_code")
        if task_status is not None and task_status != 20000:
            raise ValueError(f"DataForSEO task error: {task_entry.get('status_message', 'unknown error')} (code={task_status})")


# Maps common gl country codes to DataForSEO location_name values.
# DataForSEO requires one of location_code, location_name, or location_coordinate.
# When gl is not in this map, the adapter omits location_name and relies on se_domain alone.
_GL_TO_LOCATION: dict[str, str] = {
    "us": "United States",
    "gb": "United Kingdom",
    "uk": "United Kingdom",  # Alias for UK users who expect ISO 3166-1 alpha-2
    "ua": "Ukraine",
    "ru": "Russia",
    "de": "Germany",
    "fr": "France",
    "es": "Spain",
    "it": "Italy",
    "pl": "Poland",
    "cz": "Czech Republic",
    "br": "Brazil",
    "ca": "Canada",
    "au": "Australia",
    "jp": "Japan",
    "in": "India",
    "nl": "Netherlands",
    "tr": "Turkey",
    "mx": "Mexico",
    "kr": "South Korea",
    "cn": "China",
}


# CLASS_CONTRACT: SERPProviderAdapter
# Purpose: Define the common provider adapter interface for SERP HTTP integrations.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class SERPProviderAdapter(ABC):
    provider_name: str = ""
    env_var: str | tuple[str, ...] = ""
    max_retries: int | None = None  # None = use SERPClient default (4)
    _SEARCH_SPEC: _SerpSearchSpec | None = None

    # FUNCTION_CONTRACT: SERPProviderAdapter.__init__
    # Purpose: Store the API key used by one SERP provider adapter.
    # Input: api_key (str | None)
    # Output: None
    # Side Effects: reads process environment when api_key is omitted.
    # Business Rules: Direct adapter construction still reads the documented provider env var; when env_var is a tuple, joins values with ':' for factory-constructed keys.
    # Failure Modes: none; client/factory owns empty-key degradation.
    # LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
    def __init__(self, api_key: Optional[str] = None) -> None:
        if api_key:
            self.api_key = api_key
        elif isinstance(self.env_var, tuple):
            self.api_key = ":".join(os.environ.get(v, "") for v in self.env_var)
        else:
            self.api_key = os.environ.get(self.env_var, "")

    # FUNCTION_CONTRACT: SERPProviderAdapter.search
    # Purpose: Execute a provider-specific SERP request and return a normalized result.
    # Input: query (str), num_results (int), gl (str), hl (str), timeout (int), extra_params (dict | None)
    # Output: SERPSearchResult
    # Side Effects: performs outbound HTTP request to provider API.
    # Business Rules: Each concrete adapter must pass timeout and normalize missing fields gracefully.
    # Failure Modes: requests.RequestException, TimeoutError, JSON parsing exceptions.
    # LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
    def search(
        self,
        query: str,
        num_results: int,
        gl: str,
        hl: str,
        timeout: int,
        extra_params: dict | None = None,
    ) -> SERPSearchResult:
        spec = self._SEARCH_SPEC
        if spec is None:
            raise NotImplementedError
        return self._search_with_spec(spec, query, num_results, gl, hl, timeout, extra_params)

    def _search_with_spec(
        self,
        spec: _SerpSearchSpec,
        query: str,
        num_results: int,
        gl: str,
        hl: str,
        timeout: int,
        extra_params: dict | None = None,
    ) -> SERPSearchResult:
        return _run_serp_get_search(
            spec,
            self.api_key,
            query,
            num_results,
            gl,
            hl,
            timeout,
            extra_params,
        )


# CLASS_CONTRACT: SerperDevAdapter
# Purpose: Query serper.dev and normalize its SERP response.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class SerperDevAdapter(SERPProviderAdapter):
    provider_name = "serper_dev"
    env_var = "SERPER_API_KEY"
    endpoint = "https://google.serper.dev/search"
    max_per_page = 100
    start_param = None

    # FUNCTION_CONTRACT: SerperDevAdapter.search
    # Purpose: POST a Serper.dev search request and normalize organic, related, PAA, and knowledge graph data.
    # Input: query (str), num_results (int), gl (str), hl (str), timeout (int), extra_params (dict | None)
    # Output: SERPSearchResult
    # Side Effects: performs HTTP POST to Serper.dev.
    # Business Rules: Uses X-API-KEY header; search_type changes endpoint path; device/tbs/google_domain merged into JSON body.
    # Failure Modes: requests.RequestException, JSON parsing exceptions.
    # LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
    def search(
        self,
        query: str,
        num_results: int,
        gl: str,
        hl: str,
        timeout: int,
        extra_params: dict | None = None,
    ) -> SERPSearchResult:
        base_url = self.endpoint
        body: dict[str, Any] = _build_serp_request_params(
            base_params={"q": query, "num": num_results, "gl": gl, "hl": hl},
            extra_params=extra_params,
            device_target="device",
            time_period_target="tbs",
            time_period_transform=_build_tbs_value,
            google_domain_target="google_domain",
        )
        if extra_params:
            st_val = extra_params.get("search_type", "web")
            if st_val not in ("web", None):
                path = {
                    "images": "/images",
                    "videos": "/videos",
                    "news": "/news",
                    "shopping": "/shopping",
                }.get(st_val)
                if path:
                    base_url = "https://google.serper.dev" + path
        payload = _perform_serp_request(
            requests.post,
            base_url,
            timeout=timeout,
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
            json_body=body,
        )
        return _normalize_serp_payload(
            query,
            self.provider_name,
            payload,
            organic_key="organic",
            related_key="relatedSearches",
            people_also_ask_key="peopleAlsoAsk",
            knowledge_graph_key="knowledgeGraph",
        )


# CLASS_CONTRACT: SerpApiAdapter
# Purpose: Query serpapi.com and normalize its Google SERP response.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class SerpApiAdapter(SERPProviderAdapter):
    provider_name = "serpapi"
    env_var = "SERPAPI_KEY"
    endpoint = "https://serpapi.com/search.json"
    max_per_page = 10
    start_param = "start"
    _SEARCH_SPEC = _SerpSearchSpec(
        provider_name="serpapi",
        endpoint=endpoint,
        base_params_factory=lambda api_key, keyword, num_results, gl, hl: {
            "q": keyword,
            "api_key": api_key,
            "num": num_results,
            "gl": gl,
            "hl": hl,
        },
        request_param_kwargs={
            "search_type_target": "tbm",
            "search_type_transform": lambda value: {
                "images": "isch",
                "videos": "vid",
                "news": "nws",
                "shopping": "shop",
            }.get(value),
            "time_period_target": "tbs",
            "time_period_transform": _build_tbs_value,
            "google_domain_target": "google_domain",
            "location_target": "location",
            "uule_target": "uule",
            "pagination_target": "start",
            "pagination_source_key": "start",
        },
        normalize_kwargs={
            "organic_key": "organic_results",
            "related_key": "related_searches",
            "people_also_ask_key": "related_questions",
            "knowledge_graph_key": "knowledge_graph",
        },
    )

# CLASS_CONTRACT: SearchApiIoAdapter
# Purpose: Query SearchApi.io Google Search API and normalize organic, related, PAA, and knowledge graph data.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class SearchApiIoAdapter(SERPProviderAdapter):
    provider_name = "searchapi_io"
    env_var = "SEARCHAPI_IO_KEY"
    endpoint = "https://www.searchapi.io/api/v1/search"
    max_per_page = 10
    start_param = "page"
    _SEARCH_SPEC = _SerpSearchSpec(
        provider_name="searchapi_io",
        endpoint=endpoint,
        base_params_factory=lambda api_key, keyword, num_results, gl, hl: {
            "api_key": api_key,
            "engine": "google",
            "q": keyword,
            "num": num_results,
            "gl": gl,
            "hl": hl,
        },
        request_param_kwargs={
            "device_target": "device",
            "time_period_target": "tbs",
            "time_period_transform": _build_tbs_value,
            "location_target": "location",
            "pagination_target": "page",
            "pagination_source_key": "page",
        },
        normalize_kwargs={
            "organic_key": "organic_results",
            "related_key": "related_searches",
            "people_also_ask_key": "people_also_ask",
            "knowledge_graph_key": "knowledge_graph",
            "organic_kwargs": {
                "title_fields": ("title",),
                "url_fields": ("link", "url"),
                "snippet_fields": ("snippet", "description"),
            },
        },
    )

# CLASS_CONTRACT: ZenserpAdapter
# Purpose: Query Zenserp and normalize its Google SERP response.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class ZenserpAdapter(SERPProviderAdapter):
    provider_name = "zenserp"
    env_var = "ZENSERP_KEY"
    endpoint = "https://app.zenserp.com/api/v2/search"
    max_per_page = 10
    start_param = "start"  # Zenserp supports offset-based pagination via start parameter
    _SEARCH_SPEC = _SerpSearchSpec(
        provider_name="zenserp",
        endpoint=endpoint,
        base_params_factory=lambda api_key, keyword, num_results, gl, hl: {
            "q": keyword,
            "gl": gl,
            "hl": hl,
        },
        request_param_kwargs={
            "device_target": "device",
            "google_domain_target": "search_engine",
            "location_target": "location",
            "search_type_warning": lambda value: logger.warning(
                f"Zenserp does not support search_type='{value}'; web results only"
            ),
        },
        normalize_kwargs={
            "organic_key": "organic",
            "related_key": "related_searches",
            "people_also_ask_key": "questions",
            "organic_kwargs": {
                "title_fields": ("title",),
                "url_fields": ("url", "destination"),
                "snippet_fields": ("description",),
            },
        },
        headers_factory=lambda api_key: {"apikey": api_key},
    )

# CLASS_CONTRACT: ScraperApiAdapter
# Purpose: Query ScraperAPI structured Google SERP endpoint and normalize organic results.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class ScraperApiAdapter(SERPProviderAdapter):
    provider_name = "scraperapi"
    env_var = "SCRAPERAPI_KEY"
    endpoint = "https://api.scraperapi.com/structured/google/search"
    max_per_page = 10
    start_param = "START"
    max_retries = 1  # ScraperAPI internally retries for 70s; multiple retries would freeze UI
    _SEARCH_SPEC = _SerpSearchSpec(
        provider_name="scraperapi",
        endpoint=endpoint,
        base_params_factory=lambda api_key, keyword, num_results, gl, hl: {
            "api_key": api_key,
            "query": keyword,
            "GL": gl,
            "HL": hl,
            "output_format": "json",
        },
        request_param_kwargs={
            "google_domain_target": "tld",
            "google_domain_transform": lambda value: value.replace("google.", "") if value.startswith("google.") else value,
            "uule_target": "UULE",
            "time_period_target": "TBS",
            "time_period_transform": _build_tbs_value,
        },
        timeout_transform=lambda timeout: max(timeout, 70),
        normalize_kwargs={
            "organic_key": "organic_results",
            "related_key": "related_searches",
            "organic_kwargs": {"url_fields": ("link", "url")},
        },
    )

# CLASS_CONTRACT: DataForSeoAdapter
# Purpose: Query DataForSEO live Google SERP endpoint and normalize organic results from deeply nested task response.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class DataForSeoAdapter(SERPProviderAdapter):
    provider_name = "dataforseo"
    env_var = ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD")
    endpoint = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    max_per_page = 200
    start_param = None

    # FUNCTION_CONTRACT: DataForSeoAdapter.__init__
    # Purpose: Store DataForSEO login and password parsed from combined api_key string.
    # Input: api_key (str) -- "login:password" format, assembled by factory from two env vars
    # Output: None
    # Side Effects: stores login and password attributes for Basic auth header construction.
    # Business Rules: api_key must contain colon separator; missing password defaults to empty string.
    # Failure Modes: malformed api_key results in empty credentials.
    # LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
    def __init__(self, api_key: str) -> None:
        super().__init__(api_key)
        parts = api_key.split(":", 1)
        self.login: str = parts[0]
        self.password: str = parts[1] if len(parts) > 1 else ""

    # FUNCTION_CONTRACT: DataForSeoAdapter.search
    # Purpose: POST a DataForSEO live advanced SERP request and normalize organic items from nested task response.
    # Input: query (str), num_results (int), gl (str), hl (str), timeout (int), extra_params (dict | None)
    # Output: SERPSearchResult
    # Side Effects: performs HTTP POST to DataForSEO with Basic auth.
    # Business Rules: Body is a single-task array; depth maps to num_results (max 200); hl mapped to language_code; google_domain mapped to se_domain; gl mapped to location_name via _GL_TO_LOCATION lookup (if gl not in map, location_name is omitted and se_domain provides geo-targeting); body-level status_code checked even on HTTP 200; items filtered by type=="organic".
    # Failure Modes: requests.RequestException, JSON parsing exceptions, ValueError on body-level task failure, nested response traversal errors caught gracefully.
    # LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
    def search(
        self,
        query: str,
        num_results: int,
        gl: str,
        hl: str,
        timeout: int,
        extra_params: dict | None = None,
    ) -> SERPSearchResult:
        # SEMANTIC_BLOCK: block_serp_provider_http_request
        import base64
        credentials: str = base64.b64encode(f"{self.login}:{self.password}".encode()).decode()
        headers: dict[str, str] = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }
        task: dict[str, Any] = {
            "keyword": query,
            "depth": min(num_results, 200),
            "language_code": hl,
        }
        # Map gl to DataForSEO location_name (required parameter for live SERP)
        location_name = _GL_TO_LOCATION.get(gl)
        if location_name:
            task["location_name"] = location_name
        else:
            logger.warning(f"DataForSEO: No location_name mapping for gl='{gl}'; geo-targeting may be inaccurate")
        if extra_params:
            if extra_params.get("device"):
                task["device"] = extra_params["device"]
            if extra_params.get("google_domain"):
                task["se_domain"] = extra_params["google_domain"]
        body: list[dict[str, Any]] = [task]
        response = requests.post(
            self.endpoint,
            json=body,
            headers=headers,
            timeout=timeout,
        )
        _raise_for_provider_error(response)
        data = response.json()
        # SEMANTIC_BLOCK: block_serp_provider_payload_normalize
        _raise_for_dataforseo_body_error(data)
        organic_items: list[dict[str, Any]] = []
        kg_data: Optional[dict[str, Any]] = None
        related_items: list[Any] = []
        try:
            for task_entry in data.get("tasks", []):
                for result in task_entry.get("result", []):
                    for item in result.get("items", []):
                        if item.get("type") == "organic":
                            organic_items.append(item)
                        elif item.get("type") == "knowledge_graph":
                            kg_data = item
                    related_items.extend(result.get("related_searches", []))
        except (KeyError, TypeError, IndexError):
            pass
        return _make_result(
            keyword=query,
            provider=self.provider_name,
            organic=_normalize_organic_results(
                organic_items,
                title_fields=("title",),
                url_fields=("url",),
                snippet_fields=("description", "snippet"),
            ),
            related_searches=_normalize_related_searches(related_items),
            knowledge_graph=_normalize_knowledge_graph(kg_data) if kg_data else None,
        )


# CLASS_CONTRACT: SerpstatAdapter
# Purpose: Query Serpstat keyword suggestions API and normalize results as related searches.
# NOTE: This adapter provides KEYWORD RESEARCH DATA (related keywords), NOT organic SERP results.
# The organic, people_also_ask, and knowledge_graph fields are always empty.
# Keyword suggestions populate the related_searches field.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class SerpstatAdapter(SERPProviderAdapter):
    provider_name = "serpstat"
    env_var = "SERPSTAT_TOKEN"
    endpoint = "https://api.serpstat.com/v4/"
    max_per_page = 100
    start_param = None

    # FUNCTION_CONTRACT: SerpstatAdapter.search
    # Purpose: POST a Serpstat JSON-RPC request for keyword suggestions and normalize into SERPSearchResult.related_searches.
    # Input: query (str), num_results (int), gl (str), hl (str), timeout (int), extra_params (dict | None)
    # Output: SERPSearchResult with empty organic, populated related_searches from keyword suggestions
    # Side Effects: performs HTTP POST to Serpstat with token in query string.
    # Business Rules: Uses JSON-RPC 2.0 format; se param is g_{gl} format; getSuggestions returns keyword suggestions NOT organic SERP results; suggestions populate related_searches only; organic/PAA/KG are always empty; gl is used for se database selection only.
    # Failure Modes: requests.RequestException, JSON parsing exceptions, JSON-RPC error responses.
    # LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
    def search(
        self,
        query: str,
        num_results: int,
        gl: str,
        hl: str,
        timeout: int,
        extra_params: dict | None = None,
    ) -> SERPSearchResult:
        # SEMANTIC_BLOCK: block_serp_provider_http_request
        rpc_params: dict[str, Any] = {"keyword": query, "se": f"g_{gl}"}
        body: dict[str, Any] = {
            "id": 1,
            "method": "SerpstatKeywordProcedure.getSuggestions",
            "params": rpc_params,
        }
        response = requests.post(
            f"{self.endpoint}?token={self.api_key}",
            json=body,
            timeout=timeout,
        )
        _raise_for_provider_error(response)
        data = response.json()
        # SEMANTIC_BLOCK: block_serp_provider_payload_normalize
        # Check for JSON-RPC error
        if "error" in data:
            error_msg = data["error"].get("message", str(data["error"])) if isinstance(data["error"], dict) else str(data["error"])
            raise ValueError(f"Serpstat JSON-RPC error: {error_msg}")
        suggestions = data.get("result", {}).get("data", [])
        # Map keyword suggestions to related_searches (NOT organic -- suggestions are keywords, not SERP results)
        related: list[str] = []
        for item in suggestions:
            if isinstance(item, dict):
                keyword_text = _text(item.get("keyword", ""))
                if keyword_text:
                    related.append(keyword_text)
        return _make_result(
            keyword=query,
            provider=self.provider_name,
            organic=[],  # Serpstat does not provide organic SERP results
            related_searches=related,
        )


# FUNCTION_CONTRACT: _semrush_database
# Purpose: Map internal gl country codes to Semrush database codes.
# Input: gl (str)
# Output: str
# Side Effects: none
# Business Rules: Known aliases are normalized conservatively; unsupported country codes pass through lower-case instead of forcing a default database.
# Failure Modes: Empty input falls back to "us" because Semrush requires a database code.
# LINKS: docs/operational-packets.xml#PACKET-17-SEMRUSH-SERP
def _semrush_database(gl: str) -> str:
    normalized = _text(gl).strip().lower()
    aliases = {
        "gb": "uk",
        "uk": "uk",
        "us": "us",
        "ua": "ua",
        "de": "de",
        "pl": "pl",
        "ru": "ru",
        "fr": "fr",
        "tr": "tr",
    }
    return aliases.get(normalized, normalized or "us")


# FUNCTION_CONTRACT: _semrush_first_text
# Purpose: Return the first populated value for Semrush CSV long/short header variants.
# Input: row (dict[str, str]), fields (Sequence[str])
# Output: str
# Side Effects: none
# Business Rules: Supports both human-readable CSV headers and explicit export column abbreviations.
# Failure Modes: Returns empty string when headers or values are absent.
# LINKS: docs/operational-packets.xml#PACKET-17-SEMRUSH-SERP
def _semrush_first_text(row: dict[str, Any], fields: Sequence[str]) -> str:
    normalized_row = {(_text(key).strip().lower()): value for key, value in row.items()}
    for field in fields:
        value = _text(normalized_row.get(field.lower())).strip()
        if value:
            return value
    return ""


# FUNCTION_CONTRACT: _normalize_semrush_csv
# Purpose: Normalize Semrush phrase_organic semicolon-delimited CSV into the shared SERP result shape.
# Input: keyword (str), csv_text (str)
# Output: SERPSearchResult
# Side Effects: none
# Business Rules: Semrush phrase_organic is a degraded legacy report; title/snippet are unavailable and receive explicit limited fallbacks.
# Failure Modes: Malformed rows without URLs are skipped; invalid positions fall back to row order.
# LINKS: docs/operational-packets.xml#PACKET-17-SEMRUSH-SERP
def _normalize_semrush_csv(keyword: str, csv_text: str) -> SERPSearchResult:
    organic: list[SERPOrganicResult] = []
    related_searches: list[str] = []
    seen_related: set[str] = set()
    reader = csv.DictReader(io.StringIO(csv_text or ""), delimiter=";")
    for index, row in enumerate(reader, start=1):
        if not isinstance(row, dict):
            continue
        url = _semrush_first_text(row, ("Url", "Ur"))
        if not url:
            continue
        domain = _semrush_first_text(row, ("Domain", "Dn")) or url
        position = _semrush_first_text(row, ("Position", "Po"))
        try:
            position_int = int(position)
        except (TypeError, ValueError):
            position_int = index
        organic.append(
            SERPOrganicResult(
                position=position_int,
                title=domain,
                url=url,
                snippet="Semrush limited organic result; title/snippet unavailable from phrase_organic report.",
                displayed_link=domain,
            )
        )
        for field_name in ("Keywords SERP Features", "Fk", "SERP Features", "Fp"):
            features = _semrush_first_text(row, (field_name,))
            for feature in features.split(","):
                feature_text = feature.strip()
                if feature_text and feature_text not in seen_related:
                    related_searches.append(feature_text)
                    seen_related.add(feature_text)
    return _make_result(
        keyword=keyword,
        provider="semrush",
        organic=organic,
        related_searches=related_searches,
    )


# CLASS_CONTRACT: SemrushAdapter
# Purpose: Query Semrush legacy phrase_organic report and normalize limited Google organic SERP fields.
# NOTE: Semrush phrase_organic is a degraded/deprecated SERP source: it does not return title, snippet, hl, device, safe-search, google_domain, location, or UULE.
# LINKS: docs/operational-packets.xml#PACKET-17-SEMRUSH-SERP
class SemrushAdapter(SERPProviderAdapter):
    provider_name = "semrush"
    env_var = "SEMRUSH_API_KEY"
    endpoint = "https://api.semrush.com/"
    max_per_page = 100
    start_param = None
    export_columns = "Po,Dn,Ur,Fk,Fp"

    # FUNCTION_CONTRACT: SemrushAdapter.search
    # Purpose: GET Semrush phrase_organic CSV report and normalize its limited organic rows.
    # Input: query (str), num_results (int), gl (str), hl (str), timeout (int), extra_params (dict | None)
    # Output: SERPSearchResult
    # Side Effects: performs HTTP GET to Semrush legacy API.
    # Business Rules: Uses explicit export_columns and database derived from gl; ignores unsupported advanced SERP parameters because Semrush does not provide them.
    # Failure Modes: requests.RequestException, provider HTTP errors.
    # LINKS: docs/operational-packets.xml#PACKET-17-SEMRUSH-SERP
    def search(
        self,
        query: str,
        num_results: int,
        gl: str,
        hl: str,
        timeout: int,
        extra_params: dict | None = None,
    ) -> SERPSearchResult:
        params: dict[str, Any] = {
            "type": "phrase_organic",
            "key": self.api_key,
            "phrase": query,
            "database": _semrush_database(gl),
            "display_limit": num_results,
            "export_columns": self.export_columns,
        }
        response = requests.get(self.endpoint, params=params, timeout=timeout)
        _raise_for_provider_error(response)
        return _normalize_semrush_csv(query, response.text)


# CLASS_CONTRACT: BraveSearchAdapter
# Purpose: Query Brave Search and normalize its web result response.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class BraveSearchAdapter(SERPProviderAdapter):
    provider_name = "brave_search"
    env_var = "BRAVE_SEARCH_API_KEY"
    endpoint = "https://api.search.brave.com/res/v1/web/search"
    max_per_page = 20
    start_param = "offset"
    _SEARCH_SPEC = _SerpSearchSpec(
        provider_name="brave_search",
        endpoint=endpoint,
        base_params_factory=lambda api_key, keyword, num_results, gl, hl: {
            "q": keyword,
            "count": num_results,
            "country": gl,
            "search_lang": hl,
        },
        request_param_kwargs={
            "time_period_target": "freshness",
            "time_period_transform": lambda value: {
                "day": "pd",
                "week": "pw",
                "month": "pm",
                "year": "py",
            }.get(value),
            "safe_search_target": "safesearch",
            "pagination_target": "offset",
            "pagination_source_key": "offset",
        },
        normalize_kwargs={
            "organic_key": "results",
            "organic_kwargs": {
                "url_fields": ("url", "link"),
                "snippet_fields": ("description", "snippet"),
            },
        },
        headers_factory=lambda api_key: {"X-Subscription-Token": api_key, "Accept": "application/json"},
        payload_transform=lambda payload: payload.get("web", {}) if isinstance(payload.get("web"), dict) else {},
    )

# CLASS_CONTRACT: SerpstackAdapter
# Purpose: Query Serpstack and normalize confirmed organic SERP fields.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class SerpstackAdapter(SERPProviderAdapter):
    provider_name = "serpstack"
    env_var = "SERPSTACK_KEY"
    endpoint = "https://api.serpstack.com/search"
    max_per_page = 10
    start_param = "start"
    _SEARCH_SPEC = _SerpSearchSpec(
        provider_name="serpstack",
        endpoint=endpoint,
        base_params_factory=lambda api_key, keyword, num_results, gl, hl: {
            "access_key": api_key,
            "query": keyword,
            "num": num_results,
            "gl": gl,
            "hl": hl,
        },
        request_param_kwargs={
            "device_target": "device",
            "search_type_target": "type",
            "search_type_transform": lambda value: {
                "images": "images",
                "videos": "videos",
                "news": "news",
                "shopping": "shopping",
            }.get(value),
            "google_domain_target": "google_domain",
            "pagination_target": "start",
            "pagination_source_key": "start",
        },
        normalize_kwargs={
            "organic_key": "organic_results",
            "organic_kwargs": {
                "title_fields": ("title", "name"),
                "url_fields": ("url", "link", "destination"),
                "snippet_fields": ("snippet", "description", "text"),
            },
        },
    )



# FUNCTION_CONTRACT: _traject_data_normalize
# Purpose: Normalize ScaleSERP and ValueSERP payloads that share Traject Data response shapes.
# Input: keyword (str), provider (str), payload (dict)
# Output: SERPSearchResult
# Side Effects: none
# Business Rules: Organic, related searches, and knowledge graph are normalized when present; PAA remains empty unless provider schema adds a known field later.
# Failure Modes: malformed payloads produce empty feature lists.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def _traject_data_normalize(keyword: str, provider: str, payload: Dict[str, Any]) -> SERPSearchResult:
    return _normalize_serp_payload(
        keyword,
        provider,
        payload,
        organic_key="organic_results",
        related_key="related_searches",
        knowledge_graph_key="knowledge_graph",
    )


# CLASS_CONTRACT: ScaleSERPAdapter
# Purpose: Query ScaleSERP and normalize Traject Data SERP response fields.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class ScaleSERPAdapter(SERPProviderAdapter):
    provider_name = "scaleserp"
    env_var = "SCALESERP_KEY"
    endpoint = "https://api.scaleserp.com/search"
    max_per_page = 10
    start_param = "page"
    _SEARCH_SPEC = _SerpSearchSpec(
        provider_name="scaleserp",
        endpoint=endpoint,
        base_params_factory=lambda api_key, keyword, num_results, gl, hl: {
            "api_key": api_key,
            "q": keyword,
            "num": num_results,
            "gl": gl,
            "hl": hl,
        },
        request_param_kwargs={
            "time_period_target": "time_period",
            "time_period_transform": lambda value: value if value != "any" else None,
            "safe_search_target": "safe",
            "location_target": "location",
            "uule_target": "uule",
            "pagination_target": "page",
            "pagination_source_key": "page",
            "device_target": None,
        },
        normalize_kwargs={
            "organic_key": "organic_results",
            "related_key": "related_searches",
            "knowledge_graph_key": "knowledge_graph",
        },
    )



# CLASS_CONTRACT: ValueSERPAdapter
# Purpose: Query ValueSERP and normalize Traject Data SERP response fields.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class ValueSERPAdapter(SERPProviderAdapter):
    provider_name = "valueserp"
    env_var = "VALUESERP_KEY"
    endpoint = "https://api.valueserp.com/search"
    max_per_page = 10
    start_param = "page"
    _SEARCH_SPEC = _SerpSearchSpec(
        provider_name="valueserp",
        endpoint=endpoint,
        base_params_factory=lambda api_key, keyword, num_results, gl, hl: {
            "api_key": api_key,
            "q": keyword,
            "num": num_results,
            "gl": gl,
            "hl": hl,
        },
        request_param_kwargs={
            "device_target": "device",
            "search_type_target": "search_type",
            "search_type_transform": lambda value: value if value != "web" else None,
            "time_period_target": "time_period",
            "time_period_transform": lambda value: value if value != "any" else None,
            "safe_search_target": "safe",
            "location_target": "location",
            "uule_target": "uule",
            "pagination_target": "page",
            "pagination_source_key": "page",
        },
        normalize_kwargs={
            "organic_key": "organic_results",
            "related_key": "related_searches",
            "knowledge_graph_key": "knowledge_graph",
        },
    )



# CLASS_CONTRACT: SERPClient
# Purpose: Execute retry-aware SERP searches through one configured provider adapter.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
class SERPClient:
    # FUNCTION_CONTRACT: SERPClient.__init__
    # Purpose: Configure one SERP provider client with auth, adapter, locale, result count, and timeout.
    # Input: provider (str), api_key (str), adapter (SERPProviderAdapter), num_results (int), gl (str), hl (str), timeout (int)
    # Output: None
    # Side Effects: stores client configuration.
    # Business Rules: Empty API keys are rejected defensively; factory handles graceful degradation before construction.
    # Failure Modes: ValueError for missing API key.
    # LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
    def __init__(
        self,
        provider: str,
        api_key: str,
        adapter: SERPProviderAdapter,
        num_results: int = 10,
        gl: str = "ua",
        hl: str = "uk",
        timeout: int = 30,
        extra_params: dict | None = None,
    ) -> None:
        # Allow empty API key for browser providers (API-key-free)
        if not api_key and provider != "browser_cloakbrowser":
            raise ValueError("SERP API key is required")
        self.provider = provider
        self.api_key = api_key
        self.adapter = adapter
        self.num_results = num_results
        self.gl = gl
        self.hl = hl
        self.timeout = timeout
        self.extra_params = extra_params

    # FUNCTION_CONTRACT: _search_with_retry
    # Purpose: Run one adapter search with the required retry policy for transient HTTP failures.
    # Input: query (str)
    # Output: SERPSearchResult
    # Side Effects: performs outbound HTTP through the configured adapter; emits retry-driven provider calls.
    # Business Rules: Retries requests.RequestException and TimeoutError up to the adapter-specific max_retries value, defaulting to four attempts, with exponential backoff.
    # Failure Modes: Propagates final retriable exception to search() for structured failure conversion.
    # LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
    def _search_with_retry(self, query: str, num_results: int | None = None, extra_params: dict | None = None) -> SERPSearchResult:
        # SEMANTIC_BLOCK: block_serp_client_retry_search
        max_retries = getattr(self.adapter, "max_retries", None) or 4
        retrying = Retrying(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((requests.RequestException, TimeoutError)),
            reraise=True,
        )
        return retrying(
            self.adapter.search,
            query=query,
            num_results=num_results if num_results is not None else self.num_results,
            gl=self.gl,
            hl=self.hl,
            timeout=self.timeout,
            extra_params=extra_params if extra_params is not None else self.extra_params,
        )

    # FUNCTION_CONTRACT: SERPClient.search
    # Purpose: Search one keyword and return a successful or structured failed SERP result.
    # Input: query (str)
    # Output: SERPSearchResult
    # Side Effects: performs outbound HTTP through adapter; logs success/failure details.
    # Business Rules: Final retry exhaustion returns success=False instead of raising.
    # Failure Modes: Non-retriable exceptions also become structured failure results.
    # LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
    def search(self, query: str) -> SERPSearchResult:
        try:
            max_per_page = getattr(self.adapter, 'max_per_page', self.num_results)
            start_param = getattr(self.adapter, 'start_param', None)

            # Fast path: no pagination needed (provider supports num directly)
            if start_param is None:
                result = self._search_with_retry(query)
                if result.success:
                    logger.info(f"SERP search completed for '{query}' via {self.provider} ({len(result.organic)}/{self.num_results} results)")
                else:
                    logger.error(f"SERP search failed for '{query}' via {self.provider}: {result.error}")
                return result

            # Pagination: collect results across multiple pages
            all_organic: list[SERPOrganicResult] = []
            all_related: list[str] = []
            all_paa: list[SERPPeopleAlsoAsk] = []
            knowledge_graph: SERPKnowledgeGraph | None = None
            first_success = False
            page_num = 1
            cumulative_offset = 0  # only used by start/offset-based pagination
            max_pages = 10  # Safety limit

            while len(all_organic) < self.num_results and page_num <= max_pages:
                remaining = self.num_results - len(all_organic)
                page_num_results = min(remaining, max_per_page)

                page_extra = dict(self.extra_params or {})
                if start_param == "page":
                    page_extra[start_param] = page_num
                else:
                    page_extra[start_param] = cumulative_offset

                result = self._search_with_retry(query, num_results=page_num_results, extra_params=page_extra)

                if not result.success:
                    if not first_success:
                        logger.error(f"SERP search failed for '{query}' (page {page_num}): {result.error}")
                        return result
                    break

                if not first_success:
                    all_related = result.related_searches
                    all_paa = result.people_also_ask
                    knowledge_graph = result.knowledge_graph
                    first_success = True

                all_organic.extend(result.organic)
                cumulative_offset += len(result.organic)
                logger.info(f"SERP page {page_num} for '{query}': got {len(result.organic)} results (total {len(all_organic)}/{self.num_results})")

                if len(result.organic) < page_num_results:
                    break  # API returned all available results

                page_num += 1

            if page_num > max_pages:
                logger.warning(f"SERP pagination for '{query}' exceeded {max_pages} pages; returning partial results")

            if not first_success:
                return _failure_result(query, self.provider, Exception("No results from any page"))

            result = _make_result(
                keyword=query,
                provider=self.provider,
                organic=all_organic[:self.num_results],
                related_searches=all_related,
                people_also_ask=all_paa,
                knowledge_graph=knowledge_graph,
            )
            logger.info(f"SERP search completed for '{query}' via {self.provider} ({len(result.organic)}/{self.num_results} results)")
            return result
        except (requests.RequestException, TimeoutError) as exc:
            logger.error(f"SERP search failed after retries for '{query}': {exc}")
            return _failure_result(query, self.provider, exc)
        except Exception as exc:
            logger.error(f"SERP search failed for '{query}': {exc}", exc_info=True)
            return _failure_result(query, self.provider, exc)

    # FUNCTION_CONTRACT: SERPClient.search_batch
    # Purpose: Search multiple keywords while isolating failures per keyword.
    # Input: queries (list[str]), progress_callback (Callable | None)
    # Output: list[SERPSearchResult]
    # Side Effects: performs multiple outbound HTTP searches; invokes optional progress callback after each keyword.
    # Business Rules: Every input query receives one result object even when a callback or search path fails.
    # Failure Modes: Unexpected per-keyword exceptions become structured failure results.
    # LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
    def search_batch(
        self,
        queries: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[SERPSearchResult]:
        # SEMANTIC_BLOCK: block_serp_client_batch_iterate
        results: List[SERPSearchResult] = []
        total = len(queries)
        for index, query in enumerate(queries, start=1):
            try:
                results.append(self.search(query))
            except Exception as exc:
                logger.error(f"SERP batch item failed for '{query}': {exc}", exc_info=True)
                results.append(_failure_result(query, self.provider, exc))
            finally:
                if progress_callback:
                    try:
                        progress_callback(index, total)
                    except Exception as exc:
                        logger.warning(f"SERP progress callback failed: {exc}")
        return results


# CLASS_CONTRACT: BrowserCloakbrowserAdapter
# Purpose: API-key-free SERP provider using browser automation via cloakbrowser/playwright
# LINKS: .planning/phases/12-browser-google-parsing-prompt-cleanup/12-01-PLAN.md#task-12-05
class BrowserCloakbrowserAdapter(SERPProviderAdapter):

    provider_name = "browser_cloakbrowser"
    env_var = ""  # No API key required
    max_retries = 1

    # FUNCTION_CONTRACT: BrowserCloakbrowserAdapter.__init__
    # Purpose: Store browser-adapter defaults without requiring API credentials.
    # Input: api_key (str | None), num_results (int), kwargs (browser_config optional)
    # Output: None
    # Side Effects: none
    # Business Rules: Ignores API key because local browser parsing is API-key-free.
    # Failure Modes: none.
    # LINKS: .planning/phases/12-browser-google-parsing-prompt-cleanup/12-01-PLAN.md#task-12-05
    def __init__(self, api_key: Optional[str] = None, num_results: int = 10, **kwargs: Any) -> None:
        self.num_results = num_results
        self.browser_config = kwargs.get("browser_config") or None

    # FUNCTION_CONTRACT: BrowserCloakbrowserAdapter.search
    # Purpose: Execute a browser-backed Google SERP query and normalize it to the shared SERP model.
    # Input: query (str), num_results (int), gl (str), hl (str), timeout (int), extra_params (dict | None)
    # Output: SERPSearchResult
    # Side Effects: Launches local browser automation through BrowserScraper.
    # Business Rules: Does not require API credentials; failure returns structured SERPSearchResult instead of raising.
    # Failure Modes: Browser disabled, missing dependencies, launch errors, Google blocks, and parser errors become success=False.
    # LINKS: .planning/phases/12-browser-google-parsing-prompt-cleanup/12-01-PLAN.md#task-12-05
    def search(
        self,
        query: str,
        num_results: int,
        gl: str,
        hl: str,
        timeout: int,
        extra_params: dict | None = None,
    ) -> SERPSearchResult:
        from utils.browser_scraper import create_browser_scraper, get_dependency_install_message

        extra = dict(extra_params or {})
        google_domain = extra.get("google_domain") or ("google.com.ua" if gl == "ua" else "google.com")
        locale = extra.get("locale") or f"{hl}-{gl.upper()}"
        params = {
            "google_domain": google_domain,
            "total_results_target": num_results or self.num_results,
            "pages_max": max(1, min(10, ((num_results or self.num_results) + 9) // 10)),
            "gl": gl,
            "hl": hl,
            "locale": locale,
            "timeout_seconds": timeout,
        }
        for key in ("device", "search_type", "time_period", "safe_search", "location", "uule"):
            if extra.get(key):
                params[key] = extra[key]

        browser_config = self.browser_config
        if browser_config is None:
            settings = load_config()
            browser_settings = dict(settings.get("scraper", {}))
            raw_headless = extra["headless"] if "headless" in extra else settings.get("serp", {}).get("headless", False)
            if isinstance(raw_headless, str):
                browser_settings["headless"] = raw_headless.strip().lower() in {"1", "true", "yes", "on"}
            else:
                browser_settings["headless"] = bool(raw_headless)
            browser_config = browser_settings

        scraper = create_browser_scraper(config=browser_config)
        if scraper is None:
            return SERPSearchResult(
                keyword=query,
                provider=self.provider_name,
                success=False,
                error=f"Browser scraping is disabled or unavailable. {get_dependency_install_message()}",
            )

        result = scraper.scrape_serp(query, params)

        if not result.success:
            return SERPSearchResult(
                keyword=query,
                provider=self.provider_name,
                success=False,
                error=", ".join(result.errors or ["Unknown browser SERP error"]),
            )

        parsed = result.parsed_content or {}
        organic_payload = parsed.get("results") or parsed.get("organic") or []
        organic = _normalize_organic_results(organic_payload, url_fields=("url", "link"))
        related_searches = _normalize_related_searches(parsed.get("related_searches") or [])
        people_also_ask = _normalize_people_also_ask(parsed.get("people_also_ask") or [])
        if not organic:
            status = (result.metadata or {}).get("status")
            if status == "blocked":
                error = "Google returned 429/block page"
            else:
                error = "Google SERP returned no organic results"
            return SERPSearchResult(
                keyword=query,
                provider=self.provider_name,
                success=False,
                error=error,
            )

        return _make_result(
            keyword=query,
            provider=self.provider_name,
            organic=organic,
            people_also_ask=people_also_ask,
            related_searches=related_searches,
        )


PROVIDER_REGISTRY = {
    "serper_dev": ("SERPER_API_KEY", SerperDevAdapter),
    "serpapi": ("SERPAPI_KEY", SerpApiAdapter),
    "brave_search": ("BRAVE_SEARCH_API_KEY", BraveSearchAdapter),
    "searchapi_io": ("SEARCHAPI_IO_KEY", SearchApiIoAdapter),
    "zenserp": ("ZENSERP_KEY", ZenserpAdapter),
    "scraperapi": ("SCRAPERAPI_KEY", ScraperApiAdapter),
    "dataforseo": (("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"), DataForSeoAdapter),
    "serpstat": ("SERPSTAT_TOKEN", SerpstatAdapter),
    "semrush": ("SEMRUSH_API_KEY", SemrushAdapter),
    "serpstack": ("SERPSTACK_KEY", SerpstackAdapter),
    "scaleserp": ("SCALESERP_KEY", ScaleSERPAdapter),
    "valueserp": ("VALUESERP_KEY", ValueSERPAdapter),
    "browser_cloakbrowser": ("", BrowserCloakbrowserAdapter),  # API-key-free
}


# FUNCTION_CONTRACT: create_serp_client
# Purpose: Build a configured SERPClient when the selected provider has an API key.
# Input: config (dict | None)
# Output: SERPClient | None
# Side Effects: reads process environment for provider API keys; logs missing/invalid provider warnings.
# Business Rules: Factory is the graceful degradation boundary and returns None instead of raising when auth is absent.
# Failure Modes: ValueError from direct SERPClient construction if an empty key slips past validation.
# LINKS: requirements.xml#UC-006, verification-plan.xml#V-MOD-006
def create_serp_client(config: Optional[dict] = None) -> Optional[SERPClient]:
    serp_config = config if config is not None else load_config().get("serp", {})
    provider = serp_config.get("provider", "serper_dev")
    provider_entry = PROVIDER_REGISTRY.get(provider)
    if provider_entry is None:
        logger.warning(f"Unknown SERP provider configured: {provider}")
        return None

    env_var, adapter_class = provider_entry

    # Handle API-key-free providers (env_var is empty string)
    if env_var == "":
        # Browser provider doesn't need an API key
        api_key = "no-key-required"
        logger.info(f"Using API-key-free SERP provider: {provider}")
    # Handle tuple env_var (e.g., DataForSEO requires LOGIN + PASSWORD)
    elif isinstance(env_var, tuple):
        values = [os.environ.get(v, "") for v in env_var]
        if not all(values):
            logger.warning(f"SERP API keys missing for provider {provider} ({', '.join(env_var)})")
            return None
        api_key = ":".join(values)
    else:
        api_key = os.environ.get(env_var, "")
        if not api_key:
            logger.warning(f"SERP API key missing for provider {provider} ({env_var})")
            return None

    adapter = adapter_class(api_key)
    extra_params: dict[str, Any] = {}
    for key in ("device", "search_type", "time_period", "google_domain", "location", "uule", "headless"):
        value = serp_config.get(key)
        if value is not None and value != "" and value != "any":
            extra_params[key] = value
    # Only send safe_search when active; "off" is the default for all providers
    safe_val = serp_config.get("safe_search")
    if safe_val == "active":
        extra_params["safe_search"] = safe_val
    return SERPClient(
        provider=provider,
        api_key=api_key,
        adapter=adapter,
        num_results=serp_config.get("num_results", 10),
        gl=serp_config.get("gl", "ua"),
        hl=serp_config.get("hl", "uk"),
        timeout=serp_config.get("timeout_seconds", 30),
        extra_params=extra_params if extra_params else None,
    )
