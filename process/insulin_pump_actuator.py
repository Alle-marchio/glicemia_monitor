import paho.mqtt.client as mqtt
import json
import time
import sys
import os
import random
import threading

# Import dei modelli
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.insulin_pump_data import InsulinPumpCommand, InsulinPumpStatus
from model.patient_descriptor import PatientDescriptor
from conf.SystemConfiguration import SystemConfig as Config
from utils.senml_helper import SenMLHelper


class InsulinPumpActuatorSenML:
    """
    Pompa insulina simulata con supporto SenML
    """

    def __init__(self, pump_id, patient_id, initial_insulin=None, initial_battery=None):
        self.pump_id = pump_id
        self.patient_id = patient_id

        # Inizializza lo status della pompa (usa i default di Config se None)
        self.status = InsulinPumpStatus(
            pump_id,
            patient_id,
            initial_reservoir=initial_insulin,
            initial_battery=initial_battery
        )

        # Configurazione MQTT
        self.broker_address = Config.BROKER_ADDRESS
        self.broker_port = Config.BROKER_PORT
        self.client = mqtt.Client(f"insulin_pump_senml_{pump_id}")

        # Topic MQTT
        self.base_topic = f"/iot/patient/{patient_id}"
        self.command_topic = f"{self.base_topic}/insulin/pump/command"
        self.status_topic = f"{self.base_topic}/insulin/pump/status"
        self.alert_topic = f"{self.base_topic}/notifications/alert"

        # Intervallo pubblicazione status
        self.status_interval = Config.PUMP_STATUS_INTERVAL

        # Parametri di sicurezza
        self.max_single_bolus = Config.SAFETY_MAX_BOLUS_U
        self.max_basal_rate = Config.SAFETY_MAX_BASAL_RATE_UH

        # Log comandi ricevuti
        self.command_history = []

        # Thread per pubblicazione status periodico
        self.status_thread = None
        self.running = False

        # Configurazione callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, rc):
        """Callback quando la pompa si connette al broker"""
        if rc == 0:
            print(f"✅ Pompa insulina (SenML) connessa al broker MQTT")
            print(f"📥 Subscribing a: {self.command_topic}")
            print(f"📤 Pubblicazione status su: {self.status_topic}")

            client.subscribe(self.command_topic, qos=Config.QOS_COMMANDS)
            self.publish_status()
            print("🎯 Pompa pronta per ricevere comandi SenML...")
        else:
            print(f"❌ Connessione fallita con codice: {rc}")

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(f"⚠️ Disconnessione imprevista dal broker (rc: {rc})")

    def on_message(self, client, userdata, msg):
        try:
            if "insulin/pump/command" in msg.topic:
                self.process_senml_command(msg.payload.decode())
        except Exception as e:
            print(f"❌ Errore nell'elaborazione del messaggio: {e}")

    def parse_senml_command(self, senml_json):
        try:
            parsed = SenMLHelper.parse_senml(senml_json)
            measurements = parsed.get('measurements', {})

            return {
                'insulin_amount': measurements.get('dose', {}).get('value', 0.0),
                'delivery_mode': measurements.get('type', {}).get('value', 'bolus'),
                'command_id': measurements.get('command_id', {}).get('value', 'unknown'),
                'priority': measurements.get('priority', {}).get('value', 'normal'),
                'reason': measurements.get('reason', {}).get('value', 'N/A'),
                'timestamp': parsed.get('base_time', time.time())
            }
        except Exception as e:
            print(f"❌ Errore nel parsing comando SenML: {e}")
            return None

    def process_senml_command(self, senml_payload):
        print("\n" + "=" * 60)
        print("📬 NUOVO COMANDO SENML RICEVUTO")
        print("=" * 60)

        try:
            command_data = self.parse_senml_command(senml_payload)
            if command_data is None:
                return False

            command_id = command_data['command_id']
            delivery_mode = command_data['delivery_mode']
            insulin_amount = command_data['insulin_amount']

            print(f"🆔 Command ID: {command_id}")
            print(f"💉 Modalità: {delivery_mode}")
            print(f"📊 Quantità: {insulin_amount:.2f} unità")

            # Controlli (Stato, Insulina, Sicurezza)
            if self.status.pump_status != "active":
                self.send_senml_alert("ERROR", f"Comando {command_id} rifiutato: pompa non attiva", "high")
                return False

            if self.status.insulin_reservoir_level < insulin_amount:
                self.send_senml_alert("ERROR", f"Insulina insufficiente per comando {command_id}", "critical")
                return False

            if delivery_mode in ["bolus", "correction"]:
                if insulin_amount > self.max_single_bolus:
                    self.send_senml_alert("ERROR", f"Dose {insulin_amount:.2f}U supera limite sicurezza", "critical")
                    return False

            self.send_senml_alert("PUMP_ACK",
                                  f"Ricevuto cmd {command_id}. Erogazione {insulin_amount:.2f}U ({delivery_mode})",
                                  "low")

            # ESEGUI
            success = self.execute_delivery(delivery_mode, insulin_amount)

            if success:
                print(f"✅ Comando eseguito con successo!")
                self.command_history.append({
                    'timestamp': time.time(),
                    'command_id': command_id,
                    'delivery_mode': delivery_mode,
                    'amount': insulin_amount
                })
                self.publish_status()
                self.send_senml_alert("INFO", f"Erogazione completata: {insulin_amount:.2f}U ({delivery_mode})", "low")

            print("=" * 60 + "\n")
            return success

        except Exception as e:
            print(f"❌ Errore nel processamento comando: {e}")
            return False

    def execute_delivery(self, delivery_mode, amount):
        """Simula l'erogazione di insulina con tempi realistici (da Config)"""
        try:
            print(f"\n💉 Inizio erogazione...")

            # Calcola tempo erogazione
            delivery_time = amount * Config.SIM_PUMP_DELIVERY_SEC_PER_UNIT
            print(f"⏱️  Tempo stimato: {delivery_time:.1f}s")

            # Simula attesa (bloccante ma limitata per non freezare il thread troppo a lungo)
            wait_time = min(delivery_time, Config.SIM_PUMP_DELIVERY_MAX_WAIT_S)
            time.sleep(wait_time)

            if delivery_mode in ["bolus", "correction"]:
                return self.status.deliver_bolus(amount, delivery_mode)

            elif delivery_mode == "basal":
                if amount <= self.max_basal_rate:
                    self.status.current_basal_rate = amount
                    return True
                return False

            elif delivery_mode == "emergency_stop":
                self.status.current_basal_rate = 0.0
                return True

            return False

        except Exception as e:
            print(f"❌ Errore durante erogazione: {e}")
            return False

    def create_senml_status(self):
        # Utilizza il metodo to_senml dello status che è già pulito
        return self.status.to_senml()

    def publish_status(self):
        try:
            self.status.update_status()
            status_senml = self.create_senml_status()

            self.client.publish(
                self.status_topic,
                status_senml,
                qos=Config.QOS_SENSOR_DATA,
                retain=Config.RETAIN_PUMP_STATUS
            )

            # Gestione allarmi critici
            if self.status.has_critical_alarms():
                for alarm in self.status.active_alarms:
                    self.send_senml_alert("PUMP_ALARM", f"🚨 ALLARME CRITICO: {alarm}", "critical")

            return True
        except Exception as e:
            print(f"❌ Errore pubblicazione status: {e}")
            return False

    def send_senml_alert(self, alert_type, message, severity="medium"):
        try:
            alert_senml = SenMLHelper.create_notification_alert(
                patient_id=self.patient_id,
                alert_type=alert_type,
                message=message,
                severity=severity
            )
            self.client.publish(self.alert_topic, alert_senml, qos=Config.QOS_NOTIFICATIONS)
        except Exception:
            pass

    def status_publisher_loop(self):
        while self.running:
            self.publish_status()
            time.sleep(self.status_interval)

    def start(self):
        try:
            print(f"🚀 AVVIO POMPA (ID: {self.pump_id})")
            self.client.connect(self.broker_address, self.broker_port, Config.MQTT_KEEPALIVE_S)
            self.client.loop_start()

            self.running = True
            self.status_thread = threading.Thread(target=self.status_publisher_loop)
            self.status_thread.daemon = True
            self.status_thread.start()

            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.running = False
        self.client.loop_stop()
        self.client.disconnect()


if __name__ == "__main__":
    CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'conf',
                                    'patient_config.json')

    pump_id = 'pump_001'
    initial_insulin = Config.PUMP_DEFAULT_CAPACITY
    initial_battery = Config.PUMP_DEFAULT_BATTERY

    try:
        patient = PatientDescriptor.from_json_file(CONFIG_FILE_PATH)
        pump = InsulinPumpActuatorSenML(pump_id, patient.patient_id, initial_insulin, initial_battery)
        pump.start()
    except Exception as e:
        print(f"❌ Errore avvio: {e}")