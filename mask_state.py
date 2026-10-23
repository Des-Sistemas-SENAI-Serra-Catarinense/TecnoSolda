"""Decide se a máscara está levantada ou abaixada, sem treino e sem fotos de exemplo.

Regra: rosto visível na imagem da câmera = máscara levantada; rosto coberto = abaixada.
O rosto conta como visível se o detector do OpenCV o encontra ou se há pele
suficiente na região central (cobre rosto inclinado, que o detector perde).
Não aciona luz, relé ou GPIO e não autoriza soldagem.
"""
import cv2

from helmet_experiment import Prediction
from overlay import Region, largest_box

SKIN_MIN = 0.12  # fração mínima de pixels de pele na região central
CENTER = (0.15, 0.2, 0.85, 0.8)  # esquerda, topo, direita, base da região central


class FaceMaskDetector:
    def __init__(self):
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.cascade = cv2.CascadeClassifier(path)
        if self.cascade.empty():
            raise RuntimeError(f"Detector de rosto do OpenCV não encontrado: {path}")

    def skin_mask(self, image):
        """Máscara de pele da região central e a fração de pixels de pele nela."""
        height, width = image.shape[:2]
        left, top, right, bottom = CENTER
        center = image[int(height * top):int(height * bottom), int(width * left):int(width * right)]
        ycrcb = cv2.cvtColor(center, cv2.COLOR_BGR2YCrCb)
        mask = cv2.inRange(ycrcb, (0, 135, 85), (255, 180, 135))
        return mask, float(mask.mean()) / 255

    def skin_fraction(self, image):
        return self.skin_mask(image)[1]

    def faces(self, image):
        gray = cv2.equalizeHist(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
        minimum = max(24, int(min(gray.shape[:2]) * 0.18))
        return self.cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4,
                                             minSize=(minimum, minimum))

    def face_found(self, image):
        return len(self.faces(image)) > 0

    def predict(self, image):
        height, width = image.shape[:2]
        mask, skin = self.skin_mask(image)
        faces = self.faces(image)
        regions = [Region("mascara", "Rosto", (x / width, y / height, (x + w) / width, (y + h) / height))
                   for x, y, w, h in faces]
        box = largest_box(mask) if skin >= SKIN_MIN else None
        if box is not None:
            left, top, right, bottom = CENTER
            scale_x, scale_y = right - left, bottom - top
            regions.append(Region("mascara", "Pele", (left + box[0] * scale_x, top + box[1] * scale_y,
                                                       left + box[2] * scale_x, top + box[3] * scale_y)))
        regions = tuple(regions)
        if skin >= SKIN_MIN or len(faces) > 0:
            return Prediction("levantada", skin, 0.0,
                              f"Rosto visível (pele {skin:.0%}): máscara levantada.", regions)
        return Prediction("abaixada", skin, 0.0, f"Rosto coberto (pele {skin:.0%}): máscara abaixada.")
