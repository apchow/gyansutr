import json
import os
from datetime import datetime, timezone


RECEIPTS_DIR = os.path.join("workspace", "receipts")
QUERY_RECEIPTS_PATH = os.path.join(RECEIPTS_DIR, "query.jsonl")
ACTION_RECEIPTS_PATH = os.path.join(RECEIPTS_DIR, "action.jsonl")


def _append_record(path, record):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    entry = dict(record)
    entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as receipt_file:
        receipt_file.write(line)
        receipt_file.flush()
        os.fsync(receipt_file.fileno())
    return entry


def _read_records(path, n=None):
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as receipt_file:
        for line in receipt_file:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
    if n is None:
        return records
    if n <= 0:
        return []
    return records[-n:]


def log_query(record=None, **fields):
    return _append_record(QUERY_RECEIPTS_PATH, {**(record or {}), **fields})


def log_action(record=None, **fields):
    return _append_record(ACTION_RECEIPTS_PATH, {**(record or {}), **fields})


def read_queries(n=None):
    return _read_records(QUERY_RECEIPTS_PATH, n)


def read_actions(n=None):
    return _read_records(ACTION_RECEIPTS_PATH, n)