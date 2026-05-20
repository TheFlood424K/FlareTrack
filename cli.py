# cli.py
# Command-line interface for FlareTrack
import os
import getpass
from datetime import date
from tracker import ChronicTracker
from ai_engine import FlareUpPredictor
from pubmed_engine import PubMedEngine
from context_snapshot import ContextSnapshot
from storage import StorageManager
from models import Patient


class FlareTrackCLI:
    """Interactive command-line interface for the health tracking application."""

    def __init__(
        self,
        tracker: ChronicTracker,
        predictor: FlareUpPredictor,
        pubmed_engine: PubMedEngine = None,
        snapshot: ContextSnapshot = None,
    ):
        self.tracker   = tracker
        self.predictor = predictor
        self.pubmed    = pubmed_engine or PubMedEngine()
        self.snapshot  = snapshot
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
            print("8. PubMed Evidence Lookup")
            print("9. Environmental Context Snapshot")
            print("10. Train / Retrain ML Model")
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
            elif choice == '8':
                self.menu_pubmed_evidence()
            elif choice == '9':
                self.menu_context_snapshot()
            elif choice == '10':
                self.menu_train_model()
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
            if prediction.get('ml_used'):
                print("Method:     Random Forest (ML model active)")
            else:
                print("Method:     Rule-based engine  [train via option 10 to upgrade]")
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

    def menu_pubmed_evidence(self):
        self.print_header("PubMed Evidence Lookup")
        diagnoses = self.tracker.patient.diagnosis
        if not diagnoses:
            print("No diagnoses on your profile.")
            print("Add them when creating your profile to enable evidence lookup.")
            print()
            input("Press Enter to return...")
            return

        print("Diagnoses: " + ", ".join(diagnoses))
        print()
        print("Analysing your top triggers and correlated factors...")
        print("(Results are cached locally for 7 days — internet required on first run)")
        print()

        report      = self.predictor.weighted_factor_report(days=30)
        top_triggers = report.get("top_triggers", [])

        if not top_triggers:
            print("Not enough logged data to identify triggers yet.")
            print("Log at least 5 days to enable evidence lookup.")
            print()
            input("Press Enter to return...")
            return

        print("Top triggers detected: " + ", ".join(top_triggers))
        print()
        print("Querying PubMed... (this may take a few seconds)")
        print()

        enriched = self.pubmed.enrich_factor_report(report, diagnoses, max_per_query=3)
        evidence  = enriched.get("pubmed_evidence", {})

        if "error" in evidence:
            print("Error: " + evidence["error"])
            print()
            input("Press Enter to return...")
            return

        # --- Trigger evidence ---
        print("--- Evidence by Trigger ---")
        trigger_ev = evidence.get("trigger_evidence", {})
        for trigger, papers in trigger_ev.items():
            print()
            badge = "[PubMed backed]" if papers else "[pattern only]"
            print(f"  {trigger.upper()} {badge}")
            if not papers:
                print("    No matching papers found in PubMed.")
            for p in papers[:2]:
                authors = ", ".join(p["authors"]) or "Unknown"
                print(f"    * {p['title']} ({p['year']})")
                print(f"      {authors}")
                print(f"      {p['url']}")
                if p.get("abstract"):
                    excerpt = p["abstract"][:200].replace("\n", " ")
                    print(f"      \"{excerpt}...\"")

        # --- Factor evidence ---
        factor_ev = evidence.get("factor_evidence", {})
        if factor_ev:
            print()
            print("--- Evidence by Correlated Factor ---")
            for field, papers in factor_ev.items():
                label = field.replace("_", " ").title()
                print()
                print(f"  {label}: {len(papers)} paper(s) found")
                for p in papers[:1]:
                    print(f"    * {p['title']} ({p['year']})")
                    print(f"      {p['url']}")

        # --- 70/30 blend summary ---
        blend = evidence.get("evidence_blend", {})
        if blend:
            print()
            print("--- Evidence Confidence ---")
            supported    = evidence.get("academic_supported_triggers", [])
            pattern_only = evidence.get("pattern_only_triggers", [])
            print(f"  PubMed-backed triggers:  {', '.join(supported) or 'none'}")
            print(f"  Pattern-only triggers:   {', '.join(pattern_only) or 'none'}")
            print(f"  Supported fraction:      {int(blend.get('supported_fraction', 0) * 100)}%")
            print(f"  Blended confidence:      {int(blend.get('blended_confidence', 0) * 100)}%")
            print(f"  (Academic weight 70% + User-pattern weight 30%)")

        stats = self.pubmed.cache_stats()
        print()
        print(f"Cache: {stats['cached_queries']} queries stored in {stats['cache_dir']} ({stats['total_size_kb']} KB)")
        print()
        input("Press Enter to return...")

    def menu_train_model(self):
        self.print_header("Train / Retrain ML Model")
        print("Fits a Random Forest classifier on your last 90 days of logs.")
        print("Requires: pip install scikit-learn numpy")
        print("Minimum:  30 logged days with symptoms.")
        print()

        confirm = input("Proceed with training? (y/n): ").strip().lower()
        if confirm != 'y':
            print()
            input("Cancelled. Press Enter to return...")
            return

        print()
        print("Exporting training data and fitting model...")
        print()

        report = self.predictor.train_model(days=90)

        if 'error' in report:
            print("Error: " + report['error'])
            print()
            input("Press Enter to return...")
            return

        print("Training complete!")
        print()
        print("  Samples:    " + str(report['n_samples']) + " logged days")
        print("  Flare days: " + str(report['n_flare_days']))
        if report.get('cv_auc') is not None:
            print("  CV ROC-AUC: " + str(report['cv_auc']) +
                  "  (1.0 = perfect, 0.5 = random guess)")
        print()

        capped = report.get('importances_capped', {})
        raw    = report.get('importances_raw',    {})
        if capped:
            print("Feature Importances (capped at 35% each):")
            print("-" * 54)
            for name, imp in sorted(capped.items(), key=lambda x: -x[1]):
                raw_imp  = raw.get(name, imp)
                bar      = "#" * max(1, int(imp * 50))
                cap_tag  = f"  [was {raw_imp * 100:.0f}%]" if raw_imp > imp + 0.005 else ""
                print(f"  {name:<28} {bar:<20} {imp * 100:5.1f}%{cap_tag}")
            print()

        if report.get('capped_features'):
            print("  Features that hit the 35% cap (excess redistributed):")
            for fname in report['capped_features']:
                print("    * " + fname)
            print()

        print("Model saved to data/model.pkl")
        print("Option 5 will now use this model when >= 30 logged days are available.")
        print()
        input("Press Enter to return...")

    def menu_context_snapshot(self):
        self.print_header("Environmental Context Snapshot")

        if not self.snapshot.has_location():
            print("No location saved in your profile.")
            print("Coordinates are sent only to Open-Meteo (free, no account needed).")
            print("Find yours: right-click your location on Google Maps.")
            print()
            lat_raw = input("Latitude  (e.g. 40.7128, blank to cancel): ").strip()
            if not lat_raw:
                print()
                input("Cancelled. Press Enter to return...")
                return
            lon_raw = input("Longitude (e.g. -74.0060): ").strip()
            try:
                self.tracker.patient.latitude  = float(lat_raw)
                self.tracker.patient.longitude = float(lon_raw)
            except ValueError:
                print()
                input("Invalid coordinates. Press Enter to return...")
                return
            self.tracker.storage.save_patient(self.tracker.patient)
            print()
            print("Location saved.")
            print()

        print("Fetching current environmental data...")
        print()
        snap = self.snapshot.fetch_and_merge(date.today().isoformat())
        print()

        if "error" in snap:
            print("Error: " + snap["error"])
        else:
            print("--- Weather ---")
            print(" Conditions:  " + str(snap.get("weather", "N/A")))
            print(" Temperature: " + str(snap.get("temperature_f", "N/A")) + " °F")
            print(" Humidity:    " + str(snap.get("humidity_percent", "N/A")) + " %")
            print(" Pressure:    " + str(snap.get("barometric_pressure_hpa", "N/A")) + " hPa")
            print(" UV Index:    " + str(snap.get("uv_index", "N/A")))
            print(" Wind:        " + str(snap.get("wind_speed_mph", "N/A")) + " mph")
            print()
            print("--- Air Quality ---")
            print(" US AQI:      " + str(snap.get("air_quality_index", "N/A")))
            if snap.get("pm25") is not None:
                print(" PM2.5:       " + str(snap["pm25"]) + " μg/m³")
            if snap.get("pm10") is not None:
                print(" PM10:        " + str(snap["pm10"]) + " μg/m³")
            if snap.get("european_aqi") is not None:
                print(" EU AQI:      " + str(snap["european_aqi"]))
            print()
            print("--- Pollen ---")
            if snap.get("pollen_tree_index") is not None:
                _scale = ["None", "Very Low", "Low", "Medium", "High", "Very High"]
                def _pl(v):
                    return f"{v} ({_scale[v]})" if isinstance(v, int) and 0 <= v <= 5 else str(v)
                print(" Tree:        " + _pl(snap["pollen_tree_index"]) + "  (Tomorrow.io 0-5)")
                print(" Grass:       " + _pl(snap["pollen_grass_index"]))
                print(" Weed:        " + _pl(snap["pollen_weed_index"]))
            elif snap.get("pollen_index") is not None:
                print(" Index:       " + str(snap["pollen_index"]) + " grains/m³  (Open-Meteo, EU only)")
            else:
                print(" No pollen data. Set TOMORROW_API_KEY for global tree/grass/weed indices.")
            print()
            stats = self.snapshot.cache_stats()
            print(f"Cache: {stats['cached_days']} day(s) stored in {stats['cache_dir']} "
                  f"({stats['total_size_kb']} KB, {stats['ttl_hours']}h TTL)")

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
        print()

        # Location setup for auto environmental snapshots
        print("Optional: Enter your GPS coordinates for auto environmental snapshots.")
        print("When you log a flare (severity ≥7), weather, pressure, AQI, and pollen")
        print("are fetched automatically from Open-Meteo (free, no account needed).")
        print("Find your coordinates: right-click your location on Google Maps.")
        print()
        lat_raw = input("Latitude  (e.g. 40.7128, blank to skip): ").strip()
        if lat_raw:
            lon_raw = input("Longitude (e.g. -74.0060): ").strip()
            try:
                patient.latitude  = float(lat_raw)
                patient.longitude = float(lon_raw)
                storage.save_patient(patient)
                print("Location saved.")
            except ValueError:
                print("Invalid input — location skipped. Configure later via menu option 9.")
        else:
            print("Skipped — configure location anytime via menu option 9.")

    snapshot  = ContextSnapshot(patient=patient, storage=storage)
    tracker   = ChronicTracker(patient=patient, storage_manager=storage, snapshot=snapshot)
    predictor = FlareUpPredictor(storage_manager=storage)
    pubmed    = PubMedEngine()
    app       = FlareTrackCLI(tracker=tracker, predictor=predictor, pubmed_engine=pubmed, snapshot=snapshot)
    app.run()
