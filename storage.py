# storage.py
# JSON-based persistence layer

import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from models import Patient, DailyLog


DATA_DIR = "data"
PATIENT_FILE = os.path.join(DATA_DIR, "patient.json")
LOGS_DIR = os.path.join(DATA_DIR, "logs")


def ensure_dirs():
    """Create necessary directories if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)


# ---- Patient Storage ----

def save_patient(patient: Patient) -> None:
    ensure_dirs()
    with open(PATIENT_FILE, "w") as f:
        json.dump(patient.to_dict(), f, indent=2)
    print(f"[Storage] Patient profile saved for {patient.name}.")


def load_patient() -> Optional[Patient]:
    if not os.path.exists(PATIENT_FILE):
        return None
    with open(PATIENT_FILE, "r") as f:
        data = json.load(f)
    return Patient.from_dict(data)


# ---- Daily Log Storage ----

def _log_path(date_str: str) -> str:
    return os.path.join(LOGS_DIR, f"{date_str}.json")


def save_daily_log(log: DailyLog) -> None:
    ensure_dirs()
    path = _log_path(log.date)
    with open(path, "w") as f:
        json.dump(log.to_dict(), f, indent=2)
    print(f"[Storage] Log saved for {log.date}.")


def load_daily_log(date_str: str) -> Optional[DailyLog]:
    path = _log_path(date_str)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        data = json.load(f)
    return DailyLog.from_dict(data)


def load_all_logs() -> List[DailyLog]:
    """Load all daily logs sorted by date ascending."""
    ensure_dirs()
    logs = []
    for filename in sorted(os.listdir(LOGS_DIR)):
        if filename.endswith(".json"):
            with open(os.path.join(LOGS_DIR, filename), "r") as f:
                data = json.load(f)
            logs.append(DailyLog.from_dict(data))
    return logs


def load_logs_range(start_date: str, end_date: str) -> List[DailyLog]:
    """Load logs within a date range (inclusive). Dates as YYYY-MM-DD strings."""
    all_logs = load_all_logs()
    return [log for log in all_logs if start_date <= log.date <= end_date]


def delete_daily_log(date_str: str) -> bool:
    path = _log_path(date_str)
    if os.path.exists(path):
        os.remove(path)
        print(f"[Storage] Log for {date_str} deleted.")
        return True
    print(f"[Storage] No log found for {date_str}.")
    return False


def export_logs_json(output_path: str) -> None:
    """Export all logs to a single consolidated JSON file."""
    logs = load_all_logs()
    export_data = {
        "exported_at": datetime.now().isoformat(),
        "total_days": len(logs),
        "logs": [log.to_dict() for log in logs],
    }
    with open(output_path, "w") as f:
        json.dump(export_data, f, indent=2)
    print(f"[Storage] Exported {len(logs)} logs to {output_path}.")
