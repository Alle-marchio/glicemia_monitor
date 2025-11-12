import json
import time
import random
from utils.senml_helper import SenMLHelper


class GlucoseSensorData:
    """Dati del sensore di glucosio con informazioni complete"""

    def __init__(self, sensor_id, patient_id, glucose_value=100.0):
        # Identificazione
        self.sensor_id = sensor_id
        self.patient_id = patient_id

        # Dati glicemici
        self.glucose_value = glucose_value  # mg/dL
        self.glucose_status = self._determine_glucose_status(glucose_value)

        # Metadati sensore
        self.sensor_status = "active"
        self.battery_level = 100.0  # percentuale 0-100
        self.signal_strength = -45  # dBm

        # Timestamp
        self.timestamp = int(time.time())

        # Informazioni di contesto
        self.trend_direction = "stable"  # "rising", "falling", "stable"
        self.trend_rate = 0.0  # mg/dL per minuto

        # Qualità del dato
        self.confidence_level = 1.0  # 0-1, dove 1 è massima confidenza
        self.calibration_needed = False

    def _determine_glucose_status(self, glucose_value):
        """Determina lo status basato sul valore glicemico"""
        if glucose_value < 40.0:
            return "critical_low"
        elif glucose_value < 60.0:
            return "low"
        elif glucose_value > 250.0:
            return "high"
        elif glucose_value > 400.0:
            return "critical_high"
        else:
            return "normal"

    def update_measurements(self):
        """Aggiorna le misurazioni simulando letture reali del sensore"""
        # Simula variazioni naturali della glicemia
        variation = random.uniform(-10.0, 10.0)
        self.glucose_value = max(40.0, min(400.0, self.glucose_value + variation))

        # Aggiorna lo status
        self.glucose_status = self._determine_glucose_status(self.glucose_value)

        # Simula trend
        if variation > 3:
            self.trend_direction = "rising"
            self.trend_rate = abs(variation) / 5.0
        elif variation < -3:
            self.trend_direction = "falling"
            self.trend_rate = abs(variation) / 5.0
        else:
            self.trend_direction = "stable"
            self.trend_rate = 0.0

        # Simula degradazione batteria
        self.battery_level = max(0.0, self.battery_level - random.uniform(0.0, 0.1))

        # Aggiorna timestamp
        self.timestamp = int(time.time())

    def is_critical(self):
        """Verifica se la lettura è in stato critico"""
        return self.glucose_status in ["critical_low", "critical_high"]

    def requires_immediate_action(self):
        """Verifica se la lettura richiede azione immediata"""
        return (self.is_critical() or
                self.glucose_status in ["low", "high"] or
                self.sensor_status == "error")

    def get_alert_level(self):
        """Restituisce il livello di allerta"""
        if self.glucose_status == "critical_low":
            return "EMERGENCY_LOW"
        elif self.glucose_status == "critical_high":
            return "EMERGENCY_HIGH"
        elif self.glucose_status == "low":
            return "WARNING_LOW"
        elif self.glucose_status == "high":
            return "WARNING_HIGH"
        elif self.sensor_status == "error":
            return "SENSOR_ERROR"
        else:
            return "NORMAL"

    def to_json(self):
        """Converte in JSON per invio MQTT"""
        return json.dumps(self, default=lambda o: o.__dict__)

    def to_senml(self):
        return SenMLHelper.create_glucose_measurement(
            patient_id=self.patient_id,
            glucose_value=self.glucose_value,
            trend=self.trend_direction,
            timestamp=self.timestamp
        )