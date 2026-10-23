import asyncio
from dataclasses import replace
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.live.auth import Sessions, hash_password, verify_password
from app.live.capture import CameraPipeline, Packet, encode_annotated
from app.live.inference import SimulatedDetector
from app.live.runtime import LiveRuntime
from app.live.server import COOKIE, SessionStream, create_app, mjpeg_frames
from app.live.settings import Settings
from app.models import State

PASSWORD = "senha-exclusiva-de-teste"
PASSWORD_HASH = hash_password(PASSWORD)
ORIGIN = "http://127.0.0.1:8000"


def settings(**changes):
    return Settings("instrutor-teste", PASSWORD_HASH, **changes)


class FakePipeline:
    """Fixture sem câmera ou imagens de pessoas; nunca usada pelo servidor real."""
    def __init__(self):
        self.settings = settings()
        self.packet = None
        self.version = 0
        self.mode = "off"
        self.removed = False
        self.sequence = 0

    def configure(self, removed, mode):
        self.version += 1
        self.removed, self.mode = removed, mode
        self.packet = None
        return self.version

    def latest(self):
        return self.packet, "Câmera de teste indisponível."

    def start(self): pass
    def stop(self): pass

    def produce(self, captured_at=None):
        self.sequence += 1
        now = time.monotonic() if captured_at is None else captured_at
        inference = SimulatedDetector().infer(None, self.sequence, now, self.mode if self.removed else "off")
        self.packet = Packet(self.sequence, now, self.version, b"JPEG_TEST_FIXTURE",
                             960, 540, 12, 3.2, inference, True)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = FakePipeline()
        self.runtime = LiveRuntime(self.pipeline)

    def frames(self, count=4):
        for _ in range(count):
            self.pipeline.produce()
            self.runtime.tick()

    def verify(self):
        self.runtime.configure(True, "raised", "op")
        self.frames()
        self.assertTrue(self.runtime.data["status"]["initial_verified"])
        self.runtime.configure(True, "lowered", "op")
        self.frames()
        self.assertTrue(self.runtime.data["status"]["green"])

    def test_sequence_survives_normal_helmet_transition(self):
        self.verify()
        self.assertFalse(self.runtime.data["physical_outputs_connected"])
        self.assertTrue(all(box["simulated"] for box in self.runtime.data["detections"]))

    def test_no_camera_means_no_fake_video_or_green(self):
        self.runtime.configure(True, "raised", "op")
        self.runtime.tick()
        self.assertFalse(self.runtime.data["camera"]["connected"])
        self.assertFalse(self.runtime.data["status"]["green"])
        self.assertEqual(self.runtime.data["detections"], [])

    def test_disconnect_and_reconnect_invalidate_respiration(self):
        self.verify()
        self.pipeline.packet = None
        self.runtime.tick()
        self.assertFalse(self.runtime.data["status"]["green"])
        self.assertFalse(self.runtime.data["status"]["respirator_verified"])
        self.frames()
        self.assertFalse(self.runtime.data["status"]["green"])

    def test_camera_failure_does_not_flood_history(self):
        self.runtime.configure(True, "raised", "op")
        before = self.runtime.controller.engine.events.sequence
        for _ in range(20):
            self.runtime.tick()
        self.assertEqual(self.runtime.controller.engine.events.sequence, before)

    def test_stale_packet_cannot_leave_green(self):
        self.verify()
        self.pipeline.produce(time.monotonic() - 5)
        self.runtime.tick()
        self.assertFalse(self.runtime.data["status"]["green"])
        self.assertFalse(self.runtime.data["camera"]["connected"])

    def test_simulation_changes_drop_green_before_next_frame(self):
        for mode in ("missing_glove", "hidden_glove", "occluded", "unavailable"):
            with self.subTest(mode=mode):
                self.setUp()
                self.verify()
                self.runtime.configure(True, mode, "op")
                self.assertFalse(self.runtime.data["status"]["green"])
                self.frames()
                self.assertFalse(self.runtime.data["status"]["green"])

    def test_waiting_keeps_real_video_but_not_detections(self):
        self.runtime.configure(False, "raised", "op")
        self.frames()
        self.assertTrue(self.runtime.data["camera"]["connected"])
        self.assertFalse(self.runtime.data["inference"]["analyzing"])
        self.assertEqual(self.runtime.data["detections"], [])

    def test_detector_failure_keeps_video_and_reports_unavailable(self):
        self.runtime.configure(True, "raised", "op")
        self.frames()
        packet = self.pipeline.packet
        failed = SimulatedDetector().infer(None, packet.sequence + 1, time.monotonic(), "unavailable")
        self.pipeline.packet = replace(packet, sequence=packet.sequence + 1,
                                       captured_at=failed.observation.captured_at,
                                       inference=failed, processing_ok=False)
        self.runtime.tick()
        self.assertTrue(self.runtime.data["camera"]["connected"])
        self.assertFalse(self.runtime.data["inference"]["available"])
        self.assertFalse(self.runtime.data["status"]["green"])

    def test_annotations_encode_in_memory_without_file(self):
        import cv2
        import numpy as np
        # Imagem sintética só para teste do codec; não é publicada como câmera real.
        image = np.zeros((540, 960, 3), dtype=np.uint8)
        inference = SimulatedDetector().infer(image, 1, 1.0, "raised")
        result = encode_annotated(image, inference, True)
        self.assertEqual(result[:2], b"\xff\xd8")
        decoded = cv2.imdecode(np.frombuffer(result, dtype=np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(decoded.shape, image.shape)
        self.assertGreater(int(decoded.sum()), 0)
        self.assertEqual(int(image.sum()), 0)


class AuthTests(unittest.TestCase):
    def test_hash_and_fixed_expiration(self):
        self.assertTrue(verify_password(PASSWORD, PASSWORD_HASH))
        self.assertFalse(verify_password("incorreta", PASSWORD_HASH))
        now = [10.0]
        sessions = Sessions(5, clock=lambda: now[0])
        token, _ = sessions.issue("op")
        now[0] = 14.9
        self.assertIsNotNone(sessions.get(token))
        now[0] = 15.0
        self.assertIsNone(sessions.get(token))

    def test_cannot_issue_access_from_unapproved_role(self):
        sessions = Sessions(10)
        token, access = sessions.issue("op")
        sessions.items[token] = replace(access, role="visitante")
        self.assertIsNone(sessions.get(token))

    def test_lan_configuration_requires_tls_and_private_subnet(self):
        with self.assertRaises(ValueError):
            settings(origin="http://192.168.0.5:8000")
        for cidr in ("0.0.0.0/0", "8.8.8.0/24", "::/0"):
            with self.subTest(cidr=cidr), self.assertRaises(ValueError):
                settings(allowed_networks=(cidr,))
        configured = settings(origin="https://192.168.0.5:8000", allowed_networks=("192.168.0.0/24",))
        self.assertTrue(configured.secure_cookie)
        self.assertTrue(configured.allows("192.168.0.8"))
        self.assertFalse(configured.allows("192.168.1.8"))

    def test_login_rate_limit_and_revocation(self):
        sessions = Sessions(10)
        for _ in range(5):
            self.assertTrue(sessions.permit_attempt("127.0.0.1"))
        self.assertFalse(sessions.permit_attempt("127.0.0.1"))
        token, _ = sessions.issue("op")
        sessions.revoke(token)
        self.assertIsNone(sessions.get(token))


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = FakePipeline()
        self.runtime = LiveRuntime(self.pipeline)
        self.sessions = Sessions(900)
        self.app = create_app(settings(), self.runtime, self.sessions)
        self.client = TestClient(self.app, base_url=ORIGIN, client=("127.0.0.1", 50000))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def login(self):
        response = self.client.post("/api/auth/login", headers={"Origin": ORIGIN},
                                    json={"username": "instrutor-teste", "password": PASSWORD})
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def test_unauthenticated_status_video_and_history_are_blocked(self):
        for path in ("/api/live/video.mjpg", "/api/live/status", "/api/alerts"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)

    def test_cookie_and_authenticated_status(self):
        response = self.login()
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        self.assertIn("path=/api", cookie)
        state = self.client.get("/api/live/status")
        self.assertEqual(state.status_code, 200)
        self.assertIn("no-store", state.headers["cache-control"])
        self.assertFalse(state.json()["physical_outputs_connected"])

    def test_secure_cookie_in_https_configuration(self):
        app = create_app(settings(origin="https://127.0.0.1:8000"), LiveRuntime(FakePipeline()))
        with TestClient(app, base_url="https://127.0.0.1:8000", client=("127.0.0.1", 50000)) as client:
            response = client.post("/api/auth/login", headers={"Origin": "https://127.0.0.1:8000"},
                                   json={"username": "instrutor-teste", "password": PASSWORD})
            self.assertIn("Secure", response.headers["set-cookie"])

    def test_simulation_requires_csrf_and_same_origin(self):
        access = self.login().json()
        body = {"removed": True, "mode": "raised"}
        self.assertEqual(self.client.post("/api/simulation", json=body).status_code, 403)
        self.assertEqual(self.client.post("/api/simulation", json=body, headers={
            "Origin": "https://other.example", "X-CSRF-Token": access["csrf"]}).status_code, 403)
        response = self.client.post("/api/simulation", json=body, headers={
            "Origin": ORIGIN, "X-CSRF-Token": access["csrf"]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.runtime.removed)

    def test_login_rejects_wrong_origin_and_password(self):
        body = {"username": "instrutor-teste", "password": PASSWORD}
        self.assertEqual(self.client.post("/api/auth/login", json=body).status_code, 403)
        body["password"] = "wrong"
        self.assertEqual(self.client.post("/api/auth/login", json=body,
                                         headers={"Origin": ORIGIN}).status_code, 401)

    def test_network_and_host_are_enforced_even_with_proxy_headers(self):
        with TestClient(self.app, base_url=ORIGIN, client=("8.8.8.8", 50000)) as client:
            self.assertEqual(client.get("/api/auth/session",
                                        headers={"X-Forwarded-For": "127.0.0.1"}).status_code, 403)
        self.assertEqual(self.client.get("/api/auth/session", headers={"Host": "evil.example"}).status_code, 403)

    def test_logout_invalidates_cookie_server_side(self):
        access = self.login().json()
        token = self.client.cookies.get(COOKIE)
        response = self.client.post("/api/auth/logout", headers={
            "Origin": ORIGIN, "X-CSRF-Token": access["csrf"]})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.sessions.get(token))
        self.assertEqual(self.client.get("/api/live/status").status_code, 401)

    def test_websocket_rejects_anonymous_and_wrong_origin(self):
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("ws://127.0.0.1:8000/api/live/ws", headers={"Origin": ORIGIN}):
                pass
        self.login()
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("ws://127.0.0.1:8000/api/live/ws", headers={"Origin": "https://evil.example"}):
                pass

    def test_websocket_pushes_and_closes_on_revocation(self):
        self.login()
        token = self.client.cookies.get(COOKIE)
        with self.client.websocket_connect("ws://127.0.0.1:8000/api/live/ws", headers={"Origin": ORIGIN}) as socket:
            state = socket.receive_json()
            self.assertTrue(state["inference"]["simulated"])
            self.sessions.revoke(token)
            with self.assertRaises(WebSocketDisconnect) as closed:
                while True:
                    socket.receive_json()
            self.assertEqual(closed.exception.code, 4401)


class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_mjpeg_contains_only_latest_frame_and_stops_on_expiry(self):
        pipeline = FakePipeline()
        runtime = LiveRuntime(pipeline)
        pipeline.produce()
        now = [0.0]
        sessions = Sessions(5, clock=lambda: now[0])
        token, _ = sessions.issue("op")
        generator = mjpeg_frames(runtime, sessions, token)
        part = await anext(generator)
        self.assertIn(b"Content-Type: image/jpeg", part)
        self.assertIn(b"JPEG_TEST_FIXTURE", part)
        now[0] = 5
        with self.assertRaises(StopAsyncIteration):
            await anext(generator)

    async def test_mjpeg_never_sends_stale_image(self):
        pipeline = FakePipeline()
        runtime = LiveRuntime(pipeline)
        pipeline.produce(time.monotonic() - 10)
        sessions = Sessions(5)
        token, _ = sessions.issue("op")
        generator = mjpeg_frames(runtime, sessions, token)
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(anext(generator), timeout=0.1)

    async def test_expiration_interrupts_blocked_asgi_send(self):
        sessions = Sessions(5)
        token, _ = sessions.issue("op")
        started = asyncio.Event()
        finished = []
        async def frames():
            while True:
                yield b"frame"
                await asyncio.sleep(0.01)
        async def send(message):
            if message["type"] == "http.response.body" and message.get("more_body"):
                started.set()
                await asyncio.Event().wait()
            else:
                finished.append(message)
        async def receive():
            await asyncio.Event().wait()
        response = SessionStream(frames(), sessions, token)
        scope = {"type": "http", "asgi": {"spec_version": "2.4"}}
        task = asyncio.create_task(response(scope, receive, send))
        await asyncio.wait_for(started.wait(), 1)
        sessions.revoke(token)
        await asyncio.wait_for(task, 1)
        self.assertTrue(any(message.get("more_body") is False for message in finished))


if __name__ == "__main__":
    unittest.main()
