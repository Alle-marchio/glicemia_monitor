import json
import time


class PatientDescriptor:
    """Descrittore del paziente diabetico con parametri di configurazione"""

    def __init__(self, patient_id, name, age, weight,
                 target_glucose_min=70.0, target_glucose_max=140.0,
                 hypoglycemia_threshold=60.0, hyperglycemia_threshold=250.0,
                 insulin_sensitivity_factor=50.0, carb_ratio=12.0, basal_insulin_rate=1.0,
                 sensor_reading_interval=5, alert_enabled=True, emergency_contact=None):

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