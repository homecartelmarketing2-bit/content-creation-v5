# =====================================================================
#  AIRTABLE SERVICE
#  Handles all reads/writes to Airtable records.
# =====================================================================

import base64
import os

import requests

from config.settings import AIRTABLE_TOKEN, AIRTABLE_BASE_ID


# ── Helpers ─────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }


def _api_url(table_id: str) -> str:
    return f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}"


# ── Read ────────────────────────────────────────────────────────────

def get_next_unfinished_row(table_id: str):
    """
    Fetches ONE row whose Status is actionable.
    Returns (record_id, fields_dict) or (None, None).
    """
    params = {
        "filterByFormula": (
            "OR("
            "{Status} = 'Standby', "
            "{Status} = 'Processing Adding a Prompt', "
            "{Status} = 'Complete Adding a Prompt', "
            "{Status} = 'Processing'"
            ")"
        ),
        "maxRecords": 1,
    }
    try:
        resp = requests.get(_api_url(table_id), headers=_headers(), params=params)
        resp.raise_for_status()
        records = resp.json().get("records", [])
        if records:
            rec = records[0]
            return rec["id"], rec.get("fields", {})
        return None, None
    except requests.RequestException as e:
        print(f"[ERROR] Fetching unfinished row: {e}")
        return None, None


def refetch_record(table_id: str, record_id: str) -> dict:
    """Re-fetches a single record and returns its fields."""
    try:
        resp = requests.get(f"{_api_url(table_id)}/{record_id}", headers=_headers())
        resp.raise_for_status()
        return resp.json().get("fields", {})
    except requests.RequestException as e:
        print(f"[ERROR] Re-fetching record: {e}")
        return {}


# ── Write ───────────────────────────────────────────────────────────

def _patch(table_id: str, record_id: str, fields: dict, *, silent: bool = False) -> bool:
    """Generic PATCH wrapper for a single record.

    When ``silent`` is True the helper does not print on failure; this
    lets callers gracefully tolerate writes to fields that may or may
    not exist on a given table (e.g. the optional poll text fields).
    """
    url = f"{_api_url(table_id)}/{record_id}"
    try:
        resp = requests.patch(url, headers=_headers(), json={"fields": fields})
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        if not silent:
            print(f"[ERROR] Patching record ({fields}): {e}")
        return False


def update_status(table_id: str, record_id: str, status: str) -> bool:
    ok = _patch(table_id, record_id, {"Status": status})
    if ok:
        print(f"[OK] Status → '{status}'")
    return ok


def update_field(table_id: str, record_id: str, field_name: str, value,
                 *, silent: bool = False) -> bool:
    ok = _patch(table_id, record_id, {field_name: value}, silent=silent)
    if ok:
        print(f"[OK] '{field_name}' updated")
    return ok


def update_attachment(table_id: str, record_id: str, field_name: str, url: str) -> bool:
    ok = _patch(table_id, record_id, {field_name: [{"url": url}]})
    if ok:
        print(f"[OK] '{field_name}' attachment uploaded")
    return ok


def upload_attachment_file(
    record_id: str,
    field_name: str,
    file_path: str,
    content_type: str = "image/jpeg",
) -> bool:
    """Uploads a local file directly to an attachment field.

    Uses Airtable's content API (``content.airtable.com``) so the
    file's bytes are streamed in the request body — no public URL
    required. This is the right path for assets we generated locally
    (e.g. the Phase 12 CTA overlay) when we don't have a publicly
    fetchable mirror.

    NOTE: Airtable's direct-upload endpoint is currently limited to
    files up to 5 MB. Callers should compress / re-encode larger
    images before invoking this helper.
    """
    if not os.path.isfile(file_path):
        print(f"[ERROR] upload_attachment_file: file not found: {file_path}")
        return False

    size = os.path.getsize(file_path)
    if size > 5 * 1024 * 1024:
        print(
            f"[WARN] '{field_name}' file is {size} bytes (>5 MB); "
            "Airtable direct-upload may reject it."
        )

    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")

    url = (
        f"https://content.airtable.com/v0/{AIRTABLE_BASE_ID}/"
        f"{record_id}/{field_name}/uploadAttachment"
    )
    try:
        resp = requests.post(
            url,
            headers=_headers(),
            json={
                "contentType": content_type,
                "file": encoded,
                "filename": os.path.basename(file_path),
            },
            timeout=60,
        )
        resp.raise_for_status()
        print(f"[OK] '{field_name}' attachment uploaded directly ({size} bytes)")
        return True
    except requests.RequestException as e:
        body = getattr(e.response, "text", "")[:200] if e.response is not None else ""
        print(f"[ERROR] Direct-uploading '{field_name}': {e} {body}")
        return False
