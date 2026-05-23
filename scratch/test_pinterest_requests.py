import os
import re
import json
import requests

def test_pinterest_requests(query="modern home lighting ideas"):
    print(f"=== Testing Pinterest Scraping via HTTP Requests for: '{query}' ===")
    
    # 1. Prepare search URL
    search_url = f"https://www.pinterest.com/search/pins/?q={requests.utils.quote(query)}"
    
    # 2. Set headers to look like a standard web browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.pinterest.com/",
    }
    
    try:
        print(f"[INFO] Fetching search page: {search_url}")
        response = requests.get(search_url, headers=headers, timeout=15)
        print(f"[INFO] Response Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"[FAIL] HTTP Request returned status code {response.status_code}")
            return False
            
        # 3. Locate JSON script using regular expressions (avoiding BeautifulSoup dependency)
        json_str = None
        
        # Method A: Look for script id="initial-state"
        match_a = re.search(r'<script[^>]+id="initial-state"[^>]*>(.*?)</script>', response.text, re.DOTALL)
        if match_a:
            print("[INFO] Found script with id='initial-state' using Regex.")
            json_str = match_a.group(1).strip()
            
        # Method B: Look for window.__PWS_DATA__
        if not json_str:
            match_b = re.search(r'window\.__PWS_DATA__\s*=\s*(\{.*?\});?\s*</script>', response.text, re.DOTALL)
            if match_b:
                print("[INFO] Found window.__PWS_DATA__ using Regex.")
                json_str = match_b.group(1).strip()

        # Method B2: Look for script id="__PWS_DATA__" tag
        if not json_str:
            match_b2 = re.search(r'<script[^>]+id="__PWS_DATA__"[^>]*>(.*?)</script>', response.text, re.DOTALL)
            if match_b2:
                print("[INFO] Found script with id='__PWS_DATA__' using Regex.")
                json_str = match_b2.group(1).strip()
                
        # Method C: General __PWS_DATA__ search
        if not json_str:
            match_c = re.search(r'__PWS_DATA__\s*=\s*(\{.*?\})', response.text)
            if match_c:
                print("[INFO] Found __PWS_DATA__ variable using Regex.")
                json_str = match_c.group(1).strip()
        
        if not json_str:
            print("[FAIL] Could not find Pinterest JSON script payload in the HTML.")
            # Save debug HTML file
            debug_path = "scratch_pinterest_response.html"
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"[INFO] Saved HTML response to {debug_path} for manual inspection.")
            return False
            
        # 4. Parse JSON content
        try:
            data = json.loads(json_str)
            print("[OK] Successfully parsed JSON payload from Pinterest page!")
        except json.JSONDecodeError as jde:
            print(f"[FAIL] JSON parsing failed: {jde}")
            # Try to sanitize and parse if there are Javascript trailing characters
            # sometimes there is trailing JS or unescaped characters
            return False
        
        # Save parsed json for debugging
        with open("scratch_pinterest_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print("[INFO] Saved parsed JSON metadata to scratch_pinterest_data.json")
        
        # 5. Extract image URLs
        image_urls = []
        
        def extract_urls_recursive(obj):
            if isinstance(obj, dict):
                # Look for standard pin image structure
                if "images" in obj and isinstance(obj["images"], dict):
                    img_dict = obj["images"]
                    for size in ["originals", "736x", "600x", "474x"]:
                        if size in img_dict and isinstance(img_dict[size], dict):
                            url = img_dict[size].get("url")
                            if url:
                                image_urls.append(url)
                                break
                for k, v in obj.items():
                    extract_urls_recursive(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract_urls_recursive(item)
                    
        extract_urls_recursive(data)
        
        # Remove duplicates
        image_urls = list(dict.fromkeys(image_urls))
        
        print(f"\n[OK] Extracted {len(image_urls)} unique high-resolution image URLs:")
        for i, url in enumerate(image_urls[:10]):
            print(f"  {i+1}. {url}")
            
        if len(image_urls) > 10:
            print(f"  ... and {len(image_urls) - 10} more.")
            
        if not image_urls:
            print("[WARN] No image URLs were found in the JSON metadata structure.")
            return False
            
        # 6. Try downloading the first image to test download success
        test_img_url = image_urls[0]
        print(f"\n[INFO] Downloading test image: {test_img_url}")
        img_resp = requests.get(test_img_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        
        if img_resp.status_code == 200:
            test_output = "scratch_test_download.jpg"
            with open(test_output, "wb") as f:
                f.write(img_resp.content)
            print(f"[OK] Downloaded and saved test image to: {test_output} (Size: {len(img_resp.content)} bytes)")
            return True
        else:
            print(f"[FAIL] Image download failed with status code: {img_resp.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")
        return False

if __name__ == "__main__":
    test_pinterest_requests()
