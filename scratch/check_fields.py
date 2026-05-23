import sys
import os
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

base_id = "appSAnIy8QWSP2aZ9"
table_id = "tblDDmCs4S2ePxIfQ"
token = os.environ.get("AIRTABLE_TOKEN")

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"

try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    tables = response.json().get("tables", [])
    for table in tables:
        if table.get("id") == table_id:
            print(f"Table: {table.get('name')}")
            for field in table.get("fields", []):
                print(f"  - '{field.get('name')}' ({field.get('type')})")
            break
except Exception as e:
    print("Error:", e)
