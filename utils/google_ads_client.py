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

try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
except ImportError:
    GoogleAdsClient = None
    GoogleAdsException = Exception


class GoogleAdsHandler:
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

    def _get_customer_currency_code(self) -> str:
        """Read the Google Ads account currency for bid micros conversion."""
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

    @staticmethod
    def _merge_monthly_volumes(
        existing_volumes: List[Dict[str, Any]], metrics: Any
    ) -> List[Dict[str, Any]]:
        """Merge monthly volumes across language passes without double counting."""
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

    @staticmethod
    def _competition_name(metrics: Any) -> str:
        return str(getattr(metrics, "competition", "UNSPECIFIED")).split(".")[-1]

    def _normalize_languages(self) -> List[str]:
        if isinstance(self.language_id, list):
            return [str(lang_id) for lang_id in self.language_id]
        return [str(self.language_id)]

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

    def _init_client(self) -> Optional[Any]:
        """Initialize Google Ads client with graceful degradation (improvement #15)."""
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

    def get_keyword_metrics(self, keywords: List[str]) -> pd.DataFrame:
        """
        Fetch historical metrics for a list of keywords using KeywordPlanIdeaService.
        Supports aggregation across multiple languages.

        Returns empty DataFrame gracefully if Google Ads is unavailable (improvement #15).
        """
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
            keyword_plan_idea_service = self.client.get_service(
                "KeywordPlanIdeaService"
            )
            geo_target: str = self.client.get_service(
                "GeoTargetConstantService"
            ).geo_target_constant_path(self.location_id)
            google_ads_service = self.client.get_service("GoogleAdsService")
            source_currency_code = self._get_customer_currency_code()
            aggregated_metrics: Dict[str, Dict[str, Any]] = {}

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

                    logger.log_api_request(
                        "google_ads",
                        f"Raw metrics for '{kw}'",
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

                    if kw not in aggregated_metrics:
                        aggregated_metrics[kw] = self._create_metric_bucket(kw, metrics)
                        continue

                    self._merge_metric_bucket(aggregated_metrics[kw], metrics)

            logger.log_api_response(
                "google_ads",
                0,
                f"Got aggregated metrics for {len(aggregated_metrics)} keywords",
            )
            return self._finalize_metric_buckets(
                aggregated_metrics,
                source_currency_code,
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

    def get_keyword_ideas(
        self,
        seed_keywords: List[str],
        page_url: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> pd.DataFrame:
        """Generate keyword ideas using KeywordPlanIdeaService.GenerateKeywordIdeas."""
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
            keyword_plan_idea_service = self.client.get_service(
                "KeywordPlanIdeaService"
            )
            geo_target: str = self.client.get_service(
                "GeoTargetConstantService"
            ).geo_target_constant_path(self.location_id)
            google_ads_service = self.client.get_service("GoogleAdsService")
            source_currency_code = self._get_customer_currency_code()
            aggregated_metrics: Dict[str, Dict[str, Any]] = {}
            resolved_source_url = source_url or page_url or ""
            if page_url and cleaned_keywords:
                seed_strategy = "keyword_and_url_seed"
            elif page_url:
                seed_strategy = "url_seed"
            else:
                seed_strategy = "keyword_seed"

            for lang_id in self._normalize_languages():
                request = self.client.get_type("GenerateKeywordIdeasRequest")
                request.customer_id = self.customer_id
                request.geo_target_constants.append(geo_target)
                request.keyword_plan_network = (
                    self.client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
                )
                request.language = google_ads_service.language_constant_path(lang_id)
                request.include_adult_keywords = False

                if page_url and cleaned_keywords:
                    request.keyword_and_url_seed.url = page_url
                    request.keyword_and_url_seed.keywords.extend(cleaned_keywords)
                elif page_url:
                    request.url_seed.url = page_url
                else:
                    request.keyword_seed.keywords.extend(cleaned_keywords)

                logger.log_api_request(
                    "google_ads",
                    f"GenerateKeywordIdeas (Lang: {lang_id})",
                    {
                        "count": len(cleaned_keywords),
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

                    logger.log_api_request(
                        "google_ads",
                        f"Raw keyword idea metrics for '{kw}'",
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
            return self._finalize_metric_buckets(
                aggregated_metrics,
                source_currency_code,
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
