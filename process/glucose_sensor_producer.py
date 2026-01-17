import paho.mqtt.client as mqtt
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.glucose_sensor_data import GlucoseSensorData
from model.glucose_simulation_logic import GlucoseSimulationLogic
from model.patient_descriptor import PatientDescriptor
from conf.SystemConfiguration import SystemConfig as Config
from utils.senml_helper import SenMLHelper

class GlucoseSensorProducerSenML:
    def __init__(self, sensor_id, patient_id, initial_glucose=None, simulation_mode="normal"):
        self.sensor_id = sensor_id
        self.patient_id = patient_id
        start_val = initial_glucose if initial_glucose is not None else Config.SIM_SENSOR_START_VALUE
        self.sensor = GlucoseSensorData(sensor_id, patient_id, glucose_value=start_val)

        # Configurazione MQTT
        self.broker_address = Config.BROKER_ADDRESS
        self.broker_port = Config.BROKER_PORT
        self.client = mqtt.Client(f"glucose_sensor_senml_{sensor_id}")

        # Topic MQTT
        self.base_topic = f"/iot/patient/{patient_id}"
        self.publish_topic = f"{self.base_topic}/glucose/sensor/data"
        self.command_topic = f"{self.base_topic}/insulin/pump/command"
        self.control_topic = f"{self.base_topic}/glucose/sensor/set_mode"

        # Letture
        self.reading_interval = Config.GLUCOSE_READING_INTERVAL
        self.simulation_mode = simulation_mode
        self.reading_count = 0

        # Parametri per l'effetto insulina
        self.active_insulin_doses = []
        self.insulin_sensitivity_factor = Config.INSULIN_CORRECTION_FACTOR

        # Callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✅ Sensore glicemia connesso")
            print(f"Topic pubblicazione: {self.publish_topic}")
            print(f"Modalità: {self.simulation_mode}")
            client.subscribe(self.command_topic, qos=Config.QOS_COMMANDS)
            client.subscribe(self.control_topic)
        else:
            print(f"❌ Connessione fallita: rc={rc}")

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"⚠️ Disconnessione inattesa (rc={rc})")

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()

            if msg.topic == self.control_topic:
                self.change_simulation_mode(payload)

            if "insulin/pump/command" in msg.topic:
                parsed = SenMLHelper.parse_senml(payload)
                data = parsed.get("measurements", {})
                dose = data.get("dose", {}).get("value", 0.0)
                d_type = data.get("type", {}).get("value", "bolus")

                if dose > 0 and d_type in ["bolus", "correction"]:
                    self.active_insulin_doses.append({'amount': dose, 'start_time': time.time()})
                    print(f"💉 Sensore: Rilevata insulina {dose:.2f}U")

        except Exception as e:
            print(f"❌ Errore comando sensore: {e}")

    def simulate_glucose_reading(self):
        # Variazione naturale
        natural_variation = GlucoseSimulationLogic.generate_variation(
            current_value=self.sensor.glucose_value,
            simulation_mode=self.simulation_mode
        )
        # Effetto insulina
        insulin_effect = GlucoseSimulationLogic.calculate_insulin_effect(
            active_insulin_doses=self.active_insulin_doses,
            isf=self.insulin_sensitivity_factor,
            current_time=time.time(),
            reading_interval=self.reading_interval
        )
        total_variation = natural_variation + insulin_effect
        if insulin_effect < -0.1: # Log per debug
            print(f"   [DBG] Var. Naturale: {natural_variation:.1f}, Effetto Insulina: {insulin_effect:.1f}")
        self.sensor.apply_variation(total_variation, self.reading_interval)
        return self.sensor

    def publish_reading(self):
        try:
            self.reading_count += 1
            reading = self.simulate_glucose_reading()
            senml_json = reading.to_senml()
            self.client.publish(self.publish_topic, senml_json, qos=Config.QOS_SENSOR_DATA)

            # Log compatto
            print(f"Lettura #{self.reading_count} | {reading.glucose_value:.1f} mg/dL | {reading.trend_direction}({reading.trend_rate:.1f} mg/dL/min) | {reading.battery_level:.1f}% |📡:{reading.signal_strength} dBm")
            if reading.is_critical():
                print("🚨 Valore critico!")

        except Exception as e:
            print(f"❌ Errore pubblicazione: {e}")

    def change_simulation_mode(self, new_mode):
        valid = ["normal", "hypoglycemia", "hyperglycemia", "fluctuating"]
        if new_mode in valid:
            self.simulation_mode = new_mode
            print(f"🎭 Modalità: {new_mode}")

    def run_continuous(self):
        try:
            print("🚀 AVVIO SENSORE GLICEMIA")
            self.client.connect(self.broker_address, self.broker_port, Config.MQTT_KEEPALIVE_S)
            self.client.loop_start()

            while True:
                self.publish_reading()
                time.sleep(self.reading_interval)

        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()


if __name__ == "__main__":
    CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'conf',
                                    'patient_config.json')

    initial_glucose = Config.SIM_SENSOR_START_VALUE
    simulation_mode = "normal"
    sensor_id = "sensor_001"

    try:
        patient = PatientDescriptor.from_json_file(CONFIG_FILE_PATH)
        sensor = GlucoseSensorProducerSenML(sensor_id, patient.patient_id, initial_glucose, simulation_mode)
        sensor.run_continuous()
    except Exception as e:
        print(f"❌ Errore avvio: {e}")