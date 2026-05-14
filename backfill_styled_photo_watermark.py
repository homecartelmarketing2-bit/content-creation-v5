# =====================================================================
#  BACKFILL — Stamp HomeCartel watermark on existing Styled Photos
#  One-time pass over every table in `config/tables.py`. For each row
#  with a "Styled Photo" attachment that hasn't been watermarked yet,
#  this script:
#     1. Downloads the attachment.
#     2. Stamps it with the brand watermark (using BRAND_WATERMARK_*
#        settings from .env — same defaults as the pipeline).
#     3. Re-uploads the watermarked image back to the same "Styled
#        Photo" field via Airtable's direct-upload endpoint.
#     4. Optionally mirrors the watermarked file to Zoho ("Styled Photo"
#        folder) for parity with the live pipeline.
#
#  Detection of "already watermarked":
#     The pipeline writes watermarked Styled Photos with the filename
#     ``<record_id>_styled_photo.jpg``. Any attachment whose first
#     image already has that filename is treated as watermarked and
#     skipped. This makes the script idempotent — re-runs are no-ops.
#
#  Usage:
#     python backfill_styled_photo_watermark.py --dry-run
#     python backfill_styled_photo_watermark.py --table-id tbl0H4CE8jdcawJfT --limit 5
#     python backfill_styled_photo_watermark.py --skip-zoho
#     python backfill_styled_photo_watermark.py        # full live run
# =====================================================================

import argparse
import os
import sys
import time

# Ensure the project root is on sys.path so `config` / `services` import
# whether the script is run from the repo root or elsewhere.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Heavy imports (`config.settings`, `services.*`) are pulled in lazily
# from `_load_runtime()` so that `--help` works without requiring a
# fully-populated `.env`.
AIRTABLE_TABLES = None
list_records = upload_attachment_file = None
make_watermarked_image = None
download = cleanup_temp_files = None
upload_local_file = None
BRAND_WATERMARK_JPEG_QUALITY = None
BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO = None
BRAND_WATERMARK_LINE1 = None
BRAND_WATERMARK_LINE2 = None
BRAND_WATERMARK_OPACITY = None
BRAND_WATERMARK_PATH = None
BRAND_WATERMARK_POSITION = None
BRAND_WATERMARK_VERTICAL_PADDING_RATIO = None
BRAND_WATERMARK_WIDTH_RATIO = None


def _load_runtime() -> None:
    """Imports the heavy modules. Called after argparse so `--help` runs
    even when the `.env` is missing required keys."""
    global AIRTABLE_TABLES, list_records, upload_attachment_file
    global make_watermarked_image, download, cleanup_temp_files
    global upload_local_file
    global BRAND_WATERMARK_JPEG_QUALITY
    global BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO
    global BRAND_WATERMARK_LINE1, BRAND_WATERMARK_LINE2
    global BRAND_WATERMARK_OPACITY, BRAND_WATERMARK_PATH
    global BRAND_WATERMARK_POSITION
    global BRAND_WATERMARK_VERTICAL_PADDING_RATIO
    global BRAND_WATERMARK_WIDTH_RATIO

    from config.settings import (
        BRAND_WATERMARK_JPEG_QUALITY as _JPEG_QUALITY,
        BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO as _H_PAD,
        BRAND_WATERMARK_LINE1 as _LINE1,
        BRAND_WATERMARK_LINE2 as _LINE2,
        BRAND_WATERMARK_OPACITY as _OPACITY,
        BRAND_WATERMARK_PATH as _WM_PATH,
        BRAND_WATERMARK_POSITION as _POSITION,
        BRAND_WATERMARK_VERTICAL_PADDING_RATIO as _V_PAD,
        BRAND_WATERMARK_WIDTH_RATIO as _WIDTH_RATIO,
    )
    from config.tables import AIRTABLE_TABLES as _TABLES
    from services.airtable import (
        list_records as _list_records,
        upload_attachment_file as _upload_attachment,
    )
    from services.image_overlay import make_watermarked_image as _mk_wm
    from services.video import (
        cleanup_temp_files as _cleanup,
        download as _download,
    )
    from services.zoho import upload_local_file as _zoho_upload

    AIRTABLE_TABLES = _TABLES
    list_records = _list_records
    upload_attachment_file = _upload_attachment
    make_watermarked_image = _mk_wm
    download = _download
    cleanup_temp_files = _cleanup
    upload_local_file = _zoho_upload
    BRAND_WATERMARK_JPEG_QUALITY = _JPEG_QUALITY
    BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO = _H_PAD
    BRAND_WATERMARK_LINE1 = _LINE1
    BRAND_WATERMARK_LINE2 = _LINE2
    BRAND_WATERMARK_OPACITY = _OPACITY
    BRAND_WATERMARK_PATH = _WM_PATH
    BRAND_WATERMARK_POSITION = _POSITION
    BRAND_WATERMARK_VERTICAL_PADDING_RATIO = _V_PAD
    BRAND_WATERMARK_WIDTH_RATIO = _WIDTH_RATIO


