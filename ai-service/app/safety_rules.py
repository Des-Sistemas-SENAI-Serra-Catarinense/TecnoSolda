from math import isfinite

from .epi_validator import all_present, visible_equipment
from .events import EventLog
from .models import Config, Evidence, Frame, Helmet, SensorReading, State, Status
from .session_manager import Session


class SafetyEngine:
    """Máquina determinística; now é um relógio monotônico, nunca horário civil.

    O chamador deve executar step também sem novos quadros (watchdog).
    Só observações distintas contribuem para a confirmação temporal.
    """

    def __init__(self, config: Config | None = None,
                 events: EventLog | None = None) -> None:
        self.config = config or Config()
        self.events = events if events is not None else EventLog()
        self.session: Session | None = None
        self.state = State.WAITING
        self.reason = "tocha_no_suporte"
        self.last_frame: Frame | None = None
        self.last_now = 0.0
        self.up_count = 0
        self.down_count = 0
        self.missing: dict[str, int] = {}
        self.sensor: SensorReading | None = None

    def _invalidate(self) -> None:
        if self.session is not None:
            self.session.invalidate()
        self.up_count = self.down_count = 0

    def _set(self, state: State, reason: str, now: float,
             epi: str | None = None) -> Status:
        if (state, reason) != (self.state, self.reason):
            self.events.record(
                now, self.session.id if self.session else None,
                "TRANSICAO", state, reason, epi=epi,
            )
        self.state, self.reason = state, reason
        return self.snapshot()

    def _fail(self, state: State, reason: str, now: float) -> Status:
        self._invalidate()
        self.missing.clear()
        return self._set(state, reason, now)

    def technical_failure(self, reason: str) -> Status:
        return self._fail(State.PROCESSING_FAILURE, reason, self.last_now)

    def snapshot(self) -> Status:
        frame = self.last_frame
        active = self.session is not None
        verified = bool(self.session and self.session.initial_verified)
        green = active and verified and self.state == State.COMPLIANT
        sensor_ok = bool(self.sensor and self.sensor.available and
                         0 <= self.last_now - self.sensor.sampled_at
                         <= self.config.sensor_timeout)
        camera_ok = bool(self.state != State.CAMERA_FAILURE and frame and frame.camera_ok and
                         0 <= self.last_now - frame.captured_at
                         <= self.config.frame_timeout)
        return Status(
            self.state, self.reason, self.session.id if self.session else None,
            green, (active or self.state in {State.SENSOR_FAILURE, State.CAMERA_FAILURE,
                                     State.PROCESSING_FAILURE}) and not green,
            bool(self.session and self.session.respirator_verified), verified,
            self.sensor.torch_removed if sensor_ok and self.sensor else None,
            camera_ok,
            frame.helmet if frame and active else Helmet.UNKNOWN,
            frame.apron if frame and active else Evidence.UNKNOWN,
            frame.left_glove if frame and active else Evidence.UNKNOWN,
            frame.right_glove if frame and active else Evidence.UNKNOWN,
            frame.respirator if frame and active else Evidence.UNKNOWN,
        )

    def step(self, now: float, sensor: SensorReading,
             frame: Frame | None = None, camera_available: bool = True) -> Status:
        if not isfinite(now) or now < self.last_now:
            return self._fail(State.PROCESSING_FAILURE, "relogio_invalido", self.last_now)
        self.last_now = now
        self.sensor = sensor
        if not sensor.available or not 0 <= now - sensor.sampled_at <= self.config.sensor_timeout:
            return self._fail(State.SENSOR_FAILURE, "sensor_sem_leitura_confiavel", now)

        if not sensor.torch_removed:
            if self.session:
                self.events.record(now, self.session.id, "SESSAO_ENCERRADA",
                                   State.WAITING, "tocha_devolvida")
            self._invalidate()
            self.session = None
            self.missing.clear()
            return self._set(State.WAITING, "tocha_no_suporte", now)

        if self.session is None:
            self.session = Session(now)
            self.events.record(now, self.session.id, "SESSAO_INICIADA",
                               State.CHECKING, "tocha_retirada")
            self._set(State.CHECKING, "apresente_epis_com_mascara_levantada", now)

        if not camera_available:
            return self._fail(State.CAMERA_FAILURE, "camera_sem_quadro", now)

        previous = self.last_frame
        if frame is not None:
            if previous and (frame.sequence < previous.sequence or
                             frame.captured_at < previous.captured_at or
                             (frame.sequence == previous.sequence and frame != previous)):
                return self._fail(State.PROCESSING_FAILURE, "quadro_fora_de_ordem", now)
            self.last_frame = frame
        current = self.last_frame
        if current is None or not current.camera_ok:
            return self._fail(State.CAMERA_FAILURE, "camera_sem_quadro", now)
        if not 0 <= now - current.captured_at <= self.config.frame_timeout:
            return self._fail(State.CAMERA_FAILURE, "quadro_expirado_ou_futuro", now)
        if not current.processing_ok:
            return self._fail(State.PROCESSING_FAILURE, "inferencia_indisponivel", now)
        if current.captured_at < self.session.started_at:
            return self._fail(State.INCONCLUSIVE, "aguardando_quadro_da_sessao", now)

        if frame is None or (previous and frame.sequence == previous.sequence):
            return self.snapshot()
        if previous and frame.captured_at == previous.captured_at:
            return self._fail(State.PROCESSING_FAILURE, "timestamp_de_quadro_repetido", now)
        if previous and frame.captured_at - previous.captured_at > self.config.frame_timeout:
            return self._fail(State.INCONCLUSIVE, "intervalo_sem_acompanhamento", now)

        if (not frame.person_visible or frame.person_count != 1
                or not frame.tracking_reliable or not frame.track_id):
            return self._fail(State.INCONCLUSIVE, "visibilidade_ou_rastreamento_perdido", now)
        if self.session.track_id is not None and frame.track_id != self.session.track_id:
            return self._fail(State.INCONCLUSIVE, "continuidade_perdida", now)
        self.session.track_id = frame.track_id

        equipment = visible_equipment(frame)
        if frame.helmet == Helmet.UP:
            equipment["respirador"] = frame.respirator
        for name, evidence in equipment.items():
            self.missing[name] = self.missing.get(name, 0) + 1 if evidence == Evidence.ABSENT else 0
        if frame.helmet != Helmet.UP:
            self.missing.pop("respirador", None)

        if not all_present(equipment):
            self._invalidate()
            absent = next((name for name in equipment
                           if self.missing[name] >= self.config.missing_frames), None)
            if absent:
                return self._set(State.IRREGULAR, "ausencia_consistente:" + absent, now, absent)
            return self._set(State.INCONCLUSIVE, "epi_nao_confirmado", now)

        if frame.helmet == Helmet.UNKNOWN:
            return self._fail(State.INCONCLUSIVE, "posicao_da_mascara_inconclusiva", now)

        if self.state == State.COMPLIANT and frame.helmet == Helmet.UP:
            self._invalidate()

        if not self.session.initial_verified:
            self.down_count = 0
            if frame.helmet != Helmet.UP:
                self.up_count = 0
                return self._set(State.CHECKING, "levante_mascara_para_verificar_respirador", now)
            self.up_count += 1
            if self.up_count < self.config.stable_frames:
                return self._set(State.CHECKING, "confirmando_epis_em_multiplos_quadros", now)
            self.session.initial_verified = True
            self.session.respirator_verified = True
            return self._set(State.WAIT_HELMET, "abaixe_mascara", now)

        if frame.helmet == Helmet.UP:
            self.down_count = 0
            return self._set(State.WAIT_HELMET, "abaixe_mascara", now)
        self.down_count += 1
        if self.down_count < self.config.stable_frames:
            return self._set(State.WAIT_HELMET, "confirmando_mascara_abaixada", now)
        return self._set(State.COMPLIANT, "criterios_visuais_atendidos", now)
