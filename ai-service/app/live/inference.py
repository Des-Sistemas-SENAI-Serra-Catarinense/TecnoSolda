from dataclasses import dataclass, replace
from typing import Literal, Protocol

from ..models import Evidence, Frame, Helmet

Mode = Literal["off", "raised", "lowered", "missing_glove", "hidden_glove", "occluded", "unavailable"]


@dataclass(frozen=True)
class Box:
    label: str
    confidence: float | None
    xyxy: tuple[float, float, float, float]
    assessment: Literal["confirmed", "irregular", "inconclusive"]
    simulated: bool = True


@dataclass(frozen=True)
class Inference:
    observation: Frame
    boxes: tuple[Box, ...]
    simulated: bool


class LiveDetector(Protocol):
    def infer(self, image: object, sequence: int, captured_at: float, mode: Mode) -> Inference: ...


class SimulatedDetector:
    """Caixas ilustrativas fixas. NÃO inspeciona os pixels nem detecta pessoas/EPIs."""

    def infer(self, image: object, sequence: int, captured_at: float, mode: Mode) -> Inference:
        frame = Frame(
            sequence, captured_at, track_id="simulacao-explicita",
            apron=Evidence.PRESENT, left_glove=Evidence.PRESENT,
            right_glove=Evidence.PRESENT, respirator=Evidence.PRESENT,
            helmet=Helmet.UP,
        )
        if mode in {"off", "unavailable"}:
            return Inference(replace(frame, processing_ok=False, track_id=None,
                                     person_visible=False, person_count=0,
                                     apron=Evidence.UNKNOWN, left_glove=Evidence.UNKNOWN,
                                     right_glove=Evidence.UNKNOWN, respirator=Evidence.UNKNOWN,
                                     helmet=Helmet.UNKNOWN), (), True)
        if mode == "occluded":
            return Inference(replace(frame, person_visible=False, person_count=0), (), True)
        lowered = mode in {"lowered", "missing_glove", "hidden_glove"}
        if lowered:
            frame = replace(frame, helmet=Helmet.DOWN, respirator=Evidence.UNKNOWN)
        glove_status = "confirmed"
        glove_confidence = 0.95
        if mode == "missing_glove":
            frame = replace(frame, right_glove=Evidence.ABSENT)
            glove_status, glove_confidence = "irregular", None
        if mode == "hidden_glove":
            frame = replace(frame, right_glove=Evidence.UNKNOWN)
            glove_status, glove_confidence = "inconclusive", None
        boxes = [
            Box("Avental de soldagem", 0.97, (0.30, 0.40, 0.69, 0.92), "confirmed"),
            Box("Luva esquerda", 0.96, (0.17, 0.57, 0.31, 0.77), "confirmed"),
            Box("Luva direita", glove_confidence, (0.69, 0.57, 0.83, 0.77), glove_status),
            Box("Mascara " + ("abaixada" if lowered else "levantada"),
                0.98, (0.37, 0.12, 0.63, 0.39), "confirmed"),
        ]
        if not lowered:
            boxes.append(Box("Respirador com valvula", 0.94, (0.43, 0.29, 0.57, 0.40), "confirmed"))
        return Inference(frame, tuple(boxes), True)