STYLED_PHOTO_FIELD = "Styled Photo"
ZOHO_FOLDER_KEY = "Styled Photo"
# Airtable rate limit is 5 req/sec/base. A 0.25s pause per record keeps
# us comfortably under the ceiling even with the surrounding
# download/upload calls.
SLEEP_BETWEEN_RECORDS = 0.25


def _is_watermarked(filename: str, record_id: str) -> bool:
    """Returns True if ``filename`` matches the pipeline's watermarked
    naming scheme for this record."""
    if not filename:
        return False
    return filename.lower() == f"{record_id}_styled_photo.jpg".lower()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill the HomeCartel watermark across existing Styled "
            "Photo attachments in every Airtable table."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Walk every table and report what would be watermarked, "
            "but do not download, watermark, or upload anything."
        ),
    )
    parser.add_argument(
        "--table-id",
        action="append",
        default=None,
        help=(
            "Restrict the backfill to one or more table IDs "
            "(repeat the flag to add multiple). Defaults to all tables."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Process at most N records per table (useful for smoke "
            "testing). Defaults to no limit."
        ),
    )
    parser.add_argument(
        "--skip-zoho",
        action="store_true",
        help=(
            "Do not mirror the watermarked image to the Zoho 'Styled "
            "Photo' folder. Defaults to mirroring for parity with the "
            "pipeline."
        ),
    )
    return parser.parse_args(argv)


def _select_tables(table_ids: list[str] | None) -> list[dict]:
    if not table_ids:
        return list(AIRTABLE_TABLES)
    wanted = {tid.strip() for tid in table_ids if tid and tid.strip()}
    selected = [t for t in AIRTABLE_TABLES if t["id"] in wanted]
    missing = wanted - {t["id"] for t in selected}
    if missing:
        print(f"[WARN] Unknown table IDs ignored: {sorted(missing)}")
    return selected


def _process_record(
    table_id: str,
    record: dict,
    *,
    dry_run: bool,
    skip_zoho: bool,
) -> str:
    """Returns one of: 'skipped-no-photo', 'skipped-already-wm',
    'watermarked', 'failed'."""
    record_id = record.get("id")
    fields = record.get("fields", {})
    attachments = fields.get(STYLED_PHOTO_FIELD) or []
    if not attachments:
        return "skipped-no-photo"

    first = attachments[0]
    filename = first.get("filename", "")
    source_url = first.get("url")
    if not source_url:
        return "skipped-no-photo"

    if _is_watermarked(filename, record_id):
        return "skipped-already-wm"

    if dry_run:
        print(
            f"  [DRY] {record_id}: would watermark "
            f"(filename={filename or '<no name>'})"
        )
        return "watermarked"

    raw_path = download(source_url, f"{record_id}_styled_photo_raw.png")
    if not raw_path:
        print(f"  [FAIL] {record_id}: download failed")
        return "failed"

    watermarked_path = make_watermarked_image(
        raw_path,
        record_id,
        output_basename=f"{record_id}_styled_photo",
        extension=".jpg",
        watermark_path=BRAND_WATERMARK_PATH,
        line1=BRAND_WATERMARK_LINE1,
        line2=BRAND_WATERMARK_LINE2,
        width_ratio=BRAND_WATERMARK_WIDTH_RATIO,
        position=BRAND_WATERMARK_POSITION,
        horizontal_padding_ratio=BRAND_WATERMARK_HORIZONTAL_PADDING_RATIO,
        vertical_padding_ratio=BRAND_WATERMARK_VERTICAL_PADDING_RATIO,
        opacity=BRAND_WATERMARK_OPACITY,
        jpeg_quality=BRAND_WATERMARK_JPEG_QUALITY,
    )
    if not watermarked_path:
        print(f"  [FAIL] {record_id}: watermarking failed")
        cleanup_temp_files(raw_path)
        return "failed"

    attached = upload_attachment_file(
        record_id,
        STYLED_PHOTO_FIELD,
        watermarked_path,
        content_type="image/jpeg",
    )
    if not attached:
        print(f"  [FAIL] {record_id}: Airtable upload failed")
        cleanup_temp_files(raw_path, watermarked_path)
        return "failed"

    if not skip_zoho:
        try:
            upload_local_file(
                watermarked_path,
                f"{record_id}_styled_photo.jpg",
                ZOHO_FOLDER_KEY,
            )
        except Exception as e:
            print(f"  [WARN] {record_id}: Zoho upload failed: {e}")

    cleanup_temp_files(raw_path, watermarked_path)
    print(f"  [OK] {record_id}: watermarked")
    return "watermarked"


def _process_table(
    table: dict,
    *,
    dry_run: bool,
    limit: int | None,
    skip_zoho: bool,
) -> dict:
    table_id = table["id"]
    table_name = table["name"]
    print(f"\n[TABLE] {table_name} ({table_id})")

    counts = {
        "watermarked": 0,
        "skipped-already-wm": 0,
        "skipped-no-photo": 0,
        "failed": 0,
        "seen": 0,
    }

    for record in list_records(table_id):
        counts["seen"] += 1
        outcome = _process_record(
            table_id, record, dry_run=dry_run, skip_zoho=skip_zoho,
        )
        counts[outcome] = counts.get(outcome, 0) + 1

        if not dry_run:
            time.sleep(SLEEP_BETWEEN_RECORDS)

        if limit is not None and counts["seen"] >= limit:
            print(f"  [INFO] Hit per-table --limit {limit}; moving on.")
            break

    print(
        f"  → seen={counts['seen']} "
        f"watermarked={counts['watermarked']} "
        f"already_wm={counts['skipped-already-wm']} "
        f"no_photo={counts['skipped-no-photo']} "
        f"failed={counts['failed']}"
    )
    return counts


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _load_runtime()

    tables = _select_tables(args.table_id)
    if not tables:
        print("[ERROR] No matching tables to process.")
        return 2

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    zoho_note = "Airtable only" if args.skip_zoho else "Airtable + Zoho"
    print(f"[INFO] Mode: {mode} | Upload targets: {zoho_note}")
    print(f"[INFO] Tables to process: {len(tables)}")
    if args.limit is not None:
        print(f"[INFO] Per-table record limit: {args.limit}")

    totals = {
        "watermarked": 0,
        "skipped-already-wm": 0,
        "skipped-no-photo": 0,
        "failed": 0,
        "seen": 0,
    }
    for table in tables:
        counts = _process_table(
            table,
            dry_run=args.dry_run,
            limit=args.limit,
            skip_zoho=args.skip_zoho,
        )
        for k, v in counts.items():
            totals[k] = totals.get(k, 0) + v

    print("\n[SUMMARY]")
    print(f"  tables processed       : {len(tables)}")
    print(f"  records seen           : {totals['seen']}")
    print(f"  watermarked            : {totals['watermarked']}")
    print(f"  skipped (already wm)   : {totals['skipped-already-wm']}")
    print(f"  skipped (no photo)     : {totals['skipped-no-photo']}")
    print(f"  failed                 : {totals['failed']}")

    return 1 if totals["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
