# Glicemia Monitor

Sistema IoT per il monitoraggio della glicemia e la gestione della terapia insulinica tramite MQTT.

## Struttura del progetto
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