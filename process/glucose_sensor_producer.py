import paho.mqtt.client as mqtt
import json
import time
import sys
import os
import random

# Import dei modelli
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.glucose_sensor_data import GlucoseSensorData
from conf.mqtt_conf_params import MqttConfigurationParameters as Config
from utils.senml_helper import SenMLHelper


class GlucoseSensorProducerSenML:
    """
    Sensore glicemia simulato (versione rifattorizzata):
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

        # Letture
        self.reading_interval = Config.GLUCOSE_READING_INTERVAL
        self.simulation_mode = simulation_mode
        self.reading_count = 0

        # Callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

    # ---------------------------------------------------------------------
    # MQTT CALLBACKS
    # ---------------------------------------------------------------------
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✅ Sensore glicemia (SenML) connesso al broker MQTT")
            print(f"📡 Topic pubblicazione: {self.publish_topic}")
            print(f"⏱️  Intervallo letture: {self.reading_interval}s")
            print(f"🎭 Modalità: {self.simulation_mode}")
            print("=" * 60)
        else:
            print(f"❌ Connessione fallita: rc={rc}")

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"⚠️ Disconnessione inattesa (rc={rc})")

    # ---------------------------------------------------------------------
    # LOGICA SIMULATIVA (SOLO VARIATION)
    # ---------------------------------------------------------------------
    def _generate_variation(self):
        """Genera una variazione della glicemia in base alla modalità scelto."""

        current_value = self.sensor.glucose_value

        if self.simulation_mode == "normal":
            target = random.uniform(90, 130)
            return (target - current_value) * 0.1 + random.uniform(-5, 5)

        elif self.simulation_mode == "hypoglycemia":
            v = random.uniform(-8, -2)
            if random.random() < 0.1:
                v = random.uniform(2, 8)
            return v

        elif self.simulation_mode == "hyperglycemia":
            v = random.uniform(2, 10)
            if random.random() < 0.1:
                v = random.uniform(-8, -2)
            return v

        elif self.simulation_mode == "fluctuating":
            return random.uniform(-15, 15)

        return random.uniform(-7, 7)

    def simulate_glucose_reading(self):
        """Genera una lettura completa delegando la logica al modello."""
        variation = self._generate_variation()
        self.sensor.apply_variation(variation, self.reading_interval)
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

            print(f"\n📊 Lettura #{self.reading_count} (SenML)")
            print(f"🩸 Glicemia: {reading.glucose_value:.1f} mg/dL {status_emoji}")
            print(f"📈 Status: {reading.glucose_status}")
            print(f"{trend_emoji} Trend: {reading.trend_direction} ({reading.trend_rate:.1f} mg/dL/min)")
            print(f"🔋 Batteria: {reading.battery_level:.1f}%")
            print(f"📡 Segnale: {reading.signal_strength} dBm")

            if reading.is_critical():
                print("🚨 Valore critico!")

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                preview = senml_json[:150] + "..." if len(senml_json) > 150 else senml_json
                print(f"✅ SenML pubblicato: {preview}")
            else:
                print(f"⚠️ Errore pubblicazione: rc={result.rc}")

        except Exception as e:
            print(f"❌ Errore nella pubblicazione: {e}")

    # ---------------------------------------------------------------------
    # UTILS
    # ---------------------------------------------------------------------
    def _get_status_emoji(self, status):
        return {
            "critical_low": "🔴🔻",
            "low": "🟡⬇️",
            "normal": "🟢✅",
            "high": "🟡⬆️",
            "critical_high": "🔴🔺"
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

    def run_n_readings(self, n):
        try:
            print("\n" + "=" * 60)
            print(f"🚀 AVVIO SENSORE GLICEMIA ({n} letture)")

            self.client.connect(self.broker_address, self.broker_port, 60)
            self.client.loop_start()

            for i in range(n):
                self.publish_reading()
                if i < n - 1:
                    time.sleep(self.reading_interval)

            print(f"✅ Completate {n} letture")
            time.sleep(1)
            self.stop()

        except KeyboardInterrupt:
            print("\n⏹️ Interrotto dall'utente")
            self.stop()

    def stop(self):
        print("\n🛑 Arresto sensore...")
        self.client.loop_stop()
        self.client.disconnect()
        print("✅ Sensore disconnesso")


# MAIN - Esempi di utilizzo
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Simulatore sensore glicemia SenML')
    parser.add_argument('--patient-id', type=str, default='patient_001',
                        help='ID del paziente')
    parser.add_argument('--sensor-id', type=str, default='sensor_001',
                        help='ID del sensore')
    parser.add_argument('--initial-glucose', type=float, default=120.0,
                        help='Valore glicemia iniziale (mg/dL)')
    parser.add_argument('--mode', type=str, default='normal',
                        choices=['normal', 'hypoglycemia', 'hyperglycemia', 'fluctuating'],
                        help='Modalità di simulazione')
    parser.add_argument('--readings', type=int, default=None,
                        help='Numero di letture da eseguire (default: infinito)')

    args = parser.parse_args()

    # Crea il sensore con supporto SenML
    sensor = GlucoseSensorProducerSenML(
        sensor_id=args.sensor_id,
        patient_id=args.patient_id,
        initial_glucose=args.initial_glucose,
        simulation_mode=args.mode
    )

    # Esegui in base ai parametri
    if args.readings:
        sensor.run_n_readings(args.readings)
    else:
        sensor.run_continuous()

    # Esempi di utilizzo:
    # python glucose_sensor_producer_senml.py --mode normal
    # python glucose_sensor_producer_senml.py --mode hyperglycemia --initial-glucose 200
    # python glucose_sensor_producer_senml.py --readings 20 --mode hypoglycemia