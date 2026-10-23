"""Duplicatas: fixtures temporárias, sem acesso à câmera ou fotos do usuário."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import cv2
import numpy as np

from photo_duplicates import DuplicateGuard, DuplicatePhotoError, image_signature, visually_similar
from tirar_foto import save_photo
from helmet_experiment import capture_sample


def scene():
    image = np.full((240, 320, 3), (50, 70, 90), np.uint8)
    cv2.rectangle(image, (100, 25), (220, 170), (170, 180, 190), -1)
    cv2.rectangle(image, (118, 60), (202, 90), (15, 15, 15), -1)
    cv2.circle(image, (160, 200), 25, (80, 150, 100), -1)
    return image


class DuplicateTests(unittest.TestCase):
    def test_identical_frame_is_not_written_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            first = save_photo(scene(), folder)
            with self.assertRaises(DuplicatePhotoError):
                save_photo(scene(), folder)
            self.assertEqual(list(folder.glob("*.jpg")), [first])

    def test_noise_exposure_resize_jpeg_and_small_shift_are_duplicates(self):
        frame = scene()
        noise = np.random.default_rng(7).normal(0, 2, frame.shape)
        noisy = np.clip(frame.astype(float) + noise + 12, 0, 255).astype(np.uint8)
        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
        shifted = cv2.warpAffine(frame, np.float32([[1, 0, 2], [0, 1, 0]]),
                                (320, 240), borderMode=cv2.BORDER_REPLICATE)
        variants = (noisy, cv2.imdecode(jpeg, cv2.IMREAD_COLOR),
                    cv2.resize(frame, (640, 480)), shifted)
        for variant in variants:
            with self.subTest(shape=variant.shape):
                self.assertTrue(visually_similar(image_signature(frame), image_signature(variant)))

    def test_changed_helmet_is_accepted_with_same_background(self):
        raised = scene()
        lowered = raised.copy()
        cv2.rectangle(lowered, (100, 25), (220, 170), (20, 25, 30), -1)
        cv2.rectangle(lowered, (118, 105), (202, 135), (100, 100, 100), -1)
        self.assertFalse(visually_similar(image_signature(raised), image_signature(lowered)))
        with tempfile.TemporaryDirectory() as temp:
            first = save_photo(raised, Path(temp))
            second = save_photo(lowered, Path(temp))
            self.assertNotEqual(first, second)

    def test_cross_session_and_reopened_index_find_existing_image(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            save_photo(scene(), base / "s1", duplicate_root=base)
            with self.assertRaises(DuplicatePhotoError):
                save_photo(scene(), base / "s2", duplicate_root=base)
            self.assertFalse((base / "s2").exists())
            with self.assertRaises(DuplicatePhotoError):
                DuplicateGuard(base).check(scene())

    def test_helmet_checks_other_labels_and_splits(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            capture_sample(base, "treino", "s1", "levantada", scene())
            for split, session, label in (("treino", "s1", "abaixada"), ("validacao", "s2", "levantada")):
                with self.assertRaises(DuplicatePhotoError):
                    capture_sample(base, split, session, label, scene())
            self.assertEqual(len(list(base.rglob("*.jpg"))), 1)

    def test_cache_removes_deleted_image(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = save_photo(scene(), base)
            guard = DuplicateGuard(base)
            with self.assertRaises(DuplicatePhotoError):
                guard.check(scene())
            original.unlink()
            guard.check(scene())

    def test_cache_reloads_modified_file(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            original = save_photo(scene(), base)
            guard = DuplicateGuard(base)
            with self.assertRaises(DuplicatePhotoError):
                guard.check(scene())
            _, other = cv2.imencode(".jpg", np.full((240, 320, 3), 250, np.uint8))
            original.write_bytes(other.tobytes())
            guard.check(scene())

    def test_unreadable_existing_image_blocks_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "broken.jpg").write_bytes(b"broken")
            with self.assertRaisesRegex(ValueError, "verificar"):
                save_photo(scene(), folder)
            self.assertEqual(len(list(folder.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
