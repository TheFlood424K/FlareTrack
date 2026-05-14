# FlareTrack — Claude Code Session Guide

FlareTrack is a local-first, fully encrypted health tracking CLI for chronically ill patients.
All patient data stays on-device. The only outbound network calls are:
- Generic medical vocabulary strings sent to NCBI PubMed (indistinguishable from a manual search)
- Lat/lon coordinates sent to Open-Meteo (same as any weather app)

---

## Running the app

```
python main.py
```

`requirements.txt` has one dependency: `cryptography>=41.0.0`. All other modules are stdlib.

---

## File structure

```
FlareTrack-1.0/
├── main.py                 # Entry point → calls cli.main_menu()
├── cli.py                  # FlareTrackCLI class + main_menu() setup
├── tracker.py              # ChronicTracker — high-level API over storage
├── ai_engine.py            # FlareUpPredictor — weighted rule engine (Phase 1)
├── pubmed_engine.py        # PubMedEngine — NCBI E-utilities + 7-day cache (Phase 3)
├── context_snapshot.py     # ContextSnapshot — Open-Meteo APIs + 1-hour cache (Phase 4)
├── models.py               # Dataclasses: Patient, SymptomEntry, MedicationEntry,
│                           #   EnvironmentalEntry (alias: EnvironmentEntry), DailyLog
├── storage.py              # StorageManager — JSON + AES-256 daily log files
├── encryption.py           # DataEncryption (Fernet/PBKDF2), DataMigration
├── migrate_to_encrypted.py # One-time migration: plaintext JSON → .enc
├── ml_engine.py            # FlareRFModel — Random Forest classifier (Phase 2)
├── mobile_app.py           # Placeholder for future mobile interface
└── data/
    ├── patient.json                  # Patient profile — unencrypted (no PHI)
    ├── logs/YYYY-MM-DD.enc           # Daily logs — AES-256 encrypted
    ├── model.pkl                     # Trained RF model (created by menu option 10)
    ├── training_export.json          # Temp file written during training; safe to delete
    ├── pubmed_cache/<sha256>.json    # PubMed query results — 7-day TTL
    └── snapshot_cache/YYYY-MM-DD.json # Weather/AQI snapshots — 1-hour TTL
```

Sensitive key files live in the user's home directory:

```
~/.flaretrack.key           # Fernet key (mode 0o600)
~/.flaretrack.key.password  # PBKDF2-HMAC-SHA256 password hash
~/.flaretrack.key.salt      # Salt file
```

---

## Architecture: 7 layers

| # | Layer | Status |
|---|-------|--------|
| 1 | User logs: symptoms, medications, environment, custom variables | Done |
| 2 | Severity weighting applied to every entry before analysis | Done (Phase 1) |
| 3 | Auto context snapshot on severity ≥ 7 (weather, pressure, AQI, pollen) | Done (Phase 4) |
| 4 | Local encrypted storage — AES-256 via Fernet + PBKDF2, one file per day | Done |
| 5 | AI engine 70/30 split: 70% PubMed evidence, 30% user patterns | Done (Phases 1+3) |
| 6 | On-device ML: Random Forest classifier, severity-weighted, 35% importance cap | Done (Phase 2) |
| 7 | Output: risk score, weighted factors, PubMed citations, trigger insights | Done |

---

## Phase 1 — Weighted rule engine (`ai_engine.py`)

`FlareUpPredictor` is a pure-statistics engine. No ML.

### Severity weights

Every historical log entry is multiplied by its severity weight before contributing to any analysis. High-severity days dominate pattern detection.

| Severity | Weight |
|----------|--------|
| 9–10 (critical flare) | ×2.0 |
| 7–8 (bad) | ×1.5 |
| 5–6 (moderate) | ×1.0 |
| 3–4 (low) | ×0.4 |
| 0–2 (good) | ×0.2 |

```python
def _severity_weight(severity: float) -> float:
    if severity >= 9: return 2.0
    if severity >= 7: return 1.5
    if severity >= 5: return 1.0
    if severity >= 3: return 0.4
    return 0.2
```

