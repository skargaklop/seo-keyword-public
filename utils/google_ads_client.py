"""
Google Ads client module - fetches keyword metrics.
Graceful degradation added (improvement #15).
Type hints added (improvement #5).
"""

import os
from typing import List, Dict, Optional, Any, Union

import pandas as pd

from config.settings import GOOGLE_ADS_CONFIG
from utils.currency_rates import CurrencyRateService
from utils.logger import logger
from utils.request_cache import build_cache_key, request_cache

try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
except ImportError:
    GoogleAdsClient = None
    GoogleAdsException = Exception


# MODULE_CONTRACT: google_ads_client
# Purpose: Google Ads API integration for keyword ideas and search volume metrics
# Rationale: Provides keyword performance data (volume, competition, CPC) from Google Ads for SEO analysis
# Dependencies: google-ads SDK, config.settings, utils.currency_rates, utils.logger
# Exports: GoogleAdsHandler (class with get_keyword_ideas, get_keyword_metrics)
# LINKS: requirements.xml#UC-001, technology.xml#SVC-003, development-plan.xml#MOD-003
# MODULE_MAP: google_ads_client
# Public Functions: GoogleAdsHandler.__init__(), get_keyword_ideas(), get_keyword_metrics()
# Private Helpers: _init_client(), _get_customer_currency_code(), _normalize_languages(), _build_ads_request_params(), _build_ads_cache_context(), _prepare_ads_services(), _get_cached_ads_dataframe(), _store_ads_cache_result(), _finalize_and_cache_ads_result(), _log_ads_metric_snapshot(), _create_metric_bucket(), _merge_metric_bucket(), _finalize_metric_buckets(), _merge_monthly_volumes(), _competition_name()
# Key Semantic Blocks: block_ads_api_init, block_ads_keyword_metrics, block_ads_keyword_ideas
# Critical Flows: Client init with graceful degradation -> keyword metrics aggregation across languages -> CPC currency conversion
# Verification: verification-plan.xml#V-MOD-003
# CHANGE_SUMMARY: Replaced shallow GRACE markers with complete module-level contracts

