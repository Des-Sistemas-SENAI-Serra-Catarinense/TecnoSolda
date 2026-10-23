from typing import Protocol

from .models import Frame


class Camera(Protocol):
    """Uma fonte frontal; read não deve bloquear o watchdog."""

    def read(self, now: float) -> Frame | None: ...