### Risk score components (must sum to 1.0)

```python
COMPONENT_WEIGHTS = {
    'symptom_severity':      0.35,
    'medication_adherence':  0.25,
    'environmental_factors': 0.20,
    'sleep_quality':         0.10,
    'stress_level':          0.10,
}
```

Scores are normalized to [0, 1] before multiplying by their weight. A +0.15 cluster bonus applies when 3+ flare days occur within the last 14 days. The final score is capped with `min(1.0, ...)`.

### Confidence growth

```python
confidence = min(0.92, 0.50 + n_logged_days * 0.015)
```

Starts at 50%, caps at 92% after ~28 logged days.

### Key methods

| Method | Description |
|--------|-------------|
| `extract_features(date_str)` | Single-day feature dict including `severity_weight`, `is_flare_day`, all env fields |
| `_load_range_features(days)` | Loads only dates with actual saved log files — avoids polluting analysis with calendar gaps |
| `predict_flare_risk()` | 7-day risk score, level, confidence, component breakdown |
| `correlate_symptoms_with_environment(days)` | Weighted Pearson r for all 11 env fields vs severity |
| `detect_triggers(days)` | Trigger frequency weighted by day severity |
| `detect_trends(days)` | First-half vs second-half weighted average comparison |
| `weighted_factor_report(days)` | Comprehensive report: risk + correlations + triggers + trends |

### Backward compatibility rule

`predict_flare_risk()` returns **both** a legacy `factors` dict (consumed by `cli.py menu_ai_prediction()`) and a new `weighted_factors` dict. `correlate_symptoms_with_environment()` returns legacy `sleep`/`stress`/`exercise` sub-dicts **and** a new `correlations` dict. **Never remove legacy keys.** New output goes in parallel keys.

### Environmental risk sub-score

The `_compute_env_risk_score()` helper evaluates:
- AQI: `min(1.0, aqi / 150)` — 150+ is unhealthy
- Humidity: `min(1.0, |humidity - 50| / 50)` — extremes < 30% or > 70% score higher
- Barometric pressure: `min(1.0, max_daily_delta / 15)` — delta > 10 hPa is a common trigger

---

## Phase 2 — Random Forest classifier (`ml_engine.py`)

`FlareRFModel` trains on severity-weighted daily log data and replaces the rule engine
in `predict_flare_risk()` once `data/model.pkl` exists and the patient has >= 30 logged days.

### Feature columns (13 total)

```python
FEATURE_COLS = [
    "symptom_count", "medication_adherence",
    "sleep_hours", "sleep_quality", "stress_level", "exercise_minutes",
    "temperature_f", "humidity_percent", "air_quality_index",
    "barometric_pressure_hpa", "alcohol_units", "caffeine_mg", "hydration_oz",
]
```

Excluded from features (label leakage): `avg_severity`, `max_severity`, `is_flare_day`,
`severity_weight`, `date`, `triggers`.

### Training pipeline

```
SimpleImputer(strategy='median') -> RandomForestClassifier(n_estimators=200, max_depth=6,
                                                            min_samples_leaf=3, random_state=42)
```

- Fitted with `rf__sample_weight = severity_weight` — high-severity days dominate
- Only records with `symptom_count > 0` are used (phantom empty-day records from
  `extract_features_range()` are excluded, matching `_load_range_features()` behaviour)
- CV ROC-AUC reported (unweighted, stratified K-fold, k = min(5, n_flare, n_nonflare))
- Model persisted via `pickle` to `data/model.pkl`

### Reinforcement cap

`_apply_cap(raw_importances, cap=0.35)` iteratively caps each feature at 35% and
redistributes the excess proportionally to uncapped features until stable, then
renormalises the sum to 1.0. With 13 features the cascade edge-case cannot occur.

### ML overlay in `predict_flare_risk()`

The rule-based score is always computed first. When `self.ml_model is not None` and
`len(features) >= 30`, the RF probability replaces `risk_score` and `risk_level` and
`result['ml_used']` is set to `True`. On any exception the rule-based result is kept.

