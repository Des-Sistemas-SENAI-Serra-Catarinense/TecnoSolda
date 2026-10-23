"""Decide se um EPI (luva de raspa, avental) está presente, sem treino de modelo.

O usuário mostra a câmera com o item e sem o item (calibração ao vivo). Depois, cada
quadro é comparado, pela distribuição de cores da imagem inteira, com essas duas
referências. Não aciona luz, relé ou GPIO e não autoriza soldagem.
"""
import itertools

import cv2
import numpy as np

from helmet_experiment import Prediction
from overlay import Region, largest_box

MAX_DISTANCE = 0.55  # acima disso a imagem não lembra nenhuma referência
MIN_MARGIN = 0.05  # diferença mínima entre as duas distâncias
KINDS = ("com", "sem")
MIN_COLOR_SHARE = 0.002  # fração mínima de pixels da referência numa cor para contar
COLOR_RATIO = 0.75  # parte dessa cor que precisa vir da referência "com item"


def color_histogram(image):
    """Histogramas de luminosidade e de cor (a, b do espaço Lab), normalizados."""
    lab = cv2.cvtColor(cv2.resize(image, (96, 96), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2LAB)
    light = cv2.calcHist([lab], [0], None, [16], [0, 256]).ravel()
    chroma = cv2.calcHist([lab], [1, 2], None, [16, 16], [0, 256, 0, 256]).ravel()
    return light / light.sum(), chroma / chroma.sum()


class ColorPresenceDetector:
    def __init__(self, item):
        self.item = item  # "luva", "avental"
        self.sums = {kind: None for kind in KINDS}
        self.counts = {kind: 0 for kind in KINDS}
        self.references = {}  # substituído por inteiro; a análise lê de outra thread

    def add_sample(self, kind, image):
        if kind not in KINDS:
            raise ValueError("Referência inválida.")
        light, chroma = color_histogram(image)
        total = self.sums[kind]
        self.sums[kind] = (light, chroma) if total is None else (total[0] + light, total[1] + chroma)
        self.counts[kind] += 1
        references = dict(self.references)
        light, chroma = self.sums[kind]
        references[kind] = (light / self.counts[kind], chroma / self.counts[kind])
        self.references = references

    def reset(self):
        self.sums = {kind: None for kind in KINDS}
        self.counts = {kind: 0 for kind in KINDS}
        self.references = {}

    @property
    def ready(self):
        return all(self.counts[kind] > 0 for kind in KINDS)

    @staticmethod
    def distance(sample, reference):
        parts = [cv2.compareHist(a.astype(np.float32), b.astype(np.float32), cv2.HISTCMP_BHATTACHARYYA)
                 for a, b in zip(sample, reference)]
        return float(np.mean(parts))

    def predict(self, image):
        references = self.references
        if not all(kind in references for kind in KINDS):
            return Prediction("inconclusiva", 0.0, 0.0, f"Calibre com {self.item} e sem {self.item}.")
        sample = color_histogram(image)
        with_item = self.distance(sample, references["com"])
        without = self.distance(sample, references["sem"])
        margin = abs(with_item - without)
        label = "com" if with_item < without else "sem"
        nearest = min(with_item, without)
        info = f"distância com {self.item} {with_item:.2f} | sem {self.item} {without:.2f}"
        if nearest > MAX_DISTANCE or margin < MIN_MARGIN:
            return Prediction("inconclusiva", 1 - nearest, margin, f"Cor ambígua ou diferente das referências. {info}")
        text = f"Com {self.item}" if label == "com" else f"Sem {self.item}"
        return Prediction(label, 1 - nearest, margin, f"{text}. {info}")


class CombinationDetector:
    """Calibra cada combinação de itens (ex.: com luva + sem avental) e escolhe a mais próxima.

    Como a comparação usa a imagem inteira, calibrar combinações evita atribuir à luva
    uma mudança causada pelo avental, e vice-versa.
    """

    def __init__(self, items):
        self.items = tuple(items)
        self.keys = tuple(itertools.product(KINDS, repeat=len(self.items)))
        self.reset()

    def reset(self):
        self.sums = {key: None for key in self.keys}
        self.counts = {key: 0 for key in self.keys}
        self.references = {}  # substituído por inteiro; a análise lê de outra thread

    @property
    def ready(self):
        return all(self.counts[key] > 0 for key in self.keys)

    def add_sample(self, key, image):
        key = tuple(key)
        if key not in self.sums:
            raise ValueError("Combinação inválida.")
        light, chroma = color_histogram(image)
        total = self.sums[key]
        self.sums[key] = (light, chroma) if total is None else (total[0] + light, total[1] + chroma)
        self.counts[key] += 1
        light, chroma = self.sums[key]
        references = dict(self.references)
        references[key] = (light / self.counts[key], chroma / self.counts[key])
        self.references = references

    def locate(self, image, item):
        """Caixa (fração do quadro) das cores típicas de "com item" frente a "sem item".

        Compara, por cor, as referências com o item e sem o item: o que só aparece
        com o item é a região que sustenta a decisão. Não é detecção do objeto.
        """
        position = self.items.index(item)
        references = self.references
        groups = {kind: [references[key][1] for key in self.keys if key[position] == kind] for kind in KINDS}
        with_item = np.mean(groups["com"], axis=0).reshape(16, 16)
        without = np.mean(groups["sem"], axis=0).reshape(16, 16)
        lab = cv2.cvtColor(cv2.resize(image, (160, 120), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2LAB)
        a_bin, b_bin = lab[:, :, 1] // 16, lab[:, :, 2] // 16
        match, other = with_item[a_bin, b_bin], without[a_bin, b_bin]
        mask = ((match > MIN_COLOR_SHARE) & (match / (match + other + 1e-9) > COLOR_RATIO)).astype(np.uint8) * 255
        return largest_box(mask)

    def unknown(self, reason, score=0.0, margin=0.0):
        return {item: Prediction("inconclusiva", score, margin, reason) for item in self.items}

    def predict(self, image):
        references = self.references
        if len(references) < len(self.keys):
            return self.unknown("Calibre as quatro combinações." if len(self.items) == 2
                                else "Calibre todas as combinações.")
        sample = color_histogram(image)
        ranking = sorted((ColorPresenceDetector.distance(sample, references[key]), key) for key in self.keys)
        (nearest, best), (second_distance, second) = ranking[0], ranking[1]
        margin = second_distance - nearest
        if nearest > MAX_DISTANCE:
            return self.unknown("Cor diferente de todas as referências.", 1 - nearest, margin)
        results = {}
        for position, item in enumerate(self.items):
            # Se as duas combinações mais próximas discordam e a diferença é pequena, o item é incerto.
            if margin < MIN_MARGIN and best[position] != second[position]:
                results[item] = Prediction("inconclusiva", 1 - nearest, margin,
                                           f"Combinações parecidas; {item} indefinido.")
            else:
                label = best[position]
                text = "Com" if label == "com" else "Sem"
                regions = ()
                if label == "com":
                    box = self.locate(image, item)
                    if box is not None:
                        regions = (Region(item, f"{item.capitalize()} (cor compativel)", box),)
                results[item] = Prediction(label, 1 - nearest, margin, f"{text} {item}.", regions)
        return results
