from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from components.results import _build_google_trends_export_metadata
from utils.excel_exporter import ExcelExporter
from utils.google_trends_client import GoogleTrendsRequest


def test_google_trends_export_metadata_preserves_averages_and_request_context() -> None:
    result = SimpleNamespace(
        provider="cloakbrowser",
        data_confidence="medium",
        warnings=[],
        integrity_warnings=[],
        provider_metadata={"provider": "cloakbrowser"},
        cache_metadata={"cache_key": "abc123"},
        averages={"seo": 79.5094},
        request=GoogleTrendsRequest(keywords=["seo"], geo="UA", timeframe="today 12-m"),
    )

    metadata = _build_google_trends_export_metadata(result)
    exported = ExcelExporter.add_trends_columns(
        pd.DataFrame({"Keyword": ["seo"]}),
        metadata,
    )

    assert metadata["averages"] == {"seo": 79.5094}
    assert metadata["geo"] == "UA"
    assert metadata["timeframe"] == "today 12-m"
    assert exported["Average Interest"].iloc[0] == 79.51