`aggregate_features(rows)` computes the severity-weighted mean of each feature across
the 14 most-recent logged days, collapsing the window into a single prediction vector.

### Key constants

| Constant | Value | Meaning |
|----------|-------|---------|
| `MIN_TRAIN_DAYS` | 30 | Minimum logged days with symptoms required to train |
| `IMPORTANCE_CAP` | 0.35 | Maximum allowed importance share per feature |
| `MODEL_PATH` | `"data/model.pkl"` | Default save/load location |

### Graceful degradation

- `_load_ml_model()` in `FlareUpPredictor.__init__` wraps the import in `try/except` so
  missing sklearn or absent `model.pkl` silently leaves `self.ml_model = None`
- `FlareRFModel.load()` returns `None` on any file or unpickling error
- The ML overlay block in `predict_flare_risk()` is wrapped in `try/except` — any
  runtime error falls back to the rule-based result without surfacing to the user

---

## Phase 3 — PubMed evidence layer (`pubmed_engine.py`)

`PubMedEngine` queries NCBI E-utilities using a two-step pattern:
1. `esearch.fcgi` (JSON) → list of PMIDs
2. `efetch.fcgi` (XML) → article metadata + abstracts

Rate limit: 0.35 s between requests (NCBI allows 3 req/s without an API key).

### 70/30 academic/user-pattern split

```python
ACADEMIC_WEIGHT = 0.70
USER_WEIGHT     = 0.30

blended_confidence = ACADEMIC_WEIGHT * supported_fraction + USER_WEIGHT
```

- `supported_fraction` = fraction of top triggers that have ≥ 1 PubMed paper
- Floor is always 0.30 (user-pattern baseline even with zero academic backing)
- Triggers with papers → `academic_supported_triggers`
- Triggers without papers → `pattern_only_triggers`

### Cache

- Location: `data/pubmed_cache/<sha256_of_query[:20]>.json`
- TTL: 7 days
- Cache key: `hashlib.sha256(query.lower().strip().encode()).hexdigest()[:20]`
- Plain JSON — contains only public vocabulary (diagnosis names + trigger words)

### Key methods

| Method | Description |
|--------|-------------|
| `search(query, max_results)` | Cache-first single query → `List[Dict]` of articles |
| `enrich_factor_report(report, diagnoses)` | Attaches `pubmed_evidence` key to a `weighted_factor_report()` dict |
| `query_for_diagnosis_and_triggers(diagnoses, triggers)` | Standalone lookup without needing a full report |
| `cache_stats()` | `{cache_dir, cached_queries, total_size_kb, ttl_days}` |
| `clear_cache()` | Deletes all cached `.json` files, returns count |

### Query format

```python
# Trigger queries
f'"{primary_dx}" "{trigger}" flare'

# Environmental factor queries
f'"{primary_dx}" "{term}" pain'
```

`FIELD_QUERY_TERMS` maps `ai_engine.py` feature field names (e.g., `barometric_pressure_hpa`) to PubMed search vocabulary (e.g., `"barometric pressure"`).

---

## Phase 4 — Context snapshot (`context_snapshot.py`)

`ContextSnapshot` auto-fires when a symptom is logged at severity ≥ 7.

### APIs

| API | Endpoint | Key required | Data fetched |
|-----|----------|-------------|-------------|
| Open-Meteo Forecast | `https://api.open-meteo.com/v1/forecast` | No | temperature (°F), humidity, surface pressure (hPa), UV index, wind speed (mph), WMO weather code |
| Open-Meteo Air Quality | `https://air-quality-api.open-meteo.com/v1/air-quality` | No | US AQI, PM2.5, PM10, European AQI, pollen grains/m³ (Europe only) |
| Tomorrow.io Realtime | `https://api.tomorrow.io/v4/weather/realtime` | Yes (free tier) | `treeIndex`, `grassIndex`, `weedIndex` (0–5 scale, global coverage) |

**Open-Meteo pollen** (`pollen_index`, grains/m³) is only populated for European coordinates — the `max()` of 6 species fields. It stays in the snapshot regardless of Tomorrow.io status.

