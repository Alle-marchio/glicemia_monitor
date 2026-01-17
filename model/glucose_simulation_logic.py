import random
from conf.SystemConfiguration import SystemConfig as Config
class GlucoseSimulationLogic:
    """
    Contiene la logica per generare la variazione (incremento/decremento)
    della glicemia in base alla modalità di simulazione.
    """

    #parte assolutamente da cambiare
    @staticmethod
    def generate_variation(current_value: float, simulation_mode: str) -> float:
        """Genera una variazione in base alla modalità scelta."""

        if simulation_mode == "normal":
            # Simula una lenta deriva casuale (Random Walk) tipica di un diabetico
            return random.uniform(-3, 3)

        elif simulation_mode == "hypoglycemia":
            # Forte tendenza alla discesa, con piccola probabilità di rialzo
            v = random.uniform(-8, -2)
            if random.random() < 0.1: # 10% di probabilità di un piccolo rialzo
                v = random.uniform(2, 8)
            return v

        elif simulation_mode == "hyperglycemia":
            # Forte tendenza alla salita, con piccola probabilità di discesa
            v = random.uniform(2, 10)
            if random.random() < 0.1: # 10% di probabilità di un piccolo ribasso
                v = random.uniform(-8, -2)
            return v

        elif simulation_mode == "fluctuating":
            # Variazioni casuali molto ampie
            return random.uniform(-15, 15)

        return random.uniform(-7, 7) # Fallback

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

        # Limita la riduzione per non avere crolli iperbolici in un singolo intervallo
        return max(-30.0, total_effect)