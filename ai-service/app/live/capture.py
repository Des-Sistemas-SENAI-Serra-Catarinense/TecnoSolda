from collections import deque
from dataclasses import dataclass
import threading
import time
from typing import Any, Protocol

from .inference import Inference, LiveDetector, Mode, SimulatedDetector
from .settings import Settings


class ImageSource(Protocol):
    def read(self) -> Any | None: ...
    def close(self) -> None: ...


class OpenCVCamera:
    """Somente câmera local por índice; não aceita URL nem arquivo como fonte."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.capture: Any = None

    def read(self) -> Any | None:
        import cv2
        if self.capture is None:
            self.capture = cv2.VideoCapture(self.settings.camera_index)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.height)
            self.capture.set(cv2.CAP_PROP_FPS, self.settings.fps)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.capture.isOpened():
            return None
        ok, frame = self.capture.read()
        if not ok or frame is None or frame.size == 0:
            return None
        return frame

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None


@dataclass(frozen=True)
class Packet:
    sequence: int
    captured_at: float
    version: int
    jpeg: bytes
    width: int
    height: int
    fps: float
    pipeline_ms: float
    inference: Inference
    processing_ok: bool


def encode_annotated(image: Any, inference: Inference, active: bool) -> bytes:
    import cv2
    canvas = image.copy()
    height, width = canvas.shape[:2]
    colors = {"confirmed": (80, 210, 100), "irregular": (70, 70, 245),
              "inconclusive": (30, 190, 250)}
    for box in inference.boxes:
        x1, y1, x2, y2 = box.xyxy
        a, b = (int(x1 * width), int(y1 * height)), (int(x2 * width), int(y2 * height))
        color = colors[box.assessment]
        cv2.rectangle(canvas, a, b, color, 2)
        confidence = f"{box.confidence * 100:.0f}%" if box.confidence is not None else "?"
        label = f"SIM | {box.label} | {confidence}"
        cv2.putText(canvas, label, (a[0], max(55, a[1] - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    cv2.rectangle(canvas, (0, 0), (width, 42), (15, 23, 35), -1)
    label = "SIMULACAO DE DETECCOES - NAO VALIDA EPIs" if active else "CAMERA REAL | IA TREINADA NAO INSTALADA"
    cv2.putText(canvas, label, (12, 27), cv2.FONT_HERSHEY_SIMPLEX,
                min(0.58, width / 1150), (60, 200, 255), 1, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 78])
    if not ok:
        raise RuntimeError("Falha ao codificar quadro.")
    return encoded.tobytes()


class CameraPipeline:
    """Um produtor compartilhado; memória guarda só o último quadro, sem gravação.

    Captura/inferência ficam fora do loop HTTP e do watchdog. Um driver bloqueado
    não bloqueia a expiração dos acessos nem mantém verde no estado transmitido.
    """

    def __init__(self, settings: Settings, source: ImageSource | None = None,
                 detector: LiveDetector | None = None) -> None:
        self.settings = settings
        self.source = source or OpenCVCamera(settings)
        self.detector = detector or SimulatedDetector()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.packet: Packet | None = None
        self.problem = "Aguardando câmera."
        self.version = 0
        self.mode: Mode = "off"
        self.torch_removed = False

    def configure(self, removed: bool, mode: Mode) -> int:
        with self.lock:
            self.version += 1
            self.torch_removed, self.mode = removed, mode
            self.packet = None
            return self.version

    def latest(self) -> tuple[Packet | None, str]:
        with self.lock:
            return self.packet, self.problem

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="camera-local", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        # release pertence à thread produtora: nunca disputar um read bloqueado.

    def _run(self) -> None:
        sequence = 0
        timestamps: deque[float] = deque(maxlen=30)
        try:
            while not self.stop_event.is_set():
                start = time.monotonic()
                try:
                    image = self.source.read()
                    if image is None:
                        raise OSError("Câmera desconectada ou sem permissão.")
                    captured = time.monotonic()
                    with self.lock:
                        version, mode, active = self.version, self.mode, self.torch_removed
                    sequence += 1
                    processing_ok = True
                    try:
                        inference = (self.detector.infer(image, sequence, captured, mode) if active and mode != "off"
                                     else SimulatedDetector().infer(image, sequence, captured, "off"))
                    except Exception:
                        inference = SimulatedDetector().infer(image, sequence, captured, "unavailable")
                        processing_ok = False
                    jpeg = encode_annotated(image, inference, active and mode != "off")
                    timestamps.append(captured)
                    fps = ((len(timestamps) - 1) / (timestamps[-1] - timestamps[0])
                           if len(timestamps) > 1 and timestamps[-1] > timestamps[0] else 0.0)
                    packet = Packet(sequence, captured, version, jpeg, image.shape[1],
                                    image.shape[0], round(fps, 1),
                                    round((time.monotonic() - start) * 1000, 1),
                                    inference, processing_ok)
                    with self.lock:
                        if version == self.version:
                            self.packet = packet
                            self.problem = ""
                except Exception:
                    with self.lock:
                        self.packet = None
                        self.problem = "Câmera indisponível. Tentando reconectar."
                    self.source.close()
                    timestamps.clear()
                    self.stop_event.wait(1.0)
                self.stop_event.wait(max(0, 1 / self.settings.fps - (time.monotonic() - start)))
        finally:
            self.source.close()
