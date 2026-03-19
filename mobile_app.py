# mobile_app.py
# Kivy mobile UI for FlareTrack Android app

import os
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView

from tracker import ChronicTracker
from ai_engine import FlareUpPredictor
from storage import StorageManager
from models import Patient


class MainMenu(Screen):
    """Main menu screen with navigation buttons."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        # Title
        layout.add_widget(Label(
            text="FlareTrack Mobile",
            font_size=32,
            size_hint_y=0.2
        ))
        
        # Navigation buttons
        buttons = [
            ("Log Symptom", "log_symptom"),
            ("Log Medication", "log_medication"),
            ("Log Environment", "log_environment"),
            ("Daily Summary", "summary"),
            ("AI Prediction", "prediction"),
            ("Reports", "reports"),
            ("Exit", "exit")
        ]
        
        for text, screen_name in buttons:
            btn = Button(text=text, size_hint_y=0.1, font_size=18)
            if screen_name == "exit":
                btn.bind(on_release=lambda x: App.get_running_app().stop())
            else:
                btn.bind(on_release=lambda x, sn=screen_name: self.change_screen(sn))
            layout.add_widget(btn)
            
        self.add_widget(layout)
        
    def change_screen(self, screen_name):
        self.manager.current = screen_name


class LogSymptomScreen(Screen):
    """Screen for logging symptoms."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        # Title
        self.layout.add_widget(Label(
            text="Log Symptom",
            font_size=24,
            size_hint_y=0.1
        ))
        
        # Input fields
        self.name_input = TextInput(
            hint_text="Symptom Name",
            multiline=False,
            size_hint_y=0.1
        )
        self.severity_input = TextInput(
            hint_text="Severity (0-10)",
            multiline=False,
            input_filter='int',
            size_hint_y=0.1
        )
        self.location_input = TextInput(
            hint_text="Location (optional)",
            multiline=False,
            size_hint_y=0.1
        )
        
        self.layout.add_widget(self.name_input)
        self.layout.add_widget(self.severity_input)
        self.layout.add_widget(self.location_input)
        
        # Buttons
        save_btn = Button(text="Save Symptom", size_hint_y=0.1)
        save_btn.bind(on_release=self.save_symptom)
        
        back_btn = Button(text="Back", size_hint_y=0.1)
        back_btn.bind(on_release=self.go_back)
        
        self.layout.add_widget(save_btn)
        self.layout.add_widget(back_btn)
        self.add_widget(self.layout)

    def save_symptom(self, instance):
        app = App.get_running_app()
        try:
            name = self.name_input.text
            severity = int(self.severity_input.text)
            location = self.location_input.text
            
            if not name:
                return
                
            app.tracker.log_symptom(
                symptom_name=name,
                severity=severity,
                location=location
            )
            
            # Clear inputs
            self.name_input.text = ""
            self.severity_input.text = ""
            self.location_input.text = ""
            
            self.go_back()
        except ValueError:
            pass

    def go_back(self, *args):
        self.manager.current = 'main_menu'


class SummaryScreen(Screen):
    """Screen showing daily summary."""
    def on_enter(self):
        self.clear_widgets()
        app = App.get_running_app()
        summary = app.tracker.get_daily_summary()
        
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        scroll = ScrollView()
        content = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=5
        )
        content.bind(minimum_height=content.setter('height'))
        
        # Date header
        content.add_widget(Label(
            text=f"Summary for {summary['date']}",
            font_size=20,
            size_hint_y=None,
            height=40
        ))
        
        # Symptoms section
        content.add_widget(Label(
            text="--- Symptoms ---",
            size_hint_y=None,
            height=30
        ))
        if summary['symptoms']:
            for s in summary['symptoms']:
                content.add_widget(Label(
                    text=f"* {s['symptom_name']} (Severity: {s['severity']})",
                    size_hint_y=None,
                    height=30
                ))
        else:
            content.add_widget(Label(
                text="No symptoms logged today",
                size_hint_y=None,
                height=30
            ))
            
        # Back button
        back_btn = Button(text="Back", size_hint_y=None, height=50)
        back_btn.bind(on_release=lambda x: self.go_back())
        
        scroll.add_widget(content)
        layout.add_widget(scroll)
        layout.add_widget(back_btn)
        self.add_widget(layout)
        
    def go_back(self):
        self.manager.current = 'main_menu'


class FlareTrackApp(App):
    """Main Kivy application."""
    def build(self):
        # Initialize storage and patient
        storage = StorageManager()
        patient = storage.load_patient()
        
        if not patient:
            # Create default patient for mobile
            patient = Patient(name="Mobile User", age=0)
            storage.save_patient(patient)
            
        # Initialize tracker and predictor
        self.tracker = ChronicTracker(patient=patient, storage_manager=storage)
        self.predictor = FlareUpPredictor(storage_manager=storage)
        
        # Create screen manager with all screens
        sm = ScreenManager()
        sm.add_widget(MainMenu(name='main_menu'))
        sm.add_widget(LogSymptomScreen(name='log_symptom'))
        
        # Placeholder screens (to be implemented)
        sm.add_widget(Screen(name='log_medication'))
        sm.add_widget(Screen(name='log_environment'))
        sm.add_widget(SummaryScreen(name='summary'))
        sm.add_widget(Screen(name='prediction'))
        sm.add_widget(Screen(name='reports'))
        
        return sm


if __name__ == '__main__':
    FlareTrackApp().run()
