#!/usr/bin/env python3
"""
bridge.py - Electron IPC bridge for FlareTrack.

Electron shells out to this script for every read/write operation so that
all encryption/decryption stays inside Python (using the same StorageManager
and DataEncryption used by the CLI).  Data is exchanged as JSON on
stdin/stdout.  The app password is passed as the first argument so the
bridge can verify it before doing anything.

Usage:
  python bridge.py <command> [args...]  [--password <pw>]

Commands:
  verify-password <password>        -> {"ok": true/false}
  has-password                      -> {"has_password": true/false}
  set-password <password>           -> {"ok": true}
  get-patient                       -> patient dict
  save-patient                      (reads JSON from stdin) -> {"ok": true}
  get-log <date>                    -> log dict
  save-log <date>                   (reads JSON from stdin) -> {"ok": true}
  list-log-dates                    -> ["2025-01-01", ...]
  get-all-logs                      -> [{...}, ...]
"""

import sys
import json
import os

# Ensure we can import from the repo root regardless of cwd
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, REPO_ROOT)

from storage import StorageManager
from encryption import DataEncryption


def respond(data):
    """Write a JSON response to stdout and exit cleanly."""
    print(json.dumps(data), flush=True)


def error(msg, code=1):
    """Write an error response and exit with a non-zero code."""
    print(json.dumps({"error": msg}), flush=True)
    sys.exit(code)


def main():
    args = sys.argv[1:]
    if not args:
        error("No command provided")

    command = args[0]
    rest = args[1:]

    # DataEncryption lives in the home directory (.flaretrack.key) - same as CLI
    enc = DataEncryption()

    # StorageManager always uses the repo-root data/ directory
    data_dir = os.path.join(REPO_ROOT, "data")
    storage = StorageManager(data_dir=data_dir, use_encryption=True)

    # ------------------------------------------------------------------ #
    # Password commands (no password check needed for these)
    # ------------------------------------------------------------------ #
    if command == "has-password":
        respond({"has_password": enc.has_password()})
        return

    if command == "verify-password":
        if not rest:
            error("verify-password requires a password argument")
        pw = rest[0]
        respond({"ok": enc.verify_password(pw)})
        return

    if command == "set-password":
        if not rest:
            error("set-password requires a password argument")
        pw = rest[0]
        enc.set_password(pw)
        respond({"ok": True})
        return

    # ------------------------------------------------------------------ #
    # Data commands
    # ------------------------------------------------------------------ #
    if command == "get-patient":
        patient = storage.load_patient()
        if patient is None:
            respond(None)
        else:
            respond(patient.to_dict())
        return

    if command == "save-patient":
        raw = sys.stdin.read()
        data = json.loads(raw)
        from models import Patient
        patient = Patient.from_dict(data)
        storage.save_patient(patient)
        respond({"ok": True})
        return

    if command == "get-log":
        if not rest:
            error("get-log requires a date argument")
        date_str = rest[0]
        day = storage._load_day(date_str)
        respond(day)
        return

    if command == "save-log":
        if not rest:
            error("save-log requires a date argument")
        date_str = rest[0]
        raw = sys.stdin.read()
        data = json.loads(raw)
        data["date"] = date_str
        storage._save_day(date_str, data)
        respond({"ok": True})
        return

    if command == "list-log-dates":
        dates = storage.list_log_dates()
        # Newest first to match the UI expectation
        dates_sorted = sorted(dates, reverse=True)
        respond(dates_sorted)
        return

    if command == "get-all-logs":
        dates = storage.list_log_dates()
        logs = []
        for d in dates:
            try:
                logs.append(storage._load_day(d))
            except Exception:
                pass
        logs.sort(key=lambda l: l.get("date", ""), reverse=True)
        respond(logs)
        return

    error(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
