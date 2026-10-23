from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class Evidence(StrEnum):
    PRESENT = "PRESENTE"
    ABSENT = "AUSENCIA_OBSERVADA"
    UNKNOWN = "INCONCLUSIVO"


class Helmet(StrEnum):
    UP = "LEVANTADA"
    DOWN = "ABAIXADA"
    UNKNOWN = "INCONCLUSIVO"


class State(StrEnum):
    WAITING = "AGUARDANDO_TOCHA"
    CHECKING = "VERIFICANDO_EPIS"
    WAIT_HELMET = "AGUARDANDO_MASCARA_ABAIXADA"
    COMPLIANT = "CONFORME_VISUAL"
    INCONCLUSIVE = "INCONCLUSIVO"
    IRREGULAR = "POSSIVEL_IRREGULARIDADE"
    CAMERA_FAILURE = "CAMERA_INDISPONIVEL"
    SENSOR_FAILURE = "SENSOR_INDISPONIVEL"
    PROCESSING_FAILURE = "FALHA_PROCESSAMENTO"


@dataclass(frozen=True)
class Frame:
    """Observação de UMA câmera; ausência de detecção deve virar UNKNOWN.

    track_id é um identificador efêmero, sem biometria. Luvas são evidências
    independentes já associadas às mãos da mesma pessoa pelo futuro adaptador.
    """
    sequence: int
    captured_at: float
    track_id: str | None = "track-simulado"
    person_visible: bool = True
    person_count: int = 1
    tracking_reliable: bool = True
    camera_ok: bool = True
    processing_ok: bool = True
    apron: Evidence = Evidence.UNKNOWN
    left_glove: Evidence = Evidence.UNKNOWN
    right_glove: Evidence = Evidence.UNKNOWN
    respirator: Evidence = Evidence.UNKNOWN
    helmet: Helmet = Helmet.UNKNOWN

    def __post_init__(self) -> None:
        if self.sequence < 0 or not isfinite(self.captured_at):
            raise ValueError("Quadro deve ter sequência não negativa e horário finito.")
        if self.person_count < 0:
            raise ValueError("Quantidade de pessoas inválida.")
        if not all(isinstance(value, Evidence) for value in (
            self.apron, self.left_glove, self.right_glove, self.respirator
        )) or not isinstance(self.helmet, Helmet):
            raise ValueError("Evidências devem usar os enums tipados.")


@dataclass(frozen=True)
class SensorReading:
    sampled_at: float
    torch_removed: bool
    available: bool = True

    def __post_init__(self) -> None:
        if not isfinite(self.sampled_at):
            raise ValueError("Horário do sensor inválido.")


@dataclass(frozen=True)
class Config:
    stable_frames: int = 3
    missing_frames: int = 3
    frame_timeout: float = 0.75
    sensor_timeout: float = 1.0

    def __post_init__(self) -> None:
        if self.stable_frames < 2 or self.missing_frames < 2:
            raise ValueError("A confirmação exige múltiplos quadros.")
        if any(not isfinite(v) or v <= 0 for v in (
            self.frame_timeout, self.sensor_timeout
        )):
            raise ValueError("Timeouts devem ser positivos e finitos.")


@dataclass(frozen=True)
class Status:
    state: State
    reason: str
    session_id: str | None
    green: bool
    red: bool
    respirator_verified: bool
    initial_verified: bool
    torch_removed: bool | None
    camera_ok: bool
    helmet: Helmet
    apron: Evidence
    left_glove: Evidence
    right_glove: Evidence
    respirator: Evidence
