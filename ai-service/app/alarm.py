from dataclasses import dataclass, field
from math import isfinite

from .events import EventLog
from .models import State, Status


@dataclass(frozen=True)
class Operator:
    identifier: str
    role: str


@dataclass(frozen=True)
class AlarmConfig:
    enabled: bool = True
    delay: float = 1.0
    pulse: float = 0.5
    cooldown: float = 5.0
    states: frozenset[State] = field(default_factory=lambda: frozenset({
        State.INCONCLUSIVE, State.IRREGULAR, State.CAMERA_FAILURE,
        State.SENSOR_FAILURE, State.PROCESSING_FAILURE,
    }))

    def __post_init__(self) -> None:
        if any(not isfinite(v) for v in (self.delay, self.pulse, self.cooldown)):
            raise ValueError("Tempos do alarme devem ser finitos.")
        if self.delay < 0 or self.pulse <= 0 or self.cooldown < self.pulse:
            raise ValueError("Atraso >= 0; pulso > 0; intervalo >= pulso.")


class Alarm:
    def __init__(self, events: EventLog, config: AlarmConfig | None = None) -> None:
        self.events = events
        self.config = config or AlarmConfig()
        self.signature: tuple[str | None, State, str] | None = None
        self.since = 0.0
        self.last_trigger = float("-inf")
        self.until = float("-inf")
        self.acknowledged = False

    def update(self, now: float, status: Status) -> bool:
        signature = (status.session_id, status.state, status.reason)
        if not self.config.enabled or status.state not in self.config.states:
            self.signature = None
            self.until = float("-inf")
            self.acknowledged = False
            return False
        if signature != self.signature:
            self.signature = signature
            self.since = now
            self.until = float("-inf")
            self.acknowledged = False
        if self.acknowledged:
            return False
        if now - self.since >= self.config.delay and now - self.last_trigger >= self.config.cooldown:
            self.last_trigger = now
            self.until = now + self.config.pulse
            self.events.record(now, status.session_id, "ALARME_ACIONADO",
                               status.state, status.reason, "alarme_simulado")
        return now < self.until

    def acknowledge(self, now: float, operator: Operator) -> None:
        # O futuro backend deve derivar este perfil da sessão autenticada.
        # A CLI apenas demonstra autorização; não autentica identidades.
        if operator.role not in {"operador", "administrador"} or not operator.identifier.strip():
            raise PermissionError("Reconhecimento exige operador autorizado.")
        if self.signature is None:
            raise ValueError("Não há incidente para reconhecer.")
        session_id, state, reason = self.signature
        if not self.acknowledged:
            self.events.record(now, session_id, "ALARME_RECONHECIDO", state,
                               reason, "operador_local", actor=operator.identifier)
        self.acknowledged = True
        self.until = float("-inf")
