import paho.mqtt.client as mqtt
import json
import time
import sys
import os
import uuid

# Import dei modelli e helper
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.glucose_sensor_data import GlucoseSensorData
from model.patient_descriptor import PatientDescriptor
from model.insulin_pump_data import InsulinPumpCommand, InsulinPumpStatus
from conf.mqtt_conf_params import MqttConfigurationParameters as Config
from utils.senml_helper import SenMLHelper


class DataCollectorConsumerSenML:
    """
    Data Collector principale con supporto completo SenML che:
    - Riceve dati dal sensore glicemia in formato SenML
    - Analizza i valori e calcola azioni necessarie
    - Invia comandi alla pompa insulina in formato SenML compatibile
    - Genera notifiche in formato SenML
    """

    def __init__(self, patient_id, patient_descriptor):
        self.patient_id = patient_id
        self.patient = patient_descriptor

        # Configurazione MQTT
        self.broker_address = Config.BROKER_ADDRESS
        self.broker_port = Config.BROKER_PORT
        self.client = mqtt.Client(f"data_collector_senml_{patient_id}")

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
            print(f"✅ Data Collector (SenML) connesso al broker MQTT")
            print(f"📡 Subscribing a topic glicemia: {self.glucose_data_topic}")
            print(f"📡 Subscribing a topic status pompa: {self.pump_status_topic}")
            print(f"📋 Formato: SenML (RFC 8428)")
            print("=" * 60)

            client.subscribe(self.glucose_data_topic, qos=Config.QOS_SENSOR_DATA)
            client.subscribe(self.pump_status_topic, qos=Config.QOS_SENSOR_DATA)

            print("🎯 Data Collector pronto per ricevere dati SenML...")
        else:
            print(f"❌ Connessione fallita con codice: {rc}")

    def on_message(self, client, userdata, msg):
        """Callback quando arriva un messaggio MQTT in formato SenML"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()

            # ✅ Parse del payload in formato SenML
            parsed = SenMLHelper.parse_senml(payload)
            measurements = parsed.get("measurements", {})

            # Gestione messaggi dal sensore glicemia
            if "glucose/sensor/data" in topic:
                self.process_glucose_data(measurements, parsed.get("base_time"))

            # Gestione status pompa insulina
            elif "insulin/pump/status" in topic:
                self.process_pump_status(measurements, parsed.get("base_time"))

        except Exception as e:
            print(f"❌ Errore nell'elaborazione del messaggio SenML: {e}")

    def process_glucose_data(self, data, timestamp):
        """Elabora i dati SenML del sensore glicemia"""
        print("\n" + "=" * 60)
        print("📊 NUOVO DATO GLICEMIA RICEVUTO (SenML)")
        print("=" * 60)

        glucose_value = data.get("level", {}).get("value")
        trend_direction = data.get("trend", {}).get("value", "stable")
        glucose_status = data.get("status", {}).get("value", "unknown")
        trend_rate = data.get("trend_rate", {}).get("value", 0.0)
        battery_level = data.get("battery", {}).get("value", 100.0)

        print(f"🩸 Glicemia: {glucose_value:.1f} mg/dL")
        print(f"📈 Status: {glucose_status}")
        print(f"📉 Trend: {trend_direction} ({trend_rate:.1f} mg/dL/min)")
        print(f"🔋 Batteria sensore: {battery_level:.1f}%")

        self.last_glucose_reading = data

        # ANALISI E DECISIONE
        action_needed = False
        insulin_dose = 0.0
        alert_level = "NORMAL"
        alert_message = ""
        priority = "normal"

        # 1️⃣ IPOGLICEMIA
        if self.patient.is_hypoglycemic(glucose_value):
            if glucose_value < 50:
                alert_level = "EMERGENCY_LOW"
                alert_message = f"⚠️ IPOGLICEMIA CRITICA: {glucose_value:.1f} mg/dL - Somministrare glucosio immediatamente!"
                priority = "emergency"
            else:
                alert_level = "WARNING_LOW"
                alert_message = f"⚠️ IPOGLICEMIA: {glucose_value:.1f} mg/dL - Assumere 15g di carboidrati"
                priority = "high"

            print(f"\n🚨 {alert_message}")
            self.send_notification(alert_level, alert_message, "critical" if glucose_value < 50 else "high")
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
                    priority = "emergency"
                else:
                    alert_level = "WARNING_HIGH"
                    alert_message = f"⚠️ IPERGLICEMIA: {glucose_value:.1f} mg/dL - Correzione con {insulin_dose:.2f}U insulina"
                    priority = "high"

                print(f"\n💉 Dose insulina calcolata: {insulin_dose:.2f} unità")
                print(f"🎯 Target glicemico: {target_glucose:.1f} mg/dL")
                print(f"⚡ Priorità comando: {priority}")

                self.send_notification(alert_level, alert_message, "critical" if glucose_value > 250 else "high")

            elif insulin_dose > 0:
                remaining = self.min_time_between_corrections - time_since_last_correction
                print(f"⏳ Attesa tra correzioni: {remaining:.0f}s rimanenti")
                self.send_notification("INFO", "⏳ Iperglicemia rilevata ma in attesa prima di nuova correzione", "low")

        # 3️⃣ VALORI NORMALI
        else:
            print(
                f"✅ Glicemia nel range target ({self.patient.target_glucose_min}-{self.patient.target_glucose_max} mg/dL)")

        # ✅ Invia comando alla pompa in SenML se necessario
        if action_needed and insulin_dose > 0:
            reason = f"Glucose level: {glucose_value:.1f} mg/dL (High)"
            self.send_insulin_command_senml(
                insulin_amount=insulin_dose,
                delivery_mode="correction",
                priority=priority,
                reason=reason
            )
            self.last_correction_time = time.time()

        print("=" * 60 + "\n")

    def process_pump_status(self, data, timestamp):
        """Elabora lo status pompa da messaggio SenML"""
        self.last_pump_status = data

        # Estrai i dati dal messaggio SenML
        pump_status = data.get("status", {}).get("value", "active")
        insulin_level = data.get("reservoir", {}).get("value", 0)
        reservoir_pct = data.get("reservoir_pct", {}).get("value", 0)
        battery_level = data.get("battery", {}).get("value", 0)
        basal_rate = data.get("basal_rate", {}).get("value", 0)
        total_daily = data.get("total_daily_insulin", {}).get("value", 0)
        alarms_count = data.get("alarms_count", {}).get("value", 0)
        alarms_str = data.get("alarms", {}).get("value", "")
        last_bolus = data.get("last_bolus", {}).get("value")

        print(f"\n📊 Status pompa SenML ricevuto: {pump_status}")
        print(f"   💉 Insulina: {insulin_level:.1f}U ({reservoir_pct:.0f}%)")
        print(f"   🔋 Batteria: {battery_level:.1f}%")
        print(f"   ⚙️  Rate basale: {basal_rate:.2f} U/h")
        print(f"   📈 Totale giornaliero: {total_daily:.1f}U")

        if last_bolus is not None:
            print(f"   💊 Ultimo bolo: {last_bolus:.1f}U")

        if alarms_count > 0:
            print(f"   🚨 Allarmi attivi ({alarms_count}): {alarms_str}")

        # Gestione allarmi
        if insulin_level < 30 and "low_insulin" not in alarms_str:
            self.send_notification("WARNING",
                                   f"⚠️ Insulina quasi terminata ({insulin_level:.1f}U)",
                                   "high")

        if battery_level < 20 and "low_battery" not in alarms_str:
            self.send_notification("WARNING",
                                   f"🔋 Batteria pompa bassa ({battery_level:.0f}%)",
                                   "medium")

        if insulin_level <= 0:
            self.send_notification("EMERGENCY",
                                   "🚨 POMPA INSULINA VUOTA - Ricaricare immediatamente!",
                                   "critical")

        if "battery_critical" in alarms_str:
            self.send_notification("EMERGENCY",
                                   "🚨 BATTERIA CRITICA - Sostituire immediatamente!",
                                   "critical")

    def create_insulin_command_senml(self, insulin_amount, delivery_mode, priority, reason):
        """
        Crea un comando insulina in formato SenML compatibile con InsulinPumpActuatorSenML

        Formato generato:
        [
            {"bn": "urn:patient:patient_001:insulin:command:", "bt": 1234567890.0},
            {"n": "dose", "v": 2.5, "u": "U"},
            {"n": "type", "vs": "correction"},
            {"n": "command_id", "vs": "cmd_abc123"},
            {"n": "priority", "vs": "high"},
            {"n": "reason", "vs": "High glucose detected"}
        ]
        """
        base_name = f"urn:patient:{self.patient_id}:insulin:command:"
        timestamp = time.time()
        command_id = f"cmd_{uuid.uuid4().hex[:8]}"

        senml_record = [
            {
                "bn": base_name,
                "bt": timestamp
            },
            {
                "n": "dose",
                "v": round(insulin_amount, 2),
                "u": "U",
                "t": 0
            },
            {
                "n": "type",
                "vs": delivery_mode,
                "t": 0
            },
            {
                "n": "command_id",
                "vs": command_id,
                "t": 0
            },
            {
                "n": "priority",
                "vs": priority,
                "t": 0
            },
            {
                "n": "reason",
                "vs": reason,
                "t": 0
            }
        ]

        return json.dumps(senml_record), command_id

    def send_insulin_command_senml(self, insulin_amount, delivery_mode, priority="normal", reason=""):
        """
        Invia comando alla pompa in formato SenML compatibile

        Args:
            insulin_amount: Quantità di insulina (unità)
            delivery_mode: Modalità erogazione ("bolus", "correction", "basal")
            priority: Priorità comando ("normal", "high", "emergency")
            reason: Motivo del comando
        """
        try:
            # ✅ Crea comando SenML compatibile con la pompa
            command_senml, command_id = self.create_insulin_command_senml(
                insulin_amount=insulin_amount,
                delivery_mode=delivery_mode,
                priority=priority,
                reason=reason
            )

            # Pubblica il comando
            result = self.client.publish(
                self.pump_command_topic,
                command_senml,
                qos=Config.QOS_COMMANDS,
                retain=False
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"\n💉 Comando insulina SenML inviato:")
                print(f"   🆔 Command ID: {command_id}")
                print(f"   💊 Dose: {insulin_amount:.2f}U")
                print(f"   📋 Tipo: {delivery_mode}")
                print(f"   ⚡ Priorità: {priority}")
                print(f"   📝 Motivo: {reason}")
                print(f"   📤 Topic: {self.pump_command_topic}")

                # Mostra preview del SenML (primi 100 caratteri)
                preview = command_senml[:100] + "..." if len(command_senml) > 100 else command_senml
                print(f"   📋 SenML: {preview}")
            else:
                print(f"❌ Errore pubblicazione comando (rc: {result.rc})")

            # Salva nel log
            self.insulin_commands_sent.append({
                'timestamp': time.time(),
                'command_id': command_id,
                'amount': insulin_amount,
                'delivery_mode': delivery_mode,
                'priority': priority,
                'reason': reason
            })

        except Exception as e:
            print(f"❌ Errore invio comando insulina SenML: {e}")

    def send_notification(self, alert_level, message, severity="medium"):
        """
        Invia notifica al topic alerts in SenML

        Args:
            alert_level: Livello alert (es. "WARNING_HIGH", "EMERGENCY_LOW")
            message: Messaggio descrittivo
            severity: Gravità ("low", "medium", "high", "critical")
        """
        try:
            alert_senml = SenMLHelper.create_notification_alert(
                patient_id=self.patient_id,
                alert_type=alert_level,
                message=message,
                severity=severity,
                timestamp=time.time()
            )

            self.client.publish(
                self.alert_topic,
                alert_senml,
                qos=Config.QOS_NOTIFICATIONS,
                retain=False
            )

            severity_emoji = {"low": "ℹ️", "medium": "⚠️", "high": "🔶", "critical": "🚨"}
            emoji = severity_emoji.get(severity, "📢")
            print(f"{emoji} Notifica SenML inviata: [{alert_level}] {severity}")

            self.alert_history.append({
                'timestamp': time.time(),
                'level': alert_level,
                'message': message,
                'severity': severity
            })

            # Mantieni solo le ultime 10 notifiche
            if len(self.alert_history) > 10:
                self.alert_history = self.alert_history[-10:]

        except Exception as e:
            print(f"❌ Errore invio notifica SenML: {e}")

    def start(self):
        """Avvia il Data Collector"""
        try:
            print("\n" + "=" * 60)
            print("🚀 AVVIO DATA COLLECTOR (SenML)")
            print("=" * 60)
            print(f"👤 Paziente: {self.patient.name} (ID: {self.patient_id})")
            print(f"🎯 Range target: {self.patient.target_glucose_min}-{self.patient.target_glucose_max} mg/dL")
            print(f"💉 Fattore sensibilità: {self.patient.insulin_sensitivity_factor} mg/dL per unità")
            print(f"⏱️  Min tempo tra correzioni: {self.min_time_between_corrections}s")
            print(f"📡 Broker: {self.broker_address}:{self.broker_port}")
            print(f"📋 Formato: SenML (RFC 8428)")
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

    def get_statistics(self):
        """Restituisce statistiche del Data Collector"""
        total_commands = len(self.insulin_commands_sent)
        total_insulin = sum(cmd['amount'] for cmd in self.insulin_commands_sent)

        return {
            'total_commands_sent': total_commands,
            'total_insulin_commanded': total_insulin,
            'total_alerts': len(self.alert_history),
            'last_glucose': self.last_glucose_reading,
            'last_pump_status': self.last_pump_status
        }


# MAIN - Esempio di utilizzo
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Data Collector con supporto SenML completo')
    parser.add_argument('--patient-id', type=str, default='patient_001',
                        help='ID del paziente')

    args = parser.parse_args()

    # Configurazione paziente
    patient = PatientDescriptor(
        patient_id=args.patient_id,
        name="Mario Rossi",
        age=45,
        weight=75,
        target_glucose_min=70.0,
        target_glucose_max=140.0,
        hypoglycemia_threshold=60.0,
        hyperglycemia_threshold=200.0,
        insulin_sensitivity_factor=50.0,  # 1U riduce glicemia di 50 mg/dL
        carb_ratio=12.0,
        basal_insulin_rate=1.0,
        sensor_reading_interval=5,
        alert_enabled=True,
        emergency_contact="+39 123 456 7890"
    )

    # Avvia Data Collector con supporto SenML
    collector = DataCollectorConsumerSenML(args.patient_id, patient)
    collector.start()

    # Esempi di utilizzo:
    # python data_collector_consumer_senml.py
    # python data_collector_consumer_senml.py --patient-id patient_002