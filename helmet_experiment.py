"""Classificador experimental local. Não autoriza soldagem nem aciona GPIO."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4

import cv2
import numpy as np

from tirar_foto import save_photo, session_directory
from photo_duplicates import DuplicatePhotoError, find_similar, image_signature

DEFAULT_DATA = Path(__file__).resolve().parent / "ai-service/datasets/local/teste_mascara"
CLASSES = ("levantada", "abaixada", "inconclusiva")
SPLITS = ("treino", "validacao")
MIN_COUNTS = {"treino": 10, "validacao": 5}
ROI = (0.25, 0.08, 0.75, 0.80)
SIMILARITY_MIN = 0.70
MARGIN_MIN = 0.04
FRESH_SECONDS = 0.6
GREEN_SECONDS = 0.5
FEATURE_SIZE = 1764


def crop_head(frame):
    height, width = frame.shape[:2]
    left, top, right, bottom = ROI
    crop = frame[int(top * height):int(bottom * height),
                 int(left * width):int(right * width)]
    if min(crop.shape[:2]) < 32:
        raise ValueError("Imagem pequena demais para analisar a região da máscara.")
    return crop.copy()


def feature(image):
    if image is None or min(image.shape[:2]) < 32:
        raise ValueError("Recorte inválido ou menor que 32 pixels.")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
    if gray.std() < 8:
        return np.zeros(FEATURE_SIZE, dtype=np.float32)
    hog = cv2.HOGDescriptor((64, 64), (16, 16), (8, 8), (8, 8), 9)
    vector = hog.compute(gray).ravel().astype(np.float32)
    length = float(np.linalg.norm(vector))
    return vector / length if length > 1e-6 else np.zeros_like(vector)


def capture_sample(base, split, session, label, frame):
    base = Path(base).resolve()
    if split not in SPLITS or label not in CLASSES:
        raise ValueError("Grupo ou classe inválidos.")
    folder = session_directory(session, base / split)
    other = "validacao" if split == "treino" else "treino"
    if session_directory(session, base / other).exists():
        raise ValueError("Use outra sessão: a mesma sessão não pode estar no treino e na validação.")
    # A área fixa serve apenas de guia, não é uma caixa detectada por IA.
    return save_photo(crop_head(frame), folder / label, duplicate_root=base)


def counts(base):
    return {
        split: {label: len(list((Path(base) / split).glob(f"*/{label}/*.jpg")))
                for label in CLASSES}
        for split in SPLITS
    }


def read_dataset(base):
    base = Path(base).resolve()
    data = {split: [] for split in SPLITS}
    sessions = {}
    hashes = {}
    signatures = []
    fingerprint = hashlib.sha256()
    for split in SPLITS:
        for path in sorted((base / split).glob("*/*/*.jpg")):
            if not path.resolve().is_relative_to(base):
                raise ValueError("Imagem fora da pasta do teste.")
            session, label = path.parent.parent.name, path.parent.name
            if label not in CLASSES:
                raise ValueError(f"Classe desconhecida: {label}")
            session_directory(session, base / split)
            if session.casefold() in sessions and sessions[session.casefold()] != split:
                raise ValueError(f"Sessão {session} aparece no treino e na validação.")
            sessions[session.casefold()] = split
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest in hashes:
                raise ValueError(f"Foto idêntica repetida: {path.name}. Remova a duplicata antes de treinar.")
            hashes[digest] = split
            image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"Foto ilegível: {path.name}")
            signature = image_signature(image)
            match = find_similar(signature, signatures)
            if match is not None:
                raise DuplicatePhotoError(match)
            signatures.append((path.relative_to(base), signature))
            vector = feature(image)
            if label != "inconclusiva" and not vector.any():
                raise ValueError(f"Foto sem detalhes suficientes: {path.name}. Recapture com boa iluminação.")
            relative = path.relative_to(base).as_posix()
            fingerprint.update((relative + ":" + digest + "\n").encode())
            data[split].append((vector, label, relative))
        for label in CLASSES:
            amount = sum(row[1] == label for row in data[split])
            if amount < MIN_COUNTS[split]:
                raise ValueError(
                    f"{split}: faltam fotos de {label}. Há {amount}; mínimo do teste: {MIN_COUNTS[split]}."
                )
    return data, fingerprint.hexdigest()


@dataclass(frozen=True)
class Prediction:
    label: str
    similarity: float
    margin: float
    reason: str
    regions: tuple = ()  # overlay.Region que sustentam a decisão


class HelmetModel:
    def __init__(self, vectors, labels):
        self.vectors = np.asarray(vectors, dtype=np.float32)
        self.labels = np.asarray(labels)
        self.report = None

    def predict_feature(self, vector):
        if not np.isfinite(vector).all() or not vector.any():
            return Prediction("inconclusiva", 0.0, 0.0, "Imagem sem detalhes suficientes.")
        similarities = np.clip(self.vectors @ vector, 0.0, 1.0)
        scores = []
        for label in CLASSES:
            candidates = np.sort(similarities[self.labels == label])
            scores.append(float(candidates[-min(3, len(candidates)):].mean()))
        ranking = np.argsort(scores)
        winner = int(ranking[-1])
        similarity = scores[winner]
        margin = similarity - scores[int(ranking[-2])]
        if similarity < SIMILARITY_MIN or margin < MARGIN_MIN:
            return Prediction("inconclusiva", similarity, margin, "Pouca semelhança ou classes ambíguas.")
        label = CLASSES[winner]
        return Prediction(label, similarity, margin, "Comparação visual com as fotos de treino.")

    def predict(self, image):
        return self.predict_feature(feature(image))


def validation_report(model, rows):
    matrix = {label: {predicted: 0 for predicted in CLASSES} for label in CLASSES}
    for vector, expected, _ in rows:
        matrix[expected][model.predict_feature(vector).label] += 1
    recall = {label: matrix[label][label] / sum(matrix[label].values()) for label in CLASSES}
    false_green = sum(matrix[label]["abaixada"] for label in CLASSES if label != "abaixada")
    total = sum(sum(row.values()) for row in matrix.values())
    return {
        "validation_images": total,
        "accuracy": sum(matrix[label][label] for label in CLASSES) / total,
        "recall": recall,
        "confusion_matrix": matrix,
        "false_green": false_green,
        "green_enabled": false_green == 0 and all(value >= 0.80 for value in recall.values()),
    }


def train_experiment(base):
    """Usa apenas treino para construir o modelo; validação não escolhe parâmetros."""
    base = Path(base).resolve()
    data, fingerprint = read_dataset(base)
    model = HelmetModel([row[0] for row in data["treino"]], [row[1] for row in data["treino"]])
    report = validation_report(model, data["validacao"])
    report.update(
        version=1, algorithm="HOG + média dos 3 vizinhos por classe",
        classes=list(CLASSES), fingerprint=fingerprint,
        created_at=datetime.now(timezone.utc).isoformat(),
        training_images=len(data["treino"]),
        thresholds={"similarity": SIMILARITY_MIN, "margin": MARGIN_MIN},
        roi=list(ROI), approved_for_operation=False,
    )
    # Confere que a coleta não mudou durante o treinamento.
    if read_dataset(base)[1] != fingerprint:
        raise ValueError("Fotos alteradas durante o treinamento. Treine novamente.")
    run = base / "resultados" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:8])
    run.mkdir(parents=True)
    np.savez_compressed(run / "modelo.npz", vectors=model.vectors, labels=model.labels)
    (run / "relatorio.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    model.report = report
    return model, run


class SignalGate:
    """Verde exige quadros distintos e estáveis; qualquer outra evidência o retira."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.started = None
        self.last_at = None
        self.hits = 0
        self.color = "amber"

    def update(self, label, captured_at, now=None, green_enabled=False):
        now = time.monotonic() if now is None else now
        if (label not in CLASSES or captured_at is None or
                not np.isfinite(captured_at) or not np.isfinite(now) or
                now - captured_at > FRESH_SECONDS or captured_at > now):
            self.reset()
            return "amber"
        if label != "abaixada" or not green_enabled:
            self.reset()
            self.color = "red" if label == "levantada" else "amber"
            return self.color
        if self.last_at is not None and captured_at < self.last_at:
            self.reset()
            return "amber"
        if self.last_at == captured_at:
            return self.color
        if self.last_at is None or captured_at - self.last_at > FRESH_SECONDS:
            self.started = captured_at
            self.hits = 0
        self.last_at = captured_at
        self.hits += 1
        self.color = "green" if self.hits >= 3 and captured_at - self.started >= GREEN_SECONDS else "amber"
        return self.color