# CLASS_CONTRACT: GoogleAdsHandler
# Purpose: Fetch Google Ads keyword ideas, metrics, and account currency metadata.
# LINKS: requirements.xml#UC-001, technology.xml#SVC-003
class GoogleAdsHandler:
    # FUNCTION_CONTRACT: __init__
    # Purpose: Initialize the surrounding object state.
    # Input: location_id (Optional[str] = None), language_id (Optional[Union[str, List[str]]] = None), target_currency_code (Optional[str] = None), exchange_rate_service (Optional[Any] = None)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def __init__(
        self,
        location_id: Optional[str] = None,
        language_id: Optional[Union[str, List[str]]] = None,
        target_currency_code: Optional[str] = None,
        exchange_rate_service: Optional[Any] = None,
    ) -> None:
        customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "").strip()
        self.customer_id: Optional[str] = customer_id or None
        self.location_id: str = (
            location_id if location_id else GOOGLE_ADS_CONFIG.get("location_id", "2840")
        )
        self.language_id: Union[str, List[str]] = (
            language_id if language_id else GOOGLE_ADS_CONFIG.get("language_id", "1000")
        )
        self.target_currency_code: str = str(
            target_currency_code
            if target_currency_code
            else GOOGLE_ADS_CONFIG.get("currency_code", "UAH")
        ).upper()
        self.exchange_rate_service = exchange_rate_service or CurrencyRateService
        self.client: Optional[Any] = self._init_client()
    # FUNCTION_CONTRACT: _get_customer_currency_code
    # Purpose: Implement the  get customer currency code helper for this module.
    # Input: (none)
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _get_customer_currency_code(self) -> str:
        if not self.client or not self.customer_id:
            return ""

        try:
            google_ads_service = self.client.get_service("GoogleAdsService")
            response = google_ads_service.search(
                customer_id=self.customer_id,
                query="SELECT customer.currency_code FROM customer LIMIT 1",
            )
            for row in response:
                currency_code = str(row.customer.currency_code).upper()
                if currency_code:
                    return currency_code
        except Exception as exc:
            logger.warning(f"Failed to resolve Google Ads account currency: {exc}")

        return ""
    # FUNCTION_CONTRACT: _merge_monthly_volumes
    # Purpose: Implement the  merge monthly volumes helper for this module.
    # Input: existing_volumes (List[Dict[str, Any]]), metrics (Any)
    # Output: List[Dict[str, Any]]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _merge_monthly_volumes(
        existing_volumes: List[Dict[str, Any]], metrics: Any
    ) -> List[Dict[str, Any]]:
        merged: Dict[tuple[int, str], int] = {
            (item["year"], item["month"]): item["searches"] for item in existing_volumes
        }
        monthly_volumes = getattr(metrics, "monthly_search_volumes", None) or []
        for monthly_search in monthly_volumes:
            key = (monthly_search.year, str(monthly_search.month).split(".")[-1])
            merged[key] = max(merged.get(key, 0), monthly_search.monthly_searches)

        return [
            {"year": year, "month": month, "searches": searches}
            for (year, month), searches in sorted(merged.items())
        ]
    # FUNCTION_CONTRACT: _competition_name
    # Purpose: Implement the  competition name helper for this module.
    # Input: metrics (Any)
    # Output: str
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    @staticmethod
    def _competition_name(metrics: Any) -> str:
        return str(getattr(metrics, "competition", "UNSPECIFIED")).split(".")[-1]
    # FUNCTION_CONTRACT: _normalize_languages
    # Purpose: Implement the  normalize languages helper for this module.
    # Input: (none)
    # Output: List[str]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _normalize_languages(self) -> List[str]:
        if isinstance(self.language_id, list):
            return [str(lang_id) for lang_id in self.language_id]
        return [str(self.language_id)]

    # FUNCTION_CONTRACT: _build_ads_request_params
    # Purpose: Build normalized request params for Google Ads cache keys.
    # Input: operation (str), keywords (List[str]), page_url (Optional[str] = None)
    # Output: Dict[str, Any]
    # Side Effects: none.
    # Business Rules: Preserves the current keyword normalization and language ordering used by cache keys.
    # Failure Modes: never raises.
    # LINKS: PLAN 10-02 Task 6
    def _build_ads_request_params(
        self,
        operation: str,
        keywords: List[str],
        page_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_keywords = sorted(
            str(k).lower().strip() for k in keywords if k and str(k).strip()
        )

        if isinstance(self.language_id, list):
            lang_str = ",".join(sorted(str(language) for language in self.language_id))
        else:
            lang_str = str(self.language_id)

        params: Dict[str, Any] = {
            "operation": operation,
            "keywords": normalized_keywords,
            "location_id": str(self.location_id),
            "language_id": lang_str,
            "currency_code": str(self.target_currency_code).upper(),
        }
        if page_url is not None:
            params["page_url"] = str(page_url or "").strip()
        return params

    # FUNCTION_CONTRACT: _get_cached_ads_dataframe
    # Purpose: Resolve a cached Google Ads payload into the stored return shape.
    # Input: cache_key (str), force_refresh (bool = False)
    # Output: Optional[Any]
    # Side Effects: Logs cache hits and reconstructs DataFrames from serialized cache payloads.
    # Business Rules: Preserves the current dict/list/raw payload handling for cached results.
    # Failure Modes: never raises; returns None on cache miss or empty payload.
    # LINKS: PLAN 10-02 Task 6
    def _get_cached_ads_dataframe(
        self,
        cache_key: str,
        force_refresh: bool = False,
    ) -> Optional[Any]:
        cached = request_cache.get(cache_key, force_refresh=force_refresh)
        if cached is None:
            return None

        logger.info(
            f"[GRACE:block_ads_cache_lookup:HIT] kind=ads key={cache_key[:8]}... "
            f"hits={cached.get('cache_hit_count', 0)}"
        )
        payload = cached.get("result", {}).get("payload")
        if payload is None:
            return None
        if isinstance(payload, dict) and "data" in payload:
            return pd.DataFrame(payload["data"], columns=payload.get("columns"))
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        return payload

    # FUNCTION_CONTRACT: _store_ads_cache_result
    # Purpose: Persist a successful Google Ads result in the shared cache.
    # Input: cache_key (str), request_params (Dict[str, Any]), result (Any)
    # Output: None
    # Side Effects: Writes one cache record with the google_ads provider tag.
    # Business Rules: Preserves the current cache record shape used by keyword metrics and ideas.
    # Failure Modes: Propagates upstream exceptions from request_cache.set unchanged.
    # LINKS: PLAN 10-02 Task 6
    def _store_ads_cache_result(
        self,
        cache_key: str,
        request_params: Dict[str, Any],
        result: Any,
    ) -> None:
        request_cache.set(
            kind="ads",
            cache_key=cache_key,
            request_params=request_params,
            result=result,
            provider="google_ads",
        )

    # FUNCTION_CONTRACT: _build_ads_cache_context
    # Purpose: Assemble the normalized request params, cache key, and cache hit payload for Google Ads calls.
    # Input: operation (str), keywords (List[str]), page_url (Optional[str] = None), force_refresh (bool = False)
    # Output: tuple[Dict[str, Any], str, Optional[Any]]
    # Side Effects: Logs cache hits through the shared cache lookup helper.
    # Business Rules: Preserves the same cache key derivation for keyword metrics and keyword ideas.
    # Failure Modes: never raises.
    # LINKS: PLAN 10-02 Task 6
    def _build_ads_cache_context(
        self,
        operation: str,
        keywords: List[str],
        page_url: Optional[str] = None,
        force_refresh: bool = False,
    ) -> tuple[Dict[str, Any], str, Optional[Any]]:
        params = self._build_ads_request_params(
            operation,
            keywords,
            page_url=page_url,
        )
        cache_key = build_cache_key(
            kind="ads",
            provider="google_ads",
            params=params,
        )
        cached_payload = self._get_cached_ads_dataframe(
            cache_key,
            force_refresh=force_refresh,
        )
        return params, cache_key, cached_payload

    # FUNCTION_CONTRACT: _prepare_ads_services
    # Purpose: Load the shared Google Ads services used by keyword metrics and keyword ideas.
    # Input: (none)
    # Output: tuple[Any, str, Any, Dict[str, Dict[str, Any]]]
    # Side Effects: May resolve the account currency through Google Ads.
    # Business Rules: Preserves the shared service lookup sequence and empty aggregation state.
    # Failure Modes: Propagates upstream exceptions from service lookup.
    # LINKS: PLAN 10-02 Task 6
    def _prepare_ads_services(
        self,
    ) -> tuple[Any, str, Any, Dict[str, Dict[str, Any]]]:
        keyword_plan_idea_service = self.client.get_service("KeywordPlanIdeaService")
        geo_target: str = self.client.get_service(
            "GeoTargetConstantService"
        ).geo_target_constant_path(self.location_id)
        google_ads_service = self.client.get_service("GoogleAdsService")
        source_currency_code = self._get_customer_currency_code()
        aggregated_metrics: Dict[str, Dict[str, Any]] = {}
        return (
            keyword_plan_idea_service,
            geo_target,
            google_ads_service,
            source_currency_code,
            aggregated_metrics,
        )

    # FUNCTION_CONTRACT: _finalize_and_cache_ads_result
    # Purpose: Finalize Google Ads metrics and persist the resulting DataFrame in cache.
    # Input: aggregated_metrics (Dict[str, Dict[str, Any]]), source_currency_code (str), cache_key (str), request_params (Dict[str, Any])
    # Output: pd.DataFrame
    # Side Effects: Stores the final DataFrame in request_cache.
    # Business Rules: Preserves the current DataFrame finalization and caching path.
    # Failure Modes: Propagates upstream exceptions from the finalizer or cache write.
    # LINKS: PLAN 10-02 Task 6
    def _finalize_and_cache_ads_result(
        self,
        aggregated_metrics: Dict[str, Dict[str, Any]],
        source_currency_code: str,
        cache_key: str,
        request_params: Dict[str, Any],
    ) -> pd.DataFrame:
        result_df = self._finalize_metric_buckets(
            aggregated_metrics,
            source_currency_code,
        )
        self._store_ads_cache_result(cache_key, request_params, result_df)
        return result_df

    # FUNCTION_CONTRACT: _log_ads_metric_snapshot
    # Purpose: Log the raw Google Ads metric snapshot before aggregation.
    # Input: metric_label (str), keyword (str), metrics (Any)
    # Output: None
    # Side Effects: Writes a structured API request log entry.
    # Business Rules: Preserves the exact fields logged for metrics and keyword idea metrics.
    # Failure Modes: never raises.
    # LINKS: PLAN 10-02 Task 6
    def _log_ads_metric_snapshot(self, metric_label: str, keyword: str, metrics: Any) -> None:
        logger.log_api_request(
            "google_ads",
            f"Raw {metric_label} for '{keyword}'",
            {
                "avg_searches": getattr(metrics, "avg_monthly_searches", 0),
                "competition": str(getattr(metrics, "competition", "")),
                "comp_index": getattr(metrics, "competition_index", 0),
                "low_bid_micros": getattr(
                    metrics, "low_top_of_page_bid_micros", 0
                ),
                "high_bid_micros": getattr(
                    metrics, "high_top_of_page_bid_micros", 0
                ),
            },
        )
    # FUNCTION_CONTRACT: _create_metric_bucket
    # Purpose: Implement the  create metric bucket helper for this module.
    # Input: keyword (str), metrics (Any), source_url (str = '')
    # Output: Dict[str, Any]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _create_metric_bucket(
        self,
        keyword: str,
        metrics: Any,
        source_url: str = "",
    ) -> Dict[str, Any]:
        low_cpc = (
            getattr(metrics, "low_top_of_page_bid_micros", 0) / 1_000_000
            if getattr(metrics, "low_top_of_page_bid_micros", 0)
            else 0
        )
        high_cpc = (
            getattr(metrics, "high_top_of_page_bid_micros", 0) / 1_000_000
            if getattr(metrics, "high_top_of_page_bid_micros", 0)
            else 0
        )
        return {
            "Keyword": keyword,
            "Source URL": source_url,
            "Avg Monthly Searches": getattr(metrics, "avg_monthly_searches", 0) or 0,
            "Competition": self._competition_name(metrics),
            "Competition Index": getattr(metrics, "competition_index", 0) or 0,
            "Low CPC": low_cpc,
            "High CPC": high_cpc,
            "Monthly Volumes": self._merge_monthly_volumes([], metrics),
        }
    # FUNCTION_CONTRACT: _merge_metric_bucket
    # Purpose: Implement the  merge metric bucket helper for this module.
    # Input: existing_bucket (Dict[str, Any]), metrics (Any)
    # Output: None
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _merge_metric_bucket(
        self,
        existing_bucket: Dict[str, Any],
        metrics: Any,
    ) -> None:
        current_competition_index = getattr(metrics, "competition_index", 0) or 0
        if current_competition_index >= existing_bucket["Competition Index"]:
            existing_bucket["Competition"] = self._competition_name(metrics)

        existing_bucket["Avg Monthly Searches"] = max(
            existing_bucket["Avg Monthly Searches"],
            getattr(metrics, "avg_monthly_searches", 0) or 0,
        )
        existing_bucket["Competition Index"] = max(
            existing_bucket["Competition Index"],
            current_competition_index,
        )
        existing_bucket["Monthly Volumes"] = self._merge_monthly_volumes(
            existing_bucket["Monthly Volumes"], metrics
        )

        current_low = (
            getattr(metrics, "low_top_of_page_bid_micros", 0) / 1_000_000
            if getattr(metrics, "low_top_of_page_bid_micros", 0)
            else 0
        )
        current_high = (
            getattr(metrics, "high_top_of_page_bid_micros", 0) / 1_000_000
            if getattr(metrics, "high_top_of_page_bid_micros", 0)
            else 0
        )
        existing_bucket["Low CPC"] = max(existing_bucket["Low CPC"], current_low)
        existing_bucket["High CPC"] = max(existing_bucket["High CPC"], current_high)
    # FUNCTION_CONTRACT: _finalize_metric_buckets
    # Purpose: Implement the  finalize metric buckets helper for this module.
    # Input: aggregated_metrics (Dict[str, Dict[str, Any]]), source_currency_code (str)
    # Output: pd.DataFrame
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _finalize_metric_buckets(
        self,
        aggregated_metrics: Dict[str, Dict[str, Any]],
        source_currency_code: str,
    ) -> pd.DataFrame:
        final_data: List[Dict[str, Any]] = []
        for _, data in aggregated_metrics.items():
            output_currency_code = source_currency_code or self.target_currency_code
            if source_currency_code and source_currency_code != self.target_currency_code:
                try:
                    data["Low CPC"] = self.exchange_rate_service.convert_amount(
                        data["Low CPC"],
                        source_currency_code,
                        self.target_currency_code,
                    )
                    data["High CPC"] = self.exchange_rate_service.convert_amount(
                        data["High CPC"],
                        source_currency_code,
                        self.target_currency_code,
                    )
                    output_currency_code = self.target_currency_code
                except Exception as exc:
                    logger.warning(
                        "Failed to convert CPC values from "
                        f"{source_currency_code} to {self.target_currency_code}: {exc}"
                    )

            data["Low CPC"] = round(data["Low CPC"], 4)
            data["High CPC"] = round(data["High CPC"], 4)
            data["CPC Currency"] = output_currency_code
            monthly = data.pop("Monthly Volumes", [])
            data["Months With Data"] = len(
                [month for month in monthly if month["searches"] > 0]
            )
            final_data.append(data)

        return pd.DataFrame(final_data)
    # FUNCTION_CONTRACT: _init_client
    # Purpose: Implement the  init client helper for this module.
    # Input: (none)
    # Output: Optional[Any]
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path.
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001
    def _init_client(self) -> Optional[Any]:
        if GoogleAdsClient is None:
            logger.warning(
                "Google Ads SDK not installed. Keyword metrics will be unavailable."
            )
            return None

        try:
            if not self.customer_id:
                logger.warning(
                    "GOOGLE_ADS_CUSTOMER_ID is missing in environment. "
                    "Keyword metrics and ideas will be unavailable."
                )
                return None

            config: Dict[str, Any] = {
                "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
                "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
                "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
                "login_customer_id": os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
                "use_proto_plus": True,
            }

            if not all(config.values()):
                logger.warning(
                    "Google Ads credentials missing in environment. "
                    "Keywords will be shown without metrics (graceful degradation)."
                )
                return None

            return GoogleAdsClient.load_from_dict(config)

        except Exception as e:
            logger.error(f"Failed to initialize Google Ads Client: {e}")
            logger.warning(
                "Continuing without Google Ads metrics (graceful degradation)."
            )
            return None
    # FUNCTION_CONTRACT: get_keyword_metrics
    # Purpose: Implement the get keyword metrics helper for this module.
    # Input: keywords (List[str]), force_refresh (bool = False)
    # Output: pd.DataFrame
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path; checks cache before API call
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001, PLAN 10-02 Task 6
    def get_keyword_metrics(self, keywords: List[str], force_refresh: bool = False) -> pd.DataFrame:
        params, cache_key, cached_payload = self._build_ads_cache_context(
            "historical_metrics",
            keywords,
            force_refresh=force_refresh,
        )
        if cached_payload is not None:
            return cached_payload

        # Cache miss - call API
        logger.info(f"[GRACE:block_ads_cache_lookup:MISS] kind=ads key={cache_key[:8]}...")

        if not self.client:
            logger.warning(
                "Google Ads Client not available. Returning empty metrics "
                "(keywords will be shown without metrics)."
            )
            return pd.DataFrame()

        if not keywords:
            logger.warning("No keywords provided for metrics lookup.")
            return pd.DataFrame()

        try:
            (
                keyword_plan_idea_service,
                geo_target,
                google_ads_service,
                source_currency_code,
                aggregated_metrics,
            ) = self._prepare_ads_services()

            for lang_id in self._normalize_languages():
                request = self.client.get_type(
                    "GenerateKeywordHistoricalMetricsRequest"
                )
                request.customer_id = self.customer_id
                request.keywords = keywords
                request.geo_target_constants.append(geo_target)
                request.keyword_plan_network = (
                    self.client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
                )
                request.language = google_ads_service.language_constant_path(lang_id)

                logger.log_api_request(
                    "google_ads",
                    f"GenerateKeywordHistoricalMetrics (Lang: {lang_id})",
                    {"count": len(keywords)},
                )

                response = (
                    keyword_plan_idea_service.generate_keyword_historical_metrics(
                        request=request
                    )
                )

                for result in response.results:
                    kw: str = result.text
                    metrics = result.keyword_metrics

                    self._log_ads_metric_snapshot("metrics", kw, metrics)

                    if kw not in aggregated_metrics:
                        aggregated_metrics[kw] = self._create_metric_bucket(kw, metrics)
                        continue

                    self._merge_metric_bucket(aggregated_metrics[kw], metrics)

            logger.log_api_response(
                "google_ads",
                0,
                f"Got aggregated metrics for {len(aggregated_metrics)} keywords",
            )
            return self._finalize_and_cache_ads_result(
                aggregated_metrics,
                source_currency_code,
                cache_key,
                params,
            )

        except GoogleAdsException as ex:
            logger.error(
                f"Google Ads API Request Failed with {len(ex.failure.errors)} errors:"
            )
            for error in ex.failure.errors:
                logger.error(f"	Error: {error.message}")
            logger.warning(
                "Returning empty metrics due to Google Ads error (graceful degradation)."
            )
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error in Google Ads request: {e}", exc_info=True)
            logger.warning(
                "Returning empty metrics due to unexpected error (graceful degradation)."
            )
            return pd.DataFrame()
    # FUNCTION_CONTRACT: get_keyword_ideas
    # Purpose: Get keyword ideas with cache lookup (Phase 10 Task 6).
    # Input: seed_keywords (List[str]), page_url (Optional[str] = None), source_url (Optional[str] = None)
    # Output: pd.DataFrame
    # Side Effects: Follows the existing state, file, or UI behavior implemented by this function.
    # Business Rules: Preserves the current validation and control flow for this call path; checks cache before API call
    # Failure Modes: Propagates upstream exceptions and existing fallback paths.
    # LINKS: requirements.xml#UC-001, PLAN 10-02 Task 6
    def get_keyword_ideas(
        self,
        seed_keywords: List[str],
        page_url: Optional[str] = None,
        source_url: Optional[str] = None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        params, cache_key, cached_payload = self._build_ads_cache_context(
            "keyword_ideas",
            seed_keywords,
            page_url=page_url,
            force_refresh=force_refresh,
        )
        if cached_payload is not None:
            return cached_payload

        # Cache miss - call API
        logger.info(f"[GRACE:block_ads_cache_lookup:MISS] kind=ads key={cache_key[:8]}...")

        if not self.client:
            logger.warning(
                "Google Ads Client not available. Returning empty keyword ideas."
            )
            return pd.DataFrame()

        cleaned_keywords = [keyword.strip() for keyword in seed_keywords if keyword.strip()]
        if not cleaned_keywords and not page_url:
            logger.warning("No URL or seed keywords provided for keyword ideas lookup.")
            return pd.DataFrame()

        try:
            (
                keyword_plan_idea_service,
                geo_target,
                google_ads_service,
                source_currency_code,
                aggregated_metrics,
            ) = self._prepare_ads_services()
            resolved_source_url = source_url or page_url or ""
            if page_url and cleaned_keywords:
                seed_strategy = "keyword_and_url_seed"
            elif page_url:
                seed_strategy = "url_seed"
            else:
                seed_strategy = "keyword_seed"

            # Google Ads API limits keyword_seed and keyword_and_url_seed to 20 keywords
            KEYWORD_SEED_BATCH_SIZE = 20

            for lang_id in self._normalize_languages():
                # Determine batches based on seed strategy
                if seed_strategy == "keyword_seed":
                    if len(cleaned_keywords) > KEYWORD_SEED_BATCH_SIZE:
                        logger.warning(
                            f"Google Ads keyword_seed supports max {KEYWORD_SEED_BATCH_SIZE} items. "
                            f"Batching {len(cleaned_keywords)} keywords into chunks of {KEYWORD_SEED_BATCH_SIZE}."
                        )
                    keyword_batches = [
                        cleaned_keywords[i:i + KEYWORD_SEED_BATCH_SIZE]
                        for i in range(0, len(cleaned_keywords), KEYWORD_SEED_BATCH_SIZE)
                    ]
                elif seed_strategy == "keyword_and_url_seed" and len(cleaned_keywords) > KEYWORD_SEED_BATCH_SIZE:
                    logger.warning(
                        f"Google Ads keyword_and_url_seed supports max {KEYWORD_SEED_BATCH_SIZE} items. "
                        f"Batching {len(cleaned_keywords)} keywords into chunks of {KEYWORD_SEED_BATCH_SIZE}."
                    )
                    keyword_batches = [
                        cleaned_keywords[i:i + KEYWORD_SEED_BATCH_SIZE]
                        for i in range(0, len(cleaned_keywords), KEYWORD_SEED_BATCH_SIZE)
                    ]
                else:
                    keyword_batches = [cleaned_keywords]

                for batch_idx, keyword_batch in enumerate(keyword_batches):
                    request = self.client.get_type("GenerateKeywordIdeasRequest")
                    request.customer_id = self.customer_id
                    request.geo_target_constants.append(geo_target)
                    request.keyword_plan_network = (
                        self.client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
                    )
                    request.language = google_ads_service.language_constant_path(lang_id)
                    request.include_adult_keywords = False

                    if page_url and keyword_batch:
                        request.keyword_and_url_seed.url = page_url
                        request.keyword_and_url_seed.keywords.extend(keyword_batch)
                    elif page_url:
                        request.url_seed.url = page_url
                    else:
                        request.keyword_seed.keywords.extend(keyword_batch)

                    logger.log_api_request(
                        "google_ads",
                        f"GenerateKeywordIdeas (Lang: {lang_id})"
                        + (f" Batch {batch_idx + 1}/{len(keyword_batches)}" if len(keyword_batches) > 1 else ""),
                        {
                            "count": len(keyword_batch),
                            "use_url_seed": bool(page_url),
                            "seed_strategy": seed_strategy,
                            "source_url": resolved_source_url,
                        },
                    )

                    response = keyword_plan_idea_service.generate_keyword_ideas(
                        request=request
                    )

                    for result in response:
                        kw: str = result.text
                        metrics = getattr(result, "keyword_idea_metrics", None)
                        if metrics is None:
                            continue

                        self._log_ads_metric_snapshot("keyword idea metrics", kw, metrics)

                        if kw not in aggregated_metrics:
                            aggregated_metrics[kw] = self._create_metric_bucket(
                                kw,
                                metrics,
                                source_url=resolved_source_url,
                            )
                            continue

                        self._merge_metric_bucket(aggregated_metrics[kw], metrics)

            logger.log_api_response(
                "google_ads",
                0,
                f"Got keyword ideas for {len(aggregated_metrics)} keywords",
            )
            return self._finalize_and_cache_ads_result(
                aggregated_metrics,
                source_currency_code,
                cache_key,
                params,
            )

        except GoogleAdsException as ex:
            logger.error(
                f"Google Ads keyword ideas request failed with {len(ex.failure.errors)} errors:"
            )
            for error in ex.failure.errors:
                logger.error(f"	Error: {error.message}")
            logger.warning(
                "Returning empty keyword ideas due to Google Ads error (graceful degradation)."
            )
            return pd.DataFrame()
        except Exception as e:
            logger.error(
                f"Unexpected error in Google Ads keyword ideas request: {e}",
                exc_info=True,
            )
            logger.warning(
                "Returning empty keyword ideas due to unexpected error (graceful degradation)."
            )
            return pd.DataFrame()
