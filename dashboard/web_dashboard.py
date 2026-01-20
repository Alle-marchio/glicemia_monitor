import paho.mqtt.client as mqtt
from flask import Flask, render_template, jsonify
import threading
import sys
import os
import json
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conf.SystemConfiguration import SystemConfig as Config
from utils.senml_helper import SenMLHelper
from model.patient_descriptor import PatientDescriptor

data_lock = threading.Lock()
current_data = {
    'glucose_value': 'N/A',
    'glucose_status': 'N/A',
    'pump_status': 'N/A',
    'insulin_reservoir': 'N/A',
    'battery_level': 'N/A',
    'alarms_count': 0
}
glucose_history = []
alert_log = []
app = Flask(__name__)
PATIENT_ID = "patient_001"
PATIENT_NAME = "Paziente"

def load_patient_config():
    global PATIENT_ID, PATIENT_NAME
    config_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'conf','patient_config.json')
    try:
        patient = PatientDescriptor.from_json_file(config_file_path)
        PATIENT_ID = patient.patient_id
        PATIENT_NAME = patient.name
        return patient
    except Exception as e:
        print(f"❌ Errore di caricamento configurazione paziente: {e}")
        return None

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Dashboard MQTT client connesso.")
        base_topic = f"/iot/patient/{PATIENT_ID}"
        topics = [
            (f"{base_topic}/glucose/sensor/data", Config.QOS_SENSOR_DATA),
            (f"{base_topic}/insulin/pump/status", Config.QOS_SENSOR_DATA),
            (f"{base_topic}/notifications/alert", Config.QOS_NOTIFICATIONS)
        ]
        client.subscribe(topics)
        print(f"📥 Subscribed a 3 topic chiave per il paziente {PATIENT_NAME} (ID: {PATIENT_ID}).")
    else:
        print(f"❌ Dashboard MQTT client connessione fallita: {rc}")


def on_message(client, userdata, msg):
    """Gestisce e aggiorna i dati in base al topic ricevuto."""
    try:
        payload = msg.payload.decode()
        parsed = SenMLHelper.parse_senml(payload)
        measurements = parsed.get("measurements", {})
        timestamp = time.strftime('%H:%M:%S', time.localtime(parsed.get("base_time")))

        with data_lock:
            # Dati Sensore Glicemia
            if "glucose/sensor/data" in msg.topic:
                glucose = measurements.get("level", {}).get("value")
                status = measurements.get("status", {}).get("value")
                trend = measurements.get("trend", {}).get("value")
                trend_rate = measurements.get("trend_rate", {}).get("value", 0.0)
                battery = measurements.get("battery", {}).get("value")

                # Aggiornamento dati correnti
                current_data['glucose_value'] = round(glucose, 1)
                current_data['glucose_status'] = status
                current_data['sensor_battery'] = round(battery, 1)
                current_data['glucose_trend'] = trend.capitalize()
                current_data['trend_rate'] = round(trend_rate, 1)

                # Aggiungi alla cronologia per il grafico
                glucose_history.append({'time': timestamp, 'value': round(glucose, 1)})
                if len(glucose_history) > Config.DASHBOARD_HISTORY_LIMIT:
                    glucose_history.pop(0)

            # Dati Status Pompa
            elif "insulin/pump/status" in msg.topic:
                current_data['pump_status'] = measurements.get("status", {}).get("value")
                current_data['insulin_reservoir'] = round(measurements.get("reservoir", {}).get("value", 0), 1)
                current_data['battery_level'] = round(measurements.get("battery", {}).get("value", 0), 1)
                current_data['alarms_count'] = measurements.get("alarms_count", {}).get("value", 0)

            # Alert/Notifiche
            elif "notifications/alert" in msg.topic:
                alert_log.append({
                    'time': timestamp,
                    'type': measurements.get("type", {}).get("value"),
                    'message': measurements.get("message", {}).get("value"),
                    'severity': measurements.get("severity", {}).get("value")
                })
                if len(alert_log) > Config.DASHBOARD_ALERT_LIMIT:
                    alert_log.pop(0)

    except Exception as e:
        print(f"❌ Errore nel processare messaggio MQTT: {e}")


def mqtt_client_loop():
    client = mqtt.Client(f"web_dashboard_client_{PATIENT_ID}")
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(Config.BROKER_ADDRESS, Config.BROKER_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"❌ Connessione MQTT fallita: {e}")

# --- FLASK ROUTES ---
@app.route('/')
def index():
    return render_template('dashboard.html', patient_name=PATIENT_NAME)

@app.route('/data')
def get_data():
    """Endpoint AJAX per fornire i dati aggiornati al frontend."""
    with data_lock:
        response_data = {
            'current': current_data.copy(),
            'history': glucose_history.copy(),
            'alerts': list(reversed(alert_log)).copy()
        }
    return jsonify(response_data)

@app.route('/patient_config')
def get_patient_config():
    """Endpoint per fornire la configurazione del paziente."""
    try:
        config_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'conf',
            'patient_config.json'
        )
        with open(config_file_path, 'r') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/simulate/<mode>')
def simulate_condition(mode):
    """Invia un comando MQTT al sensore per cambiare modalità di simulazione."""
    valid_modes = ["normal", "hypoglycemia", "hyperglycemia", "fluctuating"]
    if mode in valid_modes:
        command_topic = f"/iot/patient/{PATIENT_ID}/glucose/sensor/set_mode"

        temp_client = mqtt.Client(f"web_cmd_{PATIENT_ID}")
        temp_client.connect(Config.BROKER_ADDRESS, Config.BROKER_PORT)
        temp_client.publish(command_topic, mode)
        temp_client.disconnect()

        return jsonify({"status": "success", "mode": mode})
    return jsonify({"status": "error", "message": "Invalid mode"}), 400

if __name__ == '__main__':
    patient_config = load_patient_config()
    if patient_config is None:
        sys.exit(1)

    print(f"Avvio Dashboard Web per Paziente: {PATIENT_NAME} (ID: {PATIENT_ID})")

    mqtt_thread = threading.Thread(target=mqtt_client_loop)
    mqtt_thread.daemon = True
    mqtt_thread.start()

    app.run(debug=False, host='0.0.0.0', port=5000)