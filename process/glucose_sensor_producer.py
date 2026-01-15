import paho.mqtt.client as mqtt
import time
import sys
import os
import json

# Import dei modelli
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.glucose_sensor_data import GlucoseSensorData
from model.glucose_simulation_logic import GlucoseSimulationLogic
from model.patient_descriptor import PatientDescriptor
from conf.SystemConfiguration import SystemConfig as Config
from utils.senml_helper import SenMLHelper

class GlucoseSensorProducerSenML:
    """
    Sensore glicemia simulato:
    - La logica del sensore è nel modello
    - Qui si decide solo la modalità e la variation da applicare
    """

    def __init__(self, sensor_id, patient_id, initial_glucose=120.0, simulation_mode="normal"):
        self.sensor_id = sensor_id
        self.patient_id = patient_id

        # Istanza del modello
        self.sensor = GlucoseSensorData(sensor_id, patient_id, initial_glucose)

        # Configurazione MQTT
        self.broker_address = Config.BROKER_ADDRESS
        self.broker_port = Config.BROKER_PORT
        self.client = mqtt.Client(f"glucose_sensor_senml_{sensor_id}")

        # Topic MQTT
        self.base_topic = f"/iot/patient/{patient_id}"
        self.publish_topic = f"{self.base_topic}/glucose/sensor/data"
        self.command_topic = f"{self.base_topic}/insulin/pump/command"

        # Letture
        self.reading_interval = Config.GLUCOSE_READING_INTERVAL
        self.simulation_mode = simulation_mode
        self.reading_count = 0

        # Parametri per l'effetto insulina
        self.active_insulin_doses = []  # Lista di [{'amount': X, 'start_time': Y}]
        # Usa il fattore di sensibilità dalle configurazioni globali
        self.insulin_sensitivity_factor = Config.INSULIN_CORRECTION_FACTOR

        # Callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message  # Abilitiamo la ricezione di messaggi

    # ---------------------------------------------------------------------
    # MQTT CALLBACKS
    # ---------------------------------------------------------------------
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✅ Sensore glicemia (SenML) connesso al broker MQTT")
            print(f"📡 Topic pubblicazione: {self.publish_topic}")
            print(f"📥 Subscribing a: {self.command_topic}")
            print(f"⏱️ Intervallo letture: {self.reading_interval}s")
            print(f"🎭 Modalità: {self.simulation_mode}")
            print("=" * 60)

            client.subscribe(self.command_topic, qos=Config.QOS_COMMANDS)
            self.control_topic = f"{self.base_topic}/glucose/sensor/set_mode"
            client.subscribe(self.control_topic)
            print(f"📥 Ascolto cambio modalità su: {self.control_topic}")

        else:
            print(f"❌ Connessione fallita: rc={rc}")

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"⚠️ Disconnessione inattesa (rc={rc})")

    def on_message(self, client, userdata, msg):
        """Callback quando arriva un comando MQTT (gestisce l'insulina erogata)"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()

            if msg.topic == getattr(self, 'control_topic', ''):
                self.change_simulation_mode(payload)

            if "insulin/pump/command" in topic:
                # Parse del comando SenML per estrarre la dose
                parsed_senml = SenMLHelper.parse_senml(payload)
                data = parsed_senml.get("measurements", {})

                dose = data.get("dose", {}).get("value", 0.0)
                delivery_type = data.get("type", {}).get("value", "bolus")

                # Registra la dose se è un bolo o una correzione valida
                if dose > 0 and delivery_type in ["bolus", "correction"]:
                    self.active_insulin_doses.append({
                        'amount': dose,
                        'start_time': time.time()
                    })
                    print(f"💉 Sensore: Registrata dose {dose:.2f}U di insulina per simulazione effetto.")

        except Exception as e:
            print(f"❌ Errore nell'elaborazione del comando SenML in Sensore: {e}")

    # ---------------------------------------------------------------------
    # LOGICA SIMULATIVA
    # ---------------------------------------------------------------------
    def simulate_glucose_reading(self):
        """Genera una lettura completa, delegando la variazione alla logica di simulazione."""

        # CHIAMA LA LOGICA DI SIMULAZIONE ESTERNA per ottenere la variazione
        natural_variation = GlucoseSimulationLogic.generate_variation(
            current_value=self.sensor.glucose_value,
            simulation_mode=self.simulation_mode
        )
        # CALCOLA L'EFFETTO DELL'INSULINA ATTIVA
        insulin_effect = GlucoseSimulationLogic.calculate_insulin_effect(
            active_insulin_doses=self.active_insulin_doses,
            isf=self.insulin_sensitivity_factor,
            current_time=time.time(),
            reading_interval=self.reading_interval
        )

        total_variation = natural_variation + insulin_effect

        # Log per debug (opzionale, ma utile per l'esame)
        if insulin_effect < -0.1:
            print(f"   [DBG] Var. Naturale: {natural_variation:.1f}, Effetto Insulina: {insulin_effect:.1f}")

        # APPLICA LA VARIAZIONE al modello
        self.sensor.apply_variation(total_variation, self.reading_interval)
        return self.sensor

    # ---------------------------------------------------------------------
    # CREAZIONE SENML
    # ---------------------------------------------------------------------
    def create_senml_message(self, reading):
        """Genera il SenML tramite il modello."""
        return reading.to_senml()

    # ---------------------------------------------------------------------
    # PUBBLICAZIONE MQTT
    # ---------------------------------------------------------------------
    def publish_reading(self):
        try:
            self.reading_count += 1

            reading = self.simulate_glucose_reading()
            senml_json = self.create_senml_message(reading)

            result = self.client.publish(
                self.publish_topic,
                senml_json,
                qos=Config.QOS_SENSOR_DATA,
                retain=False
            )

            # Output leggibile
            status_emoji = self._get_status_emoji(reading.glucose_status)
            trend_emoji = self._get_trend_emoji(reading.trend_direction)

            print(f"\n📊 Lettura glicemia #{self.reading_count} (SenML)")
            print(f"🩸 Glicemia: {reading.glucose_value:.1f} mg/dL {status_emoji}")
            print(f"📈 Status: {reading.glucose_status}")
            print(f"{trend_emoji} Trend: {reading.trend_direction} ({reading.trend_rate:.1f} mg/dL/min)")
            print(f"🔋 Batteria sensore glicemia: {reading.battery_level:.1f}%")
            print(f"📡 Segnale: {reading.signal_strength} dBm")
            print("-" * 40)
            if reading.is_critical():
                print("🚨 Valore critico!")

            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"⚠️ Errore pubblicazione: rc={result.rc}")

        except Exception as e:
            print(f"❌ Errore nella pubblicazione: {e}")

    # ---------------------------------------------------------------------
    # UTILS
    # ---------------------------------------------------------------------
    def _get_status_emoji(self, status):
        return {
            "critical_low": "🔴🔻🔻",
            "low": "🔴🔻",
            "normal": "🟢",
            "high": "🔴🔺",
            "critical_high": "🔴🔺🔺"
        }.get(status, "⚪")

    def _get_trend_emoji(self, trend):
        return {
            "rising": "📈",
            "falling": "📉",
            "stable": "➡️"
        }.get(trend, "❓")

    # ---------------------------------------------------------------------
    # RUN MODES
    # ---------------------------------------------------------------------
    def change_simulation_mode(self, new_mode):
        valid = ["normal", "hypoglycemia", "hyperglycemia", "fluctuating"]
        if new_mode in valid:
            self.simulation_mode = new_mode
            print(f"🎭 Modalità cambiata in: {new_mode}")
        else:
            print(f"⚠️ Modalità non valida. Valide: {', '.join(valid)}")

    def run_continuous(self):
        try:
            print("\n" + "=" * 60)
            print("🚀 AVVIO SENSORE GLICEMIA (SenML)")
            print("=" * 60)

            self.client.connect(self.broker_address, self.broker_port, 60)
            self.client.loop_start()

            while True:
                self.publish_reading()
                time.sleep(self.reading_interval)

        except KeyboardInterrupt:
            print("\n⏹️ Interrotto dall'utente")
            self.stop()

    def stop(self):
        print("\n🛑 Arresto sensore...")
        self.client.loop_stop()
        self.client.disconnect()
        print("✅ Sensore disconnesso")


if __name__ == "__main__":

    # Rimuoviamo l'importazione di argparse

    # Definisce il percorso di default al file JSON nella cartella conf/
    CONFIG_FILE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'conf',
        'patient_config.json'
    )

    # Valori di default interni al main (se non specificati nel JSON)
    initial_glucose = 120.0
    simulation_mode = "normal"
    sensor_id = "sensor_001"  # ID del sensore non del paziente

    # Configurazione paziente - ORA CARICATA DA FILE
    try:
        patient = PatientDescriptor.from_json_file(CONFIG_FILE_PATH)
        patient_id = patient.patient_id

        print(f"✅ Configurazione paziente '{patient.name}' caricata da: {CONFIG_FILE_PATH}")

    except (FileNotFoundError, ValueError) as e:
        print(f"❌ Errore di caricamento o parsing della configurazione: {e}")
        sys.exit(1)

    # Crea il sensore
    sensor = GlucoseSensorProducerSenML(
        sensor_id=sensor_id,
        patient_id=patient_id,
        initial_glucose=initial_glucose,
        simulation_mode=simulation_mode
    )

    sensor.run_continuous()
