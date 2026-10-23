"""Filtro visual local para evitar repetição de fotos na coleta."""
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

# Limites heurísticos conservadores. Comparação em escala 0..1.
MEAN_LIMIT = 0.025
TILE_LIMIT = 0.10
COLOR_LIMIT = 0.04
EXPOSURE_LIMIT = 25 / 255
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


class DuplicatePhotoError(ValueError):
    def __init__(self, path):
        self.match = Path(path)
        super().__init__(
            f"Foto recusada: muito parecida com {path}. "
            "Varie a pose, o ângulo ou a distância antes de fotografar novamente."
        )


def image_signature(image):
    if image is None or image.size == 0:
        raise ValueError("Imagem vazia na verificação de duplicatas.")
    # Suavização e redução atenuam ruído do sensor e recompressão JPEG.
    resized = cv2.resize(image, (96, 96), interpolation=cv2.INTER_AREA)
    blurred = cv2.GaussianBlur(resized, (3, 3), 0.6)
    gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255
    color = cv2.resize(blurred, (24, 24), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    return gray, color


def visually_similar(first, second):
    left, left_color = first
    right, right_color = second
    # Permite exposição ligeiramente diferente sem ignorar mudanças de cor.
    exposure = float(np.median(left - right))
    if abs(exposure) > EXPOSURE_LIMIT:
        return False
    if float(np.mean(np.abs(left_color - right_color - exposure))) > COLOR_LIMIT:
        return False
    # Deslocamentos de até um pixel na miniatura representam pequenos movimentos.
    center = left[2:94, 2:94]
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            shifted = right[2+dy:94+dy, 2+dx:94+dx]
            difference = np.abs(center - shifted - exposure)
            if float(difference.mean()) > MEAN_LIMIT:
                continue
            # Um fundo igual não deve esconder uma mudança localizada na máscara.
            tiles = difference.reshape(4, 23, 4, 23).mean(axis=(1, 3))
            if float(tiles.max()) <= TILE_LIMIT:
                return True
    return False


def find_similar(signature, entries):
    for path, previous in entries:
        if visually_similar(signature, previous):
            return path
    return None


class DuplicateGuard:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.cache = {}

    def check(self, image):
        current = {}
        # Atualiza o índice com arquivos novos, alterados ou removidos.
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            if not path.resolve().is_relative_to(self.root):
                raise ValueError(f"Imagem fora da pasta de coleta: {path.name}")
            stat = path.stat()
            stamp = (stat.st_mtime_ns, stat.st_size)
            cached = self.cache.get(path)
            if cached is None or cached[0] != stamp:
                decoded = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
                if decoded is None:
                    raise ValueError(f"Não foi possível verificar a foto existente: {path.name}")
                cached = (stamp, image_signature(decoded))
            current[path] = cached
        self.cache = current
        match = find_similar(image_signature(image), ((path, value[1]) for path, value in current.items()))
        if match is not None:
            raise DuplicatePhotoError(match.relative_to(self.root))


@lru_cache(maxsize=4)
def guard_for(root):
    return DuplicateGuard(root)
