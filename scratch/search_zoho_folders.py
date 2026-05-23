import os
import sys
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from debug_zoho_folders import get_access_token

def main():
    token = get_access_token()
    if not token:
        print("Could not get access token")
        return
        
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    
    # Check CTA and Polls and Slider folders
    folders = {
        "CTA": "h8atd1190158bb68e4930be8974c9abbe88c0",
        "Polls and Slider": "h8atddf8980c8b6be40fb84d65e46b0ca4d61"
    }
    
    for name, folder_id in folders.items():
        url = f"https://workdrive.zoho.com/api/v1/files/{folder_id}"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"Failed to get {name} metadata: {resp.text}")
            continue
        data = resp.json().get("data", {})
        attrs = data.get("attributes", {})
        parent_id = attrs.get("parent_id")
        print(f"\n{name} Folder Name: {attrs.get('name')} | ID: {folder_id} | Parent: {parent_id}")
        
        if parent_id:
            url_siblings = f"https://workdrive.zoho.com/api/v1/files/{parent_id}/files"
            resp_siblings = requests.get(url_siblings, headers=headers)
            if resp_siblings.status_code == 200:
                siblings = resp_siblings.json().get("data", [])
                print(f"Siblings of {name}:")
                for sibling in siblings:
                    s_attrs = sibling.get("attributes", {})
                    print(f"  - {s_attrs.get('name')} | ID: {sibling.get('id')} | IsFolder: {s_attrs.get('is_folder')}")
            else:
                print(f"Failed to get siblings for parent {parent_id}: {resp_siblings.text}")

if __name__ == "__main__":
    main()
