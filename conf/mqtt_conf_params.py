class MqttConfigurationParameters(object):
    """
    Classe per la configurazione dei parametri MQTT del sistema di monitoraggio glicemia
    """

    # Configurazione Broker MQTT (usa un broker locale o pubblico per test)
    BROKER_ADDRESS = "localhost"  # Cambia con il tuo broker MQTT
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

    # Intervalli di tempo (secondi)
    GLUCOSE_READING_INTERVAL = 10  # Ogni 5 secondi (CGM realistico: 1-5 min)
    PUMP_STATUS_INTERVAL = 30  # Status pompa ogni 30 secondi

    # Soglie glicemia (mg/dL)
    GLUCOSE_LOW_THRESHOLD = 70  # Ipoglicemia
    GLUCOSE_HIGH_THRESHOLD = 180  # Iperglicemia
    GLUCOSE_CRITICAL_LOW = 50  # Ipoglicemia severa
    GLUCOSE_CRITICAL_HIGH = 250  # Iperglicemia severa

    # Parametri insulina
    INSULIN_UNITS_PER_CARB = 1.0 / 15.0  # 1 unità per 15g carboidrati
    INSULIN_CORRECTION_FACTOR = 50  # 1 unità riduce glicemia di 50 mg/dL, alzato solo per test
    TARGET_GLUCOSE = 100  # Target glicemico