import paho.mqtt.client as mqtt
import sys
import os
import time

# Import dei modelli e helper
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conf.SystemConfiguration import SystemConfig as Config
from utils.senml_helper import SenMLHelper
from model.patient_descriptor import PatientDescriptor


class NotificationManager:
    """
    Componente che si occupa solo di ricevere e loggare gli alert/notifiche
    inviate dal Data Collector o dalla Pompa.
    """

    def __init__(self, patient_id):
        self.patient_id = patient_id
        self.broker_address = Config.BROKER_ADDRESS
        self.broker_port = Config.BROKER_PORT
        self.client = mqtt.Client(f"notification_manager_{patient_id}")

        # Topic alert
        self.base_topic = f"/iot/patient/{patient_id}"
        self.alert_topic = f"{self.base_topic}/notifications/alert"

        # Configurazione callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.severity_emoji = {"low": "ℹ️", "medium": "⚠️", "high": "🔶", "critical": "🚨", "emergency": "🛑"}

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✅ Notification Manager connesso al broker MQTT")
            print(f"📥 Subscribing a topic alert: {self.alert_topic}")
            client.subscribe(self.alert_topic, qos=Config.QOS_NOTIFICATIONS)
        else:
            print(f"❌ Connessione fallita con codice: {rc}")

    def on_message(self, client, userdata, msg):
        """Callback quando arriva un alert SenML"""
        try:
            payload = msg.payload.decode()

            # Parse del messaggio SenML
            parsed = SenMLHelper.parse_senml(payload)
            measurements = parsed.get("measurements", {})

            alert_type = measurements.get("type", {}).get("value", "UNKNOWN")
            message = measurements.get("message", {}).get("value", "N/A")
            severity = measurements.get("severity", {}).get("value", "medium")
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(parsed.get("base_time")))

            emoji = self.severity_emoji.get(severity, "📢")

            print("\n" + "=" * 50)
            print(f"{emoji} {timestamp} | NUOVA NOTIFICA RICEVUTA")
            print(f"Tipo: {alert_type} | Gravità: {severity.upper()}")
            print(f"Messaggio: {message}")
            print("=" * 50)

        except Exception as e:
            print(f"❌ Errore nell'elaborazione alert SenML: {e}")

    def start(self):
        """Avvia il Notification Manager"""
        try:
            print("\n" + "=" * 60)
            print(f"🚀 AVVIO NOTIFICATION MANAGER (Paziente: {self.patient_id})")
            print("=" * 60)
            self.client.connect(self.broker_address, self.broker_port, 60)
            self.client.loop_forever()

        except KeyboardInterrupt:
            print("\n⏹️  Notification Manager fermato dall'utente")
        except Exception as e:
            print(f"❌ Errore critico: {e}")


if __name__ == "__main__":
    # Logica di caricamento configurazione paziente (come negli altri processi)
    CONFIG_FILE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'conf',
        'patient_config.json'
    )

    try:
        patient = PatientDescriptor.from_json_file(CONFIG_FILE_PATH)
        patient_id = patient.patient_id
    except Exception as e:
        print(f"❌ Errore di caricamento configurazione: {e}")
        sys.exit(1)

    manager = NotificationManager(patient_id)
    manager.start()