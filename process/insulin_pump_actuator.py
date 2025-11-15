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
from conf.mqtt_conf_params import MqttConfigurationParameters as Config


class InsulinPumpActuator:
    """
    Pompa insulina simulata che:
    - Riceve comandi dal Data Collector via MQTT
    - Esegue erogazioni di insulina (bolo/basale)
    - Pubblica status periodicamente
    - Gestisce allarmi (insulina bassa, batteria scarica)
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
        self.client = mqtt.Client(f"insulin_pump_{pump_id}")

        # Topic MQTT
        self.base_topic = f"/iot/patient/{patient_id}"
        self.command_topic = f"{self.base_topic}/insulin/pump/command"
        self.status_topic = f"{self.base_topic}/insulin/pump/status"
        self.alert_topic = f"{self.base_topic}/notifications/alert"

        # Intervallo pubblicazione status
        self.status_interval = Config.PUMP_STATUS_INTERVAL

        # Parametri di sicurezza
        self.max_single_bolus = 15.0  # Unità massime per singolo bolo
        self.max_basal_rate = 5.0  # Unità/ora massime per basale

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
            print(f"✅ Pompa insulina connessa al broker MQTT")
            print(f"📥 Subscribing a: {self.command_topic}")
            print(f"📤 Pubblicazione status su: {self.status_topic}")
            print(f"⏱️  Intervallo status: {self.status_interval}s")
            print("=" * 60)

            # Subscribe al topic comandi
            client.subscribe(self.command_topic, qos=Config.QOS_COMMANDS)

            # Pubblica status iniziale (retained)
            self.publish_status()

            print("🎯 Pompa pronta per ricevere comandi...")
        else:
            print(f"❌ Connessione fallita con codice: {rc}")

    def on_disconnect(self, client, userdata, rc):
        """Callback quando la pompa si disconnette"""
        if rc != 0:
            print(f"⚠️ Disconnessione imprevista dal broker (rc: {rc})")

    def on_message(self, client, userdata, msg):
        """Callback quando arriva un comando MQTT"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            # Gestione comandi
            if "insulin/pump/command" in topic:
                self.process_command(payload)

        except Exception as e:
            print(f"❌ Errore nell'elaborazione del messaggio: {e}")

    def process_command(self, command_data):
        """Elabora un comando ricevuto dal Data Collector"""
        print("\n" + "=" * 60)
        print("📬 NUOVO COMANDO RICEVUTO")
        print("=" * 60)

        try:
            # Estrai parametri comando
            command_id = command_data.get('command_id', 'unknown')
            delivery_mode = command_data.get('delivery_mode')
            insulin_amount = command_data.get('insulin_amount')
            priority = command_data.get('priority', 'normal')
            reason = command_data.get('reason', 'N/A')

            print(f"🆔 Command ID: {command_id}")
            print(f"💉 Modalità: {delivery_mode}")
            print(f"📊 Quantità: {insulin_amount:.2f} unità")
            print(f"⚡ Priorità: {priority}")
            print(f"📝 Motivo: {reason}")

            # Verifica stato pompa
            if self.status.pump_status != "active":
                print(f"⚠️ COMANDO RIFIUTATO: Pompa non attiva (status: {self.status.pump_status})")
                self.send_alert("ERROR",
                                f"Comando {command_id} rifiutato: pompa non attiva")
                return False

            # Verifica disponibilità insulina
            if self.status.insulin_reservoir_level < insulin_amount:
                print(f"⚠️ COMANDO RIFIUTATO: Insulina insufficiente")
                print(f"   Richiesto: {insulin_amount:.2f}U")
                print(f"   Disponibile: {self.status.insulin_reservoir_level:.2f}U")
                self.send_alert("ERROR",
                                f"Insulina insufficiente per comando {command_id}")
                return False

            # Verifica limiti di sicurezza
            if delivery_mode in ["bolus", "correction"]:
                if insulin_amount > self.max_single_bolus:
                    print(f"⚠️ COMANDO RIFIUTATO: Dose supera limite sicurezza")
                    print(f"   Richiesto: {insulin_amount:.2f}U")
                    print(f"   Limite: {self.max_single_bolus:.2f}U")
                    self.send_alert("ERROR",
                                    f"Dose {insulin_amount:.2f}U supera limite sicurezza")
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

                # Pubblica nuovo status
                self.publish_status()

                # Invia conferma
                self.send_alert("INFO",
                                f"Erogazione completata: {insulin_amount:.2f}U ({delivery_mode})")
            else:
                print(f"❌ Errore nell'esecuzione del comando")

            print("=" * 60 + "\n")
            return success

        except Exception as e:
            print(f"❌ Errore nel processamento comando: {e}")
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

    def publish_status(self):
        """Pubblica lo status corrente della pompa"""
        try:
            # Aggiorna lo status (consuma batteria/insulina basale)
            self.status.update_status()

            # Converti in JSON
            status_json = self.status.to_json()

            # Pubblica su MQTT (retained per avere sempre l'ultimo status)
            result = self.client.publish(
                self.status_topic,
                status_json,
                qos=Config.QOS_SENSOR_DATA,
                retain=Config.RETAIN_PUMP_STATUS
            )

            # Log status (versione compatta)
            insulin_pct = self.status.insulin_percentage()
            print(f"📊 Status pubblicato | "
                  f"💉 {self.status.insulin_reservoir_level:.1f}U ({insulin_pct:.0f}%) | "
                  f"🔋 {self.status.battery_level:.1f}% | "
                  f"⚙️  {self.status.pump_status} | "
                  f"🚨 {len(self.status.active_alarms)} allarmi")

            # Gestione allarmi critici
            if self.status.has_critical_alarms():
                for alarm in self.status.active_alarms:
                    self.send_alert("EMERGENCY", f"🚨 ALLARME CRITICO: {alarm}")

            return result.rc == mqtt.MQTT_ERR_SUCCESS

        except Exception as e:
            print(f"❌ Errore pubblicazione status: {e}")
            return False

    def send_alert(self, level, message):
        """Invia un alert al topic notifiche"""
        try:
            alert = {
                'pump_id': self.pump_id,
                'patient_id': self.patient_id,
                'timestamp': int(time.time()),
                'alert_level': level,
                'message': message,
                'insulin_level': self.status.insulin_reservoir_level,
                'battery_level': self.status.battery_level
            }

            alert_json = json.dumps(alert)
            self.client.publish(
                self.alert_topic,
                alert_json,
                qos=Config.QOS_NOTIFICATIONS,
                retain=False
            )

        except Exception as e:
            print(f"❌ Errore invio alert: {e}")

    def status_publisher_loop(self):
        """Loop per pubblicazione periodica dello status"""
        while self.running:
            self.publish_status()
            time.sleep(self.status_interval)

    def start(self):
        """Avvia la pompa"""
        try:
            print("\n" + "=" * 60)
            print("🚀 AVVIO POMPA INSULINA")
            print("=" * 60)
            print(f"🆔 Pompa ID: {self.pump_id}")
            print(f"👤 Paziente ID: {self.patient_id}")
            print(f"💉 Insulina iniziale: {self.status.insulin_reservoir_level:.1f}U")
            print(f"🔋 Batteria: {self.status.battery_level:.1f}%")
            print(f"📡 Broker: {self.broker_address}:{self.broker_port}")
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


# MAIN - Esempi di utilizzo
if __name__ == "__main__":
    import argparse

    # Parser argomenti da linea di comando
    parser = argparse.ArgumentParser(description='Simulatore pompa insulina')
    parser.add_argument('--patient-id', type=str, default='patient_001',
                        help='ID del paziente')
    parser.add_argument('--pump-id', type=str, default='pump_001',
                        help='ID della pompa')
    parser.add_argument('--initial-insulin', type=float, default=300.0,
                        help='Livello iniziale insulina (unità)')
    parser.add_argument('--initial-battery', type=float, default=100.0,
                        help='Livello iniziale batteria (percentuale)')

    args = parser.parse_args()

    # Crea la pompa
    pump = InsulinPumpActuator(
        pump_id=args.pump_id,
        patient_id=args.patient_id,
        initial_insulin=args.initial_insulin,
        initial_battery=args.initial_battery
    )

    # Avvia la pompa
    pump.start()

    # Esempi di utilizzo:
    # python insulin_pump_actuator.py
    # python insulin_pump_actuator.py --initial-insulin 200
    # python insulin_pump_actuator.py --patient-id patient_002 --pump-id pump_002