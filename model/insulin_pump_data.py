import json
import time
import uuid
from utils.senml_helper import SenMLHelper

class InsulinPumpCommand:
    """Comando per la pompa insulina"""

    def __init__(self, pump_id, patient_id, delivery_mode, insulin_amount,
                 delivery_rate=None, priority="normal", reason=None):

        # Identificazione
        self.pump_id = pump_id
        self.patient_id = patient_id
        self.command_id = str(uuid.uuid4())[:8]  # ID univoco comando

        # Parametri erogazione
        self.delivery_mode = delivery_mode  # "basal", "bolus", "correction", "emergency_stop"
        self.insulin_amount = insulin_amount  # unità
        self.delivery_rate = delivery_rate  # unità/ora per basale

        # Metadati comando
        self.timestamp = int(time.time())
        self.priority = priority  # "low", "normal", "high", "emergency"
        self.reason = reason  # Motivo del comando

        # Parametri di sicurezza
        self.max_delivery_rate = 25.0  # unità/ora massime
        self.timeout_minutes = 60  # timeout comando

    def is_safe_dose(self, max_bolus=15.0, max_basal=5.0):
        """Verifica se la dose è sicura"""
        if self.delivery_mode in ["bolus", "correction"]:
            return self.insulin_amount <= max_bolus
        elif self.delivery_mode == "basal":
            return (self.delivery_rate or 0) <= max_basal
        return True

    def to_json(self):
        """Converte in JSON per invio MQTT"""
        return json.dumps(self, default=lambda o: o.__dict__)

    def to_senml(self):
        """ Converte il comando in formato SenML"""
        return SenMLHelper.create_insulin_command(
            patient_id=self.patient_id,
            units=self.insulin_amount,
            command_type=self.delivery_mode,
            timestamp=self.timestamp
        )


class InsulinPumpStatus:
    """Status della pompa insulina"""

    def __init__(self, pump_id, patient_id):
        # Identificazione
        self.pump_id = pump_id
        self.patient_id = patient_id

        # Stato operativo
        self.pump_status = "active"  # "active", "inactive", "error", "maintenance", "low_insulin"
        self.current_basal_rate = 1.0  # unità/ora

        # Livelli
        self.insulin_reservoir_level = 300.0  # unità rimanenti
        self.insulin_reservoir_capacity = 300.0  # capacità totale
        self.battery_level = 100.0  # percentuale

        # Ultima erogazione
        self.last_bolus_amount = None
        self.last_bolus_time = None
        self.total_daily_insulin = 0.0

        # Allarmi e errori
        self.active_alarms = []
        self.last_error = None

        # Timestamp
        self.timestamp = int(time.time())

    def update_status(self):
        """Aggiorna lo status della pompa simulando operazioni reali"""
        # Simula consumo insulina basale
        hourly_consumption = self.current_basal_rate / 720.0  # ogni 5 secondi
        self.insulin_reservoir_level = max(0.0, self.insulin_reservoir_level - hourly_consumption)

        # Simula consumo batteria
        battery_drain = 0.1  # 0.01% ogni aggiornamento
        self.battery_level = max(0.0, self.battery_level - battery_drain)

        # Controlla allarmi
        self._check_alarms()

        # Aggiorna timestamp
        self.timestamp = int(time.time())

    def _check_alarms(self):
        """Controlla e aggiorna gli allarmi"""
        self.active_alarms = []

        if self.insulin_percentage() < 20.0:
            self.active_alarms.append("low_insulin")

        if self.battery_level < 15.0:
            self.active_alarms.append("low_battery")

        if self.insulin_reservoir_level <= 0:
            self.active_alarms.append("insulin_empty")
            self.pump_status = "inactive"

        if self.battery_level <= 5.0:
            self.active_alarms.append("battery_critical")

    def deliver_bolus(self, amount, bolus_type="correction"):
        """Simula erogazione di un bolo"""
        if self.insulin_reservoir_level >= amount and self.pump_status == "active":
            self.insulin_reservoir_level -= amount
            self.last_bolus_amount = amount
            self.last_bolus_time = int(time.time())
            self.total_daily_insulin += amount
            return True
        return False

    def insulin_percentage(self):
        """Percentuale insulina rimanente"""
        return (self.insulin_reservoir_level / self.insulin_reservoir_capacity) * 100

    def needs_refill(self, threshold=20.0):
        """Verifica se serve ricarica insulina"""
        return self.insulin_percentage() < threshold

    def battery_low(self, threshold=15.0):
        """Verifica se batteria è scarica"""
        return self.battery_level < threshold

    def has_critical_alarms(self):
        """Verifica se ci sono allarmi critici"""
        critical_alarms = ["insulin_empty", "battery_critical", "pump_error"]
        return any(alarm in self.active_alarms for alarm in critical_alarms)

    def to_json(self):
        """Converte in JSON per invio MQTT"""
        return json.dumps(self, default=lambda o: o.__dict__)

    def to_senml(self):
        return SenMLHelper.create_pump_status(
            patient_id=self.patient_id,
            reservoir_level=self.insulin_reservoir_level,
            battery_level=self.battery_level,
            status=self.pump_status,
            timestamp=self.timestamp
        )