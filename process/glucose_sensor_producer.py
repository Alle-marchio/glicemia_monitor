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
    Sensore glicemia simulato con formato SenML che:
    - Genera letture glicemiche realistiche
    - Pubblica dati in formato SenML su MQTT
    - Simula variazioni naturali e scenari critici
    """

    def __init__(self, sensor_id, patient_id, initial_glucose=120.0, simulation_mode="normal"):
        self.sensor_id = sensor_id
        self.patient_id = patient_id

        # Inizializza il sensore con un valore di partenza
        self.sensor = GlucoseSensorData(sensor_id, patient_id, initial_glucose)

        # Configurazione MQTT
        self.broker_address = Config.BROKER_ADDRESS
        self.broker_port = Config.BROKER_PORT
        self.client = mqtt.Client(f"glucose_sensor_senml_{sensor_id}")

        # Topic MQTT per pubblicazione dati
        self.base_topic = f"/iot/patient/{patient_id}"
        self.publish_topic = f"{self.base_topic}/glucose/sensor/data"

        # Intervallo letture (secondi)
        self.reading_interval = Config.GLUCOSE_READING_INTERVAL

        # Modalità simulazione
        self.simulation_mode = simulation_mode
        self.reading_count = 0

        # Configurazione callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, rc):
        """Callback quando il sensore si connette al broker"""
        if rc == 0:
            print(f"✅ Sensore glicemia (SenML) connesso al broker MQTT")
            print(f"📡 Topic pubblicazione: {self.publish_topic}")
            print(f"⏱️  Intervallo letture: {self.reading_interval}s")
            print(f"🎭 Modalità: {self.simulation_mode}")
            print(f"📋 Formato: SenML (RFC 8428)")
            print("=" * 60)
        else:
            print(f"❌ Connessione fallita con codice: {rc}")

    def on_disconnect(self, client, userdata, rc):
        """Callback quando il sensore si disconnette"""
        if rc != 0:
            print(f"⚠️ Disconnessione imprevista dal broker (rc: {rc})")

    def simulate_glucose_reading(self):
        """
        Simula una lettura glicemica realistica in base alla modalità
        """
        current_value = self.sensor.glucose_value

        if self.simulation_mode == "normal":
            target = random.uniform(90, 130)
            variation = (target - current_value) * 0.1 + random.uniform(-5, 5)

        elif self.simulation_mode == "hypoglycemia":
            variation = random.uniform(-8, -2)
            if random.random() < 0.1:
                variation = random.uniform(2, 8)

        elif self.simulation_mode == "hyperglycemia":
            variation = random.uniform(2, 10)
            if random.random() < 0.1:
                variation = random.uniform(-8, -2)

        elif self.simulation_mode == "fluctuating":
            variation = random.uniform(-15, 15)

        else:
            variation = random.uniform(-7, 7)

        # Applica la variazione
        new_glucose = current_value + variation
        new_glucose = max(30.0, min(500.0, new_glucose))

        # Aggiorna il sensore
        self.sensor.glucose_value = new_glucose
        self.sensor.glucose_status = self.sensor._determine_glucose_status(new_glucose)

        # Aggiorna trend
        if variation > 3:
            self.sensor.trend_direction = "rising"
            self.sensor.trend_rate = abs(variation) / (self.reading_interval / 60.0)
        elif variation < -3:
            self.sensor.trend_direction = "falling"
            self.sensor.trend_rate = abs(variation) / (self.reading_interval / 60.0)
        else:
            self.sensor.trend_direction = "stable"
            self.sensor.trend_rate = 0.0

        # Aggiorna timestamp
        self.sensor.timestamp = int(time.time())

        # Simula consumo batteria
        self.sensor.battery_level = max(0.0, self.sensor.battery_level - random.uniform(0.01, 0.05))

        # Simula qualità segnale
        self.sensor.signal_strength = random.randint(-60, -40)

        return self.sensor

    def create_senml_message(self, reading):
        """
        Crea un messaggio SenML usando il SenMLHelper del progetto

        Args:
            reading: Oggetto GlucoseSensorData con la lettura corrente

        Returns:
            Stringa JSON in formato SenML
        """
        # Usa il metodo create_glucose_measurement del SenMLHelper
        senml_json = SenMLHelper.create_glucose_measurement(
            patient_id=self.patient_id,
            glucose_value=reading.glucose_value,
            trend=reading.trend_direction,
            timestamp=float(reading.timestamp)
        )

        return senml_json

    def publish_reading(self):
        """Pubblica la lettura in formato SenML sul topic MQTT"""
        try:
            # Incrementa contatore letture
            self.reading_count += 1

            # Ottieni lettura corrente
            reading = self.simulate_glucose_reading()

            # Crea messaggio SenML
            senml_json = self.create_senml_message(reading)

            # Pubblica su MQTT
            result = self.client.publish(
                self.publish_topic,
                senml_json,
                qos=Config.QOS_SENSOR_DATA,
                retain=False
            )

            # Log della lettura
            status_emoji = self._get_status_emoji(reading.glucose_status)
            trend_emoji = self._get_trend_emoji(reading.trend_direction)

            print(f"\n📊 Lettura #{self.reading_count} (SenML)")
            print(f"🩸 Glicemia: {reading.glucose_value:.1f} mg/dL {status_emoji}")
            print(f"📈 Status: {reading.glucose_status}")
            print(f"{trend_emoji} Trend: {reading.trend_direction} ({reading.trend_rate:.1f} mg/dL/min)")
            print(f"🔋 Batteria: {reading.battery_level:.1f}%")
            print(f"📡 Segnale: {reading.signal_strength} dBm")

            if reading.is_critical():
                print(f"🚨 ATTENZIONE: Valore critico rilevato!")

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"✅ Dati SenML pubblicati con successo")
                # Mostra preview del messaggio SenML (primi 150 caratteri)
                preview = senml_json[:150] + "..." if len(senml_json) > 150 else senml_json
                print(f"📋 SenML: {preview}")
            else:
                print(f"⚠️ Errore pubblicazione (rc: {result.rc})")

        except Exception as e:
            print(f"❌ Errore nella pubblicazione: {e}")

    def _get_status_emoji(self, status):
        """Restituisce emoji per lo status glicemico"""
        emoji_map = {
            "critical_low": "🔴🔻",
            "low": "🟡⬇️",
            "normal": "🟢✅",
            "high": "🟡⬆️",
            "critical_high": "🔴🔺"
        }
        return emoji_map.get(status, "⚪")

    def _get_trend_emoji(self, trend):
        """Restituisce emoji per il trend"""
        emoji_map = {
            "rising": "📈",
            "falling": "📉",
            "stable": "➡️"
        }
        return emoji_map.get(trend, "❓")

    def change_simulation_mode(self, new_mode):
        """Cambia la modalità di simulazione"""
        valid_modes = ["normal", "hypoglycemia", "hyperglycemia", "fluctuating"]
        if new_mode in valid_modes:
            self.simulation_mode = new_mode
            print(f"\n🎭 Modalità cambiata in: {new_mode}")
        else:
            print(f"⚠️ Modalità non valida. Opzioni: {', '.join(valid_modes)}")

    def run_continuous(self):
        """Esegue letture continue ad intervalli regolari"""
        try:
            print("\n" + "=" * 60)
            print("🚀 AVVIO SENSORE GLICEMIA (SenML)")
            print("=" * 60)
            print(f"🆔 Sensore ID: {self.sensor_id}")
            print(f"👤 Paziente ID: {self.patient_id}")
            print(f"🩸 Glicemia iniziale: {self.sensor.glucose_value:.1f} mg/dL")
            print(f"📡 Broker: {self.broker_address}:{self.broker_port}")
            print(f"📋 Formato: SenML (RFC 8428)")
            print("=" * 60 + "\n")

            # Connetti al broker
            self.client.connect(self.broker_address, self.broker_port, 60)
            self.client.loop_start()

            # Loop principale con letture periodiche
            while True:
                self.publish_reading()
                time.sleep(self.reading_interval)

        except KeyboardInterrupt:
            print("\n\n⏹️  Sensore fermato dall'utente")
            self.stop()
        except Exception as e:
            print(f"\n❌ Errore critico: {e}")
            self.stop()

    def run_n_readings(self, n):
        """Esegue un numero specifico di letture"""
        try:
            print("\n" + "=" * 60)
            print(f"🚀 AVVIO SENSORE GLICEMIA SenML ({n} letture)")
            print("=" * 60)
            print(f"🆔 Sensore ID: {self.sensor_id}")
            print(f"👤 Paziente ID: {self.patient_id}")
            print(f"🩸 Glicemia iniziale: {self.sensor.glucose_value:.1f} mg/dL")
            print("=" * 60 + "\n")

            # Connetti al broker
            self.client.connect(self.broker_address, self.broker_port, 60)
            self.client.loop_start()

            # Esegui n letture
            for i in range(n):
                self.publish_reading()
                if i < n - 1:
                    time.sleep(self.reading_interval)

            print(f"\n✅ Completate {n} letture")
            time.sleep(2)
            self.stop()

        except KeyboardInterrupt:
            print("\n⏹️  Sensore fermato dall'utente")
            self.stop()
        except Exception as e:
            print(f"❌ Errore critico: {e}")
            self.stop()

    def stop(self):
        """Ferma il sensore"""
        print("\n🛑 Chiusura sensore glicemia...")
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