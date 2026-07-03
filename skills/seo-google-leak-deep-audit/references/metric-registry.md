# Metric Registry (Leak Coverage)

This registry tracks leaked/internal metric names, current proxy formulas, required data, and expected confidence.
Runtime coverage state is emitted to `analysis.json -> metric_coverage`.

| Metric | Proxy Key | Default Status | Data Required | Confidence | Used In |
|---|---|---|---|---|---|
| `siteRadius` | `siteRadius_proxy` | implemented | crawl | Medium | check_01 |
| `siteFocusScore` | `siteFocusScore_proxy` | implemented | crawl | Medium | check_01 |
| `contentEffort` | `contentEffort_proxy_avg` | implemented | crawl | Medium | check_02 |
| `OriginalContentScore` | `originalContentScore_proxy` | implemented | crawl | Medium | check_02, check_09 |
| `PageRank` | `internalPageRank_proxy` | implemented | crawl | Medium | authority panel |
| `iPullRank` | `iPullRank_proxy` | implemented | crawl | Medium | authority panel |
| `anchorStats` | `anchorStats_proxy` | implemented | crawl | Medium | authority panel |
| `siteAuthority` | `siteAuthority_proxy` | implemented | crawl | Medium | summary |
| `NSR` | `NSR_proxy` | implemented | crawl | Medium | summary |
| `predictedDefaultNsr` | `predictedDefaultNsr_proxy` | implemented | crawl | Medium | summary |
| `lowQuality` | `lowQuality_proxy` | implemented | crawl | Medium | summary |
| `COEC` | `COEC_proxy_site_median` | missing-data when absent | gsc_timeseries | High | navboost panel |
| `serpDemotion` | `serpDemotion_proxy_count` | missing-data when absent | gsc_timeseries | High | navboost panel |
| `scrollDepth` | `scrollDepth_proxy` | missing-data when absent | ga4_scroll | High | navboost panel |
| `directUrlVisits` | `directUrlVisits_proxy` | missing-data when absent | ga4_traffic | High | navboost panel |
| `Goldmine` | `titleRewriteRisk_proxy` | implemented | crawl | Medium | check_03 |
| `dupTokens` | `dupTokens_proxy` | implemented | crawl | Medium | check_03 |
| `goldmineBlockbertFactor` | `goldmineBlockbertFactor_proxy` | implemented | crawl | Medium | check_03 |
| `violatesMobileInterstitialPolicy` | `violatesMobileInterstitialPolicy_proxy` | implemented | crawl + playwright/DOM fallback | High | check_04, check_10 |
| `ugcDiscussionEffortScore` | `ugcDiscussionEffortScore_proxy` | implemented | crawl | Medium | proxy panel |
| `productReviewPUhqPage` | `productReviewPUhqPage_proxy` | implemented | crawl | Low | proxy panel |
| `unsquashedClicks` | n/a | unavailable | internal logs | Low | coverage only |
| `chromeInTotal` | n/a | unavailable | Chrome telemetry | Low | coverage only |
| `authorObfuscatedGaiaStr` | n/a | unavailable | KG internal IDs | Low | coverage only |
