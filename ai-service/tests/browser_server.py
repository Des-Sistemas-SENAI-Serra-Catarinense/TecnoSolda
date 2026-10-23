"""Servidor exclusivo de QA, sem câmera e sem imagens; nunca usar em produção."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-service"))
sys.path.insert(0, str(ROOT))

import uvicorn
from app.live.auth import hash_password
from app.live.capture import CameraPipeline
from app.live.runtime import LiveRuntime
from app.live.server import create_app
from app.live.settings import Settings


class UnavailableCamera:
    def read(self):
        return None
    def close(self):
        pass


if __name__ == "__main__":
    settings = Settings(
        "browser-test", hash_password("only-for-local-browser-tests"),
        origin="http://127.0.0.1:8765", session_seconds=12,
    )
    runtime = LiveRuntime(CameraPipeline(settings, source=UnavailableCamera()))
    uvicorn.run(create_app(settings, runtime), host="127.0.0.1", port=8765,
                proxy_headers=False, access_log=False, log_level="warning")