**Tomorrow.io pollen** (`pollen_tree_index`, `pollen_grass_index`, `pollen_weed_index`) uses a 0–5 index (0=None, 1=Very Low, 2=Low, 3=Medium, 4=High, 5=Very High) and works globally. Stored separately so both datasets coexist in `custom_factors` without conflict.

### Tomorrow.io API key configuration

The key is resolved in this order (first non-empty value wins):

1. `TOMORROW_API_KEY` environment variable
2. `"TOMORROW_API_KEY"` key in `data/config.json`

```json
{ "TOMORROW_API_KEY": "your_key_here" }
```

The module-level `TOMORROW_API_KEY` constant is set once at import time. `_fetch_pollen_tomorrow()` also calls `_load_api_key()` at invocation time so a `data/config.json` created after import (same session) is still found.

If the key is absent, empty, or the request fails for any reason, `_fetch_pollen_tomorrow()` returns `{}` silently — the snapshot continues with Open-Meteo data only.

### Cache

- Location: `data/snapshot_cache/YYYY-MM-DD.json`
- TTL: 1 hour (re-fetches if stale — weather changes throughout the day)
- Plain JSON — lat/lon and weather data only, no patient health data

### Merge semantics (important invariant)

`fetch_and_merge()` uses **fill-in** semantics:
- Standard `EnvironmentalEntry` fields (`temperature_f`, `humidity_percent`, `air_quality_index`, `barometric_pressure_hpa`) are **only written if currently `None`** — manually entered values are never overwritten
- Extended fields always go into `custom_factors` so they reach `extract_features()` correlations:
  - Open-Meteo: `weather`, `uv_index`, `wind_speed_mph`, `pm25`, `pm10`, `pollen_index`, `european_aqi`
  - Tomorrow.io: `pollen_tree_index`, `pollen_grass_index`, `pollen_weed_index`, `pollen_source`
  - Always present: `snapshot_at`, `snapshot_source` (`"open-meteo"` or `"open-meteo + tomorrow.io"`)

### Wiring

```
main_menu()
  → ContextSnapshot(patient, storage)          # one shared instance
  → ChronicTracker(..., snapshot=snapshot)     # auto-triggers on severity ≥ 7
  → FlareTrackCLI(..., snapshot=snapshot)      # drives menu option 9
```

`ChronicTracker.log_symptom()` calls `snapshot.fetch_and_merge(current_date)` only when `severity >= 7` and `snapshot.has_location()` is True. If location is missing it prints a one-line hint pointing to menu option 9.

### Location storage

`Patient.latitude` and `Patient.longitude` (both `Optional[float]`, default `None`) are persisted in `data/patient.json`. Existing profiles without these keys load cleanly — `from_dict()` uses `.get()`.

---

## Data models (`models.py`)

### `Patient`
```python
name: str
age: int
diagnosis: List[str]       # used as PubMed search terms
patient_id: str            # 8-char UUID prefix
latitude: Optional[float]  # for context snapshots
longitude: Optional[float]
notes: str
```

### `EnvironmentalEntry`
The 11 fields that feed into the weighted Pearson correlations:
`temperature_f`, `humidity_percent`, `air_quality_index`, `barometric_pressure_hpa`,
`stress_level`, `sleep_hours`, `sleep_quality`, `exercise_minutes`,
`alcohol_units`, `caffeine_mg`, `hydration_oz`

Plus `custom_factors: Dict[str, Any]` for snapshot extras (UV, wind, PM2.5, pollen…).

`EnvironmentEntry` is an alias for `EnvironmentalEntry` — both names work.

---

## Storage (`storage.py`)

One encrypted file per day: `data/logs/YYYY-MM-DD.enc`

The raw day structure (before encryption):
```json
{
  "date": "YYYY-MM-DD",
  "symptoms": [...],
  "medications": [...],
  "environment": { ... } | null
}
```

`_load_day()` returns this structure; `_save_day()` encrypts and writes it.
`list_log_dates()` scans `data/logs/` for `.json` or `.enc` files and returns dates — this is what `_load_range_features()` uses to skip calendar gaps.

---

## Encryption (`encryption.py`)

