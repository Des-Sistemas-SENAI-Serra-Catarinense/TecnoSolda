"""Marcações sobre a imagem: mostram o que cada detector está usando para decidir.

As caixas são regiões que sustentam a decisão (rosto encontrado, pele, cor compatível
com a referência), não uma detecção de objeto treinada.
"""
from dataclasses import dataclass

import cv2

# BGR por item; cv2.putText não desenha acentos, então os textos das regiões são ASCII.
ITEM_COLORS = {"mascara": (235, 150, 40), "luva": (40, 140, 245), "avental": (200, 80, 170)}


@dataclass(frozen=True)
class Region:
    item: str  # "mascara", "luva", "avental"
    text: str
    box: tuple  # (x1, y1, x2, y2) em fração do quadro, de 0 a 1


def largest_box(mask, min_fraction=0.01):
    """Caixa (fração de 0 a 1) do maior grupo de pixels ligados da máscara, ou None."""
    height, width = mask.shape[:2]
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    count, _, stats, _ = cv2.connectedComponentsWithStats(cleaned)
    if count < 2:
        return None
    best = 1 + int(stats[1:, cv2.CC_STAT_AREA].argmax())
    x, y, w, h, area = stats[best]
    if area / (height * width) < min_fraction:
        return None
    return (float(x / width), float(y / height), float((x + w) / width), float((y + h) / height))


def draw_regions(image, regions):
    height, width = image.shape[:2]
    for region in regions:
        color = ITEM_COLORS.get(region.item, (255, 210, 60))
        x1, y1, x2, y2 = region.box
        p1, p2 = (int(x1 * width), int(y1 * height)), (int(x2 * width), int(y2 * height))
        cv2.rectangle(image, p1, p2, color, 2)
        (text_w, text_h), _ = cv2.getTextSize(region.text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        top = max(text_h + 6, p1[1])
        cv2.rectangle(image, (p1[0], top - text_h - 6), (p1[0] + text_w + 6, top), color, -1)
        cv2.putText(image, region.text, (p1[0] + 3, top - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (255, 255, 255), 1, cv2.LINE_AA)
    return image
