from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Event:
    sequence: int
    occurred_at: str
    elapsed: float
    booth: str
    session_id: str | None
    kind: str
    state: str
    reason: str
    origin: str
    epi: str | None = None
    review: str = "PENDENTE"
    actor: str | None = None


class EventLog:
    """Memória limitada, sem imagens, nomes de alunos ou persistência implícita."""

    def __init__(self, capacity: int = 1000) -> None:
        if capacity <= 0:
            raise ValueError("Capacidade deve ser positiva.")
        self.events: deque[Event] = deque(maxlen=capacity)
        self.sequence = 0

    def record(self, now: float, session_id: str | None, kind: str,
               state: str, reason: str, origin: str = "motor",
               epi: str | None = None, actor: str | None = None) -> None:
        self.sequence += 1
        self.events.append(Event(
            self.sequence, datetime.now(timezone.utc).isoformat(), now,
            "cabine-01", session_id, kind, state, reason, origin, epi, actor=actor,
        ))

    def as_dicts(self) -> list[dict]:
        return [asdict(event) for event in self.events]
