"""Test Google Trends browser fallback."""

import sys
from utils.browser_scraper import create_browser_scraper

# Purpose: main implementation
def main():
    print("Testing Google Trends browser fallback...")

    # Create browser scraper
    scraper = create_browser_scraper()
    if not scraper:
        print("ERROR: Failed to create browser scraper")
        sys.exit(1)

    print(f"Browser scraper created: {scraper.is_available()}")

    # Test Trends extraction
    keywords = ["seo"]
    params = {
        "geo": "UA",
        "timeframe": "today 12-m",
        "category": 0,
        "hl": "uk-UA",
        "tz": -120,
    }

    print(f"Testing with keywords: {keywords}")
    print(f"Params: {params}")

    result = scraper.scrape_google_trends(keywords=keywords, params=params)

    print(f"\nResult success: {result.success}")
    print(f"Result source: {result.source}")
    print(f"Result errors: {result.errors}")

    if result.extracted_data:
        print(f"\nExtracted data keys: {list(result.extracted_data.keys())}")

        timeline = result.extracted_data.get("timeline", [])
        related = result.extracted_data.get("related_queries", {})

        print(f"Timeline points: {len(timeline)}")
        print(f"Related queries (top): {len(related.get('top', []))}")
        print(f"Related queries (rising): {len(related.get('rising', []))}")

        if timeline:
            print(f"\nSample timeline data: {timeline[0]}")
        if related.get('top'):
            print(f"Sample related query (top): {related['top'][0]}")

    # Check widget data debug info
    widget_data = result.extracted_data.get("widget_data", {}) if result.extracted_data else {}
    if widget_data:
        print(f"\nWidget data debug keys: {list(widget_data.keys())}")
        if 'success' in widget_data:
            print(f"Widget extraction success: {widget_data['success']}")
        if 'debug_info' in widget_data:
            print(f"Debug info: {widget_data['debug_info']}")

    # Proper validation - check for actual data, not just empty containers
    has_timeline = result.extracted_data and result.extracted_data.get("timeline") and len(result.extracted_data.get("timeline", [])) > 0
    has_related = result.extracted_data and result.extracted_data.get("related_queries") and (
        len(result.extracted_data.get("related_queries", {}).get("top", [])) > 0 or
        len(result.extracted_data.get("related_queries", {}).get("rising", [])) > 0
    )

    if result.success and (has_timeline or has_related):
        print("\n[OK] Google Trends browser extraction SUCCESS!")
        sys.exit(0)
    else:
        print("\n[FAIL] Google Trends browser extraction FAILED - No data extracted!")
        print(f"  Has timeline data: {has_timeline}")
        print(f"  Has related queries: {has_related}")
        sys.exit(1)

if __name__ == "__main__":
    main()