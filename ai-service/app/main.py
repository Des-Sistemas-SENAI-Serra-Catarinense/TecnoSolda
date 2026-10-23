import argparse
import json
import sys
from dataclasses import asdict

from hardware.signaling import SimulatedSignals
from hardware.simulator import SimulatedCamera, SimulatedTorchSensor

from .alarm import Operator
from .controller import Controller, Result
from .models import Evidence, Helmet

SCENARIOS = (
    "fluxo", "perda-visibilidade", "falha-camera", "falha-sensor",
    "falha-processamento", "luva-oculta", "luva-ausente",
    "troca-pessoa", "quadros-expirados", "falha-sinalizacao",
)


class Simulation:
    def __init__(self) -> None:
        self.now = 0.0
        self.camera = SimulatedCamera()
        self.sensor = SimulatedTorchSensor()
        self.signals = SimulatedSignals()
        self.controller = Controller(self.signals)

    def step(self, advance: float = 0.2, capture: bool = True, **changes: object) -> Result:
        self.now = round(self.now + advance, 6)
        frame = self.camera.read(self.now, **changes) if capture else None
        return self.controller.step(self.now, self.sensor.read(self.now), frame)

    def report(self, label: str, **changes: object) -> Result:
        result = self.step(**changes)
        print(json.dumps({"simulacao": True, "passo": label, "tempo": self.now,
                          **asdict(result)}, ensure_ascii=False))
        return result

    def verify(self) -> None:
        for _ in range(self.controller.engine.config.stable_frames):
            self.report("respirador visível / máscara levantada")
        for _ in range(self.controller.engine.config.stable_frames):
            self.report("máscara abaixada / respirador oculto",
                        helmet=Helmet.DOWN, respirator=Evidence.UNKNOWN)


def run_scenario(name: str, show_events: bool) -> None:
    simulation = Simulation()
    simulation.report("aguardando")
    simulation.sensor.removed = True
    simulation.verify()
    changes: dict[str, object] = {"helmet": Helmet.DOWN, "respirator": Evidence.UNKNOWN}
    if name == "perda-visibilidade":
        changes["person_visible"] = False
    elif name == "falha-camera":
        simulation.camera.available = False
    elif name == "falha-sensor":
        simulation.sensor.available = False
    elif name == "falha-processamento":
        changes["processing_ok"] = False
    elif name == "luva-oculta":
        changes["right_glove"] = Evidence.UNKNOWN
    elif name == "luva-ausente":
        changes["right_glove"] = Evidence.ABSENT
    elif name == "troca-pessoa":
        changes["track_id"] = "outro-track-simulado"
    elif name == "quadros-expirados":
        changes.update(capture=False, advance=1.0)
    elif name == "falha-sinalizacao":
        simulation.signals.available = False

    if name != "fluxo":
        for _ in range(10):
            simulation.report(name, **changes)
        simulation.camera.available = simulation.sensor.available = simulation.signals.available = True
        simulation.report("retorno ainda com máscara abaixada",
                          helmet=Helmet.DOWN, respirator=Evidence.UNKNOWN)
        simulation.verify()

    simulation.sensor.removed = False
    simulation.report("tocha devolvida")
    simulation.sensor.removed = True
    simulation.report("nova sessão exige respirador novamente",
                      helmet=Helmet.DOWN, respirator=Evidence.UNKNOWN)
    simulation.sensor.removed = False
    simulation.report("encerramento")
    if show_events:
        print(json.dumps({"eventos": simulation.controller.engine.events.as_dicts()},
                         ensure_ascii=False, indent=2))


def interactive(operator: Operator) -> None:
    simulation = Simulation()
    print("SIMULAÇÃO LOCAL — sem câmera, IA ou GPIO reais.")
    print("Comandos: retirar, devolver, cima, baixo, oculto, luva-oculta,")
    print("luva-ausente, camera-falha, sensor-falha, processamento-falha,")
    print("sinal-falha, recuperar, tick, reconhecer, eventos, sair.")
    print("Cada comando de observação avança um quadro (0,2 s). Use 3 cima e 3 baixo.")
    print("O tempo é virtual: esperar no terminal não avança o watchdog.")
    changes: dict[str, object] = {}
    while True:
        try:
            command = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            command = "sair"
        if command == "sair":
            simulation.sensor.available = True
            simulation.sensor.removed = False
            simulation.report("encerramento")
            return
        if command == "eventos":
            print(json.dumps(simulation.controller.engine.events.as_dicts(),
                             ensure_ascii=False, indent=2))
            continue
        if command == "reconhecer":
            try:
                simulation.controller.acknowledge(operator)
                print("Incidente reconhecido; a avaliação visual permanece inalterada.")
            except (PermissionError, ValueError, OSError) as error:
                print(str(error))
            continue
        if command == "retirar":
            simulation.sensor.removed = True
        elif command == "devolver":
            simulation.sensor.removed = False
        elif command == "cima":
            changes = {"helmet": Helmet.UP}
        elif command == "baixo":
            changes = {"helmet": Helmet.DOWN, "respirator": Evidence.UNKNOWN}
        elif command == "oculto":
            changes["person_visible"] = False
        elif command == "luva-oculta":
            changes["right_glove"] = Evidence.UNKNOWN
        elif command == "luva-ausente":
            changes["right_glove"] = Evidence.ABSENT
        elif command == "camera-falha":
            simulation.camera.available = False
        elif command == "sensor-falha":
            simulation.sensor.available = False
        elif command == "processamento-falha":
            changes["processing_ok"] = False
        elif command == "sinal-falha":
            simulation.signals.available = False
        elif command == "recuperar":
            simulation.camera.available = simulation.sensor.available = simulation.signals.available = True
            changes = {}
        elif command == "tick":
            simulation.report("watchdog sem novos quadros", capture=False, advance=1.0)
            continue
        else:
            print("Comando desconhecido.")
            continue
        simulation.report(command, **changes)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Protótipo local com câmera e dispositivos simulados.")
    parser.add_argument("--scenario", choices=SCENARIOS, default="fluxo")
    parser.add_argument("--events", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--operator", default="operador-simulado")
    parser.add_argument("--role", choices=("visitante", "operador", "administrador"), default="visitante")
    args = parser.parse_args()
    if args.interactive:
        interactive(Operator(args.operator, args.role))
    else:
        run_scenario(args.scenario, args.events)
