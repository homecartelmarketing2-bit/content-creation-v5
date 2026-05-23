import sys
import os

# Ensure the parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.airtable import list_records

TABLE_ID = "tblDDmCs4S2ePxIfQ"

def test():
    print("Testing Phase 11 Styling Tip Generation...")
    
    # Let's find any record with a blended image
    for rec in list_records(TABLE_ID):
        fields = rec.get("fields", {})
        if fields.get("Blended Image"):
            blended_url = fields["Blended Image"][0]["url"]
            print(f"Testing with blended image from record: {rec['id']}")
            
            from services.video import download
            from services.video import cleanup_temp_files
            blended_path = download(blended_url, "test_blended_caption.png")
            if blended_path:
                from services.vision_llm import generate_styling_tip
                caption = generate_styling_tip(blended_path)
                print(f"Generated Tip: {caption}")
                cleanup_temp_files(blended_path)
            break

if __name__ == "__main__":
    test()
