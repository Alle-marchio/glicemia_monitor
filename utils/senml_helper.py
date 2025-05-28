import json
import time
from typing import List, Dict, Any, Union


class SenMLHelper:
    """
    Classe helper per creare e gestire messaggi in formato SenML (Sensor Markup Language)
    Seguendo la specifica RFC 8428
    """

    @staticmethod
    def create_glucose_measurement(patient_id: str, glucose_value: float,
                                   trend: str = "stable", timestamp: float = None) -> str:
        """
        Crea un messaggio SenML per una misurazione della glicemia

        Args:
            patient_id: ID del paziente
            glucose_value: Valore glicemia in mg/dL
            trend: Tendenza ("rising", "falling", "stable")
            timestamp: Timestamp UNIX (se None, usa tempo corrente)

        Returns:
            Stringa JSON in formato SenML
        """
        if timestamp is None:
            timestamp = time.time()

        base_name = f"urn:patient:{patient_id}:glucose:"

        senml_record = [
            {
                "bn": base_name,  # Base Name
                "bt": timestamp,  # Base Time
                "bu": "mg/dL"  # Base Unit
            },
            {
                "n": "level",  # Name
                "v": glucose_value,  # Value
                "t": 0  # Time offset from base time
            },
            {
                "n": "trend",  # Name
                "vs": trend  # Value String
            }
        ]

        return json.dumps(senml_record)

    @staticmethod
    def create_insulin_command(patient_id: str, units: float,
                               command_type: str = "bolus", timestamp: float = None) -> str:
        """
        Crea un comando SenML per la pompa di insulina

        Args:
            patient_id: ID del paziente
            units: Unità di insulina da erogare
            command_type: Tipo comando ("bolus", "basal", "stop")
            timestamp: Timestamp UNIX

        Returns:
            Stringa JSON in formato SenML
        """
        if timestamp is None:
            timestamp = time.time()

        base_name = f"urn:patient:{patient_id}:insulin:"

        senml_record = [
            {
                "bn": base_name,
                "bt": timestamp,
                "bu": "U"  # Units (unità di insulina)
            },
            {
                "n": "dose",
                "v": units,
                "t": 0
            },
            {
                "n": "command",
                "vs": command_type
            }
        ]

        return json.dumps(senml_record)

    @staticmethod
    def create_pump_status(patient_id: str, reservoir_level: float,
                           battery_level: float, status: str = "active",
                           timestamp: float = None) -> str:
        """
        Crea un messaggio SenML per lo status della pompa

        Args:
            patient_id: ID del paziente
            reservoir_level: Livello serbatoio insulina (unità)
            battery_level: Livello batteria (%)
            status: Status pompa ("active", "alarm", "stopped")
            timestamp: Timestamp UNIX

        Returns:
            Stringa JSON in formato SenML
        """
        if timestamp is None:
            timestamp = time.time()

        base_name = f"urn:patient:{patient_id}:pump:"

        senml_record = [
            {
                "bn": base_name,
                "bt": timestamp
            },
            {
                "n": "reservoir",
                "v": reservoir_level,
                "u": "U",  # Units
                "t": 0
            },
            {
                "n": "battery",
                "v": battery_level,
                "u": "%",
                "t": 0
            },
            {
                "n": "status",
                "vs": status,
                "t": 0
            }
        ]

        return json.dumps(senml_record)

    @staticmethod
    def create_notification_alert(patient_id: str, alert_type: str,
                                  message: str, severity: str = "medium",
                                  timestamp: float = None) -> str:
        """
        Crea un alert/notifica in formato SenML

        Args:
            patient_id: ID del paziente
            alert_type: Tipo alert ("hypoglycemia", "hyperglycemia", "pump_alarm")
            message: Messaggio descrittivo
            severity: Gravità ("low", "medium", "high", "critical")
            timestamp: Timestamp UNIX

        Returns:
            Stringa JSON in formato SenML
        """
        if timestamp is None:
            timestamp = time.time()

        base_name = f"urn:patient:{patient_id}:alert:"

        senml_record = [
            {
                "bn": base_name,
                "bt": timestamp
            },
            {
                "n": "type",
                "vs": alert_type,
                "t": 0
            },
            {
                "n": "message",
                "vs": message,
                "t": 0
            },
            {
                "n": "severity",
                "vs": severity,
                "t": 0
            }
        ]

        return json.dumps(senml_record)

    @staticmethod
    def parse_senml(senml_json: str) -> Dict[str, Any]:
        """
        Parse un messaggio SenML e restituisce i dati in formato dizionario

        Args:
            senml_json: Stringa JSON in formato SenML

        Returns:
            Dizionario con i dati parsati
        """
        try:
            senml_data = json.loads(senml_json)

            if not isinstance(senml_data, list) or len(senml_data) == 0:
                raise ValueError("Invalid SenML format")

            # Estrai base fields dal primo record
            base_record = senml_data[0]
            base_name = base_record.get("bn", "")
            base_time = base_record.get("bt", time.time())
            base_unit = base_record.get("bu", "")

            parsed_data = {
                "base_name": base_name,
                "base_time": base_time,
                "base_unit": base_unit,
                "measurements": {}
            }

            # Parse tutti i record di misurazione
            for record in senml_data[1:]:  # Salta il primo record (base)
                name = record.get("n", "")
                time_offset = record.get("t", 0)

                if "v" in record:  # Valore numerico
                    parsed_data["measurements"][name] = {
                        "value": record["v"],
                        "timestamp": base_time + time_offset,
                        "unit": record.get("u", base_unit)
                    }
                elif "vs" in record:  # Valore stringa
                    parsed_data["measurements"][name] = {
                        "value": record["vs"],
                        "timestamp": base_time + time_offset,
                        "type": "string"
                    }

            return parsed_data

        except Exception as e:
            raise ValueError(f"Error parsing SenML: {str(e)}")

    @staticmethod
    def validate_senml(senml_json: str) -> bool:
        """
        Valida se una stringa JSON è un formato SenML valido

        Args:
            senml_json: Stringa JSON da validare

        Returns:
            True se valido, False altrimenti
        """
        try:
            SenMLHelper.parse_senml(senml_json)
            return True
        except:
            return False