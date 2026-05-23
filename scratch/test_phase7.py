import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pipeline import _phase_closeup_photo
from services.airtable import list_records

TABLE_ID = "tblDDmCs4S2ePxIfQ"  # Chandelier Table

def ui_print(*args, **kwargs):
    desc = kwargs.get('desc_text', '')
    print(f"UI CALLBACK: {args[0]} | {desc}")

def run_test():
    print("Fetching records to test Phase 7 on the Chandelier table...")
    
    for rec in list_records(TABLE_ID):
        fields = rec.get("fields", {})
        
        # We need a record that has a Blended Image
        if fields.get("Blended Image"):
            record_id = rec["id"]
            
            # Optionally, you can find one that doesn't have the closeup yet to truly test it
            # But we can test it anyway
            print(f"\n======================================")
            print(f"Testing Phase 7 on Record ID: {record_id}")
            print(f"======================================")
            
            # _phase_closeup_photo(table_id, record_id, item_name, target_field, label, ui_callback, closeup_idx)
            _phase_closeup_photo(
                table_id=TABLE_ID,
                record_id=record_id,
                item_name="Chandelier",
                target_field="Closeup Photo One",
                label="Phase 7: Closeup Photo One",
                ui_callback=ui_print,
                closeup_idx=1
            )
            
            print("\nTest completed for one record.")
            break
    else:
        print("No record found with a 'Blended Image' to test on.")

if __name__ == "__main__":
    run_test()
