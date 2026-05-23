import os
import sys
import shutil

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config.settings as settings
from services.pinterest_scraper import scrape_pinterest_photos, count_available_photos

def run_scraper_test(method, limit=2):
    print("\n" + "="*60)
    print(f" TESTING SCRAPER METHOD: {method.upper()}")
    print("="*60)
    
    # Override settings for the test
    settings.PINTEREST_SCRAPER_METHOD = method
    settings.PINTEREST_SEARCH_TERMS = ["interior design living room lighting"]
    settings.PINTEREST_MIN_PHOTOS = 1
    
    # We will print the current photo count before scraping
    initial_count = count_available_photos(settings.MARKETING_PHOTO_DIR)
    print(f"Initial photo count in {settings.MARKETING_PHOTO_DIR}: {initial_count}")
    
    try:
        result = scrape_pinterest_photos(limit=limit)
        print(f"Scrape result for {method}: {result}")
        final_count = count_available_photos(settings.MARKETING_PHOTO_DIR)
        print(f"Final photo count: {final_count}")
        print(f"Successfully downloaded: {final_count - initial_count} new photos")
        return True
    except Exception as e:
        print(f"Error executing scraper {method}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("Starting Scrapers Comparison Test...")
    print(f"Marketing photo directory: {settings.MARKETING_PHOTO_DIR}")
    
    # Ensure marketing photo dir exists
    os.makedirs(settings.MARKETING_PHOTO_DIR, exist_ok=True)
    
    # 1. Test Playwright
    playwright_ok = run_scraper_test("playwright", limit=2)
    
    # 2. Test Requests
    requests_ok = run_scraper_test("requests", limit=2)
    
    print("\n" + "="*60)
    print(" TEST SUMMARY")
    print("="*60)
    print(f"Playwright Scraper (Chromium): {'PASS' if playwright_ok else 'FAIL'}")
    print(f"Requests-based Scraper:        {'PASS' if requests_ok else 'FAIL'}")
    print("="*60)

if __name__ == "__main__":
    main()
