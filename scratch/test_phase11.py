import sys
import os

# Ensure the parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pipeline import _phase11_tips_reels
from services.airtable import list_records

TABLE_ID = "tblDDmCs4S2ePxIfQ"

def test():
    print("Fetching records to find one with 'Blended Image' and 'Styled Reels'...")
    found_record = None
    
    # Try to find a record that doesn't have 'Tips Reels' yet
    for rec in list_records(TABLE_ID):
        fields = rec.get("fields", {})
        if fields.get("Blended Image") and fields.get("Styled Reels"):
            if not fields.get("Tips Reels"):
                found_record = rec
                break
            
    # If all have Tips Reels, just take the first one and remove the field to bypass idempotency check
    if not found_record:
        print("All matching records already have 'Tips Reels'. Falling back to the first available record and bypassing the skip check...")
        for rec in list_records(TABLE_ID):
            fields = rec.get("fields", {})
            if fields.get("Blended Image") and fields.get("Styled Reels"):
                found_record = rec
                if "Tips Reels" in found_record["fields"]:
                    del found_record["fields"]["Tips Reels"]
                break

    if not found_record:
        print("Could not find any record with 'Blended Image' and 'Styled Reels'.")
        return

    record_id = found_record["id"]
    fields = found_record["fields"]
    
    print(f"\n--- Testing Phase 11 on Record ID: {record_id} ---")
    
    def mock_ui_callback(title, desc_text="", image_path=None, scanning=False):
        print(f"[UI Callback] {title} | {desc_text}")
        
    _phase11_tips_reels(TABLE_ID, record_id, fields, ui_callback=mock_ui_callback)

if __name__ == "__main__":
    test()
