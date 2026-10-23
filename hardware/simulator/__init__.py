from dataclasses import dataclass, replace

from app.models import Evidence, Frame, Helmet, SensorReading


@dataclass
class SimulatedCamera:
    sequence: int = 0
    available: bool = True

    def read(self, now: float, **changes: object) -> Frame:
        self.sequence += 1
        frame = Frame(
            self.sequence, now, camera_ok=self.available,
            apron=Evidence.PRESENT, left_glove=Evidence.PRESENT,
            right_glove=Evidence.PRESENT, respirator=Evidence.PRESENT,
            helmet=Helmet.UP,
        )
        return replace(frame, **changes)


@dataclass
class SimulatedTorchSensor:
    removed: bool = False
    available: bool = True

    def read(self, now: float) -> SensorReading:
        return SensorReading(now, self.removed, self.available)
