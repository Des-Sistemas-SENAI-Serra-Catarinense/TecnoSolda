"""Fixtures artificiais apenas temporárias; não medem acurácia em máscaras reais."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import cv2
import numpy as np

import helmet_experiment as helmet


def fixture_image(label, seed):
    rng = np.random.default_rng(seed)
    image = rng.integers(20, 35, (100, 80, 3), dtype=np.uint8)
    if label == "levantada":
        for x in range(10, 75, 12):
            cv2.line(image, (x, 5), (x, 95), (220, 220, 220), 4)
    elif label == "abaixada":
        for y in range(10, 95, 12):
            cv2.line(image, (5, y), (75, y), (220, 220, 220), 4)
    else:
        for n in range(10, 90, 15):
            cv2.circle(image, (40, 50), n // 2, (170, 170, 170), 2)
    return image


def make_dataset(base):
    for split in helmet.SPLITS:
        for label in helmet.CLASSES:
            for index in range(helmet.MIN_COUNTS[split]):
                seed = index + (100 if split == "validacao" else 0)
                # Variação visual significativa entre fixtures, não só ruído de sensor.
                rng = np.random.default_rng(seed)
                tint = cv2.resize(rng.integers(0, 100, (5, 5, 3), dtype=np.uint8), (80, 100))
                image = np.clip(fixture_image(label, seed).astype(int) + tint, 0, 255).astype(np.uint8)
                helmet.save_photo(image, base / split / f"sessao_{split}" / label)


class HelmetExperimentTests(unittest.TestCase):
    def test_hog_extracts_image_features(self):
        vector = helmet.feature(fixture_image("levantada", 1))
        self.assertEqual(vector.shape, (helmet.FEATURE_SIZE,))
        self.assertAlmostEqual(float(np.linalg.norm(vector)), 1.0, places=5)
        other = helmet.feature(fixture_image("abaixada", 1))
        self.assertLess(float(vector @ other), 0.8)

    def test_flat_image_is_inconclusive(self):
        vectors = np.eye(3, dtype=np.float32)
        model = helmet.HelmetModel(vectors, helmet.CLASSES)
        self.assertEqual(model.predict_feature(np.zeros(3)).label, "inconclusiva")

    def test_ambiguous_matches_are_rejected(self):
        model = helmet.HelmetModel(np.ones((3, 3), dtype=np.float32) / np.sqrt(3), helmet.CLASSES)
        prediction = model.predict_feature(np.ones(3, dtype=np.float32) / np.sqrt(3))
        self.assertEqual(prediction.label, "inconclusiva")

    def test_real_feature_matching_separates_fixture_classes(self):
        model = helmet.HelmetModel([helmet.feature(fixture_image(c, i)) for c in helmet.CLASSES for i in range(3)],
                                  [c for c in helmet.CLASSES for _ in range(3)])
        for label in helmet.CLASSES:
            self.assertEqual(model.predict(fixture_image(label, 50)).label, label)

    def test_empty_dataset_does_not_produce_model(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "faltam fotos"):
                helmet.train_experiment(Path(temp))
            self.assertFalse((Path(temp) / "resultados").exists())

    def test_capture_crops_and_separates_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            frame = fixture_image("levantada", 1)
            path = helmet.capture_sample(base, "treino", "s1", "levantada", frame)
            self.assertEqual(path.parent, base.resolve() / "treino/s1/levantada")
            saved = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            self.assertEqual(saved.shape, helmet.crop_head(frame).shape)
            with self.assertRaisesRegex(ValueError, "outra sessão"):
                helmet.capture_sample(base, "validacao", "s1", "abaixada", frame)
            with self.assertRaises(ValueError):
                helmet.capture_sample(base, "treino", "../escape", "abaixada", frame)

    def test_training_uses_only_training_rows_and_writes_real_report(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            make_dataset(base)
            model, run = helmet.train_experiment(base)
            self.assertEqual(model.vectors.shape, (30, helmet.FEATURE_SIZE))
            self.assertEqual(model.report["validation_images"], 15)
            self.assertEqual(model.report["training_images"], 30)
            self.assertFalse(model.report["approved_for_operation"])
            self.assertTrue((run / "relatorio.json").is_file())
            with np.load(run / "modelo.npz", allow_pickle=False) as saved:
                self.assertEqual(saved["vectors"].shape[0], 30)

    def test_session_overlap_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            make_dataset(base)
            (base / "validacao/sessao_validacao").rename(base / "validacao/sessao_treino")
            with self.assertRaisesRegex(ValueError, "aparece no treino"):
                helmet.read_dataset(base)

    def test_duplicate_across_splits_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            make_dataset(base)
            original = next((base / "treino").rglob("*.jpg"))
            duplicate = next((base / "validacao").rglob("*.jpg"))
            duplicate.write_bytes(original.read_bytes())
            with self.assertRaisesRegex(ValueError, "idêntica"):
                helmet.read_dataset(base)

    def test_near_duplicate_imported_manually_blocks_training(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            make_dataset(base)
            original = next((base / "treino").rglob("*.jpg"))
            duplicate = next((base / "validacao").rglob("*.jpg"))
            image = cv2.imdecode(np.frombuffer(original.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            variant = np.clip(image.astype(int) + 5, 0, 255).astype(np.uint8)
            _, encoded = cv2.imencode(".jpg", variant, [cv2.IMWRITE_JPEG_QUALITY, 85])
            duplicate.write_bytes(encoded.tobytes())
            self.assertNotEqual(original.read_bytes(), duplicate.read_bytes())
            with self.assertRaises(helmet.DuplicatePhotoError):
                helmet.train_experiment(base)
            self.assertFalse((base / "resultados").exists())

    def test_false_green_blocks_green_permission(self):
        model = helmet.HelmetModel(np.eye(3), helmet.CLASSES)
        rows = [(np.eye(3)[0], label, "unused") for label in helmet.CLASSES]
        with patch.object(model, "predict_feature", return_value=helmet.Prediction("abaixada", 1, 1, "")):
            report = helmet.validation_report(model, rows)
        self.assertEqual(report["false_green"], 2)
        self.assertFalse(report["green_enabled"])

    def test_green_requires_time_and_distinct_frames(self):
        gate = helmet.SignalGate()
        self.assertEqual(gate.update("abaixada", 10, now=10, green_enabled=True), "amber")
        for _ in range(6):
            self.assertEqual(gate.update("abaixada", 10, now=10.1, green_enabled=True), "amber")
        self.assertEqual(gate.update("abaixada", 10.3, now=10.3, green_enabled=True), "amber")
        self.assertEqual(gate.update("abaixada", 10.6, now=10.6, green_enabled=True), "green")
        self.assertEqual(gate.update("levantada", 10.7, now=10.7, green_enabled=True), "red")

    def test_stale_missing_or_unknown_evidence_removes_green(self):
        for label, timestamp, now in (("abaixada", 10.6, 12), (None, None, 11),
                                      ("inconclusiva", 10.7, 10.7)):
            gate = helmet.SignalGate()
            for t in (10, 10.3, 10.6):
                gate.update("abaixada", t, now=t, green_enabled=True)
            self.assertEqual(gate.color, "green")
            self.assertEqual(gate.update(label, timestamp, now=now, green_enabled=True), "amber")

    def test_failed_validation_never_allows_green(self):
        gate = helmet.SignalGate()
        for t in (10, 10.3, 10.6, 11, 12):
            self.assertEqual(gate.update("abaixada", t, now=t, green_enabled=False), "amber")

    def test_gap_or_backward_time_restarts_confirmation(self):
        gate = helmet.SignalGate()
        for t in (10, 10.3, 10.6):
            gate.update("abaixada", t, now=t, green_enabled=True)
        self.assertEqual(gate.update("abaixada", 12, now=12, green_enabled=True), "amber")
        self.assertEqual(gate.hits, 1)
        self.assertEqual(gate.update("abaixada", 11.9, now=12, green_enabled=True), "amber")
        self.assertEqual(gate.hits, 0)


if __name__ == "__main__":
    unittest.main()



