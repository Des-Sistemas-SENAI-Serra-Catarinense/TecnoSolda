from dataclasses import replace
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.alarm import AlarmConfig, Operator
from app.controller import Controller
from app.events import EventLog
from app.models import Config, Evidence, Frame, Helmet, SensorReading, State
from app.safety_rules import SafetyEngine
from hardware.signaling import SimulatedSignals
from hardware.simulator import SimulatedCamera, SimulatedTorchSensor


class Rig:
    def __init__(self, alarm_config=None):
        self.now = 0.0
        self.camera = SimulatedCamera()
        self.sensor = SimulatedTorchSensor()
        self.device = SimulatedSignals()
        self.controller = Controller(self.device, alarm_config=alarm_config)
        self.engine = self.controller.engine

    def step(self, advance=0.1, capture=True, **changes):
        self.now = round(self.now + advance, 6)
        frame = self.camera.read(self.now, **changes) if capture else None
        return self.controller.step(self.now, self.sensor.read(self.now), frame)

    def up(self):
        return self.step()

    def down(self, **changes):
        return self.step(helmet=Helmet.DOWN, respirator=Evidence.UNKNOWN, **changes)

    def verify(self):
        self.sensor.removed = True
        for _ in range(3):
            self.up()
        for _ in range(3):
            result = self.down()
        assert result.outputs.green
        return result


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.rig = Rig()

    def assert_blocked(self, result, state=None):
        self.assertFalse(result.outputs.green)
        self.assertFalse(result.status.green)
        if state is not None:
            self.assertEqual(result.status.state, state)

    def test_waiting_is_off_without_session(self):
        result = self.rig.up()
        self.assertEqual(result.status.state, State.WAITING)
        self.assertIsNone(result.status.session_id)
        self.assertFalse(result.outputs.green)
        self.assertFalse(result.outputs.red)
        self.assertFalse(result.outputs.alarm)

    def test_full_sequence_requires_three_distinct_frames_per_stage(self):
        self.rig.sensor.removed = True
        for _ in range(2):
            self.assert_blocked(self.rig.up(), State.CHECKING)
        initial = self.rig.up()
        self.assert_blocked(initial, State.WAIT_HELMET)
        self.assertTrue(initial.status.respirator_verified)
        for _ in range(2):
            self.assert_blocked(self.rig.down(), State.WAIT_HELMET)
        self.assertTrue(self.rig.down().outputs.green)

    def test_mask_down_without_respirator_never_passes(self):
        self.rig.sensor.removed = True
        for _ in range(20):
            self.assert_blocked(self.rig.down(), State.CHECKING)

    def test_respirator_can_be_hidden_after_initial_stage(self):
        self.rig.verify()
        for _ in range(10):
            result = self.rig.down()
            self.assertTrue(result.outputs.green)
            self.assertTrue(result.status.respirator_verified)
            self.assertEqual(result.status.respirator, Evidence.UNKNOWN)

    def test_hidden_respirator_cannot_pass_initial_stage(self):
        self.rig.sensor.removed = True
        for _ in range(10):
            result = self.rig.step(respirator=Evidence.UNKNOWN)
            self.assert_blocked(result, State.INCONCLUSIVE)
            self.assertFalse(result.status.respirator_verified)

    def test_single_glove_never_confirms_pair(self):
        self.rig.sensor.removed = True
        for side in ("left_glove", "right_glove"):
            with self.subTest(side=side):
                for _ in range(5):
                    self.assert_blocked(self.rig.step(**{side: Evidence.UNKNOWN}),
                                        State.INCONCLUSIVE)

    def test_occlusion_immediately_clears_green_and_respirator(self):
        self.rig.verify()
        result = self.rig.down(person_visible=False)
        self.assert_blocked(result, State.INCONCLUSIVE)
        self.assertFalse(result.status.respirator_verified)
        for _ in range(5):
            self.assert_blocked(self.rig.down())
        self.rig.verify()

    def test_tracking_change_requires_full_revalidation(self):
        self.rig.verify()
        result = self.rig.down(track_id="nova-pessoa")
        self.assert_blocked(result)
        self.assertFalse(result.status.respirator_verified)
        for _ in range(5):
            self.assert_blocked(self.rig.down(track_id="nova-pessoa"))

    def test_ambiguous_person_or_tracking_clears_cache(self):
        for changes in ({"person_count": 2}, {"person_count": 0},
                        {"track_id": None}, {"tracking_reliable": False}):
            with self.subTest(changes=changes):
                rig = Rig()
                rig.verify()
                result = rig.down(**changes)
                self.assert_blocked(result, State.INCONCLUSIVE)
                self.assertFalse(result.status.respirator_verified)

    def test_unknown_equipment_never_becomes_missing_evidence(self):
        self.rig.verify()
        for _ in range(10):
            result = self.rig.down(right_glove=Evidence.UNKNOWN)
            self.assert_blocked(result, State.INCONCLUSIVE)

    def test_missing_requires_consistent_evidence_but_green_drops_first_frame(self):
        self.rig.verify()
        for _ in range(2):
            self.assert_blocked(self.rig.down(left_glove=Evidence.ABSENT),
                                State.INCONCLUSIVE)
        result = self.rig.down(left_glove=Evidence.ABSENT)
        self.assert_blocked(result, State.IRREGULAR)
        self.assertEqual(self.rig.engine.events.events[-1].epi, "luva_esquerda")

    def test_missing_counter_resets_on_unknown(self):
        self.rig.sensor.removed = True
        for _ in range(4):
            self.rig.step(apron=Evidence.ABSENT)
            self.assert_blocked(self.rig.step(apron=Evidence.UNKNOWN), State.INCONCLUSIVE)
        self.assert_blocked(self.rig.step(apron=Evidence.ABSENT), State.INCONCLUSIVE)

    def test_raised_helmet_after_green_requires_respirator_again(self):
        self.rig.verify()
        result = self.rig.step(helmet=Helmet.UP, respirator=Evidence.UNKNOWN)
        self.assert_blocked(result, State.INCONCLUSIVE)
        self.assertFalse(result.status.respirator_verified)
        self.assert_blocked(self.rig.down())

    def test_unknown_helmet_clears_green(self):
        self.rig.verify()
        self.assert_blocked(self.rig.step(helmet=Helmet.UNKNOWN), State.INCONCLUSIVE)

    def test_helmet_lowering_must_be_consecutive(self):
        self.rig.sensor.removed = True
        for _ in range(3):
            self.rig.up()
        self.rig.down()
        self.rig.down()
        self.rig.up()
        for _ in range(2):
            self.assert_blocked(self.rig.down())
        self.assertTrue(self.rig.down().outputs.green)

    def test_return_ends_session_and_clears_results(self):
        old_id = self.rig.verify().status.session_id
        self.rig.sensor.removed = False
        result = self.rig.down()
        self.assert_blocked(result, State.WAITING)
        self.assertIsNone(result.status.session_id)
        self.assertFalse(result.status.respirator_verified)
        self.rig.sensor.removed = True
        result = self.rig.down()
        self.assert_blocked(result, State.CHECKING)
        self.assertNotEqual(result.status.session_id, old_id)
        closed = [e for e in self.rig.engine.events.events if e.kind == "SESSAO_ENCERRADA"]
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].session_id, old_id)

    def test_camera_processing_and_sensor_failures(self):
        for fault, state in (("camera", State.CAMERA_FAILURE),
                             ("processing", State.PROCESSING_FAILURE),
                             ("sensor", State.SENSOR_FAILURE)):
            with self.subTest(fault=fault):
                rig = Rig()
                rig.verify()
                changes = {}
                if fault == "camera":
                    rig.camera.available = False
                elif fault == "sensor":
                    rig.sensor.available = False
                else:
                    changes["processing_ok"] = False
                result = rig.down(**changes)
                self.assert_blocked(result, state)
                self.assertFalse(result.status.respirator_verified)
                rig.camera.available = rig.sensor.available = True
                self.assert_blocked(rig.down())
                rig.verify()

    def test_watchdog_catches_camera_without_new_frames(self):
        self.rig.verify()
        self.assert_blocked(self.rig.step(advance=0.8, capture=False), State.CAMERA_FAILURE)

    def test_gap_cannot_reuse_respiration_even_if_new_frame_arrives(self):
        self.rig.verify()
        self.assert_blocked(self.rig.step(advance=1.0, helmet=Helmet.DOWN))
        self.assertFalse(self.rig.engine.snapshot().respirator_verified)

    def test_stale_and_future_sensor_samples_fail_closed(self):
        for offset in (-2.0, 0.1):
            with self.subTest(offset=offset):
                rig = Rig()
                rig.verify()
                result = rig.controller.step(rig.now, SensorReading(rig.now + offset, True))
                self.assert_blocked(result, State.SENSOR_FAILURE)

    def test_stale_or_future_frame_fails_closed(self):
        for offset in (-2.0, 0.1):
            with self.subTest(offset=offset):
                rig = Rig()
                rig.sensor.removed = True
                rig.now = 3.0
                frame = rig.camera.read(rig.now + offset)
                result = rig.controller.step(rig.now, rig.sensor.read(rig.now), frame)
                self.assert_blocked(result, State.CAMERA_FAILURE)

    def test_same_frame_cannot_advance_evidence(self):
        self.rig.sensor.removed = True
        self.rig.up()
        frame = self.rig.engine.last_frame
        for _ in range(10):
            result = self.rig.controller.step(self.rig.now, self.rig.sensor.read(self.rig.now), frame)
            self.assert_blocked(result, State.CHECKING)
        self.assertFalse(result.status.respirator_verified)

    def test_out_of_order_frame_and_changed_duplicate_are_rejected(self):
        for modification in ({"sequence": 0}, {"apron": Evidence.UNKNOWN}):
            with self.subTest(modification=modification):
                rig = Rig()
                rig.verify()
                frame = replace(rig.engine.last_frame, **modification)
                result = rig.controller.step(rig.now, rig.sensor.read(rig.now), frame)
                self.assert_blocked(result, State.PROCESSING_FAILURE)

    def test_new_sequence_with_same_timestamp_is_not_new_evidence(self):
        self.rig.verify()
        frame = replace(self.rig.engine.last_frame, sequence=100)
        result = self.rig.controller.step(self.rig.now, self.rig.sensor.read(self.rig.now), frame)
        self.assert_blocked(result, State.PROCESSING_FAILURE)

    def test_time_regression_fails_closed(self):
        self.rig.verify()
        result = self.rig.controller.step(0.0, self.rig.sensor.read(0.0))
        self.assert_blocked(result, State.PROCESSING_FAILURE)

    def test_nonfinite_time_fails_closed(self):
        self.rig.verify()
        result = self.rig.controller.step(float("nan"), self.rig.sensor.read(self.rig.now))
        self.assert_blocked(result, State.PROCESSING_FAILURE)

    def test_signaling_failure_is_reported_and_invalidates_session(self):
        self.rig.verify()
        self.rig.device.available = False
        result = self.rig.down()
        self.assert_blocked(result, State.PROCESSING_FAILURE)
        self.assertFalse(result.signaling_ok)
        self.assertFalse(self.rig.device.outputs.green)
        self.assertFalse(result.status.respirator_verified)
        self.rig.device.available = True
        self.assert_blocked(self.rig.down())

    def test_processing_exception_does_not_leave_simulated_green_on(self):
        self.rig.verify()
        def broken(*args):
            raise RuntimeError("falha simulada")
        self.rig.engine.step = broken
        result = self.rig.down()
        self.assert_blocked(result, State.PROCESSING_FAILURE)
        self.assertFalse(self.rig.device.outputs.green)

    def test_old_frame_cannot_validate_new_session(self):
        self.rig.verify()
        self.rig.sensor.removed = False
        self.rig.step(capture=False)
        self.rig.sensor.removed = True
        self.assert_blocked(self.rig.step(capture=False), State.INCONCLUSIVE)

    def test_idle_sensor_failure_does_not_create_a_session(self):
        self.rig.sensor.available = False
        result = self.rig.up()
        self.assert_blocked(result, State.SENSOR_FAILURE)
        self.assertIsNone(result.status.session_id)

    def test_config_rejects_single_frame_confirmation(self):
        for changes in ({"stable_frames": 1}, {"missing_frames": 1},
                        {"frame_timeout": 0}, {"sensor_timeout": float("inf")}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    Config(**changes)

    def test_event_log_is_bounded_and_contains_no_images(self):
        events = EventLog(3)
        for i in range(10):
            events.record(i, None, "TESTE", State.WAITING, "teste")
        self.assertEqual(len(events.events), 3)
        self.assertEqual(events.events[-1].sequence, 10)
        self.assertNotIn("image", events.as_dicts()[0])
        self.assertNotIn("track_id", events.as_dicts()[0])

    def test_random_traces_preserve_green_invariants(self):
        rng = random.Random(42)
        self.rig.verify()
        for _ in range(1500):
            self.rig.sensor.removed = rng.random() > 0.05
            changes = {
                "helmet": rng.choice(list(Helmet)),
                "right_glove": rng.choice(list(Evidence)),
                "person_visible": rng.random() > 0.08,
                "processing_ok": rng.random() > 0.03,
            }
            result = self.rig.step(**changes)
            if result.outputs.green:
                self.assertEqual(result.status.state, State.COMPLIANT)
                self.assertTrue(result.status.initial_verified)
                self.assertTrue(result.status.respirator_verified)
                self.assertTrue(self.rig.sensor.removed)
                self.assertEqual(changes["helmet"], Helmet.DOWN)
                self.assertEqual(changes["right_glove"], Evidence.PRESENT)
                self.assertTrue(changes["person_visible"])
                self.assertTrue(changes["processing_ok"])
                self.assertFalse(result.outputs.red)
            if result.status.state == State.INCONCLUSIVE:
                self.assertFalse(result.outputs.green)


class AlarmTests(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(AlarmConfig(delay=0, pulse=0.2, cooldown=1.0))
        self.rig.verify()

    def test_alarm_pulses_and_respects_cooldown(self):
        result = self.rig.down(person_visible=False)
        self.assertTrue(result.outputs.alarm)
        for _ in range(5):
            result = self.rig.down(person_visible=False)
        self.assertFalse(result.outputs.alarm)
        events = lambda: [e for e in self.rig.engine.events.events if e.kind == "ALARME_ACIONADO"]
        self.assertEqual(len(events()), 1)
        for _ in range(6):
            self.rig.down(person_visible=False)
        self.assertEqual(len(events()), 2)

    def test_ack_requires_authorized_profile_and_does_not_restore_green(self):
        self.rig.down(person_visible=False)
        with self.assertRaises(PermissionError):
            self.rig.controller.acknowledge(Operator("leitor", "visitante"))
        self.rig.controller.acknowledge(Operator("instrutor-teste", "operador"))
        self.assertFalse(self.rig.device.outputs.alarm)
        for _ in range(15):
            result = self.rig.down(person_visible=False)
            self.assertFalse(result.outputs.alarm)
            self.assertFalse(result.outputs.green)
        acknowledged = [e for e in self.rig.engine.events.events if e.kind == "ALARME_RECONHECIDO"]
        self.assertEqual(acknowledged[0].actor, "instrutor-teste")

    def test_new_incident_after_ack_can_sound_again(self):
        self.rig.down(person_visible=False)
        self.rig.controller.acknowledge(Operator("op", "administrador"))
        self.rig.verify()
        result = self.rig.step(advance=1.0, processing_ok=False)
        self.assertTrue(result.outputs.alarm)

    def test_torch_return_stops_alarm(self):
        self.rig.down(person_visible=False)
        self.rig.sensor.removed = False
        result = self.rig.down()
        self.assertFalse(result.outputs.alarm)
        self.assertFalse(result.outputs.green)

    def test_disabled_alarm_never_sounds(self):
        rig = Rig(AlarmConfig(enabled=False, delay=0))
        rig.verify()
        for _ in range(20):
            self.assertFalse(rig.down(person_visible=False).outputs.alarm)

    def test_alarm_delay(self):
        rig = Rig(AlarmConfig(delay=0.5, pulse=0.2, cooldown=1))
        rig.verify()
        for _ in range(5):
            self.assertFalse(rig.down(person_visible=False).outputs.alarm)
        self.assertTrue(rig.down(person_visible=False).outputs.alarm)


if __name__ == "__main__":
    unittest.main()
