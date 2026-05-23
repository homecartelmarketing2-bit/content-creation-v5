import sys
import os

# Ensure the parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pipeline import _phase6_combine_reels
from services.airtable import refetch_record

TABLE_ID = "tblDDmCs4S2ePxIfQ"
RECORD_ID = "rec4AzYfkkfX4uF4U"

def test():
    print(f"Fetching explicit record ID: {RECORD_ID} to test Phase 6...")
    fields = refetch_record(TABLE_ID, RECORD_ID)
    
    if not fields:
        print(f"Could not fetch record {RECORD_ID}")
        return

    # To ensure it runs, we temporarily bypass the check by overriding _get_mapped_field_val
    import pipeline
    original_get_mapped_field_val = pipeline._get_mapped_field_val

    def mock_get_mapped_field_val(rec_id, rec_fields, field_key, table_id):
        if field_key == "Combine Video Before and After":
            return None # Force it to run
        return original_get_mapped_field_val(rec_id, rec_fields, field_key, table_id)

    pipeline._get_mapped_field_val = mock_get_mapped_field_val
    
    print(f"\n--- Testing Phase 6 on Record ID: {RECORD_ID} ---")
    
    def mock_ui_callback(title, desc_text="", image_path=None, scanning=False):
        print(f"[UI Callback] {title} | {desc_text}")
        
    try:
        _phase6_combine_reels(TABLE_ID, RECORD_ID, ui_callback=mock_ui_callback)
    finally:
        pipeline._get_mapped_field_val = original_get_mapped_field_val

if __name__ == "__main__":
    test()
