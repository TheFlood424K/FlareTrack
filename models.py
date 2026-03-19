# models.py
# Core data models for the Chronic Illness Tracker

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid


class Severity(Enum):
    """Universal 1-10 severity scale."""
    NONE = 0
    MILD = 1
    MODERATE = 5
    SEVERE = 8
    EXTREME = 10


class MedicationStatus(Enum):
    TAKEN = "taken"
    MISSED = "missed"
    LATE = "late"
    SKIPPED = "skipped"


@dataclass
class Patient:
    """Represents the patient profile."""
    name: str
    age: int
    diagnosis: List[str] = field(default_factory=list)
    patient_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "age": self.age,
            "diagnosis": self.diagnosis,
            "patient_id": self.patient_id,
            "created_at": self.created_at,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Patient":
        return cls(
            name=data["name"],
            age=data["age"],
            diagnosis=data.get("diagnosis", []),
            patient_id=data.get("patient_id", str(uuid.uuid4())[:8]),
            created_at=data.get("created_at", datetime.now().isoformat()),
            notes=data.get("notes", ""),
        )


@dataclass
class SymptomEntry:
    """A single symptom log entry."""
    symptom_name: str
    severity: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    location: str = ""
    description: str = ""
    triggers: List[str] = field(default_factory=list)
    duration_minutes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "symptom_name": self.symptom_name,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "location": self.location,
            "description": self.description,
            "triggers": self.triggers,
            "duration_minutes": self.duration_minutes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymptomEntry":
        return cls(
            symptom_name=data["symptom_name"],
            severity=data["severity"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            entry_id=data.get("entry_id", str(uuid.uuid4())[:8]),
            location=data.get("location", ""),
            description=data.get("description", ""),
            triggers=data.get("triggers", []),
            duration_minutes=data.get("duration_minutes"),
        )


@dataclass
class MedicationEntry:
    """A single medication log entry."""
    medication_name: str
    dosage: str
    status: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    route: str = "oral"
    scheduled_time: Optional[str] = None
    side_effects: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "medication_name": self.medication_name,
            "dosage": self.dosage,
            "status": self.status,
            "timestamp": self.timestamp,
            "route": self.route,
            "scheduled_time": self.scheduled_time,
            "side_effects": self.side_effects,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MedicationEntry":
        return cls(
            medication_name=data["medication_name"],
            dosage=data["dosage"],
            status=data["status"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            entry_id=data.get("entry_id", str(uuid.uuid4())[:8]),
            route=data.get("route", "oral"),
            scheduled_time=data.get("scheduled_time"),
            side_effects=data.get("side_effects", []),
            notes=data.get("notes", ""),
        )


@dataclass
class EnvironmentalEntry:
    """Environmental and lifestyle factors that may correlate with flare-ups."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    temperature_f: Optional[float] = None
    humidity_percent: Optional[float] = None
    air_quality_index: Optional[int] = None
    barometric_pressure_hpa: Optional[float] = None
    stress_level: Optional[int] = None
    sleep_hours: Optional[float] = None
    sleep_quality: Optional[int] = None
    exercise_minutes: Optional[int] = None
    exercise_type: str = ""
    diet_notes: str = ""
    alcohol_units: Optional[float] = None
    caffeine_mg: Optional[float] = None
    hydration_oz: Optional[float] = None
    menstrual_cycle_day: Optional[int] = None
    custom_factors: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "temperature_f": self.temperature_f,
            "humidity_percent": self.humidity_percent,
            "air_quality_index": self.air_quality_index,
            "barometric_pressure_hpa": self.barometric_pressure_hpa,
            "stress_level": self.stress_level,
            "sleep_hours": self.sleep_hours,
            "sleep_quality": self.sleep_quality,
            "exercise_minutes": self.exercise_minutes,
            "exercise_type": self.exercise_type,
            "diet_notes": self.diet_notes,
            "alcohol_units": self.alcohol_units,
            "caffeine_mg": self.caffeine_mg,
            "hydration_oz": self.hydration_oz,
            "menstrual_cycle_day": self.menstrual_cycle_day,
            "custom_factors": self.custom_factors,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvironmentalEntry":
        obj = cls()
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        return obj


@dataclass
class DailyLog:
    """A container for all entries on a single day."""
    date: str
    patient_id: str
    symptoms: List[SymptomEntry] = field(default_factory=list)
    medications: List[MedicationEntry] = field(default_factory=list)
    environment: List[EnvironmentalEntry] = field(default_factory=list)
    overall_wellbeing: Optional[int] = None
    daily_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "patient_id": self.patient_id,
            "symptoms": [s.to_dict() for s in self.symptoms],
            "medications": [m.to_dict() for m in self.medications],
            "environment": [e.to_dict() for e in self.environment],
            "overall_wellbeing": self.overall_wellbeing,
            "daily_notes": self.daily_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DailyLog":
        return cls(
            date=data["date"],
            patient_id=data["patient_id"],
            symptoms=[SymptomEntry.from_dict(s) for s in data.get("symptoms", [])],
            medications=[MedicationEntry.from_dict(m) for m in data.get("medications", [])],
            environment=[EnvironmentalEntry.from_dict(e) for e in data.get("environment", [])],
            overall_wellbeing=data.get("overall_wellbeing"),
            daily_notes=data.get("daily_notes", ""),
        )

    def average_symptom_severity(self) -> float:
        """Calculate the mean severity across all symptom entries for the day."""
        if not self.symptoms:
            return 0.0
        return sum(s.severity for s in self.symptoms) / len(self.symptoms)

    def missed_medications(self) -> List[MedicationEntry]:
        """Return list of missed/skipped medications."""
        return [
            m for m in self.medications
            if m.status in (MedicationStatus.MISSED.value, MedicationStatus.SKIPPED.value)
        ]


# Alias so that tracker.py, cli.py, ai_engine.py, and storage.py
# can all use the shorter name 'EnvironmentEntry'.
EnvironmentEntry = EnvironmentalEntry

