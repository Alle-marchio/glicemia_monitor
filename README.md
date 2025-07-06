# Glicemia Monitor IoT System

Un sistema IoT per il monitoraggio della glicemia e la gestione remota della pompa per insulina dei pazienti diabetici. Il progetto utilizza MQTT come sistema di messaggistica per raccogliere, elaborare e visualizzare i dati sanitari in tempo reale.

## Funzionalità principali

- Raccolta dati da sensori glicemici tramite MQTT.
- Invio comandi alle pompe di insulina.
- Monitoraggio stato pompa e notifiche critiche.
- Dashboard web per la visualizzazione dei dati.
- Struttura modulare con componenti riutilizzabili.

---

## Struttura del progetto
```
glicemia_monitor/
├── model/ # Classi di modello
│ ├── glucose_sensor_data.py
│ ├── insulin_pump_data.py
│ └── patient_descriptor.py
├── conf/ # Configurazione
│ └── mqtt_conf_params.py
├── process/ # Processi MQTT
│ ├── glucose_sensor_producer.py
│ ├── insulin_pump_actuator.py
│ ├── data_collector_consumer.py
│ └── notification_manager.py
├── utils/ # Utilità
│ └── senml_helper.py
└── dashboard/ # Interfaccia web
└── web_dashboard.py
```

---

## MQTT Topic Structure

| Topic                                                       | Descrizione                         |
|-------------------------------------------------------------|-------------------------------------|
| `/iot/patient/<patient_id>/glucose/sensor/data`            | Dati sensore glicemia               |
| `/iot/patient/<patient_id>/insulin/pump/command`           | Comandi alla pompa di insulina      |
| `/iot/patient/<patient_id>/insulin/pump/status`            | Stato della pompa di insulina       |
| `/iot/patient/<patient_id>/notifications/alert`            | Notifiche critiche                  |
| `/iot/patient/<patient_id>/info`                           | Info generali sul paziente (retained) |

---

## Requisiti

Installa le dipendenze con:

```bash
pip install -r requirements.txt

