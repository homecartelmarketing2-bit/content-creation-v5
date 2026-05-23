import os
import sys

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config.settings as settings
from services.pinterest_scraper import scrape_pinterest_photos

def test_integrated():
    print("=== Testing Integrated Scraper with Method: requests ===")
    
    # Dynamically set scraper method to requests
    settings.PINTEREST_SCRAPER_METHOD = "requests"
    
    # We will attempt to scrape 2 photos
    res = scrape_pinterest_photos(limit=2)
    print("Result of requests scrape:", res)

if __name__ == "__main__":
    test_integrated()
