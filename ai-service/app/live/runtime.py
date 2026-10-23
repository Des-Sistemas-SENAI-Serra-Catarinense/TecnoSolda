import asyncio
from dataclasses import asdict
import time

from hardware.signaling import SimulatedSignals
from ..alarm import Operator
from ..controller import Controller
from ..models import SensorReading, State
from .capture import CameraPipeline
from .inference import Mode


class LiveRuntime:
    """Controlador de demonstração: nenhuma saída física é conectada."""

    def __init__(self, pipeline: CameraPipeline) -> None:
        self.pipeline = pipeline
        self.controller = Controller(SimulatedSignals())
        self.mode: Mode = "off"
        self.removed = False
        self.version = 0
        self.running = False
        self.task: asyncio.Task | None = None
        self.data: dict = {}
        self.camera_last_ok: bool | None = None
        self.pending_lowering = False

    def start(self) -> None:
        self.pipeline.start()
        self.running = True
        self.tick()
        self.task = asyncio.create_task(self._watch())

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await asyncio.to_thread(self.pipeline.stop)

    async def _watch(self) -> None:
        while self.running:
            self.tick()
            await asyncio.sleep(0.1)

    def audit(self, kind: str, reason: str, actor: str | None = None) -> None:
        engine = self.controller.engine
        engine.events.record(time.monotonic(), engine.session.id if engine.session else None,
                             kind, engine.state, reason, "dashboard_local", actor=actor)

    def configure(self, removed: bool, mode: Mode, actor: str) -> None:
        session = self.controller.engine.session
        self.pending_lowering = bool(self.removed and removed and self.mode == "raised"
                                     and mode == "lowered" and session and session.initial_verified)
        self.removed, self.mode = removed, mode
        self.version = self.pipeline.configure(removed, mode)
        # Mudança de evidência de teste não pode deixar um verde antigo publicado.
        if not self.pending_lowering:
            self.controller.engine.technical_failure("aguardando_novo_quadro")
        self.audit("SIMULACAO_ALTERADA", f"tocha={removed};cenario={mode}", actor)
        self.tick()

    def acknowledge(self, actor: str) -> None:
        self.controller.acknowledge(Operator(actor, "operador"))
        self.tick()

    def tick(self) -> None:
        now = time.monotonic()
        packet, problem = self.pipeline.latest()
        camera_ok = bool(packet and packet.version == self.version and
                         0 <= now - packet.captured_at <= self.pipeline.settings.frame_timeout)
        previous = self.controller.engine.last_frame
        if (self.pending_lowering and not camera_ok and previous and
                now - previous.captured_at <= self.pipeline.settings.frame_timeout):
            # Preservar apenas a transição normal levantada -> abaixada.
            # O vídeo e o verde ficam ocultos até chegar o novo quadro.
            self.data = {**self.data, "sequence": None, "detections": [],
                         "camera": {**self.data.get("camera", {}), "connected": False,
                                    "message": "Aguardando quadro com máscara abaixada."}}
            return
        self.pending_lowering = False
        processing_ok = camera_ok and bool(packet and packet.processing_ok) and self.mode not in {"off", "unavailable"}
        if self.camera_last_ok != camera_ok:
            self.audit("CAMERA_CONECTADA" if camera_ok else "CAMERA_INDISPONIVEL",
                       "captura_real" if camera_ok else "sem_quadro_recente")
            self.camera_last_ok = camera_ok
        result = self.controller.step(
            now, SensorReading(now, self.removed),
            packet.inference.observation if camera_ok and packet else None,
            camera_available=camera_ok,
        )
        status = asdict(result.status)
        self.data = {
            "sequence": packet.sequence if camera_ok and packet else None,
            "camera": {
                "connected": camera_ok, "source": "real",
                "message": "" if camera_ok else problem or "Quadro expirado. Reconectando.",
                "width": packet.width if camera_ok and packet else 960,
                "height": packet.height if camera_ok and packet else 540,
            },
            "inference": {
                "mode": self.mode, "simulated": True, "available": processing_ok,
                "analyzing": self.removed and processing_ok,
                "message": ("Inferência simulada; não analisa os pixels."
                            if processing_ok else "IA treinada não instalada / processamento indisponível."),
            },
            "sensor": {"simulated": True, "removed": self.removed},
            "metrics": {
                "fps": packet.fps if camera_ok and packet else 0,
                "pipeline_ms": packet.pipeline_ms if camera_ok and packet else None,
                "frame_age_ms": round((now - packet.captured_at) * 1000) if camera_ok and packet else None,
            },
            "status": status,
            "simulated_outputs": {"green": status["green"], "red": status["red"],
                                  "alarm": result.outputs.alarm},
            "physical_outputs_connected": False,
            "detections": [asdict(box) for box in packet.inference.boxes]
                          if camera_ok and packet and processing_ok and self.removed else [],
            "events": self.controller.engine.events.as_dicts()[-100:],
        }
