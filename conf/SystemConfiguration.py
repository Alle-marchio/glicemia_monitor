class SystemConfig(object):
    # ---------------------------------------------------------------------
    # Configurazione Broker MQTT
    # ---------------------------------------------------------------------
    BROKER_ADDRESS = "localhost"
    BROKER_PORT = 1883
    MQTT_USERNAME = "glicemia_user"  # Il tuo username
    MQTT_PASSWORD = "glicemia_pass"  # La tua password

    # Topic base per il paziente
    MQTT_BASIC_TOPIC = "/iot/patient/{0}".format(MQTT_USERNAME)

    # Topic specifici per i componenti
    GLUCOSE_TOPIC = "glucose"
    GLUCOSE_SENSOR_TOPIC = "sensor"
    GLUCOSE_DATA_TOPIC = "data"

    INSULIN_TOPIC = "insulin"
    INSULIN_PUMP_TOPIC = "pump"
    INSULIN_COMMAND_TOPIC = "command"
    INSULIN_STATUS_TOPIC = "status"

    NOTIFICATIONS_TOPIC = "notifications"
    ALERT_TOPIC = "alert"

    PATIENT_INFO_TOPIC = "info"

    # QoS Levels
    QOS_SENSOR_DATA = 1  # At least once per dati critici
    QOS_COMMANDS = 2  # Exactly once per comandi
    QOS_NOTIFICATIONS = 1  # At least once per notifiche

    # Retained Messages
    RETAIN_PATIENT_INFO = True
    RETAIN_PUMP_STATUS = True

    # ---------------------------------------------------------------------
    # Intervalli di Tempo (secondi)
    # ---------------------------------------------------------------------
    GLUCOSE_READING_INTERVAL = 10  # Ogni 5 secondi (CGM realistico: 1-5 min)
    PUMP_STATUS_INTERVAL = 30  # Status pompa ogni 30 secondi
    INSULIN_ACTION_DURATION_SECONDS = 60 #durata azione insulina

    # ---------------------------------------------------------------------
    # Soglie Glicemia (mg/dL)
    # ---------------------------------------------------------------------
    GLUCOSE_LOW_THRESHOLD = 70  # Ipoglicemia
    GLUCOSE_HIGH_THRESHOLD = 180  # Iperglicemia
    GLUCOSE_CRITICAL_LOW = 50  # Ipoglicemia severa
    GLUCOSE_CRITICAL_HIGH = 250  # Iperglicemia severa
    TARGET_GLUCOSE = 100  # Target glicemico

    INSULIN_CORRECTION_FACTOR = 50  # 1 unità riduce glicemia di 50 mg/dL

    # ---------------------------------------------------------------------
    # Parametri Sensore Glicemia
    # ---------------------------------------------------------------------
    SENSOR_MIN_VALUE = 40.0  # Limite fisico minimo
    SENSOR_MAX_VALUE = 400.0  # Limite fisico massimo

    # Parametri segnale e batteria sensore
    SENSOR_BATTERY_DRAIN_MIN = 0.1
    SENSOR_BATTERY_DRAIN_MAX = 0.2
    SENSOR_SIGNAL_MIN_DBM = -60
    SENSOR_SIGNAL_MAX_DBM = -40

    # Soglia per definire un trend "in salita/discesa" (mg/dL per intervallo)
    SENSOR_TREND_THRESHOLD = 3.0

    # ---------------------------------------------------------------------
    # Parametri Pompa Insulina
    # ---------------------------------------------------------------------
    PUMP_DEFAULT_CAPACITY = 300.0  # Capacità serbatoio (U)
    PUMP_DEFAULT_BATTERY = 100.0  # Carica iniziale (%)

    # Soglie Allarmi Pompa
    PUMP_ALARM_LOW_INSULIN_PCT = 20.0  # Soglia avviso insulina bassa (%)
    PUMP_ALARM_LOW_BATTERY_PCT = 15.0  # Soglia avviso batteria bassa (%)
    PUMP_ALARM_CRITICAL_BATTERY_PCT = 5.0  # Soglia critica batteria (%)

    # ---------------------------------------------------------------------
    # Parametri di Sicurezza
    # ---------------------------------------------------------------------
    SAFETY_MAX_BOLUS_U = 15.0  # Unità massime per singolo bolo
    SAFETY_MAX_BASAL_RATE_UH = 5.0  # Unità/ora massime per basale
    SAFETY_MIN_CORRECTION_INTERVAL_S = 180  # 3 minuti

    # ---------------------------------------------------------------------
    # Parametri di Simulazione
    # ---------------------------------------------------------------------
    SIM_PUMP_BATTERY_DRAIN_PCT = 0.1  # Scarico batteria per ciclo
    # Range variazioni glicemia (mg/dL) per le diverse modalità
    # Normal (Random Walk)
    SIM_NORMAL_MIN = -3.0
    SIM_NORMAL_MAX = 3.0

    # Hypoglycemia (tendenza a scendere)
    SIM_HYPO_DOWN_MIN = -8.0
    SIM_HYPO_DOWN_MAX = -2.0
    SIM_HYPO_UP_PROBABILITY = 0.1  # 10% probabilità di piccolo rialzo
    SIM_HYPO_UP_MIN = 2.0
    SIM_HYPO_UP_MAX = 8.0

    # Hyperglycemia (tendenza a salire)
    SIM_HYPER_UP_MIN = 2.0
    SIM_HYPER_UP_MAX = 10.0
    SIM_HYPER_DOWN_PROBABILITY = 0.1  # 10% probabilità di piccolo ribasso
    SIM_HYPER_DOWN_MIN = -8.0
    SIM_HYPER_DOWN_MAX = -2.0

    # Fluctuating (instabile)
    SIM_FLUCTUATING_MIN = -15.0
    SIM_FLUCTUATING_MAX = 15.0

    # Fallback generico
    SIM_FALLBACK_MIN = -7.0
    SIM_FALLBACK_MAX = 7.0

    # Configurazioni Dashboard
    DASHBOARD_HISTORY_LIMIT = 30  # Numero massimo di letture da mostrare nel grafico
    DASHBOARD_ALERT_LIMIT = 10  # Numero massimo di alert da mostrare nel log