from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class Session:
    started_at: float
    id: str = field(default_factory=lambda: str(uuid4()))
    track_id: str | None = None
    initial_verified: bool = False
    respirator_verified: bool = False

    def invalidate(self) -> None:
        self.initial_verified = False
        self.respirator_verified = False
        self.track_id = None
