# FlareTrack Brain — Android Integration Handoff

This document is written for the Android developer receiving the FlareTrack analysis engine. It assumes you know Android development well and Python/data science not at all. Everything is plain English. When you hit a term you don't recognise, Perplexity is your friend.

---

## What the Brain Is

FlareTrack is a health tracking tool for people with chronic illnesses — conditions like lupus, fibromyalgia, or Crohn's disease where symptoms flare up unpredictably. The "brain" is the analysis engine that lives on the user's device and answers one central question:

> "Based on everything this patient has logged, how likely are they to have a bad flare-up soon, and why?"

It does this without sending any health data to a server. The only things that ever leave the device are:
- A generic medical search query sent to PubMed (looks exactly like a doctor typing into a search engine — no patient names, no severities, nothing identifiable)
- GPS coordinates sent to a weather API (identical to any weather app)

The brain has three layers:
1. A **rule engine** that scores risk based on weighted patterns in logged data
2. A **machine learning model** that trains on the patient's own history and refines predictions over time
3. A **research layer** that backs trigger detections up with real medical literature from PubMed

---

## Files You Need

These are the Python files that make up the brain. They all need to travel together — they import each other.

| File | What it does |
|------|--------------|
| `main.py` | Entry point for the CLI app — you won't call this from Android |
| `cli.py` | The terminal menu UI — you won't use this either |
| `tracker.py` | High-level API for logging data and reading summaries — **you'll call this** |
| `ai_engine.py` | The analysis brain — **your main interface for predictions** |
| `ml_engine.py` | The Random Forest ML model — called automatically by ai_engine |
| `pubmed_engine.py` | PubMed evidence lookup — called by ai_engine when you ask for a full report |
| `context_snapshot.py` | Fetches current weather/AQI/pollen automatically when a severe symptom is logged |
| `models.py` | Data structure definitions — needed everywhere |
| `storage.py` | Reads and writes encrypted daily log files |
| `encryption.py` | Handles AES-256 encryption of all health data |
| `migrate_to_encrypted.py` | One-time migration helper — you probably won't need this |
| `mobile_app.py` | Placeholder stub — empty, ignore it |

The `data/` folder is created automatically on first run. It holds all logs, the trained ML model, and API caches.

---

## What the Brain Gives Back

When you ask for a prediction, the brain returns a structured dictionary (think JSON object). Here is what is inside it, in plain English:

### Risk Prediction (`predict_flare_risk()`)

- **risk_score** — a number from 0.0 to 1.0. Think of it as a percentage chance of a flare-up. 0.72 means 72% risk.
- **risk_level** — one of three strings: `"low"`, `"moderate"`, or `"high"`. Low is below 35%, high is above 65%.
- **confidence** — how much the engine trusts its own answer, from 0.0 to 0.92. Starts at 50% and grows as the patient logs more days. Caps at 92% after about 28 days of consistent logging.
- **factors** — a breakdown showing which component drove the score up. Includes symptom severity, medication adherence, sleep quality, stress, and environmental factors. Each shows its contribution as a number from 0 to 1.
- **ml_used** — `true` or `false`. When `true`, a trained Random Forest model specific to this patient replaced the rule-based score. This only happens after the patient has 30+ logged days and has trained their personal model.
- **days_analyzed** — how many days of the patient's history were used in this prediction.

### Full Factor Report (`weighted_factor_report()`)

This is the detailed version. It includes everything above, plus:

- **top_correlated_factors** — ranked list of environmental and lifestyle variables that correlate most strongly with this patient's flare-ups. For example: `sleep_hours: -0.821` means that when this patient sleeps less, their flares get worse. `stress_level: +0.818` means high stress days predict flares.
- **top_triggers** — words and phrases pulled from the patient's own symptom logs that appear most often on bad days. Examples: `"stress"`, `"poor sleep"`, `"alcohol"`.
- **trends** — whether things are getting better or worse. Compares the first half of the logged window against the second half for sleep, severity, and medication adherence.

### PubMed Evidence (`enrich_factor_report()`)

This wraps the full report above and adds a `pubmed_evidence` section:

- **trigger_evidence** — for each top trigger, a list of real academic papers from PubMed that link that trigger to the patient's diagnosed condition. Each paper includes title, authors, year, abstract excerpt, and a URL.
- **factor_evidence** — same idea but for environmental variables like barometric pressure changes, humidity, air quality.
- **academic_supported_triggers** — which of the patient's triggers have at least one supporting paper.
- **pattern_only_triggers** — triggers detected in the data but not yet backed by a paper (still valid, just pattern-only).
- **blended_confidence** — a score from 0.30 to 1.0 that reflects how much of the risk picture has academic backing. 0.30 is the floor (pure user pattern), 1.0 means every detected trigger has peer-reviewed support.

