import random

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