from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Outputs:
    green: bool = False
    red: bool = False
    alarm: bool = False


class SignalingDevice(Protocol):
    def apply(self, outputs: Outputs) -> None: ...


class SimulatedSignals:
    def __init__(self) -> None:
        self.outputs = Outputs()
        self.available = True

    def apply(self, outputs: Outputs) -> None:
        if not self.available:
            self.outputs = Outputs(green=False, red=True)
            raise OSError("Dispositivo simulado indisponível.")
        if outputs.green and outputs.red:
            raise ValueError("As luzes não podem indicar estados contraditórios.")
        self.outputs = outputs

    def emergency_off(self) -> None:
        self.outputs = Outputs(green=False, red=True)
