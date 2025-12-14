# Sistema IoT per Monitoraggio Glicemia e Gestione Insulina
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![MQTT](https://img.shields.io/badge/MQTT-Paho-orange.svg)](https://www.eclipse.org/paho/)
[![SenML](https://img.shields.io/badge/SenML-RFC%208428-green.svg)](https://tools.ietf.org/html/rfc8428)
[![Flask](https://img.shields.io/badge/Flask-2.3.3-black.svg)](https://flask.palletsprojects.com/)

---

Sistema IoT completo per il **monitoraggio continuo della glicemia** in pazienti diabetici e la **gestione automatizzata dell'insulina** tramite pompa intelligente. Il progetto utilizza **MQTT** come protocollo di messaggistica e **SenML** (Sensor Markup Language) come formato standard per lo scambio dati.

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
│
├── conf/                           # Configurazione
│   ├── mqtt_conf_params.py        # Parametri MQTT e soglie cliniche
│   └── patient_config.json        # Profilo paziente (ISF, target, ecc.)
│
├── model/                          # Modelli dati
│   ├── glucose_sensor_data.py     
│   ├── glucose_simulation_logic.py 
│   ├── insulin_pump_data.py       
│   └── patient_descriptor.py      
│
├── process/                        # Processi MQTT
│   ├── glucose_sensor_producer.py
│   ├── insulin_pump_actuator.py 
│   ├── data_collector_consumer.py
│   └── notification_manager.py
│
├── utils/                          # Utilità
│   └── senml_helper.py            
│
├── dashboard/                      # Web Dashboard
│   ├── web_dashboard.py
│   └── templates/
│       └── dashboard.html
│
├── requirements.txt               
├── .gitignore
└── README.md
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