### Environmental Snapshot (`context_snapshot.py`)

When a patient logs a symptom with severity 7 or higher, the brain automatically fetches current conditions at their location and attaches them to that day's log. This data comes back in the daily log and feeds into future correlations:

- **temperature_f** — current temperature in Fahrenheit
- **humidity_percent** — relative humidity
- **air_quality_index** — US AQI (0 = clean, 150+ = unhealthy)
- **barometric_pressure_hpa** — atmospheric pressure in hectopascals. Drops in pressure are a documented flare trigger for many conditions.
- **uv_index** — UV radiation level
- **wind_speed_mph** — wind speed
- **pm25 / pm10** — fine particulate matter (air pollution particles)
- **pollen_index** — grains per cubic metre from Open-Meteo (European coordinates only)
- **pollen_tree_index / pollen_grass_index / pollen_weed_index** — 0–5 scale pollen levels from Tomorrow.io (works worldwide, requires an API key — see API section below)

---

## The Four Inputs

The brain learns from four types of data the patient logs each day.

### 1. Symptoms

Each symptom entry captures:
- The symptom name (free text, e.g. "joint pain", "fatigue")
- A severity from 1–10
- An optional location on the body
- An optional description
- Tags for suspected triggers (e.g. "stress", "lack of sleep")
- How long it lasted (minutes)

Severity drives everything. A severity-10 day carries 10× the analytical weight of a severity-1 day. This is intentional — the brain should learn from the worst days, not average them away.

### 2. Medications

Each medication entry captures:
- Medication name
- Dosage
- Status: `taken`, `missed`, `late`, or `skipped`
- Route (oral, injection, etc.)
- Scheduled time
- Any noted side effects

Medication adherence feeds directly into the risk score. Missing doses on high-severity days is a strong signal.

### 3. Environment

One environment entry per day captures the lifestyle and environmental context:
- Sleep hours and sleep quality (1–10)
- Stress level (1–10)
- Exercise minutes
- Temperature, humidity, AQI, barometric pressure (auto-filled from snapshot if not manually entered)
- Alcohol units consumed
- Caffeine in mg
- Hydration in oz

If the patient has their location set and logs a severe symptom, these environmental fields are auto-populated from weather APIs. Manual entries take priority — the snapshot only fills in blanks.

### 4. Custom Variables

The environment entry also has a `custom_factors` dictionary for anything that doesn't fit the standard fields. The auto-snapshot uses this for extended weather data (UV index, PM2.5, pollen indices). You can also let users log anything bespoke here — menstrual cycle day is already defined in the model as an optional field.

---

## How the ML Model Works (Plain English)

The brain has two prediction modes.

**Mode 1 — Rule engine (always active):** Uses weighted averages and statistical correlations across the patient's history. It knows, for example, that this patient's flares tend to follow poor sleep within two days. It computes a score from five components: symptom severity, medication adherence, environmental factors, sleep quality, and stress. No learning happens — it is pure pattern calculation.

**Mode 2 — Personal ML model (activates after 30 logged days):** Once a patient has enough history, they can train a Random Forest model that is specific to them. Think of it as the app building a decision tree based entirely on this one patient's data. It learns which combination of variables predicts that patient's flares specifically, not flares in general.

Once trained, this model replaces the rule engine's final score. The rule engine still runs (its components and factors are still reported), but the headline risk score comes from the patient's personal model.

The model is stored as a file (`data/model.pkl`) on the device. It never leaves. It is retrained by calling `train_model()` — typically exposed as a menu option the user triggers manually when they want to update their model with newer data.

One safety feature: no single variable can account for more than 35% of the model's prediction. If sleep hours would otherwise dominate, the excess weight is redistributed to other factors. This prevents the model from becoming a single-variable detector.

---

## What APIs Are Used and What Keys Are Needed

### Open-Meteo (no key required)

Used for weather and air quality when a severe symptom is logged. Free, no account needed, no rate limits for reasonable use. Sends only GPS coordinates. Returns temperature, humidity, pressure, UV, wind, PM2.5, PM10, and pollen (Europe only).

Two endpoints:
- `https://api.open-meteo.com/v1/forecast` — weather
- `https://air-quality-api.open-meteo.com/v1/air-quality` — pollution and pollen

