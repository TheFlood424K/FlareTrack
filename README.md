# FlareTrack

A comprehensive Python application for chronically ill patients to track symptoms, medications, and environmental factors with AI-powered flare-up prediction.

## Features

- **Symptom Tracking**: Log symptoms with severity (0-10 scale), location, triggers, and duration
- **Medication Management**: Track medication adherence with status (taken/missed/late/skipped)
- **Environmental Tracking**: Monitor lifestyle factors including sleep, stress, exercise, weather, and diet
- **Wellbeing Scoring**: Rate overall daily wellbeing
- **Summary Reports**: View aggregate statistics over custom time periods
- **AI Flare-Up Prediction**: Predict risk of flare-ups based on recent patterns (0-100 risk score)
- **Trigger Detection**: Identify correlations between environmental factors and flare-ups

## Installation

1. Clone the repository:
```bash
git clone https://github.com/TheFlood424K/FlareTrack.git
cd FlareTrack
```

2. No external dependencies required! The application uses Python's standard library.

3. Run the application:
```bash
python main.py
```

## Usage

On first run, you'll set up your patient profile. Then you can:

1. Log symptoms as they occur
2. Track medications taken/missed
3. Record environmental factors (evening routine recommended)
4. Rate overall wellbeing before bed
5. View weekly summary reports to track trends
6. Run AI prediction to assess flare-up risk
7. Detect triggers to identify patterns

## Data Storage

All data is stored locally in JSON format:
```
data/
  patient.json          # Patient profile
  logs/
    2026-03-19.json     # Daily log (one file per day)
    2026-03-20.json
    ...
```

## AI Integration

The ai_engine.py module provides:

1. **Rule-based heuristic prediction** (works immediately):
   - Analyzes symptom trends, medication adherence, sleep, and stress
   - Returns risk score (0-100) with contributing factors

2. **ML integration foundation** (placeholder for advanced models):
   - Feature extraction pipeline ready for scikit-learn, TensorFlow
   - `train_ml_model()` method with example code for Random Forest classifier
   - Uncomment ML library imports in requirements.txt to enable

## File Structure

```
FlareTrack/
├── models.py          # Data models
├── tracker.py         # Core tracking logic
├── storage.py         # JSON persistence
├── ai_engine.py       # AI flare-up prediction
├── cli.py             # Command-line interface
├── main.py            # Entry point
└── requirements.txt   # Dependencies
```

## License

MIT License

## Disclaimer

⚠️ **IMPORTANT**: This is a tracking and analysis tool, NOT medical advice.
- Always consult healthcare providers for medical decisions
- AI predictions are probabilistic, not diagnostic
- Store all health data securely and privately

## AI Usage Attribution

**This program was fully written by Claude Sonet 4.6 under the close supervision and guidance of a real human.**
