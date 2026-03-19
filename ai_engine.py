# ai_engine.py
# AI flare-up prediction system (placeholder with ML-ready structure)

from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import statistics
import json

class FlareUpPredictor:
    """AI engine for predicting flare-ups based on historical data."""
    
    def __init__(self, storage_manager):
        self.storage = storage_manager
        self.risk_weights = {
            'symptom_severity': 0.35,
            'medication_adherence': 0.25,
            'environmental_factors': 0.20,
            'sleep_quality': 0.10,
            'stress_level': 0.10
        }
    
    # ========== FEATURE EXTRACTION ==========
    
    def extract_features(self, date_str: str) -> Dict[str, Any]:
        """Extract all relevant features for a given date."""
        symptoms = self.storage.load_symptoms(date_str)
        medications = self.storage.load_medications(date_str)
        environment = self.storage.load_environment(date_str)
        
        # Symptom features
        symptom_count = len(symptoms)
        avg_severity = statistics.mean([s.severity for s in symptoms]) if symptoms else 0
        max_severity = max([s.severity for s in symptoms]) if symptoms else 0
        
        # Medication adherence
        med_total = len(medications)
        med_taken = sum(1 for m in medications if m.status == "taken")
        adherence_rate = (med_taken / med_total) if med_total > 0 else 1.0
        
        # Environmental features
        sleep_hours = environment.sleep_hours if environment else 7
        stress_level = environment.stress_level if environment else 5
        exercise_minutes = environment.exercise_minutes if environment else 0
        
        return {
            'date': date_str,
            'symptom_count': symptom_count,
            'avg_severity': avg_severity,
            'max_severity': max_severity,
            'medication_adherence': adherence_rate,
            'sleep_hours': sleep_hours,
            'stress_level': stress_level,
            'exercise_minutes': exercise_minutes,
            'is_flare_day': max_severity >= 7  # Define flare as severity >= 7
        }
    
    def extract_features_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Extract features for a date range."""
        features_list = []
        current = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()
        
        while current <= end:
            date_str = current.isoformat()
            features = self.extract_features(date_str)
            features_list.append(features)
            current += timedelta(days=1)
        
        return features_list
    
    # ========== PATTERN DETECTION ==========
    
    def detect_triggers(self, days: int = 30) -> Dict[str, Any]:
        """Analyze historical data to detect common triggers."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        trigger_analysis = defaultdict(list)
        
        # Analyze each day
        current = start_date
        while current <= end_date:
            date_str = current.isoformat()
            symptoms = self.storage.load_symptoms(date_str)
            
            for symptom in symptoms:
                for trigger in symptom.triggers:
                    trigger_analysis[trigger.lower()].append(symptom.severity)
            
            current += timedelta(days=1)
        
        # Calculate statistics for each trigger
        results = {}
        for trigger, severities in trigger_analysis.items():
            results[trigger] = {
                'occurrences': len(severities),
                'avg_severity': statistics.mean(severities),
                'max_severity': max(severities),
                'risk_score': statistics.mean(severities) * (len(severities) / days)
            }
        
        # Sort by risk score
        sorted_triggers = sorted(results.items(), key=lambda x: x[1]['risk_score'], reverse=True)
        
        return {
            'days_analyzed': days,
            'triggers': dict(sorted_triggers),
            'top_triggers': [t[0] for t in sorted_triggers[:5]]
        }
    
    def detect_trends(self, days: int = 30) -> Dict[str, Any]:
        """Identify trends in symptoms over time."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        features = self.extract_features_range(start_date.isoformat(), end_date.isoformat())
        
        if len(features) < 7:
            return {'error': 'Insufficient data for trend analysis'}
        
        # Calculate trends
        severities = [f['avg_severity'] for f in features if f['avg_severity'] > 0]
        flare_days = sum(1 for f in features if f['is_flare_day'])
        
        # Simple trend: compare first week to last week
        first_week_avg = statistics.mean([f['avg_severity'] for f in features[:7]])
        last_week_avg = statistics.mean([f['avg_severity'] for f in features[-7:]])
        
        trend_direction = "improving" if last_week_avg < first_week_avg else "worsening" if last_week_avg > first_week_avg else "stable"
        
        return {
            'days_analyzed': days,
            'flare_days': flare_days,
            'flare_frequency': flare_days / days,
            'avg_severity_overall': statistics.mean(severities) if severities else 0,
            'trend_direction': trend_direction,
            'first_week_avg': first_week_avg,
            'last_week_avg': last_week_avg
        }
    
    # ========== PREDICTION ==========
    
    def predict_flare_risk(self, lookahead_days: int = 7) -> Dict[str, Any]:
        """Predict flare-up risk for upcoming days (placeholder algorithm)."""
        # Analyze last 30 days
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        historical_features = self.extract_features_range(start_date.isoformat(), end_date.isoformat())
        
        if len(historical_features) < 7:
            return {
                'error': 'Insufficient historical data',
                'risk_level': 'unknown',
                'confidence': 0
            }
        
        # Calculate risk factors
        recent_flares = sum(1 for f in historical_features[-14:] if f['is_flare_day'])
        avg_recent_severity = statistics.mean([f['avg_severity'] for f in historical_features[-7:]])
        avg_adherence = statistics.mean([f['medication_adherence'] for f in historical_features[-7:]])
        avg_sleep = statistics.mean([f['sleep_hours'] for f in historical_features[-7:] if f['sleep_hours']])
        avg_stress = statistics.mean([f['stress_level'] for f in historical_features[-7:] if f['stress_level']])
        
        # Simple risk scoring (placeholder for ML model)
        risk_score = (
            (avg_recent_severity / 10) * self.risk_weights['symptom_severity'] +
            ((1 - avg_adherence)) * self.risk_weights['medication_adherence'] +
            ((10 - avg_sleep) / 10) * self.risk_weights['sleep_quality'] +
            (avg_stress / 10) * self.risk_weights['stress_level']
        )
        
        # Recent flare pattern
        if recent_flares >= 3:
            risk_score += 0.15
        
        # Determine risk level
        if risk_score >= 0.7:
            risk_level = 'high'
        elif risk_score >= 0.4:
            risk_level = 'moderate'
        else:
            risk_level = 'low'
        
        return {
            'lookahead_days': lookahead_days,
            'risk_score': round(risk_score, 3),
            'risk_level': risk_level,
            'confidence': 0.65,  # Placeholder confidence
            'factors': {
                'recent_flares': recent_flares,
                'avg_severity': round(avg_recent_severity, 2),
                'medication_adherence': round(avg_adherence, 2),
                'avg_sleep_hours': round(avg_sleep, 1),
                'avg_stress_level': round(avg_stress, 1)
            },
            'recommendations': self._generate_recommendations(risk_level, avg_adherence, avg_sleep, avg_stress)
        }
    
    def _generate_recommendations(self, risk_level: str, adherence: float, sleep: float, stress: float) -> List[str]:
        """Generate personalized recommendations based on risk factors."""
        recommendations = []
        
        if risk_level == 'high':
            recommendations.append("⚠️ High flare risk detected. Consider consulting your healthcare provider.")
        
        if adherence < 0.8:
            recommendations.append("💊 Improve medication adherence to reduce flare risk.")
        
        if sleep < 6.5:
            recommendations.append("😴 Aim for 7-9 hours of sleep to support recovery.")
        
        if stress >= 7:
            recommendations.append("🧘 High stress detected. Consider stress-reduction techniques.")
        
        if not recommendations:
            recommendations.append("✅ Keep up the good work! Maintain current health habits.")
        
        return recommendations
    
    # ========== CORRELATION ANALYSIS ==========
    
    def correlate_symptoms_with_environment(self, days: int = 30) -> Dict[str, Any]:
        """Find correlations between symptoms and environmental factors."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        features = self.extract_features_range(start_date.isoformat(), end_date.isoformat())
        
        if len(features) < 10:
            return {'error': 'Insufficient data for correlation analysis'}
        
        # Separate flare days vs non-flare days
        flare_features = [f for f in features if f['is_flare_day']]
        non_flare_features = [f for f in features if not f['is_flare_day']]
        
        if not flare_features or not non_flare_features:
            return {'error': 'Need both flare and non-flare days for comparison'}
        
        # Compare averages
        flare_sleep = statistics.mean([f['sleep_hours'] for f in flare_features if f['sleep_hours']])
        normal_sleep = statistics.mean([f['sleep_hours'] for f in non_flare_features if f['sleep_hours']])
        
        flare_stress = statistics.mean([f['stress_level'] for f in flare_features if f['stress_level']])
        normal_stress = statistics.mean([f['stress_level'] for f in non_flare_features if f['stress_level']])
        
        flare_exercise = statistics.mean([f['exercise_minutes'] for f in flare_features if f['exercise_minutes'] is not None])
        normal_exercise = statistics.mean([f['exercise_minutes'] for f in non_flare_features if f['exercise_minutes'] is not None])
        
        return {
            'days_analyzed': days,
            'flare_days': len(flare_features),
            'non_flare_days': len(non_flare_features),
            'sleep': {
                'flare_avg': round(flare_sleep, 1),
                'normal_avg': round(normal_sleep, 1),
                'difference': round(normal_sleep - flare_sleep, 1)
            },
            'stress': {
                'flare_avg': round(flare_stress, 1),
                'normal_avg': round(normal_stress, 1),
                'difference': round(flare_stress - normal_stress, 1)
            },
            'exercise': {
                'flare_avg': round(flare_exercise, 1),
                'normal_avg': round(normal_exercise, 1),
                'difference': round(normal_exercise - flare_exercise, 1)
            }
        }
    
    # ========== ML PLACEHOLDER ==========
    
    def train_model(self, days: int = 90):
        """Placeholder for future ML model training."""
        print("[AI Engine] ML model training not yet implemented.")
        print(f"[AI Engine] Would train on {days} days of historical data.")
        print("[AI Engine] Future: Use scikit-learn, TensorFlow, or PyTorch here.")
        return {'status': 'placeholder', 'message': 'ML integration pending'}
    
    def export_training_data(self, output_path: str, days: int = 90):
        """Export data in ML-ready format."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        features = self.extract_features_range(start_date.isoformat(), end_date.isoformat())
        
        with open(output_path, 'w') as f:
            json.dump(features, f, indent=2)
        
        print(f"[AI Engine] Exported {len(features)} days of training data to {output_path}")
        return {'records': len(features), 'path': output_path}
