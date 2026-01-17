import random
from conf.SystemConfiguration import SystemConfig as Config
class GlucoseSimulationLogic:
    """
    Contiene la logica per generare la variazione (incremento/decremento)
    della glicemia in base alla modalità di simulazione.
    """

    @staticmethod
    def generate_variation(current_value: float, simulation_mode: str) -> float:
        if simulation_mode == "normal":
            # Simula una lenta deriva casuale (Random Walk)
            return random.uniform(Config.SIM_NORMAL_MIN, Config.SIM_NORMAL_MAX)

        elif simulation_mode == "hypoglycemia":
            v = random.uniform(Config.SIM_HYPO_DOWN_MIN, Config.SIM_HYPO_DOWN_MAX)
            if random.random() < Config.SIM_HYPO_UP_PROBABILITY: # Possibile piccolo rialzo
                v = random.uniform(Config.SIM_HYPO_UP_MIN, Config.SIM_HYPO_UP_MAX)
            return v

        elif simulation_mode == "hyperglycemia":
            v = random.uniform(Config.SIM_HYPER_UP_MIN, Config.SIM_HYPER_UP_MAX)
            if random.random() < Config.SIM_HYPER_DOWN_PROBABILITY: # Possibile piccolo ribasso
                v = random.uniform(Config.SIM_HYPER_DOWN_MIN, Config.SIM_HYPER_DOWN_MAX)
            return v

        elif simulation_mode == "fluctuating":
            # Variazioni molto ampie
            return random.uniform(Config.SIM_FLUCTUATING_MIN, Config.SIM_FLUCTUATING_MAX)

        # Fallback generico
        return random.uniform(Config.SIM_FALLBACK_MIN, Config.SIM_FALLBACK_MAX)

    @staticmethod
    def calculate_insulin_effect(active_insulin_doses: list, isf: float, current_time: float,
                                 reading_interval: float) -> float:
        """
        Calcola l'effetto di abbassamento della glicemia dovuto all'insulina attiva.

        Args:
            active_insulin_doses: Lista di {'amount': X, 'start_time': Y}
            isf: Fattore di Sensibilità all'Insulina (mg/dL per Unità)
            current_time: Tempo corrente
            reading_interval: Intervallo di lettura in secondi

        Returns:
            La variazione negativa di glicemia (mg/dL) da applicare.
        """

        # Tempo di azione dell'insulina
        INSULIN_DURATION = Config.INSULIN_ACTION_DURATION_SECONDS

        total_effect = 0.0
        new_active_doses = []

        # Calcola l'effetto di ogni dose attiva
        for dose in active_insulin_doses:
            elapsed = current_time - dose['start_time']

            if elapsed < INSULIN_DURATION:
                # Calcoliamo la riduzione potenziale in mg/dL per l'intero bolo
                total_glucose_reduction = dose['amount'] * isf

                # Calcoliamo la percentuale di effetto nel solo intervallo di lettura
                # Applichiamo una riduzione uniforme su tutta la durata
                reduction_per_interval = total_glucose_reduction * (reading_interval / INSULIN_DURATION)

                total_effect -= reduction_per_interval
                new_active_doses.append(dose)
            # Se elapsed >= INSULIN_DURATION, la dose viene "dimenticata"

        # Aggiorna la lista di dosi attive (rimuove le scadute)
        active_insulin_doses[:] = new_active_doses

        # Limita la riduzione per evitare crolli improvvisi (safety guard interna)
        return max(-30.0, total_effect)