# tracker.py
# Core tracking logic: manage daily logs and entries

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from models import Patient, SymptomEntry, MedicationEntry, EnvironmentalEntry
from storage import StorageManager


class ChronicTracker:
    """Main tracking class for logging symptoms, medications, and environmental factors."""

    def __init__(self, patient: Patient, storage_manager: StorageManager):
        self.patient = patient
        self.storage = storage_manager
        self.current_date = date.today().isoformat()

    # ========== SYMPTOM TRACKING ==========

    def log_symptom(self, symptom_name: str, severity: int, **kwargs) -> SymptomEntry:
        """Log a new symptom entry."""
        if not 0 <= severity <= 10:
            raise ValueError("Severity must be between 0-10")

        entry = SymptomEntry(
            symptom_name=symptom_name,
            severity=severity,
            location=kwargs.get('location', ''),
            description=kwargs.get('description', ''),
            triggers=kwargs.get('triggers', []),
            duration_minutes=kwargs.get('duration_minutes')
        )

        self.storage.save_symptom(entry, self.current_date)
        print(f"[Tracker] Logged symptom: {symptom_name} (severity {severity})")
        return entry

    def get_symptoms_by_date(self, date_str: str = None) -> List[SymptomEntry]:
        """Get all symptoms for a specific date."""
        target_date = date_str or self.current_date
        return self.storage.load_symptoms(target_date)

    def get_symptoms_by_severity(self, min_severity: int, date_str: str = None) -> List[SymptomEntry]:
        """Get symptoms above a certain severity threshold."""
        symptoms = self.get_symptoms_by_date(date_str)
        return [s for s in symptoms if s.severity >= min_severity]

    def get_symptom_summary(self, symptom_name: str, days: int = 7) -> Dict[str, Any]:
        """Get summary statistics for a specific symptom over recent days."""
        from datetime import timedelta

        all_entries = []
        current = datetime.now()

        for i in range(days):
            check_date = (current - timedelta(days=i)).date().isoformat()
            day_symptoms = self.get_symptoms_by_date(check_date)
            matching = [s for s in day_symptoms if s.symptom_name.lower() == symptom_name.lower()]
            all_entries.extend(matching)

        if not all_entries:
            return {"symptom": symptom_name, "entries": 0, "average_severity": 0}

        severities = [e.severity for e in all_entries]
        return {
            "symptom": symptom_name,
            "entries": len(all_entries),
            "average_severity": sum(severities) / len(severities),
            "max_severity": max(severities),
            "min_severity": min(severities),
            "days_analyzed": days
        }

    # ========== MEDICATION TRACKING ==========

    def log_medication(self, medication_name: str, dosage: str, status: str, **kwargs) -> MedicationEntry:
        """Log a medication entry."""
        valid_statuses = ["taken", "missed", "late", "skipped"]
        if status not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")

        entry = MedicationEntry(
            medication_name=medication_name,
            dosage=dosage,
            status=status,
            route=kwargs.get('route', 'oral'),
            scheduled_time=kwargs.get('scheduled_time'),
            notes=kwargs.get('notes', '')
        )

        self.storage.save_medication(entry, self.current_date)
        print(f"[Tracker] Logged medication: {medication_name} ({status})")
        return entry

    def get_medications_by_date(self, date_str: str = None) -> List[MedicationEntry]:
        """Get all medications for a specific date."""
        target_date = date_str or self.current_date
        return self.storage.load_medications(target_date)

    def get_medication_adherence(self, days: int = 30) -> Dict[str, Any]:
        """Calculate medication adherence over recent days."""
        from datetime import timedelta

        all_entries = []
        current = datetime.now()

        for i in range(days):
            check_date = (current - timedelta(days=i)).date().isoformat()
            day_meds = self.get_medications_by_date(check_date)
            all_entries.extend(day_meds)

        if not all_entries:
            return {"total": 0, "adherence_rate": 0}

        taken = sum(1 for e in all_entries if e.status == "taken")
        total = len(all_entries)

        return {
            "total_doses": total,
            "taken": taken,
            "missed": sum(1 for e in all_entries if e.status == "missed"),
            "late": sum(1 for e in all_entries if e.status == "late"),
            "skipped": sum(1 for e in all_entries if e.status == "skipped"),
            "adherence_rate": (taken / total * 100) if total > 0 else 0,
            "days_analyzed": days
        }

    # ========== ENVIRONMENT TRACKING ==========

    def log_environment(self, **kwargs) -> EnvironmentalEntry:
        """Log environmental factors."""
        # Build custom_factors dict to include legacy 'weather' field
        custom_factors = kwargs.get('custom_factors', {})
        if 'weather' in kwargs:
            custom_factors['weather'] = kwargs['weather']
        
        entry = EnvironmentalEntry(
            # Weather-related / physical environment
            temperature_f=kwargs.get('temperature_f', kwargs.get('temperature')),
            humidity_percent=kwargs.get('humidity_percent', kwargs.get('humidity')),
            air_quality_index=kwargs.get('air_quality_index', kwargs.get('air_quality')),
            barometric_pressure_hpa=kwargs.get('barometric_pressure_hpa'),

            # Lifestyle factors
            stress_level=kwargs.get('stress_level'),
            sleep_hours=kwargs.get('sleep_hours'),
            sleep_quality=kwargs.get('sleep_quality'),
            exercise_minutes=kwargs.get('exercise_minutes'),
            exercise_type=kwargs.get('exercise_type', ''),

            # Intake / other
            diet_notes=kwargs.get('diet_notes', ''),
            alcohol_units=kwargs.get('alcohol_units'),
            caffeine_mg=kwargs.get('caffeine_mg'),
            hydration_oz=kwargs.get('hydration_oz'),
            menstrual_cycle_day=kwargs.get('menstrual_cycle_day'),

            # Free-form extra factors
            custom_factors=custom_factors,
        )

        self.storage.save_environment(entry, self.current_date)
        print("[Tracker] Logged environmental factors")
        return entry

    def get_environment_by_date(self, date_str: str = None) -> Optional[EnvironmentalEntry]:
        """Get environmental entry for a specific date."""
        target_date = date_str or self.current_date
        return self.storage.load_environment(target_date)

    # ========== QUERY HELPERS ==========

    def get_daily_summary(self, date_str: str = None) -> Dict[str, Any]:
        """Get a complete summary for a specific day."""
        target_date = date_str or self.current_date

        return {
            "date": target_date,
            "patient": self.patient.name,
            "symptoms": [s.to_dict() for s in self.get_symptoms_by_date(target_date)],
            "medications": [m.to_dict() for m in self.get_medications_by_date(target_date)],
            "environment": env.to_dict() if (env := self.get_environment_by_date(target_date)) else None
        }

    def search_by_trigger(self, trigger: str, days: int = 30) -> List[SymptomEntry]:
        """Find all symptoms associated with a specific trigger."""
        from datetime import timedelta

        results = []
        current = datetime.now()

        for i in range(days):
            check_date = (current - timedelta(days=i)).date().isoformat()
            day_symptoms = self.get_symptoms_by_date(check_date)
            matching = [s for s in day_symptoms if trigger.lower() in [t.lower() for t in s.triggers]]
            results.extend(matching)

        return results

    def get_flare_days(self, severity_threshold: int = 7, days: int = 30) -> List[str]:
        """Identify days with flare-ups (high severity symptoms)."""
        from datetime import timedelta

        flare_days = []
        current = datetime.now()

        for i in range(days):
            check_date = (current - timedelta(days=i)).date().isoformat()
            day_symptoms = self.get_symptoms_by_date(check_date)

            if any(s.severity >= severity_threshold for s in day_symptoms):
                flare_days.append(check_date)

        return sorted(flare_days)
