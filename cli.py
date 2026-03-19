# cli.py
# Command-line interface for FlareTrack

import os
import sys
from datetime import datetime
from tracker import ChronicTracker
from ai_engine import FlareUpPredictor
from storage import StorageManager
from models import Patient

class FlareTrackCLI:
    """Interactive command-line interface for the health tracking application."""
    
    def __init__(self, tracker: ChronicTracker, predictor: FlareUpPredictor):
        self.tracker = tracker
        self.predictor = predictor
        self.user_name = tracker.patient.name
    
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self, title):
        print("
" + "="*50)
        print(f" {title.upper()} ".center(50, "="))
        print("="*50 + "
")
    
    def run(self):
        """Main application loop."""
        while True:
            self.clear_screen()
            self.print_header(f"FlareTrack - Welcome, {self.user_name}")
            
            print("1. Log Symptom")
            print("2. Log Medication")
            print("3. Log Environmental Factors")
            print("4. View Today's Summary")
            print("5. AI Flare Prediction & Analysis")
            print("6. Adherence & Trend Reports")
            print("7. Search Logs by Trigger")
            print("0. Exit")
            
            choice = input("
Select an option: ")
            
            if choice == '1':
                self.menu_log_symptom()
            elif choice == '2':
                self.menu_log_medication()
            elif choice == '3':
                self.menu_log_environment()
            elif choice == '4':
                self.menu_view_summary()
            elif choice == '5':
                self.menu_ai_prediction()
            elif choice == '6':
                self.menu_reports()
            elif choice == '7':
                self.menu_search()
            elif choice == '0':
                print("
Stay healthy! Goodbye.")
                break
            else:
                input("
Invalid choice. Press Enter to try again...")

    # ========== LOGGING MENUS ==========

    def menu_log_symptom(self):
        self.print_header("Log New Symptom")
        name = input("Symptom name: ")
        try:
            severity = int(input("Severity (0-10): "))
            location = input("Body location (optional): ")
            desc = input("Description (optional): ")
            triggers = input("Triggers (comma separated): ").split(",")
            triggers = [t.strip() for t in triggers if t.strip()]
            
            self.tracker.log_symptom(
                symptom_name=name,
                severity=severity,
                location=location,
                description=desc,
                triggers=triggers
            )
            input("
Symptom logged successfully! Press Enter to return...")
        except ValueError as e:
            input(f"
Error: {e}. Press Enter to try again...")

    def menu_log_medication(self):
        self.print_header("Log Medication")
        name = input("Medication name: ")
        dosage = input("Dosage (e.g. 500mg): ")
        print("
Status options: taken, missed, late, skipped")
        status = input("Status: ").lower()
        
        try:
            self.tracker.log_medication(name, dosage, status)
            input("
Medication logged successfully! Press Enter to return...")
        except ValueError as e:
            input(f"
Error: {e}. Press Enter to try again...")

    def menu_log_environment(self):
        self.print_header("Log Environment & Lifestyle")
        try:
            weather = input("Weather description: ")
            temp = float(input("Temperature: ") or 0)
            sleep = float(input("Hours of sleep: ") or 7)
            stress = int(input("Stress level (1-10): ") or 5)
            exercise = int(input("Exercise minutes: ") or 0)
            
            self.tracker.log_environment(
                weather=weather,
                temperature=temp,
                sleep_hours=sleep,
                stress_level=stress,
                exercise_minutes=exercise
            )
            input("
Environmental factors logged! Press Enter to return...")
        except ValueError:
            input("
Invalid input. Press Enter to try again...")

    # ========== ANALYSIS MENUS ==========

    def menu_view_summary(self):
        self.print_header("Today's Health Summary")
        summary = self.tracker.get_daily_summary()
        
        print(f"Date: {summary['date']}")
        print(f"Patient: {summary['patient']}")
        
        print("
--- Symptoms ---")
        if not summary['symptoms']:
            print("No symptoms logged today.")
        for s in summary['symptoms']:
            print(f"• {s['symptom_name']}: Severity {s['severity']} ({s['location']})")
            
        print("
--- Medications ---")
        if not summary['medications']:
            print("No medications logged today.")
        for m in summary['medications']:
            print(f"• {m['medication_name']} {m['dosage']}: {m['status'].upper()}")
            
        print("
--- Environment ---")
        if summary['environment']:
            env = summary['environment']
            print(f"Weather: {env['weather']}")
            print(f"Sleep: {env['sleep_hours']} hrs | Stress: {env['stress_level']}/10")
        else:
            print("No environmental data logged today.")
            
        input("
Press Enter to return...")

    def menu_ai_prediction(self):
        self.print_header("AI Flare Prediction")
        print("Analyzing your historical patterns...
")
        
        prediction = self.predictor.predict_flare_risk()
        
        if 'error' in prediction:
            print(f"NOTICE: {prediction['error']}")
        else:
            risk = prediction['risk_level'].upper()
            color = "!!!" if risk == "HIGH" else "!!" if risk == "MODERATE" else "✓"
            
            print(f"7-DAY FLARE RISK: {color} {risk} {color}")
            print(f"Risk Score: {prediction['risk_score']}")
            print(f"Confidence: {prediction['confidence']*100}%")
            
            print("
Contributing Factors:")
            factors = prediction['factors']
            print(f"- Recent Flare Days: {factors['recent_flares']}")
            print(f"- Average Severity: {factors['avg_severity']}/10")
            print(f"- Adherence Rate: {factors['medication_adherence']*100}%")
            
            print("
Recommendations:")
            for rec in prediction['recommendations']:
                print(f"• {rec}")
                
        input("
Press Enter to return...")

    def menu_reports(self):
        self.print_header("Trends & Adherence Reports")
        
        adherence = self.tracker.get_medication_adherence(days=14)
        print(f"14-Day Medication Adherence: {adherence['adherence_rate']:.1f}%")
        print(f"Doses: {adherence['taken']} taken / {adherence['total_doses']} total")
        
        print("
Environmental Correlations (30 Days):")
        correlations = self.predictor.correlate_symptoms_with_environment()
        if 'error' in correlations:
            print(f"- {correlations['error']}")
        else:
            print(f"- Sleep: Flare days had {correlations['sleep']['difference']} fewer hours")
            print(f"- Stress: Flare days were {correlations['stress']['difference']} points higher")
            
        input("
Press Enter to return...")

    def menu_search(self):
        self.print_header("Search by Trigger")
        trigger = input("Enter trigger to search (e.g. 'caffeine', 'stress'): ")
        results = self.tracker.search_by_trigger(trigger)
        
        print(f"
Found {len(results)} matches for '{trigger}':")
        for res in results:
            print(f"• {res.timestamp[:10]}: {res.symptom_name} (Severity {res.severity})")
            
        input("
Press Enter to return...")
