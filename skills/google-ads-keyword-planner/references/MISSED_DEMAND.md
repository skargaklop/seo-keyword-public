# Missed Demand (Google Ads)

Find uncovered demand using Search Terms export + Keyword Planner metrics.

## Input

- Google Ads Search Terms export in `.csv` or `.xlsx`.
- Configured Google Ads credentials in `config/.env`.

## Workflow

1. Parse export and get groups:
```bash
uv run --script scripts/missed_demand.py parse-export path/to/search_terms.csv
```

2. Parse a specific group:
```bash
uv run --script scripts/missed_demand.py parse-export path/to/search_terms.csv --group "Ad Group Name"
```

3. Build OR query from slots:
```bash
uv run --script scripts/missed_demand.py build-query '<slots_json>'
```

4. Merge batch segmentation for large groups:
```bash
echo '<merge_input_json>' | uv run --script scripts/missed_demand.py merge-slots
```

5. Estimate demand for OR query via Google Ads historical metrics:
```bash
bash scripts/query_total.sh --phrase "(buy|order) chimney" --regions "2840"
```

## Output fields

`query-total` returns JSON:

- `total_count`: sum of `avgMonthlySearches` over expanded keyword combinations.
- `keyword_count`: number of generated keyword combinations.
- `truncated`: `true` if expansion hit `--max-keywords` cap.

## Constraints

- Expansion uses OR-structure heuristics, not exact broad-match simulation.
- If OR combinations are huge, `--max-keywords` limits request size.
- This workflow analyzes Google Ads planning/account data, not organic SERP.
