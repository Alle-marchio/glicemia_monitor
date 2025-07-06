# Glicemia Monitor

Sistema IoT per il monitoraggio della glicemia e la gestione della terapia insulinica tramite MQTT.

## Struttura del progetto

glicemia_monitor/
├── model/                    # Classi di modello
│   ├── glucose_sensor_data.py
│   ├── insulin_pump_data.py
│   └── patient_descriptor.py
├── conf/                     # Configurazione
│   └── mqtt_conf_params.py
├── process/                  # Processi MQTT
│   ├── glucose_sensor_producer.py
│   ├── insulin_pump_actuator.py
│   ├── data_collector_consumer.py
│   └── notification_manager.py
├── utils/                    # Utilità
│   └── senml_helper.py
└── dashboard/               # Web interface
    └── web_dashboard.py

## Topic MQTT

- `/iot/patient/<patient_id>/glucose/sensor/data` — Dati sensore glicemia
- `/iot/patient/<patient_id>/insulin/pump/command` — Comandi pompa insulina
- `/iot/patient/<patient_id>/insulin/pump/status` — Stato pompa insulina
- `/iot/patient/<patient_id>/notifications/alert` — Notifiche critiche
- `/iot/patient/<patient_id>/info` — Info paziente

## Requisiti

- Python 3.8+
- pip
- [paho-mqtt](https://pypi.org/project/paho-mqtt/)

## Installazione

```bash
pip install -r requirements.txtpython test_mqtt.py