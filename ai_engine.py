# ai_engine.py
# Weighted rule engine (Phase 1) + Random Forest overlay (Phase 2).
# Phase 2 activates automatically when data/model.pkl exists and the patient
# has at least 30 logged days; otherwise falls back to the rule engine.

import math
import json
import os
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import statistics


# Severity tier boundaries → multipliers applied to each log entry before analysis.
# Critical flare (9-10) ×2.0 means those days dominate pattern detection;
# good days (0-2) ×0.2 contribute only lightly.
def _severity_weight(severity: float) -> float:
    if severity >= 9:
        return 2.0
    if severity >= 7:
        return 1.5
    if severity >= 5:
        return 1.0
    if severity >= 3:
        return 0.4
    return 0.2


class FlareUpPredictor:
    """Weighted rule engine: every historical entry is scaled by its severity
    weight before contributing to pattern detection and risk scoring."""

    # Final risk-score component weights (must sum to 1.0)
    COMPONENT_WEIGHTS = {
        'symptom_severity':      0.35,
        'medication_adherence':  0.25,
        'environmental_factors': 0.20,
        'sleep_quality':         0.10,
        'stress_level':          0.10,
    }

    def __init__(self, storage_manager):
        self.storage      = storage_manager
        self.risk_weights = self.COMPONENT_WEIGHTS  # legacy alias
        self.ml_model     = self._load_ml_model()

    def _load_ml_model(self):
        """Try to load a trained FlareRFModel from data/model.pkl.
        Returns None silently on ImportError (sklearn missing) or missing file."""
        try:
            from ml_engine import load_model
            return load_model()
        except Exception:
            return None

    # =========================================================
    # STATISTICS HELPERS
    # =========================================================

    @staticmethod
    def _weighted_mean(values: List[float], weights: List[float]) -> Optional[float]:
        """Weighted arithmetic mean. Returns None when lists are empty."""
        pairs = [(v, w) for v, w in zip(values, weights) if v is not None]
        if not pairs:
            return None
        total_w = sum(p[1] for p in pairs)
        if total_w == 0:
            return None
        return sum(p[0] * p[1] for p in pairs) / total_w

    @staticmethod
    def _weighted_pearson(xs: List[float], ys: List[float], ws: List[float]) -> float:
        """Weighted Pearson correlation coefficient in [-1, 1].
        Returns 0.0 when there are fewer than 3 points or no variance."""
        triples = [(x, y, w) for x, y, w in zip(xs, ys, ws)
                   if x is not None and y is not None]
        if len(triples) < 3:
            return 0.0
        xs_, ys_, ws_ = zip(*triples)
        total_w = sum(ws_)
        if total_w == 0:
            return 0.0
        x_bar = sum(w * x for w, x in zip(ws_, xs_)) / total_w
        y_bar = sum(w * y for w, y in zip(ws_, ys_)) / total_w
        cov  = sum(w * (x - x_bar) * (y - y_bar) for w, x, y in zip(ws_, xs_, ys_)) / total_w
        vx   = sum(w * (x - x_bar) ** 2 for w, x in zip(ws_, xs_)) / total_w
        vy   = sum(w * (y - y_bar) ** 2 for w, y in zip(ws_, ys_)) / total_w
        denom = math.sqrt(vx * vy)
        if denom == 0:
            return 0.0
        return max(-1.0, min(1.0, cov / denom))

    # =========================================================
    # FEATURE EXTRACTION
    # =========================================================

    def extract_features(self, date_str: str) -> Dict[str, Any]:
        """Extract all relevant features for a single date.

        Every feature dict now includes `severity_weight` so downstream
        analysis can scale observations by how bad that day was.
        """
        symptoms    = self.storage.load_symptoms(date_str)
        medications = self.storage.load_medications(date_str)
        env         = self.storage.load_environment(date_str)

        # --- Symptom features ---
        avg_severity = statistics.mean([s.severity for s in symptoms]) if symptoms else 0.0
        max_severity = max((s.severity for s in symptoms), default=0)
        all_triggers = [t.lower() for s in symptoms for t in s.triggers]

        # --- Medication adherence ---
        med_total = len(medications)
        med_taken = sum(1 for m in medications if m.status == "taken")
        adherence  = (med_taken / med_total) if med_total > 0 else 1.0

        # --- Environmental / lifestyle ---
        sleep_hours           = env.sleep_hours           if env else None
        sleep_quality         = env.sleep_quality         if env else None
        stress_level          = env.stress_level          if env else None
        exercise_minutes      = env.exercise_minutes      if env else None
        temperature_f         = env.temperature_f         if env else None
        humidity_percent      = env.humidity_percent      if env else None
        air_quality_index     = env.air_quality_index     if env else None
        barometric_pressure   = env.barometric_pressure_hpa if env else None
        alcohol_units         = env.alcohol_units         if env else None
        caffeine_mg           = env.caffeine_mg           if env else None
        hydration_oz          = env.hydration_oz          if env else None

        return {
            'date':                  date_str,
            # Core severity
            'symptom_count':         len(symptoms),
            'avg_severity':          avg_severity,
            'max_severity':          max_severity,
            'severity_weight':       _severity_weight(max_severity),
            'is_flare_day':          max_severity >= 7,
            'triggers':              all_triggers,
            # Medication
            'medication_adherence':  adherence,
            # Lifestyle
            'sleep_hours':           sleep_hours,
            'sleep_quality':         sleep_quality,
            'stress_level':          stress_level,
            'exercise_minutes':      exercise_minutes,
            # Environmental
            'temperature_f':         temperature_f,
            'humidity_percent':      humidity_percent,
            'air_quality_index':     air_quality_index,
            'barometric_pressure_hpa': barometric_pressure,
            # Intake
            'alcohol_units':         alcohol_units,
            'caffeine_mg':           caffeine_mg,
            'hydration_oz':          hydration_oz,
        }

    def extract_features_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Extract features for every calendar day in [start_date, end_date]."""
        features = []
        current = datetime.fromisoformat(start_date).date()
        end     = datetime.fromisoformat(end_date).date()
        while current <= end:
            features.append(self.extract_features(current.isoformat()))
            current += timedelta(days=1)
        return features

    def _load_range_features(self, days: int) -> List[Dict[str, Any]]:
        """Load features only for dates that have actual saved log files,
        within the last `days` days.  Avoids polluting analysis with
        calendar days the patient simply didn't open the app."""
        end_date   = date.today()
        start_date = end_date - timedelta(days=days)
        features   = []
        for date_str in self.storage.list_log_dates():
            try:
                d = date.fromisoformat(date_str)
            except ValueError:
                continue
            if start_date <= d <= end_date:
                features.append(self.extract_features(date_str))
        return features

    # =========================================================
    # PATTERN DETECTION
    # =========================================================

    def detect_triggers(self, days: int = 30) -> Dict[str, Any]:
        """Identify symptom triggers, weighted by the severity of the day
        they occurred on.  A trigger on a severity-9 flare day scores
        ×2.0 vs ×0.2 on a good day."""
        features = self._load_range_features(days)

        trigger_buckets: Dict[str, Dict] = defaultdict(
            lambda: {'weighted_score': 0.0, 'occurrences': 0, 'severities': []}
        )

        for f in features:
            w = f['severity_weight']
            for trigger in f['triggers']:
                b = trigger_buckets[trigger]
                b['occurrences']    += 1
                b['severities'].append(f['avg_severity'])
                b['weighted_score'] += f['avg_severity'] * w

        results = {}
        for trigger, b in trigger_buckets.items():
            results[trigger] = {
                'occurrences':        b['occurrences'],
                'avg_severity':       round(statistics.mean(b['severities']), 2),
                'max_severity':       max(b['severities']),
                'weighted_risk_score': round(b['weighted_score'] / max(days, 1), 3),
            }

        sorted_triggers = sorted(
            results.items(),
            key=lambda x: x[1]['weighted_risk_score'],
            reverse=True,
        )

        return {
            'days_analyzed': days,
            'logged_days':   len(features),
            'triggers':      dict(sorted_triggers),
            'top_triggers':  [t[0] for t in sorted_triggers[:5]],
        }

    def detect_trends(self, days: int = 30) -> Dict[str, Any]:
        """Identify severity trends, using weighted means so flare periods
        pull the averages more than quiet stretches."""
        features = self._load_range_features(days)

        if len(features) < 7:
            return {'error': 'Insufficient data for trend analysis (need 7+ logged days)'}

        weights     = [f['severity_weight'] for f in features]
        severities  = [f['avg_severity']    for f in features]
        flare_days  = sum(1 for f in features if f['is_flare_day'])

        # Compare first-half vs second-half weighted averages
        mid         = len(features) // 2
        first_half  = features[:mid]
        second_half = features[mid:]

        first_w_avg  = self._weighted_mean(
            [f['avg_severity'] for f in first_half],
            [f['severity_weight'] for f in first_half],
        ) or 0.0
        second_w_avg = self._weighted_mean(
            [f['avg_severity'] for f in second_half],
            [f['severity_weight'] for f in second_half],
        ) or 0.0

        delta = second_w_avg - first_w_avg
        if delta < -0.5:
            trend = 'improving'
        elif delta > 0.5:
            trend = 'worsening'
        else:
            trend = 'stable'

        overall_w_avg = self._weighted_mean(severities, weights) or 0.0

        return {
            'days_analyzed':         days,
            'logged_days':           len(features),
            'flare_days':            flare_days,
            'flare_frequency':       round(flare_days / len(features), 3),
            'weighted_avg_severity': round(overall_w_avg, 2),
            'trend_direction':       trend,
            'first_half_w_avg':      round(first_w_avg, 2),
            'second_half_w_avg':     round(second_w_avg, 2),
            'severity_delta':        round(delta, 2),
        }

    def correlate_symptoms_with_environment(self, days: int = 30) -> Dict[str, Any]:
        """Compute weighted Pearson correlations between each environmental
        factor and symptom severity.  Days with higher severity are weighted
        more heavily so the engine learns from flare conditions first.

        Returns the legacy `sleep` / `stress` / `exercise` sub-dicts so
        cli.py menu_reports() continues to work unchanged, plus a richer
        `correlations` dict sorted by absolute correlation strength.
        """
        features = self._load_range_features(days)

        if len(features) < 5:
            return {'error': 'Insufficient data (need at least 5 logged days)'}

        flare_features     = [f for f in features if f['is_flare_day']]
        non_flare_features = [f for f in features if not f['is_flare_day']]

        # --- Legacy CLI-compatible block (sleep / stress / exercise) ---
        def _safe_avg(lst):
            return statistics.mean(lst) if lst else None

        def _flare_vs_normal(field):
            f_vals = [f[field] for f in flare_features     if f.get(field) is not None]
            n_vals = [f[field] for f in non_flare_features if f.get(field) is not None]
            f_avg  = _safe_avg(f_vals)
            n_avg  = _safe_avg(n_vals)
            return f_avg, n_avg

        f_sleep, n_sleep = _flare_vs_normal('sleep_hours')
        f_stress, n_stress = _flare_vs_normal('stress_level')
        f_ex, n_ex = _flare_vs_normal('exercise_minutes')

        legacy_sleep = {
            'flare_avg':  round(f_sleep, 1)  if f_sleep  is not None else None,
            'normal_avg': round(n_sleep, 1)  if n_sleep  is not None else None,
            'difference': round((n_sleep or 0) - (f_sleep or 0), 1),
        }
        legacy_stress = {
            'flare_avg':  round(f_stress, 1) if f_stress is not None else None,
            'normal_avg': round(n_stress, 1) if n_stress is not None else None,
            'difference': round((f_stress or 0) - (n_stress or 0), 1),
        }
        legacy_exercise = {
            'flare_avg':  round(f_ex, 1) if f_ex is not None else None,
            'normal_avg': round(n_ex, 1) if n_ex is not None else None,
            'difference': round((n_ex or 0) - (f_ex or 0), 1),
        }

        # --- Weighted Pearson correlations for all env factors ---
        env_fields = [
            ('stress_level',           'Stress Level (1-10)'),
            ('sleep_hours',            'Sleep Hours'),
            ('sleep_quality',          'Sleep Quality (1-10)'),
            ('air_quality_index',      'Air Quality Index (AQI)'),
            ('barometric_pressure_hpa','Barometric Pressure (hPa)'),
            ('humidity_percent',       'Humidity (%)'),
            ('temperature_f',          'Temperature (°F)'),
            ('exercise_minutes',       'Exercise (minutes)'),
            ('alcohol_units',          'Alcohol (units)'),
            ('caffeine_mg',            'Caffeine (mg)'),
            ('hydration_oz',           'Hydration (oz)'),
        ]

        correlations: Dict[str, Any] = {}

        for field_name, label in env_fields:
            xs = [f[field_name]      for f in features]
            ys = [f['avg_severity']  for f in features]
            ws = [f['severity_weight'] for f in features]

            # Drop rows where env value is missing
            valid = [(x, y, w) for x, y, w in zip(xs, ys, ws) if x is not None]
            if len(valid) < 3:
                continue

            vxs, vys, vws = zip(*valid)
            r = self._weighted_pearson(list(vxs), list(vys), list(vws))

            f_vals = [x for x, y, _ in valid if y >= 7]
            n_vals = [x for x, y, _ in valid if y <  7]

            correlations[field_name] = {
                'label':           label,
                'correlation':     round(r, 3),
                'abs_correlation': round(abs(r), 3),
                'direction':  'positive' if r >  0.05 else 'negative' if r < -0.05 else 'none',
                'impact':     'strong'   if abs(r) >= 0.5
                              else 'moderate' if abs(r) >= 0.3
                              else 'weak',
                'data_points':      len(valid),
                'flare_day_avg':    round(statistics.mean(f_vals), 2) if f_vals else None,
                'non_flare_day_avg': round(statistics.mean(n_vals), 2) if n_vals else None,
            }

        # Sort by absolute correlation strength
        correlations = dict(sorted(
            correlations.items(),
            key=lambda kv: kv[1]['abs_correlation'],
            reverse=True,
        ))

        top_factors = [
            k for k, v in correlations.items()
            if v['abs_correlation'] >= 0.3
        ][:5]

        return {
            'days_analyzed':  days,
            'logged_days':    len(features),
            'flare_days':     len(flare_features),
            'non_flare_days': len(non_flare_features),
            # Legacy keys — consumed by cli.py menu_reports()
            'sleep':          legacy_sleep,
            'stress':         legacy_stress,
            'exercise':       legacy_exercise,
            # New rich output
            'correlations':   correlations,
            'top_factors':    top_factors,
        }

    # =========================================================
    # ENVIRONMENTAL RISK COMPONENT
    # =========================================================

    def _compute_env_risk_score(self, features: List[Dict]) -> float:
        """Derive a 0-1 environmental risk score from recent logged data.
        Uses weighted means so conditions on high-severity days count more."""
        recent  = features[-7:] if len(features) >= 7 else features
        weights = [f['severity_weight'] for f in recent]
        scores: List[float] = []

        # AQI: 0-50 = good, 150+ = unhealthy
        aqi_data = [(f['air_quality_index'], w)
                    for f, w in zip(recent, weights)
                    if f.get('air_quality_index') is not None]
        if aqi_data:
            w_aqi = self._weighted_mean([v for v, _ in aqi_data], [w for _, w in aqi_data])
            if w_aqi is not None:
                scores.append(min(1.0, w_aqi / 150))

        # Humidity: extremes (< 30% or > 70%) are associated with flares
        hum_data = [(f['humidity_percent'], w)
                    for f, w in zip(recent, weights)
                    if f.get('humidity_percent') is not None]
        if hum_data:
            w_hum = self._weighted_mean([v for v, _ in hum_data], [w for _, w in hum_data])
            if w_hum is not None:
                scores.append(min(1.0, abs(w_hum - 50) / 50))

        # Barometric pressure: day-over-day delta > 10 hPa is a common flare trigger
        pressure_pts = sorted(
            [(f['date'], f['barometric_pressure_hpa'])
             for f in recent if f.get('barometric_pressure_hpa') is not None],
            key=lambda t: t[0],
        )
        if len(pressure_pts) >= 2:
            deltas = [
                abs(pressure_pts[i + 1][1] - pressure_pts[i][1])
                for i in range(len(pressure_pts) - 1)
            ]
            scores.append(min(1.0, max(deltas) / 15))

        return statistics.mean(scores) if scores else 0.5

    # =========================================================
    # RISK PREDICTION
    # =========================================================

    def predict_flare_risk(self, lookahead_days: int = 7) -> Dict[str, Any]:
        """Predict flare-up risk using severity-weighted historical data.

        Each of the last 30 logged days is multiplied by its severity weight
        before contributing to the baseline statistics, so the model learns
        mostly from what was happening on the worst days.
        """
        features = self._load_range_features(30)

        if len(features) < 7:
            return {
                'error':      'Insufficient historical data (need at least 7 logged days)',
                'risk_level': 'unknown',
                'confidence': 0,
            }

        recent  = features[-14:] if len(features) >= 14 else features
        weights = [f['severity_weight'] for f in recent]

        # Weighted means — high-severity days dominate each average
        w_severity  = self._weighted_mean([f['avg_severity']       for f in recent], weights) or 0.0
        w_adherence = self._weighted_mean([f['medication_adherence'] for f in recent], weights) or 1.0

        sleep_pairs  = [(f['sleep_hours'],  f['severity_weight']) for f in recent if f['sleep_hours']  is not None]
        stress_pairs = [(f['stress_level'], f['severity_weight']) for f in recent if f['stress_level'] is not None]

        w_sleep  = self._weighted_mean([p[0] for p in sleep_pairs],  [p[1] for p in sleep_pairs])
        w_stress = self._weighted_mean([p[0] for p in stress_pairs], [p[1] for p in stress_pairs])

        # --- Component scores (each normalised to 0-1) ---
        severity_component   = (w_severity / 10) * self.COMPONENT_WEIGHTS['symptom_severity']
        adherence_component  = (1 - w_adherence) * self.COMPONENT_WEIGHTS['medication_adherence']
        sleep_component      = (max(0, 8 - (w_sleep  or 8)) / 8)  * self.COMPONENT_WEIGHTS['sleep_quality']
        stress_component     = ((w_stress or 5) / 10)              * self.COMPONENT_WEIGHTS['stress_level']
        env_score            = self._compute_env_risk_score(features)
        env_component        = env_score * self.COMPONENT_WEIGHTS['environmental_factors']

        risk_score = (severity_component + adherence_component +
                      sleep_component + stress_component + env_component)

        # Boost when flares are clustered in the recent window
        recent_flares = sum(1 for f in features[-14:] if f['is_flare_day'])
        if recent_flares >= 3:
            risk_score = min(1.0, risk_score + 0.15)

        if risk_score >= 0.7:
            risk_level = 'high'
        elif risk_score >= 0.4:
            risk_level = 'moderate'
        else:
            risk_level = 'low'

        # Confidence grows with the number of logged days (caps at 0.92)
        confidence = min(0.92, 0.50 + len(features) * 0.015)

        result = {
            'lookahead_days': lookahead_days,
            'risk_score':     round(min(1.0, risk_score), 3),
            'risk_level':     risk_level,
            'confidence':     round(confidence, 2),
            # Legacy keys consumed by cli.py
            'factors': {
                'recent_flares':        recent_flares,
                'avg_severity':         round(w_severity, 2),
                'medication_adherence': round(w_adherence, 2),
                'avg_sleep_hours':      round(w_sleep,  1) if w_sleep  is not None else None,
                'avg_stress_level':     round(w_stress, 1) if w_stress is not None else None,
            },
            # Weighted component breakdown (how much each factor drives the score)
            'weighted_factors': {
                'symptom_severity':         round(severity_component,  3),
                'medication_non_adherence': round(adherence_component, 3),
                'sleep_deficit':            round(sleep_component,     3),
                'stress_level':             round(stress_component,    3),
                'environmental_factors':    round(env_component,       3),
            },
            'recommendations': self._generate_recommendations(
                risk_level, w_adherence, w_sleep, w_stress,
            ),
            'ml_used':       False,
            'ml_risk_score': None,
        }

        # Phase 2 ML overlay: replace rule-based score when the Random Forest model
        # is available and the patient has at least 30 logged days of history.
        if self.ml_model is not None and len(features) >= 30:
            try:
                agg = self.ml_model.aggregate_features(features[-14:])
                ml  = self.ml_model.predict(agg)
                result['ml_risk_score'] = ml['risk_score']
                result['risk_score']    = ml['risk_score']
                result['risk_level']    = ml['risk_level']
                result['ml_used']       = True
            except Exception:
                pass  # keep rule-based result on any ML failure

        return result

    def _generate_recommendations(
        self,
        risk_level: str,
        adherence: float,
        sleep: Optional[float],
        stress: Optional[float],
    ) -> List[str]:
        recs: List[str] = []

        if risk_level == 'high':
            recs.append("High flare risk detected — consider contacting your healthcare provider.")

        if adherence < 0.8:
            recs.append("Medication adherence is below 80%. Consistent dosing reduces flare frequency.")

        if sleep is not None and sleep < 6.5:
            recs.append(f"Average weighted sleep is {sleep:.1f} hrs. Aim for 7-9 hrs to support recovery.")

        if stress is not None and stress >= 7:
            recs.append(f"Weighted stress average is {stress:.1f}/10. Stress-reduction techniques may help.")

        if not recs:
            recs.append("Patterns look stable. Keep maintaining your current health habits.")

        return recs

    # =========================================================
    # FULL WEIGHTED FACTOR REPORT
    # =========================================================

    def weighted_factor_report(self, days: int = 30) -> Dict[str, Any]:
        """Return a comprehensive summary of weighted patterns:
        risk score, top correlated factors, trigger insights, and trends.
        Intended as the primary analysis output for future UI integration."""
        risk        = self.predict_flare_risk()
        correlations = self.correlate_symptoms_with_environment(days)
        triggers    = self.detect_triggers(days)
        trends      = self.detect_trends(days)

        return {
            'generated_at':   datetime.now().isoformat(),
            'days_analyzed':  days,
            'risk_prediction': risk,
            'top_correlated_factors': correlations.get('correlations', {}),
            'top_triggers':   triggers.get('top_triggers', []),
            'trends':         trends,
        }

    # =========================================================
    # ML PLACEHOLDER (Phase 2)
    # =========================================================

    def train_model(self, days: int = 90) -> Dict[str, Any]:
        """Train (or retrain) the Random Forest flare predictor.

        Exports the last `days` days of logged data, fits a severity-weighted
        RandomForest with a 35% importance cap, saves to data/model.pkl, and
        reloads the model into this predictor so predictions upgrade immediately.
        """
        try:
            from ml_engine import FlareRFModel
        except ImportError:
            return {"error": "scikit-learn / numpy not installed. Run: pip install scikit-learn numpy"}

        tmp_path = os.path.join(self.storage.data_dir, "training_export.json")
        self.export_training_data(tmp_path, days)

        with open(tmp_path, "r") as f:
            records = json.load(f)

        model  = FlareRFModel()
        report = model.train(records)

        if report.get("status") == "ok":
            self.ml_model = model   # live-swap — next predict_flare_risk() uses ML

        return report

    def export_training_data(self, output_path: str, days: int = 90) -> Dict[str, Any]:
        """Export severity-weighted features in ML-ready format."""
        end_date   = date.today()
        start_date = end_date - timedelta(days=days)
        features   = self.extract_features_range(start_date.isoformat(), end_date.isoformat())

        with open(output_path, 'w') as f:
            json.dump(features, f, indent=2, default=str)

        print(f"[AI Engine] Exported {len(features)} days of training data to {output_path}")
        return {'records': len(features), 'path': output_path}
