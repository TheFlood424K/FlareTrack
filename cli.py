# cli.py
# Command-line interface for FlareTrack
import os
import getpass
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
        print()
        print("=" * 50)
        print((" " + title.upper() + " ").center(50, "="))
        print("=" * 50)
        print()

    def run(self):
        """Main application loop."""
        while True:
            self.clear_screen()
            self.print_header("FlareTrack - Welcome, " + self.user_name)
            print("1. Log Symptom")
            print("2. Log Medication")
            print("3. Log Environmental Factors")
            print("4. View Today's Summary")
            print("5. AI Flare Prediction & Analysis")
            print("6. Adherence & Trend Reports")
            print("7. Search Logs by Trigger")
            print("0. Exit")
            print()
            choice = input("Select an option: ")

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
                print()
                print("Stay healthy! Goodbye.")
                break
            else:
                input("Invalid choice. Press Enter to try again...")

    # ========== LOGGING MENUS ==========

    def menu_log_symptom(self):
        self.print_header("Log New Symptom")
        name = input("Symptom name: ")
        try:
            severity = int(input("Severity (0-10): "))
            location = input("Body location (optional): ")
            desc = input("Description (optional): ")
            raw = input("Triggers (comma separated, or leave blank): ")
            triggers = [t.strip() for t in raw.split(",") if t.strip()]

            self.tracker.log_symptom(
                symptom_name=name,
                severity=severity,
                location=location,
                description=desc,
                triggers=triggers
            )
            print()
            input("Symptom logged successfully! Press Enter to return...")
        except ValueError as e:
            print()
            input("Error: " + str(e) + ". Press Enter to try again...")

    def menu_log_medication(self):
        self.print_header("Log Medication")
        name = input("Medication name: ")
        dosage = input("Dosage (e.g. 500mg): ")
        print()
        print("Status options: taken, missed, late, skipped")
        status = input("Status: ").lower()

        try:
            self.tracker.log_medication(name, dosage, status)
            print()
            input("Medication logged successfully! Press Enter to return...")
        except ValueError as e:
            print()
            input("Error: " + str(e) + ". Press Enter to try again...")

    def menu_log_environment(self):
        self.print_header("Log Environment & Lifestyle")
        try:
            weather = input("Weather description: ")
            temp_raw = input("Temperature (leave blank to skip): ")
            temp = float(temp_raw) if temp_raw.strip() else None

            sleep_raw = input("Hours of sleep: ")
            sleep = float(sleep_raw) if sleep_raw.strip() else 7.0

            stress_raw = input("Stress level (1-10): ")
            stress = int(stress_raw) if stress_raw.strip() else 5

            ex_raw = input("Exercise minutes: ")
            exercise = int(ex_raw) if ex_raw.strip() else 0

            self.tracker.log_environment(
                weather=weather,
                temperature=temp,
                sleep_hours=sleep,
                stress_level=stress,
                exercise_minutes=exercise
            )
            print()
            input("Environmental factors logged! Press Enter to return...")
        except ValueError:
            print()
            input("Invalid input. Press Enter to try again...")

    # ========== ANALYSIS MENUS ==========

    def menu_view_summary(self):
        self.print_header("Today's Health Summary")
        summary = self.tracker.get_daily_summary()
        print("Date: " + summary['date'])
        print("Patient: " + summary['patient'])
        print()

        print("--- Symptoms ---")
        if not summary['symptoms']:
            print("No symptoms logged today.")
        for s in summary['symptoms']:
            print(" * " + s['symptom_name'] + ": Severity " + str(s['severity']) + " (" + s['location'] + ")")
        print()

        print("--- Medications ---")
        if not summary['medications']:
            print("No medications logged today.")
        for m in summary['medications']:
            print(" * " + m['medication_name'] + " " + m['dosage'] + ": " + m['status'].upper())
        print()

        print("--- Environment ---")
        if summary['environment']:
            env = summary['environment']
            print(" Weather: " + str(env.get('weather', '')))
            print(" Sleep: " + str(env.get('sleep_hours', '')) + " hrs")
            print(" Stress: " + str(env.get('stress_level', '')) + "/10")
        else:
            print("No environmental data logged today.")
        print()
        input("Press Enter to return...")

    def menu_ai_prediction(self):
        self.print_header("AI Flare Prediction")
        print("Analyzing your historical patterns...")
        print()

        prediction = self.predictor.predict_flare_risk()
        if 'error' in prediction:
            print("NOTICE: " + prediction['error'])
        else:
            risk = prediction['risk_level'].upper()
            marker = "!!!" if risk == "HIGH" else "!!" if risk == "MODERATE" else "OK"
            print("7-DAY FLARE RISK: [" + marker + "] " + risk)
            print("Risk Score: " + str(prediction['risk_score']))
            print("Confidence: " + str(int(prediction['confidence'] * 100)) + "%")
            print()

            print("Contributing Factors:")
            factors = prediction['factors']
            print(" Recent Flare Days: " + str(factors['recent_flares']))
            print(" Avg Severity: " + str(factors['avg_severity']) + "/10")
            print(" Adherence Rate: " + str(int(factors['medication_adherence'] * 100)) + "%")
            print()

            print("Recommendations:")
            for rec in prediction['recommendations']:
                print(" * " + rec)
        print()
        input("Press Enter to return...")

    def menu_reports(self):
        self.print_header("Trends & Adherence Reports")
        adherence = self.tracker.get_medication_adherence(days=14)
        print("14-Day Medication Adherence: " + str(round(adherence.get('adherence_rate', 0), 1)) + "%")
        taken = adherence.get('taken', 0)
        total = adherence.get('total_doses', 0)
        print("Doses: " + str(taken) + " taken / " + str(total) + " total")
        print()

        print("Environmental Correlations (30 Days):")
        correlations = self.predictor.correlate_symptoms_with_environment()
        if 'error' in correlations:
            print(" " + correlations['error'])
        else:
            sleep_diff = correlations['sleep']['difference']
            stress_diff = correlations['stress']['difference']
            print(" Sleep: Flare days had " + str(sleep_diff) + " fewer hours")
            print(" Stress: Flare days were " + str(stress_diff) + " points higher")
        print()
        input("Press Enter to return...")

    def menu_search(self):
        self.print_header("Search by Trigger")
        trigger = input("Enter trigger to search (e.g. caffeine, stress): ")
        results = self.tracker.search_by_trigger(trigger)
        print()
        print("Found " + str(len(results)) + " match(es) for '" + trigger + "':")
        for res in results:
            print(" * " + res.timestamp[:10] + ": " + res.symptom_name + " (Severity " + str(res.severity) + ")")
        print()
        input("Press Enter to return...")


