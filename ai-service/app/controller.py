from dataclasses import dataclass

from hardware.signaling import Outputs, SignalingDevice

from .alarm import Alarm, AlarmConfig, Operator
from .models import Frame, SensorReading, Status
from .safety_rules import SafetyEngine


@dataclass(frozen=True)
class Result:
    status: Status
    outputs: Outputs
    signaling_ok: bool


class Controller:
    """Orquestração serial. Não conectar este protótipo a dispositivos reais."""

    def __init__(self, device: SignalingDevice, engine: SafetyEngine | None = None,
                 alarm_config: AlarmConfig | None = None) -> None:
        self.engine = engine if engine is not None else SafetyEngine()
        self.device = device
        self.alarm = Alarm(self.engine.events, alarm_config)

    def step(self, now: float, sensor: SensorReading,
             frame: Frame | None = None, camera_available: bool = True) -> Result:
        try:
            status = self.engine.step(now, sensor, frame, camera_available=camera_available)
        except Exception:
            status = self.engine.technical_failure("excecao_de_processamento")
        active_alarm = self.alarm.update(self.engine.last_now, status)
        outputs = Outputs(status.green, status.red, active_alarm)
        try:
            self.device.apply(outputs)
        except Exception:
            status = self.engine.technical_failure("sinalizacao_indisponivel")
            self.alarm.update(self.engine.last_now, status)
            outputs = Outputs(False, True, False)
            try:
                self.device.apply(outputs)
            except Exception:
                pass  # Saída física desconhecida: nunca afirmar sucesso de escrita.
            return Result(status, outputs, False)
        return Result(status, outputs, True)

    def acknowledge(self, operator: Operator) -> None:
        self.alarm.acknowledge(self.engine.last_now, operator)
        status = self.engine.snapshot()
        try:
            self.device.apply(Outputs(status.green, status.red, False))
        except Exception:
            self.engine.technical_failure("sinalizacao_indisponivel")
            raise
