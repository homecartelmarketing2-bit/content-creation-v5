import os
import sys
import requests

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load credentials from .env file
load_dotenv()

ZOHO_CLIENT_ID = os.environ.get("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.environ.get("ZOHO_CLIENT_SECRET")
ZOHO_REFRESH_TOKEN = os.environ.get("ZOHO_REFRESH_TOKEN")
ZOHO_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"

def get_access_token():
    """Refreshes and returns the Zoho access token."""
    try:
        resp = requests.post(ZOHO_TOKEN_URL, data={
            "refresh_token": ZOHO_REFRESH_TOKEN,
            "client_id": ZOHO_CLIENT_ID,
            "client_secret": ZOHO_CLIENT_SECRET,
            "grant_type": "refresh_token",
        })
        data = resp.json()
        if "access_token" in data:
            return data["access_token"]
        else:
            print(f"[ERROR] Failed to refresh token: {data}")
            return None
    except Exception as e:
        print(f"[ERROR] Exception during token refresh: {e}")
        return None

def create_zoho_folder(folder_name: str, parent_folder_id: str):
    """Creates a new folder in Zoho WorkDrive under the specified parent folder ID."""
    token = get_access_token()
    if not token:
        print("[ERROR] Could not retrieve access token.")
        return None

    url = "https://workdrive.zoho.com/api/v1/files"
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/json",
    }
    payload = {
        "data": {
            "attributes": {
                "name": folder_name,
                "parent_id": parent_folder_id
            },
            "type": "files"
        }
    }

    try:
        print(f"[INFO] Attempting to create folder '{folder_name}' under parent folder ID '{parent_folder_id}'...")
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if resp.status_code in (200, 201):
            data = resp.json()
            folder_id = data.get("data", {}).get("id", "")
            print(f"[SUCCESS] Created Zoho folder successfully!")
            print(f"  Folder Name: {folder_name}")
            print(f"  Folder ID: {folder_id}")
            return folder_id
        else:
            print(f"[ERROR] Failed to create folder. HTTP Status Code: {resp.status_code}")
            print(f"Response: {resp.text}")
            return None
    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")
        return None

if __name__ == "__main__":
    # Example usage:
    # Set the parent folder ID where you want to create your new folder.
    # For example, your "Before and After Reels" folder id is: w3zku2c37afa890e347ce8b3e9b39df7b4745
    # or "CTA" folder id is: h8atd1190158bb68e4930be8974c9abbe88c0
    PARENT_ID = "h8atd1190158bb68e4930be8974c9abbe88c0"  # Zoho CTA Folder
    NEW_FOLDER_NAME = "Automated Test Folder"
    
    print("=== Zoho Folder Creator Automation ===")
    if not all([ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN]):
        print("[ERROR] Missing Zoho credentials in .env file.")
        sys.exit(1)

    create_zoho_folder(NEW_FOLDER_NAME, PARENT_ID)
