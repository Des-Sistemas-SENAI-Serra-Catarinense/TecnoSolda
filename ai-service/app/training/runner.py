import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
from uuid import uuid4

from .catalog import dataset_config, dataset_directory, initialize, specification
from .dataset import sha256, validate
from .registry import read_registry, register, update_evaluation, utc_now, write_json

TRACKERS = ("sync", "hub", "wandb", "mlflow", "clearml", "comet", "dvc",
            "dvclive", "neptune", "raytune", "tensorboard")


def runtime_dependencies(workspace: Path):
    # Isolar também as configurações da biblioteca, sem alterar as do dashboard.
    os.environ["YOLO_CONFIG_DIR"] = str(workspace / ".ultralytics")
    try:
        import torch
        from ultralytics import YOLO, settings
    except ImportError as error:
        raise ValueError("Instale as dependências: python -m pip install --user -r ai-service/requirements-training.txt") from error
    settings.update({key: False for key in TRACKERS if key in settings})
    return YOLO, torch


def class_names(model) -> list[str]:
    names = model.names
    return [names[key] for key in sorted(names, key=int)] if isinstance(names, dict) else list(names)


def clean_metrics(value):
    if isinstance(value, dict):
        return {str(key): clean_metrics(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [clean_metrics(item) for item in value]
    if hasattr(value, "tolist"):
        return clean_metrics(value.tolist())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise ValueError(f"Tipo de métrica não suportado: {type(value).__name__}")


def environment() -> dict:
    versions = {"python": platform.python_version()}
    for name in ("ultralytics", "torch", "numpy"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def training_plan(workspace: Path, task: str, epochs: int | None,
                  batch: int | None, device: str) -> tuple[dict, dict]:
    spec = specification(task)
    if device != "auto" and device != "cpu" and not device.isdecimal():
        raise ValueError("Dispositivo deve ser auto, cpu ou índice de GPU, por exemplo 0.")
    selected_epochs = spec["epochs"] if epochs is None else epochs
    selected_batch = spec["batch"] if batch is None else batch
    if selected_epochs < 1 or selected_batch < 1:
        raise ValueError("Épocas e batch devem ser positivos.")
    report = validate(workspace, task)
    plan = {
        "task": task, "model": spec["id"], "classes": spec["classes"],
        "base_weights": spec["base_weights"], "epochs": selected_epochs,
        "batch": selected_batch, "imgsz": spec["image_size"], "device": device,
        "workers": 0, "seed": 42, "patience": 20,
        "physical_outputs_connected": False,
    }
    return plan, report.to_dict()


def train(workspace: Path, task: str, epochs: int | None = None,
          batch: int | None = None, device: str = "auto", dry_run: bool = False) -> dict:
    workspace = workspace.resolve()
    plan, report = training_plan(workspace, task, epochs, batch, device)
    if dry_run:
        return {"plan": plan, "validation": report, "training_started": False}
    if not report["valid"]:
        raise ValueError("Dataset inválido; execute validate antes de treinar. Nenhum modelo foi carregado.")
    YOLO, torch = runtime_dependencies(workspace)
    selected_device = 0 if torch.cuda.is_available() else "cpu"
    if device != "auto":
        selected_device = device
    if selected_device != "cpu" and not torch.cuda.is_available():
        raise ValueError("GPU CUDA indisponível; use --device cpu ou configure o PyTorch.")
    initialize(workspace)
    spec = specification(task)
    model_id = f"{spec['id']}-{uuid4().hex[:12]}"
    run = workspace / "runs" / model_id
    run.mkdir()
    manifest = {
        "schema_version": 1, "id": model_id, "started_at": utc_now(),
        "status": "TREINANDO", "plan": {**plan, "device": selected_device},
        "dataset_fingerprint": report["fingerprint"], "dataset_report": report,
        "environment": environment(), "simulated": False, "approved": False,
    }
    write_json(run / "run.json", manifest)
    try:
        config = run / "data.yaml"
        # JSON é um subconjunto válido de YAML. Config gerada apenas de caminhos/classes validados.
        write_json(config, dataset_config(workspace))
        model = YOLO(str(workspace / "base_weights" / spec["base_weights"]))
        model.train(
            data=str(config) if task == "detect" else str(dataset_directory(workspace, task)),
            epochs=plan["epochs"], imgsz=plan["imgsz"], batch=plan["batch"],
            device=selected_device, workers=0, patience=20, seed=42,
            project=str(run), name="fit", exist_ok=False, plots=True,
        )
        output = Path(model.trainer.save_dir).resolve()
        weights = output / "weights" / "best.pt"
        if not weights.is_file() or not weights.resolve().is_relative_to(run):
            raise ValueError("O treinamento não gerou best.pt no diretório privado esperado.")
        if model.task != task or class_names(model) != spec["classes"]:
            raise ValueError("Classes/tarefa do modelo treinado não correspondem ao cadastro.")
        after_training = validate(workspace, task)
        if not after_training.valid or after_training.fingerprint != report["fingerprint"]:
            raise ValueError("Dataset mudou durante o treinamento; pesos não registrados.")
        record = {
            "id": model_id, "model": spec["id"], "task": task,
            "classes": spec["classes"], "status": "TREINADO_NAO_VALIDADO",
            "created_at": utc_now(), "weights": weights.relative_to(workspace).as_posix(),
            "sha256": sha256(weights), "dataset_fingerprint": report["fingerprint"],
            "run": (run / "run.json").relative_to(workspace).as_posix(),
            "environment": manifest["environment"], "approved": False,
        }
        register(workspace, record)
        manifest.update(status="TREINADO_NAO_VALIDADO", finished_at=utc_now(), weights=record["weights"],
                        sha256=record["sha256"])
        write_json(run / "run.json", manifest)
        return record
    except BaseException as error:
        manifest.update(status="INTERROMPIDO" if isinstance(error, KeyboardInterrupt) else "FALHOU",
                        finished_at=utc_now(), error_type=type(error).__name__)
        write_json(run / "run.json", manifest)
        raise


def evaluate(workspace: Path, model_id: str, device: str = "cpu") -> dict:
    workspace = workspace.resolve()
    if device != "cpu" and not device.isdecimal():
        raise ValueError("Dispositivo deve ser cpu ou índice de GPU.")
    records = read_registry(workspace)["models"]
    record = next((item for item in records if item["id"] == model_id), None)
    if record is None:
        raise ValueError("Modelo não registrado. Use registry para listar os treinamentos concluídos.")
    weights = (workspace / record["weights"]).resolve()
    if not weights.is_relative_to(workspace) or not weights.is_file() or sha256(weights) != record["sha256"]:
        raise ValueError("Pesos ausentes, fora do workspace ou alterados após o registro.")
    report = validate(workspace, record["task"])
    if not report.valid or report.fingerprint != record["dataset_fingerprint"]:
        raise ValueError("Dataset inválido ou alterado. Preserve a versão usada no treinamento.")
    YOLO, _ = runtime_dependencies(workspace)
    model = YOLO(str(weights))
    spec = specification(record["task"])
    if model.task != record["task"] or class_names(model) != spec["classes"]:
        raise ValueError("Modelo não corresponde à tarefa/classes registradas.")
    run_manifest = (workspace / record["run"]).resolve()
    if not run_manifest.is_relative_to(workspace):
        raise ValueError("Registro fora do workspace.")
    run = run_manifest.parent
    # Não confiar em caminhos editados no YAML de uma execução anterior.
    write_json(run / "data.yaml", dataset_config(workspace))
    metrics = model.val(
        data=str(run / "data.yaml") if record["task"] == "detect" else str(dataset_directory(workspace, "classify")),
        split="test", device=device, workers=0, plots=True,
        project=str(run), name="evaluation-" + uuid4().hex[:8],
    )
    evaluation = {
        "evaluated_at": utc_now(), "split": "test", "weights_sha256": record["sha256"],
        "dataset_fingerprint": report.fingerprint,
        "metrics": clean_metrics(metrics.results_dict),
        "per_class": clean_metrics(metrics.summary()),
        "approved": False,
    }
    output = run / ("evaluation-" + uuid4().hex[:8] + ".json")
    write_json(output, evaluation)
    update_evaluation(workspace, model_id, {**evaluation, "report": output.relative_to(workspace).as_posix()})
    return evaluation
