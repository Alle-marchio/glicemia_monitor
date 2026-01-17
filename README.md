# Sistema IoT per Monitoraggio Glicemia e Gestione Insulina
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![MQTT](https://img.shields.io/badge/MQTT-Paho-orange.svg)](https://www.eclipse.org/paho/)
[![SenML](https://img.shields.io/badge/SenML-RFC%208428-green.svg)](https://tools.ietf.org/html/rfc8428)
[![Flask](https://img.shields.io/badge/Flask-2.3.3-black.svg)](https://flask.palletsprojects.com/)

---

Questo progetto implementa un ecosistema IoT avanzato per il **monitoraggio continuo della glicemia (CGM)** e la **somministrazione automatizzata di insulina** (Closed-Loop System simulato). Il sistema sfrutta il protocollo **MQTT** per la comunicazione tra dispositivi e il formato **SenML** (RFC 8428) per garantire l'interoperabilità e la leggerezza dei dati trasmessi.
## Funzionalità principali

-   **Simulazione Dinamica**: Sensore di glicemia con logiche di variazione naturale, iperglicemia, ipoglicemia e risposta all'insulina.
-   **Controllo Intelligente**: Data Collector che analizza i livelli glicemici e calcola autonomamente le dosi di correzione basandosi sull'Insulin-on-Board (IOB) e sulla sensibilità del paziente.
-   **Sicurezza Avanzata**: Limiti di sicurezza per boli massimi, intervalli minimi tra correzioni e gestione allarmi critici della pompa.
-   **Standard SenML**: Tutti i messaggi (dati, comandi e notifiche) utilizzano il formato standard SenML per una gestione strutturata dei metadati e dei timestamp.
-   **Dashboard Real-time**: Interfaccia web interattiva basata su Flask e Chart.js per visualizzare grafici, stato dei dispositivi e simulare scenari clinici.

---

## Struttura del progetto

```text
glicemia_monitor/
├── conf/                    # Configurazioni di sistema e profilo paziente
│   ├── SystemConfiguration.py   # Soglie cliniche, parametri MQTT e simulazione
│   └── patient_config.json      # Dati bio-fisici e target del paziente
├── model/                   # Logica di business e modelli dati
│   ├── glucose_sensor_data.py   # Modello del sensore (batteria, trend, stato)
│   ├── glucose_simulation_logic.py # Motore di simulazione glicemica
│   ├── insulin_pump_data.py     # Stato pompa e logica erogazione
│   └── patient_descriptor.py    # Profilo clinico e calcolo dosi
├── process/                 # Componenti attivi (Agenti MQTT)
│   ├── glucose_sensor_producer.py # Pubblica letture glicemiche
│   ├── insulin_pump_actuator.py   # Riceve comandi ed eroga insulina
│   ├── data_collector_consumer.py # Il "cervello" del sistema (Closed-Loop)
│   └── notification_manager.py    # Gestore centralizzato degli alert
├── dashboard/               # Interfaccia Utente
│   ├── web_dashboard.py         # Server Flask e client MQTT per la UI
│   ├── templates/               # Layout HTML (Dashboard)
│   └── static/                  # Asset CSS e logiche JS
└── utils/
    └── senml_helper.py          # Utility per parsing e creazione record SenML
```
---

## MQTT Topic Structure

| Topic                                                       | Descrizione                        |
|-------------------------------------------------------------|------------------------------------|
| `/iot/patient/<patient_id>/glucose/sensor/data`            | Letture glicemia, trend e batteria  |
| `/iot/patient/<patient_id>/insulin/pump/command`           | Comandi di erogazione (bolus/basal) |
| `/iot/patient/<patient_id>/insulin/pump/status`            | Stato serbatoio, batteria e allarmi |
| `/iot/patient/<patient_id>/notifications/alert`            | Notifiche di sistema e alert clinici|
| `/iot/patient/<patient_id>/info`                           | Info generali sul paziente(retained)|

---

## Requisiti

Installa le dipendenze con:

```bash
pip install -r requirements.txt

