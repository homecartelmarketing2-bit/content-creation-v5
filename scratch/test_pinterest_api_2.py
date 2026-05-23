import urllib.parse
import json
import requests

def test_pinterest_searxng_style(query="modern home lighting ideas"):
    print(f"=== Testing Pinterest Scraping via SearXNG method for: '{query}' ===")
    
    # 1. Prepare query parameters
    args = {
        'options': {
            'query': query,
            'bookmarks': [''],
        },
        'context': {},
    }
    
    # URL encode the serialized JSON data
    data_param = json.dumps(args)
    url = f"https://www.pinterest.com/resource/BaseSearchResource/get/?data={urllib.parse.quote(data_param)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        'X-Pinterest-AppState': 'active',
        'X-Pinterest-Source-Url': f'/search/pins/?q={urllib.parse.quote(query)}',
        'X-Pinterest-PWS-Handler': 'www/search/pins.js', # or 'www/ideas.js'
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.pinterest.com/',
    }
    
    try:
        print(f"[INFO] Fetching URL: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        print(f"[INFO] Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"[FAIL] HTTP Status Code: {response.status_code}")
            print(f"[INFO] Response preview: {response.text[:500]}")
            return False
            
        try:
            res_json = response.json()
            print("[OK] Parsed response JSON successfully!")
        except Exception as e:
            print(f"[FAIL] Failed to parse JSON: {e}")
            print(f"[INFO] Response preview: {response.text[:500]}")
            return False
            
        # Save JSON for inspection
        with open("scratch_searxng_response.json", "w", encoding="utf-8") as f:
            json.dump(res_json, f, indent=2)
        print("[INFO] Saved API response to scratch_searxng_response.json")
        
        # Parse pins
        resource_data = res_json.get("resource_response", {})
        data_list = resource_data.get("data", [])
        
        results = []
        if isinstance(data_list, list):
            results = data_list
        elif isinstance(data_list, dict):
            results = data_list.get("results", [])
            
        print(f"[INFO] Found {len(results)} items in response data list.")
        
        image_urls = []
        for idx, item in enumerate(results):
            if not isinstance(item, dict):
                continue
            images = item.get("images")
            if isinstance(images, dict):
                # Try to get highest resolution available
                for size in ["originals", "736x", "600x", "474x"]:
                    if size in images and isinstance(images[size], dict):
                        url_img = images[size].get("url")
                        if url_img:
                            image_urls.append(url_img)
                            break
                            
        # Print extracted image URLs
        print(f"[OK] Extracted {len(image_urls)} image URLs:")
        for i, u in enumerate(image_urls[:10]):
            print(f"  {i+1}. {u}")
            
        return len(image_urls) > 0
        
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return False

if __name__ == "__main__":
    test_pinterest_searxng_style()
