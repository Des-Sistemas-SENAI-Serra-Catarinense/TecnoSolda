import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "config"
DEFAULT_WORKSPACE = Path(__file__).resolve().parents[2] / "datasets" / "local"
SPLITS = ("train", "val", "test")


def catalogs() -> dict:
    epis = json.loads((CONFIG / "epis.json").read_text(encoding="utf-8-sig"))
    models = json.loads((CONFIG / "modelos.json").read_text(encoding="utf-8-sig"))
    return {"epis": epis["epis"], "models": models["models"]}


def specification(task: str) -> dict:
    return next(model for model in catalogs()["models"] if model["task"] == task)


def dataset_directory(workspace: Path, task: str) -> Path:
    return workspace / ("detection" if task == "detect" else "helmet")


def dataset_config(workspace: Path) -> dict:
    return {
        "path": dataset_directory(workspace, "detect").resolve().as_posix(),
        "train": "images/train", "val": "images/val", "test": "images/test",
        "names": dict(enumerate(specification("detect")["classes"])),
    }


def initialize(workspace: Path) -> None:
    """Cria diretórios e templates ausentes; nunca sobrescreve anotações existentes."""
    workspace.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        for kind in ("images", "labels"):
            (workspace / "detection" / kind / split).mkdir(parents=True, exist_ok=True)
        for name in specification("classify")["classes"]:
            (workspace / "helmet" / split / name).mkdir(parents=True, exist_ok=True)
    (workspace / "runs").mkdir(exist_ok=True)
    (workspace / "base_weights").mkdir(exist_ok=True)
    templates = {
        workspace / "provenance.csv": "image,group_id,authorization_ref\n",
        workspace / "registry.json": json.dumps({"schema_version": 1, "models": []}, indent=2) + "\n",
        workspace / "detection" / "data.yaml": json.dumps(dataset_config(workspace), ensure_ascii=False, indent=2) + "\n",
    }
    for path, content in templates.items():
        try:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(content)
        except FileExistsError:
            pass
