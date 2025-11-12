import paho.mqtt.client as mqtt
import json
import time
import sys
import os

# Import dei modelli e helper
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.glucose_sensor_data import GlucoseSensorData
from model.patient_descriptor import PatientDescriptor
from model.insulin_pump_data import InsulinPumpCommand, InsulinPumpStatus
from conf.mqtt_conf_params import MqttConfigurationParameters as Config
from utils.senml_helper import SenMLHelper  # ✅ Nuovo import


class DataCollectorConsumer:
    """
    Data Collector principale che:
    - Riceve dati dal sensore glicemia in formato SenML
    - Analizza i valori e calcola azioni necessarie
    - Invia comandi alla pompa insulina (SenML)
    - Genera notifiche in formato SenML
    """

    def __init__(self, patient_id, patient_descriptor):
        self.patient_id = patient_id
        self.patient = patient_descriptor

        # Configurazione MQTT
        self.broker_address = Config.BROKER_ADDRESS
        self.broker_port = Config.BROKER_PORT
        self.client = mqtt.Client(f"data_collector_{patient_id}")

        # Topic MQTT
        self.base_topic = f"/iot/patient/{patient_id}"
        self.glucose_data_topic = f"{self.base_topic}/glucose/sensor/data"
        self.pump_command_topic = f"{self.base_topic}/insulin/pump/command"
        self.pump_status_topic = f"{self.base_topic}/insulin/pump/status"
        self.alert_topic = f"{self.base_topic}/notifications/alert"

        # Stato interno
        self.last_glucose_reading = None
        self.last_pump_status = None
        self.alert_history = []
        self.insulin_commands_sent = []

        # Configurazione callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Safety limits
        self.max_bolus_dose = 15.0  # Unità massime per singolo bolo
        self.min_time_between_corrections = 180  # 3 ore in secondi
        self.last_correction_time = 0

    def on_connect(self, client, userdata, flags, rc):
        """Callback quando il client si connette al broker"""
        if rc == 0:
            print(f"✅ Data Collector connesso al broker MQTT")
            print(f"📡 Subscribing a topic glicemia: {self.glucose_data_topic}")
            print(f"📡 Subscribing a topic status pompa: {self.pump_status_topic}")

            client.subscribe(self.glucose_data_topic, qos=Config.QOS_SENSOR_DATA)
            client.subscribe(self.pump_status_topic, qos=Config.QOS_SENSOR_DATA)

            print("🎯 Data Collector pronto per ricevere dati...")
        else:
            print(f"❌ Connessione fallita con codice: {rc}")

    def on_message(self, client, userdata, msg):
        """Callback quando arriva un messaggio MQTT"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()

            # ✅ Parse del payload in formato SenML
            parsed = SenMLHelper.parse_senml(payload)
            measurements = parsed.get("measurements", {})

            # Gestione messaggi dal sensore glicemia
            if "glucose/sensor/data" in topic:
                self.process_glucose_data(measurements)

            # Gestione status pompa insulina
            elif "insulin/pump/status" in topic:
                self.process_pump_status(measurements)

        except Exception as e:
            print(f"❌ Errore nell'elaborazione del messaggio: {e}")

    def process_glucose_data(self, data):
        """Elabora i dati SenML del sensore glicemia"""
        print("\n" + "=" * 60)
        print("📊 NUOVO DATO GLICEMIA RICEVUTO (SenML)")
        print("=" * 60)

        glucose_value = data.get("level", {}).get("value")
        trend_direction = data.get("trend", {}).get("value", "stable")
        glucose_status = self._determine_status(glucose_value)

        print(f"🩸 Glicemia: {glucose_value:.1f} mg/dL")
        print(f"📈 Status: {glucose_status}")
        print(f"📉 Trend: {trend_direction}")

        self.last_glucose_reading = data

        # ANALISI E DECISIONE
        action_needed = False
        insulin_dose = 0.0
        alert_level = "NORMAL"
        alert_message = ""

        # 1️⃣ IPOGLICEMIA
        if self.patient.is_hypoglycemic(glucose_value):
            if glucose_value < 50:
                alert_level = "EMERGENCY_LOW"
                alert_message = f"⚠️ IPOGLICEMIA CRITICA: {glucose_value:.1f} mg/dL - Somministrare glucosio immediatamente!"
            else:
                alert_level = "WARNING_LOW"
                alert_message = f"⚠️ IPOGLICEMIA: {glucose_value:.1f} mg/dL - Assumere 15g di carboidrati"

            print(f"\n🚨 {alert_message}")
            self.send_notification(alert_level, alert_message)
            action_needed = False

        # 2️⃣ IPERGLICEMIA
        elif self.patient.is_hyperglycemic(glucose_value):
            target_glucose = (self.patient.target_glucose_min + self.patient.target_glucose_max) / 2
            insulin_dose = self.patient.calculate_insulin_dose(glucose_value, target_glucose)
            time_since_last_correction = time.time() - self.last_correction_time

            if insulin_dose > 0 and time_since_last_correction > self.min_time_between_corrections:
                insulin_dose = min(insulin_dose, self.max_bolus_dose)
                action_needed = True

                if glucose_value > 250:
                    alert_level = "EMERGENCY_HIGH"
                    alert_message = f"🚨 IPERGLICEMIA CRITICA: {glucose_value:.1f} mg/dL - Somministrazione {insulin_dose:.2f}U insulina"
                else:
                    alert_level = "WARNING_HIGH"
                    alert_message = f"⚠️ IPERGLICEMIA: {glucose_value:.1f} mg/dL - Correzione con {insulin_dose:.2f}U insulina"

                print(f"\n💉 Dose insulina calcolata: {insulin_dose:.2f} unità")
                print(f"🎯 Target glicemico: {target_glucose:.1f} mg/dL")

                self.send_notification(alert_level, alert_message)

            elif insulin_dose > 0:
                remaining = self.min_time_between_corrections - time_since_last_correction
                print(f"⏳ Attesa tra correzioni: {remaining:.0f}s rimanenti")
                self.send_notification("INFO", "⏳ Iperglicemia rilevata ma in attesa prima di nuova correzione")

        # 3️⃣ VALORI NORMALI
        else:
            print(f"✅ Glicemia nel range target ({self.patient.target_glucose_min}-{self.patient.target_glucose_max} mg/dL)")

        # ✅ Invia comando alla pompa in SenML se necessario
        if action_needed and insulin_dose > 0:
            self.send_insulin_command(insulin_dose, "correction")
            self.last_correction_time = time.time()

        print("=" * 60 + "\n")

    def _determine_status(self, value):
        """Determina lo stato glicemico testuale"""
        if value < self.patient.hypoglycemia_threshold:
            return "LOW"
        elif value > self.patient.hyperglycemia_threshold:
            return "HIGH"
        return "NORMAL"

    def process_pump_status(self, data):
        """Elabora lo status pompa da messaggio SenML"""
        self.last_pump_status = data
        pump_status = data.get("status", {}).get("value", "active")
        insulin_level = data.get("reservoir", {}).get("value", 0)
        battery_level = data.get("battery", {}).get("value", 0)

        print(f"🔧 Stato pompa: {pump_status}, insulina {insulin_level}U, batteria {battery_level}%")

        if insulin_level < 30:
            self.send_notification("WARNING", f"⚠️ Insulina quasi terminata ({insulin_level:.1f}U)")
        if battery_level < 20:
            self.send_notification("WARNING", f"🔋 Batteria pompa bassa ({battery_level:.0f}%)")
        if insulin_level <= 0:
            self.send_notification("EMERGENCY", "🚨 POMPA INSULINA VUOTA - Ricaricare immediatamente!")

    def send_insulin_command(self, insulin_amount, delivery_mode, reason=""):
        """Invia comando alla pompa in formato SenML"""
        try:
            # ✅ Usa SenMLHelper per creare il comando
            command_senml = SenMLHelper.create_insulin_command(
                patient_id=self.patient_id,
                units=round(insulin_amount, 2),
                command_type=delivery_mode
            )

            self.client.publish(
                self.pump_command_topic,
                command_senml,
                qos=Config.QOS_COMMANDS,
                retain=False
            )

            print(f"💉 Comando insulina inviato: {insulin_amount:.2f}U ({delivery_mode})")
            print(f"📤 Topic: {self.pump_command_topic}")

            self.insulin_commands_sent.append({
                'timestamp': time.time(),
                'amount': insulin_amount,
                'reason': reason
            })

        except Exception as e:
            print(f"❌ Errore invio comando insulina: {e}")

    def send_notification(self, alert_level, message):
        """Invia notifica al topic alerts in SenML"""
        try:
            alert_senml = SenMLHelper.create_notification_alert(
                patient_id=self.patient_id,
                alert_type=alert_level,
                message=message,
                severity=alert_level.lower()
            )

            self.client.publish(
                self.alert_topic,
                alert_senml,
                qos=Config.QOS_NOTIFICATIONS,
                retain=False
            )

            print(f"🔔 Notifica SenML inviata: {alert_level}")

            self.alert_history.append({
                'timestamp': time.time(),
                'level': alert_level,
                'message': message
            })
            if len(self.alert_history) > 10:
                self.alert_history = self.alert_history[-10:]

        except Exception as e:
            print(f"❌ Errore invio notifica: {e}")

    def start(self):
        """Avvia il Data Collector"""
        try:
            print("\n" + "=" * 60)
            print("🚀 AVVIO DATA COLLECTOR")
            print("=" * 60)
            print(f"👤 Paziente: {self.patient.name} (ID: {self.patient_id})")
            print(f"🎯 Range target: {self.patient.target_glucose_min}-{self.patient.target_glucose_max} mg/dL")
            print(f"💉 Fattore sensibilità: {self.patient.insulin_sensitivity_factor} mg/dL per unità")
            print(f"📡 Broker: {self.broker_address}:{self.broker_port}")
            print("=" * 60 + "\n")

            self.client.connect(self.broker_address, self.broker_port, 60)
            self.client.loop_forever()

        except KeyboardInterrupt:
            print("\n⏹️  Data Collector fermato dall'utente")
            self.stop()
        except Exception as e:
            print(f"❌ Errore critico: {e}")
            self.stop()

    def stop(self):
        """Ferma il Data Collector"""
        print("\n🛑 Chiusura Data Collector...")
        self.client.disconnect()
        print("✅ Data Collector disconnesso")


# MAIN - Esempio di utilizzo
if __name__ == "__main__":
    patient = PatientDescriptor(
        patient_id="patient_001",
        name="Mario Rossi",
        age=45,
        weight=75,
        target_glucose_min=70.0,
        target_glucose_max=140.0,
        hypoglycemia_threshold=60.0,
        hyperglycemia_threshold=200.0,
        insulin_sensitivity_factor=50.0,
        carb_ratio=12.0,
        basal_insulin_rate=1.0,
        sensor_reading_interval=5,
        alert_enabled=True,
        emergency_contact="+39 123 456 7890"
    )

    collector = DataCollectorConsumer("patient_001", patient)
    collector.start()
