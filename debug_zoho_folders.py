"""
Debug script – lists the contents of every configured Zoho WorkDrive folder
so you can verify that uploads are landing in the right place.

Usage:
    python debug_zoho_folders.py              # list all folders
    python debug_zoho_folders.py "Styled Photo"  # list one folder only
"""

import sys
import os
import requests
from datetime import datetime

# ── Bootstrap project imports ───────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config.settings import (
    ZOHO_CLIENT_ID,
    ZOHO_CLIENT_SECRET,
    ZOHO_REFRESH_TOKEN,
    ZOHO_TOKEN_URL,
    ZOHO_FOLDERS,
)


def get_access_token() -> str | None:
    """Refresh and return a valid Zoho OAuth access token."""
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
        print(f"[ERROR] Token refresh failed: {data}")
    except Exception as e:
        print(f"[ERROR] Token refresh error: {e}")
    return None


def list_folder_contents(token: str, folder_id: str) -> list[dict]:
    """Return a list of file/folder dicts inside the given Zoho folder."""
    url = f"https://workdrive.zoho.com/api/v1/files/{folder_id}/files"
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    params = {"page[limit]": 50}  # max per page

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("data", [])
        else:
            print(f"  [WARN] API returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  [ERROR] {e}")
    return []


def format_size(size_bytes) -> str:
    """Human-readable file size."""
    try:
        size_bytes = int(size_bytes)
    except (TypeError, ValueError):
        return "? B"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_date(iso_str: str) -> str:
    """Convert ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso_str or "—"


def main():
    # Optional filter: only show one folder
    filter_key = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else None

    print("=" * 70)
    print("  ZOHO WORKDRIVE FOLDER DEBUG")
    print("=" * 70)

    token = get_access_token()
    if not token:
        print("\n[FATAL] Cannot get access token. Check your .env credentials.")
        return

    print("[OK] Access token acquired.\n")

    folders_to_check = {}
    if filter_key:
        fid = ZOHO_FOLDERS.get(filter_key)
        if fid:
            folders_to_check = {filter_key: fid}
        else:
            print(f"[ERROR] No folder named '{filter_key}'.")
            print(f"Available folders: {', '.join(ZOHO_FOLDERS.keys())}")
            return
    else:
        folders_to_check = ZOHO_FOLDERS

    total_files = 0

    for folder_name, folder_id in folders_to_check.items():
        print("-" * 70)
        print(f"[FOLDER]  {folder_name}")
        print(f"    Folder ID : {folder_id}")
        print(f"    Zoho Link : https://workdrive.zoho.com/folder/{folder_id}")

        items = list_folder_contents(token, folder_id)

        if not items:
            print("    (empty -- no files found)")
        else:
            print(f"    [{len(items)} file(s)]:\n")
            for i, item in enumerate(items, 1):
                attrs = item.get("attributes", {})
                name = attrs.get("name", "???")
                size = attrs.get("storage_info", {}).get("size", 0)
                created = attrs.get("created_time", "")
                modified = attrs.get("modified_time", "")
                file_type = attrs.get("type", "")

                type_icon = "[VID]" if any(
                    name.lower().endswith(ext)
                    for ext in (".mp4", ".mov", ".avi", ".webm")
                ) else "[IMG]" if any(
                    name.lower().endswith(ext)
                    for ext in (".png", ".jpg", ".jpeg", ".webp")
                ) else "[FILE]"

                print(f"    {i:3d}. {type_icon}  {name}")
                print(f"         Size: {format_size(size)}  |  "
                      f"Created: {format_date(created)}  |  "
                      f"Modified: {format_date(modified)}")

            total_files += len(items)

        print()

    print("=" * 70)
    print(f"  TOTAL: {len(folders_to_check)} folder(s) checked, "
          f"{total_files} file(s) found")
    print("=" * 70)


if __name__ == "__main__":
    main()
