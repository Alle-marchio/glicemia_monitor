import json
import time
from utils.senml_helper import SenMLHelper

class PatientDescriptor:
    """Descrittore del paziente diabetico con parametri di configurazione"""

    def __init__(self, patient_id, name, age, weight,
                 target_glucose_min, target_glucose_max,
                 hypoglycemia_threshold, hyperglycemia_threshold,
                 insulin_sensitivity_factor, carb_ratio, basal_insulin_rate,
                 sensor_reading_interval, alert_enabled, emergency_contact):

        # Identificazione paziente
        self.patient_id = patient_id
        self.name = name
        self.age = age
        self.weight = weight  # kg

        # Parametri glicemici (mg/dL)
        self.target_glucose_min = target_glucose_min  # Soglia minima normale
        self.target_glucose_max = target_glucose_max  # Soglia massima normale
        self.hypoglycemia_threshold = hypoglycemia_threshold  # Soglia ipoglicemia
        self.hyperglycemia_threshold = hyperglycemia_threshold  # Soglia iperglicemia

        # Parametri insulina
        self.insulin_sensitivity_factor = insulin_sensitivity_factor  # mg/dL per unità di insulina
        self.carb_ratio = carb_ratio  # grammi di carboidrati per unità di insulina
        self.basal_insulin_rate = basal_insulin_rate  # unità/ora

        # Configurazione sistema
        self.sensor_reading_interval = sensor_reading_interval  # minuti
        self.alert_enabled = alert_enabled
        self.emergency_contact = emergency_contact

        # Metadati
        self.created_at = int(time.time())
        self.last_updated = int(time.time())

    def is_glucose_in_target_range(self, glucose_value):
        """Verifica se il valore glicemico è nel range target"""
        return self.target_glucose_min <= glucose_value <= self.target_glucose_max

    def is_hypoglycemic(self, glucose_value):
        """Verifica se il valore indica ipoglicemia"""
        return glucose_value < self.hypoglycemia_threshold

    def is_hyperglycemic(self, glucose_value):
        """Verifica se il valore indica iperglicemia"""
        return glucose_value > self.hyperglycemia_threshold

    def calculate_insulin_dose(self, current_glucose, target_glucose=None):
        """Calcola dose insulina necessaria per correzione"""
        if target_glucose is None:
            target_glucose = (self.target_glucose_min + self.target_glucose_max) / 2

        glucose_difference = current_glucose - target_glucose
        if glucose_difference <= 0:
            return 0.0

        return glucose_difference / self.insulin_sensitivity_factor

    def to_json(self):
        """Converte il modello in JSON per invio MQTT"""
        return json.dumps(self, default=lambda o: o.__dict__)

    def to_senml(self):
        timestamp = self.last_updated

        base_name = f"urn:patient:{self.patient_id}:descriptor:"
        return json.dumps([
            {"bn": base_name, "bt": timestamp},
            {"n": "target_glucose_min", "v": self.target_glucose_min},
            {"n": "target_glucose_max", "v": self.target_glucose_max},
            {"n": "hypo_threshold", "v": self.hypoglycemia_threshold},
            {"n": "hyper_threshold", "v": self.hyperglycemia_threshold},
            {"n": "isf", "v": self.insulin_sensitivity_factor},
            {"n": "carb_ratio", "v": self.carb_ratio},
            {"n": "basal_rate", "v": self.basal_insulin_rate},
            {"n": "alerts_enabled", "vs": str(self.alert_enabled)}
        ])

    @classmethod
    def from_json_file(cls, file_path):
        """Crea un'istanza di PatientDescriptor caricando i parametri da un file JSON."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"File di configurazione paziente non trovato a: {file_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Errore di sintassi nel file JSON: {file_path}")

        return cls(
            patient_id=data.get("patient_id"),
            name=data.get("name"),
            age=data.get("age"),
            weight=data.get("weight"),
            target_glucose_min=data.get("target_glucose_min"),
            target_glucose_max=data.get("target_glucose_max"),
            hypoglycemia_threshold=data.get("hypoglycemia_threshold"),
            hyperglycemia_threshold=data.get("hyperglycemia_threshold"),
            insulin_sensitivity_factor=data.get("insulin_sensitivity_factor"),
            carb_ratio=data.get("carb_ratio"),
            basal_insulin_rate=data.get("basal_insulin_rate"),
            sensor_reading_interval=data.get("sensor_reading_interval"),
            alert_enabled=data.get("alert_enabled"),
            emergency_contact=data.get("emergency_contact")
        )