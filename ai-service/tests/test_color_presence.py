"""Fixtures artificiais de cor; não medem acurácia com luvas reais."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import numpy as np

import color_presence as presence


def patch(bgr, seed):
    rng = np.random.default_rng(seed)
    image = np.empty((120, 100, 3), np.uint8)
    image[:] = bgr
    return np.clip(image + rng.integers(-12, 12, image.shape), 0, 255).astype(np.uint8)


LEATHER = (60, 130, 190)
SKIN = (140, 160, 230)
BLUE = (200, 60, 30)


class ColorPresenceTests(unittest.TestCase):
    def calibrated(self):
        detector = presence.ColorPresenceDetector("luva")
        for seed in range(3):
            detector.add_sample("com", patch(LEATHER, seed))
            detector.add_sample("sem", patch(SKIN, seed))
        return detector

    def test_requires_both_references(self):
        detector = presence.ColorPresenceDetector("luva")
        detector.add_sample("com", patch(LEATHER, 1))
        self.assertFalse(detector.ready)
        self.assertEqual(detector.predict(patch(LEATHER, 2)).label, "inconclusiva")

    def test_nearest_reference_wins(self):
        detector = self.calibrated()
        self.assertEqual(detector.predict(patch(LEATHER, 50)).label, "com")
        self.assertEqual(detector.predict(patch(SKIN, 51)).label, "sem")

    def test_unrelated_colors_are_inconclusive(self):
        self.assertEqual(self.calibrated().predict(patch(BLUE, 52)).label, "inconclusiva")

    def test_reset_clears_references(self):
        detector = self.calibrated()
        detector.reset()
        self.assertFalse(detector.ready)
        self.assertEqual(detector.predict(patch(LEATHER, 1)).label, "inconclusiva")


COMBINATION_COLORS = {("com", "com"): (60, 130, 190), ("com", "sem"): (120, 200, 80),
                      ("sem", "com"): (200, 90, 60), ("sem", "sem"): (150, 150, 150)}


class CombinationTests(unittest.TestCase):
    def calibrated(self, skip=None):
        detector = presence.CombinationDetector(("luva", "avental"))
        for key, color in COMBINATION_COLORS.items():
            if key != skip:
                for seed in range(3):
                    detector.add_sample(key, patch(color, seed))
        return detector

    def test_needs_all_four_combinations(self):
        detector = self.calibrated(skip=("sem", "sem"))
        self.assertFalse(detector.ready)
        self.assertEqual(detector.predict(patch(COMBINATION_COLORS[("com", "com")], 9))["luva"].label,
                         "inconclusiva")

    def test_each_combination_is_recognized(self):
        detector = self.calibrated()
        self.assertTrue(detector.ready)
        for (luva, avental), color in COMBINATION_COLORS.items():
            result = detector.predict(patch(color, 40))
            self.assertEqual((result["luva"].label, result["avental"].label), (luva, avental))

    def test_unrelated_color_is_inconclusive_for_both_items(self):
        result = self.calibrated().predict(patch(BLUE, 41))
        self.assertEqual({r.label for r in result.values()}, {"inconclusiva"})

    def test_reset_clears_combinations(self):
        detector = self.calibrated()
        detector.reset()
        self.assertFalse(detector.ready)


if __name__ == "__main__":
    unittest.main()
