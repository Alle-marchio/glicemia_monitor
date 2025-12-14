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
    Pompa insulina simulata con supporto SenML che:
    - Riceve comandi in formato SenML dal Data Collector via MQTT
    - Esegue erogazioni di insulina (bolo/basale)
    - Pubblica status in formato SenML periodicamente
    - Gestisce allarmi (insulina bassa, batteria scarica) in formato SenML
    """

    def __init__(self, pump_id, patient_id, initial_insulin=300.0, initial_battery=100.0):
        self.pump_id = pump_id
        self.patient_id = patient_id

        # Inizializza lo status della pompa
        self.status = InsulinPumpStatus(pump_id, patient_id)
        self.status.insulin_reservoir_level = initial_insulin
        self.status.battery_level = initial_battery

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
        self.max_single_bolus = Config.SAFETY_MAX_BOLUS_U # Unità massime per singolo bolo
        self.max_basal_rate = Config.SAFETY_MAX_BASAL_RATE_UH # Unità/ora massime per basale

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
            print(f"⏱️  Intervallo status: {self.status_interval}s")
            print(f"📋 Formato: SenML (RFC 8428)")
            print("=" * 60)

            # Subscribe al topic comandi
            client.subscribe(self.command_topic, qos=Config.QOS_COMMANDS)

            # Pubblica status iniziale (retained)
            self.publish_status()

            print("🎯 Pompa pronta per ricevere comandi SenML...")
        else:
            print(f"❌ Connessione fallita con codice: {rc}")

    def on_disconnect(self, client, userdata, rc):
        """Callback quando la pompa si disconnette"""
        if rc != 0:
            print(f"⚠️ Disconnessione imprevista dal broker (rc: {rc})")

    def on_message(self, client, userdata, msg):
        """Callback quando arriva un comando MQTT in formato SenML"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()

            # Gestione comandi SenML
            if "insulin/pump/command" in topic:
                self.process_senml_command(payload)

        except Exception as e:
            print(f"❌ Errore nell'elaborazione del messaggio: {e}")

    def parse_senml_command(self, senml_json):
        """
        Parse un comando SenML e estrae i parametri

        Formato atteso SenML:
        [
            {
                "bn": "urn:patient:patient_001:insulin:command:",
                "bt": 1234567890.0
            },
            {"n": "dose", "v": 2.5, "u": "U"},
            {"n": "type", "vs": "bolus"},
            {"n": "command_id", "vs": "cmd_123"},
            {"n": "priority", "vs": "high"},
            {"n": "reason", "vs": "High glucose detected"}
        ]

        Returns:
            Dict con i parametri del comando
        """
        try:
            parsed = SenMLHelper.parse_senml(senml_json)
            measurements = parsed.get('measurements', {})

            # Estrai i parametri dal messaggio SenML
            command_data = {
                'insulin_amount': measurements.get('dose', {}).get('value', 0.0),
                'delivery_mode': measurements.get('type', {}).get('value', 'bolus'),
                'command_id': measurements.get('command_id', {}).get('value', 'unknown'),
                'priority': measurements.get('priority', {}).get('value', 'normal'),
                'reason': measurements.get('reason', {}).get('value', 'N/A'),
                'timestamp': parsed.get('base_time', time.time())
            }

            return command_data

        except Exception as e:
            print(f"❌ Errore nel parsing comando SenML: {e}")
            return None

    def process_senml_command(self, senml_payload):
        """Elabora un comando ricevuto in formato SenML"""
        print("\n" + "=" * 60)
        print("📬 NUOVO COMANDO SENML RICEVUTO")
        print("=" * 60)

        try:
            # Parse del messaggio SenML
            command_data = self.parse_senml_command(senml_payload)

            if command_data is None:
                print("❌ Comando SenML non valido")
                return False

            # Estrai parametri comando
            command_id = command_data['command_id']
            delivery_mode = command_data['delivery_mode']
            insulin_amount = command_data['insulin_amount']
            priority = command_data['priority']
            reason = command_data['reason']

            print(f"🆔 Command ID: {command_id}")
            print(f"💉 Modalità: {delivery_mode}")
            print(f"📊 Quantità: {insulin_amount:.2f} unità")
            print(f"⚡ Priorità: {priority}")
            print(f"📝 Motivo: {reason}")
            print(f"📋 Formato: SenML")

            # Verifica stato pompa
            if self.status.pump_status != "active":
                print(f"⚠️ COMANDO RIFIUTATO: Pompa non attiva (status: {self.status.pump_status})")
                self.send_senml_alert("ERROR",
                                      f"Comando {command_id} rifiutato: pompa non attiva",
                                      "high")
                return False

            # Verifica disponibilità insulina
            if self.status.insulin_reservoir_level < insulin_amount:
                print(f"⚠️ COMANDO RIFIUTATO: Insulina insufficiente")
                print(f"   Richiesto: {insulin_amount:.2f}U")
                print(f"   Disponibile: {self.status.insulin_reservoir_level:.2f}U")
                self.send_senml_alert("ERROR",
                                      f"Insulina insufficiente per comando {command_id}",
                                      "critical")
                return False

            # Verifica limiti di sicurezza
            if delivery_mode in ["bolus", "correction"]:
                if insulin_amount > self.max_single_bolus:
                    print(f"⚠️ COMANDO RIFIUTATO: Dose supera limite sicurezza")
                    print(f"   Richiesto: {insulin_amount:.2f}U")
                    print(f"   Limite: {self.max_single_bolus:.2f}U")
                    self.send_senml_alert("ERROR",
                                          f"Dose {insulin_amount:.2f}U supera limite sicurezza",
                                          "critical")
                    return False

            # ESEGUI IL COMANDO
            success = self.execute_delivery(delivery_mode, insulin_amount)

            if success:
                print(f"✅ Comando eseguito con successo!")

                # Salva nel log
                self.command_history.append({
                    'timestamp': time.time(),
                    'command_id': command_id,
                    'delivery_mode': delivery_mode,
                    'amount': insulin_amount,
                    'reason': reason
                })

                # Pubblica nuovo status in SenML
                self.publish_status()

                # Invia conferma in SenML
                self.send_senml_alert("INFO",
                                      f"Erogazione completata: {insulin_amount:.2f}U ({delivery_mode})",
                                      "low")
            else:
                print(f"❌ Errore nell'esecuzione del comando")

            print("=" * 60 + "\n")
            return success

        except Exception as e:
            print(f"❌ Errore nel processamento comando SenML: {e}")
            return False

    def execute_delivery(self, delivery_mode, amount):
        """Simula l'erogazione di insulina"""
        try:
            print(f"\n💉 Inizio erogazione...")

            # Simula tempo di erogazione (1 secondo per unità)
            delivery_time = amount * 1.0
            print(f"⏱️  Tempo stimato: {delivery_time:.1f}s")

            # Simula erogazione progressiva
            time.sleep(min(delivery_time, 3.0))  # Max 3 secondi per non bloccare

            # Esegui l'erogazione
            if delivery_mode in ["bolus", "correction"]:
                success = self.status.deliver_bolus(amount, delivery_mode)
                if success:
                    print(f"✅ Bolo erogato: {amount:.2f} unità")
                    return True
                else:
                    print(f"❌ Errore nell'erogazione del bolo")
                    return False

            elif delivery_mode == "basal":
                # Per basale, aggiorna il rate
                delivery_rate = amount  # unità/ora
                if delivery_rate <= self.max_basal_rate:
                    self.status.current_basal_rate = delivery_rate
                    print(f"✅ Rate basale aggiornato: {delivery_rate:.2f} U/h")
                    return True
                else:
                    print(f"❌ Rate basale supera limite")
                    return False

            elif delivery_mode == "emergency_stop":
                self.status.current_basal_rate = 0.0
                print(f"🛑 STOP EMERGENZA: Tutte le erogazioni fermate")
                return True

            else:
                print(f"⚠️ Modalità sconosciuta: {delivery_mode}")
                return False

        except Exception as e:
            print(f"❌ Errore durante erogazione: {e}")
            return False

    def create_senml_status(self):
        """
        Crea un messaggio SenML completo per lo status della pompa

        Formato SenML generato (compatibile con InsulinPumpStatus):
        [
            {
                "bn": "urn:patient:patient_001:pump:pump_001:",
                "bt": 1234567890.0
            },
            {"n": "reservoir", "v": 285.5, "u": "U"},
            {"n": "reservoir_capacity", "v": 300.0, "u": "U"},
            {"n": "reservoir_pct", "v": 95.2, "u": "%"},
            {"n": "battery", "v": 95.2, "u": "%"},
            {"n": "status", "vs": "active"},
            {"n": "basal_rate", "v": 1.0, "u": "U/h"},
            {"n": "total_daily_insulin", "v": 14.5, "u": "U"},
            {"n": "last_bolus", "v": 2.5, "u": "U"},
            {"n": "last_bolus_time", "v": 1234567890},
            {"n": "alarms_count", "v": 0},
            {"n": "alarms", "vs": "low_insulin,low_battery"}
        ]
        """
        base_name = f"urn:patient:{self.patient_id}:pump:{self.pump_id}:"
        timestamp = time.time()

        # Record base - campi sempre presenti
        senml_record = [
            {
                "bn": base_name,
                "bt": timestamp
            },
            {
                "n": "reservoir",
                "v": round(self.status.insulin_reservoir_level, 2),
                "u": "U",
                "t": 0
            },
            {
                "n": "reservoir_capacity",
                "v": round(self.status.insulin_reservoir_capacity, 2),
                "u": "U",
                "t": 0
            },
            {
                "n": "reservoir_pct",
                "v": round(self.status.insulin_percentage(), 1),
                "u": "%",
                "t": 0
            },
            {
                "n": "battery",
                "v": round(self.status.battery_level, 2),
                "u": "%",
                "t": 0
            },
            {
                "n": "status",
                "vs": self.status.pump_status,
                "t": 0
            },
            {
                "n": "basal_rate",
                "v": round(self.status.current_basal_rate, 2),
                "u": "U/h",
                "t": 0
            },
            {
                "n": "total_daily_insulin",
                "v": round(self.status.total_daily_insulin, 2),
                "u": "U",
                "t": 0
            },
            {
                "n": "alarms_count",
                "v": len(self.status.active_alarms),
                "t": 0
            }
        ]

        # Aggiungi last_bolus se esiste
        if self.status.last_bolus_amount is not None:
            senml_record.append({
                "n": "last_bolus",
                "v": round(self.status.last_bolus_amount, 2),
                "u": "U",
                "t": 0
            })

        # Aggiungi last_bolus_time se esiste
        if self.status.last_bolus_time is not None:
            senml_record.append({
                "n": "last_bolus_time",
                "v": self.status.last_bolus_time,
                "t": 0
            })

        # Aggiungi lista allarmi attivi come stringa
        if self.status.active_alarms:
            senml_record.append({
                "n": "alarms",
                "vs": ",".join(self.status.active_alarms),
                "t": 0
            })

        # Aggiungi last_error se presente
        if self.status.last_error is not None:
            senml_record.append({
                "n": "last_error",
                "vs": str(self.status.last_error),
                "t": 0
            })

        return json.dumps(senml_record)

    def publish_status(self):
        """Pubblica lo status corrente della pompa in formato SenML"""
        try:
            # Aggiorna lo status (consuma batteria/insulina basale)
            self.status.update_status()

            # Crea messaggio SenML
            status_senml = self.create_senml_status()

            # Pubblica su MQTT (retained per avere sempre l'ultimo status)
            result = self.client.publish(
                self.status_topic,
                status_senml,
                qos=Config.QOS_SENSOR_DATA,
                retain=Config.RETAIN_PUMP_STATUS
            )

            # Log status (versione compatta)
            insulin_pct = self.status.insulin_percentage()
            print(f"📊 Status SenML pubblicato | "
                  f"💉 {self.status.insulin_reservoir_level:.1f}U ({insulin_pct:.0f}%) | "
                  f"🔋 {self.status.battery_level:.1f}% | "
                  f"⚙️  {self.status.pump_status} | "
                  f"🚨 {len(self.status.active_alarms)} allarmi")

            # Gestione allarmi critici
            if self.status.has_critical_alarms():
                for alarm in self.status.active_alarms:
                    self.send_senml_alert("PUMP_ALARM", f"🚨 ALLARME CRITICO: {alarm}", "critical")

            return result.rc == mqtt.MQTT_ERR_SUCCESS

        except Exception as e:
            print(f"❌ Errore pubblicazione status SenML: {e}")
            return False

    def send_senml_alert(self, alert_type, message, severity="medium"):
        """
        Invia un alert al topic notifiche in formato SenML

        Args:
            alert_type: Tipo di alert (es. "ERROR", "INFO", "PUMP_ALARM")
            message: Messaggio descrittivo
            severity: Gravità ("low", "medium", "high", "critical")
        """
        try:
            # Usa il metodo del SenMLHelper
            alert_senml = SenMLHelper.create_notification_alert(
                patient_id=self.patient_id,
                alert_type=alert_type,
                message=message,
                severity=severity,
                timestamp=time.time()
            )

            # Pubblica l'alert
            self.client.publish(
                self.alert_topic,
                alert_senml,
                qos=Config.QOS_NOTIFICATIONS,
                retain=False
            )

            # Log dell'alert inviato
            severity_emoji = {"low": "ℹ️", "medium": "⚠️", "high": "🔶", "critical": "🚨"}
            emoji = severity_emoji.get(severity, "📢")
            print(f"{emoji} Alert SenML inviato: [{alert_type}] {message}")

        except Exception as e:
            print(f"❌ Errore invio alert SenML: {e}")

    def status_publisher_loop(self):
        """Loop per pubblicazione periodica dello status in SenML"""
        while self.running:
            self.publish_status()
            time.sleep(self.status_interval)

    def start(self):
        """Avvia la pompa"""
        try:
            print("\n" + "=" * 60)
            print("🚀 AVVIO POMPA INSULINA (SenML)")
            print("=" * 60)
            print(f"🆔 Pompa ID: {self.pump_id}")
            print(f"👤 Paziente ID: {self.patient_id}")
            print(f"💉 Insulina iniziale: {self.status.insulin_reservoir_level:.1f}U")
            print(f"🔋 Batteria: {self.status.battery_level:.1f}%")
            print(f"📡 Broker: {self.broker_address}:{self.broker_port}")
            print(f"📋 Formato: SenML (RFC 8428)")
            print("=" * 60 + "\n")

            # Connetti al broker
            self.client.connect(self.broker_address, self.broker_port, 60)
            self.client.loop_start()

            # Avvia thread per pubblicazione status periodica
            self.running = True
            self.status_thread = threading.Thread(target=self.status_publisher_loop)
            self.status_thread.daemon = True
            self.status_thread.start()

            # Mantieni il programma in esecuzione
            while self.running:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n⏹️  Pompa fermata dall'utente")
            self.stop()
        except Exception as e:
            print(f"❌ Errore critico: {e}")
            self.stop()

    def stop(self):
        """Ferma la pompa"""
        print("\n🛑 Chiusura pompa insulina...")
        self.running = False

        # Attendi thread status
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=2)

        self.client.loop_stop()
        self.client.disconnect()
        print("✅ Pompa disconnessa")

    def get_statistics(self):
        """Restituisce statistiche della pompa"""
        total_commands = len(self.command_history)
        total_insulin = sum(cmd['amount'] for cmd in self.command_history)

        return {
            'total_commands': total_commands,
            'total_insulin_delivered': total_insulin,
            'current_insulin_level': self.status.insulin_reservoir_level,
            'battery_level': self.status.battery_level,
            'pump_status': self.status.pump_status
        }


if __name__ == "__main__":

    # Definisce il percorso di default al file JSON nella cartella conf/
    CONFIG_FILE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'conf',
        'patient_config.json'
    )

    # Valori di default
    pump_id = 'pump_001'  # Pump ID non è nel config paziente
    initial_insulin = 300.0
    initial_battery = 100.0

    # Configurazione paziente - ORA CARICATA DA FILE
    try:
        patient = PatientDescriptor.from_json_file(CONFIG_FILE_PATH)
        patient_id = patient.patient_id

        print(f"✅ Configurazione paziente '{patient.name}' caricata da: {CONFIG_FILE_PATH}")

    except (FileNotFoundError, ValueError) as e:
        print(f"❌ Errore di caricamento o parsing della configurazione: {e}")
        sys.exit(1)

    # Crea la pompa con supporto SenML
    pump = InsulinPumpActuatorSenML(
        pump_id=pump_id,
        patient_id=patient_id,
        initial_insulin=initial_insulin,
        initial_battery=initial_battery
    )

    # Avvia la pompa
    pump.start()