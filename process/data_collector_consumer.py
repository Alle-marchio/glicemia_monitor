import paho.mqtt.client as mqtt
import json
import time
import sys
import os

# Import dei modelli
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.glucose_sensor_data import GlucoseSensorData
from model.patient_descriptor import PatientDescriptor
from model.insulin_pump_data import InsulinPumpCommand, InsulinPumpStatus
from conf.mqtt_conf_params import MqttConfigurationParameters as Config


class DataCollectorConsumer:
    """
    Data Collector principale che:
    - Riceve dati dal sensore glicemia
    - Analizza i valori e calcola azioni necessarie
    - Invia comandi alla pompa insulina
    - Genera notifiche per paziente/medico
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

            # Subscribe ai topic necessari
            client.subscribe(self.glucose_data_topic, qos=Config.QOS_SENSOR_DATA)
            client.subscribe(self.pump_status_topic, qos=Config.QOS_SENSOR_DATA)

            print("🎯 Data Collector pronto per ricevere dati...")
        else:
            print(f"❌ Connessione fallita con codice: {rc}")

    def on_message(self, client, userdata, msg):
        """Callback quando arriva un messaggio MQTT"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            # Gestione messaggi dal sensore glicemia
            if "glucose/sensor/data" in topic:
                self.process_glucose_data(payload)

            # Gestione status pompa insulina
            elif "insulin/pump/status" in topic:
                self.process_pump_status(payload)

        except Exception as e:
            print(f"❌ Errore nell'elaborazione del messaggio: {e}")

    def process_glucose_data(self, data):
        """Elabora i dati del sensore glicemia e decide le azioni"""
        print("\n" + "=" * 60)
        print("📊 NUOVO DATO GLICEMIA RICEVUTO")
        print("=" * 60)

        glucose_value = data.get('glucose_value')
        glucose_status = data.get('glucose_status')
        trend_direction = data.get('trend_direction', 'stable')

        print(f"🩸 Glicemia: {glucose_value:.1f} mg/dL")
        print(f"📈 Status: {glucose_status}")
        print(f"📉 Trend: {trend_direction}")

        self.last_glucose_reading = data

        # ANALISI E DECISIONE
        action_needed = False
        insulin_dose = 0.0
        alert_level = "NORMAL"
        alert_message = ""

        # 1. IPOGLICEMIA CRITICA
        if self.patient.is_hypoglycemic(glucose_value):
            if glucose_value < 50:
                alert_level = "EMERGENCY_LOW"
                alert_message = f"⚠️ IPOGLICEMIA CRITICA: {glucose_value:.1f} mg/dL - Somministrare glucosio immediatamente!"
            else:
                alert_level = "WARNING_LOW"
                alert_message = f"⚠️ IPOGLICEMIA: {glucose_value:.1f} mg/dL - Assumere 15g di carboidrati"

            print(f"\n🚨 {alert_message}")
            self.send_notification(alert_level, alert_message, glucose_value)
            action_needed = False  # Non serve insulina in ipoglicemia!

        # 2. IPERGLICEMIA - Necessaria correzione con insulina
        elif self.patient.is_hyperglycemic(glucose_value):
            # Calcola dose correzione
            target_glucose = (self.patient.target_glucose_min + self.patient.target_glucose_max) / 2
            insulin_dose = self.patient.calculate_insulin_dose(glucose_value, target_glucose)

            # Verifica safety limits
            time_since_last_correction = time.time() - self.last_correction_time

            if insulin_dose > 0 and time_since_last_correction > self.min_time_between_corrections:
                # Limita la dose massima
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

                self.send_notification(alert_level, alert_message, glucose_value)

            elif insulin_dose > 0:
                print(
                    f"⏳ Attesa tra correzioni: {self.min_time_between_corrections - time_since_last_correction:.0f}s rimanenti")
                alert_message = f"⏳ Iperglicemia rilevata ma in attesa prima di nuova correzione"
                self.send_notification("INFO", alert_message, glucose_value)

        # 3. VALORI NORMALI
        else:
            print(
                f"✅ Glicemia nel range target ({self.patient.target_glucose_min}-{self.patient.target_glucose_max} mg/dL)")

        # Invia comando alla pompa se necessario
        if action_needed and insulin_dose > 0:
            self.send_insulin_command(insulin_dose, "correction",
                                      reason=f"Correzione iperglicemia - Glicemia: {glucose_value:.1f} mg/dL")
            self.last_correction_time = time.time()

        print("=" * 60 + "\n")

    def process_pump_status(self, status_data):
        """Elabora lo status della pompa insulina"""
        self.last_pump_status = status_data

        pump_status = status_data.get('pump_status')
        insulin_level = status_data.get('insulin_reservoir_level')
        battery_level = status_data.get('battery_level')
        active_alarms = status_data.get('active_alarms', [])

        # Notifiche per allarmi pompa
        if 'low_insulin' in active_alarms:
            insulin_pct = (insulin_level / status_data.get('insulin_reservoir_capacity', 300)) * 100
            self.send_notification("WARNING",
                                   f"⚠️ Insulina in esaurimento: {insulin_pct:.0f}% rimanente ({insulin_level:.0f}U)",
                                   None)

        if 'low_battery' in active_alarms:
            self.send_notification("WARNING",
                                   f"🔋 Batteria pompa scarica: {battery_level:.0f}%",
                                   None)

        if 'insulin_empty' in active_alarms:
            self.send_notification("EMERGENCY",
                                   f"🚨 POMPA INSULINA VUOTA - Ricaricare immediatamente!",
                                   None)

    def send_insulin_command(self, insulin_amount, delivery_mode, reason=""):
        """Invia comando alla pompa per erogare insulina"""
        try:
            command = InsulinPumpCommand(
                pump_id=f"pump_{self.patient_id}",
                patient_id=self.patient_id,
                delivery_mode=delivery_mode,
                insulin_amount=round(insulin_amount, 2),
                priority="high" if insulin_amount > 5.0 else "normal",
                reason=reason
            )

            # Verifica sicurezza dose
            if not command.is_safe_dose(max_bolus=self.max_bolus_dose):
                print(f"⚠️ DOSE NON SICURA - Comando NON inviato!")
                self.send_notification("ERROR",
                                       f"❌ Dose richiesta ({insulin_amount:.2f}U) supera il limite di sicurezza",
                                       None)
                return False

            # Pubblica comando MQTT
            command_json = command.to_json()
            self.client.publish(self.pump_command_topic,
                                command_json,
                                qos=Config.QOS_COMMANDS,
                                retain=False)

            print(f"💉 Comando insulina inviato: {insulin_amount:.2f}U ({delivery_mode})")
            print(f"📤 Topic: {self.pump_command_topic}")

            # Salva nel log comandi
            self.insulin_commands_sent.append({
                'timestamp': time.time(),
                'command_id': command.command_id,
                'amount': insulin_amount,
                'reason': reason
            })

            return True

        except Exception as e:
            print(f"❌ Errore invio comando insulina: {e}")
            return False

    def send_notification(self, alert_level, message, glucose_value):
        """Invia notifica al topic alerts"""
        try:
            notification = {
                'patient_id': self.patient_id,
                'timestamp': int(time.time()),
                'alert_level': alert_level,
                'message': message,
                'glucose_value': glucose_value,
                'requires_action': alert_level in ["EMERGENCY_LOW", "EMERGENCY_HIGH", "EMERGENCY"]
            }

            notification_json = json.dumps(notification)
            self.client.publish(self.alert_topic,
                                notification_json,
                                qos=Config.QOS_NOTIFICATIONS,
                                retain=False)

            print(f"🔔 Notifica inviata: {alert_level}")

            # Salva nella history
            self.alert_history.append(notification)

            # Mantieni solo ultime 100 notifiche
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

            # Connetti al broker
            self.client.connect(self.broker_address, self.broker_port, 60)

            # Loop principale
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
    # Crea un paziente di esempio
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

    # Crea e avvia il Data Collector
    collector = DataCollectorConsumer("patient_001", patient)
    collector.start()