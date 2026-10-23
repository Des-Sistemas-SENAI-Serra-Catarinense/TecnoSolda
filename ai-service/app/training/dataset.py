import csv
from dataclasses import asdict, dataclass, field
import hashlib
import math
from pathlib import Path

from .catalog import SPLITS, dataset_directory, specification

EXTENSIONS = {".jpg", ".jpeg", ".png"}


@dataclass
class Report:
    task: str
    valid: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    images: dict[str, int] = field(default_factory=dict)
    instances: dict[str, dict[str, int]] = field(default_factory=dict)
    backgrounds: int = 0
    fingerprint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def provenance(workspace: Path, report: Report) -> dict[str, dict]:
    manifest = workspace / "provenance.csv"
    if not manifest.is_file():
        report.errors.append("Falta provenance.csv: registre gravação/grupo e referência de autorização.")
        return {}
    entries: dict[str, dict] = {}
    groups: dict[str, str] = {}
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or []) != {"image", "group_id", "authorization_ref"}:
            report.errors.append("Cabeçalho esperado: image,group_id,authorization_ref.")
            return {}
        for line, row in enumerate(reader, 2):
            if None in row or any(not str(row.get(key) or "").strip()
                                  for key in ("image", "group_id", "authorization_ref")):
                report.errors.append(f"provenance.csv linha {line}: campos ausentes/inválidos.")
                continue
            image = row["image"].strip().replace("\\", "/")
            parts = image.split("/")
            if (Path(image).is_absolute() or ".." in parts or ":" in image or
                    not (workspace / image).resolve().is_relative_to(workspace.resolve())):
                report.errors.append(f"provenance.csv linha {line}: caminho fora do dataset.")
                continue
            if len(parts) >= 4 and parts[:2] == ["detection", "images"]:
                split = parts[2]
            elif len(parts) >= 4 and parts[0] == "helmet":
                split = parts[1]
            else:
                report.errors.append(f"provenance.csv linha {line}: estrutura de imagem inválida.")
                continue
            if split not in SPLITS or not (workspace / image).is_file():
                report.errors.append(f"provenance.csv linha {line}: imagem ou split inexistente.")
                continue
            key = image.casefold()
            if key in entries:
                report.errors.append(f"Origem duplicada: {image}.")
            group = row["group_id"].strip()
            if group in groups and groups[group] != split:
                report.errors.append(f"Vazamento entre splits no grupo {group}.")
            groups[group] = split
            entries[key] = {"group": group, "authorization_ref": row["authorization_ref"].strip()}
    return entries


def validate(workspace: Path, task: str) -> Report:
    workspace = workspace.resolve()
    report = Report(task)
    root = dataset_directory(workspace, task)
    names = specification(task)["classes"]
    origins = provenance(workspace, report)
    fingerprint = hashlib.sha256()
    fingerprint.update(task.encode())
    fingerprint.update("|".join(names).encode())
    manifest = workspace / "provenance.csv"
    if manifest.is_file():
        fingerprint.update(manifest.read_bytes())
    seen_content: dict[str, tuple[str, str]] = {}
    all_labels: set[Path] = set()
    try:
        import cv2
        import numpy as np
    except ImportError:
        cv2 = np = None
        report.errors.append("Validação de imagens requer OpenCV/NumPy: instale requirements.txt.")

    for split in SPLITS:
        image_root = root / "images" / split if task == "detect" else root / split
        images = sorted(path for path in image_root.rglob("*")
                        if path.is_file() and path.suffix.lower() in EXTENSIONS) if image_root.is_dir() else []
        report.images[split] = len(images)
        report.instances[split] = dict.fromkeys(names, 0)
        if not images:
            report.errors.append(f"{split}: nenhuma imagem JPG/PNG encontrada.")
        stems: set[str] = set()
        for image in images:
            relative = image.relative_to(workspace).as_posix()
            if not image.resolve().is_relative_to(workspace):
                report.errors.append(f"Imagem aponta para fora do workspace: {relative}.")
                continue
            origin = origins.get(relative.casefold())
            if origin is None:
                report.errors.append(f"Imagem sem grupo/autorização: {relative}.")
            digest = sha256(image)
            fingerprint.update(relative.encode())
            fingerprint.update(digest.encode())
            if digest in seen_content:
                other_split, other_image = seen_content[digest]
                if other_split != split:
                    report.errors.append(f"Imagem duplicada entre splits: {relative} / {other_image}.")
                else:
                    report.warnings.append(f"Imagem idêntica repetida: {relative}.")
            seen_content[digest] = split, relative
            if cv2 is not None:
                try:
                    decoded = cv2.imdecode(np.frombuffer(image.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
                    if decoded is None or min(decoded.shape[:2]) < 16:
                        report.errors.append(f"Imagem ilegível ou menor que 16 pixels: {relative}.")
                except Exception:
                    report.errors.append(f"Falha de decodificação: {relative}.")

            if task == "classify":
                parts = image.relative_to(image_root).parts
                if len(parts) != 2 or parts[0] not in names:
                    report.errors.append(f"Pasta de classe inválida: {relative}.")
                else:
                    report.instances[split][parts[0]] += 1
                continue
            relative_image = image.relative_to(image_root)
            stem = relative_image.with_suffix("").as_posix().casefold()
            if stem in stems:
                report.errors.append(f"Imagens compartilham a mesma anotação: {relative}.")
            stems.add(stem)
            label = root / "labels" / split / relative_image.with_suffix(".txt")
            all_labels.add(label)
            if not label.is_file() or not label.resolve().is_relative_to(workspace):
                report.errors.append(f"Anotação ausente/inválida: {relative_image.with_suffix('.txt')}.")
                continue
            fingerprint.update(label.read_bytes())
            try:
                lines = label.read_text(encoding="utf-8-sig").splitlines()
            except UnicodeError:
                report.errors.append(f"Anotação não UTF-8: {label.name}.")
                continue
            if not any(line.strip() for line in lines):
                report.backgrounds += 1
            for number, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                values = line.split()
                try:
                    if len(values) != 5:
                        raise ValueError
                    class_id = int(values[0])
                    x, y, width, height = map(float, values[1:])
                    if not 0 <= class_id < len(names):
                        raise ValueError
                    if not all(math.isfinite(v) for v in (x, y, width, height)):
                        raise ValueError
                    if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
                        raise ValueError
                    if min(x - width / 2, y - height / 2) < -1e-6 or max(x + width / 2, y + height / 2) > 1 + 1e-6:
                        raise ValueError
                    report.instances[split][names[class_id]] += 1
                except ValueError:
                    report.errors.append(f"{label.relative_to(workspace)}:{number}: classe ou caixa YOLO inválida.")
        for name, count in report.instances[split].items():
            if not count:
                report.errors.append(f"{split}: falta exemplo da classe {name}.")

    if task == "detect":
        for label in (root / "labels").rglob("*.txt"):
            if label not in all_labels:
                report.errors.append(f"Anotação sem imagem correspondente: {label.relative_to(workspace)}.")
    report.warnings.append("Contagens não comprovam qualidade; revise rótulos, quase duplicatas e cenários da oficina.")
    report.fingerprint = fingerprint.hexdigest()
    report.valid = not report.errors
    return report
