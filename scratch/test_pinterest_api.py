import urllib.parse
import json
import requests

def test_pinterest_base_search_resource(query="modern home lighting ideas"):
    print(f"=== Testing Pinterest Scraping via BaseSearchResource for: '{query}' ===")
    
    # 1. Prepare query parameters
    source_url = f"/search/pins/?q={urllib.parse.quote(query)}"
    
    data_dict = {
        "options": {
            "isPrefetch": False,
            "query": query,
            "scope": "pins",
            "no_meta": True
        },
        "context": {}
    }
    
    params = {
        "source_url": source_url,
        "data": json.dumps(data_dict),
        "_": "1716336000000"  # A cache-buster timestamp
    }
    
    url = "https://www.pinterest.com/resource/BaseSearchResource/get/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.pinterest.com/",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    try:
        print(f"[INFO] Fetching API: {url}")
        print(f"[INFO] Params: {params}")
        response = requests.get(url, params=params, headers=headers, timeout=15)
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
        with open("scratch_api_response.json", "w", encoding="utf-8") as f:
            json.dump(res_json, f, indent=2)
        print("[INFO] Saved API response to scratch_api_response.json")
        
        # Check if we got data/results
        resource_data = res_json.get("resource_response", {})
        data_list = resource_data.get("data", [])
        
        # Sometimes results are nested differently or inside results list
        results = []
        if isinstance(data_list, list):
            results = data_list
        elif isinstance(data_list, dict):
            results = data_list.get("results", [])
            
        print(f"[INFO] Found {len(results)} items in response data list.")
        
        # Look for images in the results
        image_urls = []
        for idx, item in enumerate(results):
            if not isinstance(item, dict):
                continue
            # Extract image URLs
            images = item.get("images")
            if isinstance(images, dict):
                # Try to get highest resolution available
                for size in ["originals", "736x", "600x", "474x"]:
                    if size in images and isinstance(images[size], dict):
                        url = images[size].get("url")
                        if url:
                            image_urls.append(url)
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
    test_pinterest_base_search_resource()
