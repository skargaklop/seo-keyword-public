# Google Leak Metrics Map (Proxy Layer)

| Leaked/Internal Metric | Proxy in v1 | Confidence | Data Needed |
|---|---|---|---|
| `siteAuthority` | Blend of internal PageRank + NSR proxies | Medium | Crawl internal links + check outcomes |
| `NSR` / `predictedDefaultNsr` | Aggregate quality score from low-effort, duplication, toxic outlinks | Medium | Crawl signals |
| `PageRank` / `iPullRank` / `PageRankPerDocData` | Internal link-graph PageRank (max + mean + per-doc) | Medium | Crawl internal links |
| `anchorStats` / `perDocData` | Anchor diversity and per-page link distribution | Medium | Crawl internal anchors |
| `siteRadius` | Topical dispersion vs site centroid | Medium | Page token vectors |
| `siteFocusScore` | 1 - off-topic page ratio | Medium | Crawl signals |
| `contentEffort` | Structure richness (tables/lists/citations/media + originality) | Medium | Crawl signals |
| `OriginalContentScore` | Near-duplicate and template reuse penalties | Medium | Shingles / token similarity |
| `authorReputationScore` | Presence of author entities, `Person` schema, `sameAs`, author pages | Medium | Schema + link graph |
| `clutterScore` | Fixed/sticky overlay coverage and intrusive UI heuristics | Medium/High | Playwright or DOM heuristics |
| `anchorMismatchDemotion` | Anchor repetition + low semantic anchor-target overlap | Medium | Internal anchors + target content terms |
| `lastSignificantUpdate` | Real content updates vs synthetic date updates | Low/Medium | Page text + dates + sitemap optional |
| `onsiteProminence` | Inlinks to money pages + click depth from homepage | Medium | Crawl graph |
| `mobileCwv` proxy | Render blocking hints, overlays, horizontal scroll | Medium | Playwright preferred |
| `goodClicks` / `badClicks` | CTR-engagement mismatch (GSC + GA4) | Medium/High | Optional CSV imports |
| `COEC` / `serpDemotion` | Actual vs expected clicks by position bins | High | GSC time-series by page/date |
| `scrollDepth` / `directUrlVisits` | Scroll events per user and direct session share | High | GA4 extra exports |
| `Goldmine` / `AlternativeTitlesAnnotator` / `dupTokens` | Title rewrite-risk based on overlap + duplicate token patterns | Medium | Crawl title/h1/intro |
| `violatesMobileInterstitialPolicy` | Full-screen or delayed popup heuristic flags | High | Playwright or DOM heuristics |
| `ugcDiscussionEffortScore` | Comment depth + unique author participation score | Medium | Crawl discussion/comment blocks |
| `productReviewPUhqPage` | Optional high-quality review page detection | Low | Crawl + structural signals |
| `unsquashedClicks` / `chromeInTotal` | Unavailable without proprietary logs/telemetry | Low | Internal Google datasets |

Notes:
- All values are proxies, not true Google internal scores.
- Confidence grows when optional data (GSC/GA4/Playwright) is available.
- Runtime coverage output now includes `status`, `proxy_formula`, `confidence`, and `data_required` per metric.
