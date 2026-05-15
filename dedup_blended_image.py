# =====================================================================
#  DEDUP — Trim duplicate / un-watermarked photos in 'Blended Image'
#
#  One-time cleanup over every table in `config/tables.py`. For each
#  row whose `Blended Image` attachment field holds more than one
#  attachment, this script keeps the most recent **watermarked**
#  attachment and drops everything else.
#
#  Detection of "watermarked":
#     The pipeline (Phase 2) writes the watermarked Blended Image with
#     the filename ``<record_id>_blended.jpg``. Any attachment whose
#     filename matches that pattern (case-insensitive) is treated as
#     watermarked. Anything else (raw Kie.ai outputs, manual
#     uploads, etc.) is treated as un-watermarked.
#
#  Keep rule (per row):
#     0 attachments  → skip
#     1 attachment   → skip (already clean)
#     2+ attachments →
#        if any watermarked → keep the LAST watermarked one,
#                              drop everything else
#        if none watermarked → skip with WARN (manual review)
#
#  Default run mode is dry-run. Pass --apply to actually PATCH
#  Airtable. The script never re-uploads files: the kept attachment
#  is referenced by its Airtable attachment ID, so the existing file
#  is preserved as-is.
#
#  Usage:
#     python dedup_blended_image.py                          # dry-run, all tables
#     python dedup_blended_image.py --table-id tbl0H4CE8jdcawJfT
#     python dedup_blended_image.py --table-id tbl... --limit 5
#     python dedup_blended_image.py --apply                  # full live cleanup
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

# Heavy imports are pulled in lazily from `_load_runtime()` so that
# `--help` works without requiring a fully-populated `.env`.
AIRTABLE_TABLES = None
list_records = None
update_field = None


def _load_runtime() -> None:
    global AIRTABLE_TABLES, list_records, update_field

    from config.tables import AIRTABLE_TABLES as _TABLES
    from services.airtable import (
        list_records as _list_records,
        update_field as _update_field,
    )

    AIRTABLE_TABLES = _TABLES
    list_records = _list_records
    update_field = _update_field


FIELD_NAME = "Blended Image"
# The pipeline (Phase 2) writes the watermarked Blended Image with this
# filename. Anything else in the attachment field is treated as raw /
# un-watermarked.
WATERMARKED_FILENAME_SUFFIX = "_blended.jpg"
# Airtable's API is rate-limited at 5 req/sec/base. A short pause
# between PATCHes keeps us comfortably under the ceiling.
SLEEP_BETWEEN_WRITES = 0.25


def _is_watermarked(filename: str, record_id: str) -> bool:
    """Returns True if ``filename`` matches the pipeline's watermarked
    naming scheme for this record."""
    if not filename or not record_id:
        return False
    return filename.lower() == f"{record_id}{WATERMARKED_FILENAME_SUFFIX}".lower()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Deduplicate the 'Blended Image' attachment field across "
            "every Airtable table. Keeps the most recent watermarked "
            "attachment per row and drops the rest."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Actually PATCH Airtable. Without this flag the script "
            "runs in dry-run mode and only prints what it would do."
        ),
    )
    parser.add_argument(
        "--table-id",
        action="append",
        default=None,
        help=(
            "Restrict the cleanup to one or more table IDs "
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
    apply: bool,
) -> str:
    """Returns one of: 'skipped-no-photo', 'skipped-clean',
    'skipped-no-watermarked', 'would-dedup', 'deduped', 'failed'."""
    record_id = record.get("id") or ""
    fields = record.get("fields", {})
    attachments = fields.get(FIELD_NAME) or []

    if not attachments:
        return "skipped-no-photo"

    if len(attachments) == 1:
        return "skipped-clean"

    watermarked = [
        a for a in attachments
        if _is_watermarked(a.get("filename", ""), record_id)
    ]

    if not watermarked:
        filenames = ", ".join(
            repr(a.get("filename") or "<no name>") for a in attachments
        )
        print(
            f"  [WARN] {record_id}: {len(attachments)} attachments, "
            f"NONE watermarked → SKIP (manual review). Filenames: {filenames}"
        )
        return "skipped-no-watermarked"

    # Keep the LAST watermarked attachment (most recent upload).
    keep = watermarked[-1]
    keep_id = keep.get("id")
    keep_name = keep.get("filename") or "<no name>"
    n_drop = len(attachments) - 1

    if not keep_id:
        print(f"  [FAIL] {record_id}: chosen attachment has no id; cannot dedup safely.")
        return "failed"

    if not apply:
        print(
            f"  [DRY] {record_id}: would keep '{keep_name}' (id={keep_id}); "
            f"drop {n_drop} other attachment(s)."
        )
        return "would-dedup"

    # PATCH the field to a single-attachment list referenced by ID.
    # Using {"id": ...} preserves the existing file bytes — Airtable
    # does NOT re-download anything.
    ok = update_field(
        table_id, record_id, FIELD_NAME, [{"id": keep_id}],
    )
    if not ok:
        print(f"  [FAIL] {record_id}: PATCH failed.")
        return "failed"

    print(
        f"  [OK] {record_id}: kept '{keep_name}'; dropped {n_drop} other(s)."
    )
    time.sleep(SLEEP_BETWEEN_WRITES)
    return "deduped"


def _process_table(
    table: dict,
    *,
    apply: bool,
    limit: int | None,
) -> dict:
    table_id = table["id"]
    table_name = table["name"]
    print(f"\n[TABLE] {table_name} ({table_id})")

    counts = {
        "skipped-no-photo": 0,
        "skipped-clean": 0,
        "skipped-no-watermarked": 0,
        "would-dedup": 0,
        "deduped": 0,
        "failed": 0,
        "seen": 0,
    }

    for i, record in enumerate(list_records(table_id)):
        if limit is not None and i >= limit:
            break
        counts["seen"] += 1
        outcome = _process_record(table_id, record, apply=apply)
        counts[outcome] = counts.get(outcome, 0) + 1

    print(
        f"[TABLE-SUMMARY] {table_name}: "
        f"seen={counts['seen']} "
        f"clean={counts['skipped-clean']} "
        f"no-photo={counts['skipped-no-photo']} "
        f"no-wm={counts['skipped-no-watermarked']} "
        f"would-dedup={counts['would-dedup']} "
        f"deduped={counts['deduped']} "
        f"failed={counts['failed']}"
    )
    return counts


def _print_grand_summary(tally: dict, *, dry_run: bool) -> None:
    print("\n" + "=" * 64)
    print("GRAND SUMMARY" + ("  (DRY-RUN — nothing was modified)" if dry_run else ""))
    print("=" * 64)
    for key in (
        "seen",
        "skipped-clean",
        "skipped-no-photo",
        "skipped-no-watermarked",
        "would-dedup",
        "deduped",
        "failed",
    ):
        print(f"  {key:<24}{tally.get(key, 0)}")
    if dry_run and tally.get("would-dedup", 0):
        print(
            "\n  Re-run with --apply to actually trim the duplicate "
            "attachments on the rows above."
        )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _load_runtime()

    if not args.apply:
        print("[DRY-RUN] No Airtable writes will be made. Pass --apply to commit changes.\n")
    else:
        print("[APPLY] Live mode: PATCH calls will be sent to Airtable.\n")

    tables = _select_tables(args.table_id)
    if not tables:
        print("[ERROR] No tables to process.")
        return 1

    tally: dict[str, int] = {}
    for table in tables:
        counts = _process_table(
            table, apply=args.apply, limit=args.limit,
        )
        for k, v in counts.items():
            tally[k] = tally.get(k, 0) + v

    _print_grand_summary(tally, dry_run=not args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
