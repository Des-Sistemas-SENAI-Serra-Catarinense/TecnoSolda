"""Marcações sobre a imagem, com imagens artificiais."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import numpy as np

import color_presence as presence
import overlay


def scene(glove, apron):
    image = np.full((240, 320, 3), 128, np.uint8)
    if glove:
        image[100:180, 200:290] = (60, 130, 190)
    if apron:
        image[:, 20:90] = (200, 90, 60)
    return image


class OverlayTests(unittest.TestCase):
    def test_largest_box_uses_biggest_region_and_ignores_noise(self):
        mask = np.zeros((100, 200), np.uint8)
        mask[10:60, 20:120] = 255
        mask[80:84, 150:154] = 255
        self.assertEqual(overlay.largest_box(mask), (0.1, 0.1, 0.6, 0.6))
        self.assertIsNone(overlay.largest_box(np.zeros((100, 200), np.uint8)))
        tiny = np.zeros((100, 200), np.uint8)
        tiny[0:4, 0:4] = 255
        self.assertIsNone(overlay.largest_box(tiny))

    def test_draw_regions_changes_only_the_marked_area(self):
        image = np.zeros((100, 200, 3), np.uint8)
        overlay.draw_regions(image, (overlay.Region("luva", "Luva", (0.25, 0.25, 0.75, 0.75)),))
        self.assertTrue(image.any())
        self.assertFalse(image[80:].any())

    def test_item_regions_follow_where_the_colors_are(self):
        detector = presence.CombinationDetector(("luva", "avental"))
        for key in detector.keys:
            for _ in range(3):
                detector.add_sample(key, scene(key[0] == "com", key[1] == "com"))
        result = detector.predict(scene(True, True))
        glove, = result["luva"].regions
        apron, = result["avental"].regions
        self.assertAlmostEqual(glove.box[0], 0.62, delta=0.04)
        self.assertAlmostEqual(glove.box[3], 0.75, delta=0.05)
        self.assertAlmostEqual(apron.box[2], 0.28, delta=0.04)
        # Sem o item não há o que marcar.
        self.assertEqual(detector.predict(scene(False, True))["luva"].regions, ())


if __name__ == "__main__":
    unittest.main()
