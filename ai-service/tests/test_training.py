"""Fixtures sintéticas exclusivamente para testar preparação; não treinam IA."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

from app.training.catalog import catalogs, initialize, specification
from app.training.dataset import validate
from app.training.registry import read_registry, register
from app.training.runner import evaluate, train

ROOT = Path(__file__).resolve().parents[2]


class DatasetFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="tecnosolda-training-test-")
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        initialize(self.workspace)
        self.rows = []

    def image(self, relative, split, number, group=None):
        target = self.workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # Pixels artificiais de teste; jamais publicados como captura real.
        array = np.full((32, 32, 3), number, dtype=np.uint8)
        ok, encoded = cv2.imencode(".png", array)
        assert ok
        target.write_bytes(encoded.tobytes())
        self.rows.append({"image": relative, "group_id": group or f"session-{split}",
                          "authorization_ref": "TEST_FIXTURE_NOT_REAL_PERSON"})
        self.manifest()
        return target

    def manifest(self):
        with (self.workspace / "provenance.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=("image", "group_id", "authorization_ref"))
            writer.writeheader()
            writer.writerows(self.rows)

    def detection(self):
        for number, split in enumerate(("train", "val", "test"), 1):
            self.image(f"detection/images/{split}/image.png", split, number)
            (self.workspace / "detection" / "labels" / split / "image.txt").write_text(
                "\n".join(f"{class_id} 0.5 0.5 0.2 0.2" for class_id in range(5)), encoding="utf-8")

    def classification(self):
        number = 20
        for split in ("train", "val", "test"):
            for name in specification("classify")["classes"]:
                number += 1
                self.image(f"helmet/{split}/{name}/image.png", split, number)


class DatasetTests(DatasetFixture):
    def test_catalog_has_exactly_four_required_epis_and_distinct_glove_checks(self):
        catalog = catalogs()
        self.assertEqual(len(catalog["epis"]), 4)
        self.assertTrue(all(epi["required"] for epi in catalog["epis"]))
        self.assertEqual(catalog["epis"][2]["checks"], ["mao_esquerda", "mao_direita"])
        self.assertEqual(len(specification("detect")["classes"]), 5)

    def test_init_preserves_existing_manifest_and_registry(self):
        marker = self.workspace / "registry.json"
        marker.write_text('{"schema_version":1,"models":[{"id":"keep"}]}', encoding="utf-8")
        initialize(self.workspace)
        self.assertEqual(read_registry(self.workspace)["models"][0]["id"], "keep")
        self.assertFalse(list((self.workspace / "detection" / "images").rglob("*.png")))

    def test_empty_dataset_is_not_ready(self):
        report = validate(self.workspace, "detect")
        self.assertFalse(report.valid)
        self.assertIn("nenhuma imagem", " ".join(report.errors))

    def test_valid_detection_and_fingerprint_changes_with_label(self):
        self.detection()
        initial = validate(self.workspace, "detect")
        self.assertTrue(initial.valid, initial.errors)
        label = self.workspace / "detection/labels/train/image.txt"
        label.write_text(label.read_text() + "\n0 0.4 0.4 0.1 0.1", encoding="utf-8")
        changed = validate(self.workspace, "detect")
        self.assertTrue(changed.valid, changed.errors)
        self.assertNotEqual(initial.fingerprint, changed.fingerprint)

    def test_missing_label_is_not_silently_background(self):
        self.detection()
        (self.workspace / "detection/labels/train/image.txt").unlink()
        self.assertFalse(validate(self.workspace, "detect").valid)

    def test_explicit_empty_label_is_background(self):
        self.detection()
        self.image("detection/images/train/empty.png", "train", 8)
        (self.workspace / "detection/labels/train/empty.txt").write_text("", encoding="utf-8")
        report = validate(self.workspace, "detect")
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.backgrounds, 1)

    def test_rejects_bad_coordinates_and_classes(self):
        self.detection()
        for line in ("5 0.5 0.5 0.2 0.2", "1 nan 0.5 0.2 0.2",
                     "1 0.01 0.5 0.5 0.2", "1 0.5 0.5 0 0.2", "1 2 3"):
            with self.subTest(line=line):
                label = self.workspace / "detection/labels/train/image.txt"
                label.write_text(line, encoding="utf-8")
                self.assertFalse(validate(self.workspace, "detect").valid)

    def test_same_recording_cannot_span_splits(self):
        self.detection()
        self.rows[1]["group_id"] = self.rows[0]["group_id"]
        self.manifest()
        report = validate(self.workspace, "detect")
        self.assertIn("Vazamento entre splits", " ".join(report.errors))

    def test_duplicate_image_cannot_span_splits(self):
        self.detection()
        original = self.workspace / "detection/images/train/image.png"
        (self.workspace / "detection/images/test/image.png").write_bytes(original.read_bytes())
        self.assertIn("duplicada entre splits", " ".join(validate(self.workspace, "detect").errors))

    def test_unlisted_or_unauthorized_image_is_rejected(self):
        self.detection()
        self.rows[0]["authorization_ref"] = ""
        self.manifest()
        self.assertFalse(validate(self.workspace, "detect").valid)

    def test_corrupted_image_is_rejected(self):
        self.detection()
        (self.workspace / "detection/images/train/image.png").write_bytes(b"not an image")
        self.assertFalse(validate(self.workspace, "detect").valid)

    def test_orphan_labels_are_rejected(self):
        self.detection()
        (self.workspace / "detection/labels/train/orphan.txt").write_text("", encoding="utf-8")
        self.assertIn("sem imagem", " ".join(validate(self.workspace, "detect").errors))

    def test_classification_has_three_classes_in_each_split(self):
        self.classification()
        report = validate(self.workspace, "classify")
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.images, {"train": 3, "val": 3, "test": 3})

    def test_groups_cannot_leak_between_detector_and_classifier(self):
        self.detection()
        self.classification()
        self.rows[-1]["group_id"] = "session-train"
        self.manifest()
        self.assertFalse(validate(self.workspace, "detect").valid)
        self.assertFalse(validate(self.workspace, "classify").valid)

    def test_manifest_cannot_escape_workspace(self):
        self.detection()
        self.rows[0]["image"] = "../outside.png"
        self.manifest()
        self.assertFalse(validate(self.workspace, "detect").valid)


class RunnerTests(DatasetFixture):
    def fake_runtime(self, task="detect"):
        test = self
        class FakeModel:
            def __init__(self, path):
                self.task = task
                self.names = dict(enumerate(specification(task)["classes"]))
                self.trainer = None

            def train(self, **kwargs):
                test.training_arguments = kwargs
                output = Path(kwargs["project"]) / kwargs["name"]
                (output / "weights").mkdir(parents=True)
                (output / "weights/best.pt").write_bytes(b"TEST_ONLY_NOT_A_MODEL")
                self.trainer = SimpleNamespace(save_dir=output)

            def val(self, **kwargs):
                test.evaluation_arguments = kwargs
                return SimpleNamespace(results_dict={"fixture_metric": 0.5},
                                       summary=lambda: [{"class": "test-fixture", "metric": 0.5}])
        return FakeModel, SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))

    def test_invalid_dataset_never_imports_or_downloads_yolo(self):
        with patch("app.training.runner.runtime_dependencies") as loader:
            with self.assertRaises(ValueError):
                train(self.workspace, "detect")
            loader.assert_not_called()
        self.assertEqual(read_registry(self.workspace)["models"], [])

    def test_dry_run_never_trains_even_with_valid_data(self):
        self.detection()
        with patch("app.training.runner.runtime_dependencies") as loader:
            result = train(self.workspace, "detect", dry_run=True)
            loader.assert_not_called()
        self.assertTrue(result["validation"]["valid"])
        self.assertFalse(result["training_started"])
        self.assertEqual(list((self.workspace / "runs").iterdir()), [])

    def test_recorded_model_is_not_approved_or_activated(self):
        self.detection()
        with patch("app.training.runner.runtime_dependencies", return_value=self.fake_runtime()):
            record = train(self.workspace, "detect", epochs=1)
        self.assertEqual(record["status"], "TREINADO_NAO_VALIDADO")
        self.assertFalse(record["approved"])
        self.assertEqual(self.training_arguments["epochs"], 1)
        self.assertEqual(len(read_registry(self.workspace)["models"]), 1)
        self.assertTrue((self.workspace / record["weights"]).exists())

    def test_failed_training_records_failure_without_registering(self):
        self.detection()
        FakeModel, torch = self.fake_runtime()
        with patch.object(FakeModel, "train", side_effect=RuntimeError("test failure")):
            with patch("app.training.runner.runtime_dependencies", return_value=(FakeModel, torch)):
                with self.assertRaises(RuntimeError):
                    train(self.workspace, "detect")
        run = next((self.workspace / "runs").glob("*/run.json"))
        self.assertEqual(json.loads(run.read_text())["status"], "FALHOU")
        self.assertEqual(read_registry(self.workspace)["models"], [])

    def test_evaluation_uses_test_split_without_approval(self):
        self.detection()
        with patch("app.training.runner.runtime_dependencies", return_value=self.fake_runtime()):
            record = train(self.workspace, "detect", epochs=1)
            result = evaluate(self.workspace, record["id"])
        self.assertEqual(self.evaluation_arguments["split"], "test")
        self.assertFalse(result["approved"])
        self.assertEqual(read_registry(self.workspace)["models"][0]["status"], "AVALIADO_AGUARDANDO_REVISAO")

    def test_tampered_weights_or_dataset_block_evaluation(self):
        self.detection()
        with patch("app.training.runner.runtime_dependencies", return_value=self.fake_runtime()):
            record = train(self.workspace, "detect", epochs=1)
        weights = self.workspace / record["weights"]
        weights.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            evaluate(self.workspace, record["id"])

    def test_dataset_change_after_training_blocks_evaluation(self):
        self.detection()
        with patch("app.training.runner.runtime_dependencies", return_value=self.fake_runtime()):
            record = train(self.workspace, "detect", epochs=1)
        label = self.workspace / "detection/labels/test/image.txt"
        label.write_text(label.read_text() + "\n0 0.5 0.5 0.1 0.1", encoding="utf-8")
        with self.assertRaises(ValueError):
            evaluate(self.workspace, record["id"])

    def test_evaluation_regenerates_config_from_validated_workspace(self):
        self.detection()
        with patch("app.training.runner.runtime_dependencies", return_value=self.fake_runtime()):
            record = train(self.workspace, "detect", epochs=1)
            config = (self.workspace / record["run"]).parent / "data.yaml"
            config.write_text('{"path":"untrusted-external-path"}', encoding="utf-8")
            evaluate(self.workspace, record["id"])
        self.assertEqual(json.loads(config.read_text())["path"],
                         (self.workspace / "detection").resolve().as_posix())

    def test_duplicate_registration_does_not_overwrite(self):
        register(self.workspace, {"id": "test"})
        with self.assertRaises(ValueError):
            register(self.workspace, {"id": "test"})
        self.assertEqual(len(read_registry(self.workspace)["models"]), 1)

    def test_classifier_uses_directory_not_detection_yaml(self):
        self.classification()
        with patch("app.training.runner.runtime_dependencies", return_value=self.fake_runtime("classify")):
            train(self.workspace, "classify", epochs=1)
        self.assertEqual(Path(self.training_arguments["data"]), (self.workspace / "helmet").resolve())

    def test_cli_validation_has_nonzero_exit_for_empty_dataset(self):
        result = subprocess.run([sys.executable, str(ROOT / "ai-service/training.py"),
                                 "validate", "--workspace", str(self.workspace)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
