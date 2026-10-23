from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                             encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def registry_lock(workspace: Path):
    lock = workspace / "registry.lock"
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink()


def read_registry(workspace: Path) -> dict:
    path = workspace / "registry.json"
    if not path.exists():
        return {"schema_version": 1, "models": []}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def register(workspace: Path, record: dict) -> None:
    with registry_lock(workspace):
        registry = read_registry(workspace)
        if any(item["id"] == record["id"] for item in registry["models"]):
            raise ValueError("ID de modelo já registrado.")
        registry["models"].append(record)
        write_json(workspace / "registry.json", registry)


def update_evaluation(workspace: Path, model_id: str, evaluation: dict) -> None:
    with registry_lock(workspace):
        registry = read_registry(workspace)
        record = next(item for item in registry["models"] if item["id"] == model_id)
        record["evaluation"] = evaluation
        record["status"] = "AVALIADO_AGUARDANDO_REVISAO"
        write_json(workspace / "registry.json", registry)
