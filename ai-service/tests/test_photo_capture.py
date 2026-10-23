"""Captura: imagens sintéticas ficam somente em diretórios temporários."""
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

SPEC = importlib.util.spec_from_file_location(
    "photo_capture", Path(__file__).resolve().parents[2] / "tirar_foto.py"
)
photo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(photo)


class PhotoCaptureTests(unittest.TestCase):
    def test_session_rejects_paths_and_windows_reserved_names(self):
        for value in ("../fora", "a/b", "a\\b", "", "CON", "LPT1", "nome.", "x" * 65):
            with self.subTest(value=value), self.assertRaises(ValueError):
                photo.session_directory(value)

    def test_session_stays_under_collection(self):
        self.assertEqual(photo.session_directory(" sessao_002 ").parent, photo.COLLECTION.resolve())

    def test_save_preserves_dimensions_and_uses_unique_names_in_unicode_path(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "sessão"
            frame = np.zeros((48, 64, 3), dtype=np.uint8)
            first = photo.save_photo(frame, folder)
            second = photo.save_photo(np.full_like(frame, 255), folder)
            self.assertNotEqual(first, second)
            decoded = cv2.imdecode(np.frombuffer(first.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
            self.assertEqual(decoded.shape, frame.shape)
            self.assertEqual(len(list(folder.glob("*.jpg"))), 2)

    def test_encoder_failure_creates_no_photo(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "session"
            with patch.object(photo.cv2, "imencode", return_value=(False, None)):
                with self.assertRaises(RuntimeError):
                    photo.save_photo(None, folder)
            self.assertFalse(folder.exists())

    def test_unavailable_camera_releases_device_and_has_no_frame(self):
        camera = Mock()
        camera.isOpened.return_value = False
        reader = photo.CameraReader(0, factory=lambda _: camera)
        reader.run()
        camera.release.assert_called_once()
        self.assertIsNone(reader.snapshot()[0])
        self.assertIn("indisponível", reader.snapshot()[2])

    def test_failed_read_clears_previous_frame(self):
        camera = Mock()
        camera.isOpened.return_value = True
        camera.read.side_effect = [(True, np.zeros((20, 20, 3), dtype=np.uint8)), (False, None)]
        reader = photo.CameraReader(0, factory=lambda _: camera)
        reader.run()
        self.assertEqual(reader.snapshot()[1], 0)
        self.assertIsNone(reader.snapshot()[0])
        camera.release.assert_called_once()

    def test_stopped_reader_releases_camera(self):
        camera = Mock()
        camera.isOpened.return_value = True
        reader = photo.CameraReader(0, factory=lambda _: camera)
        reader.stop.set()
        reader.run()
        camera.read.assert_not_called()
        camera.release.assert_called_once()

    def test_stale_and_disconnected_frames_cannot_be_saved(self):
        app = photo.PhotoApp.__new__(photo.PhotoApp)
        app.connected = True
        app.reader = photo.CameraReader(0)
        app.reader.frame = np.zeros((20, 20, 3), dtype=np.uint8)
        app.reader.timestamp = time.monotonic() - photo.MAX_FRAME_AGE - 1
        self.assertIsNone(app.fresh_frame())
        app.reader.timestamp = time.monotonic()
        self.assertIsNotNone(app.fresh_frame())
        app.connected = False
        self.assertIsNone(app.fresh_frame())


if __name__ == "__main__":
    unittest.main()

