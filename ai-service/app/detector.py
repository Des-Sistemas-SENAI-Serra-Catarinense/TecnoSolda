from typing import Protocol

from .models import Frame


class Detector(Protocol):
    """Futuro adaptador OpenCV/YOLO: não existe modelo treinado nesta versão.

    Deve associar EPIs a uma pessoa, distinguir mãos e estimar posição da
    máscara. Apenas não detectar uma classe deve resultar em UNKNOWN.
    """

    def observe(self, image: object, sequence: int, captured_at: float) -> Frame: ...
