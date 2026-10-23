"""Abra com python teste_avental.py. Mostra se a pessoa está com avental ou sem avental.
Ensaio visual local, calibrado ao vivo, sem treino e sem sinalização física."""
from teste_presenca import PresenceSpec, run

SPEC = PresenceSpec(
    item="avental",
    title="Teste do avental",
    placement_hint="Fique de frente para a câmera com o tronco visível, ocupando boa parte da imagem.",
    variation_hint="variando levemente a posição e a inclinação do corpo",
)

if __name__ == "__main__":
    run(SPEC)
