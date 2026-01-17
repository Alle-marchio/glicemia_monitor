import json
import time
import random
from utils.senml_helper import SenMLHelper
from conf.SystemConfiguration import SystemConfig as Config

class GlucoseSensorData:
    def __init__(self, sensor_id, patient_id, glucose_value=None, initial_battery=None):

        # Identificazione
        self.sensor_id = sensor_id
        self.patient_id = patient_id

        # Dati glicemici
        if glucose_value is None:
            self.glucose_value = Config.TARGET_GLUCOSE
        else:
            self.glucose_value = glucose_value
        self.glucose_status = self._determine_glucose_status(self.glucose_value)

        # Metadati sensore
        self.sensor_status = "active"
        if initial_battery is not None:
            self.battery_level = initial_battery
        else:
            self.battery_level = 100.0

        # Segnale iniziale (valore medio)
        self.signal_strength = int((Config.SENSOR_SIGNAL_MIN_DBM + Config.SENSOR_SIGNAL_MAX_DBM) / 2)

        # Timestamp
        self.timestamp = int(time.time())

        # Trend
        self.trend_direction = "stable"
        self.trend_rate = 0.0  # mg/dL/min

        # Qualità del dato
        self.confidence_level = 1.0
        self.calibration_needed = False

    def _determine_glucose_status(self, glucose_value):
        """Determina lo stato glicemico rispetto alle soglie del sistema."""
        if glucose_value < Config.GLUCOSE_CRITICAL_LOW:
            return "critical_low"
        elif glucose_value < Config.GLUCOSE_LOW_THRESHOLD:
            return "low"
        elif glucose_value > Config.GLUCOSE_CRITICAL_HIGH:
            return "critical_high"
        elif glucose_value > Config.GLUCOSE_HIGH_THRESHOLD:
            return "high"
        else:
            return "normal"

    def apply_variation(self, variation: float, reading_interval: float):
        """
        Applica una variazione di glicemia e aggiorna TUTTI
        i parametri del sensore in modo coerente.
        """

        new_value = self.glucose_value + variation
        self.glucose_value = max(Config.SENSOR_MIN_VALUE, min(Config.SENSOR_MAX_VALUE, new_value))

        # Stato glicemico
        self.glucose_status = self._determine_glucose_status(self.glucose_value)

        # Calcolo del trend
        if variation > Config.SENSOR_TREND_THRESHOLD:
            self.trend_direction = "rising"
            self.trend_rate = abs(variation) / (reading_interval / 60.0)
        elif variation < -Config.SENSOR_TREND_THRESHOLD:
            self.trend_direction = "falling"
            self.trend_rate = abs(variation) / (reading_interval / 60.0)
        else:
            self.trend_direction = "stable"
            self.trend_rate = 0.0

        # Degradazione batteria
        drain = random.uniform(Config.SENSOR_BATTERY_DRAIN_MIN, Config.SENSOR_BATTERY_DRAIN_MAX)
        self.battery_level = max(0.0, self.battery_level - drain)

        # Qualità segnale
        self.signal_strength = random.randint(Config.SENSOR_SIGNAL_MIN_DBM, Config.SENSOR_SIGNAL_MAX_DBM)

        # Timestamp aggiornato
        self.timestamp = int(time.time())

    # METODI DI UTILITÀ
    def is_critical(self):
        return self.glucose_status in ["critical_low", "critical_high"]

    def requires_immediate_action(self):
        return (
                self.is_critical()
                or self.glucose_status in ["low", "high"]
                or self.sensor_status == "error"
        )

    def get_alert_level(self):
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
        return json.dumps(self, default=lambda o: o.__dict__)

    def to_senml(self):
        return SenMLHelper.create_glucose_sensor_full_data(
            patient_id=self.patient_id,
            sensor_id=self.sensor_id,
            glucose_value=self.glucose_value,
            glucose_status=self.glucose_status,
            trend_direction=self.trend_direction,
            trend_rate=self.trend_rate,
            battery_level=self.battery_level,
            signal_strength=self.signal_strength,
            sensor_status=self.sensor_status,
            confidence_level=self.confidence_level,
            calibration_needed=self.calibration_needed,
            timestamp=float(self.timestamp)
        )
