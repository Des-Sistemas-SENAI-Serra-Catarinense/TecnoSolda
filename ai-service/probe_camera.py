"""Diagnóstico sem gravar ou exibir imagens: abre a câmera local por até 4 s."""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.live.auth import hash_password
from app.live.capture import CameraPipeline
from app.live.settings import Settings

if __name__ == "__main__":
    # Credencial descartável apenas para construir a configuração; nenhum servidor inicia.
    settings = Settings("probe", hash_password("camera-probe-no-http-server"))
    pipeline = CameraPipeline(settings)
    pipeline.start()
    try:
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            packet, problem = pipeline.latest()
            if packet:
                print(f"Câmera real disponível: {packet.width}x{packet.height}; JPEG em memória; sem gravação.")
                break
            time.sleep(0.1)
        else:
            print("Câmera real indisponível neste ambiente. Nenhum quadro substituto foi gerado.")
    finally:
        pipeline.stop()
