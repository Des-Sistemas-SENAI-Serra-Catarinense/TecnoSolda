from pathlib import Path
import os
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.live.server import create_app
from app.live.settings import Settings


if __name__ == "__main__":
    import uvicorn
    settings = Settings.from_env()
    origin = urlsplit(settings.origin)
    host = os.environ.get("LIVE_BIND", "127.0.0.1")
    cert, key = os.environ.get("LIVE_TLS_CERT"), os.environ.get("LIVE_TLS_KEY")
    if host not in {"127.0.0.1", "::1", "localhost"} and not (settings.secure_cookie and cert and key):
        raise SystemExit("Bind LAN exige LIVE_ORIGIN HTTPS, LIVE_TLS_CERT e LIVE_TLS_KEY.")
    if settings.secure_cookie and not (cert and key):
        raise SystemExit("Configure certificado e chave TLS para a origem HTTPS.")
    uvicorn.run(create_app(settings), host=host, port=int(os.environ.get("LIVE_PORT", origin.port or 8000)),
                ssl_certfile=cert, ssl_keyfile=key, proxy_headers=False,
                access_log=False, workers=1)