### Tomorrow.io (optional, free tier available)

Used for pollen index data worldwide. Open-Meteo pollen only works in Europe; Tomorrow.io fills the gap for North America, Asia, etc. Returns tree, grass, and weed pollen on a 0–5 scale.

To enable: create a free account at tomorrow.io, get an API key, and store it in one of two places:
- An environment variable named `TOMORROW_API_KEY`
- A file at `data/config.json` with the content `{ "TOMORROW_API_KEY": "your_key_here" }`

If the key is absent or the request fails, the snapshot continues with Open-Meteo data only. Nothing breaks.

### NCBI PubMed / E-utilities (no key required for basic use)

Used to find academic papers that support detected triggers. Free, no account needed for up to 3 requests per second. The brain stays under that limit with a built-in 0.35-second delay between requests.

If you expect heavier usage, NCBI offers a free API key that raises the limit to 10 req/s. Store it in the `PubMedEngine` constructor or as a config value.

Queries look like: `"lupus" "stress" flare` — only generic medical vocabulary, no patient data.

Results are cached locally for 7 days so repeat queries don't hit the network.

---

## What Stays On Device and Why

The regulations covering patient health data (HIPAA in the US, GDPR in Europe, etc.) are strict. The safest engineering answer is to never transmit it in the first place.

**What is encrypted on device:**
- Every daily log (symptoms, medications, environment entries) — AES-256 encrypted, one file per day
- The encryption key itself is stored in the user's home directory at `~/.flaretrack.key` with read-only permissions

**What is stored unencrypted on device (but never transmitted):**
- The patient profile (`data/patient.json`) — contains name, age, and diagnoses only (no clinical data)
- PubMed cache — contains only public vocabulary (diagnosis names, trigger words) fetched from a public API
- Weather snapshot cache — contains GPS coordinates and weather data

**What is transmitted and why it is safe:**
- PubMed queries: a string like `"lupus" "stress" flare` — indistinguishable from a doctor using PubMed manually
- GPS coordinates to Open-Meteo and Tomorrow.io — identical to any weather app

The trained ML model (`data/model.pkl`) is the most sensitive artifact — it encodes the patient's symptom patterns in a machine-learned form. It never leaves the device.

---

## What to Install to Run It

Python 3.9 or later is required.

The only external dependency is the encryption library:

```
pip install cryptography>=41.0.0
```

To also use the ML model (optional — the app works without it, falling back to the rule engine):

```
pip install scikit-learn numpy
```

Everything else — JSON handling, HTTP requests, XML parsing, statistics — uses Python's standard library.

For Android integration, you have two paths:

**Path A — Run Python as a subprocess.** Package a Python interpreter with the app (Chaquopy is the standard library for this on Android). Call the brain's functions via a thin bridge layer. Suitable if you want to keep the Python codebase intact.

**Path B — Port to Kotlin/Java.** Rewrite the rule engine logic in Kotlin. The formulas are straightforward. The ML model would need a different approach — export it as ONNX or TensorFlow Lite after training on desktop, then load the exported model on Android. The PubMed and weather integrations are standard HTTP calls that translate directly.

Path A is faster to ship. Path B gives you a fully native app. The choice depends on how much ongoing Python maintenance you want to carry.

---

## Quick Reference: Key Numbers

| Value | What it means |
|-------|--------------|
| 30 | Minimum logged days before ML training is available |
| 92% | Maximum confidence the rule engine will ever report |
| 0.35 | Maximum share of prediction any single variable can hold (ML cap) |
| 7+ | Severity threshold that triggers automatic weather/pollen snapshot |
| 10 hPa | Barometric pressure drop threshold flagged as a flare trigger |
| 150 | AQI value above which air quality starts contributing to risk score |
| 7 days | How long PubMed query results are cached before re-fetching |
| 1 hour | How long weather snapshots are cached before re-fetching |

---

## Questions to Ask Before You Start

1. Will the Android app manage its own data store, or pipe data into the Python layer?
2. Do you want the ML model to train on-device (needs `scikit-learn` bundled) or on a companion desktop tool and sync the `.pkl` file?
3. Is the patient population primarily European (Open-Meteo pollen works) or global (Tomorrow.io key needed)?
4. Do you want PubMed evidence queries in the app, or is that a desktop/web-only feature?
5. What is your encryption strategy for Android — do you want to reuse the same Fernet/PBKDF2 scheme, or replace it with Android Keystore?

These five questions will determine roughly 80% of the integration architecture.