def main_menu():
    """Entry point called by main.py. Sets up patient, storage, tracker, and runs the CLI."""
    print()
    print("=" * 50)
    print(" Welcome to FlareTrack ".center(50, "="))
    print("=" * 50)
    print()

    storage = StorageManager()

    # ========== PASSWORD AUTHENTICATION ==========
    # Check if a password has been set
    if storage.encryption and storage.encryption.has_password():
        # Prompt for password
        print("This app is password protected.")
        print()
        for attempt in range(3):
            password = getpass.getpass("Enter app password: ")
            if storage.encryption.verify_password(password):
                print("\nAccess granted!\n")
                break
            else:
                print("\nIncorrect password.")
                if attempt < 2:
                    print(f"You have {2 - attempt} attempt(s) remaining.\n")
                else:
                    print("Too many failed attempts. Exiting.\n")
                    return
    elif storage.use_encryption:
        # First launch with encryption enabled - set up password
        print("Welcome! Let's set up app password protection.")
        print("This password will be required each time you launch FlareTrack.")
        print()
        while True:
            pw1 = getpass.getpass("Choose an app password: ")
            if len(pw1) < 4:
                print("Password must be at least 4 characters.\n")
                continue
            pw2 = getpass.getpass("Confirm password: ")
            if pw1 == pw2:
                storage.encryption.set_password(pw1)
                print("\nPassword set successfully!\n")
                break
            else:
                print("Passwords do not match. Try again.\n")

    # ========== PATIENT PROFILE SETUP ==========
    # Load existing patient or create new one
    patient = storage.load_patient()
    if patient is None:
        print("No patient profile found. Let's create one.")
        print()
        name = input("Your name: ")
        age_raw = input("Your age: ")
        age = int(age_raw) if age_raw.strip().isdigit() else 0
        diag_raw = input("Diagnoses (comma separated, or leave blank): ")
        diagnoses = [d.strip() for d in diag_raw.split(",") if d.strip()]
        patient = Patient(name=name, age=age, diagnosis=diagnoses)
        storage.save_patient(patient)
        print()
        print("Profile created for " + patient.name + ".")

    tracker = ChronicTracker(patient=patient, storage_manager=storage)
    predictor = FlareUpPredictor(storage_manager=storage)
    app = FlareTrackCLI(tracker=tracker, predictor=predictor)
    app.run()
