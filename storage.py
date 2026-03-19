# storage.py
# JSON-based persistence layer

import json
import os
from typing import Optional, List
from datetime import datetime
from models import Patient, SymptomEntry, MedicationEntry, EnvironmentEntry


class StorageManager:
    """Handles all JSON-based reading and writing for FlareTrack data."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.patient_file = os.path.join(data_dir, "patient.json")
        self.logs_dir = os.path.join(data_dir, "logs")
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Create necessary directories if they don't exist."""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

    def _log_path(self, date_str: str) -> str:
        return os.path.join(self.logs_dir, date_str + ".json")

    def _load_day(self, date_str: str) -> dict:
        """Load the raw dict for a given day, or return a blank structure."""
        path = self._log_path(date_str)
        if not os.path.exists(path):
            return {"date": date_str, "symptoms": [], "medications": [], "environment": None}
        with open(path, "r") as f:
            return json.load(f)

    def _save_day(self, date_str: str, data: dict):
        """Write the raw dict for a given day to disk."""
        path = self._log_path(date_str)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    # ========== PATIENT ==========

    def save_patient(self, patient: Patient) -> None:
        """Persist patient profile to disk."""
        with open(self.patient_file, "w") as f:
            json.dump(patient.to_dict(), f, indent=2)
        print("[Storage] Patient profile saved for " + patient.name + ".")

    def load_patient(self) -> Optional[Patient]:
        """Load patient profile from disk, or return None if not found."""
        if not os.path.exists(self.patient_file):
            return None
        with open(self.patient_file, "r") as f:
            data = json.load(f)
        return Patient.from_dict(data)

    # ========== SYMPTOMS ==========

    def save_symptom(self, entry: SymptomEntry, date_str: str) -> None:
        """Append a symptom entry to the day's log."""
        day = self._load_day(date_str)
        day["symptoms"].append(entry.to_dict())
        self._save_day(date_str, day)

    def load_symptoms(self, date_str: str) -> List[SymptomEntry]:
        """Load all symptom entries for a given date."""
        day = self._load_day(date_str)
        return [SymptomEntry.from_dict(s) for s in day.get("symptoms", [])]

    # ========== MEDICATIONS ==========

    def save_medication(self, entry: MedicationEntry, date_str: str) -> None:
        """Append a medication entry to the day's log."""
        day = self._load_day(date_str)
        day["medications"].append(entry.to_dict())
        self._save_day(date_str, day)

    def load_medications(self, date_str: str) -> List[MedicationEntry]:
        """Load all medication entries for a given date."""
        day = self._load_day(date_str)
        return [MedicationEntry.from_dict(m) for m in day.get("medications", [])]

    # ========== ENVIRONMENT ==========

    def save_environment(self, entry: EnvironmentEntry, date_str: str) -> None:
        """Save the environment entry for a given date (one per day)."""
        day = self._load_day(date_str)
        day["environment"] = entry.to_dict()
        self._save_day(date_str, day)

    def load_environment(self, date_str: str) -> Optional[EnvironmentEntry]:
        """Load the environment entry for a given date, or None."""
        day = self._load_day(date_str)
        env = day.get("environment")
        if env is None:
            return None
        return EnvironmentEntry.from_dict(env)

    # ========== UTILITIES ==========

    def list_log_dates(self) -> List[str]:
        """Return all dates that have a saved log file, sorted ascending."""
        dates = []
        for filename in sorted(os.listdir(self.logs_dir)):
            if filename.endswith(".json"):
                dates.append(filename[:-5])  # strip .json
        return dates

    def export_all_json(self, output_path: str) -> None:
        """Export every day's log to a single consolidated JSON file."""
        all_data = []
        for date_str in self.list_log_dates():
            all_data.append(self._load_day(date_str))
        export = {
            "exported_at": datetime.now().isoformat(),
            "total_days": len(all_data),
            "logs": all_data,
        }
        with open(output_path, "w") as f:
            json.dump(export, f, indent=2)
        print("[Storage] Exported " + str(len(all_data)) + " days to " + output_path + ".")