- Daily logs: AES-256 via `cryptography.fernet.Fernet`
- Key: generated once, stored at `~/.flaretrack.key` (0o600)
- App password: optional, stored as `PBKDF2-HMAC-SHA256` hash (480,000 iterations) at `~/.flaretrack.key.password`
- `patient.json` is unencrypted (name + age + diagnoses — no clinical data)
- PubMed cache and snapshot cache are unencrypted (public data only)

---

## CLI menu map (`cli.py`)

| Option | Method | What it calls |
|--------|--------|--------------|
| 1 | `menu_log_symptom()` | `tracker.log_symptom()` → auto-triggers snapshot if severity ≥ 7 |
| 2 | `menu_log_medication()` | `tracker.log_medication()` |
| 3 | `menu_log_environment()` | `tracker.log_environment()` |
| 4 | `menu_view_summary()` | `tracker.get_daily_summary()` |
| 5 | `menu_ai_prediction()` | `predictor.predict_flare_risk()` |
| 6 | `menu_reports()` | `tracker.get_medication_adherence()` + `predictor.correlate_symptoms_with_environment()` |
| 7 | `menu_search()` | `tracker.search_by_trigger()` |
| 8 | `menu_pubmed_evidence()` | `predictor.weighted_factor_report()` → `pubmed.enrich_factor_report()` |
| 9 | `menu_context_snapshot()` | `snapshot.fetch_and_merge()` + location prompt if missing |
| 10 | `menu_train_model()` | `predictor.train_model(days=90)` → `FlareRFModel.train()` → saves `data/model.pkl` |
| 0 | exit | — |

---

## Key design invariants — do not break

1. **Nothing patient-identifying leaves the device.** PubMed queries contain only `"diagnosis" "trigger" flare` — generic vocabulary. Open-Meteo receives only lat/lon. No symptom descriptions, severities, or names are transmitted.

2. **Severity weights applied consistently.** `_severity_weight(max_severity)` from `extract_features()` must be used as the weight whenever computing weighted means or Pearson correlations over historical data.

3. **Legacy CLI keys preserved.** `predict_flare_risk()` must always return `factors` dict. `correlate_symptoms_with_environment()` must always return `sleep`, `stress`, `exercise` sub-dicts. Add new output in parallel keys, never replace old ones.

4. **Fill-in semantics in `fetch_and_merge()`.** Never overwrite a non-None `EnvironmentalEntry` field with a snapshot value. User-entered data takes precedence. Tomorrow.io pollen fields (`pollen_tree_index` etc.) are custom-factors only and do not affect standard fields.

5. **`_load_range_features(days)`** only loads dates that have actual saved log files — never iterate over every calendar day. This prevents analysis being diluted by days the patient didn't open the app.

6. **Single shared `ContextSnapshot` instance.** `main_menu()` creates one snapshot object and passes it to both `ChronicTracker` and `FlareTrackCLI`. They share it so location changes in menu 9 are immediately reflected in auto-triggers.

7. **Reinforcement cap (rule engine).** No single variable can push `risk_score` above 1.0 — all components are normalized before summing and the result is capped with `min(1.0, ...)`.

8. **Reinforcement cap (ML engine).** Feature importances in `data/model.pkl` are capped at 35% via `_apply_cap()`. Never bypass this when displaying or consuming importances. Do not retrain without the cap applied.

9. **ML training uses only logged days.** `FlareRFModel.train()` filters `symptom_count > 0` to exclude phantom empty-day records from `extract_features_range()`. Do not remove this filter.

10. **ML overlay is additive, not replacing.** The rule-based score is always computed. The ML score is layered on top. Legacy keys (`factors`, `weighted_factors`, `confidence`) remain in the return dict regardless of `ml_used`.

---

## Pending work

### Possible Phase 5+ ideas
- `mobile_app.py` placeholder exists for a future mobile interface
- Doctor-report export (PDF or structured JSON from `storage.export_all_json()`)
- Medication schedule + reminder push notifications
- Barometric pressure change alerts (delta > 10 hPa is already flagged in `_compute_env_risk_score()`)
