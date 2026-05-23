import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import AIRTABLE_TOKEN, AIRTABLE_BASE_ID

def main():
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/tbl0H4CE8jdcawJfT"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    params = {"maxRecords": 100}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    records = resp.json().get("records", [])
    if not records:
        print("No records found in table tbl0H4CE8jdcawJfT")
        return
    
    unique_fields = set()
    for record in records:
        unique_fields.update(record["fields"].keys())
        
    print(f"Inspected {len(records)} records. Found {len(unique_fields)} unique field names:")
    for field in sorted(unique_fields):
        print(f" - {field}")

if __name__ == "__main__":
    main()
