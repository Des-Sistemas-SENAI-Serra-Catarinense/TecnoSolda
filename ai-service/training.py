"""CLI de preparação e treinamento; usa o Python selecionado, sem ativar venv."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

from app.training.catalog import DEFAULT_WORKSPACE, catalogs, initialize
from app.training.dataset import validate
from app.training.registry import read_registry
from app.training.runner import environment, evaluate, train


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Cadastro e preparação local de modelos de EPIs.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="Mostrar os quatro EPIs e os dois modelos planejados.")
    commands.add_parser("doctor", help="Verificar o Python e as bibliotecas, sem instalar nem carregar pesos.")
    for name in ("init", "validate", "train", "evaluate", "registry"):
        command = commands.add_parser(name)
        command.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
        if name in {"validate", "train"}:
            command.add_argument("--task", choices=("detect", "classify"), default="detect")
        if name == "train":
            command.add_argument("--epochs", type=int)
            command.add_argument("--batch", type=int)
            command.add_argument("--device", default="auto")
            command.add_argument("--dry-run", action="store_true")
        if name == "evaluate":
            command.add_argument("--model-id", required=True)
            command.add_argument("--device", default="cpu")
    args = parser.parse_args()
    try:
        if args.command == "catalog":
            emit(catalogs())
        elif args.command == "doctor":
            emit({"python": sys.executable, "virtual_environment": sys.prefix != sys.base_prefix,
                  "versions": environment(), "opencv_available": importlib.util.find_spec("cv2") is not None,
                  "training_dependencies_ready": all(importlib.util.find_spec(name) is not None
                                                     for name in ("torch", "ultralytics")),
                  "note": "Não verifica GPU, não baixa pesos e não inicia treinamento."})
        elif args.command == "init":
            initialize(args.workspace.resolve())
            emit({"workspace": str(args.workspace.resolve()), "created": True,
                  "next": "Importe imagens/labels autorizados e preencha provenance.csv; nenhum dado foi fabricado."})
        elif args.command == "registry":
            emit(read_registry(args.workspace.resolve()))
        elif args.command == "validate":
            report = validate(args.workspace, args.task)
            emit(report.to_dict())
            return 0 if report.valid else 2
        elif args.command == "train":
            result = train(args.workspace, args.task, args.epochs, args.batch, args.device, args.dry_run)
            emit(result)
            return 0 if not args.dry_run or result["validation"]["valid"] else 2
        elif args.command == "evaluate":
            emit(evaluate(args.workspace, args.model_id, args.device))
        return 0
    except (ValueError, OSError, KeyError, RuntimeError, ImportError) as error:
        emit({"error": str(error), "status": "NAO_CONCLUIDO"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
