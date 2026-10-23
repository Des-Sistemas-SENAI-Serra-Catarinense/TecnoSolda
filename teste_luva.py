"""Abra com python teste_luva.py. Mostra se a mão está com luva de raspa ou sem luva.
Ensaio visual local, calibrado ao vivo, sem treino e sem sinalização física."""
from teste_presenca import PresenceSpec, run

SPEC = PresenceSpec(
    item="luva",
    title="Teste da luva de raspa",
    placement_hint="Mostre a mão bem à frente, ocupando boa parte da imagem.",
    variation_hint="variando posição e ângulo da mão",
)

if __name__ == "__main__":
    run(SPEC)
